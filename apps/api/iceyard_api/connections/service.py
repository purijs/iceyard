import json
import os
import re
import tempfile
from contextlib import suppress
from typing import Any
from urllib.parse import urlparse

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from iceyard_api.core.config import get_settings
from iceyard_api.core.time import utcnow
from iceyard_api.db.models import (
    CatalogConnection,
    ComputeBackend,
    Environment,
    IcebergTable,
    ManifestFileCache,
    MetadataLogEntry,
    Namespace,
    ObjectStoreConnection,
    OperationRequest,
    PartitionSpec,
    PartitionSummary,
    RestorePoint,
    SchemaVersion,
    SecretReference,
    Snapshot,
    SnapshotLogEntry,
    SortOrder,
    TableFileCache,
    TableMetrics,
    TableRef,
)

SECRET_AUTH_FIELDS = {
    "aws_secret_access_key",
    "aws_session_token",
    "password",
    "bearer_token",
    "access_token",
    "client_secret",
    "secret_key",
}


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

    def _unique_secret_name(self, workspace_id: str, resource_name: str, purpose: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", f"{resource_name}-{purpose}").strip("-")
        base = slug[:100] or "connection-secret"
        candidate = base
        index = 2
        while self.session.scalar(
            select(SecretReference.id).where(
                SecretReference.workspace_id == workspace_id,
                SecretReference.name == candidate,
            )
        ):
            suffix = f"-{index}"
            candidate = f"{base[: 120 - len(suffix)]}{suffix}"
            index += 1
        return candidate

    def _create_inline_secret(
        self,
        *,
        workspace_id: str,
        resource_name: str,
        purpose: str,
        value: dict[str, str],
    ) -> SecretReference:
        encoded_reference = self._encode_inline_secret(value)
        secret = SecretReference(
            workspace_id=workspace_id,
            name=self._unique_secret_name(workspace_id, resource_name, purpose),
            provider="inline",
            reference=encoded_reference,
        )
        self.session.add(secret)
        self.session.flush()
        return secret

    def _secret_fernet(self) -> Fernet | None:
        key = get_settings().secret_encryption_key
        return Fernet(key.encode("utf-8")) if key else None

    def _encode_inline_secret(self, value: dict[str, str]) -> str:
        payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
        fernet = self._secret_fernet()
        if fernet:
            return f"fernet:v1:{fernet.encrypt(payload).decode('utf-8')}"
        if get_settings().environment == "production":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "ICEYARD_SECRET_ENCRYPTION_KEY is required before inline "
                    "connection secrets can be stored in production."
                ),
            )
        return payload.decode("utf-8")

    def _read_inline_secret(self, workspace_id: str, secret_id: str | None) -> dict[str, str]:
        if not secret_id:
            return {}
        secret = self.session.scalar(
            select(SecretReference).where(
                SecretReference.workspace_id == workspace_id,
                SecretReference.id == secret_id,
                SecretReference.provider == "inline",
            )
        )
        if not secret:
            return {}
        reference = secret.reference
        if reference.startswith("fernet:v1:"):
            fernet = self._secret_fernet()
            if not fernet:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="ICEYARD_SECRET_ENCRYPTION_KEY is required to read this secret.",
                )
            try:
                reference = fernet.decrypt(reference.removeprefix("fernet:v1:").encode()).decode(
                    "utf-8"
                )
            except InvalidToken as exc:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Stored connection secret could not be decrypted.",
                ) from exc
        try:
            loaded = json.loads(reference)
        except json.JSONDecodeError:
            return {}
        if not isinstance(loaded, dict):
            return {}
        return {str(key): str(value) for key, value in loaded.items() if value is not None}

    def _sanitize_auth_settings(
        self,
        *,
        workspace_id: str,
        resource_name: str,
        settings: dict[str, object],
        section: str,
    ) -> tuple[dict[str, object], str | None]:
        clean = dict(settings)
        auth = clean.get(section)
        if not isinstance(auth, dict):
            return clean, None

        auth_clean = dict(auth)
        secret_payload: dict[str, str] = {}
        for field in SECRET_AUTH_FIELDS:
            value = auth_clean.pop(field, None)
            if isinstance(value, str) and value.strip():
                secret_payload[field] = value.strip()
                auth_clean[f"{field}_present"] = True

        secret_id: str | None = None
        if secret_payload:
            secret = self._create_inline_secret(
                workspace_id=workspace_id,
                resource_name=resource_name,
                purpose=section.replace("_auth", "-auth"),
                value=secret_payload,
            )
            secret_id = secret.id
            auth_clean["secret_ref_id"] = secret.id
            auth_clean["secret_provider"] = secret.provider
        clean[section] = auth_clean
        return clean, secret_id

    def _sanitize_connection_settings(
        self,
        *,
        workspace_id: str,
        resource_name: str,
        settings: dict[str, object],
        section: str,
        auth_ref: str | None,
    ) -> tuple[dict[str, object], str | None]:
        clean, inline_secret_id = self._sanitize_auth_settings(
            workspace_id=workspace_id,
            resource_name=resource_name,
            settings=settings,
            section=section,
        )
        return clean, inline_secret_id or auth_ref

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
        self._delete_table_index_for_environment(workspace_id, environment_id)
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
        clean_settings, clean_auth_ref = self._sanitize_connection_settings(
            workspace_id=workspace_id,
            resource_name=name,
            settings=settings,
            section="catalog_auth",
            auth_ref=auth_ref,
        )
        connection = CatalogConnection(
            workspace_id=workspace_id,
            environment_id=environment_id,
            name=name,
            catalog_type=catalog_type,
            endpoint=endpoint,
            warehouse=warehouse,
            auth_ref=clean_auth_ref,
            settings=clean_settings,
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
            if field not in values:
                continue
            if field == "settings" and values[field] is not None:
                settings, auth_ref = self._sanitize_connection_settings(
                    workspace_id=workspace_id,
                    resource_name=connection.name,
                    settings=values[field],
                    section="catalog_auth",
                    auth_ref=connection.auth_ref,
                )
                connection.settings = settings
                connection.auth_ref = auth_ref
            elif field != "settings":
                setattr(connection, field, values[field])
        self.session.flush()
        return connection

    def delete_catalog_connection(self, workspace_id: str, connection_id: str) -> None:
        connection = self.get_catalog_connection(workspace_id, connection_id)
        linked_store_id = (
            connection.settings.get("object_store_connection_id")
            if isinstance(connection.settings, dict)
            else None
        )
        self._delete_table_index_for_connection(workspace_id, connection_id)
        if isinstance(linked_store_id, str) and linked_store_id:
            self._delete_unshared_object_store(workspace_id, linked_store_id, connection_id)
        self.session.delete(connection)

    def _delete_unshared_object_store(
        self, workspace_id: str, store_id: str, deleting_connection_id: str
    ) -> None:
        other_connections = self.session.scalars(
            select(CatalogConnection).where(
                CatalogConnection.workspace_id == workspace_id,
                CatalogConnection.id != deleting_connection_id,
            )
        )
        still_referenced = any(
            isinstance(connection.settings, dict)
            and connection.settings.get("object_store_connection_id") == store_id
            for connection in other_connections
        )
        if still_referenced:
            return
        store = self.session.scalar(
            select(ObjectStoreConnection).where(
                ObjectStoreConnection.workspace_id == workspace_id,
                ObjectStoreConnection.id == store_id,
            )
        )
        if store:
            self.session.delete(store)

    def _delete_table_index_for_connection(
        self, workspace_id: str, connection_id: str
    ) -> None:
        namespace_ids = list(
            self.session.scalars(
                select(Namespace.id).where(
                    Namespace.workspace_id == workspace_id,
                    Namespace.catalog_connection_id == connection_id,
                )
            )
        )
        if not namespace_ids:
            return
        self._delete_tables_for_namespaces(workspace_id, namespace_ids)
        self.session.execute(delete(Namespace).where(Namespace.id.in_(namespace_ids)))

    def _delete_table_index_for_environment(
        self, workspace_id: str, environment_id: str
    ) -> None:
        table_rows = list(
            self.session.execute(
                select(IcebergTable.id, IcebergTable.namespace_id).where(
                    IcebergTable.workspace_id == workspace_id,
                    IcebergTable.environment_id == environment_id,
                )
            )
        )
        table_ids = [row.id for row in table_rows]
        namespace_ids = list({row.namespace_id for row in table_rows})
        self._delete_tables(table_ids)
        if namespace_ids:
            self.session.execute(
                delete(Namespace).where(
                    Namespace.workspace_id == workspace_id,
                    Namespace.id.in_(namespace_ids),
                )
            )

    def _delete_tables_for_namespaces(
        self, workspace_id: str, namespace_ids: list[str]
    ) -> None:
        table_ids = list(
            self.session.scalars(
                select(IcebergTable.id).where(
                    IcebergTable.workspace_id == workspace_id,
                    IcebergTable.namespace_id.in_(namespace_ids),
                )
            )
        )
        self._delete_tables(table_ids)

    def _delete_tables(self, table_ids: list[str]) -> None:
        if not table_ids:
            return
        for model in (
            TableMetrics,
            Snapshot,
            SchemaVersion,
            PartitionSpec,
            SortOrder,
            TableRef,
            MetadataLogEntry,
            SnapshotLogEntry,
            ManifestFileCache,
            TableFileCache,
            PartitionSummary,
            RestorePoint,
        ):
            self.session.execute(delete(model).where(model.table_id.in_(table_ids)))
        self.session.execute(
            update(OperationRequest)
            .where(OperationRequest.table_id.in_(table_ids))
            .values(table_id=None)
        )
        self.session.execute(delete(IcebergTable).where(IcebergTable.id.in_(table_ids)))

    def _component(self, name: str, status_value: str, message: str) -> dict[str, str]:
        return {"name": name, "status": status_value, "message": message}

    def _overall_status(self, components: list[dict[str, str]]) -> str:
        statuses = {component["status"] for component in components}
        if "failed" in statuses:
            return "failed"
        if "warning" in statuses:
            return "warning"
        return "ok"

    def _test_message(self, status_value: str, target: str) -> str:
        if status_value == "ok":
            return f"{target} test passed."
        if status_value == "warning":
            return f"{target} test completed with warnings."
        return f"{target} test failed."

    def _auth_secret_id(self, auth: dict[str, object], fallback: str | None) -> str | None:
        secret_ref_id = auth.get("secret_ref_id")
        if isinstance(secret_ref_id, str) and secret_ref_id:
            return secret_ref_id
        return fallback

    def _catalog_auth_components(self, connection: CatalogConnection) -> list[dict[str, str]]:
        settings = connection.settings if isinstance(connection.settings, dict) else {}
        auth = settings.get("catalog_auth")
        auth_settings = auth if isinstance(auth, dict) else {}
        mode = str(auth_settings.get("mode") or "none")

        if mode == "basic":
            has_user = bool(auth_settings.get("username"))
            has_secret = bool(auth_settings.get("password_present") or connection.auth_ref)
            if has_user and has_secret:
                return [
                    self._component(
                        "catalog auth",
                        "ok",
                        "Database username and password reference are configured.",
                    )
                ]
            return [
                self._component(
                    "catalog auth",
                    "failed",
                    "Database username and password are required for basic auth.",
                )
            ]

        if mode == "bearer":
            has_secret = bool(auth_settings.get("bearer_token_present") or connection.auth_ref)
            status_value = "ok" if has_secret else "failed"
            message = (
                "Bearer token reference is configured."
                if has_secret
                else "Bearer token is required."
            )
            return [self._component("catalog auth", status_value, message)]

        if mode == "oauth_client":
            has_client = bool(auth_settings.get("client_id"))
            has_secret = bool(auth_settings.get("client_secret_present") or connection.auth_ref)
            if has_client and has_secret:
                return [
                    self._component(
                        "catalog auth",
                        "ok",
                        "OAuth client id and secret reference are configured.",
                    )
                ]
            return [
                self._component(
                    "catalog auth",
                    "failed",
                    "OAuth client id and client secret are required.",
                )
            ]

        if mode == "aws_iam":
            identity = auth_settings.get("identity")
            message = (
                f"AWS IAM identity configured: {identity}."
                if identity
                else "AWS IAM uses the runtime credential chain."
            )
            return [self._component("catalog auth", "ok", message)]

        if mode == "secret_ref":
            has_reference = bool(auth_settings.get("secret_reference") or connection.auth_ref)
            status_value = "ok" if has_reference else "failed"
            message = (
                "External secret reference is configured."
                if has_reference
                else "Secret reference is required."
            )
            return [self._component("catalog auth", status_value, message)]

        if connection.catalog_type in {"jdbc", "rest", "hive", "nessie", "glue", "s3_tables"}:
            return [
                self._component(
                    "catalog auth",
                    "warning",
                    "No explicit catalog auth is configured; runtime defaults will be used.",
                )
            ]
        return [
            self._component(
                "catalog auth",
                "ok",
                "No catalog auth is required for this catalog type.",
            )
        ]

    def _storage_auth_components(self, store: ObjectStoreConnection) -> list[dict[str, str]]:
        settings = store.settings if isinstance(store.settings, dict) else {}
        auth = settings.get("storage_auth")
        auth_settings = auth if isinstance(auth, dict) else {}
        mode = str(auth_settings.get("mode") or "keyless")

        if mode == "credential_vending":
            return [
                self._component(
                    "storage auth",
                    "warning",
                    "Storage credentials are expected from catalog credential vending.",
                )
            ]
        if mode == "static_key":
            has_access_key = bool(auth_settings.get("aws_access_key_id"))
            has_secret = bool(auth_settings.get("aws_secret_access_key_present") or store.auth_ref)
            if has_access_key and has_secret:
                return [
                    self._component(
                        "storage auth",
                        "ok",
                        "Static access key id and secret reference are configured.",
                    )
                ]
            return [
                self._component(
                    "storage auth",
                    "failed",
                    "AWS access key id and secret access key are required.",
                )
            ]
        if mode == "secret_ref":
            has_reference = bool(auth_settings.get("secret_reference") or store.auth_ref)
            status_value = "ok" if has_reference else "failed"
            message = (
                "External storage secret reference is configured."
                if has_reference
                else "Storage secret reference is required."
            )
            return [self._component("storage auth", status_value, message)]
        if mode == "keyless":
            identity = auth_settings.get("identity")
            message = (
                f"Storage identity configured: {identity}."
                if identity
                else "Storage access uses the runtime credential chain."
            )
            return [self._component("storage auth", "ok", message)]
        return [
            self._component(
                "storage auth",
                "failed",
                f"Unsupported storage auth mode: {mode}.",
            )
        ]

    def _catalog_endpoint_component(self, connection: CatalogConnection) -> dict[str, str]:
        if connection.catalog_type == "hadoop":
            if connection.warehouse:
                return self._component(
                    "catalog metadata",
                    "ok",
                    "Hadoop warehouse path is configured.",
                )
            return self._component(
                "catalog metadata",
                "failed",
                "Hadoop catalog requires a warehouse path.",
            )
        if connection.endpoint:
            return self._component("catalog metadata", "ok", "Catalog endpoint is configured.")
        return self._component("catalog metadata", "failed", "Catalog endpoint is required.")

    def _http_headers_for_catalog(self, connection: CatalogConnection) -> dict[str, str]:
        settings = connection.settings if isinstance(connection.settings, dict) else {}
        auth = settings.get("catalog_auth")
        auth_settings = auth if isinstance(auth, dict) else {}
        if auth_settings.get("mode") != "bearer":
            return {}
        secret = self._read_inline_secret(
            connection.workspace_id,
            self._auth_secret_id(auth_settings, connection.auth_ref),
        )
        token = secret.get("bearer_token") or secret.get("access_token")
        return {"authorization": f"Bearer {token}"} if token else {}

    def _http_catalog_probe(self, connection: CatalogConnection) -> dict[str, str]:
        if not connection.endpoint:
            return self._component("catalog reachability", "failed", "Catalog endpoint is missing.")
        endpoint = connection.endpoint.rstrip("/")
        if connection.catalog_type == "rest":
            url = f"{endpoint}/config" if endpoint.endswith("/v1") else f"{endpoint}/v1/config"
        else:
            url = endpoint
        try:
            response = httpx.get(
                url,
                headers=self._http_headers_for_catalog(connection),
                timeout=5.0,
                follow_redirects=True,
            )
            if response.status_code < 500:
                return self._component(
                    "catalog reachability",
                    "ok" if response.status_code < 400 else "failed",
                    f"HTTP probe returned {response.status_code}.",
                )
            return self._component(
                "catalog reachability",
                "failed",
                f"HTTP probe returned {response.status_code}.",
            )
        except httpx.HTTPError as exc:
            return self._component("catalog reachability", "failed", f"HTTP probe failed: {exc}.")

    def _jdbc_catalog_probe(self, connection: CatalogConnection) -> dict[str, str]:
        if not connection.endpoint:
            return self._component("catalog reachability", "failed", "JDBC URI is missing.")
        uri = connection.endpoint
        if uri.startswith("jdbc:"):
            uri = uri[5:]
        settings = connection.settings if isinstance(connection.settings, dict) else {}
        auth = settings.get("catalog_auth")
        auth_settings = auth if isinstance(auth, dict) else {}
        secret = self._read_inline_secret(
            connection.workspace_id,
            self._auth_secret_id(auth_settings, connection.auth_ref),
        )
        username = auth_settings.get("username")
        password = secret.get("password")
        jdbc_options = settings.get("jdbc_options")
        jdbc_settings = jdbc_options if isinstance(jdbc_options, dict) else {}
        if uri.startswith("postgresql://") or uri.startswith("postgres://"):
            root_cert_path: str | None = None
            try:
                import psycopg

                connect_kwargs: dict[str, object] = {"connect_timeout": 5}
                if username:
                    connect_kwargs["user"] = str(username)
                if password:
                    connect_kwargs["password"] = password
                sslmode = jdbc_settings.get("sslmode")
                if isinstance(sslmode, str) and sslmode:
                    connect_kwargs["sslmode"] = sslmode
                application_name = jdbc_settings.get("application_name")
                if isinstance(application_name, str) and application_name:
                    connect_kwargs["application_name"] = application_name
                root_cert = jdbc_settings.get("ssl_root_cert")
                if isinstance(root_cert, str) and root_cert.strip():
                    with tempfile.NamedTemporaryFile(
                        mode="w",
                        encoding="utf-8",
                        prefix="iceyard-pg-ca-",
                        suffix=".pem",
                        delete=False,
                    ) as cert_file:
                        cert_file.write(root_cert)
                        root_cert_path = cert_file.name
                    connect_kwargs["sslrootcert"] = root_cert_path
                elif sslmode == "require":
                    connect_kwargs["sslrootcert"] = os.path.join(
                        tempfile.gettempdir(), "iceyard-no-postgres-root-ca.pem"
                    )

                with psycopg.connect(
                    uri,
                    **connect_kwargs,
                ):
                    return self._component(
                        "catalog reachability",
                        "ok",
                        "PostgreSQL catalog database accepted a connection.",
                    )
            except Exception as exc:
                return self._component(
                    "catalog reachability",
                    "failed",
                    f"PostgreSQL probe failed: {exc}.",
                )
            finally:
                if root_cert_path:
                    with suppress(OSError):
                        os.unlink(root_cert_path)
        if uri.startswith("mysql://"):
            return self._component(
                "catalog reachability",
                "warning",
                "MySQL probing requires a MySQL driver; configuration was validated only.",
            )
        return self._component(
            "catalog reachability",
            "warning",
            "JDBC scheme is not directly probed by this service.",
        )

    def _catalog_reachability_component(self, connection: CatalogConnection) -> dict[str, str]:
        if connection.catalog_type == "jdbc":
            return self._jdbc_catalog_probe(connection)
        if connection.catalog_type in {"rest", "nessie"}:
            return self._http_catalog_probe(connection)
        if connection.catalog_type in {"glue", "s3_tables", "hive", "hadoop"}:
            return self._component(
                "catalog reachability",
                "warning",
                (
                    f"{connection.catalog_type} catalog reachability uses its provider "
                    "client and is not directly probed here."
                ),
            )
        return self._component(
            "catalog reachability",
            "warning",
            "Catalog type is not directly probed.",
        )

    def _linked_object_store(self, connection: CatalogConnection) -> ObjectStoreConnection | None:
        settings = connection.settings if isinstance(connection.settings, dict) else {}
        store_id = settings.get("object_store_connection_id")
        if not isinstance(store_id, str) or not store_id:
            return None
        return self.session.scalar(
            select(ObjectStoreConnection).where(
                ObjectStoreConnection.workspace_id == connection.workspace_id,
                ObjectStoreConnection.id == store_id,
            )
        )

    def _store_location_component(self, store: ObjectStoreConnection) -> dict[str, str]:
        settings = store.settings if isinstance(store.settings, dict) else {}
        warehouse = settings.get("warehouse")
        warehouse_text = warehouse if isinstance(warehouse, str) else ""
        if store.store_type == "s3" and warehouse_text.startswith("s3://"):
            return self._component("storage location", "ok", "S3 warehouse URI is configured.")
        if store.store_type == "gcs" and warehouse_text.startswith("gs://"):
            return self._component("storage location", "ok", "GCS warehouse URI is configured.")
        if store.store_type == "adls" and warehouse_text:
            return self._component("storage location", "ok", "ADLS warehouse URI is configured.")
        if store.store_type in {"hdfs", "local"} and warehouse_text:
            return self._component(
                "storage location",
                "ok",
                "Filesystem warehouse path is configured.",
            )
        return self._component(
            "storage location",
            "failed",
            f"{store.store_type} warehouse URI is required.",
        )

    def _s3_bucket_from_store(self, store: ObjectStoreConnection) -> str | None:
        settings = store.settings if isinstance(store.settings, dict) else {}
        warehouse = settings.get("warehouse")
        if not isinstance(warehouse, str):
            return None
        parsed = urlparse(warehouse)
        if parsed.scheme != "s3" or not parsed.netloc:
            return None
        return parsed.netloc

    def _s3_store_probe(self, store: ObjectStoreConnection) -> dict[str, str]:
        bucket = self._s3_bucket_from_store(store)
        if not bucket:
            return self._component(
                "storage reachability",
                "failed",
                "S3 warehouse bucket could not be parsed.",
            )
        settings = store.settings if isinstance(store.settings, dict) else {}
        auth = settings.get("storage_auth")
        auth_settings = auth if isinstance(auth, dict) else {}
        mode = str(auth_settings.get("mode") or "keyless")
        if mode == "credential_vending":
            return self._component(
                "storage reachability",
                "warning",
                "Direct S3 probe skipped because storage credentials are catalog-vended.",
            )
        if mode == "secret_ref" and not auth_settings.get("secret_ref_id"):
            return self._component(
                "storage reachability",
                "warning",
                "External secret references are not resolved by the local probe.",
            )
        try:
            import boto3
            from botocore.config import Config
        except ImportError:
            return self._component(
                "storage reachability",
                "warning",
                "Install runtime dependencies to run the S3 reachability probe.",
            )

        secret = self._read_inline_secret(
            store.workspace_id,
            self._auth_secret_id(auth_settings, store.auth_ref),
        )
        access_key_id = (
            auth_settings.get("aws_access_key_id") if mode == "static_key" else None
        )
        session = boto3.session.Session(
            aws_access_key_id=access_key_id,
            aws_secret_access_key=(
                secret.get("aws_secret_access_key") if mode == "static_key" else None
            ),
            aws_session_token=(
                secret.get("aws_session_token") if mode == "static_key" else None
            ),
            region_name=store.region or str(settings.get("region") or "") or None,
        )
        addressing_style = "path" if settings.get("access_style") == "path-style" else "virtual"
        client = session.client(
            "s3",
            endpoint_url=store.endpoint or None,
            config=Config(s3={"addressing_style": addressing_style}),
        )
        try:
            client.head_bucket(Bucket=bucket)
        except Exception as exc:
            return self._component(
                "storage reachability",
                "failed",
                f"S3 HeadBucket failed: {exc}.",
            )
        return self._component("storage reachability", "ok", f"S3 bucket {bucket} is reachable.")

    def _store_reachability_component(self, store: ObjectStoreConnection) -> dict[str, str]:
        if store.store_type == "s3":
            return self._s3_store_probe(store)
        if store.store_type == "local":
            return self._component(
                "storage reachability",
                "ok",
                "Local path validation is deferred to the worker process.",
            )
        return self._component(
            "storage reachability",
            "warning",
            f"{store.store_type} live probing is not implemented yet.",
        )

    def test_catalog_connection(self, connection: CatalogConnection) -> dict[str, object]:
        connection.last_tested_at = utcnow()
        connection.capabilities = capabilities_for_catalog(connection.catalog_type)
        components = [
            self._catalog_endpoint_component(connection),
            *self._catalog_auth_components(connection),
            self._catalog_reachability_component(connection),
        ]
        linked_store = self._linked_object_store(connection)
        if linked_store:
            storage_result = self.test_object_store(linked_store)
            components.extend(
                {
                    **component,
                    "name": f"linked {component['name']}",
                }
                for component in storage_result["components"]
            )
        else:
            components.append(
                self._component(
                    "linked storage",
                    "warning",
                    "No linked object store reference is configured for this catalog.",
                )
            )
        status_value = self._overall_status(components)
        return {
            "connection_id": connection.id,
            "status": status_value,
            "message": self._test_message(status_value, "Catalog connection"),
            "capabilities": connection.capabilities,
            "components": components,
        }

    def test_object_store(self, store: ObjectStoreConnection) -> dict[str, object]:
        components = [
            self._store_location_component(store),
            *self._storage_auth_components(store),
            self._store_reachability_component(store),
        ]
        status_value = self._overall_status(components)
        return {
            "connection_id": store.id,
            "status": status_value,
            "message": self._test_message(status_value, "Storage connection"),
            "capabilities": {},
            "components": components,
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
        clean_settings, clean_auth_ref = self._sanitize_connection_settings(
            workspace_id=workspace_id,
            resource_name=name,
            settings=settings,
            section="storage_auth",
            auth_ref=auth_ref,
        )
        store = ObjectStoreConnection(
            workspace_id=workspace_id,
            environment_id=environment_id,
            name=name,
            store_type=store_type,
            endpoint=endpoint,
            region=region,
            auth_ref=clean_auth_ref,
            settings=clean_settings,
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
            if field not in values:
                continue
            if field == "settings" and values[field] is not None:
                settings, auth_ref = self._sanitize_connection_settings(
                    workspace_id=workspace_id,
                    resource_name=store.name,
                    settings=values[field],
                    section="storage_auth",
                    auth_ref=store.auth_ref,
                )
                store.settings = settings
                store.auth_ref = auth_ref
            elif field != "settings":
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
