"""yt-dlp metadata extraction + /api/check item shaping.

extract_video_info() takes a classify.Classification - what a link IS was
already decided by classify.classify_url(); this module only executes the
extraction that classification dictates (profile resolver vs flat playlist vs
single) and shapes the results for the frontend.
"""

import yt_dlp

from backend import classify, config, cookies, instagram


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


def extract_video_info(cls):
    # `cls` is a classify.Classification - what the link IS was already decided
    # by classify.classify_url() (owner core capability #4); this function only
    # executes the extraction that classification dictates. It never re-derives
    # platform/kind from the URL string.
    url = cls.extraction_url
    playlist_limit = config.load_session().get("playlist_limit", 100)
    
    if cls.kind == classify.LinkKind.INSTAGRAM_PROFILE:
        # Use our Custom Instagram Profile/Reels Resolver to bypass Meta blocks
        username = cls.username
        if not username:
            raise Exception("Cannot extract Instagram username from URL")
            
        cookies_path = config.get_cookies_path()
        auto_cookiefile = None
        # Fall back to auto browser cookies extraction if manual cookies settings not valid/empty
        if not (cookies_path and config.cookies_status_for(cookies_path) == "valid"):
            candidates = cookies.instagram_cookiefile_candidates()
            if candidates:
                auto_cookiefile = candidates[0]
                cookies._cleanup_temp_cookiefiles(candidates[1:])
                cookies_path = auto_cookiefile
                
        try:
            print(f"[debug] Resolving Instagram profile for username: {username} using cookies: {cookies_path}", flush=True)
            entries = []
            # Cap Instagram profile limit at a sensible default (30) for the
            # /api/check call - loading 100+ videos via sequential API pages
            # adds many seconds of latency. The user can refine in Settings.
            # Never let a playlist_limit of 0 become 500 requests.
            limit = min(playlist_limit, 30) if playlist_limit > 0 else 30
            try:
                # Primary method: Instagram's own private feed API (2026-07-07).
                # web_profile_info/GraphQL/instaloader all now return a post
                # *count* with no *edges* for a profile the session doesn't
                # own - confirmed live, see MISTAKES.md - so this must go
                # first, not last.
                entries = instagram.fetch_instagram_profile_reel_media(username, cookies_path, limit=limit)
            except Exception as e_primary:
                # Only try fallbacks if primary totally failed (not just slow).
                # Each fallback adds up to 15s timeout, so keep the chain short.
                print(f"[debug] Private feed API failed: {e_primary}. Trying Web Profile API fallback...", flush=True)
                data = None
                try:
                    data = instagram.fetch_instagram_profile_info(username, cookies_path)
                except Exception as e1:
                    print(f"[debug] fetch_instagram_profile_info failed: {e1}. Trying Graph API fallback...", flush=True)
                    try:
                        data = instagram.fetch_instagram_profile_info_fallback(username, cookies_path)
                    except Exception as e2:
                        print(f"[debug] All Instagram profile fallbacks failed: {e2}", flush=True)
                        raise Exception(
                            f"Failed to fetch Instagram profile: {e_primary} / {e1} / {e2}"
                        )
                entries = instagram.parse_instagram_profile_json(data, username, limit=limit)

            if not entries:
                # Never a silent empty state (design-principles §3): every
                # method above either raises or returns entries here, so an
                # empty list means Instagram genuinely answered with zero
                # videos for every method tried - surface that, don't render
                # a confusing "0 items" playlist.
                raise Exception(f"No public video posts/reels found for Instagram profile {username}")

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
                cookies._cleanup_temp_cookiefiles([auto_cookiefile])

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
        "check_formats": False,
    }
    if cls.is_multi:
        # Flat extraction: list each entry's id/title/url/duration/thumbnail
        # WITHOUT fetching every video's full metadata - a channel with thousands
        # of videos would otherwise hang the app. playlistend caps the count as a
        # second guard on top of the flat (metadata-free) listing; the classifier
        # already picked the cap (50 for an endless Mix, 100 otherwise).
        ydl_opts["noplaylist"] = False
        ydl_opts["extract_flat"] = "in_playlist"
        if cls.kind == classify.LinkKind.YOUTUBE_MIX:
            ydl_opts["playlistend"] = cls.playlist_cap or 50
        elif playlist_limit > 0:
            ydl_opts["playlistend"] = playlist_limit
        else:
            ydl_opts["playlistend"] = 10000
        ydl_opts["ignoreerrors"] = True
    else:
        ydl_opts["noplaylist"] = True

    cookies_path = config.get_cookies_path()
    auto_cookiefile = None

    if "instagram" in url.lower():
        # Inject modern browser user-agent and referer headers to bypass block/rate-limits
        ydl_opts["http_headers"] = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.instagram.com/",
        }
        # Fall back to auto browser cookies extraction if manual cookies settings not valid/empty
        if not (cookies_path and config.cookies_status_for(cookies_path) == "valid"):
            candidates = cookies.instagram_cookiefile_candidates()
            if candidates:
                auto_cookiefile = candidates[0]
                # Cleanup candidates list we won't use
                cookies._cleanup_temp_cookiefiles(candidates[1:])
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
            cookies._cleanup_temp_cookiefiles([auto_cookiefile])


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
