import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import server as server_module


@pytest.fixture
def client():
    server_module.app.config["TESTING"] = True
    return server_module.app.test_client()


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    monkeypatch.setattr(server_module, "CONFIG_FILE", str(config_file))
    return config_file


@pytest.fixture(autouse=True)
def clear_jobs():
    server_module.jobs.clear()
    yield
    server_module.jobs.clear()
