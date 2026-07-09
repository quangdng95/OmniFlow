"""The download engine - yt-dlp options, H.264 enforcement, progress math,
filename hygiene, and the two low-level downloaders (yt-dlp + direct CDN).
"""

import os
import re
import subprocess
import time
import urllib.request

import yt_dlp

from backend import config, cookies, extraction, instagram, jobs


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


def combined_download_percent(stream_index, raw_percent, total_streams):
    return min(100.0, (stream_index * 100 + raw_percent) / total_streams)


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


def _fetch_formats_for_quality_resolution(url, cookies_path, entry_index):
    # A lightweight metadata-only lookup so build_download_options can map a
    # quality label (e.g. "1080p") to the raw pixel height that label
    # actually means for THIS media (extraction.resolve_quality_height) -
    # without it, a request for "1080p" on a non-16:9 source could silently
    # download a different real quality than what the platform itself calls
    # 1080p. Best-effort: any failure here just means the label's own number
    # gets treated as a literal height ceiling, same as before per-label
    # resolution existed.
    opts = {"quiet": True, "no_warnings": True}
    if entry_index:
        opts["noplaylist"] = False
        opts["playlist_items"] = str(entry_index)
    else:
        opts["noplaylist"] = True
    if url and "instagram" in url.lower():
        opts["http_headers"] = {"User-Agent": instagram.INSTAGRAM_UA}
    if cookies_path:
        opts["cookiefile"] = cookies_path
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return []
    if not info:
        return []
    if info.get("entries"):
        entries = [e for e in info["entries"] if e]
        info = entries[0] if entries else info
    return info.get("formats") or []


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
        if quality == "Best":
            # No cap at all - always the single highest-resolution stream
            # available, whatever that is. (Hardcoding a "2160" ceiling here
            # used to silently exclude anything above 4K and, worse, was in
            # the same raw-pixel-height space that can be smaller than a
            # non-16:9 source's true top label - see resolve_quality_height.)
            height_filter = ""
        else:
            # Map the label (e.g. "1080p") to the raw pixel height that
            # label actually means for THIS media, not just its number - a
            # non-16:9 (e.g. ultrawide/letterboxed) source's real "1080p"
            # can have a raw height far from 1080, and using the number
            # directly either misses that tier or lets a higher tier through
            # unintentionally. Falls back to the literal number when the
            # lookup fails or the source has no format_note to match against.
            formats = _fetch_formats_for_quality_resolution(url, cookies_path, entry_index)
            resolved_height = extraction.resolve_quality_height(formats, quality)
            height_filter = f"[height<={resolved_height}]" if resolved_height else ""
        # Prefer H.264 (avc1) video + AAC (m4a) audio when it doesn't cost
        # resolution. macOS (Finder QuickLook / QuickTime) cannot decode VP9
        # or AV1 inside an .mp4 - such a file opens as a black/white screen
        # even though the download "succeeded" - so a hard `[vcodec^=avc1]`
        # filter used to sit in front of every alternative below. That was a
        # real bug: yt-dlp's "A/B/C" selector commits to the FIRST
        # alternative that matches ANYTHING, so as soon as any avc1 format
        # existed at all under the height cap it won - even a far lower
        # resolution than what was actually available. YouTube commonly only
        # ships avc1 up to 1080p, so picking "Best"/1440p/2160p silently
        # downgraded to whatever the highest avc1 tier happened to be instead
        # of the true best. Codec preference now lives only in format_sort as
        # a tie-break (res ranked first), so the true highest resolution
        # within the requested cap always wins; a VP9/AV1 pick that slips
        # through is still caught afterward by the ensure_h264() re-encode
        # safety net in run().
        opts["format"] = (
            f"bestvideo{height_filter}+bestaudio[ext=m4a]/"
            f"bestvideo{height_filter}+bestaudio/"
            f"best{height_filter}/"
            f"best"
        )
        opts["format_sort"] = ["res", "vcodec:h264", "acodec:m4a"]
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
