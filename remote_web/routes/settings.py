"""GET/POST /api/settings, POST /api/settings/cookies.

Three very different kinds of state live behind these routes:
- `language` is remote_web's own concern, in its own small file next to
  config.STATE_FILE - in practice the frontend's actual language switch
  reads/writes localStorage directly (LanguageContext.tsx), never this
  route, but the field is kept for API-shape parity with the native app and
  in case a future frontend change starts using it.
- `playlist_limit` is deliberately proxied straight through to
  backend.config's own session file (reused unmodified) - the frontend's
  Playlist Limit control is NOT gated behind isLocal() the way Target
  Path/Cookies are (it's a real, unhidden control in remote mode), and
  backend.extraction.extract_video_info already reads playlist_limit from
  backend.config.load_session() internally, so proxying it here is what
  makes changing it from the phone actually affect real playlist
  extraction - keeping a wholly separate copy would silently do nothing.
- `cookies_path`/`cookies_status` (new, spec:
  docs/superpowers/specs/2026-08-30-remote-web-cloud-portability-design.md
  §2.2): a headless Linux cloud deployment has no browser/Keychain to
  auto-extract Instagram/Threads cookies from the way the native app does,
  so this exposes a manual cookies.txt upload instead. The uploaded file is
  wired into backend.config's EXISTING cookies_path mechanism (reused
  unmodified) - backend.cookies.instagram_cookiefile_candidates() and every
  Instagram/Threads resolver in remote_web/routes/media.py already consult
  backend.config.get_cookies_path() first, so nothing else needs to change
  for an uploaded cookies file to actually take effect.

`path`/`browser` are deliberately NOT part of this response at all - the
frontend never reads or writes them in remote mode (that section is hidden
behind isLocal(), see frontend/src/pages/SettingsPage.tsx).
"""

import json
import os

from flask import Blueprint, jsonify, request

from backend import config as backend_config
from remote_web import config

bp = Blueprint("settings", __name__)

_DEFAULT_LANGUAGE = "en"
# Deliberately NOT under config.TEMP_ROOT - reaper.py's mtime-based sweep
# (original design spec §5.4) must never treat this as an orphaned job
# directory and delete a live credential.
_COOKIES_FILE = os.path.join(os.path.dirname(config.STATE_FILE), ".manual_cookies.txt")
_MAX_COOKIES_FILE_BYTES = 64 * 1024


def _get_settings_file():
    """Compute dynamically so monkeypatched config.STATE_FILE is used in tests."""
    return os.path.join(os.path.dirname(config.STATE_FILE), "settings.json")


def _load_language():
    settings_file = _get_settings_file()
    if not os.path.exists(settings_file):
        return _DEFAULT_LANGUAGE
    try:
        with open(settings_file, "r") as f:
            return json.load(f).get("language", _DEFAULT_LANGUAGE)
    except (OSError, json.JSONDecodeError):
        return _DEFAULT_LANGUAGE


def _save_language(language):
    settings_file = _get_settings_file()
    os.makedirs(os.path.dirname(settings_file), exist_ok=True)
    with open(settings_file, "w") as f:
        json.dump({"language": language}, f)


@bp.get("/api/settings")
def get_settings():
    session = backend_config.load_session()
    return jsonify({
        "language": _load_language(),
        "playlist_limit": session["playlist_limit"],
        "cookies_status": backend_config.cookies_status_for(session["cookies_path"]),
    })


@bp.post("/api/settings")
def update_settings():
    data = request.get_json(force=True) or {}
    language = data.get("language", _load_language())
    _save_language(language)

    session = backend_config.load_session()
    playlist_limit = data.get("playlist_limit", session["playlist_limit"])
    if playlist_limit != session["playlist_limit"]:
        backend_config.save_session(session["path"], session["cookies_path"], session["browser"], playlist_limit)

    return jsonify({"language": language, "playlist_limit": playlist_limit})


@bp.post("/api/settings/cookies")
def upload_cookies():
    uploaded = request.files.get("cookies")
    if uploaded is None or uploaded.filename == "":
        return jsonify({"error": "No file uploaded"}), 400

    body = uploaded.read(_MAX_COOKIES_FILE_BYTES + 1)
    if not body:
        return jsonify({"error": "Uploaded file is empty"}), 400
    if len(body) > _MAX_COOKIES_FILE_BYTES:
        return jsonify({"error": "Uploaded file is too large (max 64 KiB) - this doesn't look like a real cookies.txt"}), 400

    os.makedirs(os.path.dirname(_COOKIES_FILE), exist_ok=True)
    with open(_COOKIES_FILE, "wb") as f:
        f.write(body)
    # This is a live session credential, same care as config.STATE_FILE.
    os.chmod(_COOKIES_FILE, 0o600)

    session = backend_config.load_session()
    backend_config.save_session(session["path"], _COOKIES_FILE, session["browser"], session["playlist_limit"])

    return jsonify({"cookies_status": backend_config.cookies_status_for(_COOKIES_FILE)})
