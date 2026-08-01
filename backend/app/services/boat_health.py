"""Fuel & Boat Health Service — maintenance tracking, fuel management, and boat health scoring."""
import json
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.models.phase5 import (
    BoatFuelLog,
    BoatMaintenance,
    BoatHealthStatus,
    FuelPrediction,
)
from app.models.boat import Boat


# =================================================================
# SCHEMAS
# =================================================================


class FuelLogCreate(BaseModel):
    """Create fuel log entry."""
    boat_id: int
    trip_id: Optional[int] = None
    fuel_level_start_percent: float = Field(..., ge=0, le=100)
    fuel_level_end_percent: float = Field(..., ge=0, le=100)
    fuel_consumed_liters: Optional[float] = None
    distance_traveled_km: Optional[float] = None


class FuelLogResponse(BaseModel):
    """Fuel log response."""
    id: int
    boat_id: int
    trip_id: Optional[int]
    fuel_level_start_percent: float
    fuel_level_end_percent: float
    fuel_consumed_liters: Optional[float]
    distance_traveled_km: Optional[float]
    efficiency_km_per_liter: Optional[float]
    timestamp: datetime

    class Config:
        from_attributes = True


class MaintenanceCreate(BaseModel):
    """Create maintenance record."""
    boat_id: int
    maintenance_type: str  # "oil_change", "filter_replacement", "engine_servicing"
    description: str
    scheduled_date: datetime
    cost_rupees: Optional[float] = None
    technician_name: Optional[str] = None
    service_center: Optional[str] = None


class MaintenanceResponse(BaseModel):
    """Maintenance record response."""
    id: int
    boat_id: int
    maintenance_type: str
    description: str
    scheduled_date: datetime
    completed_date: Optional[datetime]
    cost_rupees: Optional[float]
    technician_name: Optional[str]
    service_center: Optional[str]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class FuelSummaryResponse(BaseModel):
    """Fuel summary for boat."""
    boat_id: int
    current_fuel_percent: Optional[float]
    average_consumption_km_per_liter: Optional[float]
    estimated_range_km: Optional[float]
    low_fuel_warning: bool
    last_fuel_log_date: Optional[datetime]
    total_fuel_logs: int


class HealthScoreResponse(BaseModel):
    """Boat health score response."""
    boat_id: int
    health_score: float = Field(..., ge=0, le=100)
    status: str  # "Good", "Warning", "Critical"
    engine_hours: Optional[float]
    last_service_date: Optional[datetime]
    next_service_date: Optional[datetime]
    days_until_service: Optional[int]
    maintenance_due: List[str]
    issues: List[str]
    risk_level: str  # "Low", "Medium", "High"


class MaintenanceDueResponse(BaseModel):
    """Maintenance due response."""
    boat_id: int
    overdue_maintenance: List[MaintenanceResponse]
    upcoming_maintenance: List[MaintenanceResponse]
    critical_issues: List[str]


# =================================================================
# BOAT HEALTH SERVICE
# =================================================================


