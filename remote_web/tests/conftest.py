import os

import pytest

from remote_web import config as config_module


@pytest.fixture
def isolated_state_file(tmp_path, monkeypatch):
    # config.py persists the trust token + signing key to a real file - point
    # every test at a throwaway path so tests never read/write the real
    # deployment's own .state.json.
    state_file = tmp_path / ".state.json"
    monkeypatch.setattr(config_module, "STATE_FILE", str(state_file))
    return state_file
