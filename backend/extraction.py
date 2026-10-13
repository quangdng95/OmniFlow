"""yt-dlp metadata extraction + /api/check item shaping.

extract_video_info() takes a classify.Classification - what a link IS was
already decided by classify.classify_url(); this module only executes the
extraction that classification dictates (profile resolver vs flat playlist vs
single) and shapes the results for the frontend.
"""

import re
import socket

import yt_dlp

from backend import classify, config, cookies, instagram, messages

_QUALITY_LABEL_RE = re.compile(r"^(\d+)p")


def resolve_thumbnail(info):
    # Some extractors (e.g. RedNote/Xiaohongshu) only populate the plural
    # "thumbnails" list and rely on a later processing step - which doesn't
    # always run in --simulate/skip_download mode - to fill in the singular
    # "thumbnail" field. Fall back to the list directly instead of showing no
    # thumbnail at all when that field is missing.
    thumbnail = info.get("thumbnail")
    if thumbnail:
        return thumbnail
    thumbnails = info.get("thumbnails") or []
    if thumbnails:
        # yt-dlp orders thumbnails worst-to-best by convention
        return thumbnails[-1].get("url")
    return None


# "All items" in Settings is stored as 0. yt-dlp still needs a number, and a
# channel can hold tens of thousands of entries, so "All" is bounded by this
# safety cap rather than being truly unlimited.
ALL_ITEMS_SAFETY_CAP = 10000
# An Instagram profile is paged through its private feed API one request at a
# time, so listing more than this adds many seconds to /api/check.
INSTAGRAM_PROFILE_LIST_CAP = 30


def effective_item_limit(cls):
    """How many entries a multi-item check lists for this classification.

    The one place that turns the Settings "Playlist / Channel Loading Limit"
    (30/50/100/200/500, 0 = All) plus the per-kind technical caps into a
    number, so extraction and the `truncated` flag in /api/check can never
    disagree about it.
    """
    # A Mix/Radio is endless and only resolves through its seed video.
    if cls.kind == classify.LinkKind.YOUTUBE_MIX:
        return cls.playlist_cap or classify.MIX_ITEM_CAP
    try:
        limit = int(config.load_session().get("playlist_limit", classify.PLAYLIST_ITEM_CAP))
    except (TypeError, ValueError):
        limit = classify.PLAYLIST_ITEM_CAP
    if cls.kind == classify.LinkKind.INSTAGRAM_PROFILE:
        return min(limit, INSTAGRAM_PROFILE_LIST_CAP) if limit > 0 else INSTAGRAM_PROFILE_LIST_CAP
    return limit if limit > 0 else ALL_ITEMS_SAFETY_CAP


