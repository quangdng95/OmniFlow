"""remote_web/scripts/sync_cloud_cookies.py - the Mac-side cookie push.

It used to scp the jar over SSH to a hard-coded public IP; once public SSH was
closed (2026-09-16) that failed silently every 6 hours (found 2026-10-03). It
now POSTs over HTTPS with the Bearer token, so a firewall/IP change can't break
it, and any failure is loud (non-zero exit + a macOS notification).
"""

import importlib.util
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "sync_cloud_cookies.py")
_spec = importlib.util.spec_from_file_location("sync_cloud_cookies", _SCRIPT)
sync = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync)

JAR = b"# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t1999999999\tSID\tvalue\n"


class _Server:
    """A real local HTTP server that records requests and answers from a script."""

    def __init__(self, responses):
        self.responses = list(responses)  # [(status, json_body), ...]
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                outer.requests.append({"path": self.path, "headers": dict(self.headers), "body": self.rfile.read(length)})
                status, body = outer.responses.pop(0) if outer.responses else (200, {})
                payload = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def server():
    made = []

    def make(responses):
        s = _Server(responses)
        made.append(s)
        return s

    yield make
    for s in made:
        s.close()


def test_upload_posts_the_jar_with_the_bearer_token(server):
    srv = server([(200, {"cookies_status": "valid", "updated_at": 1759500000})])
    result = sync._upload(JAR, "s3cret", base_url=srv.url)

    assert result["cookies_status"] == "valid"
    req = srv.requests[0]
    assert req["path"] == "/api/settings/cookies"
    assert req["headers"]["Authorization"] == "Bearer s3cret"
    assert req["headers"]["Content-Type"].startswith("multipart/form-data; boundary=")
    assert b'name="cookies"' in req["body"] and JAR in req["body"]


def test_upload_retries_a_transient_server_error_then_succeeds(server):
    srv = server([(502, {"error": "bad gateway"}), (200, {"cookies_status": "valid", "updated_at": 1})])
    result = sync._upload(JAR, "t", base_url=srv.url, sleep=lambda s: None)
    assert result["cookies_status"] == "valid"
    assert len(srv.requests) == 2


def test_upload_does_not_retry_a_rejection(server):
    # 401 (wrong token) / 400 (not a cookie jar) will never succeed on retry.
    srv = server([(401, {"error": "Unlock required."})])
    with pytest.raises(sync.SyncError) as excinfo:
        sync._upload(JAR, "wrong", base_url=srv.url, sleep=lambda s: None)
    assert "401" in str(excinfo.value) and "Unlock required" in str(excinfo.value)
    assert len(srv.requests) == 1


def test_upload_gives_up_after_three_attempts(server):
    srv = server([(500, {}), (500, {}), (500, {})])
    with pytest.raises(sync.SyncError):
        sync._upload(JAR, "t", base_url=srv.url, sleep=lambda s: None)
    assert len(srv.requests) == 3


def test_upload_reports_an_unreachable_server_without_leaking_the_token():
    with pytest.raises(sync.SyncError) as excinfo:
        sync._upload(JAR, "top-secret-token", base_url="http://127.0.0.1:1", sleep=lambda s: None)
    assert "top-secret-token" not in str(excinfo.value)


def test_token_comes_from_the_environment_first(monkeypatch, tmp_path):
    token_file = tmp_path / "cloud_token"
    token_file.write_text("from-file\n")
    monkeypatch.setattr(sync, "TOKEN_FILE", str(token_file))
    monkeypatch.setenv("OMNIFLOW_CLOUD_TOKEN", " from-env ")
    assert sync._load_token() == "from-env"


def test_token_falls_back_to_the_token_file(monkeypatch, tmp_path):
    token_file = tmp_path / "cloud_token"
    token_file.write_text("from-file\n")
    os.chmod(token_file, 0o600)
    monkeypatch.setattr(sync, "TOKEN_FILE", str(token_file))
    monkeypatch.delenv("OMNIFLOW_CLOUD_TOKEN", raising=False)
    assert sync._load_token() == "from-file"


def test_missing_token_says_how_to_fix_it(monkeypatch, tmp_path):
    monkeypatch.setattr(sync, "TOKEN_FILE", str(tmp_path / "nope"))
    monkeypatch.delenv("OMNIFLOW_CLOUD_TOKEN", raising=False)
    with pytest.raises(sync.SyncError) as excinfo:
        sync._load_token()
    assert "set-cloud-token" in str(excinfo.value)


def test_a_failure_is_loud_exit_code_and_notification(monkeypatch, capsys):
    notified = []
    monkeypatch.setattr(sync, "_notify", lambda message: notified.append(message))
    monkeypatch.setattr(sync, "_harvest", lambda: object())
    monkeypatch.setattr(sync, "_serialize", lambda jar: JAR)
    monkeypatch.setattr(sync, "_load_token", lambda: "t")

    def boom(*a, **k):
        raise sync.SyncError("upload to cloud failed: HTTP 401")

    monkeypatch.setattr(sync, "_upload", boom)

    with pytest.raises(SystemExit) as excinfo:
        sync.main()

    assert excinfo.value.code != 0
    assert "HTTP 401" in capsys.readouterr().err
    assert notified and "HTTP 401" in notified[0]


