"""
Harbor Intelligence Service Tests.

Tests for Harbor service including:
- Harbor CRUD operations
- Nearest harbor finder
- Emergency harbor retrieval
- Distance calculations
- Harbor reviews
- Harbor visits
"""
import json
import pytest
from sqlalchemy.orm import Session
from app.models.phase5 import Harbor, HarborReview, HarborVisit
from app.models.user import User
from app.services.harbor import (
    HarborService,
    HarborCreate,
    HarborReviewCreate,
    calculate_distance_km,
    estimate_minutes_to_reach,
    HarborLocation,
)


# =================================================================
# FIXTURES
# =================================================================


@pytest.fixture
def fisherman(db: Session) -> User:
    """Create a test fisherman."""
    user = User(
        phone_number="9876543210",
        password_hash="hashed_password",
        full_name="Test Fisherman",
        role="fisherman",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def harbor_data() -> HarborCreate:
    """Sample harbor creation data."""
    return HarborCreate(
        name="Trivandrum Harbor",
        latitude=8.5241,
        longitude=76.9366,
        state="Kerala",
        district="Thiruvananthapuram",
        harbor_type="major",
        contact_number="+91-471-2333456",
        operating_hours="0500-2200",
        depth_meters=8.5,
        fuel_availability=True,
        ice_availability=True,
        medical_facility=True,
        repair_facility=True,
        emergency_shelter=True,
    )


@pytest.fixture
def harbor_data_minor() -> HarborCreate:
    """Sample minor harbor creation data (for testing filters)."""
    return HarborCreate(
        name="Kochi Minor Harbor",
        latitude=9.9312,
        longitude=76.2673,
        state="Kerala",
        district="Kochi",
        harbor_type="minor",
        fuel_availability=False,
        ice_availability=False,
        medical_facility=False,
        repair_facility=False,
        emergency_shelter=False,
    )


# =================================================================
# DISTANCE CALCULATION TESTS
# =================================================================


def test_calculate_distance_km():
    """Test distance calculation using Haversine formula."""
    # Test distance from Trivandrum to Kochi (approx 265 km)
    distance = calculate_distance_km(
        lat1=8.5241, lon1=76.9366,  # Trivandrum
        lat2=9.9312, lon2=76.2673,  # Kochi
    )
    assert 260 < distance < 270


def test_calculate_distance_zero():
    """Test distance calculation when coordinates are the same."""
    distance = calculate_distance_km(
        lat1=8.5241, lon1=76.9366,
        lat2=8.5241, lon2=76.9366,
    )
    assert abs(distance) < 0.01


def test_estimate_minutes_to_reach():
    """Test ETA estimation."""
    # At 15 km/h, 30 km should take 120 minutes
    minutes = estimate_minutes_to_reach(distance_km=30, boat_speed_kmh=15)
    assert minutes == 120

    # At 15 km/h, 5 km should take 20 minutes
    minutes = estimate_minutes_to_reach(distance_km=5, boat_speed_kmh=15)
    assert minutes == 20

    # Should never be less than 1 minute
    minutes = estimate_minutes_to_reach(distance_km=0.5, boat_speed_kmh=15)
    assert minutes >= 1


# =================================================================
# LOCATION SCHEMA TESTS
# =================================================================


def test_harbor_location_to_json():
    """Test HarborLocation serialization."""
    location = HarborLocation(latitude=8.5241, longitude=76.9366)
    json_str = location.to_json()
    data = json.loads(json_str)
    assert data["lat"] == 8.5241
    assert data["lng"] == 76.9366


def test_harbor_location_from_json():
    """Test HarborLocation deserialization."""
    json_str = '{"lat": 8.5241, "lng": 76.9366}'
    location = HarborLocation.from_json(json_str)
    assert location.latitude == 8.5241
    assert location.longitude == 76.9366


# =================================================================
# HARBOR CRUD TESTS
# =================================================================


def test_create_harbor(db: Session, harbor_data: HarborCreate):
    """Test harbor creation."""
    harbor = HarborService.create_harbor(db, harbor_data)
    assert harbor.id is not None
    assert harbor.name == "Trivandrum Harbor"
    assert harbor.state == "Kerala"
    assert harbor.harbor_type == "major"
    assert harbor.fuel_availability is True


def test_get_harbor(db: Session, harbor_data: HarborCreate):
    """Test getting harbor by ID."""
    created = HarborService.create_harbor(db, harbor_data)
    fetched = HarborService.get_harbor(db, created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.name == "Trivandrum Harbor"


def test_get_nonexistent_harbor(db: Session):
    """Test getting non-existent harbor returns None."""
    result = HarborService.get_harbor(db, 99999)
    assert result is None


def test_list_harbors(db: Session, harbor_data: HarborCreate, harbor_data_minor: HarborCreate):
    """Test listing harbors."""
    HarborService.create_harbor(db, harbor_data)
    HarborService.create_harbor(db, harbor_data_minor)

    harbors, total = HarborService.list_harbors(db, skip=0, limit=10)
    assert total >= 2
    assert len(harbors) >= 2


def test_list_harbors_filter_by_type(db: Session, harbor_data: HarborCreate, harbor_data_minor: HarborCreate):
    """Test filtering harbors by type."""
    HarborService.create_harbor(db, harbor_data)
    HarborService.create_harbor(db, harbor_data_minor)

    # Get only major harbors
    majors, total = HarborService.list_harbors(db, harbor_type="major")
    assert total >= 1
    assert all(h.harbor_type == "major" for h in majors)

    # Get only minor harbors
    minors, total = HarborService.list_harbors(db, harbor_type="minor")
    assert total >= 1
    assert all(h.harbor_type == "minor" for h in minors)


def test_list_harbors_filter_by_state(db: Session, harbor_data: HarborCreate):
    """Test filtering harbors by state."""
    HarborService.create_harbor(db, harbor_data)

    harbors, total = HarborService.list_harbors(db, state="Kerala")
    assert total >= 1
    assert all(h.state == "Kerala" for h in harbors)


# =================================================================
# NEAREST HARBOR TESTS
# =================================================================


def test_find_nearest_harbors(db: Session, harbor_data: HarborCreate, harbor_data_minor: HarborCreate):
    """Test finding nearest harbors."""
    HarborService.create_harbor(db, harbor_data)  # Trivandrum
    HarborService.create_harbor(db, harbor_data_minor)  # Kochi

    # Search from Trivandrum
    nearest = HarborService.find_nearest_harbors(
        db, latitude=8.5241, longitude=76.9366, max_distance_km=300, limit=5
    )

    assert len(nearest) >= 1
    assert nearest[0].harbor.name == "Trivandrum Harbor"
    assert nearest[0].distance_km < 1  # Should be very close


def test_find_nearest_harbors_distance_limit(db: Session, harbor_data: HarborCreate):
    """Test distance limit in nearest harbor search."""
    HarborService.create_harbor(db, harbor_data)

    # Search with very small distance limit
    nearest = HarborService.find_nearest_harbors(
        db, latitude=8.0, longitude=76.0, max_distance_km=10, limit=5
    )

    # Should be empty or have very few results
    assert len(nearest) == 0


def test_find_nearest_harbors_limit(db: Session, harbor_data: HarborCreate, harbor_data_minor: HarborCreate):
    """Test result limit in nearest harbor search."""
    HarborService.create_harbor(db, harbor_data)
    HarborService.create_harbor(db, harbor_data_minor)

    # Search with limit of 1
    nearest = HarborService.find_nearest_harbors(
        db, latitude=8.5, longitude=76.9, max_distance_km=500, limit=1
    )

    assert len(nearest) <= 1


# =================================================================
# EMERGENCY HARBOR TESTS
# =================================================================


def test_get_emergency_harbor(db: Session, harbor_data: HarborCreate):
    """Test getting emergency harbor."""
    harbor_data.harbor_type = "emergency"
    HarborService.create_harbor(db, harbor_data)

    emergency = HarborService.get_emergency_harbor(db, latitude=8.5, longitude=76.9)
    assert emergency is not None
    assert emergency.harbor.harbor_type == "emergency"


def test_get_emergency_harbor_fallback_to_major(db: Session):
    """Test fallback to major harbor when no emergency harbor exists."""
    # Create only major harbor
    harbor_data = HarborCreate(
        name="Major Harbor",
        latitude=8.5,
        longitude=76.9,
        state="Kerala",
        district="Test",
        harbor_type="major",
    )
    HarborService.create_harbor(db, harbor_data)

    # Should fall back to major harbor
    emergency = HarborService.get_emergency_harbor(db, latitude=8.5, longitude=76.9)
    assert emergency is not None
    assert emergency.harbor.harbor_type == "major"


# =================================================================
# HARBOR REVIEW TESTS
# =================================================================


def test_add_harbor_review(db: Session, harbor_data: HarborCreate, fisherman: User):
    """Test adding harbor review."""
    harbor = HarborService.create_harbor(db, harbor_data)
    review_data = HarborReviewCreate(
        rating=5,
        review_text="Excellent facility",
        service_quality=5,
        facilities_quality=5,
        staff_helpfulness=5,
    )

    review = HarborService.add_review(db, harbor.id, fisherman.id, review_data)
    assert review.id is not None
    assert review.rating == 5
    assert review.review_text == "Excellent facility"


def test_harbor_average_rating(db: Session, harbor_data: HarborCreate, fisherman: User):
    """Test harbor average rating calculation."""
    harbor = HarborService.create_harbor(db, harbor_data)

    # Add 3-star review
    review_data1 = HarborReviewCreate(rating=3)
    HarborService.add_review(db, harbor.id, fisherman.id, review_data1)

    # Add 5-star review
    review_data2 = HarborReviewCreate(rating=5)
    HarborService.add_review(db, harbor.id, fisherman.id, review_data2)

    # Check average
    updated_harbor = HarborService.get_harbor(db, harbor.id)
    assert updated_harbor.average_rating == 4.0
    assert updated_harbor.total_reviews == 2


def test_get_harbor_reviews(db: Session, harbor_data: HarborCreate, fisherman: User):
    """Test retrieving harbor reviews."""
    harbor = HarborService.create_harbor(db, harbor_data)

    # Add 3 reviews
    for i in range(3):
        review_data = HarborReviewCreate(rating=i + 1, review_text=f"Review {i + 1}")
        HarborService.add_review(db, harbor.id, fisherman.id, review_data)

    reviews, total = HarborService.get_harbor_reviews(db, harbor.id, skip=0, limit=10)
    assert total == 3
    assert len(reviews) == 3


# =================================================================
# HARBOR VISITS TESTS
# =================================================================


def test_log_harbor_visit(db: Session, harbor_data: HarborCreate, fisherman: User):
    """Test logging harbor visit."""
    harbor = HarborService.create_harbor(db, harbor_data)
    services_used = ["Fuel", "Ice"]

    visit = HarborService.log_harbor_visit(
        db,
        trip_id=1,
        harbor_id=harbor.id,
        fisherman_id=fisherman.id,
        services_used=services_used,
        notes="Test visit",
    )

    assert visit.id is not None
    assert visit.harbor_id == harbor.id
    assert visit.fisherman_id == fisherman.id
    assert visit.arrival_time is not None
    assert visit.departure_time is None  # Not set until end_harbor_visit


def test_end_harbor_visit(db: Session, harbor_data: HarborCreate, fisherman: User):
    """Test ending harbor visit."""
    harbor = HarborService.create_harbor(db, harbor_data)

    visit = HarborService.log_harbor_visit(
        db, trip_id=1, harbor_id=harbor.id, fisherman_id=fisherman.id, services_used=["Fuel"]
    )

    # End visit
    ended_visit = HarborService.end_harbor_visit(db, visit.id)
    assert ended_visit.departure_time is not None
    assert ended_visit.departure_time > ended_visit.arrival_time


def test_end_nonexistent_visit(db: Session):
    """Test ending non-existent visit returns None."""
    result = HarborService.end_harbor_visit(db, 99999)
    assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
