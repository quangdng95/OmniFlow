"""POST /api/check, /api/download, /api/download-batch.

This is a straight port of backend/app.py's check_link()/start_download()/
start_batch_download() (spec §2), with the local/remote branching removed
entirely: trust was already established globally by remote_web/app.py's
before_request gate, so there is no is_local_request() concept here at all,
Instagram/Threads are never rejected, and every download always streams
back to the requesting device (a fresh temp dir under remote_web.config.TEMP_ROOT
instead of the native app's configured save folder).

Error-message constants are intentionally duplicated from backend/app.py
rather than imported from it - backend.app is deliberately the one module
remote_web never depends on (it's the module THIS blueprint replaces), and
importing a module-level string from it would silently couple this file to
an internal a future backend/app.py change could rename without warning.
"""

import os
import shutil
import tempfile
import threading
import uuid

import yt_dlp
from flask import Blueprint, jsonify, request

from backend import classify
from backend import config as backend_config
from backend import cookies, download, extraction, instagram, jobs, linkedin, paths, threads, tiktok
from remote_web import config, ffmpeg_locator

bp = Blueprint("media", __name__)

INSTAGRAM_NO_SESSION_ERROR = "❌ Lỗi: Không tìm thấy phiên đăng nhập Instagram nào trên trình duyệt của máy này. Vui lòng đăng nhập Instagram trên Chrome/Safari/Brave (hoặc thêm cookies.txt thủ công trong Settings) rồi thử lại."
THREADS_AUTH_ERROR = "❌ Lỗi: Cần một trình duyệt đã đăng nhập Threads (threads.com) trên máy này để tải bài viết. Vui lòng đăng nhập rồi thử lại."
THREADS_EXTRACT_ERROR = "❌ Lỗi: Không thể trích xuất dữ liệu từ liên kết này. Vui lòng kiểm tra lại liên kết hoặc trạng thái công khai của nội dung."
LINKEDIN_DOCUMENT_POST_ERROR = "❌ Lỗi: Bài đăng LinkedIn dạng tài liệu/slide (PDF) hiện chưa được OmniFlow hỗ trợ tải. OmniFlow hiện chỉ hỗ trợ bài đăng LinkedIn dạng video hoặc ảnh."


@bp.post("/api/check")
def check_link():
    data = request.get_json(force=True) or {}
    raw_url = (data.get("url") or "").strip()
    if not raw_url:
        return jsonify({"error": "Missing url"}), 400
    cls = classify.classify_url(raw_url)
    url = cls.url

    # No Instagram/Threads local-only rejection here at all - the whole
    # point of remote_web is that these DO work remotely (spec §1), using
    # the deployment Mac's own logged-in browser session exactly as the
    # native app already does.

    ig_resolver_error = None
    if cls.kind == classify.LinkKind.INSTAGRAM_POST_OR_CAROUSEL:
        candidates = cookies.instagram_cookiefile_candidates()
        if not candidates:
            return jsonify({"error": INSTAGRAM_NO_SESSION_ERROR}), 400
        try:
            media = instagram.fetch_instagram_media_any(url, candidates)
            return jsonify(instagram.instagram_check_response(url, media))
        except Exception as e:
            ig_resolver_error = e
            manual_path = backend_config.get_cookies_path()
            source = (
                "manual Settings cookies.txt"
                if manual_path and manual_path in candidates
                else f"{len(candidates)} browser-auto-extracted session(s)"
            )
            paths.log_exception(
                f"remote_web check_link Instagram resolver failed for all {len(candidates)} candidate(s), source: {source}",
                e,
            )
            print(f"[remote_web] Custom Instagram resolver failed: {e}. Falling through to yt-dlp.")
        finally:
            cookies._cleanup_temp_cookiefiles(candidates)

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
        if cls.platform == "LinkedIn":
            try:
                media = linkedin.fetch_linkedin_image_post(url)
                return jsonify(instagram.instagram_check_response(url, media))
            except linkedin.LinkedInUnsupportedPostError:
                return jsonify({"error": LINKEDIN_DOCUMENT_POST_ERROR}), 400
            except Exception:
                pass
        if cls.platform == "TikTok" and "unsupported url" in str(e).lower():
            try:
                media = tiktok.fetch_tiktok_photo_post(url)
                return jsonify(instagram.instagram_check_response(url, media))
            except Exception:
                pass
        error_to_describe = ig_resolver_error if ig_resolver_error is not None else e
        return jsonify({"error": extraction.describe_extraction_error(url, error_to_describe, backend_config.get_cookies_path())}), 400
    except Exception as e:
        paths.log_exception(f"remote_web check_link ({cls.platform}): {url}", e)
        error_to_describe = ig_resolver_error if ig_resolver_error is not None else e
        return jsonify({"error": extraction.describe_extraction_error(url, error_to_describe, backend_config.get_cookies_path())}), 400

    if not info:
        return jsonify({"error": extraction.describe_extraction_error(url, ig_resolver_error or Exception(""), backend_config.get_cookies_path())}), 400

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


def _save_single_cdn_image(job_id, save_dir, title, cdn_url):
    # Same small helper backend/app.py defines privately for its LinkedIn/
    # TikTok single-image fallbacks - reimplemented here (not imported from
    # backend.app) since remote_web deliberately never depends on
    # backend.app, the module this blueprint replaces (see this file's
    # module docstring).
    jpg_path = download.get_unique_filename(save_dir, title, "jpg")
    jobs.jobs[job_id]["filename"] = os.path.basename(jpg_path)
    jobs.jobs[job_id]["filepath"] = jpg_path
    download.download_direct_url(cdn_url, jpg_path, job_id)
    jobs.jobs[job_id]["percent"] = 100
    jobs.jobs[job_id]["text"] = f"Saved: {jobs.jobs[job_id]['filename']}"
    jobs.jobs[job_id]["status"] = "done"


