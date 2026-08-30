# Remote Web Access Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `remote_web/`, a standalone Flask deployment that serves OmniFlow's existing check/download flow (including Instagram/Threads and playlist/carousel batch downloads) over a personal, token-gated public URL, with zero changes to `backend/`, `server.py`, `desktop_app.py`, or `OmniFlow.spec`.

**Architecture:** A new top-level package, `remote_web/`, reuses every platform-extraction/download module in `backend/` unmodified via plain Python import, and reimplements only the HTTP/routing layer that today's `backend/app.py` couples to `is_local_request()` — a single-tier trust-cookie gate replaces that local/remote split, every download always streams back to the requesting device (single file or an incrementally-built `.zip` for a batch), and a filesystem-mtime reaper thread cleans up temp dirs so the deployment can run unattended for weeks.

**Tech Stack:** Python 3 + Flask (already a project dependency) + `itsdangerous` (ships with Flask, confirmed installed at v2.2.0) for signed cookies. No new pip dependencies. Reuses `backend.classify`, `backend.extraction`, `backend.download`, `backend.instagram`, `backend.threads`, `backend.linkedin`, `backend.tiktok`, `backend.cookies`, `backend.config`, `backend.jobs`, `backend.paths` unmodified.

**Spec:** [docs/superpowers/specs/2026-08-29-remote-web-access-design.md](../specs/2026-08-29-remote-web-access-design.md) (v3) — this plan implements every numbered section of that spec; section references below (`§4.2`, `§5.3`, …) point back to it.

## Global Constraints

- **Zero changes to `backend/`, `server.py`, `desktop_app.py`, `OmniFlow.spec`.** Every task in this plan only creates or edits files under `remote_web/` (plus one one-line addition to the repo-root `.gitignore` in Task 1). If any task's implementation seems to require touching one of those files, stop and re-read spec §2 — the intended fix is always a new function in `remote_web/`, never an edit to `backend/`.
- **Package name is `remote_web` (underscore), never `remote-web`.** Hyphens are invalid in a Python dotted import path (spec §9.1). Always run it as `python3 -m remote_web.app` from the repo root — the `-m` form is what puts the repo root on `sys.path` so `import backend` resolves at all (spec §6 step 7).
- **Name collision to watch for:** `remote_web/config.py` and `backend/config.py` are two different modules with the same short name. Every file in `remote_web/` that needs both must alias one: `from backend import config as backend_config` alongside `from remote_web import config`. Never write a bare `from backend import config` in a file that also does `from remote_web import config` — the second import silently shadows the first.
- **`remote_web` binds to `127.0.0.1:5050` only — never `0.0.0.0`.** This is load-bearing for the `CF-Connecting-IP` trust in §4.5 (spec §3): the only way to reach the process at all is through `cloudflared` on the same machine.
- **Every `/api/*` route requires the trust cookie; nothing else does.** The gate is one `before_request` hook keyed purely on `request.path.startswith("/api/")` (spec §4.4) — no per-route allowlist needed, since `/`, `/unlock`, static assets, and `/health` are simply never under `/api/`.
- **No raw tracebebacks or yt-dlp CLI-flag messages ever reach the client** (design-principles §3, spec §7) — every route wraps extraction/download in `try/except` and reuses `backend.extraction.describe_extraction_error` for message text, exactly like `backend/app.py` already does.
- **`ZIP_STORED`, never the default `ZIP_DEFLATE`**, for batch zips (spec §5.3) — the contents are already-compressed video/image files.
- All new Python files follow the existing repo's docstring-at-top-of-file convention (see any `backend/*.py` module) and module-attribute-style imports for cross-package reuse (`from backend import config` then `config.load_session()` — already how `backend/*.py` imports its own siblings, per `tests/test_import_convention.py`; that specific test only enforces this within `backend/`, but `remote_web/` follows the same style for consistency).

---

## File Structure

```
remote_web/
├── __init__.py
├── app.py                  # Flask app: trust gate, Referrer-Policy header,
│                              static frontend serving, blueprint mounting,
│                              startup ffmpeg check, reaper thread start
├── trust.py                 # cookie signing/verification, is_trusted_request(),
│                              the /unlock blueprint, CF-Connecting-IP lockout
├── config.py                # token/secret-key persistence + rotation CLI,
│                              port/temp-root/cookie-maxage/lockout/health-cache/
│                              reaper tunables
├── ffmpeg_locator.py          # resolve_ffmpeg_binary() — architecture-aware
├── zipper.py                # BatchZipper — incremental ZIP_STORED assembly
├── reaper.py                 # filesystem-mtime sweep of stale temp dirs
├── routes/
│   ├── __init__.py
│   ├── health.py             # GET /health, GET /api/health/detail
│   ├── settings.py            # GET/POST /api/settings
│   ├── media.py               # POST /api/check, /api/download, /api/download-batch
│   └── jobs.py                # GET /api/progress/<id>, POST /api/cancel/<id>,
│                                 GET /api/download-file/<id>
├── requirements.txt          # documents that nothing new is needed beyond root
│                                requirements.txt
├── README.md                  # deployment steps, token/key rotation, Cloudflare
│                                Tunnel + Access, launchd plist, manual checklist
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_config.py
    ├── test_trust.py
    ├── test_ffmpeg_locator.py
    ├── test_app_gate.py
    ├── test_health_routes.py
    ├── test_zipper.py
    ├── test_reaper.py
    ├── test_settings_routes.py
    ├── test_media_routes.py
    └── test_jobs_routes.py
```

`remote_web/.state.json` (token + secret key) and `remote_web/.tmp/` (job temp dirs) are runtime-generated, never committed — Task 1 adds them to the repo-root `.gitignore`.

No pytest config file exists in the repo (confirmed: no `pytest.ini`/`pyproject.toml`/`setup.cfg`), so a bare `pytest` at the repo root auto-discovers both `tests/` and `remote_web/tests/` — this is what makes spec §8's "the existing suite must stay green, untouched by this work" a real, single-command check once this plan is done.

---

### Task 1: Package scaffold + `config.py` (token/secret-key persistence)

**Files:**
- Create: `remote_web/__init__.py`
- Create: `remote_web/routes/__init__.py`
- Create: `remote_web/config.py`
- Create: `remote_web/tests/__init__.py`
- Create: `remote_web/tests/conftest.py`
- Test: `remote_web/tests/test_config.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `remote_web.config.PORT` (int, `5050`), `TEMP_ROOT` (str path), `COOKIE_MAX_AGE_DAYS` (`90`), `COOKIE_MAX_AGE_SECONDS` (int), `TRUST_COOKIE_NAME` (str), `LOCKOUT_THRESHOLD` (`10`), `LOCKOUT_WINDOW_SECONDS` (`300`), `HEALTH_CACHE_SECONDS` (`300`), `REAPER_SWEEP_INTERVAL_SECONDS` (`300`), `REAPER_STALE_MINUTES` (`30`), `STATE_FILE` (str path); `get_or_create_token() -> str`, `get_or_create_secret_key() -> str`, `rotate_token() -> str`, `rotate_secret_key() -> str`.

- [ ] **Step 1: Create the package skeleton**

```bash
mkdir -p remote_web/routes remote_web/tests
touch remote_web/__init__.py remote_web/routes/__init__.py remote_web/tests/__init__.py
```

`remote_web/__init__.py` and `remote_web/routes/__init__.py` stay empty — their only job is making `remote_web` and `remote_web.routes` real importable packages (spec §3's file-tree comment).

- [ ] **Step 2: Write the failing tests**

```python
# remote_web/tests/test_config.py
"""Token/secret-key persistence + rotation (spec §4.2, §4.3)."""

import json
import os

from remote_web import config


def test_get_or_create_token_persists_across_calls(isolated_state_file):
    first = config.get_or_create_token()
    second = config.get_or_create_token()
    assert first == second
    assert len(first) > 20  # secrets.token_urlsafe(32) is well over 20 chars


def test_get_or_create_secret_key_is_independent_of_the_token(isolated_state_file):
    token = config.get_or_create_token()
    key = config.get_or_create_secret_key()
    assert token != key


def test_rotate_token_changes_the_token_but_not_the_secret_key(isolated_state_file):
    old_token = config.get_or_create_token()
    old_key = config.get_or_create_secret_key()
    new_token = config.rotate_token()
    assert new_token != old_token
    assert config.get_or_create_token() == new_token
    assert config.get_or_create_secret_key() == old_key


def test_rotate_secret_key_changes_the_key_but_not_the_token(isolated_state_file):
    old_token = config.get_or_create_token()
    old_key = config.get_or_create_secret_key()
    new_key = config.rotate_secret_key()
    assert new_key != old_key
    assert config.get_or_create_secret_key() == new_key
    assert config.get_or_create_token() == old_token


def test_state_file_is_owner_only_readable(isolated_state_file):
    config.get_or_create_token()
    mode = os.stat(config.STATE_FILE).st_mode & 0o777
    assert mode == 0o600


def test_state_file_survives_a_fresh_load_from_disk(isolated_state_file):
    token = config.get_or_create_token()
    with open(config.STATE_FILE) as f:
        data = json.load(f)
    assert data["token"] == token
```

```python
# remote_web/tests/conftest.py
import os

import pytest

from remote_web import config as config_module


@pytest.fixture
def isolated_state_file(tmp_path, monkeypatch):
    # config.py persists the trust token + signing key to a real file - point
    # every test at a throwaway path so tests never read/write the real
    # deployment's own .state.json.
    state_file = tmp_path / ".state.json"
    monkeypatch.setattr(config_module, "STATE_FILE", str(state_file))
    return state_file
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `pytest remote_web/tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'remote_web.config'` (or similar import error) — the module doesn't exist yet.

- [ ] **Step 4: Implement `remote_web/config.py`**

```python
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
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest remote_web/tests/test_config.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Add the runtime state files to `.gitignore`**

Open `.gitignore` and add, near the other build-artifact entries:

```
# remote_web's own runtime state - trust token/secret key + job temp dirs,
# never committed (see docs/superpowers/specs/2026-08-29-remote-web-access-design.md)
remote_web/.state.json
remote_web/.tmp/
```

- [ ] **Step 7: Commit**

```bash
git add remote_web/__init__.py remote_web/routes/__init__.py remote_web/config.py \
        remote_web/tests/__init__.py remote_web/tests/conftest.py remote_web/tests/test_config.py \
        .gitignore
git commit -m "remote_web: scaffold package + trust-token/secret-key config"
```

---

### Task 2: `trust.py` — cookie signing, `is_trusted_request`, `/unlock` form, lockout

**Files:**
- Create: `remote_web/trust.py`
- Test: `remote_web/tests/test_trust.py`

**Interfaces:**
- Consumes: `remote_web.config.get_or_create_token()`, `get_or_create_secret_key()`, `TRUST_COOKIE_NAME`, `COOKIE_MAX_AGE_SECONDS`, `LOCKOUT_THRESHOLD`, `LOCKOUT_WINDOW_SECONDS` (Task 1).
- Produces: `remote_web.trust.unlock_bp` (a Flask `Blueprint` with `GET /unlock` and `POST /unlock`), `sign_trust_cookie() -> str`, `verify_trust_cookie(cookie_value: str | None) -> bool`, `is_trusted_request(req) -> bool` (used by Task 4's `app.py` gate).

- [ ] **Step 1: Write the failing tests**

```python
# remote_web/tests/test_trust.py
"""Cookie signing/verification, the /unlock form, and CF-Connecting-IP
brute-force lockout (spec §4.1, §4.2, §4.5)."""

import time

import pytest
from flask import Flask

from remote_web import config, trust


@pytest.fixture
def app(isolated_state_file):
    app = Flask(__name__)
    app.register_blueprint(trust.unlock_bp)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def clear_lockout_state():
    trust._failed_attempts.clear()
    yield
    trust._failed_attempts.clear()


def test_verify_trust_cookie_accepts_a_freshly_signed_cookie(isolated_state_file):
    cookie = trust.sign_trust_cookie()
    assert trust.verify_trust_cookie(cookie) is True


def test_verify_trust_cookie_rejects_garbage(isolated_state_file):
    assert trust.verify_trust_cookie("not-a-real-signed-value") is False


def test_verify_trust_cookie_rejects_none(isolated_state_file):
    assert trust.verify_trust_cookie(None) is False


def test_verify_trust_cookie_rejects_an_expired_cookie(isolated_state_file, monkeypatch):
    cookie = trust.sign_trust_cookie()
    monkeypatch.setattr(config, "COOKIE_MAX_AGE_SECONDS", -1)  # already "expired"
    assert trust.verify_trust_cookie(cookie) is False


def test_rotating_the_secret_key_invalidates_existing_cookies(isolated_state_file):
    cookie = trust.sign_trust_cookie()
    assert trust.verify_trust_cookie(cookie) is True
    config.rotate_secret_key()
    assert trust.verify_trust_cookie(cookie) is False


def test_unlock_get_renders_a_form_with_no_token_in_the_page(isolated_state_file, client):
    resp = client.get("/unlock")
    assert resp.status_code == 200
    assert b"<form" in resp.data
    assert config.get_or_create_token().encode() not in resp.data


def test_unlock_post_with_correct_token_sets_cookie_and_redirects(isolated_state_file, client):
    token = config.get_or_create_token()
    resp = client.post("/unlock", data={"token": token})
    assert resp.status_code == 302
    assert resp.location == "/"
    set_cookie = resp.headers.get("Set-Cookie", "")
    assert config.TRUST_COOKIE_NAME in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "SameSite=Lax" in set_cookie


def test_unlock_post_with_wrong_token_does_not_set_cookie(isolated_state_file, client):
    config.get_or_create_token()
    resp = client.post("/unlock", data={"token": "wrong"})
    assert resp.status_code == 401
    assert config.TRUST_COOKIE_NAME not in resp.headers.get("Set-Cookie", "")


def test_unlock_lockout_after_threshold_failures(isolated_state_file, client, monkeypatch):
    monkeypatch.setattr(config, "LOCKOUT_THRESHOLD", 3)
    for _ in range(3):
        client.post("/unlock", data={"token": "wrong"}, headers={"CF-Connecting-IP": "1.2.3.4"})
    resp = client.post(
        "/unlock", data={"token": "wrong"}, headers={"CF-Connecting-IP": "1.2.3.4"}
    )
    assert resp.status_code == 429


def test_unlock_lockout_is_keyed_per_ip(isolated_state_file, client, monkeypatch):
    monkeypatch.setattr(config, "LOCKOUT_THRESHOLD", 3)
    for _ in range(3):
        client.post("/unlock", data={"token": "wrong"}, headers={"CF-Connecting-IP": "1.2.3.4"})
    # A different IP is unaffected by the first IP's lockout.
    correct = config.get_or_create_token()
    resp = client.post(
        "/unlock", data={"token": correct}, headers={"CF-Connecting-IP": "9.9.9.9"}
    )
    assert resp.status_code == 302


