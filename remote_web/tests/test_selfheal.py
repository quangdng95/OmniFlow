"""remote_web/selfheal.py - keeps yt-dlp current on the cloud VM and notices
when a platform stops working.

Most "can't check / can't download" breakages are yt-dlp falling behind a
platform change, so the VM upgrades yt-dlp itself - but an upgrade must never
make things WORSE unattended, so every upgrade is followed by a canary run and
rolled back if a platform that worked before no longer does.
"""

import json

import pytest

from remote_web import selfheal


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(selfheal, "STATUS_FILE", str(tmp_path / ".canary.json"))
    monkeypatch.delenv("OMNIFLOW_NTFY_TOPIC", raising=False)
    monkeypatch.setattr(selfheal.time, "sleep", lambda s: None)
    return tmp_path


CANARIES = [
    {"name": "youtube", "url": "https://www.youtube.com/watch?v=x", "expect": "video", "download": True},
    {"name": "tiktok", "url": "https://www.tiktok.com/@a/video/1", "expect": "video", "download": False},
]


def _api_always(ok_by_name):
    """A fake API: /api/check answers from ok_by_name keyed by the canary URL's platform."""

    def api(path, body=None):
        name = "youtube" if "youtube" in (body or {}).get("url", "") else "tiktok"
        if path == "/api/check":
            return (200, {"type": "video"}) if ok_by_name.get(name, True) else (400, {"error": "boom"})
        if path == "/api/download":
            return (200, {"job_id": "j"}) if ok_by_name.get(name, True) else (400, {"error": "no"})
        return 200, {"status": "done"}

    return api


# ---- run_canary ----


def test_canary_reports_each_platform():
    results = selfheal.run_canary(_api_always({"tiktok": False}), CANARIES)
    assert results["youtube"]["ok"] is True
    assert results["tiktok"]["ok"] is False
    assert "boom" in results["tiktok"]["detail"]


def test_a_check_that_returns_the_wrong_kind_fails():
    def api(path, body=None):
        return 200, {"type": "playlist"}

    results = selfheal.run_canary(api, [CANARIES[1]])
    assert results["tiktok"]["ok"] is False


def test_a_transient_failure_is_retried_once_before_it_counts():
    calls = {"n": 0}

    def flaky(path, body=None):
        calls["n"] += 1
        return (400, {"error": "blip"}) if calls["n"] == 1 else (200, {"type": "video"})

    results = selfheal.run_canary(flaky, [CANARIES[1]])
    assert results["tiktok"]["ok"] is True


def test_a_download_canary_must_finish_downloading():
    def api(path, body=None):
        if path == "/api/check":
            return 200, {"type": "video"}
        if path == "/api/download":
            return 200, {"job_id": "j"}
        return 200, {"status": "error", "text": "unable to download video data: HTTP Error 403: Forbidden"}

    results = selfheal.run_canary(api, [CANARIES[0]])
    assert results["youtube"]["ok"] is False
    assert "403" in results["youtube"]["detail"]


# ---- run(): update, canary, roll back ----


class Env:
    """Stands in for pip + systemd + the canary, recording what happened."""

    def __init__(self, monkeypatch, versions, canary_results):
        self.versions = list(versions)  # what ytdlp_version() reports over time
        self.canary_results = list(canary_results)  # one results dict per canary run
        self.installs, self.restarts = [], 0
        self.healthy_after_restart = True
        monkeypatch.setattr(selfheal, "ytdlp_version", lambda: self.versions.pop(0) if len(self.versions) > 1 else self.versions[0])
        monkeypatch.setattr(selfheal, "pip_install", lambda spec: self.installs.append(spec))
        monkeypatch.setattr(selfheal, "restart_service", self.restart)
        monkeypatch.setattr(selfheal, "load_canaries", lambda: CANARIES)
        monkeypatch.setattr(selfheal, "run_canary", lambda api, canaries: self.canary_results.pop(0))
        monkeypatch.setattr(selfheal, "_api", lambda path, body=None: (200, {}))

    def restart(self):
        self.restarts += 1
        return self.healthy_after_restart


GOOD = {"youtube": {"ok": True, "detail": "", "secs": 1}, "tiktok": {"ok": True, "detail": "", "secs": 1}}
BAD_YT = {"youtube": {"ok": False, "detail": "403", "secs": 1}, "tiktok": {"ok": True, "detail": "", "secs": 1}}


def _status():
    return json.load(open(selfheal.STATUS_FILE))


def test_no_new_version_means_a_canary_run_and_no_restart(monkeypatch):
    env = Env(monkeypatch, ["2026.8.19", "2026.8.19"], [GOOD])
    selfheal.run()
    assert env.restarts == 0
    assert _status()["ok"] is True and _status()["yt_dlp"] == "2026.8.19"
    assert _status()["updated_from"] is None


