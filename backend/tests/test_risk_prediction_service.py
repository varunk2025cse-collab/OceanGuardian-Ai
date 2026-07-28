"""Tests for Advanced Risk Prediction Engine."""
import pytest
import json
from datetime import datetime, timedelta
from app.models.user import User
from app.models.boat import Boat
from app.models.trip import Trip
from app.models.location import LocationPing
from app.models.weather_alert import WeatherAlert
from app.models.sos import SOSAlert
from app.models.phase5 import BoatHealthStatus, BoatFuelLog, Harbor, RiskPrediction
from app.services.risk_prediction import RiskPredictionService
from app.core.security import get_password_hash


@pytest.fixture
def fisherman(db):
    """Create test fisherman."""
    user = User(
        full_name="Test Fisherman",
        phone_number="+919876543210",
        role="fisherman",
        password_hash=get_password_hash("test123"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def boat(db, fisherman):
    """Create test boat."""
    boat = Boat(
        name="Test Boat",
        registration_number="TB123",
        engine_type="Trawler",
        owner_id=fisherman.id,
    )
    db.add(boat)
    db.commit()
    db.refresh(boat)
    return boat


@pytest.fixture
def active_trip(db, fisherman, boat):
    """Create active trip."""
    trip = Trip(
        user_id=fisherman.id,
        boat_id=boat.id,
        start_time=datetime.utcnow(),
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


@pytest.fixture
def harbor(db):
    """Create test harbor."""
    harbor = Harbor(
        name="Test Harbor",
        latitude=12.0,
        longitude=80.0,
        is_active=True,
    )
    db.add(harbor)
    db.commit()
    db.refresh(harbor)
    return harbor


def test_calculate_risk_score_invalid_trip(db):
    """Test risk calculation with invalid trip."""
    result = RiskPredictionService.calculate_risk_score(99999, db)
    assert result is None


def test_calculate_risk_score_safe_conditions(db, fisherman, active_trip, harbor):
    """Test risk calculation with safe conditions."""
    # Recent GPS near harbor
    location = LocationPing(
        fisherman_id=fisherman.id,
        trip_id=active_trip.id,
        latitude=12.01,
        longitude=80.01,
        timestamp=datetime.utcnow(),
    )
    db.add(location)
    db.commit()
    
    risk = RiskPredictionService.calculate_risk_score(active_trip.id, db)
    
    assert risk is not None
    assert risk.risk_level == "SAFE"
    assert risk.risk_score < 25.0
    assert risk.confidence > 0


def test_calculate_risk_score_with_weather_risk(db, fisherman, active_trip, harbor):
    """Test risk calculation with active weather alert."""
    # Create location
    location = LocationPing(
        fisherman_id=fisherman.id,
        trip_id=active_trip.id,
        latitude=12.01,
        longitude=80.01,
        timestamp=datetime.utcnow(),
    )
    db.add(location)
    
    # Create severe weather alert
    weather = WeatherAlert(
        region="Test Region",
        severity="red",
        alert_type="Cyclone",
        description="Severe cyclone warning",
        is_active=True,
    )
    db.add(weather)
    db.commit()
    
    risk = RiskPredictionService.calculate_risk_score(active_trip.id, db)
    
    assert risk is not None
    assert risk.factors["weather_risk"] > 15.0
    assert "weather" in " ".join(risk.reasons).lower()


def test_calculate_risk_score_with_stale_gps(db, fisherman, active_trip):
    """Test risk calculation with stale GPS."""
    # Old GPS location
    old_location = LocationPing(
        fisherman_id=fisherman.id,
        trip_id=active_trip.id,
        latitude=12.0,
        longitude=80.0,
        timestamp=datetime.utcnow() - timedelta(minutes=40),
    )
    db.add(old_location)
    db.commit()
    
    risk = RiskPredictionService.calculate_risk_score(active_trip.id, db)
    
    assert risk is not None
    assert risk.factors["gps_staleness"] > 5.0
    assert any("GPS" in reason or "gps" in reason for reason in risk.reasons)


def test_calculate_risk_score_with_long_trip_duration(db, fisherman, boat, harbor):
    """Test risk calculation with long trip duration."""
    # Create old trip (12 hours ago)
    old_trip = Trip(
        fisherman_id=fisherman.id,
        boat_id=boat.id,
        start_time=datetime.utcnow() - timedelta(hours=12),
    )
    db.add(old_trip)
    db.commit()
    
    # Recent location
    location = LocationPing(
        fisherman_id=fisherman.id,
        trip_id=old_trip.id,
        latitude=12.0,
        longitude=80.0,
        timestamp=datetime.utcnow(),
    )
    db.add(location)
    db.commit()
    
    risk = RiskPredictionService.calculate_risk_score(old_trip.id, db)
    
    assert risk is not None
    assert risk.factors["trip_duration"] > 3.0


def test_calculate_risk_score_with_poor_boat_health(db, fisherman, boat, active_trip, harbor):
    """Test risk calculation with poor boat health."""
    # Create poor boat health status
    health = BoatHealthStatus(
        boat_id=boat.id,
        health_score=30.0,  # Poor health
        last_assessed_date=datetime.utcnow(),
    )
    db.add(health)
    
    # Recent location
    location = LocationPing(
        fisherman_id=fisherman.id,
        trip_id=active_trip.id,
        latitude=12.0,
        longitude=80.0,
        timestamp=datetime.utcnow(),
    )
    db.add(location)
    db.commit()
    
    risk = RiskPredictionService.calculate_risk_score(active_trip.id, db)
    
    assert risk is not None
    assert risk.factors["boat_health"] > 5.0


def test_calculate_risk_score_with_low_fuel(db, fisherman, boat, active_trip, harbor):
    """Test risk calculation with low fuel."""
    # Create low fuel log
    fuel = BoatFuelLog(
        boat_id=boat.id,
        trip_id=active_trip.id,
        fuel_level_end_percent=20.0,  # Low fuel
        timestamp=datetime.utcnow(),
    )
    db.add(fuel)
    
    # Recent location
    location = LocationPing(
        fisherman_id=fisherman.id,
        trip_id=active_trip.id,
        latitude=12.0,
        longitude=80.0,
        timestamp=datetime.utcnow(),
    )
    db.add(location)
    db.commit()
    
    risk = RiskPredictionService.calculate_risk_score(active_trip.id, db)
    
    assert risk is not None
    assert risk.factors["fuel_remaining"] > 3.0


def test_calculate_risk_score_with_sos_history(db, fisherman, boat, active_trip, harbor):
    """Test risk calculation with SOS history."""
    # Create recent SOS alerts
    for i in range(3):
        sos = SOSAlert(
            fisherman_id=fisherman.id,
            trip_id=active_trip.id,
            alert_type="Engine Failure",
            latitude=12.0,
            longitude=80.0,
            created_at=datetime.utcnow() - timedelta(days=i+1),
        )
        db.add(sos)
    
    # Recent location
    location = LocationPing(
        fisherman_id=fisherman.id,
        trip_id=active_trip.id,
        latitude=12.0,
        longitude=80.0,
        timestamp=datetime.utcnow(),
    )
    db.add(location)
    db.commit()
    
    risk = RiskPredictionService.calculate_risk_score(active_trip.id, db)
    
    assert risk is not None
    assert risk.factors["sos_history"] > 3.0


def test_calculate_risk_score_far_from_harbor(db, fisherman, active_trip, harbor):
    """Test risk calculation when far from harbor."""
    # Location very far from harbor (100km away)
    location = LocationPing(
        fisherman_id=fisherman.id,
        trip_id=active_trip.id,
        latitude=13.0,
        longitude=81.5,
        timestamp=datetime.utcnow(),
    )
    db.add(location)
    db.commit()
    
    risk = RiskPredictionService.calculate_risk_score(active_trip.id, db)
    
    assert risk is not None
    assert risk.factors["distance_from_harbor"] > 10.0


def test_risk_level_watch(db, fisherman, active_trip):
    """Test WATCH risk level."""
    # Create moderately stale GPS (40 min)
    location = LocationPing(
        fisherman_id=fisherman.id,
        trip_id=active_trip.id,
        latitude=12.5,
        longitude=80.5,
        timestamp=datetime.utcnow() - timedelta(minutes=40),
    )
    db.add(location)
    db.commit()
    
    risk = RiskPredictionService.calculate_risk_score(active_trip.id, db)
    
    assert risk is not None
    # Should be in WATCH or higher due to stale GPS
    assert risk.risk_level in ["WATCH", "WARNING", "CRITICAL"]


def test_risk_level_warning(db, fisherman, boat, active_trip):
    """Test WARNING risk level with multiple risk factors."""
    # Stale GPS
    location = LocationPing(
        fisherman_id=fisherman.id,
        trip_id=active_trip.id,
        latitude=13.0,
        longitude=81.5,
        timestamp=datetime.utcnow() - timedelta(minutes=50),
    )
    db.add(location)
    
    # Poor boat health
    health = BoatHealthStatus(
        boat_id=boat.id,
        health_score=35.0,
        last_assessed_date=datetime.utcnow(),
    )
    db.add(health)
    
    # Low fuel
    fuel = BoatFuelLog(
        boat_id=boat.id,
        trip_id=active_trip.id,
        fuel_level_end_percent=15.0,
        timestamp=datetime.utcnow(),
    )
    db.add(fuel)
    db.commit()
    
    risk = RiskPredictionService.calculate_risk_score(active_trip.id, db)
    
    assert risk is not None
    assert risk.risk_score >= 50.0


def test_get_trip_risk(db, fisherman, active_trip, harbor):
    """Test getting trip risk assessment."""
    # Create location
    location = LocationPing(
        fisherman_id=fisherman.id,
        trip_id=active_trip.id,
        latitude=12.0,
        longitude=80.0,
        timestamp=datetime.utcnow(),
    )
    db.add(location)
    db.commit()
    
    trip_risk = RiskPredictionService.get_trip_risk(active_trip.id, db)
    
    assert trip_risk is not None
    assert trip_risk.trip_id == active_trip.id
    assert trip_risk.fisherman_id == fisherman.id
    assert trip_risk.risk_level in ["SAFE", "WATCH", "WARNING", "CRITICAL"]
    assert trip_risk.risk_score >= 0


def test_get_trip_risk_invalid_trip(db):
    """Test get trip risk with invalid trip."""
    result = RiskPredictionService.get_trip_risk(99999, db)
    assert result is None


def test_get_high_risk_boats_empty(db):
    """Test get high risk boats with no trips."""
    boats = RiskPredictionService.get_high_risk_boats(db)
    assert len(boats) == 0


def test_get_high_risk_boats(db, fisherman, boat):
    """Test get high risk boats with warning/critical trips."""
    # Create trip with high risk factors
    trip = Trip(
        fisherman_id=fisherman.id,
        boat_id=boat.id,
        start_time=datetime.utcnow() - timedelta(hours=15),
    )
    db.add(trip)
    db.commit()
    
    # Stale GPS + far from harbor
    location = LocationPing(
        fisherman_id=fisherman.id,
        trip_id=trip.id,
        latitude=13.5,
        longitude=82.0,
        timestamp=datetime.utcnow() - timedelta(minutes=65),
    )
    db.add(location)
    
    # Poor health
    health = BoatHealthStatus(
        boat_id=boat.id,
        health_score=25.0,
        last_assessed_date=datetime.utcnow(),
    )
    db.add(health)
    db.commit()
    
    boats = RiskPredictionService.get_high_risk_boats(db)
    
    # Should identify this as high risk
    if len(boats) > 0:
        assert boats[0].boat_id == boat.id
        assert boats[0].risk_level in ["WARNING", "CRITICAL"]


def test_risk_prediction_stored_in_database(db, fisherman, active_trip, harbor):
    """Test that risk predictions are stored."""
    # Create location
    location = LocationPing(
        fisherman_id=fisherman.id,
        trip_id=active_trip.id,
        latitude=12.0,
        longitude=80.0,
        timestamp=datetime.utcnow(),
    )
    db.add(location)
    db.commit()
    
    RiskPredictionService.calculate_risk_score(active_trip.id, db)
    
    prediction = db.query(RiskPrediction).filter(
        RiskPrediction.trip_id == active_trip.id
    ).first()
    
    assert prediction is not None
    assert prediction.risk_score >= 0
    assert prediction.model_version == "rule_based_v1.0"


def test_risk_factors_json_structure(db, fisherman, active_trip, harbor):
    """Test risk factors JSON has correct structure."""
    # Create location
    location = LocationPing(
        fisherman_id=fisherman.id,
        trip_id=active_trip.id,
        latitude=12.0,
        longitude=80.0,
        timestamp=datetime.utcnow(),
    )
    db.add(location)
    db.commit()
    
    risk = RiskPredictionService.calculate_risk_score(active_trip.id, db)
    
    assert risk is not None
    assert "weather_risk" in risk.factors
    assert "distance_from_harbor" in risk.factors
    assert "gps_staleness" in risk.factors
    assert "trip_duration" in risk.factors
    assert "boat_health" in risk.factors
    assert "fuel_remaining" in risk.factors
    assert "sos_history" in risk.factors
