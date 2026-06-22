"""API blueprint (JSON, MJPEG video, SSE events, media)."""

from flask import Blueprint

bp = Blueprint("api", __name__, url_prefix="/api")

from . import routes  # noqa: E402,F401  (attaches routes to bp)
