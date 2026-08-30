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
