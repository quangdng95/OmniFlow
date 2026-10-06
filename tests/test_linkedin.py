"""Unit tests for backend.linkedin - the LinkedIn image-post resolver.

yt-dlp's LinkedInIE handles video posts already; this resolver only covers
the image-post case it can't (confirmed live 2026-07-07 against a real
public LinkedIn image post - a plain og:image meta tag, no auth needed).
"""

import urllib.request

import pytest

from backend import linkedin as linkedin_module
from backend.linkedin import LinkedInUnsupportedPostError, fetch_linkedin_image_post


class _HtmlResponse:
    def __init__(self, html):
        self._html = html.encode()

    def read(self):
        return self._html

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_fetch_linkedin_image_post_parses_og_image_and_title(monkeypatch):
    html = (
        '<meta property="og:title" content="Figma MCP Revolutionizes Design-to-Code | LinkedIn">'
        '<meta property="og:image" content="https://media.licdn.com/dms/image/v2/abc/feedshare-image-high-res/0/123?e=1&amp;v=beta&amp;t=xyz">'
    )
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=20: _HtmlResponse(html))

    media = fetch_linkedin_image_post("https://www.linkedin.com/posts/someone_activity-123-abcd")
    assert media["title"] == "Figma MCP Revolutionizes Design-to-Code | LinkedIn"
    assert media["items"] == [{
        "kind": "image",
        "url": "https://media.licdn.com/dms/image/v2/abc/feedshare-image-high-res/0/123?e=1&v=beta&t=xyz",
        "thumbnail": "https://media.licdn.com/dms/image/v2/abc/feedshare-image-high-res/0/123?e=1&v=beta&t=xyz",
    }]


def test_fetch_linkedin_image_post_raises_when_no_og_image(monkeypatch):
    # A video post (og:video, no og:image) or a document/slide-deck post -
    # either way, unsupported by this resolver; the caller falls back to
    # yt-dlp for the video case and surfaces a friendly error otherwise.
    html = '<meta property="og:title" content="Some post">'
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=20: _HtmlResponse(html))

    with pytest.raises(LinkedInUnsupportedPostError):
        fetch_linkedin_image_post("https://www.linkedin.com/posts/someone_activity-123-abcd")


# ---- native document / slide-deck posts (2026-10-06) ----
#
# A LinkedIn "document" post (a PDF carousel) used to be mistaken for an image
# post: it also has an og:image, which is only the COVER, so the app reported
# "one image" and silently saved page 1. The page embeds the whole document in
# `data-native-document-config` -> doc.manifestUrl -> perResolutions[].imageManifestUrl
# -> {"pages": [image urls]} (confirmed live against a real 10-page deck).

import html as _html
import json as _json

MANIFEST = "https://media.licdn.com/dms/document/pl/v2/AAA/feedshare-document-master-manifest/x"
SMALL_IM = "https://media.licdn.com/dms/document/pl/v2/AAA/feedshare-document-images_160/x"
BIG_IM = "https://media.licdn.com/dms/document/pl/v2/AAA/feedshare-document-images_1920/x"
PAGES = [f"https://media.licdn.com/dms/image/v2/AAA/feedshare-document-images_1920/p{n}?e=1" for n in (1, 2, 3)]


def _document_html(manifest_url=MANIFEST, title="UX Metrics Flashcards"):
    cfg = {"doc": {"title": title, "totalPageCount": 3, "manifestUrl": manifest_url}}
    attr = _html.escape(_json.dumps(cfg), quote=True)
    return (
        '<meta property="og:title" content="8 UX Metrics | Someone posted on the topic | LinkedIn">'
        '<meta property="og:image" content="https://media.licdn.com/dms/image/v2/AAA/feedshare-document-cover-images_480/0/1">'
        f'<div data-native-document-config="{attr}"></div>'
    )


class _Router:
    """Serves a post page, a document manifest and image manifests by URL."""

    def __init__(self, routes):
        self.routes, self.requested = routes, []

    def __call__(self, req, timeout=20):
        url = req.full_url if hasattr(req, "full_url") else req
        self.requested.append(url)
        body = self.routes.get(url)
        if body is None:
            raise urllib.error.URLError("not routed: " + url)
        return _HtmlResponse(body if isinstance(body, str) else _json.dumps(body))


import urllib.error  # noqa: E402

POST = "https://www.linkedin.com/posts/someone_deck-ugcPost-1-abcd"
FULL_ROUTES = {
    POST: _document_html(),
    MANIFEST: {"perResolutions": [
        {"width": 135, "height": 168, "imageManifestUrl": SMALL_IM},
        {"width": 1545, "height": 1931, "imageManifestUrl": BIG_IM},
    ]},
    SMALL_IM: {"pages": ["https://media.licdn.com/dms/image/v2/AAA/small/p1"]},
    BIG_IM: {"pages": PAGES},
}


def test_a_document_post_returns_every_page_not_just_the_cover(monkeypatch):
    router = _Router(FULL_ROUTES)
    monkeypatch.setattr(urllib.request, "urlopen", router)

    media = fetch_linkedin_image_post(POST)

    assert media["title"] == "UX Metrics Flashcards"
    assert [item["url"] for item in media["items"]] == PAGES  # in page order
    assert all(item["kind"] == "image" and item["thumbnail"] == item["url"] for item in media["items"])
    # The sharpest resolution was used, the 135px thumbnails never fetched.
    assert BIG_IM in router.requested and SMALL_IM not in router.requested


def test_a_document_whose_pages_cannot_be_resolved_is_refused_not_downgraded_to_its_cover(monkeypatch):
    routes = dict(FULL_ROUTES)
    del routes[BIG_IM]
    monkeypatch.setattr(urllib.request, "urlopen", _Router(routes))
    with pytest.raises(LinkedInUnsupportedPostError):
        fetch_linkedin_image_post(POST)


def test_a_manifest_on_a_foreign_host_is_not_fetched(monkeypatch):
    evil = "http://169.254.169.254/latest/meta-data/"
    router = _Router({POST: _document_html(manifest_url=evil), evil: {"perResolutions": []}})
    monkeypatch.setattr(urllib.request, "urlopen", router)
    with pytest.raises(LinkedInUnsupportedPostError):
        fetch_linkedin_image_post(POST)
    assert evil not in router.requested


def test_page_urls_not_on_linkedins_cdn_are_dropped(monkeypatch):
    routes = dict(FULL_ROUTES)
    routes[BIG_IM] = {"pages": [PAGES[0], "http://169.254.169.254/x", PAGES[2]]}
    monkeypatch.setattr(urllib.request, "urlopen", _Router(routes))
    assert [i["url"] for i in fetch_linkedin_image_post(POST)["items"]] == [PAGES[0], PAGES[2]]


def test_a_plain_image_post_is_unaffected(monkeypatch):
    html = (
        '<meta property="og:title" content="A photo | LinkedIn">'
        '<meta property="og:image" content="https://media.licdn.com/dms/image/v2/abc/feedshare-image/0/1">'
    )
    monkeypatch.setattr(urllib.request, "urlopen", _Router({POST: html}))
    assert len(fetch_linkedin_image_post(POST)["items"]) == 1
