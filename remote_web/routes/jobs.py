"""GET /api/progress/<id>, POST /api/cancel/<id>, GET /api/download-file/<id>.

remote_web always operates in "stream the finished file back" mode - no
is_local_request() branch exists anywhere in this file, unlike
backend/app.py's equivalents. download_file needs no zip-vs-single-file
special case: Flask's send_file() already infers the right Content-Type
from the file extension, whether that's video.mp4 or batch.zip.
"""

import os
import shutil

from flask import Blueprint, after_this_request, jsonify, send_file

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

    @after_this_request
    def cleanup(response):
        shutil.rmtree(os.path.dirname(filepath), ignore_errors=True)
        return response

    return send_file(filepath, as_attachment=True, download_name=job["filename"])
