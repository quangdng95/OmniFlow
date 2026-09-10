"""GET/POST /api/settings - language (remote_web's own file) + playlist_limit
(proxied through to backend.config's session, since
backend.extraction.extract_video_info reads it from there and the frontend's
Playlist Limit control is NOT gated behind isLocal(), unlike Target Path)."""

import io

import pytest

from backend import config as backend_config
from remote_web import config
from remote_web.app import app as remote_app


@pytest.fixture
def client(isolated_state_file, tmp_path, monkeypatch):
    monkeypatch.setattr(backend_config, "CONFIG_FILE", str(tmp_path / "backend-config.json"))
    remote_app.config["TESTING"] = True
    return remote_app.test_client()


def _unlock(client):
    token = config.get_or_create_token()
    client.post("/unlock", data={"token": token})


def test_get_settings_requires_trust(client):
    resp = client.get("/api/settings")
    assert resp.status_code == 401


def test_get_settings_defaults(client):
    _unlock(client)
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["language"] == "en"
    assert body["playlist_limit"] == 100


def test_post_settings_persists_language(client):
    _unlock(client)
    resp = client.post("/api/settings", json={"language": "vi"})
    assert resp.status_code == 200
    assert resp.get_json()["language"] == "vi"
    # Persists across requests, not just echoed back.
    assert client.get("/api/settings").get_json()["language"] == "vi"


def test_post_settings_playlist_limit_reaches_backend_config(client):
    _unlock(client)
    client.post("/api/settings", json={"playlist_limit": 500})
    assert backend_config.load_session()["playlist_limit"] == 500


def test_post_settings_playlist_limit_is_readable_back(client):
    _unlock(client)
    client.post("/api/settings", json={"playlist_limit": 30})
    resp = client.get("/api/settings")
    assert resp.get_json()["playlist_limit"] == 30


def test_post_settings_partial_update_does_not_reset_the_other_field(client):
    _unlock(client)
    client.post("/api/settings", json={"language": "vi"})
    client.post("/api/settings", json={"playlist_limit": 200})
    resp = client.get("/api/settings").get_json()
    assert resp["language"] == "vi"
    assert resp["playlist_limit"] == 200


# ---- POST /api/settings/cookies ----

NETSCAPE_COOKIE_LINE = ".instagram.com\tTRUE\t/\tTRUE\t1999999999\tsessionid\tabc123\n"


def test_upload_cookies_requires_trust(client):
    remote_app.config["TESTING"] = True
    anon_client = remote_app.test_client()
    resp = anon_client.post(
        "/api/settings/cookies",
        data={"cookies": (io.BytesIO(NETSCAPE_COOKIE_LINE.encode()), "cookies.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 401


def test_upload_cookies_saves_file_and_wires_into_backend_config(client, tmp_path, monkeypatch):
    _unlock(client)
    cookies_file_path = tmp_path / "remote_web_cookies.txt"
    monkeypatch.setattr("remote_web.routes.settings._COOKIES_FILE", str(cookies_file_path))

    resp = client.post(
        "/api/settings/cookies",
        data={"cookies": (io.BytesIO(NETSCAPE_COOKIE_LINE.encode()), "cookies.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["cookies_status"] == "valid"

    assert cookies_file_path.exists()
    assert cookies_file_path.read_text() == NETSCAPE_COOKIE_LINE
    assert oct(cookies_file_path.stat().st_mode)[-3:] == "600"

    session = backend_config.load_session()
    assert session["cookies_path"] == str(cookies_file_path)


def test_upload_cookies_rejects_missing_file(client):
    _unlock(client)
    resp = client.post("/api/settings/cookies", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_upload_cookies_rejects_empty_file(client):
    _unlock(client)
    resp = client.post(
        "/api/settings/cookies",
        data={"cookies": (io.BytesIO(b""), "cookies.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_upload_cookies_rejects_oversized_file(client):
    _unlock(client)
    too_big = b"x" * (64 * 1024 + 1)
    resp = client.post(
        "/api/settings/cookies",
        data={"cookies": (io.BytesIO(too_big), "cookies.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_get_settings_reports_cookies_status(client, tmp_path, monkeypatch):
    _unlock(client)
    cookies_file_path = tmp_path / "remote_web_cookies.txt"
    monkeypatch.setattr("remote_web.routes.settings._COOKIES_FILE", str(cookies_file_path))
    client.post(
        "/api/settings/cookies",
        data={"cookies": (io.BytesIO(NETSCAPE_COOKIE_LINE.encode()), "cookies.txt")},
        content_type="multipart/form-data",
    )
    resp = client.get("/api/settings")
    assert resp.get_json()["cookies_status"] == "valid"
