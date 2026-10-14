"""X (Twitter) photo posts.

yt-dlp's Twitter extractor only handles a tweet that carries a video or a GIF; a tweet with just pictures fails
with "No video could be found" (found with real links on 2026-10-14). X's own embed endpoint,
cdn.syndication.twimg.com/tweet-result, answers for any public tweet without a login and lists its photos, so the
photos are read from there and downloaded in their original size. This module returns the same
{"title", "items": [{"kind", "url", "thumbnail"}]} shape the other resolvers return, so
instagram_check_response and the batch downloader work unchanged.
"""

import json
import re
import urllib.parse
import urllib.request

_TWEET_ID_RE = re.compile(r"/status(?:es)?/(\d+)")
_SYNDICATION = "https://cdn.syndication.twimg.com/tweet-result"
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"


class XPostError(Exception):
    """The tweet has no photos we can read (removed, protected, or video-only)."""


def tweet_id(url):
    match = _TWEET_ID_RE.search(urllib.parse.urlparse(url).path)
    return match.group(1) if match else None


def _token(tid):
    # The embed endpoint wants a token derived from the id: JavaScript's ((id / 1e15) * Math.PI).toString(36)
    # with the dot and the zeros removed.
    value = (int(tid) / 1e15) * 3.141592653589793
    whole = int(value)
    fraction = value - whole
    out = ""
    while whole:
        out = _DIGITS[whole % 36] + out
        whole //= 36
    out = (out or "0") + "."
    for _ in range(12):
        fraction *= 36
        digit = int(fraction)
        out += _DIGITS[digit]
        fraction -= digit
        if fraction == 0:
            break
    return out.replace(".", "").replace("0", "")


def _original(url):
    # https://pbs.twimg.com/media/<id>.jpg -> .../media/<id>?format=jpg&name=orig (the uncompressed original)
    base, _, ext = url.rpartition(".")
    if not base.startswith("https://pbs.twimg.com/media/") or not ext.isalnum():
        return url
    return f"{base}?format={ext}&name=orig"


def _clean_title(text, screen_name):
    text = re.sub(r"https?://\S+", "", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:80] or f"X post by @{screen_name or 'unknown'}"


def fetch_x_photo_post(url):
    tid = tweet_id(url)
    if not tid:
        raise XPostError("not a tweet link")
    request = urllib.request.Request(
        f"{_SYNDICATION}?id={tid}&lang=en&token={_token(tid)}", headers={"User-Agent": _UA, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
    except (OSError, ValueError) as error:
        raise XPostError(f"X embed endpoint unavailable: {type(error).__name__}") from None
    photos = [p for p in (data.get("photos") or []) if p.get("url")]
    if not photos:
        raise XPostError("tweet has no photos")
    screen_name = (data.get("user") or {}).get("screen_name")
    return {
        "title": _clean_title(data.get("text"), screen_name),
        "items": [{"kind": "image", "url": _original(p["url"]), "thumbnail": p["url"]} for p in photos],
    }


def try_photos(url):
    """The post's photos, or None when it has none (a video tweet) or X's endpoint cannot be reached."""
    try:
        return fetch_x_photo_post(url)
    except XPostError:
        return None
