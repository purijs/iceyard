from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from iceyard_api.db.base import Base
from iceyard_api.db.schema_sync import reconcile_schema


def test_reconcile_adds_missing_nullable_column(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'sync.db'}")
    Base.metadata.create_all(engine)

    # Simulate an older DB that predates the job.correlation_id column.
    with engine.begin() as connection:
        connection.execute(text("DROP INDEX IF EXISTS ix_job_correlation_id"))
        connection.execute(text('ALTER TABLE "job" DROP COLUMN "correlation_id"'))
    assert "correlation_id" not in {c["name"] for c in inspect(engine).get_columns("job")}

    reconcile_schema(engine)

    assert "correlation_id" in {c["name"] for c in inspect(engine).get_columns("job")}
    engine.dispose()
