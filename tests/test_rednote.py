"""backend.rednote - RedNote (Xiaohongshu) post resolver.

2026-10-06: RedNote started redirecting every unauthenticated note page to its
login page, AND renamed the stream groups in the page data from h264/h265/... to
opaque keys (EF4, EF5, ...), so yt-dlp's XiaoHongShu extractor fails with "No
video formats found" even with a login. Confirmed live against a fresh share
link: with the owner's logged-in session the page carries window.__INITIAL_STATE__
-> note.noteDetailMap.<id>.note with video.media.stream.<group>[] (masterUrl,
H.264+AAC mp4) or imageList[] for an image note.
"""

import json
import urllib.request

import pytest

from backend import rednote

NOTE_ID = "6aae0dc50000000011036339"
URL = f"https://www.rednote.com/discovery/item/{NOTE_ID}?xsec_token=T&xsec_source=pc_share"


def _page(note):
    state = {"note": {"noteDetailMap": {NOTE_ID: {"note": note}}}}
    # RedNote serialises JS `undefined` as a bare token inside the JSON.
    blob = json.dumps(state).replace('"__U__"', "undefined")
    return f'<html><script>window.__INITIAL_STATE__={blob}</script></html>'


class _Resp:
    def __init__(self, html, final_url=URL):
        self._html, self._url = html.encode(), final_url

    def read(self):
        return self._html

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _serve(monkeypatch, html, final_url=URL, seen=None):
    def fake(req, timeout=20):
        if seen is not None:
            seen.append(req)
        return _Resp(html, final_url)

    monkeypatch.setattr(urllib.request, "urlopen", fake)


def _cookies(tmp_path, domain=".rednote.com", name="web_session"):
    f = tmp_path / "cookies.txt"
    f.write_text(f"{domain}\tTRUE\t/\tTRUE\t1999999999\t{name}\tSECRETVALUE\n{domain}\tTRUE\t/\tTRUE\t1999999999\ta1\tother\n")
    return str(f)


VIDEO_NOTE = {
    "type": "video",
    "title": "魔法 colour grade",
    "desc": "a longer description",
    "imageList": [{"urlDefault": "http://sns-web-i10.rednotecdn.com/cover.jpg"}],
    "video": {"media": {"stream": {
        "EF4": [
            {"masterUrl": "http://sns-v11.rednotecdn.com/720.mp4", "height": 1280, "size": 1_581_579, "backupUrls": ["http://b/720.mp4"]},
            {"masterUrl": "http://sns-v11.rednotecdn.com/1080.mp4", "height": 1920, "size": 2_609_456, "backupUrls": []},
        ],
        "EF6": [], "EF5": [], "EF7": [],
    }}},
}


def test_a_video_note_resolves_to_its_sharpest_stream_over_https(monkeypatch, tmp_path):
    _serve(monkeypatch, _page(VIDEO_NOTE))
    media = rednote.fetch_rednote_post(URL, _cookies(tmp_path))

    assert media["title"] == "魔法 colour grade"
    assert media["items"] == [{
        "kind": "video",
        "url": "https://sns-v11.rednotecdn.com/1080.mp4",   # the 1920-high one, upgraded to https
        "thumbnail": "https://sns-web-i10.rednotecdn.com/cover.jpg",
    }]


def test_the_login_cookies_are_sent_but_never_appear_in_an_error(monkeypatch, tmp_path):
    seen = []
    _serve(monkeypatch, _page(VIDEO_NOTE), seen=seen)
    rednote.fetch_rednote_post(URL, _cookies(tmp_path))
    assert "web_session=SECRETVALUE" in seen[0].get_header("Cookie")

    _serve(monkeypatch, "<html>login</html>", final_url="https://www.rednote.com/login?redirectPath=x")
    with pytest.raises(rednote.RedNoteAuthError) as excinfo:
        rednote.fetch_rednote_post(URL, _cookies(tmp_path))
    assert "SECRETVALUE" not in str(excinfo.value)


def test_a_redirect_to_the_login_page_means_a_session_is_required(monkeypatch, tmp_path):
    _serve(monkeypatch, "<html>please sign in</html>", final_url="https://www.xiaohongshu.com/login?redirectPath=x")
    with pytest.raises(rednote.RedNoteAuthError):
        rednote.fetch_rednote_post(URL, _cookies(tmp_path))


def test_an_image_note_lists_every_image(monkeypatch, tmp_path):
    note = {"type": "normal", "title": "Photos", "imageList": [
        {"urlDefault": f"http://sns-web.rednotecdn.com/{n}.jpg", "infoList": [{"url": f"http://x/{n}-small"}]} for n in (1, 2, 3)
    ]}
    _serve(monkeypatch, _page(note))
    media = rednote.fetch_rednote_post(URL, _cookies(tmp_path))
    assert [i["url"] for i in media["items"]] == [f"https://sns-web.rednotecdn.com/{n}.jpg" for n in (1, 2, 3)]
    assert all(i["kind"] == "image" and i["thumbnail"] == i["url"] for i in media["items"])


