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
  3. POSTs it over HTTPS to the cloud deployment's /api/settings/cookies with
     the Bearer token (the same token the iOS Shortcut uses). It used to scp
     over SSH to a hard-coded public IP, which silently stopped working when
     public SSH was closed (2026-09-16; found 2026-10-03) - HTTPS goes through
     the same Cloudflare URL everyone uses, so a firewall or IP change can't
     break it. Any failure exits non-zero AND raises a macOS notification.

The token is read from $OMNIFLOW_CLOUD_TOKEN or ~/.config/omniflow/cloud_token
(save it once with set-cloud-token.sh; the file is chmod 600).

First run triggers a one-time macOS Keychain prompt
("... wants to use confidential information stored in 'Chrome Safe
Storage'") - click **Always Allow**, or a headless LaunchAgent run later
can't read the cookies.

Run manually whenever you like, or install the LaunchAgent
(install-cloud-cookie-sync.sh) to run it every hour while the Mac is on.
"""

import http.cookiejar
import json
import os
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid

# --- deployment target ------------------------------------------------------
CLOUD_URL = os.environ.get("OMNIFLOW_CLOUD_URL", "https://cloud.southframevn.com")
TOKEN_FILE = os.path.expanduser("~/.config/omniflow/cloud_token")
_UPLOAD_ATTEMPTS = 3  # for server (HTTP 5xx) errors
# Seconds to wait between tries when there is no network at all (~3 min in total).
_NETWORK_WAITS = (5, 10, 20, 30, 60, 60)
_UPLOAD_TIMEOUT_SECONDS = 30


class SyncError(Exception):
    """The sync failed in a way worth telling the owner about."""


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
        raise SyncError("nothing to sync - no logged-in YouTube/Instagram/Threads session "
                        "in any installed browser (or Keychain access was denied). Log in, then re-run.")
    return jar


def _serialize(jar):
    # MozillaCookieJar can only save to a path, so round-trip through a 0600 temp file.
    fd, path = tempfile.mkstemp(prefix="omniflow-cloud-cookies-", suffix=".txt")
    os.close(fd)
    try:
        jar.save(path, ignore_discard=True, ignore_expires=True)
        with open(path, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(path):
            os.unlink(path)


def _load_token():
    token = os.environ.get("OMNIFLOW_CLOUD_TOKEN", "").strip()
    if not token and os.path.isfile(TOKEN_FILE):
        if os.stat(TOKEN_FILE).st_mode & 0o077:
            print(f"warning: {TOKEN_FILE} is readable by other users - run: chmod 600 {TOKEN_FILE}", file=sys.stderr)
        with open(TOKEN_FILE) as f:
            token = f.read().strip()
    if not token:
        raise SyncError(
            "no cloud token - run  bash remote_web/scripts/set-cloud-token.sh  once "
            f"(or set OMNIFLOW_CLOUD_TOKEN). Looked in {TOKEN_FILE}"
        )
    return token


def _multipart(field, filename, data):
    boundary = uuid.uuid4().hex
    head = (f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
            "Content-Type: text/plain\r\n\r\n").encode()
    return head + data + f"\r\n--{boundary}--\r\n".encode(), f"multipart/form-data; boundary={boundary}"


def _ssl_context():
    # The Mac's Python may not find the system CA bundle; certifi is installed
    # (yt-dlp/requests depend on it) and always works.
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _upload(jar_bytes, token, base_url=None, sleep=time.sleep):
    url = (base_url or CLOUD_URL).rstrip("/") + "/api/settings/cookies"
    body, content_type = _multipart("cookies", "cookies.txt", jar_bytes)
    where = base_url or CLOUD_URL
    http_failures = network_failures = 0
    while True:
        request = urllib.request.Request(
            url, data=body, method="POST",
            # Own User-Agent on purpose: Cloudflare rejects the default
            # "Python-urllib/x.y" with HTTP 403 / "error code: 1010".
            headers={"Authorization": f"Bearer {token}", "Content-Type": content_type,
                     "User-Agent": "OmniFlow-CookieSync/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=_UPLOAD_TIMEOUT_SECONDS, context=_ssl_context()) as resp:
                return json.loads(resp.read().decode("utf-8", "replace") or "{}")
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                raw = e.read().decode("utf-8", "replace")
                try:
                    detail = json.loads(raw).get("error", "")
                except (ValueError, AttributeError):
                    detail = raw.strip()[:120]  # e.g. Cloudflare's plain "error code: 1010"
            except OSError:
                pass
            problem = f"HTTP {e.code} {detail}".strip()
            if 400 <= e.code < 500:
                # A wrong token / a payload the server refused will never succeed on retry.
                raise SyncError(f"upload to {where} rejected: {problem}") from None
            http_failures += 1
            if http_failures >= _UPLOAD_ATTEMPTS:
                raise SyncError(f"upload to {where} failed after {http_failures} attempts: {problem}") from None
            sleep(2 * http_failures)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            # str(e) never contains the token (it is only in a header), so this is safe to show.
            problem = f"network error: {getattr(e, 'reason', e)}"
            # A run right after the Mac wakes finds Wi-Fi/DNS not back yet (09:55
            # on 2026-10-06 failed 3x in ~10 s and nothing retried for 6 hours,
            # so the VM's YouTube cookies went stale): wait the network out.
            if network_failures >= len(_NETWORK_WAITS):
                raise SyncError(f"upload to {where} failed - no network after waiting: {problem}") from None
            sleep(_NETWORK_WAITS[network_failures])
            network_failures += 1


def _notify(message):
    # Best-effort macOS notification: a LaunchAgent run has no terminal, and a
    # silent failure is exactly how this sync stayed broken unnoticed.
    safe = message.replace("\\", " ").replace('"', "'")
    try:
        subprocess.run(
            ["osascript", "-e", f'display notification "{safe}" with title "OmniFlow cookie sync failed"'],
            check=False, capture_output=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def main():
    try:
        print("Reading browser sessions...")
        jar_bytes = _serialize(_harvest())
        result = _upload(jar_bytes, _load_token())
    except SyncError as e:
        print(f"cookie sync FAILED: {e}", file=sys.stderr)
        _notify(str(e))
        sys.exit(1)
    print(f"synced -> {CLOUD_URL} ({result.get('cookies_status', '?')}, {len(jar_bytes)} bytes)")


if __name__ == "__main__":
    main()
