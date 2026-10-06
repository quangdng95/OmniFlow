# Changelog

All notable changes to OmniFlow are documented here. Dates are in `YYYY-MM-DD` format. This file
is the raw, engineering-facing history; the app itself also has an in-app **Changelog** page
(`frontend/src/pages/ChangelogPage.tsx`, header nav) with the same entries written for end users —
keep both updated together when shipping a user-visible change.

## 2026-10-06

### Added

- [x] **History tab** — the last 10 links downloaded on this device (`localStorage`, newest first,
  one row per URL); "Download again" refills Home and re-checks the link.
- [x] **Slim sticky header** — one 49px bar (logo at half its old size, EN | VI, one menu button
  holding every page) instead of ~340px of nav pills; Home's intro moved into the page content.
- [x] **LinkedIn document / slide-deck posts** — the page embeds a manifest of every page
  (`backend/linkedin.py`); each page is an image item, downloaded like a carousel. Previously only the
  cover was saved. `lnkd.in` / `t.co` / `fb.me` short links are expanded before classification
  (`backend/shortlinks.py`, allowlisted hosts, redirects followed by hand, destination never fetched).
- [x] **RedNote resolver** (`backend/rednote.py`) — RedNote now requires a login and renamed the stream
  groups, so yt-dlp's extractor fails even when logged in; the note is read from the page state with the
  user's own session. The Mac's browser scan now includes Arc.
- [x] **Self-maintenance on the cloud VM** (`remote_web/selfheal.py`, systemd timer every 6 h) — upgrades
  yt-dlp, runs a canary per platform through the app's own API, rolls yt-dlp back if an upgrade breaks a
  platform; result in `/api/health/detail` (`canary`, `cookies_age_hours`).
- [x] TikTok videos resolved through the tikwm fallback offer **Audio Only** (MP3).

### Fixed

- [x] iPhone "The request is not allowed…" when saving a batch: the file is prepared before the tap so
  `navigator.share()` runs inside the user-activation window; a confirmation toast follows a save.
