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


def test_retention_simulation_excludes_protected_snapshots(client: TestClient, token: str) -> None:
    table = _table(client, token, "analytics.events")
    response = client.post(
        f"/api/v1/tables/{table['id']}/retention/simulate",
        json={"older_than": "2026-06-13 00:00:00", "retain_last": 1},
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    # Fixtures tag snapshot 7588120049923847 (pre-compaction-restore) + a release tag.
    assert body["expiring_count"] >= 0
    assert body["reclaimable_basis"] == "estimate_from_summary"
    protected_ids = {snap["snapshot_id"] for snap in body["protected_excluded"]}
    expiring_ids = {snap["snapshot_id"] for snap in body["expiring"]}
    assert protected_ids.isdisjoint(expiring_ids)


def test_cleanup_preview_guardrail_blocks_large_delete(client: TestClient, token: str) -> None:
    table = _table(client, token, "analytics.events")
    response = client.post(
        f"/api/v1/tables/{table['id']}/cleanup/preview",
        json={"time_column": "occurred_at", "keep_days": 1, "mode": "hard", "max_delete_pct": 1},
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["estimated_delete_pct"] >= 0
    assert body["guardrail_passed"] is False  # tiny keep + tiny pct => blocked
    assert [step["name"] for step in body["plan"]][:1] == ["delete"]
    assert "expire" in [step["name"] for step in body["plan"]]  # hard mode chain


def test_cleanup_preview_partition_aligned_for_event_time(client: TestClient, token: str) -> None:
    table = _table(client, token, "analytics.events")
    response = client.post(
        f"/api/v1/tables/{table['id']}/cleanup/preview",
        json={"time_column": "occurred_at", "keep_days": 30, "mode": "soft"},
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["partition_aligned"] is True  # fixtures partition by days(occurred_at)
    assert body["recommend_partitioning"] is False


def test_retention_operation_descriptors_registered(client: TestClient, token: str) -> None:
    response = client.get("/api/v1/operations/descriptors", headers=_auth(token))
    assert response.status_code == 200
    ids = {op["id"] for op in response.json()}
    assert {"cleanup_old_data", "backfill_default"} <= ids