def test_undefined_values_in_the_page_state_do_not_break_parsing(monkeypatch, tmp_path):
    note = dict(VIDEO_NOTE, interactInfo="__U__", extra=["__U__", 1])
    _serve(monkeypatch, _page(note))
    assert rednote.fetch_rednote_post(URL, _cookies(tmp_path))["items"][0]["kind"] == "video"


def test_a_note_with_no_media_is_an_error_not_an_empty_result(monkeypatch, tmp_path):
    _serve(monkeypatch, _page({"type": "video", "title": "x", "video": {"media": {"stream": {"EF4": []}}}}))
    with pytest.raises(rednote.RedNoteError):
        rednote.fetch_rednote_post(URL, _cookies(tmp_path))


def test_a_page_without_state_is_an_error(monkeypatch, tmp_path):
    _serve(monkeypatch, "<html>nothing here</html>")
    with pytest.raises(rednote.RedNoteError):
        rednote.fetch_rednote_post(URL, _cookies(tmp_path))


def test_only_rednote_cookie_domains_are_forwarded(monkeypatch, tmp_path):
    f = tmp_path / "c.txt"
    f.write_text(
        ".rednote.com\tTRUE\t/\tTRUE\t1999999999\tweb_session\tRN\n"
        ".google.com\tTRUE\t/\tTRUE\t1999999999\tSID\tGOOGLESECRET\n"
        ".instagram.com\tTRUE\t/\tTRUE\t1999999999\tsessionid\tIGSECRET\n"
    )
    seen = []
    _serve(monkeypatch, _page(VIDEO_NOTE), seen=seen)
    rednote.fetch_rednote_post(URL, str(f))
    header = seen[0].get_header("Cookie")
    assert "web_session=RN" in header and "GOOGLESECRET" not in header and "IGSECRET" not in header


# ---- which cookie file is used ----


def test_candidates_use_the_uploaded_file_when_it_has_a_rednote_session(monkeypatch, tmp_path):
    monkeypatch.setattr(rednote.config, "get_cookies_path", lambda: _cookies(tmp_path))
    monkeypatch.setattr(rednote.cookies, "cookiefiles_from_browsers", lambda domain="", session_cookie=None: ["/tmp/omniflow-cookies-b.txt"])
    assert rednote.rednote_cookiefile_candidates()[0] == str(tmp_path / "cookies.txt")


def test_candidates_accept_a_xiaohongshu_session_too(monkeypatch, tmp_path):
    monkeypatch.setattr(rednote.config, "get_cookies_path", lambda: _cookies(tmp_path, domain=".xiaohongshu.com"))
    monkeypatch.setattr(rednote.cookies, "cookiefiles_from_browsers", lambda domain="", session_cookie=None: [])
    assert len(rednote.rednote_cookiefile_candidates()) == 1


def test_candidates_skip_a_file_with_no_rednote_session(monkeypatch, tmp_path):
    jar = tmp_path / "c.txt"
    jar.write_text(".instagram.com\tTRUE\t/\tTRUE\t1999999999\tsessionid\tx\n")
    monkeypatch.setattr(rednote.config, "get_cookies_path", lambda: str(jar))
    monkeypatch.setattr(rednote.cookies, "cookiefiles_from_browsers", lambda domain="", session_cookie=None: [])
    assert rednote.rednote_cookiefile_candidates() == []


def test_fetch_any_falls_through_to_the_next_account(monkeypatch, tmp_path):
    first, second = _cookies(tmp_path), str(tmp_path / "second.txt")
    open(second, "w").write(".rednote.com\tTRUE\t/\tTRUE\t1999999999\tweb_session\tTWO\n")
    calls = []

    def fake(url, cookiefile):
        calls.append(cookiefile)
        if cookiefile == first:
            raise rednote.RedNoteAuthError("logged out")
        return {"title": "t", "items": [{"kind": "video", "url": "https://x/v.mp4", "thumbnail": None}]}

    monkeypatch.setattr(rednote, "fetch_rednote_post", fake)
    assert rednote.fetch_rednote_post_any(URL, [first, second])["title"] == "t"
    assert calls == [first, second]


def test_fetch_any_reports_an_auth_error_only_when_every_account_is_logged_out(monkeypatch):
    monkeypatch.setattr(rednote, "fetch_rednote_post", lambda url, cf: (_ for _ in ()).throw(rednote.RedNoteAuthError("x")))
    with pytest.raises(rednote.RedNoteAuthError):
        rednote.fetch_rednote_post_any(URL, ["a", "b"])
