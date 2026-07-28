# Phase 5 Week 2: Quick Reference & Commands

## 🚀 One-Command Setup

```bash
# 1. Apply migration
cd backend && alembic upgrade head

# 2. Run all tests
pytest tests/test_week2_services.py -v

# 3. Start backend
uvicorn app.main:app --reload --port 8000
```

---

## 📋 Verification Checklist

### ✅ Files Exist
```bash
ls -la backend/app/services/boat_health.py
ls -la backend/app/services/family_portal.py
ls -la backend/app/services/analytics.py
ls -la backend/app/routers/v2/boat_health.py
ls -la backend/app/routers/v2/family_portal.py
ls -la backend/app/routers/v2/analytics.py
ls -la backend/alembic/versions/005_week2_services.py
ls -la backend/tests/test_week2_services.py
```

### ✅ Migration Applied
```bash
cd backend
alembic current
# Should show: 005_week2_services

alembic history --indicate-current
# Should show: 005_week2_services as @
```

### ✅ Tables Created
```bash
# In Python shell after connecting to database
from app.database import engine
from sqlalchemy import inspect

inspector = inspect(engine)
tables = inspector.get_table_names()
print("boat_fuel_logs" in tables)  # Should be True
print("family_portal_access" in tables)  # Should be True
print("analytics_sos_metrics" in tables)  # Should be True
```

### ✅ Tests Pass
```bash
pytest tests/test_week2_services.py -v
# Expected output:
# test_create_fuel_log PASSED
# test_fuel_log_efficiency_calculation PASSED
# ... (39 total)
# ==================== 39 passed in 2.5s ====================
```

### ✅ API Responds
```bash
# Start server first
curl http://localhost:8000/health
# Expected: {"status":"healthy","database":"healthy"}

curl http://localhost:8000/docs
# Expected: Swagger UI with new /api/v2/* endpoints
```

---

## 🧪 Test Commands

### Run All Tests
```bash
pytest tests/test_week2_services.py -v
```

### Run by Service
```bash
# Fuel & Boat Health
pytest tests/test_week2_services.py -k "fuel or health or maintenance" -v

# Family Safety Portal
pytest tests/test_week2_services.py -k "family or safety or portal" -v

# Analytics
pytest tests/test_week2_services.py -k "analytics" -v
```

### Run Specific Test
```bash
pytest tests/test_week2_services.py::test_create_fuel_log -v
pytest tests/test_week2_services.py::test_calculate_health_score_critical -v
pytest tests/test_week2_services.py::test_family_portal_access_denied -v
pytest tests/test_week2_services.py::test_sos_trends -v
```

### With Coverage
```bash
pytest tests/test_week2_services.py --cov=app/services --cov=app/routers/v2
# Expected: >90% coverage
```

---

## 🔌 API Test Requests

### Boat Health: Create Fuel Log
```bash
curl -X POST http://localhost:8000/api/v2/boat-health/fuel-log \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "boat_id": 1,
    "trip_id": 1,
    "fuel_level_start_percent": 100,
    "fuel_level_end_percent": 75,
    "fuel_consumed_liters": 50,
    "distance_traveled_km": 100
  }'
```

### Boat Health: Get Fuel Summary
```bash
curl -X GET http://localhost:8000/api/v2/boat-health/1/fuel-summary \
  -H "Authorization: Bearer $TOKEN"
```

### Boat Health: Get Health Score
```bash
curl -X GET http://localhost:8000/api/v2/boat-health/1/health-score \
  -H "Authorization: Bearer $TOKEN"
```

### Family Portal: Get Dashboard
```bash
curl -X GET http://localhost:8000/api/v2/family/dashboard \
  -H "Authorization: Bearer $TOKEN"
```

### Family Portal: Get Safety Status
```bash
curl -X GET http://localhost:8000/api/v2/family/fisherman/1/safety-status \
  -H "Authorization: Bearer $TOKEN"
```

### Analytics: Get Overview
```bash
curl -X GET http://localhost:8000/api/v2/analytics/overview \
  -H "Authorization: Bearer $TOKEN"
```

### Analytics: Get SOS Trends (7 days)
```bash
curl -X GET "http://localhost:8000/api/v2/analytics/sos-trends?days=7" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 🐳 Docker Commands

### Build
```bash
docker-compose build
```

### Start
```bash
docker-compose up -d
```

### Migrate
```bash
docker-compose exec api alembic upgrade head
```

### Test
```bash
docker-compose exec api pytest tests/test_week2_services.py -v
```

### Logs
```bash
docker-compose logs -f api
```

### Stop
```bash
docker-compose down
```

### Full Deploy
```bash
docker-compose down
docker-compose build
docker-compose up -d
docker-compose exec api alembic upgrade head
docker-compose exec api pytest tests/test_week2_services.py -v
```

---

## 📊 Database Commands

### Connect to Database
```bash
# PostgreSQL
psql -U oceandb_user -d oceandb -h localhost

# SQLite (development)
sqlite3 backend/database.db
```

### List Tables
```bash
\dt  # PostgreSQL
.tables  # SQLite
```

### Check Boat Health Tables
```sql
SELECT table_name FROM information_schema.tables 
WHERE table_schema='public' AND table_name LIKE 'boat_%';

