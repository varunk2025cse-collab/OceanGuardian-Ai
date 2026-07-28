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


revision = '007_core_tracking_fields'
down_revision = '006_week3_services'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('location_pings', sa.Column('altitude_meters', sa.Float(), nullable=True))
    op.add_column('location_pings', sa.Column('battery_percent', sa.Float(), nullable=True))
    op.add_column('location_pings', sa.Column('network_type', sa.String(20), nullable=True))
    op.add_column(
        'location_pings',
        sa.Column('source', sa.String(20), nullable=False, server_default='MOBILE_GPS'),
    )


def downgrade() -> None:
    op.drop_column('location_pings', 'source')
    op.drop_column('location_pings', 'network_type')
    op.drop_column('location_pings', 'battery_percent')
    op.drop_column('location_pings', 'altitude_meters')
