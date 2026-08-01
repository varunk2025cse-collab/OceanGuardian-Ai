from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.boat import Boat
from app.models.trip import Trip
from app.models.sos import SOSAlert
from app.models.phase5 import Harbor
from app.core.deps import get_current_user, get_current_operator
from app.core.rate_limit import rate_limit

from app.schemas.intelligence import (
    BoatHealthReport, DecisionSupport, HarborReport, 
    MaintenanceReport, SOSReport, TripRiskReport, WeatherRiskReport
)
from app.services.intelligence.boat_intelligence import BoatIntelligenceService
from app.services.intelligence.equipment_intelligence import EquipmentIntelligenceService
from app.services.intelligence.maintenance_intelligence import MaintenanceIntelligenceService
from app.services.intelligence.trip_intelligence import TripIntelligenceService
from app.services.intelligence.weather_intelligence import WeatherIntelligenceService
from app.services.intelligence.harbor_intelligence import HarborIntelligenceService
from app.services.intelligence.sos_intelligence import SOSIntelligenceService

router = APIRouter(prefix="/api/v2/intelligence", tags=["intelligence"])

@router.get("/boat/{boat_id}/health", response_model=BoatHealthReport, dependencies=[Depends(rate_limit("intel_boat", limit=10))])
def get_boat_health_intelligence(boat_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Full health report for a boat, including engine, documents, and equipment."""
    boat = db.query(Boat).filter(Boat.id == boat_id).first()
    if not boat:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Boat not found")
    # In a real app we'd verify current_user can view this boat
    return BoatIntelligenceService.evaluate(db, boat)

@router.get("/boat/{boat_id}/equipment", response_model=DecisionSupport, dependencies=[Depends(rate_limit("intel_equip", limit=10))])
def get_equipment_intelligence(boat_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Evaluate equipment readiness, missing mandatory items, and expirations."""
    boat = db.query(Boat).filter(Boat.id == boat_id).first()
    if not boat:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Boat not found")
    return EquipmentIntelligenceService.evaluate(db, boat)

@router.get("/boat/{boat_id}/maintenance", response_model=MaintenanceReport, dependencies=[Depends(rate_limit("intel_maint", limit=10))])
def get_maintenance_intelligence(boat_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Evaluate predictive maintenance, RUL, and overdue services."""
    boat = db.query(Boat).filter(Boat.id == boat_id).first()
    if not boat:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Boat not found")
    return MaintenanceIntelligenceService.evaluate(db, boat)

@router.get("/trip/{trip_id}/risk", response_model=TripRiskReport, dependencies=[Depends(rate_limit("intel_trip", limit=10))])
def get_trip_risk_intelligence(trip_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Evaluate trip risk, delays, and fuel predictions."""
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Trip not found")
    return TripIntelligenceService.evaluate(db, trip)

@router.get("/weather", response_model=WeatherRiskReport, dependencies=[Depends(rate_limit("intel_weather", limit=20))])
def get_weather_intelligence(lat: float, lon: float, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Evaluate weather risks: wind, waves, visibility, storms."""
    return WeatherIntelligenceService.evaluate(lat, lon)

@router.get("/harbor/{harbor_id}/capacity", response_model=HarborReport, dependencies=[Depends(rate_limit("intel_harbor", limit=10))])
def get_harbor_intelligence(harbor_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Evaluate harbor capacity and traffic."""
    harbor = db.query(Harbor).filter(Harbor.id == harbor_id).first()
    if not harbor:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Harbor not found")
    return HarborIntelligenceService.evaluate(db, harbor)

@router.get("/sos/{alert_id}", response_model=SOSReport, dependencies=[Depends(rate_limit("intel_sos", limit=10))])
def get_sos_intelligence(alert_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_operator)):
    """Evaluate SOS incident severity and recommend resources."""
    alert = db.query(SOSAlert).filter(SOSAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="SOS not found")
    return SOSIntelligenceService.evaluate(db, alert)
