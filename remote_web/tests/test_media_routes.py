"""POST /api/check, /api/download, /api/download-batch - mirrors
tests/test_api.py's conventions (mocking backend.extraction.extract_video_info,
backend.download.download_one_video, etc.) but proves the one behavior that
must differ from backend/app.py: Instagram/Threads are NOT rejected here."""

import pytest

from backend import config as backend_config
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


def test_download_tiktok_resolver_audio_only_saves_the_soundtrack_as_mp3(client, monkeypatch, tmp_path):
    # Mirrors tests/test_api.py: a TikTok video that falls back to tikwm.com
    # must honor "Audio Only" by saving the soundtrack, not the mp4
    # (docs/internal/MISTAKES.md 2026-09-30).
    from backend import tiktok as tiktok_module

    monkeypatch.setattr("remote_web.routes.media.ffmpeg_locator.resolve_ffmpeg_binary", lambda: "/fake/ffmpeg")
    monkeypatch.setattr(config, "TEMP_ROOT", str(tmp_path))

    import yt_dlp

    def yt_fails(opts):
        raise yt_dlp.utils.DownloadError("Unable to extract universal data for rehydration")

    monkeypatch.setattr(yt_dlp, "YoutubeDL", yt_fails)
    monkeypatch.setattr(
        tiktok_module,
        "fetch_tiktok_post",
        lambda url: {
            "title": "A real video",
            "items": [{"kind": "video", "url": "http://cdn/v.mp4", "thumbnail": None}],
            "audio_url": "http://cdn/sound.mp3",
        },
    )
    fetched = []

    def fake_direct(cdn_url, output_path, job_id, *args, **kwargs):
        fetched.append((cdn_url, output_path))
        with open(output_path, "wb") as f:
            f.write(b"fake mp3")

    monkeypatch.setattr(download_module, "download_direct_url", fake_direct)

    resp = client.post(
        "/api/download",
        json={"url": "https://www.tiktok.com/@someone/video/123", "title": "A real video", "quality": "Audio Only"},
    )
    assert resp.status_code == 200
    job = _wait_for_job(resp.get_json()["job_id"])
    assert job["status"] == "done"
    assert [url for url, _ in fetched] == ["http://cdn/sound.mp3"]
    assert job["filename"].endswith(".mp3")


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


def test_download_batch_linkedin_document_zips_the_selected_pages(client, monkeypatch, tmp_path):
    from backend import linkedin as linkedin_module
    from backend import shortlinks

    shortlinks._cache.clear()
    monkeypatch.setattr(shortlinks, "_fetch_location", lambda url: "https://www.linkedin.com/posts/someone_deck-ugcPost-1-abcd/")
    monkeypatch.setattr(config, "TEMP_ROOT", str(tmp_path))
    monkeypatch.setattr("remote_web.routes.media.ffmpeg_locator.resolve_ffmpeg_binary", lambda: "/fake/ffmpeg")
    pages = [{"kind": "image", "url": f"http://cdn/p{n}.jpg", "thumbnail": None} for n in (1, 2, 3)]
    monkeypatch.setattr(linkedin_module, "fetch_linkedin_image_post", lambda url: {"title": "UX Deck", "items": pages})

    def fake_direct(cdn_url, output_path, job_id, on_progress=None):
        with open(output_path, "wb") as f:
            f.write(cdn_url.encode())
        if on_progress:
            on_progress(100)

    monkeypatch.setattr(download_module, "download_direct_url", fake_direct)

    resp = client.post("/api/download-batch", json={
        "url": "https://lnkd.in/p/gGaVJcim",  # the short link the owner pasted
        "quality": "Best",
        "items": [{"title": f"UX Deck ({n})", "entry_index": n} for n in (1, 2, 3)],
    })
    assert resp.status_code == 200
    job = _wait_for_job(resp.get_json()["job_id"])
    assert job["status"] == "done" and job["saved_count"] == 3
    with zipfile.ZipFile(job["filepath"]) as zf:
        assert len(zf.namelist()) == 3 and all(n.endswith(".jpg") for n in zf.namelist())


