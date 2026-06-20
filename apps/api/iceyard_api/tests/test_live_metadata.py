import json
from datetime import UTC, date, datetime, time
from decimal import Decimal
from types import SimpleNamespace

import pytest

from iceyard_api.iceberg.live_metadata import (
    LiveIcebergReader,
    arrow_table_preview_rows,
    ensure_pyarrow_type_compatibility,
)
from iceyard_api.iceberg.schemas import TablePreviewRead
from iceyard_api.iceberg.service import IcebergIndexService


class EmptySchemaTable:
    def schemas(self) -> list[object]:
        return [object()]


def test_live_metadata_schema_prefers_raw_metadata_fields() -> None:
    reader = LiveIcebergReader.__new__(LiveIcebergReader)
    metadata = {
        "schemas": [
            {
                "schema-id": 2,
                "fields": [
                    {"id": 1, "name": "campaign_id", "type": "long", "required": True}
                ],
            }
        ]
    }

    schemas = reader._schemas(EmptySchemaTable(), metadata)

    assert schemas == [
        {
            "schema_id": 2,
            "schema": metadata["schemas"][0],
        }
    ]


def test_live_metadata_schema_preserves_iceberg_type_surface() -> None:
    reader = LiveIcebergReader.__new__(LiveIcebergReader)
    fields = [
        {"id": 1, "name": "bool_col", "type": "boolean", "required": False},
        {"id": 2, "name": "int_col", "type": "int", "required": False},
        {"id": 3, "name": "long_col", "type": "long", "required": False},
        {"id": 4, "name": "float_col", "type": "float", "required": False},
        {"id": 5, "name": "double_col", "type": "double", "required": False},
        {"id": 6, "name": "decimal_col", "type": "decimal(38, 10)", "required": False},
        {"id": 7, "name": "date_col", "type": "date", "required": False},
        {"id": 8, "name": "time_col", "type": "time", "required": False},
        {"id": 9, "name": "timestamp_col", "type": "timestamp", "required": False},
        {"id": 10, "name": "timestamptz_col", "type": "timestamptz", "required": False},
        {"id": 11, "name": "string_col", "type": "string", "required": False},
        {"id": 12, "name": "uuid_col", "type": "uuid", "required": False},
        {"id": 13, "name": "fixed_col", "type": "fixed[16]", "required": False},
        {"id": 14, "name": "binary_col", "type": "binary", "required": False},
        {"id": 15, "name": "variant_col", "type": "variant", "required": False},
        {"id": 16, "name": "unknown_col", "type": "unknown", "required": False},
        {
            "id": 17,
            "name": "struct_col",
            "type": {
                "type": "struct",
                "fields": [
                    {"id": 18, "name": "nested_string", "type": "string", "required": False}
                ],
            },
            "required": False,
        },
        {
            "id": 19,
            "name": "list_col",
            "type": {
                "type": "list",
                "element-id": 20,
                "element": "long",
                "element-required": False,
            },
            "required": False,
        },
        {
            "id": 21,
            "name": "map_col",
            "type": {
                "type": "map",
                "key-id": 22,
                "key": "string",
                "value-id": 23,
                "value": "double",
                "value-required": False,
            },
            "required": False,
        },
    ]
    metadata = {"schemas": [{"schema-id": 7, "fields": fields}]}

    schemas = reader._schemas(EmptySchemaTable(), metadata)

    assert schemas[0]["schema"]["fields"] == fields


def test_row_preview_uses_live_columns_when_synced_schema_is_empty() -> None:
    service = IcebergIndexService.__new__(IcebergIndexService)
    service.list_schema_versions = lambda _table_id: []  # type: ignore[method-assign]
    service.preview_rows = lambda _table, limit: {  # type: ignore[method-assign]
        "columns": ["campaign_id", "name"],
        "rows": [{"campaign_id": 1001, "name": "launch"}],
        "query": "SELECT * FROM tst.demand LIMIT 5",
    }
    table = SimpleNamespace(id="table-1", name="tst.demand")

    preview = service.preview_table_resource(table, "rows")

    assert preview["columns"] == ["campaign_id", "name"]
    assert preview["rows"] == [{"campaign_id": 1001, "name": "launch"}]


