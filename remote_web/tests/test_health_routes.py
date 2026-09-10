"""GET /health (public) + GET /api/health/detail (trust-gated, cached) — spec §4.6."""

import pytest

from remote_web import config
from remote_web.app import app as remote_app
from remote_web.routes import health as health_routes


@pytest.fixture
def client(isolated_state_file):
    remote_app.config["TESTING"] = True
    return remote_app.test_client()


@pytest.fixture(autouse=True)
def reset_health_cache():
    health_routes._detail_cache["payload"] = None
    health_routes._detail_cache["at"] = 0.0
    yield
    health_routes._detail_cache["payload"] = None
    health_routes._detail_cache["at"] = 0.0


def _unlock(client):
    token = config.get_or_create_token()
    client.post("/unlock", data={"token": token})


def test_health_is_unauthenticated(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_health_leaks_no_detail(client):
    resp = client.get("/health")
    body = resp.get_json()
    assert "ffmpeg" not in body
    assert "instagram_cookies" not in body


def test_health_detail_requires_trust(client):
    resp = client.get("/api/health/detail")
    assert resp.status_code == 401


def test_health_detail_reports_all_fields_when_trusted(client, monkeypatch):
    monkeypatch.setattr(health_routes.ffmpeg_locator, "resolve_ffmpeg_binary", lambda: "/fake/ffmpeg")
    monkeypatch.setattr(health_routes.backend_cookies, "instagram_cookiefile_candidates", lambda: ["/fake/cookies.txt"])
    monkeypatch.setattr(health_routes.backend_threads, "threads_cookiefile_candidates", lambda: [])
    _unlock(client)
    resp = client.get("/api/health/detail")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ffmpeg"] is True
    assert body["instagram_cookies"] is True
    assert body["threads_cookies"] is False
    assert "temp_dir_disk_free_mb" in body


def test_health_detail_never_leaks_secrets(client, monkeypatch):
    monkeypatch.setattr(health_routes.ffmpeg_locator, "resolve_ffmpeg_binary", lambda: "/fake/ffmpeg")
    monkeypatch.setattr(health_routes.backend_cookies, "instagram_cookiefile_candidates", lambda: [])
    monkeypatch.setattr(health_routes.backend_threads, "threads_cookiefile_candidates", lambda: [])
    _unlock(client)
    resp = client.get("/api/health/detail")
    text = resp.get_data(as_text=True)
    assert config.get_or_create_token() not in text
    assert config.get_or_create_secret_key() not in text
    assert config.STATE_FILE not in text


def test_health_detail_is_cached_between_calls(client, monkeypatch):
    calls = {"count": 0}

    def fake_resolve():
        calls["count"] += 1
        return "/fake/ffmpeg"

    monkeypatch.setattr(health_routes.ffmpeg_locator, "resolve_ffmpeg_binary", fake_resolve)
    monkeypatch.setattr(health_routes.backend_cookies, "instagram_cookiefile_candidates", lambda: [])
    monkeypatch.setattr(health_routes.backend_threads, "threads_cookiefile_candidates", lambda: [])
    _unlock(client)
    client.get("/api/health/detail")
    client.get("/api/health/detail")
    assert calls["count"] == 1


def test_health_detail_recomputes_after_cache_expiry(client, monkeypatch):
    monkeypatch.setattr(config, "HEALTH_CACHE_SECONDS", 0)
    monkeypatch.setattr(health_routes.ffmpeg_locator, "resolve_ffmpeg_binary", lambda: "/fake/ffmpeg")
    monkeypatch.setattr(health_routes.backend_cookies, "instagram_cookiefile_candidates", lambda: [])
    monkeypatch.setattr(health_routes.backend_threads, "threads_cookiefile_candidates", lambda: [])
    _unlock(client)
    calls = {"count": 0}
    original = health_routes.ffmpeg_locator.resolve_ffmpeg_binary

    def counting():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(health_routes.ffmpeg_locator, "resolve_ffmpeg_binary", counting)
    client.get("/api/health/detail")
    client.get("/api/health/detail")
    assert calls["count"] == 2
