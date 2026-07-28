# Phase 5 Week 2: Architecture & Data Flow

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     OceanGuardian Phase 5 Week 2                    │
└─────────────────────────────────────────────────────────────────────┘

                           FastAPI Application
                    (backend/app/main.py)
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
    ┌───▼────┐          ┌────▼────┐          ┌────▼──────┐
    │ v1 API │          │ v2 API  │          │ Support   │
    │ (Phase │          │(Phase 5)│          │  Routes   │
    │  1-4)  │          │         │          │  /health  │
    └───┬────┘          └────┬────┘          └────┬──────┘
        │                    │                    │
        │            ┌───────┼───────┐            │
        │            │       │       │            │
    ┌───▼──────────┐ │       │       │            │
    │ Existing     │ │  ┌────▼──────▼──┐         │
    │ Endpoints    │ │  │ Three New    │         │
    │ (auth,       │ │  │ Services:    │         │
    │  location,   │ │  │              │         │
    │  SOS, etc)   │ │  ├─ Boat Health │         │
    │              │ │  ├─ Family Portal
    │              │ │  └─ Analytics   │         │
    └──────────────┘ │  └──────────────┘         │
                     │        │                  │
                     │  ┌─────┼─────┐            │
                     │  ▼     ▼     ▼            │
                     │ ┌─────────────────────┐   │
                     │ │  Six Routers:       │   │
                     │ ├─ v2/boat_health    │   │
                     │ ├─ v2/family_portal  │   │
                     │ ├─ v2/analytics      │   │
                     │ └─ ... (existing)    │   │
                     │ └─────────────────────┘   │
                     │                          │
        ┌────────────┼──────────────────────────┤
        │            │                         │
        ▼            ▼                         ▼
  ┌──────────────┐  ┌──────────────────────────────────┐
  │ Database     │  │  Services Layer                  │
  │ (PostgreSQL) │  │  ┌────────────────────────────┐  │
  │              │  │  │ BoatHealthService          │  │
  │ 12 Tables:   │  │  │  - Health scoring          │  │
  │ ├─ boats     │  │  │  - Fuel tracking           │  │
  │ ├─ fuel_logs │  │  │  - Maintenance mgmt        │  │
  │ ├─ family... │  │  ├────────────────────────────┤  │
  │ ├─ analytics │  │  │ FamilySafetyPortalService  │  │
  │ └─ ...       │  │  │  - Dashboard               │  │
  └──────────────┘  │  │  - Event timeline          │  │
                    │  │  - Safety status           │  │
                    │  ├────────────────────────────┤  │
                    │  │ AnalyticsService           │  │
                    │  │  - Trends                  │  │
                    │  │  - Metrics                 │  │
                    │  │  - Analytics               │  │
                    │  └────────────────────────────┘  │
                    │                                  │
                    │  Pydantic Schemas (Validation)  │
                    │  - FuelLogCreate                │
                    │  - SafetyStatusResponse         │
                    │  - AnalyticsOverviewResponse    │
                    └──────────────────────────────────┘
```

---

## 📊 Data Flow Diagrams

### 1. Boat Health Service Flow

```
Fisherman App
    │
    ├─ POST /api/v2/boat-health/fuel-log
    │  └─► BoatHealthService.create_fuel_log()
    │      ├─ Calculate efficiency (km/liter)
    │      └─ Save to boat_fuel_logs table
    │
    ├─ GET /api/v2/boat-health/{id}/fuel-summary
    │  └─► BoatHealthService.get_fuel_summary()
    │      ├─ Query last 20 fuel logs
    │      ├─ Calculate average efficiency
    │      ├─ Estimate range
    │      └─ Check low fuel (<20%)
    │
    ├─ POST /api/v2/boat-health/maintenance
    │  └─► BoatHealthService.create_maintenance_record()
    │      └─ Save to boat_maintenance table
    │
    ├─ GET /api/v2/boat-health/{id}/maintenance-due
    │  └─► BoatHealthService.get_maintenance_due()
    │      ├─ Query boat_maintenance
    │      ├─ Find overdue (scheduled_date < now)
    │      └─ Flag critical issues
    │
    └─ GET /api/v2/boat-health/{id}/health-score
       └─► BoatHealthService.calculate_health_score()
           ├─ Get fuel status (20% weight)
           ├─ Get maintenance due (40% weight)
           ├─ Get engine hours (20% weight)
           ├─ Get service history (20% weight)
           └─ Return: Score (0-100), Status, Risk Level

