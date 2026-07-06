"""Unit tests for backend.download - filenames, progress math, yt-dlp options,
H.264 enforcement."""

import os
import subprocess
import time
from types import SimpleNamespace

import pytest
import yt_dlp

from backend import download as download_module
from backend import jobs as jobs_module
from backend.download import (
    apply_progress_update,
    build_download_options,
    combined_download_percent,
    detect_video_codec,
    ensure_h264,
    get_unique_filename,
    sanitize_filename,
)


# ---- sanitize_filename ----


def test_sanitize_filename_strips_illegal_characters():
    assert sanitize_filename('a/b\\c:d*e?f"g<h>i|j') == "abcdefghij"


def test_sanitize_filename_trims_whitespace():
    assert sanitize_filename("  My Video  ") == "My Video"


# ---- get_unique_filename ----


def test_get_unique_filename_no_collision(tmp_path):
    result = get_unique_filename(str(tmp_path), "My Video", "mp4")
    assert result == str(tmp_path / "My Video.mp4")


def test_get_unique_filename_appends_counter_on_collision(tmp_path):
    (tmp_path / "My Video.mp4").write_text("existing")
    result = get_unique_filename(str(tmp_path), "My Video", "mp4")
    assert result == str(tmp_path / "My Video (1).mp4")


def test_get_unique_filename_increments_past_multiple_collisions(tmp_path):
    (tmp_path / "clip.mp4").write_text("x")
    (tmp_path / "clip (1).mp4").write_text("x")
    result = get_unique_filename(str(tmp_path), "clip", "mp4")
    assert result == str(tmp_path / "clip (2).mp4")


# ---- download progress tracking ----


def test_combined_download_percent_single_stream_passes_through():
    assert combined_download_percent(0, 42.0, 1) == 42.0


def test_combined_download_percent_splits_across_two_streams():
    # first stream's 0-100% maps to the first half
    assert combined_download_percent(0, 0.0, 2) == 0.0
    assert combined_download_percent(0, 100.0, 2) == 50.0
    # second stream's 0-100% maps to the second half - always >= where stream 1 ended
    assert combined_download_percent(1, 0.0, 2) == 50.0
    assert combined_download_percent(1, 100.0, 2) == 100.0


def test_combined_download_percent_never_exceeds_100():
    assert combined_download_percent(1, 100.0, 2) <= 100.0


def test_apply_progress_update_tracks_percent_within_a_stream():
    job = {}
    stream_index = apply_progress_update(
        job, {"status": "downloading", "downloaded_bytes": 50, "total_bytes": 100}, 0, 2
    )
    assert stream_index == 0
    assert job["percent"] == 25.0  # 50% of the first of 2 streams


def test_apply_progress_update_advances_stream_index_on_finished():
    job = {}
    stream_index = apply_progress_update(job, {"status": "finished"}, 0, 2)
    assert stream_index == 1
    # second stream's progress now maps into the second half
    stream_index = apply_progress_update(
        job, {"status": "downloading", "downloaded_bytes": 100, "total_bytes": 100}, stream_index, 2
    )
    assert job["percent"] == 100.0


def test_apply_progress_update_never_advances_past_the_last_stream():
    stream_index = 1
    for _ in range(3):
        stream_index = apply_progress_update({}, {"status": "finished"}, stream_index, 2)
    assert stream_index == 1


def test_apply_progress_update_falls_back_to_total_bytes_estimate():
    job = {}
    apply_progress_update(
        job, {"status": "downloading", "downloaded_bytes": 10, "total_bytes_estimate": 100}, 0, 1
    )
    assert job["percent"] == 10.0


def test_apply_progress_update_ignores_downloading_status_with_no_known_total():
    job = {"percent": 5}
    apply_progress_update(job, {"status": "downloading", "downloaded_bytes": 10}, 0, 1)
    assert job["percent"] == 5  # unchanged, avoids a ZeroDivisionError


# ---- build_download_options ----


def test_build_download_options_for_audio():
    opts = build_download_options("Audio Only", "/tmp/My Video", "/path/to/ffmpeg", [], [])
    assert opts["format"] == "bestaudio/best"
    assert opts["postprocessors"] == [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}]
    assert opts["outtmpl"] == "/tmp/My Video.%(ext)s"
    assert opts["ffmpeg_location"] == "/path/to/ffmpeg"


def test_build_download_options_includes_network_retry_flags():
    # Resilience against a dropped connection / fragment mid-download.
    opts = build_download_options("720p", "/tmp/v", "/ff", [], [])
    assert opts["retries"] == 5
    assert opts["fragment_retries"] == 5
    assert opts["socket_timeout"] == 30


def test_build_download_options_speed_flags():
    # PRD §7: 10 parallel fragments, no leftover pre-merge files.
    opts = build_download_options("720p", "/tmp/v", "/ff", [], [])
    assert opts["concurrent_fragment_downloads"] == 10
    assert opts["keepvideo"] is False


