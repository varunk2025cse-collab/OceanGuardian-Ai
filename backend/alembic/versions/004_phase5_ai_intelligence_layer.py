"""Phase 5 — AI Intelligence Layer (Copilot, Risk Engine, Check-in, Harbor, Fuel, Family, Analytics).

Revision ID: 004
Revises: 003
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text, inspect as sa_inspect

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def _table_exists(name):
    return sa_inspect(op.get_bind()).has_table(name)


def _pg_exec(sql):
    op.execute(text(sql))


def upgrade():
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    # =================================================================
    # ENUMS (PostgreSQL only)
    # =================================================================
    if not is_sqlite:
        # Risk level enum
        _pg_exec("""DO $$ BEGIN
            CREATE TYPE risk_level AS ENUM ('green', 'yellow', 'red', 'critical');
            EXCEPTION WHEN duplicate_object THEN NULL;
        END $$""")

        # Copilot intent enum
        _pg_exec("""DO $$ BEGIN
            CREATE TYPE copilot_intent AS ENUM (
                'weather_query', 'safety_guidance', 'navigation_help',
                'scheme_information', 'boat_info', 'trip_status',
                'emergency_help', 'other'
            );
            EXCEPTION WHEN duplicate_object THEN NULL;
        END $$""")

        # Check-in status enum
        _pg_exec("""DO $$ BEGIN
            CREATE TYPE checkin_status AS ENUM ('active', 'warning', 'alert', 'resolved');
            EXCEPTION WHEN duplicate_object THEN NULL;
        END $$""")

    # =================================================================
    # 1. COPILOT TABLES
    # =================================================================
    if not _table_exists("copilot_sessions"):
        op.create_table(
            "copilot_sessions",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("fisherman_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("session_key", sa.String(255), unique=True, nullable=False),
            sa.Column("language", sa.String(10), default="ta"),  # 'ta' or 'en'
            sa.Column("context_json", sa.Text, default="{}"),  # Current context as JSON
            sa.Column("last_activity_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("is_active", sa.Boolean, default=True),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index("ix_copilot_sessions_fisherman", "copilot_sessions", ["fisherman_id"])

    if not _table_exists("copilot_conversations"):
        op.create_table(
            "copilot_conversations",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("session_id", sa.Integer, sa.ForeignKey("copilot_sessions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_message", sa.Text, nullable=False),
            sa.Column("ai_response", sa.Text, nullable=False),
            sa.Column("intent", sa.String(50)),  # Mapped from enum in logic
            sa.Column("confidence_score", sa.Float, default=0.0),  # 0.0 to 1.0
            sa.Column("audio_request_url", sa.String(500)),  # URL to user's voice input
            sa.Column("audio_response_url", sa.String(500)),  # URL to AI's voice output
            sa.Column("tokens_used", sa.Integer, default=0),
            sa.Column("response_time_ms", sa.Integer, default=0),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        )
        op.create_index("ix_copilot_conversations_session", "copilot_conversations", ["session_id"])
        op.create_index("ix_copilot_conversations_intent", "copilot_conversations", ["intent"])

    # =================================================================
    # 2. RISK PREDICTION TABLES
    # =================================================================
    if not _table_exists("risk_predictions"):
        op.create_table(
            "risk_predictions",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("trip_id", sa.Integer, sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
            sa.Column("risk_level", sa.String(20)),  # Mapped from enum
            sa.Column("risk_score", sa.Float, nullable=False),  # 0.0 to 100.0
            sa.Column("contributing_factors_json", sa.Text, default="{}"),  # Weather, location, boat, etc.
            sa.Column("model_version", sa.String(50)),  # e.g., "xgboost_v1.2"
            sa.Column("prediction_confidence", sa.Float, default=0.0),  # 0.0 to 1.0
            sa.Column("recommendations_json", sa.Text, default="{}"),  # Safety recommendations
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index("ix_risk_predictions_trip", "risk_predictions", ["trip_id"])
        op.create_index("ix_risk_predictions_level", "risk_predictions", ["risk_level"])

    if not _table_exists("risk_incidents"):
        op.create_table(
            "risk_incidents",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("trip_id", sa.Integer, sa.ForeignKey("trips.id", ondelete="CASCADE")),
            sa.Column("sos_alert_id", sa.Integer, sa.ForeignKey("sos_alerts.id", ondelete="CASCADE")),
            sa.Column("incident_type", sa.String(100)),  # e.g., "engine_failure", "collision", "weather_hit"
            sa.Column("severity", sa.String(20)),
            sa.Column("description", sa.Text),
            sa.Column("location_json", sa.Text, default="{}"),  # lat/lng at time of incident
            sa.Column("weather_conditions_json", sa.Text, default="{}"),  # weather data at incident time
            sa.Column("boat_condition_json", sa.Text, default="{}"),  # boat data at incident time
            sa.Column("resolution", sa.Text),
            sa.Column("lessons_learned", sa.Text),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        )
        op.create_index("ix_risk_incidents_trip", "risk_incidents", ["trip_id"])

    if not _table_exists("risk_model_metrics"):
        op.create_table(
            "risk_model_metrics",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("model_version", sa.String(50), unique=True, nullable=False),
            sa.Column("accuracy", sa.Float),
            sa.Column("precision", sa.Float),
            sa.Column("recall", sa.Float),
            sa.Column("f1_score", sa.Float),
            sa.Column("training_samples", sa.Integer),
            sa.Column("last_trained_at", sa.DateTime),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        )

    # =================================================================
    # 3. SMART CHECK-IN TABLES
    # =================================================================
    if not _table_exists("checkin_logs"):
        op.create_table(
            "checkin_logs",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("trip_id", sa.Integer, sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
            sa.Column("fisherman_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("last_gps_location_json", sa.Text, default="{}"),  # {lat, lng, accuracy}
            sa.Column("last_update_time", sa.DateTime),
            sa.Column("time_since_last_update_minutes", sa.Integer, default=0),
            sa.Column("movement_detected", sa.Boolean, default=True),
            sa.Column("offline_duration_minutes", sa.Integer, default=0),
            sa.Column("status", sa.String(20)),  # Mapped from enum
            sa.Column("check_status", sa.String(50)),  # "ok", "stale", "offline", "alert"
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        )
        op.create_index("ix_checkin_logs_trip", "checkin_logs", ["trip_id"])
        op.create_index("ix_checkin_logs_fisherman", "checkin_logs", ["fisherman_id"])

    if not _table_exists("checkin_alerts"):
        op.create_table(
            "checkin_alerts",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("trip_id", sa.Integer, sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
            sa.Column("fisherman_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("alert_type", sa.String(50)),  # "no_gps_updates", "no_movement", "offline_too_long"
            sa.Column("threshold_value", sa.String(100)),  # e.g., "30 minutes"
            sa.Column("alert_description", sa.Text),
            sa.Column("family_notified", sa.Boolean, default=False),
            sa.Column("rescue_operator_notified", sa.Boolean, default=False),
            sa.Column("dismissed", sa.Boolean, default=False),
            sa.Column("resolution_notes", sa.Text),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("resolved_at", sa.DateTime),
        )
        op.create_index("ix_checkin_alerts_trip", "checkin_alerts", ["trip_id"])

    # =================================================================
    # 4. HARBOR INTELLIGENCE TABLES
    # =================================================================
    if not _table_exists("harbors"):
        op.create_table(
            "harbors",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("location_json", sa.Text, nullable=False),  # {lat, lng}
            sa.Column("state", sa.String(50)),
            sa.Column("district", sa.String(50)),
            sa.Column("country", sa.String(50), default="India"),
            sa.Column("harbor_type", sa.String(50)),  # "major", "minor", "emergency"
            sa.Column("available_services", sa.Text, default="[]"),  # JSON array
            sa.Column("fuel_availability", sa.Boolean, default=False),
            sa.Column("ice_availability", sa.Boolean, default=False),
            sa.Column("medical_facility", sa.Boolean, default=False),
            sa.Column("repair_facility", sa.Boolean, default=False),
            sa.Column("emergency_shelter", sa.Boolean, default=False),
            sa.Column("contact_number", sa.String(20)),
            sa.Column("operating_hours", sa.String(100)),
            sa.Column("depth_meters", sa.Float),
            sa.Column("average_rating", sa.Float, default=0.0),
            sa.Column("total_reviews", sa.Integer, default=0),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index("ix_harbors_location", "harbors", ["name"])
        op.create_index("ix_harbors_type", "harbors", ["harbor_type"])

    if not _table_exists("harbor_reviews"):
        op.create_table(
            "harbor_reviews",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("harbor_id", sa.Integer, sa.ForeignKey("harbors.id", ondelete="CASCADE"), nullable=False),
            sa.Column("fisherman_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE")),
            sa.Column("rating", sa.Integer),  # 1-5
            sa.Column("review_text", sa.Text),
            sa.Column("service_quality", sa.Integer),
            sa.Column("facilities_quality", sa.Integer),
            sa.Column("staff_helpfulness", sa.Integer),
            sa.Column("visit_date", sa.DateTime),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        )
        op.create_index("ix_harbor_reviews_harbor", "harbor_reviews", ["harbor_id"])

    if not _table_exists("harbor_visits"):
        op.create_table(
            "harbor_visits",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("trip_id", sa.Integer, sa.ForeignKey("trips.id", ondelete="CASCADE")),
            sa.Column("harbor_id", sa.Integer, sa.ForeignKey("harbors.id", ondelete="CASCADE")),
            sa.Column("fisherman_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE")),
            sa.Column("arrival_time", sa.DateTime),
            sa.Column("departure_time", sa.DateTime),
            sa.Column("services_used", sa.Text, default="[]"),  # JSON array
            sa.Column("notes", sa.Text),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        )
        op.create_index("ix_harbor_visits_trip", "harbor_visits", ["trip_id"])

    # =================================================================
    # 5. FUEL & BOAT HEALTH TABLES
    # =================================================================
    if not _table_exists("boat_fuel_logs"):
        op.create_table(
            "boat_fuel_logs",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("boat_id", sa.Integer, sa.ForeignKey("boats.id", ondelete="CASCADE"), nullable=False),
            sa.Column("trip_id", sa.Integer, sa.ForeignKey("trips.id", ondelete="CASCADE")),
            sa.Column("fuel_level_start_percent", sa.Float),
            sa.Column("fuel_level_end_percent", sa.Float),
            sa.Column("fuel_consumed_liters", sa.Float),
            sa.Column("distance_traveled_km", sa.Float),
            sa.Column("efficiency_km_per_liter", sa.Float),
            sa.Column("timestamp", sa.DateTime, server_default=sa.func.now()),
        )
        op.create_index("ix_boat_fuel_logs_boat", "boat_fuel_logs", ["boat_id"])

    if not _table_exists("boat_maintenance"):
        op.create_table(
            "boat_maintenance",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("boat_id", sa.Integer, sa.ForeignKey("boats.id", ondelete="CASCADE"), nullable=False),
            sa.Column("maintenance_type", sa.String(100)),  # "oil_change", "filter_replacement", "engine_servicing"
            sa.Column("description", sa.Text),
            sa.Column("scheduled_date", sa.DateTime),
            sa.Column("completed_date", sa.DateTime),
            sa.Column("cost_rupees", sa.Float),
            sa.Column("technician_name", sa.String(120)),
            sa.Column("service_center", sa.String(120)),
            sa.Column("parts_replaced", sa.Text),  # JSON
            sa.Column("notes", sa.Text),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        )
        op.create_index("ix_boat_maintenance_boat", "boat_maintenance", ["boat_id"])

    if not _table_exists("boat_health_status"):
        op.create_table(
            "boat_health_status",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("boat_id", sa.Integer, sa.ForeignKey("boats.id", ondelete="CASCADE"), nullable=False),
            sa.Column("engine_hours", sa.Float),
            sa.Column("last_service_date", sa.DateTime),
            sa.Column("next_service_date", sa.DateTime),
            sa.Column("total_maintenance_cost", sa.Float),
            sa.Column("health_score", sa.Float),  # 0-100
            sa.Column("issues_json", sa.Text, default="[]"),  # Array of issues
            sa.Column("last_assessed_date", sa.DateTime),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        )

    if not _table_exists("fuel_predictions"):
        op.create_table(
            "fuel_predictions",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("trip_id", sa.Integer, sa.ForeignKey("trips.id", ondelete="CASCADE")),
            sa.Column("boat_id", sa.Integer, sa.ForeignKey("boats.id", ondelete="CASCADE")),
            sa.Column("estimated_fuel_needed_liters", sa.Float),
            sa.Column("estimated_return_fuel_percent", sa.Float),
            sa.Column("distance_estimate_km", sa.Float),
            sa.Column("model_accuracy_percent", sa.Float),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        )
        op.create_index("ix_fuel_predictions_trip", "fuel_predictions", ["trip_id"])

    # =================================================================
    # 6. FAMILY PORTAL TABLES
    # =================================================================
    if not _table_exists("family_portal_access"):
        op.create_table(
            "family_portal_access",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("family_member_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("fisherman_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("access_level", sa.String(50)),  # "view_only", "emergency_contact", "primary"
            sa.Column("can_view_live_location", sa.Boolean, default=True),
            sa.Column("can_view_trip_history", sa.Boolean, default=True),
            sa.Column("can_receive_alerts", sa.Boolean, default=True),
            sa.Column("can_contact_rescue", sa.Boolean, default=True),
            sa.Column("notification_preferences_json", sa.Text, default="{}"),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        )
        op.create_index("ix_family_portal_access_family", "family_portal_access", ["family_member_id"])

    if not _table_exists("family_safety_events"):
        op.create_table(
            "family_safety_events",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("family_member_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("fisherman_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("event_type", sa.String(50)),  # "trip_started", "sos_alert", "trip_completed", "location_update"
            sa.Column("event_description", sa.Text),
            sa.Column("trip_id", sa.Integer, sa.ForeignKey("trips.id", ondelete="CASCADE")),
            sa.Column("sos_alert_id", sa.Integer, sa.ForeignKey("sos_alerts.id", ondelete="CASCADE")),
            sa.Column("location_json", sa.Text),  # Last known location
            sa.Column("severity", sa.String(20)),  # "info", "warning", "critical"
            sa.Column("read_at", sa.DateTime),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        )
        op.create_index("ix_family_safety_events_family", "family_safety_events", ["family_member_id"])

    if not _table_exists("family_notifications"):
        op.create_table(
            "family_notifications",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("family_member_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("notification_type", sa.String(50)),  # "push", "sms", "email"
            sa.Column("message", sa.Text),
            sa.Column("related_event_id", sa.Integer),
            sa.Column("sent_at", sa.DateTime),
            sa.Column("read_at", sa.DateTime),
            sa.Column("delivery_status", sa.String(20)),  # "pending", "sent", "failed"
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        )
        op.create_index("ix_family_notifications_family", "family_notifications", ["family_member_id"])

    # =================================================================
    # 7. ANALYTICS TABLES
    # =================================================================
    if not _table_exists("analytics_sos_metrics"):
        op.create_table(
            "analytics_sos_metrics",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("period_date", sa.Date, nullable=False),  # YYYY-MM-DD
            sa.Column("period_type", sa.String(20)),  # "daily", "weekly", "monthly"
            sa.Column("total_sos_alerts", sa.Integer, default=0),
            sa.Column("acknowledged_count", sa.Integer, default=0),
            sa.Column("resolved_count", sa.Integer, default=0),
            sa.Column("false_alarm_count", sa.Integer, default=0),
            sa.Column("average_response_time_minutes", sa.Float),
            sa.Column("by_region_json", sa.Text, default="{}"),  # {region: count}
            sa.Column("by_hazard_type_json", sa.Text, default="{}"),  # {hazard_type: count}
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        )
        op.create_index("ix_analytics_sos_metrics_date", "analytics_sos_metrics", ["period_date"])

    if not _table_exists("analytics_trip_metrics"):
        op.create_table(
            "analytics_trip_metrics",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("period_date", sa.Date, nullable=False),
            sa.Column("period_type", sa.String(20)),
            sa.Column("total_trips", sa.Integer, default=0),
            sa.Column("completed_trips", sa.Integer, default=0),
            sa.Column("trips_with_incidents", sa.Integer, default=0),
            sa.Column("average_trip_duration_hours", sa.Float),
            sa.Column("total_catch_value_rupees", sa.Float, default=0.0),
            sa.Column("by_harbor_json", sa.Text, default="{}"),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        )

    if not _table_exists("analytics_risk_metrics"):
        op.create_table(
            "analytics_risk_metrics",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("period_date", sa.Date, nullable=False),
            sa.Column("period_type", sa.String(20)),
            sa.Column("green_risk_trips", sa.Integer, default=0),
            sa.Column("yellow_risk_trips", sa.Integer, default=0),
            sa.Column("red_risk_trips", sa.Integer, default=0),
            sa.Column("critical_risk_trips", sa.Integer, default=0),
            sa.Column("average_risk_score", sa.Float),
            sa.Column("predictive_accuracy", sa.Float),
            sa.Column("by_weather_condition_json", sa.Text, default="{}"),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        )

    if not _table_exists("analytics_user_engagement"):
        op.create_table(
            "analytics_user_engagement",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("period_date", sa.Date, nullable=False),
            sa.Column("active_fishermen", sa.Integer, default=0),
            sa.Column("active_operators", sa.Integer, default=0),
            sa.Column("active_family_members", sa.Integer, default=0),
            sa.Column("copilot_queries_total", sa.Integer, default=0),
            sa.Column("copilot_queries_by_intent_json", sa.Text, default="{}"),
            sa.Column("dashboard_sessions", sa.Integer, default=0),
            sa.Column("mobile_app_sessions", sa.Integer, default=0),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        )


def downgrade():
    # Drop all tables created in this migration
    tables = [
        "analytics_user_engagement",
        "analytics_risk_metrics",
        "analytics_trip_metrics",
        "analytics_sos_metrics",
        "family_notifications",
        "family_safety_events",
        "family_portal_access",
        "fuel_predictions",
        "boat_health_status",
        "boat_maintenance",
        "boat_fuel_logs",
        "harbor_visits",
        "harbor_reviews",
        "harbors",
        "checkin_alerts",
        "checkin_logs",
        "risk_model_metrics",
        "risk_incidents",
        "risk_predictions",
        "copilot_conversations",
        "copilot_sessions",
    ]

    for table in tables:
        op.drop_table(table, if_exists=True)

    # Drop enums (PostgreSQL only)
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        _pg_exec("DROP TYPE IF EXISTS checkin_status CASCADE")
        _pg_exec("DROP TYPE IF EXISTS copilot_intent CASCADE")
        _pg_exec("DROP TYPE IF EXISTS risk_level CASCADE")
