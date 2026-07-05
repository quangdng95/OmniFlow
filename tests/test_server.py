import json
import os
from types import SimpleNamespace

import server as server_module
from server import (
    apply_progress_update,
    build_download_options,
    combined_download_percent,
    cookies_file_has_instagram_session,
    cookies_status_for,
    describe_extraction_error,
    get_cookies_path,
    get_platform_info,
    get_unique_filename,
    is_local_request,
    load_session,
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
    assert session == {"path": str(tmp_path), "cookies_path": ""}


def test_save_and_load_session_round_trip_with_cookies_path(isolated_config, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# fake cookies file")
    save_session(str(tmp_path), str(cookies_file))
    session = load_session()
    assert session == {"path": str(tmp_path), "cookies_path": str(cookies_file)}


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


def test_build_download_options_for_video_quality():
    opts = build_download_options("720p", "/tmp/My Video", "/path/to/ffmpeg", [], [])
    assert opts["format"] == "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
    assert opts["format_sort"] == ["vcodec:h264", "res:720"]
    assert opts["postprocessors"] == [{"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}]
    assert opts["postprocessor_args"] == {"ffmpeg": ["-movflags", "+faststart"]}


def test_build_download_options_for_best_quality_maps_to_2160():
    opts = build_download_options("Best", "/tmp/My Video", "/path/to/ffmpeg", [], [])
    assert opts["format"] == "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best"


def test_build_download_options_includes_cookiefile_when_provided():
    opts = build_download_options("720p", "/tmp/My Video", "/path/to/ffmpeg", [], [], "/path/to/cookies.txt")
    assert opts["cookiefile"] == "/path/to/cookies.txt"


def test_build_download_options_omits_cookiefile_when_not_provided():
    opts = build_download_options("720p", "/tmp/My Video", "/path/to/ffmpeg", [], [])
    assert "cookiefile" not in opts


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
    assert "logged-in session" in resp.get_json()["error"]
    assert "--cookies" not in resp.get_json()["error"]


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
    assert "doesn't look like it contains a logged-in session" in resp.get_json()["error"]


def test_check_link_instagram_with_expired_session_cookies_suggests_refreshing(client, monkeypatch, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    save_session(os.path.expanduser("~/Downloads"), str(cookies_file))

    def raise_error(url):
        raise server_module.yt_dlp.utils.DownloadError(
            "ERROR: [Instagram] abc: Instagram sent an empty media response."
        )

    monkeypatch.setattr(server_module, "extract_video_info", raise_error)
    resp = client.post("/api/check", json={"url": "https://www.instagram.com/p/abc/"})
    assert resp.status_code == 400
    assert "session looks expired or invalid" in resp.get_json()["error"]


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
    assert "logged-in session" in message
    assert "--cookies-from-browser" not in message


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
    assert "logged-in session" in message
    assert "registered users" not in message
    assert "--cookies" not in message


def test_describe_extraction_error_instagram_cookies_without_session_flags_the_file(tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# no session in here\n")
    error = server_module.yt_dlp.utils.DownloadError(
        "ERROR: [Instagram] abc: Instagram sent an empty media response."
    )
    message = describe_extraction_error("https://www.instagram.com/reel/abc/", error, str(cookies_file))
    assert "doesn't look like it contains a logged-in session" in message


def test_describe_extraction_error_instagram_cookies_with_session_suggests_refreshing(tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    error = server_module.yt_dlp.utils.DownloadError(
        "ERROR: [Instagram] abc: Instagram sent an empty media response."
    )
    message = describe_extraction_error("https://www.instagram.com/reel/abc/", error, str(cookies_file))
    assert "session looks expired or invalid" in message


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
    result = server_module.extract_video_info("https://youtube.com/watch?v=abc")

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


def test_start_download_missing_ffmpeg(client, monkeypatch, tmp_path):
    monkeypatch.setattr(
        server_module, "load_session", lambda: {"path": str(tmp_path)}
    )
    monkeypatch.setattr(server_module, "get_ffmpeg_path", lambda: None)
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


def test_check_link_instagram_not_blocked_when_local(client, monkeypatch):
    monkeypatch.setattr(server_module, "extract_video_info", lambda url: {"title": "A reel", "formats": []})
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
