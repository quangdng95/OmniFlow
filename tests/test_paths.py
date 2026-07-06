"""backend.paths anchoring — BASE_DIR must stay the repo root after the package split."""

import os

import server
from backend import paths


def test_paths_anchor_to_repo_root():
    # backend/paths.py sits one level below the repo root, so its BASE_DIR must
    # resolve to server.py's own directory - config.json (dev), frontend/dist
    # and the vendored ffmpeg are all found relative to it.
    assert paths.BASE_DIR == os.path.dirname(os.path.abspath(server.__file__))
    assert paths.WEB_DIR.endswith(os.path.join("frontend", "dist"))
    assert paths.resource_path("ffmpeg") == os.path.join(paths.RESOURCE_BASE, "ffmpeg")
