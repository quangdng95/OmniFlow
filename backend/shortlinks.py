"""Expand a platform's own short link (lnkd.in, t.co, fb.me) to the real post
URL, before classify.classify_url() looks at it.

classify_url() is pure (no network), and the short hosts contain none of the
substrings it matches on, so a LinkedIn share link `lnkd.in/p/<id>` was treated
as the generic "Link" platform and failed in yt-dlp's generic extractor, though
the same post pasted as its full linkedin.com URL works (2026-10-06).

This runs on user-supplied URLs inside a server, so it is deliberately narrow:
  * only an allowlist of short-link hosts is ever contacted;
  * redirects are followed by hand, never automatically - lnkd.in lets anyone
    create a link to anything, and following those blindly would be an SSRF hole;
  * every hop must stay on a short-link host or land on a supported platform
    (classify.get_platform_info() != "Link"), with a plain http(s) scheme;
  * the destination page is never fetched - the last hop's Location is returned.

A Threads share link (threads.com/share/<id>) is expanded the same way. Threads
answers a real 302 to that link only for a non-browser User-Agent (yt-dlp's own
default and curl get it; a full Chrome UA gets a 200 JS app shell with no
redirect and no post data), so those requests use _SHARE_UA.
On any problem the original URL is returned unchanged.
"""

import time
import urllib.error
import urllib.parse
import urllib.request

from backend import classify

# Hosts that are a platform's OWN shortener. instagr.am, youtu.be, vt./vm.tiktok.com
# and xhslink.com are already recognised by classify (and resolved by their
# extractors), so they are not listed here.
SHORT_HOSTS = frozenset({"lnkd.in", "t.co", "fb.me", "pin.it"})
MAX_HOPS = 5
_TIMEOUT_SECONDS = 8
_CACHE_SECONDS = 3600
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# A UA without a "Chrome/…" token: this is what makes threads.com answer 302.
_SHARE_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
THREADS_HOSTS = frozenset({"threads.com", "www.threads.com", "threads.net", "www.threads.net"})

_cache = {}  # short url -> (expires_at, expanded url)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def _host(url):
    try:
        return (urllib.parse.urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def _is_short(url):
    return _host(url) in SHORT_HOSTS


def _is_threads_share(url):
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return False
    if (parsed.hostname or "").lower() not in THREADS_HOSTS:
        return False
    parts = [p for p in parsed.path.split("/") if p]
    return len(parts) == 2 and parts[0] == "share"


def _needs_expansion(url):
    return _is_short(url) or _is_threads_share(url)


def _fetch_location(url):
    # One request, redirects NOT followed; returns the Location header or None.
    ua = _SHARE_UA if _is_threads_share(url) else _UA
    request = urllib.request.Request(url, headers={"User-Agent": ua})
    try:
        with _opener.open(request, timeout=_TIMEOUT_SECONDS):
            return None  # answered directly, no redirect
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308):
            return e.headers.get("Location")
        return None


def _acceptable(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    return _needs_expansion(url) or classify.get_platform_info(url) != "Link"


def expand(url, fetch=None):
    url = (url or "").strip()
    if not url or not _needs_expansion(url):
        return url

    cached = _cache.get(url)
    if cached and cached[0] > time.time():
        return cached[1]

    fetch = fetch or _fetch_location
    current = url
    try:
        for _ in range(MAX_HOPS):
            if not _needs_expansion(current):
                break
            location = fetch(current)
            if not location:
                return url
            nxt = urllib.parse.urljoin(current, location)
            if not _acceptable(nxt):
                return url
            current = nxt
        else:
            return url  # still on a short host after MAX_HOPS: a loop, give up
    except (OSError, ValueError):
        return url

    _cache[url] = (time.time() + _CACHE_SECONDS, current)
    return current