def extract_video_info(cls):
    # `cls` is a classify.Classification - what the link IS was already decided
    # by classify.classify_url() (owner core capability #4); this function only
    # executes the extraction that classification dictates. It never re-derives
    # platform/kind from the URL string.
    url = cls.extraction_url
    item_limit = effective_item_limit(cls)

    if cls.kind == classify.LinkKind.INSTAGRAM_PROFILE:
        # Use our Custom Instagram Profile/Reels Resolver to bypass Meta blocks
        username = cls.username
        if not username:
            raise Exception("Cannot extract Instagram username from URL")
            
        cookies_path = config.get_cookies_path()
        auto_cookiefile = None
        # Fall back to auto browser cookies extraction if manual cookies settings not valid/empty
        if not (cookies_path and config.cookies_status_for(cookies_path) == "valid"):
            candidates = cookies.instagram_cookiefile_candidates()
            if candidates:
                auto_cookiefile = candidates[0]
                cookies._cleanup_temp_cookiefiles(candidates[1:])
                cookies_path = auto_cookiefile
                
        try:
            print(f"[debug] Resolving Instagram profile for username: {username} using cookies: {cookies_path}", flush=True)
            entries = []
            # effective_item_limit() already holds an Instagram profile to
            # INSTAGRAM_PROFILE_LIST_CAP, and never lets "All" (0) become an
            # unbounded number of sequential API requests.
            limit = item_limit
            try:
                # Primary method: Instagram's own private feed API (2026-07-07).
                # web_profile_info/GraphQL/instaloader all now return a post
                # *count* with no *edges* for a profile the session doesn't
                # own - confirmed live, see docs/internal/MISTAKES.md - so this must go
                # first, not last.
                entries = instagram.fetch_instagram_profile_reel_media(username, cookies_path, limit=limit)
            except Exception as e_primary:
                # Only try fallbacks if primary totally failed (not just slow).
                # Each fallback adds up to 15s timeout, so keep the chain short.
                print(f"[debug] Private feed API failed: {e_primary}. Trying Web Profile API fallback...", flush=True)
                data = None
                try:
                    data = instagram.fetch_instagram_profile_info(username, cookies_path)
                except Exception as e1:
                    print(f"[debug] fetch_instagram_profile_info failed: {e1}. Trying Graph API fallback...", flush=True)
                    try:
                        data = instagram.fetch_instagram_profile_info_fallback(username, cookies_path)
                    except Exception as e2:
                        print(f"[debug] All Instagram profile fallbacks failed: {e2}", flush=True)
                        raise Exception(
                            f"Failed to fetch Instagram profile: {e_primary} / {e1} / {e2}"
                        )
                entries = instagram.parse_instagram_profile_json(data, username, limit=limit)

            if not entries:
                # Never a silent empty state (design-principles §3): every
                # method above either raises or returns entries here, so an
                # empty list means Instagram genuinely answered with zero
                # videos for every method tried - surface that, don't render
                # a confusing "0 items" playlist.
                raise Exception(f"No public video posts/reels found for Instagram profile {username}")

            # Format as playlist/entries
            return {
                "_type": "playlist",
                "title": f"Instagram: {username}",
                "uploader": username,
                "entries": entries,
                "thumbnail": entries[0].get("thumbnail") if entries else None,
            }
        finally:
            if auto_cookiefile:
                cookies._cleanup_temp_cookiefiles([auto_cookiefile])

    # Runs in-process via the yt-dlp Python package instead of spawning the
    # vendored PyInstaller-frozen ./yt-dlp binary: that binary self-extracts
    # its bundled Python runtime into a temp dir on every single invocation,
    # which measured 12+ seconds of pure startup overhead before it even
    # begins extracting - the actual network extraction only takes ~1-2s.
    # Calling the library directly skips that overhead entirely.
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "simulate": True,
        "skip_download": True,
        "socket_timeout": 30,
        "check_formats": False,
        # YouTube forces SABR streaming (URL-less formats needing an n-sig
        # challenge solve) for an authenticated/cookied request; without this,
        # yt-dlp silently skips its EJS challenge-solver fetch and raises "No
        # video formats found" instead of extracting. Harmless when unused.
        "remote_components": {"ejs:github"},
    }
    if cls.is_multi:
        # Flat extraction: list each entry's id/title/url/duration/thumbnail
        # WITHOUT fetching every video's full metadata - a channel with thousands
        # of videos would otherwise hang the app. playlistend caps the count as a
        # second guard on top of the flat (metadata-free) listing; the classifier
        # already picked what the link is; the cap itself comes from effective_item_limit().
        ydl_opts["noplaylist"] = False
        ydl_opts["extract_flat"] = "in_playlist"
        ydl_opts["playlistend"] = item_limit
        ydl_opts["ignoreerrors"] = True
    else:
        ydl_opts["noplaylist"] = True

    cookies_path = config.get_cookies_path()
    auto_cookiefile = None

    if "instagram" in url.lower():
        # Inject modern browser user-agent and referer headers to bypass block/rate-limits
        ydl_opts["http_headers"] = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.instagram.com/",
        }
        # Fall back to auto browser cookies extraction if manual cookies settings not valid/empty
        if not (cookies_path and config.cookies_status_for(cookies_path) == "valid"):
            candidates = cookies.instagram_cookiefile_candidates()
            if candidates:
                auto_cookiefile = candidates[0]
                # Cleanup candidates list we won't use
                cookies._cleanup_temp_cookiefiles(candidates[1:])
                cookies_path = auto_cookiefile

    if cookies_path:
        ydl_opts["cookiefile"] = cookies_path

    def attempt(cookiefile):
        opts = dict(ydl_opts)
        if cookiefile:
            opts["cookiefile"] = cookiefile
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    try:
        # A YouTube login/anti-bot answer gets exactly one retry with the
        # configured browser profile's cookies (see cookies.run_with_youtube_cookie_fallback).
        return cookies.run_with_youtube_cookie_fallback(url, cookies_path, attempt)
    except Exception as e:
        # Only an Instagram failure is labelled as one - this line used to say
        # "Instagram" for every platform (it misled a Threads debugging session).
        if "instagram" in url.lower():
            print(f"[debug] Instagram check failed for {url}. Error: {strip_ansi(str(e))}", flush=True)
        raise
    finally:
        if auto_cookiefile:
            cookies._cleanup_temp_cookiefiles([auto_cookiefile])


