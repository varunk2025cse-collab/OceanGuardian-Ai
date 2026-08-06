"""add retry fields to family_notifications

Revision ID: 024_notification_retry
Revises: 023_performance_indexes
Create Date: 2026-08-06 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '024_notification_retry'
down_revision = '023_performance_indexes'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'family_notifications',
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'family_notifications',
        sa.Column('last_retry_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column('family_notifications', 'last_retry_at')
    op.drop_column('family_notifications', 'retry_count')
