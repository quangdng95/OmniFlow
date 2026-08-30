"""GET/POST /api/settings.

Two very different kinds of state live behind this one endpoint:
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

`path`/`cookies_path`/`browser` are deliberately NOT part of this response at
all - the frontend never reads or writes them in remote mode (those
sections are hidden behind isLocal(), see frontend/src/pages/SettingsPage.tsx).
"""

import json
import os

from flask import Blueprint, jsonify, request

from backend import config as backend_config
from remote_web import config

bp = Blueprint("settings", __name__)

_DEFAULT_LANGUAGE = "en"


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
    return jsonify({"language": _load_language(), "playlist_limit": session["playlist_limit"]})


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
