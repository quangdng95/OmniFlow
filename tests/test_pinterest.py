"""backend.pinterest - boards and pins through Pinterest's web API (no network: _Api is faked)."""

import pytest

from backend import classify, pinterest

BOARD = "https://www.pinterest.com/quangdng95/pregnant-photo/"
PIN = "https://www.pinterest.com/pin/123456789/"


def _pin(pid, image=True, mp4=None, kind="pin"):
    pin = {"id": pid, "type": kind, "title": f"Pin {pid}"}
    if image:
        pin["images"] = {
            "236x": {"url": f"https://i.pinimg.com/236x/{pid}.jpg", "width": 236},
            "474x": {"url": f"https://i.pinimg.com/474x/{pid}.jpg", "width": 474},
            "orig": {"url": f"https://i.pinimg.com/originals/{pid}.png", "width": 2000},
        }
    if mp4:
        pin["videos"] = {"video_list": {"V_720P": {"url": mp4, "width": 720, "height": 1280}, "HLS": {"url": "https://x/a.m3u8", "width": 1, "height": 1}}}
    return pin


class FakeApi:
    """Stands in for _Api: serves a board in pages of two pins, or a pin."""

    def __init__(self, pins=None, board=None, pin=None):
        self.pins, self.board, self.pin = pins or [], board, pin
        self.calls = []

    def call(self, resource, options, handler, source):
        self.calls.append((resource, options.get("bookmarks")))
        if resource == "BoardResource":
            return {"data": self.board}
        if resource == "PinResource":
            return {"data": self.pin}
        start = int((options.get("bookmarks") or ["0"])[0])
        page = self.pins[start:start + 2]
        more = start + 2 < len(self.pins)
        return {"data": page, "bookmark": str(start + 2) if more else "-end-"}


def _patch(monkeypatch, api):
    monkeypatch.setattr(pinterest, "_Api", lambda cookie_path=None: api)


def test_pin_to_item_prefers_the_original_image_and_a_small_thumbnail():
    item = pinterest.pin_to_item(_pin("1"))
    assert item == {"kind": "image", "url": "https://i.pinimg.com/originals/1.png", "thumbnail": "https://i.pinimg.com/474x/1.jpg", "title": "Pin 1"}


def test_pin_to_item_video_pin_uses_the_largest_mp4_not_the_playlist():
    item = pinterest.pin_to_item(_pin("2", mp4="https://v.pinimg.com/videos/2.mp4"))
    assert item["kind"] == "video" and item["url"].endswith("2.mp4")


@pytest.mark.parametrize("pin", [None, {}, _pin("3", kind="story"), {"id": "4", "type": "pin"}])
def test_pin_to_item_skips_what_is_not_a_plain_pin(pin):
    assert pinterest.pin_to_item(pin) is None


def test_board_is_paged_to_the_end_and_deduplicated(monkeypatch):
    pins = [_pin("1"), _pin("2"), _pin("2"), _pin("3"), _pin("4", kind="story"), _pin("5")]
    api = FakeApi(pins=pins, board={"id": "b1", "name": "Pregnant photo"})
    _patch(monkeypatch, api)
    media = pinterest.fetch_pinterest_board("quangdng95", "pregnant-photo")
    assert media["title"] == "Pregnant photo"
    assert [i["title"] for i in media["items"]] == ["Pin 1", "Pin 2", "Pin 3", "Pin 5"]


def test_board_stops_at_the_limit(monkeypatch):
    api = FakeApi(pins=[_pin(str(n)) for n in range(10)], board={"id": "b1", "name": "B"})
    _patch(monkeypatch, api)
    assert len(pinterest.fetch_pinterest_board("u", "s", limit=3)["items"]) == 3


def test_board_not_found_is_an_auth_error(monkeypatch):
    # Pinterest answers a private board to a stranger exactly like a board that does not exist.
    _patch(monkeypatch, FakeApi(board=None))
    with pytest.raises(pinterest.PinterestAuthError):
        pinterest.fetch_pinterest_board("u", "s")


def test_empty_board_is_an_error_not_an_empty_list(monkeypatch):
    _patch(monkeypatch, FakeApi(pins=[], board={"id": "b1", "name": "B"}))
    with pytest.raises(pinterest.PinterestError):
        pinterest.fetch_pinterest_board("u", "s")


def test_single_pin(monkeypatch):
    _patch(monkeypatch, FakeApi(pin=_pin("9")))
    media = pinterest.fetch_pinterest_pin("9")
    assert len(media["items"]) == 1 and media["title"] == "Pin 9"


def test_media_tries_public_first_and_never_reads_cookies_when_it_works(monkeypatch):
    _patch(monkeypatch, FakeApi(pins=[_pin("1")], board={"id": "b", "name": "B"}))

    def boom():
        raise AssertionError("cookies must not be read for a public board")

    assert pinterest.fetch_pinterest_media(BOARD, get_candidates=boom)["items"]


