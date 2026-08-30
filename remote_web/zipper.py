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
        # ZIP_STORED - no compression. The contents are already-compressed
        # video/image files, so the module's default ZIP_DEFLATE would just
        # burn CPU on the deployment Mac for no size reduction (§5.3).
        self._zf = zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_STORED)

    def add_and_delete(self, source_path, filename):
        # write() + the uniquing decision happen under one lock so two batch
        # items finishing at the same instant can't race on the same
        # candidate name or interleave writes into the same ZipFile handle.
        with self._lock:
            arcname = _unique_archive_name(self._names, filename)
            self._zf.write(source_path, arcname=arcname)
        try:
            os.remove(source_path)
        except OSError:
            pass
        return arcname

    def close(self):
        with self._lock:
            self._zf.close()
