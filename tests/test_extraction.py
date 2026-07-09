"""Unit tests for backend.extraction - metadata extraction, error mapping,
item shaping."""

import pytest
import yt_dlp

from backend import classify
from backend import extraction as extraction_module
from backend.extraction import (
    describe_extraction_error,
    format_duration,
    qualities_for,
    resolve_thumbnail,
)


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


# ---- qualities_for / format_duration ----


def test_qualities_for_lists_resolutions_high_to_low_plus_defaults():
    info = {"formats": [{"height": 480}, {"height": 720}, {"height": 240}]}
    assert qualities_for(info) == ["720p", "480p", "Best", "Audio Only"]


def test_qualities_for_ignores_formats_without_a_usable_height():
    info = {"formats": [{"height": None}, {}, {"height": 720}]}
    assert qualities_for(info) == ["720p", "Best", "Audio Only"]


def test_qualities_for_defaults_only_when_no_formats():
    assert qualities_for({}) == ["Best", "Audio Only"]


def test_qualities_for_uses_youtubes_label_not_raw_height_for_ultrawide_video():
    # Regression: a non-16:9 (e.g. ultrawide/letterboxed) source has a raw
    # pixel `height` well below its YouTube-labeled tier - a real "2160p"
    # stream can be as short as 1440px tall. Using raw height both shows the
    # wrong number (e.g. "1440p" for what YouTube itself calls 2160p) and can
    # drop a tier that's really >= 360p under the raw-height floor. Numbers
    # below are real values pulled from a live 2.5:1 aspect-ratio video.
    info = {
        "formats": [
            {"height": 170, "format_note": "240p"},
            {"height": 256, "format_note": "360p"},
            {"height": 342, "format_note": "480p"},
            {"height": 512, "format_note": "720p"},
            {"height": 768, "format_note": "1080p"},
            {"height": 1024, "format_note": "1440p"},
            {"height": 1440, "format_note": "2160p"},
        ]
    }
    assert qualities_for(info) == [
        "2160p", "1440p", "1080p", "720p", "480p", "360p", "Best", "Audio Only",
    ]


def test_qualities_for_falls_back_to_raw_height_when_format_note_is_missing_or_unparsable():
    info = {"formats": [{"height": 720, "format_note": None}, {"height": 480, "format_note": "storyboard"}]}
    assert qualities_for(info) == ["720p", "480p", "Best", "Audio Only"]


def test_format_duration_formats_minutes_and_seconds():
    assert format_duration(95) == "01:35"


def test_format_duration_returns_none_for_non_numeric():
    assert format_duration(None) is None
    assert format_duration("unknown") is None


# ---- describe_extraction_error ----


def test_describe_extraction_error_trims_to_first_sentence():
    error = yt_dlp.utils.DownloadError(
        "ERROR: Video unavailable. This video has been removed by the uploader. Confirm you are on the latest version."
    )
    # strips the CLI-style "ERROR: " prefix and keeps just the first sentence
    assert describe_extraction_error("https://youtube.com/watch?v=abc", error) == "Video unavailable"


def test_describe_extraction_error_special_cases_instagram_login_message():
    error = yt_dlp.utils.DownloadError(
        "ERROR: [Instagram] abc: Instagram sent an empty media response. Check if this post is accessible "
        "in your browser without being logged-in. Use --cookies-from-browser for authentication."
    )
    message = describe_extraction_error("https://www.instagram.com/reel/abc/", error)
    assert "Không thể tải video từ tài khoản Private" in message


def test_describe_extraction_error_special_cases_instagram_private_post_message():
    # real message shape from a live private Instagram post - raise_login_required()
    # here uses wording that contains neither "empty media response" nor "login",
    # only the "Use --cookies..." hint it always appends
    error = yt_dlp.utils.DownloadError(
        "ERROR: [Instagram] abc123: This content is only available for registered users who follow this "
        "account. Use --cookies-from-browser or --cookies for the authentication. See "
        "https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp for how to manually pass cookies"
    )
    message = describe_extraction_error("https://www.instagram.com/reel/abc123/", error)
    assert "Không thể tải video từ tài khoản Private" in message


def test_describe_extraction_error_network_failure_gets_its_own_message():
    # ConnectionError/TimeoutError/socket.gaierror are bare builtin
    # exceptions (module "builtins"/"socket"), so without a dedicated check
    # they'd otherwise fall into the generic "something broke" fallback -
    # hiding a real "you're offline" failure behind a message that gives no
    # actionable hint. Regression guard for the case reported live where
    # every link failed identically on one specific machine.
    import socket

    for error in (
        ConnectionError("Connection refused"),
        TimeoutError("timed out"),
        socket.gaierror("Name or service not known"),
    ):
        message = describe_extraction_error("https://www.youtube.com/watch?v=abc", error)
        assert "kết nối mạng" in message


def test_describe_extraction_error_ip_blocked_is_not_reported_as_private_account():
    # Regression: reported live on a real TikTok video. The bare substring
    # check for "400" used to match the digits embedded inside the video
    # ID ("...5400105274...") and misreport an IP block as "Private
    # account" - a completely different, actionable-differently failure.
    error = yt_dlp.utils.DownloadError(
        "ERROR: [TikTok] 7632605400105274: Your IP address is blocked from accessing this post"
    )
    message = describe_extraction_error("https://www.tiktok.com/@x/video/7632605400105274", error)
    assert "IP" in message
    assert "Private" not in message


