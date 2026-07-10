"""Filesystem anchoring + bundled-resource resolution (dev and frozen .app)."""

import datetime
import os
import shutil
import sys
import traceback

import certifi

# A Python interpreter built inside a Homebrew or conda/micromamba
# environment (as this project's build machines are - both a Homebrew-based
# arm64 .venv and a micromamba-based x86_64 env for the Intel build) bakes in
# an OpenSSL default certificate search path relative to THAT environment
# (e.g. "/opt/homebrew/etc/openssl@3/cert.pem", or a conda env's own
# "envs/x86_64/ssl/cert.pem"). Once frozen into a standalone .app via
# PyInstaller, that path travels with the binary but the FILE does not - so
# on any end-user machine without that exact Homebrew/conda layout, every
# bare urllib/ssl HTTPS connection (the Instagram/Threads/LinkedIn resolvers
# all use raw urllib.request, not requests) fails with
# "CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate"
# (confirmed live 2026-07-10, MISTAKES.md - reproduced on both the arm64 and
# Intel builds via ssl.get_default_verify_paths()). certifi is already
# bundled in the frozen app (a yt-dlp dependency, auto-collected by
# PyInstaller's own certifi hook), so point Python's global SSL default there
# unconditionally, before any other backend module (all of which import this
# one early) can open a connection. Costs nothing in dev - certifi's bundle
# is a valid, current CA list either way.
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
# The repo root — where server.py, config.json (dev), frontend/ and the
# vendored ffmpeg live. This file sits one level down (backend/), so anchor
# one directory up; a unit test pins this to server.py's own directory.
BASE_DIR = os.path.dirname(PACKAGE_DIR)
# When packaged with PyInstaller, bundled read-only resources (the built
# frontend and the vendored ffmpeg) live under sys._MEIPASS, not next to the
# source. In dev this is just BASE_DIR, so nothing changes there.
RESOURCE_BASE = getattr(sys, "_MEIPASS", BASE_DIR)
WEB_DIR = os.path.join(RESOURCE_BASE, "frontend", "dist")

# Same reasoning as config.py's CONFIG_FILE: the frozen .app bundle is
# read-only, so diagnostic logs need a per-user writable dir instead of
# living next to the source.
if getattr(sys, "frozen", False):
    LOG_DIR = os.path.join(os.path.expanduser("~/Library/Logs"), "OmniFlow")
else:
    LOG_DIR = os.path.join(BASE_DIR, ".logs")


def resource_path(relative_path):
    return os.path.join(RESOURCE_BASE, relative_path)


def log_exception(context, error):
    # A friendly generic message is deliberately all the user ever sees for
    # an untrusted/unexpected exception (describe_extraction_error) - so
    # without this, a genuinely new bug leaves ZERO trace anywhere once it's
    # packaged (no terminal to read stdout from). This appends a timestamped
    # full traceback to a persistent log file instead, so a user hitting a
    # mysterious failure has something concrete to send back. Best-effort
    # only: a logging failure must never mask or replace the original error.
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(os.path.join(LOG_DIR, "errors.log"), "a") as f:
            f.write(f"\n--- {datetime.datetime.now().isoformat()} | {context} ---\n")
            f.write("".join(traceback.format_exception(type(error), error, error.__traceback__)))
    except Exception:
        pass


def get_ffmpeg_path():
    local_ffmpeg = resource_path("ffmpeg")
    if os.path.exists(local_ffmpeg):
        # A bundled ffmpeg can lose its +x bit when unpacked from the .app, so
        # restore it before trusting it (no-op in dev, where it's already +x).
        if not os.access(local_ffmpeg, os.X_OK):
            try:
                os.chmod(local_ffmpeg, 0o755)
            except OSError:
                pass
        if os.access(local_ffmpeg, os.X_OK):
            return local_ffmpeg
    # The vendored ffmpeg should always be found above - this system-PATH
    # fallback exists only as a last resort. On a dev machine with ffmpeg
    # installed via Homebrew this can silently "work" even when the bundled
    # one is broken, masking a real packaging bug that a clean end-user
    # machine (no system ffmpeg at all) would immediately hit as a hard
    # failure - so log loudly whenever this path is actually taken.
    system_ffmpeg = shutil.which("ffmpeg")
    log_exception(
        "get_ffmpeg_path: bundled ffmpeg missing/non-executable, "
        f"falling back to system PATH (found: {system_ffmpeg!r})",
        RuntimeError(f"bundled ffmpeg not usable at {local_ffmpeg!r}"),
    )
    return system_ffmpeg
