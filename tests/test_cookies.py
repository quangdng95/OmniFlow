"""Unit tests for backend.cookies - temp cookiefile hygiene + browser extraction."""

import os
import shutil
import sys
import types
from types import SimpleNamespace

from backend import cookies as cookies_module
from backend.config import cookies_file_has_instagram_session
from backend import instagram as instagram_module
from backend import paths as paths_module


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


def test_cookiefiles_from_browsers_logs_diagnostics_when_everything_fails(no_browser_cookie_scan, monkeypatch):
    # Every per-browser attempt used to fail silently (bare except: pass), so a
    # machine where extraction never worked left zero trace anywhere. This
    # pins the fix: when the function ends up empty-handed, it must report the
    # real reason via paths.log_exception instead of swallowing it.
    real = no_browser_cookie_scan
    monkeypatch.setattr(cookies_module, "CHROMIUM_BROWSER_DIRS", {})

    def failing(cookie_file=None, domain_name=""):
        raise RuntimeError("keychain locked")

    fake_module = types.SimpleNamespace(
        chrome=failing, brave=failing, edge=failing, chromium=failing,
        vivaldi=failing, opera=failing, safari=failing, firefox=failing,
    )
    monkeypatch.setitem(sys.modules, "browser_cookie3", fake_module)

    logged = []
    monkeypatch.setattr(paths_module, "log_exception", lambda context, error: logged.append((context, str(error))))

    result = real("instagram.com")

    assert result == []
    assert len(logged) == 1
    context, detail = logged[0]
    assert "instagram.com" in context
    assert "keychain locked" in detail


def test_cookiefiles_from_browsers_diagnostic_names_the_profile_and_other_cookies(no_browser_cookie_scan, monkeypatch):
    # Pins the 2026-07-10 diagnostic upgrade: a real Intel-Mac log showed
    # "chrome (Cookies): no sessionid (not logged in)" with no way to tell
    # whether Chrome had ZERO cookies for the domain (Keychain decrypt
    # silently failing) or just some non-auth cookies (wrong/logged-out
    # profile) - the message must now name the profile and list whatever
    # cookies WERE found, so that distinction is visible in errors.log.
    real = no_browser_cookie_scan
    monkeypatch.setattr(cookies_module, "_profile_cookie_db", lambda profile_dir: "/fake/Cookies")
    monkeypatch.setattr(cookies_module, "CHROMIUM_BROWSER_DIRS", {"chrome": "/fake"})
    monkeypatch.setattr(os.path, "isdir", lambda p: True)
    monkeypatch.setattr(os, "listdir", lambda p: ["Profile 1"])
    monkeypatch.setattr(shutil, "copy2", lambda *a, **k: None)

    def chrome_missing_sessionid(cookie_file=None, domain_name=""):
        return [SimpleNamespace(name="csrftoken", value="c", domain=".instagram.com")]

    monkeypatch.setitem(sys.modules, "browser_cookie3", types.SimpleNamespace(chrome=chrome_missing_sessionid))

    logged = []
    monkeypatch.setattr(paths_module, "log_exception", lambda context, error: logged.append(str(error)))

    result = real("instagram.com")

    assert result == []
    assert len(logged) == 1
    assert "chrome/Profile 1" in logged[0]
    assert "1 instagram.com cookie(s) read" in logged[0]
    assert "csrftoken" in logged[0]


def test_cookiefiles_from_browsers_does_not_log_when_a_session_is_found(no_browser_cookie_scan, monkeypatch):
    real = no_browser_cookie_scan
    monkeypatch.setattr(cookies_module, "CHROMIUM_BROWSER_DIRS", {})

    def fake_chrome(cookie_file=None, domain_name=""):
        return [SimpleNamespace(name="sessionid", value="ok", domain=".instagram.com")]

    monkeypatch.setitem(sys.modules, "browser_cookie3", types.SimpleNamespace(chrome=fake_chrome))

    logged = []
    monkeypatch.setattr(paths_module, "log_exception", lambda context, error: logged.append((context, error)))

    paths = real("instagram.com")
    try:
        assert len(paths) == 1
        assert logged == []
    finally:
        for p in paths:
            os.remove(p)
