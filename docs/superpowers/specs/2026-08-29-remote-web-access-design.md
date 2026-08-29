# Remote Web Access — Design Spec

**Date:** 2026-08-29
**Status:** Draft v3, revised after two rounds of owner review (see §10 and §11 for what changed)

## 1. Problem & Goals

The owner wants to reach OmniFlow's check/download functionality from a phone (or any
device with a browser), anywhere with internet, via a real URL — without installing the
native macOS app on that device.

**Goals:**
- A public HTTPS URL that serves OmniFlow's check/download flow.
- Personal use only — one trusted user (the owner), not a public multi-tenant service.
- Instagram and Threads must work (using the deployment machine's own logged-in browser
  session — the same mechanism the native app already uses).
- Playlist/channel and carousel (multi-item) downloads must work, delivered as a single
  `.zip` to the requesting device.
- **Zero changes to the existing native macOS app**: `backend/`, `server.py`,
  `desktop_app.py`, `OmniFlow.spec`, and the packaged `.app` build must be byte-for-byte
  unaffected by this work. All new code lives in one new, clearly separate top-level
  folder.
- Runs on a dedicated, always-on Mac (an older machine, separate from the owner's main
  dev machine), reachable via a free tunnel service — not a paid cloud VPS. Two reasons:
  cost, and reliability (yt-dlp against cloud-provider IP ranges is materially more
  likely to get rate-limited/blocked by platforms like TikTok than a residential IP —
  see `.claude/rules/web-app.md`'s own dual-mode section for the existing local/remote
  design this builds alongside, and `requirements.txt`'s `curl_cffi` comment for why
  IP reputation already matters to this app today).
- Basic operational visibility — the owner should be able to tell, before relying on it
  away from home, whether the deployment is actually healthy (server up, ffmpeg usable,
  Instagram/Threads cookies still readable).

**Non-goals (v1):**
- Not a public/shareable tool — no accounts, no per-user rate limiting, no billing.
- Not a change to `backend/app.py`'s existing `is_local_request()` behavior or route
  bodies — those keep serving the native app exactly as today.
- Not deployed to a cloud VPS.
- No OAuth/account system — a single shared secret token is the whole auth model,
  backed by Cloudflare Access as a second, edge-level layer (see §4 — elevated from
  "recommended" to "documented as effectively required" after review, §10).

## 2. Why Not Reuse `backend/app.py` Directly

Investigated three lighter-touch alternatives before settling on a separate route layer;
all three fail for the same underlying reason.

`backend/app.py`'s existing `is_local_request()` is a single boolean that currently
controls **two independent concerns** at once inside `check_link`/`start_download`:
(a) whether Instagram/Threads are allowed at all, and (b) whether a finished download
saves straight to the configured local folder or streams back to the requesting browser.
A remote web deployment needs these two answers to *diverge*: Instagram/Threads should
be **allowed** (this is the owner, just not on the loopback address), while file delivery
must stay in **"remote" mode** (stream to the phone, not save to the deployment Mac's own
disk where the phone can never retrieve it).

- **Header-spoofing at a reverse proxy** (make requests through the tunnel look like
  `Host: 127.0.0.1` before they reach the untouched backend) — solves (a) but breaks (b)
  identically, since both checks read the same `is_local_request()` result.
- **Per-request monkeypatching** of `is_local_request()` scoped to just the Instagram/
  Threads code path — same problem: `start_download`'s `save_dir` decision reads the same
  function *before* dispatching to any platform-specific logic, so making it lie for
  Instagram also makes it lie for where the file goes.
- **Editing `backend/app.py`** to split the boolean into two — directly violates the "zero
  changes" goal above.

Conclusion: the HTTP/routing layer for the handful of routes that read
`is_local_request()` needs its own implementation. Everything *below* that layer — actual
extraction, download, per-platform resolvers, progress tracking — has no local/remote
branching at all and is reused unmodified via Python import.

## 3. Architecture

New top-level folder: **`remote_web/`**. Nothing outside it changes.

