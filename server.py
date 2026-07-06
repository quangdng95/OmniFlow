import os, sys, json, re, subprocess, tempfile, threading, time, uuid, shutil
import urllib.request, urllib.error, urllib.parse, http.cookiejar, requests
from concurrent.futures import ThreadPoolExecutor
import yt_dlp
import instaloader
from flask import Flask, request, jsonify, send_from_directory, send_file, after_this_request

from backend import classify, paths

# config.json must be writable at runtime: next to the source in dev, but the
# frozen .app bundle is read-only, so fall back to a per-user app-support dir.
if getattr(sys, "frozen", False):
    _config_dir = os.path.join(os.path.expanduser("~/Library/Application Support"), "OmniFlow")
    os.makedirs(_config_dir, exist_ok=True)
    CONFIG_FILE = os.path.join(_config_dir, "config.json")
else:
    CONFIG_FILE = os.path.join(paths.BASE_DIR, "config.json")

app = Flask(__name__, static_folder=paths.WEB_DIR, static_url_path="")

jobs = {}

LOCAL_HOSTNAMES = {"127.0.0.1", "localhost", "::1"}


def is_local_request():
    # request.host is the Host header the browser actually addressed - unlike
    # request.remote_addr, this stays correct even when the server is exposed
    # through a tunnel (ngrok/Cloudflare Tunnel): the tunnel daemon forwards
    # to 127.0.0.1 locally, so remote_addr would misleadingly always look
    # local. A loopback hostname, on the other hand, is only reachable by a
    # browser running on this same machine - desktop_app.py's pywebview
    # window always navigates to http://127.0.0.1:{PORT}, so it naturally
    # lands here regardless of this check.
    host = (request.host or "").lower()
    if host.startswith("["):
        # bracketed IPv6 host:port form, e.g. "[::1]:5001" - a plain split(":")
        # would wrongly grab "[" as the hostname
        hostname = host.split("]")[0].lstrip("[")
    else:
        hostname = host.split(":")[0]
    return hostname in LOCAL_HOSTNAMES


def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()


def get_unique_filename(directory, filename, extension):
    base_name = sanitize_filename(filename)
    full_path = os.path.join(directory, f"{base_name}.{extension}")
    counter = 1
    while os.path.exists(full_path):
        full_path = os.path.join(directory, f"{base_name} ({counter}).{extension}")
        counter += 1
    return full_path


def fetch_instagram_profile_instaloader(username, cookiefile_path=None):
    L = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_metadata=False
    )
    
    if cookiefile_path:
        try:
            cj = http.cookiejar.MozillaCookieJar(cookiefile_path)
            cj.load(ignore_discard=True, ignore_expires=True)
            L.context._session.cookies.update(cj)
            print(f"[debug] Loaded cookies into instaloader session from {cookiefile_path}", flush=True)
        except Exception as e:
            print(f"[debug] Instaloader failed to load cookiefile: {e}", flush=True)
            
    L.context._session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    
    print(f"[debug] Fetching instaloader profile for {username}...", flush=True)
    profile = instaloader.Profile.from_username(L.context, username)
    
    entries = []
    posts = profile.get_posts()
    
    count = 0
    for post in posts:
        if count >= 30:
            break
            
        if not post.is_video:
            continue
            
        shortcode = post.shortcode
        title = post.caption or f"Instagram Reel {shortcode}"
        thumbnail = post.url
        
        entries.append({
            "id": shortcode,
            "title": title,
            "url": f"https://www.instagram.com/reel/{shortcode}/",
            "thumbnail": thumbnail,
            "duration": post.video_duration,
            "kind": "video",
            "_type": "url",
            "ie_key": "Instagram",
        })
        count += 1
        
    return entries

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


def fetch_instagram_profile_info(username, cookiefile_path=None):
    cookies_dict = parse_cookies_from_file(cookiefile_path)
    session = requests.Session()
    session.cookies.update(cookies_dict)
    
    headers = {
        "x-ig-app-id": "936619743392459",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/120.0.0.0",
        "Referer": f"https://www.instagram.com/{username}/",
        "Accept": "*/*",
    }
    
    api_url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    resp = session.get(api_url, headers=headers, timeout=15)
    
    if resp.status_code != 200:
        print(f"[debug] Instagram Web Profile API failed with status code {resp.status_code}. Response: {resp.text[:500]}", flush=True)
        raise Exception(f"Instagram API returned status {resp.status_code}")
        
    return resp.json()


def fetch_instagram_profile_info_fallback(username, cookiefile_path=None):
    cookies_dict = parse_cookies_from_file(cookiefile_path)
    session = requests.Session()
    session.cookies.update(cookies_dict)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/120.0.0.0",
        "Referer": f"https://www.instagram.com/{username}/",
        "Accept": "*/*",
    }
    
    api_url = f"https://www.instagram.com/{username}/?__a=1&__d=dis"
    resp = session.get(api_url, headers=headers, timeout=15)
    if resp.status_code == 200:
        return resp.json()
    raise Exception(f"Fallback Instagram API returned status {resp.status_code}")


def parse_instagram_profile_json(data, username):
    user_data = None
    if "data" in data and "user" in data["data"]:
        user_data = data["data"]["user"]
    elif "graphql" in data and "user" in data["graphql"]:
        user_data = data["graphql"]["user"]
    elif "user" in data:
        user_data = data["user"]
        
    if not user_data:
        return []
        
    edges = []
    # Combine posts/timeline media and reels/felix video timeline
    for key in ("edge_owner_to_timeline_media", "edge_felix_video_timeline"):
        if key in user_data and "edges" in user_data[key]:
            edges.extend(user_data[key]["edges"])
            
    parsed_entries = []
    seen_shortcodes = set()
    
    for edge in edges:
        node = edge.get("node")
        if not node:
            continue
        shortcode = node.get("shortcode")
        if not shortcode or shortcode in seen_shortcodes:
            continue
            
        # Only take video posts as requested!
        is_video = node.get("is_video", False)
        if not is_video:
            continue
            
        seen_shortcodes.add(shortcode)
        
        # Extract title/caption
        title = ""
        caption_edges = node.get("edge_media_to_caption", {}).get("edges", [])
        if caption_edges:
            title = caption_edges[0].get("node", {}).get("text", "")
            
        if not title:
            title = f"Instagram Post {shortcode}"
            
        thumbnail = node.get("display_url") or node.get("thumbnail_src")
        
        parsed_entries.append({
            "id": shortcode,
            "title": title,
            "url": f"https://www.instagram.com/reel/{shortcode}/",
            "thumbnail": thumbnail,
            "duration": node.get("video_duration") or None,
            "kind": "video",
            "_type": "url",
            "ie_key": "Instagram",
        })
        
    return parsed_entries


def resolve_thumbnail(info):
    # Some extractors (e.g. RedNote/Xiaohongshu) only populate the plural
    # "thumbnails" list and rely on a later processing step - which doesn't
    # always run in --simulate/skip_download mode - to fill in the singular
    # "thumbnail" field. Fall back to the list directly instead of showing no
    # thumbnail at all when that field is missing.
    thumbnail = info.get("thumbnail")
    if thumbnail:
        return thumbnail
    thumbnails = info.get("thumbnails") or []
    if thumbnails:
        # yt-dlp orders thumbnails worst-to-best by convention
        return thumbnails[-1].get("url")
    return None