_YOUTUBE_RESTRICTED_MARKERS = (
    "private video",
    "members-only",
    "members only",
    "join this channel",
    "not available in your country",
    "blocked it in your country",
    "age-restricted",
    "video unavailable",
    "has been removed",
    "this video is unavailable",
)


_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")
# yt-dlp colours "ERROR:" with ANSI codes; somewhere between yt-dlp and the UI
# the ESC byte gets dropped, leaving a literal "[0;31m" in the text.
_ANSI_ESCAPE_LOST_RE = re.compile(r"\[[0-9;]+m")


def strip_ansi(text):
    return _ANSI_ESCAPE_LOST_RE.sub("", _ANSI_ESCAPE_RE.sub("", text))


def describe_extraction_error(url, error, cookies_path=None, lang=None):
    message = strip_ansi(str(error))
    lower = message.lower()

    # A failure to even reach the network (no internet, DNS lookup failed,
    # a firewall/VPN silently dropping the connection, the request timing
    # out) is its own distinct, user-actionable case - and these are ALSO
    # bare builtin exceptions (ConnectionError/TimeoutError/socket.gaierror
    # all have __module__ == "builtins"), so without checking for them
    # first they'd otherwise fall into the generic "something broke"
    # fallback below, hiding a "you're offline" failure behind a message
    # that doesn't say so.
    if isinstance(error, (ConnectionError, TimeoutError, socket.gaierror)):
        return messages.text("network_unreachable", lang)

    # "Audio Only" on a video that has no sound track (a silent X clip, for
    # example): yt-dlp's audio extractor cannot find an audio stream and says so
    # in a ffprobe warning. Say what is true instead of the generic failure.
    if "unable to obtain file audio codec" in lower:
        return messages.text("no_audio_track", lang)

    # YouTube: tell the three causes apart (browser-cookie read denied, login /
    # anti-bot demand, a video that is restricted for everyone) - the generic
    # "check the link" text below misled the user when the link was fine.
    if isinstance(error, cookies.YouTubeCookieAccessError):
        return messages.text("youtube_cookies_keychain", lang)
    if cookies.is_youtube_url(url):
        if cookies.is_youtube_auth_error(error):
            return messages.text("youtube_signin_required", lang)
        if any(marker in lower for marker in _YOUTUBE_RESTRICTED_MARKERS):
            return messages.text("youtube_restricted", lang)

    # A site yt-dlp has no extractor for, and a site whose video player changed
    # under yt-dlp's feet: both get a mapped message, never yt-dlp's own text.
    if "unsupported url" in lower:
        platform = classify.get_platform_info(url)
        if platform and platform != "Link":
            return messages.text("unsupported_platform", lang, platform=platform)
        return messages.text("unsupported_site", lang)
    if "unable to extract video" in lower:
        return messages.text("page_changed", lang)

    # A bare builtin exception (ValueError, KeyError, TypeError, ...) means
    # something broke unexpectedly deep inside an extractor (e.g. a yt-dlp
    # internal bug hitting `int('')` while parsing a platform's response) -
    # its message is raw Python internals, not something meant for a user to
    # read, unlike a DownloadError/InstagramAuthError/etc. that this
    # codebase (or yt-dlp itself) deliberately raises with a real
    # explanation. Never let the former leak through as the final fallback
    # below.
    is_trusted_message = type(error).__module__ != "builtins"

    # Instagram profile / user failures
    is_ig_profile = classify.is_instagram_profile_url(url)
    if is_ig_profile or "instagram:user" in lower or "instagram:profile" in lower or ("unable to extract data" in lower and "instagram" in url.lower()):
        return messages.text("instagram_profile_restricted", lang)

    # A platform (TikTok especially) temporarily rate-limiting/blocking this
    # machine's IP is a distinct failure from a private account and deserves
    # its own clear message - lumping it into "Private account" below is
    # actively misleading. Checked before the private/login patterns since
    # "blocked" can otherwise get masked by an unrelated coincidental match.
    if "ip address is blocked" in lower or "blocked from accessing" in lower:
        return messages.text("ip_blocked", lang)

    # Instagram, TikTok, Facebook private/login required errors. "302"/"400"
    # match an HTTP status code via a word boundary - a bare substring check
    # used to false-positive on those digits appearing inside an unrelated
    # video ID (e.g. "...5400105274..." contains "400"), misreporting a
    # completely different failure (confirmed live on a real TikTok video)
    # as "Private account".
    is_private_or_login = (
        "login" in lower or
        "cookie" in lower or
        "confirm your identity" in lower or
        "requires logged-in session" in lower or
        "private video" in lower or
        "private account" in lower or
        "only available for registered users" in lower or
        "empty media response" in lower or
        re.search(r"\b(?:302|400)\b", lower) or
        "redirect" in lower
    )
    is_major_platform = any(p in url.lower() for p in ("instagram", "tiktok", "facebook", "fb.watch", "fb.com"))

    if is_major_platform and is_private_or_login:
        return messages.text("private_account", lang)

    # General cleanup: hide traceback or github links
    if "unable to extract data" in lower or "traceback" in lower or "report this issue" in lower or "github.com" in lower:
        return messages.text("extract_failed", lang)
        
    generic_fallback = messages.text("process_failed", lang)
    if not is_trusted_message:
        return generic_fallback
    # yt-dlp's own wording is never shown to the user - only messages mapped
    # above. (Errors this codebase raises itself, e.g. InstagramAuthError, carry
    # a written explanation and still pass through below.)
    if type(error).__module__.startswith("yt_dlp"):
        return generic_fallback

    message = message.removeprefix("ERROR: ")
    first_sentence = message.split(". ")[0].strip()
    if "github" in first_sentence.lower() or "report this issue" in first_sentence.lower():
        return messages.text("load_failed", lang)

    # Last resort: an exception with no usable message at all (e.g. a bare
    # `raise SomeCustomError()`) reaching this point means every earlier,
    # more specific mapping above missed it - still say something
    # actionable instead of the old bare "Invalid link or private video"
    # dead end.
    return first_sentence or generic_fallback


