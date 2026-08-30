"""remote_web's own tunables + trust-token/secret-key persistence (spec §4.2, §4.3).

This is a SEPARATE state file from backend/config.py's config.json (the
native app's save-folder/cookies-path settings) - remote_web has no save
folder of its own (every download streams to the requesting device) and no
manual-cookies UI, so there is nothing to share there. The one deliberate
exception is `playlist_limit`, which remote_web/routes/settings.py proxies
straight through to backend.config's own session file, since
backend.extraction.extract_video_info already reads it from there - see that
file for why.

Name collision warning (also called out in this plan's Global Constraints):
a file that needs both this module and backend/config.py must alias one,
e.g. `from backend import config as backend_config`.
"""

import json
import os
import secrets

from backend import paths

# Deliberately NOT backend.config.CONFIG_FILE - a wholly separate file so
# this deployment never touches the native app's own settings at all.
STATE_FILE = os.path.join(paths.BASE_DIR, "remote_web", ".state.json")
# Where job temp dirs (single downloads and batch zips) are staged.
TEMP_ROOT = os.path.join(paths.BASE_DIR, "remote_web", ".tmp")

PORT = 5050

# The trust cookie's own lifetime (§4.2) - not unbounded, so a lost/stolen
# phone's access expires on its own even if never explicitly revoked.
COOKIE_MAX_AGE_DAYS = 90
COOKIE_MAX_AGE_SECONDS = COOKIE_MAX_AGE_DAYS * 24 * 60 * 60
TRUST_COOKIE_NAME = "omniflow_remote_trust"

# Brute-force lockout on POST /unlock (§4.5): N failures within the window
# locks out that CF-Connecting-IP for WINDOW seconds.
LOCKOUT_THRESHOLD = 10
LOCKOUT_WINDOW_SECONDS = 300

# /api/health/detail's cookie-liveness check is cached this long (§4.6) so an
# automated monitor pinging it frequently doesn't hammer Keychain access.
HEALTH_CACHE_SECONDS = 300

# reaper.py's sweep interval and staleness window (§5.4).
REAPER_SWEEP_INTERVAL_SECONDS = 300
REAPER_STALE_MINUTES = 30


def _load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)
    # The trust token and secret key are this deployment's entire auth model
    # (§4.1-§4.2) - keep the file readable only by its owner.
    os.chmod(STATE_FILE, 0o600)


def get_or_create_token():
    # The raw shared secret typed into the /unlock form. Generated once, on
    # first use, and persisted - never regenerated silently (that would lock
    # the owner out with no warning).
    state = _load_state()
    if "token" not in state:
        state["token"] = secrets.token_urlsafe(32)
        _save_state(state)
    return state["token"]


def get_or_create_secret_key():
    # Signs the trust cookie (itsdangerous) - deliberately separate from the
    # raw token (§4.2): compromising one doesn't compromise the other.
    state = _load_state()
    if "secret_key" not in state:
        state["secret_key"] = secrets.token_urlsafe(32)
        _save_state(state)
    return state["secret_key"]


def rotate_token():
    # Stops any NEW /unlock attempt with the old token (§4.3). Does not
    # affect cookies already issued.
    state = _load_state()
    state["token"] = secrets.token_urlsafe(32)
    _save_state(state)
    return state["token"]


def rotate_secret_key():
    # Invalidates EVERY previously-issued trust cookie at once (§4.3) - the
    # actual "I lost my phone" response. Every device, including the owner's
    # own, must re-/unlock afterward.
    state = _load_state()
    state["secret_key"] = secrets.token_urlsafe(32)
    _save_state(state)
    return state["secret_key"]


if __name__ == "__main__":
    # `python3 -m remote_web.config show|rotate-token|rotate-key` - the
    # operational commands documented in remote_web/README.md (§4.3).
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
    if cmd == "rotate-token":
        print(f"New token: {rotate_token()}")
    elif cmd == "rotate-key":
        rotate_secret_key()
        print("Secret key rotated - every previously-issued trust cookie is now invalid.")
    elif cmd == "show":
        print(f"Token: {get_or_create_token()}")
    else:
        print(f"Unknown command: {cmd!r}. Use: show | rotate-token | rotate-key", file=sys.stderr)
        sys.exit(1)
