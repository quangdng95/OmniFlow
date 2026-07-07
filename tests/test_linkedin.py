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
