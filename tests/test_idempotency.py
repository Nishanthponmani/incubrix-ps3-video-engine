
from fastapi.testclient import TestClient

from app.main import app
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

client = TestClient(app)


def test_render_same_idempotency_key_returns_original_response():
    payload = {
        "script": "A short test script for rendering.",
    }
    headers = {"Idempotency-Key": "render-retry-test-001"}

    first_response = client.post(
        "/api/v1/render",
        json=payload,
        headers=headers,
    )
    second_response = client.post(
        "/api/v1/render",
        json=payload,
        headers=headers,
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert first_response.json() == second_response.json()


def test_render_reused_key_with_different_payload_returns_409():
    headers = {"Idempotency-Key": "render-conflict-test-001"}

    first_response = client.post(
        "/api/v1/render",
        json={"script": "First script."},
        headers=headers,
    )
    second_response = client.post(
        "/api/v1/render",
        json={"script": "A different script."},
        headers=headers,
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 409
    assert (
    second_response.json()["error"]["code"]
    == "IDEMPOTENCY_KEY_REUSED"
    )



def test_broll_job_same_idempotency_key_returns_original_response():
    payload = {
        "script": "A short test script for a B-roll job.",
    }
    headers = {"Idempotency-Key": "broll-retry-test-001"}

    first_response = client.post(
        "/api/v1/broll/jobs",
        json=payload,
        headers=headers,
    )
    second_response = client.post(
        "/api/v1/broll/jobs",
        json=payload,
        headers=headers,
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert first_response.json() == second_response.json()


def test_broll_job_reused_key_with_different_payload_returns_409():
    headers = {"Idempotency-Key": "broll-conflict-test-001"}

    first_response = client.post(
        "/api/v1/broll/jobs",
        json={"script": "First B-roll script."},
        headers=headers,
    )
    second_response = client.post(
        "/api/v1/broll/jobs",
        json={"script": "A different B-roll script."},
        headers=headers,
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 409
    assert (
        second_response.json()["error"]["code"]
        == "IDEMPOTENCY_KEY_REUSED"
    )



def test_plan_same_idempotency_key_returns_original_response():
    payload = {
        "script": "A short script about technology and innovation.",
    }
    headers = {"Idempotency-Key": "plan-retry-test-001"}

    first_response = client.post(
        "/api/v1/plan",
        json=payload,
        headers=headers,
    )
    second_response = client.post(
        "/api/v1/plan",
        json=payload,
        headers=headers,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json() == second_response.json()


def test_plan_reused_key_with_different_payload_returns_409():
    headers = {"Idempotency-Key": "plan-conflict-test-001"}

    first_response = client.post(
        "/api/v1/plan",
        json={"script": "A script about technology."},
        headers=headers,
    )
    second_response = client.post(
        "/api/v1/plan",
        json={"script": "A script about nature."},
        headers=headers,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    assert (
        second_response.json()["error"]["code"]
        == "IDEMPOTENCY_KEY_REUSED"
    )


def test_script_same_idempotency_key_returns_original_response():
    payload = {
        "script": "A short script about technology and innovation.",
    }
    headers = {"Idempotency-Key": "script-retry-test-001"}

    first_response = client.post(
        "/api/v1/script",
        json=payload,
        headers=headers,
    )
    second_response = client.post(
        "/api/v1/script",
        json=payload,
        headers=headers,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json() == second_response.json()


def test_script_reused_key_with_different_payload_returns_409():
    headers = {"Idempotency-Key": "script-conflict-test-001"}

    first_response = client.post(
        "/api/v1/script",
        json={"script": "A script about technology."},
        headers=headers,
    )
    second_response = client.post(
        "/api/v1/script",
        json={"script": "A script about nature."},
        headers=headers,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    assert (
        second_response.json()["error"]["code"]
        == "IDEMPOTENCY_KEY_REUSED"
    )


def test_concurrent_render_requests_with_same_key_create_one_job():
    payload = {
        "script": "A short script for a concurrent rendering test.",
    }
    headers = {"Idempotency-Key": "render-concurrent-test-001"}
    barrier = Barrier(2)

    def send_request():
        barrier.wait()
        return client.post(
            "/api/v1/render",
            json=payload,
            headers=headers,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(send_request),
            executor.submit(send_request),
        ]
        responses = [future.result() for future in futures]

    assert all(response.status_code == 202 for response in responses)
    assert responses[0].json()["job_id"] == responses[1].json()["job_id"]



def test_concurrent_plan_requests_with_same_key_return_same_response():
    payload = {
        "script": "A concurrent test script about technology and innovation.",
    }
    headers = {"Idempotency-Key": "plan-concurrent-test-001"}
    barrier = Barrier(2)

    def send_request():
        barrier.wait()
        return client.post(
            "/api/v1/plan",
            json=payload,
            headers=headers,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(send_request),
            executor.submit(send_request),
        ]
        responses = [future.result() for future in futures]

    assert all(response.status_code == 200 for response in responses)
    assert responses[0].json() == responses[1].json()



def test_concurrent_script_requests_with_same_key_return_same_response():
    payload = {
        "script": "A concurrent test script about technology and innovation.",
    }
    headers = {"Idempotency-Key": "script-concurrent-test-001"}
    barrier = Barrier(2)

    def send_request():
        barrier.wait()
        return client.post(
            "/api/v1/script",
            json=payload,
            headers=headers,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(send_request),
            executor.submit(send_request),
        ]
        responses = [future.result() for future in futures]

    assert all(response.status_code == 200 for response in responses)
    assert responses[0].json() == responses[1].json()



def test_concurrent_broll_requests_with_same_key_return_same_response():
    payload = {
        "script": "A concurrent test script for a B-roll video.",
    }
    headers = {"Idempotency-Key": "broll-concurrent-test-001"}
    barrier = Barrier(2)

    def send_request():
        barrier.wait()
        return client.post(
            "/api/v1/broll/jobs",
            json=payload,
            headers=headers,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(send_request),
            executor.submit(send_request),
        ]
        responses = [future.result() for future in futures]

    assert all(response.status_code == 202 for response in responses)
    assert responses[0].json() == responses[1].json()



def test_render_without_idempotency_key_creates_job():
    response = client.post(
        "/api/v1/render",
        json={
            "script": "A short test video.",
        },
    )

    assert response.status_code in (200, 202)
    data = response.json()
    assert "job_id" in data
