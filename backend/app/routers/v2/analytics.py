"""Analytics Engine API routes — v2 API."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.deps import get_current_operator
from app.core.rate_limit import rate_limit
from app.models.user import User
from app.services.analytics import (
    AnalyticsService,
    AnalyticsOverviewResponse,
    SOSTrendsResponse,
    ResponseTimeMetricsResponse,
    ActiveBoatsAnalyticsResponse,
    RiskZoneAnalyticsResponse,
    HarborUsageAnalyticsResponse,
    BoatHealthAnalyticsResponse,
)

router = APIRouter(prefix="/api/v2/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverviewResponse, dependencies=[Depends(rate_limit("analytics_overview", limit=10))])
async def get_analytics_overview(
    current_user: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    """Get real-time analytics overview (operators only)."""
    overview = AnalyticsService.get_overview(db)
    return overview


@router.get("/sos-trends", response_model=SOSTrendsResponse, dependencies=[Depends(rate_limit("analytics_sos", limit=10))])
async def get_sos_trends(
    days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    """Get SOS trends analytics."""
    trends = AnalyticsService.get_sos_trends(db, days=days)
    return trends


@router.get("/response-times", response_model=ResponseTimeMetricsResponse, dependencies=[Depends(rate_limit("analytics_response", limit=10))])
async def get_response_times(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    """Get response time metrics."""
    metrics = AnalyticsService.get_response_times(db, days=days)
    return metrics


@router.get("/active-boats", response_model=ActiveBoatsAnalyticsResponse, dependencies=[Depends(rate_limit("analytics_boats", limit=10))])
async def get_active_boats(
    current_user: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    """Get active boats analytics."""
    analytics = AnalyticsService.get_active_boats(db)
    return analytics


@router.get("/risk-zones", response_model=RiskZoneAnalyticsResponse, dependencies=[Depends(rate_limit("analytics_risk", limit=10))])
async def get_risk_zones(
    days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    """Get risk zone analytics."""
    zones = AnalyticsService.get_risk_zones(db, days=days)
    return zones


@router.get("/harbor-usage", response_model=HarborUsageAnalyticsResponse, dependencies=[Depends(rate_limit("analytics_harbor", limit=10))])
async def get_harbor_usage(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    """Get harbor usage analytics."""
    usage = AnalyticsService.get_harbor_usage(db, days=days)
    return usage


@router.get("/boat-health", response_model=BoatHealthAnalyticsResponse, dependencies=[Depends(rate_limit("analytics_health", limit=10))])
async def get_boat_health_analytics(
    current_user: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    """Get boat health analytics."""
    analytics = AnalyticsService.get_boat_health(db)
    return analytics