def test_unlock_lockout_expires_after_the_window(isolated_state_file, client, monkeypatch):
    monkeypatch.setattr(config, "LOCKOUT_THRESHOLD", 2)
    monkeypatch.setattr(config, "LOCKOUT_WINDOW_SECONDS", 300)
    ip = {"CF-Connecting-IP": "5.5.5.5"}
    for _ in range(2):
        client.post("/unlock", data={"token": "wrong"}, headers=ip)
    # Simulate the window having passed by rewriting the recorded timestamps.
    trust._failed_attempts["5.5.5.5"] = [time.time() - 301, time.time() - 301]
    correct = config.get_or_create_token()
    resp = client.post("/unlock", data={"token": correct}, headers=ip)
    assert resp.status_code == 302
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest remote_web/tests/test_trust.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'remote_web.trust'`

- [ ] **Step 3: Implement `remote_web/trust.py`**

```python
"""Trust cookie signing/verification, the /unlock form, and CF-Connecting-IP
brute-force lockout (spec §4)."""

import hmac
import time

from flask import Blueprint, Response, redirect, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from remote_web import config

unlock_bp = Blueprint("unlock", __name__)

# In-memory failed-attempt counters, keyed on CF-Connecting-IP (§4.5). Reset
# on every process restart - same documented trade-off as backend.jobs.jobs
# (spec §6 step 8).
_failed_attempts = {}  # {ip: [timestamp, ...]}


def _client_ip():
    # Through Cloudflare Tunnel every request Flask sees originates from the
    # local cloudflared process, so request.remote_addr is always 127.0.0.1
    # regardless of the real client - CF-Connecting-IP is the only header
    # that carries the real one. Trusting it is safe specifically because
    # remote_web only ever binds to 127.0.0.1 (spec §3): a direct attacker
    # can't reach this process at all, only cloudflared can, and cloudflared
    # is the one setting this header truthfully.
    return request.headers.get("CF-Connecting-IP", "unknown")


def _is_locked_out(ip):
    now = time.time()
    attempts = [t for t in _failed_attempts.get(ip, []) if now - t < config.LOCKOUT_WINDOW_SECONDS]
    _failed_attempts[ip] = attempts
    return len(attempts) >= config.LOCKOUT_THRESHOLD


def _record_failed_attempt(ip):
    _failed_attempts.setdefault(ip, []).append(time.time())


def _serializer():
    return URLSafeTimedSerializer(config.get_or_create_secret_key(), salt="omniflow-remote-trust")


def sign_trust_cookie():
    return _serializer().dumps({"trusted": True})


def verify_trust_cookie(cookie_value):
    if not cookie_value:
        return False
    try:
        _serializer().loads(cookie_value, max_age=config.COOKIE_MAX_AGE_SECONDS)
        return True
    except (BadSignature, SignatureExpired):
        return False


def is_trusted_request(req):
    return verify_trust_cookie(req.cookies.get(config.TRUST_COOKIE_NAME))


_UNLOCK_FORM_HTML = """<!doctype html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>OmniFlow</title>
<style>
body {{ font-family: -apple-system, sans-serif; display: flex; align-items: center;
       justify-content: center; height: 100vh; margin: 0; background: #f5f5f5; }}
form {{ background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 1px 4px rgba(0,0,0,.1);
       width: min(320px, 90vw); box-sizing: border-box; }}
input {{ display: block; width: 100%; padding: .75rem; margin: .5rem 0 1rem; box-sizing: border-box;
        border: 1px solid #ccc; border-radius: 8px; font-size: 1rem; }}
button {{ width: 100%; padding: .75rem; background: #111; color: white; border: none;
         border-radius: 8px; font-size: 1rem; }}
.error {{ color: #c00; margin: 0 0 1rem; font-size: .875rem; }}
</style></head>
<body>
<form method="post" action="/unlock">
<h2>OmniFlow</h2>
{error}
<input type="password" name="token" placeholder="Access token" autofocus required>
<button type="submit">Unlock</button>
</form>
</body></html>"""


def _render_unlock_form(error=None):
    error_html = f'<p class="error">{error}</p>' if error else ""
    return _UNLOCK_FORM_HTML.format(error=error_html)


@unlock_bp.get("/unlock")
def unlock_form():
    # No token ever appears in a URL (spec §4.1) - this is a plain HTML form,
    # no React/JS required, so it renders even before the frontend bundle's
    # own JS has a chance to load.
    return Response(_render_unlock_form(), mimetype="text/html")


@unlock_bp.post("/unlock")
def unlock_submit():
    ip = _client_ip()
    if _is_locked_out(ip):
        return Response(
            _render_unlock_form("Too many attempts. Try again in a few minutes."),
            mimetype="text/html", status=429,
        )
    token = request.form.get("token", "")
    # Constant-time compare (§4.1) - a plain == leaks how many leading
    # characters matched via response-time differences.
    if not hmac.compare_digest(token, config.get_or_create_token()):
        _record_failed_attempt(ip)
        return Response(_render_unlock_form("Incorrect token."), mimetype="text/html", status=401)
    resp = redirect("/")
    resp.set_cookie(
        config.TRUST_COOKIE_NAME,
        sign_trust_cookie(),
        max_age=config.COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=True,
        samesite="Lax",
    )
    return resp
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest remote_web/tests/test_trust.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add remote_web/trust.py remote_web/tests/test_trust.py
git commit -m "remote_web: add trust cookie signing + /unlock form + lockout"
```

---

### Task 3: `ffmpeg_locator.py` — architecture-aware ffmpeg resolution

**Files:**
- Create: `remote_web/ffmpeg_locator.py`
- Test: `remote_web/tests/test_ffmpeg_locator.py`

**Interfaces:**
- Consumes: `backend.paths.BASE_DIR` (existing, unmodified).
- Produces: `resolve_ffmpeg_binary() -> str | None`, `ffmpeg_unavailable_message() -> str` (both used by Task 5's health route and Tasks 10-11's download routes).

- [ ] **Step 1: Write the failing tests**

```python
# remote_web/tests/test_ffmpeg_locator.py
"""Architecture-aware ffmpeg resolution for remote_web's unfrozen execution
(spec §5.1) - mirrors tests/test_paths.py's pattern for simulating a
wrong-architecture exec failure."""

import os
import subprocess

from remote_web import ffmpeg_locator


def _make_fake_binary(tmp_path, name):
    fake = tmp_path / name
    fake.write_text("#!/bin/sh\necho fake\n")
    fake.chmod(0o755)
    return str(fake)


