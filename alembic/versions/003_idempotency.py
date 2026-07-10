"""003_idempotency — add idempotency_keys table.

Per AGENTS.md Section 6:
- Every side-effecting action (file writes, shell commands) carries an
  idempotency key so a crash-retry can never duplicate the effect.
"""
from alembic import op
import sqlalchemy as sa


revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.Text, primary_key=True),
        sa.Column("run_id", sa.Text, nullable=False),
        sa.Column("tool_name", sa.Text, nullable=False),
        sa.Column("tool_args", sa.dialects.postgresql.JSONB, nullable=False),
        sa.Column("result", sa.Text, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_idempotency_keys_run_id", "idempotency_keys", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_idempotency_keys_run_id", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
