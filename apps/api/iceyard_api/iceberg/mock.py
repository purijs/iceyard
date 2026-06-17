from iceyard_api.iceberg.connectors import IcebergCatalogConnector


class MockIcebergCatalogConnector(IcebergCatalogConnector):
    def list_namespaces(self) -> list[str]:
        return ["analytics", "sales", "marketing", "staging", "finance"]

    def list_tables(self, namespace: str) -> list[str]:
        tables = {
            "analytics": ["events", "sessions"],
            "sales": ["orders", "order_items"],
            "marketing": ["campaigns"],
            "staging": ["raw_clickstream"],
            "finance": ["ledger"],
        }
        return tables.get(namespace, [])

    def load_table_metadata(self, table_name: str) -> dict[str, object]:
        return {
            "table": table_name,
            "format_version": 2,
            "properties": {"write.format.default": "parquet"},
        }

    def list_snapshots(self, table_name: str) -> list[dict[str, object]]:
        return [
            {"snapshot_id": "8364920157712043", "operation": "append"},
            {"snapshot_id": "7588120049923847", "operation": "rewrite"},
        ]

    def list_refs(self, table_name: str) -> list[dict[str, object]]:
        return [
            {"name": "main", "type": "branch", "snapshot_id": "8364920157712043"},
            {"name": "pre-compaction-restore", "type": "tag", "snapshot_id": "7588120049923847"},
        ]

    def get_table_schema(self, table_name: str) -> dict[str, object]:
        return {
            "fields": [
                {"id": 1, "name": "event_id", "type": "long", "required": True},
                {"id": 2, "name": "user_id", "type": "long", "required": True},
                {"id": 3, "name": "event_type", "type": "string", "required": True},
                {"id": 4, "name": "payload", "type": "variant", "required": False},
                {"id": 5, "name": "occurred_at", "type": "timestamptz", "required": True},
            ]
        }

    def get_table_properties(self, table_name: str) -> dict[str, object]:
        return {
            "write.target-file-size-bytes": "536870912",
            "write.format.default": "parquet",
            "owner": "data-platform",
        }
