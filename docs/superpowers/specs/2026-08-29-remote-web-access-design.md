# Remote Web Access — Design Spec

**Date:** 2026-08-29
**Status:** Draft, awaiting owner review

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

**Non-goals (v1):**
- Not a public/shareable tool — no accounts, no per-user rate limiting, no billing.
- Not a change to `backend/app.py`'s existing `is_local_request()` behavior or route
  bodies — those keep serving the native app exactly as today.
- Not deployed to a cloud VPS.
- No OAuth/account system — a single shared secret token is the whole auth model,
  optionally backed by Cloudflare Access as a second, edge-level layer.

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

New top-level folder: **`remote-web/`**. Nothing outside it changes.

```
remote-web/
├── app.py               # Flask app: creates the app, registers the global trust gate,
│                           mounts the route modules below, serves frontend/dist
├── trust.py              # is_trusted_request(), token verification, cookie signing,
│                           the /unlock route
├── routes/
│   ├── __init__.py
│   ├── media.py            # POST /api/check, /api/download, /api/download-batch
│   ├── jobs.py              # GET /api/progress/<id>, POST /api/cancel/<id>,
│   │                          GET /api/download-file/<id> (single file OR batch .zip)
│   └── settings.py          # GET/POST /api/settings (language only)
├── zipper.py               # Batch-job .zip assembly (stdlib zipfile, no new dependency)
├── config.py                # Trust token loading (env var or local-only file), remote
│                              server port, temp-dir root
├── requirements.txt          # Additions beyond the root requirements.txt, if any
│                              (expected: none new — itsdangerous ships with Flask already)
├── README.md                  # Setup: venv, first-run token generation, Cloudflare
│                                Tunnel + Access, launchd service
└── tests/
    ├── test_trust.py
    ├── test_media_routes.py
    └── test_zipper.py
```

**Reused, unmodified, via plain Python import:** `backend.classify`, `backend.extraction`,
`backend.download`, `backend.instagram`, `backend.threads`, `backend.linkedin`,
`backend.tiktok`, `backend.cookies`, `backend.config`, `backend.jobs`, `backend.paths`.
None of these modules reference `is_local_request()` or any local/remote concept — that
logic lives exclusively in `backend/app.py`'s route bodies, confirmed by inspection this
session. `remote-web/routes/jobs.py`'s progress/cancel routes read and write
`backend.jobs.jobs` the same way the native app's routes do; `jobs` is plain in-process
module state, not shared storage, so `remote-web` and the native app never actually
interact even if both happened to run at once on the same machine — each Python process
gets its own independent dict. Two Flask servers can't share port `5050` on one machine
regardless, so this only matters as a note that there's no hidden coupling to worry
about, not a real deployment constraint.

**Not reused, since it always applies:** `backend/app.py`'s local-only convenience routes
(`/api/browse`, `/api/browse-file`, `/api/open-folder`, `/api/open-logs`, `/api/clipboard`)
have no `remote-web` equivalent — the frontend already handles their absence gracefully
for a "remote" client (falls back to `navigator.clipboard.readText()`, hides the
Target-Path/Cookies Settings sections). `frontend/dist` itself is reused unmodified; no
frontend code changes at all.

**Port:** `remote-web` binds to `127.0.0.1:5050` (distinct from the native app's `:5001`,
avoiding any ambiguity even though the two are expected to run on separate machines).
Cloudflare Tunnel points at this port.

## 4. Trust Model