def test_media_falls_back_to_each_login_for_a_private_board(monkeypatch):
    seen = []

    def api_for(cookie_path=None):
        seen.append(cookie_path)
        return FakeApi(pins=[_pin("1")], board={"id": "b", "name": "Secret"}) if cookie_path == "/second.txt" else FakeApi(board=None)

    monkeypatch.setattr(pinterest, "_Api", api_for)
    cleaned = []
    monkeypatch.setattr(pinterest.cookies, "_cleanup_temp_cookiefiles", lambda c: cleaned.append(list(c)))
    media = pinterest.fetch_pinterest_media(BOARD, get_candidates=lambda: ["/first.txt", "/second.txt"])
    assert media["title"] == "Secret"
    assert seen == [None, "/first.txt", "/second.txt"]
    assert cleaned == [["/first.txt", "/second.txt"]]


def test_media_with_no_login_raises_the_auth_error(monkeypatch):
    _patch(monkeypatch, FakeApi(board=None))
    monkeypatch.setattr(pinterest.cookies, "_cleanup_temp_cookiefiles", lambda c: None)
    with pytest.raises(pinterest.PinterestAuthError):
        pinterest.fetch_pinterest_media(BOARD, get_candidates=lambda: [])


@pytest.mark.parametrize("url", ["https://www.pinterest.com/quangdng95/", "https://www.pinterest.com/u/board/section/", "https://example.com/x"])
def test_profiles_and_sections_are_unsupported(url):
    with pytest.raises(pinterest.PinterestUnsupportedError):
        pinterest.fetch_pinterest_media(url, get_candidates=lambda: [])


def test_friendly_errors_never_leak_the_raw_text():
    for error in (pinterest.PinterestError("HTTP 500 secret detail"), pinterest.PinterestAuthError("x"), pinterest.PinterestUnsupportedError("x")):
        for cloud in (False, True):
            text = pinterest.friendly_error(error, "en", cloud=cloud)
            assert text and "secret detail" not in text and "Traceback" not in text
    assert pinterest.friendly_error(pinterest.PinterestAuthError("x"), "en", cloud=True) != pinterest.friendly_error(pinterest.PinterestAuthError("x"), "en", cloud=False)


@pytest.mark.parametrize(
    "item, ext",
    [
        ({"kind": "video", "url": "https://v/a.mp4"}, "mp4"),
        ({"kind": "image", "url": "https://i/a.png"}, "png"),
        ({"kind": "image", "url": "https://i/a.JPG?x=1"}, "jpg"),
        ({"kind": "image", "url": "https://i/a.gif"}, "gif"),
        ({"kind": "image", "url": "https://i/a"}, "jpg"),
    ],
)
def test_file_extension(item, ext):
    assert pinterest.file_extension(item) == ext


def test_has_session(tmp_path):
    jar = tmp_path / "c.txt"
    jar.write_text(".pinterest.com\tTRUE\t/\tTRUE\t1799999999\t_pinterest_sess\tabc\n")
    assert pinterest.has_session(str(jar))
    jar.write_text(".pinterest.com\tTRUE\t/\tTRUE\t1799999999\tcsrftoken\tabc\n")
    assert not pinterest.has_session(str(jar))
    assert not pinterest.has_session(str(tmp_path / "missing.txt"))


@pytest.mark.parametrize(
    "url, expected",
    [
        (BOARD, ("board", "quangdng95", "pregnant-photo")),
        ("https://www.pinterest.com/quangdng95/pregnant-photo", ("board", "quangdng95", "pregnant-photo")),
        ("https://vn.pinterest.com/quangdng95/pregnant-photo/", ("board", "quangdng95", "pregnant-photo")),
        ("https://www.pinterest.co.uk/u/b/", ("board", "u", "b")),
        (PIN, ("pin", "123456789")),
        ("https://www.pinterest.com/quangdng95/", ("unsupported", "profile")),
        ("https://www.pinterest.com/u/b/sec/", ("unsupported", "section")),
        ("https://www.pinterest.com/search/pins/?q=x", None),
    ],
)
def test_classify_pinterest_target(url, expected):
    assert classify.pinterest_target(url) == expected


def test_classify_url_kinds():
    assert classify.classify_url(BOARD).kind == classify.LinkKind.PINTEREST_BOARD
    assert classify.classify_url(PIN).kind == classify.LinkKind.PINTEREST_PIN
    assert classify.classify_url("https://www.pinterest.com/quangdng95/").kind == classify.LinkKind.PINTEREST_UNSUPPORTED
    assert classify.get_platform_info(BOARD) == "Pinterest"


@pytest.mark.parametrize("url", ["https://notpinterest.com/a/b/", "https://pinterest.evil.com/a/b/"])
def test_lookalike_hosts_are_not_pinterest(url):
    assert classify.get_platform_info(url) == "Link"
