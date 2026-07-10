"""Create schedules table for recurring runs — Phase 11.

Tables:
- schedules: stores recurring cron schedules
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "schedules",
        sa.Column("schedule_id", sa.String(36), primary_key=True),
        sa.Column("cron_expression", sa.Text, nullable=False),
        sa.Column("goal", sa.Text, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("TRUE")),
        sa.Column("next_run_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True),
                  nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_schedules_active_next_run", "schedules", ["active", "next_run_at"])

def downgrade() -> None:
    op.drop_index("ix_schedules_active_next_run", table_name="schedules")
    op.drop_table("schedules")
