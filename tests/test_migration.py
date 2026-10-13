"""backend.migration - the one-time COPY of OmniFlow-era data into ViDrop's
own directory. Every test uses temp directories; nothing touches the real
~/Library."""

import json
import os
import shutil
import subprocess
import sys

import pytest

from backend import migration

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _tree(root):
    out = {}
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            path = os.path.join(dirpath, name)
            with open(path, "rb") as f:
                out[os.path.relpath(path, root)] = f.read()
    return out


@pytest.fixture
def dirs(tmp_path):
    base = tmp_path / "Application Support"
    base.mkdir()
    return str(base / "OmniFlow"), str(base / "ViDrop")


def _make_old(old_dir, **extra):
    os.makedirs(old_dir)
    with open(os.path.join(old_dir, "config.json"), "w") as f:
        json.dump({"path": "/Users/x/Movies", "playlist_limit": 200}, f)
    for name, content in extra.items():
        with open(os.path.join(old_dir, name), "w") as f:
            f.write(content)


def test_copies_the_old_data_and_leaves_the_old_directory_untouched(dirs):
    old, new = dirs
    _make_old(old, **{"history.json": "[1,2]"})
    before = _tree(old)

    status, error = migration.migrate_from_omniflow(old, new)

    assert (status, error) == (migration.MIGRATED, None)
    copied = _tree(new)
    assert json.loads(copied["config.json"])["playlist_limit"] == 200
    assert copied["history.json"] == b"[1,2]"
    assert _tree(old) == before  # COPY, never move or change


def test_writes_a_marker_with_the_source_and_a_timestamp(dirs):
    import datetime

    old, new = dirs
    _make_old(old)
    migration.migrate_from_omniflow(old, new, now=lambda: datetime.datetime(2026, 10, 13, 9, 30, 0))
    marker = json.load(open(os.path.join(new, migration.MARKER_NAME)))
    assert marker == {"from": old, "at": "2026-10-13T09:30:00"}


def test_skips_temp_cookie_jars_and_caches(dirs):
    old, new = dirs
    _make_old(old, **{"omniflow-cookies-abc.txt": "sessionid", "omniflow-raw-chrome-1.db": "x", "notes.tmp": "x"})
    os.makedirs(os.path.join(old, "Cache"))
    with open(os.path.join(old, "Cache", "blob"), "w") as f:
        f.write("x")
    migration.migrate_from_omniflow(old, new)
    assert sorted(os.listdir(new)) == sorted(["config.json", migration.MARKER_NAME])


def test_nothing_to_migrate_when_there_is_no_old_directory(dirs):
    old, new = dirs
    assert migration.migrate_from_omniflow(old, new) == (migration.NOTHING_TO_MIGRATE, None)
    assert not os.path.exists(new)  # config.py creates it itself on a fresh install


def test_does_nothing_when_the_new_directory_already_exists(dirs):
    old, new = dirs
    _make_old(old)
    os.makedirs(new)
    with open(os.path.join(new, "config.json"), "w") as f:
        f.write('{"path": "/new"}')
    assert migration.migrate_from_omniflow(old, new) == (migration.ALREADY_PRESENT, None)
    assert json.load(open(os.path.join(new, "config.json"))) == {"path": "/new"}  # never overwritten


def test_running_twice_is_harmless(dirs):
    old, new = dirs
    _make_old(old)
    assert migration.migrate_from_omniflow(old, new)[0] == migration.MIGRATED
    first = _tree(new)
    assert migration.migrate_from_omniflow(old, new)[0] == migration.ALREADY_PRESENT
    assert _tree(new) == first


def test_a_copy_that_fails_midway_leaves_no_half_filled_directory(dirs, monkeypatch):
    old, new = dirs
    _make_old(old, **{"history.json": "[1]"})
    before = _tree(old)
    real_copytree = shutil.copytree

    def dying_copytree(src, dst, **kwargs):
        real_copytree(src, dst, **kwargs)  # the copy gets as far as writing files...
        raise OSError("disk full")  # ...then dies

    monkeypatch.setattr(migration.shutil, "copytree", dying_copytree)
    status, error = migration.migrate_from_omniflow(old, new)

    assert status == migration.FAILED and isinstance(error, OSError)
    assert not os.path.exists(new)
    assert [n for n in os.listdir(os.path.dirname(new)) if "migrating" in n] == []
    assert _tree(old) == before

    # and the next launch simply tries again
    monkeypatch.setattr(migration.shutil, "copytree", real_copytree)
    assert migration.migrate_from_omniflow(old, new)[0] == migration.MIGRATED


def test_cleans_up_a_temp_directory_left_by_an_app_closed_midway(dirs):
    old, new = dirs
    _make_old(old)
    stale = new + ".migrating-99999"
    os.makedirs(stale)
    with open(os.path.join(stale, "half"), "w") as f:
        f.write("x")
    assert migration.migrate_from_omniflow(old, new)[0] == migration.MIGRATED
    assert not os.path.exists(stale)


def test_a_saved_path_inside_the_old_directory_is_pointed_at_the_copy(dirs):
    old, new = dirs
    os.makedirs(old)
    with open(os.path.join(old, "config.json"), "w") as f:
        json.dump({"cookies_path": os.path.join(old, "cookies.txt"), "path": "/Users/x/Movies"}, f)
    migration.migrate_from_omniflow(old, new)
    saved = json.load(open(os.path.join(new, "config.json")))
    assert saved["cookies_path"] == os.path.join(new, "cookies.txt")
    assert saved["path"] == "/Users/x/Movies"


def test_a_corrupt_config_is_copied_as_is_and_does_not_fail_the_migration(dirs):
    old, new = dirs
    os.makedirs(old)
    with open(os.path.join(old, "config.json"), "w") as f:
        f.write("{not json")
    assert migration.migrate_from_omniflow(old, new)[0] == migration.MIGRATED
    assert open(os.path.join(new, "config.json")).read() == "{not json"


def test_the_frozen_app_migrates_on_import_with_a_temporary_home(tmp_path):
    # The real code path: backend.config runs the migration at import time when
    # frozen. A throwaway HOME keeps it away from the real ~/Library.
    home = tmp_path / "home"
    old = home / "Library" / "Application Support" / "OmniFlow"
    old.mkdir(parents=True)
    (old / "config.json").write_text(json.dumps({"path": str(home / "Movies"), "playlist_limit": 50}))
    script = (
        "import sys; sys.frozen = True\n"
        "from backend import config, paths\n"
        "print(config.CONFIG_FILE)\n"
        "print(paths.LOG_DIR)\n"
    )
    env = {**os.environ, "HOME": str(home)}
    result = subprocess.run([sys.executable, "-c", script], cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    config_file, log_dir = result.stdout.split("\n")[:2]
    assert config_file == str(home / "Library" / "Application Support" / "ViDrop" / "config.json")
    assert log_dir == str(home / "Library" / "Logs" / "ViDrop")
    assert json.load(open(config_file))["playlist_limit"] == 50
    assert os.path.exists(os.path.join(os.path.dirname(config_file), migration.MARKER_NAME))
    assert json.load(open(old / "config.json"))["playlist_limit"] == 50  # old copy intact

    # second launch: nothing changes
    marker_before = open(os.path.join(os.path.dirname(config_file), migration.MARKER_NAME)).read()
    subprocess.run([sys.executable, "-c", script], cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=60)
    assert open(os.path.join(os.path.dirname(config_file), migration.MARKER_NAME)).read() == marker_before
