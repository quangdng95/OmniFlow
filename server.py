import os, json, re, subprocess, tempfile, threading, uuid, shutil
import yt_dlp
from flask import Flask, request, jsonify, send_from_directory, send_file, after_this_request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "frontend", "dist")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

app = Flask(__name__, static_folder=WEB_DIR, static_url_path="")

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


def resource_path(relative_path):
    return os.path.join(BASE_DIR, relative_path)


def get_ffmpeg_path():
    local_ffmpeg = resource_path("ffmpeg")
    if os.path.exists(local_ffmpeg) and os.access(local_ffmpeg, os.X_OK):
        return local_ffmpeg
    return shutil.which("ffmpeg")


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


def get_platform_info(url):
    url_lower = url.lower()
    if "youtube" in url_lower or "youtu.be" in url_lower: return "YouTube"
    if "instagram" in url_lower: return "Instagram"
    if "tiktok" in url_lower: return "TikTok"
    if "facebook.com" in url_lower or "fb.watch" in url_lower: return "Facebook"
    # "RedNote" is Xiaohongshu's international rebrand - links can come from
    # either the classic domains or the newer rednote.com one.
    if "xiaohongshu" in url_lower or "xhslink" in url_lower or "rednote" in url_lower: return "RedNote"
    return "Link"


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
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                path_val = data.get("path", default_path)
                cookies_path_val = data.get("cookies_path", "")
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
        save_session(path_val, cookies_path_val)

    return {"path": path_val, "cookies_path": cookies_path_val}


def save_session(path_val, cookies_path_val=""):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"path": path_val, "cookies_path": cookies_path_val}, f)


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
    return send_from_directory(WEB_DIR, "index.html")


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
    save_session(path_val, cookies_path_val)
    return jsonify({
        "path": path_val,
        "cookies_path": cookies_path_val,
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


def extract_video_info(url):
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
        "noplaylist": True,
        "socket_timeout": 30,
    }
    cookies_path = get_cookies_path()
    if cookies_path:
        ydl_opts["cookiefile"] = cookies_path
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


def describe_extraction_error(url, error, cookies_path=None):
    message = str(error)
    lower = message.lower()
    # Instagram increasingly requires a logged-in session even for posts that
    # look public in a browser - yt-dlp's own message is accurate but full of
    # CLI-specific advice (--cookies-from-browser, GitHub issue templates)
    # that doesn't apply to this app, so replace it with a plain explanation.
    # yt-dlp's InstagramIE only ever takes this path when it found no usable
    # "sessionid" cookie for instagram.com (confirmed directly from its
    # extractor source), so the message is tailored to exactly what's missing:
    # no cookies file at all, a cookies file without a session in it, or a
    # session that Instagram itself rejected (expired/invalid).
    # Every one of the extractor's several distinct login-required messages
    # ("empty media response", "registered users who follow this account",
    # "Restricted Video", "rate-limit reached or login required", ...) is
    # raised via the shared raise_login_required() helper, which always
    # appends a "Use --cookies..." hint - checking for "cookies" instead of
    # trying to match every individual message wording is what actually
    # catches all of them (confirmed against a real "registered users" error
    # from a real private post, which contains neither "empty media
    # response" nor the literal word "login").
    if "instagram" in url.lower() and (
        "empty media response" in lower or "login" in lower or "cookies" in lower
    ):
        if not cookies_path:
            return (
                "This Instagram post requires a logged-in session and can't be checked anonymously. "
                "Try a public YouTube, TikTok, Facebook, or RedNote link instead, or add an Instagram "
                "cookies file in Settings."
            )
        if not cookies_file_has_instagram_session(cookies_path):
            return (
                "The Instagram cookies file configured in Settings doesn't look like it contains a "
                "logged-in session. Re-export cookies.txt while logged into instagram.com in your browser."
            )
        return (
            "Your Instagram session looks expired or invalid. Export a fresh cookies.txt while logged "
            "into instagram.com and update it in Settings."
        )
    message = message.removeprefix("ERROR: ")
    first_sentence = message.split(". ")[0].strip()
    return first_sentence or "Invalid link or private video"


INSTAGRAM_LOCAL_ONLY_ERROR = "Instagram downloads are only available when running OmniFlow locally on your own machine."


@app.post("/api/check")
def check_link():
    data = request.get_json(force=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "Missing url"}), 400

    # Instagram only works with a cookies.txt file configured in Settings, and
    # that config is a single, machine-wide setting (see get_cookies_path) -
    # not per-visitor. Without this check, a remote visitor's Instagram
    # request would silently succeed using the local owner's own live
    # session, burning their account's rate limits/ban risk on a stranger's
    # request. Reject it outright instead of letting it "just fail" on its
    # own, since it might not fail at all if the owner has cookies configured.
    if get_platform_info(url) == "Instagram" and not is_local_request():
        return jsonify({"error": INSTAGRAM_LOCAL_ONLY_ERROR}), 403

    try:
        info = extract_video_info(url)
    except yt_dlp.utils.DownloadError as e:
        return jsonify({"error": describe_extraction_error(url, e, get_cookies_path())}), 400
    except Exception:
        return jsonify({"error": "Invalid link or private video"}), 400

    if not info:
        return jsonify({"error": "Invalid link or private video"}), 400

    res_set = set()
    for f in info.get("formats", []):
        h = f.get("height")
        if h and isinstance(h, int) and h >= 360:
            res_set.add(h)
    qualities = [f"{h}p" for h in sorted(res_set, reverse=True)]
    qualities.append("Best")
    qualities.append("Audio Only")

    duration = info.get("duration")
    duration_text = None
    if isinstance(duration, (int, float)):
        minutes, seconds = divmod(int(duration), 60)
        duration_text = f"{minutes:02d}:{seconds:02d}"

    return jsonify({
        "title": info.get("title", "Video"),
        "uploader": info.get("uploader", ""),
        "thumbnail": resolve_thumbnail(info),
        "platform": get_platform_info(url),
        "qualities": qualities,
        "duration": duration_text,
    })


