"""Threads (threads.net / threads.com) post resolver.

Neither yt-dlp nor gallery-dl support Threads at all (verified live 2026-07-07 -
see MISTAKES.md, "Master Router spec asked for tools that don't exist"). Threads
shares Instagram's private REST API infrastructure under its own app id, so a
Threads post resolves through the exact same
https://www.threads.net/api/v1/media/<id>/info/ shape Instagram's post resolver
(backend/instagram.py) already uses - confirmed live against two real posts
(one video, one image). An unauthenticated request gets served the SPA shell
(HTML), not JSON, so this needs a live threads.com session the same way
Instagram's resolver needs a live instagram.com one - auto-extracted via
backend.cookies' browser_cookie3 plumbing.
"""

import json
import urllib.error
import urllib.request

from backend import classify, cookies

THREADS_APP_ID = "238260118697367"  # Threads' own web app id - distinct from Instagram's
THREADS_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
# Threads shortcodes decode with the same url-safe-base64 alphabet Instagram
# media ids use (confirmed live) - duplicated here rather than imported from
# backend.instagram so this module has no dependency on Instagram's resolver.
_B64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


class ThreadsAuthError(Exception):
    """Threads rejected the request for want of a valid logged-in session."""


def threads_media_id_from_shortcode(shortcode):
    media_id = 0
    for ch in shortcode:
        media_id = media_id * 64 + _B64_ALPHABET.index(ch)
    return media_id


def threads_cookiefile_candidates():
    # No manual "Threads Cookies" Settings field exists (unlike Instagram) -
    # auto-extracted browser cookies are the only source for now.
    return cookies.cookiefiles_from_browsers("threads.com")


def _parse_threads_cookies(cookies_path):
    # Mirrors backend.instagram._parse_instagram_cookies but matches the
    # threads.com cookie domain instead - hand-parsed (not MozillaCookieJar)
    # since it tolerates jars missing the Netscape magic header.
    parsed = {}
    try:
        with open(cookies_path, "r", errors="ignore") as f:
            lines = f.readlines()
    except OSError:
        return parsed
    for line in lines:
        line = line.rstrip("\n")
        if not line.strip():
            continue
        if line.startswith("#"):
            if not line.startswith("#HttpOnly_"):
                continue
            line = line[len("#HttpOnly_"):]
        fields = line.split("\t")
        if len(fields) < 7:
            continue
        domain, name, value = fields[0], fields[5], fields[6]
        if "threads.com" in domain:
            parsed[name] = value
    return parsed


def _threads_best_image(node):
    candidates = (node.get("image_versions2") or {}).get("candidates") or []
    return candidates[0] if candidates else None


def _threads_item(node):
    videos = node.get("video_versions") or []
    image = _threads_best_image(node)
    thumbnail = image.get("url") if image else None
    if videos:
        best = videos[0]
        return {
            "kind": "video",
            "url": best.get("url"),
            "thumbnail": thumbnail,
            "width": best.get("width"),
            "height": best.get("height"),
        }
    return {
        "kind": "image",
        "url": image.get("url") if image else None,
        "thumbnail": thumbnail,
        "width": image.get("width") if image else None,
        "height": image.get("height") if image else None,
    }


def _threads_title(media, shortcode):
    caption = media.get("caption")
    text = caption.get("text") if isinstance(caption, dict) else ""
    if text:
        first_line = text.strip().splitlines()[0].strip()
        if first_line:
            return first_line[:60]
    return shortcode


def fetch_threads_media(url, cookies_path):
    # Returns {"title": str, "items": [normalized item, ...]} - same shape as
    # backend.instagram.fetch_instagram_media, so instagram.instagram_check_response
    # (already platform-agnostic) can shape the /api/check response for either.
    shortcode = classify.threads_shortcode_from_url(url)
    if not shortcode:
        raise ThreadsAuthError("Not a Threads post URL (cookies).")
    media_id = threads_media_id_from_shortcode(shortcode)

    cookie_map = _parse_threads_cookies(cookies_path)
    cookie_header = "; ".join(f"{name}={value}" for name, value in cookie_map.items())
    api_url = f"https://www.threads.net/api/v1/media/{media_id}/info/"
    req = urllib.request.Request(
        api_url,
        headers={
            "User-Agent": THREADS_UA,
            "X-IG-App-ID": THREADS_APP_ID,
            "X-CSRFToken": cookie_map.get("csrftoken", ""),
            "Referer": "https://www.threads.com/",
            "Accept": "*/*",
            "Cookie": cookie_header,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", "replace")
        payload = json.loads(body)
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 401, 403):
            raise ThreadsAuthError("Threads requires a logged-in session (cookies).") from e
        raise
    except urllib.error.URLError as e:
        raise ThreadsAuthError("Could not reach Threads to fetch this post (cookies).") from e
    except json.JSONDecodeError as e:
        # An unauthenticated/expired session gets served the SPA shell (HTML),
        # not JSON - confirmed live, same failure mode as an Instagram login redirect.
        raise ThreadsAuthError("Threads requires a logged-in session (cookies).") from e

    items = payload.get("items") or []
    if not items:
        raise ThreadsAuthError("Threads sent an empty media response.")
    media = items[0]
    title = _threads_title(media, shortcode)
    nodes = media.get("carousel_media") or [media]
    return {"title": title, "items": [_threads_item(node) for node in nodes]}


def fetch_threads_media_any(url, cookiefiles):
    # Mirrors backend.instagram.fetch_instagram_media_any: try every candidate
    # account, surface the auth error only when all of them are unauthorized.
    last_auth_error = None
    last_error = None
    for cf in cookiefiles:
        try:
            return fetch_threads_media(url, cf)
        except ThreadsAuthError as e:
            last_auth_error = e
        except Exception as e:
            last_error = e
    if last_auth_error:
        raise last_auth_error
    if last_error:
        raise last_error
    raise ThreadsAuthError("Threads requires a logged-in session (cookies).")
