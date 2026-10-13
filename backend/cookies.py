"""Instagram cookie plumbing - manual cookies.txt + automatic browser extraction.

The auto-extracted temp cookiefiles carry a LIVE session token; every consumer
must hand them back to _cleanup_temp_cookiefiles() after use (prefix-guarded so
it never deletes the user's own manually-configured file).
"""

import http.cookiejar
import json
import os
import re
import shutil
import tempfile
import time

from backend import config, paths


# macOS user-data directories for the Chromium-family browsers. yt-dlp's
# --cookies-from-browser (and browser_cookie3) default to a browser's *Default*
# profile only - but a user who is logged into Instagram in "Profile 1" has no
# session in Default, so the default scan silently reads an account-less profile
# and "auto cookies" appears to fail. We enumerate the real profile folders on
# disk instead and try each exact one.
CHROMIUM_BROWSER_DIRS = {
    "chrome": "~/Library/Application Support/Google/Chrome",
    "brave": "~/Library/Application Support/BraveSoftware/Brave-Browser",
    "edge": "~/Library/Application Support/Microsoft Edge",
    "chromium": "~/Library/Application Support/Chromium",
    "vivaldi": "~/Library/Application Support/Vivaldi",
    "opera": "~/Library/Application Support/com.operasoftware.Opera",
    # Arc (Chromium-based, own folder; its cookies decrypt via browser_cookie3.arc).
    # Missing here, the desktop app found no Instagram/Threads/RedNote login for
    # anyone browsing in Arc (2026-10-06) although the cloud sync script, which
    # reads Arc directly, did.
    "arc": "~/Library/Application Support/Arc/User Data",
}


_CHROME_PROFILE_RE = re.compile(r"^(Default|Profile \d+)$")


def list_chrome_profiles():
    """Chrome profiles on this Mac that can hold a YouTube login, for Settings.

    Returns [{"id": "Default", "name": "Person 1"}, ...]. `name` is the display name
    Chrome shows for the profile (from its Local State file); the account email that
    file also holds is deliberately never read. Only profile folders that have a
    cookie database are listed. Never raises.
    """
    base = os.path.expanduser(CHROMIUM_BROWSER_DIRS["chrome"])
    try:
        folders = sorted(n for n in os.listdir(base) if _CHROME_PROFILE_RE.match(n))
    except OSError:
        return []
    names = {}
    try:
        with open(os.path.join(base, "Local State"), "r") as f:
            cache = json.load(f).get("profile", {}).get("info_cache", {})
        for folder, info in cache.items():
            if isinstance(info, dict) and isinstance(info.get("name"), str):
                names[folder] = info["name"]
    except (OSError, ValueError, AttributeError):
        pass
    profiles = []
    for folder in folders:
        if _profile_cookie_db(os.path.join(base, folder)):
            profiles.append({"id": folder, "name": names.get(folder) or folder})
    # "Default" first, then Profile 1, 2, ... in numeric order.
    profiles.sort(key=lambda p: (p["id"] != "Default", int(p["id"].split()[-1]) if p["id"] != "Default" else 0))
    return profiles


def _profile_cookie_db(profile_dir):
    # Newer Chrome moved the cookies DB to <profile>/Network/Cookies; older
    # builds keep it at <profile>/Cookies. Return whichever exists, else None.
    for rel in (os.path.join("Network", "Cookies"), "Cookies"):
        candidate = os.path.join(profile_dir, rel)
        if os.path.isfile(candidate):
            return candidate
    return None


