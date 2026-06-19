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


def test_parquet_advice_recommends_zstd(client: TestClient, token: str) -> None:
    table = _table(client, token, "analytics.events")
    response = client.get(
        f"/api/v1/tables/{table['id']}/parquet-advice", headers=_auth(token)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["recommended_codec"] == "zstd"
    assert body["apply_operation_id"] == "set_parquet_settings"
    assert body["row_group_size_bytes"] > 0


def test_distribution_advice_for_small_file_table(client: TestClient, token: str) -> None:
    table = _table(client, token, "sales.orders")
    response = client.get(
        f"/api/v1/tables/{table['id']}/distribution-advice", headers=_auth(token)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["recommended_mode"] in {"hash", "range", "none"}
    assert "write.distribution-mode" in body["ingestion_hint"]


def test_tuning_operation_descriptors_registered(client: TestClient, token: str) -> None:
    response = client.get(
        "/api/v1/operations/descriptors", headers=_auth(token)
    )
    assert response.status_code == 200
    ids = {op["id"] for op in response.json()}
    assert {"set_parquet_settings", "rewrite_parquet_encoding", "set_write_distribution"} <= ids
