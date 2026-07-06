"""Unit tests for backend.config - session persistence + folder/cookies resolution."""

import json
import os

from backend import config
from backend.config import (
    cookies_file_has_instagram_session,
    cookies_status_for,
    get_cookies_path,
    load_session,
    resolve_save_dir,
    save_session,
)


# ---- load_session / save_session ----


def test_load_session_returns_default_when_config_missing(isolated_config):
    session = load_session()
    assert session["path"].endswith("Downloads")


def test_load_session_returns_default_on_malformed_json(isolated_config):
    isolated_config.write_text("{not valid json")
    session = load_session()
    assert session["path"].endswith("Downloads")


def test_save_and_load_session_round_trip(isolated_config, tmp_path):
    save_session(str(tmp_path))
    session = load_session()
    assert session == {"path": str(tmp_path), "cookies_path": "", "browser": "chrome"}


def test_save_and_load_session_round_trip_with_cookies_path(isolated_config, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# fake cookies file")
    save_session(str(tmp_path), str(cookies_file))
    session = load_session()
    assert session == {"path": str(tmp_path), "cookies_path": str(cookies_file), "browser": "chrome"}


def test_load_session_self_heals_stale_path_to_real_downloads(isolated_config):
    save_session("/this/path/does/not/exist")
    session = load_session()
    assert session["path"] == os.path.expanduser("~/Downloads")
    # the correction is persisted, so a stale config doesn't need re-healing every request
    with open(isolated_config) as f:
        saved = json.load(f)
    assert saved["path"] == os.path.expanduser("~/Downloads")


# ---- get_cookies_path ----


def test_get_cookies_path_returns_none_when_not_configured(isolated_config):
    assert get_cookies_path() is None


def test_get_cookies_path_returns_none_when_configured_file_does_not_exist(isolated_config):
    save_session(os.path.expanduser("~/Downloads"), "/this/cookies/file/does/not/exist.txt")
    assert get_cookies_path() is None


def test_get_cookies_path_returns_path_when_file_exists(isolated_config, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# fake cookies file")
    save_session(os.path.expanduser("~/Downloads"), str(cookies_file))
    assert get_cookies_path() == str(cookies_file)


# ---- cookies_file_has_instagram_session / cookies_status_for ----


def test_cookies_file_has_instagram_session_true_for_a_normal_session_line(tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    assert cookies_file_has_instagram_session(str(cookies_file))


def test_cookies_file_has_instagram_session_true_for_httponly_prefixed_line(tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("#HttpOnly_.instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    assert cookies_file_has_instagram_session(str(cookies_file))


def test_cookies_file_has_instagram_session_ignores_real_comment_lines(tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(
        "# Netscape HTTP Cookie File\n.instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n"
    )
    assert cookies_file_has_instagram_session(str(cookies_file))


def test_cookies_file_has_instagram_session_false_for_wrong_domain(tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".youtube.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    assert not cookies_file_has_instagram_session(str(cookies_file))


def test_cookies_file_has_instagram_session_false_for_wrong_cookie_name(tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tcsrftoken\tabc123\n")
    assert not cookies_file_has_instagram_session(str(cookies_file))


def test_cookies_file_has_instagram_session_false_for_malformed_lines(tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tsessionid\tabc123\n")
    assert not cookies_file_has_instagram_session(str(cookies_file))


def test_cookies_file_has_instagram_session_false_when_file_missing():
    assert not cookies_file_has_instagram_session("/this/file/does/not/exist.txt")


def test_cookies_status_for_none_when_path_is_empty():
    assert cookies_status_for("") == "none"


def test_cookies_status_for_none_when_file_does_not_exist():
    assert cookies_status_for("/this/file/does/not/exist.txt") == "none"


def test_cookies_status_for_valid_when_file_has_session(tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(".instagram.com\tTRUE\t/\tTRUE\t1799999999\tsessionid\tabc123\n")
    assert cookies_status_for(str(cookies_file)) == "valid"


def test_cookies_status_for_no_session_when_file_lacks_session(tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# fake cookies file with no session\n")
    assert cookies_status_for(str(cookies_file)) == "no_session"


# ---- resolve_save_dir (folder-not-writable fallback) ----


def test_resolve_save_dir_returns_configured_path_when_valid(tmp_path):
    assert resolve_save_dir(str(tmp_path)) == str(tmp_path)


def test_resolve_save_dir_falls_back_and_creates_fallback_dir(tmp_path):
    fallback = tmp_path / "fallback" / "Downloads"
    result = resolve_save_dir("/this/path/does/not/exist", fallback_dir=str(fallback))
    assert result == str(fallback)
    assert fallback.is_dir()


def test_resolve_save_dir_returns_none_when_nothing_is_writable(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "access", lambda *a, **k: False)
    result = resolve_save_dir("/this/path/does/not/exist", fallback_dir=str(tmp_path / "fallback"))
    assert result is None
