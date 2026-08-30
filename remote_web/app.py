"""remote_web's Flask app - the trust gate, Referrer-Policy header, static
frontend serving, and the mount point for every routes/*.py blueprint.

Zero changes to backend/ or the native app (spec §2-3): everything here is
new code in this one top-level folder, reusing backend/* only via plain
Python import.
"""

import sys

from flask import Flask, jsonify, request, send_from_directory

from backend import paths
from remote_web import config, ffmpeg_locator, reaper, trust
from remote_web.routes import health as health_routes

app = Flask(__name__, static_folder=paths.WEB_DIR, static_url_path="")
app.register_blueprint(trust.unlock_bp)
app.register_blueprint(health_routes.bp)


@app.before_request
def _trust_gate():
    # Blanket gate (§4.4): every /api/* route requires the signed trust
    # cookie. Everything else (/, /unlock, static assets, /health) is never
    # under /api/ at all, so no separate exemption list is needed here.
    if request.path.startswith("/api/") and not trust.is_trusted_request(request):
        return jsonify({"error": "Unlock required."}), 401


@app.after_request
def _referrer_policy(response):
    # Cheap, zero-behavioral-cost - closes off Referer-leakage of the trust
    # cookie/token entirely rather than just on /unlock (§4.1).
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/")
def index():
    return send_from_directory(paths.WEB_DIR, "index.html")


def _check_ffmpeg_at_startup():
    # Fail loud in the process log (§5.1, §7) rather than only discovering
    # an unresolvable ffmpeg the first time a download silently fails.
    resolved = ffmpeg_locator.resolve_ffmpeg_binary()
    if not resolved:
        print(
            "[remote_web] WARNING: no usable ffmpeg binary found for this machine's "
            "architecture - every video download will fail until this is fixed.",
            file=sys.stderr,
        )
    return resolved


_check_ffmpeg_at_startup()
reaper.start_background_sweeper()

if __name__ == "__main__":
    # debug=False (and therefore no reloader) is deliberate: the Werkzeug
    # reloader re-executes this module in a child process, which would run
    # every top-level startup step (this ffmpeg check, and Task 7's reaper
    # thread start) twice. launchd (spec §6 step 8) already handles
    # restart-on-crash, so the dev reloader adds no value here, only risk.
    app.run(host="127.0.0.1", port=config.PORT, debug=False)