def test_describe_extraction_error_real_http_400_still_maps_to_private_account():
    # The word-boundary fix must not break the legitimate case: a real
    # "HTTP Error 400" (with actual word boundaries around the digits)
    # still maps to the private/login-required message as before.
    error = yt_dlp.utils.DownloadError("ERROR: [Instagram] abc: HTTP Error 400: Bad Request")
    message = describe_extraction_error("https://www.instagram.com/p/abc/", error)
    assert "Không thể tải video từ tài khoản Private" in message


def test_describe_extraction_error_instagram_cookies_without_session_flags_the_file(tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# no session in here\n")
    error = yt_dlp.utils.DownloadError(
        "ERROR: [Instagram] abc: Instagram sent an empty media response."
    )
    message = describe_extraction_error("https://www.instagram.com/reel/abc/", error, str(cookies_file))
    assert "Không thể tải video từ tài khoản Private" in message


def test_describe_extraction_error_instagram_cookies_with_session_suggests_refreshing(tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    error = yt_dlp.utils.DownloadError(
        "ERROR: [Instagram] abc: Instagram sent an empty media response."
    )
    message = describe_extraction_error("https://www.instagram.com/reel/abc/", error, str(cookies_file))
    assert "Không thể tải video từ tài khoản Private" in message


def test_describe_extraction_error_does_not_special_case_non_instagram_urls():
    error = yt_dlp.utils.DownloadError("ERROR: [TikTok] abc: empty media response")
    message = describe_extraction_error("https://www.tiktok.com/@user/video/1", error)
    assert "logged-in session" not in message


def test_check_link_returns_error_when_info_is_empty(client, monkeypatch):
    monkeypatch.setattr(extraction_module, "extract_video_info", lambda url: None)
    resp = client.post("/api/check", json={"url": "https://youtube.com/watch?v=abc"})
    assert resp.status_code == 400
    assert "Không thể xử lý liên kết" in resp.get_json()["error"]


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
    monkeypatch.setattr(extraction_module, "extract_video_info", lambda url: info)
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
    monkeypatch.setattr(extraction_module, "extract_video_info", lambda url: info)
    resp = client.post("/api/check", json={"url": "https://www.youtube.com/watch?v=abc"})
    body = resp.get_json()
    assert body["qualities"] == ["Best", "Audio Only"]


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

    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYoutubeDL)
    extraction_module.extract_video_info(classify.classify_url("https://www.youtube.com/playlist?list=PLxyz"))

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

    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYoutubeDL)
    extraction_module.extract_video_info(classify.classify_url("https://www.youtube.com/watch?v=abc"))
    assert captured["opts"]["noplaylist"] is True
    assert "extract_flat" not in captured["opts"]


# ---- extract_video_info: Instagram profile resolver chain ----


def _no_instagram_cookies(monkeypatch):
    # Skip real config/browser cookie lookups - the tests below only care
    # about the fallback ORDER, not real Instagram auth.
    from backend import config as config_module
    from backend import cookies as cookies_module

    monkeypatch.setattr(config_module, "get_cookies_path", lambda: None)
    monkeypatch.setattr(cookies_module, "instagram_cookiefile_candidates", lambda: [])


def test_extract_video_info_profile_tries_private_feed_api_first(monkeypatch):
    # 2026-07-07: web_profile_info/GraphQL/instaloader all now answer a
    # profile's post *count* with no *edges* for a session that doesn't own
    # it (confirmed live, MISTAKES.md) - the private feed API must be tried
    # BEFORE any of those, not after.
    _no_instagram_cookies(monkeypatch)
    from backend import instagram as instagram_module

    called = {"instaloader": False}
    monkeypatch.setattr(
        instagram_module,
        "fetch_instagram_profile_reel_media",
        lambda username, cookies_path, **kwargs: [{"id": "abc", "title": "Reel", "url": "https://www.instagram.com/reel/abc/"}],
    )

    def fake_instaloader(username, cookies_path, **kwargs):
        called["instaloader"] = True
        raise AssertionError("should not fall back when the primary method succeeds")

    monkeypatch.setattr(instagram_module, "fetch_instagram_profile_instaloader", fake_instaloader)

    cls = classify.classify_url("https://www.instagram.com/someuser/reels/")
    info = extraction_module.extract_video_info(cls)
    assert info["entries"][0]["id"] == "abc"
    assert called["instaloader"] is False


def test_extract_video_info_profile_raises_instead_of_silent_empty_playlist(monkeypatch):
    # design-principles §3: never a silent broken empty state. If every
    # resolver in the chain comes back with zero entries, extract_video_info
    # must raise (a friendly "no videos found" error), not hand back a
    # playlist with 0 items that looks like a successful, empty channel.
    _no_instagram_cookies(monkeypatch)
    from backend import instagram as instagram_module

    monkeypatch.setattr(instagram_module, "fetch_instagram_profile_reel_media", lambda username, cookies_path, **kwargs: [])
    monkeypatch.setattr(instagram_module, "fetch_instagram_profile_instaloader", lambda username, cookies_path, **kwargs: [])
    monkeypatch.setattr(instagram_module, "fetch_instagram_profile_info", lambda username, cookies_path: {"user": {}})
    monkeypatch.setattr(instagram_module, "parse_instagram_profile_json", lambda data, username, **kwargs: [])

    cls = classify.classify_url("https://www.instagram.com/someuser/reels/")
    with pytest.raises(Exception):
        extraction_module.extract_video_info(cls)
