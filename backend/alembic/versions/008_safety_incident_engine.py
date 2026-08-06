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
from sqlalchemy import inspect as sa_inspect


revision = '008_safety_incident_engine'
down_revision = '007_core_tracking_fields'
branch_labels = None
depends_on = None


def _table_exists(name):
    return sa_inspect(op.get_bind()).has_table(name)


def _column_exists(table, column):
    bind = op.get_bind()
    if not sa_inspect(bind).has_table(table):
        return False
    return column in {c["name"] for c in sa_inspect(bind).get_columns(table)}


def _index_exists(name, table):
    bind = op.get_bind()
    if not sa_inspect(bind).has_table(table):
        return False
    return any(idx["name"] == name for idx in sa_inspect(bind).get_indexes(table))


def upgrade() -> None:
    # sos_alerts.network_type
    if _table_exists("sos_alerts") and not _column_exists("sos_alerts", "network_type"):
        op.add_column('sos_alerts', sa.Column('network_type', sa.String(20), nullable=True))

    # risk_incidents columns
    if _table_exists("risk_incidents"):
        if not _column_exists("risk_incidents", "fisherman_id"):
            op.add_column('risk_incidents', sa.Column('fisherman_id', sa.Integer(), nullable=True))
        if not _column_exists("risk_incidents", "status"):
            op.add_column('risk_incidents', sa.Column('status', sa.String(30), nullable=False, server_default='received'))
        if not _column_exists("risk_incidents", "acknowledged_by"):
            op.add_column('risk_incidents', sa.Column('acknowledged_by', sa.Integer(), nullable=True))
        if not _column_exists("risk_incidents", "acknowledged_at"):
            op.add_column('risk_incidents', sa.Column('acknowledged_at', sa.DateTime(), nullable=True))
        if not _column_exists("risk_incidents", "closed_at"):
            op.add_column('risk_incidents', sa.Column('closed_at', sa.DateTime(), nullable=True))
        if not _column_exists("risk_incidents", "ix_risk_incidents_status"):
            op.create_index('ix_risk_incidents_status', 'risk_incidents', ['status'])

    # incident_events table
    if not _table_exists("incident_events"):
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
    if _table_exists("incident_events"):
        op.drop_table('incident_events')
    if _table_exists("risk_incidents") and _index_exists("ix_risk_incidents_status", "risk_incidents"):
        op.drop_index('ix_risk_incidents_status', table_name='risk_incidents')
    if _table_exists("risk_incidents"):
        for col in ("closed_at", "acknowledged_at", "acknowledged_by", "status", "fisherman_id"):
            if _column_exists("risk_incidents", col):
                op.drop_column('risk_incidents', col)
    if _table_exists("sos_alerts") and _column_exists("sos_alerts", "network_type"):
        op.drop_column('sos_alerts', 'network_type')
