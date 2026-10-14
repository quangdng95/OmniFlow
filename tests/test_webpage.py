"""backend.webpage - the index page with its absolute URLs filled in."""

import os

from backend import paths, webpage
from backend.app import app as local_app


def _site(tmp_path, monkeypatch, html):
    (tmp_path / "index.html").write_text(html, encoding="utf-8")
    monkeypatch.setattr(paths, "WEB_DIR", str(tmp_path))


def test_the_placeholder_is_replaced_everywhere_and_the_page_is_never_cached(tmp_path, monkeypatch):
    _site(tmp_path, monkeypatch, '<meta content="__PUBLIC_ORIGIN__/og-image.png"><meta content="__PUBLIC_ORIGIN__/">')
    with local_app.test_request_context("/"):
        response = webpage.render_index("https://cloud.nguyenduyquang.com/")
    body = response.get_data(as_text=True)
    assert body == '<meta content="https://cloud.nguyenduyquang.com/og-image.png"><meta content="https://cloud.nguyenduyquang.com/">'
    assert response.headers["Cache-Control"] == "no-cache" and response.mimetype == "text/html"


def test_the_mac_app_serves_the_page_with_its_own_loopback_origin(tmp_path, monkeypatch):
    _site(tmp_path, monkeypatch, '<meta content="__PUBLIC_ORIGIN__/og-image.png">')
    body = local_app.test_client().get("/").get_data(as_text=True)
    assert "http://127.0.0.1:" in body and "__PUBLIC_ORIGIN__" not in body


def test_the_source_page_has_no_hardcoded_host():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html = open(os.path.join(root, "frontend", "index.html"), encoding="utf-8").read()
    assert "southframevn" not in html and "nguyenduyquang" not in html
    assert html.count("__PUBLIC_ORIGIN__") == 3  # og:url, og:image, twitter:image
