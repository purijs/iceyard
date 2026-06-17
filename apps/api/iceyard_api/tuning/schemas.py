from pydantic import BaseModel


class ParquetAdvice(BaseModel):
    table_id: str
    table_name: str
    current_codec: str
    recommended_codec: str
    recommended_level: int
    dictionary_enabled: bool
    row_group_size_bytes: int
    apply_operation_id: str = "set_parquet_settings"
    reencode_operation_id: str = "rewrite_parquet_encoding"
    rationale: str
    note: str = (
        "Codec choice is a read/write/storage tradeoff; without a workload profile this "
        "assumes a read-heavy table. Setting properties affects future writes only."
    )


class DistributionAdvice(BaseModel):
    table_id: str
    table_name: str
    current_mode: str
    recommended_mode: str
    apply_operation_id: str = "set_write_distribution"
    projected_small_file_reduction_pct: float
    ingestion_hint: str
    rationale: str
    note: str = (
        "Distribution mode is honored by the writing engine, not the control plane. "
        "Set the table preference and the matching ingestion-job config."
    )
