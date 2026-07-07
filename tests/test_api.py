import json
import os
import subprocess
import sys
import threading
import time
import types
import urllib.error
import urllib.request
from types import SimpleNamespace

import pytest

from backend import classify, config, paths
import yt_dlp

from backend import app as app_module
from backend import download as download_module
from backend import extraction as extraction_module
from backend import instagram as instagram_module
from backend import cookies as cookies_module
from backend import jobs as jobs_module
from backend import threads as threads_module
from backend import linkedin as linkedin_module
from backend.config import (
    load_session,
    resolve_save_dir,
    save_session,
)
from backend.instagram import (
    InstagramAuthError,
)
from backend.download import (
    ensure_h264,
)
from backend.extraction import (
    describe_extraction_error,
)
from backend.app import is_local_request


# ---- /api/browse-file ----


def test_browse_file_returns_chosen_path(client, monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="/Users/test/cookies.txt\n", stderr=""),
    )
    resp = client.post("/api/browse-file")
    assert resp.status_code == 200
    # the fake path doesn't exist on the test filesystem, so status can't be anything but "none"
    assert resp.get_json() == {"path": "/Users/test/cookies.txt", "cookies_status": "none"}


def test_browse_file_reports_cookies_status_for_the_picked_file(client, monkeypatch, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=f"{cookies_file}\n", stderr=""),
    )
    resp = client.post("/api/browse-file")
    assert resp.get_json() == {"path": str(cookies_file), "cookies_status": "valid"}


def test_browse_file_returns_error_when_cancelled(client, monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="User cancelled"),
    )
    resp = client.post("/api/browse-file")
    assert resp.status_code == 400


# ---- /api/settings cookies_status ----


def test_get_settings_reports_cookies_status_none_by_default(client):
    resp = client.get("/api/settings")
    assert resp.get_json()["cookies_status"] == "none"


def test_get_settings_reports_cookies_status_valid(client, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    save_session(os.path.expanduser("~/Downloads"), str(cookies_file))
    resp = client.get("/api/settings")
    assert resp.get_json()["cookies_status"] == "valid"


def test_post_settings_reports_cookies_status_no_session(client, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# no session in here\n")
    resp = client.post("/api/settings", json={"cookies_path": str(cookies_file)})
    assert resp.get_json()["cookies_status"] == "no_session"


# ---- /api/clipboard ----


def test_get_clipboard_returns_pasteboard_text(client, monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="https://youtube.com/watch?v=abc", stderr=""),
    )
    resp = client.get("/api/clipboard")
    assert resp.status_code == 200
    assert resp.get_json() == {"text": "https://youtube.com/watch?v=abc"}


def test_get_clipboard_errors_when_pbpaste_fails(client, monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="boom"),
    )
    resp = client.get("/api/clipboard")
    assert resp.status_code == 500
    assert resp.get_json() == {"error": "Could not read clipboard"}


def test_get_clipboard_errors_when_pbpaste_is_missing(client, monkeypatch):
    def raise_not_found(*a, **k):
        raise FileNotFoundError("pbpaste not found")

    monkeypatch.setattr(subprocess, "run", raise_not_found)
    resp = client.get("/api/clipboard")
    assert resp.status_code == 500


# ---- /api/check ----


def test_check_link_missing_url(client):
    resp = client.post("/api/check", json={})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Missing url"


def test_check_link_invalid_link(client, monkeypatch):
    def raise_error(url):
        raise yt_dlp.utils.DownloadError("ERROR: no such video. more CLI-only detail here")

    monkeypatch.setattr(extraction_module, "extract_video_info", raise_error)
    resp = client.post("/api/check", json={"url": "https://example.com/dead"})
    assert resp.status_code == 400
    # surfaces yt-dlp's real (trimmed) message instead of a generic one
    assert resp.get_json()["error"] == "no such video"


def test_check_link_unexpected_exception_falls_back_to_generic_message(client, monkeypatch):
    def raise_error(url):
        raise RuntimeError("something unrelated broke")

    monkeypatch.setattr(extraction_module, "extract_video_info", raise_error)
    resp = client.post("/api/check", json={"url": "https://example.com/dead"})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Invalid link or private video"


def test_check_link_instagram_login_required_shows_clear_explanation(client, monkeypatch):
    def raise_error(url):
        raise yt_dlp.utils.DownloadError(
            "ERROR: [Instagram] abc: Instagram sent an empty media response. "
            "Check if this post is accessible in your browser without being logged-in."
        )

    monkeypatch.setattr(extraction_module, "extract_video_info", raise_error)
    resp = client.post("/api/check", json={"url": "https://www.instagram.com/p/abc/"})
    assert resp.status_code == 400
    assert "Không thể tải video từ tài khoản Private" in resp.get_json()["error"]


