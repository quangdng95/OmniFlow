"""Unit tests for backend.download - filenames, progress math, yt-dlp options,
H.264 enforcement."""

import os
import subprocess
import time
import urllib.request
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
    download_direct_url,
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


@pytest.fixture(autouse=True)
def _no_network_quality_lookup(monkeypatch):
    # build_download_options resolves a numbered quality label (e.g. "1080p")
    # against the source's real formats via a lightweight yt-dlp lookup (see
    # resolve_quality_height in extraction.py). Stub it to "no data found" by
    # default so the rest of this file's tests - which only care about the
    # general shape of the built options, not per-source resolution mapping
    # - stay offline and deterministic; that falls back to treating the
    # label's own number as the raw height, same as every existing assertion
    # below already expects. Tests that DO care about real resolution
    # mapping override this stub explicitly (see the resolve_quality_height
    # tests further down).
    monkeypatch.setattr(download_module, "_fetch_formats_for_quality_resolution", lambda *a, **k: [])


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
    # No hard vcodec filter on any alternative - a resolution cap must never
    # be satisfied by settling for a lower-resolution avc1 stream just
    # because one exists under the height ceiling (that was the bug: yt-dlp's
    # "A/B/C" selector commits to the first alternative that matches
    # anything, so a hard `[vcodec^=avc1]` filter silently downgraded
    # resolution whenever avc1 didn't reach the requested height). Codec
    # preference lives only in format_sort as a tie-break.
    assert opts["format"] == (
        "bestvideo[height<=720]+bestaudio[ext=m4a]/"
        "bestvideo[height<=720]+bestaudio/"
        "best[height<=720]/"
        "best"
    )
    assert opts["format_sort"] == ["res", "vcodec:h264", "acodec:m4a"]
    # PRD §7: merge straight to an mp4 container via a fast stream-copy remux -
    # NO blanket libx264 re-encode (that made "combine" slow). The rare VP9/AV1
    # straggler is re-encoded afterward by ensure_h264(), not here.
    assert opts["merge_output_format"] == "mp4"
    assert opts["postprocessors"] == [{"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}]
    assert "recode_video" not in opts
    assert "postprocessor_args" not in opts


def test_build_download_options_video_prefers_avc1_as_a_tiebreak_not_a_filter():
    for quality in ("360p", "1080p", "Best"):
        opts = build_download_options(quality, "/tmp/v", "/ff", [], [])
        # h264 is preferred via format_sort (a tie-break among equal
        # resolutions), never as a hard filter that could sacrifice
        # resolution by excluding a higher-res VP9/AV1-only format.
        assert "vcodec^=avc1" not in opts["format"]
        assert opts["format_sort"][0] == "res"
        assert "vcodec:h264" in opts["format_sort"]
        # It also never pins the download to a VP9/AV1-only selector.
        assert "vp9" not in opts["format"].lower()
        assert "av01" not in opts["format"].lower()


def test_build_download_options_for_best_quality_has_no_height_cap():
    # "Best" must always mean the single highest-resolution stream available,
    # full stop - a hardcoded "<=2160" ceiling used to silently exclude
    # anything above 4K, and worse, compared against raw pixel height, which
    # can be smaller than a non-16:9 source's true top label (see
    # resolve_quality_height) - so it could cap even lower than 4K.
    opts = build_download_options("Best", "/tmp/My Video", "/path/to/ffmpeg", [], [])
    assert "height<=" not in opts["format"]
    assert opts["format"].startswith("bestvideo+bestaudio")


def test_build_download_options_resolves_quality_label_to_the_sources_real_height(monkeypatch):
    # Regression for the ultrawide-video bug: requesting the platform's own
    # "1080p" label must download what THAT source actually calls 1080p (raw
    # height 768 here, per format_note), not a literal height<=1080 cap that
    # would let a higher-labeled tier (height 1024, labeled "1440p") through.
    fake_formats = [
        {"height": 342, "format_note": "480p"},
        {"height": 512, "format_note": "720p"},
        {"height": 768, "format_note": "1080p"},
        {"height": 1024, "format_note": "1440p"},
    ]
    monkeypatch.setattr(download_module, "_fetch_formats_for_quality_resolution", lambda *a, **k: fake_formats)
    opts = build_download_options("1080p", "/tmp/v", "/ff", [], [])
    assert "[height<=768]" in opts["format"]
    assert "height<=1080]" not in opts["format"]
    assert "height<=1024]" not in opts["format"]


def test_build_download_options_falls_back_to_literal_height_when_lookup_finds_no_match(monkeypatch):
    # A platform whose extractor doesn't populate format_note (most non-
    # YouTube sources), or a failed lookup, has no label to match against -
    # fall back to the label's own number as a literal height, same
    # assumption used before per-label resolution existed.
    monkeypatch.setattr(download_module, "_fetch_formats_for_quality_resolution", lambda *a, **k: [])
    opts = build_download_options("1080p", "/tmp/v", "/ff", [], [])
    assert "[height<=1080]" in opts["format"]


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


# ---- download_direct_url ----
#
# Zero test coverage existed for this function before 2026-07-07 - every
# route-level test that touched it monkeypatched download_direct_url itself
# rather than the urllib call inside it, so a real bug (backend/download.py
# never imported urllib.request at all, despite calling
# urllib.request.Request/urlopen) went unnoticed until a live download was
# actually attempted (see MISTAKES.md). This exercises the REAL function body.


class _FakeCdnResponse:
    def __init__(self, body):
        self._body = body
        self.headers = {"Content-Length": str(len(body))}

    def read(self, n=-1):
        chunk, self._body = self._body[:n if n and n > 0 else len(self._body)], self._body[n if n and n > 0 else len(self._body):]
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_download_direct_url_writes_the_response_body_to_disk(tmp_path, monkeypatch):
    jobs_module.jobs["j-direct"] = {"cancelled": False, "percent": 0, "text": ""}
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30: _FakeCdnResponse(b"fake-cdn-bytes"))

    out_path = tmp_path / "out.jpg"
    download_direct_url("http://cdn.example.com/i.jpg", str(out_path), "j-direct")

    assert out_path.read_bytes() == b"fake-cdn-bytes"
    assert jobs_module.jobs["j-direct"]["percent"] == 100
