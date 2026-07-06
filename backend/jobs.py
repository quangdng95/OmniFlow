"""Shared download-job state.

`jobs` is THE single job registry, keyed by uuid4 hex: every download route
seeds an entry, worker threads mutate it, /api/progress reads it and
/api/cancel flips its "cancelled" flag. It must never be REBOUND (no
`jobs = {}` anywhere else — tests clear it in place) so every module keeps
observing the same dict object.
"""

import os

jobs = {}


def _remove_job_file(job_id):
    # Delete a job's partially-written output file (used when an Instagram
    # direct download is cancelled or errors out mid-stream).
    filepath = jobs.get(job_id, {}).get("filepath")
    if filepath and os.path.exists(filepath):
        try:
            os.remove(filepath)
        except OSError:
            pass
