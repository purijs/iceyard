"""increase secret reference length"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_secret_reference_length"
down_revision: str | None = "0003_job_correlation_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("secret_reference") as batch_op:
        batch_op.alter_column(
            "reference",
            existing_type=sa.String(length=500),
            type_=sa.String(length=2000),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("secret_reference") as batch_op:
        batch_op.alter_column(
            "reference",
            existing_type=sa.String(length=2000),
            type_=sa.String(length=500),
            existing_nullable=False,
        )
