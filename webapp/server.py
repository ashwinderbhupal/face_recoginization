"""Run the Face Recognition web app (website mode).

    python webapp/server.py            # then open http://127.0.0.1:5000

This is a thin entrypoint; the app itself is built by the application factory
in webapp/__init__.py (create_app).
"""

import os
import sys
import threading
import webbrowser

# Allow running as `python webapp/server.py` (add project root to path and
# import the package by name).
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

from webapp import create_app  # noqa: E402

HOST = "127.0.0.1"
PORT = 5000


def main(host=HOST, port=PORT, open_browser=True):
    app = create_app()
    if open_browser:
        threading.Timer(1.2, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    app.run(host=host, port=port, threaded=True, debug=False)


if __name__ == "__main__":
    main()
