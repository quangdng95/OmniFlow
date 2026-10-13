"""One-time COPY of the old app's data (the OmniFlow-era `~/Library/Application
Support/OmniFlow`) into ViDrop's own directory.

Safety rules, in order of importance:
  * the old directory is only ever read - never moved, changed or deleted;
  * the copy is built in a sibling temp directory and renamed into place, so an
    app closed halfway never leaves a half-filled ViDrop directory behind;
  * it never raises: a failure just means "no migration", and the app starts
    with fresh settings exactly as a first install would;
  * it is idempotent: once the new directory exists it does nothing.

Pure stdlib on purpose, so it can be unit-tested with plain temp directories.
"""

import datetime
import fnmatch
import json
import os
import shutil

MARKER_NAME = ".migrated-from-omniflow"

# Never copied: temp cookie jars (live session tokens), caches, junk.
SKIP_PATTERNS = ("omniflow-cookies-*", "omniflow-raw-*", "*.db-journal", "*.tmp", "Cache", "Caches", ".DS_Store")

# Statuses returned by migrate_from_omniflow().
MIGRATED = "migrated"
ALREADY_PRESENT = "already-present"  # the new directory exists: nothing to do
NOTHING_TO_MIGRATE = "nothing-to-migrate"  # no old directory
FAILED = "failed"


def _ignore(_directory, names):
    return [n for n in names if any(fnmatch.fnmatch(n, pattern) for pattern in SKIP_PATTERNS)]


def _repoint_config(config_path, old_dir, new_dir):
    # A saved path that lives inside the old directory (for example an uploaded
    # cookies file) must keep working after the copy, so point it at the copy.
    try:
        with open(config_path, "r") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return
    if not isinstance(data, dict):
        return
    changed = False
    for key, value in data.items():
        if isinstance(value, str) and (value == old_dir or value.startswith(old_dir + os.sep)):
            data[key] = new_dir + value[len(old_dir):]
            changed = True
    if changed:
        with open(config_path, "w") as f:
            json.dump(data, f, indent=2)


def _remove_stale_temp_dirs(new_dir):
    parent = os.path.dirname(new_dir)
    prefix = os.path.basename(new_dir) + ".migrating-"
    try:
        names = os.listdir(parent)
    except OSError:
        return
    for name in names:
        if name.startswith(prefix):
            shutil.rmtree(os.path.join(parent, name), ignore_errors=True)


def migrate_from_omniflow(old_dir, new_dir, now=None):
    """Copy `old_dir` to `new_dir` once. Returns (status, error_or_None)."""
    try:
        if os.path.exists(new_dir):
            return ALREADY_PRESENT, None
        if not os.path.isdir(old_dir):
            return NOTHING_TO_MIGRATE, None

        os.makedirs(os.path.dirname(new_dir), exist_ok=True)
        _remove_stale_temp_dirs(new_dir)  # left by an earlier run closed midway
        temp_dir = f"{new_dir}.migrating-{os.getpid()}"
        try:
            shutil.copytree(old_dir, temp_dir, ignore=_ignore, symlinks=False)
            _repoint_config(os.path.join(temp_dir, "config.json"), old_dir, new_dir)
            stamp = (now or datetime.datetime.now)().isoformat(timespec="seconds")
            with open(os.path.join(temp_dir, MARKER_NAME), "w") as f:
                json.dump({"from": old_dir, "at": stamp}, f)
            os.rename(temp_dir, new_dir)
        except BaseException:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
        return MIGRATED, None
    except Exception as error:  # noqa: BLE001 - startup must never be blocked by this
        return FAILED, error
