"""The bilingual error catalog (backend/messages.py) and how routes pick a language."""

import re

import pytest
import yt_dlp
from flask import Flask

from backend import extraction as extraction_module
from backend import linkedin as linkedin_module
from backend import messages

FIELD = re.compile(r"\{(\w+)\}")


def test_every_message_exists_in_both_languages():
    for key, entry in messages._CATALOG.items():
        assert set(entry) == {messages.VI, messages.EN}, key
        assert entry[messages.VI].strip() and entry[messages.EN].strip(), key


def test_both_languages_of_a_message_use_the_same_placeholders():
    for key, entry in messages._CATALOG.items():
        assert set(FIELD.findall(entry[messages.VI])) == set(FIELD.findall(entry[messages.EN])), key


def test_the_two_languages_are_actually_different_text():
    for key, entry in messages._CATALOG.items():
        assert entry[messages.VI] != entry[messages.EN], key


@pytest.mark.parametrize(
    "raw, expected",
    [("en", "en"), ("EN-us", "en"), ("vi", "vi"), ("vi-VN", "vi"), (" en ", "en"), (None, "vi"), ("", "vi"), ("fr", "vi")],
)
def test_normalize_language(raw, expected):
    assert messages.normalize_language(raw) == expected


def test_text_formats_placeholders_and_defaults_to_vietnamese():
    assert "arm64" in messages.text("ffmpeg_wrong_chip", "en", machine="arm64", dmg="X.dmg")
    assert messages.text("ffmpeg_missing") == messages.text("ffmpeg_missing", "vi")


def test_request_language_is_the_default_outside_a_request():
    assert messages.request_language() == messages.DEFAULT_LANGUAGE


def test_request_language_reads_the_x_language_header():
    app = Flask(__name__)
    with app.test_request_context(headers={"X-Language": "en"}):
        assert messages.request_language() == "en"
    with app.test_request_context(headers={"X-Language": "vi"}):
        assert messages.request_language() == "vi"
    with app.test_request_context():
        assert messages.request_language() == messages.DEFAULT_LANGUAGE


def test_describe_extraction_error_speaks_the_requested_language():
    err = ConnectionError("no route to host")
    assert extraction_module.describe_extraction_error("https://x.com/a", err, lang="en") == messages.text(
        "network_unreachable", "en"
    )
    assert extraction_module.describe_extraction_error("https://x.com/a", err, lang="vi") == messages.text(
        "network_unreachable", "vi"
    )
    # Callers that predate the language argument keep getting Vietnamese.
    assert extraction_module.describe_extraction_error("https://x.com/a", err) == messages.text("network_unreachable", "vi")


def _linkedin_document_post(monkeypatch):
    def fake_extract(cls):
        raise yt_dlp.utils.DownloadError("Unable to extract video")

    def raise_unsupported(url):
        raise linkedin_module.LinkedInUnsupportedPostError("No image found")

    monkeypatch.setattr(extraction_module, "extract_video_info", fake_extract)
    monkeypatch.setattr(linkedin_module, "fetch_linkedin_image_post", raise_unsupported)


@pytest.mark.parametrize("header, expected", [("en", "en"), ("vi", "vi"), (None, "vi")])
def test_check_route_returns_the_error_in_the_language_of_the_header(client, monkeypatch, header, expected):
    _linkedin_document_post(monkeypatch)
    headers = {"X-Language": header} if header else {}
    resp = client.post("/api/check", json={"url": "https://www.linkedin.com/posts/someone_activity-123-abcd"}, headers=headers)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == messages.text("linkedin_document", expected)
