import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_job_status_returns_saved_manifest(tmp_path, monkeypatch):
    job_id = "a" * 32
    job_dir = tmp_path / "outputs" / "jobs" / job_id
    job_dir.mkdir(parents=True)

    manifest = {
        "status": "needs_assets",
        "progress": 50,
        "rendered": False,
        "video": None,
        "error": None,
        "scene_count": 2,
        "assets": [{}, {}],
    }

    (job_dir / "manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    response = client.get(f"/api/v1/jobs/{job_id}")

    assert response.status_code == 200
    assert response.json()["job_id"] == job_id
    assert response.json()["status"] == "needs_assets"
    assert response.json()["rendered"] is False
    assert response.json()["video"] is None
    assert response.json()["scene_count"] == 2
    assert response.json()["progress"] == 50
    assert response.json()["error"] is None


def test_job_status_returns_404_for_unknown_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    response = client.get(
        "/api/v1/jobs/00000000000000000000000000000000"
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "JOB_NOT_FOUND"


def test_job_status_returns_400_for_invalid_id():
    response = client.get("/api/v1/jobs/abc")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_JOB_ID"



def test_job_status_returns_500_for_corrupted_manifest(tmp_path, monkeypatch):
    job_id = "b" * 32
    job_dir = tmp_path / "outputs" / "jobs" / job_id
    job_dir.mkdir(parents=True)

    (job_dir / "manifest.json").write_text(
        "{invalid json",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    response = client.get(f"/api/v1/jobs/{job_id}")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "MANIFEST_READ_FAILED"


def test_job_status_accepts_uppercase_job_id(tmp_path, monkeypatch):
    job_id = "a" * 32
    job_dir = tmp_path / "outputs" / "jobs" / job_id
    job_dir.mkdir(parents=True)

    manifest = {
        "status": "needs_assets",
        "rendered": False,
        "video": None,
        "assets": [],
    }

    import json

    (job_dir / "manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    response = client.get(f"/api/v1/jobs/{job_id.upper()}")

    assert response.status_code == 200
    assert response.json()["status"] == "needs_assets"



def test_render_endpoint_creates_background_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    response = client.post(
        "/api/v1/render",
        json={
            "script": (
                "Artificial intelligence helps doctors analyze medical images. "
                "Robots assist surgeons during operations."
            ),
            "words_per_minute": 150,
            "minimum_scene_seconds": 2,
            "aspect_ratio": "16:9",
        },
    )

    assert response.status_code == 202

    data = response.json()
    job_id = data["job_id"]

    assert len(job_id) == 32
    assert data["status"] == "queued"
    assert data["progress"] == 0

    manifest_path = (
        tmp_path / "outputs" / "jobs" / job_id / "manifest.json"
    )
    assert manifest_path.is_file()


def test_broll_jobs_endpoint_accepts_script():
    response = client.post(
        "/api/v1/broll/jobs",
        json={
            "script": (
                "Artificial intelligence helps doctors analyze medical images. "
                "Robots assist surgeons during operations."
            ),
            "aspect_ratios": ["16:9"],
            "captions": {
                "burn_in": False,
                "srt": True,
            },
        },
    )

    assert response.status_code == 202

    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    assert data["progress"] == 0



def test_broll_jobs_passes_all_aspect_ratios(monkeypatch):
    from app import main

    captured = {}

    def fake_process_render_job(job_id, request):
        captured["job_id"] = job_id
        captured["request"] = request

    monkeypatch.setattr(
        main,
        "process_render_job",
        fake_process_render_job,
    )

    response = client.post(
        "/api/v1/broll/jobs",
        json={
            "script": "AI helps doctors analyze medical images.",
            "aspect_ratios": ["16:9", "9:16", "1:1"],
        },
    )

    assert response.status_code == 202
    assert captured["request"].aspect_ratios == [
        "16:9",
        "9:16",
        "1:1",
    ]





def test_correlation_id_is_generated_when_missing():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers.get("X-Correlation-Id")


def test_correlation_id_is_preserved():
    correlation_id = "test-correlation-123"

    response = client.get(
        "/health",
        headers={"X-Correlation-Id": correlation_id},
    )

    assert response.status_code == 200
    assert response.headers["X-Correlation-Id"] == correlation_id


def test_long_correlation_id_is_replaced():
    response = client.get(
        "/health",
        headers={"X-Correlation-Id": "x" * 129},
    )

    assert response.status_code == 200
    assert response.headers.get("X-Correlation-Id")
    assert response.headers["X-Correlation-Id"] != "x" * 129
