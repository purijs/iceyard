from fastapi.testclient import TestClient


def test_schema_endpoint_emits_table_schema_with_fields(client: TestClient, token: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    tables = client.get("/api/v1/tables", headers=headers)
    assert tables.status_code == 200, tables.text
    table_id = tables.json()[0]["id"]

    response = client.get(f"/api/v1/tables/{table_id}/schema", headers=headers)
    assert response.status_code == 200, response.text
    versions = response.json()
    assert versions, "expected at least one schema version"
    latest = versions[-1]
    # The client reads `table_schema.fields`; the response must use that key (not `schema`).
    assert "table_schema" in latest
    assert "schema" not in latest
    assert isinstance(latest["table_schema"].get("fields"), list)