@bp.post("/api/download")
def start_download():
    data = request.get_json(force=True) or {}
    raw_url = (data.get("url") or "").strip()
    if not raw_url:
        return jsonify({"error": "Missing url"}), 400
    cls = classify.classify_url(raw_url)
    url = cls.url
    title = data.get("title") or "Video"
    quality = data.get("quality") or "Best"
    entry_index = data.get("entry_index") or classify.entry_index_from_url(url)

    # Always a fresh temp dir - remote_web has no "local save" mode at all
    # (spec §5.2). Streamed back via GET /api/download-file (Task 12).
    os.makedirs(config.TEMP_ROOT, exist_ok=True)
    remote_temp_dir = tempfile.mkdtemp(dir=config.TEMP_ROOT, prefix="omniflow-remote-")
    save_dir = remote_temp_dir

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
                print(f"[remote_web download] job {job_id} (instagram) failed: {e}")
                jobs._remove_job_file(job_id)
                jobs.jobs[job_id]["text"] = str(e) or "Download failed"
                jobs.jobs[job_id]["status"] = "error"
                return
            finally:
                cookies._cleanup_temp_cookiefiles(ig_candidates)
            jobs.jobs[job_id]["percent"] = 100
            jobs.jobs[job_id]["text"] = f"Saved: {jobs.jobs[job_id]['filename']}"
            jobs.jobs[job_id]["status"] = "done"

        threading.Thread(target=run_instagram, daemon=True).start()
        return jsonify({"job_id": job_id})

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
                print(f"[remote_web download] job {job_id} (threads) failed: {e}")
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

    ffmpeg_bin = ffmpeg_locator.resolve_ffmpeg_binary()
    if not ffmpeg_bin:
        return jsonify({"error": ffmpeg_locator.ffmpeg_unavailable_message()}), 400

    ext = "mp3" if "Audio" in quality else "mp4"
    final_output_path = download.get_unique_filename(save_dir, title, ext)
    final_filename = os.path.basename(final_output_path)
    output_path_no_ext = os.path.splitext(final_output_path)[0]

    job_id = uuid.uuid4().hex
    jobs.jobs[job_id] = {
        "status": "running", "percent": 0, "text": "Starting...",
        "filename": final_filename, "filepath": final_output_path, "cancelled": False,
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

        cookies_path = backend_config.get_cookies_path()
        if url and "instagram" in url.lower():
            if not (cookies_path and backend_config.cookies_status_for(cookies_path) == "valid"):
                candidates = cookies.instagram_cookiefile_candidates()
                if candidates:
                    cookies_path = candidates[0]
                    cookies._cleanup_temp_cookiefiles(candidates[1:])

        ydl_opts = download.build_download_options(
            quality, output_path_no_ext, ffmpeg_bin, [progress_hook], [postprocessor_hook], cookies_path, entry_index, url
        )

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            if "Audio" not in quality:
                download.ensure_h264(final_output_path, ffmpeg_bin, job_id)
        except yt_dlp.utils.DownloadCancelled:
            jobs.jobs[job_id]["status"] = "cancelled"
            jobs.jobs[job_id]["text"] = "Cancelled"
            download.cleanup_partial_download(output_path_no_ext)
            shutil.rmtree(remote_temp_dir, ignore_errors=True)
            return
        except yt_dlp.utils.DownloadError as e:
            if cls.platform == "LinkedIn":
                try:
                    linkedin_media = linkedin.fetch_linkedin_image_post(url)
                    _save_single_cdn_image(job_id, save_dir, title, linkedin_media["items"][0]["url"])
                    return
                except yt_dlp.utils.DownloadCancelled:
                    jobs.jobs[job_id]["status"] = "cancelled"
                    jobs.jobs[job_id]["text"] = "Cancelled"
                    return
                except linkedin.LinkedInUnsupportedPostError:
                    jobs.jobs[job_id]["status"] = "error"
                    jobs.jobs[job_id]["text"] = LINKEDIN_DOCUMENT_POST_ERROR
                    return
                except Exception:
                    pass
            if cls.platform == "TikTok" and "unsupported url" in str(e).lower():
                try:
                    tiktok_media = tiktok.fetch_tiktok_photo_post(url)
                    _save_single_cdn_image(job_id, save_dir, title, tiktok_media["items"][0]["url"])
                    return
                except yt_dlp.utils.DownloadCancelled:
                    jobs.jobs[job_id]["status"] = "cancelled"
                    jobs.jobs[job_id]["text"] = "Cancelled"
                    return
                except Exception:
                    pass
            print(f"[remote_web download] job {job_id} failed: {e}")
            jobs.jobs[job_id]["status"] = "error"
            jobs.jobs[job_id]["text"] = extraction.describe_extraction_error(url, e, cookies_path)
            download.cleanup_partial_download(output_path_no_ext)
            shutil.rmtree(remote_temp_dir, ignore_errors=True)
            return
        except Exception as e:
            print(f"[remote_web download] job {job_id} failed: {e}")
            jobs.jobs[job_id]["status"] = "error"
            jobs.jobs[job_id]["text"] = str(e) or "Download failed"
            download.cleanup_partial_download(output_path_no_ext)
            shutil.rmtree(remote_temp_dir, ignore_errors=True)
            return
        finally:
            cookies._cleanup_temp_cookiefiles([ydl_opts.get("cookiefile")])

        jobs.jobs[job_id]["status"] = "done"
        jobs.jobs[job_id]["percent"] = 100
        jobs.jobs[job_id]["text"] = f"Saved: {final_filename}"

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"job_id": job_id})
