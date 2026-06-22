"""Capture + recognition engine for the web app.

Owns the active video source in a background thread, runs detection/recognition
(reusing the project engine), and emits debounced sighting events (persisted +
snapshotted + pushed live) with optional alerts.
"""

import os
import threading
import time

import cv2
import numpy as np

import config
from camera import open_camera
from db_utils import add_embedding, load_database, recognize, save_database
from face_engine import detect_faces, largest_face


def _mask(source):
    s = str(source)
    return s.split("@")[-1] if "@" in s else s


def _placeholder(text):
    img = np.zeros((360, 640, 3), dtype=np.uint8)
    img[:] = (28, 30, 38)
    cv2.putText(img, text, (22, 188), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                (180, 188, 200), 2)
    ok, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


class CameraManager:
    def __init__(self, hub):
        self.hub = hub
        self.lock = threading.Lock()
        self.cap = None
        self.source = None
        self.threshold = config.DEFAULT_THRESHOLD
        self.max_width = 1600
        self.recognize_on = True
        self.db = load_database()

        # alerting + event debounce
        self.alert_on_unknown = False
        self.alert_names = set()
        self.log_cooldown = 8.0          # seconds between logged sightings/name
        self.save_snapshots = True
        self._last_logged = {}           # name -> ts
        self._active_alert = None        # last alert event (for UI banner)

        self.latest_jpeg = _placeholder("Camera off - pick a source to start")
        self.latest_raw = None
        self.fps = 0.0
        self.last_faces = 0
        self.last_known = 0
        self.status_msg = "idle"

        os.makedirs(config.SNAPSHOTS_DIR, exist_ok=True)
        self._stop = False
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    # ---- settings -------------------------------------------------------
    def set_threshold(self, value):
        self.threshold = float(value)

    def set_recognize(self, on):
        self.recognize_on = bool(on)

    def set_alerts(self, on_unknown=None, names=None, cooldown=None):
        if on_unknown is not None:
            self.alert_on_unknown = bool(on_unknown)
        if names is not None:
            self.alert_names = set(n for n in names if n)
        if cooldown is not None:
            self.log_cooldown = max(0.0, float(cooldown))

    def set_source(self, spec):
        with self.lock:
            if self.cap is not None:
                self.cap.release()
                self.cap = None
            self.source = None
            self.latest_raw = None
            self._last_logged.clear()

            if spec is None or str(spec).strip() == "":
                self.status_msg = "stopped"
                self.latest_jpeg = _placeholder("Camera stopped")
                return True, "stopped"

            resolved = config.resolve_source(spec)
            self.status_msg = f"opening {_mask(resolved)} ..."
            cap = open_camera(resolved)
            if cap is None:
                self.status_msg = f"could not open {_mask(resolved)}"
                self.latest_jpeg = _placeholder("Could not open source")
                return False, self.status_msg
            self.cap = cap
            self.source = resolved
            self.status_msg = f"live: {_mask(resolved)}"
            return True, self.status_msg

    # ---- main loop ------------------------------------------------------
    def _loop(self):
        frame_no = 0
        results = []
        prev = time.time()
        while not self._stop:
            with self.lock:
                cap = self.cap
            if cap is None:
                time.sleep(0.05)
                continue
            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(0.02)
                continue

            if self.max_width and frame.shape[1] > self.max_width:
                scale = self.max_width / frame.shape[1]
                frame = cv2.resize(frame, None, fx=scale, fy=scale,
                                   interpolation=cv2.INTER_AREA)
            self.latest_raw = frame.copy()
            frame_no += 1

            if self.recognize_on:
                if frame_no % max(config.INFER_EVERY, 1) == 0:
                    try:
                        results = self._analyze(frame)
                    except Exception as exc:
                        results = []
                        self.status_msg = f"recognition error: {exc}"
                    self.last_faces = len(results)
                    self.last_known = sum(int(r[2]) for r in results)
                for box, label, known, name, sim in results:
                    self._draw(frame, box, label, known)
                self._maybe_log(results, frame)

            now = time.time()
            self.fps = 0.9 * self.fps + 0.1 * (1.0 / max(now - prev, 1e-6))
            prev = now
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok:
                self.latest_jpeg = buf.tobytes()

    def _analyze(self, frame):
        out = []
        for face in detect_faces(frame):
            name, sim = recognize(face.normed_embedding, self.db,
                                  threshold=self.threshold)
            known = name != "Unknown"
            out.append((face.bbox.astype(int), f"{name} {sim:.0f}%", known,
                        name, sim))
        return out

    def _maybe_log(self, results, frame):
        now = time.time()
        for box, label, known, name, sim in results:
            last = self._last_logged.get(name, 0)
            if now - last < self.log_cooldown:
                continue
            self._last_logged[name] = now
            alert = (not known and self.alert_on_unknown) or (name in self.alert_names)
            snap = self._save_snapshot(frame, name) if self.save_snapshots else None
            event = self.hub.record(name, sim, known, alert=alert,
                                    source=_mask(self.source), snapshot=snap)
            if alert:
                self._active_alert = event

    def _save_snapshot(self, frame, name):
        safe = "".join(c if c.isalnum() else "_" for c in name)[:40] or "face"
        fname = f"{int(time.time()*1000)}_{safe}.jpg"
        path = os.path.join(config.SNAPSHOTS_DIR, fname)
        try:
            cv2.imwrite(path, frame)
            return fname
        except Exception:
            return None

    @staticmethod
    def _draw(frame, box, label, known):
        x1, y1, x2, y2 = box
        color = (0, 200, 0) if known else (40, 40, 230)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        ly = y1 - 8 if y1 > 25 else y2 + th + 8
        cv2.rectangle(frame, (x1, ly - th - 6), (x1 + tw + 6, ly + 4), color, -1)
        cv2.putText(frame, label, (x1 + 3, ly), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (255, 255, 255), 2)

    # ---- enrollment -----------------------------------------------------
    def capture_current(self, name):
        frame = None if self.latest_raw is None else self.latest_raw.copy()
        if frame is None:
            return 0, "no live frame - start a camera first"
        face = largest_face(detect_faces(frame))
        if face is None:
            return 0, "no face detected in the current frame"
        add_embedding(self.db, name, face.normed_embedding)
        save_database(self.db)
        return 1, f"captured 1 face for '{name}'"

    def add_image_bytes(self, name, data):
        arr = np.frombuffer(data, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return 0
        face = largest_face(detect_faces(img))
        if face is None:
            return 0
        add_embedding(self.db, name, face.normed_embedding)
        return 1

    def reload_db(self):
        self.db = load_database()

    # ---- db summary -----------------------------------------------------
    def db_summary(self):
        from collections import Counter
        counts = Counter(self.db["names"])
        people = [{"name": n, "count": counts[n]} for n in sorted(counts)]
        return {"people": people, "total_people": len(people),
                "total_encodings": len(self.db["names"])}

    def consume_alert(self):
        a, self._active_alert = self._active_alert, None
        return a
