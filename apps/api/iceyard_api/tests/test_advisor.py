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


def test_clustering_advice_with_hints_picks_zorder(client: TestClient, token: str) -> None:
    table = _table(client, token, "analytics.events")
    response = client.post(
        f"/api/v1/tables/{table['id']}/clustering-advice",
        json={
            "workload_source": "hints",
            "hints": {"filter_cols": ["user_id", "event_type"]},
            "mode": "recommend",
        },
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["workload_basis"] == "workload hints"
    rec = body["recommendations"][0]
    assert rec["strategy"] in {"sort", "zorder"}
    assert rec["apply_params"]["sort_order"] == rec["sort_order_expr"]
    assert rec["projected_scan_reduction_pct"] >= 0


def test_clustering_advice_without_hints_uses_hygiene(client: TestClient, token: str) -> None:
    table = _table(client, token, "sales.orders")
    response = client.post(
        f"/api/v1/tables/{table['id']}/clustering-advice",
        json={"workload_source": "none"},
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["workload_basis"].startswith("layout hygiene")


def test_materialized_view_advice_reports_engine_support(client: TestClient, token: str) -> None:
    table = _table(client, token, "analytics.events")
    response = client.get(
        f"/api/v1/tables/{table['id']}/materialized-view-advice?engine=glue",
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["engine_native_supported"] is True
    assert body["fallback_operation_id"] == "create_summary_table"


def test_summary_table_descriptors_registered(client: TestClient, token: str) -> None:
    response = client.get("/api/v1/operations/descriptors", headers=_auth(token))
    assert response.status_code == 200
    ids = {op["id"] for op in response.json()}
    assert {"create_summary_table", "refresh_summary_table"} <= ids
