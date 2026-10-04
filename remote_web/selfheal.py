"""Self-maintenance for the cloud VM: keep yt-dlp current, and notice when a
platform stops working.

Most "can't check a link / can't download" breakages are yt-dlp falling behind a
platform change (YouTube, TikTok and Instagram change every few weeks), so the
VM upgrades yt-dlp by itself - but an unattended upgrade must never make things
WORSE, so every upgrade is followed by a canary run through the app's own HTTP
API, and rolled back if a platform that worked before no longer does.

    python -m remote_web.selfheal run      # upgrade yt-dlp + canary (+ roll back)
    python -m remote_web.selfheal canary   # canary only
    python -m remote_web.selfheal status   # print the last result

Run every 6 hours by omniflow-selfheal.timer (remote_web/deploy/). The result
lands in remote_web/.canary.json and in GET /api/health/detail ("canary").
Optional push notification: set OMNIFLOW_NTFY_TOPIC (https://ntfy.sh/<topic>);
nothing is sent anywhere unless it is set.
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

from remote_web import config

STATUS_FILE = os.path.join(os.path.dirname(config.STATE_FILE), ".canary.json")
CANARY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "canary_urls.json")
SERVICE = "omniflow-remote"
_RETRY_AFTER_SECONDS = 45
_DOWNLOAD_TIMEOUT_SECONDS = 150


def load_canaries():
    with open(CANARY_FILE, encoding="utf-8") as f:
        return json.load(f)


def _api(path, body=None, timeout=100):
    # Through the app's own HTTP API with the access token, so the canary
    # exercises the real routes (classification, resolvers, download workers).
    req = urllib.request.Request(
        f"http://127.0.0.1:{config.PORT}{path}",
        data=(json.dumps(body).encode() if body is not None else None),
        headers={"Authorization": f"Bearer {config.get_or_create_token()}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8", "replace"))
        except (ValueError, OSError):
            return e.code, {"error": f"HTTP {e.code}"}
    except (urllib.error.URLError, OSError, ValueError) as e:
        return 0, {"error": f"{type(e).__name__}: {str(e)[:80]}"}


def _check_one(api, canary):
    code, data = api("/api/check", {"url": canary["url"]})
    if code != 200 or data.get("type") != canary["expect"]:
        return False, (data.get("error") or f"HTTP {code}, type={data.get('type')}")[:160]
    if not canary.get("download"):
        return True, ""
    code, job = api("/api/download", {"url": canary["url"], "title": "canary", "quality": (data.get("qualities") or ["Best"])[0]})
    if code != 200:
        return False, (job.get("error") or f"download HTTP {code}")[:160]
    deadline = time.time() + _DOWNLOAD_TIMEOUT_SECONDS
    progress = {}
    while time.time() < deadline:
        time.sleep(3)
        _, progress = api(f"/api/progress/{job['job_id']}")
        if progress.get("status") != "running":
            break
    if progress.get("status") == "done":
        return True, ""
    return False, (progress.get("text") or f"download {progress.get('status', 'timed out')}")[:160]


def run_canary(api, canaries):
    results = {}
    for canary in canaries:
        started = time.time()
        ok, detail = _check_one(api, canary)
        if not ok:
            # One retry: a single network blip must not raise a false alarm.
            time.sleep(_RETRY_AFTER_SECONDS)
            ok, detail = _check_one(api, canary)
        results[canary["name"]] = {"ok": ok, "detail": detail, "secs": round(time.time() - started, 1)}
    return results


def ytdlp_version():
    # A fresh interpreter, because this process may have imported the old version.
    out = subprocess.run(
        [sys.executable, "-c", "import importlib.metadata as m; print(m.version('yt-dlp'))"],
        capture_output=True, text=True, timeout=60,
    )
    return out.stdout.strip() or None


def pip_install(spec):
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", *spec.split()], check=True, timeout=600)


def restart_service():
    subprocess.run(["sudo", "systemctl", "restart", SERVICE], check=False, timeout=60)
    for _ in range(30):
        time.sleep(2)
        code, _ = _api("/health", timeout=5)
        if code == 200:
            return True
    return False


def _read_status():
    try:
        with open(STATUS_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _write_status(status):
    tmp = STATUS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(status, f, indent=1)
    os.replace(tmp, STATUS_FILE)


def _notify(message):
    topic = os.environ.get("OMNIFLOW_NTFY_TOPIC", "").strip()
    if not topic:
        return
    try:
        urllib.request.urlopen(
            urllib.request.Request(f"https://ntfy.sh/{topic}", data=message.encode(), headers={"Title": "OmniFlow"}),
            timeout=10,
        )
    except (urllib.error.URLError, OSError):
        pass


def _failing(results):
    return sorted(name for name, r in results.items() if not r["ok"])


def run(update=True):
    previous = _read_status() or {}
    was_ok = {n for n, r in (previous.get("results") or {}).items() if r.get("ok")}
    canaries = load_canaries()
    before = ytdlp_version()
    updated_from, rolled_back = None, False

    if update:
        pip_install("--upgrade yt-dlp")
        after = ytdlp_version()
        if after and after != before:
            updated_from = before
            healthy = restart_service()
            results = run_canary(_api, canaries) if healthy else {}
            # Only a platform that WORKED before the upgrade can count against it.
            regressed = [n for n in was_ok if not results.get(n, {}).get("ok")]
            if not healthy or regressed:
                pip_install(f"yt-dlp=={before}")
                restart_service()
                rolled_back = True
                results = run_canary(_api, canaries)
        else:
            results = run_canary(_api, canaries)
    else:
        results = run_canary(_api, canaries)

    failing = _failing(results)
    status = {
        "ran_at": int(time.time()),
        "yt_dlp": ytdlp_version(),
        "updated_from": updated_from,
        "rolled_back": rolled_back,
        "results": results,
        "failing": failing,
        "ok": not failing,
    }
    _write_status(status)

    newly_failing = [n for n in failing if n not in (previous.get("failing") or [])]
    if newly_failing:
        _notify("Not working now: " + ", ".join(newly_failing) + f" (yt-dlp {status['yt_dlp']})")
    if rolled_back:
        _notify(f"yt-dlp upgrade from {updated_from} broke a platform; rolled back to {before}.")
    return status


def summary():
    """The small, secret-free view /api/health/detail exposes."""
    status = _read_status()
    if not status:
        return None
    return {
        "ran_at": status["ran_at"],
        "age_hours": round((time.time() - status["ran_at"]) / 3600, 2),
        "yt_dlp": status.get("yt_dlp"),
        "failing": status.get("failing", []),
        "rolled_back": status.get("rolled_back", False),
        "updated_from": status.get("updated_from"),
        "ok": status.get("ok", False),
    }


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    if command == "run":
        print(json.dumps(run(update=True), indent=1))
    elif command == "canary":
        print(json.dumps(run(update=False), indent=1))
    else:
        print(json.dumps(_read_status(), indent=1))