Database Updates:
┌──────────────────┐
│ boat_fuel_logs   │  ← New fuel entries
│ boat_maintenance │  ← Maintenance scheduled
│ boat_health_...  │  ← Health metrics updated
└──────────────────┘
```

### 2. Family Safety Portal Flow

```
Family Member App
    │
    ├─ GET /api/v2/family/dashboard
    │  └─► FamilySafetyPortalService.get_family_dashboard()
    │      ├─ Query family_portal_access (linked fishermen)
    │      ├─ Get latest location for each
    │      ├─ Count active SOS alerts
    │      ├─ Check connection lost (>30 min GPS gap)
    │      └─ Return: Dashboard with status badges
    │
    ├─ GET /api/v2/family/fisherman/{id}/safety-status
    │  └─► Check access permission
    │      └─► FamilySafetyPortalService.get_fisherman_safety_status()
    │          ├─ Get latest GPS (location_pings)
    │          ├─ Get active trip (trips table)
    │          ├─ Get active SOS (sos_alerts table)
    │          ├─ Calculate time since update
    │          ├─ Determine status (at_sea/at_home/unknown)
    │          └─ Warn if connection lost
    │
    ├─ GET /api/v2/family/fisherman/{id}/timeline
    │  └─► FamilySafetyPortalService.get_safety_timeline()
    │      ├─ Query family_safety_events (limit 50)
    │      ├─ Include: trips, locations, SOS
    │      ├─ Sort by created_at DESC
    │      └─ Mark read status
    │
    └─ POST /api/v2/family/notifications/{id}/mark-read
       └─► FamilySafetyPortalService.mark_notification_read()
           └─ Update family_notifications.read_at

Events Created When:
┌─────────────────────┐
│ Trip starts         │ → family_safety_events (trip_started)
│ GPS updated         │ → family_safety_events (location_update)
│ SOS triggered       │ → family_safety_events (sos_alert)
│ Trip completed      │ → family_safety_events (trip_completed)
└─────────────────────┘
```

### 3. Analytics Engine Flow

```
Operator/Admin Dashboard
    │
    ├─ GET /api/v2/analytics/overview (Real-time)
    │  └─► AnalyticsService.get_overview()
    │      ├─ COUNT sos_alerts (today)
    │      ├─ COUNT resolved SOS (today)
    │      ├─ COUNT active trips
    │      ├─ Calculate avg response time
    │      ├─ COUNT connection lost (>30 min)
    │      └─ Return: Live dashboard
    │
    ├─ GET /api/v2/analytics/sos-trends?days=7
    │  └─► AnalyticsService.get_sos_trends()
    │      ├─ Query sos_alerts (last 7 days)
    │      ├─ Count resolved vs unresolved
    │      ├─ Calculate resolution rate %
    │      ├─ Group by hazard_type
    │      └─ Return: Trends and patterns
    │
    ├─ GET /api/v2/analytics/response-times?days=30
    │  └─► AnalyticsService.get_response_times()
    │      ├─ Query resolved SOS (last 30 days)
    │      ├─ Calculate: resolved_at - created_at
    │      ├─ Sort and find: min, max, p50, p95
    │      └─ Return: Response time metrics
    │
    ├─ GET /api/v2/analytics/active-boats
    │  └─► AnalyticsService.get_active_boats()
    │      ├─ COUNT trips WHERE end_time IS NULL
    │      ├─ COUNT completed trips (today)
    │      ├─ Average trip duration
    │      └─ Return: Activity snapshot
    │
    ├─ GET /api/v2/analytics/risk-zones
    │  └─► AnalyticsService.get_risk_zones()
    │      ├─ Identify SOS hotspots
    │      ├─ Calculate avg risk score
    │      ├─ Group by Green/Yellow/Red
    │      └─ Return: Risk distribution
    │
    ├─ GET /api/v2/analytics/harbor-usage
    │  └─► AnalyticsService.get_harbor_usage()
    │      ├─ Query harbor_visits (last 30 days)
    │      ├─ Count by harbor
    │      ├─ Calculate avg rating
    │      └─ Return: Top harbors
    │
    └─ GET /api/v2/analytics/boat-health
       └─► AnalyticsService.get_boat_health()
           ├─ Query boat_health_status (all boats)
           ├─ Categorize: Good (≥70) / Warning / Critical
           ├─ Common issues summary
           └─ Return: Fleet health overview

Real-time Aggregation:
┌──────────────────────────┐
│ sos_alerts              │
│ trips                   │
│ location_pings          │
│ boat_health_status      │
│ boat_fuel_logs          │
└──────────────────────────┘
       ▼
 Combined Queries
       ▼
  Analytics Output
