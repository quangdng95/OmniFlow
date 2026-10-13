"""GET /api/progress/<id>, POST /api/cancel/<id>, GET /api/download-file/<id>."""

import os

import pytest

from backend import jobs as jobs_module
from remote_web import config
from remote_web.app import app as remote_app


@pytest.fixture
def client(isolated_state_file):
    remote_app.config["TESTING"] = True
    return remote_app.test_client()


@pytest.fixture(autouse=True)
def trusted(client):
    token = config.get_or_create_token()
    client.post("/unlock", data={"token": token})
    return client


@pytest.fixture(autouse=True)
def clear_jobs():
    jobs_module.jobs.clear()
    yield
    jobs_module.jobs.clear()


def test_progress_requires_trust():
    remote_app.config["TESTING"] = True
    anon_client = remote_app.test_client()
    resp = anon_client.get("/api/progress/doesnotmatter")
    assert resp.status_code == 401


def test_progress_unknown_job_returns_404(client):
    resp = client.get("/api/progress/unknown-job-id")
    assert resp.status_code == 404


def test_progress_returns_job_fields(client):
    jobs_module.jobs["job1"] = {
        "status": "running", "percent": 42.0, "text": "Downloading...",
        "filename": None, "item": 1, "total": 3, "saved_count": None, "items_progress": None,
    }
    resp = client.get("/api/progress/job1")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "running"
    assert body["percent"] == 42.0
    assert body["item"] == 1
    assert body["total"] == 3


def test_cancel_unknown_job_returns_404(client):
    resp = client.post("/api/cancel/unknown-job-id")
    assert resp.status_code == 404


def test_cancel_sets_the_cancelled_flag(client):
    jobs_module.jobs["job1"] = {"status": "running", "cancelled": False}
    resp = client.post("/api/cancel/job1")
    assert resp.status_code == 200
    assert jobs_module.jobs["job1"]["cancelled"] is True


def test_download_file_not_ready_returns_404(client):
    jobs_module.jobs["job1"] = {"status": "running", "filepath": None, "filename": None}
    resp = client.get("/api/download-file/job1")
    assert resp.status_code == 404


def test_download_file_streams_the_file(client, tmp_path):
    job_dir = tmp_path / "omniflow-remote-abc123"
    job_dir.mkdir()
    file_path = job_dir / "video.mp4"
    file_path.write_bytes(b"fake mp4 bytes")
    jobs_module.jobs["job1"] = {
        "status": "done", "filepath": str(file_path), "filename": "video.mp4",
    }
    resp = client.get("/api/download-file/job1")
    assert resp.status_code == 200
    assert resp.data == b"fake mp4 bytes"


def test_download_file_serves_a_zip_the_same_way_as_a_single_file(client, tmp_path):
    job_dir = tmp_path / "omniflow-remote-batch-abc123"
    job_dir.mkdir()
    zip_path = job_dir / "batch.zip"
    zip_path.write_bytes(b"PK\x03\x04fake zip bytes")
    jobs_module.jobs["job1"] = {
        "status": "done", "filepath": str(zip_path), "filename": "batch.zip",
    }
    resp = client.get("/api/download-file/job1")
    assert resp.status_code == 200
    assert resp.data == b"PK\x03\x04fake zip bytes"


def test_download_file_can_be_fetched_a_second_time(client, tmp_path):
    # A client backing out of the OS share sheet (or wanting to save it
    # somewhere else too) taps Download again for the same finished job -
    # this used to 404 because the first successful stream deleted the file
    # immediately (regression pin, MISTAKES.md 2026-09-17).
    job_dir = tmp_path / "omniflow-remote-abc123"
    job_dir.mkdir()
    file_path = job_dir / "video.mp4"
    file_path.write_bytes(b"fake mp4 bytes")
    jobs_module.jobs["job1"] = {
        "status": "done", "filepath": str(file_path), "filename": "video.mp4",
    }
    first = client.get("/api/download-file/job1")
    second = client.get("/api/download-file/job1")
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.data == b"fake mp4 bytes"


# ---- streaming contract: the browser downloads this URL straight to disk ----

def _done_job(tmp_path, filename, payload=b"0123456789" * 100):
    job_dir = tmp_path / "omniflow-remote-stream"
    job_dir.mkdir()
    file_path = job_dir / "stored.mp4"
    file_path.write_bytes(payload)
    jobs_module.jobs["job1"] = {"status": "done", "filepath": str(file_path), "filename": filename}
    return payload


def test_download_file_sends_length_range_support_and_attachment_headers(client, tmp_path):
    payload = _done_job(tmp_path, "video.mp4")
    resp = client.get("/api/download-file/job1")
    assert resp.headers["Content-Length"] == str(len(payload))
    assert resp.headers["Accept-Ranges"] == "bytes"
    assert resp.headers["Content-Disposition"].startswith("attachment;")
    assert 'filename=video.mp4' in resp.headers["Content-Disposition"]


def test_download_file_answers_a_range_request_with_206(client, tmp_path):
    payload = _done_job(tmp_path, "video.mp4")
    resp = client.get("/api/download-file/job1", headers={"Range": "bytes=10-19"})
    assert resp.status_code == 206
    assert resp.data == payload[10:20]
    assert resp.headers["Content-Range"] == f"bytes 10-19/{len(payload)}"


def test_download_file_unicode_name_gets_a_utf8_filename_star(client, tmp_path):
    _done_job(tmp_path, "한국어 영상 – Tiếng Việt.mp4")
    disposition = client.get("/api/download-file/job1").headers["Content-Disposition"]
    assert "filename*=UTF-8''" in disposition
    assert "%ED%95%9C%EA%B5%AD%EC%96%B4" in disposition  # 한국어
    assert "Ti%E1%BA%BFng" in disposition  # Tiếng
    assert disposition.encode("latin-1")  # the whole header is plain ASCII/latin-1 safe


def test_download_file_is_streamed_not_buffered(client, tmp_path):
    _done_job(tmp_path, "video.mp4")
    resp = client.get("/api/download-file/job1", buffered=False)
    assert resp.is_streamed


def test_download_file_missing_on_disk_returns_404(client, tmp_path):
    _done_job(tmp_path, "video.mp4")
    os.remove(jobs_module.jobs["job1"]["filepath"])
    assert client.get("/api/download-file/job1").status_code == 404


def test_download_file_path_traversal_in_job_id_is_not_served(client, tmp_path):
    _done_job(tmp_path, "video.mp4")
    for evil in ("../../etc/passwd", "..%2F..%2Fetc%2Fpasswd", "job1/../../../etc/passwd"):
        resp = client.get(f"/api/download-file/{evil}")
        assert resp.status_code in (404, 308)
        assert b"root:" not in resp.data


def test_download_file_requires_trust():
    remote_app.config["TESTING"] = True
    assert remote_app.test_client().get("/api/download-file/job1").status_code == 401
