"""Unit + regression tests for backend.classify — the single URL classifier.

classify_url() is the structural guarantee behind owner core capability #4
(.claude/rules/product.md): the app — not the user — decides whether a pasted
link is a single file or a multi-item source. The parameterized owner URLs
below mirror .claude/rules/test-urls.md; keep the two in sync when the owner
updates that list.
"""

import pytest

from backend import classify
from backend.classify import LinkKind, classify_url, entry_index_from_url, is_playlist_url


# ---- the owner's 8 live test URLs (.claude/rules/test-urls.md), offline ----


OWNER_URL_CASES = [
    pytest.param(
        "https://www.rednote.com/explore/6a444c6d00000000150263f7?xsec_token=ABaGIQIANnGCnsmab0cW9_NGDBexEAARQE4zSVHl5bbHk%3D&xsec_source=pc_feed",
        {"platform": "RedNote", "kind": LinkKind.SINGLE, "is_multi": False},
        id="rednote-single",
    ),
    pytest.param(
        "https://www.youtube.com/watch?v=dwWOEA00K8s&list=RDKzl6cT_u7RA&index=4",
        {"platform": "YouTube", "kind": LinkKind.YOUTUBE_MIX, "is_multi": True,
         "playlist_cap": classify.MIX_ITEM_CAP},
        id="youtube-mix",
    ),
    pytest.param(
        "https://youtu.be/dwWOEA00K8s?si=LfMB9LkTkYcKoRgX",
        {"platform": "YouTube", "kind": LinkKind.SINGLE, "is_multi": False},
        id="youtube-single-short-link",
    ),
    pytest.param(
        "https://www.facebook.com/reel/2194732404711942",
        {"platform": "Facebook", "kind": LinkKind.SINGLE, "is_multi": False},
        id="facebook-reel",
    ),
    pytest.param(
        "https://www.instagram.com/thexxlab_/p/DZFb8x-mxOP/",
        {"platform": "Instagram", "kind": LinkKind.INSTAGRAM_POST_OR_CAROUSEL,
         "is_multi": False, "shortcode": "DZFb8x-mxOP"},
        id="instagram-carousel-username-prefixed",
    ),
    pytest.param(
        "https://www.instagram.com/p/DYTRs5Loe6A",
        {"platform": "Instagram", "kind": LinkKind.INSTAGRAM_POST_OR_CAROUSEL,
         "is_multi": False, "shortcode": "DYTRs5Loe6A"},
        id="instagram-single-post",
    ),
    pytest.param(
        "https://www.instagram.com/theqazman/reels/",
        {"platform": "Instagram", "kind": LinkKind.INSTAGRAM_PROFILE,
         "is_multi": True, "username": "theqazman"},
        id="instagram-profile-reels",
    ),
    pytest.param(
        "https://www.tiktok.com/@vio_decor127/video/7650834126223805717?is_from_webapp=1&sender_device=pc",
        {"platform": "TikTok", "kind": LinkKind.SINGLE, "is_multi": False},
        id="tiktok-single",
    ),
]


@pytest.mark.parametrize("url,expected", OWNER_URL_CASES)
def test_owner_test_urls_classify_as_required(url, expected):
    cls = classify_url(url)
    for field, value in expected.items():
        assert getattr(cls, field) == value, f"{field}: {getattr(cls, field)!r} != {value!r}"


def test_owner_rednote_url_is_rewritten_to_xiaohongshu():
    cls = classify_url(OWNER_URL_CASES[0].values[0])
    assert cls.url.startswith("https://www.xiaohongshu.com/discovery/item/6a444c6d00000000150263f7")
    assert cls.extraction_url == cls.url


def test_owner_mix_url_keeps_the_watch_url_for_extraction():
    # A Mix only resolves through its seed watch URL - no playlist?list= rewrite.
    url = OWNER_URL_CASES[1].values[0]
    cls = classify_url(url)
    assert cls.extraction_url == url


# ---- classify_url per-kind units ----