def test_resolve_ffmpeg_binary_picks_arm64_binary_on_arm64(tmp_path, monkeypatch):
    _make_fake_binary(tmp_path, "ffmpeg")
    monkeypatch.setattr(ffmpeg_locator.paths, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(ffmpeg_locator.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: None)
    resolved = ffmpeg_locator.resolve_ffmpeg_binary()
    assert resolved == str(tmp_path / "ffmpeg")


def test_resolve_ffmpeg_binary_picks_x86_64_binary_on_intel(tmp_path, monkeypatch):
    _make_fake_binary(tmp_path, "ffmpeg-x86_64")
    monkeypatch.setattr(ffmpeg_locator.paths, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(ffmpeg_locator.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: None)
    resolved = ffmpeg_locator.resolve_ffmpeg_binary()
    assert resolved == str(tmp_path / "ffmpeg-x86_64")


def test_resolve_ffmpeg_binary_returns_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(ffmpeg_locator.paths, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(ffmpeg_locator.platform, "machine", lambda: "arm64")
    assert ffmpeg_locator.resolve_ffmpeg_binary() is None


def test_resolve_ffmpeg_binary_returns_none_for_a_wrong_architecture_binary(tmp_path, monkeypatch):
    _make_fake_binary(tmp_path, "ffmpeg")
    monkeypatch.setattr(ffmpeg_locator.paths, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(ffmpeg_locator.platform, "machine", lambda: "arm64")

    def fake_run(*a, **k):
        raise OSError(86, "Bad CPU type in executable")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert ffmpeg_locator.resolve_ffmpeg_binary() is None


def test_ffmpeg_unavailable_message_names_the_running_machines_architecture(monkeypatch):
    monkeypatch.setattr(ffmpeg_locator.platform, "machine", lambda: "arm64")
    assert "arm64" in ffmpeg_locator.ffmpeg_unavailable_message()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest remote_web/tests/test_ffmpeg_locator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'remote_web.ffmpeg_locator'`

- [ ] **Step 3: Implement `remote_web/ffmpeg_locator.py`**

```python
"""Architecture-aware ffmpeg binary resolution for remote_web's unfrozen
(non-PyInstaller) execution (spec §5.1).

backend.paths.get_ffmpeg_path() always looks for a file literally named
`ffmpeg` at the repo root - correct only because OmniFlow.spec already staged
the matching-architecture binary under that exact name at BUILD time.
remote_web runs unfrozen (`python3 -m remote_web.app`, no PyInstaller step),
so nothing performs that selection - this module does its own resolution
instead, entirely inside remote_web/, and never calls
backend.paths.get_ffmpeg_path().

Both source binaries are real, Git-LFS-tracked files at the repo root,
confirmed present during this design's review (see the spec's §5.1):
./ffmpeg (arm64) and ./ffmpeg-x86_64 (Intel).
"""

import os
import platform
import subprocess

from backend import paths

_BAD_CPU_TYPE_ERRNO = 86


def _exec_ok(path):
    try:
        subprocess.run([path, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def resolve_ffmpeg_binary():
    name = "ffmpeg" if platform.machine() == "arm64" else "ffmpeg-x86_64"
    candidate = os.path.join(paths.BASE_DIR, name)
    if not os.path.exists(candidate):
        return None
    if not os.access(candidate, os.X_OK):
        try:
            os.chmod(candidate, 0o755)
        except OSError:
            pass
    if not os.access(candidate, os.X_OK):
        return None
    if not _exec_ok(candidate):
        return None
    return candidate


def ffmpeg_unavailable_message():
    # Unlike backend.paths.ffmpeg_unavailable_message() (which tells an END
    # USER which .dmg to download instead), remote_web is one long-running
    # deployment on one machine - an unresolvable ffmpeg here means the
    # DEPLOYMENT itself is broken, not that the visitor picked the wrong
    # installer. The actionable audience is whoever runs the Mac, not the
    # phone on the other end.
    return (
        "❌ Lỗi: Không tìm thấy FFmpeg khả dụng cho kiến trúc CPU của máy chủ này "
        f"({platform.machine()}). Vui lòng liên hệ quản trị viên để kiểm tra lại triển khai."
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest remote_web/tests/test_ffmpeg_locator.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add remote_web/ffmpeg_locator.py remote_web/tests/test_ffmpeg_locator.py
git commit -m "remote_web: add architecture-aware ffmpeg resolution"
```

---

### Task 4: `app.py` skeleton — Flask app, trust gate, Referrer-Policy, static serving

**Files:**
- Create: `remote_web/app.py`
- Test: `remote_web/tests/test_app_gate.py`

**Interfaces:**
- Consumes: `remote_web.trust.unlock_bp`, `is_trusted_request` (Task 2); `remote_web.ffmpeg_locator.resolve_ffmpeg_binary` (Task 3); `remote_web.config.PORT` (Task 1); `backend.paths.WEB_DIR` (existing, unmodified).
- Produces: `remote_web.app.app` (the module-level Flask instance every later route task registers a blueprint on — mirrors `backend/app.py`'s own `app = Flask(...)` convention).

- [ ] **Step 1: Write the failing tests**

```python
# remote_web/tests/test_app_gate.py
"""The app-wide trust gate + Referrer-Policy header (spec §4.1, §4.4)."""

import pytest

from remote_web import config, trust
from remote_web.app import app as remote_app


@pytest.fixture
def client(isolated_state_file):
    remote_app.config["TESTING"] = True
    return remote_app.test_client()


def test_unauthenticated_api_request_is_rejected(client):
    resp = client.get("/api/anything-at-all")
    assert resp.status_code == 401


def test_unlock_route_itself_is_never_gated(client):
    resp = client.get("/unlock")
    assert resp.status_code == 200


def test_a_valid_trust_cookie_passes_the_gate(client):
    token = config.get_or_create_token()
    client.post("/unlock", data={"token": token})
    # The route still doesn't exist yet at this point in the plan, so a
    # trusted request reaches Flask's own 404 instead of the gate's 401 -
    # that distinction (401 vs. 404) is exactly what this test is pinning.
    resp = client.get("/api/anything-at-all")
    assert resp.status_code == 404


def test_every_response_sets_referrer_policy_no_referrer(client):
    resp = client.get("/unlock")
    assert resp.headers.get("Referrer-Policy") == "no-referrer"


def test_root_path_is_not_gated_by_trust(client):
    # index() serves frontend/dist/index.html - a real build may or may not
    # exist on the test machine, so this only asserts it's not blocked by
    # the trust gate (401), whatever else it returns.
    resp = client.get("/")
    assert resp.status_code != 401
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest remote_web/tests/test_app_gate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'remote_web.app'`

- [ ] **Step 3: Implement `remote_web/app.py`**

```python
"""remote_web's Flask app - the trust gate, Referrer-Policy header, static
frontend serving, and the mount point for every routes/*.py blueprint.

Zero changes to backend/ or the native app (spec §2-3): everything here is
new code in this one top-level folder, reusing backend/* only via plain
Python import.
"""

import sys

from flask import Flask, jsonify, request, send_from_directory

from backend import paths
from remote_web import ffmpeg_locator, trust

app = Flask(__name__, static_folder=paths.WEB_DIR, static_url_path="")
app.register_blueprint(trust.unlock_bp)


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

if __name__ == "__main__":
    # debug=False (and therefore no reloader) is deliberate: the Werkzeug
    # reloader re-executes this module in a child process, which would run
    # every top-level startup step (this ffmpeg check, and Task 7's reaper
    # thread start) twice. launchd (spec §6 step 8) already handles
    # restart-on-crash, so the dev reloader adds no value here, only risk.
    app.run(host="127.0.0.1", port=__import__("remote_web.config", fromlist=["PORT"]).PORT, debug=False)
```

Note the `__main__` block's import: use a plain top-of-file import instead of the inline `__import__` shown above — write it as:

```python
"""remote_web's Flask app - the trust gate, Referrer-Policy header, static
frontend serving, and the mount point for every routes/*.py blueprint.

Zero changes to backend/ or the native app (spec §2-3): everything here is
new code in this one top-level folder, reusing backend/* only via plain
Python import.
"""

import sys

from flask import Flask, jsonify, request, send_from_directory

from backend import paths
from remote_web import config, ffmpeg_locator, trust

app = Flask(__name__, static_folder=paths.WEB_DIR, static_url_path="")
app.register_blueprint(trust.unlock_bp)


@app.before_request
def _trust_gate():
    if request.path.startswith("/api/") and not trust.is_trusted_request(request):
        return jsonify({"error": "Unlock required."}), 401


@app.after_request
def _referrer_policy(response):
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/")
def index():
    return send_from_directory(paths.WEB_DIR, "index.html")


def _check_ffmpeg_at_startup():
    resolved = ffmpeg_locator.resolve_ffmpeg_binary()
    if not resolved:
        print(
            "[remote_web] WARNING: no usable ffmpeg binary found for this machine's "
            "architecture - every video download will fail until this is fixed.",
            file=sys.stderr,
        )
    return resolved


_check_ffmpeg_at_startup()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=config.PORT, debug=False)
```

Use this second version as the actual file content (it's the same design, just without the throwaway inline `__import__` — write `remote_web/app.py` directly with `from remote_web import config, ffmpeg_locator, trust` at the top).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest remote_web/tests/test_app_gate.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add remote_web/app.py remote_web/tests/test_app_gate.py
git commit -m "remote_web: add Flask app skeleton with trust gate + Referrer-Policy"
```

---

### Task 5: `routes/health.py` — public liveness + trust-gated detail

**Files:**
- Create: `remote_web/routes/health.py`
- Modify: `remote_web/app.py`
- Test: `remote_web/tests/test_health_routes.py`

**Interfaces:**
- Consumes: `remote_web.ffmpeg_locator.resolve_ffmpeg_binary` (Task 3); `remote_web.config.TEMP_ROOT`, `HEALTH_CACHE_SECONDS` (Task 1); `backend.cookies.instagram_cookiefile_candidates()`, `backend.threads.threads_cookiefile_candidates()` (existing, unmodified — both already stubbed to `[]` in tests by the `no_browser_cookie_scan`-style fixture this task adds).
- Produces: `remote_web.routes.health.bp` (Flask `Blueprint`, mounted into `app.py`).

- [ ] **Step 1: Write the failing tests**

```python
# remote_web/tests/test_health_routes.py
"""GET /health (public) + GET /api/health/detail (trust-gated, cached) — spec §4.6."""

import pytest

from remote_web import config
from remote_web.app import app as remote_app
from remote_web.routes import health as health_routes


@pytest.fixture
def client(isolated_state_file):
    remote_app.config["TESTING"] = True
    return remote_app.test_client()


@pytest.fixture(autouse=True)
def reset_health_cache():
    health_routes._detail_cache["payload"] = None
    health_routes._detail_cache["at"] = 0.0
    yield
    health_routes._detail_cache["payload"] = None
    health_routes._detail_cache["at"] = 0.0


def _unlock(client):
    token = config.get_or_create_token()
    client.post("/unlock", data={"token": token})


def test_health_is_unauthenticated(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_health_leaks_no_detail(client):
    resp = client.get("/health")
    body = resp.get_json()
    assert "ffmpeg" not in body
    assert "instagram_cookies" not in body


def test_health_detail_requires_trust(client):
    resp = client.get("/api/health/detail")
    assert resp.status_code == 401


def test_health_detail_reports_all_fields_when_trusted(client, monkeypatch):
    monkeypatch.setattr(health_routes.ffmpeg_locator, "resolve_ffmpeg_binary", lambda: "/fake/ffmpeg")
    monkeypatch.setattr(health_routes.backend_cookies, "instagram_cookiefile_candidates", lambda: ["/fake/cookies.txt"])
    monkeypatch.setattr(health_routes.backend_threads, "threads_cookiefile_candidates", lambda: [])
    _unlock(client)
    resp = client.get("/api/health/detail")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ffmpeg"] is True
    assert body["instagram_cookies"] is True
    assert body["threads_cookies"] is False
    assert "temp_dir_disk_free_mb" in body


def test_health_detail_never_leaks_secrets(client, monkeypatch):
    monkeypatch.setattr(health_routes.ffmpeg_locator, "resolve_ffmpeg_binary", lambda: "/fake/ffmpeg")
    monkeypatch.setattr(health_routes.backend_cookies, "instagram_cookiefile_candidates", lambda: [])
    monkeypatch.setattr(health_routes.backend_threads, "threads_cookiefile_candidates", lambda: [])
    _unlock(client)
    resp = client.get("/api/health/detail")
    text = resp.get_data(as_text=True)
    assert config.get_or_create_token() not in text
    assert config.get_or_create_secret_key() not in text
    assert config.STATE_FILE not in text


def test_health_detail_is_cached_between_calls(client, monkeypatch):
    calls = {"count": 0}

    def fake_resolve():
        calls["count"] += 1
        return "/fake/ffmpeg"

    monkeypatch.setattr(health_routes.ffmpeg_locator, "resolve_ffmpeg_binary", fake_resolve)
    monkeypatch.setattr(health_routes.backend_cookies, "instagram_cookiefile_candidates", lambda: [])
    monkeypatch.setattr(health_routes.backend_threads, "threads_cookiefile_candidates", lambda: [])
    _unlock(client)
    client.get("/api/health/detail")
    client.get("/api/health/detail")
    assert calls["count"] == 1


def test_health_detail_recomputes_after_cache_expiry(client, monkeypatch):
    monkeypatch.setattr(config, "HEALTH_CACHE_SECONDS", 0)
    monkeypatch.setattr(health_routes.ffmpeg_locator, "resolve_ffmpeg_binary", lambda: "/fake/ffmpeg")
    monkeypatch.setattr(health_routes.backend_cookies, "instagram_cookiefile_candidates", lambda: [])
    monkeypatch.setattr(health_routes.backend_threads, "threads_cookiefile_candidates", lambda: [])
    _unlock(client)
    calls = {"count": 0}
    original = health_routes.ffmpeg_locator.resolve_ffmpeg_binary

    def counting():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(health_routes.ffmpeg_locator, "resolve_ffmpeg_binary", counting)
    client.get("/api/health/detail")
    client.get("/api/health/detail")
    assert calls["count"] == 2
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest remote_web/tests/test_health_routes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'remote_web.routes.health'`

- [ ] **Step 3: Implement `remote_web/routes/health.py`**

```python
"""GET /health (public liveness) + GET /api/health/detail (trust-gated
diagnostics) - spec §4.6."""

import os
import shutil
import time

from flask import Blueprint, jsonify

from backend import cookies as backend_cookies
from backend import threads as backend_threads
from remote_web import config, ffmpeg_locator

bp = Blueprint("health", __name__)

_detail_cache = {"at": 0.0, "payload": None}


def _compute_detail():
    ffmpeg_path = ffmpeg_locator.resolve_ffmpeg_binary()
    instagram_ok = bool(backend_cookies.instagram_cookiefile_candidates())
    threads_ok = bool(backend_threads.threads_cookiefile_candidates())
    disk_target = config.TEMP_ROOT if os.path.isdir(config.TEMP_ROOT) else "/"
    try:
        free_mb = shutil.disk_usage(disk_target).free // (1024 * 1024)
    except OSError:
        free_mb = None
    return {
        "ffmpeg": ffmpeg_path is not None,
        "instagram_cookies": instagram_ok,
        "threads_cookies": threads_ok,
        "temp_dir_disk_free_mb": free_mb,
    }


@bp.get("/health")
def health():
    # Unauthenticated (§4.4/§4.6) - no detail beyond "something is
    # listening", so an external uptime monitor needs no credentials, and a
    # scanner that merely finds the tunnel hostname learns nothing about
    # whether this instance has a live Instagram session worth attacking.
    return jsonify({"status": "ok"})


@bp.get("/api/health/detail")
def health_detail():
    # Behind the normal /api/* trust gate (remote_web/app.py's before_request).
    # Cached for HEALTH_CACHE_SECONDS (§4.6) so a monitor polling this
    # frequently doesn't hammer Keychain access on every hit.
    now = time.time()
    if _detail_cache["payload"] is None or now - _detail_cache["at"] > config.HEALTH_CACHE_SECONDS:
        _detail_cache["payload"] = _compute_detail()
        _detail_cache["at"] = now
    return jsonify(_detail_cache["payload"])
```

- [ ] **Step 4: Mount the blueprint in `remote_web/app.py`**

In `remote_web/app.py`, add the import and registration:

```python
from remote_web import config, ffmpeg_locator, trust
from remote_web.routes import health as health_routes
```

and, right after `app.register_blueprint(trust.unlock_bp)`:

```python
app.register_blueprint(health_routes.bp)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest remote_web/tests/test_health_routes.py -v`
Expected: PASS (8 tests)

- [ ] **Step 6: Commit**

```bash
git add remote_web/routes/health.py remote_web/app.py remote_web/tests/test_health_routes.py
git commit -m "remote_web: add /health + /api/health/detail"
```

---

### Task 6: `zipper.py` — incremental `ZIP_STORED` batch assembly

**Files:**
- Create: `remote_web/zipper.py`
- Test: `remote_web/tests/test_zipper.py`

**Interfaces:**
- Produces: `remote_web.zipper.BatchZipper` (class: `__init__(zip_path)`, `add_and_delete(source_path, filename) -> str` returns the archive name actually used, `close()`).

- [ ] **Step 1: Write the failing tests**

```python
# remote_web/tests/test_zipper.py
"""Incremental ZIP_STORED batch assembly - items appended and their source
files deleted immediately, not just at the end (spec §5.3)."""

import os
import zipfile

from remote_web.zipper import BatchZipper


def _make_file(tmp_path, name, content=b"fake video bytes"):
    path = tmp_path / name
    path.write_bytes(content)
    return str(path)


def test_add_and_delete_puts_the_item_in_the_archive(tmp_path):
    src = _make_file(tmp_path, "video1.mp4")
    zip_path = str(tmp_path / "batch.zip")
    z = BatchZipper(zip_path)
    z.add_and_delete(src, "video1.mp4")
    z.close()
    with zipfile.ZipFile(zip_path) as zf:
        assert zf.namelist() == ["video1.mp4"]
        assert zf.read("video1.mp4") == b"fake video bytes"


def test_add_and_delete_removes_the_source_file_immediately(tmp_path):
    src = _make_file(tmp_path, "video1.mp4")
    z = BatchZipper(str(tmp_path / "batch.zip"))
    z.add_and_delete(src, "video1.mp4")
    assert not os.path.exists(src)
    z.close()


def test_archive_uses_zip_stored_not_deflate(tmp_path):
    src = _make_file(tmp_path, "video1.mp4")
    zip_path = str(tmp_path / "batch.zip")
    z = BatchZipper(zip_path)
    z.add_and_delete(src, "video1.mp4")
    z.close()
    with zipfile.ZipFile(zip_path) as zf:
        info = zf.getinfo("video1.mp4")
        assert info.compress_type == zipfile.ZIP_STORED


def test_duplicate_filenames_get_a_collision_suffix(tmp_path):
    src1 = _make_file(tmp_path, "a.jpg", b"first")
    src2 = _make_file(tmp_path, "b.jpg", b"second")
    zip_path = str(tmp_path / "batch.zip")
    z = BatchZipper(zip_path)
    name1 = z.add_and_delete(src1, "photo.jpg")
    name2 = z.add_and_delete(src2, "photo.jpg")
    z.close()
    assert name1 == "photo.jpg"
    assert name2 == "photo (1).jpg"
    assert name1 != name2
    with zipfile.ZipFile(zip_path) as zf:
        assert set(zf.namelist()) == {"photo.jpg", "photo (1).jpg"}


def test_multiple_items_all_end_up_in_the_same_archive(tmp_path):
    zip_path = str(tmp_path / "batch.zip")
    z = BatchZipper(zip_path)
    for i in range(5):
        src = _make_file(tmp_path, f"item{i}.mp4", f"content-{i}".encode())
        z.add_and_delete(src, f"item{i}.mp4")
    z.close()
    with zipfile.ZipFile(zip_path) as zf:
        assert len(zf.namelist()) == 5


def test_a_failed_item_never_reaches_add_and_delete_and_leaves_the_zip_valid(tmp_path):
    # Simulates the batch loop's own contract: a download that raises never
    # calls add_and_delete at all for that item, so the archive just has one
    # fewer entry - it must still close as a valid, readable zip.
    src = _make_file(tmp_path, "ok.mp4")
    zip_path = str(tmp_path / "batch.zip")
    z = BatchZipper(zip_path)
    z.add_and_delete(src, "ok.mp4")
    z.close()
    with zipfile.ZipFile(zip_path) as zf:
        assert zf.testzip() is None
        assert zf.namelist() == ["ok.mp4"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest remote_web/tests/test_zipper.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'remote_web.zipper'`

- [ ] **Step 3: Implement `remote_web/zipper.py`**

```python
"""Incremental .zip assembly for a batch job (spec §5.3) - one archive stays
open for the batch's duration; each item is appended and its raw file
deleted immediately, capping peak disk usage near BATCH_CONCURRENCY
in-flight raw files instead of the whole batch's total size.
"""

import os
import threading
import zipfile


def _unique_archive_name(existing_names, filename):
    # Same collision-suffix approach as backend.download.get_unique_filename,
    # but against the zip's own entry names instead of a directory listing -
    # a zip archive has no directory to os.path.exists() against.
    if filename not in existing_names:
        existing_names.add(filename)
        return filename
    base, ext = os.path.splitext(filename)
    counter = 1
    while True:
        candidate = f"{base} ({counter}){ext}"
        if candidate not in existing_names:
            existing_names.add(candidate)
            return candidate
        counter += 1


class BatchZipper:
    def __init__(self, zip_path):
        self.zip_path = zip_path
        self._lock = threading.Lock()
        self._names = set()
        # ZIP_STORED - no compression. The contents are already-compressed
        # video/image files, so the module's default ZIP_DEFLATE would just
        # burn CPU on the deployment Mac for no size reduction (§5.3).
        self._zf = zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_STORED)

    def add_and_delete(self, source_path, filename):
        # write() + the uniquing decision happen under one lock so two batch
        # items finishing at the same instant can't race on the same
        # candidate name or interleave writes into the same ZipFile handle.
        with self._lock:
            arcname = _unique_archive_name(self._names, filename)
            self._zf.write(source_path, arcname=arcname)
        try:
            os.remove(source_path)
        except OSError:
            pass
        return arcname

    def close(self):
        with self._lock:
            self._zf.close()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest remote_web/tests/test_zipper.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add remote_web/zipper.py remote_web/tests/test_zipper.py
git commit -m "remote_web: add incremental ZIP_STORED batch assembly"
```

---

### Task 7: `reaper.py` — filesystem-mtime temp-dir sweep

**Files:**
- Create: `remote_web/reaper.py`
- Modify: `remote_web/app.py`
- Test: `remote_web/tests/test_reaper.py`

**Interfaces:**
- Consumes: `remote_web.config.TEMP_ROOT`, `REAPER_SWEEP_INTERVAL_SECONDS`, `REAPER_STALE_MINUTES` (Task 1).
- Produces: `remote_web.reaper.sweep(temp_root, stale_minutes) -> list[str]` (paths removed), `start_background_sweeper(temp_root=None, interval_seconds=None, stale_minutes=None) -> threading.Thread`.

- [ ] **Step 1: Write the failing tests**

```python
# remote_web/tests/test_reaper.py
"""Filesystem-mtime sweep of stale temp dirs - no dependency on in-memory
job state, so it survives a launchd restart (spec §5.4)."""

import os
import time

from remote_web import reaper


def _make_dir_with_file(tmp_path, name, age_seconds):
    d = tmp_path / name
    d.mkdir()
    f = d / "video.mp4"
    f.write_bytes(b"x")
    old_time = time.time() - age_seconds
    os.utime(f, (old_time, old_time))
    os.utime(d, (old_time, old_time))
    return d


def test_sweep_deletes_a_dir_older_than_the_stale_window(tmp_path):
    stale_dir = _make_dir_with_file(tmp_path, "job-old", age_seconds=40 * 60)
    removed = reaper.sweep(str(tmp_path), stale_minutes=30)
    assert str(stale_dir) in removed
    assert not stale_dir.exists()


def test_sweep_keeps_a_dir_newer_than_the_stale_window(tmp_path):
    fresh_dir = _make_dir_with_file(tmp_path, "job-fresh", age_seconds=5 * 60)
    removed = reaper.sweep(str(tmp_path), stale_minutes=30)
    assert str(fresh_dir) not in removed
    assert fresh_dir.exists()


def test_sweep_ignores_files_directly_under_temp_root(tmp_path):
    stray_file = tmp_path / "not-a-job-dir.txt"
    stray_file.write_text("x")
    old_time = time.time() - 40 * 60
    os.utime(stray_file, (old_time, old_time))
    removed = reaper.sweep(str(tmp_path), stale_minutes=30)
    assert removed == []
    assert stray_file.exists()


def test_sweep_handles_a_nonexistent_temp_root_gracefully(tmp_path):
    missing = str(tmp_path / "does-not-exist")
    assert reaper.sweep(missing, stale_minutes=30) == []


def test_sweep_catches_a_dir_with_no_in_memory_job_record(tmp_path):
    # Simulates a directory orphaned by a mid-download launchd restart -
    # backend.jobs.jobs has nothing for it at all, proving the mtime-only
    # design doesn't depend on job state surviving a restart. This test
    # deliberately never touches backend.jobs - that's the point.
    orphan_dir = _make_dir_with_file(tmp_path, "orphaned-by-restart", age_seconds=40 * 60)
    removed = reaper.sweep(str(tmp_path), stale_minutes=30)
    assert str(orphan_dir) in removed


def test_sweep_uses_the_newest_file_inside_a_dir_not_the_dir_itself(tmp_path):
    # A dir created 40 minutes ago whose file was just written (an in-flight
    # download still actively writing into an old temp dir) must NOT be
    # swept - only the newest mtime inside it matters.
    d = tmp_path / "job-active"
    d.mkdir()
    old_time = time.time() - 40 * 60
    os.utime(d, (old_time, old_time))
    f = d / "video.mp4.part"
    f.write_bytes(b"x")  # freshly written, mtime is "now"
    removed = reaper.sweep(str(tmp_path), stale_minutes=30)
    assert str(d) not in removed


def test_start_background_sweeper_runs_as_a_daemon_thread(tmp_path, monkeypatch):
    from remote_web import config

    monkeypatch.setattr(config, "REAPER_SWEEP_INTERVAL_SECONDS", 3600)
    t = reaper.start_background_sweeper(temp_root=str(tmp_path), interval_seconds=3600, stale_minutes=30)
    assert t.daemon is True
    assert t.is_alive()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest remote_web/tests/test_reaper.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'remote_web.reaper'`

- [ ] **Step 3: Implement `remote_web/reaper.py`**

```python
"""Filesystem-mtime sweep of remote_web's temp-dir root (spec §5.4) - no
dependency on in-memory job state, so it correctly catches both a
finished-but-unfetched job AND any directory orphaned by a mid-download
launchd restart (a restart wipes backend.jobs.jobs, which a job-dict-driven
reaper would have needed to consult - see the spec's v2->v3 changelog for
why that earlier design was broken by construction).
"""

import os
import shutil
import threading
import time

from remote_web import config


def _newest_mtime(dir_path):
    newest = os.path.getmtime(dir_path)
    for root, _dirs, files in os.walk(dir_path):
        for name in files:
            try:
                newest = max(newest, os.path.getmtime(os.path.join(root, name)))
            except OSError:
                pass
    return newest


def sweep(temp_root, stale_minutes):
    # Deletes every immediate subdirectory of temp_root whose newest
    # contained file (or the directory itself, if empty) is older than
    # stale_minutes. Returns the list of paths removed - for test/log
    # visibility only, callers don't need to act on it.
    if not os.path.isdir(temp_root):
        return []
    cutoff = time.time() - stale_minutes * 60
    removed = []
    for name in os.listdir(temp_root):
        path = os.path.join(temp_root, name)
        if not os.path.isdir(path):
            continue
        try:
            if _newest_mtime(path) < cutoff:
                shutil.rmtree(path, ignore_errors=True)
                removed.append(path)
        except OSError:
            pass
    return removed


def start_background_sweeper(temp_root=None, interval_seconds=None, stale_minutes=None):
    # One lightweight daemon thread, started once at app startup - no
    # external scheduler/cron needed (§5.4).
    temp_root = temp_root or config.TEMP_ROOT
    interval_seconds = interval_seconds or config.REAPER_SWEEP_INTERVAL_SECONDS
    stale_minutes = stale_minutes if stale_minutes is not None else config.REAPER_STALE_MINUTES

    def _loop():
        while True:
            sweep(temp_root, stale_minutes)
            time.sleep(interval_seconds)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    return t
```

- [ ] **Step 4: Wire the sweeper into `remote_web/app.py`'s startup**

Add to the imports in `remote_web/app.py`:

```python
from remote_web import config, ffmpeg_locator, reaper, trust
```

and after `_check_ffmpeg_at_startup()`:

```python
_check_ffmpeg_at_startup()
reaper.start_background_sweeper()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest remote_web/tests/test_reaper.py -v`
Expected: PASS (7 tests)

- [ ] **Step 6: Commit**

```bash
git add remote_web/reaper.py remote_web/app.py remote_web/tests/test_reaper.py
git commit -m "remote_web: add filesystem-mtime temp-dir reaper"
```

---

### Task 8: `routes/settings.py` — language + shared `playlist_limit`

**Files:**
- Create: `remote_web/routes/settings.py`
- Modify: `remote_web/app.py`
- Test: `remote_web/tests/test_settings_routes.py`

**Interfaces:**
- Consumes: `remote_web.config.STATE_FILE` (Task 1, to colocate `settings.json` next to it); `backend.config.load_session()`/`save_session()` (existing, unmodified — the ONE deliberate exception to remote_web keeping its own state, since `backend.extraction.extract_video_info` already reads `playlist_limit` from there, and the frontend's Playlist Limit control renders in remote mode too, unlike Target Path/Cookies).
- Produces: `remote_web.routes.settings.bp` (Flask `Blueprint`, mounted into `app.py`).

- [ ] **Step 1: Write the failing tests**

```python
# remote_web/tests/test_settings_routes.py
"""GET/POST /api/settings - language (remote_web's own file) + playlist_limit
(proxied through to backend.config's session, since
backend.extraction.extract_video_info reads it from there and the frontend's
Playlist Limit control is NOT gated behind isLocal(), unlike Target Path)."""

import pytest

from backend import config as backend_config
from remote_web import config
from remote_web.app import app as remote_app


@pytest.fixture
def client(isolated_state_file, tmp_path, monkeypatch):
    monkeypatch.setattr(backend_config, "CONFIG_FILE", str(tmp_path / "backend-config.json"))
    remote_app.config["TESTING"] = True
    return remote_app.test_client()


def _unlock(client):
    token = config.get_or_create_token()
    client.post("/unlock", data={"token": token})


def test_get_settings_requires_trust(client):
    resp = client.get("/api/settings")
    assert resp.status_code == 401


def test_get_settings_defaults(client):
    _unlock(client)
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["language"] == "en"
    assert body["playlist_limit"] == 100


def test_post_settings_persists_language(client):
    _unlock(client)
    resp = client.post("/api/settings", json={"language": "vi"})
    assert resp.status_code == 200
    assert resp.get_json()["language"] == "vi"
    # Persists across requests, not just echoed back.
    assert client.get("/api/settings").get_json()["language"] == "vi"


def test_post_settings_playlist_limit_reaches_backend_config(client):
    _unlock(client)
    client.post("/api/settings", json={"playlist_limit": 500})
    assert backend_config.load_session()["playlist_limit"] == 500


def test_post_settings_playlist_limit_is_readable_back(client):
    _unlock(client)
    client.post("/api/settings", json={"playlist_limit": 30})
    resp = client.get("/api/settings")
    assert resp.get_json()["playlist_limit"] == 30


def test_post_settings_partial_update_does_not_reset_the_other_field(client):
    _unlock(client)
    client.post("/api/settings", json={"language": "vi"})
    client.post("/api/settings", json={"playlist_limit": 200})
    resp = client.get("/api/settings").get_json()
    assert resp["language"] == "vi"
    assert resp["playlist_limit"] == 200
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest remote_web/tests/test_settings_routes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'remote_web.routes.settings'`

- [ ] **Step 3: Implement `remote_web/routes/settings.py`**

```python
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

_SETTINGS_FILE = os.path.join(os.path.dirname(config.STATE_FILE), "settings.json")
_DEFAULT_LANGUAGE = "en"


def _load_language():
    if not os.path.exists(_SETTINGS_FILE):
        return _DEFAULT_LANGUAGE
    try:
        with open(_SETTINGS_FILE, "r") as f:
            return json.load(f).get("language", _DEFAULT_LANGUAGE)
    except (OSError, json.JSONDecodeError):
        return _DEFAULT_LANGUAGE


def _save_language(language):
    os.makedirs(os.path.dirname(_SETTINGS_FILE), exist_ok=True)
    with open(_SETTINGS_FILE, "w") as f:
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
```

- [ ] **Step 4: Mount the blueprint in `remote_web/app.py`**

Add to the imports:

```python
from remote_web.routes import health as health_routes
from remote_web.routes import settings as settings_routes
```

and after `app.register_blueprint(health_routes.bp)`:

```python
app.register_blueprint(settings_routes.bp)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest remote_web/tests/test_settings_routes.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add remote_web/routes/settings.py remote_web/app.py remote_web/tests/test_settings_routes.py
git commit -m "remote_web: add /api/settings (language + shared playlist_limit)"
```

---

### Task 9: `routes/media.py` — `POST /api/check`

**Files:**
- Create: `remote_web/routes/media.py`
- Modify: `remote_web/app.py`
- Test: `remote_web/tests/test_media_routes.py`

**Interfaces:**
- Consumes: `backend.classify.classify_url`, `backend.extraction.extract_video_info`/`describe_extraction_error`/`flat_playlist_items`/`story_playlist_items`/`resolve_thumbnail`/`qualities_for`/`format_duration`, `backend.instagram.fetch_instagram_media_any`/`instagram_check_response`, `backend.threads.fetch_threads_media_any`/`ThreadsAuthError`/`threads_cookiefile_candidates`, `backend.linkedin.fetch_linkedin_image_post`/`LinkedInUnsupportedPostError`, `backend.tiktok.fetch_tiktok_photo_post`, `backend.cookies.instagram_cookiefile_candidates`/`_cleanup_temp_cookiefiles`, `backend.config.get_cookies_path` (aliased `backend_config`), `backend.paths.log_exception` (all existing, unmodified).
- Produces: `remote_web.routes.media.bp` (Flask `Blueprint`, mounted into `app.py`); this task adds only `POST /api/check` to it — Tasks 10 and 11 add `/api/download` and `/api/download-batch` to the same blueprint/file.

This route is a straight port of `backend/app.py`'s `check_link()` (`backend/app.py:158-316`) with exactly two removals: the `if cls.platform == "Instagram" and not is_local_request(): return 403` block and the equivalent Threads block. There is no `is_local_request()` concept in `remote_web` at all — trust was already established globally by the `before_request` gate in Task 4.

- [ ] **Step 1: Write the failing tests**

```python
# remote_web/tests/test_media_routes.py
"""POST /api/check, /api/download, /api/download-batch - mirrors
tests/test_api.py's conventions (mocking backend.extraction.extract_video_info,
backend.download.download_one_video, etc.) but proves the one behavior that
must differ from backend/app.py: Instagram/Threads are NOT rejected here."""

import pytest

from backend import cookies as backend_cookies
from backend import extraction as extraction_module
from backend import instagram as instagram_module
from remote_web import config
from remote_web.app import app as remote_app


@pytest.fixture
def client(isolated_state_file, tmp_path, monkeypatch):
    from backend import config as backend_config

    monkeypatch.setattr(backend_config, "CONFIG_FILE", str(tmp_path / "backend-config.json"))
    remote_app.config["TESTING"] = True
    return remote_app.test_client()


@pytest.fixture(autouse=True)
def trusted(client):
    token = config.get_or_create_token()
    client.post("/unlock", data={"token": token})
    return client


@pytest.fixture(autouse=True)
def no_real_browser_cookies(monkeypatch):
    # Same reasoning as tests/conftest.py's no_browser_cookie_scan fixture -
    # never let a test hit the real machine's browser cookie DBs.
    monkeypatch.setattr(backend_cookies, "cookiefiles_from_browsers", lambda domain="instagram.com": [])


# ---- /api/check ----


def test_check_requires_trust(monkeypatch):
    remote_app.config["TESTING"] = True
    anon_client = remote_app.test_client()
    resp = anon_client.post("/api/check", json={"url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"})
    assert resp.status_code == 401


def test_check_missing_url_returns_400(client):
    resp = client.post("/api/check", json={})
    assert resp.status_code == 400


def test_check_returns_single_video_info(client, monkeypatch):
    monkeypatch.setattr(
        extraction_module, "extract_video_info",
        lambda cls: {"title": "Test Video", "uploader": "someone", "duration": 65, "formats": []},
    )
    resp = client.post("/api/check", json={"url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["type"] == "video"
    assert body["title"] == "Test Video"
    assert body["platform"] == "YouTube"


def test_check_instagram_post_is_not_rejected(client, monkeypatch):
    # The one behavior that must differ from backend/app.py's check_link():
    # no is_local_request() gate exists here at all.
    monkeypatch.setattr(
        backend_cookies, "instagram_cookiefile_candidates", lambda: ["/fake/cookies.txt"]
    )
    monkeypatch.setattr(
        instagram_module, "fetch_instagram_media_any",
        lambda url, cookiefiles: {"title": "IG Post", "items": [{"kind": "image", "url": "https://cdn/x.jpg", "thumbnail": "https://cdn/x.jpg"}]},
    )
    resp = client.post("/api/check", json={"url": "https://www.instagram.com/p/DYTRs5Loe6A/"})
    assert resp.status_code == 200
    assert resp.get_json()["type"] == "video"


def test_check_instagram_with_no_session_returns_friendly_error_not_403(client, monkeypatch):
    monkeypatch.setattr(backend_cookies, "instagram_cookiefile_candidates", lambda: [])
    resp = client.post("/api/check", json={"url": "https://www.instagram.com/p/DYTRs5Loe6A/"})
    assert resp.status_code == 400  # not 403 - this app has no local/remote concept
    assert "Instagram" in resp.get_json()["error"]


def test_check_extraction_failure_returns_friendly_message(client, monkeypatch):
    import yt_dlp

    def raise_error(cls):
        raise yt_dlp.utils.DownloadError("Video unavailable")

    monkeypatch.setattr(extraction_module, "extract_video_info", raise_error)
    resp = client.post("/api/check", json={"url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"})
    assert resp.status_code == 400
    assert "github.com" not in resp.get_json()["error"].lower()


def test_check_playlist_returns_items(client, monkeypatch):
    monkeypatch.setattr(
        extraction_module, "extract_video_info",
        lambda cls: {
            "_type": "playlist", "title": "My Playlist",
            "entries": [
                {"id": "a", "title": "Video A", "duration": 30, "url": "https://youtube.com/watch?v=a"},
                {"id": "b", "title": "Video B", "duration": 40, "url": "https://youtube.com/watch?v=b"},
            ],
        },
    )
    resp = client.post("/api/check", json={"url": "https://www.youtube.com/playlist?list=PL123"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["type"] == "playlist"
    assert len(body["items"]) == 2
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest remote_web/tests/test_media_routes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'remote_web.routes.media'`

- [ ] **Step 3: Implement `remote_web/routes/media.py` (check-only for now)**

```python
"""POST /api/check, /api/download, /api/download-batch.

This is a straight port of backend/app.py's check_link()/start_download()/
start_batch_download() (spec §2), with the local/remote branching removed
entirely: trust was already established globally by remote_web/app.py's
before_request gate, so there is no is_local_request() concept here at all,
Instagram/Threads are never rejected, and every download always streams
back to the requesting device (a fresh temp dir under remote_web.config.TEMP_ROOT
instead of the native app's configured save folder).

Error-message constants are intentionally duplicated from backend/app.py
rather than imported from it - backend.app is deliberately the one module
remote_web never depends on (it's the module THIS blueprint replaces), and
importing a module-level string from it would silently couple this file to
an internal a future backend/app.py change could rename without warning.
"""

import os

import yt_dlp
from flask import Blueprint, jsonify, request

from backend import classify
from backend import config as backend_config
from backend import cookies, download, extraction, instagram, jobs, linkedin, paths, threads, tiktok
from remote_web import config, ffmpeg_locator

bp = Blueprint("media", __name__)

INSTAGRAM_NO_SESSION_ERROR = "❌ Lỗi: Không tìm thấy phiên đăng nhập Instagram nào trên trình duyệt của máy này. Vui lòng đăng nhập Instagram trên Chrome/Safari/Brave (hoặc thêm cookies.txt thủ công trong Settings) rồi thử lại."
THREADS_AUTH_ERROR = "❌ Lỗi: Cần một trình duyệt đã đăng nhập Threads (threads.com) trên máy này để tải bài viết. Vui lòng đăng nhập rồi thử lại."
THREADS_EXTRACT_ERROR = "❌ Lỗi: Không thể trích xuất dữ liệu từ liên kết này. Vui lòng kiểm tra lại liên kết hoặc trạng thái công khai của nội dung."
LINKEDIN_DOCUMENT_POST_ERROR = "❌ Lỗi: Bài đăng LinkedIn dạng tài liệu/slide (PDF) hiện chưa được OmniFlow hỗ trợ tải. OmniFlow hiện chỉ hỗ trợ bài đăng LinkedIn dạng video hoặc ảnh."


@bp.post("/api/check")
def check_link():
    data = request.get_json(force=True) or {}
    raw_url = (data.get("url") or "").strip()
    if not raw_url:
        return jsonify({"error": "Missing url"}), 400
    cls = classify.classify_url(raw_url)
    url = cls.url

    # No Instagram/Threads local-only rejection here at all - the whole
    # point of remote_web is that these DO work remotely (spec §1), using
    # the deployment Mac's own logged-in browser session exactly as the
    # native app already does.

    ig_resolver_error = None
    if cls.kind == classify.LinkKind.INSTAGRAM_POST_OR_CAROUSEL:
        candidates = cookies.instagram_cookiefile_candidates()
        if not candidates:
            return jsonify({"error": INSTAGRAM_NO_SESSION_ERROR}), 400
        try:
            media = instagram.fetch_instagram_media_any(url, candidates)
            return jsonify(instagram.instagram_check_response(url, media))
        except Exception as e:
            ig_resolver_error = e
            manual_path = backend_config.get_cookies_path()
            source = (
                "manual Settings cookies.txt"
                if manual_path and manual_path in candidates
                else f"{len(candidates)} browser-auto-extracted session(s)"
            )
            paths.log_exception(
                f"remote_web check_link Instagram resolver failed for all {len(candidates)} candidate(s), source: {source}",
                e,
            )
            print(f"[remote_web] Custom Instagram resolver failed: {e}. Falling through to yt-dlp.")
        finally:
            cookies._cleanup_temp_cookiefiles(candidates)

    if cls.kind == classify.LinkKind.THREADS_POST:
        candidates = threads.threads_cookiefile_candidates()
        last_error = None
        if candidates:
            try:
                media = threads.fetch_threads_media_any(url, candidates)
                return jsonify(instagram.instagram_check_response(url, media))
            except Exception as e:
                last_error = e
            finally:
                cookies._cleanup_temp_cookiefiles(candidates)
        if not candidates or isinstance(last_error, threads.ThreadsAuthError):
            return jsonify({"error": THREADS_AUTH_ERROR}), 400
        return jsonify({"error": THREADS_EXTRACT_ERROR}), 400

    try:
        info = extraction.extract_video_info(cls)
    except yt_dlp.utils.DownloadError as e:
        if cls.platform == "LinkedIn":
            try:
                media = linkedin.fetch_linkedin_image_post(url)
                return jsonify(instagram.instagram_check_response(url, media))
            except linkedin.LinkedInUnsupportedPostError:
                return jsonify({"error": LINKEDIN_DOCUMENT_POST_ERROR}), 400
            except Exception:
                pass
        if cls.platform == "TikTok" and "unsupported url" in str(e).lower():
            try:
                media = tiktok.fetch_tiktok_photo_post(url)
                return jsonify(instagram.instagram_check_response(url, media))
            except Exception:
                pass
        error_to_describe = ig_resolver_error if ig_resolver_error is not None else e
        return jsonify({"error": extraction.describe_extraction_error(url, error_to_describe, backend_config.get_cookies_path())}), 400
    except Exception as e:
        paths.log_exception(f"remote_web check_link ({cls.platform}): {url}", e)
        error_to_describe = ig_resolver_error if ig_resolver_error is not None else e
        return jsonify({"error": extraction.describe_extraction_error(url, error_to_describe, backend_config.get_cookies_path())}), 400

    if not info:
        return jsonify({"error": extraction.describe_extraction_error(url, ig_resolver_error or Exception(""), backend_config.get_cookies_path())}), 400

    if info.get("_type") == "playlist" or "entries" in info:
        entries = [e for e in (info.get("entries") or []) if e]
        is_flat = cls.is_multi
        items = extraction.flat_playlist_items(entries) if is_flat else extraction.story_playlist_items(entries)
        return jsonify({
            "type": "playlist",
            "platform": cls.platform,
            "title": info.get("title") or ("Playlist" if is_flat else "Story"),
            "items": items,
            "truncated": is_flat and len(entries) >= classify.PLAYLIST_ITEM_CAP,
        })

    return jsonify({
        "type": "video",
        "title": info.get("title", "Video"),
        "uploader": info.get("uploader", ""),
        "thumbnail": extraction.resolve_thumbnail(info),
        "platform": cls.platform,
        "qualities": extraction.qualities_for(info),
        "duration": extraction.format_duration(info.get("duration")),
    })
```

- [ ] **Step 4: Mount the blueprint in `remote_web/app.py`**

Add to the imports:

```python
from remote_web.routes import media as media_routes
from remote_web.routes import settings as settings_routes
```

and after `app.register_blueprint(settings_routes.bp)`:

```python
app.register_blueprint(media_routes.bp)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest remote_web/tests/test_media_routes.py -v`
Expected: PASS (7 tests)

- [ ] **Step 6: Commit**

```bash
git add remote_web/routes/media.py remote_web/app.py remote_web/tests/test_media_routes.py
git commit -m "remote_web: add POST /api/check (Instagram/Threads allowed)"
```

---

### Task 10: `routes/media.py` — `POST /api/download` (single item)

**Files:**
- Modify: `remote_web/routes/media.py`
- Modify: `remote_web/tests/test_media_routes.py`

**Interfaces:**
- Consumes: everything Task 9 already imports, plus `backend.download.build_download_options`/`apply_progress_update`/`cleanup_partial_download`/`get_unique_filename`/`download_direct_url` and `backend.jobs.jobs`/`_remove_job_file` (existing, unmodified); `remote_web.ffmpeg_locator.resolve_ffmpeg_binary`/`ffmpeg_unavailable_message` (Task 3); `remote_web.config.TEMP_ROOT` (Task 1).
- Produces: adds `POST /api/download` to `remote_web.routes.media.bp` — returns `{"job_id": str}`, same shape as `backend/app.py`'s route, backed by the same `backend.jobs.jobs` dict.

This is a port of `backend/app.py`'s `start_download()` (`backend/app.py:319-605`) with: no `is_local_request()` branch at all (always stages into a fresh `tempfile.mkdtemp(dir=remote_web.config.TEMP_ROOT)`), and `ffmpeg_locator.resolve_ffmpeg_binary()`/`ffmpeg_unavailable_message()` in place of `paths.get_ffmpeg_path()`/`paths.ffmpeg_unavailable_message()`.

- [ ] **Step 1: Add the failing tests**

Append to `remote_web/tests/test_media_routes.py`:

```python
# ---- /api/download ----

import threading
import time

from backend import download as download_module
from backend import jobs as jobs_module


@pytest.fixture(autouse=True)
def clear_jobs():
    jobs_module.jobs.clear()
    yield
    jobs_module.jobs.clear()


def _wait_for_job(job_id, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = jobs_module.jobs.get(job_id)
        if job and job["status"] in ("done", "error", "cancelled"):
            return job
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} never finished: {jobs_module.jobs.get(job_id)}")


def test_download_requires_trust():
    remote_app.config["TESTING"] = True
    anon_client = remote_app.test_client()
    resp = anon_client.post("/api/download", json={"url": "https://www.youtube.com/watch?v=jNQXAC9IVRw", "title": "x", "quality": "Best"})
    assert resp.status_code == 401


def test_download_missing_ffmpeg_returns_friendly_error(client, monkeypatch, tmp_path):
    monkeypatch.setattr("remote_web.routes.media.ffmpeg_locator.resolve_ffmpeg_binary", lambda: None)
    resp = client.post("/api/download", json={"url": "https://www.youtube.com/watch?v=jNQXAC9IVRw", "title": "x", "quality": "Best"})
    assert resp.status_code == 400
    assert "FFmpeg" in resp.get_json()["error"]


def test_download_always_stages_into_a_temp_dir_not_a_configured_folder(client, monkeypatch, tmp_path):
    monkeypatch.setattr("remote_web.routes.media.ffmpeg_locator.resolve_ffmpeg_binary", lambda: "/fake/ffmpeg")
    monkeypatch.setattr(config, "TEMP_ROOT", str(tmp_path))

    captured = {}

    def fake_ydl_download(opts):
        class FakeYDL:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def download(self_inner, urls):
                captured["outtmpl"] = opts["outtmpl"]
                out_path = opts["outtmpl"].replace(".%(ext)s", ".mp4")
                with open(out_path, "wb") as f:
                    f.write(b"fake mp4 bytes")

        return FakeYDL()

    import yt_dlp

    monkeypatch.setattr(yt_dlp, "YoutubeDL", fake_ydl_download)
    monkeypatch.setattr(download_module, "ensure_h264", lambda *a, **k: None)

    resp = client.post("/api/download", json={"url": "https://www.youtube.com/watch?v=jNQXAC9IVRw", "title": "test video", "quality": "Best"})
    assert resp.status_code == 200
    job_id = resp.get_json()["job_id"]
    job = _wait_for_job(job_id)
    assert job["status"] == "done"
    assert str(tmp_path) in job["filepath"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest remote_web/tests/test_media_routes.py -k download -v`
Expected: FAIL (404, since `/api/download` doesn't exist on the blueprint yet)

- [ ] **Step 3: Add `POST /api/download` to `remote_web/routes/media.py`**

Add these imports at the top of `remote_web/routes/media.py`:

```python
import shutil
import tempfile
import threading
import uuid
```

Append the route (after `check_link`, still inside the same file/blueprint):

```python
def _save_single_cdn_image(job_id, save_dir, title, cdn_url):
    # Same small helper backend/app.py defines privately for its LinkedIn/
    # TikTok single-image fallbacks - reimplemented here (not imported from
    # backend.app) since remote_web deliberately never depends on
    # backend.app, the module this blueprint replaces (see this file's
    # module docstring).
    jpg_path = download.get_unique_filename(save_dir, title, "jpg")
    jobs.jobs[job_id]["filename"] = os.path.basename(jpg_path)
    jobs.jobs[job_id]["filepath"] = jpg_path
    download.download_direct_url(cdn_url, jpg_path, job_id)
    jobs.jobs[job_id]["percent"] = 100
    jobs.jobs[job_id]["text"] = f"Saved: {jobs.jobs[job_id]['filename']}"
    jobs.jobs[job_id]["status"] = "done"


@bp.post("/api/download")
def start_download():
    data = request.get_json(force=True) or {}
    raw_url = (data.get("url") or "").strip()
    if not raw_url:
        return jsonify({"error": "Missing url"}), 400
    cls = classify.classify_url(raw_url)
    url = cls.url
    title = data.get("title") or "Video"
    quality = data.get("quality") or "Best"
    entry_index = data.get("entry_index") or classify.entry_index_from_url(url)

    # Always a fresh temp dir - remote_web has no "local save" mode at all
    # (spec §5.2). Streamed back via GET /api/download-file (Task 12).
    os.makedirs(config.TEMP_ROOT, exist_ok=True)
    remote_temp_dir = tempfile.mkdtemp(dir=config.TEMP_ROOT, prefix="omniflow-remote-")
    save_dir = remote_temp_dir

    ig_candidates = []
    if cls.kind == classify.LinkKind.INSTAGRAM_POST_OR_CAROUSEL:
        ig_candidates = cookies.instagram_cookiefile_candidates()
    if ig_candidates:
        job_id = uuid.uuid4().hex
        jobs.jobs[job_id] = {
            "status": "running", "percent": 0, "text": "Starting...",
            "filename": None, "filepath": None, "cancelled": False,
        }

        def run_instagram():
            try:
                media = instagram.fetch_instagram_media_any(url, ig_candidates)
                items = media["items"]
                idx = (entry_index - 1) if entry_index else 0
                if idx < 0 or idx >= len(items):
                    raise ValueError("Selected item is no longer available")
                item = items[idx]
                cdn_url = item.get("url")
                if not cdn_url:
                    raise ValueError("No downloadable media found")
                ext = "jpg" if item["kind"] == "image" else "mp4"
                final_output_path = download.get_unique_filename(save_dir, title, ext)
                jobs.jobs[job_id]["filename"] = os.path.basename(final_output_path)
                jobs.jobs[job_id]["filepath"] = final_output_path
                download.download_direct_url(cdn_url, final_output_path, job_id)
            except yt_dlp.utils.DownloadCancelled:
                jobs._remove_job_file(job_id)
                jobs.jobs[job_id]["text"] = "Cancelled"
                jobs.jobs[job_id]["status"] = "cancelled"
                return
            except instagram.InstagramAuthError as e:
                jobs._remove_job_file(job_id)
                jobs.jobs[job_id]["text"] = extraction.describe_extraction_error(url, e, ig_candidates[0])
                jobs.jobs[job_id]["status"] = "error"
                return
            except Exception as e:
                print(f"[remote_web download] job {job_id} (instagram) failed: {e}")
                jobs._remove_job_file(job_id)
                jobs.jobs[job_id]["text"] = str(e) or "Download failed"
                jobs.jobs[job_id]["status"] = "error"
                return
            finally:
                cookies._cleanup_temp_cookiefiles(ig_candidates)
            jobs.jobs[job_id]["percent"] = 100
            jobs.jobs[job_id]["text"] = f"Saved: {jobs.jobs[job_id]['filename']}"
            jobs.jobs[job_id]["status"] = "done"

        threading.Thread(target=run_instagram, daemon=True).start()
        return jsonify({"job_id": job_id})

    threads_candidates = []
    if cls.kind == classify.LinkKind.THREADS_POST:
        threads_candidates = threads.threads_cookiefile_candidates()
    if threads_candidates:
        job_id = uuid.uuid4().hex
        jobs.jobs[job_id] = {
            "status": "running", "percent": 0, "text": "Starting...",
            "filename": None, "filepath": None, "cancelled": False,
        }

        def run_threads():
            try:
                media = threads.fetch_threads_media_any(url, threads_candidates)
                items = media["items"]
                idx = (entry_index - 1) if entry_index else 0
                if idx < 0 or idx >= len(items):
                    raise ValueError("Selected item is no longer available")
                item = items[idx]
                cdn_url = item.get("url")
                if not cdn_url:
                    raise ValueError("No downloadable media found")
                ext = "jpg" if item["kind"] == "image" else "mp4"
                final_output_path = download.get_unique_filename(save_dir, title, ext)
                jobs.jobs[job_id]["filename"] = os.path.basename(final_output_path)
                jobs.jobs[job_id]["filepath"] = final_output_path
                download.download_direct_url(cdn_url, final_output_path, job_id)
            except yt_dlp.utils.DownloadCancelled:
                jobs._remove_job_file(job_id)
                jobs.jobs[job_id]["text"] = "Cancelled"
                jobs.jobs[job_id]["status"] = "cancelled"
                return
            except threads.ThreadsAuthError:
                jobs._remove_job_file(job_id)
                jobs.jobs[job_id]["text"] = THREADS_AUTH_ERROR
                jobs.jobs[job_id]["status"] = "error"
                return
            except Exception as e:
                print(f"[remote_web download] job {job_id} (threads) failed: {e}")
                jobs._remove_job_file(job_id)
                jobs.jobs[job_id]["text"] = str(e) or "Download failed"
                jobs.jobs[job_id]["status"] = "error"
                return
            finally:
                cookies._cleanup_temp_cookiefiles(threads_candidates)
            jobs.jobs[job_id]["percent"] = 100
            jobs.jobs[job_id]["text"] = f"Saved: {jobs.jobs[job_id]['filename']}"
            jobs.jobs[job_id]["status"] = "done"

        threading.Thread(target=run_threads, daemon=True).start()
        return jsonify({"job_id": job_id})

    ffmpeg_bin = ffmpeg_locator.resolve_ffmpeg_binary()
    if not ffmpeg_bin:
        return jsonify({"error": ffmpeg_locator.ffmpeg_unavailable_message()}), 400

    ext = "mp3" if "Audio" in quality else "mp4"
    final_output_path = download.get_unique_filename(save_dir, title, ext)
    final_filename = os.path.basename(final_output_path)
    output_path_no_ext = os.path.splitext(final_output_path)[0]

    job_id = uuid.uuid4().hex
    jobs.jobs[job_id] = {
        "status": "running", "percent": 0, "text": "Starting...",
        "filename": final_filename, "filepath": final_output_path, "cancelled": False,
    }

    def run():
        total_streams = 1 if "Audio" in quality else 2
        state = {"stream_index": 0}

        def progress_hook(d):
            if jobs.jobs[job_id]["cancelled"]:
                raise yt_dlp.utils.DownloadCancelled("cancelled by user")
            state["stream_index"] = download.apply_progress_update(jobs.jobs[job_id], d, state["stream_index"], total_streams)

        def postprocessor_hook(d):
            if jobs.jobs[job_id]["cancelled"]:
                raise yt_dlp.utils.DownloadCancelled("cancelled by user")
            if d.get("status") == "started":
                jobs.jobs[job_id]["text"] = "Finalizing..."

        cookies_path = backend_config.get_cookies_path()
        if url and "instagram" in url.lower():
            if not (cookies_path and backend_config.cookies_status_for(cookies_path) == "valid"):
                candidates = cookies.instagram_cookiefile_candidates()
                if candidates:
                    cookies_path = candidates[0]
                    cookies._cleanup_temp_cookiefiles(candidates[1:])

        ydl_opts = download.build_download_options(
            quality, output_path_no_ext, ffmpeg_bin, [progress_hook], [postprocessor_hook], cookies_path, entry_index, url
        )

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            if "Audio" not in quality:
                download.ensure_h264(final_output_path, ffmpeg_bin, job_id)
        except yt_dlp.utils.DownloadCancelled:
            jobs.jobs[job_id]["status"] = "cancelled"
            jobs.jobs[job_id]["text"] = "Cancelled"
            download.cleanup_partial_download(output_path_no_ext)
            shutil.rmtree(remote_temp_dir, ignore_errors=True)
            return
        except yt_dlp.utils.DownloadError as e:
            if cls.platform == "LinkedIn":
                try:
                    linkedin_media = linkedin.fetch_linkedin_image_post(url)
                    _save_single_cdn_image(job_id, save_dir, title, linkedin_media["items"][0]["url"])
                    return
                except yt_dlp.utils.DownloadCancelled:
                    jobs.jobs[job_id]["status"] = "cancelled"
                    jobs.jobs[job_id]["text"] = "Cancelled"
                    return
                except linkedin.LinkedInUnsupportedPostError:
                    jobs.jobs[job_id]["status"] = "error"
                    jobs.jobs[job_id]["text"] = LINKEDIN_DOCUMENT_POST_ERROR
                    return
                except Exception:
                    pass
            if cls.platform == "TikTok" and "unsupported url" in str(e).lower():
                try:
                    tiktok_media = tiktok.fetch_tiktok_photo_post(url)
                    _save_single_cdn_image(job_id, save_dir, title, tiktok_media["items"][0]["url"])
                    return
                except yt_dlp.utils.DownloadCancelled:
                    jobs.jobs[job_id]["status"] = "cancelled"
                    jobs.jobs[job_id]["text"] = "Cancelled"
                    return
                except Exception:
                    pass
            print(f"[remote_web download] job {job_id} failed: {e}")
            jobs.jobs[job_id]["status"] = "error"
            jobs.jobs[job_id]["text"] = extraction.describe_extraction_error(url, e, cookies_path)
            download.cleanup_partial_download(output_path_no_ext)
            shutil.rmtree(remote_temp_dir, ignore_errors=True)
            return
        except Exception as e:
            print(f"[remote_web download] job {job_id} failed: {e}")
            jobs.jobs[job_id]["status"] = "error"
            jobs.jobs[job_id]["text"] = str(e) or "Download failed"
            download.cleanup_partial_download(output_path_no_ext)
            shutil.rmtree(remote_temp_dir, ignore_errors=True)
            return
        finally:
            cookies._cleanup_temp_cookiefiles([ydl_opts.get("cookiefile")])

        jobs.jobs[job_id]["status"] = "done"
        jobs.jobs[job_id]["percent"] = 100
        jobs.jobs[job_id]["text"] = f"Saved: {final_filename}"

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"job_id": job_id})
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest remote_web/tests/test_media_routes.py -k download -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full media test file**

Run: `pytest remote_web/tests/test_media_routes.py -v`
Expected: PASS (10 tests total)

- [ ] **Step 6: Commit**

```bash
git add remote_web/routes/media.py remote_web/tests/test_media_routes.py
git commit -m "remote_web: add POST /api/download (always streams to a temp dir)"
```

---

### Task 11: `routes/media.py` — `POST /api/download-batch` (incremental zip)

**Files:**
- Modify: `remote_web/routes/media.py`
- Modify: `remote_web/tests/test_media_routes.py`

**Interfaces:**
- Consumes: `remote_web.zipper.BatchZipper` (Task 6); everything else already imported by Task 9/10.
- Produces: adds `POST /api/download-batch` to `remote_web.routes.media.bp` — same `{"job_id": str}` response shape, `items_progress` job field, as `backend/app.py`.

This is a port of `backend/app.py`'s `start_batch_download()` (`backend/app.py:616-767`) with: no `is_local_request()` 403 (batch downloads work remotely now, delivered as a zip), `save_dir` always a fresh temp dir under `remote_web.config.TEMP_ROOT`, `ffmpeg_locator` for ffmpeg resolution, and — the one real behavioral addition — each successfully-downloaded item is immediately handed to a `zipper.BatchZipper` and its raw file deleted, instead of being left in `save_dir` (spec §5.3).

- [ ] **Step 1: Add the failing tests**

Append to `remote_web/tests/test_media_routes.py`:

```python
# ---- /api/download-batch ----

import zipfile

from remote_web import zipper as zipper_module


def test_download_batch_requires_trust():
    remote_app.config["TESTING"] = True
    anon_client = remote_app.test_client()
    resp = anon_client.post("/api/download-batch", json={"url": "https://www.youtube.com/playlist?list=PL1", "quality": "Best", "items": []})
    assert resp.status_code == 401


def test_download_batch_no_items_returns_400(client):
    resp = client.post("/api/download-batch", json={"url": "https://www.youtube.com/playlist?list=PL1", "quality": "Best", "items": []})
    assert resp.status_code == 400


def test_download_batch_produces_a_zip_with_every_item(client, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "TEMP_ROOT", str(tmp_path))
    monkeypatch.setattr("remote_web.routes.media.ffmpeg_locator.resolve_ffmpeg_binary", lambda: "/fake/ffmpeg")

    def fake_download_one_video(url, save_dir, title, quality, ffmpeg_bin, job_id, entry_index=None, on_progress=None):
        out = os.path.join(save_dir, f"{title}.mp4")
        with open(out, "wb") as f:
            f.write(b"fake video")
        if on_progress:
            on_progress(100)
        return out

    monkeypatch.setattr(download_module, "download_one_video", fake_download_one_video)

    resp = client.post("/api/download-batch", json={
        "url": "https://www.youtube.com/playlist?list=PL1",
        "quality": "Best",
        "items": [
            {"title": "Video A", "url": "https://youtube.com/watch?v=a"},
            {"title": "Video B", "url": "https://youtube.com/watch?v=b"},
        ],
    })
    assert resp.status_code == 200
    job_id = resp.get_json()["job_id"]
    job = _wait_for_job(job_id)
    assert job["status"] == "done"
    assert job["saved_count"] == 2
    assert job["filepath"].endswith(".zip")
    with zipfile.ZipFile(job["filepath"]) as zf:
        assert len(zf.namelist()) == 2
        assert zf.getinfo(zf.namelist()[0]).compress_type == zipfile.ZIP_STORED


def test_download_batch_deletes_raw_files_as_it_goes(client, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "TEMP_ROOT", str(tmp_path))
    monkeypatch.setattr("remote_web.routes.media.ffmpeg_locator.resolve_ffmpeg_binary", lambda: "/fake/ffmpeg")
    written_paths = []

    def fake_download_one_video(url, save_dir, title, quality, ffmpeg_bin, job_id, entry_index=None, on_progress=None):
        out = os.path.join(save_dir, f"{title}.mp4")
        with open(out, "wb") as f:
            f.write(b"fake video")
        written_paths.append(out)
        if on_progress:
            on_progress(100)
        return out

    monkeypatch.setattr(download_module, "download_one_video", fake_download_one_video)

    resp = client.post("/api/download-batch", json={
        "url": "https://www.youtube.com/playlist?list=PL1",
        "quality": "Best",
        "items": [{"title": "Video A", "url": "https://youtube.com/watch?v=a"}],
    })
    job_id = resp.get_json()["job_id"]
    _wait_for_job(job_id)
    assert not os.path.exists(written_paths[0])


def test_download_batch_partial_failure_still_saves_the_rest(client, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "TEMP_ROOT", str(tmp_path))
    monkeypatch.setattr("remote_web.routes.media.ffmpeg_locator.resolve_ffmpeg_binary", lambda: "/fake/ffmpeg")

    def fake_download_one_video(url, save_dir, title, quality, ffmpeg_bin, job_id, entry_index=None, on_progress=None):
        if title == "Broken":
            raise ValueError("boom")
        out = os.path.join(save_dir, f"{title}.mp4")
        with open(out, "wb") as f:
            f.write(b"fake video")
        if on_progress:
            on_progress(100)
        return out

    monkeypatch.setattr(download_module, "download_one_video", fake_download_one_video)

    resp = client.post("/api/download-batch", json={
        "url": "https://www.youtube.com/playlist?list=PL1",
        "quality": "Best",
        "items": [
            {"title": "Broken", "url": "https://youtube.com/watch?v=broken"},
            {"title": "Good", "url": "https://youtube.com/watch?v=good"},
        ],
    })
    job_id = resp.get_json()["job_id"]
    job = _wait_for_job(job_id)
    assert job["status"] == "done"
    assert job["saved_count"] == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest remote_web/tests/test_media_routes.py -k download_batch -v`
Expected: FAIL (404, `/api/download-batch` doesn't exist yet)

- [ ] **Step 3: Add `POST /api/download-batch` to `remote_web/routes/media.py`**

Add to the imports at the top of the file:

```python
import time
from concurrent.futures import ThreadPoolExecutor

from remote_web import zipper as zipper_module
```

Append the route:

```python
# How many playlist items download at once - same value and rationale as
# backend/app.py's BATCH_CONCURRENCY (YouTube throttles each stream, so
# independent streams add up; too many at once trips rate limits).
BATCH_CONCURRENCY = 3


@bp.post("/api/download-batch")
def start_batch_download():
    data = request.get_json(force=True) or {}
    cls = classify.classify_url((data.get("url") or "").strip())
    url = cls.url
    quality = data.get("quality") or "Best"
    items = data.get("items") or []
    if not items:
        return jsonify({"error": "No items selected"}), 400

    # No is_local_request() gate - batch downloads work remotely here,
    # delivered as a single .zip (spec §5.3), unlike backend/app.py where
    # this route is local-only (a remote .zip was scoped out there).

    ffmpeg_bin = ffmpeg_locator.resolve_ffmpeg_binary()
    if not ffmpeg_bin:
        return jsonify({"error": ffmpeg_locator.ffmpeg_unavailable_message()}), 400

    os.makedirs(config.TEMP_ROOT, exist_ok=True)
    save_dir = tempfile.mkdtemp(dir=config.TEMP_ROOT, prefix="omniflow-remote-batch-items-")

    is_ig_carousel = cls.kind == classify.LinkKind.INSTAGRAM_POST_OR_CAROUSEL
    is_tiktok_photo = cls.platform == "TikTok"

    job_id = uuid.uuid4().hex
    total = len(items)
    jobs.jobs[job_id] = {
        "status": "running", "percent": 0, "text": "Starting...",
        "filename": None, "filepath": None, "cancelled": False,
        "item": 0, "total": total,
        "items_progress": [
            {"title": (it.get("title") or f"Video {i + 1}"), "status": "pending", "percent": 0}
            for i, it in enumerate(items)
        ],
    }

    def run_batch():
        prog = jobs.jobs[job_id]["items_progress"]
        state = {"saved": 0, "failed": 0}
        media_holder = {"media": None}
        ig_candidates = []
        lock = threading.Lock()

        # A batch job's own zip dir - separate from `save_dir` (where raw
        # per-item files land transiently before being zipped and deleted).
        zip_dir = tempfile.mkdtemp(dir=config.TEMP_ROOT, prefix="omniflow-remote-batch-zip-")
        zip_name = download.sanitize_filename(f"{cls.platform}_{time.strftime('%Y%m%d_%H%M%S')}") + ".zip"
        zip_path = os.path.join(zip_dir, zip_name)
        zipper = zipper_module.BatchZipper(zip_path)

        def recompute_overall():
            jobs.jobs[job_id]["percent"] = min(100.0, sum(p["percent"] for p in prog) / total)
            jobs.jobs[job_id]["item"] = sum(1 for p in prog if p["status"] in ("done", "error"))

        def download_item(i, item):
            p = prog[i]
            if jobs.jobs[job_id]["cancelled"]:
                return
            p["status"] = "downloading"
            item_title = item.get("title") or f"Video {i + 1}"

            def on_progress(pct, p=p):
                p["percent"] = pct
                recompute_overall()

            try:
                if is_ig_carousel or is_tiktok_photo:
                    idx = item.get("entry_index") or (i + 1)
                    node = media_holder["media"]["items"][idx - 1]
                    cdn_url = node.get("url")
                    if not cdn_url:
                        raise ValueError("No downloadable media found")
                    ext = "jpg" if node["kind"] == "image" else "mp4"
                    out = download.get_unique_filename(save_dir, item_title, ext)
                    download.download_direct_url(cdn_url, out, job_id, on_progress=on_progress)
                elif item.get("url"):
                    out = download.download_one_video(item["url"], save_dir, item_title, quality, ffmpeg_bin, job_id, on_progress=on_progress)
                elif item.get("entry_index"):
                    out = download.download_one_video(url, save_dir, item_title, quality, ffmpeg_bin, job_id, entry_index=item["entry_index"], on_progress=on_progress)
                else:
                    p["status"] = "error"
                    with lock:
                        state["failed"] += 1
                    recompute_overall()
                    return
                # Incremental zip (§5.3): append then delete the raw file
                # immediately - peak disk usage stays near BATCH_CONCURRENCY
                # in-flight files instead of the whole batch's total size.
                zipper.add_and_delete(out, os.path.basename(out))
                p["percent"] = 100
                p["status"] = "done"
                with lock:
                    state["saved"] += 1
            except yt_dlp.utils.DownloadCancelled:
                p["status"] = "error"
            except Exception as e:
                print(f"[remote_web batch] job {job_id} item {i + 1}/{total} failed: {e}")
                p["status"] = "error"
                with lock:
                    state["failed"] += 1
            recompute_overall()

        try:
            if is_ig_carousel:
                ig_candidates = cookies.instagram_cookiefile_candidates()
                if not ig_candidates:
                    raise instagram.InstagramAuthError("Instagram requires a logged-in session (cookies).")
                media_holder["media"] = instagram.fetch_instagram_media_any(url, ig_candidates)
            elif is_tiktok_photo:
                media_holder["media"] = tiktok.fetch_tiktok_photo_post(url)

            with ThreadPoolExecutor(max_workers=min(BATCH_CONCURRENCY, total)) as ex:
                futures = [ex.submit(download_item, i, item) for i, item in enumerate(items)]
                for f in futures:
                    f.result()
        except Exception as e:
            print(f"[remote_web batch] job {job_id} failed: {e}")
            cookies._cleanup_temp_cookiefiles(ig_candidates)
            zipper.close()
            shutil.rmtree(zip_dir, ignore_errors=True)
            shutil.rmtree(save_dir, ignore_errors=True)
            jobs.jobs[job_id]["text"] = extraction.describe_extraction_error(url, e) if is_ig_carousel else (str(e) or "Download failed")
            jobs.jobs[job_id]["status"] = "error"
            return

        cookies._cleanup_temp_cookiefiles(ig_candidates)
        zipper.close()
        shutil.rmtree(save_dir, ignore_errors=True)  # every successful item was already moved into the zip
        saved, failed = state["saved"], state["failed"]
        if jobs.jobs[job_id]["cancelled"]:
            shutil.rmtree(zip_dir, ignore_errors=True)
            jobs.jobs[job_id]["text"] = f"Cancelled (saved {saved} of {total})"
            jobs.jobs[job_id]["status"] = "cancelled"
            return
        jobs.jobs[job_id]["percent"] = 100
        jobs.jobs[job_id]["saved_count"] = saved
        if not saved:
            shutil.rmtree(zip_dir, ignore_errors=True)
            jobs.jobs[job_id]["text"] = "Could not download any item"
            jobs.jobs[job_id]["status"] = "error"
            return
        jobs.jobs[job_id]["filename"] = os.path.basename(zip_path)
        jobs.jobs[job_id]["filepath"] = zip_path
        jobs.jobs[job_id]["text"] = f"Saved {saved} of {total} videos" + (f" ({failed} failed)" if failed else "")
        jobs.jobs[job_id]["status"] = "done"

    threading.Thread(target=run_batch, daemon=True).start()
    return jsonify({"job_id": job_id})
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest remote_web/tests/test_media_routes.py -k download_batch -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Run the full media test file**

Run: `pytest remote_web/tests/test_media_routes.py -v`
Expected: PASS (15 tests total)

- [ ] **Step 6: Commit**

```bash
git add remote_web/routes/media.py remote_web/tests/test_media_routes.py
git commit -m "remote_web: add POST /api/download-batch (incremental ZIP_STORED)"
```

---

### Task 12: `routes/jobs.py` — progress, cancel, download-file

**Files:**
- Create: `remote_web/routes/jobs.py`
- Modify: `remote_web/app.py`
- Test: `remote_web/tests/test_jobs_routes.py`

**Interfaces:**
- Consumes: `backend.jobs.jobs` (existing, unmodified — shared in-process state with Tasks 9-11's routes, since they're the same Python process).
- Produces: `remote_web.routes.jobs.bp` (Flask `Blueprint`, mounted into `app.py`); `GET /api/progress/<job_id>`, `POST /api/cancel/<job_id>`, `GET /api/download-file/<job_id>` — identical response shapes to `backend/app.py`'s equivalents (`backend/app.py:770-813`).

This route module needs no local/remote branching at all: `remote_web` always operates in "stream the file back" mode, so `download_file` is a direct, unconditional port of `backend/app.py`'s existing remote-mode branch (`backend/app.py:795-813`), and it needs no zip-vs-single-file special case — `send_file`'s mimetype detection from the file extension already handles a `.zip` the same way it handles a `.mp4`.

- [ ] **Step 1: Write the failing tests**

```python
# remote_web/tests/test_jobs_routes.py
"""GET /api/progress/<id>, POST /api/cancel/<id>, GET /api/download-file/<id>."""

import os

import pytest

from backend import jobs as jobs_module
from remote_web import config
from remote_web.app import app as remote_app


@pytest.fixture
def client(isolated_state_file):
    remote_app.config["TESTING"] = True
    return remote_app.test_client()


@pytest.fixture(autouse=True)
def trusted(client):
    token = config.get_or_create_token()
    client.post("/unlock", data={"token": token})
    return client


@pytest.fixture(autouse=True)
def clear_jobs():
    jobs_module.jobs.clear()
    yield
    jobs_module.jobs.clear()


def test_progress_requires_trust():
    remote_app.config["TESTING"] = True
    anon_client = remote_app.test_client()
    resp = anon_client.get("/api/progress/doesnotmatter")
    assert resp.status_code == 401


def test_progress_unknown_job_returns_404(client):
    resp = client.get("/api/progress/unknown-job-id")
    assert resp.status_code == 404


def test_progress_returns_job_fields(client):
    jobs_module.jobs["job1"] = {
        "status": "running", "percent": 42.0, "text": "Downloading...",
        "filename": None, "item": 1, "total": 3, "saved_count": None, "items_progress": None,
    }
    resp = client.get("/api/progress/job1")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "running"
    assert body["percent"] == 42.0
    assert body["item"] == 1
    assert body["total"] == 3


def test_cancel_unknown_job_returns_404(client):
    resp = client.post("/api/cancel/unknown-job-id")
    assert resp.status_code == 404


def test_cancel_sets_the_cancelled_flag(client):
    jobs_module.jobs["job1"] = {"status": "running", "cancelled": False}
    resp = client.post("/api/cancel/job1")
    assert resp.status_code == 200
    assert jobs_module.jobs["job1"]["cancelled"] is True


def test_download_file_not_ready_returns_404(client):
    jobs_module.jobs["job1"] = {"status": "running", "filepath": None, "filename": None}
    resp = client.get("/api/download-file/job1")
    assert resp.status_code == 404


def test_download_file_streams_and_cleans_up_the_temp_dir(client, tmp_path):
    job_dir = tmp_path / "omniflow-remote-abc123"
    job_dir.mkdir()
    file_path = job_dir / "video.mp4"
    file_path.write_bytes(b"fake mp4 bytes")
    jobs_module.jobs["job1"] = {
        "status": "done", "filepath": str(file_path), "filename": "video.mp4",
    }
    resp = client.get("/api/download-file/job1")
    assert resp.status_code == 200
    assert resp.data == b"fake mp4 bytes"
    assert not job_dir.exists()  # cleaned up after streaming


def test_download_file_serves_a_zip_the_same_way_as_a_single_file(client, tmp_path):
    job_dir = tmp_path / "omniflow-remote-batch-abc123"
    job_dir.mkdir()
    zip_path = job_dir / "batch.zip"
    zip_path.write_bytes(b"PK\x03\x04fake zip bytes")
    jobs_module.jobs["job1"] = {
        "status": "done", "filepath": str(zip_path), "filename": "batch.zip",
    }
    resp = client.get("/api/download-file/job1")
    assert resp.status_code == 200
    assert resp.data == b"PK\x03\x04fake zip bytes"
    assert not job_dir.exists()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest remote_web/tests/test_jobs_routes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'remote_web.routes.jobs'`

- [ ] **Step 3: Implement `remote_web/routes/jobs.py`**

```python
"""GET /api/progress/<id>, POST /api/cancel/<id>, GET /api/download-file/<id>.

remote_web always operates in "stream the finished file back" mode - no
is_local_request() branch exists anywhere in this file, unlike
backend/app.py's equivalents. download_file needs no zip-vs-single-file
special case: Flask's send_file() already infers the right Content-Type
from the file extension, whether that's video.mp4 or batch.zip.
"""

import os
import shutil

from flask import Blueprint, after_this_request, jsonify, send_file

from backend import jobs

bp = Blueprint("jobs", __name__)


@bp.get("/api/progress/<job_id>")
def progress(job_id):
    job = jobs.jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404
    return jsonify({
        "status": job["status"], "percent": job["percent"], "text": job["text"],
        "filename": job["filename"],
        "item": job.get("item"), "total": job.get("total"),
        "saved_count": job.get("saved_count"),
        "items_progress": job.get("items_progress"),
    })


@bp.post("/api/cancel/<job_id>")
def cancel(job_id):
    job = jobs.jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404
    job["cancelled"] = True
    return jsonify({"ok": True})


@bp.get("/api/download-file/<job_id>")
def download_file(job_id):
    job = jobs.jobs.get(job_id)
    if not job or job["status"] != "done":
        return jsonify({"error": "File not ready"}), 404
    filepath = job.get("filepath")
    if not filepath or not os.path.isfile(filepath):
        return jsonify({"error": "File not found"}), 404

    @after_this_request
    def cleanup(response):
        shutil.rmtree(os.path.dirname(filepath), ignore_errors=True)
        return response

    return send_file(filepath, as_attachment=True, download_name=job["filename"])
```

- [ ] **Step 4: Mount the blueprint in `remote_web/app.py`**

Add to the imports:

```python
from remote_web.routes import jobs as jobs_routes
from remote_web.routes import media as media_routes
```

and after `app.register_blueprint(media_routes.bp)`:

```python
app.register_blueprint(jobs_routes.bp)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest remote_web/tests/test_jobs_routes.py -v`
Expected: PASS (7 tests)

- [ ] **Step 6: Commit**

```bash
git add remote_web/routes/jobs.py remote_web/app.py remote_web/tests/test_jobs_routes.py
git commit -m "remote_web: add /api/progress, /api/cancel, /api/download-file"
```

---

### Task 13: `requirements.txt`, `README.md`, and final full-suite verification

**Files:**
- Create: `remote_web/requirements.txt`
- Create: `remote_web/README.md`
- No code changes — this task documents deployment and runs the whole-repo verification pass.

**Interfaces:**
- Consumes: nothing new — this task is documentation + verification only.

- [ ] **Step 1: Create `remote_web/requirements.txt`**

```
# remote_web adds no new Python dependencies beyond the repo root's own
# requirements.txt. itsdangerous (used by trust.py for signed cookies)
# already ships as a direct dependency of Flask (confirmed installed at
# v2.2.0 alongside Flask 3.1.3 in this repo's .venv during design review -
# see docs/superpowers/specs/2026-08-29-remote-web-access-design.md).
#
# Setup for this deployment is therefore identical to the root project's own:
#   python3 -m venv .venv && source .venv/bin/activate
#   pip install -r requirements.txt
```

- [ ] **Step 2: Write `remote_web/README.md`**

```markdown
# remote_web — Personal Remote Access for OmniFlow

Serves OmniFlow's check/download flow (including Instagram/Threads and
playlist/carousel batch downloads) over a personal, token-gated public URL,
so it's reachable from a phone anywhere with internet — no native macOS app
install required on that device.

**Design spec:** [docs/superpowers/specs/2026-08-29-remote-web-access-design.md](../docs/superpowers/specs/2026-08-29-remote-web-access-design.md)

This is a *separate deployment* from the native `.app` — it does not touch
`backend/`, `server.py`, `desktop_app.py`, or `OmniFlow.spec` at all, and is
meant to run continuously on a dedicated, always-on Mac (an older machine,
**not** the same Mac used for day-to-day development), reachable through a
free Cloudflare Tunnel rather than a paid cloud VPS — running it from a
residential IP matters for platforms (TikTok especially) that are more
likely to rate-limit or block a cloud-provider IP range.

## One-time setup, on the dedicated Mac

1. Clone the repo (a full checkout — `remote_web/` imports `backend/*` as a
   normal Python package):
   ```bash
   git clone https://github.com/<owner>/OmniFlow.git
   cd OmniFlow
   ```
2. Set up the Python environment (same as the root project):
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Build the frontend once — `remote_web` serves this same built output, no
   separate frontend build of its own:
   ```bash
   cd frontend && npm install && npm run build && cd ..
   ```
4. Generate the trust token + app secret key (one-time; auto-generated on
   first access, but running this now lets you read the token before going
   anywhere near a phone):
   ```bash
   python3 -m remote_web.config show
   ```
   Write the printed token down somewhere safe (a password manager) — this
   is the one credential every device needs to type into the `/unlock` form.
5. Confirm ffmpeg resolves correctly for *this* Mac's actual CPU
   architecture before relying on it:
   ```bash
   python3 -c "from remote_web.ffmpeg_locator import resolve_ffmpeg_binary; print(resolve_ffmpeg_binary())"
   ```
   This must print a real path, not `None`. If it prints `None`, re-check
   that both `./ffmpeg` (arm64) and `./ffmpeg-x86_64` (Intel) are present at
   the repo root and executable — see
   `.claude/rules/packaging.md`'s "Two-architecture ffmpeg" section.
6. Confirm this Mac has a live, logged-in Instagram/Threads session in an
   installed browser (Chrome/Brave/Edge/Vivaldi/Opera — **not** Safari, see
   `docs/TROUBLESHOOTING.md`). With someone physically present, run the app
   once (step 7) and trigger one Instagram check from a browser — the first
   real Instagram/Threads request on this machine triggers a one-time macOS
   Keychain permission prompt ("... wants to use your confidential
   information stored in 'Chrome Safe Storage'"); click **Always Allow**.
   Nobody will be present to click this later, so it must happen now.
7. Run it from the repo root:
   ```bash
   python3 -m remote_web.app
   ```
   Must be run this way — **not** `python3 remote_web/app.py` — the `-m`
   form is what puts the repo root on `sys.path`, which is what makes
   `import backend` resolve at all. This binds `127.0.0.1:5050` only.
8. Install as a `launchd` **agent** (not a Daemon — see "Why a LaunchAgent,
   not a LaunchDaemon" below):

   Create `~/Library/LaunchAgents/com.omniflow.remoteweb.plist`:
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
     "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
     <key>Label</key><string>com.omniflow.remoteweb</string>
     <key>ProgramArguments</key>
     <array>
       <string>/path/to/OmniFlow/.venv/bin/python3</string>
       <string>-m</string>
       <string>remote_web.app</string>
     </array>
     <key>WorkingDirectory</key><string>/path/to/OmniFlow</string>
     <key>RunAtLoad</key><true/>
     <key>KeepAlive</key><true/>
   </dict>
   </plist>
   ```
   Replace `/path/to/OmniFlow` with the real absolute path on this Mac in
   **both** places (`ProgramArguments` and `WorkingDirectory`) — `launchd`
   does not go through a shell, so there is no working directory to inherit
   otherwise, and the `-m remote_web.app` form matters here for the exact
   same `sys.path` reason as step 7.

   Load it:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.omniflow.remoteweb.plist
   ```

   **Known trade-off:** a restart clears the in-memory job registry and the
   brute-force lockout counter — any in-flight download's progress is lost
   and a lockout resets to zero. Acceptable for personal use.

9. Install [`cloudflared`](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/),
   authenticate, create a named tunnel pointed at `127.0.0.1:5050`, then:
   ```bash
   cloudflared service install
   ```
   for the same auto-start/restart behavior as the launchd agent above.

10. Configure **Cloudflare Access** (Zero Trust free tier, up to 50 users)
    on the tunnel's hostname, restricted to your own email via a one-time
    login code. **Treat this as a required step, not optional** — without
    it, the app-level token from step 4 is the *only* thing standing
    between the internet and this Mac's own Instagram session and download
    bandwidth.
11. Disable macOS sleep on this Mac (System Settings → Energy Saver, or wrap
    the launchd command in `caffeinate`) so the tunnel doesn't silently drop.
12. Enable **Automatic Login** for this account (System Settings → Users &
    Groups → Login Options) and confirm **FileVault is off**. Both are
    required for this to survive an unattended reboot — see below.

### Why a LaunchAgent, not a LaunchDaemon

A `LaunchAgent` only starts once a GUI session begins; after a reboot with
nobody physically logging in, it never starts at all. Switching to a
`LaunchDaemon` (which starts before any login) looks like the fix, but
isn't: a Daemon has no GUI session, and macOS's login Keychain — which
`browser_cookie3` needs to decrypt Instagram/Threads cookies — is only
unlocked as part of an interactive login. A Daemon trades "survives reboot"
for "Instagram/Threads permanently broken until someone logs in anyway."

**The actual fix:** keep the LaunchAgent, and enable **Automatic Login**
(step 12). macOS performs that login itself at boot with no one present,
which both unlocks the Keychain *and* starts the GUI session the LaunchAgent
needs.

**The catch:** if FileVault is enabled, its own pre-boot passphrase prompt
gates the entire boot process before Automatic Login (or anything else) can
run — no login configuration works around it. FileVault and "survives an
unattended reboot" are mutually exclusive on macOS. This means **Automatic
Login without FileVault means anyone with physical access to this Mac gets
straight into the account, no password, and the disk is unencrypted at
rest.** For a dedicated machine whose only real secrets are a browser
session and this deployment's own token/key (both revocable — see below),
this is a reasonable trade for "always reachable from a phone" — but it is a
real security posture change from "a normal Mac," and depends on the
dedicated Mac's physical location being reasonably secure.

### Ongoing maintenance

Any macOS or browser (Chrome/Brave/Edge) update on this Mac can reset the
Keychain permission `browser_cookie3` relies on, re-triggering the one-time
consent prompt from step 6 — but with nobody physically present to click it,
Instagram/Threads extraction then fails silently (still logged to
`.logs/errors.log` via the same mechanism the native app uses, but nobody is
watching that file unless they think to look). Check
`GET /api/health/detail` (while unlocked) after any update to this Mac, or
periodically, rather than only discovering the failure mid-use away from
home.

## Revoking access

Two different operations:

- **Rotate the token** — stops any *new* `/unlock` attempt with the old
  token. Existing already-unlocked devices are unaffected.
  ```bash
  python3 -m remote_web.config rotate-token
  ```
- **Rotate the secret key** — the actual "I lost my phone" response.
  Invalidates *every* previously-issued cookie at once, forcing every
  device (including your own) to `/unlock` again.
  ```bash
  python3 -m remote_web.config rotate-key
  ```

## Manual live checklist (not automated)

Run through this once after first deploying, and again after any
significant change:

- [ ] Visit the tunnel URL from an actual phone browser — the `/unlock` form
      renders.
- [ ] Enter the token — redirected to the app, trust cookie set.
- [ ] A browser with no trust cookie hitting any `/api/*` path gets a
      friendly 401, not a crash or a raw error page.
- [ ] Check + download a single video (any supported platform).
- [ ] Check + download a playlist/channel or Instagram carousel — confirm
      the browser receives one `.zip` containing every selected item.
- [ ] Check + download an Instagram post and a Threads post — confirm both
      work without any "local only" rejection.
- [ ] `GET /api/health/detail` (while unlocked) reports `ffmpeg: true`,
      `instagram_cookies: true`, `threads_cookies: true`.
- [ ] `GET /health` (no cookie needed) returns `{"status": "ok"}`.

## Testing

```bash
pytest remote_web/tests/ -v          # this package's own tests
pytest                                 # confirms the native app's suite is
                                        # still 100% green and untouched
```
```

- [ ] **Step 3: Run remote_web's own test suite in isolation**

Run: `pytest remote_web/tests/ -v`
Expected: PASS — every test added across Tasks 1-12 (config, trust, ffmpeg_locator, app gate, health, zipper, reaper, settings, media ×3, jobs). Confirm the total count matches (config 6 + trust 11 + ffmpeg_locator 5 + app_gate 5 + health 8 + zipper 6 + reaper 7 + settings 6 + media 15 + jobs 7 = 76 tests).

- [ ] **Step 4: Run the full repository test suite**

Run: `pytest -v`
Expected: PASS for both `tests/` (the pre-existing native-app suite — must show the same pass count it had before this plan started, confirming nothing under `backend/` regressed) and `remote_web/tests/` (this plan's new suite) in the same invocation.

- [ ] **Step 5: Confirm zero changes to the protected files**

```bash
git diff main -- backend/ server.py desktop_app.py OmniFlow.spec
```

Expected: empty output. If this prints anything, stop — a task in this plan touched a file it should never have (re-check Tasks 1-12's `Modify:` lists, all of which name only files under `remote_web/` or `.gitignore`).

- [ ] **Step 6: Run the frontend lint/build to confirm zero frontend changes were needed**

```bash
cd frontend && npm run build && cd ..
git status --porcelain frontend/
```

Expected: `npm run build` succeeds (proves `frontend/dist` — the build `remote_web/app.py` serves via `paths.WEB_DIR` — is buildable unchanged), and `git status` on `frontend/` shows nothing beyond the untracked `frontend/dist/` (already gitignored) — confirming no frontend source file needed editing anywhere in this plan, exactly as spec §3 states ("no frontend code changes at all").

- [ ] **Step 7: Commit**

```bash
git add remote_web/requirements.txt remote_web/README.md
git commit -m "remote_web: add deployment README + requirements.txt"
```

---

## Self-Review

**Spec coverage** — every numbered spec section maps to a task:
- §3 (architecture/file tree) → Task 1 (scaffold), and every later task creates exactly the file the tree names.
- §4.1 (`/unlock` POST form) → Task 2.
- §4.2 (trust cookie) → Task 2.
- §4.3 (revocation) → Task 1 (`rotate_token`/`rotate_secret_key`) + Task 13 (documented as README CLI steps).
- §4.4 (`is_trusted_request` + gate) → Task 2 (predicate) + Task 4 (`before_request` wiring).
- §4.5 (lockout) → Task 2.
- §4.6 (health split + caching) → Task 5.
- §4.7 (Cloudflare Access) → Task 13 (README, not code — matches spec's own "not a hard code dependency").
- §5.1 (ffmpeg resolution) → Task 3, wired into Tasks 10-11.
- §5.2 (single item) → Tasks 9-10 + 12.
- §5.3 (batch + incremental zip) → Task 6 (zipper) + Task 11 (wiring).
- §5.4 (reaper) → Task 7.
- §5.5 (cancellation) → Task 12 (reuses `backend.jobs`'s existing cooperative-cancel flag unmodified — no new code needed beyond the `POST /api/cancel/<id>` route itself).
- §6 (deployment steps 1-12) + §6.4 (LaunchAgent/Keychain/FileVault) + §6.5 (maintenance) → Task 13's README.
- §7 (error handling) → covered throughout Tasks 9-11 (every route wraps in try/except, reuses `describe_extraction_error`) + Task 3/10 (ffmpeg failure messages) + Task 4 (startup fail-loud log).
- §8 (testing) → every `remote_web/tests/*.py` file named in spec's file tree is created by the matching task; the "pytest for the existing suite must stay green" line is Task 13 Step 4-5.
- §9 (resolved open questions) → already baked into the naming (`remote_web`), the batch design (Task 11), and Task 13's README (Cloudflare Access language).

**Placeholder scan** — no "TBD"/"add error handling"/"similar to Task N" anywhere; every code step above is a complete file or complete diff, not a description of one.

**Type/interface consistency** — `BatchZipper.add_and_delete(source_path, filename) -> str` (Task 6) is called identically in Task 11's `download_item`. `resolve_ffmpeg_binary() -> str | None` (Task 3) is called identically in Tasks 4, 5, 10, 11. `is_trusted_request(req) -> bool` (Task 2) is called identically in Task 4's `before_request` hook. `jobs.jobs[job_id]` dict keys (`status`, `percent`, `text`, `filename`, `filepath`, `cancelled`, `item`, `total`, `saved_count`, `items_progress`) are written identically by Tasks 10-11 and read identically by Task 12 — matching `backend.jobs`'s existing shape exactly, since it's the same shared dict object.
