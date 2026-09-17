"""GET /api/progress/<id>, POST /api/cancel/<id>, GET /api/download-file/<id>.

remote_web always operates in "stream the finished file back" mode - no
is_local_request() branch exists anywhere in this file, unlike
backend/app.py's equivalents. download_file needs no zip-vs-single-file
special case: Flask's send_file() already infers the right Content-Type
from the file extension, whether that's video.mp4 or batch.zip.
"""

import os

from flask import Blueprint, jsonify, send_file

from backend import jobs

bp = Blueprint("jobs", __name__)


@bp.get("/api/progress/<job_id>")
def progress(job_id):
    job = jobs.jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404
    return jsonify({
        "status": job["status"], "percent": job["percent"], "text": job["text"],
        "filename": job["filename"],
        "item": job.get("item"), "total": job.get("total"),
        "saved_count": job.get("saved_count"),
        "items_progress": job.get("items_progress"),
    })


@bp.post("/api/cancel/<job_id>")
def cancel(job_id):
    job = jobs.jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404
    job["cancelled"] = True
    return jsonify({"ok": True})


@bp.get("/api/download-file/<job_id>")
def download_file(job_id):
    job = jobs.jobs.get(job_id)
    if not job or job["status"] != "done":
        return jsonify({"error": "File not ready"}), 404
    filepath = job.get("filepath")
    if not filepath or not os.path.isfile(filepath):
        return jsonify({"error": "File not found"}), 404

    # Deliberately NOT deleted here on the first successful stream (that used
    # to 404 a client retrying the same job - e.g. the user backed out of the
    # OS share sheet, or picked "Save to Files" and wants to also AirDrop it,
    # and tapping Download again just got "File not found" with no recovery
    # but re-pasting the link - MISTAKES.md 2026-09-17). reaper.py's
    # mtime-based sweep already exists to clean up a finished-but-unfetched
    # job after REAPER_STALE_MINUTES; it cleans up an already-fetched one on
    # the same schedule now too, giving a real retry window instead of none.
    return send_file(filepath, as_attachment=True, download_name=job["filename"])
