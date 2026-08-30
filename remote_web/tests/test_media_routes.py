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
