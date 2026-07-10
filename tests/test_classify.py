"""Unit + regression tests for backend.classify — the single URL classifier.

classify_url() is the structural guarantee behind owner core capability #4
(.claude/rules/product.md): the app — not the user — decides whether a pasted
link is a single file or a multi-item source. The parameterized owner URLs
below mirror .claude/rules/test-urls.md; keep the two in sync when the owner
updates that list.
"""

import pytest

from backend import classify
from backend.classify import (
    LinkKind,
    classify_url,
    entry_index_from_url,
    get_platform_info,
    instagram_shortcode_from_url,
    is_playlist_url,
)


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
        # Same Mix, different `index=` - the owner reported this exact variant
        # (index=6) as "returns no result". Pinned to prove index= never
        # affects classification: only `list=` decides Mix vs playlist vs single.
        "https://www.youtube.com/watch?v=dwWOEA00K8s&list=RDKzl6cT_u7RA&index=6",
        {"platform": "YouTube", "kind": LinkKind.YOUTUBE_MIX, "is_multi": True,
         "playlist_cap": classify.MIX_ITEM_CAP},
        id="youtube-mix-different-index",
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
    pytest.param(
        "https://www.linkedin.com/posts/mishalkhawaja_sendinblueviews-toronto-digitalmarketing-ugcPost-6850898786781339649-mM20",
        {"platform": "LinkedIn", "kind": LinkKind.SINGLE, "is_multi": False},
        id="linkedin-video-post",
    ),
    pytest.param(
        "https://www.threads.com/@unrootdesign/post/DWE8-rMEmXp?xmt=AQG02YOkgRow_Lg2H1w1Fj79vUlnAuBuMZEZbm9PHcaavw",
        {"platform": "Threads", "kind": LinkKind.THREADS_POST, "is_multi": False, "shortcode": "DWE8-rMEmXp"},
        id="threads-video-post",
    ),
    pytest.param(
        "https://www.threads.com/@figma/post/DaTf9pqiaMW?xmt=AQG02YOkgRow_Lg2H1w1Fj79vUlnAuBuMZEZbm9PHcaavw",
        {"platform": "Threads", "kind": LinkKind.THREADS_POST, "is_multi": False, "shortcode": "DaTf9pqiaMW"},
        id="threads-image-post",
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


def test_extract_url_from_text_pulls_url_out_of_rednote_share_caption():
    # RedNote's own "Share" button copies title + hashtags + emoji ahead of
    # the real link, not a bare URL - the owner hit this exact real example.
    raw = (
        "88 【岁末的西贡某个角落 - SFVN | 小红书 - 你的生活兴趣社区】 😆 HcQEAeLAuw1RoAT 😆 "
        "https://www.xiaohongshu.com/discovery/item/678bb418000000001602aa02"
        "?source=webshare&xhsshare=pc_web&xsec_token=AB2jV_KkkD_KjGae1c-abw8c61oN206_OadoWsAFjQOJE="
        "&xsec_source=pc_share"
    )
    cls = classify_url(raw)
    assert cls.url == (
        "https://www.xiaohongshu.com/discovery/item/678bb418000000001602aa02"
        "?source=webshare&xhsshare=pc_web&xsec_token=AB2jV_KkkD_KjGae1c-abw8c61oN206_OadoWsAFjQOJE="
        "&xsec_source=pc_share"
    )
    assert cls.platform == "RedNote"


def test_extract_url_from_text_strips_trailing_sentence_punctuation():
    cls = classify_url("check this out: https://www.youtube.com/watch?v=jNQXAC9IVRw.")
    assert cls.url == "https://www.youtube.com/watch?v=jNQXAC9IVRw"


def test_extract_url_from_text_leaves_a_bare_url_unchanged():
    url = "https://www.tiktok.com/@user/video/123"
    cls = classify_url(url)
    assert cls.url == url


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
# ---- get_platform_info ----


def test_get_platform_info_youtube():
    assert get_platform_info("https://www.youtube.com/watch?v=abc") == "YouTube"
    assert get_platform_info("https://youtu.be/abc") == "YouTube"


def test_get_platform_info_instagram():
    assert get_platform_info("https://www.instagram.com/reel/abc") == "Instagram"


def test_get_platform_info_tiktok():
    assert get_platform_info("https://www.tiktok.com/@user/video/1") == "TikTok"


def test_get_platform_info_facebook():
    assert get_platform_info("https://www.facebook.com/watch/?v=1") == "Facebook"
    assert get_platform_info("https://fb.watch/abc") == "Facebook"


def test_get_platform_info_rednote():
    assert get_platform_info("https://www.xiaohongshu.com/explore/abc") == "RedNote"
    assert get_platform_info("https://xhslink.com/abc") == "RedNote"
    # "RedNote" is Xiaohongshu's international rebrand and uses its own domain
    assert get_platform_info("https://www.rednote.com/explore/abc") == "RedNote"


def test_get_platform_info_linkedin():
    assert get_platform_info("https://www.linkedin.com/posts/someone_activity-1234567890-abcd/") == "LinkedIn"


def test_classify_url_linkedin_post_is_single():
    # LinkedIn posts (video or otherwise) are one item each - no list=-style
    # multi-item shape exists on LinkedIn, so this always falls through to the
    # SINGLE default (same as TikTok/Facebook), letting yt-dlp's LinkedInIE
    # handle it unchanged.
    cls = classify_url("https://www.linkedin.com/posts/mishalkhawaja_sendinblueviews-toronto-digitalmarketing-ugcPost-6850898786781339649-mM20")
    assert cls.platform == "LinkedIn"
    assert cls.kind == LinkKind.SINGLE
    assert cls.is_multi is False


def test_get_platform_info_threads():
    assert get_platform_info("https://www.threads.com/@someone/post/Abc123") == "Threads"
    assert get_platform_info("https://www.threads.net/@someone/post/Abc123") == "Threads"


def test_get_platform_info_x():
    assert get_platform_info("https://x.com/someone/status/12345") == "X"
    assert get_platform_info("https://www.x.com/someone/status/12345") == "X"
    assert get_platform_info("https://twitter.com/someone/status/12345") == "X"
    assert get_platform_info("https://mobile.twitter.com/someone/status/12345") == "X"


def test_get_platform_info_x_does_not_false_positive_on_similar_domains():
    # "x.com" is a short substring - must be checked via hostname, not a bare
    # `in` check, since an unrelated domain could contain it (e.g. "vertex.com").
    assert get_platform_info("https://vertex.com/some/path") == "Link"
    assert get_platform_info("https://example.com/x.com/fake") == "Link"


def test_classify_url_x_post_is_single():
    cls = classify_url("https://x.com/someone/status/12345")
    assert cls.platform == "X"
    assert cls.kind == LinkKind.SINGLE
    assert cls.is_multi is False


def test_threads_shortcode_from_url():
    assert classify.threads_shortcode_from_url(
        "https://www.threads.com/@unrootdesign/post/DWE8-rMEmXp?xmt=abc"
    ) == "DWE8-rMEmXp"
    assert classify.threads_shortcode_from_url("https://www.threads.com/@someone/") is None


def test_classify_url_threads_post_is_single_multi_false():
    # A Threads post is always one item (video or image, decided by the
    # resolver, not the URL) - is_multi is False even though its own LinkKind
    # (THREADS_POST) differs from the generic SINGLE default.
    cls = classify_url("https://www.threads.com/@figma/post/DaTf9pqiaMW")
    assert cls.kind == LinkKind.THREADS_POST
    assert cls.is_multi is False


def test_get_platform_info_unknown_falls_back_to_link():
    assert get_platform_info("https://example.com/video") == "Link"


def test_instagram_shortcode_from_url_post():
    assert instagram_shortcode_from_url("https://www.instagram.com/p/DYTRs5Loe6A/") == "DYTRs5Loe6A"


def test_instagram_shortcode_from_url_reel():
    assert instagram_shortcode_from_url("https://www.instagram.com/reel/DUvAWWREkNIWX8/?x=1") == "DUvAWWREkNIWX8"


def test_instagram_shortcode_from_url_tv():
    assert instagram_shortcode_from_url("https://instagram.com/tv/ABC123_-/") == "ABC123_-"


def test_instagram_shortcode_from_url_stories_returns_none():
    # Stories keep the yt-dlp path - they carry no post shortcode.
    assert instagram_shortcode_from_url("https://www.instagram.com/stories/someone/123/") is None


def test_instagram_shortcode_from_url_non_instagram_returns_none():
    assert instagram_shortcode_from_url("https://www.youtube.com/watch?v=abc") is None


def test_instagram_shortcode_from_url_is_case_insensitive_on_domain_and_keyword():
    # Regression: the domain/path-keyword match used to be case-sensitive,
    # so an upper/mixed-case URL (e.g. from a source that capitalizes it)
    # silently fell through to the unreliable generic yt-dlp path instead of
    # the custom resolver - reported live as "Invalid link or private
    # video"/"Unable to extract data" for a genuinely public post.
    assert instagram_shortcode_from_url("HTTPS://WWW.INSTAGRAM.COM/REEL/DYTRs5Loe6A/") == "DYTRs5Loe6A"
    assert instagram_shortcode_from_url("https://WWW.Instagram.COM/p/DYTRs5Loe6A/") == "DYTRs5Loe6A"


def test_instagram_shortcode_from_url_recognizes_instagr_am_short_domain():
    # instagr.am is Instagram's own official short domain - it does not
    # contain the substring "instagram" (the dot breaks it) so it needs its
    # own explicit match, both here and in get_platform_info.
    assert instagram_shortcode_from_url("https://instagr.am/p/DYTRs5Loe6A/") == "DYTRs5Loe6A"


def test_get_platform_info_recognizes_instagr_am_short_domain():
    assert get_platform_info("https://instagr.am/p/DYTRs5Loe6A/") == "Instagram"


# ---- is_playlist_url ----


def test_is_playlist_url_matches_playlist_channel_and_handle():
    assert is_playlist_url("https://www.youtube.com/playlist?list=PLxyz")
    assert is_playlist_url("https://www.youtube.com/channel/UCabc")
    assert is_playlist_url("https://www.youtube.com/c/SomeChannel")
    assert is_playlist_url("https://www.youtube.com/user/SomeUser")
    assert is_playlist_url("https://www.youtube.com/@SomeHandle")
    assert is_playlist_url("https://www.youtube.com/@SomeHandle/videos")


def test_is_playlist_url_matches_a_youtube_url_carrying_a_list_param():
    # A YouTube URL with a list= param is a playlist, even in watch?v=...&list=...
    # form (extract the whole list, not just the one video).
    assert is_playlist_url("https://www.youtube.com/watch?v=abc&list=PLxyz")
    assert is_playlist_url("https://youtu.be/abc?list=PLxyz")


def test_is_playlist_url_treats_a_plain_video_as_a_single_video():
    # No list= param and not a channel/handle shape -> a single video.
    assert not is_playlist_url("https://www.youtube.com/watch?v=abc")
    assert not is_playlist_url("https://youtu.be/abc")
    assert not is_playlist_url("https://www.tiktok.com/@user/video/1")


# ---- Instagram profile detection ----


def test_is_instagram_profile_url():
    from backend.classify import is_instagram_profile_url
    assert is_instagram_profile_url("https://www.instagram.com/thexxlab_")
    assert is_instagram_profile_url("https://www.instagram.com/thexxlab_/")
    assert is_instagram_profile_url("https://www.instagram.com/thexxlab_/reels")
    assert is_instagram_profile_url("https://www.instagram.com/thexxlab_/reels/")
    
    # Exclude posts, stories, single reels
    assert not is_instagram_profile_url("https://www.instagram.com/p/C-i9vJ2ST7C/")
    assert not is_instagram_profile_url("https://www.instagram.com/reel/C-i9vJ2ST7C/")
    assert not is_instagram_profile_url("https://www.instagram.com/stories/username/123/")


def test_instagram_username_from_url():
    from backend.classify import instagram_username_from_url
    assert instagram_username_from_url("https://www.instagram.com/thexxlab_") == "thexxlab_"
    assert instagram_username_from_url("https://www.instagram.com/thexxlab_/") == "thexxlab_"
    assert instagram_username_from_url("https://www.instagram.com/thexxlab_/reels/") == "thexxlab_"
    assert instagram_username_from_url("https://www.instagram.com/p/C-i9vJ2ST7C/") == "p"
