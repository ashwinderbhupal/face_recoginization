"""Central configuration for the face recognition tool."""

import os

# Project paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PHOTOS_DIR = os.path.join(BASE_DIR, "photos")        # photos/<PersonName>/*.jpg
DATABASE_DIR = os.path.join(BASE_DIR, "database")
DB_PATH = os.path.join(DATABASE_DIR, "face_db.pkl")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")        # annotated images land here

# Web UI data
EVENTS_DB_PATH = os.path.join(DATABASE_DIR, "events.db")   # sighting log (SQLite)
SNAPSHOTS_DIR = os.path.join(OUTPUT_DIR, "snapshots")      # saved detection frames

# InsightFace model pack:
#   buffalo_l = RetinaFace detector + ArcFace (w600k_r50) 512-d embeddings (most accurate)
#   buffalo_s = smaller/faster, slightly less accurate
MODEL_NAME = "buffalo_l"
DET_SIZE = (640, 640)   # full quality; GPU handles it easily (drop to 320 on CPU-only)

# Which InsightFace sub-models to load. Recognition only needs detection +
# recognition; the landmark and gender/age nets are skipped for speed.
# 'genderage' is added automatically when you pass --show-age.
ALLOWED_MODULES = ["detection", "recognition"]

# Run heavy detection/recognition only every Nth frame in the live view; the
# video keeps displaying every frame with the last known boxes (smooth playback).
# 2-3 makes a high-res / network (RTSP) feed feel much smoother at almost no
# visible cost. Set to 1 for max responsiveness on a fast GPU.
INFER_EVERY = 2

# Cosine-similarity threshold for a positive match (range -1..1).
# Higher = stricter. ~0.40 is a good default for buffalo_l.
DEFAULT_THRESHOLD = 0.40

# Minimum detector confidence to consider a face at all.
MIN_DET_SCORE = 0.50

# ---------------------------------------------------------------------------
# Camera source
# ---------------------------------------------------------------------------
# The default video source used by recognize.py / add_face.py when no
# --source / --camera is given. This can be either:
#   * an integer (as a string), e.g. "0" -> local webcam index 0
#   * an RTSP/HTTP URL, e.g. an IP camera stream
#
# To use your IP camera (e.g. Tapo) WITHOUT putting the password in this file
# (and therefore in git), set an environment variable instead:
#
#   Windows (PowerShell):  $env:FACE_RTSP_URL = "rtsp://user:pass@192.168.0.24:554/stream1"
#   Windows (cmd):         set FACE_RTSP_URL=rtsp://user:pass@192.168.0.24:554/stream1
#
# FACE_RTSP_URL (if set) always wins over CAMERA_SOURCE below.
CAMERA_SOURCE = os.environ.get("FACE_RTSP_URL", "0")

# For RTSP, force TCP transport (more reliable than UDP, avoids torn frames)
# and keep buffering low so the recognised feed stays close to real time.
# This is applied by camera.py via OpenCV's FFmpeg backend.
RTSP_TRANSPORT = "tcp"
RTSP_LATENCY_MS = 200


def resolve_source(value=None):
    """Return a webcam index (int) or a stream URL (str).

    Priority: explicit ``value`` arg > FACE_RTSP_URL env var > CAMERA_SOURCE.
    A purely numeric value is treated as a local webcam index.
    """
    if value is None:
        value = CAMERA_SOURCE
    value = str(value).strip()
    return int(value) if value.isdigit() else value
