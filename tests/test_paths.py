"""backend.paths anchoring — BASE_DIR must stay the repo root after the package split."""

import os
import subprocess

import pytest

import server
from backend import paths


def test_paths_anchor_to_repo_root():
    # backend/paths.py sits one level below the repo root, so its BASE_DIR must
    # resolve to server.py's own directory - config.json (dev), frontend/dist
    # and the vendored ffmpeg are all found relative to it.
    assert paths.BASE_DIR == os.path.dirname(os.path.abspath(server.__file__))
    assert paths.WEB_DIR.endswith(os.path.join("frontend", "dist"))
    assert paths.resource_path("ffmpeg") == os.path.join(paths.RESOURCE_BASE, "ffmpeg")


# ---- get_ffmpeg_path / architecture-mismatch detection ----
#
# A wrong-architecture bundled ffmpeg (e.g. the Intel build's binary shipped
# to an Apple Silicon Mac with no Rosetta 2 installed) passes both existence
# and +x checks but can't actually exec at all - macOS raises OSError errno
# 86 ("Bad CPU type in executable") the moment a process tries to run it.
# Confirmed live 2026-08-29 (MISTAKES.md) while building the arm64-native
# ffmpeg: this is a real, distinct failure mode from "ffmpeg not installed".


def _make_fake_ffmpeg(tmp_path):
    fake = tmp_path / "ffmpeg"
    fake.write_text("#!/bin/sh\necho fake\n")
    fake.chmod(0o755)
    return str(fake)


def test_get_ffmpeg_path_trusts_a_bundled_binary_that_actually_runs(tmp_path, monkeypatch):
    fake = _make_fake_ffmpeg(tmp_path)
    monkeypatch.setattr(paths, "resource_path", lambda name: fake)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: None)  # simulate a clean exec
    assert paths.get_ffmpeg_path() == fake


def test_get_ffmpeg_path_rejects_a_wrong_architecture_binary_and_falls_back(tmp_path, monkeypatch):
    fake = _make_fake_ffmpeg(tmp_path)
    monkeypatch.setattr(paths, "resource_path", lambda name: fake)

    def fake_run(*a, **k):
        raise OSError(86, "Bad CPU type in executable")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(paths.shutil, "which", lambda name: "/usr/local/bin/ffmpeg")
    assert paths.get_ffmpeg_path() == "/usr/local/bin/ffmpeg"


def test_ffmpeg_unavailable_message_names_the_matching_dmg_for_a_cpu_mismatch(tmp_path, monkeypatch):
    fake = _make_fake_ffmpeg(tmp_path)
    monkeypatch.setattr(paths, "resource_path", lambda name: fake)

    def fake_run(*a, **k):
        raise OSError(86, "Bad CPU type in executable")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(paths.platform, "machine", lambda: "arm64")

    message = paths.ffmpeg_unavailable_message()
    assert "OmniFlow-AppleSilicon.dmg" in message
    assert "OmniFlow-Intel.dmg" not in message


def test_ffmpeg_unavailable_message_is_generic_when_ffmpeg_is_just_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "resource_path", lambda name: str(tmp_path / "no-such-file"))
    message = paths.ffmpeg_unavailable_message()
    assert "OmniFlow-AppleSilicon.dmg" not in message
    assert "OmniFlow-Intel.dmg" not in message
