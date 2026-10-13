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


def test_a_valid_bearer_token_passes_the_gate_without_any_cookie(client):
    token = config.get_or_create_token()
    resp = client.get("/api/anything-at-all", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404  # past the gate, into Flask's own 404


def test_root_path_serves_index_html_once_trusted(client):
    token = config.get_or_create_token()
    client.post("/unlock", data={"token": token})
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Location" not in resp.headers


# ---- public brand assets: icons and the manifest must load WITHOUT the access token --------------
#
# iOS fetches the Home Screen icon (and browsers the favicon) with no cookie. These are the minimum
# public files; nothing under /api/, the main page and downloaded files stay behind the gate.

PUBLIC_ASSETS = [
    "/favicon.ico",
    "/favicon.svg",
    "/favicon-16.png",
    "/favicon-32.png",
    "/apple-touch-icon.png",
    "/apple-touch-icon-precomposed.png",
    "/apple-touch-icon-180x180.png",
    "/icon-192.png",
    "/icon-512.png",
    "/icon-maskable-512.png",
    "/og-image.png",
    "/manifest.webmanifest",
]


def _dist_has(name):
    import os

    from backend import paths

    return os.path.isfile(os.path.join(paths.WEB_DIR, name))


@pytest.mark.parametrize("path", PUBLIC_ASSETS)
def test_brand_assets_load_without_a_token(client, path):
    if not _dist_has(path.lstrip("/").replace("-precomposed", "").replace("-180x180", "")):
        pytest.skip("frontend/dist is not built on this machine")
    resp = client.get(path)
    assert resp.status_code == 200
    assert "text/html" not in resp.headers["Content-Type"]


def test_apple_touch_icon_aliases_serve_the_same_png(client):
    if not _dist_has("apple-touch-icon.png"):
        pytest.skip("frontend/dist is not built on this machine")
    base = client.get("/apple-touch-icon.png").data
    assert base.startswith(b"\x89PNG")
    assert client.get("/apple-touch-icon-precomposed.png").data == base
    assert client.get("/apple-touch-icon-180x180.png").data == base


def test_the_open_assets_do_not_open_anything_else(client):
    assert client.get("/api/settings").status_code == 401
    assert client.get("/api/download-file/anything").status_code == 401
    assert client.get("/api/health/detail").status_code == 401
    resp = client.get("/")
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/unlock")


def test_the_manifest_names_the_app_and_every_icon_it_lists_exists(client):
    import json
    import os

    from backend import paths

    if not _dist_has("manifest.webmanifest"):
        pytest.skip("frontend/dist is not built on this machine")
    manifest = json.loads(client.get("/manifest.webmanifest").data)
    assert manifest["name"] == manifest["short_name"] == "ViDrop"
    assert manifest["display"] == "standalone" and manifest["theme_color"] == "#ffd60a"
    purposes = {icon["purpose"] for icon in manifest["icons"]}
    assert purposes == {"any", "maskable"}
    for icon in manifest["icons"]:
        assert os.path.isfile(os.path.join(paths.WEB_DIR, icon["src"].split("?")[0].lstrip("/")))
