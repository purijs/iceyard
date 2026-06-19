import sys
import types

from fastapi.testclient import TestClient
from sqlalchemy import select

from iceyard_api.connections.service import ConnectionService
from iceyard_api.db.models import CatalogConnection, ObjectStoreConnection, SecretReference
from iceyard_api.db.session import SessionLocal
from iceyard_api.iceberg.live_metadata import LiveIcebergReader


def test_connection_lifecycle(client: TestClient, token: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    env = client.post(
        "/api/v1/environments",
        json={"name": "lifecycle-dev", "kind": "dev", "region": "eu-central-1"},
        headers=headers,
    )
    assert env.status_code == 201, env.text
    env_id = env.json()["id"]

    connection = client.post(
        "/api/v1/connections/catalogs",
        json={
            "environment_id": env_id,
            "name": "lifecycle-catalog",
            "catalog_type": "rest",
            "endpoint": "https://catalog.internal",
            "warehouse": "s3://warehouse-a",
        },
        headers=headers,
    )
    assert connection.status_code == 201, connection.text
    connection_id = connection.json()["id"]
    assert connection.json()["capabilities"]["supports_credential_vending"] is True

    jdbc_connection = client.post(
        "/api/v1/connections/catalogs",
        json={
            "environment_id": env_id,
            "name": "catalog-jdbc",
            "catalog_type": "jdbc",
            "endpoint": "jdbc:postgresql://database.internal:5432/iceberg_catalog",
            "warehouse": "s3://warehouse-a",
            "settings": {
                "jdbc_options": {
                    "sslmode": "require",
                    "application_name": "iceyard",
                }
            },
        },
        headers=headers,
    )
    assert jdbc_connection.status_code == 201, jdbc_connection.text
    jdbc_connection_id = jdbc_connection.json()["id"]
    assert jdbc_connection.json()["settings"]["jdbc_options"]["sslmode"] == "require"

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
    deleted_jdbc_catalog = client.delete(
        f"/api/v1/connections/catalogs/{jdbc_connection_id}", headers=headers
    )
    assert deleted_jdbc_catalog.status_code == 204
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


def test_catalog_connection_trims_inline_secret_values(
    client: TestClient, token: str
) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    env = client.post(
        "/api/v1/environments",
        json={"name": "tls-dev", "kind": "dev", "region": "eu-central-1"},
        headers=headers,
    )
    assert env.status_code == 201, env.text

    response = client.post(
        "/api/v1/connections/catalogs",
        json={
            "environment_id": env.json()["id"],
            "name": "catalog-with-secret",
            "catalog_type": "jdbc",
            "endpoint": "jdbc:postgresql://database.internal:5432/iceberg_catalog",
            "settings": {
                "catalog_auth": {
                    "mode": "basic",
                    "username": "postgres",
                    "password": " copied-password \n",
                }
            },
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text

    with SessionLocal() as session:
        connection = session.scalar(
            select(CatalogConnection).where(CatalogConnection.name == "catalog-with-secret")
        )
        assert connection is not None
        secret = session.scalar(
            select(SecretReference).where(SecretReference.id == connection.auth_ref)
        )
        assert secret is not None
        assert (
            ConnectionService(session)._read_inline_secret(connection.workspace_id, secret.id)[
                "password"
            ]
            == "copied-password"
        )


def test_jdbc_require_ssl_does_not_use_default_postgres_root_cert(
    client: TestClient, token: str, monkeypatch
) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    env = client.post(
        "/api/v1/environments",
        json={"name": "tls-prod", "kind": "prod", "region": "eu-central-1"},
        headers=headers,
    )
    assert env.status_code == 201, env.text
    response = client.post(
        "/api/v1/connections/catalogs",
        json={
            "environment_id": env.json()["id"],
            "name": "catalog-tls",
            "catalog_type": "jdbc",
            "endpoint": "jdbc:postgresql://database.internal:5432/iceberg_catalog",
            "settings": {
                "catalog_auth": {
                    "mode": "basic",
                    "username": "postgres",
                    "password": "secret",
                },
                "jdbc_options": {"sslmode": "require"},
            },
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    captured: dict[str, object] = {}

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_connect(_uri: str, **kwargs):
        captured.update(kwargs)
        return FakeConnection()

    monkeypatch.setitem(sys.modules, "psycopg", types.SimpleNamespace(connect=fake_connect))
    test = client.post(
        f"/api/v1/connections/catalogs/{response.json()['id']}/test",
        headers=headers,
    )

    assert test.status_code == 200
    assert captured["sslmode"] == "require"
    assert str(captured["sslrootcert"]).endswith("iceyard-no-postgres-root-ca.pem")


def test_path_style_s3_storage_does_not_force_virtual_addressing() -> None:
    catalog = CatalogConnection(
        workspace_id="workspace",
        environment_id="env",
        name="catalog",
        catalog_type="jdbc",
        endpoint="jdbc:postgresql://database.internal:5432/iceberg_catalog",
        settings={},
        capabilities={},
    )
    store = ObjectStoreConnection(
        workspace_id="workspace",
        environment_id="env",
        name="store",
        store_type="s3",
        endpoint="https://s3.internal",
        region="eu-central-1",
        settings={
            "access_style": "path-style",
            "storage_auth": {"mode": "static_key", "aws_access_key_id": "key"},
        },
    )
    properties = LiveIcebergReader(
        catalog=catalog,
        object_store=store,
        catalog_secret={},
        storage_secret={"aws_secret_access_key": "secret"},
    ).iceberg_properties()

    assert properties["s3.endpoint"] == "https://s3.internal"
    assert properties["s3.access-key-id"] == "key"
    assert properties["s3.secret-access-key"] == "secret"
    assert "s3.force-virtual-addressing" not in properties


def test_virtual_hosted_s3_storage_sets_virtual_addressing() -> None:
    catalog = CatalogConnection(
        workspace_id="workspace",
        environment_id="env",
        name="catalog",
        catalog_type="jdbc",
        endpoint="jdbc:postgresql://database.internal:5432/iceberg_catalog",
        settings={},
        capabilities={},
    )
    store = ObjectStoreConnection(
        workspace_id="workspace",
        environment_id="env",
        name="store",
        store_type="s3",
        endpoint="https://s3.amazonaws.com",
        region="eu-central-1",
        settings={"access_style": "virtual-hosted", "storage_auth": {"mode": "keyless"}},
    )
    properties = LiveIcebergReader(
        catalog=catalog,
        object_store=store,
        catalog_secret={},
        storage_secret={},
    ).iceberg_properties()

    assert properties["s3.force-virtual-addressing"] == "true"
