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


def test_download_file_streams_and_cleans_up_the_temp_dir(client, tmp_path):
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
    assert not job_dir.exists()  # cleaned up after streaming


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
    assert not job_dir.exists()
