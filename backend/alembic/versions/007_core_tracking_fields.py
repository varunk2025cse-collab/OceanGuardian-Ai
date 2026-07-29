"""V2 core build: location telemetry fields + source column

Adds altitude/battery/network telemetry to location_pings plus a `source`
column (defaulted to MOBILE_GPS) so future IoT/satellite ingestion paths
can be distinguished without another migration. All additive/nullable
(source has a server default), so existing rows remain valid.

Revision ID: 007_core_tracking_fields
Revises: 006_week3_services
Create Date: 2025-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision = '007_core_tracking_fields'
down_revision = '006_week3_services'
branch_labels = None
depends_on = None


def _table_exists(name):
    return sa_inspect(op.get_bind()).has_table(name)


def _column_exists(table, column):
    bind = op.get_bind()
    if not sa_inspect(bind).has_table(table):
        return False
    return column in {c["name"] for c in sa_inspect(bind).get_columns(table)}


def upgrade() -> None:
    if not _table_exists("location_pings"):
        return
    if not _column_exists("location_pings", "altitude_meters"):
        op.add_column('location_pings', sa.Column('altitude_meters', sa.Float(), nullable=True))
    if not _column_exists("location_pings", "battery_percent"):
        op.add_column('location_pings', sa.Column('battery_percent', sa.Float(), nullable=True))
    if not _column_exists("location_pings", "network_type"):
        op.add_column('location_pings', sa.Column('network_type', sa.String(20), nullable=True))
    if not _column_exists("location_pings", "source"):
        op.add_column(
            'location_pings',
            sa.Column('source', sa.String(20), nullable=False, server_default='MOBILE_GPS'),
        )


def downgrade() -> None:
    if not _table_exists("location_pings"):
        return
    if _column_exists("location_pings", "source"):
        op.drop_column('location_pings', 'source')
    if _column_exists("location_pings", "network_type"):
        op.drop_column('location_pings', 'network_type')
    if _column_exists("location_pings", "battery_percent"):
        op.drop_column('location_pings', 'battery_percent')
    if _column_exists("location_pings", "altitude_meters"):
        op.drop_column('location_pings', 'altitude_meters')
