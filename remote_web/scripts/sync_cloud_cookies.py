#!/usr/bin/env python3
"""Push this Mac's logged-in YouTube / Instagram / Threads browser session up
to the OmniFlow *cloud* deployment (the GCP VM), so the cloud URL can pull
from those login-gated platforms.

Why this exists: YouTube/Instagram/Threads refuse a datacenter IP outright
("LOGIN_REQUIRED" / "Sign in to confirm you're not a bot"). A residential
login session sent up from this Mac is the only free way past that. TikTok,
Facebook, X, RedNote and LinkedIn need none of this and work on the cloud
with nothing synced.

What it does, each run:
  1. Reads Chrome's cookies for youtube/google/instagram/threads via
     browser_cookie3 (the exact mechanism the Mac remote_web deployment
     already uses) - sweeping every Chrome profile, keeping the one with a
     real session per domain.
  2. Writes one Netscape cookies.txt.
  3. scp's it to the VM's remote_web/.manual_cookies.txt (0600).

First run triggers a one-time macOS Keychain prompt
("... wants to use confidential information stored in 'Chrome Safe
Storage'") - click **Always Allow**, or a headless LaunchAgent run later
can't read the cookies.

Run manually whenever you like, or install the LaunchAgent
(install-cloud-cookie-sync.sh) to run it every 6 hours while the Mac is on.
"""

import http.cookiejar
import os
import subprocess
import sys
import tempfile

# --- deployment target (edit if the VM IP changes) -------------------------
VM_SSH = "omniflow@136.67.237.12"
VM_COOKIES_PATH = "/home/omniflow/omniflow/remote_web/.manual_cookies.txt"
SSH_KEY = os.path.expanduser("~/.ssh/omniflow_cloud")

# domain -> a cookie name that only exists when that domain has a real login
_DOMAINS = {
    "youtube.com": ("__Secure-1PSID", "LOGIN_INFO", "SID"),
    "google.com": ("__Secure-1PSID", "SAPISID", "SID"),
    "instagram.com": ("sessionid",),
    "threads.net": ("sessionid",),
    "threads.com": ("sessionid",),
}

# Chromium-family browsers browser_cookie3 can read on macOS. Whichever one
# you're actually logged into wins per-domain; the rest just come back empty.
_BROWSERS = ("chrome", "arc", "brave", "edge", "chromium", "vivaldi", "opera", "firefox")


def _harvest():
    import browser_cookie3

    loaders = [(name, getattr(browser_cookie3, name))
               for name in _BROWSERS if hasattr(browser_cookie3, name)]

    jar = http.cookiejar.MozillaCookieJar()
    total = 0
    for domain, markers in _DOMAINS.items():
        best = None  # (marker_hits, browser_name, [cookies])
        for name, loader in loaders:
            try:
                cookies = list(loader(domain_name=domain))
            except Exception:  # noqa: BLE001 - browser not installed / locked / no keychain grant
                continue
            hits = sum(1 for c in cookies if c.name in markers)
            if best is None or hits > best[0]:
                best = (hits, name, cookies)
        if not best or not best[2]:
            print(f"  {domain}: no session found", file=sys.stderr)
            continue
        for c in best[2]:
            if c.expires is None:
                c.expires = 2147483647
            c.discard = False
            jar.set_cookie(c)
        total += len(best[2])
        state = f"logged in ({best[1]})" if best[0] else f"cookies only ({best[1]}, may not be logged in)"
        print(f"  {domain}: {len(best[2])} cookies, {state}")

    if total == 0:
        sys.exit("Nothing to sync - no logged-in YouTube/Instagram/Threads session "
                 "in any installed browser. Log in, then re-run.")
    return jar


def _ship(jar):
    fd, path = tempfile.mkstemp(prefix="omniflow-cloud-cookies-", suffix=".txt")
    os.close(fd)
    try:
        jar.save(path, ignore_discard=True, ignore_expires=True)
        os.chmod(path, 0o600)
        scp = subprocess.run(
            ["scp", "-q", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=accept-new",
             "-o", "ConnectTimeout=20", path, f"{VM_SSH}:{VM_COOKIES_PATH}"],
            capture_output=True, text=True,
        )
        if scp.returncode != 0:
            sys.exit(f"scp to {VM_SSH} failed:\n{scp.stderr}")
        subprocess.run(
            ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=accept-new",
             VM_SSH, f"chmod 600 {VM_COOKIES_PATH}"],
            check=False, capture_output=True,
        )
    finally:
        if os.path.exists(path):
            os.unlink(path)
    print(f"synced -> {VM_SSH}:{VM_COOKIES_PATH}")


if __name__ == "__main__":
    print("Reading Chrome sessions...")
    _ship(_harvest())
