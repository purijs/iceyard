from fastapi.testclient import TestClient


def test_tables_health_and_operations(client: TestClient, token: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}

    tables = client.get("/api/v1/tables", headers=headers)
    assert tables.status_code == 200, tables.text
    table_rows = tables.json()
    assert table_rows
    risky_table = table_rows[0]

    refresh = client.post("/api/v1/tables/index/refresh", json={}, headers=headers)
    assert refresh.status_code == 200, refresh.text
    assert refresh.json()["table_count"] >= len(table_rows)

    namespaces = client.get("/api/v1/tables/namespaces", headers=headers)
    assert namespaces.status_code == 200
    assert {namespace["name"] for namespace in namespaces.json()} >= {"analytics", "sales"}

    catalogs = client.get("/api/v1/connections/catalogs", headers=headers)
    assert catalogs.status_code == 200
    catalog = catalogs.json()[0]
    catalog_tables = client.get(
        f"/api/v1/tables?catalog_connection_id={catalog['id']}", headers=headers
    )
    assert catalog_tables.status_code == 200
    assert catalog_tables.json()
    assert all(
        table["environment_id"] == catalog["environment_id"] for table in catalog_tables.json()
    )

    filtered = client.get("/api/v1/tables?max_health=55", headers=headers)
    assert filtered.status_code == 200
    assert all(table["health_score"] <= 55 for table in filtered.json())

    partitions = client.get(f"/api/v1/tables/{risky_table['id']}/partitions", headers=headers)
    assert partitions.status_code == 200
    assert partitions.json()[0]["is_current"] is True

    sort_orders = client.get(f"/api/v1/tables/{risky_table['id']}/sort-orders", headers=headers)
    assert sort_orders.status_code == 200
    assert sort_orders.json()[0]["fields"]

    dashboard = client.get("/api/v1/dashboard", headers=headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["table_count"] >= len(table_rows)

    health = client.get(f"/api/v1/tables/{risky_table['id']}/health", headers=headers)
    assert health.status_code == 200
    assert health.json()["dimensions"]

    descriptors = client.get("/api/v1/operations/descriptors", headers=headers)
    assert descriptors.status_code == 200
    assert len(descriptors.json()) >= 75
    operation_ids = {operation["id"] for operation in descriptors.json()}
    assert {"rewrite_data_files", "remove_orphan_files", "expire_snapshots"} <= operation_ids

    seed = client.post("/api/v1/operations/descriptors/seed", headers=headers)
    assert seed.status_code == 200, seed.text
    assert seed.json()["inserted"] >= 1

    categories = client.get("/api/v1/operations/descriptors/categories", headers=headers)
    assert categories.status_code == 200
    assert any(category["name"] == "Maintenance" for category in categories.json())

    descriptor = client.get("/api/v1/operations/descriptors/rewrite_data_files", headers=headers)
    assert descriptor.status_code == 200
    assert descriptor.json()["safety_class"] == "REWRITE"

    namespace_dry_run = client.post(
        "/api/v1/operations/dry-run",
        json={"operation_id": "create_namespace", "params": {"namespace": "sandbox"}},
        headers=headers,
    )
    assert namespace_dry_run.status_code == 200, namespace_dry_run.text

    missing_table = client.post(
        "/api/v1/operations/dry-run",
        json={"operation_id": "rewrite_data_files", "params": {"strategy": "binpack"}},
        headers=headers,
    )
    assert missing_table.status_code == 422

    preview = client.get(
        f"/api/v1/tables/{risky_table['id']}/preview?resource=refs", headers=headers
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["rows"]

    unsupported = client.post(
        "/api/v1/operations/dry-run",
        json={
            "operation_id": "rewrite_data_files",
            "table_id": risky_table["id"],
            "engine": "flink",
            "params": {"strategy": "binpack"},
        },
        headers=headers,
    )
    assert unsupported.status_code == 400

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

    missing_idempotency = client.post(
        "/api/v1/operations/execute",
        json={"dry_run_id": dry_run.json()["id"]},
        headers=headers,
    )
    assert missing_idempotency.status_code == 200
    assert missing_idempotency.json()["status"] == "blocked"

    execute = client.post(
        "/api/v1/operations/execute",
        json={"dry_run_id": dry_run.json()["id"], "idempotency_key": "rewrite-events-1"},
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
