"""GET /health (public liveness) + GET /api/health/detail (trust-gated
diagnostics) - spec §4.6."""

import os
import shutil
import time

from flask import Blueprint, jsonify

from backend import cookies as backend_cookies
from backend import threads as backend_threads
from remote_web import config, ffmpeg_locator, selfheal
from remote_web.routes import settings as settings_routes

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


def _cookies_age_hours():
    try:
        age_seconds = time.time() - os.path.getmtime(settings_routes._COOKIES_FILE)
    except OSError:
        return None
    return round(age_seconds / 3600, 2)


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
    # Computed on every request, not cached with the rest: it exists so a
    # silently-broken Mac cookie sync is noticeable (it failed unseen from
    # 2026-10-01), and a 5-minute-old age would be fine but a stale cache of
    # "fresh" must never mask it.
    return jsonify({**_detail_cache["payload"], "cookies_age_hours": _cookies_age_hours(), "canary": selfheal.summary()})