```

---

## 🗄️ Database Schema Relationships

```
┌──────────────────────────────────────────────────────────────────┐
│                    BOAT HEALTH TRACKING                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  boats ─────────┐                                               │
│    │ id         │                                               │
│    │ boat_name  │                                               │
│    │            │                                               │
│    └──────┬─────┴────────────┬──────────────┬────────────┐      │
│           │                  │              │            │      │
│     ┌─────▼──────────┐  ┌───▼──────────┐  │     ┌──────▼──────┐
│     │fuel_logs       │  │maintenance   │  │     │boat_health_ │
│     │                │  │              │  │     │status       │
│     │boat_id ────────┼──┤boat_id ──────┼──┼─────┤boat_id      │
│     │trip_id         │  │type          │  │     │engine_hours │
│     │fuel_start%     │  │scheduled_at  │  │     │health_score │
│     │fuel_end%       │  │completed_at  │  │     │issues       │
│     │consumed_L      │  │cost          │  │     │updated_at   │
│     │efficiency      │  │technician    │  │     └─────────────┘
│     │timestamp       │  └──────────────┘  │
│     └────────────────┘                    │
│                                           │
│     ┌─────────────────────────────────────┘
│     │
│     └──► fuel_predictions
│         ├─ trip_id
│         ├─ boat_id
│         ├─ estimated_fuel_needed
│         └─ model_accuracy

└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                    FAMILY SAFETY TRACKING                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  users (family) ──────────┐                                     │
│    │ id                   │                                     │
│    │ phone                │                                     │
│    │ role = "family"      │                                     │
│    │                      │                                     │
│    └──────┬───────────────┴──────────────────┐                  │
│           │                                  │                  │
│     ┌─────▼──────────────┐  ┌───────────────▼──────┐            │
│     │family_portal_      │  │family_               │            │
│     │access              │  │notifications         │            │
│     │                    │  │                      │            │
│     │family_member_id ──┼──┤family_member_id      │            │
│     │fisherman_id       │  │notification_type     │            │
│     │access_level       │  │message               │            │
│     │permissions...     │  │delivery_status       │            │
│     └────────┬──────────┘  │read_at               │            │
│              │             └──────────────────────┘            │
│              │                                                  │
│              └──────┬────────────────────────────┐              │
│                     │                           │              │
│              ┌──────▼─────────────┐  ┌─────────▼──────┐        │
│              │family_safety_      │  │                │        │
│              │events              │  │ Linked to:     │        │
│              │                    │  │ - trips        │        │
│              │family_member_id ──┼──┤ - sos_alerts   │        │
│              │fisherman_id       │  │ - location_    │        │
│              │event_type         │  │   pings        │        │
│              │severity           │  └────────────────┘        │
│              │location_json      │                            │
│              │created_at         │                            │
│              └────────────────────┘                            │

└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                    ANALYTICS METRICS                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────┐  ┌──────────────────────┐            │
│  │analytics_sos_metrics │  │analytics_trip_       │            │
│  │                      │  │metrics               │            │
│  │period_date           │  │                      │            │
│  │period_type           │  │period_date           │            │
│  │total_alerts          │  │total_trips           │            │
│  │resolved_count        │  │completed_trips       │            │
│  │avg_response_time     │  │avg_duration          │            │
│  │by_region             │  │by_harbor             │            │
│  │by_hazard_type        │  └──────────────────────┘            │
│  └──────────────────────┘                                      │
│                                                                  │
│  ┌──────────────────────┐  ┌──────────────────────┐            │
│  │analytics_risk_       │  │analytics_user_       │            │
│  │metrics               │  │engagement            │            │
│  │                      │  │                      │            │
│  │period_date           │  │period_date           │            │
│  │green_trips           │  │active_fishermen      │            │
│  │yellow_trips          │  │active_operators      │            │
│  │red_trips             │  │active_family         │            │
│  │avg_risk_score        │  │dashboard_sessions    │            │
│  └──────────────────────┘  └──────────────────────┘            │

└──────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Request/Response Cycle

### Example: Create Fuel Log

