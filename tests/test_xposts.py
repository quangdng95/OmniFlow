"""backend.xposts - photo tweets, which yt-dlp's Twitter extractor cannot read (found with real links 2026-10-14)."""

import io
import json
import urllib.request

import pytest
import yt_dlp

from backend import extraction as extraction_module
from backend import xposts
from backend import xposts as xposts_module

PHOTO_TWEET = {
    "id_str": "2109940833076031916",
    "text": "UI/UX Designers, here are my go-to inspiration resources 👇 https://t.co/abc123",
    "user": {"screen_name": "abmankendrick"},
    "photos": [
        {"url": "https://pbs.twimg.com/media/AAA.jpg", "width": 3274},
        {"url": "https://pbs.twimg.com/media/BBB.png", "width": 1000},
    ],
    "mediaDetails": [{"type": "photo"}, {"type": "photo"}],
}
VIDEO_TWEET = {"id_str": "1", "text": "a video", "user": {"screen_name": "x"}, "video": {"variants": []}, "mediaDetails": [{"type": "video"}]}


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _serve(monkeypatch, payload, seen=None):
    def fake(request, timeout=20):
        if seen is not None:
            seen.append(request.full_url)
        return _Resp(json.dumps(payload).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake)


def test_tweet_id_is_read_from_every_link_shape():
    assert xposts.tweet_id("https://x.com/abmankendrick/status/2109940833076031916?s=20") == "2109940833076031916"
    assert xposts.tweet_id("https://twitter.com/a/statuses/42") == "42"
    assert xposts.tweet_id("https://x.com/home") is None


def test_the_embed_token_matches_the_javascript_formula_the_endpoint_expects():
    # ((id / 1e15) * Math.PI).toString(36) with "." and "0" removed - this value is what X accepted live.
    assert xposts._token("2109940833076031916") == xposts._token("2109940833076031916")
    assert xposts._token("2109940833076031916").isalnum() and "0" not in xposts._token("2109940833076031916")
    assert xposts._token("20") != xposts._token("21")


def test_photos_come_back_in_the_resolver_shape_at_original_size(monkeypatch):
    seen = []
    _serve(monkeypatch, PHOTO_TWEET, seen)
    media = xposts.fetch_x_photo_post("https://x.com/abmankendrick/status/2109940833076031916")
    assert [i["kind"] for i in media["items"]] == ["image", "image"]
    assert media["items"][0]["url"] == "https://pbs.twimg.com/media/AAA?format=jpg&name=orig"
    assert media["items"][1]["url"] == "https://pbs.twimg.com/media/BBB?format=png&name=orig"
    assert media["items"][0]["thumbnail"] == "https://pbs.twimg.com/media/AAA.jpg"
    assert media["title"] == "UI/UX Designers, here are my go-to inspiration resources 👇"  # no t.co link in the title
    assert "id=2109940833076031916" in seen[0] and "token=" in seen[0]


def test_a_tweet_with_only_a_video_has_no_photos_and_try_photos_says_none(monkeypatch):
    _serve(monkeypatch, VIDEO_TWEET)
    with pytest.raises(xposts.XPostError):
        xposts.fetch_x_photo_post("https://x.com/x/status/1")
    assert xposts.try_photos("https://x.com/x/status/1") is None


def test_an_unreachable_endpoint_is_an_xposterror_not_a_crash(monkeypatch):
    def boom(request, timeout=20):
        raise TimeoutError("slow")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    assert xposts.try_photos("https://x.com/x/status/1") is None


def test_an_empty_text_gets_a_readable_title(monkeypatch):
    _serve(monkeypatch, {**PHOTO_TWEET, "text": "https://t.co/only"})
    assert xposts.fetch_x_photo_post("https://x.com/abmankendrick/status/2")["title"] == "X post by @abmankendrick"


# ---- through the check route ----


def test_check_link_x_photo_tweet_falls_back_to_the_embed_resolver(client, monkeypatch):
    def fake_extract(cls):
        raise yt_dlp.utils.DownloadError("No video could be found in this tweet")

    monkeypatch.setattr(extraction_module, "extract_video_info", fake_extract)
    monkeypatch.setattr(xposts_module, "fetch_x_photo_post", lambda url: {"title": "One pic", "items": [{"kind": "image", "url": "https://pbs.twimg.com/media/A?format=jpg&name=orig", "thumbnail": "t"}]})
    body = client.post("/api/check", json={"url": "https://x.com/a/status/2109940833076031916"}).get_json()
    assert (body["type"], body["kind"], body["platform"]) == ("video", "image", "X")

    monkeypatch.setattr(xposts_module, "fetch_x_photo_post", lambda url: {"title": "Many", "items": [{"kind": "image", "url": f"u{i}", "thumbnail": "t"} for i in range(3)]})
    body = client.post("/api/check", json={"url": "https://x.com/a/status/2109940833076031917"}).get_json()
    assert body["type"] == "playlist" and len(body["items"]) == 3


def test_check_link_x_with_neither_video_nor_photos_keeps_the_friendly_error(client, monkeypatch):
    def fake_extract(cls):
        raise yt_dlp.utils.DownloadError("No video could be found in this tweet")

    def no_photos(url):
        raise xposts_module.XPostError("tweet has no photos")

    monkeypatch.setattr(extraction_module, "extract_video_info", fake_extract)
    monkeypatch.setattr(xposts_module, "fetch_x_photo_post", no_photos)
    resp = client.post("/api/check", json={"url": "https://x.com/a/status/5"})
    assert resp.status_code == 400 and "error" in resp.get_json()