def test_build_download_options_for_video_quality():
    opts = build_download_options("720p", "/tmp/My Video", "/path/to/ffmpeg", [], [])
    # The selector prefers H.264 (avc1) at every fallback step so macOS gets a
    # playable file, but still falls back to any codec so a download never fails.
    assert opts["format"] == (
        "bestvideo[vcodec^=avc1][height<=720]+bestaudio[ext=m4a]/"
        "bestvideo[vcodec^=avc1][height<=720]+bestaudio/"
        "best[vcodec^=avc1][height<=720]/"
        "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
    )
    assert opts["format_sort"] == ["vcodec:h264", "res", "acodec:m4a"]
    # PRD §7: merge straight to an mp4 container via a fast stream-copy remux -
    # NO blanket libx264 re-encode (that made "combine" slow). The rare VP9/AV1
    # straggler is re-encoded afterward by ensure_h264(), not here.
    assert opts["merge_output_format"] == "mp4"
    assert opts["postprocessors"] == [{"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}]
    assert "recode_video" not in opts
    assert "postprocessor_args" not in opts


def test_build_download_options_video_prefers_avc1_and_never_only_vp9():
    for quality in ("360p", "1080p", "Best"):
        opts = build_download_options(quality, "/tmp/v", "/ff", [], [])
        # H.264 is the first thing tried and h264 leads the codec sort...
        assert opts["format"].startswith("bestvideo[vcodec^=avc1]")
        assert opts["format_sort"][0] == "vcodec:h264"
        # ...and it never pins the download to a VP9/AV1-only selector.
        assert "vp9" not in opts["format"].lower()
        assert "av01" not in opts["format"].lower()


def test_build_download_options_for_best_quality_maps_to_2160():
    opts = build_download_options("Best", "/tmp/My Video", "/path/to/ffmpeg", [], [])
    assert "[height<=2160]" in opts["format"]
    assert opts["format"].startswith("bestvideo[vcodec^=avc1][height<=2160]")


def test_build_download_options_includes_cookiefile_when_provided():
    opts = build_download_options("720p", "/tmp/My Video", "/path/to/ffmpeg", [], [], "/path/to/cookies.txt")
    assert opts["cookiefile"] == "/path/to/cookies.txt"


def test_build_download_options_omits_cookiefile_when_not_provided():
    opts = build_download_options("720p", "/tmp/My Video", "/path/to/ffmpeg", [], [])
    assert "cookiefile" not in opts


def test_build_download_options_sets_noplaylist_by_default():
    # Without an explicit entry_index, a playlist-shaped URL (an Instagram
    # Story, or a multi-video carousel post) must not silently download every
    # entry into the same fixed outtmpl, overwriting each one in turn.
    opts = build_download_options("720p", "/tmp/My Video", "/path/to/ffmpeg", [], [])
    assert opts["noplaylist"] is True
    assert "playlist_items" not in opts


def test_build_download_options_targets_one_entry_when_index_given():
    opts = build_download_options("720p", "/tmp/My Video", "/path/to/ffmpeg", [], [], entry_index=3)
    assert opts["noplaylist"] is False
    assert opts["playlist_items"] == "3"


# ---- H.264 safety net (detect_video_codec / ensure_h264) ----


def test_detect_video_codec_parses_ffmpeg_stderr(monkeypatch):
    stderr = (
        "Input #0, mov,mp4, from 'x.mp4':\n"
        "  Stream #0:0(und): Video: vp9 (Profile 0), yuv420p(tv), 1920x1080\n"
        "  Stream #0:1(und): Audio: aac (LC), 44100 Hz\n"
    )
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr=stderr),
    )
    assert detect_video_codec("x.mp4", "/ff") == "vp9"


def test_detect_video_codec_returns_none_when_ffmpeg_unavailable(monkeypatch):
    def boom(*a, **k):
        raise OSError("no ffmpeg")

    monkeypatch.setattr(subprocess, "run", boom)
    assert detect_video_codec("x.mp4", "/ff") is None


def test_ensure_h264_is_a_noop_for_already_h264(monkeypatch):
    jobs_module.jobs["j-h264"] = {"cancelled": False, "text": "", "status": "running"}
    monkeypatch.setattr(download_module, "detect_video_codec", lambda path, ff: "h264")

    def fail(*a, **k):
        raise AssertionError("must not re-encode an already-h264 file")

    monkeypatch.setattr(subprocess, "Popen", fail)
    ensure_h264("/tmp/some.mp4", "/ff", "j-h264")  # no exception = no re-encode


def test_ensure_h264_reencodes_vp9_in_place(monkeypatch, tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"original-vp9-bytes")
    jobs_module.jobs["j-vp9"] = {"cancelled": False, "text": "", "status": "running"}
    monkeypatch.setattr(download_module, "detect_video_codec", lambda path, ff: "vp9")

    class FakePopen:
        def __init__(self, cmd, stdout=None, stderr=None):
            self.returncode = 0
            # ffmpeg writes to the temp output (last arg); simulate that.
            with open(cmd[-1], "wb") as f:
                f.write(b"reencoded-h264-bytes")

        def poll(self):
            return 0

    monkeypatch.setattr(subprocess, "Popen", FakePopen)
    ensure_h264(str(video), "/ff", "j-vp9")
    assert video.read_bytes() == b"reencoded-h264-bytes"
    assert not (tmp_path / "clip.mp4.h264.mp4").exists()  # temp cleaned up via replace


def test_ensure_h264_honors_cancel_mid_reencode(monkeypatch, tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"original-vp9-bytes")
    jobs_module.jobs["j-cancel"] = {"cancelled": True, "text": "", "status": "running"}
    monkeypatch.setattr(download_module, "detect_video_codec", lambda path, ff: "av01")

    class FakePopenRunning:
        def __init__(self, cmd, stdout=None, stderr=None):
            self.returncode = None
            with open(cmd[-1], "wb") as f:
                f.write(b"partial")
            self.tmp = cmd[-1]

        def poll(self):
            return None  # still "running" so the cancel check fires

        def terminate(self):
            pass

        def wait(self, timeout=None):
            return 0

        def kill(self):
            pass

    monkeypatch.setattr(subprocess, "Popen", FakePopenRunning)
    with pytest.raises(yt_dlp.utils.DownloadCancelled):
        ensure_h264(str(video), "/ff", "j-cancel")
    assert video.read_bytes() == b"original-vp9-bytes"  # original untouched
    assert not (tmp_path / "clip.mp4.h264.mp4").exists()  # partial temp removed
