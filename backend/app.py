"""The Flask application - all HTTP routes + the local-vs-remote split.

This module sits at the top of the backend dependency DAG: it imports every
sibling, and NO other backend module may import backend.app (enforced by
tests/test_import_convention.py). The route bodies orchestrate; the actual
work lives in the sibling modules (classify/extraction/download/instagram/...).
"""

import os
import shutil
import subprocess
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import yt_dlp
from flask import Flask, request, jsonify, send_from_directory, send_file, after_this_request

from backend import classify, config, cookies, download, extraction, instagram, jobs, linkedin, paths, threads

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
    playlist_limit_val = data.get("playlist_limit", session.get("playlist_limit", 100))
    config.save_session(path_val, cookies_path_val, browser_val, playlist_limit_val)
    return jsonify({
        "path": path_val,
        "cookies_path": cookies_path_val,
        "browser": browser_val,
        "playlist_limit": playlist_limit_val,
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


INSTAGRAM_LOCAL_ONLY_ERROR = "Instagram downloads are only available when running OmniFlow locally on your own machine."
INSTAGRAM_NO_SESSION_ERROR = "❌ Lỗi: Không tìm thấy phiên đăng nhập Instagram nào trên trình duyệt của máy này. Vui lòng đăng nhập Instagram trên Chrome/Safari/Brave (hoặc thêm cookies.txt thủ công trong Settings) rồi thử lại."
THREADS_LOCAL_ONLY_ERROR = "Threads downloads are only available when running OmniFlow locally on your own machine."
THREADS_AUTH_ERROR = "❌ Lỗi: Cần một trình duyệt đã đăng nhập Threads (threads.com) trên máy này để tải bài viết. Vui lòng đăng nhập rồi thử lại."
THREADS_EXTRACT_ERROR = "❌ Lỗi: Không thể trích xuất dữ liệu từ liên kết này. Vui lòng kiểm tra lại liên kết hoặc trạng thái công khai của nội dung."

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
    # Threads auth is the same story as Instagram: auto-extracted from the
    # local owner's own logged-in browser, so it can't be handed to a remote
    # visitor without burning the owner's own Threads session.
    if cls.platform == "Threads" and not is_local_request():
        return jsonify({"error": THREADS_LOCAL_ONLY_ERROR}), 403

    # Instagram posts/reels/tv go through our own resolver (so photos and
    # carousels work at all). A resolver failure falls through to yt-dlp as a
    # last resort, but yt-dlp's generic Instagram scraping routinely fails
    # with an unhelpful "Unable to extract data" and no real reason - so the
    # resolver's own (usually far more specific) error is kept and preferred
    # over yt-dlp's if that fallback also fails, instead of being discarded.
    ig_resolver_error = None
    if cls.kind == classify.LinkKind.INSTAGRAM_POST_OR_CAROUSEL:
        candidates = cookies.instagram_cookiefile_candidates()
        if not candidates:
            # No Instagram session anywhere (Settings or any local browser) -
            # yt-dlp's anonymous fallback below is essentially guaranteed to
            # fail too, with a far less helpful message, so say the real
            # reason immediately instead of wasting a round trip on it.
            return jsonify({"error": INSTAGRAM_NO_SESSION_ERROR}), 400
        try:
            media = instagram.fetch_instagram_media_any(url, candidates)
            return jsonify(instagram.instagram_check_response(url, media))
        except Exception as e:
            ig_resolver_error = e
            print(f"Custom resolver failed: {e}. Falling through to yt-dlp.")
        finally:
            cookies._cleanup_temp_cookiefiles(candidates)

    # Threads has no yt-dlp/gallery-dl support at all (MISTAKES.md, 2026-07-07),
    # so unlike Instagram there is no fallback path to fall through to - a
    # resolver failure here goes straight to a friendly error.
    if cls.kind == classify.LinkKind.THREADS_POST:
        candidates = threads.threads_cookiefile_candidates()
        last_error = None
        if candidates:
            try:
                media = threads.fetch_threads_media_any(url, candidates)
                return jsonify(instagram.instagram_check_response(url, media))
            except Exception as e:
                last_error = e
            finally:
                cookies._cleanup_temp_cookiefiles(candidates)
        if not candidates or isinstance(last_error, threads.ThreadsAuthError):
            return jsonify({"error": THREADS_AUTH_ERROR}), 400
        return jsonify({"error": THREADS_EXTRACT_ERROR}), 400

    try:
        info = extraction.extract_video_info(cls)
    except yt_dlp.utils.DownloadError as e:
        # yt-dlp's LinkedInIE only handles a post with a <video> tag - an
        # image-only LinkedIn post fails here with "Unable to extract video",
        # so fall back to the custom og:image resolver before giving up.
        if cls.platform == "LinkedIn":
            try:
                media = linkedin.fetch_linkedin_image_post(url)
                return jsonify(instagram.instagram_check_response(url, media))
            except Exception:
                pass
        error_to_describe = ig_resolver_error if ig_resolver_error is not None else e
        return jsonify({"error": extraction.describe_extraction_error(url, error_to_describe, config.get_cookies_path())}), 400
    except Exception as e:
        # An exception here that ISN'T a yt_dlp.utils.DownloadError is
        # always unexpected (see describe_extraction_error's trusted-type
        # check, which hides its raw message from the user) - log the full
        # traceback so a failure that's otherwise invisible once packaged
        # still leaves something diagnosable.
        paths.log_exception(f"check_link ({cls.platform}): {url}", e)
        error_to_describe = ig_resolver_error if ig_resolver_error is not None else e
        return jsonify({"error": extraction.describe_extraction_error(url, error_to_describe, config.get_cookies_path())}), 400

    if not info:
        return jsonify({"error": extraction.describe_extraction_error(url, ig_resolver_error or Exception(""), config.get_cookies_path())}), 400

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
        items = extraction.flat_playlist_items(entries) if is_flat else extraction.story_playlist_items(entries)
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
        "thumbnail": extraction.resolve_thumbnail(info),
        "platform": cls.platform,
        "qualities": extraction.qualities_for(info),
        "duration": extraction.format_duration(info.get("duration")),
    })


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
    if cls.platform == "Threads" and not is_local_request():
        return jsonify({"error": THREADS_LOCAL_ONLY_ERROR}), 403

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
                final_output_path = download.get_unique_filename(save_dir, title, ext)
                jobs.jobs[job_id]["filename"] = os.path.basename(final_output_path)
                jobs.jobs[job_id]["filepath"] = final_output_path
                download.download_direct_url(cdn_url, final_output_path, job_id)
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
                jobs.jobs[job_id]["text"] = extraction.describe_extraction_error(url, e, ig_candidates[0])
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

    # Threads posts download through the same direct-CDN-fetch pattern as
    # Instagram (no yt-dlp/ffmpeg support exists for Threads at all).
    threads_candidates = []
    if cls.kind == classify.LinkKind.THREADS_POST:
        threads_candidates = threads.threads_cookiefile_candidates()
    if threads_candidates:

        job_id = uuid.uuid4().hex
        jobs.jobs[job_id] = {
            "status": "running", "percent": 0, "text": "Starting...",
            "filename": None, "filepath": None, "cancelled": False,
        }

        def run_threads():
            try:
                media = threads.fetch_threads_media_any(url, threads_candidates)
                items = media["items"]
                idx = (entry_index - 1) if entry_index else 0
                if idx < 0 or idx >= len(items):
                    raise ValueError("Selected item is no longer available")
                item = items[idx]
                cdn_url = item.get("url")
                if not cdn_url:
                    raise ValueError("No downloadable media found")
                ext = "jpg" if item["kind"] == "image" else "mp4"
                final_output_path = download.get_unique_filename(save_dir, title, ext)
                jobs.jobs[job_id]["filename"] = os.path.basename(final_output_path)
                jobs.jobs[job_id]["filepath"] = final_output_path
                download.download_direct_url(cdn_url, final_output_path, job_id)
            except yt_dlp.utils.DownloadCancelled:
                jobs._remove_job_file(job_id)
                jobs.jobs[job_id]["text"] = "Cancelled"
                jobs.jobs[job_id]["status"] = "cancelled"
                return
            except threads.ThreadsAuthError:
                jobs._remove_job_file(job_id)
                jobs.jobs[job_id]["text"] = THREADS_AUTH_ERROR
                jobs.jobs[job_id]["status"] = "error"
                return
            except Exception as e:
                print(f"[download] job {job_id} (threads) failed: {e}")
                jobs._remove_job_file(job_id)
                jobs.jobs[job_id]["text"] = str(e) or "Download failed"
                jobs.jobs[job_id]["status"] = "error"
                return
            finally:
                cookies._cleanup_temp_cookiefiles(threads_candidates)
            jobs.jobs[job_id]["percent"] = 100
            jobs.jobs[job_id]["text"] = f"Saved: {jobs.jobs[job_id]['filename']}"
            jobs.jobs[job_id]["status"] = "done"

        threading.Thread(target=run_threads, daemon=True).start()
        return jsonify({"job_id": job_id})

    # LinkedIn posts can be either a video (yt-dlp's LinkedInIE handles it
    # below) or a plain image (no <video> tag - needs the custom og:image
    # resolver instead). Try the cheap image resolver first; a post with no
    # og:image (a real video post, or an unsupported document/slide-deck post)
    # falls through to the standard yt-dlp pipeline, which raises its own
    # DownloadError for a document post rather than silently mis-downloading it.
    if cls.platform == "LinkedIn":
        try:
            linkedin_media = linkedin.fetch_linkedin_image_post(url)
        except Exception:
            linkedin_media = None
        if linkedin_media:
            job_id = uuid.uuid4().hex
            jobs.jobs[job_id] = {
                "status": "running", "percent": 0, "text": "Starting...",
                "filename": None, "filepath": None, "cancelled": False,
            }

            def run_linkedin_image():
                try:
                    cdn_url = linkedin_media["items"][0].get("url")
                    if not cdn_url:
                        raise ValueError("No downloadable media found")
                    final_output_path = download.get_unique_filename(save_dir, title, "jpg")
                    jobs.jobs[job_id]["filename"] = os.path.basename(final_output_path)
                    jobs.jobs[job_id]["filepath"] = final_output_path
                    download.download_direct_url(cdn_url, final_output_path, job_id)
                except yt_dlp.utils.DownloadCancelled:
                    jobs._remove_job_file(job_id)
                    jobs.jobs[job_id]["text"] = "Cancelled"
                    jobs.jobs[job_id]["status"] = "cancelled"
                    return
                except Exception as e:
                    print(f"[download] job {job_id} (linkedin image) failed: {e}")
                    jobs._remove_job_file(job_id)
                    jobs.jobs[job_id]["text"] = str(e) or "Download failed"
                    jobs.jobs[job_id]["status"] = "error"
                    return
                jobs.jobs[job_id]["percent"] = 100
                jobs.jobs[job_id]["text"] = f"Saved: {jobs.jobs[job_id]['filename']}"
                jobs.jobs[job_id]["status"] = "done"

            threading.Thread(target=run_linkedin_image, daemon=True).start()
            return jsonify({"job_id": job_id})

    ffmpeg_bin = paths.get_ffmpeg_path()
    if not ffmpeg_bin:
        return jsonify({"error": "FFmpeg missing! Run 'brew install ffmpeg'"}), 400

    ext = "mp3" if "Audio" in quality else "mp4"
    final_output_path = download.get_unique_filename(save_dir, title, ext)
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
            state["stream_index"] = download.apply_progress_update(jobs.jobs[job_id], d, state["stream_index"], total_streams)

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

        ydl_opts = download.build_download_options(
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
                download.ensure_h264(final_output_path, ffmpeg_bin, job_id)
        except yt_dlp.utils.DownloadCancelled:
            jobs.jobs[job_id]["status"] = "cancelled"
            jobs.jobs[job_id]["text"] = "Cancelled"
            download.cleanup_partial_download(output_path_no_ext)
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
            jobs.jobs[job_id]["text"] = extraction.describe_extraction_error(url, e, cookies_path)
            download.cleanup_partial_download(output_path_no_ext)
            if remote_temp_dir:
                shutil.rmtree(remote_temp_dir, ignore_errors=True)
            return
        except Exception as e:
            print(f"[download] job {job_id} failed: {e}")
            jobs.jobs[job_id]["status"] = "error"
            jobs.jobs[job_id]["text"] = str(e) or "Download failed"
            download.cleanup_partial_download(output_path_no_ext)
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
                    out = download.get_unique_filename(save_dir, item_title, ext)
                    download.download_direct_url(cdn_url, out, job_id, on_progress=on_progress)
                elif item.get("url"):
                    out = download.download_one_video(item["url"], save_dir, item_title, quality, ffmpeg_bin, job_id, on_progress=on_progress)
                elif item.get("entry_index"):
                    # Instagram Story: yt-dlp playlist, targeted by its entry index.
                    out = download.download_one_video(url, save_dir, item_title, quality, ffmpeg_bin, job_id, entry_index=item["entry_index"], on_progress=on_progress)
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
            jobs.jobs[job_id]["text"] = extraction.describe_extraction_error(url, e) if is_ig_carousel else (str(e) or "Download failed")
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


@app.post("/api/open-logs")
def open_logs():
    # Diagnostic logs (paths.log_exception) are the only trace left of a
    # failure the UI deliberately hides behind a friendly generic message
    # (extraction.describe_extraction_error) - a packaged .app has no visible
    # stdout, so this is how a user can hand the real cause back to us
    # instead of just a screenshot of "couldn't process this link".
    if not is_local_request():
        return jsonify({"error": LOCAL_ONLY_ERROR}), 403
    os.makedirs(paths.LOG_DIR, exist_ok=True)
    log_file = os.path.join(paths.LOG_DIR, "errors.log")
    subprocess.run(["open", paths.LOG_DIR])
    return jsonify({"ok": True, "has_logs": os.path.isfile(log_file) and os.path.getsize(log_file) > 0})
