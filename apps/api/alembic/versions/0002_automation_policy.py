"""automation policy table"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_automation_policy"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "automation_policy",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "workspace_id", sa.String(length=36), sa.ForeignKey("workspace.id"), nullable=False
        ),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("selector", sa.JSON(), nullable=False),
        sa.Column("trigger", sa.JSON(), nullable=False),
        sa.Column("action", sa.JSON(), nullable=False),
        sa.Column("guardrails", sa.JSON(), nullable=False),
        sa.Column("alerting", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=36), sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "name", name="uq_automation_policy_workspace_name"),
    )


def downgrade() -> None:
    op.drop_table("automation_policy")