def combined_download_percent(stream_index, raw_percent, total_streams):
    return min(100.0, (stream_index * 100 + raw_percent) / total_streams)


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
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                path_val = data.get("path", default_path)
                cookies_path_val = data.get("cookies_path", "")
                browser_val = data.get("browser", "chrome")
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
        save_session(path_val, cookies_path_val, browser_val)

    return {"path": path_val, "cookies_path": cookies_path_val, "browser": browser_val}


def save_session(path_val, cookies_path_val="", browser_val="chrome"):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"path": path_val, "cookies_path": cookies_path_val, "browser": browser_val}, f)


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


@app.get("/")
def index():
    return send_from_directory(paths.WEB_DIR, "index.html")


@app.get("/api/settings")
def get_settings():
    session = load_session()
    return jsonify({**session, "cookies_status": cookies_status_for(session["cookies_path"])})


@app.post("/api/settings")
def update_settings():
    data = request.get_json(force=True) or {}
    session = load_session()
    path_val = data.get("path", session["path"])
    cookies_path_val = data.get("cookies_path", session["cookies_path"])
    browser_val = data.get("browser", session.get("browser", "chrome"))
    save_session(path_val, cookies_path_val, browser_val)
    return jsonify({
        "path": path_val,
        "cookies_path": cookies_path_val,
        "browser": browser_val,
        "cookies_status": cookies_status_for(cookies_path_val),
    })


LOCAL_ONLY_ERROR = "This action is only available when running OmniFlow locally."


@app.get("/api/clipboard")
def get_clipboard():
    # Read the clipboard on the server side via the OS instead of the browser's
    # navigator.clipboard API - that API is unreliable in this app's actual
    # runtime contexts (permission prompts that never resolve in some browsers,
    # and no support at all inside desktop_app.py's pywebview/WKWebView window).
    # pbpaste reads the general pasteboard directly with no permission prompt.
    # Only correct when the browser and server share a machine - pbpaste would
    # otherwise read the SERVER's clipboard for a remote visitor, not theirs.
    if not is_local_request():
        return jsonify({"error": LOCAL_ONLY_ERROR}), 403
    try:
        result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return jsonify({"error": str(e)}), 500
    if result.returncode != 0:
        return jsonify({"error": "Could not read clipboard"}), 500
    return jsonify({"text": result.stdout})


@app.post("/api/browse")
def browse_folder():
    # Native macOS dialog - renders on whichever machine runs this process,
    # so it must never be reachable from a remote visitor's request.
    if not is_local_request():
        return jsonify({"error": LOCAL_ONLY_ERROR}), 403
    script = 'POSIX path of (choose folder with prompt "Select download folder")'
    try:
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timed out"}), 504
    path = result.stdout.strip()
    if result.returncode != 0 or not path:
        return jsonify({"error": "cancelled"}), 400
    return jsonify({"path": path})


@app.post("/api/browse-file")
def browse_file():
    # Same reasoning as /api/browse - this dialog renders on the server's screen.
    if not is_local_request():
        return jsonify({"error": LOCAL_ONLY_ERROR}), 403
    script = 'POSIX path of (choose file with prompt "Select cookies.txt file")'
    try:
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timed out"}), 504
    path = result.stdout.strip()
    if result.returncode != 0 or not path:
        return jsonify({"error": "cancelled"}), 400
    return jsonify({"path": path, "cookies_status": cookies_status_for(path)})


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


def extract_video_info(cls):
    # `cls` is a classify.Classification - what the link IS was already decided
    # by classify.classify_url() (owner core capability #4); this function only
    # executes the extraction that classification dictates. It never re-derives
    # platform/kind from the URL string.
    url = cls.extraction_url
    if cls.kind == classify.LinkKind.INSTAGRAM_PROFILE:
        # Use our Custom Instagram Profile/Reels Resolver to bypass Meta blocks
        username = cls.username
        if not username:
            raise Exception("Cannot extract Instagram username from URL")
            
        cookies_path = get_cookies_path()
        auto_cookiefile = None
        # Fall back to auto browser cookies extraction if manual cookies settings not valid/empty
        if not (cookies_path and cookies_status_for(cookies_path) == "valid"):
            candidates = instagram_cookiefile_candidates()
            if candidates:
                auto_cookiefile = candidates[0]
                _cleanup_temp_cookiefiles(candidates[1:])
                cookies_path = auto_cookiefile
                
        try:
            print(f"[debug] Resolving Instagram profile for username: {username} using cookies: {cookies_path}", flush=True)
            entries = []
            try:
                # Primary method: instaloader
                entries = fetch_instagram_profile_instaloader(username, cookies_path)
            except Exception as e_insta:
                print(f"[debug] Instaloader profile fetch failed: {e_insta}. Trying Web Profile API fallback...", flush=True)
                data = None
                try:
                    data = fetch_instagram_profile_info(username, cookies_path)
                except Exception as e1:
                    print(f"[debug] fetch_instagram_profile_info failed: {e1}. Trying Graph API fallback...", flush=True)
                    try:
                        data = fetch_instagram_profile_info_fallback(username, cookies_path)
                    except Exception as e2:
                        print(f"[debug] Instagram fallback profile fetch also failed: {e2}", flush=True)
                        raise Exception(f"Failed to fetch Instagram profile: {e_insta} / {e1} / {e2}")
                entries = parse_instagram_profile_json(data, username)
            
            # Format as playlist/entries
            return {
                "_type": "playlist",
                "title": f"Instagram: {username}",
                "uploader": username,
                "entries": entries,
                "thumbnail": entries[0].get("thumbnail") if entries else None,
            }
        finally:
            if auto_cookiefile:
                _cleanup_temp_cookiefiles([auto_cookiefile])

    # Runs in-process via the yt-dlp Python package instead of spawning the
    # vendored PyInstaller-frozen ./yt-dlp binary: that binary self-extracts
    # its bundled Python runtime into a temp dir on every single invocation,
    # which measured 12+ seconds of pure startup overhead before it even
    # begins extracting - the actual network extraction only takes ~1-2s.
    # Calling the library directly skips that overhead entirely.
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "simulate": True,
        "skip_download": True,
        "socket_timeout": 30,
    }
    if cls.is_multi:
        # Flat extraction: list each entry's id/title/url/duration/thumbnail
        # WITHOUT fetching every video's full metadata - a channel with thousands
        # of videos would otherwise hang the app. playlistend caps the count as a
        # second guard on top of the flat (metadata-free) listing; the classifier
        # already picked the cap (50 for an endless Mix, 200 otherwise).
        ydl_opts["noplaylist"] = False
        ydl_opts["extract_flat"] = "in_playlist"
        ydl_opts["playlistend"] = cls.playlist_cap or classify.PLAYLIST_ITEM_CAP
    else:
        ydl_opts["noplaylist"] = True

    cookies_path = get_cookies_path()
    auto_cookiefile = None

    if "instagram" in url.lower():
        # Inject modern browser user-agent and referer headers to bypass block/rate-limits
        ydl_opts["http_headers"] = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.instagram.com/",
        }
        # Fall back to auto browser cookies extraction if manual cookies settings not valid/empty
        if not (cookies_path and cookies_status_for(cookies_path) == "valid"):
            candidates = instagram_cookiefile_candidates()
            if candidates:
                auto_cookiefile = candidates[0]
                # Cleanup candidates list we won't use
                _cleanup_temp_cookiefiles(candidates[1:])
                cookies_path = auto_cookiefile

    if cookies_path:
        ydl_opts["cookiefile"] = cookies_path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        print(f"[debug] Instagram check failed for {url}. Error: {e}", flush=True)
        raise
    finally:
        if auto_cookiefile:
            _cleanup_temp_cookiefiles([auto_cookiefile])


