"""Unit tests for backend.instagram - media resolver, check-response shaping,
multi-account fallback."""

import os
import urllib.error
import urllib.request

import pytest

from backend import cookies as cookies_module
from backend import instagram as instagram_module
from backend.instagram import (
    InstagramAuthError,
    instagram_check_response,
    instagram_media_id_from_shortcode,
)


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
    cookies = instagram_module._parse_instagram_cookies(str(cookies_file))
    assert cookies["csrftoken"] == "csrf456"
    assert cookies["sessionid"] == "sess123"


def test_fetch_instagram_media_maps_login_redirect_to_auth_error(tmp_path, monkeypatch):
    # Confirmed live: an invalid/expired sessionid makes Instagram's media-info
    # endpoint 302-redirect to the login page rather than return 401/403. That
    # must still surface the friendly cookies guidance, not a generic error.
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tbad\n")

    def raise_302(req, timeout=30):
        raise urllib.error.HTTPError(req.full_url, 302, "Found", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", raise_302)
    with pytest.raises(InstagramAuthError):
        instagram_module.fetch_instagram_media("https://www.instagram.com/p/abc/", str(cookies_file))


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

    monkeypatch.setattr(instagram_module, "fetch_instagram_media", fake_fetch)
    media = instagram_module.fetch_instagram_media_any("https://www.instagram.com/p/abc/", ["/acctA.txt", "/acctB.txt"])
    assert media["title"] == "Private"
    assert calls == ["/acctA.txt", "/acctB.txt"]  # tried A, then B


def test_fetch_instagram_media_any_raises_auth_error_when_all_unauthorized(monkeypatch):
    def always_auth(url, cf):
        raise InstagramAuthError("Instagram requires a logged-in session (cookies).")

    monkeypatch.setattr(instagram_module, "fetch_instagram_media", always_auth)
    with pytest.raises(InstagramAuthError):
        instagram_module.fetch_instagram_media_any("https://www.instagram.com/p/abc/", ["/a.txt", "/b.txt"])


# ---- fetch_instagram_profile_reel_media (private feed API, 2026-07-07) ----
#
# Confirmed live against a real profile+session: web_profile_info/GraphQL/
# instaloader all answer with a post *count* but no *edges* for a profile the
# session doesn't own. https://www.instagram.com/api/v1/feed/user/<id>/ (the
# same private-API host+header pattern already proven for fetch_instagram_media)
# still returns real items, so it is now the PRIMARY resolver - see MISTAKES.md.


class _FakeResponse:
    def __init__(self, payload):
        self._body = __import__("json").dumps(payload).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_fetch_instagram_profile_reel_media_filters_videos_and_paginates(monkeypatch, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tcsrftoken\tcsrf456\n")

    monkeypatch.setattr(
        instagram_module,
        "fetch_instagram_profile_info",
        lambda username, cookies_path: {"data": {"user": {"id": "999"}}},
    )

    pages = [
        {
            "items": [
                {"media_type": 1, "code": "PHOTO1"},  # photo - must be filtered out
                {"media_type": 2, "code": "REEL1", "caption": {"text": "First reel"}, "video_duration": 12.5,
                 "image_versions2": {"candidates": [{"url": "https://cdn/reel1.jpg"}]}},
            ],
            "more_available": True,
            "next_max_id": "cursor-2",
        },
        {
            "items": [
                {"media_type": 2, "code": "REEL2", "caption": {"text": "Second reel"}, "video_duration": 8.0,
                 "image_versions2": {"candidates": [{"url": "https://cdn/reel2.jpg"}]}},
            ],
            "more_available": False,
            "next_max_id": None,
        },
    ]
    calls = []

    def fake_urlopen(req, timeout=30):
        calls.append(req.full_url)
        return _FakeResponse(pages[len(calls) - 1])

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    entries = instagram_module.fetch_instagram_profile_reel_media("someuser", str(cookies_file))

    assert len(calls) == 2  # paginated once via next_max_id
    assert "cursor-2" in calls[1]
    assert [e["id"] for e in entries] == ["REEL1", "REEL2"]  # photo dropped, both reels kept in order
    assert entries[0]["title"] == "First reel"
    assert entries[0]["thumbnail"] == "https://cdn/reel1.jpg"
    assert entries[0]["duration"] == 12.5
    assert entries[0]["url"] == "https://www.instagram.com/reel/REEL1/"


def test_fetch_instagram_profile_reel_media_respects_limit(monkeypatch, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tcsrftoken\tcsrf456\n")

    monkeypatch.setattr(
        instagram_module,
        "fetch_instagram_profile_info",
        lambda username, cookies_path: {"data": {"user": {"id": "999"}}},
    )
    page = {
        "items": [{"media_type": 2, "code": f"R{i}"} for i in range(5)],
        "more_available": True,
        "next_max_id": "cursor-2",
    }
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30: _FakeResponse(page))

    entries = instagram_module.fetch_instagram_profile_reel_media("someuser", str(cookies_file), limit=3)
    assert len(entries) == 3


def test_fetch_instagram_profile_reel_media_maps_403_to_auth_error(monkeypatch, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tcsrftoken\tcsrf456\n")

    monkeypatch.setattr(
        instagram_module,
        "fetch_instagram_profile_info",
        lambda username, cookies_path: {"data": {"user": {"id": "999"}}},
    )

    def raise_403(req, timeout=30):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", raise_403)

    with pytest.raises(InstagramAuthError):
        instagram_module.fetch_instagram_profile_reel_media("someuser", str(cookies_file))


def test_fetch_instagram_profile_reel_media_raises_when_user_id_unresolvable(monkeypatch, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tcsrftoken\tcsrf456\n")
    monkeypatch.setattr(instagram_module, "fetch_instagram_profile_info", lambda username, cookies_path: {"data": {"user": {}}})

    with pytest.raises(InstagramAuthError):
        instagram_module.fetch_instagram_profile_reel_media("someuser", str(cookies_file))
