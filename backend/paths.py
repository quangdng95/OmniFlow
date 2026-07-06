"""Filesystem anchoring + bundled-resource resolution (dev and frozen .app)."""

import os
import shutil
import sys

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


def resource_path(relative_path):
    return os.path.join(RESOURCE_BASE, relative_path)


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
    return shutil.which("ffmpeg")
