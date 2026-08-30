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

## Alternative: free-tier cloud deployment (Linux)

Everything above describes running `remote_web` on a dedicated Mac. The same
package also runs on a Linux VPS — useful if you'd rather not keep any Mac
powered on at all. This is a **separate, independent deployment**: it gets
its own hostname, its own trust token, and does not affect the Mac
deployment in any way if you're running both.

**Trade-off vs. the Mac deployment:** Instagram/Threads auth can't
auto-detect a browser session on a headless Linux box (no Keychain, no real
browser) — you upload a `cookies.txt` manually instead, via a new
Settings section that only appears when running in remote mode. Export one
from a browser where you're logged into Instagram/Threads (any cookie
export extension works), and upload it once after first unlocking the
cloud deployment; it'll need re-uploading whenever the session goes stale,
same as any exported cookies file eventually does.

1. Create an [Oracle Cloud](https://www.oracle.com/cloud/free/) account and
   provision an "Always Free" instance (an Ampere A1 / ARM shape, or an AMD
   Micro shape) running Ubuntu — this tier is free forever, not a
   time-limited trial. Note: sign-up requires a card for identity
   verification (you are not charged on the Always Free tier), and Oracle
   has been known to flag long-idle free accounts for review — check in on
   the instance occasionally.
2. `sudo apt update && sudo apt install -y python3-venv python3-pip nodejs npm ffmpeg`
   — `ffmpeg` here is the whole reason this deployment doesn't need any of
   the macOS vendored-binary machinery: a plain system package is enough.
3. Clone the repo, then the same setup as the Mac section above:
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   cd frontend && npm install && npm run build && cd ..
   ```
4. Install `cloudflared` for Linux (Cloudflare's `.deb` package or binary
   release), `cloudflared tunnel login` against the **same** Cloudflare
   account already used for the Mac's tunnel (one account can hold several
   independent tunnels), then create a second named tunnel and route a
   **different** hostname to it (e.g. `cloudflared tunnel route dns
   omniflow-cloud cloud.yourdomain.com`) — do not reuse the Mac deployment's
   hostname.
5. Two `systemd` units (the Linux equivalent of the Mac's two LaunchAgents
   — see "Why a LaunchAgent, not a LaunchDaemon" above), both
   `Restart=on-failure` and `WantedBy=multi-user.target`. Unlike the Mac's
   LaunchAgent (which needs Automatic Login to reach the login Keychain), a
   Linux VPS has no analogous GUI-session requirement at all: Instagram/
   Threads auth here is the manually-uploaded `cookies.txt`, not
   `browser_cookie3`, so a plain systemd service survives an unattended
   reboot with no special login configuration needed.
6. `python3 -m remote_web.config show` for this deployment's own token (it
   is independent from the Mac deployment's token — each `remote_web`
   process has its own `.state.json`). Visit
   `https://<your-cloud-hostname>/unlock`, unlock, then go to Settings and
   upload a `cookies.txt` if you need Instagram/Threads to work.

**Known, accepted trade-off:** a cloud provider's IP range is more likely to
be rate-limited or blocked by TikTok specifically than a residential IP —
no mitigation (e.g. a residential proxy) is built for this in v1. Every
other platform is unaffected.

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
- [ ] (Cloud deployment only) Settings shows the new cookies-upload section
      (only in remote mode); uploading a real `cookies.txt` flips its
      status to "valid".
- [ ] (Cloud deployment only) An Instagram or Threads check/download
      succeeds after uploading cookies.
- [ ] (Cloud deployment only) A plain YouTube check/download succeeds with
      no cookies uploaded at all (proves platforms that need no auth are
      unaffected by the whole cookies-upload feature being new).

## Testing

```bash
pytest remote_web/tests/ -v          # this package's own tests
pytest                                 # confirms the native app's suite is
                                        # still 100% green and untouched
```
