"""The app-wide trust gate + Referrer-Policy header (spec §4.1, §4.4)."""

import os
import shutil

import pytest

from backend import paths
from remote_web import config, trust
from remote_web.app import app as remote_app


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def web_dir(tmp_path, monkeypatch):
    """A stand-in for frontend/dist that needs no build: the repo's own public assets (icons, manifest,
    fonts) plus the source index.html, served the way the real build is. Tests that read the page or the
    brand files therefore run the same on a fresh clone and on a machine that has built the frontend."""
    site = tmp_path / "dist"
    shutil.copytree(os.path.join(REPO_ROOT, "frontend", "public"), site)
    shutil.copy(os.path.join(REPO_ROOT, "frontend", "index.html"), site / "index.html")
    monkeypatch.setattr(paths, "WEB_DIR", str(site))
    monkeypatch.setattr(remote_app, "static_folder", str(site))
    return str(site)


@pytest.fixture
def client(isolated_state_file, web_dir):
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


@pytest.mark.parametrize("path", PUBLIC_ASSETS)
def test_brand_assets_load_without_a_token(client, path):
    resp = client.get(path)
    assert resp.status_code == 200
    assert "text/html" not in resp.headers["Content-Type"]


def test_apple_touch_icon_aliases_serve_the_same_png(client):
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


def test_the_manifest_names_the_app_and_every_icon_it_lists_exists(client, web_dir):
    import json

    manifest = json.loads(client.get("/manifest.webmanifest").data)
    assert manifest["name"] == manifest["short_name"] == "ViDrop"
    assert manifest["display"] == "standalone" and manifest["theme_color"] == "#ffd60a"
    purposes = {icon["purpose"] for icon in manifest["icons"]}
    assert purposes == {"any", "maskable"}
    for icon in manifest["icons"]:
        assert os.path.isfile(os.path.join(web_dir, icon["src"].split("?")[0].lstrip("/")))


# ---- edge caching of the public brand files (iOS gives the Home Screen icon only a moment) --------


@pytest.mark.parametrize("path", ["/apple-touch-icon.png", "/favicon.ico", "/icon-192.png", "/manifest.webmanifest", "/og-image.png"])
def test_brand_files_can_be_served_from_the_cloudflare_edge(client, path):
    cache = client.get(path).headers["Cache-Control"]
    assert "public" in cache and "s-maxage=2592000" in cache


def test_hashed_build_assets_are_immutable_and_the_pages_and_api_are_not_cached(client, web_dir):
    os.makedirs(os.path.join(web_dir, "assets"), exist_ok=True)
    with open(os.path.join(web_dir, "assets", "index-abc123.js"), "w") as f:
        f.write("//")
    assert "immutable" in client.get("/assets/index-abc123.js").headers["Cache-Control"]
    assert "s-maxage" not in (client.get("/unlock").headers.get("Cache-Control") or "")
    assert "s-maxage" not in (client.get("/api/settings").headers.get("Cache-Control") or "")
    assert "s-maxage" not in (client.get("/").headers.get("Cache-Control") or "")


def test_clear_session_signs_this_browser_out_and_needs_a_trusted_visitor(client):
    assert client.post("/api/clear-session").status_code == 401  # not signed in: gated like every /api route
    client.post("/unlock", data={"token": config.get_or_create_token()})
    assert client.post("/api/settings", json={"playlist_limit": 100}).status_code == 200  # trusted now
    resp = client.post("/api/clear-session")
    assert resp.status_code == 200
    cleared = " ".join(resp.headers.getlist("Set-Cookie"))
    assert config.TRUST_COOKIE_NAME in cleared and "Expires=Thu, 01 Jan 1970" in cleared
    assert client.post("/api/clear-session").status_code == 401  # the cookie is gone: signed out


# ---- two hostnames side by side (cloud.nguyenduyquang.com primary, cloud.southframevn.com kept) ----------

PRIMARY = "cloud.nguyenduyquang.com"
LEGACY = "cloud.southframevn.com"


@pytest.mark.parametrize("host", [PRIMARY, LEGACY, "127.0.0.1:5050", "localhost", f"{PRIMARY}:443"])
def test_every_configured_host_is_served(client, host):
    assert client.get("/health", headers={"Host": host}).status_code == 200
    assert client.get("/unlock", headers={"Host": host}).status_code == 200
    assert client.get("/apple-touch-icon.png", headers={"Host": host}).status_code == 200


@pytest.mark.parametrize("host", ["evil.example.com", "cloud.nguyenduyquang.com.evil.com", "nguyenduyquang.com", "cloud.example.org"])
def test_an_unconfigured_host_is_refused_before_anything_else_runs(client, host):
    for path in ("/health", "/unlock", "/api/settings", "/apple-touch-icon.png"):
        assert client.get(path, headers={"Host": host}).status_code == 421


def test_the_trust_cookie_is_issued_for_the_new_host_alone_without_a_domain_attribute(client):
    token = config.get_or_create_token()
    resp = client.post("/unlock", data={"token": token}, base_url=f"https://{PRIMARY}")
    assert resp.status_code == 302
    cookie = resp.headers["Set-Cookie"]
    assert config.TRUST_COOKIE_NAME in cookie and "Secure" in cookie and "HttpOnly" in cookie and "SameSite=Lax" in cookie
    assert "Domain=" not in cookie  # host-only: it works on the new host and is not shared with the old one
    assert client.post("/api/clear-session", base_url=f"https://{PRIMARY}").status_code == 200  # signed in there
    assert client.post("/api/clear-session", base_url=f"https://{LEGACY}").status_code == 401  # not signed in there


def test_a_wrong_token_on_the_new_host_is_still_refused(client):
    resp = client.post("/unlock", data={"token": "nope"}, base_url=f"https://{PRIMARY}")
    assert resp.status_code == 401 and config.TRUST_COOKIE_NAME not in (resp.headers.get("Set-Cookie") or "")


def test_the_gate_holds_on_the_new_host(client):
    base = f"https://{PRIMARY}"
    assert client.get("/api/settings", base_url=base).status_code == 401
    assert client.get("/api/download-file/x", base_url=base).status_code == 401
    assert client.post("/api/clear-session", base_url=base).status_code == 401
    assert client.get("/", base_url=base).headers["Location"].endswith("/unlock")


def test_share_previews_point_at_the_primary_host_whichever_host_served_the_page(client):
    for host in (PRIMARY, LEGACY):
        page = client.get("/unlock", headers={"Host": host}).get_data(as_text=True)
        assert f'content="https://{PRIMARY}/og-image.png"' in page
        assert f'<meta property="og:url" content="https://{PRIMARY}/"' in page
        assert "__PUBLIC_ORIGIN__" not in page and "southframevn" not in page


def test_the_hosts_come_from_one_setting(monkeypatch):
    import subprocess
    import sys

    code = "from remote_web import config; print(config.PUBLIC_HOST, config.PUBLIC_ORIGIN, sorted(config.ALLOWED_HOSTS))"
    env = {**os.environ, "OMNIFLOW_PUBLIC_HOST": "Cloud.Example.org", "OMNIFLOW_EXTRA_HOSTS": "a.example.org, b.example.org"}
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=REPO_ROOT).stdout
    assert "cloud.example.org https://cloud.example.org" in out
    assert "'a.example.org'" in out and "'b.example.org'" in out and "'cloud.southframevn.com'" in out
    default = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=REPO_ROOT, env={k: v for k, v in os.environ.items() if not k.startswith("OMNIFLOW_")}).stdout
    assert default.startswith("cloud.nguyenduyquang.com https://cloud.nguyenduyquang.com")
