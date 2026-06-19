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
            "name": "catalog-a",
            "catalog_type": "rest",
            "endpoint": "https://catalog.internal",
            "warehouse": "s3://warehouse-a",
        },
        headers=headers,
    )
    assert connection.status_code == 201, connection.text
    connection_id = connection.json()["id"]
    assert connection.json()["capabilities"]["supports_credential_vending"] is True

    updated = client.patch(
        f"/api/v1/connections/catalogs/{connection_id}",
        json={"name": "dev-rest", "is_enabled": False},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "dev-rest"
    assert updated.json()["is_enabled"] is False

    test = client.post(
        f"/api/v1/connections/catalogs/{connection_id}/test",
        headers=headers,
    )
    assert test.status_code == 200
    assert test.json()["status"] in {"warning", "failed"}
    assert {component["name"] for component in test.json()["components"]} >= {
        "catalog metadata",
        "catalog auth",
        "catalog reachability",
    }

    secret = client.post(
        "/api/v1/secrets/references",
        json={"name": "catalog-role", "provider": "vault", "reference": "secret/data/catalog"},
        headers=headers,
    )
    assert secret.status_code == 201, secret.text
    assert secret.json()["has_reference"] is True
    assert "reference" not in secret.json()

    store = client.post(
        "/api/v1/connections/object-stores",
        json={
            "environment_id": env_id,
            "name": "dev-store",
            "store_type": "s3",
            "region": "eu-central-1",
            "auth_ref": "catalog-role",
            "settings": {
                "warehouse": "s3://warehouse-a",
                "storage_auth": {
                    "mode": "static_key",
                    "aws_access_key_id": "AKIAEXAMPLE",
                    "aws_secret_access_key": "secret-value",
                },
            },
        },
        headers=headers,
    )
    assert store.status_code == 201, store.text
    store_id = store.json()["id"]
    assert store.json()["settings"]["storage_auth"]["aws_secret_access_key_present"] is True
    assert "aws_secret_access_key" not in store.json()["settings"]["storage_auth"]

    local_store = client.post(
        "/api/v1/connections/object-stores",
        json={
            "environment_id": env_id,
            "name": "local-store",
            "store_type": "local",
            "settings": {
                "warehouse": "/tmp/iceyard-warehouse",
                "storage_auth": {"mode": "keyless"},
            },
        },
        headers=headers,
    )
    assert local_store.status_code == 201, local_store.text
    local_store_id = local_store.json()["id"]

    store_test = client.post(
        f"/api/v1/connections/object-stores/{local_store_id}/test",
        headers=headers,
    )
    assert store_test.status_code == 200
    assert {component["name"] for component in store_test.json()["components"]} >= {
        "storage location",
        "storage auth",
        "storage reachability",
    }

    backend = client.post(
        "/api/v1/connections/compute-backends",
        json={"environment_id": env_id, "name": "duckdb", "backend_type": "duckdb"},
        headers=headers,
    )
    assert backend.status_code == 201, backend.text
    backend_id = backend.json()["id"]

    stores = client.get("/api/v1/connections/object-stores", headers=headers)
    assert stores.json()[0]["id"] == store_id
    assert (
        client.get("/api/v1/connections/compute-backends", headers=headers).json()[0]["id"]
        == backend_id
    )

    blocked_delete = client.delete(f"/api/v1/environments/{env_id}", headers=headers)
    assert blocked_delete.status_code == 400

    deleted_catalog = client.delete(
        f"/api/v1/connections/catalogs/{connection_id}", headers=headers
    )
    assert deleted_catalog.status_code == 204
    deleted_store = client.delete(
        f"/api/v1/connections/object-stores/{store_id}", headers=headers
    )
    assert deleted_store.status_code == 204
    deleted_local_store = client.delete(
        f"/api/v1/connections/object-stores/{local_store_id}", headers=headers
    )
    assert deleted_local_store.status_code == 204
    deleted_backend = client.delete(
        f"/api/v1/connections/compute-backends/{backend_id}", headers=headers
    )
    assert deleted_backend.status_code == 204
    assert client.delete(f"/api/v1/environments/{env_id}", headers=headers).status_code == 204

    audit = client.get("/api/v1/audit", headers=headers)
    assert audit.status_code == 200
    actions = {event["action"] for event in audit.json()}
    assert {
        "connection.catalog.create",
        "connection.catalog.update",
        "secret_reference.create",
        "connection.object_store.create",
        "connection.compute.create",
        "environment.delete",
    } <= actions
