"""Persisted settings (config.json) + save-folder / cookies-file resolution."""

import json
import os
import sys

from backend import paths

# config.json must be writable at runtime: next to the source in dev, but the
# frozen .app bundle is read-only, so fall back to a per-user app-support dir.
if getattr(sys, "frozen", False):
    _config_dir = os.path.join(os.path.expanduser("~/Library/Application Support"), "OmniFlow")
    os.makedirs(_config_dir, exist_ok=True)
    CONFIG_FILE = os.path.join(_config_dir, "config.json")
else:
    CONFIG_FILE = os.path.join(paths.BASE_DIR, "config.json")


def resolve_save_dir(configured_path, fallback_dir=None):
    if os.path.isdir(configured_path) and os.access(configured_path, os.W_OK):
        return configured_path

    if fallback_dir is None:
        fallback_dir = os.path.expanduser("~/Downloads")
    try:
        os.makedirs(fallback_dir, exist_ok=True)
    except OSError:
        pass
    if os.path.isdir(fallback_dir) and os.access(fallback_dir, os.W_OK):
        return fallback_dir
    return None


def load_session():
    default_path = os.path.expanduser("~/Downloads")
    path_val = default_path
    cookies_path_val = ""
    browser_val = "chrome"
    playlist_limit_val = 100
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                path_val = data.get("path", default_path)
                cookies_path_val = data.get("cookies_path", "")
                browser_val = data.get("browser", "chrome")
                playlist_limit_val = data.get("playlist_limit", 100)
        except Exception:
            pass

    # Always prioritize the user's real Downloads folder: a configured path that
    # no longer exists/isn't writable (stale config from another machine, deleted
    # folder, etc.) is silently corrected back to it instead of persisting a dead path.
    if not (os.path.isdir(path_val) and os.access(path_val, os.W_OK)):
        path_val = default_path
        try:
            os.makedirs(default_path, exist_ok=True)
        except OSError:
            pass
        save_session(path_val, cookies_path_val, browser_val, playlist_limit_val)

    return {"path": path_val, "cookies_path": cookies_path_val, "browser": browser_val, "playlist_limit": playlist_limit_val}


def save_session(path_val, cookies_path_val="", browser_val="chrome", playlist_limit_val=100):
    with open(CONFIG_FILE, "w") as f:
        json.dump({
            "path": path_val,
            "cookies_path": cookies_path_val,
            "browser": browser_val,
            "playlist_limit": playlist_limit_val
        }, f)


def get_cookies_path():
    cookies_path = load_session().get("cookies_path")
    if cookies_path and os.path.isfile(cookies_path):
        return cookies_path
    return None


def cookies_file_has_instagram_session(path):
    # Soft diagnostic only - a false negative here never blocks the file from
    # being used as yt-dlp's real cookiefile, it only affects which hint is
    # shown to the user. Netscape cookie jar format: 7 tab-separated fields
    # per line (domain, includeSubdomains, path, secure, expiry, name, value);
    # lines starting with "#" are comments, except "#HttpOnly_"-prefixed lines,
    # which are real cookie rows with an HttpOnly marker baked into the domain
    # field by convention.
    try:
        with open(path, "r", errors="ignore") as f:
            lines = f.readlines()
    except OSError:
        return False
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
        domain, name = fields[0], fields[5]
        if "instagram.com" in domain and name == "sessionid":
            return True
    return False


def cookies_status_for(cookies_path):
    if not cookies_path or not os.path.isfile(cookies_path):
        return "none"
    return "valid" if cookies_file_has_instagram_session(cookies_path) else "no_session"
