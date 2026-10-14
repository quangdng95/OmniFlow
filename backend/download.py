"""The download engine - yt-dlp options, H.264 enforcement, progress math,
filename hygiene, and the two low-level downloaders (yt-dlp + direct CDN).
"""

import datetime
import os
import platform
import re
import subprocess
import tempfile
import threading
import time
import urllib.request

import yt_dlp

from backend import classify, config, cookies, extraction, instagram, jobs

# True only in the remote_web (cloud) process. A 1 GB / shared-vCPU VM can't
# afford libx264-re-encoding a 1080p AV1/VP9 source (minutes at 100% CPU that
# starve every other request - docs/internal/MISTAKES.md 2026-09-25), so there we take a
# native H.264 stream even at a lower resolution. The desktop app leaves this
# False: resolution first, ensure_h264() re-encodes the rare straggler.
AVOID_REENCODE = False


# macOS (APFS/HFS+) caps a single path component at 255 UTF-8 bytes. A video
# title is usually short, but a caption-as-title source (TikTok Photo Mode's
# item title is its full post caption - confirmed live, docs/internal/MISTAKES.md
# 2026-08-28) can run to 1000+ characters, and get_unique_filename's own
# collision check (os.path.exists) does NOT error on an over-long name -
# only the actual write does, so this must be enforced here, at the source,
# not left for get_unique_filename's collision-suffix math to trip over.
# 200 leaves headroom for the extension and a " (N)" collision suffix.
_MAX_FILENAME_BYTES = 200
# A multi-item post's per-item titles only differ in a short suffix
# (backend.instagram.instagram_check_response numbers them "{caption} (1)",
# "{caption} (2)", ...) - truncating from the head alone collapses every
# item to the same name once the shared prefix alone exceeds the byte cap,
# which silently clobbers files in a parallel batch download (confirmed
# live, docs/internal/MISTAKES.md 2026-08-28: 4 images saved as 2 files). Keeping the tail
# too preserves that differentiator.
_TAIL_BYTES = 24


def sanitize_filename(name):
    # A caption used as a title can carry links, line breaks and emoji: drop the links (a stripped link only
    # leaves junk like "httpslnkd.indxyKfFfM"), turn every line break/control character into a space, then
    # remove what the filesystems refuse and tidy the spaces.
    name = re.sub(r"https?://[^\s)\]>]+", "", name or "")
    name = re.sub(r"[\x00-\x1f\x7f\u2028\u2029]+", " ", name)
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"\(\s*\)", "", name)  # empty brackets left behind by a removed link
    name = re.sub(r"\s+", " ", name).strip().rstrip("…").rstrip() or "Download"
    encoded = name.encode("utf-8")
    if len(encoded) <= _MAX_FILENAME_BYTES:
        return name
    # decode(errors="ignore") already drops a dangling multi-byte sequence
    # split by the slice boundary (a stray leading/trailing continuation
    # byte just decodes to nothing) - no manual boundary-walking needed.
    head = encoded[: _MAX_FILENAME_BYTES - _TAIL_BYTES].decode("utf-8", errors="ignore")
    tail = encoded[-_TAIL_BYTES:].decode("utf-8", errors="ignore")
    return (head + tail).strip()


def get_unique_filename(directory, filename, extension):
    base_name = sanitize_filename(filename)
    full_path = os.path.join(directory, f"{base_name}.{extension}")
    counter = 1
    while os.path.exists(full_path):
        full_path = os.path.join(directory, f"{base_name} ({counter}).{extension}")
        counter += 1
    return full_path


_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}


