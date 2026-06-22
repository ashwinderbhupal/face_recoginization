"""All /api endpoints: status, source, enroll, db, events, gallery, alerts,
plus the MJPEG video feed, SSE event stream, and image serving.
"""

import queue
import time

from flask import (Response, current_app, jsonify, request,
                   send_from_directory)

import config
from db_utils import save_database

from . import bp
from ..core import gallery


def _mgr():
    return current_app.config["MGR"]


def _hub():
    return current_app.config["HUB"]


# ---- live status -------------------------------------------------------
@bp.route("/status")
def status():
    m = _mgr()
    alert = m.consume_alert()
    return jsonify({
        "source": (str(m.source).split("@")[-1] if m.source else None),
        "live": m.cap is not None,
        "fps": round(m.fps, 1),
        "faces": m.last_faces,
        "known": m.last_known,
        "threshold": m.threshold,
        "recognize_on": m.recognize_on,
        "message": m.status_msg,
        "alerts": {
            "on_unknown": m.alert_on_unknown,
            "names": sorted(m.alert_names),
            "cooldown": m.log_cooldown,
        },
        "active_alert": alert,
        "db": m.db_summary(),
        "default_source": str(config.CAMERA_SOURCE).split("@")[-1],
    })


@bp.route("/source", methods=["POST"])
def set_source():
    spec = (request.json or {}).get("source", "")
    ok, msg = _mgr().set_source(spec)
    return jsonify({"ok": ok, "message": msg})


@bp.route("/threshold", methods=["POST"])
def set_threshold():
    try:
        _mgr().set_threshold((request.json or {}).get("threshold"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "bad threshold"}), 400
    return jsonify({"ok": True, "threshold": _mgr().threshold})


@bp.route("/recognize_toggle", methods=["POST"])
def recognize_toggle():
    _mgr().set_recognize((request.json or {}).get("on", True))
    return jsonify({"ok": True, "recognize_on": _mgr().recognize_on})


@bp.route("/alerts", methods=["POST"])
def set_alerts():
    d = request.json or {}
    _mgr().set_alerts(on_unknown=d.get("on_unknown"),
                      names=d.get("names"),
                      cooldown=d.get("cooldown"))
    m = _mgr()
    return jsonify({"ok": True, "on_unknown": m.alert_on_unknown,
                    "names": sorted(m.alert_names), "cooldown": m.log_cooldown})


# ---- enrollment --------------------------------------------------------
@bp.route("/enroll/capture", methods=["POST"])
def enroll_capture():
    name = ((request.json or {}).get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "message": "name required"}), 400
    count, msg = _mgr().capture_current(name)
    return jsonify({"ok": count > 0, "message": msg, "db": _mgr().db_summary()})


@bp.route("/enroll/upload", methods=["POST"])
def enroll_upload():
    name = (request.form.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "message": "name required"}), 400
    added = 0
    for f in request.files.getlist("images"):
        added += _mgr().add_image_bytes(name, f.read())
    if added:
        save_database(_mgr().db)
    return jsonify({"ok": added > 0,
                    "message": f"added {added} face(s) for '{name}'",
                    "db": _mgr().db_summary()})


# ---- database ----------------------------------------------------------
@bp.route("/db")
def db():
    return jsonify(_mgr().db_summary())


@bp.route("/db/remove", methods=["POST"])
def db_remove():
    name = ((request.json or {}).get("name") or "").strip()
    res = gallery.delete_person(name, _mgr().db, save_database)
    _mgr().reload_db()
    return jsonify({"ok": True, "message":
                    f"removed '{name}' ({res['db_removed']} encoding(s))",
                    "db": _mgr().db_summary()})


@bp.route("/db/clear", methods=["POST"])
def db_clear():
    m = _mgr()
    m.db["names"].clear()
    m.db["embeddings"].clear()
    save_database(m.db)
    return jsonify({"ok": True, "message": "database cleared",
                    "db": m.db_summary()})


# ---- events ------------------------------------------------------------
@bp.route("/events/recent")
def events_recent():
    limit = request.args.get("limit", 50, type=int)
    return jsonify(_hub().recent(limit=min(limit, 500)))


@bp.route("/events/stats")
def events_stats():
    hours = request.args.get("hours", 24, type=int)
    return jsonify(_hub().stats(hours=hours))


@bp.route("/events/clear", methods=["POST"])
def events_clear():
    _hub().clear()
    return jsonify({"ok": True, "message": "event history cleared"})


@bp.route("/events/stream")
def events_stream():
    hub = _hub()

    def gen():
        q = hub.subscribe()
        try:
            yield "retry: 3000\n\n"
            while True:
                try:
                    data = q.get(timeout=15)
                    yield f"data: {data}\n\n"
                except queue.Empty:
                    yield ": keep-alive\n\n"
        finally:
            hub.unsubscribe(q)

    return Response(gen(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})


# ---- gallery -----------------------------------------------------------
@bp.route("/gallery")
def gallery_list():
    return jsonify(gallery.list_people(_mgr().db))


@bp.route("/gallery/<name>")
def gallery_person(name):
    return jsonify({"name": name, "photos": gallery.list_photos(name),
                    "db_count": _mgr().db["names"].count(name)})


@bp.route("/gallery/<name>/upload", methods=["POST"])
def gallery_upload(name):
    saved, enrolled = 0, 0
    for f in request.files.getlist("images"):
        data = f.read()
        try:
            gallery.add_photo_bytes(name, f.filename, data)
            saved += 1
        except ValueError:
            continue
        enrolled += _mgr().add_image_bytes(name, data)
    if enrolled:
        save_database(_mgr().db)
    return jsonify({"ok": saved > 0,
                    "message": f"saved {saved} photo(s), enrolled {enrolled} face(s)",
                    "db": _mgr().db_summary()})


@bp.route("/gallery/<name>/photo/<path:filename>", methods=["DELETE"])
def gallery_delete_photo(name, filename):
    try:
        ok = gallery.delete_photo(name, filename)
    except ValueError:
        return jsonify({"ok": False, "message": "invalid filename"}), 400
    return jsonify({"ok": ok})


@bp.route("/gallery/<name>/rename", methods=["POST"])
def gallery_rename(name):
    new = ((request.json or {}).get("new") or "").strip()
    try:
        res = gallery.rename_person(name, new, _mgr().db, save_database)
    except ValueError:
        return jsonify({"ok": False, "message": "invalid name"}), 400
    _mgr().reload_db()
    return jsonify({"ok": True, "message": f"renamed to '{new}'", **res})


@bp.route("/gallery/<name>", methods=["DELETE"])
def gallery_delete_person(name):
    res = gallery.delete_person(name, _mgr().db, save_database)
    _mgr().reload_db()
    return jsonify({"ok": True, "message": f"deleted '{name}'", **res})


# ---- media -------------------------------------------------------------
@bp.route("/video_feed")
def video_feed():
    m = _mgr()

    def gen():
        boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
        while True:
            yield boundary + m.latest_jpeg + b"\r\n"
            time.sleep(0.04)

    return Response(gen(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


@bp.route("/snapshots/<path:filename>")
def snapshot(filename):
    return send_from_directory(config.SNAPSHOTS_DIR, filename)


@bp.route("/photos/<name>/<path:filename>")
def photo(name, filename):
    try:
        d = gallery.person_dir(name)
    except ValueError:
        return ("bad name", 400)
    return send_from_directory(d, filename)
