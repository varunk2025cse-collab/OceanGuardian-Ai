"""003_phase2_fixes_last_sync_tracking

Revision ID: 003
Revises: 002
Create Date: 2024

Adds last_sync_at column to users table for tracking offline status.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def _table_exists(name):
    return sa_inspect(op.get_bind()).has_table(name)


def _column_exists(table, column):
    bind = op.get_bind()
    if not bind.dialect.name == "sqlite" and not sa_inspect(bind).has_table(table):
        return False
    if not sa_inspect(bind).has_table(table):
        return False
    return column in {c["name"] for c in sa_inspect(bind).get_columns(table)}


def upgrade():
    # Add last_sync_at to users table
    if _table_exists("users") and not _column_exists("users", "last_sync_at"):
        op.add_column('users', sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column('users', 'last_sync_at')