class BoatHealthService:
    """Fuel & Boat Health Service."""

    @staticmethod
    def create_fuel_log(db: Session, fuel_data: FuelLogCreate) -> BoatFuelLog:
        """Create fuel log entry."""
        fuel_consumed = None
        efficiency = None

        if fuel_data.fuel_consumed_liters and fuel_data.distance_traveled_km:
            if fuel_data.fuel_consumed_liters > 0:
                efficiency = fuel_data.distance_traveled_km / fuel_data.fuel_consumed_liters
        elif fuel_data.fuel_level_start_percent is not None and fuel_data.fuel_level_end_percent is not None:
            delta = max(0.0, fuel_data.fuel_level_start_percent - fuel_data.fuel_level_end_percent)
            efficiency = max(0.0, delta / 10.0)

        fuel_log = BoatFuelLog(
            boat_id=fuel_data.boat_id,
            trip_id=fuel_data.trip_id,
            fuel_level_start_percent=fuel_data.fuel_level_start_percent,
            fuel_level_end_percent=fuel_data.fuel_level_end_percent,
            fuel_consumed_liters=fuel_data.fuel_consumed_liters,
            distance_traveled_km=fuel_data.distance_traveled_km,
            efficiency_km_per_liter=efficiency,
            timestamp=datetime.utcnow(),
        )
        db.add(fuel_log)
        db.commit()
        db.refresh(fuel_log)
        return fuel_log

    @staticmethod
    def get_fuel_summary(db: Session, boat_id: int) -> FuelSummaryResponse:
        """Get fuel summary for boat."""
        fuel_logs = (
            db.query(BoatFuelLog)
            .filter(BoatFuelLog.boat_id == boat_id)
            .order_by(BoatFuelLog.timestamp.desc(), BoatFuelLog.id.desc())
            .limit(20)
            .all()
        )

        current_fuel_percent = None
        if fuel_logs:
            current_fuel_percent = fuel_logs[0].fuel_level_end_percent

        average_efficiency = None
        if fuel_logs:
            valid_logs = [l for l in fuel_logs if l.efficiency_km_per_liter]
            if valid_logs:
                average_efficiency = sum(l.efficiency_km_per_liter for l in valid_logs) / len(
                    valid_logs
                )

        estimated_range = None
        if current_fuel_percent is not None and average_efficiency:
            boat = db.query(Boat).filter(Boat.id == boat_id).first()
            if boat and boat.fuel_capacity_liters:
                current_fuel_liters = (current_fuel_percent / 100) * boat.fuel_capacity_liters
                estimated_range = current_fuel_liters * average_efficiency

        low_fuel_warning = current_fuel_percent is not None and current_fuel_percent < 20

        last_fuel_log_date = fuel_logs[0].timestamp if fuel_logs else None
        total_logs = len(fuel_logs)

        return FuelSummaryResponse(
            boat_id=boat_id,
            current_fuel_percent=current_fuel_percent,
            average_consumption_km_per_liter=average_efficiency,
            estimated_range_km=estimated_range,
            low_fuel_warning=low_fuel_warning,
            last_fuel_log_date=last_fuel_log_date,
            total_fuel_logs=total_logs,
        )

    @staticmethod
    def create_maintenance_record(
        db: Session, maintenance_data: MaintenanceCreate
    ) -> BoatMaintenance:
        """Create maintenance record."""
        maintenance = BoatMaintenance(
            boat_id=maintenance_data.boat_id,
            maintenance_type=maintenance_data.maintenance_type,
            description=maintenance_data.description,
            scheduled_date=maintenance_data.scheduled_date,
            cost_rupees=maintenance_data.cost_rupees,
            technician_name=maintenance_data.technician_name,
            service_center=maintenance_data.service_center,
            created_at=datetime.utcnow(),
        )
        db.add(maintenance)
        db.commit()
        db.refresh(maintenance)
        return maintenance

    @staticmethod
    def get_maintenance_due(db: Session, boat_id: int) -> MaintenanceDueResponse:
        """Get overdue and upcoming maintenance."""
        now = datetime.utcnow()
        maintenance_records = (
            db.query(BoatMaintenance)
            .filter(BoatMaintenance.boat_id == boat_id)
            .filter(BoatMaintenance.completed_date.is_(None))
            .all()
        )

        overdue = []
        upcoming = []
        critical_issues = []

        for rec in maintenance_records:
            if rec.scheduled_date < now:
                overdue.append(rec)
                if rec.maintenance_type in ["engine_servicing", "safety_check"]:
                    critical_issues.append(f"{rec.maintenance_type} is {(now - rec.scheduled_date).days} days overdue")
            else:
                days_until = (rec.scheduled_date - now).days
                if days_until <= 7:
                    critical_issues.append(f"{rec.maintenance_type} due in {days_until} days")
                upcoming.append(rec)

        return MaintenanceDueResponse(
            boat_id=boat_id,
            overdue_maintenance=overdue,
            upcoming_maintenance=sorted(upcoming, key=lambda x: x.scheduled_date)[:10],
            critical_issues=critical_issues,
        )

    @staticmethod
    def calculate_health_score(db: Session, boat_id: int) -> HealthScoreResponse:
        """Calculate boat health score (0-100)."""
        boat = db.query(Boat).filter(Boat.id == boat_id).first()
        if not boat:
            raise ValueError(f"Boat {boat_id} not found")

        health_status = (
            db.query(BoatHealthStatus).filter(BoatHealthStatus.boat_id == boat_id).first()
        )

        score = 100.0
        issues = []
        maintenance_due = []

        # Fuel factor (20%)
        fuel_summary = BoatHealthService.get_fuel_summary(db, boat_id)
        if fuel_summary.current_fuel_percent is not None and fuel_summary.current_fuel_percent <= 12:
            score -= 35
            issues.append("Critical fuel level")
        elif fuel_summary.low_fuel_warning:
            score -= 15
            issues.append("Low fuel level")
        if fuel_summary.current_fuel_percent is None:
            score -= 10
            issues.append("No fuel data available")

        # Maintenance factor (40%)
        maintenance = BoatHealthService.get_maintenance_due(db, boat_id)
        if maintenance.overdue_maintenance:
            overdue_count = len(maintenance.overdue_maintenance)
            score -= 25 * min(overdue_count, 3)
            maintenance_due.extend([m.maintenance_type for m in maintenance.overdue_maintenance])
            issues.extend(maintenance.critical_issues)
        elif maintenance.upcoming_maintenance:
            score -= 10
            maintenance_due.extend([m.maintenance_type for m in maintenance.upcoming_maintenance[:3]])

        # Engine hours factor (20%)
        if health_status and health_status.engine_hours:
            if health_status.engine_hours > 5000:
                score -= 20
                issues.append("High engine hours")
            elif health_status.engine_hours > 3000:
                score -= 10

        # Last service factor (20%)
        if health_status and health_status.last_service_date:
            days_since_service = (datetime.utcnow() - health_status.last_service_date).days
            if days_since_service > 365:
                score -= 15
                issues.append("Over 1 year since last service")
            elif days_since_service > 180:
                score -= 5

        score = max(0, min(100, score))

        status = "Good" if score >= 70 else "Warning" if score >= 40 else "Critical"
        risk_level = "Low" if score >= 70 else "Medium" if score >= 40 else "High"

        days_until_service = None
        next_service_date = health_status.next_service_date if health_status else None
        if next_service_date:
            days_until_service = (next_service_date - datetime.utcnow()).days

        return HealthScoreResponse(
            boat_id=boat_id,
            health_score=score,
            status=status,
            engine_hours=health_status.engine_hours if health_status else None,
            last_service_date=health_status.last_service_date if health_status else None,
            next_service_date=next_service_date,
            days_until_service=days_until_service,
            maintenance_due=list(set(maintenance_due)),
            issues=issues,
            risk_level=risk_level,
        )

    @staticmethod
    def update_health_status(db: Session, boat_id: int, engine_hours: Optional[float] = None) -> BoatHealthStatus:
        """Update boat health status."""
        health_status = (
            db.query(BoatHealthStatus).filter(BoatHealthStatus.boat_id == boat_id).first()
        )

        if not health_status:
            health_status = BoatHealthStatus(boat_id=boat_id)
            db.add(health_status)

        if engine_hours is not None:
            health_status.engine_hours = engine_hours

        health_status.last_assessed_date = datetime.utcnow()
        db.commit()
        db.refresh(health_status)
        return health_status

    @staticmethod
    def create_fuel_prediction(
        db: Session, trip_id: int, boat_id: int, estimated_fuel_needed: float
    ) -> FuelPrediction:
        """Create fuel prediction for trip."""
        prediction = FuelPrediction(
            trip_id=trip_id,
            boat_id=boat_id,
            estimated_fuel_needed_liters=estimated_fuel_needed,
            model_accuracy_percent=85.0,
            created_at=datetime.utcnow(),
        )
        db.add(prediction)
        db.commit()
        db.refresh(prediction)
        return prediction
