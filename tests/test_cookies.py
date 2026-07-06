"""Unit tests for backend.cookies - temp cookiefile hygiene + browser extraction."""

import os
import sys
import types
from types import SimpleNamespace

from backend import cookies as cookies_module
from backend.config import cookies_file_has_instagram_session
from backend import instagram as instagram_module


# ---- auto cookie extraction (_write_cookies_txt / cookiefiles_from_browsers) ----


def test_cleanup_temp_cookiefiles_only_removes_our_temp_files(tmp_path):
    manual = tmp_path / "my-cookies.txt"
    manual.write_text("keep me")
    temp = cookies_module._write_cookies_txt({"sessionid": "x"})
    assert os.path.exists(temp)
    cookies_module._cleanup_temp_cookiefiles([str(manual), temp, None])
    assert not os.path.exists(temp)  # our temp file is gone
    assert manual.exists()  # the user's own file is untouched


def test_write_cookies_txt_produces_a_valid_session_file(tmp_path):
    path = cookies_module._write_cookies_txt({"sessionid": "live123", "csrftoken": "csrf1"})
    try:
        assert cookies_file_has_instagram_session(path)
        parsed = instagram_module._parse_instagram_cookies(path)
        assert parsed["sessionid"] == "live123"
        assert parsed["csrftoken"] == "csrf1"
    finally:
        os.remove(path)


def test_cookiefiles_from_browsers_writes_a_file_per_logged_in_account(no_browser_cookie_scan, monkeypatch):
    # no_browser_cookie_scan hands back the REAL function (the autouse fixture
    # otherwise stubs it to []); exercise it against a fake browser_cookie3 with
    # two different logged-in accounts across profiles.
    real = no_browser_cookie_scan
    monkeypatch.setattr(cookies_module, "_profile_cookie_db", lambda profile_dir: "/fake/Cookies")
    monkeypatch.setattr(cookies_module, "CHROMIUM_BROWSER_DIRS", {"chrome": "/fake"})

    def fake_chrome(cookie_file=None, domain_name=""):
        # Two distinct accounts keyed on which profile DB path was requested;
        # the bare-browser call (cookie_file=None) repeats Default's session and
        # must be deduped away.
        sess = {"/fake/Cookies": "accountA"}.get(cookie_file, "accountA")
        return [
            SimpleNamespace(name="sessionid", value=sess, domain=".instagram.com"),
            SimpleNamespace(name="csrftoken", value="c", domain=".instagram.com"),
            SimpleNamespace(name="ignore", value="x", domain=".other.com"),
        ]

    monkeypatch.setitem(sys.modules, "browser_cookie3", types.SimpleNamespace(chrome=fake_chrome))

    paths = real("instagram.com")
    try:
        # Same sessionid across all loaders -> deduped to a single cookiefile.
        assert len(paths) == 1
        assert cookies_file_has_instagram_session(paths[0])
        assert instagram_module._parse_instagram_cookies(paths[0])["sessionid"] == "accountA"
    finally:
        for p in paths:
            os.remove(p)


def test_cookiefiles_from_browsers_returns_empty_without_browser_cookie3(no_browser_cookie_scan, monkeypatch):
    real = no_browser_cookie_scan
    # Simulate browser_cookie3 not being importable.
    monkeypatch.setitem(sys.modules, "browser_cookie3", None)
    assert real("instagram.com") == []
