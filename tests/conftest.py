import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import server as server_module
from backend import config as config_module
from backend import jobs as jobs_module


@pytest.fixture
def client():
    server_module.app.config["TESTING"] = True
    return server_module.app.test_client()


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    monkeypatch.setattr(config_module, "CONFIG_FILE", str(config_file))
    return config_file


@pytest.fixture(autouse=True)
def clear_jobs():
    # Clear IN PLACE - the jobs dict's identity is shared across modules and
    # must never be rebound (see backend/jobs.py).
    jobs_module.jobs.clear()
    yield
    jobs_module.jobs.clear()


@pytest.fixture(autouse=True)
def no_browser_cookie_scan(monkeypatch):
    # Auto-cookie extraction (browser_cookie3) reads the *real* logged-in browser
    # profiles on the machine running the tests - which would make Instagram tests
    # non-deterministic (and hit the network) on a dev box that happens to have a
    # live Instagram session in Chrome. Stub it out by default so every test sees
    # "no browser session found". The fixture returns the real function so the few
    # tests that specifically exercise it can call it directly.
    original = server_module.cookiefiles_from_browsers
    monkeypatch.setattr(server_module, "cookiefiles_from_browsers", lambda domain="instagram.com": [])
    return original
