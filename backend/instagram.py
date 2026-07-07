"""Instagram resolvers - the post/carousel media resolver + the profile/reels
resolver chain. yt-dlp cannot list Instagram profiles (Meta blocks it) or fetch
photos at all, so both go through Instagram's own private endpoints instead
(MISTAKES.md blacklist §1). Auth comes from backend.cookies candidates.
"""

import http.cookiejar
import json
import urllib.error
import urllib.parse
import urllib.request

import instaloader
import requests

from backend import classify, cookies


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


def fetch_instagram_profile_instaloader(username, cookiefile_path=None):
    L = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False
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

def fetch_instagram_profile_reel_media(username, cookies_path, limit=30):
    # Primary profile/reels resolver (2026-07-07). Instagram's public
    # GraphQL/AJAX surfaces (web_profile_info, ?__a=1, and instaloader's own
    # GraphQL query machinery) now return a post *count* with NO *edges* for
    # a profile the session doesn't own - confirmed live, not assumed (see
    # MISTAKES.md). This goes through the same private www.instagram.com
    # REST host + X-IG-App-ID/X-CSRFToken header pattern already proven to
    # work for fetch_instagram_media (posts/carousels), which Meta still
    # answers with real items for a logged-in session.
    profile_data = fetch_instagram_profile_info(username, cookies_path)
    user_data = (profile_data.get("data") or {}).get("user") or profile_data.get("user")
    user_id = user_data.get("id") if user_data else None
    if not user_id:
        raise InstagramAuthError(f"Could not resolve Instagram user id for {username} (cookies).")

    cookies_dict = _parse_instagram_cookies(cookies_path)
    cookie_header = "; ".join(f"{name}={value}" for name, value in cookies_dict.items())
    headers = {
        "User-Agent": INSTAGRAM_UA,
        "X-IG-App-ID": INSTAGRAM_APP_ID,
        "X-CSRFToken": cookies_dict.get("csrftoken", ""),
        "Referer": f"https://www.instagram.com/{username}/",
        "Accept": "*/*",
        "Cookie": cookie_header,
    }

    entries = []
    max_id = None
    while len(entries) < limit:
        api_url = f"https://www.instagram.com/api/v1/feed/user/{user_id}/"
        if max_id:
            api_url += f"?max_id={urllib.parse.quote(max_id)}"
        req = urllib.request.Request(api_url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 401, 403):
                raise InstagramAuthError("Instagram requires a logged-in session (cookies).") from e
            raise
        except urllib.error.URLError as e:
            raise InstagramAuthError("Could not reach Instagram to fetch this profile (cookies).") from e

        for item in payload.get("items") or []:
            if item.get("media_type") != 2:  # videos/reels only - matches the prior is_video filter
                continue
            code = item.get("code")
            if not code:
                continue
            candidates = (item.get("image_versions2") or {}).get("candidates") or []
            entries.append({
                "id": code,
                "title": (item.get("caption") or {}).get("text") or f"Instagram Reel {code}",
                "url": f"https://www.instagram.com/reel/{code}/",
                "thumbnail": candidates[0].get("url") if candidates else None,
                "duration": item.get("video_duration"),
                "kind": "video",
                "_type": "url",
                "ie_key": "Instagram",
            })
            if len(entries) >= limit:
                break

        if not payload.get("more_available") or not payload.get("next_max_id"):
            break
        max_id = payload["next_max_id"]

    return entries


def fetch_instagram_profile_info(username, cookiefile_path=None):
    cookies_dict = cookies.parse_cookies_from_file(cookiefile_path)
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
    cookies_dict = cookies.parse_cookies_from_file(cookiefile_path)
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