def parse_cookies_from_file(cookies_path):
    cookies = {}
    if not cookies_path:
        return cookies
    try:
        cj = http.cookiejar.MozillaCookieJar(cookies_path)
        cj.load(ignore_discard=True, ignore_expires=True)
        for cookie in cj:
            cookies[cookie.name] = cookie.value
    except Exception as e:
        print(f"[debug] Failed to parse cookies from MozillaCookieJar: {e}", flush=True)
        # Fall back to manual parsing
        try:
            with open(cookies_path, "r", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 7:
                        name = parts[5]
                        value = parts[6]
                        cookies[name] = value
        except Exception as e2:
            print(f"[debug] Manual cookie parse failed: {e2}", flush=True)
    return cookies


def _write_cookies_txt(cookie_map, domain="instagram.com"):
    # Serialize a {name: value} cookie dict into a Netscape cookies.txt temp file
    # that both yt-dlp (cookiefile) and our own resolver/_parse_instagram_cookies
    # can read. Left for the OS to reap - the same accepted minor-orphan tradeoff
    # as the remote temp-dir download path.
    fd, path = tempfile.mkstemp(prefix="omniflow-cookies-", suffix=".txt")
    dot_domain = domain if domain.startswith(".") else "." + domain
    far_future = "2147483647"
    with os.fdopen(fd, "w") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for name, value in cookie_map.items():
            f.write("\t".join([dot_domain, "TRUE", "/", "TRUE", far_future, name, value]) + "\n")
    return path


def _read_domain_cookies(fn, domain, cookie_file=None):
    # Shared by both scan loops below. Returns (cookies matching `domain`,
    # total cookie count across ALL domains in the jar) - the total is what
    # lets a diagnostic message distinguish "browser_cookie3 read nothing at
    # all from this file" (points at a decrypt/access failure) from "it read
    # plenty, just nothing for this specific domain" (points at a genuinely
    # logged-out account or a stale/incomplete copy - see the WAL note below).
    jar = fn(cookie_file=cookie_file, domain_name=domain)
    all_cookies = list(jar)
    cookie_map = {c.name: c.value for c in all_cookies if domain in (c.domain or "")}
    return cookie_map, len(all_cookies)


def _describe_missing_sessionid(cookie_map, total_jar_count, domain):
    if cookie_map:
        return f"{len(cookie_map)} {domain} cookie(s) read, no sessionid among them ({sorted(cookie_map.keys())})"
    return f"0 {domain} cookie(s) read (jar had {total_jar_count} cookie(s) total for other domains)"


def _cleanup_temp_cookiefiles(paths):
    # Delete only the temp cookiefiles WE generated from browser cookies - they
    # carry a live session token, so they shouldn't linger in /tmp once used. The
    # "omniflow-cookies-" prefix guard means this never touches the user's own
    # manually-configured cookies.txt even if it's mixed into the same list.
    for p in paths or []:
        if p and os.path.basename(p).startswith("omniflow-cookies-"):
            try:
                os.remove(p)
            except OSError:
                pass


def cookiefiles_from_browsers(domain="instagram.com", session_cookie="sessionid"):
    # Auto-auth: use browser_cookie3 to read `domain` cookies from EVERY installed
    # browser/profile that carries a live-looking sessionid, writing each account
    # to its own cookies.txt. To bypass SQLite locks when the browsers are running,
    # we copy the cookie database to a temporary location before reading it.
    try:
        import browser_cookie3
        import shutil
        import tempfile
    except ImportError:
        return []

    # Enumerate all target cookies database paths we want to read
    # Each entry is a tuple: (browser_name, profile_label, source_db_path). The
    # profile_label (e.g. "Default"/"Profile 1") only exists so a diagnostic
    # message can say WHICH profile came up empty - os.path.basename(src_path)
    # alone is always just "Cookies"/"Network" for every Chromium profile, so
    # without this a multi-profile machine's log can't tell them apart.
    db_paths = []

    # 1. Chromium family profiles
    for browser, base in CHROMIUM_BROWSER_DIRS.items():
        base_dir = os.path.expanduser(base)
        if not os.path.isdir(base_dir):
            continue
        # For Opera, cookies are sometimes stored directly in the base dir
        if browser == "opera":
            candidate = os.path.join(base_dir, "Cookies")
            if os.path.isfile(candidate):
                db_paths.append(("opera", "(root)", candidate))
        try:
            entries = os.listdir(base_dir)
        except OSError:
            continue
        for name in entries:
            if name != "Default" and not name.startswith("Profile "):
                continue
            profile_dir = os.path.join(base_dir, name)
            if os.path.isdir(profile_dir):
                db_file = _profile_cookie_db(profile_dir)
                if db_file:
                    db_paths.append((browser, name, db_file))

    # 2. Firefox profiles
    firefox_base = os.path.expanduser("~/Library/Application Support/Firefox/Profiles")
    if os.path.isdir(firefox_base):
        try:
            for name in os.listdir(firefox_base):
                p_path = os.path.join(firefox_base, name)
                if os.path.isdir(p_path):
                    candidate = os.path.join(p_path, "cookies.sqlite")
                    if os.path.isfile(candidate):
                        db_paths.append(("firefox", name, candidate))
        except OSError:
            pass

    # 3. Safari (special case: binarycookies file, not SQLite database, but let's list it so we can try loading it)
    safari_cookie_file = os.path.expanduser("~/Library/Containers/com.apple.Safari/Data/Library/Cookies/Cookies.binarycookies")
    if os.path.isfile(safari_cookie_file):
        db_paths.append(("safari", "(root)", safari_cookie_file))

    cookiefiles = []
    seen_sessions = set()
    # Every failure below used to be silently discarded, so a machine where
    # cookie extraction never worked (wrong Keychain state, browser_cookie3
    # version mismatch, a locked/corrupt cookie DB, ...) left zero trace
    # anywhere - "no session found" with no way to tell why. We only care
    # about the *reason* when the whole function ends up empty-handed (the
    # common case, one attempt per browser succeeding, is not worth logging),
    # so failures are collected here and reported as one consolidated
    # diagnostic entry at the end instead of spamming the log per attempt.
    errors = []

    for browser, profile_label, src_path in db_paths:
        temp_path = None
        try:
            # Copy file to temp location to bypass SQLite database locks.
            # Chrome's cookies DB runs in SQLite WAL mode, so a recently
            # written cookie (e.g. a session set by a login done minutes ago)
            # can still be sitting in the "-wal" sidecar rather than the main
            # file until Chrome next checkpoints it - copying only the main
            # file can silently yield a snapshot that's missing exactly the
            # cookie we're looking for. Copy the sidecars too when present so
            # sqlite3 can merge them on open, same as it would for the live
            # file.
            fd, temp_path = tempfile.mkstemp(prefix=f"omniflow-raw-{browser}-", suffix=".db")
            os.close(fd)
            shutil.copy2(src_path, temp_path)
            for suffix in ("-wal", "-shm"):
                sidecar = src_path + suffix
                if os.path.isfile(sidecar):
                    try:
                        shutil.copy2(sidecar, temp_path + suffix)
                    except OSError:
                        pass

            fn = getattr(browser_cookie3, browser, None)
            if not fn:
                continue

            # browser_cookie3 decrypts the macOS Keychain "Chrome Safe Storage" key itself
            # - a wholly separate implementation from yt-dlp's --cookies-from-browser.
            cookie_map, total = _read_domain_cookies(fn, domain, cookie_file=temp_path)
            session = cookie_map.get(session_cookie)
            if session and session not in seen_sessions:
                seen_sessions.add(session)
                cookiefiles.append(_write_cookies_txt(cookie_map, domain))
            elif not session:
                errors.append(f"{browser}/{profile_label}: {_describe_missing_sessionid(cookie_map, total, domain)}")
        except Exception as e:
            errors.append(f"{browser}/{profile_label}: {e!r}")
        finally:
            for suffix in ("", "-wal", "-shm"):
                p = temp_path + suffix if temp_path else None
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass

    # Fallback to browser defaults if no profiles could be read or to cover
    # other setups. Unlike the loop above, this reads the browser's LIVE
    # default-profile file directly (no manual copy at all) - so if this also
    # comes up with 0 cookies for the domain, that rules out the WAL/copy
    # explanation entirely and points at decrypt/access failure instead.
    for name in ("chrome", "brave", "edge", "chromium", "vivaldi", "opera", "safari", "firefox"):
        try:
            fn = getattr(browser_cookie3, name, None)
            if fn:
                cookie_map, total = _read_domain_cookies(fn, domain)
                session = cookie_map.get(session_cookie)
                if session and session not in seen_sessions:
                    seen_sessions.add(session)
                    cookiefiles.append(_write_cookies_txt(cookie_map, domain))
                elif not session:
                    errors.append(f"{name}/live-default: {_describe_missing_sessionid(cookie_map, total, domain)}")
        except Exception as e:
            errors.append(f"{name} (default profile): {e!r}")

    if not cookiefiles:
        detail = "; ".join(errors) if errors else f"{len(db_paths)} profile(s) scanned, none had a {domain} sessionid"
        paths.log_exception(
            f"cookiefiles_from_browsers(domain={domain!r}): extracted 0 sessions",
            RuntimeError(detail),
        )

    return cookiefiles


def instagram_cookiefile_candidates():
    # Return manual Settings file if valid, else fallback to auto-extracted browser cookies.
    # This allows public Instagram carousels and images to fetch session cookies automatically.
    candidates = []
    manual = config.get_cookies_path()
    if manual and config.cookies_status_for(manual) == "valid":
        candidates.append(manual)
    candidates.extend(cookiefiles_from_browsers("instagram.com"))
    return candidates


# ---------------------------------------------------------------------------
# YouTube: browser cookies as a last resort (local backend only)
# ---------------------------------------------------------------------------

# Off unless backend/app.py (the local server) turns it on. remote_web never
# imports backend.app, so the cloud VM can never read a browser's cookies, even
# if a youtube_cookie_source is present in its config.
BROWSER_COOKIES_ALLOWED = False

# Only youtube.com is read: it carries the login cookies yt-dlp needs (verified
# live); no other domain is ever touched.
YOUTUBE_COOKIE_DOMAIN = "youtube.com"
_STALE_TEMP_SECONDS = 3600
_YOUTUBE_AUTH_MARKERS = ("not a bot", "sign in to confirm", "login required")


class YouTubeCookieAccessError(Exception):
    """Reading the browser's YouTube cookies failed (typically macOS Keychain
    access was denied). Carries no cookie data, only a fixed explanation."""


def is_youtube_url(url):
    lower = (url or "").lower()
    return "youtube.com" in lower or "youtu.be" in lower


def is_youtube_auth_error(error):
    # The login / anti-bot group only. Private, members-only, region-blocked or
    # deleted videos are NOT here: a login would not change the outcome.
    lower = str(error).lower()
    return any(marker in lower for marker in _YOUTUBE_AUTH_MARKERS)


def sweep_stale_temp_cookiefiles():
    # Remove cookie temp files a crashed/killed earlier run left behind. Only our
    # own prefixes, only in the temp dir, only when older than an hour (so a file
    # a concurrent request is using right now is never touched). Returns paths.
    removed = []
    tmp = tempfile.gettempdir()
    try:
        names = os.listdir(tmp)
    except OSError:
        return removed
    now = time.time()
    for name in names:
        if not (name.startswith("omniflow-cookies-") or name.startswith("omniflow-raw-chrome-")):
            continue
        path = os.path.join(tmp, name)
        try:
            if os.path.isfile(path) and now - os.path.getmtime(path) > _STALE_TEMP_SECONDS:
                os.remove(path)
                removed.append(path)
        except OSError:
            pass
    return removed


def _write_youtube_cookies_txt(jar_cookies):
    # Netscape file with each cookie's own domain/path/secure/expiry (mkstemp is
    # 0600). Only cookies whose domain is youtube.com or a subdomain are written.
    fd, path = tempfile.mkstemp(prefix="omniflow-cookies-", suffix=".txt")
    far_future = "2147483647"
    try:
        with os.fdopen(fd, "w") as f:
            f.write("# Netscape HTTP Cookie File\n")
            for c in jar_cookies:
                domain = (c.domain or "").lstrip(".")
                if domain != YOUTUBE_COOKIE_DOMAIN and not domain.endswith("." + YOUTUBE_COOKIE_DOMAIN):
                    continue
                f.write("\t".join([
                    "." + domain,
                    "TRUE",
                    c.path or "/",
                    "TRUE" if c.secure else "FALSE",
                    str(int(c.expires)) if c.expires else far_future,
                    c.name,
                    c.value,
                ]) + "\n")
    except BaseException:
        _cleanup_temp_cookiefiles([path])
        raise
    return path


def youtube_browser_cookiefile():
    # Returns a temp cookies.txt with the configured Chrome profile's YouTube
    # cookies (caller deletes it), or None when nothing is configured, the
    # profile has no YouTube login, or the guard is off. Raises
    # YouTubeCookieAccessError when the read itself fails.
    if not BROWSER_COOKIES_ALLOWED:
        return None
    source = config.get_youtube_cookie_source()
    if not source:
        return None
    browser, profile = source
    sweep_stale_temp_cookiefiles()
    profile_dir = os.path.join(os.path.expanduser(CHROMIUM_BROWSER_DIRS[browser]), profile)
    db_file = _profile_cookie_db(profile_dir)
    if not db_file:
        return None
    temp_db = None
    try:
        import browser_cookie3

        fd, temp_db = tempfile.mkstemp(prefix="omniflow-raw-chrome-", suffix=".db")
        os.close(fd)
        shutil.copy2(db_file, temp_db)
        for suffix in ("-wal", "-shm"):
            if os.path.isfile(db_file + suffix):
                shutil.copy2(db_file + suffix, temp_db + suffix)
        jar = browser_cookie3.chrome(cookie_file=temp_db, domain_name=YOUTUBE_COOKIE_DOMAIN)
        found = list(jar)
        if not found:
            return None
        return _write_youtube_cookies_txt(found)
    except Exception as e:
        # Deliberately drops the original message: it can name keychain items and
        # must never reach logs or the UI. The type alone is enough to debug.
        raise YouTubeCookieAccessError(type(e).__name__) from None
    finally:
        for suffix in ("", "-wal", "-shm"):
            if temp_db and os.path.exists(temp_db + suffix):
                try:
                    os.remove(temp_db + suffix)
                except OSError:
                    pass


def run_with_youtube_cookie_fallback(url, manual_path, attempt):
    # attempt(cookiefile_or_None) does one extraction/download. Order: the manual
    # cookies file when there is one (used as-is, never second-guessed); else no
    # cookies; and only if YouTube answers with a login / anti-bot error, ONE
    # retry with the configured browser profile's cookies.
    try:
        return attempt(manual_path)
    except Exception as first_error:
        if (
            manual_path
            or not BROWSER_COOKIES_ALLOWED
            or not is_youtube_url(url)
            or not is_youtube_auth_error(first_error)
        ):
            raise
        error = first_error
    cookiefile = youtube_browser_cookiefile()
    if not cookiefile:
        raise error
    try:
        return attempt(cookiefile)
    finally:
        _cleanup_temp_cookiefiles([cookiefile])
