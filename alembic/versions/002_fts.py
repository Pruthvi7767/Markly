"""Full text search for episodic memory.

Revision ID: 002
Revises: 001
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Add a generated TSVECTOR column to the turns table
    op.execute(
        """
        ALTER TABLE turns 
        ADD COLUMN search_vector tsvector GENERATED ALWAYS AS (
            to_tsvector('english', 
                coalesce(subgoal, '') || ' ' || 
                coalesce(observation, '') || ' ' || 
                coalesce(tool_name, '') || ' ' ||
                coalesce(tool_args::text, '')
            )
        ) STORED;
        """
    )
    # Create GIN index for fast search
    op.execute("CREATE INDEX ix_turns_search_vector ON turns USING GIN (search_vector);")

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_turns_search_vector;")
    op.execute("ALTER TABLE turns DROP COLUMN IF EXISTS search_vector;")
