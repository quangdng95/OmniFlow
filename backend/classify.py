"""URL classification — the single place that decides what a pasted link IS.

Owner core capability #4 (.claude/rules/product.md): the app auto-classifies a
link as single-file vs multi-item; the user never declares it. Per
design-principles.md §5 this logic lives here in small, individually-testable
pure functions — never inline in route handlers. All three API routes and the
extractor consult classify_url(); nothing else may re-derive a link's kind.

This module is PURE: stdlib only, no imports from other backend modules, no
network, no filesystem.
"""

import dataclasses
import enum
import re
import urllib.parse

# Cap how many entries we pull from a playlist/channel. A channel can have
# thousands of videos; listing them all would make yt-dlp slow and the UI heavy.
PLAYLIST_ITEM_CAP = 200
# A YouTube Mix/Radio (list=RD…) is auto-generated and endless — cap it harder
# so extraction can't hang the app (MISTAKES.md blacklist §3).
MIX_ITEM_CAP = 50

# Flat playlist extraction can't know each entry's real available formats without
# a full per-video fetch, so a batch download offers one shared quality ladder
# applied to every selected item (build_download_options maps these the same way
# it does for a single video).
PLAYLIST_QUALITIES = ["Best", "1080p", "720p", "480p", "Audio Only"]

# Explicit playlist/channel/handle shapes route to flat playlist extraction.
_PLAYLIST_URL_RE = re.compile(r"youtube\.com/(?:playlist\?|(?:c|channel|user)/|@)", re.IGNORECASE)


class LinkKind(str, enum.Enum):
    SINGLE = "single"
    YOUTUBE_PLAYLIST = "youtube_playlist"
    YOUTUBE_MIX = "youtube_mix"
    INSTAGRAM_POST_OR_CAROUSEL = "instagram_post_or_carousel"
    INSTAGRAM_PROFILE = "instagram_profile"
    INSTAGRAM_STORY = "instagram_story"


@dataclasses.dataclass(frozen=True)
class Classification:
    platform: str  # "YouTube" | "Instagram" | "TikTok" | "Facebook" | "RedNote" | "LinkedIn" | "Link"
    kind: LinkKind
    # The two URLs are deliberately separate (do NOT merge them): downloading a
    # watch?v=X&list=PL… item must fetch video X (url), while /api/check must
    # list the whole playlist (extraction_url, rewritten to playlist?list=…).
    url: str  # after normalize_rednote_url only — what downloads use
    extraction_url: str  # additionally playlist-canonicalized — what yt-dlp extraction uses
    shortcode: str | None = None  # set iff INSTAGRAM_POST_OR_CAROUSEL
    username: str | None = None  # set iff INSTAGRAM_PROFILE
    playlist_cap: int | None = None  # 50 (Mix) / 200 (playlist/channel/profile) / None

    @property
    def is_multi(self) -> bool:
        # Kinds that list entries via flat extraction (or the profile resolver).
        # An Instagram post/carousel is data-dependent (1 slide vs many) and an
        # Instagram Story lists via a full (non-flat) yt-dlp extraction, so
        # neither belongs here — mirrors the pre-refactor is_playlist_url().
        return self.kind in (LinkKind.YOUTUBE_PLAYLIST, LinkKind.YOUTUBE_MIX, LinkKind.INSTAGRAM_PROFILE)


def normalize_rednote_url(url):
    # yt-dlp mishandles the rednote.com domain (no thumbnail, only "Best");
    # its xiaohongshu.com equivalent works fully (MISTAKES.md blacklist §4).
    if not url:
        return url
    if "rednote.com/explore/" in url:
        return url.replace("rednote.com/explore/", "xiaohongshu.com/discovery/item/")
    return url


def normalize_youtube_playlist_url(url):
    # A `youtube.com/watch?v=...&list=...` URL is a video that happens to sit in a
    # playlist. yt-dlp routes the `/watch` path to its VIDEO extractor and hands
    # back a single video (even with noplaylist=False) - so the whole list is never
    # listed. Rewrite it to the canonical `/playlist?list=<id>` URL, which routes
    # to the playlist (tab) extractor and lists every entry.
    # Exception: a Mix/Radio playlist (`list=RD...`) is auto-generated around a seed
    # video and only resolves via the watch URL, so leave those untouched.
    if not url:
        return url
    list_id = _youtube_list_id(url)
    if not list_id or list_id.upper().startswith("RD"):
        return url
    return f"https://www.youtube.com/playlist?list={list_id}"


def _youtube_list_id(url):
    # The `list=` query param of a YouTube/youtu.be URL, or None.
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return None
    host = (parsed.hostname or "").lower()
    if not (host == "youtu.be" or host.endswith("youtube.com")):
        return None
    list_ids = urllib.parse.parse_qs(parsed.query).get("list")
    return list_ids[0] if list_ids and list_ids[0] else None