- [x] TikTok videos with no sound on iPhone/Mac (H.265 video-only tier merged with an MP3 track, which
  Apple players can't play): the audio is re-encoded to AAC after download (`ensure_apple_audio`).
- [x] Downloaded images get their extension from their real bytes (LinkedIn pages are PNG, were `.jpg`).
- [x] Row checkboxes could not be toggled (Base UI's hidden input double-toggled); downloaded rows stay
  selectable; all action buttons share one size.
- [x] The Mac→VM cookie sync had silently failed since public SSH was closed: it now POSTs over HTTPS
  with the access token, waits for the network after a wake, runs hourly, and notifies on failure; the
  server refuses anything that isn't a cookie jar and writes atomically.
- [x] Threads now uses the uploaded cookie file (a headless VM has no browser to extract from).

## 2026-09-25

### Added — English / Vietnamese switch

- [x] `LanguageSwitcher` (EN | VI) in the header of every page; the language also defaults to
  Vietnamese on a Vietnamese-language browser (`i18n/storage.ts`: localStorage → shared cookie →
  `navigator.language`), and `<html lang>` follows it.
- [x] Backend error text is bilingual: `backend/messages.py` is one catalog for the desktop app and
  `remote_web`, chosen per request from the `X-Language` header the frontend now sends (captured in
  the route and passed into worker threads). Vietnamese remains the default when no header is sent,
  so the iOS Shortcut and other header-less clients behave as before. Client-side errors
  (`api.ts`, `saveFile.ts`) are translated too.
- [x] The server-rendered `/unlock` page follows `?lang=` → the shared `omniflow-language` cookie →
  `Accept-Language` → English, and has its own English / Tiếng Việt link.
- [x] The header nav wraps instead of overflowing, which had pushed "Home" out of reach on phones
  once the Changelog item was added. "Supported Platforms" was the last hardcoded UI heading.

### Fixed — Cloud (`remote_web`) Facebook downloads hanging

- [x] A Facebook reel whose DASH tiers are all AV1 was downloaded as 1080p AV1 and then re-encoded
  to H.264 by `ensure_h264()` on the 1 GB shared-vCPU cloud VM — minutes at 100% CPU that also
  slowed every other request (a concurrent link check took 27 s+). `remote_web` now sets
  `download.AVOID_REENCODE`, which puts native H.264 first in the format selector (Facebook's muxed
  `hd`/`sd` files, named by format id since yt-dlp reports their codec as unknown). Desktop app
  unchanged. Trade-off: a Facebook video with only an AV1 1080p tier downloads at 720p H.264 on the
  cloud. See MISTAKES.md 2026-09-25.
- [x] The single-video progress label shows "Processing video…" at 100% instead of a frozen
  "100% Downloading…".

## 2026-09-18

### Fixed — TikTok & download reliability

- [x] Fixed TikTok Photo Mode/carousel thumbnails not rendering correctly for some posts.
- [x] Fixed the per-row "Retry" action on a failed download returning a 404 instead of retrying.
- [x] Fixed bulk save-to-Photos (mobile Share Sheet flow) only saving the first item of a batch.

## 2026-09-16

### Added — Remote automation & mobile

- [x] **Bearer-token API auth**: `/api/*` now also accepts `Authorization: Bearer <token>`, so a
  headless client (the new iOS Shortcut) can call the API without a browser cookie session.
- [x] **iOS Shortcut Setup guide** (new page, `ShortcutSetupPage`): share a link from any app →
  OmniFlow downloads it and hands the file back, no browser needed. Linked from the header nav,
  remote-deployment only (hidden for the local desktop app).
- [x] Mobile Share Sheet saves (including bulk saves) now complete end-to-end on iOS.
- [x] Restricted remote SSH/server-management access behind the app's own IAP gate.

### Fixed — YouTube

- [x] Fixed YouTube downloads breaking after YouTube rolled out its newer SABR anti-bot streaming
  protocol.

## 2026-08-29 → 2026-09-10

### Added — Remote Web Access (new capability)

- [x] **Remote Web Access**: OmniFlow can run on a personal cloud server and be reached securely
  from a phone or any other device via a private URL, gated by a signed trust-cookie login +
  lockout (see `.claude/rules/web-app.md` and the `remote_web` package).
- [x] Batch (playlist/carousel) downloads over remote access assemble into a single incremental
  ZIP (`ZIP_STORED`) instead of requiring one file at a time.
- [x] Mac → cloud-VM Instagram/Threads cookie sync, so authenticated downloads keep working when
  OmniFlow isn't running on the machine that owns the browser session.
- [x] Manual `cookies.txt` upload path for headless/cloud deployments with no browser to
  auto-extract cookies from.
- [x] Linux ffmpeg resolution via `PATH` for cloud portability (previously macOS-only lookup).

## 2026-08-29 → 2026-08-30

### Added — TikTok Photo Mode

- [x] Support for downloading TikTok "Photo Mode" posts (multi-image slideshows) via the
  third-party `tikwm.com` resolver — previously unsupported (no yt-dlp extractor exists for this
  shape at all).
- [x] Widened the same `tikwm.com` fallback to cover normal TikTok **video** downloads too, after
  yt-dlp's own TikTok extractor broke upstream (yt-dlp/yt-dlp#16199).

### Fixed

- [x] Fixed a LinkedIn video download bug.
- [x] Rebuilt the vendored ffmpeg as a self-contained, native arm64 binary (via `dylibbundler`) —
  a real speed improvement on Apple Silicon, which previously ran the Intel binary under Rosetta 2.
- [x] `api.ts`'s `request()` no longer leaks a raw JSON-parse error to the UI on a malformed
  response.

## 2026-07-10

A full round of live bug fixes driven by real user reports and diagnostic logs from a clean Intel Mac, followed by a UI polish pass against the Figma design.

### Fixed — Instagram / Threads check & download

- [x] **Root-caused and fixed the real "check/download fails on a clean machine" bug**: the packaged `.app`'s Python interpreter had a broken default SSL certificate path baked in at build time (pointing at a Homebrew/conda location that only exists on the build machine). Every raw HTTPS request the Instagram/Threads/LinkedIn resolvers make now correctly uses the certificate bundle shipped inside the app, regardless of how it was built.
- [x] Fixed a real data-loss bug in Chrome cookie reading: Chrome's cookie database uses SQLite's WAL mode, so a copy of just the main database file could silently miss a recently-written session cookie. The cookie-extraction step now also copies the WAL sidecar files.
- [x] Cookie-extraction failures (Instagram/Threads auto-login) are no longer silently swallowed — every failure reason is now recorded so a mysterious "no session found" can actually be diagnosed instead of guessed at.
- [x] Fixed a message that could misleadingly report "Private account" when the real cause was an expired saved session, not the target post being private.

### Added — Self-serve diagnostics (Settings page)

- [x] **Diagnostic Logs**: a button to open the folder containing OmniFlow's error log, so a failure can be diagnosed and reported without digging through `~/Library/Logs` manually.
- [x] **Reset App Data**: a button to clear OmniFlow's saved settings (download path, saved cookies, etc.) and start fresh — the in-app equivalent of the old "quit the app and delete a hidden config file by hand" troubleshooting step. Does not touch any downloaded files.

### Added — Smarter link handling

- [x] Pasting a platform's full "Share" text (title, hashtags, emoji, and all) instead of a bare URL now works — the app pulls the real link out automatically. Previously this only worked for a clean, bare URL.

### Fixed — UI (pixel-matched against Figma)

- [x] App logo (header and footer) now uses the correct brand colors — it was rendering with the wrong background/icon color combination.
- [x] "Supported Platforms" section heading restyled to match the rest of the page's section headings.
- [x] Removed a redundant duplicate text label under each platform's icon on the Home page (the icon already includes its own label).
- [x] The header's divider line now spans the full width of the header bar instead of stopping short of the edges.
- [x] Improved the contrast of the Home page's secondary description text for readability.
- [x] Settings and Terms of Use page titles now sit close to the header instead of floating with a large empty gap below it.
- [x] Reordered the Settings page so "Diagnostic Logs" and "Reset App Data" sit at the bottom, after the existing settings sections.
- [x] All in-app notifications now have a close button so they can be dismissed immediately instead of waiting for them to time out.

### Housekeeping

- [x] Cleaned up a duplicate stale build artifact left in `dist/` by iCloud file sync.
