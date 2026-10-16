"""Pinterest boards and pins.

yt-dlp reads only video pins (and fails on a private board), so boards and image pins use Pinterest's own web
API, the same JSON the website loads its grid from (`/resource/<Name>Resource/get/`). A PUBLIC board needs no login;
a PRIVATE ("secret") board is only visible to its owner, so it is read with the user's own Pinterest session
(`_pinterest_sess`), extracted from the browsers on this Mac exactly like Instagram's. Nothing is sent anywhere
except pinterest.com.

The API wants a browser-like TLS fingerprint and a few headers (`X-Pinterest-PWS-Handler` is the one that matters:
without it every call is "403 Invalid Resource Request"), so requests go through curl_cffi with Chrome
impersonation. It sometimes answers with an empty body: such a call is retried.

Returns the same {"title", "items": [{"kind", "url", "thumbnail", "title"}]} shape as the other resolvers, so
instagram_check_response and the batch downloader work unchanged.
"""

import json
import re
import time
import urllib.parse

from curl_cffi import requests as curl_requests

from backend import classify, config, cookies

ROOT = "https://www.pinterest.com"
_ACCEPT = "application/json, text/javascript, */*, q=0.01"
_PAGE_SIZE = 50
_RETRIES = 3
_MAX_PAGES = 400  # 400 x 50 = 20000 pins: well past any limit the Settings allow
SESSION_COOKIE = "_pinterest_sess"


class PinterestError(Exception):
    """The board or pin could not be read (changed API, network, nothing in it)."""


class PinterestAuthError(PinterestError):
    """Not visible without a login: a private board, or one that does not exist (Pinterest answers both the same)."""


class PinterestUnsupportedError(PinterestError):
    """A link that is not a board or a pin (a profile, a board section)."""


def _compact(obj):
    return json.dumps(obj, separators=(",", ":"))


def _cookie_rows(path):
    rows = {}
    try:
        lines = open(path, "r", errors="ignore").read().splitlines()
    except OSError:
        return rows
    for line in lines:
        if line.startswith("#HttpOnly_"):
            line = line[len("#HttpOnly_"):]
        elif line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 7 and "pinterest" in parts[0].lower():
            rows[parts[5]] = parts[6]
    return rows


def has_session(path):
    return bool(_cookie_rows(path).get(SESSION_COOKIE))


class _Api:
    """One browser-like session; `cookie_path` is the user's jar for a private board, None for a public one."""

    def __init__(self, cookie_path=None):
        self.http = curl_requests.Session(impersonate="chrome")
        self.csrf = ""
        if cookie_path:
            for name, value in _cookie_rows(cookie_path).items():
                self.http.cookies.set(name, value, domain=".pinterest.com")
                if name == "csrftoken":
                    self.csrf = value
        self.app_version = "unknown"
        try:
            page = self.http.get(ROOT + "/", headers={"Accept-Language": "en-US,en;q=0.9"}, timeout=30).text
            match = re.search(r'<script id="__PWS_DATA__"[^>]*>(.*?)</script>', page, re.S)
            if match:
                self.app_version = json.loads(match.group(1)).get("appVersion") or "unknown"
        except Exception:
            pass  # the version header is a courtesy; the call itself reports a real failure

    def call(self, resource, options, handler, source):
        headers = {
            "Accept": _ACCEPT,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": ROOT + source,
            "X-APP-VERSION": self.app_version,
            "X-Pinterest-AppState": "active",
            "X-Pinterest-PWS-Handler": handler,
            "X-Pinterest-Source-Url": source,
        }
        if self.csrf:
            headers["X-CSRFToken"] = self.csrf
        params = {"source_url": source, "data": _compact({"options": options, "context": {}})}
        last = None
        for attempt in range(_RETRIES):
            try:
                response = self.http.get(f"{ROOT}/resource/{resource}/get/", params=params, headers=headers, timeout=30)
                body = response.json()
                if isinstance(body, dict) and "resource_response" in body:
                    return body["resource_response"]
                last = PinterestError("unexpected Pinterest answer")
            except (ValueError, OSError) as error:  # an empty body (json) or a network hiccup
                last = PinterestError(f"Pinterest did not answer ({type(error).__name__})")
            except Exception as error:  # curl_cffi's own errors
                last = PinterestError(f"Pinterest request failed ({type(error).__name__})")
            time.sleep(1.0 + attempt)
        raise last


def _best_image(pin):
    images = pin.get("images") or {}
    orig = images.get("orig") or {}
    if orig.get("url"):
        return orig["url"]
    sized = [v for v in images.values() if isinstance(v, dict) and v.get("url")]
    return max(sized, key=lambda v: (v.get("width") or 0)) ["url"] if sized else None


def _thumbnail(pin):
    images = pin.get("images") or {}
    for key in ("474x", "236x", "orig"):
        if (images.get(key) or {}).get("url"):
            return images[key]["url"]
    return None


def _best_mp4(pin):
    video_list = ((pin.get("videos") or {}).get("video_list")) or {}
    mp4s = [v for v in video_list.values() if isinstance(v, dict) and (v.get("url") or "").split("?")[0].endswith(".mp4")]
    return max(mp4s, key=lambda v: (v.get("width") or 0) * (v.get("height") or 0))["url"] if mp4s else None


