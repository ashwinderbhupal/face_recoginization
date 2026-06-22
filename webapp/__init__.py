"""Face Recognition web app — application factory.

Wires the core services (event hub + camera manager) into a Flask app with
blueprints for the pages and the JSON/stream API.
"""

import os
import sys

from flask import Flask

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: E402
from .core.events import EventHub  # noqa: E402
from .core.camera_manager import CameraManager  # noqa: E402


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # 64 MB uploads

    hub = EventHub(config.EVENTS_DB_PATH)
    mgr = CameraManager(hub)
    app.config["HUB"] = hub
    app.config["MGR"] = mgr

    from .views import bp as views_bp
    from .api import bp as api_bp
    app.register_blueprint(views_bp)
    app.register_blueprint(api_bp)
    return app
