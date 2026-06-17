from fastapi.testclient import TestClient


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _table(client: TestClient, token: str, name: str) -> dict[str, object]:
    response = client.get("/api/v1/tables", headers=_auth(token))
    assert response.status_code == 200, response.text
    for table in response.json():
        if table["name"] == name:
            return table
    raise AssertionError(f"table {name} not found")


def test_wap_publishes_when_green(client: TestClient, token: str) -> None:
    table = _table(client, token, "analytics.events")
    response = client.post(
        f"/api/v1/tables/{table['id']}/wap/run",
        json={
            "branch": "ingest-2026-06-17",
            "checks": [{"type": "rowcount", "params": {"min": 1}}],
            "publish": "auto_if_green",
            "tag_on_publish": "release-2026.06.17",
        },
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["green"] is True
    assert body["status"] == "published"
    assert "fast_forward" in body["compiled_publish_command"]
    assert body["publish_tag"] == "release-2026.06.17"


def test_wap_holds_when_check_fails(client: TestClient, token: str) -> None:
    table = _table(client, token, "analytics.events")
    response = client.post(
        f"/api/v1/tables/{table['id']}/wap/run",
        json={
            "branch": "ingest-bad",
            "checks": [{"type": "rowcount", "params": {"min": 10_000_000}}],
            "publish": "auto_if_green",
        },
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["green"] is False
    assert body["status"] == "held"
    assert body["compiled_publish_command"] is None


def test_wap_marks_engine_only_checks_skipped(client: TestClient, token: str) -> None:
    table = _table(client, token, "analytics.events")
    response = client.post(
        f"/api/v1/tables/{table['id']}/wap/run",
        json={
            "branch": "ingest-x",
            "checks": [{"type": "not_null", "params": {"columns": ["user_id"]}}],
            "publish": "require_approval",
        },
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["check_results"][0]["status"] == "skipped"
    assert body["status"] == "requires_approval"  # green (no failures) but gated


def test_wap_run_creates_job(client: TestClient, token: str) -> None:
    table = _table(client, token, "analytics.events")
    run = client.post(
        f"/api/v1/tables/{table['id']}/wap/run",
        json={"branch": "ingest-job", "checks": [], "publish": "auto_if_green"},
        headers=_auth(token),
    )
    assert run.status_code == 200, run.text
    jobs = client.get("/api/v1/jobs", headers=_auth(token))
    assert jobs.status_code == 200
    kinds = {job["kind"] for job in jobs.json()}
    assert "wap" in kinds