def test_a_successful_run_does_not_notify(monkeypatch, capsys):
    notified = []
    monkeypatch.setattr(sync, "_notify", lambda message: notified.append(message))
    monkeypatch.setattr(sync, "_harvest", lambda: object())
    monkeypatch.setattr(sync, "_serialize", lambda jar: JAR)
    monkeypatch.setattr(sync, "_load_token", lambda: "t")
    monkeypatch.setattr(sync, "_upload", lambda *a, **k: {"cookies_status": "valid", "updated_at": 1})
    sync.main()
    assert notified == []
    assert "synced" in capsys.readouterr().out.lower()


def test_finding_no_browser_session_is_also_loud(monkeypatch, capsys):
    notified = []
    monkeypatch.setattr(sync, "_notify", lambda message: notified.append(message))
    monkeypatch.setattr(sync.http.cookiejar, "MozillaCookieJar", sync.http.cookiejar.MozillaCookieJar)

    class NoBrowser:
        def __getattr__(self, name):
            raise AttributeError(name)

    import sys as _sys
    monkeypatch.setitem(_sys.modules, "browser_cookie3", NoBrowser())

    with pytest.raises(SystemExit):
        sync.main()
    assert notified and "nothing to sync" in notified[0]


def test_upload_sends_its_own_user_agent_not_pythons_default(server):
    # Cloudflare (in front of cloud.southframevn.com) answers "error code: 1010"
    # / HTTP 403 to the default "Python-urllib/x.y" signature, so the very first
    # real run failed with an HTTP 403 that never reached the app (2026-10-03).
    srv = server([(200, {"cookies_status": "valid", "updated_at": 1})])
    sync._upload(JAR, "t", base_url=srv.url)
    user_agent = srv.requests[0]["headers"]["User-Agent"]
    assert user_agent.startswith("OmniFlow-CookieSync/")
    assert "urllib" not in user_agent.lower()


def test_a_non_json_rejection_still_shows_what_the_server_said(server):
    # e.g. Cloudflare's plain-text "error code: 1010" - without this the
    # message was just "HTTP 403" and gave no clue where it came from.
    class PlainTextServer(_Server):
        pass

    srv = server([])

    class Handler(srv.httpd.RequestHandlerClass):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            payload = b"error code: 1010"
            self.send_response(403)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    srv.httpd.RequestHandlerClass = Handler
    with pytest.raises(sync.SyncError) as excinfo:
        sync._upload(JAR, "t", base_url=srv.url, sleep=lambda s: None)
    assert "403" in str(excinfo.value) and "error code: 1010" in str(excinfo.value)


# ---- waking from sleep: the network is not up yet (2026-10-06) ----
#
# The 09:55 run happened seconds after the Mac woke, before Wi-Fi was back:
# "nodename nor servname provided, or not known" three times in ~10 s, then no
# retry for 6 hours - so YouTube downloads on the VM went stale and 403'd.


def test_a_network_that_is_not_up_yet_is_waited_for(server):
    srv = server([(200, {"cookies_status": "valid", "updated_at": 1})])
    state = {"dns_failures_left": 4}
    real_urlopen = sync.urllib.request.urlopen

    def flaky_urlopen(request, timeout=None, context=None):
        if state["dns_failures_left"] > 0:
            state["dns_failures_left"] -= 1
            raise sync.urllib.error.URLError(OSError(8, "nodename nor servname provided, or not known"))
        return real_urlopen(request, timeout=timeout)

    delays = []
    sync.urllib.request.urlopen = flaky_urlopen
    try:
        result = sync._upload(JAR, "t", base_url=srv.url, sleep=delays.append)
    finally:
        sync.urllib.request.urlopen = real_urlopen
    assert result["cookies_status"] == "valid"
    assert len(delays) == 4  # it waited, rather than giving up after 3 quick tries
    assert delays == sorted(delays)  # backing off


def test_it_eventually_gives_up_on_a_network_that_never_comes_back():
    delays = []
    with pytest.raises(sync.SyncError) as excinfo:
        sync._upload(JAR, "tok", base_url="http://127.0.0.1:1", sleep=delays.append)
    assert len(delays) >= 5
    assert sum(delays) >= 120  # waits a couple of minutes for Wi-Fi to reconnect
    assert "tok" not in str(excinfo.value)


def test_the_launch_agent_runs_hourly_not_every_six_hours():
    installer = open(os.path.join(os.path.dirname(_SCRIPT), "install-cloud-cookie-sync.sh")).read()
    assert "<key>StartInterval</key><integer>3600</integer>" in installer


def test_the_rednote_login_is_synced_to_the_cloud_too():
    # RedNote shows nothing without a login (2026-10-06); the VM has no browser,
    # so its only source is this sync.
    assert sync._DOMAINS["rednote.com"] == ("web_session",)
    assert sync._DOMAINS["xiaohongshu.com"] == ("web_session",)
