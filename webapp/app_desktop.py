"""Desktop launcher for the Face Recognition web app.

Starts the Flask app (built by the factory in webapp/__init__.py) on a
background thread and opens it in a native desktop window using pywebview.
If pywebview isn't installed, it falls back to the default web browser.

    python webapp/app_desktop.py
"""

import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

from webapp import create_app  # noqa: E402

HOST = "127.0.0.1"
PORT = 5000
URL = f"http://{HOST}:{PORT}"


def _serve():
    app = create_app()
    app.run(host=HOST, port=PORT, threaded=True, debug=False,
            use_reloader=False)


def main():
    threading.Thread(target=_serve, daemon=True).start()
    time.sleep(1.2)  # let the server bind the port

    try:
        import webview  # pywebview
    except ImportError:
        print("pywebview not installed - opening in your web browser instead.")
        print("  (for the native app window:  pip install pywebview)")
        import webbrowser
        webbrowser.open(URL)
        print(f"\nServer running at {URL}  -  press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        return

    webview.create_window("FaceWatch", URL, width=1280, height=820,
                          min_size=(980, 640))
    webview.start()


if __name__ == "__main__":
    main()
