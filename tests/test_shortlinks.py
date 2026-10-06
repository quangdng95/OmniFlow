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
