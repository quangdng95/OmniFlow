"""Unit tests for backend.tiktok - the TikTok Photo Mode resolver.

yt-dlp has no extractor at all for TikTok's Photo Mode posts (a slideshow of
images, `/photo/<id>` URLs) - confirmed live 2026-08-28 against yt-dlp
2026.8.19, which raises a bare "Unsupported URL". Scraping TikTok's own post
page doesn't work either (its bot-check withholds the item-data blob even
with curl_cffi Chrome impersonation), and TikTok's private API needs a
signed request with no public spec. tikwm.com - a free public API already
used by many open-source TikTok downloaders - resolves the post server-side
instead and hands back direct, presigned CDN image URLs; confirmed live
against a real TikTok Photo Mode post (4 images, no auth needed).
"""

import json
import urllib.request

import pytest

from backend.tiktok import TikTokPhotoError, fetch_tiktok_photo_post


class _JsonResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_fetch_tiktok_photo_post_parses_images_and_title(monkeypatch):
    payload = {
        "code": 0,
        "msg": "success",
        "data": {
            "title": "A slideshow post",
            "cover": "https://p16-sign.tiktokcdn.com/cover.jpeg",
            "images": [
                "https://p16-sign.tiktokcdn.com/img1.jpeg",
                "https://p16-sign.tiktokcdn.com/img2.jpeg",
            ],
        },
    }
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=20: _JsonResponse(payload))

    media = fetch_tiktok_photo_post("https://www.tiktok.com/@someone/photo/123")

    assert media["title"] == "A slideshow post"
    assert media["items"] == [
        {"kind": "image", "url": "https://p16-sign.tiktokcdn.com/img1.jpeg", "thumbnail": "https://p16-sign.tiktokcdn.com/cover.jpeg"},
        {"kind": "image", "url": "https://p16-sign.tiktokcdn.com/img2.jpeg", "thumbnail": "https://p16-sign.tiktokcdn.com/cover.jpeg"},
    ]


def test_fetch_tiktok_photo_post_raises_when_no_images(monkeypatch):
    # A normal TikTok video post has no "images" field - the caller falls
    # back to yt-dlp for that case, so this must raise, never return an
    # empty carousel.
    payload = {"code": 0, "msg": "success", "data": {"title": "A video post", "images": []}}
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=20: _JsonResponse(payload))

    with pytest.raises(TikTokPhotoError):
        fetch_tiktok_photo_post("https://www.tiktok.com/@someone/video/123")


def test_fetch_tiktok_photo_post_raises_when_api_reports_failure(monkeypatch):
    # tikwm.com's own error signal (post deleted/private, or a genuine
    # tikwm.com outage) - code != 0.
    payload = {"code": -1, "msg": "TikTok is not accessible now, please try again later"}
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=20: _JsonResponse(payload))

    with pytest.raises(TikTokPhotoError):
        fetch_tiktok_photo_post("https://www.tiktok.com/@someone/photo/123")
