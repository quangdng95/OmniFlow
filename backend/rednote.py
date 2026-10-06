"""RedNote (Xiaohongshu) post resolver.

As of 2026-10-06 yt-dlp's XiaoHongShu extractor fails with "No video formats
found" for every note, for two separate reasons (confirmed live against a fresh
share link):
  1. RedNote redirects every unauthenticated note page to its login page, so a
     login session is required at all (the older fixtures only worked while it
     was still open);
  2. the page data renamed the stream groups from h264/h265/... to opaque keys
     (EF4, EF5, ...), which the extractor doesn't recognise even when logged in.

With a logged-in session the note page carries window.__INITIAL_STATE__ ->
note.noteDetailMap.<id>.note: a video note has video.media.stream.<group>[]
(masterUrl, an H.264+AAC mp4 on the rednotecdn CDN, downloadable with a plain
User-Agent), an image note has imageList[]. This module returns the same
{"title", "items": [{"kind", "url", "thumbnail"}]} shape the Instagram, Threads,
LinkedIn and TikTok resolvers return, so instagram_check_response and the
batch downloader work unchanged.

The session cookies are the user's own: the Mac auto-extracts them from the
browser (like Instagram) or the uploaded/synced cookies.txt carries them (cloud).
They are only ever sent to rednote.com / xiaohongshu.com, never shown in errors.
"""

import json
import re
import urllib.parse
import urllib.request

from backend import config, cookies

REDNOTE_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_BASE_DOMAINS = ("rednote.com", "xiaohongshu.com")
_STATE_RE = re.compile(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*</script>", re.S)
_UNDEFINED_RE = re.compile(r"(?<=[:\[,])\s*undefined\b")


class RedNoteError(Exception):
    """The note could not be resolved (removed, no media, page changed)."""


class RedNoteAuthError(RedNoteError):
    """RedNote sent us to its login page: no (valid) logged-in session."""


def _base_domain(host):
    host = (host or "").lower()
    for base in _BASE_DOMAINS:
        if host == base or host.endswith("." + base):
            return base
    return None


def _cookie_rows(cookies_path):
    # Netscape cookie rows as (domain-without-leading-dot, name, value).
    rows = []
    try:
        with open(cookies_path, "r", errors="ignore") as f:
            lines = f.readlines()
    except OSError:
        return rows
    for line in lines:
        line = line.rstrip("\n")
        if not line.strip():
            continue
        if line.startswith("#"):
            if not line.startswith("#HttpOnly_"):
                continue
            line = line[len("#HttpOnly_"):]
        fields = line.split("\t")
        if len(fields) >= 7:
            rows.append((fields[0].lstrip(".").lower(), fields[5], fields[6]))
    return rows


def _has_session(cookies_path):
    return any(name == "web_session" and _base_domain(domain) for domain, name, _ in _cookie_rows(cookies_path))


def _cookie_header(cookies_path, base):
    # Only this site's cookies: the jar is a whole browser's worth (Google,
    # Instagram...), none of which may leave for RedNote.
    return "; ".join(f"{name}={value}" for domain, name, value in _cookie_rows(cookies_path) if _base_domain(domain) == base)


def _other_host(url):
    parsed = urllib.parse.urlparse(url)
    base = _base_domain(parsed.hostname)
    swap = {"rednote.com": "www.xiaohongshu.com", "xiaohongshu.com": "www.rednote.com"}.get(base)
    return parsed._replace(netloc=swap).geturl() if swap else None


def _https(url):
    return "https://" + url[len("http://"):] if (url or "").startswith("http://") else url


def _parse_note(html, url):
    match = _STATE_RE.search(html)
    if not match:
        raise RedNoteError("RedNote page has no note data")
    try:
        state = json.loads(_UNDEFINED_RE.sub("null", match.group(1)))
        details = state["note"]["noteDetailMap"]
    except (ValueError, KeyError, TypeError):
        raise RedNoteError("RedNote page data was not readable") from None
    note_id = re.search(r"/(?:item|explore)/([0-9a-f]+)", urllib.parse.urlparse(url).path)
    entry = details.get(note_id.group(1)) if note_id else None
    entry = entry or next(iter(details.values()), None)
    note = (entry or {}).get("note")
    if not note:
        raise RedNoteError("RedNote note is missing from the page data")
    return note


def _items(note):
    images = note.get("imageList") or []
    cover = _https((images[0].get("urlDefault") if images else None) or None)
    if note.get("type") == "video":
        streams = (((note.get("video") or {}).get("media") or {}).get("stream")) or {}
        # The group keys are opaque now (EF4, ...); the first non-empty group is
        # the web player's default (H.264 in every note seen), the sharpest
        # entry of it is used.
        group = next((lst for lst in streams.values() if lst), None)
        if group:
            best = max(group, key=lambda s: ((s.get("height") or 0), (s.get("size") or 0)))
            if best.get("masterUrl"):
                return [{"kind": "video", "url": _https(best["masterUrl"]), "thumbnail": cover}]
        raise RedNoteError("RedNote video note has no downloadable stream")
    items = []
    for image in images:
        url = image.get("urlDefault") or ((image.get("infoList") or [{}])[-1].get("url"))
        if url:
            items.append({"kind": "image", "url": _https(url), "thumbnail": _https(url)})
    if not items:
        raise RedNoteError("RedNote note has no media")
    return items


def _fetch_page(url, cookies_path):
    base = _base_domain(urllib.parse.urlparse(url).hostname)
    headers = {"User-Agent": REDNOTE_UA, "Accept-Language": "en-US,en;q=0.9"}
    header = _cookie_header(cookies_path, base) if base else ""
    if header:
        headers["Cookie"] = header
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=25) as resp:
        html = resp.read().decode("utf-8", "replace")
        final = resp.geturl()
    if urllib.parse.urlparse(final).path.startswith("/login"):
        raise RedNoteAuthError("RedNote requires a logged-in session")
    return html, final


