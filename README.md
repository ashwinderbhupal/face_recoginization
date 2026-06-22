# Face Recognition Tool

A face recognition tool built on **InsightFace** — RetinaFace for detection and
**ArcFace** (512-dimensional embeddings) for recognition, running on ONNX Runtime.
This is a more accurate, modern successor to the classic FaceNet/dlib approach,
and it installs cleanly on Python 3.9–3.13 with **no C++ compiler required**.

## How it works

1. **Detect** faces in an image/frame (RetinaFace).
2. **Embed** each face into a 512-d vector (ArcFace).
3. **Match** the vector against enrolled people using **cosine similarity**.
   The closest person above the threshold wins; otherwise the face is `Unknown`.

## Install

```bat
setup_windows.bat
```
or:
```bash
pip install -r requirements.txt
```
The recognition models (~280 MB, `buffalo_l` pack) download automatically on first run.

## Project layout

```
face/
├── photos/              # your known people: photos/<Name>/*.jpg  (see photos/README.txt)
├── database/            # generated face_db.pkl
├── output/             # annotated result images
├── config.py           # paths, model, thresholds
├── face_engine.py      # InsightFace wrapper (detect + embed)
├── db_utils.py         # store / load / match embeddings
├── enroll.py           # build DB from the photos/ folder
├── add_face.py         # add a person from webcam / image / folder
├── recognize.py        # live webcam recognition
├── recognize_image.py  # recognize faces in a photo
├── manage_db.py        # list / remove / clear the database
└── webapp/             # FaceWatch — advanced web + desktop console
    ├── __init__.py     #   Flask application factory (create_app)
    ├── server.py       #   website entrypoint  (python webapp/server.py)
    ├── app_desktop.py  #   native desktop window (pywebview)
    ├── views.py        #   page route
    ├── core/           #   service layer
    │   ├── events.py        #   SQLite sighting store + SSE pub/sub
    │   ├── camera_manager.py#   capture + recognition + debounced logging/alerts
    │   └── gallery.py        #   per-person photo management
    ├── api/            #   REST + MJPEG video + SSE blueprint
    │   ├── __init__.py
    │   └── routes.py
    ├── static/         #   styles.css + app.js
    └── templates/index.html
```

## Usage

**Option A — enroll from photos (recommended):**
```bash
# Put images in photos/Alice/, photos/Bob/, etc. then:
python enroll.py
```

**Option B — enroll from webcam:**
```bash
python add_face.py "Alice" --save-photos      # SPACE to capture, Q when done
```

**Recognize:**
```bash
python recognize.py                 # live webcam
python recognize.py --show-age      # also overlay estimated age/sex
python recognize_image.py photo.jpg # a single image
```

## Using an IP / CCTV camera (RTSP)

Instead of a local webcam you can point the tool straight at a network camera
(e.g. a TP-Link Tapo). No OBS or virtual camera is needed — it connects to the
RTSP stream directly.

First create a **Camera Account** in the Tapo app
(*camera → Advanced Settings → Camera Account*); that username/password is what
goes in the URL, not your TP-Link login. The URL looks like:

```
rtsp://<user>:<pass>@<camera-ip>:554/stream1   # main/high quality
rtsp://<user>:<pass>@<camera-ip>:554/stream2   # sub/low quality
```

Pass it with `--source` (works for both recognition and enrollment):

```bash
python recognize.py --source rtsp://user:pass@192.168.0.24:554/stream1
python add_face.py "Alice" --source rtsp://user:pass@192.168.0.24:554/stream1
```

Or set it once via an environment variable so a plain `python recognize.py`
uses the camera (keeps the password out of the code / git):

```powershell
# Windows PowerShell
$env:FACE_RTSP_URL = "rtsp://user:pass@192.168.0.24:554/stream1"
python recognize.py
```

The default source and RTSP options (TCP transport, low buffering for
near-real-time frames) live in `config.py`. If the stream won't open, test the
exact URL in VLC first (*Media → Open Network Stream*).

**Manage:**
```bash
python manage_db.py --list
python manage_db.py --remove "Bob"
python manage_db.py --clear
```

## FaceWatch — web + desktop console

`webapp/` is a full recognition console that reuses the same engine, so results
are identical to the CLI. It runs as a **website** or a **native desktop app**
from one codebase (the desktop launcher just wraps the local web page).

```bash
pip install flask pywebview        # pywebview optional (desktop window)

# Website (opens in your browser):
python webapp/server.py            # http://127.0.0.1:5000

# Desktop app (native window; falls back to browser if pywebview is missing):
python webapp/app_desktop.py
```

### Features

- **Dashboard** — live feed with name boxes, KPIs (faces / known / 24h
  sightings / unknowns), a real-time sighting feed, and Chart.js analytics
  (sightings timeline + top people).
- **Live events (SSE)** — every recognition is pushed instantly over
  Server-Sent Events; no polling lag. Each sighting auto-saves an annotated
  snapshot.
- **Event history + analytics** — sightings are logged to a SQLite database
  (`database/events.db`) with who/when/confidence/source and a snapshot
  thumbnail; browse or clear the history.
- **People gallery** — per-person cards; open one to view photo thumbnails,
  add/delete individual photos, rename, or delete the person (DB stays in sync).
- **Alerts** — flag when an *Unknown* face appears or when specific named people
  are seen; alerts surface as a banner + toast, with a configurable re-log
  cooldown to avoid spam.
- **Camera source** — laptop webcam, Tapo CCTV (HD `stream1` / SD `stream2`), or
  a custom index/RTSP URL. Your `user:pass@ip` is stored in the browser only and
  passwords are masked everywhere in the UI.

### Architecture

A Flask **application factory** (`webapp/__init__.py`) wires two singletons —
an `EventHub` (SQLite store + SSE pub/sub) and a `CameraManager` (threaded
capture, recognition, debounced logging, snapshots, alerts) — into blueprints:
`views` (the page) and `api` (REST + MJPEG video + SSE). The photo gallery and
event logic live in `webapp/core/`. The frontend is a small dependency-free SPA
(`static/app.js` + `static/styles.css`) using Chart.js from CDN.

The first recognition request loads the model (~a few seconds), same as the CLI.

## GPU acceleration (NVIDIA)

The engine auto-detects the best available ONNX Runtime provider
(CUDA → DirectML → CPU). On an NVIDIA GPU it runs ~10× faster than CPU
(tested ~70 FPS at 640×640 on an RTX 4060 vs ~7 FPS on CPU).

To enable CUDA without a system CUDA install, the runtime libraries come from
pip wheels (see `requirements.txt`). `face_engine.py` registers their `bin`
folders on the DLL search path automatically, so no `CUDA_PATH` setup is needed.

If you only have CPU, `pip install onnxruntime` instead and lower
`DET_SIZE`/raise `INFER_EVERY` in `config.py` for smoother video.

## Tuning accuracy

- `--threshold` (default `0.40`): cosine similarity needed for a match.
  Raise it (e.g. `0.5`) to reduce false matches; lower it to catch more.
- Enroll **3–10 photos per person** across different angles and lighting.
- All thresholds and the model pack live in `config.py`. Switch
  `MODEL_NAME` to `buffalo_s` for a faster, lighter model.
