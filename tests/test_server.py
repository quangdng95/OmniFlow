import json
import os
import sys
import time
import types
from types import SimpleNamespace

import pytest

import server as server_module
from backend import classify, paths
from backend.classify import (
    get_platform_info,
    instagram_shortcode_from_url,
    is_playlist_url,
)
from server import (
    InstagramAuthError,
    apply_progress_update,
    build_download_options,
    combined_download_percent,
    cookies_file_has_instagram_session,
    cookies_status_for,
    describe_extraction_error,
    detect_video_codec,
    ensure_h264,
    format_duration,
    get_cookies_path,
    get_unique_filename,
    instagram_check_response,
    instagram_media_id_from_shortcode,
    is_local_request,
    load_session,
    qualities_for,
    resolve_save_dir,
    resolve_thumbnail,
    sanitize_filename,
    save_session,
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


# ---- get_platform_info ----


def test_get_platform_info_youtube():
    assert get_platform_info("https://www.youtube.com/watch?v=abc") == "YouTube"
    assert get_platform_info("https://youtu.be/abc") == "YouTube"


def test_get_platform_info_instagram():
    assert get_platform_info("https://www.instagram.com/reel/abc") == "Instagram"


def test_get_platform_info_tiktok():
    assert get_platform_info("https://www.tiktok.com/@user/video/1") == "TikTok"


def test_get_platform_info_facebook():
    assert get_platform_info("https://www.facebook.com/watch/?v=1") == "Facebook"
    assert get_platform_info("https://fb.watch/abc") == "Facebook"


def test_get_platform_info_rednote():
    assert get_platform_info("https://www.xiaohongshu.com/explore/abc") == "RedNote"
    assert get_platform_info("https://xhslink.com/abc") == "RedNote"
    # "RedNote" is Xiaohongshu's international rebrand and uses its own domain
    assert get_platform_info("https://www.rednote.com/explore/abc") == "RedNote"


def test_get_platform_info_unknown_falls_back_to_link():
    assert get_platform_info("https://example.com/video") == "Link"


# ---- resolve_thumbnail ----


def test_resolve_thumbnail_prefers_the_singular_field():
    info = {"thumbnail": "https://example.com/direct.jpg", "thumbnails": [{"url": "https://example.com/list.jpg"}]}
    assert resolve_thumbnail(info) == "https://example.com/direct.jpg"


def test_resolve_thumbnail_falls_back_to_thumbnails_list():
    # RedNote/Xiaohongshu's extractor only populates the plural "thumbnails"
    # list; the generic "thumbnail" field selection step doesn't always run
    # in --simulate/skip_download mode.
    info = {"thumbnails": [{"url": "https://example.com/small.jpg"}, {"url": "https://example.com/best.jpg"}]}
    assert resolve_thumbnail(info) == "https://example.com/best.jpg"


def test_resolve_thumbnail_returns_none_when_nothing_available():
    assert resolve_thumbnail({}) is None
    assert resolve_thumbnail({"thumbnails": []}) is None


# ---- load_session / save_session ----


def test_load_session_returns_default_when_config_missing(isolated_config):
    session = load_session()
    assert session["path"].endswith("Downloads")


def test_load_session_returns_default_on_malformed_json(isolated_config):
    isolated_config.write_text("{not valid json")
    session = load_session()
    assert session["path"].endswith("Downloads")


def test_save_and_load_session_round_trip(isolated_config, tmp_path):
    save_session(str(tmp_path))
    session = load_session()
    assert session == {"path": str(tmp_path), "cookies_path": "", "browser": "chrome"}


def test_save_and_load_session_round_trip_with_cookies_path(isolated_config, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# fake cookies file")
    save_session(str(tmp_path), str(cookies_file))
    session = load_session()
    assert session == {"path": str(tmp_path), "cookies_path": str(cookies_file), "browser": "chrome"}


def test_load_session_self_heals_stale_path_to_real_downloads(isolated_config):
    save_session("/this/path/does/not/exist")
    session = load_session()
    assert session["path"] == os.path.expanduser("~/Downloads")
    # the correction is persisted, so a stale config doesn't need re-healing every request
    with open(isolated_config) as f:
        saved = json.load(f)
    assert saved["path"] == os.path.expanduser("~/Downloads")


# ---- get_cookies_path ----


def test_get_cookies_path_returns_none_when_not_configured(isolated_config):
    assert get_cookies_path() is None


def test_get_cookies_path_returns_none_when_configured_file_does_not_exist(isolated_config):
    save_session(os.path.expanduser("~/Downloads"), "/this/cookies/file/does/not/exist.txt")
    assert get_cookies_path() is None


def test_get_cookies_path_returns_path_when_file_exists(isolated_config, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# fake cookies file")
    save_session(os.path.expanduser("~/Downloads"), str(cookies_file))
    assert get_cookies_path() == str(cookies_file)


# ---- cookies_file_has_instagram_session / cookies_status_for ----


def test_cookies_file_has_instagram_session_true_for_a_normal_session_line(tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    assert cookies_file_has_instagram_session(str(cookies_file))


def test_cookies_file_has_instagram_session_true_for_httponly_prefixed_line(tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("#HttpOnly_.instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    assert cookies_file_has_instagram_session(str(cookies_file))


def test_cookies_file_has_instagram_session_ignores_real_comment_lines(tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(
        "# Netscape HTTP Cookie File\n.instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n"
    )
    assert cookies_file_has_instagram_session(str(cookies_file))


def test_cookies_file_has_instagram_session_false_for_wrong_domain(tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".youtube.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    assert not cookies_file_has_instagram_session(str(cookies_file))


def test_cookies_file_has_instagram_session_false_for_wrong_cookie_name(tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tcsrftoken\tabc123\n")
    assert not cookies_file_has_instagram_session(str(cookies_file))


def test_cookies_file_has_instagram_session_false_for_malformed_lines(tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tsessionid\tabc123\n")
    assert not cookies_file_has_instagram_session(str(cookies_file))


def test_cookies_file_has_instagram_session_false_when_file_missing():
    assert not cookies_file_has_instagram_session("/this/file/does/not/exist.txt")


def test_cookies_status_for_none_when_path_is_empty():
    assert cookies_status_for("") == "none"


def test_cookies_status_for_none_when_file_does_not_exist():
    assert cookies_status_for("/this/file/does/not/exist.txt") == "none"


def test_cookies_status_for_valid_when_file_has_session(tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    assert cookies_status_for(str(cookies_file)) == "valid"


def test_cookies_status_for_no_session_when_file_lacks_session(tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# fake cookies file with no session\n")
    assert cookies_status_for(str(cookies_file)) == "no_session"


# ---- /api/browse-file ----


def test_browse_file_returns_chosen_path(client, monkeypatch):
    monkeypatch.setattr(
        server_module.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="/Users/test/cookies.txt\n", stderr=""),
    )
    resp = client.post("/api/browse-file")
    assert resp.status_code == 200
    # the fake path doesn't exist on the test filesystem, so status can't be anything but "none"
    assert resp.get_json() == {"path": "/Users/test/cookies.txt", "cookies_status": "none"}


def test_browse_file_reports_cookies_status_for_the_picked_file(client, monkeypatch, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    monkeypatch.setattr(
        server_module.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=f"{cookies_file}\n", stderr=""),
    )
    resp = client.post("/api/browse-file")
    assert resp.get_json() == {"path": str(cookies_file), "cookies_status": "valid"}


def test_browse_file_returns_error_when_cancelled(client, monkeypatch):
    monkeypatch.setattr(
        server_module.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="User cancelled"),
    )
    resp = client.post("/api/browse-file")
    assert resp.status_code == 400


# ---- /api/settings cookies_status ----


def test_get_settings_reports_cookies_status_none_by_default(client):
    resp = client.get("/api/settings")
    assert resp.get_json()["cookies_status"] == "none"


def test_get_settings_reports_cookies_status_valid(client, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    save_session(os.path.expanduser("~/Downloads"), str(cookies_file))
    resp = client.get("/api/settings")
    assert resp.get_json()["cookies_status"] == "valid"


def test_post_settings_reports_cookies_status_no_session(client, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# no session in here\n")
    resp = client.post("/api/settings", json={"cookies_path": str(cookies_file)})
    assert resp.get_json()["cookies_status"] == "no_session"


# ---- /api/clipboard ----


def test_get_clipboard_returns_pasteboard_text(client, monkeypatch):
    monkeypatch.setattr(
        server_module.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="https://youtube.com/watch?v=abc", stderr=""),
    )
    resp = client.get("/api/clipboard")
    assert resp.status_code == 200
    assert resp.get_json() == {"text": "https://youtube.com/watch?v=abc"}


def test_get_clipboard_errors_when_pbpaste_fails(client, monkeypatch):
    monkeypatch.setattr(
        server_module.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="boom"),
    )
    resp = client.get("/api/clipboard")
    assert resp.status_code == 500
    assert resp.get_json() == {"error": "Could not read clipboard"}


def test_get_clipboard_errors_when_pbpaste_is_missing(client, monkeypatch):
    def raise_not_found(*a, **k):
        raise FileNotFoundError("pbpaste not found")

    monkeypatch.setattr(server_module.subprocess, "run", raise_not_found)
    resp = client.get("/api/clipboard")
    assert resp.status_code == 500


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


# ---- qualities_for / format_duration ----


def test_qualities_for_lists_resolutions_high_to_low_plus_defaults():
    info = {"formats": [{"height": 480}, {"height": 720}, {"height": 240}]}
    assert qualities_for(info) == ["720p", "480p", "Best", "Audio Only"]


def test_qualities_for_ignores_formats_without_a_usable_height():
    info = {"formats": [{"height": None}, {}, {"height": 720}]}
    assert qualities_for(info) == ["720p", "Best", "Audio Only"]


def test_qualities_for_defaults_only_when_no_formats():
    assert qualities_for({}) == ["Best", "Audio Only"]


def test_format_duration_formats_minutes_and_seconds():
    assert format_duration(95) == "01:35"


def test_format_duration_returns_none_for_non_numeric():
    assert format_duration(None) is None
    assert format_duration("unknown") is None


# ---- /api/check ----


def test_check_link_missing_url(client):
    resp = client.post("/api/check", json={})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Missing url"


def test_check_link_invalid_link(client, monkeypatch):
    def raise_error(url):
        raise server_module.yt_dlp.utils.DownloadError("ERROR: no such video. more CLI-only detail here")

    monkeypatch.setattr(server_module, "extract_video_info", raise_error)
    resp = client.post("/api/check", json={"url": "https://example.com/dead"})
    assert resp.status_code == 400
    # surfaces yt-dlp's real (trimmed) message instead of a generic one
    assert resp.get_json()["error"] == "no such video"


def test_check_link_unexpected_exception_falls_back_to_generic_message(client, monkeypatch):
    def raise_error(url):
        raise RuntimeError("something unrelated broke")

    monkeypatch.setattr(server_module, "extract_video_info", raise_error)
    resp = client.post("/api/check", json={"url": "https://example.com/dead"})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Invalid link or private video"


def test_check_link_instagram_login_required_shows_clear_explanation(client, monkeypatch):
    def raise_error(url):
        raise server_module.yt_dlp.utils.DownloadError(
            "ERROR: [Instagram] abc: Instagram sent an empty media response. "
            "Check if this post is accessible in your browser without being logged-in."
        )

    monkeypatch.setattr(server_module, "extract_video_info", raise_error)
    resp = client.post("/api/check", json={"url": "https://www.instagram.com/p/abc/"})
    assert resp.status_code == 400
    assert "Không thể tải video từ tài khoản Private" in resp.get_json()["error"]


def test_check_link_instagram_with_no_session_cookies_file_flags_the_file(client, monkeypatch, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# no session in here\n")
    save_session(os.path.expanduser("~/Downloads"), str(cookies_file))

    def raise_error(url):
        raise server_module.yt_dlp.utils.DownloadError(
            "ERROR: [Instagram] abc: Instagram sent an empty media response."
        )

    monkeypatch.setattr(server_module, "extract_video_info", raise_error)
    resp = client.post("/api/check", json={"url": "https://www.instagram.com/p/abc/"})
    assert resp.status_code == 400
    assert "Không thể tải video từ tài khoản Private" in resp.get_json()["error"]


def test_check_link_instagram_with_expired_session_cookies_suggests_refreshing(client, monkeypatch, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    save_session(os.path.expanduser("~/Downloads"), str(cookies_file))

    # Cookies look valid (they have a sessionid), so the resolver actually runs
    # and Instagram itself rejects the still-invalid session.
    def raise_error(url, cookies_path):
        raise InstagramAuthError("Instagram sent an empty media response.")

    monkeypatch.setattr(server_module, "fetch_instagram_media", raise_error)
    resp = client.post("/api/check", json={"url": "https://www.instagram.com/p/abc/"})
    assert resp.status_code == 400
    assert "Không thể tải video từ tài khoản Private" in resp.get_json()["error"]


# ---- Instagram media resolver (photos/carousels) ----


def test_instagram_shortcode_from_url_post():
    assert instagram_shortcode_from_url("https://www.instagram.com/p/DYTRs5Loe6A/") == "DYTRs5Loe6A"


def test_instagram_shortcode_from_url_reel():
    assert instagram_shortcode_from_url("https://www.instagram.com/reel/DUvAWWREkNIWX8/?x=1") == "DUvAWWREkNIWX8"


def test_instagram_shortcode_from_url_tv():
    assert instagram_shortcode_from_url("https://instagram.com/tv/ABC123_-/") == "ABC123_-"


def test_instagram_shortcode_from_url_stories_returns_none():
    # Stories keep the yt-dlp path - they carry no post shortcode.
    assert instagram_shortcode_from_url("https://www.instagram.com/stories/someone/123/") is None


def test_instagram_shortcode_from_url_non_instagram_returns_none():
    assert instagram_shortcode_from_url("https://www.youtube.com/watch?v=abc") is None


def test_instagram_media_id_from_shortcode_decodes_known_value():
    # Shortcodes are the numeric media pk in url-safe base64.
    assert instagram_media_id_from_shortcode("B") == 1
    assert instagram_media_id_from_shortcode("CGwkwOEA1Aq") == 2427601842461691946


def test_parse_instagram_cookies_reads_values_without_a_magic_header(tmp_path):
    # No "# Netscape HTTP Cookie File" header - MozillaCookieJar would reject
    # this, but real browser exports vary, so the resolver parses it by hand.
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(
        "#HttpOnly_.instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tsess123\n"
        ".instagram.com\tTRUE\t/\tTRUE\t1799999999\tcsrftoken\tcsrf456\n"
        ".youtube.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tignoreme\n"
    )
    cookies = server_module._parse_instagram_cookies(str(cookies_file))
    assert cookies["csrftoken"] == "csrf456"
    assert cookies["sessionid"] == "sess123"


def test_fetch_instagram_media_maps_login_redirect_to_auth_error(tmp_path, monkeypatch):
    # Confirmed live: an invalid/expired sessionid makes Instagram's media-info
    # endpoint 302-redirect to the login page rather than return 401/403. That
    # must still surface the friendly cookies guidance, not a generic error.
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tbad\n")

    def raise_302(req, timeout=30):
        raise server_module.urllib.error.HTTPError(req.full_url, 302, "Found", {}, None)

    monkeypatch.setattr(server_module.urllib.request, "urlopen", raise_302)
    with pytest.raises(InstagramAuthError):
        server_module.fetch_instagram_media("https://www.instagram.com/p/abc/", str(cookies_file))


def test_instagram_check_response_single_image_is_a_video_typed_image_kind():
    media = {"title": "Nice pic", "items": [{"kind": "image", "url": "http://cdn/p.jpg", "thumbnail": "http://cdn/p.jpg"}]}
    body = instagram_check_response("https://www.instagram.com/p/abc/", media)
    assert body["type"] == "video"
    assert body["kind"] == "image"
    assert body["qualities"] == ["Image"]
    assert body["platform"] == "Instagram"
    assert body["thumbnail"] == "http://cdn/p.jpg"
    # The raw CDN download url is never exposed to the client.
    assert "url" not in body


def test_instagram_check_response_carousel_is_a_playlist_carrying_kinds():
    media = {
        "title": "Album",
        "items": [
            {"kind": "image", "url": "http://cdn/1.jpg", "thumbnail": "http://cdn/1.jpg"},
            {"kind": "video", "url": "http://cdn/2.mp4", "thumbnail": "http://cdn/2t.jpg"},
        ],
    }
    body = instagram_check_response("https://www.instagram.com/p/abc/", media)
    assert body["type"] == "playlist"
    assert [i["kind"] for i in body["items"]] == ["image", "video"]
    assert body["items"][0]["qualities"] == ["Image"]
    assert body["items"][1]["qualities"] == ["Video"]
    # No raw CDN urls leak into the item list either.
    assert all("url" not in i for i in body["items"])


def test_check_link_instagram_single_photo_end_to_end(client, monkeypatch, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    save_session(os.path.expanduser("~/Downloads"), str(cookies_file))
    monkeypatch.setattr(
        server_module,
        "fetch_instagram_media",
        lambda url, cookies_path: {"title": "A photo", "items": [{"kind": "image", "url": "http://cdn/p.jpg", "thumbnail": "http://cdn/p.jpg"}]},
    )
    resp = client.post("/api/check", json={"url": "https://www.instagram.com/p/abc/"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["type"] == "video"
    assert body["kind"] == "image"


def test_check_link_instagram_carousel_end_to_end(client, monkeypatch, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    save_session(os.path.expanduser("~/Downloads"), str(cookies_file))
    monkeypatch.setattr(
        server_module,
        "fetch_instagram_media",
        lambda url, cookies_path: {
            "title": "Album",
            "items": [
                {"kind": "image", "url": "http://cdn/1.jpg", "thumbnail": None},
                {"kind": "video", "url": "http://cdn/2.mp4", "thumbnail": None},
                {"kind": "image", "url": "http://cdn/3.jpg", "thumbnail": None},
            ],
        },
    )
    resp = client.post("/api/check", json={"url": "https://www.instagram.com/p/abc/"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["type"] == "playlist"
    assert len(body["items"]) == 3
    assert [i["kind"] for i in body["items"]] == ["image", "video", "image"]


# ---- describe_extraction_error ----


def test_describe_extraction_error_trims_to_first_sentence():
    error = server_module.yt_dlp.utils.DownloadError(
        "ERROR: Video unavailable. This video has been removed by the uploader. Confirm you are on the latest version."
    )
    # strips the CLI-style "ERROR: " prefix and keeps just the first sentence
    assert describe_extraction_error("https://youtube.com/watch?v=abc", error) == "Video unavailable"


def test_describe_extraction_error_special_cases_instagram_login_message():
    error = server_module.yt_dlp.utils.DownloadError(
        "ERROR: [Instagram] abc: Instagram sent an empty media response. Check if this post is accessible "
        "in your browser without being logged-in. Use --cookies-from-browser for authentication."
    )
    message = describe_extraction_error("https://www.instagram.com/reel/abc/", error)
    assert "Không thể tải video từ tài khoản Private" in message


def test_describe_extraction_error_special_cases_instagram_private_post_message():
    # real message shape from a live private Instagram post - raise_login_required()
    # here uses wording that contains neither "empty media response" nor "login",
    # only the "Use --cookies..." hint it always appends
    error = server_module.yt_dlp.utils.DownloadError(
        "ERROR: [Instagram] abc123: This content is only available for registered users who follow this "
        "account. Use --cookies-from-browser or --cookies for the authentication. See "
        "https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp for how to manually pass cookies"
    )
    message = describe_extraction_error("https://www.instagram.com/reel/abc123/", error)
    assert "Không thể tải video từ tài khoản Private" in message


def test_describe_extraction_error_instagram_cookies_without_session_flags_the_file(tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# no session in here\n")
    error = server_module.yt_dlp.utils.DownloadError(
        "ERROR: [Instagram] abc: Instagram sent an empty media response."
    )
    message = describe_extraction_error("https://www.instagram.com/reel/abc/", error, str(cookies_file))
    assert "Không thể tải video từ tài khoản Private" in message


def test_describe_extraction_error_instagram_cookies_with_session_suggests_refreshing(tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    error = server_module.yt_dlp.utils.DownloadError(
        "ERROR: [Instagram] abc: Instagram sent an empty media response."
    )
    message = describe_extraction_error("https://www.instagram.com/reel/abc/", error, str(cookies_file))
    assert "Không thể tải video từ tài khoản Private" in message


def test_describe_extraction_error_does_not_special_case_non_instagram_urls():
    error = server_module.yt_dlp.utils.DownloadError("ERROR: [TikTok] abc: empty media response")
    message = describe_extraction_error("https://www.tiktok.com/@user/video/1", error)
    assert "logged-in session" not in message


def test_check_link_returns_error_when_info_is_empty(client, monkeypatch):
    monkeypatch.setattr(server_module, "extract_video_info", lambda url: None)
    resp = client.post("/api/check", json={"url": "https://youtube.com/watch?v=abc"})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Invalid link or private video"


def test_check_link_builds_qualities_and_duration(client, monkeypatch):
    info = {
        "title": "Test Video",
        "uploader": "Someone",
        "thumbnail": "https://example.com/thumb.jpg",
        "duration": 125,
        "formats": [
            {"height": 144},
            {"height": 360},
            {"height": 720},
            {"height": 1080},
            {"height": 240, "vcodec": "none"},  # still counted, no height filtering on codec
            {"height": None},
        ],
    }
    monkeypatch.setattr(server_module, "extract_video_info", lambda url: info)
    resp = client.post("/api/check", json={"url": "https://www.youtube.com/watch?v=abc"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["type"] == "video"
    assert body["title"] == "Test Video"
    assert body["platform"] == "YouTube"
    assert body["duration"] == "02:05"
    # only heights >= 360 are kept as explicit options, then Best + Audio Only appended
    assert body["qualities"] == ["1080p", "720p", "360p", "Best", "Audio Only"]


def test_check_link_drops_formats_below_360p(client, monkeypatch):
    info = {"title": "Low res", "formats": [{"height": 144}, {"height": 240}]}
    monkeypatch.setattr(server_module, "extract_video_info", lambda url: info)
    resp = client.post("/api/check", json={"url": "https://www.youtube.com/watch?v=abc"})
    body = resp.get_json()
    assert body["qualities"] == ["Best", "Audio Only"]


# ---- /api/check playlist handling (Instagram Stories / multi-video carousels) ----


def test_check_link_playlist_returns_video_entries_only(client, monkeypatch):
    info = {
        "_type": "playlist",
        "title": "Story by someone",
        "entries": [
            {
                "id": "vid1",
                "title": "Story item 1",
                "thumbnail": "https://example.com/1.jpg",
                "duration": 15,
                "formats": [{"height": 720}],
            },
            # a photo-only story item - yt-dlp never populates "formats" for
            # these, so it must be silently excluded, not error
            {"id": "photo1", "title": "Story item 2 (photo)"},
            {
                "id": "vid2",
                "title": "Story item 3",
                "thumbnail": "https://example.com/3.jpg",
                "duration": 8,
                "formats": [{"height": 1080}],
            },
        ],
    }
    monkeypatch.setattr(server_module, "extract_video_info", lambda url: info)
    resp = client.post("/api/check", json={"url": "https://www.instagram.com/stories/someone/1/"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["type"] == "playlist"
    assert body["title"] == "Story by someone"
    assert [item["id"] for item in body["items"]] == ["vid1", "vid2"]
    assert body["items"][0]["duration"] == "00:15"
    assert body["items"][0]["qualities"] == ["720p", "Best", "Audio Only"]


def test_check_link_playlist_with_only_photo_entries_returns_empty_items(client, monkeypatch):
    info = {"_type": "playlist", "title": "Story by someone", "entries": [{"id": "photo1", "title": "Photo"}]}
    monkeypatch.setattr(server_module, "extract_video_info", lambda url: info)
    resp = client.post("/api/check", json={"url": "https://www.instagram.com/stories/someone/1/"})
    assert resp.status_code == 200
    assert resp.get_json()["items"] == []


def test_extract_video_info_uses_yt_dlp_in_process(monkeypatch):
    captured = {}

    class FakeYoutubeDL:
        def __init__(self, opts):
            captured["opts"] = opts

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, url, download):
            captured["url"] = url
            captured["download"] = download
            return {"title": "ok"}

    monkeypatch.setattr(server_module.yt_dlp, "YoutubeDL", FakeYoutubeDL)
    result = server_module.extract_video_info(classify.classify_url("https://youtube.com/watch?v=abc"))

    assert result == {"title": "ok"}
    assert captured["url"] == "https://youtube.com/watch?v=abc"
    assert captured["download"] is False
    assert captured["opts"]["simulate"] is True
    assert captured["opts"]["noplaylist"] is True


# ---- /api/download ----


def test_start_download_missing_url(client):
    resp = client.post("/api/download", json={})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Missing url"


# ---- resolve_save_dir (folder-not-writable fallback) ----


def test_resolve_save_dir_returns_configured_path_when_valid(tmp_path):
    assert resolve_save_dir(str(tmp_path)) == str(tmp_path)


def test_resolve_save_dir_falls_back_and_creates_fallback_dir(tmp_path):
    fallback = tmp_path / "fallback" / "Downloads"
    result = resolve_save_dir("/this/path/does/not/exist", fallback_dir=str(fallback))
    assert result == str(fallback)
    assert fallback.is_dir()


def test_resolve_save_dir_returns_none_when_nothing_is_writable(tmp_path, monkeypatch):
    monkeypatch.setattr(server_module.os, "access", lambda *a, **k: False)
    result = resolve_save_dir("/this/path/does/not/exist", fallback_dir=str(tmp_path / "fallback"))
    assert result is None


class _NoOpThread:
    """Stand-in for threading.Thread that never actually runs its target,
    so the test never spawns a real yt-dlp subprocess."""

    def __init__(self, target=None, daemon=None):
        pass

    def start(self):
        pass


def test_start_download_falls_back_when_configured_folder_is_missing(client, monkeypatch, tmp_path):
    monkeypatch.setattr(
        server_module,
        "load_session",
        lambda: {"path": "/this/path/does/not/exist"},
    )
    monkeypatch.setattr(server_module, "resolve_save_dir", lambda path: str(tmp_path))
    monkeypatch.setattr(server_module.threading, "Thread", _NoOpThread)
    resp = client.post(
        "/api/download",
        json={"url": "https://youtube.com/watch?v=abc", "title": "Video", "quality": "720p"},
    )
    assert resp.status_code == 200
    assert "job_id" in resp.get_json()


def test_start_download_errors_when_no_folder_is_writable_anywhere(client, monkeypatch):
    monkeypatch.setattr(server_module, "resolve_save_dir", lambda path: None)
    resp = client.post(
        "/api/download",
        json={"url": "https://youtube.com/watch?v=abc", "title": "Video", "quality": "720p"},
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Download folder not writable"


def test_start_download_of_watch_list_url_downloads_the_watch_url_not_the_playlist(client, monkeypatch, tmp_path):
    # R5 pin: for watch?v=X&list=PL… the user picked video X, so the download
    # engine must receive the WATCH url. Only /api/check widens to the whole
    # playlist (classification carries the two URLs separately for exactly this).
    monkeypatch.setattr(server_module, "load_session", lambda: {"path": str(tmp_path), "cookies_path": ""})
    monkeypatch.setattr(server_module, "resolve_save_dir", lambda path: str(tmp_path))
    monkeypatch.setattr(paths, "get_ffmpeg_path", lambda: "/ff")
    monkeypatch.setattr(server_module, "ensure_h264", lambda *a, **k: None)

    seen = {}

    class FakeYDL:
        def __init__(self, opts):
            seen["opts"] = opts

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def download(self, urls):
            seen["urls"] = urls

    monkeypatch.setattr(server_module.yt_dlp, "YoutubeDL", FakeYDL)

    class SyncThread:
        # Runs the download worker inline so the assertion sees its yt-dlp call.
        def __init__(self, target=None, daemon=None):
            self._target = target

        def start(self):
            self._target()

    monkeypatch.setattr(server_module.threading, "Thread", SyncThread)

    watch_url = "https://www.youtube.com/watch?v=-It5L-gC6nA&list=PLIILL6veL783kKkdiIybbxARNY9bAVQYe"
    resp = client.post("/api/download", json={"url": watch_url, "title": "V", "quality": "720p"})
    assert resp.status_code == 200
    assert seen["urls"] == [watch_url]  # the watch URL - NOT playlist?list=…


def test_start_download_missing_ffmpeg(client, monkeypatch, tmp_path):
    monkeypatch.setattr(
        server_module, "load_session", lambda: {"path": str(tmp_path)}
    )
    monkeypatch.setattr(paths, "get_ffmpeg_path", lambda: None)
    resp = client.post(
        "/api/download",
        json={"url": "https://youtube.com/watch?v=abc", "title": "Video", "quality": "720p"},
    )
    assert resp.status_code == 400
    assert "FFmpeg" in resp.get_json()["error"]


# ---- /api/progress & /api/cancel ----


def test_progress_unknown_job(client):
    resp = client.get("/api/progress/does-not-exist")
    assert resp.status_code == 404


def test_cancel_unknown_job(client):
    resp = client.post("/api/cancel/does-not-exist")
    assert resp.status_code == 404


def test_cancel_marks_job_as_cancelled(client):
    server_module.jobs["job-1"] = {
        "status": "running",
        "percent": 10,
        "text": "Downloading...",
        "filename": None,
        "cancelled": False,
    }
    resp = client.post("/api/cancel/job-1")
    assert resp.status_code == 200
    assert server_module.jobs["job-1"]["cancelled"] is True


# ---- is_local_request ----


def test_is_local_request_true_for_loopback_hostnames():
    for host in ("127.0.0.1:5001", "localhost:5001", "localhost", "[::1]:5001", "[::1]"):
        with server_module.app.test_request_context(headers={"Host": host}):
            assert is_local_request(), host


def test_is_local_request_false_for_other_hosts():
    for host in ("example.com", "example.com:5001", "192.168.1.5:5001", "my-tunnel.ngrok.io"):
        with server_module.app.test_request_context(headers={"Host": host}):
            assert not is_local_request(), host


# ---- local-only route guards ----


def test_browse_folder_rejected_when_remote(client):
    resp = client.post("/api/browse", headers={"Host": "example.com"})
    assert resp.status_code == 403


def test_browse_file_rejected_when_remote(client):
    resp = client.post("/api/browse-file", headers={"Host": "example.com"})
    assert resp.status_code == 403


def test_open_folder_rejected_when_remote(client):
    resp = client.post("/api/open-folder", headers={"Host": "example.com"})
    assert resp.status_code == 403


def test_get_clipboard_rejected_when_remote(client):
    resp = client.get("/api/clipboard", headers={"Host": "example.com"})
    assert resp.status_code == 403


# ---- Instagram is local-only ----


def test_check_link_instagram_rejected_when_remote(client):
    resp = client.post(
        "/api/check",
        json={"url": "https://www.instagram.com/reel/abc/"},
        headers={"Host": "example.com"},
    )
    assert resp.status_code == 403
    assert "locally" in resp.get_json()["error"]


def test_check_link_instagram_not_blocked_when_local(client, monkeypatch, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    save_session(os.path.expanduser("~/Downloads"), str(cookies_file))
    monkeypatch.setattr(
        server_module,
        "fetch_instagram_media",
        lambda url, cookies_path: {"title": "A reel", "items": [{"kind": "video", "url": "http://cdn/v.mp4", "thumbnail": None}]},
    )
    resp = client.post("/api/check", json={"url": "https://www.instagram.com/reel/abc/"})
    assert resp.status_code == 200


def test_start_download_instagram_rejected_when_remote(client):
    resp = client.post(
        "/api/download",
        json={"url": "https://www.instagram.com/reel/abc/", "title": "Video", "quality": "720p"},
        headers={"Host": "example.com"},
    )
    assert resp.status_code == 403
    assert "locally" in resp.get_json()["error"]


# ---- remote downloads stage into a temp dir, not the configured folder ----


def test_start_download_remote_uses_a_temp_dir_not_the_configured_folder(client, monkeypatch):
    monkeypatch.setattr(server_module.threading, "Thread", _NoOpThread)
    resp = client.post(
        "/api/download",
        json={"url": "https://www.tiktok.com/@user/video/1", "title": "Video", "quality": "720p"},
        headers={"Host": "example.com"},
    )
    assert resp.status_code == 200
    job_id = resp.get_json()["job_id"]
    filepath = server_module.jobs[job_id]["filepath"]
    assert os.path.dirname(filepath) != os.path.expanduser("~/Downloads")
    assert os.path.basename(os.path.dirname(filepath)).startswith("omniflow-")


def test_start_download_instagram_no_cookies_succeeds_scheduling_and_fails_async(client, monkeypatch, tmp_path):
    # With no valid cookies configured, the Instagram download branch falls through
    # to the standard yt-dlp path and schedules a background job (status code 200).
    monkeypatch.setattr(server_module, "load_session", lambda: {"path": str(tmp_path), "cookies_path": ""})
    
    # Mock yt_dlp to fail with a login/empty media response error
    class MockYoutubeDL:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def download(self, urls):
            raise server_module.yt_dlp.utils.DownloadError("ERROR: [Instagram] abc: Instagram sent an empty media response.")

    monkeypatch.setattr(server_module.yt_dlp, "YoutubeDL", MockYoutubeDL)
    
    resp = client.post(
        "/api/download",
        json={"url": "https://www.instagram.com/reel/abc/", "title": "Video", "quality": "720p"},
    )
    assert resp.status_code == 200
    job_id = resp.get_json()["job_id"]
    
    for _ in range(50):
        if server_module.jobs[job_id]["status"] != "running":
            break
        time.sleep(0.05)
        
    assert server_module.jobs[job_id]["status"] == "error"
    assert "Không thể tải video từ tài khoản Private" in server_module.jobs[job_id]["text"]


def test_start_download_instagram_resolver_error_maps_to_friendly_message(client, monkeypatch, tmp_path):
    # When Instagram rejects an otherwise-valid-looking session mid-download, the
    # async run_instagram() handler must surface describe_extraction_error()'s
    # plain message, never a raw traceback.
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    save_session(str(tmp_path), str(cookies_file))

    def raise_error(url, cookies_path):
        raise InstagramAuthError("Instagram sent an empty media response.")

    monkeypatch.setattr(server_module, "fetch_instagram_media", raise_error)

    resp = client.post(
        "/api/download",
        json={"url": "https://www.instagram.com/reel/abc/", "title": "Video", "quality": "Video"},
    )
    job_id = resp.get_json()["job_id"]

    for _ in range(50):
        if server_module.jobs[job_id]["status"] != "running":
            break
        time.sleep(0.05)

    assert server_module.jobs[job_id]["status"] == "error"
    assert "Không thể tải video từ tài khoản Private" in server_module.jobs[job_id]["text"]


def test_start_download_instagram_image_writes_a_jpg(client, monkeypatch, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    save_session(str(tmp_path), str(cookies_file))
    monkeypatch.setattr(server_module, "resolve_save_dir", lambda path: str(tmp_path))
    monkeypatch.setattr(
        server_module,
        "fetch_instagram_media",
        lambda url, cookies_path: {"title": "A photo", "items": [{"kind": "image", "url": "http://cdn/pic.jpg", "thumbnail": "http://cdn/pic.jpg"}]},
    )

    def fake_download(cdn_url, output_path, job_id, chunk_size=131072):
        with open(output_path, "wb") as f:
            f.write(b"fake-image-bytes")

    monkeypatch.setattr(server_module, "download_direct_url", fake_download)

    resp = client.post(
        "/api/download",
        json={"url": "https://www.instagram.com/p/abc/", "title": "A photo", "quality": "Image"},
    )
    job_id = resp.get_json()["job_id"]

    for _ in range(50):
        if server_module.jobs[job_id]["status"] != "running":
            break
        time.sleep(0.05)

    job = server_module.jobs[job_id]
    assert job["status"] == "done"
    assert job["filename"].endswith(".jpg")
    assert os.path.exists(job["filepath"])


def test_start_download_instagram_entry_index_picks_that_carousel_item(client, monkeypatch, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    save_session(str(tmp_path), str(cookies_file))
    monkeypatch.setattr(server_module, "resolve_save_dir", lambda path: str(tmp_path))
    monkeypatch.setattr(
        server_module,
        "fetch_instagram_media",
        lambda url, cookies_path: {
            "title": "Carousel",
            "items": [
                {"kind": "image", "url": "http://cdn/pic.jpg", "thumbnail": None},
                {"kind": "video", "url": "http://cdn/clip.mp4", "thumbnail": None},
            ],
        },
    )

    captured = {}

    def fake_download(cdn_url, output_path, job_id, chunk_size=131072):
        captured["url"] = cdn_url
        with open(output_path, "wb") as f:
            f.write(b"fake")

    monkeypatch.setattr(server_module, "download_direct_url", fake_download)

    # entry_index 2 (1-based) -> the video slide.
    resp = client.post(
        "/api/download",
        json={"url": "https://www.instagram.com/p/abc/", "title": "Carousel", "quality": "Video", "entry_index": 2},
    )
    job_id = resp.get_json()["job_id"]

    for _ in range(50):
        if server_module.jobs[job_id]["status"] != "running":
            break
        time.sleep(0.05)

    job = server_module.jobs[job_id]
    assert job["status"] == "done"
    assert captured["url"] == "http://cdn/clip.mp4"
    assert job["filename"].endswith(".mp4")


# ---- /api/download-file/<job_id> ----


def test_download_file_rejected_when_local(client, tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_text("fake video bytes")
    server_module.jobs["job-remote-1"] = {"status": "done", "filename": "clip.mp4", "filepath": str(video)}
    resp = client.get("/api/download-file/job-remote-1")
    assert resp.status_code == 403


def test_download_file_404_for_unknown_job(client):
    resp = client.get("/api/download-file/does-not-exist", headers={"Host": "example.com"})
    assert resp.status_code == 404


def test_download_file_404_when_job_not_done(client):
    server_module.jobs["job-remote-2"] = {"status": "running", "filename": None, "filepath": None}
    resp = client.get("/api/download-file/job-remote-2", headers={"Host": "example.com"})
    assert resp.status_code == 404


def test_download_file_serves_and_cleans_up(client, tmp_path):
    job_dir = tmp_path / "omniflow-abc123"
    job_dir.mkdir()
    video = job_dir / "clip.mp4"
    video.write_bytes(b"fake video bytes")
    server_module.jobs["job-remote-3"] = {"status": "done", "filename": "clip.mp4", "filepath": str(video)}

    resp = client.get("/api/download-file/job-remote-3", headers={"Host": "example.com"})

    assert resp.status_code == 200
    assert resp.data == b"fake video bytes"
    assert "clip.mp4" in resp.headers.get("Content-Disposition", "")
    assert not job_dir.exists()


# ---- H.264 safety net (detect_video_codec / ensure_h264) ----


def test_detect_video_codec_parses_ffmpeg_stderr(monkeypatch):
    stderr = (
        "Input #0, mov,mp4, from 'x.mp4':\n"
        "  Stream #0:0(und): Video: vp9 (Profile 0), yuv420p(tv), 1920x1080\n"
        "  Stream #0:1(und): Audio: aac (LC), 44100 Hz\n"
    )
    monkeypatch.setattr(
        server_module.subprocess, "run",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr=stderr),
    )
    assert detect_video_codec("x.mp4", "/ff") == "vp9"


def test_detect_video_codec_returns_none_when_ffmpeg_unavailable(monkeypatch):
    def boom(*a, **k):
        raise OSError("no ffmpeg")

    monkeypatch.setattr(server_module.subprocess, "run", boom)
    assert detect_video_codec("x.mp4", "/ff") is None


def test_ensure_h264_is_a_noop_for_already_h264(monkeypatch):
    server_module.jobs["j-h264"] = {"cancelled": False, "text": "", "status": "running"}
    monkeypatch.setattr(server_module, "detect_video_codec", lambda path, ff: "h264")

    def fail(*a, **k):
        raise AssertionError("must not re-encode an already-h264 file")

    monkeypatch.setattr(server_module.subprocess, "Popen", fail)
    ensure_h264("/tmp/some.mp4", "/ff", "j-h264")  # no exception = no re-encode


def test_ensure_h264_reencodes_vp9_in_place(monkeypatch, tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"original-vp9-bytes")
    server_module.jobs["j-vp9"] = {"cancelled": False, "text": "", "status": "running"}
    monkeypatch.setattr(server_module, "detect_video_codec", lambda path, ff: "vp9")

    class FakePopen:
        def __init__(self, cmd, stdout=None, stderr=None):
            self.returncode = 0
            # ffmpeg writes to the temp output (last arg); simulate that.
            with open(cmd[-1], "wb") as f:
                f.write(b"reencoded-h264-bytes")

        def poll(self):
            return 0

    monkeypatch.setattr(server_module.subprocess, "Popen", FakePopen)
    ensure_h264(str(video), "/ff", "j-vp9")
    assert video.read_bytes() == b"reencoded-h264-bytes"
    assert not (tmp_path / "clip.mp4.h264.mp4").exists()  # temp cleaned up via replace


def test_ensure_h264_honors_cancel_mid_reencode(monkeypatch, tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"original-vp9-bytes")
    server_module.jobs["j-cancel"] = {"cancelled": True, "text": "", "status": "running"}
    monkeypatch.setattr(server_module, "detect_video_codec", lambda path, ff: "av01")

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

    monkeypatch.setattr(server_module.subprocess, "Popen", FakePopenRunning)
    with pytest.raises(server_module.yt_dlp.utils.DownloadCancelled):
        ensure_h264(str(video), "/ff", "j-cancel")
    assert video.read_bytes() == b"original-vp9-bytes"  # original untouched
    assert not (tmp_path / "clip.mp4.h264.mp4").exists()  # partial temp removed


# ---- auto cookie extraction (_write_cookies_txt / cookiefiles_from_browsers) ----


def test_cleanup_temp_cookiefiles_only_removes_our_temp_files(tmp_path):
    manual = tmp_path / "my-cookies.txt"
    manual.write_text("keep me")
    temp = server_module._write_cookies_txt({"sessionid": "x"})
    assert os.path.exists(temp)
    server_module._cleanup_temp_cookiefiles([str(manual), temp, None])
    assert not os.path.exists(temp)  # our temp file is gone
    assert manual.exists()  # the user's own file is untouched


def test_write_cookies_txt_produces_a_valid_session_file(tmp_path):
    path = server_module._write_cookies_txt({"sessionid": "live123", "csrftoken": "csrf1"})
    try:
        assert cookies_file_has_instagram_session(path)
        parsed = server_module._parse_instagram_cookies(path)
        assert parsed["sessionid"] == "live123"
        assert parsed["csrftoken"] == "csrf1"
    finally:
        os.remove(path)


def test_cookiefiles_from_browsers_writes_a_file_per_logged_in_account(no_browser_cookie_scan, monkeypatch):
    # no_browser_cookie_scan hands back the REAL function (the autouse fixture
    # otherwise stubs it to []); exercise it against a fake browser_cookie3 with
    # two different logged-in accounts across profiles.
    real = no_browser_cookie_scan
    monkeypatch.setattr(server_module, "_profile_cookie_db", lambda profile_dir: "/fake/Cookies")
    monkeypatch.setattr(server_module, "CHROMIUM_BROWSER_DIRS", {"chrome": "/fake"})

    def fake_chrome(cookie_file=None, domain_name=""):
        # Two distinct accounts keyed on which profile DB path was requested;
        # the bare-browser call (cookie_file=None) repeats Default's session and
        # must be deduped away.
        sess = {"/fake/Cookies": "accountA"}.get(cookie_file, "accountA")
        return [
            SimpleNamespace(name="sessionid", value=sess, domain=".instagram.com"),
            SimpleNamespace(name="csrftoken", value="c", domain=".instagram.com"),
            SimpleNamespace(name="ignore", value="x", domain=".other.com"),
        ]

    monkeypatch.setitem(sys.modules, "browser_cookie3", types.SimpleNamespace(chrome=fake_chrome))

    paths = real("instagram.com")
    try:
        # Same sessionid across all loaders -> deduped to a single cookiefile.
        assert len(paths) == 1
        assert cookies_file_has_instagram_session(paths[0])
        assert server_module._parse_instagram_cookies(paths[0])["sessionid"] == "accountA"
    finally:
        for p in paths:
            os.remove(p)


def test_cookiefiles_from_browsers_returns_empty_without_browser_cookie3(no_browser_cookie_scan, monkeypatch):
    real = no_browser_cookie_scan
    # Simulate browser_cookie3 not being importable.
    monkeypatch.setitem(sys.modules, "browser_cookie3", None)
    assert real("instagram.com") == []


# ---- fetch_instagram_media_any (multi-account fallback) ----


def test_fetch_instagram_media_any_returns_first_account_that_works(monkeypatch):
    # A private post is only visible to the account that follows its owner - here
    # the first candidate is unauthorized and the second one succeeds.
    calls = []

    def fake_fetch(url, cf):
        calls.append(cf)
        if cf == "/acctA.txt":
            raise InstagramAuthError("Instagram requires a logged-in session (cookies).")
        return {"title": "Private", "items": [{"kind": "video", "url": "http://cdn/v.mp4", "thumbnail": None}]}

    monkeypatch.setattr(server_module, "fetch_instagram_media", fake_fetch)
    media = server_module.fetch_instagram_media_any("https://www.instagram.com/p/abc/", ["/acctA.txt", "/acctB.txt"])
    assert media["title"] == "Private"
    assert calls == ["/acctA.txt", "/acctB.txt"]  # tried A, then B


def test_fetch_instagram_media_any_raises_auth_error_when_all_unauthorized(monkeypatch):
    def always_auth(url, cf):
        raise InstagramAuthError("Instagram requires a logged-in session (cookies).")

    monkeypatch.setattr(server_module, "fetch_instagram_media", always_auth)
    with pytest.raises(InstagramAuthError):
        server_module.fetch_instagram_media_any("https://www.instagram.com/p/abc/", ["/a.txt", "/b.txt"])


# ---- is_playlist_url ----


def test_is_playlist_url_matches_playlist_channel_and_handle():
    assert is_playlist_url("https://www.youtube.com/playlist?list=PLxyz")
    assert is_playlist_url("https://www.youtube.com/channel/UCabc")
    assert is_playlist_url("https://www.youtube.com/c/SomeChannel")
    assert is_playlist_url("https://www.youtube.com/user/SomeUser")
    assert is_playlist_url("https://www.youtube.com/@SomeHandle")
    assert is_playlist_url("https://www.youtube.com/@SomeHandle/videos")


def test_is_playlist_url_matches_a_youtube_url_carrying_a_list_param():
    # A YouTube URL with a list= param is a playlist, even in watch?v=...&list=...
    # form (extract the whole list, not just the one video).
    assert is_playlist_url("https://www.youtube.com/watch?v=abc&list=PLxyz")
    assert is_playlist_url("https://youtu.be/abc?list=PLxyz")


def test_is_playlist_url_treats_a_plain_video_as_a_single_video():
    # No list= param and not a channel/handle shape -> a single video.
    assert not is_playlist_url("https://www.youtube.com/watch?v=abc")
    assert not is_playlist_url("https://youtu.be/abc")
    assert not is_playlist_url("https://www.tiktok.com/@user/video/1")


# ---- Instagram profile detection ----


def test_is_instagram_profile_url():
    from backend.classify import is_instagram_profile_url
    assert is_instagram_profile_url("https://www.instagram.com/thexxlab_")
    assert is_instagram_profile_url("https://www.instagram.com/thexxlab_/")
    assert is_instagram_profile_url("https://www.instagram.com/thexxlab_/reels")
    assert is_instagram_profile_url("https://www.instagram.com/thexxlab_/reels/")
    
    # Exclude posts, stories, single reels
    assert not is_instagram_profile_url("https://www.instagram.com/p/C-i9vJ2ST7C/")
    assert not is_instagram_profile_url("https://www.instagram.com/reel/C-i9vJ2ST7C/")
    assert not is_instagram_profile_url("https://www.instagram.com/stories/username/123/")


def test_instagram_username_from_url():
    from backend.classify import instagram_username_from_url
    assert instagram_username_from_url("https://www.instagram.com/thexxlab_") == "thexxlab_"
    assert instagram_username_from_url("https://www.instagram.com/thexxlab_/") == "thexxlab_"
    assert instagram_username_from_url("https://www.instagram.com/thexxlab_/reels/") == "thexxlab_"
    assert instagram_username_from_url("https://www.instagram.com/p/C-i9vJ2ST7C/") == "p"


# ---- extract_video_info flat playlist extraction ----


def test_extract_video_info_uses_flat_extraction_for_a_playlist(monkeypatch):
    captured = {}

    class FakeYoutubeDL:
        def __init__(self, opts):
            captured["opts"] = opts

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, url, download):
            return {"_type": "playlist", "entries": []}

    monkeypatch.setattr(server_module.yt_dlp, "YoutubeDL", FakeYoutubeDL)
    server_module.extract_video_info(classify.classify_url("https://www.youtube.com/playlist?list=PLxyz"))

    opts = captured["opts"]
    assert opts["extract_flat"] == "in_playlist"
    assert opts["playlistend"] == classify.PLAYLIST_ITEM_CAP
    assert opts["noplaylist"] is False


def test_extract_video_info_keeps_noplaylist_for_a_single_video(monkeypatch):
    captured = {}

    class FakeYoutubeDL:
        def __init__(self, opts):
            captured["opts"] = opts

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, url, download):
            return {"title": "ok"}

    monkeypatch.setattr(server_module.yt_dlp, "YoutubeDL", FakeYoutubeDL)
    server_module.extract_video_info(classify.classify_url("https://www.youtube.com/watch?v=abc"))
    assert captured["opts"]["noplaylist"] is True
    assert "extract_flat" not in captured["opts"]


# ---- /api/check flat playlist response ----


def test_check_link_youtube_playlist_returns_items_with_urls(client, monkeypatch):
    info = {
        "_type": "playlist",
        "title": "My Playlist",
        "entries": [
            {"id": "v1", "title": "First", "url": "https://youtube.com/watch?v=v1", "duration": 65,
             "thumbnails": [{"url": "https://img/1.jpg"}]},
            {"id": "v2", "title": "Second", "url": "https://youtube.com/watch?v=v2", "duration": 30},
        ],
    }
    monkeypatch.setattr(server_module, "extract_video_info", lambda url: info)
    resp = client.post("/api/check", json={"url": "https://www.youtube.com/playlist?list=PLxyz"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["type"] == "playlist"
    assert body["platform"] == "YouTube"
    assert [i["url"] for i in body["items"]] == [
        "https://youtube.com/watch?v=v1",
        "https://youtube.com/watch?v=v2",
    ]
    # PRD §7: titles are CLEAN (no numeric prefix) - the ordering lives in the
    # separate `position` field, used for UI numbering only, never the filename.
    assert [i["title"] for i in body["items"]] == ["First", "Second"]
    assert [i["position"] for i in body["items"]] == [1, 2]
    assert all(i["is_available"] for i in body["items"])
    assert body["items"][0]["duration"] == "01:05"
    assert body["items"][0]["qualities"] == classify.PLAYLIST_QUALITIES
    assert body["truncated"] is False


def test_normalize_youtube_playlist_url_rewrites_watch_to_playlist():
    norm = classify.normalize_youtube_playlist_url
    # The owner's exact test case: watch?v=...&list=... MUST become playlist?list=...
    assert norm("https://www.youtube.com/watch?v=-It5L-gC6nA&list=PLIILL6veL783kKkdiIybbxARNY9bAVQYe") == (
        "https://www.youtube.com/playlist?list=PLIILL6veL783kKkdiIybbxARNY9bAVQYe"
    )
    # youtu.be short links carry the same rewrite.
    assert norm("https://youtu.be/-It5L-gC6nA?list=PLabc999") == "https://www.youtube.com/playlist?list=PLabc999"
    # Already-canonical playlist URL is idempotent.
    assert norm("https://www.youtube.com/playlist?list=PLxyz") == "https://www.youtube.com/playlist?list=PLxyz"
    # Mix/Radio (list=RD...) only resolves via the seed watch URL -> left untouched.
    assert norm("https://www.youtube.com/watch?v=abc&list=RDabc123") == "https://www.youtube.com/watch?v=abc&list=RDabc123"
    # A plain video (no list=) and non-YouTube URLs are unchanged.
    assert norm("https://www.youtube.com/watch?v=jNQXAC9IVRw") == "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    assert norm("https://www.tiktok.com/@x/video/123") == "https://www.tiktok.com/@x/video/123"


def test_extract_video_info_passes_canonical_playlist_url_to_ytdlp(monkeypatch):
    # The watch?v=...&list=... URL must reach yt-dlp as playlist?list=... - otherwise
    # yt-dlp's /watch video extractor returns a single video, not the list.
    seen = {}

    class FakeYDL:
        def __init__(self, opts):
            seen["opts"] = opts
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def extract_info(self, url, download=False):
            seen["url"] = url
            return {"_type": "playlist", "title": "PL", "entries": []}

    monkeypatch.setattr(server_module.yt_dlp, "YoutubeDL", FakeYDL)
    server_module.extract_video_info(
        classify.classify_url("https://www.youtube.com/watch?v=-It5L-gC6nA&list=PLIILL6veL783kKkdiIybbxARNY9bAVQYe")
    )
    assert seen["url"] == "https://www.youtube.com/playlist?list=PLIILL6veL783kKkdiIybbxARNY9bAVQYe"
    assert seen["opts"]["noplaylist"] is False  # i.e. --yes-playlist
    assert seen["opts"]["extract_flat"] == "in_playlist"


def test_check_link_single_item_playlist_is_not_numbered(client, monkeypatch):
    # A 1-video "playlist" (e.g. a channel with one upload) keeps a clean title -
    # the frontend renders it as a plain single video, not a numbered list.
    info = {
        "_type": "playlist",
        "title": "One video channel",
        "entries": [{"id": "solo", "title": "Only Video", "url": "https://youtube.com/watch?v=solo", "duration": 42}],
    }
    monkeypatch.setattr(server_module, "extract_video_info", lambda url: info)
    resp = client.post("/api/check", json={"url": "https://www.youtube.com/@onevid"})
    body = resp.get_json()
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "Only Video"  # no "01. " prefix


def test_check_link_youtube_playlist_flags_dead_videos_as_unavailable(client, monkeypatch):
    info = {
        "_type": "playlist",
        "title": "Mixed",
        "entries": [
            {"id": "ok1", "title": "Good One", "url": "https://youtube.com/watch?v=ok1", "duration": 100},
            {"id": "p", "title": "[Private video]", "url": "https://youtube.com/watch?v=p"},
            {"id": "d", "title": "[Deleted video]", "url": "https://youtube.com/watch?v=d"},
            # No duration -> treated as unavailable even without a dead-video title.
            {"id": "nod", "title": "No duration", "url": "https://youtube.com/watch?v=nod"},
            {"id": "ok2", "title": "Good Two", "url": "https://youtube.com/watch?v=ok2", "duration": 50},
        ],
    }
    monkeypatch.setattr(server_module, "extract_video_info", lambda url: info)
    resp = client.post("/api/check", json={"url": "https://www.youtube.com/playlist?list=PLxyz"})
    body = resp.get_json()
    # Dead videos are KEPT (so numbering stays true) but flagged unavailable.
    assert [i["is_available"] for i in body["items"]] == [True, False, False, False, True]
    # Titles stay clean; `position` keeps the true 1-based order even across dead ones.
    assert [i["title"] for i in body["items"]] == [
        "Good One", "[Private video]", "[Deleted video]", "No duration", "Good Two",
    ]
    assert [i["position"] for i in body["items"]] == [1, 2, 3, 4, 5]


def test_check_link_youtube_playlist_flags_truncation_at_the_cap(client, monkeypatch):
    entries = [{"id": f"v{i}", "title": f"V{i}", "url": f"https://youtube.com/watch?v=v{i}", "duration": 60}
               for i in range(classify.PLAYLIST_ITEM_CAP)]
    monkeypatch.setattr(server_module, "extract_video_info", lambda url: {"_type": "playlist", "title": "Big", "entries": entries})
    resp = client.post("/api/check", json={"url": "https://www.youtube.com/@somechannel"})
    body = resp.get_json()
    assert body["truncated"] is True
    assert len(body["items"]) == classify.PLAYLIST_ITEM_CAP
    # Title stays clean; position carries the ordering (the frontend zero-pads it).
    assert body["items"][0]["title"] == "V0"
    assert body["items"][0]["position"] == 1


def test_check_link_instagram_story_playlist_carries_original_entry_index(client, monkeypatch):
    # A Story mixing a photo (no formats) and videos: the kept video items must
    # carry their ORIGINAL 1-based position, not their filtered position.
    info = {
        "_type": "playlist",
        "title": "Story",
        "entries": [
            {"id": "a", "title": "Photo", },  # no formats -> dropped, but occupies index 1
            {"id": "b", "title": "Vid1", "formats": [{"height": 720}], "duration": 10},
            {"id": "c", "title": "Vid2", "formats": [{"height": 1080}], "duration": 8},
        ],
    }
    monkeypatch.setattr(server_module, "extract_video_info", lambda url: info)
    resp = client.post("/api/check", json={"url": "https://www.instagram.com/stories/someone/1/"})
    body = resp.get_json()
    assert [i["entry_index"] for i in body["items"]] == [2, 3]
    assert [i["title"] for i in body["items"]] == ["Vid1", "Vid2"]


# ---- /api/download-batch ----


def test_start_batch_download_requires_items(client):
    resp = client.post("/api/download-batch", json={"url": "https://youtube.com/playlist?list=x", "items": []})
    assert resp.status_code == 400


def test_start_batch_download_rejected_when_remote(client):
    resp = client.post(
        "/api/download-batch",
        json={"url": "https://youtube.com/playlist?list=x", "items": [{"title": "a", "url": "u"}]},
        headers={"Host": "example.com"},
    )
    assert resp.status_code == 403
    assert "locally" in resp.get_json()["error"]


def test_start_batch_download_schedules_and_reports_total(client, monkeypatch, tmp_path):
    monkeypatch.setattr(server_module, "load_session", lambda: {"path": str(tmp_path)})
    monkeypatch.setattr(server_module, "resolve_save_dir", lambda path: str(tmp_path))
    monkeypatch.setattr(server_module.threading, "Thread", _NoOpThread)
    resp = client.post(
        "/api/download-batch",
        json={
            "url": "https://youtube.com/playlist?list=x",
            "quality": "720p",
            "items": [{"title": "A", "url": "u1"}, {"title": "B", "url": "u2"}],
        },
    )
    assert resp.status_code == 200
    job_id = resp.get_json()["job_id"]
    assert server_module.jobs[job_id]["total"] == 2


def test_start_batch_download_downloads_all_items_in_parallel(client, monkeypatch, tmp_path):
    monkeypatch.setattr(server_module, "load_session", lambda: {"path": str(tmp_path)})
    monkeypatch.setattr(server_module, "resolve_save_dir", lambda path: str(tmp_path))
    monkeypatch.setattr(paths, "get_ffmpeg_path", lambda: "/ff")

    downloaded = []
    lock = __import__("threading").Lock()

    def fake_download_one(url, save_dir, title, quality, ffmpeg_bin, job_id, entry_index=None, on_progress=None):
        with lock:
            downloaded.append((url, title, quality))
        if on_progress:
            on_progress(100)
        out = os.path.join(save_dir, f"{title}.mp4")
        with open(out, "wb") as f:
            f.write(b"x")
        return out

    monkeypatch.setattr(server_module, "download_one_video", fake_download_one)

    resp = client.post(
        "/api/download-batch",
        json={
            "url": "https://youtube.com/playlist?list=x",
            "quality": "720p",
            "items": [
                {"title": "A", "url": "https://youtube.com/watch?v=a"},
                {"title": "B", "url": "https://youtube.com/watch?v=b"},
            ],
        },
    )
    job_id = resp.get_json()["job_id"]
    for _ in range(50):
        if server_module.jobs[job_id]["status"] != "running":
            break
        time.sleep(0.05)

    job = server_module.jobs[job_id]
    assert job["status"] == "done"
    assert job["saved_count"] == 2
    # Parallel -> order isn't guaranteed, so compare as a set.
    assert set(downloaded) == {
        ("https://youtube.com/watch?v=a", "A", "720p"),
        ("https://youtube.com/watch?v=b", "B", "720p"),
    }
    # Per-item progress is exposed, one entry per video, all finished.
    assert [p["status"] for p in job["items_progress"]] == ["done", "done"]
    assert all(p["percent"] == 100 for p in job["items_progress"])


def test_start_batch_download_skips_a_failing_item_and_keeps_going(client, monkeypatch, tmp_path):
    monkeypatch.setattr(server_module, "load_session", lambda: {"path": str(tmp_path)})
    monkeypatch.setattr(server_module, "resolve_save_dir", lambda path: str(tmp_path))
    monkeypatch.setattr(paths, "get_ffmpeg_path", lambda: "/ff")

    def fake_download_one(url, save_dir, title, quality, ffmpeg_bin, job_id, entry_index=None, on_progress=None):
        if title == "B":
            raise server_module.yt_dlp.utils.DownloadError("boom")
        out = os.path.join(save_dir, f"{title}.mp4")
        with open(out, "wb") as f:
            f.write(b"x")
        return out

    monkeypatch.setattr(server_module, "download_one_video", fake_download_one)

    resp = client.post(
        "/api/download-batch",
        json={
            "url": "https://youtube.com/playlist?list=x",
            "quality": "Best",
            "items": [{"title": "A", "url": "ua"}, {"title": "B", "url": "ub"}, {"title": "C", "url": "uc"}],
        },
    )
    job_id = resp.get_json()["job_id"]
    for _ in range(50):
        if server_module.jobs[job_id]["status"] != "running":
            break
        time.sleep(0.05)

    job = server_module.jobs[job_id]
    # One item failed, the other two still downloaded - the batch finishes "done".
    assert job["status"] == "done"
    assert job["saved_count"] == 2
    assert "1 failed" in job["text"]
