"""add password_changed_at and password_reset_tokens

Revision ID: 022_auth_password_reset
Revises: 021_notification_engine
Create Date: 2026-08-05 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '022_auth_password_reset'
down_revision = '021_notification_engine'
branch_labels = None
depends_on = None


def upgrade():
    # Add password_changed_at to users
    op.add_column('users', sa.Column('password_changed_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False))

    # Create password_reset_tokens table
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('token_hash', sa.String(length=128), nullable=False, unique=True, index=True),
        sa.Column('used', sa.Boolean, nullable=False, server_default=sa.text('false')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
    )


def downgrade():
    op.drop_table('password_reset_tokens')
    op.drop_column('users', 'password_changed_at')
