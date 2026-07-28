"""Phase 5 Week 3: Smart Check-In, Risk Prediction Enhancements, Emergency Escalation Engine

Revision ID: 006_week3_services
Revises: 005_week2_services
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006_week3_services'
down_revision = '005_week2_services'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create Week 3 service tables."""

    # Check-in Schedule tables
    op.create_table(
        'check_in_schedules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('trip_id', sa.Integer(), nullable=False),
        sa.Column('fisherman_id', sa.Integer(), nullable=False),
        sa.Column('interval_minutes', sa.Integer(), nullable=True),
        sa.Column('next_checkin_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['trip_id'], ['trips.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['fisherman_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_check_in_schedules_trip_id', 'check_in_schedules', ['trip_id'])
    op.create_index('ix_check_in_schedules_fisherman_id', 'check_in_schedules', ['fisherman_id'])

    op.create_table(
        'check_in_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('schedule_id', sa.Integer(), nullable=False),
        sa.Column('trip_id', sa.Integer(), nullable=False),
        sa.Column('fisherman_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=True),
        sa.Column('requested_at', sa.DateTime(), nullable=True),
        sa.Column('responded_at', sa.DateTime(), nullable=True),
        sa.Column('response_status', sa.String(50), nullable=True),
        sa.Column('response_lat', sa.Float(), nullable=True),
        sa.Column('response_lng', sa.Float(), nullable=True),
        sa.Column('response_notes', sa.Text(), nullable=True),
        sa.Column('synced', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['schedule_id'], ['check_in_schedules.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['trip_id'], ['trips.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['fisherman_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_check_in_requests_schedule_id', 'check_in_requests', ['schedule_id'])
    op.create_index('ix_check_in_requests_trip_id', 'check_in_requests', ['trip_id'])
    op.create_index('ix_check_in_requests_fisherman_id', 'check_in_requests', ['fisherman_id'])
    op.create_index('ix_check_in_requests_status', 'check_in_requests', ['status'])

    # Safety Escalation tables
    op.create_table(
        'safety_escalations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('escalation_type', sa.String(50), nullable=True),
        sa.Column('level', sa.Integer(), nullable=True),
        sa.Column('fisherman_id', sa.Integer(), nullable=False),
        sa.Column('trip_id', sa.Integer(), nullable=True),
        sa.Column('sos_alert_id', sa.Integer(), nullable=True),
        sa.Column('missed_checkin_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('priority', sa.String(20), nullable=True),
        sa.Column('status', sa.String(20), nullable=True),
        sa.Column('acknowledged_by_id', sa.Integer(), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by_id', sa.Integer(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolution', sa.Text(), nullable=True),
        sa.Column('outcome', sa.String(50), nullable=True),
        sa.Column('family_notified', sa.Boolean(), nullable=True),
        sa.Column('operator_notified', sa.Boolean(), nullable=True),
        sa.Column('timeline_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['fisherman_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['trip_id'], ['trips.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sos_alert_id'], ['sos_alerts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['acknowledged_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resolved_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_safety_escalations_status', 'safety_escalations', ['status'])
    op.create_index('ix_safety_escalations_fisherman_id', 'safety_escalations', ['fisherman_id'])
    op.create_index('ix_safety_escalations_priority', 'safety_escalations', ['priority'])
    op.create_index('ix_safety_escalations_type', 'safety_escalations', ['escalation_type'])

    # Missed Check-Ins table
    op.create_table(
        'missed_check_ins',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('schedule_id', sa.Integer(), nullable=True),
        sa.Column('request_id', sa.Integer(), nullable=True),
        sa.Column('trip_id', sa.Integer(), nullable=False),
        sa.Column('fisherman_id', sa.Integer(), nullable=False),
        sa.Column('consecutive_missed', sa.Integer(), nullable=True),
        sa.Column('family_notified', sa.Boolean(), nullable=True),
        sa.Column('operator_notified', sa.Boolean(), nullable=True),
        sa.Column('risk_level_increased', sa.Boolean(), nullable=True),
        sa.Column('escalated', sa.Boolean(), nullable=True),
        sa.Column('escalation_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['schedule_id'], ['check_in_schedules.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['request_id'], ['check_in_requests.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['trip_id'], ['trips.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['fisherman_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['escalation_id'], ['safety_escalations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_missed_check_ins_trip_id', 'missed_check_ins', ['trip_id'])
    op.create_index('ix_missed_check_ins_fisherman_id', 'missed_check_ins', ['fisherman_id'])
    op.create_index('ix_missed_check_ins_escalated', 'missed_check_ins', ['escalated'])

    # Operator Action Log table
    op.create_table(
        'operator_action_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('operator_id', sa.Integer(), nullable=False),
        sa.Column('action_type', sa.String(50), nullable=True),
        sa.Column('escalation_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('details_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['operator_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['escalation_id'], ['safety_escalations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_operator_action_logs_operator_id', 'operator_action_logs', ['operator_id'])
    op.create_index('ix_operator_action_logs_escalation_id', 'operator_action_logs', ['escalation_id'])
    op.create_index('ix_operator_action_logs_action_type', 'operator_action_logs', ['action_type'])


def downgrade() -> None:
    """Drop Week 3 service tables."""
    op.drop_table('operator_action_logs')
    op.drop_table('missed_check_ins')
    op.drop_table('safety_escalations')
    op.drop_table('check_in_requests')
    op.drop_table('check_in_schedules')
