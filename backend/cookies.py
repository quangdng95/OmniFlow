"""Instagram cookie plumbing - manual cookies.txt + automatic browser extraction.

The auto-extracted temp cookiefiles carry a LIVE session token; every consumer
must hand them back to _cleanup_temp_cookiefiles() after use (prefix-guarded so
it never deletes the user's own manually-configured file).
"""

import http.cookiejar
import os
import tempfile

from backend import config


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
}


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


def cookiefiles_from_browsers(domain="instagram.com"):
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
    # Each entry is a tuple: (browser_name, source_db_path)
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
                db_paths.append(("opera", candidate))
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
                    db_paths.append((browser, db_file))

    # 2. Firefox profiles
    firefox_base = os.path.expanduser("~/Library/Application Support/Firefox/Profiles")
    if os.path.isdir(firefox_base):
        try:
            for name in os.listdir(firefox_base):
                p_path = os.path.join(firefox_base, name)
                if os.path.isdir(p_path):
                    candidate = os.path.join(p_path, "cookies.sqlite")
                    if os.path.isfile(candidate):
                        db_paths.append(("firefox", candidate))
        except OSError:
            pass

    # 3. Safari (special case: binarycookies file, not SQLite database, but let's list it so we can try loading it)
    safari_cookie_file = os.path.expanduser("~/Library/Containers/com.apple.Safari/Data/Library/Cookies/Cookies.binarycookies")
    if os.path.isfile(safari_cookie_file):
        db_paths.append(("safari", safari_cookie_file))

    cookiefiles = []
    seen_sessions = set()

    for browser, src_path in db_paths:
        temp_path = None
        try:
            # Copy file to temp location to bypass SQLite database locks
            fd, temp_path = tempfile.mkstemp(prefix=f"omniflow-raw-{browser}-", suffix=".db")
            os.close(fd)
            shutil.copy2(src_path, temp_path)
            
            fn = getattr(browser_cookie3, browser, None)
            if not fn:
                continue
                
            # browser_cookie3 decrypts the macOS Keychain "Chrome Safe Storage" key itself
            # - a wholly separate implementation from yt-dlp's --cookies-from-browser.
            jar = fn(cookie_file=temp_path, domain_name=domain)
            cookie_map = {c.name: c.value for c in jar if domain in (c.domain or "")}
            session = cookie_map.get("sessionid")
            if session and session not in seen_sessions:
                seen_sessions.add(session)
                cookiefiles.append(_write_cookies_txt(cookie_map, domain))
        except Exception as e:
            # Gracefully ignore failures for specific profiles/browsers
            pass
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    # Fallback to browser defaults if no profiles could be read or to cover other setups
    for name in ("chrome", "brave", "edge", "chromium", "vivaldi", "opera", "safari", "firefox"):
        try:
            fn = getattr(browser_cookie3, name, None)
            if fn:
                jar = fn(domain_name=domain)
                cookie_map = {c.name: c.value for c in jar if domain in (c.domain or "")}
                session = cookie_map.get("sessionid")
                if session and session not in seen_sessions:
                    seen_sessions.add(session)
                    cookiefiles.append(_write_cookies_txt(cookie_map, domain))
        except Exception:
            pass

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
