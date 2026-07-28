"""V2 core build: Safety State Engine + Incident Engine

Adds:
  - sos_alerts.network_type (device state at SOS trigger)
  - risk_incidents.status/acknowledged_by/acknowledged_at/closed_at/fisherman_id
    (the table existed but nothing wrote to it — see docs/V1_AUDIT.md)
  - incident_events (new table — the incident state-transition audit trail)

All additive: new columns are nullable or have a server default, so
existing rows remain valid.

Revision ID: 008_safety_incident_engine
Revises: 007_core_tracking_fields
Create Date: 2025-01-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '008_safety_incident_engine'
down_revision = '007_core_tracking_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sos_alerts', sa.Column('network_type', sa.String(20), nullable=True))

    op.add_column('risk_incidents', sa.Column('fisherman_id', sa.Integer(), nullable=True))
    op.add_column('risk_incidents', sa.Column('status', sa.String(30), nullable=False, server_default='received'))
    op.add_column('risk_incidents', sa.Column('acknowledged_by', sa.Integer(), nullable=True))
    op.add_column('risk_incidents', sa.Column('acknowledged_at', sa.DateTime(), nullable=True))
    op.add_column('risk_incidents', sa.Column('closed_at', sa.DateTime(), nullable=True))
    op.create_index('ix_risk_incidents_status', 'risk_incidents', ['status'])

    op.create_table(
        'incident_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('actor_id', sa.Integer(), nullable=True),
        sa.Column('previous_status', sa.String(30), nullable=True),
        sa.Column('new_status', sa.String(30), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['incident_id'], ['risk_incidents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_incident_events_incident_id', 'incident_events', ['incident_id'])


def downgrade() -> None:
    op.drop_table('incident_events')
    op.drop_index('ix_risk_incidents_status', table_name='risk_incidents')
    op.drop_column('risk_incidents', 'closed_at')
    op.drop_column('risk_incidents', 'acknowledged_at')
    op.drop_column('risk_incidents', 'acknowledged_by')
    op.drop_column('risk_incidents', 'status')
    op.drop_column('risk_incidents', 'fisherman_id')
    op.drop_column('sos_alerts', 'network_type')
