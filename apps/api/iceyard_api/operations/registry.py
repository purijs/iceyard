from iceyard_api.operations.schemas import OperationDescriptor

RAW_OPERATIONS: list[dict[str, object]] = [
    {
        "id": "show_namespaces",
        "name": "Show namespaces",
        "description": "List namespaces in a catalog.",
        "category": "Catalog and namespace",
        "safety_class": "READ",
        "supported_engines": ["spark", "trino", "flink", "embedded"],
        "required_permissions": ["tables.read"],
        "params": [{"name": "catalog", "type": "string", "required": True}],
        "sql_template": "SHOW NAMESPACES IN {catalog}",
        "dry_run_supported": False,
        "approval_required": False,
        "restore_point_required": False,
        "gates": [],
    },
    {
        "id": "add_column",
        "name": "Add column",
        "description": "Add a nullable or defaulted column.",
        "category": "Schema evolution",
        "safety_class": "METADATA",
        "supported_engines": ["spark", "trino", "flink", "embedded"],
        "required_permissions": ["operations.execute"],
        "params": [
            {"name": "column", "type": "string", "required": True, "placeholder": "device_type"},
            {"name": "type", "type": "string", "required": True, "placeholder": "string"},
        ],
        "sql_template": "ALTER TABLE {table} ADD COLUMN {column} {type}",
        "dry_run_supported": True,
        "approval_required": False,
        "restore_point_required": False,
        "gates": ["schema_compatibility"],
    },
    {
        "id": "drop_column",
        "name": "Drop column",
        "description": "Drop a column after downstream impact review.",
        "category": "Schema evolution",
        "safety_class": "DESTRUCTIVE",
        "supported_engines": ["spark", "trino", "flink", "embedded"],
        "required_permissions": ["operations.execute"],
        "params": [{"name": "column", "type": "column", "required": True}],
        "sql_template": "ALTER TABLE {table} DROP COLUMN {column}",
        "dry_run_supported": True,
        "approval_required": True,
        "restore_point_required": True,
        "gates": ["consumer_impact_check", "approval_required", "restore_point_required"],
    },
    {
        "id": "rewrite_data_files",
        "name": "Compact data files",
        "description": "Rewrite small files into target-sized data files.",
        "category": "Maintenance",
        "safety_class": "REWRITE",
        "supported_engines": ["spark", "trino", "embedded"],
        "required_permissions": ["operations.execute"],
        "params": [
            {
                "name": "strategy",
                "type": "enum",
                "default": "binpack",
                "options": ["binpack", "sort"],
            },
            {
                "name": "where",
                "type": "predicate",
                "required": False,
                "placeholder": "occurred_at >= DATE '2026-06-01'",
            },
            {
                "name": "target_file_size_bytes",
                "type": "bytes",
                "default": 536870912,
                "advanced": True,
            },
        ],
        "sql_template": (
            "CALL system.rewrite_data_files("
            "table => '{table}', "
            "strategy => '{strategy}', "
            "where => '{where}', "
            "options => map('target-file-size-bytes','{target_file_size_bytes}'))"
        ),
        "dry_run_supported": True,
        "approval_required": False,
        "restore_point_required": True,
        "gates": ["dry_run_required", "restore_point_required", "idempotent_retry"],
    },
    {
        "id": "rewrite_manifests",
        "name": "Rewrite manifests",
        "description": "Consolidate manifest files.",
        "category": "Maintenance",
        "safety_class": "REWRITE",
        "supported_engines": ["spark", "trino", "embedded"],
        "required_permissions": ["operations.execute"],
        "params": [],
        "sql_template": "CALL system.rewrite_manifests('{table}')",
        "dry_run_supported": True,
        "approval_required": False,
        "restore_point_required": True,
        "gates": ["dry_run_required", "restore_point_required", "idempotent_retry"],
    },
    {
        "id": "rewrite_position_deletes",
        "name": "Compact delete files",
        "description": "Rewrite position and equality delete files.",
        "category": "Maintenance",
        "safety_class": "REWRITE",
        "supported_engines": ["spark", "trino", "embedded"],
        "required_permissions": ["operations.execute"],
        "params": [{"name": "min_input_files", "type": "integer", "default": 2}],
        "sql_template": (
            "CALL system.rewrite_position_delete_files("
            "table => '{table}', "
            "options => map('min-input-files','{min_input_files}'))"
        ),
        "dry_run_supported": True,
        "approval_required": False,
        "restore_point_required": True,
        "gates": ["dry_run_required", "restore_point_required", "idempotent_retry"],
    },
    {
        "id": "expire_snapshots",
        "name": "Expire snapshots",
        "description": "Remove old snapshot metadata while honoring retention gates.",
        "category": "Maintenance",
        "safety_class": "DESTRUCTIVE",
        "supported_engines": ["spark", "trino", "embedded"],
        "required_permissions": ["operations.execute"],
        "params": [
            {"name": "older_than", "type": "timestamp", "required": True},
            {"name": "retain_last", "type": "integer", "default": 5},
        ],
        "sql_template": (
            "CALL system.expire_snapshots("
            "table => '{table}', "
            "older_than => TIMESTAMP '{older_than}', "
            "retain_last => {retain_last})"
        ),
        "dry_run_supported": True,
        "approval_required": True,
        "restore_point_required": True,
        "gates": [
            "dry_run_required",
            "query_window_check",
            "protected_ref_check",
            "approval_required",
        ],
    },
    {
        "id": "remove_orphan_files",
        "name": "Remove orphan files",
        "description": "Delete unreferenced files after retention and path checks.",
        "category": "Maintenance",
        "safety_class": "DESTRUCTIVE",
        "supported_engines": ["spark", "trino", "embedded"],
        "required_permissions": ["operations.execute"],
        "params": [
            {"name": "older_than", "type": "timestamp", "required": True},
            {"name": "location", "type": "string", "advanced": True},
            {"name": "equal_authorities", "type": "string", "advanced": True},
        ],
        "sql_template": (
            "CALL system.remove_orphan_files("
            "table => '{table}', "
            "older_than => TIMESTAMP '{older_than}', "
            "dry_run => true)"
        ),
        "dry_run_supported": True,
        "approval_required": True,
        "restore_point_required": True,
        "gates": [
            "dry_run_required",
            "retention_window_min_3_days",
            "path_authority_check",
            "approval_required",
        ],
    },
    {
        "id": "rollback_to_snapshot",
        "name": "Roll back to snapshot",
        "description": "Move the current table pointer to a previous snapshot.",
        "category": "Snapshot lifecycle",
        "safety_class": "METADATA",
        "supported_engines": ["spark", "embedded"],
        "required_permissions": ["operations.execute"],
        "params": [{"name": "snapshot_id", "type": "string", "required": True}],
        "sql_template": "CALL system.rollback_to_snapshot('{table}', {snapshot_id})",
        "dry_run_supported": True,
        "approval_required": True,
        "restore_point_required": True,
        "gates": ["snapshot_exists", "restore_point_required", "approval_required_in_prod"],
    },
    {
        "id": "upgrade_format",
        "name": "Upgrade table format",
        "description": "Upgrade an Iceberg table format version after reader checks.",
        "category": "Table lifecycle",
        "safety_class": "DESTRUCTIVE",
        "supported_engines": ["spark", "embedded"],
        "required_permissions": ["operations.execute"],
        "params": [{"name": "target_version", "type": "integer", "default": 3}],
        "sql_template": (
            "ALTER TABLE {table} "
            "SET TBLPROPERTIES ('format-version'='{target_version}')"
        ),
        "dry_run_supported": True,
        "approval_required": True,
        "restore_point_required": True,
        "gates": ["reader_compatibility_check", "irreversible_change_check", "approval_required"],
    },
]

OPERATIONS = [OperationDescriptor.model_validate(item) for item in RAW_OPERATIONS]
OPERATION_BY_ID = {operation.id: operation for operation in OPERATIONS}