def test_check_rednote_uses_the_synced_session_when_yt_dlp_fails(client, monkeypatch):
    import yt_dlp
    from backend import rednote as rednote_module

    def fake_extract(cls):
        raise yt_dlp.utils.DownloadError("No video formats found!")

    monkeypatch.setattr(extraction_module, "extract_video_info", fake_extract)
    monkeypatch.setattr(rednote_module, "rednote_cookiefile_candidates", lambda: ["/synced.txt"])
    monkeypatch.setattr(
        rednote_module, "fetch_rednote_post_any",
        lambda url, cfs: {"title": "魔法", "items": [{"kind": "video", "url": "https://cdn/v.mp4", "thumbnail": None}]},
    )
    resp = client.post("/api/check", json={"url": "https://www.rednote.com/discovery/item/6aae0dc50000000011036339?xsec_token=T"})
    body = resp.get_json()
    assert resp.status_code == 200 and body["type"] == "video" and body["platform"] == "RedNote"


def test_check_rednote_without_a_synced_session_explains_what_to_do(client, monkeypatch):
    import yt_dlp
    from backend import rednote as rednote_module

    monkeypatch.setattr(extraction_module, "extract_video_info", lambda cls: (_ for _ in ()).throw(yt_dlp.utils.DownloadError("No video formats found!")))
    monkeypatch.setattr(rednote_module, "rednote_cookiefile_candidates", lambda: [])
    resp = client.post("/api/check", json={"url": "https://www.rednote.com/discovery/item/6aae0dc50000000011036339?xsec_token=T"})
    assert resp.status_code == 400 and "RedNote" in resp.get_json()["error"]


def test_check_rednote_expired_link_tells_the_visitor_to_copy_a_fresh_one(client, monkeypatch):
    import yt_dlp
    from backend import rednote as rednote_module

    monkeypatch.setattr(extraction_module, "extract_video_info", lambda cls: (_ for _ in ()).throw(yt_dlp.utils.DownloadError("No video formats found!")))
    monkeypatch.setattr(rednote_module, "rednote_cookiefile_candidates", lambda: ["/synced.txt"])

    def expired(url, cfs):
        raise rednote_module.RedNoteExpiredError("404")

    monkeypatch.setattr(rednote_module, "fetch_rednote_post_any", expired)
    resp = client.post("/api/check", json={"url": "https://www.rednote.com/discovery/item/6aae0dc50000000011036339?xsec_token=T"},
                       headers={"X-Language": "en"})
    assert resp.status_code == 400 and "fresh share link" in resp.get_json()["error"]


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


def test_download_batch_touches_the_zip_during_the_run(client, monkeypatch, tmp_path):
    # final-review finding #3: recompute_overall() must call zipper.touch()
    # on every progress tick (not only when an item finishes), so an
    # in-flight batch's zip_dir never goes stale enough for reaper.py's
    # mtime sweep to reap it mid-batch. Light integration check only - the
    # reaper interaction itself is already covered by test_reaper.py.
    monkeypatch.setattr(config, "TEMP_ROOT", str(tmp_path))
    monkeypatch.setattr("remote_web.routes.media.ffmpeg_locator.resolve_ffmpeg_binary", lambda: "/fake/ffmpeg")

    touch_calls = []
    original_touch = zipper_module.BatchZipper.touch

    def spy_touch(self):
        touch_calls.append(True)
        return original_touch(self)

    monkeypatch.setattr(zipper_module.BatchZipper, "touch", spy_touch)

    def fake_download_one_video(url, save_dir, title, quality, ffmpeg_bin, job_id, entry_index=None, on_progress=None):
        if on_progress:
            on_progress(50)
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
        "items": [{"title": "Video A", "url": "https://youtube.com/watch?v=a"}],
    })
    job_id = resp.get_json()["job_id"]
    job = _wait_for_job(job_id)
    assert job["status"] == "done"
    # At least one on_progress tick (percent=50) plus the final done tick
    # both go through recompute_overall(), so touch() must fire more than
    # once across the run.
    assert len(touch_calls) >= 2


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


