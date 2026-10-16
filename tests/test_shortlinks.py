"""backend.shortlinks - expands a platform's own short link (lnkd.in, t.co, fb.me)
to the real post URL before classification.

Found 2026-10-06: a LinkedIn share link `https://lnkd.in/p/<id>` was classified
as the generic "Link" platform (the host contains none of the substrings
classify looks for), so it went to yt-dlp's generic extractor and failed - even
though the very same post, pasted as its full linkedin.com URL, works.

It runs on user-supplied URLs inside a server, so the tests pin the SSRF-safety
rules: only an allowlist of short-link hosts is ever contacted, redirects are
followed by hand and each hop must stay on a short-link host or land on a
supported platform, and the destination page is never fetched.
"""

import pytest

from backend import shortlinks

LINKEDIN_POST = "https://www.linkedin.com/posts/someone_topic-ugcPost-123-AbCd/?utm_source=share"


@pytest.fixture(autouse=True)
def fresh_cache():
    shortlinks._cache.clear()
    yield
    shortlinks._cache.clear()


class Fetcher:
    """Stands in for the network: maps a URL to the Location it redirects to."""

    def __init__(self, table):
        self.table, self.calls = dict(table), []

    def __call__(self, url):
        self.calls.append(url)
        return self.table.get(url)


def test_a_lnkd_in_link_expands_to_the_linkedin_post():
    fetch = Fetcher({"https://lnkd.in/p/gGaVJcim": LINKEDIN_POST})
    assert shortlinks.expand("https://lnkd.in/p/gGaVJcim", fetch=fetch) == LINKEDIN_POST
    assert fetch.calls == ["https://lnkd.in/p/gGaVJcim"]  # the destination page is NOT fetched


@pytest.mark.parametrize(
    "short, target",
    [
        ("https://t.co/AbC123", "https://x.com/someone/status/1"),
        ("https://fb.me/abc", "https://www.facebook.com/reel/1"),
    ],
)
def test_other_platform_short_links_expand_too(short, target):
    assert shortlinks.expand(short, fetch=Fetcher({short: target})) == target


def test_a_url_that_is_not_a_short_link_is_returned_untouched_and_never_contacted():
    fetch = Fetcher({})
    for url in (
        "https://www.youtube.com/watch?v=abc",
        "https://example.com/redirect",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata endpoint
        "http://localhost:5050/api/health/detail",
    ):
        assert shortlinks.expand(url, fetch=fetch) == url
    assert fetch.calls == []


def test_a_lookalike_host_is_not_treated_as_a_short_link():
    fetch = Fetcher({})
    for url in ("https://lnkd.in.evil.example/x", "https://notlnkd.in/x", "https://evil.example/?u=https://lnkd.in/x"):
        assert shortlinks.expand(url, fetch=fetch) == url
    assert fetch.calls == []


def test_a_redirect_to_an_unsupported_or_internal_host_is_refused():
    # lnkd.in lets members create links to anything; following those blindly
    # from a server would be an SSRF hole.
    for target in ("http://169.254.169.254/latest/meta-data/", "http://127.0.0.1:5050/", "https://example.com/x"):
        fetch = Fetcher({"https://lnkd.in/x": target})
        assert shortlinks.expand("https://lnkd.in/x", fetch=fetch) == "https://lnkd.in/x"
        assert fetch.calls == ["https://lnkd.in/x"]  # never followed to the target


def test_a_chain_of_short_links_is_followed_hop_by_hop():
    fetch = Fetcher({"https://t.co/a": "https://lnkd.in/b", "https://lnkd.in/b": LINKEDIN_POST})
    assert shortlinks.expand("https://t.co/a", fetch=fetch) == LINKEDIN_POST


def test_a_redirect_loop_gives_up_and_keeps_the_original():
    fetch = Fetcher({"https://lnkd.in/a": "https://lnkd.in/b", "https://lnkd.in/b": "https://lnkd.in/a"})
    assert shortlinks.expand("https://lnkd.in/a", fetch=fetch) == "https://lnkd.in/a"
    assert len(fetch.calls) <= shortlinks.MAX_HOPS


def test_a_short_link_that_does_not_redirect_or_fails_is_kept():
    assert shortlinks.expand("https://lnkd.in/dead", fetch=Fetcher({})) == "https://lnkd.in/dead"

    def boom(url):
        raise OSError("network down")

    assert shortlinks.expand("https://lnkd.in/dead", fetch=boom) == "https://lnkd.in/dead"


