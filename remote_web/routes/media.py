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
