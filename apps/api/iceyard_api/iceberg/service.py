import os
import tempfile
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import suppress
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from iceyard_api.core.config import get_settings
from iceyard_api.core.time import utcnow
from iceyard_api.db.models import (
    CatalogConnection,
    IcebergTable,
    ManifestFileCache,
    MetadataLogEntry,
    MetadataSyncRun,
    Namespace,
    ObjectStoreConnection,
    PartitionSpec,
    PartitionSummary,
    SchemaVersion,
    Snapshot,
    SnapshotLogEntry,
    SortOrder,
    TableFileCache,
    TableMetrics,
    TableRef,
)
from iceyard_api.iceberg.live_metadata import LiveIcebergReader


class IcebergIndexService:
    def __init__(self, session: Session):
        self.session = session

    def refresh_index(
        self, workspace_id: str, catalog_connection_id: str | None = None, force: bool = False
    ) -> dict[str, object]:
        if catalog_connection_id:
            return self.sync_catalog_metadata(workspace_id, catalog_connection_id, force=force)
        discovered = 0
        removed = 0
        mode = "refresh"
        refreshed_at = utcnow()
        table_stmt = (
            select(IcebergTable)
            .join(Namespace, IcebergTable.namespace_id == Namespace.id)
            .join(CatalogConnection, Namespace.catalog_connection_id == CatalogConnection.id)
            .where(
                IcebergTable.workspace_id == workspace_id,
                CatalogConnection.workspace_id == workspace_id,
            )
        )
        if catalog_connection_id:
            table_stmt = table_stmt.where(Namespace.catalog_connection_id == catalog_connection_id)
        tables = list(self.session.scalars(table_stmt))
        for table in tables:
            table.indexed_at = refreshed_at
        namespace_stmt = select(func.count(Namespace.id)).where(
            Namespace.workspace_id == workspace_id
        )
        if catalog_connection_id:
            namespace_stmt = namespace_stmt.where(
                Namespace.catalog_connection_id == catalog_connection_id
            )
        self.session.flush()
        return {
            "catalog_connection_id": catalog_connection_id,
            "namespace_count": int(self.session.scalar(namespace_stmt) or 0),
            "table_count": len(tables),
            "discovered_table_count": discovered,
            "removed_table_count": removed,
            "mode": mode,
            "refreshed_at": refreshed_at,
        }

    def sync_catalog_metadata(
        self, workspace_id: str, catalog_connection_id: str, *, force: bool = False
    ) -> dict[str, object]:
        catalog = self.session.scalar(
            select(CatalogConnection).where(
                CatalogConnection.workspace_id == workspace_id,
                CatalogConnection.id == catalog_connection_id,
            )
        )
        if not catalog:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Catalog connection not found."
            )
        run = MetadataSyncRun(
            workspace_id=workspace_id,
            catalog_connection_id=catalog.id,
            status="running",
            mode="incremental_deep" if not force else "force_deep",
            stats={},
        )
        self.session.add(run)
        self.session.flush()
        try:
            if catalog.catalog_type == "jdbc":
                sync = self._sync_jdbc_catalog(workspace_id, catalog, force=force)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Metadata sync currently supports JDBC/PostgreSQL catalogs. "
                        "Other catalog adapters are modeled but not enabled yet."
                    ),
                )
            run.status = "succeeded" if sync["failed"] == 0 else "warning"
            run.table_count = sync["table_count"]
            run.discovered_table_count = sync["discovered"]
            run.removed_table_count = sync["removed"]
            run.parsed_table_count = sync["parsed"]
            run.skipped_table_count = sync["skipped"]
            run.failed_table_count = sync["failed"]
            run.stats = sync["stats"]
            run.finished_at = utcnow()
            self.session.flush()
            return {
                "catalog_connection_id": catalog_connection_id,
                "namespace_count": sync["namespace_count"],
                "table_count": sync["table_count"],
                "discovered_table_count": sync["discovered"],
                "removed_table_count": sync["removed"],
                "parsed_table_count": sync["parsed"],
                "skipped_table_count": sync["skipped"],
                "failed_table_count": sync["failed"],
                "mode": run.mode,
                "sync_run_id": run.id,
                "refreshed_at": run.finished_at,
                "errors": sync["errors"],
                "worker_count": sync["stats"].get("worker_count", 1),
                "parse_job_count": sync["stats"].get("parse_job_count", 0),
            }
        except Exception as exc:
            run.status = "failed"
            run.error = str(exc)
            run.finished_at = utcnow()
            self.session.flush()
            raise

    def _sync_jdbc_catalog(
        self, workspace_id: str, catalog: CatalogConnection, *, force: bool
    ) -> dict[str, object]:
        if not catalog.endpoint:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="JDBC URI is missing.",
            )
        uri = catalog.endpoint.removeprefix("jdbc:")
        if not uri.startswith(("postgresql://", "postgres://")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Live table sync currently supports PostgreSQL JDBC catalogs.",
            )

        settings = catalog.settings if isinstance(catalog.settings, dict) else {}
        auth = (
            settings.get("catalog_auth")
            if isinstance(settings.get("catalog_auth"), dict)
            else {}
        )
        secret = self._read_inline_secret(
            workspace_id, self._auth_secret_id(auth, catalog.auth_ref)
        )
        rows = self._read_postgres_jdbc_catalog_rows(
            uri=uri,
            username=str(auth.get("username") or secret.get("username") or ""),
            password=secret.get("password"),
            jdbc_options=(
                settings.get("jdbc_options")
                if isinstance(settings.get("jdbc_options"), dict)
                else {}
            ),
        )
        refreshed_at = utcnow()
        namespace_ids: dict[str, str] = {}
        for namespace_name in sorted({row["namespace"] for row in rows}):
            namespace = self.session.scalar(
                select(Namespace).where(
                    Namespace.workspace_id == workspace_id,
                    Namespace.catalog_connection_id == catalog.id,
                    Namespace.name == namespace_name,
                )
            )
            if not namespace:
                namespace = Namespace(
                    workspace_id=workspace_id,
                    catalog_connection_id=catalog.id,
                    name=namespace_name,
                )
                self.session.add(namespace)
                self.session.flush()
            namespace_ids[namespace_name] = namespace.id

        seen_table_names: set[str] = set()
        discovered = 0
        parsed = 0
        skipped = 0
        failed = 0
        errors: list[dict[str, str]] = []
        reader = self._live_reader(workspace_id, catalog)
        parse_jobs: list[tuple[IcebergTable, str, str]] = []
        for row in rows:
            table_name = f"{row['namespace']}.{row['table_name']}"
            seen_table_names.add(table_name)
            namespace_id = namespace_ids[row["namespace"]]
            metadata_location = row["metadata_location"]
            properties = {
                "catalog_name": row["catalog_name"],
                "iceberg_type": row["iceberg_type"],
                "metadata_location": metadata_location,
                "previous_metadata_location": row["previous_metadata_location"],
                "sync_source": "jdbc_catalog",
            }
            table = self.session.scalar(
                select(IcebergTable).where(
                    IcebergTable.workspace_id == workspace_id,
                    IcebergTable.namespace_id == namespace_id,
                    IcebergTable.name == table_name,
                )
            )
            prior_metadata_location = table.metadata_location if table else None
            if not table:
                table = IcebergTable(
                    workspace_id=workspace_id,
                    namespace_id=namespace_id,
                    environment_id=catalog.environment_id,
                    name=table_name,
                    location=self._table_location_from_metadata(metadata_location),
                    format_version=2,
                    current_snapshot_id=None,
                    metadata_location=metadata_location,
                    previous_metadata_location=row["previous_metadata_location"],
                    owner=row["owner"],
                    properties=properties,
                    indexed_at=refreshed_at,
                )
                self.session.add(table)
                self.session.flush()
                self.session.add(
                    TableMetrics(
                        table_id=table.id,
                        file_count=0,
                        data_size_bytes=0,
                        delete_file_count=0,
                        snapshot_count=0,
                        manifest_count=0,
                        small_file_ratio=0,
                        last_commit_at=None,
                        last_compaction_at=None,
                    )
                )
                discovered += 1
            else:
                table.environment_id = catalog.environment_id
                table.location = self._table_location_from_metadata(metadata_location)
                table.metadata_location = metadata_location
                table.previous_metadata_location = row["previous_metadata_location"]
                table.owner = row["owner"] or table.owner
                table.properties = {**(table.properties or {}), **properties}
                table.indexed_at = refreshed_at

            if (
                not force
                and table.properties
                and table.properties.get("sync_source") == "live_metadata"
                and prior_metadata_location == metadata_location
                and table.metrics is not None
            ):
                skipped += 1
                continue

            parse_jobs.append((table, table_name, metadata_location))

        settings = get_settings()
        worker_count = max(
            1,
            min(settings.metadata_sync_workers, len(parse_jobs) or 1),
        )
        parse_results: list[tuple[IcebergTable, str, Any | None, str | None]] = []
        if parse_jobs:
            parse_results = self._parse_metadata_jobs(
                reader=reader,
                jobs=parse_jobs,
                worker_count=worker_count,
                table_timeout_seconds=settings.metadata_sync_table_timeout_seconds,
            )

        for table, table_name, parsed_metadata, parse_error in parse_results:
            if parse_error:
                failed += 1
                error = {"table": table_name, "error": parse_error}
                errors.append(error)
                table.properties = {
                    **(table.properties or {}),
                    "sync_source": "jdbc_catalog",
                    "metadata_parse_error": parse_error,
                }
                continue
            if parsed_metadata is None:
                failed += 1
                parse_error = "Metadata parser returned no table metadata."
                errors.append({"table": table_name, "error": parse_error})
                table.properties = {
                    **(table.properties or {}),
                    "sync_source": "jdbc_catalog",
                    "metadata_parse_error": parse_error,
                }
                continue
            self._replace_table_metadata(table, parsed_metadata, refreshed_at)
            parsed += 1

        existing_tables = list(
            self.session.scalars(
                select(IcebergTable)
                .join(Namespace, IcebergTable.namespace_id == Namespace.id)
                .where(
                    IcebergTable.workspace_id == workspace_id,
                    Namespace.catalog_connection_id == catalog.id,
                )
            )
        )
        stale_ids = [table.id for table in existing_tables if table.name not in seen_table_names]
        if stale_ids:
            self._delete_table_rows(stale_ids)

        self.session.flush()
        namespace_count = int(
            self.session.scalar(
                select(func.count(Namespace.id)).where(
                    Namespace.workspace_id == workspace_id,
                    Namespace.catalog_connection_id == catalog.id,
                )
            )
            or 0
        )
        return {
            "namespace_count": namespace_count,
            "table_count": len(rows),
            "discovered": discovered,
            "removed": len(stale_ids),
            "parsed": parsed,
            "skipped": skipped,
            "failed": failed,
            "errors": errors,
            "stats": {
                "metadata_source": "jdbc_catalog",
                "force": force,
                "parsed": parsed,
                "skipped": skipped,
                "failed": failed,
                "worker_count": worker_count,
                "parse_job_count": len(parse_jobs),
                "table_timeout_seconds": settings.metadata_sync_table_timeout_seconds,
                "s3_connect_timeout_seconds": settings.metadata_sync_s3_connect_timeout_seconds,
                "s3_request_timeout_seconds": settings.metadata_sync_s3_request_timeout_seconds,
                "manifest_history": "current_snapshot",
            },
        }

    def _parse_metadata_jobs(
        self,
        *,
        reader: LiveIcebergReader,
        jobs: list[tuple[IcebergTable, str, str]],
        worker_count: int,
        table_timeout_seconds: int,
    ) -> list[tuple[IcebergTable, str, Any | None, str | None]]:
        def parse_table(metadata_location: str) -> Any:
            thread_reader = LiveIcebergReader(
                catalog=reader.catalog,
                object_store=reader.object_store,
                catalog_secret=reader.catalog_secret,
                storage_secret=reader.storage_secret,
            )
            return thread_reader.parse_table(metadata_location)

        results: list[tuple[IcebergTable, str, Any | None, str | None]] = []
        executor = ThreadPoolExecutor(
            max_workers=worker_count, thread_name_prefix="iceyard-metadata-sync"
        )
        futures = {
            executor.submit(parse_table, metadata_location): (table, table_name)
            for table, table_name, metadata_location in jobs
        }
        started_at = {future: time.monotonic() for future in futures}
        pending = set(futures)
        try:
            while pending:
                done, pending = wait(pending, timeout=1, return_when=FIRST_COMPLETED)
                for future in done:
                    table, table_name = futures[future]
                    try:
                        results.append((table, table_name, future.result(), None))
                    except Exception as exc:
                        results.append((table, table_name, None, str(exc)))

                now = time.monotonic()
                timed_out = [
                    future
                    for future in pending
                    if now - started_at[future] >= table_timeout_seconds
                ]
                for future in timed_out:
                    table, table_name = futures[future]
                    future.cancel()
                    pending.remove(future)
                    results.append(
                        (
                            table,
                            table_name,
                            None,
                            (
                                "Timed out after "
                                f"{table_timeout_seconds}s while reading Iceberg metadata."
                            ),
                        )
                    )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        return results

    def _read_postgres_jdbc_catalog_rows(
        self,
        *,
        uri: str,
        username: str,
        password: str | None,
        jdbc_options: dict[str, object],
    ) -> list[dict[str, str | None]]:
        try:
            import psycopg
        except ImportError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="psycopg is required for PostgreSQL JDBC catalog sync.",
            ) from exc

        root_cert_path: str | None = None
        connect_kwargs: dict[str, object] = {"connect_timeout": 10}
        if username:
            connect_kwargs["user"] = username
        if password:
            connect_kwargs["password"] = password.strip()
        sslmode = jdbc_options.get("sslmode")
        if isinstance(sslmode, str) and sslmode:
            connect_kwargs["sslmode"] = sslmode
        root_cert = jdbc_options.get("ssl_root_cert")
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
        try:
            with (
                psycopg.connect(uri, **connect_kwargs) as connection,
                connection.cursor() as cursor,
            ):
                cursor.execute(
                    """
                    select
                      t.catalog_name,
                      t.table_namespace,
                      t.table_name,
                      t.metadata_location,
                      t.previous_metadata_location,
                      t.iceberg_type,
                      max(case when p.property_key = 'owner' then p.property_value end) as owner
                    from public.iceberg_tables t
                    left join public.iceberg_namespace_properties p
                      on p.catalog_name = t.catalog_name
                     and p.namespace = t.table_namespace
                    where coalesce(t.iceberg_type, 'TABLE') = 'TABLE'
                    group by
                      t.catalog_name,
                      t.table_namespace,
                      t.table_name,
                      t.metadata_location,
                      t.previous_metadata_location,
                      t.iceberg_type
                    order by t.table_namespace, t.table_name
                    """
                )
                return [
                    {
                        "catalog_name": row[0],
                        "namespace": row[1],
                        "table_name": row[2],
                        "metadata_location": row[3],
                        "previous_metadata_location": row[4],
                        "iceberg_type": row[5],
                        "owner": row[6],
                    }
                    for row in cursor.fetchall()
                    if row[1] and row[2] and row[3]
                ]
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Catalog sync failed: {exc}",
            ) from exc
        finally:
            if root_cert_path:
                with suppress(OSError):
                    os.unlink(root_cert_path)

    def _read_postgres_database_schema(
        self,
        *,
        uri: str,
        username: str,
        password: str | None,
        jdbc_options: dict[str, object],
    ) -> dict[str, Any]:
        try:
            import psycopg
        except ImportError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="psycopg is required for PostgreSQL JDBC catalog inspection.",
            ) from exc

        root_cert_path: str | None = None
        connect_kwargs: dict[str, object] = {"connect_timeout": 10}
        if username:
            connect_kwargs["user"] = username
        if password:
            connect_kwargs["password"] = password.strip()
        sslmode = jdbc_options.get("sslmode")
        if isinstance(sslmode, str) and sslmode:
            connect_kwargs["sslmode"] = sslmode
        root_cert = jdbc_options.get("ssl_root_cert")
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
        try:
            from psycopg import sql

            with (
                psycopg.connect(uri, **connect_kwargs) as connection,
                connection.cursor() as cursor,
            ):
                cursor.execute(
                    """
                    select table_schema, table_name
                    from information_schema.tables
                    where table_schema not in ('pg_catalog', 'information_schema')
                    order by table_schema, table_name
                    """
                )
                tables = [{"schema": row[0], "name": row[1]} for row in cursor.fetchall()]
                for table in tables:
                    cursor.execute(
                        """
                        select column_name, data_type, is_nullable
                        from information_schema.columns
                        where table_schema = %s and table_name = %s
                        order by ordinal_position
                        """,
                        (table["schema"], table["name"]),
                    )
                    table["columns"] = [
                        {"name": row[0], "type": row[1], "nullable": row[2] == "YES"}
                        for row in cursor.fetchall()
                    ]
                    cursor.execute(
                        """
                        select count(*)::bigint
                        from pg_catalog.pg_class c
                        join pg_catalog.pg_namespace n on n.oid = c.relnamespace
                        where n.nspname = %s and c.relname = %s
                        """,
                        (table["schema"], table["name"]),
                    )
                    table["catalog_rows"] = None
                    if table["name"] in {"iceberg_tables", "iceberg_namespace_properties"}:
                        cursor.execute(
                            sql.SQL("select count(*)::bigint from {}.{}").format(
                                sql.Identifier(table["schema"]),
                                sql.Identifier(table["name"]),
                            )
                        )
                        table["row_count"] = int(cursor.fetchone()[0])
                cursor.execute(
                    """
                    select schemaname, tablename, indexname, indexdef
                    from pg_indexes
                    where schemaname not in ('pg_catalog', 'information_schema')
                    order by schemaname, tablename, indexname
                    """
                )
                indexes = [
                    {"schema": row[0], "table": row[1], "name": row[2], "definition": row[3]}
                    for row in cursor.fetchall()
                ]
                return {"tables": tables, "indexes": indexes}
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Catalog database schema inspection failed: {exc}",
            ) from exc
        finally:
            if root_cert_path:
                with suppress(OSError):
                    os.unlink(root_cert_path)

    def _auth_secret_id(self, auth_settings: dict[str, object], auth_ref: str | None) -> str | None:
        secret_id = auth_settings.get("secret_ref_id")
        return secret_id if isinstance(secret_id, str) and secret_id else auth_ref

    def _read_inline_secret(self, workspace_id: str, secret_id: str | None) -> dict[str, str]:
        if not secret_id:
            return {}
        from iceyard_api.connections.service import ConnectionService

        return ConnectionService(self.session)._read_inline_secret(workspace_id, secret_id)

    def _linked_object_store(
        self,
        workspace_id: str,
        catalog: CatalogConnection,
    ) -> ObjectStoreConnection | None:
        settings = catalog.settings if isinstance(catalog.settings, dict) else {}
        store_id = settings.get("object_store_connection_id")
        if not isinstance(store_id, str) or not store_id:
            return None
        return self.session.scalar(
            select(ObjectStoreConnection).where(
                ObjectStoreConnection.workspace_id == workspace_id,
                ObjectStoreConnection.id == store_id,
            )
        )

    def _live_reader(self, workspace_id: str, catalog: CatalogConnection) -> LiveIcebergReader:
        settings = catalog.settings if isinstance(catalog.settings, dict) else {}
        auth = settings.get("catalog_auth")
        catalog_auth = auth if isinstance(auth, dict) else {}
        object_store = self._linked_object_store(workspace_id, catalog)
        store_settings = (
            object_store.settings
            if object_store and isinstance(object_store.settings, dict)
            else {}
        )
        storage_auth = store_settings.get("storage_auth")
        storage_auth = storage_auth if isinstance(storage_auth, dict) else {}
        return LiveIcebergReader(
            catalog=catalog,
            object_store=object_store,
            catalog_secret=self._read_inline_secret(
                workspace_id, self._auth_secret_id(catalog_auth, catalog.auth_ref)
            ),
            storage_secret=self._read_inline_secret(
                workspace_id,
                self._auth_secret_id(
                    storage_auth, object_store.auth_ref if object_store else None
                ),
            ),
        )

    def _replace_table_metadata(
        self, table: IcebergTable, parsed: Any, refreshed_at: datetime
    ) -> None:
        self._delete_table_metadata_children([table.id])
        updates = parsed.table_updates
        table.format_version = int(updates.get("format_version") or table.format_version)
        table.table_uuid = updates.get("table_uuid")
        table.metadata_location = updates.get("metadata_location")
        table.previous_metadata_location = updates.get("previous_metadata_location")
        table.location = updates.get("location") or table.location
        table.last_sequence_number = updates.get("last_sequence_number")
        table.last_updated_at = updates.get("last_updated_at")
        table.current_schema_id = updates.get("current_schema_id")
        table.default_spec_id = updates.get("default_spec_id")
        table.default_sort_order_id = updates.get("default_sort_order_id")
        table.current_snapshot_id = updates.get("current_snapshot_id")
        table.record_count = updates.get("record_count")
        properties = dict(table.properties or {})
        for stale_key in ("metadata_parse_error", "parse_errors"):
            properties.pop(stale_key, None)
        properties.update(updates.get("properties") or {})
        if not properties.get("parse_errors"):
            properties.pop("parse_errors", None)
        table.properties = properties
        table.indexed_at = refreshed_at

        metrics = self.session.scalar(select(TableMetrics).where(TableMetrics.table_id == table.id))
        if not metrics:
            metrics = TableMetrics(
                table_id=table.id,
                file_count=0,
                data_size_bytes=0,
                delete_file_count=0,
                snapshot_count=0,
                manifest_count=0,
                small_file_ratio=0,
                last_commit_at=None,
                last_compaction_at=None,
            )
            self.session.add(metrics)
        metrics.file_count = int(parsed.metrics.get("file_count") or 0)
        metrics.data_size_bytes = int(parsed.metrics.get("data_size_bytes") or 0)
        metrics.delete_file_count = int(parsed.metrics.get("delete_file_count") or 0)
        metrics.snapshot_count = int(parsed.metrics.get("snapshot_count") or 0)
        metrics.manifest_count = int(parsed.metrics.get("manifest_count") or 0)
        metrics.small_file_ratio = float(parsed.metrics.get("small_file_ratio") or 0)
        metrics.last_commit_at = parsed.metrics.get("last_commit_at")
        metrics.last_compaction_at = parsed.metrics.get("last_compaction_at")

        for schema in parsed.schemas:
            self.session.add(
                SchemaVersion(
                    table_id=table.id,
                    schema_id=int(schema["schema_id"]),
                    schema=schema["schema"],
                )
            )
        for spec in parsed.partition_specs:
            self.session.add(
                PartitionSpec(
                    table_id=table.id,
                    spec_id=int(spec["spec_id"]),
                    spec=spec["spec"],
                    is_current=bool(spec["is_current"]),
                )
            )
        for order in parsed.sort_orders:
            self.session.add(
                SortOrder(
                    table_id=table.id,
                    order_id=int(order["order_id"]),
                    fields=order["fields"],
                    is_current=bool(order["is_current"]),
                )
            )
        for snapshot in parsed.snapshots:
            summary = dict(snapshot["summary"])
            summary.update(
                {
                    "manifest_list": snapshot.get("manifest_list"),
                    "schema_id": snapshot.get("schema_id"),
                    "sequence_number": snapshot.get("sequence_number"),
                }
            )
            self.session.add(
                Snapshot(
                    table_id=table.id,
                    snapshot_id=snapshot["snapshot_id"],
                    parent_snapshot_id=snapshot.get("parent_snapshot_id"),
                    operation=snapshot["operation"],
                    summary=summary,
                    committed_at=snapshot["committed_at"],
                )
            )
        for ref in parsed.refs:
            if not ref.get("snapshot_id"):
                continue
            self.session.add(
                TableRef(
                    table_id=table.id,
                    name=ref["name"],
                    ref_type=ref["ref_type"],
                    snapshot_id=ref["snapshot_id"],
                    retention=ref["retention"],
                    is_protected=bool(ref["is_protected"]),
                )
            )
        for entry in parsed.metadata_log:
            self.session.add(
                MetadataLogEntry(
                    table_id=table.id,
                    timestamp_ms=entry.get("timestamp_ms"),
                    metadata_file=entry["metadata_file"],
                )
            )
        for entry in parsed.snapshot_log:
            self.session.add(
                SnapshotLogEntry(
                    table_id=table.id,
                    timestamp_ms=entry.get("timestamp_ms"),
                    snapshot_id=entry["snapshot_id"],
                )
            )
        for manifest in parsed.manifests:
            self.session.add(
                ManifestFileCache(
                    table_id=table.id,
                    snapshot_id=manifest["snapshot_id"],
                    manifest_path=manifest["manifest_path"],
                    content=manifest.get("content"),
                    partition_spec_id=manifest.get("partition_spec_id"),
                    sequence_number=manifest.get("sequence_number"),
                    manifest_length=manifest.get("manifest_length"),
                    added_files_count=int(manifest.get("added_files_count") or 0),
                    existing_files_count=int(manifest.get("existing_files_count") or 0),
                    deleted_files_count=int(manifest.get("deleted_files_count") or 0),
                    added_rows_count=int(manifest.get("added_rows_count") or 0),
                    existing_rows_count=int(manifest.get("existing_rows_count") or 0),
                    deleted_rows_count=int(manifest.get("deleted_rows_count") or 0),
                    partitions=manifest.get("partitions") or [],
                )
            )
        for file_entry in parsed.files:
            if not file_entry.get("file_path"):
                continue
            self.session.add(
                TableFileCache(
                    table_id=table.id,
                    snapshot_id=file_entry.get("snapshot_id"),
                    manifest_path=file_entry.get("manifest_path"),
                    entry_status=file_entry.get("entry_status"),
                    content=file_entry["content"],
                    file_path=file_entry["file_path"],
                    file_format=file_entry.get("file_format"),
                    spec_id=file_entry.get("spec_id"),
                    partition=file_entry.get("partition") or {},
                    record_count=int(file_entry.get("record_count") or 0),
                    file_size_in_bytes=int(file_entry.get("file_size_in_bytes") or 0),
                    column_sizes=file_entry.get("column_sizes") or {},
                    value_counts=file_entry.get("value_counts") or {},
                    null_value_counts=file_entry.get("null_value_counts") or {},
                    nan_value_counts=file_entry.get("nan_value_counts") or {},
                    lower_bounds=file_entry.get("lower_bounds") or {},
                    upper_bounds=file_entry.get("upper_bounds") or {},
                    key_metadata_present=bool(file_entry.get("key_metadata_present")),
                    split_offsets=file_entry.get("split_offsets") or [],
                    equality_ids=file_entry.get("equality_ids") or [],
                    sort_order_id=file_entry.get("sort_order_id"),
                )
            )
        for partition in parsed.partition_summaries:
            self.session.add(
                PartitionSummary(
                    table_id=table.id,
                    spec_id=int(partition.get("spec_id") or 0),
                    partition_key=partition["partition_key"],
                    partition=partition.get("partition") or {},
                    file_count=int(partition.get("file_count") or 0),
                    record_count=int(partition.get("record_count") or 0),
                    total_size_bytes=int(partition.get("total_size_bytes") or 0),
                    delete_file_count=int(partition.get("delete_file_count") or 0),
                )
            )

    def _delete_table_metadata_children(self, table_ids: list[str]) -> None:
        if not table_ids:
            return
        for model in (
            TableRef,
            SortOrder,
            PartitionSpec,
            SchemaVersion,
            Snapshot,
            MetadataLogEntry,
            SnapshotLogEntry,
            ManifestFileCache,
            TableFileCache,
            PartitionSummary,
        ):
            self.session.execute(delete(model).where(model.table_id.in_(table_ids)))

    def _delete_table_rows(self, table_ids: list[str]) -> None:
        if not table_ids:
            return
        self._delete_table_metadata_children(table_ids)
        self.session.execute(delete(TableMetrics).where(TableMetrics.table_id.in_(table_ids)))
        self.session.execute(delete(IcebergTable).where(IcebergTable.id.in_(table_ids)))

    def _table_location_from_metadata(self, metadata_location: str | None) -> str:
        if not metadata_location:
            return ""
        marker = "/metadata/"
        if marker in metadata_location:
            return metadata_location.split(marker, 1)[0]
        if "/" in metadata_location:
            return metadata_location.rsplit("/", 1)[0]
        return metadata_location

    def list_namespaces(
        self, workspace_id: str, catalog_connection_id: str | None = None
    ) -> list[Namespace]:
        stmt = (
            select(Namespace)
            .join(CatalogConnection, Namespace.catalog_connection_id == CatalogConnection.id)
            .where(
                Namespace.workspace_id == workspace_id,
                CatalogConnection.workspace_id == workspace_id,
            )
        )
        if catalog_connection_id:
            stmt = stmt.where(Namespace.catalog_connection_id == catalog_connection_id)
        return list(self.session.scalars(stmt.order_by(Namespace.name.asc())))

    def list_tables(
        self,
        workspace_id: str,
        *,
        environment_id: str | None = None,
        catalog_connection_id: str | None = None,
        namespace_id: str | None = None,
        min_health: int | None = None,
        max_health: int | None = None,
    ) -> list[IcebergTable]:
        stmt = (
            select(IcebergTable)
            .join(Namespace, IcebergTable.namespace_id == Namespace.id)
            .join(CatalogConnection, Namespace.catalog_connection_id == CatalogConnection.id)
            .where(
                IcebergTable.workspace_id == workspace_id,
                CatalogConnection.workspace_id == workspace_id,
            )
        )
        if environment_id:
            stmt = stmt.where(IcebergTable.environment_id == environment_id)
        if catalog_connection_id:
            stmt = stmt.where(Namespace.catalog_connection_id == catalog_connection_id)
        if namespace_id:
            stmt = stmt.where(IcebergTable.namespace_id == namespace_id)
        if min_health is not None:
            stmt = stmt.where(IcebergTable.health_score >= min_health)
        if max_health is not None:
            stmt = stmt.where(IcebergTable.health_score <= max_health)
        return list(
            self.session.scalars(
                stmt.order_by(IcebergTable.health_score.asc(), IcebergTable.name.asc())
            )
        )

    def get_table(self, workspace_id: str, table_id: str) -> IcebergTable | None:
        return self.session.scalar(
            select(IcebergTable)
            .join(Namespace, IcebergTable.namespace_id == Namespace.id)
            .join(CatalogConnection, Namespace.catalog_connection_id == CatalogConnection.id)
            .where(
                IcebergTable.workspace_id == workspace_id,
                CatalogConnection.workspace_id == workspace_id,
                IcebergTable.id == table_id,
            )
        )

    def list_snapshots(self, table_id: str) -> list[Snapshot]:
        return list(
            self.session.scalars(
                select(Snapshot)
                .where(Snapshot.table_id == table_id)
                .order_by(Snapshot.committed_at.desc())
            )
        )

    def list_refs(self, table_id: str) -> list[TableRef]:
        return list(self.session.scalars(select(TableRef).where(TableRef.table_id == table_id)))

    def list_schema_versions(self, table_id: str) -> list[SchemaVersion]:
        return list(
            self.session.scalars(
                select(SchemaVersion)
                .where(SchemaVersion.table_id == table_id)
                .order_by(SchemaVersion.schema_id)
            )
        )

    def list_partition_specs(self, table_id: str) -> list[PartitionSpec]:
        return list(
            self.session.scalars(
                select(PartitionSpec)
                .where(PartitionSpec.table_id == table_id)
                .order_by(PartitionSpec.spec_id)
            )
        )

    def list_sort_orders(self, table_id: str) -> list[SortOrder]:
        return list(
            self.session.scalars(
                select(SortOrder).where(SortOrder.table_id == table_id).order_by(SortOrder.order_id)
            )
        )

    def list_metadata_log(self, table_id: str) -> list[MetadataLogEntry]:
        return list(
            self.session.scalars(
                select(MetadataLogEntry)
                .where(MetadataLogEntry.table_id == table_id)
                .order_by(MetadataLogEntry.timestamp_ms.desc())
            )
        )

    def list_snapshot_log(self, table_id: str) -> list[SnapshotLogEntry]:
        return list(
            self.session.scalars(
                select(SnapshotLogEntry)
                .where(SnapshotLogEntry.table_id == table_id)
                .order_by(SnapshotLogEntry.timestamp_ms.desc())
            )
        )

    def list_sync_runs(
        self, workspace_id: str, catalog_connection_id: str | None = None
    ) -> list[MetadataSyncRun]:
        stmt = select(MetadataSyncRun).where(MetadataSyncRun.workspace_id == workspace_id)
        if catalog_connection_id:
            stmt = stmt.where(MetadataSyncRun.catalog_connection_id == catalog_connection_id)
        return list(
            self.session.scalars(stmt.order_by(MetadataSyncRun.started_at.desc()).limit(100))
        )

    def get_sync_run(self, workspace_id: str, sync_run_id: str) -> MetadataSyncRun | None:
        return self.session.scalar(
            select(MetadataSyncRun).where(
                MetadataSyncRun.workspace_id == workspace_id,
                MetadataSyncRun.id == sync_run_id,
            )
        )

    def database_schema(self, workspace_id: str, catalog_connection_id: str) -> dict[str, Any]:
        catalog = self.session.scalar(
            select(CatalogConnection).where(
                CatalogConnection.workspace_id == workspace_id,
                CatalogConnection.id == catalog_connection_id,
            )
        )
        if not catalog:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog not found.")
        if catalog.catalog_type != "jdbc":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Database schema inspection is only available for JDBC catalogs.",
            )
        if not catalog.endpoint:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="JDBC URI is missing.",
            )
        uri = catalog.endpoint.removeprefix("jdbc:")
        settings = catalog.settings if isinstance(catalog.settings, dict) else {}
        auth = settings.get("catalog_auth")
        auth_settings = auth if isinstance(auth, dict) else {}
        secret = self._read_inline_secret(
            workspace_id, self._auth_secret_id(auth_settings, catalog.auth_ref)
        )
        return self._read_postgres_database_schema(
            uri=uri,
            username=str(auth_settings.get("username") or secret.get("username") or ""),
            password=secret.get("password"),
            jdbc_options=(
                settings.get("jdbc_options")
                if isinstance(settings.get("jdbc_options"), dict)
                else {}
            ),
        )

    def preview_table_resource(self, table: IcebergTable, resource: str) -> dict[str, object]:
        resource = resource.lower().replace("-", "_")
        table_name = table.name
        schema = self.list_schema_versions(table.id)
        latest_schema = schema[-1].schema if schema else {"fields": []}
        row_columns = self._schema_columns(latest_schema)
        if resource == "rows":
            preview = self.preview_rows(table, limit=5)
            preview_columns = preview.get("columns")
            columns = (
                [str(column) for column in preview_columns]
                if isinstance(preview_columns, list) and preview_columns
                else row_columns
            )
            return {
                "resource": "rows",
                "rate_limited": True,
                "query": str(preview.get("query") or f"SELECT * FROM {table_name} LIMIT 5"),
                "columns": columns,
                "rows": preview.get("rows") if isinstance(preview.get("rows"), list) else [],
                "masked_columns": [],
            }
        resources = {
            "files": {
                "query": f"SELECT * FROM {table_name}.files LIMIT 5",
                "columns": [
                    "content",
                    "file_path",
                    "record_count",
                    "file_size_in_bytes",
                    "partition",
                ],
                "rows": self._file_preview_rows(table.id, content="DATA", limit=50),
                "masked_columns": ["file_path"],
            },
            "manifests": {
                "query": f"SELECT * FROM {table_name}.manifests LIMIT 5",
                "columns": [
                    "manifest_path",
                    "content",
                    "added_files_count",
                    "existing_files_count",
                    "deleted_files_count",
                ],
                "rows": self._manifest_preview_rows(table.id, limit=50),
                "masked_columns": ["manifest_path"],
            },
            "manifest_entries": {
                "query": f"SELECT * FROM {table_name}.manifest_entries LIMIT 5",
                "columns": [
                    "content",
                    "entry_status",
                    "file_path",
                    "record_count",
                    "file_size_in_bytes",
                    "partition",
                ],
                "rows": self._file_preview_rows(table.id, content=None, limit=50),
                "masked_columns": ["file_path"],
            },
            "snapshots": {
                "query": f"SELECT * FROM {table_name}.snapshots LIMIT 5",
                "columns": [
                    "snapshot_id",
                    "parent_snapshot_id",
                    "operation",
                    "committed_at",
                    "schema_id",
                    "sequence_number",
                    "summary",
                ],
                "rows": [
                    {
                        "snapshot_id": snapshot.snapshot_id,
                        "parent_snapshot_id": snapshot.parent_snapshot_id,
                        "operation": snapshot.operation,
                        "committed_at": snapshot.committed_at.isoformat(),
                        "schema_id": snapshot.summary.get("schema_id"),
                        "sequence_number": snapshot.summary.get("sequence_number"),
                        "summary": snapshot.summary,
                    }
                    for snapshot in self.list_snapshots(table.id)[:5]
                ],
                "masked_columns": [],
            },
            "partitions": {
                "query": f"SELECT * FROM {table_name}.partitions LIMIT 5",
                "columns": ["partition", "record_count", "file_count", "total_size"],
                "rows": self._partition_preview_rows(table.id, limit=50),
                "masked_columns": [],
            },
            "refs": {
                "query": f"SELECT * FROM {table_name}.refs",
                "columns": ["type", "name", "snapshot_id", "retention"],
                "rows": [
                    {
                        "type": ref.ref_type,
                        "name": ref.name,
                        "snapshot_id": ref.snapshot_id,
                        "retention": ref.retention,
                    }
                    for ref in self.list_refs(table.id)
                ],
                "masked_columns": [],
            },
            "position_deletes": {
                "query": f"SELECT * FROM {table_name}.position_deletes LIMIT 5",
                "columns": ["file_path", "record_count", "file_size_in_bytes", "partition"],
                "rows": self._file_preview_rows(
                    table.id,
                    content="POSITION_DELETES",
                    limit=50,
                ),
                "masked_columns": ["delete_file_path"],
            },
            "delete_files": {
                "query": f"SELECT * FROM {table_name}.delete_files LIMIT 5",
                "columns": [
                    "content",
                    "file_path",
                    "record_count",
                    "file_size_in_bytes",
                    "partition",
                ],
                "rows": self._file_preview_rows(table.id, content="delete", limit=50),
                "masked_columns": ["file_path"],
            },
            "metadata_log": {
                "query": f"SELECT * FROM {table_name}.metadata_log",
                "columns": ["timestamp_ms", "metadata_file"],
                "rows": self._metadata_log_preview_rows(table.id, limit=50),
                "masked_columns": ["metadata_file"],
            },
        }
        if resource not in resources:
            return self.preview_table_resource(table, "rows")
        selected = resources[resource]
        return {
            "resource": resource,
            "rate_limited": True,
            **selected,
        }

    def preview_rows(
        self,
        table: IcebergTable,
        *,
        limit: int,
        selected_fields: tuple[str, ...] = ("*",),
        snapshot_id: int | None = None,
    ) -> dict[str, object]:
        if not table.metadata_location:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Table metadata has not been synced yet.",
            )
        catalog = self._catalog_for_table(table)
        if not catalog:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Catalog connection for this table was not found.",
            )
        try:
            return self._live_reader(table.workspace_id, catalog).preview_rows(
                table.metadata_location,
                limit=max(1, min(limit, 100)),
                selected_fields=selected_fields,
                snapshot_id=snapshot_id,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Bounded row preview requires readable data files: {exc}",
            ) from exc

    def _catalog_for_table(self, table: IcebergTable) -> CatalogConnection | None:
        return self.session.scalar(
            select(CatalogConnection)
            .join(Namespace, Namespace.catalog_connection_id == CatalogConnection.id)
            .where(
                Namespace.id == table.namespace_id,
                CatalogConnection.workspace_id == table.workspace_id,
            )
        )

    def _schema_columns(self, schema: dict[str, Any]) -> list[str]:
        fields = schema.get("fields")
        if not isinstance(fields, list):
            return []
        return [
            str(field.get("name"))
            for field in fields
            if isinstance(field, dict) and field.get("name")
        ]

    def _file_preview_rows(
        self, table_id: str, *, content: str | None, limit: int
    ) -> list[dict[str, Any]]:
        stmt = select(TableFileCache).where(TableFileCache.table_id == table_id)
        if content == "delete":
            stmt = stmt.where(TableFileCache.content != "DATA")
        elif content:
            stmt = stmt.where(TableFileCache.content == content)
        rows = list(
            self.session.scalars(
                stmt.order_by(
                    TableFileCache.snapshot_id.desc(),
                    TableFileCache.file_path.asc(),
                ).limit(limit)
            )
        )
        return [
            {
                "content": row.content,
                "entry_status": row.entry_status,
                "file_path": row.file_path,
                "file_format": row.file_format,
                "spec_id": row.spec_id,
                "partition": row.partition,
                "record_count": row.record_count,
                "file_size_in_bytes": row.file_size_in_bytes,
                "column_sizes": row.column_sizes,
                "value_counts": row.value_counts,
                "null_value_counts": row.null_value_counts,
                "lower_bounds": row.lower_bounds,
                "upper_bounds": row.upper_bounds,
            }
            for row in rows
        ]

    def _manifest_preview_rows(self, table_id: str, *, limit: int) -> list[dict[str, Any]]:
        rows = list(
            self.session.scalars(
                select(ManifestFileCache)
                .where(ManifestFileCache.table_id == table_id)
                .order_by(
                    ManifestFileCache.snapshot_id.desc(),
                    ManifestFileCache.manifest_path.asc(),
                )
                .limit(limit)
            )
        )
        return [
            {
                "snapshot_id": row.snapshot_id,
                "manifest_path": row.manifest_path,
                "content": row.content,
                "partition_spec_id": row.partition_spec_id,
                "sequence_number": row.sequence_number,
                "manifest_length": row.manifest_length,
                "added_files_count": row.added_files_count,
                "existing_files_count": row.existing_files_count,
                "deleted_files_count": row.deleted_files_count,
                "partitions": row.partitions,
            }
            for row in rows
        ]

    def _partition_preview_rows(self, table_id: str, *, limit: int) -> list[dict[str, Any]]:
        rows = list(
            self.session.scalars(
                select(PartitionSummary)
                .where(PartitionSummary.table_id == table_id)
                .order_by(PartitionSummary.total_size_bytes.desc())
                .limit(limit)
            )
        )
        return [
            {
                "partition": row.partition,
                "record_count": row.record_count,
                "file_count": row.file_count,
                "total_size": row.total_size_bytes,
                "delete_file_count": row.delete_file_count,
            }
            for row in rows
        ]

    def _metadata_log_preview_rows(self, table_id: str, *, limit: int) -> list[dict[str, Any]]:
        rows = list(
            self.session.scalars(
                select(MetadataLogEntry)
                .where(MetadataLogEntry.table_id == table_id)
                .order_by(MetadataLogEntry.timestamp_ms.desc())
                .limit(limit)
            )
        )
        return [
            {"timestamp_ms": row.timestamp_ms, "metadata_file": row.metadata_file}
            for row in rows
        ]
