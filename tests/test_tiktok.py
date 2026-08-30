"""Unit tests for backend.tiktok - the tikwm.com-backed TikTok resolver.

yt-dlp has no extractor at all for TikTok's Photo Mode posts (a slideshow of
images, `/photo/<id>` URLs) - confirmed live 2026-08-28 against yt-dlp
2026.8.19, which raises a bare "Unsupported URL". As of 2026-08-30, yt-dlp's
own TikTok VIDEO extractor is *also* broken for every normal video post
(`Unable to extract universal data for rehydration` - a known, currently
open upstream issue, yt-dlp/yt-dlp#16199, unresolved since March 2026),
confirmed live against 4 distinct real videos even with a real logged-in
browser session's cookies supplied. tikwm.com - a free public API already
used by many open-source TikTok downloaders - resolves a post server-side
(video OR photo) and hands back direct, presigned CDN media URLs; confirmed
live against both a real Photo Mode post (4 images) and 4 distinct real
video posts (all 4/4 succeeded with a working, watermark-free CDN URL).
"""

import json
import urllib.request

import pytest

from backend.tiktok import TikTokResolverError, fetch_tiktok_post


class _JsonResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_fetch_tiktok_post_parses_a_photo_mode_slideshow(monkeypatch):
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

    media = fetch_tiktok_post("https://www.tiktok.com/@someone/photo/123")

    assert media["title"] == "A slideshow post"
    assert media["items"] == [
        {"kind": "image", "url": "https://p16-sign.tiktokcdn.com/img1.jpeg", "thumbnail": "https://p16-sign.tiktokcdn.com/cover.jpeg"},
        {"kind": "image", "url": "https://p16-sign.tiktokcdn.com/img2.jpeg", "thumbnail": "https://p16-sign.tiktokcdn.com/cover.jpeg"},
    ]


def test_fetch_tiktok_post_parses_a_normal_video(monkeypatch):
    # No "images" field at all (or an empty one) but a "play" URL means a
    # normal video post - this is the new case as of 2026-08-30: yt-dlp's
    # own TikTok video extractor currently fails on every real video
    # (confirmed live), so this resolver is now the fallback for BOTH
    # TikTok shapes, not just Photo Mode.
    payload = {
        "code": 0,
        "msg": "success",
        "data": {
            "title": "A normal video post #fyp",
            "cover": "https://p19-common-sign.tiktokcdn-us.com/cover.jpeg",
            "images": [],
            "play": "https://v16m.tiktokcdn-us.com/video.mp4",
            "duration": 12,
        },
    }
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=20: _JsonResponse(payload))

    media = fetch_tiktok_post("https://www.tiktok.com/@someone/video/123")

    assert media["title"] == "A normal video post #fyp"
    assert media["items"] == [
        {"kind": "video", "url": "https://v16m.tiktokcdn-us.com/video.mp4", "thumbnail": "https://p19-common-sign.tiktokcdn-us.com/cover.jpeg"},
    ]


def test_fetch_tiktok_post_prefers_images_over_play_when_both_present(monkeypatch):
    # Some Photo Mode posts also carry a "play" field (a bundled slideshow
    # video with the soundtrack) alongside "images" - the images (the
    # actual Photo Mode content) must win, matching this resolver's
    # existing, already-shipped Photo Mode behavior.
    payload = {
        "code": 0,
        "msg": "success",
        "data": {
            "title": "A slideshow with a bundled video too",
            "cover": "https://p16-sign.tiktokcdn.com/cover.jpeg",
            "images": ["https://p16-sign.tiktokcdn.com/img1.jpeg"],
            "play": "https://v16m.tiktokcdn-us.com/bundled-slideshow.mp4",
        },
    }
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=20: _JsonResponse(payload))

    media = fetch_tiktok_post("https://www.tiktok.com/@someone/photo/123")

    assert media["items"] == [
        {"kind": "image", "url": "https://p16-sign.tiktokcdn.com/img1.jpeg", "thumbnail": "https://p16-sign.tiktokcdn.com/cover.jpeg"},
    ]


def test_fetch_tiktok_post_raises_when_neither_images_nor_play(monkeypatch):
    # tikwm.com resolved the post but has nothing downloadable at all - a
    # genuinely unresolvable post, not a caller error.
    payload = {"code": 0, "msg": "success", "data": {"title": "Empty post", "images": [], "play": ""}}
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=20: _JsonResponse(payload))

    with pytest.raises(TikTokResolverError):
        fetch_tiktok_post("https://www.tiktok.com/@someone/video/123")


def test_fetch_tiktok_post_raises_when_api_reports_failure(monkeypatch):
    # tikwm.com's own error signal (post deleted/private, or a genuine
    # tikwm.com outage) - code != 0, and not the rate-limit case handled
    # separately below.
    payload = {"code": -1, "msg": "TikTok is not accessible now, please try again later"}
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=20: _JsonResponse(payload))

    with pytest.raises(TikTokResolverError):
        fetch_tiktok_post("https://www.tiktok.com/@someone/photo/123")


def test_fetch_tiktok_post_retries_once_on_rate_limit_then_succeeds(monkeypatch):
    # tikwm.com's free tier caps at 1 request/second (confirmed live,
    # 2026-08-30) - a burst of requests (e.g. several checks in quick
    # succession) can transiently hit this. Retrying once after a brief
    # pause turns a real, common failure mode into a success instead of
    # bubbling a confusing rate-limit message up to the user.
    limited_payload = {"code": -1, "msg": "Free Api Limit: 1 request/second."}
    ok_payload = {
        "code": 0, "msg": "success",
        "data": {"title": "Retried ok", "images": [], "play": "https://v16m.tiktokcdn-us.com/video.mp4"},
    }
    responses = [_JsonResponse(limited_payload), _JsonResponse(ok_payload)]
    calls = {"count": 0}

    def fake_urlopen(req, timeout=20):
        calls["count"] += 1
        return responses.pop(0)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    sleeps = []
    monkeypatch.setattr("backend.tiktok.time.sleep", lambda s: sleeps.append(s))

    media = fetch_tiktok_post("https://www.tiktok.com/@someone/video/123")

    assert media["title"] == "Retried ok"
    assert calls["count"] == 2
    assert len(sleeps) == 1


def test_fetch_tiktok_post_gives_up_after_repeated_rate_limiting(monkeypatch):
    limited_payload = {"code": -1, "msg": "Free Api Limit: 1 request/second."}
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=20: _JsonResponse(limited_payload))
    monkeypatch.setattr("backend.tiktok.time.sleep", lambda s: None)

    with pytest.raises(TikTokResolverError):
        fetch_tiktok_post("https://www.tiktok.com/@someone/video/123")