def test_check_link_instagram_with_no_session_cookies_file_flags_the_file(client, monkeypatch, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# no session in here\n")
    save_session(os.path.expanduser("~/Downloads"), str(cookies_file))

    def raise_error(url):
        raise yt_dlp.utils.DownloadError(
            "ERROR: [Instagram] abc: Instagram sent an empty media response."
        )

    monkeypatch.setattr(extraction_module, "extract_video_info", raise_error)
    resp = client.post("/api/check", json={"url": "https://www.instagram.com/p/abc/"})
    assert resp.status_code == 400
    assert "Không thể tải video từ tài khoản Private" in resp.get_json()["error"]


def test_check_link_instagram_with_expired_session_cookies_suggests_refreshing(client, monkeypatch, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    save_session(os.path.expanduser("~/Downloads"), str(cookies_file))

    # Cookies look valid (they have a sessionid), so the resolver actually runs
    # and Instagram itself rejects the still-invalid session.
    def raise_error(url, cookies_path):
        raise InstagramAuthError("Instagram sent an empty media response.")

    monkeypatch.setattr(instagram_module, "fetch_instagram_media", raise_error)
    resp = client.post("/api/check", json={"url": "https://www.instagram.com/p/abc/"})
    assert resp.status_code == 400
    assert "Không thể tải video từ tài khoản Private" in resp.get_json()["error"]


# ---- Instagram media resolver (photos/carousels) ----


def test_check_link_instagram_single_photo_end_to_end(client, monkeypatch, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    save_session(os.path.expanduser("~/Downloads"), str(cookies_file))
    monkeypatch.setattr(
        instagram_module,
        "fetch_instagram_media",
        lambda url, cookies_path: {"title": "A photo", "items": [{"kind": "image", "url": "http://cdn/p.jpg", "thumbnail": "http://cdn/p.jpg"}]},
    )
    resp = client.post("/api/check", json={"url": "https://www.instagram.com/p/abc/"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["type"] == "video"
    assert body["kind"] == "image"


def test_check_link_instagram_carousel_end_to_end(client, monkeypatch, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    save_session(os.path.expanduser("~/Downloads"), str(cookies_file))
    monkeypatch.setattr(
        instagram_module,
        "fetch_instagram_media",
        lambda url, cookies_path: {
            "title": "Album",
            "items": [
                {"kind": "image", "url": "http://cdn/1.jpg", "thumbnail": None},
                {"kind": "video", "url": "http://cdn/2.mp4", "thumbnail": None},
                {"kind": "image", "url": "http://cdn/3.jpg", "thumbnail": None},
            ],
        },
    )
    resp = client.post("/api/check", json={"url": "https://www.instagram.com/p/abc/"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["type"] == "playlist"
    assert len(body["items"]) == 3
    assert [i["kind"] for i in body["items"]] == ["image", "video", "image"]


# ---- /api/check playlist handling (Instagram Stories / multi-video carousels) ----


def test_check_link_playlist_returns_video_entries_only(client, monkeypatch):
    info = {
        "_type": "playlist",
        "title": "Story by someone",
        "entries": [
            {
                "id": "vid1",
                "title": "Story item 1",
                "thumbnail": "https://example.com/1.jpg",
                "duration": 15,
                "formats": [{"height": 720}],
            },
            # a photo-only story item - yt-dlp never populates "formats" for
            # these, so it must be silently excluded, not error
            {"id": "photo1", "title": "Story item 2 (photo)"},
            {
                "id": "vid2",
                "title": "Story item 3",
                "thumbnail": "https://example.com/3.jpg",
                "duration": 8,
                "formats": [{"height": 1080}],
            },
        ],
    }
    monkeypatch.setattr(extraction_module, "extract_video_info", lambda url: info)
    resp = client.post("/api/check", json={"url": "https://www.instagram.com/stories/someone/1/"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["type"] == "playlist"
    assert body["title"] == "Story by someone"
    assert [item["id"] for item in body["items"]] == ["vid1", "vid2"]
    assert body["items"][0]["duration"] == "00:15"
    assert body["items"][0]["qualities"] == ["720p", "Best", "Audio Only"]


def test_check_link_playlist_with_only_photo_entries_returns_empty_items(client, monkeypatch):
    info = {"_type": "playlist", "title": "Story by someone", "entries": [{"id": "photo1", "title": "Photo"}]}
    monkeypatch.setattr(extraction_module, "extract_video_info", lambda url: info)
    resp = client.post("/api/check", json={"url": "https://www.instagram.com/stories/someone/1/"})
    assert resp.status_code == 200
    assert resp.get_json()["items"] == []


def test_extract_video_info_uses_yt_dlp_in_process(monkeypatch):
    captured = {}

    class FakeYoutubeDL:
        def __init__(self, opts):
            captured["opts"] = opts

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, url, download):
            captured["url"] = url
            captured["download"] = download
            return {"title": "ok"}

    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYoutubeDL)
    result = extraction_module.extract_video_info(classify.classify_url("https://youtube.com/watch?v=abc"))

    assert result == {"title": "ok"}
    assert captured["url"] == "https://youtube.com/watch?v=abc"
    assert captured["download"] is False
    assert captured["opts"]["simulate"] is True
    assert captured["opts"]["noplaylist"] is True


# ---- /api/download ----


def test_start_download_missing_url(client):
    resp = client.post("/api/download", json={})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Missing url"


class _NoOpThread:
    """Stand-in for threading.Thread that never actually runs its target,
    so the test never spawns a real yt-dlp subprocess."""

    def __init__(self, target=None, daemon=None):
        pass

    def start(self):
        pass


def test_start_download_falls_back_when_configured_folder_is_missing(client, monkeypatch, tmp_path):
    monkeypatch.setattr(
        config,
        "load_session",
        lambda: {"path": "/this/path/does/not/exist"},
    )
    monkeypatch.setattr(config, "resolve_save_dir", lambda path: str(tmp_path))
    monkeypatch.setattr(threading, "Thread", _NoOpThread)
    resp = client.post(
        "/api/download",
        json={"url": "https://youtube.com/watch?v=abc", "title": "Video", "quality": "720p"},
    )
    assert resp.status_code == 200
    assert "job_id" in resp.get_json()


def test_start_download_errors_when_no_folder_is_writable_anywhere(client, monkeypatch):
    monkeypatch.setattr(config, "resolve_save_dir", lambda path: None)
    resp = client.post(
        "/api/download",
        json={"url": "https://youtube.com/watch?v=abc", "title": "Video", "quality": "720p"},
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Download folder not writable"


def test_start_download_of_watch_list_url_downloads_the_watch_url_not_the_playlist(client, monkeypatch, tmp_path):
    # R5 pin: for watch?v=X&list=PL… the user picked video X, so the download
    # engine must receive the WATCH url. Only /api/check widens to the whole
    # playlist (classification carries the two URLs separately for exactly this).
    monkeypatch.setattr(config, "load_session", lambda: {"path": str(tmp_path), "cookies_path": ""})
    monkeypatch.setattr(config, "resolve_save_dir", lambda path: str(tmp_path))
    monkeypatch.setattr(paths, "get_ffmpeg_path", lambda: "/ff")
    monkeypatch.setattr(download_module, "ensure_h264", lambda *a, **k: None)

    seen = {}

    class FakeYDL:
        def __init__(self, opts):
            seen["opts"] = opts

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def download(self, urls):
            seen["urls"] = urls

    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYDL)

    class SyncThread:
        # Runs the download worker inline so the assertion sees its yt-dlp call.
        def __init__(self, target=None, daemon=None):
            self._target = target

        def start(self):
            self._target()

    monkeypatch.setattr(threading, "Thread", SyncThread)

    watch_url = "https://www.youtube.com/watch?v=-It5L-gC6nA&list=PLIILL6veL783kKkdiIybbxARNY9bAVQYe"
    resp = client.post("/api/download", json={"url": watch_url, "title": "V", "quality": "720p"})
    assert resp.status_code == 200
    assert seen["urls"] == [watch_url]  # the watch URL - NOT playlist?list=…


def test_start_download_missing_ffmpeg(client, monkeypatch, tmp_path):
    monkeypatch.setattr(
        config, "load_session", lambda: {"path": str(tmp_path)}
    )
    monkeypatch.setattr(paths, "get_ffmpeg_path", lambda: None)
    resp = client.post(
        "/api/download",
        json={"url": "https://youtube.com/watch?v=abc", "title": "Video", "quality": "720p"},
    )
    assert resp.status_code == 400
    assert "FFmpeg" in resp.get_json()["error"]


# ---- /api/progress & /api/cancel ----


def test_progress_unknown_job(client):
    resp = client.get("/api/progress/does-not-exist")
    assert resp.status_code == 404


def test_cancel_unknown_job(client):
    resp = client.post("/api/cancel/does-not-exist")
    assert resp.status_code == 404


def test_cancel_marks_job_as_cancelled(client):
    jobs_module.jobs["job-1"] = {
        "status": "running",
        "percent": 10,
        "text": "Downloading...",
        "filename": None,
        "cancelled": False,
    }
    resp = client.post("/api/cancel/job-1")
    assert resp.status_code == 200
    assert jobs_module.jobs["job-1"]["cancelled"] is True


# ---- is_local_request ----


def test_is_local_request_true_for_loopback_hostnames():
    for host in ("127.0.0.1:5001", "localhost:5001", "localhost", "[::1]:5001", "[::1]"):
        with app_module.app.test_request_context(headers={"Host": host}):
            assert is_local_request(), host


def test_is_local_request_false_for_other_hosts():
    for host in ("example.com", "example.com:5001", "192.168.1.5:5001", "my-tunnel.ngrok.io"):
        with app_module.app.test_request_context(headers={"Host": host}):
            assert not is_local_request(), host


# ---- local-only route guards ----


def test_browse_folder_rejected_when_remote(client):
    resp = client.post("/api/browse", headers={"Host": "example.com"})
    assert resp.status_code == 403


def test_browse_file_rejected_when_remote(client):
    resp = client.post("/api/browse-file", headers={"Host": "example.com"})
    assert resp.status_code == 403


def test_open_folder_rejected_when_remote(client):
    resp = client.post("/api/open-folder", headers={"Host": "example.com"})
    assert resp.status_code == 403


def test_get_clipboard_rejected_when_remote(client):
    resp = client.get("/api/clipboard", headers={"Host": "example.com"})
    assert resp.status_code == 403


# ---- Instagram is local-only ----


def test_check_link_instagram_rejected_when_remote(client):
    resp = client.post(
        "/api/check",
        json={"url": "https://www.instagram.com/reel/abc/"},
        headers={"Host": "example.com"},
    )
    assert resp.status_code == 403
    assert "locally" in resp.get_json()["error"]


def test_check_link_instagram_not_blocked_when_local(client, monkeypatch, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    save_session(os.path.expanduser("~/Downloads"), str(cookies_file))
    monkeypatch.setattr(
        instagram_module,
        "fetch_instagram_media",
        lambda url, cookies_path: {"title": "A reel", "items": [{"kind": "video", "url": "http://cdn/v.mp4", "thumbnail": None}]},
    )
    resp = client.post("/api/check", json={"url": "https://www.instagram.com/reel/abc/"})
    assert resp.status_code == 200


def test_start_download_instagram_rejected_when_remote(client):
    resp = client.post(
        "/api/download",
        json={"url": "https://www.instagram.com/reel/abc/", "title": "Video", "quality": "720p"},
        headers={"Host": "example.com"},
    )
    assert resp.status_code == 403
    assert "locally" in resp.get_json()["error"]


# ---- Threads is local-only, same reasoning as Instagram ----


def test_check_link_threads_rejected_when_remote(client):
    resp = client.post(
        "/api/check",
        json={"url": "https://www.threads.com/@someone/post/abc123"},
        headers={"Host": "example.com"},
    )
    assert resp.status_code == 403
    assert "locally" in resp.get_json()["error"]


def test_check_link_threads_succeeds_when_local(client, monkeypatch):
    monkeypatch.setattr(threads_module, "threads_cookiefile_candidates", lambda: ["/acct.txt"])
    monkeypatch.setattr(
        threads_module,
        "fetch_threads_media",
        lambda url, cf: {"title": "A post", "items": [{"kind": "video", "url": "http://cdn/v.mp4", "thumbnail": None}]},
    )
    resp = client.post("/api/check", json={"url": "https://www.threads.com/@someone/post/abc123"})
    assert resp.status_code == 200
    assert resp.get_json()["type"] == "video"


def test_check_link_threads_no_candidates_returns_friendly_auth_error(client, monkeypatch):
    monkeypatch.setattr(threads_module, "threads_cookiefile_candidates", lambda: [])
    resp = client.post("/api/check", json={"url": "https://www.threads.com/@someone/post/abc123"})
    assert resp.status_code == 400
    assert "Threads" in resp.get_json()["error"]


def test_start_download_threads_rejected_when_remote(client):
    resp = client.post(
        "/api/download",
        json={"url": "https://www.threads.com/@someone/post/abc123", "title": "Video", "quality": "Best"},
        headers={"Host": "example.com"},
    )
    assert resp.status_code == 403
    assert "locally" in resp.get_json()["error"]


# ---- LinkedIn: yt-dlp video path, custom og:image fallback for image posts ----


def test_check_link_linkedin_falls_back_to_image_resolver(client, monkeypatch):
    def fake_extract(cls):
        raise yt_dlp.utils.DownloadError("Unable to extract video")

    monkeypatch.setattr(extraction_module, "extract_video_info", fake_extract)
    monkeypatch.setattr(
        linkedin_module,
        "fetch_linkedin_image_post",
        lambda url: {"title": "A post", "items": [{"kind": "image", "url": "http://cdn/i.jpg", "thumbnail": "http://cdn/i.jpg"}]},
    )
    resp = client.post("/api/check", json={"url": "https://www.linkedin.com/posts/someone_activity-123-abcd"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["type"] == "video"
    assert body["kind"] == "image"


def test_check_link_linkedin_video_post_unaffected(client, monkeypatch):
    # A real LinkedIn video post never reaches the image fallback - the
    # standard yt-dlp path handles it exactly like every other platform.
    monkeypatch.setattr(extraction_module, "extract_video_info", lambda cls: {"title": "A LinkedIn video", "formats": []})
    resp = client.post("/api/check", json={"url": "https://www.linkedin.com/posts/someone_activity-123-abcd"})
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "A LinkedIn video"


def test_start_download_threads_saves_with_correct_extension(client, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "load_session", lambda: {"path": str(tmp_path), "cookies_path": ""})
    monkeypatch.setattr(threads_module, "threads_cookiefile_candidates", lambda: ["/acct.txt"])
    monkeypatch.setattr(
        threads_module,
        "fetch_threads_media_any",
        lambda url, cfs: {"title": "A post", "items": [{"kind": "image", "url": "http://cdn/i.jpg", "thumbnail": None}]},
    )
    monkeypatch.setattr(download_module, "download_direct_url", lambda cdn_url, output_path, job_id: None)

    class SyncThread:
        def __init__(self, target=None, daemon=None):
            self._target = target

        def start(self):
            self._target()

    monkeypatch.setattr(threading, "Thread", SyncThread)

    resp = client.post(
        "/api/download",
        json={"url": "https://www.threads.com/@someone/post/abc123", "title": "My Post", "quality": "Best"},
    )
    assert resp.status_code == 200
    job_id = resp.get_json()["job_id"]
    assert jobs_module.jobs[job_id]["status"] == "done"
    assert jobs_module.jobs[job_id]["filename"].endswith(".jpg")


def test_start_download_linkedin_image_saves_as_jpg(client, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "load_session", lambda: {"path": str(tmp_path), "cookies_path": ""})
    monkeypatch.setattr(
        linkedin_module,
        "fetch_linkedin_image_post",
        lambda url: {"title": "A post", "items": [{"kind": "image", "url": "http://cdn/i.jpg", "thumbnail": None}]},
    )
    monkeypatch.setattr(download_module, "download_direct_url", lambda cdn_url, output_path, job_id: None)

    class SyncThread:
        def __init__(self, target=None, daemon=None):
            self._target = target

        def start(self):
            self._target()

    monkeypatch.setattr(threading, "Thread", SyncThread)

    resp = client.post(
        "/api/download",
        json={"url": "https://www.linkedin.com/posts/someone_activity-123-abcd", "title": "My Post", "quality": "Best"},
    )
    assert resp.status_code == 200
    job_id = resp.get_json()["job_id"]
    assert jobs_module.jobs[job_id]["status"] == "done"
    assert jobs_module.jobs[job_id]["filename"].endswith(".jpg")


# ---- remote downloads stage into a temp dir, not the configured folder ----


def test_start_download_remote_uses_a_temp_dir_not_the_configured_folder(client, monkeypatch):
    monkeypatch.setattr(threading, "Thread", _NoOpThread)
    resp = client.post(
        "/api/download",
        json={"url": "https://www.tiktok.com/@user/video/1", "title": "Video", "quality": "720p"},
        headers={"Host": "example.com"},
    )
    assert resp.status_code == 200
    job_id = resp.get_json()["job_id"]
    filepath = jobs_module.jobs[job_id]["filepath"]
    assert os.path.dirname(filepath) != os.path.expanduser("~/Downloads")
    assert os.path.basename(os.path.dirname(filepath)).startswith("omniflow-")


def test_start_download_instagram_no_cookies_succeeds_scheduling_and_fails_async(client, monkeypatch, tmp_path):
    # With no valid cookies configured, the Instagram download branch falls through
    # to the standard yt-dlp path and schedules a background job (status code 200).
    monkeypatch.setattr(config, "load_session", lambda: {"path": str(tmp_path), "cookies_path": ""})
    
    # Mock yt_dlp to fail with a login/empty media response error
    class MockYoutubeDL:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def download(self, urls):
            raise yt_dlp.utils.DownloadError("ERROR: [Instagram] abc: Instagram sent an empty media response.")

    monkeypatch.setattr(yt_dlp, "YoutubeDL", MockYoutubeDL)
    
    resp = client.post(
        "/api/download",
        json={"url": "https://www.instagram.com/reel/abc/", "title": "Video", "quality": "720p"},
    )
    assert resp.status_code == 200
    job_id = resp.get_json()["job_id"]
    
    for _ in range(50):
        if jobs_module.jobs[job_id]["status"] != "running":
            break
        time.sleep(0.05)
        
    assert jobs_module.jobs[job_id]["status"] == "error"
    assert "Không thể tải video từ tài khoản Private" in jobs_module.jobs[job_id]["text"]


def test_start_download_instagram_resolver_error_maps_to_friendly_message(client, monkeypatch, tmp_path):
    # When Instagram rejects an otherwise-valid-looking session mid-download, the
    # async run_instagram() handler must surface describe_extraction_error()'s
    # plain message, never a raw traceback.
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    save_session(str(tmp_path), str(cookies_file))

    def raise_error(url, cookies_path):
        raise InstagramAuthError("Instagram sent an empty media response.")

    monkeypatch.setattr(instagram_module, "fetch_instagram_media", raise_error)

    resp = client.post(
        "/api/download",
        json={"url": "https://www.instagram.com/reel/abc/", "title": "Video", "quality": "Video"},
    )
    job_id = resp.get_json()["job_id"]

    for _ in range(50):
        if jobs_module.jobs[job_id]["status"] != "running":
            break
        time.sleep(0.05)

    assert jobs_module.jobs[job_id]["status"] == "error"
    assert "Không thể tải video từ tài khoản Private" in jobs_module.jobs[job_id]["text"]


def test_start_download_instagram_image_writes_a_jpg(client, monkeypatch, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    save_session(str(tmp_path), str(cookies_file))
    monkeypatch.setattr(config, "resolve_save_dir", lambda path: str(tmp_path))
    monkeypatch.setattr(
        instagram_module,
        "fetch_instagram_media",
        lambda url, cookies_path: {"title": "A photo", "items": [{"kind": "image", "url": "http://cdn/pic.jpg", "thumbnail": "http://cdn/pic.jpg"}]},
    )

    def fake_download(cdn_url, output_path, job_id, chunk_size=131072):
        with open(output_path, "wb") as f:
            f.write(b"fake-image-bytes")

    monkeypatch.setattr(download_module, "download_direct_url", fake_download)

    resp = client.post(
        "/api/download",
        json={"url": "https://www.instagram.com/p/abc/", "title": "A photo", "quality": "Image"},
    )
    job_id = resp.get_json()["job_id"]

    for _ in range(50):
        if jobs_module.jobs[job_id]["status"] != "running":
            break
        time.sleep(0.05)

    job = jobs_module.jobs[job_id]
    assert job["status"] == "done"
    assert job["filename"].endswith(".jpg")
    assert os.path.exists(job["filepath"])


def test_start_download_instagram_entry_index_picks_that_carousel_item(client, monkeypatch, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    save_session(str(tmp_path), str(cookies_file))
    monkeypatch.setattr(config, "resolve_save_dir", lambda path: str(tmp_path))
    monkeypatch.setattr(
        instagram_module,
        "fetch_instagram_media",
        lambda url, cookies_path: {
            "title": "Carousel",
            "items": [
                {"kind": "image", "url": "http://cdn/pic.jpg", "thumbnail": None},
                {"kind": "video", "url": "http://cdn/clip.mp4", "thumbnail": None},
            ],
        },
    )

    captured = {}

    def fake_download(cdn_url, output_path, job_id, chunk_size=131072):
        captured["url"] = cdn_url
        with open(output_path, "wb") as f:
            f.write(b"fake")

    monkeypatch.setattr(download_module, "download_direct_url", fake_download)

    # entry_index 2 (1-based) -> the video slide.
    resp = client.post(
        "/api/download",
        json={"url": "https://www.instagram.com/p/abc/", "title": "Carousel", "quality": "Video", "entry_index": 2},
    )
    job_id = resp.get_json()["job_id"]

    for _ in range(50):
        if jobs_module.jobs[job_id]["status"] != "running":
            break
        time.sleep(0.05)

    job = jobs_module.jobs[job_id]
    assert job["status"] == "done"
    assert captured["url"] == "http://cdn/clip.mp4"
    assert job["filename"].endswith(".mp4")


# ---- /api/download-file/<job_id> ----


def test_download_file_rejected_when_local(client, tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_text("fake video bytes")
    jobs_module.jobs["job-remote-1"] = {"status": "done", "filename": "clip.mp4", "filepath": str(video)}
    resp = client.get("/api/download-file/job-remote-1")
    assert resp.status_code == 403


def test_download_file_404_for_unknown_job(client):
    resp = client.get("/api/download-file/does-not-exist", headers={"Host": "example.com"})
    assert resp.status_code == 404


def test_download_file_404_when_job_not_done(client):
    jobs_module.jobs["job-remote-2"] = {"status": "running", "filename": None, "filepath": None}
    resp = client.get("/api/download-file/job-remote-2", headers={"Host": "example.com"})
    assert resp.status_code == 404


def test_download_file_serves_and_cleans_up(client, tmp_path):
    job_dir = tmp_path / "omniflow-abc123"
    job_dir.mkdir()
    video = job_dir / "clip.mp4"
    video.write_bytes(b"fake video bytes")
    jobs_module.jobs["job-remote-3"] = {"status": "done", "filename": "clip.mp4", "filepath": str(video)}

    resp = client.get("/api/download-file/job-remote-3", headers={"Host": "example.com"})

    assert resp.status_code == 200
    assert resp.data == b"fake video bytes"
    assert "clip.mp4" in resp.headers.get("Content-Disposition", "")
    assert not job_dir.exists()


# ---- /api/check flat playlist response ----


def test_check_link_youtube_playlist_returns_items_with_urls(client, monkeypatch):
    info = {
        "_type": "playlist",
        "title": "My Playlist",
        "entries": [
            {"id": "v1", "title": "First", "url": "https://youtube.com/watch?v=v1", "duration": 65,
             "thumbnails": [{"url": "https://img/1.jpg"}]},
            {"id": "v2", "title": "Second", "url": "https://youtube.com/watch?v=v2", "duration": 30},
        ],
    }
    monkeypatch.setattr(extraction_module, "extract_video_info", lambda url: info)
    resp = client.post("/api/check", json={"url": "https://www.youtube.com/playlist?list=PLxyz"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["type"] == "playlist"
    assert body["platform"] == "YouTube"
    assert [i["url"] for i in body["items"]] == [
        "https://youtube.com/watch?v=v1",
        "https://youtube.com/watch?v=v2",
    ]
    # PRD §7: titles are CLEAN (no numeric prefix) - the ordering lives in the
    # separate `position` field, used for UI numbering only, never the filename.
    assert [i["title"] for i in body["items"]] == ["First", "Second"]
    assert [i["position"] for i in body["items"]] == [1, 2]
    assert all(i["is_available"] for i in body["items"])
    assert body["items"][0]["duration"] == "01:05"
    assert body["items"][0]["qualities"] == classify.PLAYLIST_QUALITIES
    assert body["truncated"] is False


def test_normalize_youtube_playlist_url_rewrites_watch_to_playlist():
    norm = classify.normalize_youtube_playlist_url
    # The owner's exact test case: watch?v=...&list=... MUST become playlist?list=...
    assert norm("https://www.youtube.com/watch?v=-It5L-gC6nA&list=PLIILL6veL783kKkdiIybbxARNY9bAVQYe") == (
        "https://www.youtube.com/playlist?list=PLIILL6veL783kKkdiIybbxARNY9bAVQYe"
    )
    # youtu.be short links carry the same rewrite.
    assert norm("https://youtu.be/-It5L-gC6nA?list=PLabc999") == "https://www.youtube.com/playlist?list=PLabc999"
    # Already-canonical playlist URL is idempotent.
    assert norm("https://www.youtube.com/playlist?list=PLxyz") == "https://www.youtube.com/playlist?list=PLxyz"
    # Mix/Radio (list=RD...) only resolves via the seed watch URL -> left untouched.
    assert norm("https://www.youtube.com/watch?v=abc&list=RDabc123") == "https://www.youtube.com/watch?v=abc&list=RDabc123"
    # A plain video (no list=) and non-YouTube URLs are unchanged.
    assert norm("https://www.youtube.com/watch?v=jNQXAC9IVRw") == "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    assert norm("https://www.tiktok.com/@x/video/123") == "https://www.tiktok.com/@x/video/123"


def test_extract_video_info_passes_canonical_playlist_url_to_ytdlp(monkeypatch):
    # The watch?v=...&list=... URL must reach yt-dlp as playlist?list=... - otherwise
    # yt-dlp's /watch video extractor returns a single video, not the list.
    seen = {}

    class FakeYDL:
        def __init__(self, opts):
            seen["opts"] = opts
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def extract_info(self, url, download=False):
            seen["url"] = url
            return {"_type": "playlist", "title": "PL", "entries": []}

    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYDL)
    extraction_module.extract_video_info(
        classify.classify_url("https://www.youtube.com/watch?v=-It5L-gC6nA&list=PLIILL6veL783kKkdiIybbxARNY9bAVQYe")
    )
    assert seen["url"] == "https://www.youtube.com/playlist?list=PLIILL6veL783kKkdiIybbxARNY9bAVQYe"
    assert seen["opts"]["noplaylist"] is False  # i.e. --yes-playlist
    assert seen["opts"]["extract_flat"] == "in_playlist"


def test_check_link_single_item_playlist_is_not_numbered(client, monkeypatch):
    # A 1-video "playlist" (e.g. a channel with one upload) keeps a clean title -
    # the frontend renders it as a plain single video, not a numbered list.
    info = {
        "_type": "playlist",
        "title": "One video channel",
        "entries": [{"id": "solo", "title": "Only Video", "url": "https://youtube.com/watch?v=solo", "duration": 42}],
    }
    monkeypatch.setattr(extraction_module, "extract_video_info", lambda url: info)
    resp = client.post("/api/check", json={"url": "https://www.youtube.com/@onevid"})
    body = resp.get_json()
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "Only Video"  # no "01. " prefix


def test_check_link_youtube_playlist_flags_dead_videos_as_unavailable(client, monkeypatch):
    info = {
        "_type": "playlist",
        "title": "Mixed",
        "entries": [
            {"id": "ok1", "title": "Good One", "url": "https://youtube.com/watch?v=ok1", "duration": 100},
            {"id": "p", "title": "[Private video]", "url": "https://youtube.com/watch?v=p"},
            {"id": "d", "title": "[Deleted video]", "url": "https://youtube.com/watch?v=d"},
            # No duration -> treated as unavailable even without a dead-video title.
            {"id": "nod", "title": "No duration", "url": "https://youtube.com/watch?v=nod"},
            {"id": "ok2", "title": "Good Two", "url": "https://youtube.com/watch?v=ok2", "duration": 50},
        ],
    }
    monkeypatch.setattr(extraction_module, "extract_video_info", lambda url: info)
    resp = client.post("/api/check", json={"url": "https://www.youtube.com/playlist?list=PLxyz"})
    body = resp.get_json()
    # Dead videos are KEPT (so numbering stays true) but flagged unavailable.
    assert [i["is_available"] for i in body["items"]] == [True, False, False, False, True]
    # Titles stay clean; `position` keeps the true 1-based order even across dead ones.
    assert [i["title"] for i in body["items"]] == [
        "Good One", "[Private video]", "[Deleted video]", "No duration", "Good Two",
    ]
    assert [i["position"] for i in body["items"]] == [1, 2, 3, 4, 5]


def test_check_link_youtube_playlist_flags_truncation_at_the_cap(client, monkeypatch):
    entries = [{"id": f"v{i}", "title": f"V{i}", "url": f"https://youtube.com/watch?v=v{i}", "duration": 60}
               for i in range(classify.PLAYLIST_ITEM_CAP)]
    monkeypatch.setattr(extraction_module, "extract_video_info", lambda url: {"_type": "playlist", "title": "Big", "entries": entries})
    resp = client.post("/api/check", json={"url": "https://www.youtube.com/@somechannel"})
    body = resp.get_json()
    assert body["truncated"] is True
    assert len(body["items"]) == classify.PLAYLIST_ITEM_CAP
    # Title stays clean; position carries the ordering (the frontend zero-pads it).
    assert body["items"][0]["title"] == "V0"
    assert body["items"][0]["position"] == 1


def test_check_link_instagram_story_playlist_carries_original_entry_index(client, monkeypatch):
    # A Story mixing a photo (no formats) and videos: the kept video items must
    # carry their ORIGINAL 1-based position, not their filtered position.
    info = {
        "_type": "playlist",
        "title": "Story",
        "entries": [
            {"id": "a", "title": "Photo", },  # no formats -> dropped, but occupies index 1
            {"id": "b", "title": "Vid1", "formats": [{"height": 720}], "duration": 10},
            {"id": "c", "title": "Vid2", "formats": [{"height": 1080}], "duration": 8},
        ],
    }
    monkeypatch.setattr(extraction_module, "extract_video_info", lambda url: info)
    resp = client.post("/api/check", json={"url": "https://www.instagram.com/stories/someone/1/"})
    body = resp.get_json()
    assert [i["entry_index"] for i in body["items"]] == [2, 3]
    assert [i["title"] for i in body["items"]] == ["Vid1", "Vid2"]


# ---- /api/download-batch ----


def test_start_batch_download_requires_items(client):
    resp = client.post("/api/download-batch", json={"url": "https://youtube.com/playlist?list=x", "items": []})
    assert resp.status_code == 400


def test_start_batch_download_rejected_when_remote(client):
    resp = client.post(
        "/api/download-batch",
        json={"url": "https://youtube.com/playlist?list=x", "items": [{"title": "a", "url": "u"}]},
        headers={"Host": "example.com"},
    )
    assert resp.status_code == 403
    assert "locally" in resp.get_json()["error"]


def test_start_batch_download_schedules_and_reports_total(client, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "load_session", lambda: {"path": str(tmp_path)})
    monkeypatch.setattr(config, "resolve_save_dir", lambda path: str(tmp_path))
    monkeypatch.setattr(threading, "Thread", _NoOpThread)
    resp = client.post(
        "/api/download-batch",
        json={
            "url": "https://youtube.com/playlist?list=x",
            "quality": "720p",
            "items": [{"title": "A", "url": "u1"}, {"title": "B", "url": "u2"}],
        },
    )
    assert resp.status_code == 200
    job_id = resp.get_json()["job_id"]
    assert jobs_module.jobs[job_id]["total"] == 2


def test_start_batch_download_downloads_all_items_in_parallel(client, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "load_session", lambda: {"path": str(tmp_path)})
    monkeypatch.setattr(config, "resolve_save_dir", lambda path: str(tmp_path))
    monkeypatch.setattr(paths, "get_ffmpeg_path", lambda: "/ff")

    downloaded = []
    lock = __import__("threading").Lock()

    def fake_download_one(url, save_dir, title, quality, ffmpeg_bin, job_id, entry_index=None, on_progress=None):
        with lock:
            downloaded.append((url, title, quality))
        if on_progress:
            on_progress(100)
        out = os.path.join(save_dir, f"{title}.mp4")
        with open(out, "wb") as f:
            f.write(b"x")
        return out

    monkeypatch.setattr(download_module, "download_one_video", fake_download_one)

    resp = client.post(
        "/api/download-batch",
        json={
            "url": "https://youtube.com/playlist?list=x",
            "quality": "720p",
            "items": [
                {"title": "A", "url": "https://youtube.com/watch?v=a"},
                {"title": "B", "url": "https://youtube.com/watch?v=b"},
            ],
        },
    )
    job_id = resp.get_json()["job_id"]
    for _ in range(50):
        if jobs_module.jobs[job_id]["status"] != "running":
            break
        time.sleep(0.05)

    job = jobs_module.jobs[job_id]
    assert job["status"] == "done"
    assert job["saved_count"] == 2
    # Parallel -> order isn't guaranteed, so compare as a set.
    assert set(downloaded) == {
        ("https://youtube.com/watch?v=a", "A", "720p"),
        ("https://youtube.com/watch?v=b", "B", "720p"),
    }
    # Per-item progress is exposed, one entry per video, all finished.
    assert [p["status"] for p in job["items_progress"]] == ["done", "done"]
    assert all(p["percent"] == 100 for p in job["items_progress"])


def test_start_batch_download_skips_a_failing_item_and_keeps_going(client, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "load_session", lambda: {"path": str(tmp_path)})
    monkeypatch.setattr(config, "resolve_save_dir", lambda path: str(tmp_path))
    monkeypatch.setattr(paths, "get_ffmpeg_path", lambda: "/ff")

    def fake_download_one(url, save_dir, title, quality, ffmpeg_bin, job_id, entry_index=None, on_progress=None):
        if title == "B":
            raise yt_dlp.utils.DownloadError("boom")
        out = os.path.join(save_dir, f"{title}.mp4")
        with open(out, "wb") as f:
            f.write(b"x")
        return out

    monkeypatch.setattr(download_module, "download_one_video", fake_download_one)

    resp = client.post(
        "/api/download-batch",
        json={
            "url": "https://youtube.com/playlist?list=x",
            "quality": "Best",
            "items": [{"title": "A", "url": "ua"}, {"title": "B", "url": "ub"}, {"title": "C", "url": "uc"}],
        },
    )
    job_id = resp.get_json()["job_id"]
    for _ in range(50):
        if jobs_module.jobs[job_id]["status"] != "running":
            break
        time.sleep(0.05)

    job = jobs_module.jobs[job_id]
    # One item failed, the other two still downloaded - the batch finishes "done".
    assert job["status"] == "done"
    assert job["saved_count"] == 2
    assert "1 failed" in job["text"]
