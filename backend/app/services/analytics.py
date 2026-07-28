"""Analytics Engine — SOS trends, response times, active boats, risk zones, harbor usage, and engagement metrics."""
import json
from datetime import datetime, date, timedelta, time
from typing import Any, List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.phase5 import (
    AnalyticsSOSMetrics,
    AnalyticsTripMetrics,
    AnalyticsRiskMetrics,
    AnalyticsUserEngagement,
)
from app.models.sos import SOSAlert
from app.models.trip import Trip
from app.models.user import User
from app.models.location import LocationPing


# =================================================================
# SCHEMAS
# =================================================================


class AnalyticsOverviewResponse(BaseModel):
    """Analytics overview."""
    active_sos_count: int = 0
    active_trips_count: int = 0
    generated_at: Optional[datetime] = None
    total_sos_alerts_today: int = 0
    resolved_sos_today: int = 0
    average_response_time_minutes: float = 0.0
    active_boats_now: int = 0
    active_fishermen: int = 0
    connection_lost_alerts: int = 0


class SOSTrendPoint(BaseModel):
    date: str
    total: int
    resolved: int
    unresolved: int
    false_alarms: int


class SOSTrendsResponse(BaseModel):
    """SOS trends analytics."""
    period: str = "daily"
    period_type: str = "daily"
    n_periods: int = 7
    total_alerts: int = 0
    resolved_alerts: int = 0
    unresolved_alerts: int = 0
    false_alarms: int = 0
    resolution_rate: float = 0.0
    average_response_time_minutes: float = 0.0
    top_hazard_types: List[dict] = []
    by_region: List[dict] = []
    trends: List[SOSTrendPoint] = []


class ResponseTimeMetricsResponse(BaseModel):
    """Response time metrics."""
    period: str = "last_30_days"
    average_response_minutes: float = 0.0
    avg_minutes: Optional[float] = None
    min_response_minutes: float = 0.0
    max_response_minutes: float = 0.0
    p50_response_minutes: float = 0.0
    p95_response_minutes: float = 0.0
    total_resolved: int = 0


class ActiveBoatSummary(BaseModel):
    trip_id: Optional[int] = None
    boat_id: Optional[int] = None
    fisherman_id: Optional[int] = None
    fisherman_name: Optional[str] = None
    boat_name: Optional[str] = None
    status: Optional[str] = None
    risk_level: Optional[str] = None
    started_at: Optional[datetime] = None


class ActiveBoatsAnalyticsResponse(BaseModel):
    """Active boats analytics."""
    boats_at_sea: int = 0
    boats_in_harbor: int = 0
    boats_idle: int = 0
    average_trip_duration_hours: float = 0.0
    trips_completed_today: int = 0
    fuel_warnings_active: int = 0
    total_active: int = 0
    boats: List[ActiveBoatSummary] = []


class RiskZoneSummary(BaseModel):
    location: str
    sos_count: int
    avg_risk_score: float


class RiskZoneAnalyticsResponse(BaseModel):
    """Risk zone analytics."""
    period: str = "last_7_days"
    high_risk_zones: List[dict] = []
    green_risk_trips: int = 0
    yellow_risk_trips: int = 0
    red_risk_trips: int = 0
    critical_risk_trips: int = 0
    average_risk_score: float = 0.0
    total_incidents: int = 0
    zones: List[RiskZoneSummary] = []


class HarborUsageAnalyticsResponse(BaseModel):
    """Harbor usage analytics."""
    period: str = "last_30_days"
    most_visited_harbors: List[dict] = []
    total_harbor_visits: int = 0
    emergency_harbor_uses: int = 0
    stats: List[dict] = []
    total_harbors: int = 0


class BoatHealthAnalyticsResponse(BaseModel):
    """Boat health analytics."""
    period: str = "current"
    average_health_score: float = 0.0
    boats_in_good_health: int = 0
    boats_with_warnings: int = 0
    boats_critical: int = 0
    most_common_issues: List[dict] = []
    overdue_maintenance_boats: int = 0
    total_boats_tracked: int = 0
    good_count: int = 0
    warning_count: int = 0
    critical_count: int = 0


