"""YouTube browser-cookie fallback: order of attempts, guards, temp-file hygiene.

browser_cookie3 is always a fake here - no real browser cookie is ever read.
"""

import json
import os
import stat
import subprocess
import sys
import types
from types import SimpleNamespace

import pytest

from backend import config as config_module
from backend import cookies as cookies_module
from backend import extraction, messages

YT = "https://www.youtube.com/watch?v=abc"
BOT_ERROR = Exception("ERROR: [youtube] abc: Sign in to confirm you’re not a bot. Use --cookies-from-browser")


class FakeCookie(SimpleNamespace):
    pass


@pytest.fixture(autouse=True)
def allowed(monkeypatch):
    monkeypatch.setattr(cookies_module, "BROWSER_COOKIES_ALLOWED", True)


@pytest.fixture
def cookie_source(monkeypatch):
    monkeypatch.setattr(config_module, "get_youtube_cookie_source", lambda: ("chrome", "Profile 1"))


@pytest.fixture
def fake_cookiefile(monkeypatch, tmp_path):
    """Replace the browser read with a spy that hands back a real temp file."""
    calls = []

    def fake():
        calls.append(1)
        fd, path = __import__("tempfile").mkstemp(prefix="omniflow-cookies-", suffix=".txt")
        os.close(fd)
        calls.append(path)
        return path

    monkeypatch.setattr(cookies_module, "youtube_browser_cookiefile", fake)
    return calls


# ---- order of attempts ----


def test_no_cookie_attempt_comes_first_and_success_never_reads_the_browser(fake_cookiefile):
    seen = []

    def attempt(cf):
        seen.append(cf)
        return "ok"

    assert cookies_module.run_with_youtube_cookie_fallback(YT, None, attempt) == "ok"
    assert seen == [None]
    assert fake_cookiefile == []


def test_auth_error_triggers_exactly_one_retry_with_cookies_and_cleans_up(fake_cookiefile):
    seen = []

    def attempt(cf):
        seen.append(cf)
        if cf is None:
            raise BOT_ERROR
        return "ok"

    assert cookies_module.run_with_youtube_cookie_fallback(YT, None, attempt) == "ok"
    assert seen[0] is None and seen[1] == fake_cookiefile[1]
    assert len(seen) == 2
    assert not os.path.exists(fake_cookiefile[1])


def test_only_one_retry_even_if_the_retry_also_fails_and_file_is_removed(fake_cookiefile):
    seen = []

    def attempt(cf):
        seen.append(cf)
        raise BOT_ERROR

    with pytest.raises(Exception, match="not a bot"):
        cookies_module.run_with_youtube_cookie_fallback(YT, None, attempt)
    assert len(seen) == 2
    assert not os.path.exists(fake_cookiefile[1])  # removed in finally despite the exception


def test_non_auth_errors_never_read_the_browser(fake_cookiefile):
    def attempt(cf):
        raise Exception("ERROR: [youtube] abc: Private video. Sign in if you've been granted access")

    with pytest.raises(Exception, match="Private video"):
        cookies_module.run_with_youtube_cookie_fallback(YT, None, attempt)
    assert fake_cookiefile == []


def test_non_youtube_urls_never_read_the_browser(fake_cookiefile):
    def attempt(cf):
        raise BOT_ERROR

    with pytest.raises(Exception):
        cookies_module.run_with_youtube_cookie_fallback("https://www.tiktok.com/@x/video/1", None, attempt)
    assert fake_cookiefile == []


def test_manual_cookies_file_is_used_as_is_with_no_browser_fallback(fake_cookiefile):
    seen = []

    def attempt(cf):
        seen.append(cf)
        raise BOT_ERROR

    with pytest.raises(Exception):
        cookies_module.run_with_youtube_cookie_fallback(YT, "/some/manual.txt", attempt)
    assert seen == ["/some/manual.txt"]
    assert fake_cookiefile == []


