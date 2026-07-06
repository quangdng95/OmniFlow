"""Entry-point facade. All application code lives in backend/ - see
backend/app.py (routes), backend/classify.py (URL classification) and friends.
desktop_app.py and OmniFlow.spec rely on `server.app` staying importable here.
"""

import os

from backend.app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="127.0.0.1", port=port, threaded=True)
