from fastapi.testclient import TestClient


def test_tables_health_and_operations(client: TestClient, token: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}

    tables = client.get("/api/v1/tables", headers=headers)
    assert tables.status_code == 200, tables.text
    table_rows = tables.json()
    assert table_rows
    risky_table = table_rows[0]

    dashboard = client.get("/api/v1/dashboard", headers=headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["table_count"] >= len(table_rows)

    health = client.get(f"/api/v1/tables/{risky_table['id']}/health", headers=headers)
    assert health.status_code == 200
    assert health.json()["dimensions"]

    descriptors = client.get("/api/v1/operations/descriptors", headers=headers)
    assert descriptors.status_code == 200
    operation_ids = {operation["id"] for operation in descriptors.json()}
    assert {"rewrite_data_files", "remove_orphan_files", "expire_snapshots"} <= operation_ids

    dry_run = client.post(
        "/api/v1/operations/dry-run",
        json={
            "operation_id": "rewrite_data_files",
            "table_id": risky_table["id"],
            "params": {"strategy": "binpack", "where": "occurred_at >= DATE '2026-06-01'"},
        },
        headers=headers,
    )
    assert dry_run.status_code == 200, dry_run.text
    assert "rewrite_data_files" in dry_run.json()["compiled_command"]

    execute = client.post(
        "/api/v1/operations/execute",
        json={"dry_run_id": dry_run.json()["id"]},
        headers=headers,
    )
    assert execute.status_code == 200, execute.text
    assert execute.json()["status"] == "queued"

    jobs = client.get("/api/v1/jobs", headers=headers)
    assert jobs.status_code == 200
    assert jobs.json()


def test_destructive_operation_requires_approval(client: TestClient, token: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    table = client.get("/api/v1/tables", headers=headers).json()[0]
    dry_run = client.post(
        "/api/v1/operations/dry-run",
        json={
            "operation_id": "remove_orphan_files",
            "table_id": table["id"],
            "params": {"older_than": "2026-06-01 00:00:00"},
        },
        headers=headers,
    )
    assert dry_run.status_code == 200, dry_run.text
    execute = client.post(
        "/api/v1/operations/execute",
        json={"dry_run_id": dry_run.json()["id"], "confirmation": "remove_orphan_files"},
        headers=headers,
    )
    assert execute.status_code == 200
    assert execute.json()["status"] == "requires_approval"

    approvals = client.get("/api/v1/approvals", headers=headers)
    assert approvals.status_code == 200
    assert approvals.json()[0]["status"] == "pending"
