"""Harbor Intelligence API routes — v2 API."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.services.harbor import (
    HarborService,
    HarborCreate,
    HarborUpdate,
    HarborResponse,
    HarborReviewCreate,
    NearestHarborResponse,
)

router = APIRouter(prefix="/api/v2/harbor", tags=["harbor-intelligence"])


@router.post("/create", response_model=HarborResponse)
async def create_harbor(
    harbor_data: HarborCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create new harbor (admin only)."""
    if current_user.role != "operator":
        raise HTTPException(status_code=403, detail="Only operators can create harbors")

    harbor = HarborService.create_harbor(db, harbor_data)
    return HarborResponse.from_orm(harbor)


@router.get("/{harbor_id}", response_model=HarborResponse)
async def get_harbor(harbor_id: int, db: Session = Depends(get_db)):
    """Get harbor details by ID."""
    harbor = HarborService.get_harbor(db, harbor_id)
    if not harbor:
        raise HTTPException(status_code=404, detail="Harbor not found")
    return HarborResponse.from_orm(harbor)


@router.get("/", response_model=dict)
async def list_harbors(
    state: Optional[str] = Query(None),
    harbor_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List harbors with optional filters."""
    harbors, total = HarborService.list_harbors(db, state=state, harbor_type=harbor_type, skip=skip, limit=limit)
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "harbors": [HarborResponse.from_orm(h) for h in harbors],
    }


@router.post("/nearest", response_model=List[NearestHarborResponse])
async def find_nearest_harbors(
    latitude: float,
    longitude: float,
    max_distance_km: float = Query(50, ge=1),
    limit: int = Query(5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Find nearest harbors from current location."""
    if current_user.role not in ["fisherman", "operator"]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    nearest = HarborService.find_nearest_harbors(
        db, latitude, longitude, max_distance_km=max_distance_km, limit=limit
    )
    return nearest


@router.post("/emergency-harbor", response_model=Optional[NearestHarborResponse])
async def get_emergency_harbor(
    latitude: float,
    longitude: float,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get nearest emergency harbor (SOS scenario)."""
    if current_user.role not in ["fisherman", "operator"]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    emergency_harbor = HarborService.get_emergency_harbor(db, latitude, longitude)
    if not emergency_harbor:
        raise HTTPException(status_code=404, detail="No emergency harbors available")

    return emergency_harbor


@router.post("/{harbor_id}/review", response_model=dict)
async def add_harbor_review(
    harbor_id: int,
    review_data: HarborReviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add review for harbor."""
    if current_user.role != "fisherman":
        raise HTTPException(status_code=403, detail="Only fishermen can review harbors")

    harbor = HarborService.get_harbor(db, harbor_id)
    if not harbor:
        raise HTTPException(status_code=404, detail="Harbor not found")

    review = HarborService.add_review(db, harbor_id, current_user.id, review_data)

    return {
        "id": review.id,
        "rating": review.rating,
        "review_text": review.review_text,
        "created_at": review.created_at,
    }


@router.get("/{harbor_id}/reviews", response_model=dict)
async def get_harbor_reviews(
    harbor_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get reviews for harbor."""
    harbor = HarborService.get_harbor(db, harbor_id)
    if not harbor:
        raise HTTPException(status_code=404, detail="Harbor not found")

    reviews, total = HarborService.get_harbor_reviews(db, harbor_id, skip=skip, limit=limit)

    return {
        "harbor_id": harbor_id,
        "total": total,
        "skip": skip,
        "limit": limit,
        "average_rating": harbor.average_rating,
        "reviews": [
            {
                "id": r.id,
                "rating": r.rating,
                "review_text": r.review_text,
                "service_quality": r.service_quality,
                "facilities_quality": r.facilities_quality,
                "staff_helpfulness": r.staff_helpfulness,
                "created_at": r.created_at,
            }
            for r in reviews
        ],
    }