def _format_label_height(f):
    # The platform's own displayed quality label (e.g. YouTube's "1440p",
    # "2160p") lives in format_note. For a non-16:9 source (ultrawide/
    # letterboxed) the raw pixel `height` can be well below the labeled tier
    # - a real "2160p" stream can be as short as 1440px - so using raw
    # height instead of the label both shows the wrong number to the user
    # and (in qualities_for) makes the >= 360 floor drop tiers that are
    # actually >= 360p by the platform's own label. Falls back to raw
    # height when there's no parseable format_note (most non-YouTube
    # extractors don't populate it, but their raw height already matches
    # what the platform displays in practice).
    h = f.get("height")
    if not h or not isinstance(h, int):
        return None
    note_match = _QUALITY_LABEL_RE.match(f.get("format_note") or "")
    return int(note_match.group(1)) if note_match else h


def qualities_for(info):
    res_set = set()
    for f in info.get("formats", []):
        label_height = _format_label_height(f)
        if label_height is not None and label_height >= 360:
            res_set.add(label_height)
    qualities = [f"{h}p" for h in sorted(res_set, reverse=True)]
    qualities.append("Best")
    qualities.append("Audio Only")
    return qualities


def resolve_quality_height(formats, quality):
    """Map a quality label like "1080p" (one of qualities_for()'s own
    outputs) back to the raw pixel `height` that label actually means for
    THIS media - not just the label's numeric value, which only equals raw
    height for a 16:9 source (see _format_label_height). This is what makes
    a download match the label the user picked instead of over- or under-
    shooting it on an unusually-shaped source. Returns None for "Best"/
    "Audio Only" (the caller should leave those uncapped) or when `quality`
    isn't a recognized "Np" label. Falls back to treating the label's own
    number as the raw height when no format in `formats` actually carries
    that label (e.g. the lookup failed, or the source has no format_note at
    all) - the same assumption used before per-label resolution existed.
    """
    if quality in ("Best", "Audio Only") or not quality.endswith("p"):
        return None
    try:
        target_label = int(quality[:-1])
    except ValueError:
        return None
    matched_height = None
    for f in formats or []:
        if _format_label_height(f) == target_label:
            h = f["height"]
            if matched_height is None or h > matched_height:
                matched_height = h
    return matched_height if matched_height is not None else target_label


