# Platform support

What ViDrop can download from each platform, checked against real links on **2026-10-13**
(Mac app, Apple Silicon, yt-dlp 2026.8.19). Every ✅ below was a real download or a real
link check, verified with `ffprobe` (picture, sound, size) and then deleted.

| Status | Meaning |
|---|---|
| ✅ Works | Checked and downloaded on 2026-10-13. |
| 🔑 Works, needs sign-in | Works when you are signed in to that platform in your browser. |
| ⚠️ Known limit | Not fixable inside ViDrop. The limit and what to do are in the Notes. |
| ➖ Not tested | No sample link, or the sample link had expired. Not a claim that it fails. |

## YouTube

| Content | Status | Notes |
|---|---|---|
| Video, up to 4K (2160p) | 🔑 Works, needs sign-in | Downloaded a 2160p video as H.264 + AAC. YouTube often refuses a Mac with "Sign in to confirm you're not a bot". Choose your Chrome profile in **Settings → YouTube sign-in** (off by default). |
| Audio only (MP3) | 🔑 Works, needs sign-in | |
| `youtu.be` short link | 🔑 Works, needs sign-in | |
| Mix / Radio (`list=RD…`) | ✅ Works | Lists 50 items. Downloading an item works; one video failed twice with a YouTube `403` and then worked, so retry if it fails. |
| Playlist and channel | ✅ Works | Lists up to your loading limit in Settings (30–500, or All up to 10,000). A channel link such as `youtube.com/@name` now lists its videos (it used to list three empty tabs). Checked with public links that are not in the sample list. |

## TikTok

| Content | Status | Notes |
|---|---|---|
| Video | ✅ Works | Read directly. If that fails, ViDrop falls back to the third-party service tikwm.com. Some videos arrive as H.265, which plays on a Mac but not in every other player. |
| Audio only (MP3) | ✅ Works | |
| Photo Mode slideshow | ✅ Works | Lists every image; download all or pick some. Always resolved through tikwm.com. |
| `vt.tiktok.com` short link | ✅ Works | |

## Instagram

| Content | Status | Notes |
|---|---|---|
| Reel | 🔑 Works, needs sign-in | H.264 + AAC. |
| Photo post | 🔑 Works, needs sign-in | |
| Carousel (photos and videos) | 🔑 Works, needs sign-in | Lists every slide. |
| Profile / Reels list | ⚠️ Known limit | Instagram refused to list the profile on both tries (the first one with a `429`, too many requests). Paste single posts or Reels instead, or try again later. |
| Story | ➖ Not tested | No sample link. |
| Private post you follow | ➖ Not tested | No sample link. |

## Facebook

| Content | Status | Notes |
|---|---|---|
| Reel | ✅ Works | 1080 × 1920 H.264 + AAC. |
| `facebook.com/share/r/…` link | ✅ Works | |
| `facebook.com/watch`, `fb.watch` | ➖ Not tested | No sample link. |
| `fb.me` short link | ➖ Not tested | No sample link. |

## X (Twitter)

| Content | Status | Notes |
|---|---|---|
| Video post | ✅ Works | Up to 1792 px. |
| Audio only | ➖ Not tested | The only sample clip has no sound. ViDrop says so ("This video has no audio track") instead of failing with a generic error. |
| Image or GIF post | ➖ Not tested | No sample link. |
| `t.co` short link | ➖ Not tested | No sample link. |

## Threads

| Content | Status | Notes |
|---|---|---|
| Video post | 🔑 Works, needs sign-in | |
| Image post | 🔑 Works, needs sign-in | |
| `threads.com/share/…` link | ➖ Not tested | No sample link. Covered by unit tests only. |

## LinkedIn

| Content | Status | Notes |
|---|---|---|
| Video post | ✅ Works | Needs no sign-in. |
| Image post | ✅ Works | Needs no sign-in. |
| Document / slide deck (`lnkd.in`) | ✅ Works | Every page becomes a PNG image (10 pages in the sample). |

## RedNote (Xiaohongshu)

| Content | Status | Notes |
|---|---|---|
| Video or image note | ➖ Not tested | Both sample links had expired (RedNote's `xsec_token` links stop working). ViDrop now says "This RedNote link has expired" instead of a generic error. Copy a fresh share link from RedNote to try it. Needs a RedNote sign-in in your browser. |

## Sample links missing

To test these, add a link to `docs/EXAMPLE_LINKS.md`: Instagram Story, Instagram private
post, Facebook `watch` / `fb.watch` and `fb.me`, X audio (a clip with sound), X image or
GIF, X `t.co`, Threads `/share/` and a Threads carousel, a fresh RedNote video note and a
fresh RedNote image note, a YouTube 4K horizontal video, and a YouTube playlist
(`list=PL…`).

## How this was checked

Run by hand with real links, never as part of the automated tests. Downloads went to a
temporary folder, were inspected with `ffprobe`, and were deleted. Each case was tried at
most twice. The cloud canary (`remote_web/canary_urls.json`) re-checks a link of each kind
every six hours.