def describe_extraction_error(url, error, cookies_path=None):
    message = str(error)
    lower = message.lower()
    
    # Instagram profile / user failures
    is_ig_profile = classify.is_instagram_profile_url(url)
    if is_ig_profile or "instagram:user" in lower or "instagram:profile" in lower or ("unable to extract data" in lower and "instagram" in url.lower()):
        return "❌ Lỗi: Không thể lấy danh sách từ tài khoản Instagram này do giới hạn bảo mật. Vui lòng tải từng bài viết (Post/Reel) hoặc kiểm tra lại Cookies trong Settings."

    # Instagram, TikTok, Facebook private/login required errors
    is_private_or_login = (
        "login" in lower or 
        "cookie" in lower or 
        "confirm your identity" in lower or 
        "requires logged-in session" in lower or 
        "private video" in lower or 
        "private account" in lower or 
        "only available for registered users" in lower or 
        "empty media response" in lower or
        "302" in lower or
        "400" in lower or
        "redirect" in lower
    )
    is_major_platform = any(p in url.lower() for p in ("instagram", "tiktok", "facebook", "fb.watch", "fb.com"))
    
    if is_major_platform and is_private_or_login:
        return "❌ Lỗi: Không thể tải video từ tài khoản Private (Kín). OmniFlow hiện tại chỉ hỗ trợ tải nội dung Public (Công khai)."

    # General cleanup: hide traceback or github links
    if "unable to extract data" in lower or "traceback" in lower or "report this issue" in lower or "github.com" in lower:
        return "❌ Lỗi: Không thể trích xuất dữ liệu từ liên kết này. Vui lòng kiểm tra lại liên kết hoặc trạng thái công khai của nội dung."
        
    message = message.removeprefix("ERROR: ")
    first_sentence = message.split(". ")[0].strip()
    if "github" in first_sentence.lower() or "report this issue" in first_sentence.lower():
        return "❌ Lỗi: Đã xảy ra lỗi khi tải nội dung. Vui lòng thử lại sau."
        
    return first_sentence or "Invalid link or private video"


INSTAGRAM_LOCAL_ONLY_ERROR = "Instagram downloads are only available when running OmniFlow locally on your own machine."

# --- Instagram photo/carousel resolver -------------------------------------
# yt-dlp cannot download Instagram photos at all (it only ever builds formats
# from video_versions/DASH), so for Instagram posts/reels we resolve the media
# ourselves through Instagram's own private media-info endpoint using the same
# cookies.txt already configured in Settings. This is the only way to reach
# single photos and carousel photos. Stories (/stories/...) keep the existing
# yt-dlp path - they resolve to a playlist there and don't carry a shortcode.
INSTAGRAM_APP_ID = "936619743392459"  # public web app id, sent as X-IG-App-ID
INSTAGRAM_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
INSTAGRAM_B64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


class InstagramAuthError(Exception):
    """Instagram rejected the request for want of a valid logged-in session.

    Its message always contains a substring describe_extraction_error() keys on
    ("cookies"/"empty media response"), so both /api/check and /api/download map
    it to the same friendly cookies guidance the yt-dlp path already produces.
    """


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
    manual = get_cookies_path()
    if manual and cookies_status_for(manual) == "valid":
        candidates.append(manual)
    candidates.extend(cookiefiles_from_browsers("instagram.com"))
    return candidates


def fetch_instagram_media_any(url, cookiefiles):
    # Try each candidate account until Instagram actually returns the media. The
    # private post may only be visible to the specific logged-in account that
    # follows its owner, which needn't be the first profile found - so a single
    # cookiefile isn't enough. Surface the auth error (the user-actionable "fix
    # your login" case) when every account is unauthorized; otherwise re-raise the
    # last concrete failure.
    last_auth_error = None
    last_error = None
    for cf in cookiefiles:
        try:
            return fetch_instagram_media(url, cf)
        except InstagramAuthError as e:
            last_auth_error = e
        except Exception as e:
            last_error = e
    if last_auth_error:
        raise last_auth_error
    if last_error:
        raise last_error
    raise InstagramAuthError("Instagram requires a logged-in session (cookies).")


def instagram_media_id_from_shortcode(shortcode):
    # An Instagram shortcode is the media's numeric primary key encoded in a
    # url-safe base64 alphabet. Decoding it locally avoids an extra network
    # round-trip just to learn the id the /media/<id>/info/ endpoint needs.
    media_id = 0
    for ch in shortcode:
        media_id = media_id * 64 + INSTAGRAM_B64_ALPHABET.index(ch)
    return media_id


def _parse_instagram_cookies(cookies_path):
    # Returns {name: value} for instagram.com cookies. Parsed by hand (mirroring
    # cookies_file_has_instagram_session) rather than via MozillaCookieJar, which
    # hard-rejects any jar file missing its "# Netscape HTTP Cookie File" magic
    # header - a real-world variation across browser cookie exporters.
    cookies = {}
    try:
        with open(cookies_path, "r", errors="ignore") as f:
            lines = f.readlines()
    except OSError:
        return cookies
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
        if "instagram.com" in domain:
            cookies[name] = value
    return cookies


def _instagram_best_image(node):
    candidates = (node.get("image_versions2") or {}).get("candidates") or []
    # Instagram orders candidates largest-first.
    return candidates[0] if candidates else None


def _instagram_item(node):
    videos = node.get("video_versions") or []
    image = _instagram_best_image(node)
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


def _instagram_title(media, shortcode):
    caption = media.get("caption")
    text = caption.get("text") if isinstance(caption, dict) else ""
    if text:
        first_line = text.strip().splitlines()[0].strip()
        if first_line:
            return first_line[:60]
    return shortcode