SELECT table_name FROM information_schema.tables 
WHERE table_schema='public' AND table_name LIKE 'family_%';

SELECT table_name FROM information_schema.tables 
WHERE table_schema='public' AND table_name LIKE 'analytics_%';
```

### Count Records
```sql
SELECT COUNT(*) FROM boat_fuel_logs;
SELECT COUNT(*) FROM boat_maintenance;
SELECT COUNT(*) FROM family_portal_access;
SELECT COUNT(*) FROM analytics_sos_metrics;
```

---

## 🔍 Debugging

### Check Import
```bash
cd backend
python -c "from app.services.boat_health import BoatHealthService; print('✅ BoatHealthService imported')"
python -c "from app.services.family_portal import FamilySafetyPortalService; print('✅ FamilySafetyPortalService imported')"
python -c "from app.services.analytics import AnalyticsService; print('✅ AnalyticsService imported')"
```

### Check Routers
```bash
python -c "from app.routers.v2 import boat_health; print('✅ boat_health router imported')"
python -c "from app.routers.v2 import family_portal; print('✅ family_portal router imported')"
python -c "from app.routers.v2 import analytics; print('✅ analytics router imported')"
```

### Check Models
```bash
python -c "from app.models.phase5 import BoatFuelLog, BoatMaintenance, BoatHealthStatus; print('✅ Boat models imported')"
python -c "from app.models.phase5 import FamilyPortalAccess, FamilySafetyEvent; print('✅ Family models imported')"
python -c "from app.models.phase5 import AnalyticsSOSMetrics; print('✅ Analytics models imported')"
```

### View API Endpoints
```bash
# Start server, then:
curl http://localhost:8000/openapi.json | python -m json.tool | grep -A2 '"path": "/api/v2'
```

---

## 📈 Monitoring

### Real-time Logs
```bash
# Development
uvicorn app.main:app --reload --log-level debug

# Docker
docker-compose logs -f api
```

### Database Queries
```bash
# Enable query logging in app/config.py
SQLALCHEMY_ECHO=True
```

### API Response Times
```bash
# Install timing middleware
time curl -X GET http://localhost:8000/api/v2/boat-health/1/health-score \
  -H "Authorization: Bearer $TOKEN"
```

---

## 🚨 Common Issues & Solutions

### Issue: Migration fails
```bash
# Solution: Check migration status
alembic current
alembic history

# If stuck, downgrade and retry
alembic downgrade base
alembic upgrade head
```

### Issue: Tests fail with "table does not exist"
```bash
# Solution: Run migration in test DB
pytest tests/test_week2_services.py -v
# Tests create in-memory SQLite, should work

# Or: Check database connection
python -c "from app.database import SessionLocal; db = SessionLocal(); print('✅ DB connected')"
```

### Issue: 403 Unauthorized on API calls
```bash
# Solution: Check JWT token
# 1. Login first
POST /login with phone_number + pin

# 2. Use returned token
Authorization: Bearer <token>

# 3. Verify user role matches endpoint requirement
```

### Issue: Docker build fails
```bash
# Solution: Clear cache and rebuild
docker-compose down
docker system prune -a
docker-compose build --no-cache
docker-compose up -d
```

---

## 📱 End-to-End Test Scenario

```bash
# 1. Login as fisherman
TOKEN_FISHERMAN=$(curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"phone_number":"+911234567890","pin":"123456"}' \
  | jq -r '.access_token')

# 2. Create fuel log
curl -X POST http://localhost:8000/api/v2/boat-health/fuel-log \
  -H "Authorization: Bearer $TOKEN_FISHERMAN" \
  -H "Content-Type: application/json" \
  -d '{
    "boat_id": 1,
    "fuel_level_start_percent": 100,
    "fuel_level_end_percent": 80,
    "fuel_consumed_liters": 40,
    "distance_traveled_km": 80
  }'

# 3. Get health score
curl -X GET http://localhost:8000/api/v2/boat-health/1/health-score \
  -H "Authorization: Bearer $TOKEN_FISHERMAN"

# 4. Login as operator
TOKEN_OPERATOR=$(curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"phone_number":"+918888888888","pin":"123456"}' \
  | jq -r '.access_token')

# 5. View analytics
curl -X GET http://localhost:8000/api/v2/analytics/overview \
  -H "Authorization: Bearer $TOKEN_OPERATOR"
```

---

## 📝 Documentation Links

- **Full Documentation:** PHASE5_WEEK2_COMPLETE.md
- **Implementation Summary:** PHASE5_WEEK2_SUMMARY.md
- **API Reference:** http://localhost:8000/docs (Swagger UI)
- **ReDoc:** http://localhost:8000/redoc

---

## 🎯 Success Criteria

- [x] 3 services implemented
- [x] 18 endpoints created
- [x] 39 tests passing
- [x] Database migration works
- [x] Authorization working
- [x] API documentation complete
- [x] Docker deployment ready
- [x] No breaking changes to Phase 1-4

---

## 📞 Next Steps

1. Review PHASE5_WEEK2_COMPLETE.md
2. Run migration: `alembic upgrade head`
3. Run tests: `pytest tests/test_week2_services.py -v`
4. Start server: `uvicorn app.main:app --reload`
5. Test APIs in Swagger UI
6. Deploy to staging/production

---

**Everything is ready! 🚀**
