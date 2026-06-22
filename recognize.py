"""
Real-time face recognition via webcam (InsightFace / ArcFace).

Usage:
    python recognize.py
    python recognize.py --threshold 0.45   # stricter matching (default 0.40)
    python recognize.py --camera 1         # different webcam index
    python recognize.py --source rtsp://user:pass@192.168.0.24:554/stream1  # IP camera
    python recognize.py --show-age         # overlay estimated age / sex

The default source comes from config.CAMERA_SOURCE / the FACE_RTSP_URL env var,
so you can also just set that env var once and run `python recognize.py`.
"""

import argparse
import sys
import time

import cv2

import config
from camera import open_camera
from db_utils import load_database, recognize
from face_engine import detect_faces, request_modules


def draw(frame, box, label, known):
    x1, y1, x2, y2 = box
    color = (0, 200, 0) if known else (0, 0, 220)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
    ly = y1 - 8 if y1 > 25 else y2 + th + 8
    cv2.rectangle(frame, (x1, ly - th - 6), (x1 + tw + 6, ly + 4), color, -1)
    cv2.putText(frame, label, (x1 + 3, ly), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)


def analyze(frame, db, threshold, show_age):
    """Run detection/recognition and return a list of (box, label, known) results."""
    results = []
    for face in detect_faces(frame):
        name, sim = recognize(face.normed_embedding, db, threshold=threshold)
        known = name != "Unknown"
        label = f"{name} {sim:.0f}%"
        if show_age and getattr(face, "age", None) is not None:
            label += f"  {face.sex} {int(face.age)}"
        results.append((face.bbox.astype(int), label, known))
    return results


def main():
    parser = argparse.ArgumentParser(description="Real-time face recognition")
    parser.add_argument("--threshold", type=float, default=config.DEFAULT_THRESHOLD,
                        help=f"Cosine match threshold (default {config.DEFAULT_THRESHOLD})")
    parser.add_argument("--camera", type=int, default=None, help="Local webcam index")
    parser.add_argument("--source", default=None,
                        help="Webcam index or stream URL (rtsp://...). "
                             "Overrides --camera. Defaults to config.CAMERA_SOURCE / "
                             "the FACE_RTSP_URL env var.")
    parser.add_argument("--show-age", action="store_true", help="Overlay age/sex estimate")
    parser.add_argument("--max-width", type=int, default=1600,
                        help="Downscale frames wider than this for display/speed "
                             "(default 1600; useful for high-res IP cameras). 0 = no scaling.")
    args = parser.parse_args()

    # Precedence: --source > --camera > configured default.
    raw_source = args.source if args.source is not None else args.camera
    source = config.resolve_source(raw_source)

    if args.show_age:
        request_modules(["genderage"])

    db = load_database()
    if not db["embeddings"]:
        print("Database is empty. Run enroll.py or add_face.py first.")
        sys.exit(1)

    print(f"Loaded {len(db['embeddings'])} encoding(s) for {len(set(db['names']))} person(s).")
    print("Press Q to quit.")

    print(f"Opening source: {source}")
    cap = open_camera(source)
    if cap is None:
        if isinstance(source, str):
            print(f"ERROR: cannot open stream {source!r}. Check the URL/credentials "
                  "(test it in VLC first), that the camera is on the same network, "
                  "and that the Tapo 'Camera Account' is set up.")
        else:
            print(f"ERROR: cannot open camera {source} (no working backend). "
                  "Check Windows Settings > Privacy > Camera, and that no other app "
                  "is using it.")
        sys.exit(1)

    cv2.namedWindow("Face Recognition", cv2.WINDOW_NORMAL)  # resizable window

    prev = time.time()
    fps = 0.0
    read_failures = 0
    frame_no = 0
    results = []  # cached (box, label, known) reused between inference frames

    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            read_failures += 1
            if read_failures > 30:
                print("ERROR: lost the camera feed.")
                break
            continue
        read_failures = 0
        frame_no += 1

        # Downscale oversized frames (e.g. a 2K IP-camera stream) so the window
        # fits the screen and detection runs faster. Boxes stay correct because
        # all work below uses this resized frame.
        if args.max_width and frame.shape[1] > args.max_width:
            scale = args.max_width / frame.shape[1]
            frame = cv2.resize(frame, None, fx=scale, fy=scale,
                               interpolation=cv2.INTER_AREA)

        # Heavy work only every Nth frame; display stays smooth in between.
        if frame_no % config.INFER_EVERY == 0:
            results = analyze(frame, db, args.threshold, args.show_age)

        known = 0
        for box, label, is_known in results:
            draw(frame, box, label, is_known)
            known += int(is_known)

        now = time.time()
        fps = 0.9 * fps + 0.1 * (1.0 / max(now - prev, 1e-6))
        prev = now

        hud = f"FPS {fps:4.1f} | faces {len(results)} | known {known} | Q=quit"
        cv2.putText(frame, hud, (10, frame.shape[0] - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

        cv2.imshow("Face Recognition", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
