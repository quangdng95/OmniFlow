"""LinkedIn image-post resolver.

yt-dlp's LinkedInIE only scrapes the <video> tag out of a post's page - it
raises "Unable to extract video" for an image-only post (confirmed live
2026-07-07). LinkedIn's public post pages server-render a plain og:image meta
tag for image posts though, with no authentication needed at all - confirmed
live against a real public LinkedIn image post. Native LinkedIn document/
slide-deck (PDF) posts are NOT handled here - no known resolver exists yet for
that post type (see MISTAKES.md); fetch_linkedin_image_post raises for one
since it has no og:image, distinct from a page missing the field entirely.
"""

import re
import urllib.request

LINKEDIN_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_OG_IMAGE_RE = re.compile(r'property="og:image"\s+content="([^"]+)"')
_OG_TITLE_RE = re.compile(r'property="og:title"\s+content="([^"]+)"')


class LinkedInUnsupportedPostError(Exception):
    """The post has no scrapable og:image - most likely a document/slide-deck
    post, which has no known resolver yet, or a private/removed post."""


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

    image_match = _OG_IMAGE_RE.search(html)
    if not image_match:
        raise LinkedInUnsupportedPostError(
            "No image found on this LinkedIn post - it may be a document/slide-deck post, "
            "which OmniFlow does not support yet."
        )
    image_url = image_match.group(1).replace("&amp;", "&")

    title_match = _OG_TITLE_RE.search(html)
    title = title_match.group(1).replace("&amp;", "&") if title_match else "LinkedIn Post"

    return {"title": title, "items": [{"kind": "image", "url": image_url, "thumbnail": image_url}]}
