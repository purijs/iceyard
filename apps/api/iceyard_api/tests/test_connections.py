from fastapi.testclient import TestClient


def test_connection_lifecycle(client: TestClient, token: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    env = client.post(
        "/api/v1/environments",
        json={"name": "dev", "kind": "dev", "region": "eu-central-1"},
        headers=headers,
    )
    assert env.status_code == 201, env.text
    env_id = env.json()["id"]

    connection = client.post(
        "/api/v1/connections/catalogs",
        json={
            "environment_id": env_id,
            "name": "dev-catalog",
            "catalog_type": "rest",
            "endpoint": "https://catalog.example.com",
            "warehouse": "s3://dev-lakehouse",
        },
        headers=headers,
    )
    assert connection.status_code == 201, connection.text
    connection_id = connection.json()["id"]
    assert connection.json()["capabilities"]["supports_credential_vending"] is True

    test = client.post(
        f"/api/v1/connections/catalogs/{connection_id}/test",
        headers=headers,
    )
    assert test.status_code == 200
    assert test.json()["status"] == "ok"

    audit = client.get("/api/v1/audit", headers=headers)
    assert audit.status_code == 200
    assert any(event["action"] == "connection.catalog.create" for event in audit.json())
