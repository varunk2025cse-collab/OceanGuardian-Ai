"""create notification engine tables

Revision ID: 021_notification_engine
Revises: 
Create Date: 2026-08-02 11:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '021_notification_engine'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'notification_event_stream',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('event_type', sa.String(length=200), nullable=False),
        sa.Column('payload_json', sa.JSON(), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('correlation_id', sa.String(length=64), nullable=False),
        sa.Column('priority', sa.String(length=50), nullable=False, server_default='NORMAL'),
        sa.Column('source_module', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='CREATED'),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index(op.f('ix_notification_event_stream_correlation_id'), 'notification_event_stream', ['correlation_id'], unique=False)

    op.create_table(
        'notification_queue_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('event_id', sa.Integer(), sa.ForeignKey('notification_event_stream.id', ondelete='CASCADE')),
        sa.Column('recipient_user_id', sa.Integer(), nullable=True),
        sa.Column('recipient_group_json', sa.JSON(), nullable=True),
        sa.Column('channel', sa.String(length=50), nullable=False),
        sa.Column('provider_name', sa.String(length=100), nullable=True),
        sa.Column('payload_json', sa.JSON(), nullable=False),
        sa.Column('priority', sa.String(length=50), nullable=False, server_default='NORMAL'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='QUEUED'),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('next_retry_at', sa.DateTime(), nullable=True),
        sa.Column('timeout_at', sa.DateTime(), nullable=True),
        sa.Column('retry_deadline', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('correlation_id', sa.String(length=64), nullable=False),
        sa.Column('locked_by', sa.String(length=200), nullable=True),
        sa.Column('locked_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index(op.f('ix_notification_queue_items_correlation_id'), 'notification_queue_items', ['correlation_id'], unique=False)
    op.create_index(op.f('ix_notification_queue_items_status_priority_next_retry'), 'notification_queue_items', ['status', 'priority', 'next_retry_at'], unique=False)

    op.create_table(
        'notification_lifecycle_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('notification_item_id', sa.Integer(), sa.ForeignKey('notification_queue_items.id', ondelete='CASCADE')),
        sa.Column('state', sa.String(length=50), nullable=False),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('actor', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('correlation_id', sa.String(length=64), nullable=False),
    )

    op.create_table(
        'notification_templates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('language', sa.String(length=10), nullable=False, server_default='en'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('channel', sa.String(length=50), nullable=False),
        sa.Column('subject', sa.String(length=400), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('placeholders_json', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'notification_preferences',
        sa.Column('user_id', sa.Integer(), primary_key=True),
        sa.Column('preferred_language', sa.String(length=10), nullable=True),
        sa.Column('preferred_channels', sa.JSON(), nullable=True),
        sa.Column('quiet_hours', sa.JSON(), nullable=True),
        sa.Column('emergency_override', sa.Boolean(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'notification_provider_health',
        sa.Column('provider_name', sa.String(length=200), primary_key=True),
        sa.Column('channel_type', sa.String(length=50), nullable=True),
        sa.Column('success_count', sa.BigInteger(), nullable=True),
        sa.Column('failure_count', sa.BigInteger(), nullable=True),
        sa.Column('avg_latency_ms', sa.Float(), nullable=True),
        sa.Column('avg_retry_count', sa.Float(), nullable=True),
        sa.Column('last_failure_at', sa.DateTime(), nullable=True),
        sa.Column('last_success_at', sa.DateTime(), nullable=True),
        sa.Column('availability_score', sa.Float(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table('notification_provider_health')
    op.drop_table('notification_preferences')
    op.drop_table('notification_templates')
    op.drop_table('notification_lifecycle_events')
    op.drop_index(op.f('ix_notification_queue_items_status_priority_next_retry'), table_name='notification_queue_items')
    op.drop_index(op.f('ix_notification_queue_items_correlation_id'), table_name='notification_queue_items')
    op.drop_table('notification_queue_items')
    op.drop_index(op.f('ix_notification_event_stream_correlation_id'), table_name='notification_event_stream')
    op.drop_table('notification_event_stream')
