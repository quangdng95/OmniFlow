# Changelog

All notable changes to ViDrop are documented here. Dates are in `YYYY-MM-DD` format. This file
is the raw, engineering-facing history; the app itself also has an in-app **Changelog** page
(`frontend/src/pages/ChangelogPage.tsx`, header nav) with the same entries written for end users —
keep both updated together when shipping a user-visible change.

## 2026-10-16 · Pinterest boards and pins

- [x] Paste a Pinterest board link (`pinterest.com/<user>/<board>/`) and every pin is listed for download, like a
  playlist: images at original size, video pins as MP4. A single `/pin/<id>/` link and `pin.it` short links work too.
  Profiles and board sections are refused with a clear message; Idea pins are skipped.
- [x] `backend/pinterest.py` reads Pinterest's own web API (`BoardResource`/`BoardFeedResource`/`PinResource`) through
  curl_cffi with Chrome impersonation and the `X-Pinterest-PWS-Handler` header (without it every call is 403). A public
  board needs no login. A private ("secret") board answers "not found" to everyone but its owner, so the resolver then
  tries the owner's `_pinterest_sess` from the browsers on the Mac. On the cloud VM there is no Pinterest login (not
  synced on purpose), so a private board says it needs the Mac app.
- [x] Classification in `classify.py` (`PINTEREST_BOARD`/`PINTEREST_PIN`/`PINTEREST_UNSUPPORTED`), routes in both
  `backend/app.py` and `remote_web/routes/media.py`; frontend: Pinterest platform tag and tile.

## 2026-10-14 · Web: new primary host `cloud.nguyenduyquang.com`

- [x] The web version is served on `cloud.nguyenduyquang.com` and, side by side, the old `cloud.southframevn.com`
  (both hostnames are in the tunnel's `~/.cloudflared/config.yml` on the VM: the tunnel is locally managed, so
  a "Public hostname" added in the Cloudflare dashboard would NOT take effect). One setting,
  `remote_web/config.py` (`PUBLIC_HOST`, `OMNIFLOW_PUBLIC_HOST`, `OMNIFLOW_EXTRA_HOSTS`), defines the primary
  host and `ALLOWED_HOSTS` (primary, old, loopback); any other `Host` header gets 421 before anything else runs.
- [x] Share previews (`og:image`, `twitter:image`, new `og:url`) use the primary host: `index.html` carries
  `__PUBLIC_ORIGIN__` and `backend/webpage.py` fills it in when a server serves the page (the Mac app uses its
  loopback origin). The trust cookie stays host-only (Secure, HttpOnly, SameSite=Lax, no Domain).
- [x] `sync_cloud_cookies.py` defaults to the new host (`OMNIFLOW_CLOUD_URL` still overrides).

## 2026-10-14 · ViDrop 2.0.3

### Fixed

- [x] **RedNote share links** (`xhslink.com/o/...`): without a session RedNote answers them with a redirect to its
  login page that carries the note URL in `redirectPath`; `rednote.expand_short_link` reads it, the note is then
  fetched with the session of the domain it belongs to (a jar with no login for a host is not asked), timeouts
  are retried and a timeout is no longer reported as "not signed in", and yt-dlp is skipped for share links
  (it cost 12 s and could not open them anyway). Works in the Mac app. On the cloud VM RedNote sends the
  server to its sign-in page even with the synced session (checked on the VM with the same cookies that work
  on the Mac: most likely it distrusts a datacenter IP), so the web version now says "use the Mac app"
  (`rednote_cloud_blocked`) instead of asking for a login on the server.
- [x] **X photo tweets**: yt-dlp only reads tweets with a video or GIF. `backend/xposts.py` reads the photos from
  X's public embed endpoint (original size). Single photo = an image item; several = a list.
- [x] **Readable titles**: LinkedIn and X posts use the caption as the title; `extraction.display_title` makes it one
  short line, and `sanitize_filename` drops links, line breaks and empty brackets from file names.
- [x] **Instagram carousel link with `?img_index=N`** opens with slide N ticked (`selected_index`).
- [x] **iPhone Home Screen icon**: `frontend/plugins/inlineIcons.ts` writes the 180 px apple-touch-icon into
  `index.html` as a data: URI (and the manifest icons inline), with file-based 167/152 px icons as fallbacks, so
  "Add to Home Screen" needs no second download. Not reproduced on a device; see MISTAKES.md.
- [x] Measured on the 2017 Intel MacBook Pro (8 logical cores): a 3:14 4K clip took 100.8 s in total with the
  hardware encoder (90.1 s of it encoding), against about 1.1 s of processing per second of video before. The
  encoder rule is unchanged (x86_64 -> VideoToolbox).
