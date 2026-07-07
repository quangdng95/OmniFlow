import threading
import webview
from server import app

PORT = 5001


def run_flask():
    app.run(host="127.0.0.1", port=PORT, threaded=True, use_reloader=False)


if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    webview.create_window("OmniFlow", f"http://127.0.0.1:{PORT}", width=720, height=1024)
    webview.start()