Single-tier, blanket gate — **every** `/api/*` route requires trust; there is no
per-platform distinction (unlike the native app's Instagram/Threads-only gate), since the
whole deployment is meant for exactly one person.

- **Setup (one-time, on the dedicated Mac):** generate a high-entropy token
  (`python3 -c "import secrets; print(secrets.token_urlsafe(32))"`), store it in a
  local-only file (`remote-web/.trust_token`, gitignored) or an environment variable read
  by `remote-web/config.py`. Never committed.
- **`GET /unlock?token=<secret>`** — if the token matches, sets a signed, `HttpOnly`,
  `Secure`, long-lived cookie (via `itsdangerous`, using a separately-generated app secret
  key, also local-only) and redirects to `/`. The owner visits this URL once from their
  phone (e.g. bookmarks it), never re-enters the token unless the cookie is cleared.
- **`is_trusted_request(request)`** — true iff the signed cookie is present and verifies.
  No IP/Host-based fallback (this app has no "local" concept — see §2).
- **Global gate:** a `before_request` hook on the `remote-web` Flask app rejects any
  `/api/*` request without a valid trust cookie (401, friendly JSON error). `/unlock` and
  static asset paths are exempt.
- **Brute-force mitigation:** a small in-memory failed-attempt counter per source IP on
  `/unlock` (e.g. 10 failures → 5 minute lockout) — cheap defense-in-depth; the token's
  entropy alone already makes guessing infeasible, this just blunts automated scanning
  noise in logs.
- **Defense in depth (recommended, not required):** Cloudflare Access (Zero Trust free
  tier, up to 50 users) in front of the tunnel, gating on the owner's own email via a
  one-time login code. This blocks unauthorized traffic at Cloudflare's edge before it
  ever reaches the Mac, independent of the app-level token. Documented as a recommended
  setup step in `remote-web/README.md`, not a hard code dependency — the app-level token
  works standalone if Access isn't configured.

## 5. Request Flow

**Single item (video/photo/post):**
1. Phone visits the tunnel URL → `frontend/dist` loads (unauthenticated; the shell itself
   isn't sensitive).
2. Frontend's existing `isLocal()` check correctly reports `false` (tunnel hostname isn't
   loopback) — Target Path/Cookies Settings sections stay hidden, exactly as today's
   remote-mode design already handles.
3. User pastes a link → `POST /api/check` → `before_request` trust gate passes (cookie
   present) → `remote-web/routes/media.py` calls `backend.classify.classify_url` +
   `backend.extraction.extract_video_info`/the Instagram/Threads/TikTok/LinkedIn resolver
   chain exactly as `backend/app.py` does today, *without* any Instagram/Threads
   rejection (no such check exists in this route — trust was already established
   globally).
4. `POST /api/download` → downloads into a fresh `tempfile.mkdtemp()` (always — this app
   has no "local save" mode at all) → `GET /api/progress/<job_id>` polled as normal
   (reusing `backend.jobs.jobs`) → on completion, frontend links to
   `GET /api/download-file/<job_id>`, which streams the file and deletes the temp dir
   afterward — this mirrors `backend/app.py`'s existing remote-mode file delivery
   exactly, just always-on instead of conditional.

**Playlist/channel/carousel (multi-item):**
1. `POST /api/check` returns `type: "playlist"` exactly as today (shared `classify`/
   `extraction` logic, unmodified).
2. `POST /api/download-batch` → downloads selected items into one shared temp dir
   (reusing `backend.download.download_one_video`/`download_direct_url` and the
   `BATCH_CONCURRENCY`-parallel pattern `backend/app.py` already uses) → once every item
   finishes (or the job is cancelled), `zipper.py` bundles the temp dir's files into a
   single `<job_id>.zip` using stdlib `zipfile` (no new dependency).
3. `GET /api/download-file/<job_id>` detects a batch job (checks whether the job produced
   a `.zip` vs. a single file) and streams whichever exists, deleting the temp dir
   afterward either way. The frontend needs no changes here — it already just links to
   this same route for a finished job; only the payload's `Content-Type`/filename differ.

**Cancellation:** `POST /api/cancel/<job_id>` sets the same cooperative `cancelled` flag
`backend.jobs`/`backend.download` already check inside their download loops — reused
unmodified.

## 6. Deployment

On the dedicated (older) Mac, kept always-on and separate from the owner's main dev
machine:

1. Clone the repo (same as any dev checkout — `remote-web/` imports `backend/*` as a
   normal Python package, so a full checkout is simplest).
2. `python3 -m venv .venv && pip install -r requirements.txt` (covers `remote-web`'s
   needs too, since it only adds `backend/*`'s existing dependencies).
3. `cd frontend && npm install && npm run build` once — `remote-web` serves this same
   built output.
4. Generate the trust token + app secret key (one-time; documented command in
   `remote-web/README.md`).
5. Confirm this Mac has a live, logged-in Instagram/Threads browser session (same
   `browser_cookie3`-based auto-extraction the native app already uses — no new
   mechanism, just needs to run on a Mac where that's true).
6. Run `python3 remote-web/app.py` — binds `127.0.0.1:5050`.
7. Install as a `launchd` agent (`~/Library/LaunchAgents/com.omniflow.remoteweb.plist`,
   `RunAtLoad` + `KeepAlive`) so it restarts on crash/reboot without a logged-in terminal
   session.
8. Install `cloudflared`, authenticate, create a named tunnel pointed at
   `127.0.0.1:5050`, then `cloudflared service install` for the same auto-start/restart
   behavior.
9. (Recommended) Configure Cloudflare Access on the tunnel's hostname, restricted to the
   owner's email.
10. Disable macOS sleep on this Mac (System Settings → Energy, or a `caffeinate` wrapper
    in the launchd plist) so the tunnel doesn't silently drop.

Full step-by-step commands go in `remote-web/README.md` during implementation, not
duplicated here.

## 7. Error Handling

Same friendly-message philosophy as the existing app (design-principles §3): every
route wraps extraction/download in `try/except`, no raw tracebacks or GitHub links reach
the client. `remote-web` reuses `backend.extraction.describe_extraction_error` for
message text — the exact same Vietnamese messages the native app already shows.
Additions specific to this deployment:

- Missing/invalid trust cookie → `401` with a short, clear message (not a stack trace).
- Zip assembly failure (disk full, a mid-batch cancellation) → the batch job reports
  `error` status with a specific message, same pattern `backend/app.py`'s existing batch
  failure handling uses.
- Tunnel/Cloudflare-level failures (Mac asleep, `cloudflared` crashed) are outside the
  app's control — the phone would simply see a connection failure. `remote-web/README.md`
  documents the launchd + sleep-prevention setup specifically to minimize this.

## 8. Testing

- `remote-web/tests/test_trust.py` — token verification, cookie signing/verification,
  the `before_request` gate rejecting untrusted requests and allowing trusted ones,
  brute-force lockout.
- `remote-web/tests/test_media_routes.py` — mirrors `tests/test_api.py`'s existing
  conventions (mocking `backend.extraction.extract_video_info`,
  `backend.download.download_one_video`, etc.) to verify `/api/check`/`/api/download`
  work for a representative platform and that Instagram/Threads are **not** rejected
  (the one behavior that must differ from `backend/app.py`).
- `remote-web/tests/test_zipper.py` — a batch job's temp dir zips correctly, preserves
  filenames, handles an empty/failed-item edge case.
- Manual live checklist (recorded in `remote-web/README.md`, not automated): access via
  a real Cloudflare Tunnel URL from an actual phone; confirm an unlocked device can
  check+download a single item and a playlist; confirm a browser without the trust
  cookie is rejected; confirm Instagram/Threads work end-to-end.
- `pytest` for the existing suite (`tests/`) must stay green and untouched by this work
  — a fast, mechanical check that nothing in `backend/` was accidentally modified.

## 9. Open Questions For Review

1. **Folder name** — going with `remote-web/`. Fine, or prefer something else?
2. **Zip vs. one-file-at-a-time for batches** — spec assumes a single `.zip` per
   completed batch job (simplest for a phone browser: one tap, one file). An
   alternative (stream files one at a time, reusing per-item `download-file`-style
   calls) was considered and rejected as worse mobile UX for no real benefit.
3. **Cloudflare Access** — recommended in the README as a setup step, not a hard
   dependency. Confirm that's the right call (vs. making it mandatory, which would block
   `remote-web` from starting without it).