def fetch_rednote_post(url, cookies_path):
    # The same note is served on rednote.com and xiaohongshu.com, but a login
    # session is only valid on the domain it was created on - so if the given
    # host sends us to the login page, try the other one before giving up.
    last_error = None
    for candidate in (url, _other_host(url)):
        if not candidate:
            continue
        try:
            html, final = _fetch_page(candidate, cookies_path)
        except RedNoteAuthError as e:
            last_error = e
            continue
        note = _parse_note(html, final)
        title = (note.get("title") or (note.get("desc") or "")[:60]).strip() or "RedNote Post"
        return {"title": title, "items": _items(note)}
    raise last_error or RedNoteAuthError("RedNote requires a logged-in session")


def fetch_rednote_post_any(url, cookiefiles):
    # Try every candidate account; surface the auth error only when ALL of them
    # are logged out (mirrors fetch_threads_media_any).
    last_auth_error = last_error = None
    for cf in cookiefiles:
        try:
            return fetch_rednote_post(url, cf)
        except RedNoteAuthError as e:
            last_auth_error = e
        except Exception as e:
            last_error = e
    if last_auth_error:
        raise last_auth_error
    if last_error:
        raise last_error
    raise RedNoteAuthError("RedNote requires a logged-in session")


def rednote_cookiefile_candidates():
    # The uploaded/synced cookies.txt first when it carries a RedNote login
    # (the only possible source on the headless cloud VM), then one auto-
    # extracted file per logged-in browser account. Never a temp file for the
    # manual one, so _cleanup_temp_cookiefiles leaves it alone.
    candidates = []
    manual = config.get_cookies_path()
    if manual and _has_session(manual):
        candidates.append(manual)
    for domain in _BASE_DOMAINS:
        candidates.extend(cookies.cookiefiles_from_browsers(domain, session_cookie="web_session"))
    return candidates