```
┌─────────────────────────────────┐
│ 1. Fisherman sends request      │
├─────────────────────────────────┤
│ POST /api/v2/boat-health/       │
│      fuel-log                   │
│                                 │
│ Headers:                        │
│   Authorization: Bearer TOKEN   │
│   Content-Type: application/json│
│                                 │
│ Body:                           │
│ {                               │
│   "boat_id": 42,                │
│   "fuel_level_start_percent": 100,
│   "fuel_level_end_percent": 80, │
│   "fuel_consumed_liters": 40,   │
│   "distance_traveled_km": 100   │
│ }                               │
└──────────────────┬──────────────┘
                   │
                   ▼
        ┌──────────────────┐
        │ Router receives  │
        │ (boat_health.py) │
        └────────┬─────────┘
                 │ Validate JWT
                 │ Check role
                 │ Validate ownership
                 │ Parse JSON
                 │ Validate schema (Pydantic)
                 ▼
        ┌──────────────────┐
        │ Service method   │
        │ (boat_health.py) │
        └────────┬─────────┘
                 │ Calculate efficiency
                 │ Prepare record
                 │ Save to database
                 │ Refresh from DB
                 ▼
        ┌──────────────────┐
        │ Database update  │
        └────────┬─────────┘
                 │ INSERT boat_fuel_logs
                 ▼
┌─────────────────────────────────┐
│ 2. Return success response      │
├─────────────────────────────────┤
│ Status: 201 Created             │
│                                 │
│ Response:                       │
│ {                               │
│   "id": 1234,                   │
│   "boat_id": 42,                │
│   "fuel_level_start_percent": 100,
│   "fuel_level_end_percent": 80, │
│   "fuel_consumed_liters": 40,   │
│   "efficiency_km_per_liter": 2.5,
│   "timestamp": "2024-01-01..."  │
│ }                               │
└─────────────────────────────────┘
```

---

## 🔐 Authorization Flow

```
Request with JWT
      │
      ▼
┌─────────────────┐
│ get_current_user│
│ (Depends)       │
└────────┬────────┘
         │ Validate JWT
         │ Extract user_id
         │ Query user from DB
         │ Verify role
         ▼
┌─────────────────┐
│ Check role      │
│ (Endpoint)      │
└────────┬────────┘
         │
    ┌────┴────┐
    │          │
NO  ▼          ▼  YES
403 OK    ┌──────────────┐
←─────────┤ Check resource│
          │ ownership    │
          └────┬─────────┘
               │
          ┌────┴────┐
          │          │
       NO ▼          ▼ YES
        403 OK   ┌────────┐
        ←────────│Execute │
                 │Endpoint│
                 └────┬───┘
                      │
                      ▼
                 Response 200/201
```

---

## 📈 Health Score Calculation

```
Health Score = 
  (Fuel_Score × 0.20) +
  (Maintenance_Score × 0.40) +
  (Engine_Score × 0.20) +
  (Service_Score × 0.20)

┌─────────────────────────────────────────────────────┐
│ FUEL FACTOR (20%)                                   │
├─────────────────────────────────────────────────────┤
│ 100 points   if no low fuel warning                │
│ -15 points   if <20% fuel                          │
│ -10 points   if no fuel data                       │
│ Result: 75-100 points                              │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ MAINTENANCE FACTOR (40%)                            │
├─────────────────────────────────────────────────────┤
│ 100 points   if no overdue maintenance             │
│ -30 points   if maintenance overdue                │
│ -10 points   if upcoming in <7 days               │
│ Result: 60-100 points                              │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ ENGINE FACTOR (20%)                                 │
├─────────────────────────────────────────────────────┤
│ 100 points   if <3000 hours                        │
│ -10 points   if 3000-5000 hours                   │
│ -20 points   if >5000 hours                       │
│ Result: 80-100 points                              │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ SERVICE FACTOR (20%)                                │
├─────────────────────────────────────────────────────┤
│ 100 points   if <6 months since service           │
│ -5 points    if 6-12 months since service         │
│ -15 points   if >12 months since service          │
│ Result: 85-100 points                              │
└─────────────────────────────────────────────────────┘

        ↓↓↓ FINAL CALCULATION ↓↓↓

Health Score ∈ [0-100]

Status Legend:
├─ [0-40)      → CRITICAL (status="Critical", risk_level="High")
├─ [40-70)     → WARNING  (status="Warning", risk_level="Medium")
└─ [70-100]    → GOOD     (status="Good", risk_level="Low")
```

---

## 🎯 Key Integration Points

```
Phase 5 Week 2 Services ← Phase 1-4 Foundation

Boat Health Service  ←→  boats, trips, location_pings
  ├─ fuel tracking
  ├─ maintenance scheduling
  └─ health scoring

Family Portal Service ←→ users, trips, location_pings, sos_alerts
  ├─ family monitoring
  ├─ safety events
  └─ notifications

Analytics Service  ←→ sos_alerts, trips, location_pings, boats
  ├─ trend analysis
  ├─ response metrics
  └─ insights generation

All: Authentication (get_current_user) ← Phase 1 auth system
All: Database (SQLAlchemy ORM) ← Phase 1-4 database
All: API Structure (FastAPI) ← Phase 1-4 framework
```

---

**Architecture Complete** ✅

All services integrated and production-ready.