- [x] The Mac app gets "Clear cache and saved data" (added to the web version earlier the same day).

## 2026-10-14 · Settings: Clear cache and saved data

- [x] **One action to clear old data** (Settings, web and Mac app): `frontend/src/lib/clearData.ts` empties
  localStorage, sessionStorage, Cache Storage, service workers, IndexedDB and the cookies the page can see,
  re-downloads the core files with `cache: "reload"` so the HTTP cache holds the current ones, then reloads
  at `/?fresh=<time>`. `POST /api/clear-session` is the server half: the web version drops the trust and
  language cookies (signs this browser out; shared VM data is untouched), the Mac app removes only its own
  temp cookie files and forgets finished jobs from memory. Downloaded files, the save folder and
  `config.json` are never touched. Limits: it cannot clear the browser's own HTTP cache directly or an icon
  iOS already copied to the Home Screen (remove and re-add that one).

## 2026-10-14 · Web update: Home Screen icon (after 2.0.2)

### Fixed

- [x] **"Add to Home Screen" on iPhone showed a plain letter tile instead of the logo.** The icon files were
  public and valid, but Cloudflare asked the VM again for every request ("REVALIDATED", 0.5-1.4 s through
  the tunnel) and iOS draws the letter tile when the icon is late. Brand files are now cacheable at the edge
  (`s-maxage`), build assets are `immutable`, and the icon links moved to `?v=4` (a new URL, so nothing
  cached earlier can get in the way). Cause is the most likely one, not reproduced on a device.

## 2026-10-14 · ViDrop 2.0.2

### Changed

- [x] **Mac app rebuilt with the web changes made after 2.0.1** (per-platform Save to device, the single
  icon source, the "Saved to your device" confirmation, paste on tap of the empty field). The cloud web
  already had them. No change to the encoder rule: it is still unverified on a real Intel Mac.
- [x] Tests: the cloud app tests no longer need a built `frontend/dist` (they serve a stand-in made of
  `frontend/public`, so a fresh clone runs the whole suite green with nothing skipped);
  `tests/test_brand_name.py` guards the `ViDrop` spelling.
- [x] README Roadmap rewritten to the real open items (EN + VI); `docs/PLATFORM_SUPPORT.md` states that
  seven of eight platforms are verified and RedNote is not.

## 2026-10-13 · Web update (after 2.0.1)

### Fixed