def test_guard_off_means_no_browser_read(monkeypatch, fake_cookiefile):
    monkeypatch.setattr(cookies_module, "BROWSER_COOKIES_ALLOWED", False)

    def attempt(cf):
        raise BOT_ERROR

    with pytest.raises(Exception):
        cookies_module.run_with_youtube_cookie_fallback(YT, None, attempt)
    assert fake_cookiefile == []


def test_empty_setting_means_no_browser_read(isolated_config):
    # No youtube_cookie_source in config.json (the default): nothing is read and
    # the original YouTube error is what the caller sees.
    seen = []

    def attempt(cf):
        seen.append(cf)
        raise BOT_ERROR

    assert cookies_module.youtube_browser_cookiefile() is None
    with pytest.raises(Exception, match="not a bot"):
        cookies_module.run_with_youtube_cookie_fallback(YT, None, attempt)
    assert seen == [None]


# ---- the local-only guard ----


def test_guard_defaults_to_off_in_the_module_source():
    src = open(cookies_module.__file__).read()
    assert "BROWSER_COOKIES_ALLOWED = False" in src


def test_remote_web_never_turns_the_guard_on():
    # A fresh interpreter that imports the cloud app: backend.app is never
    # imported, so the flag stays False no matter what the VM's config says.
    code = (
        "import remote_web.app, sys; import backend.cookies as c; "
        "print(c.BROWSER_COOKIES_ALLOWED, 'backend.app' in sys.modules)"
    )
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True, timeout=60)
    assert out.stdout.split() == ["False", "False"], out.stderr[-500:]


def test_local_backend_app_turns_the_guard_on(monkeypatch):
    import importlib

    from backend import app as app_module

    monkeypatch.setattr(cookies_module, "BROWSER_COOKIES_ALLOWED", False)
    importlib.reload(app_module)
    assert cookies_module.BROWSER_COOKIES_ALLOWED is True


# ---- the actual read (fake browser_cookie3) ----


@pytest.fixture
def chrome_profile(tmp_path, monkeypatch, cookie_source):
    profile = tmp_path / "Chrome" / "Profile 1" / "Network"
    profile.mkdir(parents=True)
    (profile / "Cookies").write_bytes(b"not a real db")
    monkeypatch.setattr(cookies_module, "CHROMIUM_BROWSER_DIRS", {"chrome": str(tmp_path / "Chrome")})
    return tmp_path


def install_fake_browser(monkeypatch, fn):
    monkeypatch.setitem(sys.modules, "browser_cookie3", types.SimpleNamespace(chrome=fn))


def test_read_writes_only_youtube_cookies_with_0600_and_removes_the_db_copy(chrome_profile, monkeypatch):
    asked = {}

    def fake_chrome(cookie_file=None, domain_name=""):
        asked["domain"] = domain_name
        asked["db"] = cookie_file
        return [
            FakeCookie(name="SID", value="fake-sid", domain=".youtube.com", path="/", secure=True, expires=2000000000),
            FakeCookie(name="PREF", value="fake-pref", domain="www.youtube.com", path="/", secure=False, expires=None),
            FakeCookie(name="NID", value="fake-nid", domain=".google.com", path="/", secure=True, expires=2000000000),
        ]

    install_fake_browser(monkeypatch, fake_chrome)
    path = cookies_module.youtube_browser_cookiefile()
    try:
        assert asked["domain"] == "youtube.com"
        assert not os.path.exists(asked["db"])  # the raw DB copy is gone
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
        body = open(path).read()
        assert "fake-sid" in body and "fake-pref" in body
        assert "fake-nid" not in body  # google.com is not read/written
        assert os.path.basename(path).startswith("omniflow-cookies-")
    finally:
        cookies_module._cleanup_temp_cookiefiles([path])


def test_profile_with_no_youtube_login_returns_none(chrome_profile, monkeypatch):
    install_fake_browser(monkeypatch, lambda cookie_file=None, domain_name="": [])
    assert cookies_module.youtube_browser_cookiefile() is None


