"""Initial schema — Phase 1.

Tables:
- runs:  full RunState as JSONB + status + heartbeat for crash recovery
- turns: per-turn audit log (tool called, observation, verify score)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "runs",
        sa.Column("run_id",     sa.String(36),  primary_key=True),
        sa.Column("goal",       sa.Text,         nullable=False),
        sa.Column("status",     sa.String(50),   nullable=False, server_default="running"),
        sa.Column("state_json", JSONB,           nullable=False),
        sa.Column("heartbeat",  sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True),
                  nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_runs_status_heartbeat", "runs", ["status", "heartbeat"])

    op.create_table(
        "turns",
        sa.Column("turn_id",       sa.String(36),  primary_key=True,
                  server_default=sa.text("gen_random_uuid()::text")),
        sa.Column("run_id",        sa.String(36),
                  sa.ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("turn_number",   sa.Integer,     nullable=False),
        sa.Column("subgoal_index", sa.Integer,     nullable=False),
        sa.Column("subgoal",       sa.Text,        nullable=False),
        sa.Column("tool_name",     sa.String(100), nullable=True),
        sa.Column("tool_args",     JSONB,          nullable=True),
        sa.Column("observation",   sa.Text,        nullable=True),
        sa.Column("verify_score",  sa.Integer,     nullable=True),
        sa.Column("created_at",    sa.TIMESTAMP(timezone=True),
                  nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_turns_run_id", "turns", ["run_id"])


def downgrade() -> None:
    op.drop_table("turns")
    op.drop_table("runs")
