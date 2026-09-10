# Remote Web — Cloud (Linux) Portability — Design Spec

**Date:** 2026-08-30 · **Deployed:** 2026-09-10 (see §5–6 for where reality diverged)
**Status:** Implemented. Code changes (§2) as designed; provider is GCP not Oracle (§5),
and a cloud IP turned out to block YouTube/Instagram/Threads, fixed by a Mac→VM cookie
sync (§6).

## 1. Problem & Goals

`remote_web/` (design: `docs/superpowers/specs/2026-08-29-remote-web-access-design.md`) currently
only runs on macOS: `ffmpeg_locator.py` resolves one of two vendored macOS binaries
(`./ffmpeg` arm64 / `./ffmpeg-x86_64` Intel), and Instagram/Threads auth relies on
`browser_cookie3` reading the macOS login Keychain + a real logged-in browser — neither
exists on a headless Linux VPS.

The owner wants `remote_web` to also run on a genuinely free-forever cloud VM (Oracle
Cloud "Always Free"), reachable 24/7 **independent of any Mac being powered on**, while
the existing Mac-hosted deployment (`download-media.southframevn.com`, set up
2026-08-30) keeps running unchanged in parallel as a secondary option.

**Goals:**
- The exact same `remote_web/` codebase runs correctly on both macOS and Linux, with no
  behavioral change on macOS.
- ffmpeg resolution works on Linux via a system-installed binary (no vendoring needed —
  Linux has no PyInstaller-style distribution constraint here, since `remote_web` runs
  from source on the VPS, not as a frozen bundle).