def build_download_options(quality, output_path_no_ext, ffmpeg_bin, progress_hooks, postprocessor_hooks, cookies_path=None):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "outtmpl": output_path_no_ext + ".%(ext)s",
        "ffmpeg_location": ffmpeg_bin,
        "progress_hooks": progress_hooks,
        "postprocessor_hooks": postprocessor_hooks,
        "socket_timeout": 30,
    }
    if cookies_path:
        opts["cookiefile"] = cookies_path
    if "Audio" in quality:
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}]
    else:
        h = quality.replace("p", "").replace("Best", "2160")
        opts["format"] = f"bestvideo[height<={h}]+bestaudio/best[height<={h}]/best"
        opts["format_sort"] = ["vcodec:h264", f"res:{h}"]
        # Remux only (fast container copy) instead of forcing a full re-encode -
        # ~3.5x faster since the source is already h264/aac-compatible most of the time.
        opts["postprocessors"] = [{"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}]
        opts["postprocessor_args"] = {"ffmpeg": ["-movflags", "+faststart"]}
    return opts


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


@app.post("/api/download")
def start_download():
    data = request.get_json(force=True) or {}
    url = (data.get("url") or "").strip()
    title = data.get("title") or "Video"
    quality = data.get("quality") or "Best"
    if not url:
        return jsonify({"error": "Missing url"}), 400

    if get_platform_info(url) == "Instagram" and not is_local_request():
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

    ffmpeg_bin = get_ffmpeg_path()
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

        ydl_opts = build_download_options(
            quality, output_path_no_ext, ffmpeg_bin, [progress_hook], [postprocessor_hook], get_cookies_path()
        )

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except yt_dlp.utils.DownloadCancelled:
            jobs[job_id]["status"] = "cancelled"
            jobs[job_id]["text"] = "Cancelled"
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

        jobs[job_id]["status"] = "done"
        jobs[job_id]["percent"] = 100
        jobs[job_id]["text"] = f"Saved: {final_filename}"

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"job_id": job_id})


@app.get("/api/progress/<job_id>")
def progress(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404
    return jsonify({"status": job["status"], "percent": job["percent"], "text": job["text"], "filename": job["filename"]})


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
