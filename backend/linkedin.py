"""LinkedIn image-post resolver.

yt-dlp's LinkedInIE only scrapes the <video> tag out of a post's page - it
raises "Unable to extract video" for an image-only post (confirmed live
2026-07-07). LinkedIn's public post pages server-render a plain og:image meta
tag for image posts though, with no authentication needed at all - confirmed
live against a real public LinkedIn image post. Native LinkedIn document/
slide-deck (PDF) posts are handled separately: their og:image is only the cover,
but the page embeds the whole document (see _document_pages), so every page is
returned as an image (2026-10-06, confirmed live against a real 10-page deck).
"""

import html as html_module
import json
import re
import urllib.parse
import urllib.request

LINKEDIN_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_OG_IMAGE_RE = re.compile(r'property="og:image"\s+content="([^"]+)"')
_OG_TITLE_RE = re.compile(r'property="og:title"\s+content="([^"]+)"')
_DOC_CONFIG_RE = re.compile(r'data-native-document-config="([^"]+)"')


class LinkedInUnsupportedPostError(Exception):
    """The post has nothing scrapable - a private/removed post, or a document
    post whose pages could not be resolved."""


def _on_linkedin_cdn(url):
    # The manifests and page images all live on LinkedIn's CDN; anything else in
    # the page's JSON is ignored rather than fetched (this runs on a server).
    parsed = urllib.parse.urlparse(url or "")
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (host == "licdn.com" or host.endswith(".licdn.com"))


def _fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": LINKEDIN_UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def _document_pages(html):
    # None when the post is not a native document; otherwise (title, [page urls]),
    # with an EMPTY list when it is a document but its pages could not be read.
    match = _DOC_CONFIG_RE.search(html)
    if not match:
        return None
    try:
        doc = json.loads(html_module.unescape(match.group(1))).get("doc") or {}
        manifest_url = doc.get("manifestUrl") or doc.get("url")
        if not _on_linkedin_cdn(manifest_url):
            return doc.get("title"), []
        resolutions = [r for r in (_fetch_json(manifest_url).get("perResolutions") or []) if _on_linkedin_cdn(r.get("imageManifestUrl"))]
        if not resolutions:
            return doc.get("title"), []
        sharpest = max(resolutions, key=lambda r: r.get("width") or 0)
        pages = [p for p in (_fetch_json(sharpest["imageManifestUrl"]).get("pages") or []) if _on_linkedin_cdn(p)]
        return doc.get("title"), pages
    except (OSError, ValueError, KeyError, TypeError):
        return None, []


def fetch_linkedin_image_post(url):
    # Returns {"title": str, "items": [{"kind": "image", "url", "thumbnail"}]}
    # - same shape as backend.instagram.fetch_instagram_media's single-item
    # case, so instagram.instagram_check_response can shape the /api/check
    # response unchanged.
    req = urllib.request.Request(url, headers={
        "User-Agent": LINKEDIN_UA,
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", "replace")

    document = _document_pages(html)
    if document is not None:
        doc_title, pages = document
        if not pages:
            # A document's og:image is only its cover: returning that would
            # silently hand the user page 1 of N as if it were the whole post.
            raise LinkedInUnsupportedPostError(
                "This LinkedIn document post's pages could not be read."
            )
        title_match = _OG_TITLE_RE.search(html)
        title = doc_title or (title_match.group(1).replace("&amp;", "&") if title_match else "LinkedIn Document")
        return {"title": title, "items": [{"kind": "image", "url": page, "thumbnail": page} for page in pages]}

    image_match = _OG_IMAGE_RE.search(html)
    if not image_match:
        raise LinkedInUnsupportedPostError(
            "No image found on this LinkedIn post - it may be a document/slide-deck post, "
            "which could not be read."
        )
    image_url = image_match.group(1).replace("&amp;", "&")

    title_match = _OG_TITLE_RE.search(html)
    title = title_match.group(1).replace("&amp;", "&") if title_match else "LinkedIn Post"

    return {"title": title, "items": [{"kind": "image", "url": image_url, "thumbnail": image_url}]}