def format_duration(duration):
    if not isinstance(duration, (int, float)):
        return None
    minutes, seconds = divmod(int(duration), 60)
    return f"{minutes:02d}:{seconds:02d}"


def flat_playlist_items(entries):
    # Shape flat-extraction entries (YouTube playlist/channel, Instagram profile)
    # into /api/check playlist items. The 1-based `position` is the video's TRUE
    # spot in the list (kept even for hidden/removed videos) and is used for UI
    # numbering ONLY - PRD §7: the number must never touch the physical filename,
    # so `title` stays the raw video title (the batch download builds the saved
    # file from it). A 1-item "playlist" gets position None - the frontend
    # renders it as a plain single video.
    number_items = len(entries) > 1
    items = []
    for pos, entry in enumerate(entries, start=1):
        item_url = entry.get("url") or entry.get("webpage_url")
        if not item_url and entry.get("id"):
            item_url = f"https://www.youtube.com/watch?v={entry['id']}"
        raw_title = entry.get("title") or "Video"
        duration = entry.get("duration")
        # A playlist routinely contains hidden/removed videos. yt-dlp lists
        # them with a "[Private video]"/"[Deleted video]" title and no
        # duration - flag those so the UI can disable/hide them and never
        # let a batch queue a doomed download. Keep them in the list (not
        # dropped) so the numbering stays true to the real playlist.
        lower = raw_title.lower()
        is_available = not (
            "[private video]" in lower
            or "[deleted video]" in lower
            or "[unavailable video]" in lower
            or duration is None
            or not item_url
        )
        items.append({
            "id": entry.get("id"),
            "title": raw_title,
            "position": pos if number_items else None,
            "uploader": entry.get("uploader") or entry.get("channel") or "",
            "thumbnail": resolve_thumbnail(entry),
            "duration": format_duration(duration),
            "url": item_url,
            "qualities": classify.PLAYLIST_QUALITIES,
            "is_available": is_available,
        })
    return items


def story_playlist_items(entries):
    # Shape a full (non-flat) yt-dlp playlist - an Instagram Story - into
    # /api/check playlist items: keep only the actual videos (photo entries
    # carry no formats) but remember each one's ORIGINAL 1-based position so
    # download targets the right entry even after photos are filtered out.
    items = []
    for original_index, entry in enumerate(entries, start=1):
        if not entry.get("formats"):
            continue
        items.append({
            "id": entry.get("id"),
            "title": entry.get("title") or "Video",
            "thumbnail": resolve_thumbnail(entry),
            "duration": format_duration(entry.get("duration")),
            "entry_index": original_index,
            "qualities": qualities_for(entry),
        })
    return items
