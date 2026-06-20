from __future__ import annotations

import json
from collections import defaultdict
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from fastapi import HTTPException, status

from iceyard_api.core.config import get_settings
from iceyard_api.db.models import CatalogConnection, ObjectStoreConnection


def ms_to_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=UTC)
    except (TypeError, ValueError, OSError):
        return None


def normalize_object_location(location: str) -> str:
    if location.startswith("s3a://") or location.startswith("s3n://"):
        return f"s3://{location.split('://', 1)[1]}"
    return location


def to_plain(value: object) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.name
    if hasattr(value, "model_dump"):
        return to_plain(value.model_dump(by_alias=True, mode="json"))
    if hasattr(value, "dict"):
        return to_plain(value.dict(by_alias=True))
    if isinstance(value, dict):
        return {str(to_plain(key)): to_plain(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [to_plain(item) for item in value]
    if hasattr(value, "__dict__"):
        return {
            key.lstrip("_"): to_plain(item)
            for key, item in vars(value).items()
            if not key.startswith("__")
        }
    return str(value)


def enum_name(value: object) -> str:
    if isinstance(value, Enum):
        return value.name
    if hasattr(value, "name"):
        name = value.name
        if isinstance(name, str):
            return name
    text = str(value)
    return text.rsplit(".", 1)[-1].upper()


def int_value(value: object, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def dict_value(value: object) -> dict[str, Any]:
    plain = to_plain(value)
    return plain if isinstance(plain, dict) else {}


def list_value(value: object) -> list[Any]:
    plain = to_plain(value)
    return plain if isinstance(plain, list) else []


@dataclass
class ParsedIcebergMetadata:
    table_updates: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    schemas: list[dict[str, Any]] = field(default_factory=list)
    partition_specs: list[dict[str, Any]] = field(default_factory=list)
    sort_orders: list[dict[str, Any]] = field(default_factory=list)
    snapshots: list[dict[str, Any]] = field(default_factory=list)
    refs: list[dict[str, Any]] = field(default_factory=list)
    metadata_log: list[dict[str, Any]] = field(default_factory=list)
    snapshot_log: list[dict[str, Any]] = field(default_factory=list)
    manifests: list[dict[str, Any]] = field(default_factory=list)
    files: list[dict[str, Any]] = field(default_factory=list)
    partition_summaries: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class LiveIcebergReader:
    def __init__(
        self,
        *,
        catalog: CatalogConnection,
        object_store: ObjectStoreConnection | None,
        catalog_secret: dict[str, str],
        storage_secret: dict[str, str],
    ):
        self.catalog = catalog
        self.object_store = object_store
        self.catalog_secret = catalog_secret
        self.storage_secret = storage_secret

    def parse_table(
        self, metadata_location: str, *, force_full_history: bool = False
    ) -> ParsedIcebergMetadata:
        table = self._load_static_table(metadata_location)
        metadata = to_plain(table.metadata)
        if not isinstance(metadata, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Iceberg table metadata could not be decoded.",
            )

        result = ParsedIcebergMetadata()
        current_snapshot_id = self._current_snapshot_id(table, metadata)
        result.table_updates = {
            "format_version": int_value(metadata.get("format-version"), 1),
            "table_uuid": str(metadata.get("table-uuid") or "") or None,
            "metadata_location": metadata_location,
            "previous_metadata_location": self._previous_metadata_location(metadata),
            "location": str(metadata.get("location") or ""),
            "last_sequence_number": int_value(metadata.get("last-sequence-number"), 0),
            "last_updated_at": ms_to_datetime(metadata.get("last-updated-ms")),
            "current_schema_id": self._optional_int(metadata.get("current-schema-id")),
            "default_spec_id": self._optional_int(metadata.get("default-spec-id")),
            "default_sort_order_id": self._optional_int(metadata.get("default-sort-order-id")),
            "current_snapshot_id": current_snapshot_id,
            "properties": dict_value(metadata.get("properties")),
        }
        result.schemas = self._schemas(table, metadata)
        result.partition_specs = self._partition_specs(table, metadata)
        result.sort_orders = self._sort_orders(table, metadata)
        result.snapshots = self._snapshots(table)
        result.refs = self._refs(table)
        result.metadata_log = [
            {
                "timestamp_ms": entry.get("timestamp-ms"),
                "metadata_file": str(entry.get("metadata-file") or ""),
            }
            for entry in list_value(metadata.get("metadata-log"))
            if isinstance(entry, dict) and entry.get("metadata-file")
        ]
        result.snapshot_log = [
            {
                "timestamp_ms": entry.get("timestamp-ms"),
                "snapshot_id": str(entry.get("snapshot-id") or ""),
            }
            for entry in list_value(metadata.get("snapshot-log"))
            if isinstance(entry, dict) and entry.get("snapshot-id")
        ]

        snapshots_to_parse = result.snapshots if force_full_history else [
            item for item in result.snapshots if item["snapshot_id"] == current_snapshot_id
        ]
        current_files: list[dict[str, Any]] = []
        for snapshot in snapshots_to_parse:
            manifest_list = snapshot.get("manifest_list")
            if not manifest_list:
                continue
            try:
                manifests = self._manifest_files(table, str(manifest_list), snapshot["snapshot_id"])
            except Exception as exc:
                result.errors.append(
                    f"Manifest list read failed for {snapshot['snapshot_id']}: {exc}"
                )
                continue
            result.manifests.extend(manifests)
            for manifest in manifests:
                try:
                    files = self._manifest_entries(table, manifest)
                except Exception as exc:
                    result.errors.append(
                        f"Manifest read failed for {manifest['manifest_path']}: {exc}"
                    )
                    continue
                result.files.extend(files)
                if snapshot["snapshot_id"] == current_snapshot_id:
                    current_files.extend(
                        file for file in files if file.get("entry_status") != "DELETED"
                    )

        result.metrics = self._metrics(result.snapshots, result.manifests, current_files)
        result.table_updates["record_count"] = result.metrics["record_count"]
        result.partition_summaries = self._partition_summaries(current_files)
        sync_properties = {
            **result.table_updates["properties"],
            "metadata_location": metadata_location,
            "sync_source": "live_metadata",
        }
        if result.errors:
            sync_properties["parse_errors"] = result.errors
        result.table_updates["properties"] = sync_properties
        return result

    def preview_rows(
        self,
        metadata_location: str,
        *,
        limit: int,
        selected_fields: tuple[str, ...] = ("*",),
        snapshot_id: int | None = None,
    ) -> dict[str, Any]:
        table = self._load_static_table(metadata_location)
        scan = table.scan(selected_fields=selected_fields, snapshot_id=snapshot_id, limit=limit)
        arrow_table = scan.to_arrow()
        rows = [dict(row) for row in arrow_table.to_pylist()[:limit]]
        columns = list(arrow_table.column_names)
        identifier = getattr(table, "identifier", None) or getattr(table, "_identifier", None)
        if isinstance(identifier, tuple | list):
            table_label = ".".join(str(part) for part in identifier)
        else:
            table_label = str(identifier or metadata_location)
        return {
            "columns": columns,
            "rows": rows,
            "query": (
                f"SELECT {', '.join(columns) if columns else '*'} "
                f"FROM {table_label} LIMIT {limit}"
            ),
        }

    def iceberg_properties(self) -> dict[str, str]:
        try:
            from pyiceberg.io import (
                FSSPEC_FILE_IO,
                PY_IO_IMPL,
                S3_ACCESS_KEY_ID,
                S3_CONNECT_TIMEOUT,
                S3_ENDPOINT,
                S3_FORCE_VIRTUAL_ADDRESSING,
                S3_REGION,
                S3_REQUEST_TIMEOUT,
                S3_SECRET_ACCESS_KEY,
                S3_SESSION_TOKEN,
            )
        except ImportError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="PyIceberg is required for live metadata sync.",
            ) from exc

        properties: dict[str, str] = {PY_IO_IMPL: FSSPEC_FILE_IO}
        app_settings = get_settings()
        settings = self.object_store.settings if self.object_store else self.catalog.settings
        settings = settings if isinstance(settings, dict) else {}
        endpoint = self.object_store.endpoint if self.object_store else settings.get("endpoint")
        region = self.object_store.region if self.object_store else settings.get("region")
        if isinstance(endpoint, str) and endpoint:
            properties[S3_ENDPOINT] = endpoint
        if isinstance(region, str) and region:
            properties[S3_REGION] = region
        properties[S3_CONNECT_TIMEOUT] = str(
            app_settings.metadata_sync_s3_connect_timeout_seconds
        )
        properties[S3_REQUEST_TIMEOUT] = str(
            app_settings.metadata_sync_s3_request_timeout_seconds
        )
        if settings.get("access_style") == "virtual-hosted":
            properties[S3_FORCE_VIRTUAL_ADDRESSING] = "true"
        storage_auth = settings.get("storage_auth")
        storage_auth = storage_auth if isinstance(storage_auth, dict) else {}
        access_key_id = storage_auth.get("aws_access_key_id")
        if isinstance(access_key_id, str) and access_key_id:
            properties[S3_ACCESS_KEY_ID] = access_key_id
        if secret := self.storage_secret.get("aws_secret_access_key"):
            properties[S3_SECRET_ACCESS_KEY] = secret
        if token := self.storage_secret.get("aws_session_token"):
            properties[S3_SESSION_TOKEN] = token
        return properties

    def _load_static_table(self, metadata_location: str):
        try:
            from pyiceberg.table import StaticTable
        except ImportError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="PyIceberg is required for live metadata sync.",
            ) from exc

        return StaticTable.from_metadata(
            normalize_object_location(metadata_location),
            self.iceberg_properties(),
        )

    def _current_snapshot_id(self, table: object, metadata: dict[str, Any]) -> str | None:
        try:
            snapshot = table.current_snapshot()
        except Exception:
            snapshot = None
        if snapshot:
            snapshot_id = getattr(snapshot, "snapshot_id", None)
            if snapshot_id is not None:
                return str(snapshot_id)
        value = metadata.get("current-snapshot-id")
        return str(value) if value is not None else None

    def _previous_metadata_location(self, metadata: dict[str, Any]) -> str | None:
        metadata_log = list_value(metadata.get("metadata-log"))
        if not metadata_log:
            return None
        latest = metadata_log[-1]
        if isinstance(latest, dict) and latest.get("metadata-file"):
            return str(latest["metadata-file"])
        return None

    def _schemas(self, table: object, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        raw_schemas = [
            schema for schema in list_value(metadata.get("schemas")) if isinstance(schema, dict)
        ]
        if not raw_schemas:
            legacy_schema = dict_value(metadata.get("schema"))
            if legacy_schema:
                raw_schemas = [legacy_schema]
        if not raw_schemas:
            try:
                schemas = list(table.schemas())
            except Exception:
                schemas = []
            raw_schemas = [
                schema
                for schema in (dict_value(schema) for schema in schemas)
                if schema.get("fields")
            ]
        return [
            {
                "schema_id": int_value(schema.get("schema-id") or schema.get("schema_id"), index),
                "schema": schema,
            }
            for index, schema in enumerate(raw_schemas)
        ]

    def _partition_specs(self, table: object, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            specs = table.specs()
            raw_specs = list(specs.values()) if isinstance(specs, dict) else list(specs)
        except Exception:
            raw_specs = list_value(metadata.get("partition-specs"))
        default_spec_id = self._optional_int(metadata.get("default-spec-id"))
        return [
            {
                "spec_id": int_value(spec.get("spec-id") or spec.get("spec_id"), index),
                "spec": spec,
                "is_current": int_value(spec.get("spec-id") or spec.get("spec_id"), index)
                == default_spec_id,
            }
            for index, spec in enumerate(dict_value(item) for item in raw_specs)
        ]

    def _sort_orders(self, table: object, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            orders = table.sort_orders()
            raw_orders = list(orders.values()) if isinstance(orders, dict) else list(orders)
        except Exception:
            raw_orders = list_value(metadata.get("sort-orders"))
        default_order_id = self._optional_int(metadata.get("default-sort-order-id"))
        return [
            {
                "order_id": int_value(order.get("order-id") or order.get("order_id"), index),
                "fields": list_value(order.get("fields")),
                "is_current": int_value(order.get("order-id") or order.get("order_id"), index)
                == default_order_id,
            }
            for index, order in enumerate(dict_value(item) for item in raw_orders)
        ]

    def _snapshots(self, table: object) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for snapshot in table.snapshots():
            data = dict_value(snapshot)
            snapshot_id = str(
                data.get("snapshot-id")
                or data.get("snapshot_id")
                or getattr(snapshot, "snapshot_id", "")
            )
            if not snapshot_id:
                continue
            timestamp_ms = (
                data.get("timestamp-ms")
                or data.get("timestamp_ms")
                or getattr(snapshot, "timestamp_ms", None)
            )
            rows.append(
                {
                    "snapshot_id": snapshot_id,
                    "parent_snapshot_id": self._optional_str(
                        data.get("parent-snapshot-id")
                        or data.get("parent_snapshot_id")
                        or getattr(snapshot, "parent_snapshot_id", None)
                    ),
                    "operation": str(data.get("operation") or "unknown"),
                    "summary": dict_value(data.get("summary")),
                    "committed_at": ms_to_datetime(timestamp_ms) or datetime.now(UTC),
                    "manifest_list": self._optional_str(
                        data.get("manifest-list")
                        or data.get("manifest_list")
                        or getattr(snapshot, "manifest_list", None)
                    ),
                    "schema_id": self._optional_int(data.get("schema-id") or data.get("schema_id")),
                    "sequence_number": self._optional_int(
                        data.get("sequence-number") or data.get("sequence_number")
                    ),
                }
            )
        return rows

    def _refs(self, table: object) -> list[dict[str, Any]]:
        try:
            refs = table.refs()
        except Exception:
            refs = {}
        rows = []
        for name, ref in refs.items():
            data = dict_value(ref)
            ref_type = str(
                data.get("type") or data.get("ref-type") or data.get("ref_type") or "branch"
            )
            rows.append(
                {
                    "name": str(name),
                    "ref_type": ref_type.lower(),
                    "snapshot_id": str(data.get("snapshot-id") or data.get("snapshot_id") or ""),
                    "retention": {
                        key: value
                        for key, value in data.items()
                        if key not in {"type", "snapshot-id", "snapshot_id"}
                    },
                    "is_protected": bool(
                        data.get("max-ref-age-ms") is None and ref_type.lower() == "branch"
                    ),
                }
            )
        return rows

    def _manifest_files(
        self, table: object, manifest_list_location: str, snapshot_id: str
    ) -> list[dict[str, Any]]:
        from pyiceberg.manifest import read_manifest_list

        input_file = table.io.new_input(normalize_object_location(manifest_list_location))
        rows: list[dict[str, Any]] = []
        for manifest in read_manifest_list(input_file):
            data = dict_value(manifest)
            rows.append(
                {
                    "snapshot_id": snapshot_id,
                    "manifest_path": normalize_object_location(
                        str(
                            data.get("manifest-path")
                            or data.get("manifest_path")
                            or getattr(manifest, "manifest_path", "")
                        )
                    ),
                    "content": enum_name(data.get("content") or getattr(manifest, "content", "")),
                    "partition_spec_id": self._optional_int(
                        data.get("partition-spec-id")
                        or data.get("partition_spec_id")
                        or getattr(manifest, "partition_spec_id", None)
                    ),
                    "sequence_number": self._optional_int(
                        data.get("sequence-number")
                        or data.get("sequence_number")
                        or getattr(manifest, "sequence_number", None)
                    ),
                    "manifest_length": self._optional_int(
                        data.get("manifest-length")
                        or data.get("manifest_length")
                        or getattr(manifest, "manifest_length", None)
                    ),
                    "added_files_count": int_value(
                        data.get("added-files-count") or data.get("added_files_count")
                    ),
                    "existing_files_count": int_value(
                        data.get("existing-files-count") or data.get("existing_files_count")
                    ),
                    "deleted_files_count": int_value(
                        data.get("deleted-files-count") or data.get("deleted_files_count")
                    ),
                    "added_rows_count": int_value(
                        data.get("added-rows-count") or data.get("added_rows_count")
                    ),
                    "existing_rows_count": int_value(
                        data.get("existing-rows-count") or data.get("existing_rows_count")
                    ),
                    "deleted_rows_count": int_value(
                        data.get("deleted-rows-count") or data.get("deleted_rows_count")
                    ),
                    "partitions": list_value(data.get("partitions")),
                    "_manifest": manifest,
                }
            )
        return rows

    def _manifest_entries(
        self,
        table: object,
        manifest_row: dict[str, Any],
    ) -> list[dict[str, Any]]:
        manifest = manifest_row.pop("_manifest")
        entries = manifest.fetch_manifest_entry(table.io, discard_deleted=False)
        rows: list[dict[str, Any]] = []
        for entry in entries:
            data_file = getattr(entry, "data_file", None)
            if data_file is None:
                continue
            file_data = dict_value(data_file)
            content = enum_name(file_data.get("content") or getattr(data_file, "content", "DATA"))
            status_value = enum_name(getattr(entry, "status", "EXISTING"))
            rows.append(
                {
                    "snapshot_id": manifest_row["snapshot_id"],
                    "manifest_path": manifest_row["manifest_path"],
                    "entry_status": status_value,
                    "content": content,
                    "file_path": str(
                        file_data.get("file-path")
                        or file_data.get("file_path")
                        or getattr(data_file, "file_path", "")
                    ),
                    "file_format": self._optional_str(
                        file_data.get("file-format")
                        or file_data.get("file_format")
                        or getattr(data_file, "file_format", None)
                    ),
                    "spec_id": self._optional_int(
                        file_data.get("spec-id")
                        or file_data.get("spec_id")
                        or getattr(data_file, "spec_id", None)
                    ),
                    "partition": dict_value(
                        file_data.get("partition") or getattr(data_file, "partition", {})
                    ),
                    "record_count": int_value(
                        file_data.get("record-count")
                        or file_data.get("record_count")
                        or getattr(data_file, "record_count", 0)
                    ),
                    "file_size_in_bytes": int_value(
                        file_data.get("file-size-in-bytes")
                        or file_data.get("file_size_in_bytes")
                        or getattr(data_file, "file_size_in_bytes", 0)
                    ),
                    "column_sizes": dict_value(
                        file_data.get("column-sizes") or file_data.get("column_sizes")
                    ),
                    "value_counts": dict_value(
                        file_data.get("value-counts") or file_data.get("value_counts")
                    ),
                    "null_value_counts": dict_value(
                        file_data.get("null-value-counts") or file_data.get("null_value_counts")
                    ),
                    "nan_value_counts": dict_value(
                        file_data.get("nan-value-counts") or file_data.get("nan_value_counts")
                    ),
                    "lower_bounds": dict_value(
                        file_data.get("lower-bounds") or file_data.get("lower_bounds")
                    ),
                    "upper_bounds": dict_value(
                        file_data.get("upper-bounds") or file_data.get("upper_bounds")
                    ),
                    "key_metadata_present": bool(
                        file_data.get("key-metadata")
                        or file_data.get("key_metadata")
                        or getattr(data_file, "key_metadata", None)
                    ),
                    "split_offsets": list_value(
                        file_data.get("split-offsets") or file_data.get("split_offsets")
                    ),
                    "equality_ids": list_value(
                        file_data.get("equality-ids") or file_data.get("equality_ids")
                    ),
                    "sort_order_id": self._optional_int(
                        file_data.get("sort-order-id") or file_data.get("sort_order_id")
                    ),
                }
            )
        return rows

    def _metrics(
        self,
        snapshots: list[dict[str, Any]],
        manifests: list[dict[str, Any]],
        current_files: list[dict[str, Any]],
    ) -> dict[str, Any]:
        data_files = [item for item in current_files if item["content"] == "DATA"]
        delete_files = [item for item in current_files if item["content"] != "DATA"]
        target_size = 536_870_912
        if self.object_store and isinstance(self.object_store.settings, dict):
            with suppress(TypeError, ValueError):
                target_size = int(
                    self.object_store.settings.get("write_target_file_size_bytes") or target_size
                )
        small_files = [
            item for item in data_files if int_value(item.get("file_size_in_bytes")) < target_size
        ]
        last_commit_at = max((item["committed_at"] for item in snapshots), default=None)
        last_compaction_at = max(
            (
                item["committed_at"]
                for item in snapshots
                if any(word in item["operation"].lower() for word in ("rewrite", "compact"))
            ),
            default=None,
        )
        return {
            "file_count": len(data_files),
            "data_size_bytes": sum(
                int_value(item.get("file_size_in_bytes")) for item in data_files
            ),
            "delete_file_count": len(delete_files),
            "snapshot_count": len(snapshots),
            "manifest_count": len(manifests),
            "small_file_ratio": len(small_files) / len(data_files) if data_files else 0,
            "last_commit_at": last_commit_at,
            "last_compaction_at": last_compaction_at,
            "record_count": sum(int_value(item.get("record_count")) for item in data_files),
        }

    def _partition_summaries(self, current_files: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[tuple[int, str], dict[str, Any]] = defaultdict(
            lambda: {
                "file_count": 0,
                "record_count": 0,
                "total_size_bytes": 0,
                "delete_file_count": 0,
            }
        )
        for item in current_files:
            spec_id = int_value(item.get("spec_id"), 0)
            partition = dict_value(item.get("partition"))
            key = json.dumps(partition, sort_keys=True, separators=(",", ":"))
            summary = grouped[(spec_id, key)]
            summary["spec_id"] = spec_id
            summary["partition_key"] = key
            summary["partition"] = partition
            if item.get("content") == "DATA":
                summary["file_count"] += 1
                summary["record_count"] += int_value(item.get("record_count"))
                summary["total_size_bytes"] += int_value(item.get("file_size_in_bytes"))
            else:
                summary["delete_file_count"] += 1
        return list(grouped.values())

    def _optional_int(self, value: object) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _optional_str(self, value: object) -> str | None:
        if value is None:
            return None
        text = str(value)
        return text if text else None
