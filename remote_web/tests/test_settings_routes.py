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
    too_big = b"x" * (256 * 1024 + 1)
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


# ---- POST /api/settings/cookies: the Mac's automatic sync (2026-10-03) ----
#
# sync_cloud_cookies.py now pushes the cookie jar here over HTTPS with the
# Bearer token (it used to scp over SSH, which stopped working once public
# SSH was closed). Because it overwrites the live cookies unattended every
# 6 hours, a bad payload must never be able to replace a working file.

REAL_LOOKING_JAR = (
    "# Netscape HTTP Cookie File\n"
    ".youtube.com\tTRUE\t/\tTRUE\t1999999999\t__Secure-1PSID\tvalue1\n"
    ".instagram.com\tTRUE\t/\tTRUE\t1999999999\tsessionid\tvalue2\n"
)


def _post_cookies(client, payload, headers=None):
    return client.post(
        "/api/settings/cookies",
        data={"cookies": (io.BytesIO(payload), "cookies.txt")},
        content_type="multipart/form-data",
        headers=headers or {},
    )


def test_upload_cookies_accepts_the_bearer_token_without_an_unlock_cookie(client, tmp_path, monkeypatch):
    monkeypatch.setattr("remote_web.routes.settings._COOKIES_FILE", str(tmp_path / "c.txt"))
    token = config.get_or_create_token()
    resp = _post_cookies(client, REAL_LOOKING_JAR.encode(), headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert (tmp_path / "c.txt").read_text() == REAL_LOOKING_JAR


def test_upload_cookies_rejects_a_wrong_bearer_token(client, tmp_path, monkeypatch):
    monkeypatch.setattr("remote_web.routes.settings._COOKIES_FILE", str(tmp_path / "c.txt"))
    resp = _post_cookies(client, REAL_LOOKING_JAR.encode(), headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401
    assert not (tmp_path / "c.txt").exists()


def test_upload_cookies_accepts_a_jar_bigger_than_the_old_64_kib_limit(client, tmp_path, monkeypatch):
    _unlock(client)
    monkeypatch.setattr("remote_web.routes.settings._COOKIES_FILE", str(tmp_path / "c.txt"))
    # A Google login alone is ~150 cookies; leave generous headroom.
    big = REAL_LOOKING_JAR + "".join(
        f".google.com\tTRUE\t/\tTRUE\t1999999999\tname{i}\t{'v' * 400}\n" for i in range(250)
    )
    assert len(big) > 64 * 1024
    assert _post_cookies(client, big.encode()).status_code == 200


@pytest.mark.parametrize(
    "garbage",
    [
        b"<html><body>Please sign in</body></html>",
        b"# Netscape HTTP Cookie File\n# nothing but comments\n",
        b"only one field per line\nand another\n",
    ],
)
def test_upload_cookies_rejects_something_that_is_not_a_cookie_jar_and_keeps_the_old_file(
    client, tmp_path, monkeypatch, garbage
):
    _unlock(client)
    cookies_file = tmp_path / "c.txt"
    cookies_file.write_text(REAL_LOOKING_JAR)
    monkeypatch.setattr("remote_web.routes.settings._COOKIES_FILE", str(cookies_file))

    resp = _post_cookies(client, garbage)

    assert resp.status_code == 400
    assert cookies_file.read_text() == REAL_LOOKING_JAR  # the working jar survives


def test_upload_cookies_reports_when_it_was_saved(client, tmp_path, monkeypatch):
    _unlock(client)
    monkeypatch.setattr("remote_web.routes.settings._COOKIES_FILE", str(tmp_path / "c.txt"))
    body = _post_cookies(client, REAL_LOOKING_JAR.encode()).get_json()
    assert isinstance(body["updated_at"], int) and body["updated_at"] > 1_700_000_000


def test_upload_cookies_leaves_no_temp_file_behind(client, tmp_path, monkeypatch):
    _unlock(client)
    monkeypatch.setattr("remote_web.routes.settings._COOKIES_FILE", str(tmp_path / "c.txt"))
    _post_cookies(client, REAL_LOOKING_JAR.encode())
    _post_cookies(client, b"garbage")
    leftovers = sorted(p.name for p in tmp_path.iterdir() if p.name.startswith(".c.txt") or p.suffix == ".tmp")
    assert leftovers == []