def test_download_batch_zip_keeps_the_selected_item_order(client, monkeypatch, tmp_path):
    # Items download BATCH_CONCURRENCY at a time, so they finish in whatever
    # order the network allows. The archive (and therefore the order the phone
    # saves them into Photos) must still match the order they were listed in.
    import time

    monkeypatch.setattr(config, "TEMP_ROOT", str(tmp_path))
    monkeypatch.setattr("remote_web.routes.media.ffmpeg_locator.resolve_ffmpeg_binary", lambda: "/fake/ffmpeg")
    delays = {"A": 0.3, "B": 0.2, "C": 0.1, "D": 0.0}  # finish order: C, D, B, A

    def fake_download_one_video(url, save_dir, title, quality, ffmpeg_bin, job_id, entry_index=None, on_progress=None):
        time.sleep(delays[title])
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
        "items": [{"title": t, "url": f"https://youtube.com/watch?v={t}"} for t in "ABCD"],
    })
    job = _wait_for_job(resp.get_json()["job_id"])
    assert job["status"] == "done"
    with zipfile.ZipFile(job["filepath"]) as zf:
        assert zf.namelist() == ["A.mp4", "B.mp4", "C.mp4", "D.mp4"]


@pytest.mark.parametrize("setting,count,expected", [
    (30, 30, True), (30, 12, False),
    (100, 100, True), (100, 99, False),
    (200, 150, False), (200, 200, True),
    (500, 150, False), (0, 150, False),
])
def test_check_truncated_follows_the_playlist_limit_setting(client, monkeypatch, setting, count, expected):
    backend_config.save_session("/tmp", playlist_limit_val=setting)
    entries = [{"id": f"v{i}", "title": f"V{i}", "url": f"https://youtube.com/watch?v=v{i}", "duration": 60}
               for i in range(count)]
    monkeypatch.setattr(extraction_module, "extract_video_info",
                        lambda cls: {"_type": "playlist", "title": "P", "entries": entries})
    body = client.post("/api/check", json={"url": "https://www.youtube.com/playlist?list=PLxyz"}).get_json()
    assert body["truncated"] is expected
    assert len(body["items"]) == count


def test_check_x_photo_tweet_uses_the_embed_resolver_on_the_cloud_too(client, monkeypatch):
    import yt_dlp
    from backend import xposts as xposts_module

    def fake_extract(cls):
        raise yt_dlp.utils.DownloadError("No video could be found in this tweet")

    monkeypatch.setattr(extraction_module, "extract_video_info", fake_extract)
    monkeypatch.setattr(xposts_module, "fetch_x_photo_post", lambda url: {"title": "Pics", "items": [{"kind": "image", "url": f"u{i}", "thumbnail": "t"} for i in range(2)]})
    body = client.post("/api/check", json={"url": "https://x.com/a/status/2109940833076031916"}).get_json()
    assert body["type"] == "playlist" and body["platform"] == "X" and len(body["items"]) == 2


def test_a_rednote_share_link_skips_ytdlp_on_the_cloud_too(client, monkeypatch):
    from backend import rednote as rednote_module

    seen = {}

    def fake_extract(cls):
        raise AssertionError("yt-dlp must not be called for a share link")

    monkeypatch.setattr(extraction_module, "extract_video_info", lambda cls: rednote_module.skip_ytdlp_for_short_link(cls.extraction_url))
    monkeypatch.setattr(rednote_module, "rednote_cookiefile_candidates", lambda: ["/synced.txt"])
    monkeypatch.setattr(rednote_module, "fetch_rednote_post_any", lambda url, files: seen.setdefault("url", url) and {"title": "N", "items": [{"kind": "video", "url": "v", "thumbnail": "t"}]})
    body = client.post("/api/check", json={"url": "https://xhslink.com/o/4AMx4jW7ZFx"}).get_json()
    assert body["type"] == "video" and seen["url"] == "https://xhslink.com/o/4AMx4jW7ZFx"


def test_a_rednote_login_redirect_on_the_cloud_says_the_server_is_blocked_and_points_to_the_mac_app(client, monkeypatch):
    import yt_dlp
    from backend import rednote as rednote_module

    monkeypatch.setattr(extraction_module, "extract_video_info", lambda cls: (_ for _ in ()).throw(yt_dlp.utils.DownloadError("x")))
    monkeypatch.setattr(rednote_module, "rednote_cookiefile_candidates", lambda: ["/synced.txt"])

    def logged_out(url, files):
        raise rednote_module.RedNoteAuthError("login")

    monkeypatch.setattr(rednote_module, "fetch_rednote_post_any", logged_out)
    resp = client.post("/api/check", json={"url": "https://xhslink.com/o/4AMx4jW7ZFx"}, headers={"X-Language": "en"})
    assert resp.status_code == 400
    assert "Mac app" in resp.get_json()["error"] and "server" in resp.get_json()["error"]
