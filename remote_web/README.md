# remote_web — Personal Remote Access for OmniFlow

Serves OmniFlow's check/download flow (including Instagram/Threads and
playlist/carousel batch downloads) over a personal, token-gated public URL,
so it's reachable from a phone anywhere with internet — no native macOS app
install required on that device.

**Design spec:** [docs/superpowers/specs/2026-08-29-remote-web-access-design.md](../docs/superpowers/specs/2026-08-29-remote-web-access-design.md)

This is a *separate deployment* from the native `.app` — it does not touch
`backend/`, `server.py`, `desktop_app.py`, or `OmniFlow.spec` at all, and is
meant to run continuously on a dedicated, always-on Mac (an older machine,
**not** the same Mac used for day-to-day development), reachable through a
free Cloudflare Tunnel rather than a paid cloud VPS — running it from a
residential IP matters for platforms (TikTok especially) that are more
likely to rate-limit or block a cloud-provider IP range.

## One-time setup, on the dedicated Mac

1. Clone the repo (a full checkout — `remote_web/` imports `backend/*` as a
   normal Python package):
   ```bash
   git clone https://github.com/<owner>/OmniFlow.git
   cd OmniFlow
   ```
2. Set up the Python environment (same as the root project):
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Build the frontend once — `remote_web` serves this same built output, no
   separate frontend build of its own:
   ```bash
   cd frontend && npm install && npm run build && cd ..
   ```
4. Generate the trust token + app secret key (one-time; auto-generated on
   first access, but running this now lets you read the token before going
   anywhere near a phone):
   ```bash
   python3 -m remote_web.config show
   ```
   Write the printed token down somewhere safe (a password manager) — this
   is the one credential every device needs to type into the `/unlock` form.
5. Confirm ffmpeg resolves correctly for *this* Mac's actual CPU
   architecture before relying on it:
   ```bash
   python3 -c "from remote_web.ffmpeg_locator import resolve_ffmpeg_binary; print(resolve_ffmpeg_binary())"
   ```
   This must print a real path, not `None`. If it prints `None`, re-check
   that both `./ffmpeg` (arm64) and `./ffmpeg-x86_64` (Intel) are present at
   the repo root and executable — see
   `.claude/rules/packaging.md`'s "Two-architecture ffmpeg" section.
