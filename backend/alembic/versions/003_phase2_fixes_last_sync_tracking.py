"""003_phase2_fixes_last_sync_tracking

Revision ID: 003
Revises: 002
Create Date: 2024

Adds last_sync_at column to users table for tracking offline status.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    # Add last_sync_at to users table
    op.add_column('users', sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column('users', 'last_sync_at')
