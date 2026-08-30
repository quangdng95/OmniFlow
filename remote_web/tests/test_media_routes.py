"""POST /api/check, /api/download, /api/download-batch - mirrors
tests/test_api.py's conventions (mocking backend.extraction.extract_video_info,
backend.download.download_one_video, etc.) but proves the one behavior that
must differ from backend/app.py: Instagram/Threads are NOT rejected here."""

import pytest

from backend import cookies as backend_cookies
from backend import extraction as extraction_module
from backend import instagram as instagram_module
from remote_web import config
from remote_web.app import app as remote_app


@pytest.fixture
def client(isolated_state_file, tmp_path, monkeypatch):
    from backend import config as backend_config

    monkeypatch.setattr(backend_config, "CONFIG_FILE", str(tmp_path / "backend-config.json"))
    remote_app.config["TESTING"] = True
    return remote_app.test_client()


@pytest.fixture(autouse=True)
def trusted(client):
    token = config.get_or_create_token()
    client.post("/unlock", data={"token": token})
    return client


@pytest.fixture(autouse=True)
def no_real_browser_cookies(monkeypatch):
    # Same reasoning as tests/conftest.py's no_browser_cookie_scan fixture -
    # never let a test hit the real machine's browser cookie DBs.
    monkeypatch.setattr(backend_cookies, "cookiefiles_from_browsers", lambda domain="instagram.com": [])


# ---- /api/check ----


def test_check_requires_trust(monkeypatch):
    remote_app.config["TESTING"] = True
    anon_client = remote_app.test_client()
    resp = anon_client.post("/api/check", json={"url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"})
    assert resp.status_code == 401


def test_check_missing_url_returns_400(client):
    resp = client.post("/api/check", json={})
    assert resp.status_code == 400