- Instagram/Threads work on the cloud deployment via a **manually uploaded** `cookies.txt`
  (no browser/Keychain available on a headless VPS) — a genuinely new capability, since
  today's `remote_web/routes/settings.py` explicitly has "no manual Instagram cookies UI"
  by design (the native app's own manual-cookies Settings field was removed years ago; see
  `.claude/rules/web-app.md`'s Instagram resolver section).
- A second, independent hostname (`cloud.southframevn.com`) points at the cloud
  deployment via its own Cloudflare Tunnel — the Mac's `download-media.southframevn.com`
  is untouched.

**Non-goals (v1, explicitly accepted by the owner):**
- No residential-proxy or IP-reputation mitigation for TikTok on the cloud IP — the owner
  accepted this risk directly (cloud IPs are more likely to be rate-limited/blocked by
  TikTok than the Mac's residential IP, per `.claude/rules/web-app.md`'s existing
  dual-mode notes and this session's own live TikTok investigation).
- No Docker/containerization — direct install (venv + systemd), matching the owner's
  stated preference for the simpler of the two options presented.
- No automatic Instagram/Threads cookie refresh — a manually uploaded `cookies.txt` will
  go stale exactly like any exported cookies file does (typically weeks), same
  expectation as manually-exported cookies already documented for the native app.

## 2. Architecture

Two small, targeted code changes inside `remote_web/` (zero changes to `backend/`,
matching every prior addition to this package) plus an operational deployment guide.
Both changes are pure additions/generalizations — nothing macOS-specific is removed, so
the existing Mac deployment's behavior is provably unaffected (covered by keeping every
existing test green and adding new Linux-path tests alongside them, not replacing them).

### 2.1 `ffmpeg_locator.py` — OS-aware resolution

Today, `resolve_ffmpeg_binary()` unconditionally looks for a vendored macOS binary
(`./ffmpeg` or `./ffmpeg-x86_64` at the repo root, matching `platform.machine()`). This
function gains a first branch on `platform.system()`:

- **`"Darwin"` (macOS):** unchanged — exactly today's vendored-binary logic, byte-for-byte.
- **`"Linux"`:** resolve via `shutil.which("ffmpeg")` instead — Linux has no PyInstaller
  distribution step for `remote_web` (it always runs from a source checkout via
  `python3 -m remote_web.app`, never frozen), so there is nothing to vendor: a plain
  `apt install ffmpeg` on the VPS puts a working, already-linked ffmpeg on `PATH`, and
  that's the correct, idiomatic way to depend on it on Linux. If `which` finds nothing,
  return `None` exactly like the macOS path does when its vendored binary is missing —
  the existing `_check_ffmpeg_at_startup()` fail-loud logging and `/api/health/detail`
  reporting in `remote_web/app.py`/`routes/health.py` need no changes at all, since they
  already just check "did `resolve_ffmpeg_binary()` return a path."
- **Anything else** (e.g. Windows, not a supported target): return `None` — explicit,
  not silently falling through to either branch.

`ffmpeg_unavailable_message()` gains the equivalent branch: the Linux message says to
install ffmpeg via the system package manager (`apt install ffmpeg` / `dnf install
ffmpeg`, phrased generically) instead of naming a repo-root vendored-binary path that
doesn't apply on Linux at all.

### 2.2 Manual cookies.txt upload (new capability)

**Why this belongs in `remote_web/routes/settings.py`, not a new file:** it's the same
"remote_web's own settings" concern the file already owns (language, playlist_limit) —
just a new field.

**Storage:** the uploaded file is saved to a new, non-tmp location
`remote_web/.manual_cookies.txt` (gitignored, alongside `.state.json`/`settings.json` —
this task adds it to `.gitignore`) — deliberately **not** under `config.TEMP_ROOT`, so
`reaper.py`'s mtime-based sweep (spec §5.4 of the original design) never treats it as an
orphaned job directory and deletes it.

**Wiring:** once saved, the route calls `backend_config.save_session(...)` (existing,
unmodified — the exact function the native app's own settings route already calls) with
`cookies_path` set to the saved file's absolute path. This is the **same** mechanism
`backend.config.get_cookies_path()`/`cookies_status_for()` already expose and that
`remote_web/routes/media.py` already calls unmodified for every Instagram/Threads
resolution — no change needed there at all. The cloud VPS's own `backend/config.py`
`CONFIG_FILE` (a local `config.json` next to that checkout, per existing, unmodified
`backend/config.py` logic) is entirely separate from the Mac's — uploading cookies on
the cloud deployment can never affect the Mac deployment's own settings, and vice versa.

**New route:** `POST /api/settings/cookies` — `multipart/form-data`, one file field
(`cookies`). Validates:
- File is present and non-empty.
- Size capped at 64 KiB (a real Netscape-format cookies.txt is a few KB at most; this
  bounds the request body without needing a library, and rejects an obviously-wrong
  upload before it's ever written to disk).
- Written to `remote_web/.manual_cookies.txt` (`0600` permissions, same care as
  `config.STATE_FILE` — this file carries live session credentials).

Response mirrors `cookies_status_for()`'s existing three-state shape (`"valid"` /
`"no_session"` / `"none"`) so the frontend can show the exact same status language the
native app's (currently-removed) manual-cookies field used to.

**Frontend:** `SettingsPage.tsx`'s Instagram/Cookies section is currently gated
`isLocal()`-only (hidden entirely in remote mode, since the native app's own manual
upload UI was removed and Instagram there instead auto-extracts from the local browser).
Add a **new**, separately-gated section — shown only when `!isLocal()` — with a plain
`<input type="file">` + upload button posting to the new route, and a status line reusing
the existing cookies-status i18n strings. This is a genuinely new section, not un-hiding
the old local-only one (their content/purpose differ: local = browse-and-pick a path on
the server's own disk; remote = upload bytes from the visitor's own device).

## 3. Deployment (operational, not code)

Documented as a new section in `remote_web/README.md` ("Alternative: free-tier cloud
deployment (Linux)"), alongside the existing macOS LaunchAgent instructions — not
replacing them, since both deployments are meant to coexist:

1. Create an Oracle Cloud account, provision an "Always Free" Ampere A1 (ARM) or AMD
   Micro instance running Ubuntu.
2. `apt update && apt install -y python3-venv python3-pip nodejs npm ffmpeg` (ffmpeg
   here is the whole point of §2.1 — no vendoring/dylib-bundling step exists on Linux).
3. Clone the repo, `python3 -m venv .venv && pip install -r requirements.txt`,
   `cd frontend && npm install && npm run build`.
4. Install `cloudflared` for Linux (Cloudflare's official `.deb`/binary), authenticate
   against the **same** Cloudflare account already used for the Mac's tunnel (one
   account, multiple tunnels is normal), create a second named tunnel (e.g.
   `omniflow-remote-cloud`), route `cloud.southframevn.com` to it.
5. Two `systemd` unit files (the Linux equivalent of the Mac's two LaunchAgents):
   `remote-web.service` running `python3 -m remote_web.app` from the repo root, and
   `cloudflared.service` running the tunnel — both `Restart=on-failure`,
   `WantedBy=multi-user.target` so they survive a VPS reboot with no login-session
   caveat at all (unlike the Mac's LaunchAgent/Automatic-Login/FileVault trade-off in
   the original spec's §6.4 — a headless Linux VPS has no analogous GUI-session-vs-
   Keychain conflict, since there is no Keychain in play here: Instagram/Threads auth
   is the manually-uploaded cookies.txt from §2.2, not `browser_cookie3`).
6. One-time: visit `https://cloud.southframevn.com/unlock`, unlock with the same trust
   token workflow (a **separate** token from the Mac's — each deployment generates its
   own via `python3 -m remote_web.config show`, since they are two independent
   `remote_web` processes with two independent `.state.json` files), then visit Settings
   and upload a `cookies.txt` exported from a real Instagram/Threads session.

## 4. Testing

- `remote_web/tests/test_ffmpeg_locator.py`: new tests for the Linux branch (mock
  `platform.system() == "Linux"`, mock `shutil.which`), keeping every existing macOS
  test unchanged and still passing — proves the macOS path is untouched.
- `remote_web/tests/test_settings_routes.py`: new tests for
  `POST /api/settings/cookies` — accepts a well-formed upload and returns the right
  status, rejects an empty/oversized file, requires trust (401 unauthenticated),
  correctly wires through to `backend_config.save_session`.
- Manual live checklist (added to `remote_web/README.md`'s existing checklist, cloud
  section): the VPS resolves ffmpeg via `apt`, a YouTube check+download works end to end
  on the cloud URL, an Instagram/Threads check works after a real cookies.txt upload.

## 5. Resolved Open Questions

- **Docker vs. direct install:** direct install (owner's explicit choice, simpler).
- **Which free-tier cloud provider:** **GCP `e2-micro` Always Free** (as deployed
  2026-09-10). Oracle Cloud Always Free was the original plan — its Ampere shape has far
  more RAM — but Oracle flagged/locked the free account partway through setup, and the
  owner chose not to fight it. GCP's `e2-micro` is genuinely always-free forever (a
  separate thing from the 90-day $300 trial; §5's original "12-month trial like GCP" note
  was wrong — that's a different GCP offer), an ephemeral external IP is free on a
  free-tier VM, and it must sit in `us-west1`/`us-central1`/`us-east1`. Its ~1 GB RAM
  means: add a 2 GB swapfile before `pip install`, and build `frontend/dist` off-box
  (a Vite build OOMs on the VM).
- **Domain:** a new, separate hostname (`cloud.southframevn.com`).
- **TikTok IP-reputation risk on a cloud IP:** accepted by the owner — and in practice
  TikTok worked fine from the GCP IP (both yt-dlp direct and the tikwm.com fallback).
  The IP problem landed on YouTube instead (see §6).

## 6. Delivered reality: the cloud-IP auth wall (2026-09-10)

Discovered during deployment, not anticipated by §1–5:

- **YouTube refuses a datacenter IP outright.** Not the "Sign in to confirm you're not a
  bot" challenge that a PO token clears — the player response comes back with
  `playability status: LOGIN_REQUIRED`. A [bgutil POT
  provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) (v2.0.0 HTTP server
  on `127.0.0.1:4416` as a third `systemd` unit, plus the `bgutil-ytdlp-pot-provider`
  pip plugin and a system `deno` install for yt-dlp's JS runtime) is deployed and clears
  the bot-check layer, but **cannot** clear `LOGIN_REQUIRED`.
- **Instagram / Threads** have no anonymous path at all (they need a `sessionid`), same
  as always.
- **The fix for all three:** a Mac logged into those sites pushes its browser session up
  to the VM. `remote_web/scripts/sync_cloud_cookies.py` reads YouTube/Google/Instagram/
  Threads cookies via `browser_cookie3` (sweeping every installed Chromium-family
  browser + profile, keeping the one with a real session per domain), writes one
  Netscape `cookies.txt`, and `scp`s it to the VM's `remote_web/.manual_cookies.txt`
  (the exact file §2.2's upload endpoint writes — so the wiring through
  `backend_config.save_session` is identical, just fed by scp instead of a multipart
  POST). `install-cloud-cookie-sync.sh` runs it once and installs a LaunchAgent
  (`com.omniflow.cloudcookies`, `StartInterval` 21600) to repeat every 6 h while the Mac
  is awake. The Mac is now a **cookie source, not a parallel deployment** — it does not
  run `remote_web` or a tunnel of its own.
- **What needs nothing:** TikTok, Facebook, X, RedNote, LinkedIn — all work on the cloud
  VM with no cookies and no POT provider.
- **Manual upload still exists** (§2.2's Settings box) as the fallback for anyone with no
  Mac to sync from; the sync script just automates feeding the same file.
- **`backend/cookies.py` on headless Linux:** `cookiefiles_from_browsers()` throws
  `KeyError('DBUS_SESSION_BUS_ADDRESS')` per call (no DBus session bus under systemd) and
  logs it to `.logs/errors.log`. Non-fatal — it's caught, returns zero sessions, and the
  code falls through to the manual/synced `cookies.txt`. Left as-is (`backend/` is
  out of scope for this package); the log noise is cosmetic and cached behind
  `HEALTH_CACHE_SECONDS` for the one caller that hits it unconditionally.
