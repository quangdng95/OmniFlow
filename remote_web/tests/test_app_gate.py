"""The app-wide trust gate + Referrer-Policy header (spec §4.1, §4.4)."""

import pytest

from remote_web import config, trust
from remote_web.app import app as remote_app


@pytest.fixture
def client(isolated_state_file):
    remote_app.config["TESTING"] = True
    return remote_app.test_client()


def test_unauthenticated_api_request_is_rejected(client):
    resp = client.get("/api/anything-at-all")
    assert resp.status_code == 401


def test_unlock_route_itself_is_never_gated(client):
    resp = client.get("/unlock")
    assert resp.status_code == 200


def test_a_valid_trust_cookie_passes_the_gate(client):
    token = config.get_or_create_token()
    client.post("/unlock", data={"token": token})
    # The route still doesn't exist yet at this point in the plan, so a
    # trusted request reaches Flask's own 404 instead of the gate's 401 -
    # that distinction (401 vs. 404) is exactly what this test is pinning.
    resp = client.get("/api/anything-at-all")
    assert resp.status_code == 404


def test_every_response_sets_referrer_policy_no_referrer(client):
    resp = client.get("/unlock")
    assert resp.headers.get("Referrer-Policy") == "no-referrer"


def test_root_path_is_not_gated_by_trust(client):
    # index() serves frontend/dist/index.html - a real build may or may not
    # exist on the test machine, so this only asserts it's not blocked by
    # the trust gate (401), whatever else it returns.
    resp = client.get("/")
    assert resp.status_code != 401


def test_root_path_redirects_untrusted_visitor_to_unlock(client):
    # A first-time phone visitor has no way to discover /unlock except being
    # told the URL by hand otherwise - the React app would load and just
    # 401 silently on every /api/* call (final-review finding #2).
    resp = client.get("/")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/unlock"


def test_root_path_serves_index_html_once_trusted(client):
    token = config.get_or_create_token()
    client.post("/unlock", data={"token": token})
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Location" not in resp.headers