def sniff_image_extension(path):
    # The extension an image file's own bytes call for, or None if it is not a
    # recognisable image (or unreadable).
    try:
        with open(path, "rb") as f:
            head = f.read(12)
    except OSError:
        return None
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith(b"GIF8"):
        return "gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def fix_image_extension(path):
    # Rename a downloaded image so its extension matches its real format (a
    # LinkedIn document page is a PNG but was saved as ".jpg" because the name
    # was picked from the item kind alone). Never overwrites: the new name goes
    # through get_unique_filename. Non-images and unrecognised files are untouched.
    stem, ext = os.path.splitext(path)
    current = ext.lstrip(".").lower()
    if current not in _IMAGE_EXTENSIONS:
        return path
    real = sniff_image_extension(path)
    if real is None or real == ("jpg" if current in ("jpg", "jpeg") else current):
        return path
    fixed = get_unique_filename(os.path.dirname(path), os.path.basename(stem), real)
    os.replace(path, fixed)
    return fixed


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
    opts = {"quiet": True, "no_warnings": True, "remote_components": {"ejs:github"}}
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
    quality, output_path_no_ext, ffmpeg_bin, progress_hooks, postprocessor_hooks, cookies_path=None, entry_index=None, url=None, keep_codec=False
):
    # keep_codec=True (video only): keep whatever codec the platform serves (VP9/AV1 for 4K)
    # and just merge it into an .mkv - no re-encode at all, the fastest result. The file may
    # not open in QuickTime / on an iPhone, which is why it is an explicit opt-in.
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
        # See the matching comment in extraction.py - required for an
        # authenticated YouTube download to find real format URLs at all.
        "remote_components": {"ejs:github"},
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
        video_format = (
            f"bestvideo{height_filter}+bestaudio[ext=m4a]/"
            f"bestvideo{height_filter}+bestaudio/"
            f"best{height_filter}/"
            f"best"
        )
        if AVOID_REENCODE and not keep_codec:
            # Native H.264 first. Facebook serves its 1080p tier as AV1 only,
            # but always also offers muxed H.264 `hd` (720p) / `sd` files whose
            # codec yt-dlp reports as unknown, so they can't be matched by a
            # vcodec filter and have to be named by format id.
            native_h264 = f"bestvideo[vcodec^=avc1]{height_filter}+bestaudio[ext=m4a]/"
            if classify.get_platform_info(url or "") == "Facebook":
                native_h264 += "hd/sd/"
            video_format = native_h264 + video_format
        opts["format"] = video_format
        opts["format_sort"] = ["res", "vcodec:h264", "acodec:m4a"]
        # PRD §7: merge straight into an mp4 container. Because the selector above
        # already lands H.264 video + m4a audio in the common case, both the merge
        # and the FFmpegVideoRemuxer are a fast stream-COPY (`-c copy`) - NO
        # re-encode, which is what was making "combine" slow before. The remuxer
        # also normalizes any single-file (non-merged) result to .mp4 so the saved
        # extension is predictable. The rare VP9/AV1 straggler that a copy can't
        # make macOS-playable is caught afterward by ensure_h264() in run().
        if keep_codec:
            opts["merge_output_format"] = "mkv"
        else:
            opts["merge_output_format"] = "mp4"
            opts["postprocessors"] = [{"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}]
    return opts


# Video codecs macOS' native stack (Finder QuickLook / QuickTime) can't play
# when muxed into an .mp4 - the download looks fine but the file is unwatchable.
MACOS_INCOMPATIBLE_VCODECS = ("vp9", "vp09", "vp8", "av01", "av1")


# How many H.264 re-encodes may run at once. A 4K encode saturates the CPU (or the
# hardware encoder), so two at a time is plenty on a Mac; remote_web sets this to 1
# because its VM has one shared vCPU (see remote_web/app.py).
ENCODE_SLOTS = threading.BoundedSemaphore(2)


# A 4K conversion on a small shared VM can run for ages and starve everything else; remote_web
# sets this (15 minutes). None = no limit (the desktop app).
ENCODE_TIMEOUT_SECONDS = None


class EncodeTimeoutError(Exception):
    """The H.264 conversion ran longer than ENCODE_TIMEOUT_SECONDS and was stopped."""


def set_encode_timeout(seconds):
    global ENCODE_TIMEOUT_SECONDS
    ENCODE_TIMEOUT_SECONDS = seconds


def set_encode_concurrency(n):
    global ENCODE_SLOTS
    ENCODE_SLOTS = threading.BoundedSemaphore(max(1, int(n)))


def probe_media(path, ffmpeg_bin):
    # Parses `ffmpeg -i` stderr (no ffprobe dependency). Returns a dict with
    # vcodec, acodec, width, height, fps and duration (seconds); a missing value is None.
    info = {"vcodec": None, "acodec": None, "width": None, "height": None, "fps": None, "duration": None}
    try:
        result = subprocess.run(
            [ffmpeg_bin, "-hide_banner", "-i", path],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return info
    for line in result.stderr.splitlines():
        if "Duration:" in line and info["duration"] is None:
            m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", line)
            if m:
                info["duration"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        elif "Video:" in line and info["vcodec"] is None:
            m = re.search(r"Video:\s*([A-Za-z0-9_]+)", line)
            if m:
                info["vcodec"] = m.group(1).lower()
            m = re.search(r"\b(\d{2,5})x(\d{2,5})\b", line.split("Video:", 1)[1])
            if m:
                info["width"], info["height"] = int(m.group(1)), int(m.group(2))
            m = re.search(r"([\d.]+)\s*fps", line)
            if m:
                info["fps"] = float(m.group(1))
        elif "Audio:" in line and info["acodec"] is None:
            m = re.search(r"Audio:\s*([A-Za-z0-9_]+)", line)
            if m:
                info["acodec"] = m.group(1).lower()
    return info


def detect_video_codec(path, ffmpeg_bin):
    # Returns the video stream's codec name (lowercased) for `path`, or None if
    # it can't be determined.
    return probe_media(path, ffmpeg_bin)["vcodec"]


_VT_CACHE = {}


def videotoolbox_available(ffmpeg_bin):
    # True only on macOS, when this very ffmpeg build lists the h264_videotoolbox
    # encoder. Cached per binary: `ffmpeg -encoders` is cheap but not free.
    if platform.system() != "Darwin":
        return False
    if ffmpeg_bin not in _VT_CACHE:
        try:
            out = subprocess.run([ffmpeg_bin, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=30).stdout
            _VT_CACHE[ffmpeg_bin] = "h264_videotoolbox" in out
        except (OSError, subprocess.SubprocessError):
            _VT_CACHE[ffmpeg_bin] = False
    return _VT_CACHE[ffmpeg_bin]


# Measured 2026-10-13 on a 3:58-5:00 4K VP9 clip (docs/internal/session.md): the Mac hardware encoder
# runs at a fixed ~60 fps for 4K whatever the options, while libx264 veryfast scales with the
# cores - 127 fps on a 14-core M4 Pro (faster than hardware), a few times slower on a dual-core
# 2017 Intel MacBook. So hardware wins on small CPUs and software on big ones; the cut is 8 logical cores.
HARDWARE_ENCODER_MAX_CPUS = 8


def hardware_encoder_decision(cpu_count=None, override=None, machine=None):
    # Returns (use_hardware, reason). VIDROP_H264_ENCODER=videotoolbox|libx264 forces one (also in the
    # packaged app: `VIDROP_H264_ENCODER=libx264 open -a ViDrop`). Otherwise: always on an x86_64
    # process (an Intel Mac, or the Intel build under Rosetta where libx264 runs emulated: 4K took
    # 178 s with libx264 vs 135 s with VideoToolbox on an M4 Pro), and on Apple Silicon only for
    # small CPUs.
    env = os.environ.get("VIDROP_H264_ENCODER", "")
    forced = (override if override is not None else env).strip().lower()
    if forced in ("videotoolbox", "libx264"):
        return forced == "videotoolbox", f"forced by VIDROP_H264_ENCODER={forced}"
    if (machine if machine is not None else platform.machine()) == "x86_64" and override in (None, ""):
        return True, "x86_64 process (Intel Mac or Rosetta)"
    cpus = cpu_count if cpu_count is not None else (os.cpu_count() or 1)
    if cpus <= HARDWARE_ENCODER_MAX_CPUS:
        return True, f"{cpus} logical cores <= {HARDWARE_ENCODER_MAX_CPUS}"
    return False, f"{cpus} logical cores > {HARDWARE_ENCODER_MAX_CPUS}, software encoding is faster"


def prefer_hardware_encoder(cpu_count=None, override=None, machine=None):
    return hardware_encoder_decision(cpu_count, override, machine)[0]


def choose_video_action(vcodec, can_videotoolbox):
    # What to do with a finished download's video stream so it plays in QuickTime:
    #   "copy"         already H.264 (or unknown) - leave the file alone (the remux already happened)
    #   "videotoolbox" VP9/AV1/... on a Mac whose ffmpeg has the hardware encoder (and the caller
    #                  judged it worth using - see prefer_hardware_encoder)
    #   "libx264"      VP9/AV1/... anywhere else (veryfast software encode)
    if not vcodec or not any(vcodec.startswith(bad) for bad in MACOS_INCOMPATIBLE_VCODECS):
        return "copy"
    return "videotoolbox" if can_videotoolbox else "libx264"


def videotoolbox_bitrate_kbps(width, height, fps):
    # Hardware encoders have no CRF, so give them a bitrate that keeps 4K sharp:
    # about 25 Mbps for 2160p30, 16 for 1440p, 10 for 1080p, 5 below that, x1.4 for 50/60 fps.
    px = (width or 0) * (height or 0)
    if px >= 3840 * 2160 * 0.9 or (height or 0) >= 2000 or (width or 0) >= 3600:
        base = 25000
    elif px >= 2560 * 1440 * 0.9:
        base = 16000
    elif px >= 1920 * 1080 * 0.9:
        base = 10000
    else:
        base = 5000
    if fps and fps > 35:
        base = int(base * 1.4)
    return base


def build_h264_command(action, ffmpeg_bin, path, tmp_out, probe):
    # The full ffmpeg command line for the chosen re-encode. yuv420p 8-bit is the
    # profile QuickTime decodes (some VP9/AV1 sources are 10-bit). Audio is
    # copied when it is already AAC, otherwise encoded to AAC.
    cmd = [ffmpeg_bin, "-y", "-hide_banner", "-nostats", "-progress", "pipe:1", "-i", path, "-map", "0:v:0", "-map", "0:a?"]
    if action == "videotoolbox":
        kbps = videotoolbox_bitrate_kbps(probe.get("width"), probe.get("height"), probe.get("fps"))
        cmd += ["-c:v", "h264_videotoolbox", "-b:v", f"{kbps}k", "-maxrate", f"{int(kbps * 1.5)}k",
                "-profile:v", "high", "-allow_sw", "1", "-tag:v", "avc1"]
    else:
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-profile:v", "high"]
    cmd += ["-pix_fmt", "yuv420p"]
    cmd += ["-c:a", "copy"] if probe.get("acodec") == "aac" else ["-c:a", "aac", "-b:a", "192k"]
    cmd += ["-movflags", "+faststart", "-f", "mp4", tmp_out]
    return cmd


def ensure_h264(path, ffmpeg_bin, job_id):
    # Guarantees the finished video is macOS-playable H.264. An already-H.264
    # file is only probed (no re-encode). A VP9/AV1 file is re-encoded: with the
    # Mac's hardware encoder when this ffmpeg has it (several times faster than
    # software, and the only thing that keeps a 4K clip tolerable on an older
    # Intel Mac), otherwise - or if the hardware encode fails - with libx264
    # veryfast. Honors the cooperative cancel flag. Progress goes to the job as
    # `encode_percent` (from ffmpeg's -progress output) and a readable `text`.
    probe = probe_media(path, ffmpeg_bin)
    vt_present = videotoolbox_available(ffmpeg_bin)
    use_hw, hw_reason = hardware_encoder_decision()
    action = choose_video_action(probe["vcodec"], vt_present and use_hw)
    if action == "copy":
        reason = "source is not VP9/AV1 (already plays in QuickTime)"
    elif action == "videotoolbox":
        reason = hw_reason
    else:
        reason = "no VideoToolbox encoder in this ffmpeg or OS" if not vt_present else hw_reason
    job = jobs.jobs[job_id]
    perf = job.setdefault("perf", {})
    perf.update({"src_codec": probe["vcodec"], "width": probe["width"], "height": probe["height"], "encoder": action, "reason": reason, "encode_s": 0.0})
    if action == "copy":
        return action
    with ENCODE_SLOTS:
        for attempt_action in ([action, "libx264"] if action == "videotoolbox" else [action]):
            tmp_out = path + ".h264.mp4"
            cmd = build_h264_command(attempt_action, ffmpeg_bin, path, tmp_out, probe)
            job["stage"] = "encoding"
            job["encode_percent"] = 0
            job["text"] = "Converting to H.264 for macOS..."
            ok, err = _run_ffmpeg_replacing(cmd, tmp_out, path, job_id, probe.get("duration"))
            perf["encode_s"] = round(perf["encode_s"] + job.get("encode_seconds", 0), 1)
            if ok:
                perf["encoder"] = attempt_action
                return attempt_action
            from backend import paths
            perf["encoder"] = "libx264" if attempt_action == "videotoolbox" else "failed"
            perf["reason"] = reason + (f"; {attempt_action} failed" if attempt_action != "libx264" or action == "videotoolbox" else "")
            paths.log_exception(
                f"ensure_h264: {attempt_action} encode failed"
                + (", falling back to libx264 veryfast" if attempt_action == "videotoolbox" else ", keeping the original file"),
                RuntimeError(err or "ffmpeg exited with an error"),
            )
    return perf["encoder"]


def _run_ffmpeg_replacing(cmd, tmp_out, path, job_id, duration=None):
    # Runs an ffmpeg command whose last argument is `tmp_out` (and which was given
    # `-progress pipe:1`), honoring the cooperative cancel flag, and swaps `tmp_out`
    # over `path` on success. Returns (ok, last stderr lines). On failure the
    # original file is kept and the temp output is removed, so a failed conversion
    # never leaves a truncated file behind.
    job = jobs.jobs[job_id]
    started = time.time()
    with tempfile.TemporaryFile() as err_file:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err_file, text=True)

        def read_progress():
            for line in proc.stdout:
                if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
                    try:
                        done = int(line.split("=", 1)[1]) / 1_000_000
                    except ValueError:
                        continue
                    if duration and done >= 0:
                        pct = min(99, int(done / duration * 100))
                        job["encode_percent"] = pct
                        job["text"] = f"Converting to H.264... ({pct}%)"

        reader = threading.Thread(target=read_progress, daemon=True)
        reader.start()
        while proc.poll() is None:
            timed_out = ENCODE_TIMEOUT_SECONDS is not None and time.time() - started > ENCODE_TIMEOUT_SECONDS
            if job["cancelled"] or timed_out:
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
                if timed_out and not job["cancelled"]:
                    raise EncodeTimeoutError(f"conversion stopped after {ENCODE_TIMEOUT_SECONDS} s")
                raise yt_dlp.utils.DownloadCancelled("cancelled by user")
            time.sleep(0.3)
        reader.join(timeout=2)
        err_file.seek(0)
        err_tail = " | ".join(err_file.read().decode("utf-8", "replace").strip().splitlines()[-3:])
    job["encode_seconds"] = round(time.time() - started, 1)
    if proc.returncode == 0 and os.path.exists(tmp_out):
        os.replace(tmp_out, path)
        job["encode_percent"] = 100
        return True, ""
    if os.path.exists(tmp_out):
        # Conversion failed - keep the original (still-playable-elsewhere) file
        # rather than leaving a truncated temp output behind.
        try:
            os.remove(tmp_out)
        except OSError:
            pass
    return False, err_tail


# Audio codecs iOS / QuickTime can't decode inside an .mp4. MP3-in-MP4 is the
# one that actually happens: TikTok serves its 1080p/720p H.265 tiers
# video-only, so yt-dlp merges them with TikTok's separate `audio` format,
# which is MP3 (2026-09-30) - the saved file then shows picture with no sound.
APPLE_INCOMPATIBLE_ACODECS = ("mp3", "opus", "vorbis", "flac")


def detect_audio_codec(path, ffmpeg_bin):
    # Returns the first audio stream's codec name (lowercased) for `path`, or
    # None if there is none / it can't be determined. Same `ffmpeg -i` stderr
    # parse as detect_video_codec (no ffprobe dependency).
    try:
        result = subprocess.run(
            [ffmpeg_bin, "-hide_banner", "-i", path],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    for line in result.stderr.splitlines():
        if "Audio:" in line:
            m = re.search(r"Audio:\s*([A-Za-z0-9_]+)", line)
            if m:
                return m.group(1).lower()
    return None


def ensure_apple_audio(path, ffmpeg_bin, job_id):
    # Guarantees the finished video's sound is playable on iPhone/macOS. Only
    # re-encodes when the audio positively is a codec Apple can't decode in an
    # mp4 (see APPLE_INCOMPATIBLE_ACODECS); the picture is stream-copied, so
    # this is a couple of seconds even for a long 1080p file. A fast probe and
    # return for the usual AAC case. Honors the same cancel flag as the rest.
    codec = detect_audio_codec(path, ffmpeg_bin)
    if not codec or codec not in APPLE_INCOMPATIBLE_ACODECS:
        return
    jobs.jobs[job_id]["text"] = "Converting audio for iPhone/macOS..."
    tmp_out = path + ".aac.mp4"
    cmd = [
        ffmpeg_bin, "-y", "-hide_banner", "-nostats", "-progress", "pipe:1", "-i", path,
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", "-f", "mp4", tmp_out,
    ]
    _run_ffmpeg_replacing(cmd, tmp_out, path, job_id)


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
        job.setdefault("t_first_dl", time.time())
        total = progress_dict.get("total_bytes") or progress_dict.get("total_bytes_estimate")
        downloaded = progress_dict.get("downloaded_bytes") or 0
        if total:
            raw_percent = downloaded / total * 100
            combined = combined_download_percent(stream_index, raw_percent, total_streams)
            job["percent"] = combined
            job["text"] = f"Downloading... ({combined:.1f}%)"
    elif status == "finished":
        job["t_dl_end"] = time.time()
        stream_index = min(stream_index + 1, total_streams - 1)
    return stream_index


def cleanup_partial_download(output_path_no_ext, final_path=None):
    """Remove what a failed or cancelled yt-dlp download left in the save folder.

    Deletes only this download's own temporary files - the separate video/audio
    streams (`Title.f137.mp4`), `.part` / `.ytdl` / `.temp.*` files - plus, when
    given, the exact `final_path`. It never matches by name prefix alone: a plain
    `startswith` also swept up other files the user kept, such as `Title 2.mp4`.
    """
    directory = os.path.dirname(output_path_no_ext) or "."
    stem = re.escape(os.path.basename(output_path_no_ext))
    # yt-dlp names a separate stream `Title.f<format id>.<ext>`: the id is digits
    # (`f137`, `f251-drc`) or a protocol word (`fhls-720p`, `fhttp-2176`, `fdash-1`).
    stream = r"\.f(?:\d[0-9A-Za-z-]*|hls-[0-9A-Za-z-]+|http-[0-9A-Za-z-]+|dash-[0-9A-Za-z-]+)\.[A-Za-z0-9]+"
    temporary = re.compile(
        rf"^{stem}(?:{stream}|\.temp\.[A-Za-z0-9]+|\.[A-Za-z0-9]+)?(?:\.part|\.ytdl)$"
        rf"|^{stem}{stream}$"
        rf"|^{stem}\.temp\.[A-Za-z0-9]+$"
    )
    try:
        for name in os.listdir(directory):
            if temporary.match(name):
                try:
                    os.remove(os.path.join(directory, name))
                except OSError:
                    pass
    except OSError:
        pass
    if final_path:
        try:
            os.remove(final_path)
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

    auto_cookiefiles = [cookies_path]

    def attempt(cookiefile):
        ydl_opts = build_download_options(
            quality, output_path_no_ext, ffmpeg_bin, [progress_hook], [postprocessor_hook], cookiefile, entry_index, url
        )
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    try:
        # A YouTube login/anti-bot answer gets one retry with the configured
        # browser profile's cookies (cookies.run_with_youtube_cookie_fallback).
        cookies.run_with_youtube_cookie_fallback(url, cookies_path, attempt)
        if "Audio" not in quality:
            ensure_h264(final_output_path, ffmpeg_bin, job_id)
            ensure_apple_audio(final_output_path, ffmpeg_bin, job_id)
    except BaseException:
        # A failed or cancelled item must not leave half a download (a video-only
        # .f137.mp4, a .part file) in the user's save folder.
        cleanup_partial_download(output_path_no_ext, final_output_path)
        raise
    finally:
        cookies._cleanup_temp_cookiefiles(auto_cookiefiles)
    return final_output_path


def _short_url(url):
    # host + path only: no query string (tracking ids, tokens), no fragment, at most 60 characters.
    try:
        from urllib.parse import urlsplit

        parts = urlsplit(url or "")
        return ((parts.hostname or "") + parts.path)[:60]
    except ValueError:
        return ""


def write_perf_log(job_id, url, quality, keep_codec, final_path):
    # One line per finished download in <LOG_DIR>/perf.log (~/Library/Logs/ViDrop/perf.log in the
    # app): when, short link, source codec, resolution, the encoder chosen and why, logical cores,
    # and the time of each stage. Best effort - a logging failure never touches the download.
    # No cookies, no tokens, no query strings.
    try:
        from backend import paths

        job = jobs.jobs[job_id]
        perf = job.get("perf", {})
        now = time.time()
        t0 = job.get("t_start") or now
        t_first = job.get("t_first_dl")
        t_dl_end = job.get("t_dl_end") or now
        fields = [
            ("time", datetime.datetime.now().isoformat(timespec="seconds")),
            ("url", _short_url(url)),
            ("quality", quality),
            ("keep_codec", "yes" if keep_codec else "no"),
            ("src_codec", perf.get("src_codec") or "-"),
            ("resolution", f"{perf.get('width')}x{perf.get('height')}" if perf.get("width") else "-"),
            ("encoder", perf.get("encoder") or "none"),
            ("reason", (perf.get("reason") or "no conversion step").replace("|", "/")),
            ("cpus", os.cpu_count()),
            ("machine", platform.machine()),
            ("info_s", round((t_first or t_dl_end) - t0, 1)),
            ("download_s", round(t_dl_end - (t_first or t_dl_end), 1)),
            ("encode_s", perf.get("encode_s", 0)),
            ("total_s", round(now - t0, 1)),
            ("size_mb", round(os.path.getsize(final_path) / 1e6, 1) if final_path and os.path.exists(final_path) else "-"),
        ]
        os.makedirs(paths.LOG_DIR, exist_ok=True)
        with open(os.path.join(paths.LOG_DIR, "perf.log"), "a") as f:
            f.write(" | ".join(f"{k}={v}" for k, v in fields) + "\n")
    except Exception:
        pass