6. Confirm this Mac has a live, logged-in Instagram/Threads session in an
   installed browser (Chrome/Brave/Edge/Vivaldi/Opera — **not** Safari, see
   `docs/TROUBLESHOOTING.md`). With someone physically present, run the app
   once (step 7) and trigger one Instagram check from a browser — the first
   real Instagram/Threads request on this machine triggers a one-time macOS
   Keychain permission prompt ("... wants to use your confidential
   information stored in 'Chrome Safe Storage'"); click **Always Allow**.
   Nobody will be present to click this later, so it must happen now.
7. Run it from the repo root:
   ```bash
   python3 -m remote_web.app
   ```
   Must be run this way — **not** `python3 remote_web/app.py` — the `-m`
   form is what puts the repo root on `sys.path`, which is what makes
   `import backend` resolve at all. This binds `127.0.0.1:5050` only.
8. Install as a `launchd` **agent** (not a Daemon — see "Why a LaunchAgent,
   not a LaunchDaemon" below):

   Create `~/Library/LaunchAgents/com.omniflow.remoteweb.plist`:
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
     "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
     <key>Label</key><string>com.omniflow.remoteweb</string>
     <key>ProgramArguments</key>
     <array>
       <string>/path/to/OmniFlow/.venv/bin/python3</string>
       <string>-m</string>
       <string>remote_web.app</string>
     </array>
     <key>WorkingDirectory</key><string>/path/to/OmniFlow</string>
     <key>RunAtLoad</key><true/>
     <key>KeepAlive</key><true/>
   </dict>
   </plist>
   ```
   Replace `/path/to/OmniFlow` with the real absolute path on this Mac in
   **both** places (`ProgramArguments` and `WorkingDirectory`) — `launchd`
   does not go through a shell, so there is no working directory to inherit
   otherwise, and the `-m remote_web.app` form matters here for the exact
   same `sys.path` reason as step 7.

   Load it:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.omniflow.remoteweb.plist
   ```

   **Known trade-off:** a restart clears the in-memory job registry and the
   brute-force lockout counter — any in-flight download's progress is lost
   and a lockout resets to zero. Acceptable for personal use.

9. Install [`cloudflared`](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/),
   authenticate, create a named tunnel pointed at `127.0.0.1:5050`, then:
   ```bash
   cloudflared service install
   ```
   for the same auto-start/restart behavior as the launchd agent above.

10. Configure **Cloudflare Access** (Zero Trust free tier, up to 50 users)
    on the tunnel's hostname, restricted to your own email via a one-time
    login code. **Treat this as a required step, not optional** — without
    it, the app-level token from step 4 is the *only* thing standing
    between the internet and this Mac's own Instagram session and download
    bandwidth.
11. Disable macOS sleep on this Mac (System Settings → Energy Saver, or wrap
    the launchd command in `caffeinate`) so the tunnel doesn't silently drop.
12. Enable **Automatic Login** for this account (System Settings → Users &
    Groups → Login Options) and confirm **FileVault is off**. Both are
    required for this to survive an unattended reboot — see below.

### Why a LaunchAgent, not a LaunchDaemon

A `LaunchAgent` only starts once a GUI session begins; after a reboot with
nobody physically logging in, it never starts at all. Switching to a
`LaunchDaemon` (which starts before any login) looks like the fix, but
isn't: a Daemon has no GUI session, and macOS's login Keychain — which
`browser_cookie3` needs to decrypt Instagram/Threads cookies — is only
unlocked as part of an interactive login. A Daemon trades "survives reboot"
for "Instagram/Threads permanently broken until someone logs in anyway."

**The actual fix:** keep the LaunchAgent, and enable **Automatic Login**
(step 12). macOS performs that login itself at boot with no one present,
which both unlocks the Keychain *and* starts the GUI session the LaunchAgent
needs.

**The catch:** if FileVault is enabled, its own pre-boot passphrase prompt
gates the entire boot process before Automatic Login (or anything else) can
run — no login configuration works around it. FileVault and "survives an
unattended reboot" are mutually exclusive on macOS. This means **Automatic
Login without FileVault means anyone with physical access to this Mac gets
straight into the account, no password, and the disk is unencrypted at
rest.** For a dedicated machine whose only real secrets are a browser
session and this deployment's own token/key (both revocable — see below),
this is a reasonable trade for "always reachable from a phone" — but it is a
real security posture change from "a normal Mac," and depends on the
dedicated Mac's physical location being reasonably secure.

### Ongoing maintenance

Any macOS or browser (Chrome/Brave/Edge) update on this Mac can reset the
Keychain permission `browser_cookie3` relies on, re-triggering the one-time
consent prompt from step 6 — but with nobody physically present to click it,
Instagram/Threads extraction then fails silently (still logged to
`.logs/errors.log` via the same mechanism the native app uses, but nobody is
watching that file unless they think to look). Check
`GET /api/health/detail` (while unlocked) after any update to this Mac, or
periodically, rather than only discovering the failure mid-use away from
home.

## Free-tier cloud deployment (Linux) — the primary deployment

Everything above describes running `remote_web` on a dedicated Mac. The same
package also runs, unchanged, on a free Linux cloud VM — so nothing needs a
Mac powered on at all. This is the deployment actually in use
(`cloud.southframevn.com`, on a GCP `e2-micro`, 2026-09-10); the Mac
instructions above are kept for reference.

### What works on a cloud IP, and what doesn't

A datacenter IP changes the auth story for three platforms:

| Platform | On a cloud IP |
|---|---|
| TikTok, Facebook, X, RedNote, LinkedIn | Work with nothing configured. |
| **YouTube** | Refuses outright — `playability status: LOGIN_REQUIRED` (not merely a "confirm you're not a bot" challenge). A [bgutil POT provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) is installed (step 6) and clears the *bot-check* layer, but **cannot** clear `LOGIN_REQUIRED` — that needs a real logged-in session. |
| **Instagram / Threads** | Need a `sessionid` — there is no anonymous path at all. |

So YouTube / Instagram / Threads on the cloud VM require a login session,
and the only free way to get one onto a datacenter box is to **push it up
from a Mac** that's logged into those sites in a browser
(`remote_web/scripts/sync_cloud_cookies.py`, step 7). The Mac only has to be
awake briefly for each sync — it is not a parallel deployment, just a
cookie source.

### Setup

The VM has ~1 GB RAM, so two things differ from the Mac path: add swap
before installing anything, and **build `frontend/dist` on your dev machine
and copy it up** rather than running `npm` on the VM (a Vite build OOMs
there).

1. Create a [Google Cloud](https://cloud.google.com/free) account (card
   required for verification; Always Free is genuinely free forever and not
   the same thing as the 90-day $300 trial). Provision **one `e2-micro`**
   instance — it is only free in `us-west1`, `us-central1`, or `us-east1` —
   running **Ubuntu 24.04 LTS**, **30 GB Standard persistent disk**, an
   ephemeral external IP (free on a free-tier VM), and your SSH public key
   in the instance metadata. No inbound firewall rule is needed beyond SSH:
   the Cloudflare tunnel dials outbound.
   (Oracle Cloud's Always Free Ampere shape was the original plan — it has
   far more RAM — but Oracle flagged/locked the free account during setup.
   GCP has been steadier for this.)
2. On the VM: add a swapfile, then the system packages —
   ```bash
   sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
   sudo mkswap /swapfile && sudo swapon /swapfile
   echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
   sudo apt-get update
   sudo apt-get install -y python3-venv python3-pip ffmpeg rsync unzip
   ```
   `ffmpeg` from `apt` is the whole reason this deployment needs none of the
   macOS vendored-binary machinery — `ffmpeg_locator.py`'s Linux branch just
   uses `shutil.which("ffmpeg")`.
3. From your dev machine, build the frontend and copy the app up (no `.git`,
   no `node_modules`, no venv, no macOS ffmpeg binaries):
   ```bash
   cd frontend && npm ci && npm run build && cd ..
   rsync -az --exclude=__pycache__ --exclude='*.pyc' --exclude=tests \
     backend remote_web requirements.txt  <user>@<vm>:~/omniflow/
   rsync -az frontend/dist  <user>@<vm>:~/omniflow/frontend/
   ```
4. On the VM: `python3 -m venv ~/omniflow/.venv && ~/omniflow/.venv/bin/pip
   install -r ~/omniflow/requirements.txt`. Then confirm ffmpeg resolves:
   `~/omniflow/.venv/bin/python3 -c "from remote_web.ffmpeg_locator import
   resolve_ffmpeg_binary as r; print(r())"` (must print a path).
5. Install `cloudflared` (Cloudflare's `linux-amd64.deb`), copy your
   existing `~/.cloudflared/cert.pem` up from any machine already logged
   into the Cloudflare account, then
   `cloudflared tunnel create omniflow-gcp`,
   `cloudflared tunnel route dns omniflow-gcp cloud.<yourdomain>`, and write
   `~/.cloudflared/config.yml` pointing the hostname at
   `http://127.0.0.1:5050`.
6. **YouTube bot-check layer** — install [`deno`](https://deno.land) (a
   `yt-dlp` JS-runtime requirement) to `/usr/local/bin`, then the bgutil POT
   provider: `git clone --branch 2.0.0
   https://github.com/Brainicism/bgutil-ytdlp-pot-provider`, `cd server &&
   npm ci && npx tsc` (needs Node 20 via NodeSource), run
   `node build/main.js` as a systemd service (listens on `127.0.0.1:4416`),
   and `~/omniflow/.venv/bin/pip install bgutil-ytdlp-pot-provider` for the
   `yt-dlp` plugin (auto-detects the server). This alone does **not** make
   YouTube work from the VM (see the table above) — it's the floor, not the
   fix.
7. **The actual YouTube/Instagram/Threads fix** — on a Mac logged into those
   sites, run `bash remote_web/scripts/install-cloud-cookie-sync.sh`. It
   reads the browser sessions (`browser_cookie3`, one Keychain
   "Always Allow" prompt on first run), `scp`s a combined `cookies.txt` to
   the VM's `remote_web/.manual_cookies.txt`, and installs a LaunchAgent
   that repeats every 6 hours while the Mac is awake. On the VM, point the
   backend at that file once:
   `~/omniflow/.venv/bin/python3 -c "from backend import config as c;
   s=c.load_session(); c.save_session(s['path'],
   '/home/<user>/omniflow/remote_web/.manual_cookies.txt', s['browser'],
   s['playlist_limit'])"`.
8. **Three `systemd` units**, all `Restart=on-failure`,
   `WantedBy=multi-user.target` (no login-session caveat — a headless Linux
   VM has no Keychain in play): `omniflow-remote` (`python3 -m
   remote_web.app` from `~/omniflow`), `omniflow-tunnel`
   (`cloudflared tunnel --config … run`), and `bgutil-pot`
   (`node …/build/main.js`).
9. `~/omniflow/.venv/bin/python3 -m remote_web.config show` for this
   deployment's token, then visit `https://cloud.<yourdomain>/unlock`.
   Settings still shows a manual cookies-upload box (works as a one-off if
   you have no Mac to run the sync from), but with the sync installed you
   never touch it.

### Cost

$0 within Always Free: one `e2-micro`, 30 GB Standard PD, one of the three
free regions, ephemeral external IP. The one place a small charge can leak
is **network egress** — 1 GB/month free, then ~$0.12/GB — and every
downloaded video is egress (VM → Cloudflare → you). Light personal use
stays at or near $0; set a $1 budget alert to be sure. After the 90-day
trial ends, "Activate full account" in Billing keeps the VM running (still
$0 in Always Free).

## Revoking access

Two different operations:

- **Rotate the token** — stops any *new* `/unlock` attempt with the old
  token. Existing already-unlocked devices are unaffected.
  ```bash
  python3 -m remote_web.config rotate-token
  ```
- **Rotate the secret key** — the actual "I lost my phone" response.
  Invalidates *every* previously-issued cookie at once, forcing every
  device (including your own) to `/unlock` again.
  ```bash
  python3 -m remote_web.config rotate-key
  ```

## Manual live checklist (not automated)

Run through this once after first deploying, and again after any
significant change:

- [ ] Visit the tunnel URL from an actual phone browser — the `/unlock` form
      renders.
- [ ] Enter the token — redirected to the app, trust cookie set.
- [ ] A browser with no trust cookie hitting any `/api/*` path gets a
      friendly 401, not a crash or a raw error page.
- [ ] Check + download a single video (any supported platform).
- [ ] Check + download a playlist/channel or Instagram carousel — confirm
      the browser receives one `.zip` containing every selected item.
- [ ] Check + download an Instagram post and a Threads post — confirm both
      work without any "local only" rejection.
- [ ] `GET /api/health/detail` (while unlocked) reports `ffmpeg: true`,
      `instagram_cookies: true`, `threads_cookies: true`.
- [ ] `GET /health` (no cookie needed) returns `{"status": "ok"}`.
- [ ] (Cloud deployment only) `GET /api/health/detail` on the cloud hostname
      reports `ffmpeg: true` (resolved via `apt`-installed ffmpeg, not a
      vendored binary).
- [ ] (Cloud deployment only) A TikTok check/download succeeds with nothing
      configured (proves the no-auth platforms are unaffected on a cloud IP).
- [ ] (Cloud deployment only) `bgutil-pot.service` is active and
      `curl 127.0.0.1:4416/ping` responds.
- [ ] (Cloud deployment only) After `sync_cloud_cookies.py` has run from a
      logged-in Mac, a YouTube **and** an Instagram check/download both
      succeed on the cloud hostname.
- [ ] (Cloud deployment only) `~/Library/Logs/OmniFlowCloudCookies/err.log`
      on the Mac shows the 6-hourly sync completing, not a Keychain denial.

## Testing

```bash
pytest remote_web/tests/ -v          # this package's own tests
pytest                                 # confirms the native app's suite is
                                        # still 100% green and untouched
```
