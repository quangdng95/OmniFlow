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