def test_read_failure_raises_a_message_free_error_and_removes_the_db_copy(chrome_profile, monkeypatch):
    seen = {}

    def boom(cookie_file=None, domain_name=""):
        seen["db"] = cookie_file
        raise RuntimeError("Unable to get key for cookie decryption: secret-token-xyz")

    install_fake_browser(monkeypatch, boom)
    with pytest.raises(cookies_module.YouTubeCookieAccessError) as info:
        cookies_module.youtube_browser_cookiefile()
    assert "secret-token-xyz" not in str(info.value)
    assert str(info.value) == "RuntimeError"
    assert not os.path.exists(seen["db"])


def test_read_failure_surfaces_through_the_fallback(chrome_profile, monkeypatch):
    def boom(cookie_file=None, domain_name=""):
        raise RuntimeError("denied")

    install_fake_browser(monkeypatch, boom)

    def attempt(cf):
        raise BOT_ERROR

    with pytest.raises(cookies_module.YouTubeCookieAccessError):
        cookies_module.run_with_youtube_cookie_fallback(YT, None, attempt)


def test_sweep_removes_only_old_files_with_our_prefixes(tmp_path, monkeypatch):
    import tempfile
    import time

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    old = tmp_path / "omniflow-cookies-old.txt"
    old.write_text("x")
    os.utime(old, (time.time() - 7200, time.time() - 7200))
    fresh = tmp_path / "omniflow-cookies-fresh.txt"
    fresh.write_text("x")
    other = tmp_path / "unrelated.txt"
    other.write_text("x")
    os.utime(other, (time.time() - 7200, time.time() - 7200))
    removed = cookies_module.sweep_stale_temp_cookiefiles()
    assert removed == [str(old)]
    assert fresh.exists() and other.exists()


# ---- config setting ----


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("chrome:Default", ("chrome", "Default")),
        ("chrome:Profile 1", ("chrome", "Profile 1")),
        ("", None),
        ("arc:Default", None),
        ("chrome:../../etc", None),
        ("chrome:Profile", None),
        (None, None),
    ],
)
def test_youtube_cookie_source_parsing(isolated_config, raw, expected):
    isolated_config.write_text(json.dumps({"youtube_cookie_source": raw}))
    assert config_module.get_youtube_cookie_source() == expected


def test_source_is_empty_by_default(isolated_config):
    assert config_module.get_youtube_cookie_source() is None


def test_save_session_keeps_the_youtube_cookie_source(isolated_config):
    isolated_config.write_text(json.dumps({"path": "/x", "youtube_cookie_source": "chrome:Default"}))
    config_module.save_session("/y", "", "chrome", 50)
    data = json.loads(isolated_config.read_text())
    assert data["youtube_cookie_source"] == "chrome:Default"
    assert data["path"] == "/y" and data["playlist_limit"] == 50


# ---- messages ----


def test_new_youtube_messages_have_en_and_vi():
    for key in ("youtube_signin_required", "youtube_restricted", "youtube_cookies_keychain"):
        assert messages.text(key, "en") and messages.text(key, "vi")
        assert messages.text(key, "en") != messages.text(key, "vi")


def test_keychain_message_mentions_keychain_in_both_languages():
    assert "Keychain" in messages.text("youtube_cookies_keychain", "en")
    assert "Keychain" in messages.text("youtube_cookies_keychain", "vi")


def test_describe_error_tells_the_three_youtube_causes_apart():
    d = extraction.describe_extraction_error
    assert d(YT, BOT_ERROR, lang="en") == messages.text("youtube_signin_required", "en")
    assert d(YT, Exception("ERROR: [youtube] abc: Video unavailable"), lang="en") == messages.text("youtube_restricted", "en")
    assert d(YT, cookies_module.YouTubeCookieAccessError("RuntimeError"), lang="en") == messages.text("youtube_cookies_keychain", "en")
    assert d(YT, ConnectionError("x"), lang="en") == messages.text("network_unreachable", "en")
    # the same bot text on another platform is not rewritten as a YouTube message
    assert d("https://example.com/v", BOT_ERROR, lang="en") != messages.text("youtube_signin_required", "en")
