"""Additive schema reconciliation for dev/embedded deployments.

``Base.metadata.create_all`` creates missing tables but never alters existing ones, so a
DB created by an older build is missing columns added since (e.g. ``job.correlation_id``),
which makes queries fail at runtime. This reconciler adds any missing **nullable** columns
to existing tables on startup. It is intentionally conservative: it never drops or alters
columns and never adds NOT NULL columns to a populated table. Destructive or data-shaping
migrations still belong in Alembic.
"""

import structlog
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from iceyard_api.db.base import Base

logger = structlog.get_logger(__name__)


def reconcile_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        existing_columns = {column["name"] for column in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing_columns:
                continue
            can_add_nullable = column.nullable
            has_default = column.default is not None or column.server_default is not None
            if not can_add_nullable and not has_default:
                logger.warning(
                    "schema_sync.skip_non_nullable_column",
                    table=table.name,
                    column=column.name,
                )
                continue
            column_type = column.type.compile(dialect=engine.dialect)
            statement = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column_type}'
            try:
                with engine.begin() as connection:
                    connection.execute(text(statement))
                logger.info("schema_sync.column_added", table=table.name, column=column.name)
            except Exception as exc:  # pragma: no cover - defensive, logged not raised
                logger.warning(
                    "schema_sync.add_column_failed",
                    table=table.name,
                    column=column.name,
                    error=str(exc),
                )
