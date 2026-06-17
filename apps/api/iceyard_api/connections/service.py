from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from iceyard_api.core.time import utcnow
from iceyard_api.db.models import (
    CatalogConnection,
    ComputeBackend,
    Environment,
    ObjectStoreConnection,
    SecretReference,
)


def capabilities_for_catalog(catalog_type: str) -> dict[str, object]:
    base = {
        "protocol": catalog_type,
        "supports_credential_vending": False,
        "supports_remote_signing": False,
        "supports_multi_table_commit": False,
        "supports_server_side_scan_planning": False,
        "supports_branches_tags": True,
        "supports_catalog_level_branching": False,
        "max_namespace_depth": 8,
        "can_create_v3": True,
        "can_update_table_via_protocol": True,
        "manages_own_maintenance": False,
    }
    if catalog_type == "rest":
        base.update(
            {
                "supports_credential_vending": True,
                "supports_remote_signing": True,
                "supports_multi_table_commit": True,
                "supports_server_side_scan_planning": True,
            }
        )
    if catalog_type == "glue":
        base.update(
            {
                "max_namespace_depth": 1,
                "can_create_v3": False,
                "can_update_table_via_protocol": False,
            }
        )
    if catalog_type == "nessie":
        base.update(
            {"supports_catalog_level_branching": True, "supports_credential_vending": False}
        )
    if catalog_type == "s3_tables":
        base.update({"manages_own_maintenance": True, "supports_credential_vending": True})
    if catalog_type in {"jdbc", "hive", "hadoop"}:
        base.update(
            {
                "supports_credential_vending": False,
                "supports_remote_signing": False,
                "supports_multi_table_commit": False,
                "supports_server_side_scan_planning": False,
            }
        )
    return base


