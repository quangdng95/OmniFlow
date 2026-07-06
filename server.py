import os, sys, json, re, subprocess, tempfile, threading, time, uuid, shutil
import urllib.request, urllib.error, urllib.parse, http.cookiejar, requests
from concurrent.futures import ThreadPoolExecutor
import yt_dlp
import instaloader
from flask import Flask, request, jsonify, send_from_directory, send_file, after_this_request

from backend import classify, config, cookies, instagram, jobs, paths

app = Flask(__name__, static_folder=paths.WEB_DIR, static_url_path="")

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


@app.get("/")
def index():
    return send_from_directory(paths.WEB_DIR, "index.html")


@app.get("/api/settings")
def get_settings():
    session = config.load_session()
    return jsonify({**session, "cookies_status": config.cookies_status_for(session["cookies_path"])})


@app.post("/api/settings")
def update_settings():
    data = request.get_json(force=True) or {}
    session = config.load_session()
    path_val = data.get("path", session["path"])
    cookies_path_val = data.get("cookies_path", session["cookies_path"])
    browser_val = data.get("browser", session.get("browser", "chrome"))
    config.save_session(path_val, cookies_path_val, browser_val)
    return jsonify({
        "path": path_val,
        "cookies_path": cookies_path_val,
        "browser": browser_val,
        "cookies_status": config.cookies_status_for(cookies_path_val),
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
    return jsonify({"path": path, "cookies_status": config.cookies_status_for(path)})


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
            try:
                # Primary method: instaloader
                entries = instagram.fetch_instagram_profile_instaloader(username, cookies_path)
            except Exception as e_insta:
                print(f"[debug] Instaloader profile fetch failed: {e_insta}. Trying Web Profile API fallback...", flush=True)
                data = None
                try:
                    data = instagram.fetch_instagram_profile_info(username, cookies_path)
                except Exception as e1:
                    print(f"[debug] fetch_instagram_profile_info failed: {e1}. Trying Graph API fallback...", flush=True)
                    try:
                        data = instagram.fetch_instagram_profile_info_fallback(username, cookies_path)
                    except Exception as e2:
                        print(f"[debug] Instagram fallback profile fetch also failed: {e2}", flush=True)
                        raise Exception(f"Failed to fetch Instagram profile: {e_insta} / {e1} / {e2}")
                entries = instagram.parse_instagram_profile_json(data, username)
            
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


INSTAGRAM_LOCAL_ONLY_ERROR = "Instagram downloads are only available when running OmniFlow locally on your own machine."

def download_direct_url(cdn_url, output_path, job_id, chunk_size=131072, on_progress=None):
    # Streams a resolved Instagram CDN url (image or video) to disk, driving the
    # same jobs-dict progress model and honoring the same cooperative cancel
    # flag as the yt-dlp path. Instagram CDN urls are pre-signed, so only a
    # browser-like User-Agent is needed (no cookies). When on_progress is given
    # (batch mode) it reports this item's own 0-100 percent instead of writing
    # the shared job percent/text, so per-item bars stay independent.
    req = urllib.request.Request(cdn_url, headers={"User-Agent": instagram.INSTAGRAM_UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw_total = resp.headers.get("Content-Length")
        total = int(raw_total) if raw_total and raw_total.isdigit() else 0
        downloaded = 0
        with open(output_path, "wb") as out:
            while True:
                if jobs.jobs[job_id]["cancelled"]:
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
                        jobs.jobs[job_id]["percent"] = percent
                        jobs.jobs[job_id]["text"] = f"Downloading... ({percent:.1f}%)"
                elif not on_progress:
                    jobs.jobs[job_id]["text"] = "Downloading..."


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
        candidates = cookies.instagram_cookiefile_candidates()
        if candidates:
            try:
                media = instagram.fetch_instagram_media_any(url, candidates)
                return jsonify(instagram.instagram_check_response(url, media))
            except Exception as e:
                # Fall through to yt-dlp path below
                print(f"Custom resolver failed: {e}. Falling through to yt-dlp.")
                pass
            finally:
                cookies._cleanup_temp_cookiefiles(candidates)

    try:
        info = extract_video_info(cls)
    except yt_dlp.utils.DownloadError as e:
        return jsonify({"error": describe_extraction_error(url, e, config.get_cookies_path())}), 400
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
        opts["http_headers"] = {"User-Agent": instagram.INSTAGRAM_UA}
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
    jobs.jobs[job_id]["text"] = "Converting to H.264 for macOS..."
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
        if jobs.jobs[job_id]["cancelled"]:
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


def download_one_video(url, save_dir, title, quality, ffmpeg_bin, job_id, entry_index=None, on_progress=None):
    # Download a single video URL into save_dir via yt-dlp and return the saved
    # path. Used by the batch runner - the single-video /api/download route keeps
    # its own copy so this can't destabilize that tested path. Honors
    # jobs.jobs[job_id]['cancelled'] (raising DownloadCancelled), applies the H.264
    # safety net, and reports THIS item's own 0-100 percent via on_progress(pct)
    # so the caller can fold it into an overall bar. Raises yt-dlp errors to the
    # caller so the batch loop can record/skip a failed item and keep going.
    ext = "mp3" if "Audio" in quality else "mp4"
    final_output_path = get_unique_filename(save_dir, title, ext)
    output_path_no_ext = os.path.splitext(final_output_path)[0]
    total_streams = 1 if "Audio" in quality else 2
    state = {"stream_index": 0, "scratch": {}}

    def progress_hook(d):
        if jobs.jobs[job_id]["cancelled"]:
            raise yt_dlp.utils.DownloadCancelled("cancelled by user")
        state["stream_index"] = apply_progress_update(state["scratch"], d, state["stream_index"], total_streams)
        if on_progress and "percent" in state["scratch"]:
            on_progress(state["scratch"]["percent"])

    def postprocessor_hook(d):
        if jobs.jobs[job_id]["cancelled"]:
            raise yt_dlp.utils.DownloadCancelled("cancelled by user")

    cookies_path = config.get_cookies_path()
    if url and "instagram" in url.lower():
        if not (cookies_path and config.cookies_status_for(cookies_path) == "valid"):
            candidates = cookies.instagram_cookiefile_candidates()
            if candidates:
                cookies_path = candidates[0]
                cookies._cleanup_temp_cookiefiles(candidates[1:])

    ydl_opts = build_download_options(
        quality, output_path_no_ext, ffmpeg_bin, [progress_hook], [postprocessor_hook], cookies_path, entry_index, url
    )
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        if "Audio" not in quality:
            ensure_h264(final_output_path, ffmpeg_bin, job_id)
    finally:
        cookies._cleanup_temp_cookiefiles([ydl_opts.get("cookiefile")])
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
        session = config.load_session()
        save_dir = config.resolve_save_dir(session["path"])
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
        ig_candidates = cookies.instagram_cookiefile_candidates()
    if ig_candidates:

        job_id = uuid.uuid4().hex
        jobs.jobs[job_id] = {
            "status": "running", "percent": 0, "text": "Starting...",
            "filename": None, "filepath": None, "cancelled": False,
        }

        def run_instagram():
            try:
                media = instagram.fetch_instagram_media_any(url, ig_candidates)
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
                jobs.jobs[job_id]["filename"] = os.path.basename(final_output_path)
                jobs.jobs[job_id]["filepath"] = final_output_path
                download_direct_url(cdn_url, final_output_path, job_id)
            # In every terminal branch the final text/percent is written BEFORE
            # flipping status off "running", so any observer keying on status
            # (the frontend poll, tests) always reads a fully-updated job.
            except yt_dlp.utils.DownloadCancelled:
                jobs._remove_job_file(job_id)
                jobs.jobs[job_id]["text"] = "Cancelled"
                jobs.jobs[job_id]["status"] = "cancelled"
                return
            except instagram.InstagramAuthError as e:
                jobs._remove_job_file(job_id)
                jobs.jobs[job_id]["text"] = describe_extraction_error(url, e, ig_candidates[0])
                jobs.jobs[job_id]["status"] = "error"
                return
            except Exception as e:
                print(f"[download] job {job_id} (instagram) failed: {e}")
                jobs._remove_job_file(job_id)
                jobs.jobs[job_id]["text"] = str(e) or "Download failed"
                jobs.jobs[job_id]["status"] = "error"
                return
            finally:
                # Media is already resolved (and the CDN download needs no cookies),
                # so the temp session files can go regardless of outcome.
                cookies._cleanup_temp_cookiefiles(ig_candidates)
            jobs.jobs[job_id]["percent"] = 100
            jobs.jobs[job_id]["text"] = f"Saved: {jobs.jobs[job_id]['filename']}"
            jobs.jobs[job_id]["status"] = "done"

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
    jobs.jobs[job_id] = {
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
            if jobs.jobs[job_id]["cancelled"]:
                raise yt_dlp.utils.DownloadCancelled("cancelled by user")
            state["stream_index"] = apply_progress_update(jobs.jobs[job_id], d, state["stream_index"], total_streams)

        def postprocessor_hook(d):
            if jobs.jobs[job_id]["cancelled"]:
                raise yt_dlp.utils.DownloadCancelled("cancelled by user")
            if d.get("status") == "started":
                jobs.jobs[job_id]["text"] = "Finalizing..."

        cookies_path = config.get_cookies_path()
        if url and "instagram" in url.lower():
            if not (cookies_path and config.cookies_status_for(cookies_path) == "valid"):
                candidates = cookies.instagram_cookiefile_candidates()
                if candidates:
                    cookies_path = candidates[0]
                    # Clean up other temporary files immediately
                    cookies._cleanup_temp_cookiefiles(candidates[1:])

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
            jobs.jobs[job_id]["status"] = "cancelled"
            jobs.jobs[job_id]["text"] = "Cancelled"
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
            jobs.jobs[job_id]["status"] = "error"
            jobs.jobs[job_id]["text"] = describe_extraction_error(url, e, cookies_path)
            cleanup_partial_download(output_path_no_ext)
            if remote_temp_dir:
                shutil.rmtree(remote_temp_dir, ignore_errors=True)
            return
        except Exception as e:
            print(f"[download] job {job_id} failed: {e}")
            jobs.jobs[job_id]["status"] = "error"
            jobs.jobs[job_id]["text"] = str(e) or "Download failed"
            cleanup_partial_download(output_path_no_ext)
            if remote_temp_dir:
                shutil.rmtree(remote_temp_dir, ignore_errors=True)
            return
        finally:
            # If build_download_options auto-extracted a browser cookies.txt for
            # Instagram, it's served its purpose once the download call returns.
            cookies._cleanup_temp_cookiefiles([ydl_opts.get("cookiefile")])

        jobs.jobs[job_id]["status"] = "done"
        jobs.jobs[job_id]["percent"] = 100
        jobs.jobs[job_id]["text"] = f"Saved: {final_filename}"

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

    save_dir = config.resolve_save_dir(config.load_session()["path"])
    if save_dir is None:
        return jsonify({"error": "Download folder not writable"}), 400

    ffmpeg_bin = paths.get_ffmpeg_path()
    if not ffmpeg_bin:
        return jsonify({"error": "FFmpeg missing! Run 'brew install ffmpeg'"}), 400

    is_ig_carousel = cls.kind == classify.LinkKind.INSTAGRAM_POST_OR_CAROUSEL

    job_id = uuid.uuid4().hex
    total = len(items)
    jobs.jobs[job_id] = {
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
        prog = jobs.jobs[job_id]["items_progress"]
        state = {"saved": [], "failed": 0}
        media_holder = {"media": None}
        ig_candidates = []
        lock = threading.Lock()

        def recompute_overall():
            # Overall bar = mean of every item's own percent; "item" = how many finished.
            jobs.jobs[job_id]["percent"] = min(100.0, sum(p["percent"] for p in prog) / total)
            jobs.jobs[job_id]["item"] = sum(1 for p in prog if p["status"] in ("done", "error"))

        def download_item(i, item):
            p = prog[i]
            if jobs.jobs[job_id]["cancelled"]:
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
                    jobs.jobs[job_id]["filename"] = os.path.basename(out)
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
                ig_candidates = cookies.instagram_cookiefile_candidates()
                if not ig_candidates:
                    raise instagram.InstagramAuthError("Instagram requires a logged-in session (cookies).")
                media_holder["media"] = instagram.fetch_instagram_media_any(url, ig_candidates)

            # Download BATCH_CONCURRENCY items at once. download_item swallows its
            # own per-item errors, so a future never raises here.
            with ThreadPoolExecutor(max_workers=min(BATCH_CONCURRENCY, total)) as ex:
                futures = [ex.submit(download_item, i, item) for i, item in enumerate(items)]
                for f in futures:
                    f.result()
        except Exception as e:
            # Only a pre-flight failure (e.g. Instagram auth before the pool starts).
            print(f"[batch] job {job_id} failed: {e}")
            cookies._cleanup_temp_cookiefiles(ig_candidates)
            jobs.jobs[job_id]["text"] = describe_extraction_error(url, e) if is_ig_carousel else (str(e) or "Download failed")
            jobs.jobs[job_id]["status"] = "error"
            return

        cookies._cleanup_temp_cookiefiles(ig_candidates)
        saved, failed = state["saved"], state["failed"]
        if jobs.jobs[job_id]["cancelled"]:
            jobs.jobs[job_id]["text"] = f"Cancelled (saved {len(saved)} of {total})"
            jobs.jobs[job_id]["status"] = "cancelled"
            return
        jobs.jobs[job_id]["percent"] = 100
        jobs.jobs[job_id]["saved_count"] = len(saved)
        if not saved:
            jobs.jobs[job_id]["text"] = "Could not download any item"
            jobs.jobs[job_id]["status"] = "error"
            return
        jobs.jobs[job_id]["filename"] = saved[-1]
        jobs.jobs[job_id]["text"] = f"Saved {len(saved)} of {total} videos" + (f" ({failed} failed)" if failed else "")
        jobs.jobs[job_id]["status"] = "done"

    threading.Thread(target=run_batch, daemon=True).start()
    return jsonify({"job_id": job_id})


@app.get("/api/progress/<job_id>")
def progress(job_id):
    job = jobs.jobs.get(job_id)
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
    job = jobs.jobs.get(job_id)
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
    job = jobs.jobs.get(job_id)
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
    subprocess.run(["open", config.load_session()["path"]])
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="127.0.0.1", port=port, threaded=True)