```
remote_web/
├── __init__.py           # makes remote_web a real, explicitly-importable package -
│                           needed for `python3 -m remote_web.app` / `from remote_web
│                           import ...` to work; also why the folder is remote_web
│                           (underscore), not remote-web - Python cannot import a
│                           hyphenated dotted path at all, this isn't a style choice
├── app.py               # Flask app: creates the app, registers the global trust gate
│                           and Referrer-Policy header, mounts the route modules below,
│                           starts the background reaper thread, serves frontend/dist
├── trust.py              # is_trusted_request(), cookie signing/verification, the
│                           /unlock form (POST-only), CF-Connecting-IP-based lockout
├── routes/
│   ├── __init__.py
│   ├── media.py            # POST /api/check, /api/download, /api/download-batch
│   ├── jobs.py              # GET /api/progress/<id>, POST /api/cancel/<id>,
│   │                          GET /api/download-file/<id> (single file OR batch .zip)
│   ├── settings.py          # GET/POST /api/settings (language only)
│   └── health.py             # GET /health + GET /api/health/detail — see §4.6
├── zipper.py               # Batch-job .zip assembly, ZIP_STORED (see §5)
├── reaper.py                # Filesystem-mtime sweep of stale temp dirs (§5.4) - no
│                              dependency on in-memory job state, survives restarts
├── ffmpeg_locator.py          # resolve_ffmpeg_binary() — architecture-aware, see §5.1
├── config.py                # Trust token/secret-key loading, remote server port, temp
│                              root, cookie max-age
├── requirements.txt          # Additions beyond the root requirements.txt, if any
│                              (expected: none new — itsdangerous ships with Flask already)
├── README.md                  # Setup: venv, first-run token generation, Cloudflare
│                                Tunnel + Access, launchd service, key-rotation and
│                                Keychain-re-approval operational notes
└── tests/
    ├── test_trust.py
    ├── test_media_routes.py
    ├── test_zipper.py
    ├── test_reaper.py
    └── test_ffmpeg_locator.py
```

**Reused, unmodified, via plain Python import:** `backend.classify`, `backend.extraction`,
`backend.download`, `backend.instagram`, `backend.threads`, `backend.linkedin`,
`backend.tiktok`, `backend.cookies`, `backend.config`, `backend.jobs`, `backend.paths`
(only for `log_exception`/`BASE_DIR`-derived paths — not for `get_ffmpeg_path()`, see
§5.1). None of these modules reference `is_local_request()` or any local/remote concept
— that logic lives exclusively in `backend/app.py`'s route bodies, confirmed by
inspection this session. `remote_web/routes/jobs.py`'s progress/cancel routes read and
write `backend.jobs.jobs` the same way the native app's routes do; `jobs` is plain
in-process module state, not shared storage, so `remote_web` and the native app never
actually interact even if both happened to run at once on the same machine — each Python
process gets its own independent dict. This only matters as a note that there's no
hidden coupling to worry about, not a real deployment constraint.

**Not reused, since it always applies:** `backend/app.py`'s local-only convenience routes
(`/api/browse`, `/api/browse-file`, `/api/open-folder`, `/api/open-logs`, `/api/clipboard`)
have no `remote_web` equivalent — the frontend already handles their absence gracefully
for a "remote" client (falls back to `navigator.clipboard.readText()`, hides the
Target-Path/Cookies Settings sections). `frontend/dist` itself is reused unmodified; no
frontend code changes at all.

**Port:** `remote_web` binds to `127.0.0.1:5050` only (distinct from the native app's
`:5001`) — **never** to `0.0.0.0`. This is load-bearing for §4.5's IP-trust design: since
the process only accepts loopback connections, the *only* way to reach it at all is
through `cloudflared` running on the same machine, which means every request Flask ever
sees genuinely came from the tunnel, not directly from the internet.

## 4. Trust Model

