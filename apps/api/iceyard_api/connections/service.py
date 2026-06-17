from sqlalchemy import select
from sqlalchemy.orm import Session

from iceyard_api.core.time import utcnow
from iceyard_api.db.models import (
    CatalogConnection,
    ComputeBackend,
    Environment,
    ObjectStoreConnection,
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

    def create_environment(
        self,
        *,
        workspace_id: str,
        name: str,
        kind: str,
        region: str | None,
        posture: dict[str, object],
    ) -> Environment:
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
    ) -> CatalogConnection | None:
        return self.session.scalar(
            select(CatalogConnection).where(
                CatalogConnection.workspace_id == workspace_id,
                CatalogConnection.id == connection_id,
            )
        )

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

    def create_compute_backend(
        self,
        *,
        workspace_id: str,
        environment_id: str,
        name: str,
        backend_type: str,
        settings: dict[str, object],
    ) -> ComputeBackend:
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
