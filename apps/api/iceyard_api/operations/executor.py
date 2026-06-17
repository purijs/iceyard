from iceyard_api.operations.schemas import OperationDescriptor


class OperationExecutor:
    def dry_run(
        self,
        *,
        descriptor: OperationDescriptor,
        compiled_command: str,
        table_name: str | None,
        params: dict[str, object],
    ) -> dict[str, object]:
        if descriptor.id == "rewrite_data_files":
            return {
                "candidate_files": 612,
                "output_files": 9,
                "estimated_reclaimed_bytes": 300_000_000,
            }
        if descriptor.id == "expire_snapshots":
            return {
                "candidate_snapshots": 42,
                "protected_snapshots": 2,
                "estimated_reclaimed_bytes": 800_000_000,
            }
        if descriptor.id == "remove_orphan_files":
            return {
                "candidate_files": 0,
                "path_authority_changed": False,
                "estimated_reclaimed_bytes": 0,
            }
        return {"preview": True, "table": table_name, "params": params}

    def execute(self, *, compiled_command: str) -> dict[str, object]:
        return {"submitted": True, "compiled_command": compiled_command}
