"""Token/secret-key persistence + rotation (spec §4.2, §4.3)."""

import json
import os

from remote_web import config


def test_get_or_create_token_persists_across_calls(isolated_state_file):
    first = config.get_or_create_token()
    second = config.get_or_create_token()
    assert first == second
    assert len(first) > 20  # secrets.token_urlsafe(32) is well over 20 chars


def test_get_or_create_secret_key_is_independent_of_the_token(isolated_state_file):
    token = config.get_or_create_token()
    key = config.get_or_create_secret_key()
    assert token != key


def test_rotate_token_changes_the_token_but_not_the_secret_key(isolated_state_file):
    old_token = config.get_or_create_token()
    old_key = config.get_or_create_secret_key()
    new_token = config.rotate_token()
    assert new_token != old_token
    assert config.get_or_create_token() == new_token
    assert config.get_or_create_secret_key() == old_key


def test_rotate_secret_key_changes_the_key_but_not_the_token(isolated_state_file):
    old_token = config.get_or_create_token()
    old_key = config.get_or_create_secret_key()
    new_key = config.rotate_secret_key()
    assert new_key != old_key
    assert config.get_or_create_secret_key() == new_key
    assert config.get_or_create_token() == old_token


def test_state_file_is_owner_only_readable(isolated_state_file):
    config.get_or_create_token()
    mode = os.stat(config.STATE_FILE).st_mode & 0o777
    assert mode == 0o600


def test_state_file_survives_a_fresh_load_from_disk(isolated_state_file):
    token = config.get_or_create_token()
    with open(config.STATE_FILE) as f:
        data = json.load(f)
    assert data["token"] == token
