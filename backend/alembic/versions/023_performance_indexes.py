"""Add performance indexes for frequently queried columns.

Revision ID: 023_performance_indexes
Revises: 022_auth_password_reset
Create Date: 2026-08-06 00:00:00.000000

Adds indexes on frequently queried columns across the notification,
incident, check-in, escalation, and family portal tables. All index
creation is idempotent (checks for existing index before creating) so
this migration is safe to run on both fresh and existing databases.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

# revision identifiers, used by Alembic.
revision = '023_performance_indexes'
down_revision = '022_auth_password_reset'
branch_labels = None
depends_on = None


def _index_exists(conn, table_name, index_name):
    """Check if an index exists on the given table (works for both SQLite and PostgreSQL)."""
    inspector = sa_inspect(conn)
    indexes = inspector.get_indexes(table_name)
    return any(idx["name"] == index_name for idx in indexes)


def upgrade():
    conn = op.get_bind()

    # ── Notification tables ──────────────────────────────────────────────
    if not _index_exists(conn, "notification_event_stream", "ix_notification_event_stream_status"):
        op.create_index("ix_notification_event_stream_status", "notification_event_stream", ["status"])

    if not _index_exists(conn, "notification_queue_items", "ix_notification_queue_items_status"):
        op.create_index("ix_notification_queue_items_status", "notification_queue_items", ["status"])

    if not _index_exists(conn, "notification_queue_items", "ix_notification_queue_items_event_id"):
        op.create_index("ix_notification_queue_items_event_id", "notification_queue_items", ["event_id"])

    if not _index_exists(conn, "notification_queue_items", "ix_notification_queue_items_recipient_user_id"):
        op.create_index("ix_notification_queue_items_recipient_user_id", "notification_queue_items", ["recipient_user_id"])

    if not _index_exists(conn, "notification_lifecycle_events", "ix_notification_lifecycle_events_notification_item_id"):
        op.create_index("ix_notification_lifecycle_events_notification_item_id", "notification_lifecycle_events", ["notification_item_id"])

    # ── Incident tables ──────────────────────────────────────────────────
    if not _index_exists(conn, "risk_incidents", "ix_risk_incidents_trip_id"):
        op.create_index("ix_risk_incidents_trip_id", "risk_incidents", ["trip_id"])

    if not _index_exists(conn, "risk_incidents", "ix_risk_incidents_sos_alert_id"):
        op.create_index("ix_risk_incidents_sos_alert_id", "risk_incidents", ["sos_alert_id"])

    if not _index_exists(conn, "risk_incidents", "ix_risk_incidents_fisherman_id"):
        op.create_index("ix_risk_incidents_fisherman_id", "risk_incidents", ["fisherman_id"])

    # ── Check-in tables ──────────────────────────────────────────────────
    if not _index_exists(conn, "checkin_logs", "ix_checkin_logs_trip_id"):
        op.create_index("ix_checkin_logs_trip_id", "checkin_logs", ["trip_id"])

    if not _index_exists(conn, "checkin_logs", "ix_checkin_logs_fisherman_id"):
        op.create_index("ix_checkin_logs_fisherman_id", "checkin_logs", ["fisherman_id"])

    # ── Escalation tables ────────────────────────────────────────────────
    if not _index_exists(conn, "safety_escalations", "ix_safety_escalations_fisherman_id"):
        op.create_index("ix_safety_escalations_fisherman_id", "safety_escalations", ["fisherman_id"])

    if not _index_exists(conn, "safety_escalations", "ix_safety_escalations_trip_id"):
        op.create_index("ix_safety_escalations_trip_id", "safety_escalations", ["trip_id"])

    if not _index_exists(conn, "safety_escalations", "ix_safety_escalations_sos_alert_id"):
        op.create_index("ix_safety_escalations_sos_alert_id", "safety_escalations", ["sos_alert_id"])

    if not _index_exists(conn, "safety_escalations", "ix_safety_escalations_status"):
        op.create_index("ix_safety_escalations_status", "safety_escalations", ["status"])

    # ── Copilot tables ───────────────────────────────────────────────────
    if not _index_exists(conn, "copilot_sessions", "ix_copilot_sessions_fisherman_id"):
        op.create_index("ix_copilot_sessions_fisherman_id", "copilot_sessions", ["fisherman_id"])

    # ── Family portal tables ─────────────────────────────────────────────
    if not _index_exists(conn, "family_portal_access", "ix_family_portal_access_family_member_id"):
        op.create_index("ix_family_portal_access_family_member_id", "family_portal_access", ["family_member_id"])

    if not _index_exists(conn, "family_portal_access", "ix_family_portal_access_fisherman_id"):
        op.create_index("ix_family_portal_access_fisherman_id", "family_portal_access", ["fisherman_id"])

    if not _index_exists(conn, "family_safety_events", "ix_family_safety_events_family_member_id"):
        op.create_index("ix_family_safety_events_family_member_id", "family_safety_events", ["family_member_id"])

    if not _index_exists(conn, "family_safety_events", "ix_family_safety_events_fisherman_id"):
        op.create_index("ix_family_safety_events_fisherman_id", "family_safety_events", ["fisherman_id"])

    if not _index_exists(conn, "family_notifications", "ix_family_notifications_family_member_id"):
        op.create_index("ix_family_notifications_family_member_id", "family_notifications", ["family_member_id"])


def downgrade():
    """Drop the indexes added in upgrade()."""
    conn = op.get_bind()

    # Notification tables
    if _index_exists(conn, "notification_event_stream", "ix_notification_event_stream_status"):
        op.drop_index("ix_notification_event_stream_status", table_name="notification_event_stream")
    if _index_exists(conn, "notification_queue_items", "ix_notification_queue_items_status"):
        op.drop_index("ix_notification_queue_items_status", table_name="notification_queue_items")
    if _index_exists(conn, "notification_queue_items", "ix_notification_queue_items_event_id"):
        op.drop_index("ix_notification_queue_items_event_id", table_name="notification_queue_items")
    if _index_exists(conn, "notification_queue_items", "ix_notification_queue_items_recipient_user_id"):
        op.drop_index("ix_notification_queue_items_recipient_user_id", table_name="notification_queue_items")
    if _index_exists(conn, "notification_lifecycle_events", "ix_notification_lifecycle_events_notification_item_id"):
        op.drop_index("ix_notification_lifecycle_events_notification_item_id", table_name="notification_lifecycle_events")

    # Incident tables
    if _index_exists(conn, "risk_incidents", "ix_risk_incidents_trip_id"):
        op.drop_index("ix_risk_incidents_trip_id", table_name="risk_incidents")
    if _index_exists(conn, "risk_incidents", "ix_risk_incidents_sos_alert_id"):
        op.drop_index("ix_risk_incidents_sos_alert_id", table_name="risk_incidents")
    if _index_exists(conn, "risk_incidents", "ix_risk_incidents_fisherman_id"):
        op.drop_index("ix_risk_incidents_fisherman_id", table_name="risk_incidents")

    # Check-in tables
    if _index_exists(conn, "checkin_logs", "ix_checkin_logs_trip_id"):
        op.drop_index("ix_checkin_logs_trip_id", table_name="checkin_logs")
    if _index_exists(conn, "checkin_logs", "ix_checkin_logs_fisherman_id"):
        op.drop_index("ix_checkin_logs_fisherman_id", table_name="checkin_logs")

    # Escalation tables
    if _index_exists(conn, "safety_escalations", "ix_safety_escalations_fisherman_id"):
        op.drop_index("ix_safety_escalations_fisherman_id", table_name="safety_escalations")
    if _index_exists(conn, "safety_escalations", "ix_safety_escalations_trip_id"):
        op.drop_index("ix_safety_escalations_trip_id", table_name="safety_escalations")
    if _index_exists(conn, "safety_escalations", "ix_safety_escalations_sos_alert_id"):
        op.drop_index("ix_safety_escalations_sos_alert_id", table_name="safety_escalations")
    if _index_exists(conn, "safety_escalations", "ix_safety_escalations_status"):
        op.drop_index("ix_safety_escalations_status", table_name="safety_escalations")

    # Copilot tables
    if _index_exists(conn, "copilot_sessions", "ix_copilot_sessions_fisherman_id"):
        op.drop_index("ix_copilot_sessions_fisherman_id", table_name="copilot_sessions")

    # Family portal tables
    if _index_exists(conn, "family_portal_access", "ix_family_portal_access_family_member_id"):
        op.drop_index("ix_family_portal_access_family_member_id", table_name="family_portal_access")
    if _index_exists(conn, "family_portal_access", "ix_family_portal_access_fisherman_id"):
        op.drop_index("ix_family_portal_access_fisherman_id", table_name="family_portal_access")
    if _index_exists(conn, "family_safety_events", "ix_family_safety_events_family_member_id"):
        op.drop_index("ix_family_safety_events_family_member_id", table_name="family_safety_events")
    if _index_exists(conn, "family_safety_events", "ix_family_safety_events_fisherman_id"):
        op.drop_index("ix_family_safety_events_fisherman_id", table_name="family_safety_events")
    if _index_exists(conn, "family_notifications", "ix_family_notifications_family_member_id"):
        op.drop_index("ix_family_notifications_family_member_id", table_name="family_notifications")