Single-tier, blanket gate — **every** `/api/*` route requires trust; there is no
per-platform distinction (unlike the native app's Instagram/Threads-only gate), since the
whole deployment is meant for exactly one person.

### 4.1 Unlocking (revised: form POST, not a magic GET link)

A token in a URL (`GET /unlock?token=...`) ends up in browser history (synced to
iCloud/Google if bookmarked), in `cloudflared`'s own access logs, and potentially in a
`Referer` header if the post-redirect page makes any outbound request — unacceptable when
that token is the entire auth model.

- **`GET /unlock`** renders a minimal, dependency-free HTML page (no React, no JS
  required) with a single password-type input and a POST form. No token ever appears in
  a URL.
- **`POST /unlock`** (body: `token`) — constant-time-compares against the configured
  secret (`hmac.compare_digest`, not `==`, to avoid a timing side-channel). On match, sets
  the signed trust cookie (§4.2) and redirects to `/`. On mismatch, counts toward the
  lockout (§4.5) and re-renders the form with a generic error.
- Every response from `remote_web` (not just `/unlock`) sets
  `Referrer-Policy: no-referrer`, via a global `after_request` hook — cheap, zero
  behavioral cost, closes off Referer-leakage entirely rather than just for this one
  route.

### 4.2 The trust cookie

- Signed with `itsdangerous.URLSafeTimedSerializer`, using a locally-generated app secret
  key (separate from the raw unlock token — compromising one doesn't compromise the
  other).
- Flags: `HttpOnly`, `Secure`, `SameSite=Lax` (explicit — not left to browser defaults;
  `Lax` still allows the cookie on a top-level navigation to the app but blocks
  cross-site XHR/fetch use).
- `max-age`: 90 days (configurable in `remote_web/config.py`). Not "long-lived" and
  unbounded — a lost/stolen phone's access expires on its own within that window even if
  never explicitly revoked.

### 4.3 Revocation

Two distinct operations, both documented as CLI steps in `remote_web/README.md`:

- **Rotate the raw token** (`python3 -m remote_web.config rotate-token` or similar) —
  stops anyone from completing a *new* `/unlock` with the old token. Does **not** affect
  cookies already issued.
- **Rotate the signing key** — invalidates every previously-issued cookie at once
  (`itsdangerous` verification fails for all of them), forcing every device, including
  the owner's own, to re-`/unlock`. This is the actual "I lost my phone" response.

### 4.4 `is_trusted_request(request)`

True iff the signed cookie is present and verifies (signature + not expired). No IP or
Host-based fallback — this app has no "local" concept at all (see §2). A `before_request`
hook on the `remote_web` Flask app applies this to every route except `/unlock`, `/health`
(§4.6 — deliberately unauthenticated so an uptime check doesn't need the token), and
static asset paths, returning `401` with a short friendly JSON message otherwise.

### 4.5 Brute-force lockout

A small in-memory failed-attempt counter on `POST /unlock` (e.g. 10 failures → 5 minute
lockout). Keyed on the **`CF-Connecting-IP`** header, not `request.remote_addr` — through
Cloudflare Tunnel, every request Flask sees originates from the local `cloudflared`
process, so `remote_addr` is always `127.0.0.1` regardless of the real client, making a
`remote_addr`-keyed counter useless (every attempt would share one bucket). Trusting
`CF-Connecting-IP` is safe specifically *because* of the loopback-only bind in §3 — the
header can't be spoofed by a direct attacker, since a direct attacker can't reach this
process at all, only `cloudflared` can, and `cloudflared` is the one setting that header
truthfully.

The token's own entropy already makes brute-forcing it computationally infeasible; this
lockout is cheap defense-in-depth against scanning noise, not the primary protection.

### 4.6 Health checks — public liveness vs. trusted detail (revised — addresses review feedback)

v2 put every diagnostic behind one unauthenticated `/health` route — including whether an
Instagram session is currently live. That's real reconnaissance value for anyone who
merely finds the tunnel's hostname (a public HTTPS URL is discoverable by internet-wide
scanners regardless of whether anyone was ever told it), even before Cloudflare Access
(§4.7) gets a chance to block them: it confirms "this is a live OmniFlow instance with an
active Instagram session" is worth attacking, before they've authenticated at all. Split
into two routes instead:

- **`GET /health`** — unauthenticated (exempt in §4.4, same as before), so an external
  uptime monitor can still ping it with no credentials. Returns only
  `{"status": "ok"}` if the process is up. No detail, nothing to learn from it beyond
  "something is listening."
- **`GET /api/health/detail`** — behind the normal trust gate (§4.4), same as every other
  `/api/*` route. Returns the full diagnostic payload from v2:
  - `ffmpeg`: whether `ffmpeg_locator.resolve_ffmpeg_binary()` (§5.1) found a binary that
    actually executes on this machine.
  - `instagram_cookies` / `threads_cookies`: whether `backend.cookies`/`backend.threads`'s
    existing candidate-discovery functions currently find a live, readable browser
    session — directly surfaces the Keychain-popup failure mode from §6.5 *before* the
    owner is away from the Mac and actually needs it, rather than discovering it mid-use.
    **Cached** for 5 minutes (`remote_web/config.py`-configurable) rather than
    re-checked on every hit — an automated monitor pinging this frequently shouldn't
    hammer Keychain access repeatedly, both for overhead and to avoid any risk of
    re-triggering a permission-prompt reset.
  - `temp_dir_disk_free_mb`: remaining space where job temp dirs/zips are staged — an
    early signal before the reaper (§5.4) can't keep up or the disk genuinely fills.

  No secrets (the token, the signing key, filesystem paths) appear in either response —
  status flags only, even behind the trust gate.

No secrets or paths leaked in the response — this is a status page, not a debug dump.

### 4.7 Cloudflare Access (elevated from "recommended" — see §10)

Cloudflare Access (Zero Trust free tier, up to 50 users) in front of the tunnel, gating
on the owner's own email via a one-time login code, blocks unauthorized traffic at
Cloudflare's edge before it ever reaches the Mac — entirely independent of the app-level
token. Not a hard code dependency (the app works standalone without it), but
`remote_web/README.md` states plainly: **without Access, the single shared token in §4.1
is the only thing standing between the internet and this Mac's own Instagram session and
download bandwidth** — treat enabling it as a required setup step in practice, not an
optional nice-to-have.

## 5. Request Flow

### 5.1 ffmpeg binary resolution (new — addresses review feedback)

`backend.paths.get_ffmpeg_path()` always looks for a file literally named `ffmpeg` at the
repo root — correct for the native app, where `OmniFlow.spec` already picked the
matching-architecture binary and staged it under that exact name at *build* time (see
`.claude/rules/packaging.md`). `remote_web` runs unfrozen (`python3 -m remote_web.app`,
no PyInstaller step), so nothing performs that selection — if the dedicated Mac isn't the
same architecture as whichever binary happens to be named `ffmpeg` at the repo root right
now (arm64, as of this session), every download would fail.

`remote_web/ffmpeg_locator.py` does its own resolution instead of calling
`paths.get_ffmpeg_path()`, entirely inside `remote_web/` (no `backend/` changes):

```
resolve_ffmpeg_binary():
    candidate = "<repo_root>/ffmpeg" if platform.machine() == "arm64" else "<repo_root>/ffmpeg-x86_64"
    verify it exists, is executable, and actually runs (`ffmpeg -version`) —
    mirrors backend.paths._ffmpeg_exec_error's approach (a wrong-architecture binary
    passes existence/+x checks but fails to exec)
    return the path, or None with a clear reason if it fails
```

**Verified, not assumed (review feedback flagged this specific risk):** confirmed both
binaries actually exist in the repo right now — `ffmpeg` (arm64, 440 KB) and
`ffmpeg-x86_64` (x86_64, 80 MB), both tracked in Git LFS
(`git lfs ls-files` → `e499399d32 * ffmpeg`, `872adac66b * ffmpeg-x86_64`), both already
pushed. If the dedicated Mac turns out to be Intel, the x86_64 binary this design depends
on is genuinely there, not a symmetry assumption.

The resolved path is passed explicitly into `backend.download.build_download_options`/
`download_one_video`/`ensure_h264` as their existing `ffmpeg_bin` parameter — all three
already take it as a plain argument, never hardcode a lookup internally (confirmed by
reading `backend/download.py` this session), so no shared code needs to change at all.
Checked at startup (fail loud in the process log if unresolvable) and surfaced via
`/api/health/detail` (§4.6) — never silently discovered only when a download fails.

### 5.2 Single item (video/photo/post)

1. Phone visits the tunnel URL → `frontend/dist` loads (unauthenticated; the shell itself
   isn't sensitive).
2. Frontend's existing `isLocal()` check correctly reports `false` (tunnel hostname isn't
   loopback) — Target Path/Cookies Settings sections stay hidden, exactly as today's
   remote-mode design already handles.
3. User pastes a link → `POST /api/check` → `before_request` trust gate passes (cookie
   present) → `remote_web/routes/media.py` calls `backend.classify.classify_url` +
   `backend.extraction.extract_video_info`/the Instagram/Threads/TikTok/LinkedIn resolver
   chain exactly as `backend/app.py` does today, *without* any Instagram/Threads
   rejection (no such check exists in this route — trust was already established
   globally).
4. `POST /api/download` → downloads into a fresh `tempfile.mkdtemp()` (always — this app
   has no "local save" mode at all), using the `ffmpeg_bin` from §5.1 → `GET
   /api/progress/<job_id>` polled as normal (reusing `backend.jobs.jobs`) → on
   completion, frontend links to `GET /api/download-file/<job_id>`, which streams the
   file and deletes the temp dir afterward — this mirrors `backend/app.py`'s existing
   remote-mode file delivery exactly, just always-on instead of conditional. If the
   client never fetches it (closed the tab), `reaper.py` (§5.4) cleans it up later
   instead of leaving it forever.

### 5.3 Playlist/channel/carousel (multi-item)

1. `POST /api/check` returns `type: "playlist"` exactly as today (shared `classify`/
   `extraction` logic, unmodified).
2. `POST /api/download-batch` → downloads selected items into one shared temp dir
   (reusing `backend.download.download_one_video`/`download_direct_url` and the
   `BATCH_CONCURRENCY`-parallel pattern `backend/app.py` already uses).
3. **Incremental zipping, not batch-at-the-end (revised — addresses review feedback on
   peak disk usage):** v2 assembled the `.zip` only after every item finished, meaning
   every raw file *and* the zip coexisted on disk at once — on a batch large enough,
   roughly double the batch's real size, on the machine least able to spare it. Instead,
   `zipper.py` keeps one `zipfile.ZipFile` open (mode `"a"`, **`ZIP_STORED`** — no
   compression; the contents are already-compressed video/image files, so `ZIP_DEFLATE`,
   the module's default, would just burn CPU on the older deployment Mac for no size
   reduction) for the duration of the batch job. As each item's download completes,
   `zipper.py` immediately `write()`s it into the archive and deletes the raw file. Peak
   disk usage is bounded by roughly `BATCH_CONCURRENCY` (3) in-flight raw files plus the
   zip's current size, not the whole batch's total size.
4. `GET /api/download-file/<job_id>` detects a batch job (checks whether the job produced
   a `.zip` vs. a single file) and streams whichever exists, deleting the temp dir
   afterward either way. The frontend needs no changes here — it already just links to
   this same route for a finished job; only the payload's `Content-Type`/filename differ.

### 5.4 Temp-dir/zip cleanup (revised — addresses review feedback)

Every job stages into its own temp dir; today's `backend/app.py` remote-mode code already
accepts an orphan risk here for the rare "closed the tab" case (documented as "a minor
gap" in `.claude/rules/web-app.md`) — acceptable there because it's a rare edge case atop
an otherwise-local, disk-rich deployment. `remote_web` runs on an older machine
continuously, so unfetched temp dirs accumulating over weeks is a real, not theoretical,
risk of filling the disk.

v2's reaper design consulted `backend.jobs.jobs` (in-memory) to decide which temp dirs
were stale — broken by construction: a `launchd` restart (§6 step 8, already a documented
trade-off) wipes that dict, so every temp dir created before the most recent restart has
no job record left to check against, and a job-dict-driven reaper would never even know
they exist. `remote_web/reaper.py` instead sweeps the temp-dir root directly on the
**filesystem**, independent of any in-memory state: a lightweight background thread
(started once at app startup, sleeping between sweeps — no external scheduler/cron
needed, and no job-dict dependency to go stale) deletes any subdirectory under the temp
root whose most-recently-modified file is older than a configurable window (default 30
minutes — enough time to actually tap "download" on a phone, short enough not to matter
for disk space). This correctly catches both a finished-but-unfetched job **and** any
directory orphaned by a mid-download restart, using one mechanism instead of two.
Surfaced indirectly via `/api/health/detail`'s `temp_dir_disk_free_mb`.

### 5.5 Cancellation

`POST /api/cancel/<job_id>` sets the same cooperative `cancelled` flag
`backend.jobs`/`backend.download` already check inside their download loops — reused
unmodified.

## 6. Deployment

On the dedicated (older) Mac, kept always-on and separate from the owner's main dev
machine:

1. Clone the repo (same as any dev checkout — `remote_web/` imports `backend/*` as a
   normal Python package, so a full checkout is simplest).
2. `python3 -m venv .venv && pip install -r requirements.txt` (covers `remote_web`'s
   needs too, since it only adds `backend/*`'s existing dependencies).
3. `cd frontend && npm install && npm run build` once — `remote_web` serves this same
   built output.
4. Generate the trust token + app secret key (one-time; documented command in
   `remote_web/README.md`).
5. Confirm `remote_web/ffmpeg_locator.py` resolves correctly on *this* Mac's actual
   architecture (`python3 -c "from remote_web.ffmpeg_locator import resolve_ffmpeg_binary; print(resolve_ffmpeg_binary())"`
   or equivalent) — verify before relying on it, not after a download silently fails.
6. Confirm this Mac has a live, logged-in Instagram/Threads browser session (same
   `browser_cookie3`-based auto-extraction the native app already uses), and manually
   trigger one Instagram check once to walk through any first-time Keychain permission
   prompt while someone is physically present to click "Always Allow" — a prompt that
   appears later with nobody watching just fails silently (see §6.5 below and
   `/api/health/detail` in §4.6).
7. Run `python3 -m remote_web.app` **from the repo root** — binds `127.0.0.1:5050` only.
   Must be run this way (not `python3 remote_web/app.py`): the `-m` form is what puts the
   repo root on `sys.path`, which is what makes `import backend` resolve at all; a plain
   script-path invocation would only put `remote_web/`'s own directory on the path.
8. Install as a `launchd` **agent** (`~/Library/LaunchAgents/com.omniflow.remoteweb.plist`,
   `RunAtLoad` + `KeepAlive`), **not** a LaunchDaemon — deliberately, see §6.4 for why a
   Daemon actively breaks Instagram/Threads. The plist's `WorkingDirectory` key **must**
   be set to the repo root (launchd does not go through a shell, so there's no CWD to
   inherit otherwise) and `ProgramArguments` must use the same `-m remote_web.app` form
   as step 7, for the same `sys.path` reason. **Known trade-off, documented not hidden:**
   a restart clears the in-memory `backend.jobs.jobs` dict and the brute-force lockout
   counter (§4.5) — any in-flight download's progress is lost and a lockout resets to
   zero. Acceptable for personal use; would need persistent storage (SQLite, a file) to
   survive restarts, which is out of scope for v1.
9. Install `cloudflared`, authenticate, create a named tunnel pointed at
   `127.0.0.1:5050`, then `cloudflared service install` for the same auto-start/restart
   behavior.
10. Configure Cloudflare Access on the tunnel's hostname, restricted to the owner's email
    — see §4.7 for why this is effectively required, not optional, despite being a
    separate product from the app itself.
11. Disable macOS sleep on this Mac (System Settings → Energy, or a `caffeinate` wrapper
    in the launchd plist) so the tunnel doesn't silently drop.
12. Enable **Automatic Login** for this account (System Settings → Users & Groups →
    Login Options) and confirm **FileVault is off** on this Mac. Both are required for
    the deployment to actually survive an unattended reboot — see §6.4 for why; skipping
    either one means a random forced restart (power blip, a macOS security update that
    demands a reboot) leaves the service down until someone physically visits the Mac,
    directly defeating the "always reachable" goal in §1.

### 6.4 Why Automatic Login + no FileVault are required, not optional (new — addresses review feedback)

A real conflict exists between two of this design's own requirements that v2 didn't
resolve: "survives an unattended reboot" and "can read the login Keychain for
Instagram/Threads cookies."

- **`LaunchAgent`** (§6 step 8) only starts once a GUI user session begins — after a
  reboot with nobody physically logging in, it simply never starts, `RunAtLoad`/
  `KeepAlive` notwithstanding. This is exactly the failure mode this whole project exists
  to avoid: discovering, from a phone far from home, that the service has been down since
  a reboot nobody was there for.
- **Switching to a `LaunchDaemon`** (`/Library/LaunchDaemons`, starts before any login,
  survives reboot unconditionally) looks like the fix, but isn't: a Daemon runs with no
  GUI session at all, and macOS's login Keychain is only unlocked as part of *that*
  specific user's interactive login — `browser_cookie3`'s Keychain decryption (the same
  mechanism `backend/cookies.py` already relies on for the native app) would fail for
  every Instagram/Threads request, unconditionally, the moment nothing has logged in
  since boot. A Daemon trades "survives reboot" for "Instagram/Threads permanently
  broken until someone logs in anyway" — no net improvement.
- **The actual fix:** keep the `LaunchAgent` (§6 step 8, unchanged), but enable
  **Automatic Login** for the dedicated account. macOS performs that login itself at
  boot, with no one present, which both unlocks the login Keychain (satisfying
  `browser_cookie3`) *and* starts the GUI session the `LaunchAgent` needs — one setting
  resolves both halves of the conflict using stock macOS behavior, no custom code.
- **The catch: FileVault.** If FileVault (whole-disk encryption) is enabled on this Mac,
  its own pre-boot passphrase prompt gates the *entire* boot process, before Automatic
  Login (or anything else) ever runs — no amount of login configuration works around it,
  since the disk itself can't be read until someone types the passphrase at a screen no
  one is looking at. FileVault and "survives an unattended reboot" are mutually
  exclusive on macOS, full stop. §1's "always reachable" goal requires FileVault to
  stay **off** on this specific dedicated Mac.
- **Accepted trade-off, stated plainly:** Automatic Login without FileVault means anyone
  with physical access to this Mac gets straight into the account, no password, and the
  disk is unencrypted at rest. For a dedicated machine whose only real secrets are an
  Instagram/Threads browser session and this deployment's own trust token/secret key
  (§4.2–§4.3, both revocable), this is a reasonable trade for the stated goal — but it's
  a real security posture change from "a normal Mac," worth the owner consciously
  accepting rather than discovering later. If physical security of the dedicated Mac's
  location can't be guaranteed, this whole "always reachable" goal may need revisiting
  rather than working around FileVault.

### 6.5 Ongoing maintenance note

Every macOS or browser (Chrome/Brave/Edge) update on the dedicated Mac can reset the
Keychain permission `browser_cookie3` relies on, re-triggering the one-time consent
prompt from step 6 — but with nobody physically present to click it, Instagram/Threads
extraction fails silently from that point on (still logged to `errors.log` via
`backend.paths.log_exception`, reused unmodified, but nobody's watching that file either
unless they think to look). `/api/health/detail` (§4.6) is the mitigation: check it after any update
to that Mac, or periodically, rather than only discovering the failure mid-use.

Full step-by-step commands go in `remote_web/README.md` during implementation, not
duplicated here.

## 7. Error Handling

Same friendly-message philosophy as the existing app (design-principles §3): every
route wraps extraction/download in `try/except`, no raw tracebacks or GitHub links reach
the client. `remote_web` reuses `backend.extraction.describe_extraction_error` for
message text — the exact same Vietnamese messages the native app already shows.
Additions specific to this deployment:

- Missing/invalid trust cookie → `401` with a short, clear message (not a stack trace).
- Zip assembly failure (disk full, a mid-batch cancellation) → the batch job reports
  `error` status with a specific message, same pattern `backend/app.py`'s existing batch
  failure handling uses.
- ffmpeg unresolvable (§5.1) → fails loud at startup (process log), also reflected in
  `/api/health/detail`, rather than surfacing only as a mysterious per-download failure.
- Tunnel/Cloudflare-level failures (Mac asleep, `cloudflared` crashed) are outside the
  app's control — the phone would simply see a connection failure. `remote_web/README.md`
  documents the launchd + sleep-prevention setup specifically to minimize this.

## 8. Testing

- `remote_web/tests/test_trust.py` — cookie signing/verification (including `max-age`
  expiry and `SameSite`/`Secure`/`HttpOnly` flags), the `before_request` gate rejecting
  untrusted requests and allowing trusted ones, `CF-Connecting-IP`-keyed brute-force
  lockout, signing-key rotation invalidating existing cookies.
- `remote_web/tests/test_media_routes.py` — mirrors `tests/test_api.py`'s existing
  conventions (mocking `backend.extraction.extract_video_info`,
  `backend.download.download_one_video`, etc.) to verify `/api/check`/`/api/download`
  work for a representative platform and that Instagram/Threads are **not** rejected
  (the one behavior that must differ from `backend/app.py`).
- `remote_web/tests/test_zipper.py` — items appended incrementally end up correctly
  archived with filenames preserved, uses `ZIP_STORED` (assert on the resulting
  archive's compression type, not just that a zip exists), each source file is deleted
  immediately after being added (not just at the end), handles an empty/failed-item edge
  case.
- `remote_web/tests/test_reaper.py` — a temp dir whose newest file is older than the
  configured window gets deleted; one with a recent modification time does not; a
  simulated "orphaned by restart" dir (no corresponding entry in `backend.jobs.jobs` at
  all) is still correctly swept, proving the mtime-only design doesn't depend on job
  state surviving a restart.
- `remote_web/tests/test_ffmpeg_locator.py` — picks `ffmpeg` vs `ffmpeg-x86_64` correctly
  per `platform.machine()`, mirrors `tests/test_paths.py`'s existing pattern for
  simulating a wrong-architecture exec failure.
- Manual live checklist (recorded in `remote_web/README.md`, not automated): access via
  a real Cloudflare Tunnel URL from an actual phone; confirm an unlocked device can
  check+download a single item and a playlist; confirm a browser without the trust
  cookie is rejected; confirm Instagram/Threads work end-to-end; check
  `/api/health/detail` reports everything green.
- `pytest` for the existing suite (`tests/`) must stay green and untouched by this work
  — a fast, mechanical check that nothing in `backend/` was accidentally modified.

## 9. Resolved Open Questions

1. **Folder name** — owner confirmed `remote-web/` (hyphen) as fine in v1. Self-review
   caught a real problem with that spelling, not a style objection: Python cannot import
   a hyphenated path at all (`from remote-web.config import ...` is a syntax error), and
   several pieces of this design need it importable as a real package (`/unlock`'s
   token-rotation CLI, `ffmpeg_locator.py`'s verification command, tests importing from
   it). Corrected to **`remote_web/`** (underscore) throughout this revision — same
   name, same purpose, just the one spelling Python can actually load.
2. **Zip vs. one-file-at-a-time for batches** — confirmed: single `.zip` per completed
   batch job, using `ZIP_STORED` per §5.3.
3. **Cloudflare Access** — confirmed optional at the code level, but elevated to
   "documented as effectively required" in the README per §4.7 — the app-level token is
   the *only* protection without it.

## 10. Changelog (v1 → v2, after owner review)

Owner review surfaced three critical gaps and several should-fix/minor issues, all
addressed above:

- **Critical:** token-in-URL exposure → replaced `GET /unlock?token=` with a POST-only
  form + global `Referrer-Policy: no-referrer` (§4.1).
- **Critical:** unverified ffmpeg path resolution in unfrozen/dev-mode execution on a
  possibly-different-architecture Mac → verified `ffmpeg_bin` is a plain parameter
  throughout `backend/download.py` (not hardcoded), designed `ffmpeg_locator.py` to
  resolve and pass it explicitly, entirely inside `remote_web/` (§5.1).
- **Critical:** silent Keychain-consent failure on an unattended machine → documented as
  an operational risk (originally §6.3, now §6.5 after v3's renumbering) and given a
  concrete mitigation (`/health`'s cookie-status fields, §4.6).
- **Should-fix:** orphaned temp dirs/zips (§5.4, new `reaper.py`), documented in-memory
  state loss on restart (§6 step 8), trust cookie expiry + revocation (§4.2, §4.3),
  explicit `SameSite=Lax` (§4.2), `ZIP_STORED` instead of default DEFLATE (§5.3).
- **Minor:** brute-force lockout keyed on `CF-Connecting-IP` instead of useless
  `remote_addr` through the tunnel (§4.5), added `/health` endpoint (§4.6).
- **Self-caught during this revision (not from owner feedback):** the previously-approved
  folder name `remote-web/` can't actually be imported as a Python package (hyphens are
  invalid in dotted module paths) — renamed to `remote_web/` throughout, see §9.1.

## 11. Changelog (v2 → v3, second owner review round)

- **Critical:** `LaunchAgent` vs. login-Keychain vs. surviving an unattended reboot were
  three requirements in tension that v2 never actually reconciled → root-caused in new
  §6.4: a `LaunchAgent` doesn't start without a GUI login, a `LaunchDaemon` starts but
  can't reach the login Keychain at all: neither alone satisfies both "always reachable"
  and "Instagram/Threads work." Resolved by keeping the `LaunchAgent` and requiring
  Automatic Login (§6 step 12) — plus the FileVault caveat that follows from it (FileVault
  gates the whole boot behind an unattended pre-boot prompt no login setting can bypass),
  stated as an explicit, accepted security trade-off rather than left implicit.
- **Critical:** `ffmpeg-x86_64`'s existence was asserted, not confirmed → actually checked
  the repo and Git LFS state before writing this revision; both binaries are real (§5.1).
- **Should-fix:** reaper redesigned from job-dict-driven (silently blind to anything
  orphaned by a `launchd` restart, since that wipes the dict it was consulting) to a plain
  filesystem `mtime` sweep of the temp-dir root — one mechanism that can't go stale (§5.4).
- **Should-fix:** `/health` split into a public, contentless liveness check and a
  trust-gated `/api/health/detail` carrying the actual diagnostic payload — the previous
  single unauthenticated route leaked "this instance has a live Instagram session" to
  anyone who found the URL, before any auth layer even applied (§4.6).
- **Should-fix:** batch zipping changed from all-items-then-zip to incremental
  write-then-delete-source per item, capping peak disk usage near `BATCH_CONCURRENCY`
  in-flight files instead of the whole batch's total size (§5.3).
- **Minor:** the cookie-liveness check inside `/api/health/detail` is now cached (5
  minutes) instead of re-querying Keychain on every hit (§4.6).