- [x] **Phone follow-ups**: the page confirms "Saved to your device" after the iOS share sheet completes (it used to stay silent); tapping the empty URL field reads the clipboard (a phone only allows that inside a tap), on top of the load/focus/visibility attempts plus a retry 600 ms later.
- [x] **Save to device per platform** (`frontend/src/lib/saveFile.ts`, `hooks/usePreparedSave.ts`).
  iPhone/iPad (incl. iPadOS with a desktop user agent): the finished file is fetched ahead of the tap
  (progress, abortable, 400 MB cap) so the tap calls `navigator.share({files})` at once ("Save to
  Photos"); a file that is too big or cannot be shared is streamed to the Files app with an iOS
  message. Android and desktop: plain download of the server URL. Cause of the old behaviour: after the
  streaming fix every file over 100 MB (or with a missing size probe) went to the anchor download, whose
  toast talks about a "download bar" that iOS does not have.
- [x] **One icon everywhere**: `frontend/public/brand/logo.svg` is the single source;
  `scripts/gen-icons.sh` regenerates the favicons, apple-touch-icon, PWA/maskable icons, `og-image.png`,
  the header logo and `docs/logo.png`. `?v=3` on the icon links, iOS' alternative apple-touch-icon names
  answered, tests that the icons and manifest load without the access token while `/api/*` stays gated.

## 2026-10-13 · ViDrop 2.0.1

### Changed

- [x] **Faster 4K / 1440p processing.** VP9/AV1 downloads are converted to H.264 by
  `backend/download.py` `ensure_h264`, which now probes the file once and picks `copy` (already
  H.264), `h264_videotoolbox` or `libx264 -preset veryfast`. Measured on a 4:57 4K clip: the
  conversion is ~85% of the time (libx264 78 s of 97 s on an M4 Pro; hardware encoder 120 s, because it
  runs at a fixed ~60 fps at 4K while libx264 scales with cores; Intel build under Rosetta 178 s
  libx264 vs 135 s hardware). Rule: x86_64 process -> VideoToolbox, Apple Silicon with <= 8
  logical cores -> VideoToolbox, otherwise libx264. `VIDROP_H264_ENCODER=videotoolbox|libx264`
  overrides. A failed hardware encode falls back to libx264 and logs why. AAC audio is copied.
  The rule was measured on an M4 Pro and Rosetta only; a real 2017 Intel Mac has not been timed yet.
- [x] **Real conversion progress**: `/api/progress` returns `stage` and `encode_percent` (from
  `ffmpeg -progress`); the UI shows "Converting to H.264… N%".
- [x] **Keep original codec (fastest)**: for 1440p+ single videos, `keep_codec` merges the VP9/AV1
  stream into a `.mkv` with no conversion (9 s instead of 97 s on the clip above).
- [x] **Web**: a 4K warning before the download starts (1440p+, without keep-codec), a
  15-minute limit on a conversion (friendly error suggesting keep-codec or a lower quality) and one
  conversion at a time.
- [x] `perf.log` (`~/Library/Logs/ViDrop/perf.log`): one line per download with the stage times, the encoder chosen and why.
  No query strings, cookies or tokens.

## 2026-10-13 · ViDrop 2.0.0

### Added

- [x] **Mac app, new identity** — bundle ID `com.vidrop.app`, `ViDrop.app`, a new square yellow
  icon (`Assets/Logo/ViDrop.icns`; the older logo files were removed from the tree and remain in git history), DMGs named per chip:
  `ViDrop-AppleSilicon.dmg` and `ViDrop-Intel.dmg` (`scripts/build.sh` names them by architecture
  and can build the Intel app via `PYTHON_BIN` / `ARCH_PREFIX` / `DIST_DIR`).
- [x] **Data moved to `~/Library/Application Support/ViDrop`** (logs in `~/Library/Logs/ViDrop`).
  On the first launch `backend/migration.py` COPIES the old `OmniFlow` directory: built in a temp
  directory and renamed into place, skips temp cookie jars and caches, writes
  `.migrated-from-omniflow`, never raises, never touches the old directory.
- [x] **Settings → YouTube sign-in** (Mac app, off by default) — choose the Chrome profile whose
  YouTube login is used when YouTube answers "Sign in to confirm you're not a bot".
  `/api/settings` validates `chrome:Default` / `chrome:Profile N`, lists the profiles (display
  names only, never the email) and refuses the setting for a remote visitor.
- [x] `docs/PLATFORM_SUPPORT.md` — what works on each of the 8 platforms, from real-link checks.
- [x] Cloud canary covers more content types (YouTube Mix, TikTok photo slideshow, Instagram
  carousel, Threads image, LinkedIn video, Facebook `share/r/`), with optional `kind` / `min_items`
  expectations. Check-only; RedNote stays out because its links expire.

### Fixed

- [x] **The Mac app icon sat inside a grey tile on macOS 26.** The artwork had a transparent border
  (824 px of art on a 1024 px canvas), so macOS put it on its own plate. The icon is now full-bleed:
  yellow edge to edge, opaque, glyph centred at about half the canvas (`scripts/make-icon.sh`, pinned by
  `tests/test_app_icon.py`).
- [x] **History and the language choice were never kept in the Mac app.** pywebview's macOS default
  (`private_mode=True`) wipes the web view's saved data at every launch; the app now starts with
  `private_mode=False`. (`storage_path` is ignored by the macOS backend, so no old store existed to
  migrate.)
- [x] A pasted YouTube channel link (`/@name`, `/channel/UC…`, `/c/…`, `/user/…`) listed three empty
  tabs (Videos / Live / Shorts); it is now listed through `<channel>/videos`
  (`classify.normalize_youtube_channel_url`). Downloads still use the pasted link.
- [x] A failed or cancelled batch item left its video-only `.f137.mp4` / `.part` file in the save
  folder. `cleanup_partial_download` now runs there too and removes only this download's own
  temporary files and its exact final file; it used to delete by name prefix, which could remove
  other files such as `Title 2.mp4`.
- [x] RedNote share links with an expired `xsec_token` land on `/404?source=/404/sec_…`; the message
  now says the link expired (EN/VI, desktop and cloud).
- [x] "Audio Only" on a video with no sound track (a silent X clip) said "could not process this
  link"; it now says there is no audio.
- [x] The YouTube sign-in error told people to sign in to Chrome and retry although nothing could
  read Chrome unless `youtube_cookie_source` was added to `config.json` by hand; it now points at
  the new setting.
- [x] The Settings text for the playlist limit says what the code does (a Mix lists 50, an Instagram
  profile at most 30).

### Known limits

- Instagram profile / Reels lists can be refused with `429`; single posts, Reels and carousels work.
- YouTube may need the Chrome sign-in above; an occasional `403` on a download goes away on retry.
- TikTok depends on tikwm.com for Photo Mode and as the fallback for videos.

## 2026-10-13

### Changed

- [x] **Display name is ViDrop** everywhere a person reads it (UI, i18n EN/VI, `<title>`, manifest, README,
  docs, error messages, the cloud `/unlock` page). Internal identifiers keep the old `omniflow` names on
  purpose so production and saved data are not disturbed (service/user/SSH key/GCP names, `OMNIFLOW_*`
  variables, the `omniflow-language` / `omniflow_remote_trust` cookies, the data directory); renaming
  those is a separate migration.
- [x] **V3 UI** — design tokens, self-hosted fonts and one shared page column (`.page-container`) so every
  section lines up; the toast close button sits inside the toast with a 44px target.
- [x] **Square yellow logo** — `--signal` background, `--ink` glyph, no rounded corners; new favicon
  (`.svg`, `-32.png`, `.ico`), apple-touch icon, 192/512 and maskable PWA icons, `theme_color` `#ffd60a`.
- [x] **Compact playlist header** — the title is a fixed `clamp()` (24px phone → 40px desktop), at most 3
  lines on a phone and 2 on desktop, with the full text in a `title` attribute; "Total Items" and
  Download All share one row. The oversized title was two conflicting `text-[clamp(...)]` classes.

### Added

- [x] An elapsed-time counter next to "Processing video…" and a hint that 1440p+ takes longer
  (`ElapsedTimer`, `slowHint`).
- [x] A finished download shows a toast, and a system notification when the tab is in the background
  (`lib/notify.ts`; permission is asked once, from a Download click).
- [x] Threads `threads.com/share/<id>` links are expanded to the post URL before classification
  (`backend/shortlinks.py`).
- [x] **YouTube sign-in fallback (local app only, off by default)** — if YouTube answers a sign-in or
  anti-bot error and `config.json` has `youtube_cookie_source` (`chrome:Default` / `chrome:Profile N`),
  the download retries once with that profile's youtube.com cookies. There is no Settings control for it
  yet; `remote_web` never imports the code that reads browser cookies.

### Fixed

- [x] **Playlist `truncated` flag follows the Settings limit** — `/api/check` compared the list length with
  the fixed `PLAYLIST_ITEM_CAP` (100), so a 200/500/All setting flagged a complete list as truncated and a
  30/50 setting never flagged one. `extraction.effective_item_limit()` is now the single source for both
  yt-dlp's `playlistend` and the flag, on the desktop and cloud routes. Technical caps stay: "All" (stored as
  `0`) is bounded at 10000, an Instagram profile at 30, a YouTube Mix at 50.
