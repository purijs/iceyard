"""job correlation id"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_job_correlation_id"
down_revision: str | None = "0002_automation_policy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("job", sa.Column("correlation_id", sa.String(length=64), nullable=True))
    op.create_index("ix_job_correlation_id", "job", ["correlation_id"])


def downgrade() -> None:
    op.drop_index("ix_job_correlation_id", table_name="job")
    op.drop_column("job", "correlation_id")
