from types import SimpleNamespace

from iceyard_api.iceberg.live_metadata import LiveIcebergReader
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
