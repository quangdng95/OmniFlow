"""Incremental .zip assembly for a batch job (spec §5.3) - one archive stays
open for the batch's duration; each item is appended and its raw file
deleted immediately, capping peak disk usage near BATCH_CONCURRENCY
in-flight raw files instead of the whole batch's total size.
"""

import os
import threading
import zipfile


def _unique_archive_name(existing_names, filename):
    # Same collision-suffix approach as backend.download.get_unique_filename,
    # but against the zip's own entry names instead of a directory listing -
    # a zip archive has no directory to os.path.exists() against.
    if filename not in existing_names:
        existing_names.add(filename)
        return filename
    base, ext = os.path.splitext(filename)
    counter = 1
    while True:
        candidate = f"{base} ({counter}){ext}"
        if candidate not in existing_names:
            existing_names.add(candidate)
            return candidate
        counter += 1


class BatchZipper:
    def __init__(self, zip_path):
        self.zip_path = zip_path
        self._lock = threading.Lock()
        self._names = set()
        # Ordering (batch items finish in whatever order the network allows,
        # but the archive - and so the order a phone saves the files into
        # Photos - must match the order the user listed them in): an indexed
        # item finishing early is parked in _held until every lower index has
        # been written or skipped. _next_index is the lowest unresolved one.
        self._held = {}
        self._skipped = set()
        self._next_index = 0
        # ZIP_STORED - no compression. The contents are already-compressed
        # video/image files, so the module's default ZIP_DEFLATE would just
        # burn CPU on the deployment Mac for no size reduction (§5.3).
        self._zf = zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_STORED)

    def _write_and_delete(self, source_path, filename):
        arcname = _unique_archive_name(self._names, filename)
        self._zf.write(source_path, arcname=arcname)
        try:
            os.remove(source_path)
        except OSError:
            pass
        return arcname

    def _drain(self):
        # Caller holds self._lock. Write every held item that is now next in line.
        while True:
            if self._next_index in self._skipped:
                self._skipped.discard(self._next_index)
            elif self._next_index in self._held:
                self._write_and_delete(*self._held.pop(self._next_index))
            else:
                return
            self._next_index += 1

    def add_and_delete(self, source_path, filename, index=None):
        # write() + the uniquing decision happen under one lock so two batch
        # items finishing at the same instant can't race on the same
        # candidate name or interleave writes into the same ZipFile handle.
        # With an `index`, the item is written only once every earlier index
        # has been written or skip()ped (its raw file stays on disk until
        # then), so the zip keeps item order instead of completion order.
        with self._lock:
            if index is None:
                return self._write_and_delete(source_path, filename)
            self._held[index] = (source_path, filename)
            self._drain()
        return filename

    def skip(self, index):
        # An item that failed (or was cancelled) will never be added - release
        # the items queued up behind it.
        with self._lock:
            self._skipped.add(index)
            self._drain()

    def close(self):
        with self._lock:
            # Anything still held is waiting on an index that never reported
            # back (e.g. a cancelled batch) - write it in index order anyway.
            for index in sorted(self._held):
                self._write_and_delete(*self._held.pop(index))
            self._zf.close()

    def touch(self):
        # Keeps zip_dir's mtime fresh while a batch is actively downloading,
        # even before any single item finishes and gets add_and_delete()'d -
        # otherwise reaper.py's mtime-based sweep (spec §5.4) could reap an
        # in-flight batch whose items each take longer than
        # REAPER_STALE_MINUTES to download, silently losing the whole job.
        try:
            os.utime(self.zip_path, None)
        except OSError:
            pass