def fetch_instagram_media(url, cookies_path):
    # Returns {"title": str, "items": [normalized item, ...]} where each item is
    # {"kind": "image"|"video", "url": <cdn>, "thumbnail", "width", "height"}.
    # A single post -> one item; a carousel -> one item per slide (photos and
    # videos mixed, in order). Raises InstagramAuthError when Instagram wants a
    # valid session.
    shortcode = classify.instagram_shortcode_from_url(url)
    if not shortcode:
        raise InstagramAuthError("Not an Instagram post or reel URL (cookies).")
    media_id = instagram_media_id_from_shortcode(shortcode)

    cookies = _parse_instagram_cookies(cookies_path)
    cookie_header = "; ".join(f"{name}={value}" for name, value in cookies.items())
    api_url = f"https://www.instagram.com/api/v1/media/{media_id}/info/"
    req = urllib.request.Request(
        api_url,
        headers={
            "User-Agent": INSTAGRAM_UA,
            "X-IG-App-ID": INSTAGRAM_APP_ID,
            "X-CSRFToken": cookies.get("csrftoken", ""),
            "Referer": "https://www.instagram.com/",
            "Accept": "*/*",
            "Cookie": cookie_header,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", "replace")
        payload = json.loads(body)
    except urllib.error.HTTPError as e:
        # A bad/expired session redirects to the login page (301/302) or is
        # rejected outright (401/403) - confirmed live: an invalid sessionid
        # returns 302, not 401. Map all of these to the friendly cookies
        # guidance instead of a generic "invalid link" error.
        if e.code in (301, 302, 401, 403):
            raise InstagramAuthError("Instagram requires a logged-in session (cookies).") from e
        raise
    except urllib.error.URLError as e:
        raise InstagramAuthError("Could not reach Instagram to fetch this media (cookies).") from e
    except json.JSONDecodeError as e:
        # A followed login redirect returns HTML, not JSON - also a session
        # problem, so surface the same cookies guidance.
        raise InstagramAuthError("Instagram requires a logged-in session (cookies).") from e

    items = payload.get("items") or []
    if not items:
        raise InstagramAuthError("Instagram sent an empty media response.")
    media = items[0]
    title = _instagram_title(media, shortcode)
    nodes = media.get("carousel_media") or [media]
    return {"title": title, "items": [_instagram_item(node) for node in nodes]}


def instagram_check_response(url, media):
    # Maps fetch_instagram_media()'s normalized media into the same /api/check
    # response shapes the frontend already understands (single "video" vs
    # "playlist"), adding a "kind" discriminator and a nominal quality label.
    # The raw CDN url is intentionally NOT sent to the client - it's re-resolved
    # server-side at download time by /api/download.
    items = media["items"]
    title = media["title"]
    platform = classify.get_platform_info(url)

    def quality_label(kind):
        return ["Image"] if kind == "image" else ["Video"]

    if len(items) == 1:
        item = items[0]
        return {
            "type": "video",
            "title": title,
            "uploader": "",
            "thumbnail": item.get("thumbnail"),
            "platform": platform,
            "kind": item["kind"],
            "qualities": quality_label(item["kind"]),
            "duration": None,
        }
    entries = []
    for i, item in enumerate(items, start=1):
        entries.append({
            "id": str(i),
            "title": f"{title} ({i})",
            "thumbnail": item.get("thumbnail"),
            "duration": None,
            "kind": item["kind"],
            # 1-based carousel slide index - download re-resolves the media and
            # picks items[entry_index-1] (same basis the single-download path uses).
            "entry_index": i,
            "qualities": quality_label(item["kind"]),
        })
    return {"type": "playlist", "platform": platform, "title": title, "items": entries}


def download_direct_url(cdn_url, output_path, job_id, chunk_size=131072, on_progress=None):
    # Streams a resolved Instagram CDN url (image or video) to disk, driving the
    # same jobs-dict progress model and honoring the same cooperative cancel
    # flag as the yt-dlp path. Instagram CDN urls are pre-signed, so only a
    # browser-like User-Agent is needed (no cookies). When on_progress is given
    # (batch mode) it reports this item's own 0-100 percent instead of writing
    # the shared job percent/text, so per-item bars stay independent.
    req = urllib.request.Request(cdn_url, headers={"User-Agent": INSTAGRAM_UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw_total = resp.headers.get("Content-Length")
        total = int(raw_total) if raw_total and raw_total.isdigit() else 0
        downloaded = 0
        with open(output_path, "wb") as out:
            while True:
                if jobs[job_id]["cancelled"]:
                    raise yt_dlp.utils.DownloadCancelled("cancelled by user")
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                if total:
                    percent = min(100.0, downloaded / total * 100)
                    if on_progress:
                        on_progress(percent)
                    else:
                        jobs[job_id]["percent"] = percent
                        jobs[job_id]["text"] = f"Downloading... ({percent:.1f}%)"
                elif not on_progress:
                    jobs[job_id]["text"] = "Downloading..."


# ---------------------------------------------------------------------------


def qualities_for(info):
    res_set = set()
    for f in info.get("formats", []):
        h = f.get("height")
        if h and isinstance(h, int) and h >= 360:
            res_set.add(h)
    qualities = [f"{h}p" for h in sorted(res_set, reverse=True)]
    qualities.append("Best")
    qualities.append("Audio Only")
    return qualities


def format_duration(duration):
    if not isinstance(duration, (int, float)):
        return None
    minutes, seconds = divmod(int(duration), 60)
    return f"{minutes:02d}:{seconds:02d}"


def flat_playlist_items(entries):
    # Shape flat-extraction entries (YouTube playlist/channel, Instagram profile)
    # into /api/check playlist items. The 1-based `position` is the video's TRUE
    # spot in the list (kept even for hidden/removed videos) and is used for UI
    # numbering ONLY - PRD §7: the number must never touch the physical filename,
    # so `title` stays the raw video title (the batch download builds the saved
    # file from it). A 1-item "playlist" gets position None - the frontend
    # renders it as a plain single video.
    number_items = len(entries) > 1
    items = []
    for pos, entry in enumerate(entries, start=1):
        item_url = entry.get("url") or entry.get("webpage_url")
        if not item_url and entry.get("id"):
            item_url = f"https://www.youtube.com/watch?v={entry['id']}"
        raw_title = entry.get("title") or "Video"
        duration = entry.get("duration")
        # A playlist routinely contains hidden/removed videos. yt-dlp lists
        # them with a "[Private video]"/"[Deleted video]" title and no
        # duration - flag those so the UI can disable/hide them and never
        # let a batch queue a doomed download. Keep them in the list (not
        # dropped) so the numbering stays true to the real playlist.
        lower = raw_title.lower()
        is_available = not (
            "[private video]" in lower
            or "[deleted video]" in lower
            or "[unavailable video]" in lower
            or duration is None
            or not item_url
        )
        items.append({
            "id": entry.get("id"),
            "title": raw_title,
            "position": pos if number_items else None,
            "uploader": entry.get("uploader") or entry.get("channel") or "",
            "thumbnail": resolve_thumbnail(entry),
            "duration": format_duration(duration),
            "url": item_url,
            "qualities": classify.PLAYLIST_QUALITIES,
            "is_available": is_available,
        })
    return items


def story_playlist_items(entries):
    # Shape a full (non-flat) yt-dlp playlist - an Instagram Story - into
    # /api/check playlist items: keep only the actual videos (photo entries
    # carry no formats) but remember each one's ORIGINAL 1-based position so
    # download targets the right entry even after photos are filtered out.
    items = []
    for original_index, entry in enumerate(entries, start=1):
        if not entry.get("formats"):
            continue
        items.append({
            "id": entry.get("id"),
            "title": entry.get("title") or "Video",
            "thumbnail": resolve_thumbnail(entry),
            "duration": format_duration(entry.get("duration")),
            "entry_index": original_index,
            "qualities": qualities_for(entry),
        })
    return items


@app.post("/api/check")
def check_link():
    data = request.get_json(force=True) or {}
    raw_url = (data.get("url") or "").strip()
    if not raw_url:
        return jsonify({"error": "Missing url"}), 400
    cls = classify.classify_url(raw_url)
    url = cls.url

    # Instagram only works with a cookies.txt file configured in Settings, and
    # that config is a single, machine-wide setting (see get_cookies_path) -
    # not per-visitor. Without this check, a remote visitor's Instagram
    # request would silently succeed using the local owner's own live
    # session, burning their account's rate limits/ban risk on a stranger's
    # request. Reject it outright instead of letting it "just fail" on its
    # own, since it might not fail at all if the owner has cookies configured.
    if cls.platform == "Instagram" and not is_local_request():
        return jsonify({"error": INSTAGRAM_LOCAL_ONLY_ERROR}), 403

    # Instagram posts/reels/tv go through our own resolver (so photos and
    # carousels work at all) ONLY if we have a valid cookies file.
    # Otherwise (or if custom resolver fails), we fall through to yt-dlp.
    if cls.kind == classify.LinkKind.INSTAGRAM_POST_OR_CAROUSEL:
        candidates = instagram_cookiefile_candidates()
        if candidates:
            try:
                media = fetch_instagram_media_any(url, candidates)
                return jsonify(instagram_check_response(url, media))
            except Exception as e:
                # Fall through to yt-dlp path below
                print(f"Custom resolver failed: {e}. Falling through to yt-dlp.")
                pass
            finally:
                _cleanup_temp_cookiefiles(candidates)

    try:
        info = extract_video_info(cls)
    except yt_dlp.utils.DownloadError as e:
        return jsonify({"error": describe_extraction_error(url, e, get_cookies_path())}), 400
    except Exception:
        return jsonify({"error": "Invalid link or private video"}), 400

    if not info:
        return jsonify({"error": "Invalid link or private video"}), 400

    # Two kinds of playlist resolve here:
    #  - a YouTube playlist/channel or Instagram profile (flat/resolver listing):
    #    entries carry no per-item formats, so each item carries its own video
    #    URL + the shared quality ladder, and batch download hits each URL.
    #  - an Instagram Story (full yt-dlp playlist): entries carry formats; keep
    #    only the actual videos (photo items have none) but remember each one's
    #    ORIGINAL 1-based position so download targets the right entry even after
    #    photo entries are filtered out.
    if info.get("_type") == "playlist" or "entries" in info:
        entries = [e for e in (info.get("entries") or []) if e]
        is_flat = cls.is_multi
        items = flat_playlist_items(entries) if is_flat else story_playlist_items(entries)
        return jsonify({
            "type": "playlist",
            "platform": cls.platform,
            "title": info.get("title") or ("Playlist" if is_flat else "Story"),
            "items": items,
            "truncated": is_flat and len(entries) >= classify.PLAYLIST_ITEM_CAP,
        })

    return jsonify({
        "type": "video",
        "title": info.get("title", "Video"),
        "uploader": info.get("uploader", ""),
        "thumbnail": resolve_thumbnail(info),
        "platform": cls.platform,
        "qualities": qualities_for(info),
        "duration": format_duration(info.get("duration")),
    })


def build_download_options(
    quality, output_path_no_ext, ffmpeg_bin, progress_hooks, postprocessor_hooks, cookies_path=None, entry_index=None, url=None
):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "outtmpl": output_path_no_ext + ".%(ext)s",
        "ffmpeg_location": ffmpeg_bin,
        "progress_hooks": progress_hooks,
        "postprocessor_hooks": postprocessor_hooks,
        # Network resilience: auto-retry a flaky connection / dropped fragment
        # instead of failing the whole item on a transient blip - important for a
        # long playlist where one hiccup shouldn't kill an item.
        "socket_timeout": 30,
        "retries": 5,
        "fragment_retries": 5,
        # Speed: pull 10 fragments of a stream in parallel (PRD §7). Applies to
        # both the single-video route and each item of a batch.
        "concurrent_fragment_downloads": 10,
        # Never keep the separate pre-merge video/audio files (the .f137/.f140
        # leftovers) - yt-dlp deletes them after a successful merge when this is
        # False (the default, pinned explicitly here so it can't drift).
        "keepvideo": False,
    }
    if entry_index:
        # The URL resolves to a playlist (an Instagram Story, or a multi-video
        # carousel post) and the caller picked one specific item. Without
        # this, yt-dlp downloads every entry into the same fixed outtmpl,
        # each one silently overwriting the last.
        opts["noplaylist"] = False
        opts["playlist_items"] = str(entry_index)
    else:
        opts["noplaylist"] = True
        
    is_ig = url and "instagram" in url.lower()
    if is_ig:
        opts["http_headers"] = {"User-Agent": INSTAGRAM_UA}
    if cookies_path:
        opts["cookiefile"] = cookies_path
            
    if "Audio" in quality:
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}]
    else:
        h = quality.replace("p", "").replace("Best", "2160")
        # Strongly prefer H.264 (avc1) video + AAC (m4a) audio. macOS (Finder
        # QuickLook / QuickTime) cannot decode VP9 or AV1 inside an .mp4 - such a
        # file opens as a black/white screen even though the download "succeeded".
        # yt-dlp will otherwise happily hand back VP9 for anything YouTube serves
        # above 1080p. This format ladder tries h264 first at every step, relaxing
        # one constraint per fallback so a download never fails outright; anything
        # that STILL slips through as VP9/AV1 (e.g. a 4K source with no h264 track)
        # is caught afterward by the ensure_h264() re-encode safety net in run().
        opts["format"] = (
            f"bestvideo[vcodec^=avc1][height<={h}]+bestaudio[ext=m4a]/"
            f"bestvideo[vcodec^=avc1][height<={h}]+bestaudio/"
            f"best[vcodec^=avc1][height<={h}]/"
            f"bestvideo[height<={h}]+bestaudio/best[height<={h}]/best"
        )
        opts["format_sort"] = ["vcodec:h264", "res", "acodec:m4a"]
        # PRD §7: merge straight into an mp4 container. Because the selector above
        # already lands H.264 video + m4a audio in the common case, both the merge
        # and the FFmpegVideoRemuxer are a fast stream-COPY (`-c copy`) - NO
        # re-encode, which is what was making "combine" slow before. The remuxer
        # also normalizes any single-file (non-merged) result to .mp4 so the saved
        # extension is predictable. The rare VP9/AV1 straggler that a copy can't
        # make macOS-playable is caught afterward by ensure_h264() in run().
        opts["merge_output_format"] = "mp4"
        opts["postprocessors"] = [{"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}]
    return opts


# Video codecs macOS' native stack (Finder QuickLook / QuickTime) can't play
# when muxed into an .mp4 - the download looks fine but the file is unwatchable.
MACOS_INCOMPATIBLE_VCODECS = ("vp9", "vp09", "vp8", "av01", "av1")


def detect_video_codec(path, ffmpeg_bin):
    # Returns the video stream's codec name (lowercased) for `path`, or None if
    # it can't be determined. Uses the bundled ffmpeg itself (`-i` prints stream
    # info to stderr) so we never depend on a separate ffprobe binary being
    # present - only ./ffmpeg is vendored.
    try:
        result = subprocess.run(
            [ffmpeg_bin, "-hide_banner", "-i", path],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    for line in result.stderr.splitlines():
        if "Video:" in line:
            m = re.search(r"Video:\s*([A-Za-z0-9_]+)", line)
            if m:
                return m.group(1).lower()
    return None


def ensure_h264(path, ffmpeg_bin, job_id):
    # Guarantees the finished video is macOS-playable H.264. When the format
    # selector already landed h264 (the common case) this only probes and
    # returns - no re-encode. It re-encodes ONLY when the file positively
    # carries a known-incompatible codec (VP9/AV1), which the h264-preferring
    # selector should make rare (e.g. a 4K-only-in-VP9 source). Honors the same
    # cooperative cancel flag as the rest of the download.
    codec = detect_video_codec(path, ffmpeg_bin)
    if not codec or not any(codec.startswith(bad) for bad in MACOS_INCOMPATIBLE_VCODECS):
        return
    jobs[job_id]["text"] = "Converting to H.264 for macOS..."
    tmp_out = path + ".h264.mp4"
    cmd = [
        ffmpeg_bin, "-y", "-i", path,
        # yuv420p 8-bit is the profile QuickTime actually decodes - some VP9/AV1
        # sources are 10-bit (yuv420p10le), which would stay unplayable if copied
        # through, so pin it explicitly.
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", tmp_out,
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    while proc.poll() is None:
        if jobs[job_id]["cancelled"]:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            if os.path.exists(tmp_out):
                try:
                    os.remove(tmp_out)
                except OSError:
                    pass
            raise yt_dlp.utils.DownloadCancelled("cancelled by user")
        time.sleep(0.3)
    if proc.returncode == 0 and os.path.exists(tmp_out):
        os.replace(tmp_out, path)
    elif os.path.exists(tmp_out):
        # Re-encode failed - keep the original (still-playable-elsewhere) file
        # rather than leaving a truncated temp output behind.
        try:
            os.remove(tmp_out)
        except OSError:
            pass


def apply_progress_update(job, progress_dict, stream_index, total_streams):
    # Video downloads merge two separate yt-dlp streams (video then audio), each
    # reporting its own independent 0-100% sequence - naively showing that raw
    # number makes the progress bar visibly jump backwards when the second
    # stream starts. Split the displayed percent into one slice per expected
    # stream so it only ever moves forward. Our own format selector always
    # requests a video+audio pair (falling back to a single combined format
    # only if that pair isn't available), so 2 is the correct expectation for
    # non-audio jobs.
    status = progress_dict.get("status")
    if status == "downloading":
        total = progress_dict.get("total_bytes") or progress_dict.get("total_bytes_estimate")
        downloaded = progress_dict.get("downloaded_bytes") or 0
        if total:
            raw_percent = downloaded / total * 100
            combined = combined_download_percent(stream_index, raw_percent, total_streams)
            job["percent"] = combined
            job["text"] = f"Downloading... ({combined:.1f}%)"
    elif status == "finished":
        stream_index = min(stream_index + 1, total_streams - 1)
    return stream_index


def cleanup_partial_download(output_path_no_ext):
    directory = os.path.dirname(output_path_no_ext) or "."
    prefix = os.path.basename(output_path_no_ext)
    try:
        for name in os.listdir(directory):
            if name.startswith(prefix):
                try:
                    os.remove(os.path.join(directory, name))
                except OSError:
                    pass
    except OSError:
        pass


def _remove_job_file(job_id):
    # Delete a job's partially-written output file (used when an Instagram
    # direct download is cancelled or errors out mid-stream).
    filepath = jobs.get(job_id, {}).get("filepath")
    if filepath and os.path.exists(filepath):
        try:
            os.remove(filepath)
        except OSError:
            pass


def download_one_video(url, save_dir, title, quality, ffmpeg_bin, job_id, entry_index=None, on_progress=None):
    # Download a single video URL into save_dir via yt-dlp and return the saved
    # path. Used by the batch runner - the single-video /api/download route keeps
    # its own copy so this can't destabilize that tested path. Honors
    # jobs[job_id]['cancelled'] (raising DownloadCancelled), applies the H.264
    # safety net, and reports THIS item's own 0-100 percent via on_progress(pct)
    # so the caller can fold it into an overall bar. Raises yt-dlp errors to the
    # caller so the batch loop can record/skip a failed item and keep going.
    ext = "mp3" if "Audio" in quality else "mp4"
    final_output_path = get_unique_filename(save_dir, title, ext)
    output_path_no_ext = os.path.splitext(final_output_path)[0]
    total_streams = 1 if "Audio" in quality else 2
    state = {"stream_index": 0, "scratch": {}}

    def progress_hook(d):
        if jobs[job_id]["cancelled"]:
            raise yt_dlp.utils.DownloadCancelled("cancelled by user")
        state["stream_index"] = apply_progress_update(state["scratch"], d, state["stream_index"], total_streams)
        if on_progress and "percent" in state["scratch"]:
            on_progress(state["scratch"]["percent"])

    def postprocessor_hook(d):
        if jobs[job_id]["cancelled"]:
            raise yt_dlp.utils.DownloadCancelled("cancelled by user")

    cookies_path = get_cookies_path()
    if url and "instagram" in url.lower():
        if not (cookies_path and cookies_status_for(cookies_path) == "valid"):
            candidates = instagram_cookiefile_candidates()
            if candidates:
                cookies_path = candidates[0]
                _cleanup_temp_cookiefiles(candidates[1:])

    ydl_opts = build_download_options(
        quality, output_path_no_ext, ffmpeg_bin, [progress_hook], [postprocessor_hook], cookies_path, entry_index, url
    )
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        if "Audio" not in quality:
            ensure_h264(final_output_path, ffmpeg_bin, job_id)
    finally:
        _cleanup_temp_cookiefiles([ydl_opts.get("cookiefile")])
    return final_output_path


@app.post("/api/download")
def start_download():
    data = request.get_json(force=True) or {}
    raw_url = (data.get("url") or "").strip()
    if not raw_url:
        return jsonify({"error": "Missing url"}), 400
    cls = classify.classify_url(raw_url)
    # Always download cls.url (the pasted link, RedNote-normalized) - NEVER
    # cls.extraction_url: for a watch?v=X&list=PL… link the user picked video X,
    # while extraction_url deliberately widens to the whole playlist for /api/check.
    url = cls.url
    title = data.get("title") or "Video"
    quality = data.get("quality") or "Best"
    entry_index = data.get("entry_index") or classify.entry_index_from_url(url)

    if cls.platform == "Instagram" and not is_local_request():
        return jsonify({"error": INSTAGRAM_LOCAL_ONLY_ERROR}), 403

    remote_temp_dir = None
    if is_local_request():
        session = load_session()
        save_dir = resolve_save_dir(session["path"])
        if save_dir is None:
            return jsonify({"error": "Download folder not writable"}), 400
    else:
        # No local folder to write into for a remote visitor - stage the file
        # in a throwaway temp dir and hand it to their browser afterward via
        # /api/download-file instead.
        remote_temp_dir = tempfile.mkdtemp(prefix="omniflow-")
        save_dir = remote_temp_dir

    # Instagram posts/reels/tv download through our own resolver + a direct CDN
    # fetch (the only way to get photos), bypassing yt-dlp and ffmpeg entirely,
    # ONLY if we have a valid manual cookies file.
    # Otherwise, let it fall through to the standard yt-dlp download pipeline.
    ig_candidates = []
    if cls.kind == classify.LinkKind.INSTAGRAM_POST_OR_CAROUSEL:
        ig_candidates = instagram_cookiefile_candidates()
    if ig_candidates:

        job_id = uuid.uuid4().hex
        jobs[job_id] = {
            "status": "running", "percent": 0, "text": "Starting...",
            "filename": None, "filepath": None, "cancelled": False,
        }

        def run_instagram():
            try:
                media = fetch_instagram_media_any(url, ig_candidates)
                items = media["items"]
                idx = (entry_index - 1) if entry_index else 0
                if idx < 0 or idx >= len(items):
                    raise ValueError("Selected item is no longer available")
                item = items[idx]
                cdn_url = item.get("url")
                if not cdn_url:
                    raise ValueError("No downloadable media found")
                ext = "jpg" if item["kind"] == "image" else "mp4"
                final_output_path = get_unique_filename(save_dir, title, ext)
                jobs[job_id]["filename"] = os.path.basename(final_output_path)
                jobs[job_id]["filepath"] = final_output_path
                download_direct_url(cdn_url, final_output_path, job_id)
            # In every terminal branch the final text/percent is written BEFORE
            # flipping status off "running", so any observer keying on status
            # (the frontend poll, tests) always reads a fully-updated job.
            except yt_dlp.utils.DownloadCancelled:
                _remove_job_file(job_id)
                jobs[job_id]["text"] = "Cancelled"
                jobs[job_id]["status"] = "cancelled"
                return
            except InstagramAuthError as e:
                _remove_job_file(job_id)
                jobs[job_id]["text"] = describe_extraction_error(url, e, ig_candidates[0])
                jobs[job_id]["status"] = "error"
                return
            except Exception as e:
                print(f"[download] job {job_id} (instagram) failed: {e}")
                _remove_job_file(job_id)
                jobs[job_id]["text"] = str(e) or "Download failed"
                jobs[job_id]["status"] = "error"
                return
            finally:
                # Media is already resolved (and the CDN download needs no cookies),
                # so the temp session files can go regardless of outcome.
                _cleanup_temp_cookiefiles(ig_candidates)
            jobs[job_id]["percent"] = 100
            jobs[job_id]["text"] = f"Saved: {jobs[job_id]['filename']}"
            jobs[job_id]["status"] = "done"

        threading.Thread(target=run_instagram, daemon=True).start()
        return jsonify({"job_id": job_id})

    ffmpeg_bin = paths.get_ffmpeg_path()
    if not ffmpeg_bin:
        return jsonify({"error": "FFmpeg missing! Run 'brew install ffmpeg'"}), 400

    ext = "mp3" if "Audio" in quality else "mp4"
    final_output_path = get_unique_filename(save_dir, title, ext)
    final_filename = os.path.basename(final_output_path)
    output_path_no_ext = os.path.splitext(final_output_path)[0]

    job_id = uuid.uuid4().hex
    jobs[job_id] = {
        "status": "running",
        "percent": 0,
        "text": "Starting...",
        "filename": final_filename,
        "filepath": final_output_path,
        "cancelled": False,
    }

    def run():
        total_streams = 1 if "Audio" in quality else 2
        state = {"stream_index": 0}

        def progress_hook(d):
            if jobs[job_id]["cancelled"]:
                raise yt_dlp.utils.DownloadCancelled("cancelled by user")
            state["stream_index"] = apply_progress_update(jobs[job_id], d, state["stream_index"], total_streams)

        def postprocessor_hook(d):
            if jobs[job_id]["cancelled"]:
                raise yt_dlp.utils.DownloadCancelled("cancelled by user")
            if d.get("status") == "started":
                jobs[job_id]["text"] = "Finalizing..."

        cookies_path = get_cookies_path()
        if url and "instagram" in url.lower():
            if not (cookies_path and cookies_status_for(cookies_path) == "valid"):
                candidates = instagram_cookiefile_candidates()
                if candidates:
                    cookies_path = candidates[0]
                    # Clean up other temporary files immediately
                    _cleanup_temp_cookiefiles(candidates[1:])

        ydl_opts = build_download_options(
            quality, output_path_no_ext, ffmpeg_bin, [progress_hook], [postprocessor_hook], cookies_path, entry_index, url
        )

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            # Safety net: if a VP9/AV1 stream still slipped through into the .mp4
            # despite the h264-preferring selector, re-encode it to H.264 so the
            # file is actually playable on macOS. No-op (a fast probe only) for
            # the common already-h264 case and for audio-only jobs.
            if "Audio" not in quality:
                ensure_h264(final_output_path, ffmpeg_bin, job_id)
        except yt_dlp.utils.DownloadCancelled:
            jobs[job_id]["status"] = "cancelled"
            jobs[job_id]["text"] = "Cancelled"
            cleanup_partial_download(output_path_no_ext)
            if remote_temp_dir:
                shutil.rmtree(remote_temp_dir, ignore_errors=True)
            return
        except yt_dlp.utils.DownloadError as e:
            # Same friendly-message treatment as /api/check - without this,
            # a download failure shows yt-dlp's raw CLI-flag-laden message
            # (--cookies-from-browser, GitHub issue templates) instead of the
            # plain explanation check_link() already gives for the same error.
            print(f"[download] job {job_id} failed: {e}")
            jobs[job_id]["status"] = "error"
            jobs[job_id]["text"] = describe_extraction_error(url, e, cookies_path)
            cleanup_partial_download(output_path_no_ext)
            if remote_temp_dir:
                shutil.rmtree(remote_temp_dir, ignore_errors=True)
            return
        except Exception as e:
            print(f"[download] job {job_id} failed: {e}")
            jobs[job_id]["status"] = "error"
            jobs[job_id]["text"] = str(e) or "Download failed"
            cleanup_partial_download(output_path_no_ext)
            if remote_temp_dir:
                shutil.rmtree(remote_temp_dir, ignore_errors=True)
            return
        finally:
            # If build_download_options auto-extracted a browser cookies.txt for
            # Instagram, it's served its purpose once the download call returns.
            _cleanup_temp_cookiefiles([ydl_opts.get("cookiefile")])

        jobs[job_id]["status"] = "done"
        jobs[job_id]["percent"] = 100
        jobs[job_id]["text"] = f"Saved: {final_filename}"

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"job_id": job_id})


PLAYLIST_LOCAL_ONLY_ERROR = "Batch playlist downloads are only available when running OmniFlow locally on your own machine."

# How many playlist items download at once. Parallelism is the main speed win for
# a playlist (YouTube throttles each stream, so independent streams add up), but
# too many at once trips rate limits and thrashes ffmpeg merges - 3 is a safe mix.
BATCH_CONCURRENCY = 3


@app.post("/api/download-batch")
def start_batch_download():
    # Downloads several selected items (a YouTube playlist/channel, or an
    # Instagram carousel/Story) in ONE job, BATCH_CONCURRENCY at a time (faster
    # than sequential for a playlist), exposing per-item progress so the frontend
    # can show one bar per video. Each item is identified by its own video "url"
    # (YouTube) or an "entry_index" into the original `url` (Instagram carousel
    # via the resolver, or a Story via yt-dlp playlist_items).
    data = request.get_json(force=True) or {}
    cls = classify.classify_url((data.get("url") or "").strip())
    url = cls.url
    quality = data.get("quality") or "Best"
    items = data.get("items") or []
    if not items:
        return jsonify({"error": "No items selected"}), 400

    # A batch writes many files; a remote visitor's browser can only pull one file
    # back via /api/download-file, so batch is local-only for now (a remote zip
    # was deliberately scoped out - see .claude/rules/web-app.md).
    if not is_local_request():
        return jsonify({"error": PLAYLIST_LOCAL_ONLY_ERROR}), 403

    save_dir = resolve_save_dir(load_session()["path"])
    if save_dir is None:
        return jsonify({"error": "Download folder not writable"}), 400

    ffmpeg_bin = paths.get_ffmpeg_path()
    if not ffmpeg_bin:
        return jsonify({"error": "FFmpeg missing! Run 'brew install ffmpeg'"}), 400

    is_ig_carousel = cls.kind == classify.LinkKind.INSTAGRAM_POST_OR_CAROUSEL

    job_id = uuid.uuid4().hex
    total = len(items)
    jobs[job_id] = {
        "status": "running", "percent": 0, "text": "Starting...",
        "filename": None, "filepath": None, "cancelled": False,
        "item": 0, "total": total,
        # Per-item progress the frontend renders as one bar per video.
        "items_progress": [
            {"title": (it.get("title") or f"Video {i + 1}"), "status": "pending", "percent": 0}
            for i, it in enumerate(items)
        ],
    }

    def run_batch():
        prog = jobs[job_id]["items_progress"]
        state = {"saved": [], "failed": 0}
        media_holder = {"media": None}
        ig_candidates = []
        lock = threading.Lock()

        def recompute_overall():
            # Overall bar = mean of every item's own percent; "item" = how many finished.
            jobs[job_id]["percent"] = min(100.0, sum(p["percent"] for p in prog) / total)
            jobs[job_id]["item"] = sum(1 for p in prog if p["status"] in ("done", "error"))

        def download_item(i, item):
            p = prog[i]
            if jobs[job_id]["cancelled"]:
                return
            p["status"] = "downloading"
            item_title = item.get("title") or f"Video {i + 1}"

            def on_progress(pct, p=p):
                p["percent"] = pct
                recompute_overall()

            try:
                if is_ig_carousel:
                    idx = item.get("entry_index") or (i + 1)
                    node = media_holder["media"]["items"][idx - 1]
                    cdn_url = node.get("url")
                    if not cdn_url:
                        raise ValueError("No downloadable media found")
                    ext = "jpg" if node["kind"] == "image" else "mp4"
                    out = get_unique_filename(save_dir, item_title, ext)
                    download_direct_url(cdn_url, out, job_id, on_progress=on_progress)
                elif item.get("url"):
                    out = download_one_video(item["url"], save_dir, item_title, quality, ffmpeg_bin, job_id, on_progress=on_progress)
                elif item.get("entry_index"):
                    # Instagram Story: yt-dlp playlist, targeted by its entry index.
                    out = download_one_video(url, save_dir, item_title, quality, ffmpeg_bin, job_id, entry_index=item["entry_index"], on_progress=on_progress)
                else:
                    p["status"] = "error"
                    with lock:
                        state["failed"] += 1
                    recompute_overall()
                    return
                p["percent"] = 100
                p["status"] = "done"
                with lock:
                    state["saved"].append(os.path.basename(out))
                    jobs[job_id]["filename"] = os.path.basename(out)
            except yt_dlp.utils.DownloadCancelled:
                p["status"] = "error"  # a cancel interrupts in-flight items
            except Exception as e:
                print(f"[batch] job {job_id} item {i + 1}/{total} failed: {e}")
                p["status"] = "error"
                with lock:
                    state["failed"] += 1
            recompute_overall()

        try:
            if is_ig_carousel:
                # Resolve the carousel's CDN urls once, reuse across selected slides.
                ig_candidates = instagram_cookiefile_candidates()
                if not ig_candidates:
                    raise InstagramAuthError("Instagram requires a logged-in session (cookies).")
                media_holder["media"] = fetch_instagram_media_any(url, ig_candidates)

            # Download BATCH_CONCURRENCY items at once. download_item swallows its
            # own per-item errors, so a future never raises here.
            with ThreadPoolExecutor(max_workers=min(BATCH_CONCURRENCY, total)) as ex:
                futures = [ex.submit(download_item, i, item) for i, item in enumerate(items)]
                for f in futures:
                    f.result()
        except Exception as e:
            # Only a pre-flight failure (e.g. Instagram auth before the pool starts).
            print(f"[batch] job {job_id} failed: {e}")
            _cleanup_temp_cookiefiles(ig_candidates)
            jobs[job_id]["text"] = describe_extraction_error(url, e) if is_ig_carousel else (str(e) or "Download failed")
            jobs[job_id]["status"] = "error"
            return

        _cleanup_temp_cookiefiles(ig_candidates)
        saved, failed = state["saved"], state["failed"]
        if jobs[job_id]["cancelled"]:
            jobs[job_id]["text"] = f"Cancelled (saved {len(saved)} of {total})"
            jobs[job_id]["status"] = "cancelled"
            return
        jobs[job_id]["percent"] = 100
        jobs[job_id]["saved_count"] = len(saved)
        if not saved:
            jobs[job_id]["text"] = "Could not download any item"
            jobs[job_id]["status"] = "error"
            return
        jobs[job_id]["filename"] = saved[-1]
        jobs[job_id]["text"] = f"Saved {len(saved)} of {total} videos" + (f" ({failed} failed)" if failed else "")
        jobs[job_id]["status"] = "done"

    threading.Thread(target=run_batch, daemon=True).start()
    return jsonify({"job_id": job_id})


@app.get("/api/progress/<job_id>")
def progress(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404
    return jsonify({
        "status": job["status"], "percent": job["percent"], "text": job["text"],
        "filename": job["filename"],
        # Present only for batch jobs; the frontend renders a localized
        # "item X of N" line and a batch-aware success message from these.
        "item": job.get("item"), "total": job.get("total"),
        "saved_count": job.get("saved_count"),
        "items_progress": job.get("items_progress"),
    })


@app.post("/api/cancel/<job_id>")
def cancel(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404
    job["cancelled"] = True
    return jsonify({"ok": True})


@app.get("/api/download-file/<job_id>")
def download_file(job_id):
    # Only meaningful for a remote visitor - the local flow already has the
    # finished file sitting in their own configured folder.
    if is_local_request():
        return jsonify({"error": "Not available in local mode"}), 403
    job = jobs.get(job_id)
    if not job or job["status"] != "done":
        return jsonify({"error": "File not ready"}), 404
    filepath = job.get("filepath")
    if not filepath or not os.path.isfile(filepath):
        return jsonify({"error": "File not found"}), 404

    @after_this_request
    def cleanup(response):
        shutil.rmtree(os.path.dirname(filepath), ignore_errors=True)
        return response

    return send_file(filepath, as_attachment=True, download_name=job["filename"])


@app.post("/api/open-folder")
def open_folder():
    # "open" targets a folder on the server's own disk - meaningless for a
    # remote visitor, whose downloaded file lives in their own browser's
    # download location instead (see /api/download-file).
    if not is_local_request():
        return jsonify({"error": LOCAL_ONLY_ERROR}), 403
    subprocess.run(["open", load_session()["path"]])
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="127.0.0.1", port=port, threaded=True)