def get_platform_info(url):
    url = normalize_rednote_url(url)
    url_lower = url.lower()
    if "youtube" in url_lower or "youtu.be" in url_lower: return "YouTube"
    if "instagram" in url_lower: return "Instagram"
    if "tiktok" in url_lower: return "TikTok"
    if "facebook.com" in url_lower or "fb.watch" in url_lower: return "Facebook"
    # "RedNote" is Xiaohongshu's international rebrand - links can come from
    # either the classic domains or the newer rednote.com one.
    if "xiaohongshu" in url_lower or "xhslink" in url_lower or "rednote" in url_lower: return "RedNote"
    if "linkedin.com" in url_lower: return "LinkedIn"
    return "Link"


def is_instagram_profile_url(url):
    url_lower = url.lower()
    if "instagram.com" not in url_lower:
        return False
    try:
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path.strip("/")
        parts = [p for p in path.split("/") if p]
        if not parts:
            return False
        # Ignore common non-profile endpoints/paths
        if parts[0] in ("p", "reel", "reels", "tv", "stories", "api", "accounts", "explore", "developer", "static"):
            return False
        if len(parts) == 1:
            return True
        if len(parts) == 2 and parts[1] == "reels":
            return True
        return False
    except Exception:
        return False


def is_instagram_story_url(url):
    # Stories (/stories/<user>/<id>) carry no shortcode and list via a full
    # (non-flat) yt-dlp playlist extraction — a distinct kind from post/profile.
    if "instagram.com" not in url.lower():
        return False
    try:
        path = urllib.parse.urlparse(url).path.strip("/")
    except Exception:
        return False
    return path.split("/", 1)[0] == "stories"


def instagram_username_from_url(url):
    try:
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path.strip("/")
        parts = [p for p in path.split("/") if p]
        if parts:
            return parts[0]
    except Exception:
        pass
    return None


def instagram_shortcode_from_url(url):
    # Only post/reel/tv shapes carry a media shortcode resolvable via the
    # private media-info endpoint. Stories (/stories/<user>/<id>/) are a
    # different shape handled by the yt-dlp path, so they return None. The
    # optional leading segment tolerates the <username>/p/<shortcode> shape.
    m = re.search(r"instagram\.com/(?:[^/]+/)?(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)", url)
    return m.group(1) if m else None


def entry_index_from_url(url):
    # Instagram carousel share links can carry the picked slide as ?img_index=N.
    try:
        params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        if "img_index" in params:
            return int(params["img_index"][0])
    except Exception:
        pass
    return None


def classify_url(raw_url):
    # THE single source of truth for what a link is. Decision order mirrors the
    # routes' historical precedence: RedNote rewrite → platform → Instagram
    # (shortcode → story → profile) → YouTube list= (Mix vs playlist) →
    # playlist/channel/handle path shapes → single.
    url = normalize_rednote_url((raw_url or "").strip())
    platform = get_platform_info(url)

    kind = LinkKind.SINGLE
    extraction_url = url
    shortcode = None
    username = None
    playlist_cap = None

    if platform == "Instagram":
        shortcode = instagram_shortcode_from_url(url)
        if shortcode:
            kind = LinkKind.INSTAGRAM_POST_OR_CAROUSEL
        elif is_instagram_story_url(url):
            kind = LinkKind.INSTAGRAM_STORY
        elif is_instagram_profile_url(url):
            kind = LinkKind.INSTAGRAM_PROFILE
            username = instagram_username_from_url(url)
            playlist_cap = PLAYLIST_ITEM_CAP
    elif platform == "YouTube":
        list_id = _youtube_list_id(url)
        if list_id and list_id.upper().startswith("RD"):
            # Mix/Radio: keep the seed watch URL (the Mix only resolves through
            # it) and cap the endless list (MISTAKES.md blacklist §3).
            kind = LinkKind.YOUTUBE_MIX
            playlist_cap = MIX_ITEM_CAP
        elif list_id:
            kind = LinkKind.YOUTUBE_PLAYLIST
            extraction_url = normalize_youtube_playlist_url(url)
            playlist_cap = PLAYLIST_ITEM_CAP
        elif _PLAYLIST_URL_RE.search(url):
            kind = LinkKind.YOUTUBE_PLAYLIST
            playlist_cap = PLAYLIST_ITEM_CAP

    return Classification(
        platform=platform,
        kind=kind,
        url=url,
        extraction_url=extraction_url,
        shortcode=shortcode,
        username=username,
        playlist_cap=playlist_cap,
    )


def is_playlist_url(url):
    # Thin compatibility wrapper — the answer is derived from classify_url so
    # this can never drift from the classifier.
    return classify_url(url).is_multi