def _pin_title(pin):
    text = (pin.get("title") or pin.get("grid_title") or pin.get("description") or "").strip()
    return re.sub(r"\s+", " ", text)[:70]


def pin_to_item(pin):
    """One pin as a download item, or None for something that is not a plain image/video pin (an Idea pin, an ad)."""
    if not isinstance(pin, dict) or pin.get("type") != "pin" or not pin.get("id"):
        return None
    video = _best_mp4(pin)
    if video:
        return {"kind": "video", "url": video, "thumbnail": _thumbnail(pin), "title": _pin_title(pin)}
    image = _best_image(pin)
    if image:
        return {"kind": "image", "url": image, "thumbnail": _thumbnail(pin) or image, "title": _pin_title(pin)}
    return None


def _board_items(api, board_id, user, slug, limit):
    source = f"/{user}/{slug}/"
    items, bookmark, seen = [], None, set()
    for _ in range(_MAX_PAGES):
        options = {
            "board_id": board_id, "board_url": source, "field_set_key": "react_grid_pin", "filter_section_pins": True,
            "sort": "default", "layout": "default", "page_size": _PAGE_SIZE, "redux_normalize_feed": True,
        }
        if bookmark:
            options["bookmarks"] = [bookmark]
        response = api.call("BoardFeedResource", options, "www/[username]/[slug].js", source)
        for pin in response.get("data") or []:
            item = pin_to_item(pin)
            if item and pin["id"] not in seen:
                seen.add(pin["id"])
                items.append(item)
                if len(items) >= limit:
                    return items
        bookmark = response.get("bookmark")
        if not bookmark or bookmark == "-end-":
            break
    return items


def fetch_pinterest_board(user, slug, cookie_path=None, limit=10000):
    api = _Api(cookie_path)
    source = f"/{user}/{slug}/"
    response = api.call("BoardResource", {"username": user, "slug": slug, "field_set_key": "detailed"}, "www/[username]/[slug].js", source)
    board = response.get("data") or {}
    if not board.get("id"):
        # "Board not found." is also what a private board answers to anyone who is not its owner.
        raise PinterestAuthError("board not visible")
    items = _board_items(api, board["id"], user, slug, limit)
    if not items:
        raise PinterestError("the board has no pictures or videos")
    return {"title": (board.get("name") or slug).strip(), "items": items}


def fetch_pinterest_pin(pin_id, cookie_path=None):
    api = _Api(cookie_path)
    source = f"/pin/{pin_id}/"
    response = api.call("PinResource", {"id": pin_id, "field_set_key": "detailed"}, "www/pin/[id].js", source)
    pin = response.get("data") or {}
    if not pin.get("id"):
        raise PinterestAuthError("pin not visible")
    pin = {**pin, "type": pin.get("type") or "pin"}
    item = pin_to_item(pin)
    if not item:
        raise PinterestError("the pin has no picture or video")
    return {"title": _pin_title(pin) or "Pinterest pin", "items": [item]}


def _fetch(url, cookie_path, limit):
    target = classify.pinterest_target(url)
    if not target or target[0] == "unsupported":
        raise PinterestUnsupportedError("not a board or a pin")
    if target[0] == "pin":
        return fetch_pinterest_pin(target[1], cookie_path)
    return fetch_pinterest_board(target[1], target[2], cookie_path, limit)


def pinterest_cookiefile_candidates():
    # The synced/uploaded jar first when it carries a Pinterest login (the only source on the headless VM), then one
    # file per logged-in browser account (the Mac). Never a temp file for the manual one.
    candidates = []
    manual = config.get_cookies_path()
    if manual and has_session(manual):
        candidates.append(manual)
    candidates.extend(cookies.cookiefiles_from_browsers("pinterest.com", session_cookie=SESSION_COOKIE))
    return candidates


def fetch_pinterest_media(url, limit=10000, get_candidates=pinterest_cookiefile_candidates):
    """Public first (no cookies read, no Keychain prompt); only when Pinterest says "not found" is a login tried,
    one account after another. Raises PinterestAuthError when nothing could see it."""
    try:
        return _fetch(url, None, limit)
    except PinterestAuthError:
        pass
    candidates = get_candidates()
    try:
        last_error = PinterestAuthError("no Pinterest login found")
        for cookie_path in candidates:
            try:
                return _fetch(url, cookie_path, limit)
            except PinterestAuthError as error:
                last_error = error
            except PinterestError as error:
                last_error = error
        raise last_error
    finally:
        cookies._cleanup_temp_cookiefiles(candidates)


def friendly_error(error, lang=None, cloud=False):
    """The message a person should read for a failed Pinterest link (never the raw error)."""
    from backend import messages

    if isinstance(error, PinterestUnsupportedError):
        return messages.text("pinterest_unsupported", lang)
    if isinstance(error, PinterestAuthError):
        return messages.text("pinterest_cloud_private" if cloud else "pinterest_login", lang)
    return messages.text("pinterest_failed", lang)


def file_extension(item):
    """jpg/png/gif/webp for an image item (from its URL), mp4 for a video."""
    if item.get("kind") == "video":
        return "mp4"
    ext = urllib.parse.urlparse(item.get("url") or "").path.rsplit(".", 1)[-1].lower()
    return ext if ext in ("jpg", "jpeg", "png", "gif", "webp") else "jpg"