def test_check_returns_single_video_info(client, monkeypatch):
    monkeypatch.setattr(
        extraction_module, "extract_video_info",
        lambda cls: {"title": "Test Video", "uploader": "someone", "duration": 65, "formats": []},
    )
    resp = client.post("/api/check", json={"url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["type"] == "video"
    assert body["title"] == "Test Video"
    assert body["platform"] == "YouTube"


def test_check_instagram_post_is_not_rejected(client, monkeypatch):
    # The one behavior that must differ from backend/app.py's check_link():
    # no is_local_request() gate exists here at all.
    monkeypatch.setattr(
        backend_cookies, "instagram_cookiefile_candidates", lambda: ["/fake/cookies.txt"]
    )
    monkeypatch.setattr(
        instagram_module, "fetch_instagram_media_any",
        lambda url, cookiefiles: {"title": "IG Post", "items": [{"kind": "image", "url": "https://cdn/x.jpg", "thumbnail": "https://cdn/x.jpg"}]},
    )
    resp = client.post("/api/check", json={"url": "https://www.instagram.com/p/DYTRs5Loe6A/"})
    assert resp.status_code == 200
    assert resp.get_json()["type"] == "video"


def test_check_instagram_with_no_session_returns_friendly_error_not_403(client, monkeypatch):
    monkeypatch.setattr(backend_cookies, "instagram_cookiefile_candidates", lambda: [])
    resp = client.post("/api/check", json={"url": "https://www.instagram.com/p/DYTRs5Loe6A/"})
    assert resp.status_code == 400  # not 403 - this app has no local/remote concept
    assert "Instagram" in resp.get_json()["error"]


def test_check_extraction_failure_returns_friendly_message(client, monkeypatch):
    import yt_dlp

    def raise_error(cls):
        raise yt_dlp.utils.DownloadError("Video unavailable")

    monkeypatch.setattr(extraction_module, "extract_video_info", raise_error)
    resp = client.post("/api/check", json={"url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"})
    assert resp.status_code == 400
    assert "github.com" not in resp.get_json()["error"].lower()


def test_check_playlist_returns_items(client, monkeypatch):
    monkeypatch.setattr(
        extraction_module, "extract_video_info",
        lambda cls: {
            "_type": "playlist", "title": "My Playlist",
            "entries": [
                {"id": "a", "title": "Video A", "duration": 30, "url": "https://youtube.com/watch?v=a"},
                {"id": "b", "title": "Video B", "duration": 40, "url": "https://youtube.com/watch?v=b"},
            ],
        },
    )
    resp = client.post("/api/check", json={"url": "https://www.youtube.com/playlist?list=PL123"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["type"] == "playlist"
    assert len(body["items"]) == 2


# ---- /api/download ----

import threading
import time

from backend import download as download_module
from backend import jobs as jobs_module


@pytest.fixture(autouse=True)
def clear_jobs():
    jobs_module.jobs.clear()
    yield
    jobs_module.jobs.clear()


def _wait_for_job(job_id, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = jobs_module.jobs.get(job_id)
        if job and job["status"] in ("done", "error", "cancelled"):
            return job
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} never finished: {jobs_module.jobs.get(job_id)}")


def test_download_requires_trust():
    remote_app.config["TESTING"] = True
    anon_client = remote_app.test_client()
    resp = anon_client.post("/api/download", json={"url": "https://www.youtube.com/watch?v=jNQXAC9IVRw", "title": "x", "quality": "Best"})
    assert resp.status_code == 401


def test_download_missing_ffmpeg_returns_friendly_error(client, monkeypatch, tmp_path):
    monkeypatch.setattr("remote_web.routes.media.ffmpeg_locator.resolve_ffmpeg_binary", lambda: None)
    resp = client.post("/api/download", json={"url": "https://www.youtube.com/watch?v=jNQXAC9IVRw", "title": "x", "quality": "Best"})
    assert resp.status_code == 400
    assert "FFmpeg" in resp.get_json()["error"]


def test_download_always_stages_into_a_temp_dir_not_a_configured_folder(client, monkeypatch, tmp_path):
    monkeypatch.setattr("remote_web.routes.media.ffmpeg_locator.resolve_ffmpeg_binary", lambda: "/fake/ffmpeg")
    monkeypatch.setattr(config, "TEMP_ROOT", str(tmp_path))

    captured = {}

    def fake_ydl_download(opts):
        class FakeYDL:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def download(self_inner, urls):
                captured["outtmpl"] = opts["outtmpl"]
                out_path = opts["outtmpl"].replace(".%(ext)s", ".mp4")
                with open(out_path, "wb") as f:
                    f.write(b"fake mp4 bytes")

        return FakeYDL()

    import yt_dlp

    monkeypatch.setattr(yt_dlp, "YoutubeDL", fake_ydl_download)
    monkeypatch.setattr(download_module, "ensure_h264", lambda *a, **k: None)

    resp = client.post("/api/download", json={"url": "https://www.youtube.com/watch?v=jNQXAC9IVRw", "title": "test video", "quality": "Best"})
    assert resp.status_code == 200
    job_id = resp.get_json()["job_id"]
    job = _wait_for_job(job_id)
    assert job["status"] == "done"
    assert str(tmp_path) in job["filepath"]


# ---- /api/download-batch ----

import os
import zipfile

from remote_web import zipper as zipper_module


def test_download_batch_requires_trust():
    remote_app.config["TESTING"] = True
    anon_client = remote_app.test_client()
    resp = anon_client.post("/api/download-batch", json={"url": "https://www.youtube.com/playlist?list=PL1", "quality": "Best", "items": []})
    assert resp.status_code == 401


def test_download_batch_no_items_returns_400(client):
    resp = client.post("/api/download-batch", json={"url": "https://www.youtube.com/playlist?list=PL1", "quality": "Best", "items": []})
    assert resp.status_code == 400


def test_download_batch_produces_a_zip_with_every_item(client, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "TEMP_ROOT", str(tmp_path))
    monkeypatch.setattr("remote_web.routes.media.ffmpeg_locator.resolve_ffmpeg_binary", lambda: "/fake/ffmpeg")

    def fake_download_one_video(url, save_dir, title, quality, ffmpeg_bin, job_id, entry_index=None, on_progress=None):
        out = os.path.join(save_dir, f"{title}.mp4")
        with open(out, "wb") as f:
            f.write(b"fake video")
        if on_progress:
            on_progress(100)
        return out

    monkeypatch.setattr(download_module, "download_one_video", fake_download_one_video)

    resp = client.post("/api/download-batch", json={
        "url": "https://www.youtube.com/playlist?list=PL1",
        "quality": "Best",
        "items": [
            {"title": "Video A", "url": "https://youtube.com/watch?v=a"},
            {"title": "Video B", "url": "https://youtube.com/watch?v=b"},
        ],
    })
    assert resp.status_code == 200
    job_id = resp.get_json()["job_id"]
    job = _wait_for_job(job_id)
    assert job["status"] == "done"
    assert job["saved_count"] == 2
    assert job["filepath"].endswith(".zip")
    with zipfile.ZipFile(job["filepath"]) as zf:
        assert len(zf.namelist()) == 2
        assert zf.getinfo(zf.namelist()[0]).compress_type == zipfile.ZIP_STORED


def test_download_batch_deletes_raw_files_as_it_goes(client, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "TEMP_ROOT", str(tmp_path))
    monkeypatch.setattr("remote_web.routes.media.ffmpeg_locator.resolve_ffmpeg_binary", lambda: "/fake/ffmpeg")
    written_paths = []

    def fake_download_one_video(url, save_dir, title, quality, ffmpeg_bin, job_id, entry_index=None, on_progress=None):
        out = os.path.join(save_dir, f"{title}.mp4")
        with open(out, "wb") as f:
            f.write(b"fake video")
        written_paths.append(out)
        if on_progress:
            on_progress(100)
        return out

    monkeypatch.setattr(download_module, "download_one_video", fake_download_one_video)

    resp = client.post("/api/download-batch", json={
        "url": "https://www.youtube.com/playlist?list=PL1",
        "quality": "Best",
        "items": [{"title": "Video A", "url": "https://youtube.com/watch?v=a"}],
    })
    job_id = resp.get_json()["job_id"]
    _wait_for_job(job_id)
    assert not os.path.exists(written_paths[0])


def test_download_batch_partial_failure_still_saves_the_rest(client, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "TEMP_ROOT", str(tmp_path))
    monkeypatch.setattr("remote_web.routes.media.ffmpeg_locator.resolve_ffmpeg_binary", lambda: "/fake/ffmpeg")

    def fake_download_one_video(url, save_dir, title, quality, ffmpeg_bin, job_id, entry_index=None, on_progress=None):
        if title == "Broken":
            raise ValueError("boom")
        out = os.path.join(save_dir, f"{title}.mp4")
        with open(out, "wb") as f:
            f.write(b"fake video")
        if on_progress:
            on_progress(100)
        return out

    monkeypatch.setattr(download_module, "download_one_video", fake_download_one_video)

    resp = client.post("/api/download-batch", json={
        "url": "https://www.youtube.com/playlist?list=PL1",
        "quality": "Best",
        "items": [
            {"title": "Broken", "url": "https://youtube.com/watch?v=broken"},
            {"title": "Good", "url": "https://youtube.com/watch?v=good"},
        ],
    })
    job_id = resp.get_json()["job_id"]
    job = _wait_for_job(job_id)
    assert job["status"] == "done"
    assert job["saved_count"] == 1
