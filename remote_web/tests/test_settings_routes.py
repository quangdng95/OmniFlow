"""GET/POST /api/settings - language (remote_web's own file) + playlist_limit
(proxied through to backend.config's session, since
backend.extraction.extract_video_info reads it from there and the frontend's
Playlist Limit control is NOT gated behind isLocal(), unlike Target Path)."""

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
