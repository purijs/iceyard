from fastapi.testclient import TestClient

from iceyard_api.core.ratelimit import FixedWindowRateLimiter


def test_security_headers_present(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert (
        response.headers.get("content-security-policy")
        == "default-src 'none'; frame-ancestors 'none'"
    )


def test_correlation_id_echoed(client: TestClient) -> None:
    response = client.get("/healthz", headers={"x-correlation-id": "corr-123"})
    assert response.headers.get("x-correlation-id") == "corr-123"
    assert response.headers.get("x-request-id") == "corr-123"


def test_correlation_id_generated_when_absent(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.headers.get("x-request-id")


def test_rate_limiter_blocks_after_max() -> None:
    limiter = FixedWindowRateLimiter(max_attempts=2, window_seconds=60)
    assert limiter.allow("ip", now=0.0) is True
    assert limiter.allow("ip", now=1.0) is True
    assert limiter.allow("ip", now=2.0) is False  # third within window
    assert limiter.allow("ip", now=61.0) is True  # window slid


def test_bearer_request_bypasses_csrf(client: TestClient, token: str) -> None:
    # Mutating request with a Bearer header is CSRF-exempt and proceeds normally.
    response = client.post(
        "/api/v1/operations/dry-run",
        json={"operation_id": "meta_files", "engine": "spark", "params": {}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code in {200, 422}  # not a 403 CSRF block


def test_cookie_request_without_csrf_is_blocked(client: TestClient) -> None:
    # Establish a session cookie (login sets iceyard_session + iceyard_csrf in the jar).
    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
    assert login.status_code == 200, login.text
    # Drop the CSRF cookie so the double-submit check fails; keep the session cookie.
    client.cookies.delete("iceyard_csrf")
    response = client.post(
        "/api/v1/operations/dry-run",
        json={"operation_id": "meta_files", "engine": "spark", "params": {}},
    )
    assert response.status_code == 403
    assert "csrf" in response.json()["detail"].lower()


def test_cookie_request_with_matching_csrf_passes(client: TestClient) -> None:
    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
    assert login.status_code == 200, login.text
    csrf = client.cookies.get("iceyard_csrf")
    assert csrf
    response = client.post(
        "/api/v1/operations/dry-run",
        json={"operation_id": "meta_files", "engine": "spark", "params": {}},
        headers={"x-csrf-token": csrf},
    )
    assert response.status_code != 403


def test_job_carries_correlation_id(client: TestClient, token: str) -> None:
    tables = client.get("/api/v1/tables", headers={"Authorization": f"Bearer {token}"})
    table_id = tables.json()[0]["id"]
    run = client.post(
        f"/api/v1/tables/{table_id}/wap/run",
        json={"branch": "ingest-corr", "checks": [], "publish": "auto_if_green"},
        headers={"Authorization": f"Bearer {token}", "x-correlation-id": "wap-corr-1"},
    )
    assert run.status_code == 200, run.text
    jobs = client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {token}"})
    wap_jobs = [job for job in jobs.json() if job["kind"] == "wap"]
    assert any(job["correlation_id"] == "wap-corr-1" for job in wap_jobs)
