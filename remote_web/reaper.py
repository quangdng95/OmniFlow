"""Filesystem-mtime sweep of remote_web's temp-dir root (spec §5.4) - no
dependency on in-memory job state, so it correctly catches both a
finished-but-unfetched job AND any directory orphaned by a mid-download
launchd restart (a restart wipes backend.jobs.jobs, which a job-dict-driven
reaper would have needed to consult - see the spec's v2->v3 changelog for
why that earlier design was broken by construction).
"""

import os
import shutil
import threading
import time

from remote_web import config


def _newest_mtime(dir_path):
    newest = os.path.getmtime(dir_path)
    for root, _dirs, files in os.walk(dir_path):
        for name in files:
            try:
                newest = max(newest, os.path.getmtime(os.path.join(root, name)))
            except OSError:
                pass
    return newest


def sweep(temp_root, stale_minutes):
    # Deletes every immediate subdirectory of temp_root whose newest
    # contained file (or the directory itself, if empty) is older than
    # stale_minutes. Returns the list of paths removed - for test/log
    # visibility only, callers don't need to act on it.
    if not os.path.isdir(temp_root):
        return []
    cutoff = time.time() - stale_minutes * 60
    removed = []
    for name in os.listdir(temp_root):
        path = os.path.join(temp_root, name)
        if not os.path.isdir(path):
            continue
        try:
            if _newest_mtime(path) < cutoff:
                shutil.rmtree(path, ignore_errors=True)
                removed.append(path)
        except OSError:
            pass
    return removed


def start_background_sweeper(temp_root=None, interval_seconds=None, stale_minutes=None):
    # One lightweight daemon thread, started once at app startup - no
    # external scheduler/cron needed (§5.4).
    temp_root = temp_root or config.TEMP_ROOT
    interval_seconds = interval_seconds or config.REAPER_SWEEP_INTERVAL_SECONDS
    stale_minutes = stale_minutes if stale_minutes is not None else config.REAPER_STALE_MINUTES

    def _loop():
        while True:
            sweep(temp_root, stale_minutes)
            time.sleep(interval_seconds)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    return t