def test_non_http_redirect_targets_are_refused():
    fetch = Fetcher({"https://lnkd.in/x": "file:///etc/passwd"})
    assert shortlinks.expand("https://lnkd.in/x", fetch=fetch) == "https://lnkd.in/x"


def test_a_relative_location_is_resolved_against_the_short_host():
    fetch = Fetcher({"https://lnkd.in/a": "/b", "https://lnkd.in/b": LINKEDIN_POST})
    assert shortlinks.expand("https://lnkd.in/a", fetch=fetch) == LINKEDIN_POST


def test_the_result_is_cached_so_check_then_download_costs_one_lookup():
    fetch = Fetcher({"https://lnkd.in/p/z": LINKEDIN_POST})
    shortlinks.expand("https://lnkd.in/p/z", fetch=fetch)
    shortlinks.expand("https://lnkd.in/p/z", fetch=fetch)
    assert len(fetch.calls) == 1


def test_whitespace_and_empty_input_are_handled():
    assert shortlinks.expand("", fetch=Fetcher({})) == ""
    assert shortlinks.expand("  https://lnkd.in/p/q  ", fetch=Fetcher({"https://lnkd.in/p/q": LINKEDIN_POST})) == LINKEDIN_POST


# ---- Threads share links (threads.com/share/<id>) ----

SHARE = "https://www.threads.com/share/D6of7LwSj/"
THREADS_POST = "https://www.threads.com/@someone/post/DeZZtk8jUv1?xmt=AQG0"


def test_a_threads_share_link_expands_to_the_post_url():
    fetch = Fetcher({SHARE: THREADS_POST})
    assert shortlinks.expand(SHARE, fetch=fetch) == THREADS_POST
    assert fetch.calls == [SHARE]  # the post page itself is never fetched


def test_threads_net_share_links_expand_too():
    share = "https://threads.net/share/AbC123"
    post = "https://www.threads.net/@someone/post/AbC123"
    assert shortlinks.expand(share, fetch=Fetcher({share: post})) == post


def test_a_failed_threads_share_expand_keeps_the_original_url():
    assert shortlinks.expand(SHARE, fetch=Fetcher({})) == SHARE  # no redirect (SPA shell)

    def boom(url):
        raise OSError("network down")

    assert shortlinks.expand(SHARE, fetch=boom) == SHARE


def test_a_threads_share_redirect_off_platform_is_refused():
    assert shortlinks.expand(SHARE, fetch=Fetcher({SHARE: "https://evil.example/x"})) == SHARE
    assert shortlinks.expand(SHARE, fetch=Fetcher({SHARE: "http://127.0.0.1/admin"})) == SHARE


@pytest.mark.parametrize(
    "url",
    [
        "https://www.threads.com/@someone/post/DeZZtk8jUv1",  # an existing /post/ link is untouched
        "https://www.threads.com/share/",  # no id
        "https://www.threads.com/share/a/b",  # not a share-link shape
        "https://www.threads.com/@someone",
        "https://threads.com.evil.example/share/abc",  # lookalike host
    ],
)
def test_only_real_threads_share_links_are_contacted(url):
    fetch = Fetcher({})
    assert shortlinks.expand(url, fetch=fetch) == url
    assert fetch.calls == []


def test_share_links_use_the_non_browser_user_agent_and_short_links_keep_theirs(monkeypatch):
    seen = {}

    class FakeOpener:
        def open(self, request, timeout=None):
            seen[request.full_url] = request.get_header("User-agent")
            raise shortlinks.urllib.error.HTTPError(request.full_url, 302, "Found", {"Location": "https://x/"}, None)

    monkeypatch.setattr(shortlinks, "_opener", FakeOpener())
    shortlinks._fetch_location(SHARE)
    shortlinks._fetch_location("https://lnkd.in/p/abc")
    assert seen[SHARE] == shortlinks._SHARE_UA and "Chrome" not in shortlinks._SHARE_UA
    assert seen["https://lnkd.in/p/abc"] == shortlinks._UA


def test_a_pin_it_link_expands_to_the_board():
    board = "https://www.pinterest.com/someone/a-board/"
    assert shortlinks.expand("https://pin.it/4abCdE", fetch=Fetcher({"https://pin.it/4abCdE": board})) == board
