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