class ConnectionService:
    def __init__(self, session: Session):
        self.session = session

    def _not_found(self, resource: str) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{resource} not found."
        )

    def _ensure_environment(self, workspace_id: str, environment_id: str) -> Environment:
        environment = self.session.scalar(
            select(Environment).where(
                Environment.workspace_id == workspace_id,
                Environment.id == environment_id,
            )
        )
        if not environment:
            raise self._not_found("Environment")
        return environment

    def _ensure_unique_name(
        self,
        model: type[Environment]
        | type[CatalogConnection]
        | type[ObjectStoreConnection]
        | type[ComputeBackend]
        | type[SecretReference],
        workspace_id: str,
        name: str,
        current_id: str | None = None,
    ) -> None:
        stmt = select(model).where(model.workspace_id == workspace_id, model.name == name)
        if current_id:
            stmt = stmt.where(model.id != current_id)
        if self.session.scalar(stmt):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{model.__tablename__.replace('_', ' ').title()} already exists.",
            )

    def create_environment(
        self,
        *,
        workspace_id: str,
        name: str,
        kind: str,
        region: str | None,
        posture: dict[str, object],
    ) -> Environment:
        self._ensure_unique_name(Environment, workspace_id, name)
        environment = Environment(
            workspace_id=workspace_id,
            name=name,
            kind=kind,
            region=region,
            posture=posture,
        )
        self.session.add(environment)
        self.session.flush()
        return environment

    def list_environments(self, workspace_id: str) -> list[Environment]:
        return list(
            self.session.scalars(
                select(Environment).where(Environment.workspace_id == workspace_id)
            )
        )

    def get_environment(self, workspace_id: str, environment_id: str) -> Environment:
        return self._ensure_environment(workspace_id, environment_id)

    def update_environment(
        self,
        workspace_id: str,
        environment_id: str,
        values: dict[str, Any],
    ) -> Environment:
        environment = self._ensure_environment(workspace_id, environment_id)
        if name := values.get("name"):
            self._ensure_unique_name(Environment, workspace_id, name, current_id=environment.id)
            environment.name = name
        if "kind" in values and values["kind"] is not None:
            environment.kind = values["kind"]
        if "region" in values:
            environment.region = values["region"]
        if "posture" in values and values["posture"] is not None:
            environment.posture = values["posture"]
        self.session.flush()
        return environment

    def delete_environment(self, workspace_id: str, environment_id: str) -> None:
        environment = self._ensure_environment(workspace_id, environment_id)
        has_children = any(
            self.session.scalar(
                select(model.id).where(
                    model.workspace_id == workspace_id,
                    model.environment_id == environment.id,
                )
            )
            for model in (CatalogConnection, ObjectStoreConnection, ComputeBackend)
        )
        if has_children:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Environment still has connections.",
            )
        self.session.delete(environment)

    def create_catalog_connection(
        self,
        *,
        workspace_id: str,
        environment_id: str,
        name: str,
        catalog_type: str,
        endpoint: str | None,
        warehouse: str | None,
        auth_ref: str | None,
        settings: dict[str, object],
    ) -> CatalogConnection:
        self._ensure_environment(workspace_id, environment_id)
        self._ensure_unique_name(CatalogConnection, workspace_id, name)
        connection = CatalogConnection(
            workspace_id=workspace_id,
            environment_id=environment_id,
            name=name,
            catalog_type=catalog_type,
            endpoint=endpoint,
            warehouse=warehouse,
            auth_ref=auth_ref,
            settings=settings,
            capabilities=capabilities_for_catalog(catalog_type),
        )
        self.session.add(connection)
        self.session.flush()
        return connection

    def list_catalog_connections(self, workspace_id: str) -> list[CatalogConnection]:
        return list(
            self.session.scalars(
                select(CatalogConnection).where(CatalogConnection.workspace_id == workspace_id)
            )
        )

    def get_catalog_connection(
        self, workspace_id: str, connection_id: str
    ) -> CatalogConnection:
        connection = self.session.scalar(
            select(CatalogConnection).where(
                CatalogConnection.workspace_id == workspace_id,
                CatalogConnection.id == connection_id,
            )
        )
        if not connection:
            raise self._not_found("Connection")
        return connection

    def update_catalog_connection(
        self,
        workspace_id: str,
        connection_id: str,
        values: dict[str, Any],
    ) -> CatalogConnection:
        connection = self.get_catalog_connection(workspace_id, connection_id)
        if environment_id := values.get("environment_id"):
            self._ensure_environment(workspace_id, environment_id)
            connection.environment_id = environment_id
        if name := values.get("name"):
            self._ensure_unique_name(
                CatalogConnection, workspace_id, name, current_id=connection.id
            )
            connection.name = name
        if catalog_type := values.get("catalog_type"):
            connection.catalog_type = catalog_type
            connection.capabilities = capabilities_for_catalog(catalog_type)
        for field in ("endpoint", "warehouse", "auth_ref", "settings", "is_enabled"):
            if field in values and values[field] is not None:
                setattr(connection, field, values[field])
        self.session.flush()
        return connection

    def delete_catalog_connection(self, workspace_id: str, connection_id: str) -> None:
        connection = self.get_catalog_connection(workspace_id, connection_id)
        self.session.delete(connection)

    def test_catalog_connection(self, connection: CatalogConnection) -> dict[str, object]:
        connection.last_tested_at = utcnow()
        connection.capabilities = capabilities_for_catalog(connection.catalog_type)
        return {
            "connection_id": connection.id,
            "status": "ok",
            "message": (
                "Connection settings are syntactically valid. "
                "Live catalog probing is not enabled in this build."
            ),
            "capabilities": connection.capabilities,
        }

    def create_object_store(
        self,
        *,
        workspace_id: str,
        environment_id: str,
        name: str,
        store_type: str,
        endpoint: str | None,
        region: str | None,
        auth_ref: str | None,
        settings: dict[str, object],
    ) -> ObjectStoreConnection:
        self._ensure_environment(workspace_id, environment_id)
        self._ensure_unique_name(ObjectStoreConnection, workspace_id, name)
        store = ObjectStoreConnection(
            workspace_id=workspace_id,
            environment_id=environment_id,
            name=name,
            store_type=store_type,
            endpoint=endpoint,
            region=region,
            auth_ref=auth_ref,
            settings=settings,
        )
        self.session.add(store)
        self.session.flush()
        return store

    def list_object_stores(self, workspace_id: str) -> list[ObjectStoreConnection]:
        return list(
            self.session.scalars(
                select(ObjectStoreConnection).where(
                    ObjectStoreConnection.workspace_id == workspace_id
                )
            )
        )

    def get_object_store(self, workspace_id: str, store_id: str) -> ObjectStoreConnection:
        store = self.session.scalar(
            select(ObjectStoreConnection).where(
                ObjectStoreConnection.workspace_id == workspace_id,
                ObjectStoreConnection.id == store_id,
            )
        )
        if not store:
            raise self._not_found("Object store connection")
        return store

    def update_object_store(
        self, workspace_id: str, store_id: str, values: dict[str, Any]
    ) -> ObjectStoreConnection:
        store = self.get_object_store(workspace_id, store_id)
        if environment_id := values.get("environment_id"):
            self._ensure_environment(workspace_id, environment_id)
            store.environment_id = environment_id
        if name := values.get("name"):
            self._ensure_unique_name(
                ObjectStoreConnection, workspace_id, name, current_id=store.id
            )
            store.name = name
        for field in ("store_type", "endpoint", "region", "auth_ref", "settings"):
            if field in values and values[field] is not None:
                setattr(store, field, values[field])
        self.session.flush()
        return store

    def delete_object_store(self, workspace_id: str, store_id: str) -> None:
        self.session.delete(self.get_object_store(workspace_id, store_id))

    def create_compute_backend(
        self,
        *,
        workspace_id: str,
        environment_id: str,
        name: str,
        backend_type: str,
        settings: dict[str, object],
    ) -> ComputeBackend:
        self._ensure_environment(workspace_id, environment_id)
        self._ensure_unique_name(ComputeBackend, workspace_id, name)
        backend = ComputeBackend(
            workspace_id=workspace_id,
            environment_id=environment_id,
            name=name,
            backend_type=backend_type,
            settings=settings,
        )
        self.session.add(backend)
        self.session.flush()
        return backend

    def list_compute_backends(self, workspace_id: str) -> list[ComputeBackend]:
        return list(
            self.session.scalars(
                select(ComputeBackend).where(ComputeBackend.workspace_id == workspace_id)
            )
        )

    def get_compute_backend(self, workspace_id: str, backend_id: str) -> ComputeBackend:
        backend = self.session.scalar(
            select(ComputeBackend).where(
                ComputeBackend.workspace_id == workspace_id,
                ComputeBackend.id == backend_id,
            )
        )
        if not backend:
            raise self._not_found("Compute backend")
        return backend

    def update_compute_backend(
        self, workspace_id: str, backend_id: str, values: dict[str, Any]
    ) -> ComputeBackend:
        backend = self.get_compute_backend(workspace_id, backend_id)
        if environment_id := values.get("environment_id"):
            self._ensure_environment(workspace_id, environment_id)
            backend.environment_id = environment_id
        if name := values.get("name"):
            self._ensure_unique_name(
                ComputeBackend, workspace_id, name, current_id=backend.id
            )
            backend.name = name
        for field in ("backend_type", "settings", "is_enabled"):
            if field in values and values[field] is not None:
                setattr(backend, field, values[field])
        self.session.flush()
        return backend

    def delete_compute_backend(self, workspace_id: str, backend_id: str) -> None:
        self.session.delete(self.get_compute_backend(workspace_id, backend_id))

    def create_secret_reference(
        self, *, workspace_id: str, name: str, provider: str, reference: str
    ) -> SecretReference:
        self._ensure_unique_name(SecretReference, workspace_id, name)
        secret = SecretReference(
            workspace_id=workspace_id,
            name=name,
            provider=provider,
            reference=reference,
        )
        self.session.add(secret)
        self.session.flush()
        return secret

    def list_secret_references(self, workspace_id: str) -> list[SecretReference]:
        return list(
            self.session.scalars(
                select(SecretReference).where(SecretReference.workspace_id == workspace_id)
            )
        )

    def get_secret_reference(self, workspace_id: str, secret_id: str) -> SecretReference:
        secret = self.session.scalar(
            select(SecretReference).where(
                SecretReference.workspace_id == workspace_id,
                SecretReference.id == secret_id,
            )
        )
        if not secret:
            raise self._not_found("Secret reference")
        return secret

    def update_secret_reference(
        self, workspace_id: str, secret_id: str, values: dict[str, Any]
    ) -> SecretReference:
        secret = self.get_secret_reference(workspace_id, secret_id)
        if "provider" in values and values["provider"] is not None:
            secret.provider = values["provider"]
        if "reference" in values and values["reference"] is not None:
            secret.reference = values["reference"]
        self.session.flush()
        return secret

    def delete_secret_reference(self, workspace_id: str, secret_id: str) -> None:
        self.session.delete(self.get_secret_reference(workspace_id, secret_id))