- [x] Settings and FAQ wording matches the code: a language change applies immediately (no restart), "no
  limits" became "no fees" (playlists are capped by the Settings limit).
- [x] README / `docs/` / `.github/DISCLAIMER.md` describe the two modes (Mac app on your machine, web version
  on a server behind an access token), the tikwm.com TikTok fallback, 1440p+ re-encoding, and that RedNote
  also needs a browser login.
- [x] Raw yt-dlp text is never shown: "Unsupported URL" and "Unable to extract video" map to friendly
  EN/VI messages (`backend/messages.py`, `describe_extraction_error`).

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
  cloud. See docs/internal/MISTAKES.md 2026-09-25.
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
  ViDrop downloads it and hands the file back, no browser needed. Linked from the header nav,
  remote-deployment only (hidden for the local desktop app).
- [x] Mobile Share Sheet saves (including bulk saves) now complete end-to-end on iOS.
- [x] Restricted remote SSH/server-management access behind the app's own IAP gate.

### Fixed — YouTube

- [x] Fixed YouTube downloads breaking after YouTube rolled out its newer SABR anti-bot streaming
  protocol.

## 2026-08-29 → 2026-09-10

### Added — Remote Web Access (new capability)

- [x] **Remote Web Access**: ViDrop can run on a personal cloud server and be reached securely
  from a phone or any other device via a private URL, gated by a signed trust-cookie login +
  lockout (see `.claude/rules/web-app.md` and the `remote_web` package).
- [x] Batch (playlist/carousel) downloads over remote access assemble into a single incremental
  ZIP (`ZIP_STORED`) instead of requiring one file at a time.
- [x] Mac → cloud-VM Instagram/Threads cookie sync, so authenticated downloads keep working when
  ViDrop isn't running on the machine that owns the browser session.
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

- [x] **Diagnostic Logs**: a button to open the folder containing ViDrop's error log, so a failure can be diagnosed and reported without digging through `~/Library/Logs` manually.
- [x] **Reset App Data**: a button to clear ViDrop's saved settings (download path, saved cookies, etc.) and start fresh — the in-app equivalent of the old "quit the app and delete a hidden config file by hand" troubleshooting step. Does not touch any downloaded files.

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
