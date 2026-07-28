"""Phase 5 Models — AI Intelligence Layer.

Copilot sessions, Risk predictions, Check-in logs, Harbor intelligence,
Fuel tracking, Family portal, Analytics tables, Week 3 services.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime,
    ForeignKey, Enum, Date
)
from sqlalchemy.orm import relationship
from app.database import Base
from enum import Enum as PyEnum


# =================================================================
# ENUMS
# =================================================================
class RiskLevel(PyEnum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    CRITICAL = "critical"


class CopilotIntent(PyEnum):
    WEATHER_QUERY = "weather_query"
    SAFETY_GUIDANCE = "safety_guidance"
    NAVIGATION_HELP = "navigation_help"
    SCHEME_INFORMATION = "scheme_information"
    BOAT_INFO = "boat_info"
    TRIP_STATUS = "trip_status"
    EMERGENCY_HELP = "emergency_help"
    OTHER = "other"


class CheckinStatus(PyEnum):
    ACTIVE = "active"
    WARNING = "warning"
    ALERT = "alert"
    RESOLVED = "resolved"


# =================================================================
# 1. COPILOT TABLES
# =================================================================
class CopilotSession(Base):
    __tablename__ = "copilot_sessions"

    id = Column(Integer, primary_key=True)
    fisherman_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_key = Column(String(255), unique=True, nullable=False)
    language = Column(String(10), default="ta")  # 'ta' or 'en'
    context_json = Column(Text, default="{}")  # Current context as JSON
    last_activity_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    fisherman = relationship("User", foreign_keys=[fisherman_id])
    conversations = relationship("CopilotConversation", cascade="all, delete-orphan")


class CopilotConversation(Base):
    __tablename__ = "copilot_conversations"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("copilot_sessions.id", ondelete="CASCADE"), nullable=False)
    user_message = Column(Text, nullable=False)
    ai_response = Column(Text, nullable=False)
    intent = Column(String(50))  # Mapped from CopilotIntent enum
    confidence_score = Column(Float, default=0.0)  # 0.0 to 1.0
    audio_request_url = Column(String(500))  # URL to user's voice input
    audio_response_url = Column(String(500))  # URL to AI's voice output
    tokens_used = Column(Integer, default=0)
    response_time_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("CopilotSession", foreign_keys=[session_id])


# =================================================================
# 2. RISK PREDICTION TABLES
# =================================================================
class RiskPrediction(Base):
    __tablename__ = "risk_predictions"

    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    risk_level = Column(String(20))  # Mapped from RiskLevel enum
    risk_score = Column(Float, nullable=False)  # 0.0 to 100.0
    contributing_factors_json = Column(Text, default="{}")  # Weather, location, boat, etc.
    model_version = Column(String(50))  # e.g., "xgboost_v1.2"
    prediction_confidence = Column(Float, default=0.0)  # 0.0 to 1.0
    recommendations_json = Column(Text, default="{}")  # Safety recommendations
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    trip = relationship("Trip", foreign_keys=[trip_id])


class RiskIncident(Base):
    """The incident record itself. Was schema-only in V1 (audit finding —
    nothing wrote to it); the V2 core build's incident engine
    (app/services/incident_service.py) is what actually populates and
    transitions it now. `status` drives the 8-state lifecycle; every
    transition is separately recorded in IncidentEvent below so there's a
    real audit trail, not just a snapshot of the current state."""
    __tablename__ = "risk_incidents"

    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"))
    sos_alert_id = Column(Integer, ForeignKey("sos_alerts.id", ondelete="CASCADE"))
    fisherman_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    incident_type = Column(String(100))  # e.g., "engine_failure", "collision", "weather_hit"
    severity = Column(String(20))
    description = Column(Text)
    location_json = Column(Text, default="{}")  # lat/lng at time of incident
    weather_conditions_json = Column(Text, default="{}")  # weather data at incident time
    boat_condition_json = Column(Text, default="{}")  # boat data at incident time
    resolution = Column(Text)
    lessons_learned = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # V2 core build additions — incident state machine (docs/INCIDENT_ENGINE.md)
    status = Column(String(30), nullable=False, default="received", index=True)
    acknowledged_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    # Relationships
    trip = relationship("Trip", foreign_keys=[trip_id])
    sos_alert = relationship("SOSAlert", foreign_keys=[sos_alert_id])
    fisherman = relationship("User", foreign_keys=[fisherman_id])
    acknowledged_by_user = relationship("User", foreign_keys=[acknowledged_by])
    events = relationship("IncidentEvent", back_populates="incident", order_by="IncidentEvent.created_at")


class IncidentEvent(Base):
    """Immutable audit trail entry for one incident state transition —
    actor, timestamp, old/new state, reason. Rows are never updated or
    deleted once written."""
    __tablename__ = "incident_events"

    id = Column(Integer, primary_key=True)
    incident_id = Column(Integer, ForeignKey("risk_incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # null = system-generated
    previous_status = Column(String(30), nullable=True)
    new_status = Column(String(30), nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    incident = relationship("RiskIncident", back_populates="events")
    actor = relationship("User", foreign_keys=[actor_id])


class RiskModelMetric(Base):
    __tablename__ = "risk_model_metrics"

    id = Column(Integer, primary_key=True)
    model_version = Column(String(50), unique=True, nullable=False)
    accuracy = Column(Float)
    precision = Column(Float)
    recall = Column(Float)
    f1_score = Column(Float)
    training_samples = Column(Integer)
    last_trained_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


# =================================================================
# 3. SMART CHECK-IN TABLES
# =================================================================
class CheckinLog(Base):
    __tablename__ = "checkin_logs"

    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    fisherman_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    last_gps_location_json = Column(Text, default="{}")  # {lat, lng, accuracy}
    last_update_time = Column(DateTime)
    time_since_last_update_minutes = Column(Integer, default=0)
    movement_detected = Column(Boolean, default=True)
    offline_duration_minutes = Column(Integer, default=0)
    status = Column(String(20))  # Mapped from CheckinStatus enum
    check_status = Column(String(50))  # "ok", "stale", "offline", "alert"
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    trip = relationship("Trip", foreign_keys=[trip_id])
    fisherman = relationship("User", foreign_keys=[fisherman_id])


class CheckinAlert(Base):
    __tablename__ = "checkin_alerts"

    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    fisherman_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    alert_type = Column(String(50))  # "no_gps_updates", "no_movement", "offline_too_long"
    threshold_value = Column(String(100))  # e.g., "30 minutes"
    alert_description = Column(Text)
    family_notified = Column(Boolean, default=False)
    rescue_operator_notified = Column(Boolean, default=False)
    dismissed = Column(Boolean, default=False)
    resolution_notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime)

    # Relationships
    trip = relationship("Trip", foreign_keys=[trip_id])
    fisherman = relationship("User", foreign_keys=[fisherman_id])


# =================================================================
# Week 3 — CheckInSchedule, MissedCheckIn, SafetyEscalation
# =================================================================
class CheckInSchedule(Base):
    """Scheduled check-in configuration per trip."""
    __tablename__ = "check_in_schedules"

    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    fisherman_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    interval_minutes = Column(Integer, default=30)
    next_checkin_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    trip = relationship("Trip", foreign_keys=[trip_id])
    fisherman = relationship("User", foreign_keys=[fisherman_id])


class CheckInRequest(Base):
    """Individual check-in request instances triggered by schedule."""
    __tablename__ = "check_in_requests"

    id = Column(Integer, primary_key=True)
    schedule_id = Column(Integer, ForeignKey("check_in_schedules.id", ondelete="CASCADE"), nullable=False)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    fisherman_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), default="pending")  # pending, responded, missed
    requested_at = Column(DateTime, default=datetime.utcnow)
    responded_at = Column(DateTime)
    response_status = Column(String(50))  # safe, help_needed, busy
    response_lat = Column(Float)
    response_lng = Column(Float)
    response_notes = Column(Text)
    synced = Column(Boolean, default=True)  # False for offline response
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    schedule = relationship("CheckInSchedule", foreign_keys=[schedule_id])
    trip = relationship("Trip", foreign_keys=[trip_id])
    fisherman = relationship("User", foreign_keys=[fisherman_id])


class MissedCheckIn(Base):
    """Record of missed check-in events with escalation tracking."""
    __tablename__ = "missed_check_ins"

    id = Column(Integer, primary_key=True)
    schedule_id = Column(Integer, ForeignKey("check_in_schedules.id", ondelete="SET NULL"))
    request_id = Column(Integer, ForeignKey("check_in_requests.id", ondelete="SET NULL"))
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    fisherman_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    consecutive_missed = Column(Integer, default=1)
    family_notified = Column(Boolean, default=False)
    operator_notified = Column(Boolean, default=False)
    risk_level_increased = Column(Boolean, default=False)
    escalated = Column(Boolean, default=False)
    escalation_id = Column(Integer, ForeignKey("safety_escalations.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime)

    # Relationships
    trip = relationship("Trip", foreign_keys=[trip_id])
    fisherman = relationship("User", foreign_keys=[fisherman_id])
    schedule = relationship("CheckInSchedule", foreign_keys=[schedule_id])


class SafetyEscalation(Base):
    """Emergency escalation records with level-1-to-4 tracking."""
    __tablename__ = "safety_escalations"

    id = Column(Integer, primary_key=True)
    escalation_type = Column(String(50))  # missed_checkin, sos_unacknowledged, stale_gps_weather
    level = Column(Integer, default=1)  # 1-4
    fisherman_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"))
    sos_alert_id = Column(Integer, ForeignKey("sos_alerts.id", ondelete="CASCADE"))
    missed_checkin_id = Column(Integer, ForeignKey("missed_check_ins.id"))
    description = Column(Text)
    priority = Column(String(20), default="normal")  # normal, high, critical
    status = Column(String(20), default="active")  # active, acknowledged, resolved
    acknowledged_by_id = Column(Integer, ForeignKey("users.id"))
    acknowledged_at = Column(DateTime)
    resolved_by_id = Column(Integer, ForeignKey("users.id"))
    resolved_at = Column(DateTime)
    resolution = Column(Text)
    outcome = Column(String(50))  # resolved_safe, resolved_assisted, false_alarm
    family_notified = Column(Boolean, default=False)
    operator_notified = Column(Boolean, default=False)
    timeline_json = Column(Text, default="[]")  # JSON array of timeline events
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    fisherman = relationship("User", foreign_keys=[fisherman_id])
    trip = relationship("Trip", foreign_keys=[trip_id])
    sos_alert = relationship("SOSAlert", foreign_keys=[sos_alert_id])
    acknowledged_by = relationship("User", foreign_keys=[acknowledged_by_id])
    resolved_by = relationship("User", foreign_keys=[resolved_by_id])


class OperatorActionLog(Base):
    """Audit log of operator actions on escalations."""
    __tablename__ = "operator_action_logs"

    id = Column(Integer, primary_key=True)
    operator_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    action_type = Column(String(50))  # acknowledged, resolved, escalated, notified_family
    escalation_id = Column(Integer, ForeignKey("safety_escalations.id"))
    description = Column(Text)
    details_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    operator = relationship("User", foreign_keys=[operator_id])
    escalation = relationship("SafetyEscalation", foreign_keys=[escalation_id])


# =================================================================
# 4. HARBOR INTELLIGENCE TABLES
# =================================================================
class Harbor(Base):
    __tablename__ = "harbors"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    location_json = Column(Text, nullable=True)   # {lat, lng} — Phase 5 v2
    # Legacy Phase 2 columns kept for v1 API compatibility
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    region = Column(String(120), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    contact_phone = Column(String(20), nullable=True)  # v1 compat alias
    description = Column(Text, nullable=True)
    # Phase 5 columns
    state = Column(String(50), nullable=True)
    district = Column(String(50), nullable=True)
    country = Column(String(50), default="India")
    harbor_type = Column(String(50), nullable=True)  # "major", "minor", "emergency"
    available_services = Column(Text, default="[]")
    fuel_availability = Column(Boolean, default=False)
    ice_availability = Column(Boolean, default=False)
    medical_facility = Column(Boolean, default=False)
    repair_facility = Column(Boolean, default=False)
    emergency_shelter = Column(Boolean, default=False)
    contact_number = Column(String(20), nullable=True)
    operating_hours = Column(String(100), nullable=True)
    depth_meters = Column(Float, nullable=True)
    average_rating = Column(Float, default=0.0)
    total_reviews = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    reviews = relationship("HarborReview", cascade="all, delete-orphan")
    visits = relationship("HarborVisit", cascade="all, delete-orphan")


class HarborReview(Base):
    __tablename__ = "harbor_reviews"

    id = Column(Integer, primary_key=True)
    harbor_id = Column(Integer, ForeignKey("harbors.id", ondelete="CASCADE"), nullable=False)
    fisherman_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    rating = Column(Integer)  # 1-5
    review_text = Column(Text)
    service_quality = Column(Integer)
    facilities_quality = Column(Integer)
    staff_helpfulness = Column(Integer)
    visit_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    harbor = relationship("Harbor", foreign_keys=[harbor_id])
    fisherman = relationship("User", foreign_keys=[fisherman_id])


class HarborVisit(Base):
    __tablename__ = "harbor_visits"

    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"))
    harbor_id = Column(Integer, ForeignKey("harbors.id", ondelete="CASCADE"))
    fisherman_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    arrival_time = Column(DateTime)
    departure_time = Column(DateTime)
    services_used = Column(Text, default="[]")  # JSON array
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    trip = relationship("Trip", foreign_keys=[trip_id])
    harbor = relationship("Harbor", foreign_keys=[harbor_id])
    fisherman = relationship("User", foreign_keys=[fisherman_id])


# =================================================================
# 5. FUEL & BOAT HEALTH TABLES
# =================================================================
class BoatFuelLog(Base):
    __tablename__ = "boat_fuel_logs"

    id = Column(Integer, primary_key=True)
    boat_id = Column(Integer, ForeignKey("boats.id", ondelete="CASCADE"), nullable=False)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"))
    fuel_level_start_percent = Column(Float)
    fuel_level_end_percent = Column(Float)
    fuel_consumed_liters = Column(Float)
    distance_traveled_km = Column(Float)
    efficiency_km_per_liter = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    boat = relationship("Boat", foreign_keys=[boat_id])
    trip = relationship("Trip", foreign_keys=[trip_id])


class BoatMaintenance(Base):
    __tablename__ = "boat_maintenance"

    id = Column(Integer, primary_key=True)
    boat_id = Column(Integer, ForeignKey("boats.id", ondelete="CASCADE"), nullable=False)
    maintenance_type = Column(String(100))  # "oil_change", "filter_replacement", "engine_servicing"
    description = Column(Text)
    scheduled_date = Column(DateTime)
    completed_date = Column(DateTime)
    cost_rupees = Column(Float)
    technician_name = Column(String(120))
    service_center = Column(String(120))
    parts_replaced = Column(Text)  # JSON
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    boat = relationship("Boat", foreign_keys=[boat_id])


class BoatHealthStatus(Base):
    __tablename__ = "boat_health_status"

    id = Column(Integer, primary_key=True)
    boat_id = Column(Integer, ForeignKey("boats.id", ondelete="CASCADE"), nullable=False)
    engine_hours = Column(Float)
    last_service_date = Column(DateTime)
    next_service_date = Column(DateTime)
    total_maintenance_cost = Column(Float)
    health_score = Column(Float)  # 0-100
    issues_json = Column(Text, default="[]")  # Array of issues
    last_assessed_date = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    boat = relationship("Boat", foreign_keys=[boat_id])


class FuelPrediction(Base):
    __tablename__ = "fuel_predictions"

    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"))
    boat_id = Column(Integer, ForeignKey("boats.id", ondelete="CASCADE"))
    estimated_fuel_needed_liters = Column(Float)
    estimated_return_fuel_percent = Column(Float)
    distance_estimate_km = Column(Float)
    model_accuracy_percent = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    trip = relationship("Trip", foreign_keys=[trip_id])
    boat = relationship("Boat", foreign_keys=[boat_id])


# =================================================================
# 6. FAMILY PORTAL TABLES
# =================================================================
class FamilyPortalAccess(Base):
    __tablename__ = "family_portal_access"

    id = Column(Integer, primary_key=True)
    family_member_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    fisherman_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    access_level = Column(String(50))  # "view_only", "emergency_contact", "primary"
    can_view_live_location = Column(Boolean, default=True)
    can_view_trip_history = Column(Boolean, default=True)
    can_receive_alerts = Column(Boolean, default=True)
    can_contact_rescue = Column(Boolean, default=True)
    notification_preferences_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    family_member = relationship("User", foreign_keys=[family_member_id])
    fisherman = relationship("User", foreign_keys=[fisherman_id])


class FamilySafetyEvent(Base):
    __tablename__ = "family_safety_events"

    id = Column(Integer, primary_key=True)
    family_member_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    fisherman_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(50))  # "trip_started", "sos_alert", "trip_completed", "location_update"
    event_description = Column(Text)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"))
    sos_alert_id = Column(Integer, ForeignKey("sos_alerts.id", ondelete="CASCADE"))
    location_json = Column(Text)  # Last known location
    severity = Column(String(20))  # "info", "warning", "critical"
    read_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    family_member = relationship("User", foreign_keys=[family_member_id])
    fisherman = relationship("User", foreign_keys=[fisherman_id])
    trip = relationship("Trip", foreign_keys=[trip_id])
    sos_alert = relationship("SOSAlert", foreign_keys=[sos_alert_id])


class FamilyNotification(Base):
    __tablename__ = "family_notifications"

    id = Column(Integer, primary_key=True)
    family_member_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    notification_type = Column(String(50))  # "push", "sms", "email"
    message = Column(Text)
    related_event_id = Column(Integer)
    sent_at = Column(DateTime)
    read_at = Column(DateTime)
    delivery_status = Column(String(20))  # "pending", "sent", "failed"
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    family_member = relationship("User", foreign_keys=[family_member_id])


# =================================================================
# 7. ANALYTICS TABLES
# =================================================================
class AnalyticsSOSMetrics(Base):
    __tablename__ = "analytics_sos_metrics"

    id = Column(Integer, primary_key=True)
    period_date = Column(Date, nullable=False)  # YYYY-MM-DD
    period_type = Column(String(20))  # "daily", "weekly", "monthly"
    total_sos_alerts = Column(Integer, default=0)
    acknowledged_count = Column(Integer, default=0)
    resolved_count = Column(Integer, default=0)
    false_alarm_count = Column(Integer, default=0)
    average_response_time_minutes = Column(Float)
    by_region_json = Column(Text, default="{}")  # {region: count}
    by_hazard_type_json = Column(Text, default="{}")  # {hazard_type: count}
    created_at = Column(DateTime, default=datetime.utcnow)


class AnalyticsTripMetrics(Base):
    __tablename__ = "analytics_trip_metrics"

    id = Column(Integer, primary_key=True)
    period_date = Column(Date, nullable=False)
    period_type = Column(String(20))
    total_trips = Column(Integer, default=0)
    completed_trips = Column(Integer, default=0)
    trips_with_incidents = Column(Integer, default=0)
    average_trip_duration_hours = Column(Float)
    total_catch_value_rupees = Column(Float, default=0.0)
    by_harbor_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)


class AnalyticsRiskMetrics(Base):
    __tablename__ = "analytics_risk_metrics"

    id = Column(Integer, primary_key=True)
    period_date = Column(Date, nullable=False)
    period_type = Column(String(20))
    green_risk_trips = Column(Integer, default=0)
    yellow_risk_trips = Column(Integer, default=0)
    red_risk_trips = Column(Integer, default=0)
    critical_risk_trips = Column(Integer, default=0)
    average_risk_score = Column(Float)
    predictive_accuracy = Column(Float)
    by_weather_condition_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)


class AnalyticsUserEngagement(Base):
    __tablename__ = "analytics_user_engagement"

    id = Column(Integer, primary_key=True)
    period_date = Column(Date, nullable=False)
    active_fishermen = Column(Integer, default=0)
    active_operators = Column(Integer, default=0)
    active_family_members = Column(Integer, default=0)
    copilot_queries_total = Column(Integer, default=0)
    copilot_queries_by_intent_json = Column(Text, default="{}")
    dashboard_sessions = Column(Integer, default=0)
    mobile_app_sessions = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
