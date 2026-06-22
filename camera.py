"""Robust video-source opening for Windows.

Handles two kinds of source:
  * a local webcam given by integer index (flaky backends / slow warmup), and
  * a network IP-camera stream given by an RTSP/HTTP URL (e.g. Tapo CCTV).

For network streams the capture is wrapped in a background reader thread that
always keeps only the *latest* decoded frame. This is the key to low latency:
instead of pulling frames from the front of an ever-growing buffer (which makes
the feed drift seconds behind real time), consumers always get the freshest
frame, so the view stays "live".
"""

import os
import threading
import time

import cv2

import config

# Backends to try for LOCAL webcams, in order. MSMF is the Win10/11 default but
# can be flaky with some webcams; DSHOW (DirectShow) is the reliable fallback;
# ANY lets OpenCV pick.
_BACKENDS = [
    ("MSMF", cv2.CAP_MSMF),
    ("DSHOW", cv2.CAP_DSHOW),
    ("ANY", cv2.CAP_ANY),
]


def _is_url(source):
    return isinstance(source, str) and "://" in source


class LatestFrameStream:
    """Wrap a VideoCapture in a reader thread that keeps only the newest frame.

    Drop-in for the parts of cv2.VideoCapture this project uses: read(),
    isOpened(), release(). ``read()`` returns (ok, frame) just like OpenCV, but
    always the most recent frame, and never blocks on a backlog.
    """

    def __init__(self, cap):
        self._cap = cap
        self._lock = threading.Lock()
        self._frame = None
        self._ok = False
        self._seq = 0          # increments on every new frame
        self._last_read_seq = -1
        self._stopped = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while not self._stopped:
            ok, frame = self._cap.read()
            if not ok or frame is None:
                time.sleep(0.005)   # transient hiccup; keep pulling
                continue
            with self._lock:
                self._frame = frame
                self._ok = True
                self._seq += 1

    def read(self):
        with self._lock:
            if self._frame is None:
                return False, None
            self._last_read_seq = self._seq
            return self._ok, self._frame.copy()

    def is_fresh(self):
        """True if a new frame has arrived since the last read()."""
        with self._lock:
            return self._seq != self._last_read_seq

    def isOpened(self):
        return self._cap.isOpened()

    def release(self):
        self._stopped = True
        try:
            self._thread.join(timeout=1.0)
        except RuntimeError:
            pass
        self._cap.release()


def _open_stream(url, warmup_frames):
    """Open a network stream (RTSP/HTTP) via the FFmpeg backend."""
    # Ask FFmpeg to use TCP for RTSP (more reliable than the default UDP) and
    # keep latency low. Must be set before the VideoCapture is constructed.
    if url.lower().startswith("rtsp"):
        os.environ.setdefault(
            "OPENCV_FFMPEG_CAPTURE_OPTIONS",
            f"rtsp_transport;{config.RTSP_TRANSPORT}",
        )

    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        cap.release()
        return None

    # Minimise the internal buffer so frames stay close to real time
    # (best-effort: not all backends honour this).
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except cv2.error:
        pass

    # Network streams can take a moment to deliver the first decoded frame.
    for _ in range(max(warmup_frames, 30)):
        ret, frame = cap.read()
        if ret and frame is not None:
            safe = url.split("@")[-1]  # don't print credentials
            print(f"Stream opened via FFMPEG backend: {safe}")
            return LatestFrameStream(cap)   # threaded, always-fresh -> low lag
        time.sleep(0.1)

    cap.release()
    return None


def _open_webcam(index, warmup_frames):
    """Open a local webcam, trying several backends."""
    for name, backend in _BACKENDS:
        cap = cv2.VideoCapture(index, backend)
        if not cap.isOpened():
            cap.release()
            continue

        # Warm up: give the camera a moment and confirm we get a real frame.
        ok = False
        for _ in range(warmup_frames):
            ret, frame = cap.read()
            if ret and frame is not None:
                ok = True
                break
            time.sleep(0.1)

        if ok:
            print(f"Camera {index} opened via {name} backend.")
            return cap

        cap.release()

    return None


def open_camera(source=0, warmup_frames=10):
    """Open a video source and return something with read()/release().

    ``source`` may be an integer webcam index or an RTSP/HTTP URL string.
    Network streams come back wrapped so frames are always fresh (low latency).
    Returns None if the source can't be opened.
    """
    if _is_url(source):
        return _open_stream(source, warmup_frames)
    return _open_webcam(source, warmup_frames)
