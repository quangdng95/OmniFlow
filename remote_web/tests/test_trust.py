"""Cookie signing/verification, the /unlock form, and CF-Connecting-IP
brute-force lockout (spec §4.1, §4.2, §4.5)."""

import time

import pytest
from flask import Flask

from remote_web import config, trust


@pytest.fixture
def app(isolated_state_file):
    app = Flask(__name__)
    app.register_blueprint(trust.unlock_bp)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def clear_lockout_state():
    trust._failed_attempts.clear()
    yield
    trust._failed_attempts.clear()


def test_verify_trust_cookie_accepts_a_freshly_signed_cookie(isolated_state_file):
    cookie = trust.sign_trust_cookie()
    assert trust.verify_trust_cookie(cookie) is True


def test_verify_trust_cookie_rejects_garbage(isolated_state_file):
    assert trust.verify_trust_cookie("not-a-real-signed-value") is False


def test_verify_trust_cookie_rejects_none(isolated_state_file):
    assert trust.verify_trust_cookie(None) is False


def test_verify_trust_cookie_rejects_an_expired_cookie(isolated_state_file, monkeypatch):
    cookie = trust.sign_trust_cookie()
    monkeypatch.setattr(config, "COOKIE_MAX_AGE_SECONDS", -1)  # already "expired"
    assert trust.verify_trust_cookie(cookie) is False


def test_rotating_the_secret_key_invalidates_existing_cookies(isolated_state_file):
    cookie = trust.sign_trust_cookie()
    assert trust.verify_trust_cookie(cookie) is True
    config.rotate_secret_key()
    assert trust.verify_trust_cookie(cookie) is False


def test_verify_trust_cookie_rejects_a_validly_signed_but_corrupt_payload(isolated_state_file):
    # A cookie whose HMAC signature is valid (so BadSignature/SignatureExpired
    # would NOT catch it) but whose payload segment isn't valid base64/JSON
    # underneath. itsdangerous raises BadPayload for this - a BadData sibling
    # of BadSignature (not a subclass of it), which an
    # `except (BadSignature, SignatureExpired)` clause would NOT catch,
    # letting the exception escape verify_trust_cookie's `-> bool` contract.
    # Built by signing an intentionally-bogus payload directly with the
    # module's own signer, so the HMAC itself is genuinely valid.
    signer = trust._serializer().make_signer()
    forged = signer.sign(b"not-valid-base64!!!").decode()
    assert trust.verify_trust_cookie(forged) is False


def test_unlock_get_renders_a_form_with_no_token_in_the_page(isolated_state_file, client):
    resp = client.get("/unlock")
    assert resp.status_code == 200
    assert b"<form" in resp.data
    assert config.get_or_create_token().encode() not in resp.data


def test_unlock_post_with_correct_token_sets_cookie_and_redirects(isolated_state_file, client):
    token = config.get_or_create_token()
    resp = client.post("/unlock", data={"token": token})
    assert resp.status_code == 302
    assert resp.location == "/"
    set_cookie = resp.headers.get("Set-Cookie", "")
    assert config.TRUST_COOKIE_NAME in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "SameSite=Lax" in set_cookie


def test_unlock_post_with_wrong_token_does_not_set_cookie(isolated_state_file, client):
    config.get_or_create_token()
    resp = client.post("/unlock", data={"token": "wrong"})
    assert resp.status_code == 401
    assert config.TRUST_COOKIE_NAME not in resp.headers.get("Set-Cookie", "")


def test_unlock_lockout_after_threshold_failures(isolated_state_file, client, monkeypatch):
    monkeypatch.setattr(config, "LOCKOUT_THRESHOLD", 3)
    for _ in range(3):
        client.post("/unlock", data={"token": "wrong"}, headers={"CF-Connecting-IP": "1.2.3.4"})
    resp = client.post(
        "/unlock", data={"token": "wrong"}, headers={"CF-Connecting-IP": "1.2.3.4"}
    )
    assert resp.status_code == 429


def test_unlock_lockout_is_keyed_per_ip(isolated_state_file, client, monkeypatch):
    monkeypatch.setattr(config, "LOCKOUT_THRESHOLD", 3)
    for _ in range(3):
        client.post("/unlock", data={"token": "wrong"}, headers={"CF-Connecting-IP": "1.2.3.4"})
    # A different IP is unaffected by the first IP's lockout.
    correct = config.get_or_create_token()
    resp = client.post(
        "/unlock", data={"token": correct}, headers={"CF-Connecting-IP": "9.9.9.9"}
    )
    assert resp.status_code == 302


def test_unlock_lockout_expires_after_the_window(isolated_state_file, client, monkeypatch):
    monkeypatch.setattr(config, "LOCKOUT_THRESHOLD", 2)
    monkeypatch.setattr(config, "LOCKOUT_WINDOW_SECONDS", 300)
    ip = {"CF-Connecting-IP": "5.5.5.5"}
    for _ in range(2):
        client.post("/unlock", data={"token": "wrong"}, headers=ip)
    # Simulate the window having passed by rewriting the recorded timestamps.
    trust._failed_attempts["5.5.5.5"] = [time.time() - 301, time.time() - 301]
    correct = config.get_or_create_token()
    resp = client.post("/unlock", data={"token": correct}, headers=ip)
    assert resp.status_code == 302
