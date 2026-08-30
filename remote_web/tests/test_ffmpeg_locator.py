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
