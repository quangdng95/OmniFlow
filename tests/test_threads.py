"""Unit tests for backend.threads - the Threads post resolver.

Mirrors tests/test_instagram.py's structure: Threads shares Instagram's
private REST API shape (confirmed live 2026-07-07 against two real owner
posts - one video, one image), so the resolver's own logic (shortcode decode,
auth-error mapping, item shaping) is tested the same way.
"""

import json
import urllib.error
import urllib.request

import pytest

from backend import threads as threads_module
from backend.threads import ThreadsAuthError, threads_media_id_from_shortcode


def test_threads_media_id_from_shortcode_matches_instagram_scheme():
    # Confirmed live: Threads shortcodes decode with the exact same url-safe
    # base64 alphabet Instagram media ids use.
    from backend.instagram import instagram_media_id_from_shortcode
    for code in ("DWE8-rMEmXp", "DaTf9pqiaMW"):
        assert threads_media_id_from_shortcode(code) == instagram_media_id_from_shortcode(code)


def test_parse_threads_cookies_filters_by_threads_domain(tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(
        "#HttpOnly_.threads.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tsess123\n"
        ".threads.com\tTRUE\t/\tTRUE\t1799999999\tcsrftoken\tcsrf456\n"
        ".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tignoreme\n"
    )
    cookies = threads_module._parse_threads_cookies(str(cookies_file))
    assert cookies["sessionid"] == "sess123"
    assert cookies["csrftoken"] == "csrf456"


def test_fetch_threads_media_maps_login_redirect_to_auth_error(tmp_path, monkeypatch):
    # Mirrors the Instagram 302-redirect test - an invalid/expired session
    # redirects to login rather than returning 401/403.
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".threads.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tbad\n")

    def raise_302(req, timeout=30):
        raise urllib.error.HTTPError(req.full_url, 302, "Found", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", raise_302)
    with pytest.raises(ThreadsAuthError):
        threads_module.fetch_threads_media("https://www.threads.com/@someone/post/DWE8-rMEmXp", str(cookies_file))


def test_fetch_threads_media_maps_html_response_to_auth_error(tmp_path, monkeypatch):
    # An unauthenticated request gets served the SPA shell (HTML), not JSON -
    # confirmed live 2026-07-07, distinct from a clean HTTP error status.
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".threads.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tbad\n")

    class _HtmlResponse:
        def read(self):
            return b"<!DOCTYPE html><html>...</html>"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30: _HtmlResponse())
    with pytest.raises(ThreadsAuthError):
        threads_module.fetch_threads_media("https://www.threads.com/@someone/post/DWE8-rMEmXp", str(cookies_file))


def test_fetch_threads_media_parses_video_item(tmp_path, monkeypatch):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".threads.com\tTRUE\t/\tTRUE\t1799999999\tcsrftoken\tabc\n")

    payload = {
        "items": [{
            "code": "DWE8-rMEmXp",
            "caption": {"text": "Almost finished!\nmore text"},
            "video_versions": [{"url": "https://cdn/video.mp4", "width": 1280, "height": 706}],
            "image_versions2": {"candidates": [{"url": "https://cdn/thumb.jpg"}]},
        }],
    }

    class _JsonResponse:
        def read(self):
            return json.dumps(payload).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30: _JsonResponse())
    media = threads_module.fetch_threads_media("https://www.threads.com/@someone/post/DWE8-rMEmXp", str(cookies_file))
    assert media["title"] == "Almost finished!"
    assert media["items"] == [{
        "kind": "video", "url": "https://cdn/video.mp4", "thumbnail": "https://cdn/thumb.jpg",
        "width": 1280, "height": 706,
    }]


def test_fetch_threads_media_parses_image_item(tmp_path, monkeypatch):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".threads.com\tTRUE\t/\tTRUE\t1799999999\tcsrftoken\tabc\n")

    payload = {
        "items": [{
            "code": "DaTf9pqiaMW",
            "caption": {"text": "Signs everywhere"},
            "image_versions2": {"candidates": [{"url": "https://cdn/full.jpg", "width": 3024, "height": 4032}]},
        }],
    }

    class _JsonResponse:
        def read(self):
            return json.dumps(payload).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30: _JsonResponse())
    media = threads_module.fetch_threads_media("https://www.threads.com/@figma/post/DaTf9pqiaMW", str(cookies_file))
    assert media["items"] == [{
        "kind": "image", "url": "https://cdn/full.jpg", "thumbnail": "https://cdn/full.jpg",
        "width": 3024, "height": 4032,
    }]


def test_fetch_threads_media_any_returns_first_account_that_works(monkeypatch):
    calls = []

    def fake_fetch(url, cf):
        calls.append(cf)
        if cf == "/acctA.txt":
            raise ThreadsAuthError("Threads requires a logged-in session (cookies).")
        return {"title": "Post", "items": [{"kind": "video", "url": "http://cdn/v.mp4", "thumbnail": None}]}

    monkeypatch.setattr(threads_module, "fetch_threads_media", fake_fetch)
    media = threads_module.fetch_threads_media_any("https://www.threads.com/@someone/post/abc", ["/acctA.txt", "/acctB.txt"])
    assert media["title"] == "Post"
    assert calls == ["/acctA.txt", "/acctB.txt"]


def test_fetch_threads_media_any_raises_auth_error_when_all_unauthorized(monkeypatch):
    def always_auth(url, cf):
        raise ThreadsAuthError("Threads requires a logged-in session (cookies).")

    monkeypatch.setattr(threads_module, "fetch_threads_media", always_auth)
    with pytest.raises(ThreadsAuthError):
        threads_module.fetch_threads_media_any("https://www.threads.com/@someone/post/abc", ["/a.txt", "/b.txt"])