def test_pyarrow_type_view_compatibility_helpers_are_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pa = pytest.importorskip("pyarrow")
    pa_types = pytest.importorskip("pyarrow.types")
    for helper in (
        "is_string_view",
        "is_binary_view",
        "is_list_view",
        "is_large_list_view",
    ):
        monkeypatch.delattr(pa_types, helper, raising=False)

    ensure_pyarrow_type_compatibility()

    assert pa_types.is_string_view(pa.string()) is False
    assert pa_types.is_binary_view(pa.binary()) is False
    assert pa_types.is_list_view(pa.list_(pa.int32())) is False
    assert pa_types.is_large_list_view(pa.large_list(pa.string())) is False


def test_arrow_preview_rows_cover_iceberg_and_parquet_value_shapes() -> None:
    pa = pytest.importorskip("pyarrow")
    arrow_table = pa.table(
        {
            "bool_col": pa.array([True], type=pa.bool_()),
            "int32_col": pa.array([123], type=pa.int32()),
            "int64_col": pa.array([1234567890123], type=pa.int64()),
            "float_col": pa.array([1.25], type=pa.float32()),
            "double_col": pa.array([2.5], type=pa.float64()),
            "nan_col": pa.array([float("nan")], type=pa.float64()),
            "decimal128_col": pa.array([Decimal("12345.67")], type=pa.decimal128(12, 2)),
            "decimal256_col": pa.array(
                [Decimal("12345678901234567890.1234")],
                type=pa.decimal256(38, 4),
            ),
            "string_col": pa.array(["hello"], type=pa.string()),
            "large_string_col": pa.array(["large"], type=pa.large_string()),
            "binary_col": pa.array([b"\x00\x01"], type=pa.binary()),
            "large_binary_col": pa.array([b"\x02\x03"], type=pa.large_binary()),
            "fixed_binary_col": pa.array([b"abcd"], type=pa.binary(4)),
            "date32_col": pa.array([date(2026, 6, 20)], type=pa.date32()),
            "date64_col": pa.array([date(2026, 6, 20)], type=pa.date64()),
            "time32_col": pa.array([time(12, 30, 15)], type=pa.time32("s")),
            "time64_col": pa.array([time(12, 30, 15, 123456)], type=pa.time64("us")),
            "timestamp_col": pa.array(
                [datetime(2026, 6, 20, 10, 30, 15, 123456)],
                type=pa.timestamp("us"),
            ),
            "timestamptz_col": pa.array(
                [datetime(2026, 6, 20, 10, 30, 15, 123456, tzinfo=UTC)],
                type=pa.timestamp("us", tz="UTC"),
            ),
            "list_col": pa.array([[1, 2, 3]], type=pa.list_(pa.int32())),
            "large_list_col": pa.array([["a", "b"]], type=pa.large_list(pa.string())),
            "fixed_size_list_col": pa.array([[1, 2]], type=pa.list_(pa.int32(), 2)),
            "struct_col": pa.array(
                [{"name": "x", "score": 9}],
                type=pa.struct([("name", pa.string()), ("score", pa.int32())]),
            ),
            "map_col": pa.array(
                [[("a", 1), ("b", 2)]],
                type=pa.map_(pa.string(), pa.int32()),
            ),
            "dictionary_col": pa.array(
                ["blue"],
                type=pa.dictionary(pa.int8(), pa.string()),
            ),
            "null_col": pa.array([None], type=pa.null()),
        }
    )

    rows = arrow_table_preview_rows(arrow_table, limit=5)
    payload = TablePreviewRead(
        resource="rows",
        query="SELECT * FROM fixture LIMIT 5",
        columns=list(arrow_table.column_names),
        rows=rows,
    )

    encoded = json.loads(payload.model_dump_json())
    row = encoded["rows"][0]
    assert row["decimal128_col"] == "12345.67"
    assert row["decimal256_col"] == "12345678901234567890.1234"
    assert row["binary_col"] == "0001"
    assert row["large_binary_col"] == "0203"
    assert row["fixed_binary_col"] == "61626364"
    assert row["date32_col"] == "2026-06-20"
    assert row["time64_col"] == "12:30:15.123456"
    assert row["timestamp_col"] == "2026-06-20T10:30:15.123456"
    assert row["timestamptz_col"] == "2026-06-20T10:30:15.123456+00:00"
    assert row["map_col"] == [["a", 1], ["b", 2]]
    assert row["struct_col"] == {"name": "x", "score": 9}
    assert row["dictionary_col"] == "blue"
    assert row["nan_col"] == "nan"
    assert row["null_col"] is None