def test_classify_youtube_playlist_shapes():
    for url in (
        "https://www.youtube.com/playlist?list=PLxyz",
        "https://www.youtube.com/channel/UCabc",
        "https://www.youtube.com/c/SomeChannel",
        "https://www.youtube.com/user/SomeUser",
        "https://www.youtube.com/@SomeHandle",
        "https://www.youtube.com/@SomeHandle/videos",
    ):
        cls = classify_url(url)
        assert cls.kind == LinkKind.YOUTUBE_PLAYLIST, url
        assert cls.is_multi
        assert cls.playlist_cap == classify.PLAYLIST_ITEM_CAP
        # Path-shaped playlist/channel URLs need no rewrite.
        assert cls.extraction_url == url


def test_classify_watch_plus_list_rewrites_extraction_url_only():
    cls = classify_url("https://www.youtube.com/watch?v=abc&list=PLxyz")
    assert cls.kind == LinkKind.YOUTUBE_PLAYLIST
    # url (what downloads use) keeps the watch form; extraction_url widens to
    # the playlist. Merging these two would silently change download semantics.
    assert cls.url == "https://www.youtube.com/watch?v=abc&list=PLxyz"
    assert cls.extraction_url == "https://www.youtube.com/playlist?list=PLxyz"


def test_classify_youtu_be_with_list_param():
    cls = classify_url("https://youtu.be/abc?list=PLxyz")
    assert cls.kind == LinkKind.YOUTUBE_PLAYLIST
    assert cls.extraction_url == "https://www.youtube.com/playlist?list=PLxyz"


def test_classify_plain_watch_is_single():
    cls = classify_url("https://www.youtube.com/watch?v=abc")
    assert cls.kind == LinkKind.SINGLE
    assert not cls.is_multi
    assert cls.playlist_cap is None
    assert cls.extraction_url == cls.url


def test_classify_instagram_story():
    cls = classify_url("https://www.instagram.com/stories/someone/1234567890/")
    assert cls.kind == LinkKind.INSTAGRAM_STORY
    # A Story lists via a full (non-flat) yt-dlp extraction - NOT flat/multi.
    assert not cls.is_multi
    assert cls.shortcode is None
    assert cls.username is None


def test_classify_instagram_reel_and_tv_shortcodes():
    assert classify_url("https://www.instagram.com/reel/DUvAWWREkNIWX8/?x=1").shortcode == "DUvAWWREkNIWX8"
    assert classify_url("https://instagram.com/tv/ABC123_-/").shortcode == "ABC123_-"


def test_classify_instagram_profile_plain_username():
    cls = classify_url("https://www.instagram.com/thexxlab_")
    assert cls.kind == LinkKind.INSTAGRAM_PROFILE
    assert cls.username == "thexxlab_"
    assert cls.is_multi


def test_classify_unknown_platform_is_single_link():
    cls = classify_url("https://example.com/video")
    assert cls.platform == "Link"
    assert cls.kind == LinkKind.SINGLE


def test_classify_empty_url_is_single():
    cls = classify_url("")
    assert cls.kind == LinkKind.SINGLE
    assert not cls.is_multi


# ---- is_playlist_url can never drift from the classifier ----


def test_is_playlist_url_matches_classifier_is_multi():
    grid = [case.values[0] for case in OWNER_URL_CASES] + [
        "https://www.youtube.com/playlist?list=PLxyz",
        "https://www.youtube.com/watch?v=abc&list=PLxyz",
        "https://www.youtube.com/watch?v=abc",
        "https://www.youtube.com/@SomeHandle",
        "https://www.instagram.com/stories/someone/123/",
        "https://www.instagram.com/p/C-i9vJ2ST7C/",
        "https://example.com/video",
        "",
    ]
    for url in grid:
        assert is_playlist_url(url) == classify_url(url).is_multi, url


# ---- entry_index_from_url ----


def test_entry_index_from_url_reads_img_index():
    assert entry_index_from_url("https://www.instagram.com/p/abc/?img_index=3") == 3


def test_entry_index_from_url_none_without_param_or_on_garbage():
    assert entry_index_from_url("https://www.instagram.com/p/abc/") is None
    assert entry_index_from_url("https://www.instagram.com/p/abc/?img_index=lol") is None