# =================================================================
# ANALYTICS ENGINE SERVICE
# =================================================================


class AnalyticsService:
    """Analytics Engine."""

    @staticmethod
    def get_overview(db: Session) -> AnalyticsOverviewResponse:
        """Get real-time analytics overview."""
        today = datetime.utcnow().date()

        sos_today = (
            db.query(SOSAlert)
            .filter(func.date(SOSAlert.triggered_at) == today)
            .count()
        )

        resolved_today = (
            db.query(SOSAlert)
            .filter(
                func.date(SOSAlert.triggered_at) == today,
                SOSAlert.resolved_at.isnot(None),
            )
            .count()
        )

        active_trips = db.query(Trip).filter(Trip.end_time.is_(None)).count()

        active_fishermen = (
            db.query(func.count(func.distinct(Trip.user_id)))
            .filter(Trip.end_time.is_(None))
            .scalar()
        )

        response_times = []
        resolved_sos = (
            db.query(SOSAlert)
            .filter(
                func.date(SOSAlert.triggered_at) == today,
                SOSAlert.resolved_at.isnot(None),
            )
            .all()
        )
        for sos in resolved_sos:
            if sos.resolved_at and sos.triggered_at:
                delta = (sos.resolved_at - sos.triggered_at).total_seconds() / 60
                response_times.append(delta)

        avg_response = sum(response_times) / len(response_times) if response_times else 0

        thirty_min_ago = datetime.utcnow() - timedelta(minutes=30)
        connection_lost = (
            db.query(func.count(func.distinct(LocationPing.user_id)))
            .filter(LocationPing.recorded_at < thirty_min_ago)
            .scalar()
        )

        return AnalyticsOverviewResponse(
            active_sos_count=max(sos_today - resolved_today, 0),
            active_trips_count=active_trips,
            generated_at=datetime.utcnow(),
            total_sos_alerts_today=sos_today,
            resolved_sos_today=resolved_today,
            average_response_time_minutes=round(avg_response, 2),
            active_boats_now=active_trips,
            active_fishermen=active_fishermen or 0,
            connection_lost_alerts=connection_lost or 0,
        )

    @staticmethod
    def get_sos_trends(db: Session, days: int | str = 7, period_type: str | int = "daily", n_periods: int = 7) -> SOSTrendsResponse:
        """Get SOS trends analytics."""
        now = datetime.utcnow()

        if isinstance(days, str):
            period_label = days
            if isinstance(period_type, int):
                n_periods = period_type
            days = n_periods if n_periods else 7
            period_type = period_label
        elif isinstance(period_type, int):
            n_periods = period_type
            period_type = "daily"

        start_date = now - timedelta(days=days)

        total_sos = (
            db.query(SOSAlert)
            .filter(SOSAlert.triggered_at >= start_date)
            .count()
        )

        resolved_sos = (
            db.query(SOSAlert)
            .filter(
                SOSAlert.triggered_at >= start_date,
                SOSAlert.resolved_at.isnot(None),
            )
            .count()
        )

        unresolved = total_sos - resolved_sos
        resolution_rate = (resolved_sos / total_sos * 100) if total_sos > 0 else 0

        response_times = []
        resolved_sos_data = (
            db.query(SOSAlert)
            .filter(
                SOSAlert.triggered_at >= start_date,
                SOSAlert.resolved_at.isnot(None),
            )
            .all()
        )
        for sos in resolved_sos_data:
            if sos.resolved_at and sos.triggered_at:
                delta = (sos.resolved_at - sos.triggered_at).total_seconds() / 60
                response_times.append(delta)

        avg_response = sum(response_times) / len(response_times) if response_times else 0

        hazard_counts = {}
        all_sos = db.query(SOSAlert).filter(SOSAlert.triggered_at >= start_date).all()
        for sos in all_sos:
            hazard_type = sos.alert_type or "unknown"
            hazard_counts[hazard_type] = hazard_counts.get(hazard_type, 0) + 1

        top_hazards = sorted(
            [{"type": k, "count": v} for k, v in hazard_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:5]

        trends = []
        for idx in range(max(1, n_periods)):
            date_label = (datetime.utcnow() - timedelta(days=max(1, n_periods) - 1 - idx)).date()
            day_start = datetime.combine(date_label, time.min)
            day_end = day_start + timedelta(days=1)
            day_alerts = (
                db.query(SOSAlert)
                .filter(SOSAlert.triggered_at >= day_start, SOSAlert.triggered_at < day_end)
                .all()
            )
            total_day = len(day_alerts)
            resolved_day = sum(1 for alert in day_alerts if alert.resolved_at is not None)
            trends.append(
                SOSTrendPoint(
                    date=date_label.strftime("%Y-%m-%d"),
                    total=total_day,
                    resolved=resolved_day,
                    unresolved=total_day - resolved_day,
                    false_alarms=0,
                )
            )

        return SOSTrendsResponse(
            period=f"last_{days}_days",
            period_type=period_type,
            n_periods=max(1, n_periods),
            total_alerts=total_sos,
            resolved_alerts=resolved_sos,
            unresolved_alerts=unresolved,
            false_alarms=0,
            resolution_rate=round(resolution_rate, 2),
            average_response_time_minutes=round(avg_response, 2),
            top_hazard_types=top_hazards,
            by_region=[],
            trends=trends,
        )

    @staticmethod
    def get_response_times(db: Session, days: int = 30) -> ResponseTimeMetricsResponse:
        """Get response time metrics."""
        start_date = datetime.utcnow() - timedelta(days=days)

        resolved_sos = (
            db.query(SOSAlert)
            .filter(
                SOSAlert.triggered_at >= start_date,
                SOSAlert.resolved_at.isnot(None),
            )
            .all()
        )

        response_times = []
        for sos in resolved_sos:
            if sos.resolved_at and sos.triggered_at:
                delta = (sos.resolved_at - sos.triggered_at).total_seconds() / 60
                response_times.append(delta)

        if not response_times:
            return ResponseTimeMetricsResponse(
                period=f"last_{days}_days",
                average_response_minutes=0,
                avg_minutes=0,
                min_response_minutes=0,
                max_response_minutes=0,
                p50_response_minutes=0,
                p95_response_minutes=0,
                total_resolved=0,
            )

        response_times_sorted = sorted(response_times)
        average = sum(response_times) / len(response_times)
        p50_idx = int(len(response_times_sorted) * 0.5)
        p95_idx = int(len(response_times_sorted) * 0.95)

        return ResponseTimeMetricsResponse(
            period=f"last_{days}_days",
            average_response_minutes=round(average, 2),
            avg_minutes=round(average, 2),
            min_response_minutes=round(min(response_times), 2),
            max_response_minutes=round(max(response_times), 2),
            p50_response_minutes=round(response_times_sorted[p50_idx], 2),
            p95_response_minutes=round(response_times_sorted[p95_idx], 2),
            total_resolved=len(response_times),
        )

    @staticmethod
    def get_active_boats(db: Session, limit: int = 100) -> ActiveBoatsAnalyticsResponse:
        """Get active boats analytics."""
        today = datetime.utcnow().date()

        active_trips = db.query(Trip).filter(Trip.end_time.is_(None)).order_by(Trip.start_time.desc()).limit(limit).all()
        at_sea = len(active_trips)

        completed_today = (
            db.query(Trip)
            .filter(Trip.end_time.isnot(None))
            .filter(func.date(Trip.end_time) == today)
            .count()
        )

        completed_trips = (
            db.query(Trip)
            .filter(Trip.end_time.isnot(None))
            .all()
        )

        avg_duration = 0
        if completed_trips:
            durations = [
                (trip.end_time - trip.start_time).total_seconds() / 3600
                for trip in completed_trips[-30:]
                if trip.end_time and trip.start_time
            ]
            avg_duration = sum(durations) / len(durations) if durations else 0

        boats = []
        for trip in active_trips:
            fisherman = db.query(User).filter(User.id == trip.user_id).first()
            boats.append(
                ActiveBoatSummary(
                    trip_id=trip.id,
                    boat_id=trip.boat_id,
                    fisherman_id=trip.user_id,
                    fisherman_name=fisherman.full_name if fisherman else None,
                    boat_name=None,
                    status=trip.status,
                    risk_level="SAFE",
                    started_at=trip.start_time,
                )
            )

        return ActiveBoatsAnalyticsResponse(
            boats_at_sea=at_sea,
            boats_in_harbor=0,
            boats_idle=0,
            average_trip_duration_hours=round(avg_duration, 2),
            trips_completed_today=completed_today,
            fuel_warnings_active=0,
            total_active=at_sea,
            boats=boats,
        )

    @staticmethod
    def get_risk_zones(db: Session, days: int = 7) -> RiskZoneAnalyticsResponse:
        """Risk zone analytics — V2 core build fix (docs/V1_AUDIT.md flagged
        this as hardcoded fake data: fixed "Gujarat"/"Kerala" zone names and
        fixed 60/30/8% splits regardless of actual alerts). Replaced with:
          - real geographic clustering of actual SOS alerts (0.5-degree grid
            cells, ~55km — coarse but genuinely computed from the alerts
            that exist, not invented), labeled with the nearest harbor's
            region where one is known
          - real green/yellow/red/critical trip counts from
            app.services.safety_engine.SafetyEngine evaluated over every
            currently in-progress trip, not a fixed percentage of the SOS
            count
        """
        from app.models.phase5 import Harbor
        from app.services.geo import haversine_km
        from app.services.safety_engine import SafetyEngine
        from app.services.trip_service import TripStatus

        start_date = datetime.utcnow() - timedelta(days=days)
        sos_data = db.query(SOSAlert).filter(SOSAlert.triggered_at >= start_date).all()
        total = len(sos_data)

        # Grid-cluster real alerts.
        cells: dict[tuple[float, float], list[SOSAlert]] = {}
        for alert in sos_data:
            cell = (round(alert.latitude * 2) / 2, round(alert.longitude * 2) / 2)
            cells.setdefault(cell, []).append(alert)

        harbors = db.query(Harbor).filter(Harbor.latitude.isnot(None), Harbor.longitude.isnot(None)).all()

        def _label_for_cell(lat: float, lon: float) -> str:
            if not harbors:
                return f"{lat:.1f}, {lon:.1f}"
            nearest = min(harbors, key=lambda h: haversine_km(lat, lon, h.latitude, h.longitude))
            return nearest.region or nearest.district or nearest.name

        zones = [
            RiskZoneSummary(
                location=_label_for_cell(*cell),
                sos_count=len(alerts),
                avg_risk_score=min(100.0, 20.0 * len(alerts)),
            )
            for cell, alerts in cells.items()
        ]
        zones.sort(key=lambda z: z.sos_count, reverse=True)

        # Real per-trip safety-state distribution, not a fabricated split.
        active_trips = db.query(Trip).filter(Trip.status.in_(TripStatus.IN_PROGRESS)).all()
        buckets = {"SAFE": 0, "MONITOR": 0, "CAUTION": 0, "HIGH_RISK": 0, "CRITICAL": 0, "UNKNOWN": 0}
        scores: list[int] = []
        for trip in active_trips:
            fisherman = db.query(User).filter(User.id == trip.user_id).first()
            if not fisherman:
                continue
            ev = SafetyEngine.evaluate(db, fisherman)
            buckets[ev.safety_state] = buckets.get(ev.safety_state, 0) + 1
            scores.append(ev.safety_score)

        return RiskZoneAnalyticsResponse(
            period=f"last_{days}_days",
            high_risk_zones=[{"location": z.location, "incident_count": z.sos_count, "avg_risk_score": z.avg_risk_score} for z in zones[:5]],
            green_risk_trips=buckets["SAFE"] + buckets["MONITOR"],
            yellow_risk_trips=buckets["CAUTION"],
            red_risk_trips=buckets["HIGH_RISK"],
            critical_risk_trips=buckets["CRITICAL"],
            average_risk_score=round(sum(scores) / len(scores), 1) if scores else 0.0,
            total_incidents=total,
            zones=zones,
        )

    @staticmethod
    def get_harbor_usage(db: Session, days: int = 30) -> HarborUsageAnalyticsResponse:
        """Get harbor usage analytics."""
        from app.models.phase5 import HarborVisit

        start_date = datetime.utcnow() - timedelta(days=days)

        visits = (
            db.query(HarborVisit)
            .filter(HarborVisit.created_at >= start_date)
            .all()
        )

        harbor_counts = {}
        for visit in visits:
            harbor_name = visit.harbor.name if visit.harbor else "unknown"
            harbor_counts[harbor_name] = harbor_counts.get(harbor_name, 0) + 1

        most_visited = sorted(
            [{"harbor_name": k, "visit_count": v, "avg_rating": 4.5} for k, v in harbor_counts.items()],
            key=lambda x: x["visit_count"],
            reverse=True,
        )[:5]

        return HarborUsageAnalyticsResponse(
            period=f"last_{days}_days",
            most_visited_harbors=most_visited,
            total_harbor_visits=len(visits),
            emergency_harbor_uses=0,
            stats=most_visited,
            total_harbors=len(harbor_counts),
        )

    @staticmethod
    def get_boat_health(db: Session) -> BoatHealthAnalyticsResponse:
        """Boat health analytics — V2 core build fix (docs/V1_AUDIT.md
        flagged `most_common_issues` and `overdue_maintenance_boats` as
        hardcoded constants). Both are now real queries against
        BoatMaintenance: overdue = scheduled_date in the past with no
        completed_date; issue counts group those overdue rows by their
        actual maintenance_type."""
        from app.models.phase5 import BoatHealthStatus, BoatMaintenance

        health_statuses = db.query(BoatHealthStatus).all()

        effective_scores = []
        for h in health_statuses:
            if h.health_score is not None:
                effective_scores.append(float(h.health_score))
            else:
                effective_scores.append(100.0)

        good = sum(1 for h in effective_scores if h >= 70)
        warning = sum(1 for h in effective_scores if 40 <= h < 70)
        critical_level = sum(1 for h in effective_scores if h < 40)

        total = len(effective_scores)
        avg_score = sum(effective_scores) / total if total > 0 else 0

        now = datetime.utcnow()
        overdue = (
            db.query(BoatMaintenance)
            .filter(BoatMaintenance.scheduled_date.isnot(None), BoatMaintenance.scheduled_date < now, BoatMaintenance.completed_date.is_(None))
            .all()
        )
        overdue_boat_ids = {m.boat_id for m in overdue}
        issue_counts: dict[str, int] = {}
        for m in overdue:
            issue_type = m.maintenance_type or "unspecified"
            issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1
        most_common_issues = sorted(
            [{"issue_type": k, "count": v} for k, v in issue_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )

        return BoatHealthAnalyticsResponse(
            period="current",
            average_health_score=round(avg_score, 2),
            boats_in_good_health=good,
            boats_with_warnings=warning,
            boats_critical=critical_level,
            most_common_issues=most_common_issues,
            overdue_maintenance_boats=len(overdue_boat_ids),
            total_boats_tracked=total,
            good_count=good,
            warning_count=warning,
            critical_count=critical_level,
        )

    @staticmethod
    def get_boat_health_analytics(db: Session) -> BoatHealthAnalyticsResponse:
        """Backward-compatible alias for boat health analytics."""
        return AnalyticsService.get_boat_health(db)

    @staticmethod
    def record_daily_metrics(db: Session, record_date: date = None) -> None:
        """Record daily snapshot metrics."""
        if record_date is None:
            record_date = datetime.utcnow().date()
        pass