def test_a_new_version_is_kept_when_everything_still_works(monkeypatch):
    env = Env(monkeypatch, ["2026.8.19", "2026.9.30"], [GOOD, GOOD])
    selfheal.run()
    assert env.restarts == 1
    assert _status()["updated_from"] == "2026.8.19" and _status()["yt_dlp"] == "2026.9.30"
    assert _status()["rolled_back"] is False


def test_a_new_version_that_breaks_a_working_platform_is_rolled_back(monkeypatch):
    # First a healthy baseline run is recorded, then an update regresses youtube.
    env = Env(monkeypatch, ["2026.8.19", "2026.8.19"], [GOOD])
    selfheal.run()

    env2 = Env(monkeypatch, ["2026.8.19", "2026.9.30", "2026.8.19"], [BAD_YT, GOOD])
    selfheal.run()

    assert env2.installs == ["--upgrade yt-dlp", "yt-dlp==2026.8.19"] or env2.installs[-1] == "yt-dlp==2026.8.19"
    assert env2.restarts == 2  # restarted for the upgrade, again after rolling back
    status = _status()
    assert status["rolled_back"] is True
    assert status["yt_dlp"] == "2026.8.19"
    assert status["ok"] is True  # the rolled-back state is healthy again


def test_a_platform_that_was_already_broken_does_not_block_an_update(monkeypatch):
    # YouTube was failing before the upgrade, so it failing after proves nothing against the new version.
    env = Env(monkeypatch, ["2026.8.19", "2026.8.19"], [BAD_YT])
    selfheal.run()  # baseline recorded with youtube failing

    env2 = Env(monkeypatch, ["2026.8.19", "2026.9.30"], [BAD_YT, BAD_YT])
    selfheal.run()
    assert env2.restarts == 1
    assert _status()["rolled_back"] is False and _status()["yt_dlp"] == "2026.9.30"
    assert _status()["failing"] == ["youtube"]


def test_a_service_that_does_not_come_back_after_an_upgrade_is_rolled_back(monkeypatch):
    env = Env(monkeypatch, ["2026.8.19", "2026.9.30", "2026.8.19"], [GOOD])
    env.healthy_after_restart = False
    selfheal.run()
    assert env.installs[-1] == "yt-dlp==2026.8.19"
    assert _status()["rolled_back"] is True


# ---- notifications ----


def test_nothing_is_sent_anywhere_unless_a_topic_is_configured(monkeypatch):
    sent = []
    monkeypatch.setattr(selfheal.urllib.request, "urlopen", lambda *a, **k: sent.append(a))
    Env(monkeypatch, ["1", "1"], [BAD_YT])
    selfheal.run()
    assert sent == []


def test_a_newly_failing_platform_triggers_one_notification_when_configured(monkeypatch):
    sent = []
    monkeypatch.setenv("OMNIFLOW_NTFY_TOPIC", "my-topic")
    monkeypatch.setattr(selfheal.urllib.request, "urlopen", lambda req, timeout=10: sent.append((req.full_url, req.data)))
    Env(monkeypatch, ["1", "1"], [BAD_YT])
    selfheal.run()
    assert len(sent) == 1 and sent[0][0].endswith("/my-topic") and b"youtube" in sent[0][1]

    Env(monkeypatch, ["1", "1"], [BAD_YT])
    selfheal.run()
    assert len(sent) == 1  # still failing, not NEW - no repeat spam


# ---- health detail ----


def test_health_detail_shows_the_latest_canary_result(monkeypatch, isolated):
    from remote_web import config
    from remote_web.app import app
    from remote_web.routes import health

    monkeypatch.setattr(config, "STATE_FILE", str(isolated / ".state.json"))
    selfheal._write_status({"ran_at": 1_700_000_000, "yt_dlp": "2026.8.19", "updated_from": None,
                            "rolled_back": False, "results": BAD_YT, "failing": ["youtube"], "ok": False})
    health._detail_cache["payload"] = None
    app.config["TESTING"] = True
    client = app.test_client()
    client.post("/unlock", data={"token": config.get_or_create_token()})
    canary = client.get("/api/health/detail").get_json()["canary"]
    assert canary["failing"] == ["youtube"] and canary["yt_dlp"] == "2026.8.19"
    assert "results" not in canary  # summary only


def test_health_detail_canary_is_null_before_the_first_run(monkeypatch, isolated):
    from remote_web import config
    from remote_web.app import app
    from remote_web.routes import health

    monkeypatch.setattr(config, "STATE_FILE", str(isolated / ".state.json"))
    health._detail_cache["payload"] = None
    app.config["TESTING"] = True
    client = app.test_client()
    client.post("/unlock", data={"token": config.get_or_create_token()})
    assert client.get("/api/health/detail").get_json()["canary"] is None
