import threading
import webview
from server import app

PORT = 5001


def run_flask():
    app.run(host="127.0.0.1", port=PORT, threaded=True, use_reloader=False)


if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    webview.create_window("ViDrop", f"http://127.0.0.1:{PORT}", width=720, height=1024)
    # private_mode=False: pywebview's macOS default (True) wipes the web view's
    # saved data on every launch, which erased the History tab and the language
    # choice each time the app was closed.
    webview.start(private_mode=False)
