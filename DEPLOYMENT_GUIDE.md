# OceanGuardian AI — Deployment & Operations Guide

**Complete guide for deploying and operating the platform**

---

## 📋 Pre-Deployment Checklist

### System Requirements

**Server Specifications:**
- CPU: 2+ cores (4+ recommended)
- RAM: 4GB+ (8GB+ recommended)
- Storage: 20GB+ SSD
- OS: Ubuntu 20.04 LTS or later

**Software Requirements:**
- Docker 20.10+
- Docker Compose 2.0+
- PostgreSQL 13+ (if not using Docker)
- Node.js 18+ (if deploying dashboard separately)
- Flutter SDK (if deploying mobile app separately)

**Network Requirements:**
- Port 80 (HTTP)
- Port 443 (HTTPS)
- Port 5432 (PostgreSQL, internal only)
- Port 8000 (API, if not behind reverse proxy)
- Port 3000 (Dashboard, if not behind reverse proxy)

### Security Checklist

✅ SSL/TLS certificate installed  
✅ Firewall rules configured  
✅ Database credentials secured  
✅ JWT secret key generated  
✅ Environment variables configured  
✅ API keys rotated  
✅ Backups configured  
✅ Monitoring enabled  

---

## 🚀 Docker Deployment (Recommended)

### Step 1: Prepare Environment

```bash
# Clone repository
git clone <repository-url>
cd oceanguardian-phase2

# Create environment file
cp backend/.env.example backend/.env

# Edit .env with production values
nano backend/.env
```

**Required Environment Variables:**
```bash
# Database
DATABASE_URL=postgresql://oceanguardian:secure_password@db:5432/oceanguardian

# JWT Security
JWT_SECRET_KEY=your-super-secret-key-change-this
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
JWT_REFRESH_EXPIRATION_DAYS=7

# Environment
ENV=production
DEBUG=false

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Dashboard
REACT_APP_API_URL=https://api.yourdomain.com
```

### Step 2: Build and Start Services

```bash
# Build dashboard
cd rescue-dashboard
npm install
npm run build
cd ..

# Start all services
docker-compose up -d --build

# Check service status
docker-compose ps

# View logs
docker-compose logs -f api      # Backend logs
docker-compose logs -f dashboard # Dashboard logs
docker-compose logs -f db       # Database logs
```

### Step 3: Initialize Database

```bash
# Run migrations
docker-compose exec api alembic upgrade head

# Seed initial data
docker-compose exec api python seed.py

# Verify database
docker-compose exec db psql -U oceanguardian -d oceanguardian \
  -c "SELECT COUNT(*) FROM users;"
```

### Step 4: Verify Deployment

```bash
# Check health
curl http://localhost:8000/health

# Expected response:
{
  "status": "healthy",
  "database": "healthy",
  "version": "0.2.0",
  "environment": "production"
}

# Test login endpoint
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "+911234567890",
    "password": "rescue123"
  }'

# Access dashboard
# Open browser to http://localhost:3000
# Login with phone: +911234567890, password: rescue123
```

---

## 🔧 Local Development Setup

### Backend Setup

```bash
# Navigate to backend
cd backend

# Create Python virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your values

# Run migrations
alembic upgrade head

# Seed database
python seed.py

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# API available at:
# - Base: http://localhost:8000
# - Docs: http://localhost:8000/docs
# - ReDoc: http://localhost:8000/redoc
```

### Dashboard Setup

```bash
# Navigate to dashboard
cd rescue-dashboard

# Install dependencies
npm install

# Start development server
npm run dev

# Dashboard available at:
# http://localhost:5173 (or URL shown in console)

# Build for production
npm run build

# Preview production build
npm run preview
```

### Mobile Setup

```bash
# Navigate to mobile
cd mobile

# Get Flutter packages
flutter pub get

# Run on device/emulator
flutter run

# Build for release
flutter build apk      # Android
flutter build ios      # iOS
```

---

## 📊 Database Management

### Backup Strategy

```bash
# Manual backup
docker-compose exec db pg_dump -U oceanguardian oceanguardian > backup.sql

# Restore from backup
cat backup.sql | docker-compose exec -T db psql -U oceanguardian -d oceanguardian

# Automated daily backups (add to crontab)
0 2 * * * docker-compose exec db pg_dump -U oceanguardian oceanguardian > /backups/oceanguardian_$(date +\%Y\%m\%d).sql
```

### Database Migrations

```bash
# Check current migration state
docker-compose exec api alembic current

# Show migration history
docker-compose exec api alembic history

# Create new migration
docker-compose exec api alembic revision --autogenerate -m "description"

# Apply migrations
docker-compose exec api alembic upgrade head

# Rollback one migration
docker-compose exec api alembic downgrade -1
```

### Connect to Database

```bash
# Connect directly
docker-compose exec db psql -U oceanguardian -d oceanguardian

# Useful queries:
# List users
SELECT id, phone, role, created_at FROM users;

# Active SOS alerts
SELECT id, fisherman_id, status, created_at FROM sos_alerts WHERE status = 'triggered';

# Active trips
SELECT id, fisherman_id, boat_id, start_time FROM trips WHERE status = 'active';

# Statistics
SELECT COUNT(*) as total_users FROM users;
SELECT COUNT(*) as active_trips FROM trips WHERE status = 'active';
```

---

## 🔍 Monitoring & Logging

### Health Check Endpoints

```bash
# General health
curl http://localhost:8000/health

# Response format:
{
  "status": "healthy",
  "database": "healthy",
  "version": "0.2.0",
  "environment": "production",
  "timestamp": "2024-06-24T21:18:18.891Z"
}
```

### Log Monitoring

```bash
# View real-time logs
docker-compose logs -f api

# View logs for specific time period
docker-compose logs --since 10m api

# Export logs to file
docker-compose logs api > logs/api_$(date +%Y%m%d_%H%M%S).log

# Check for errors
docker-compose logs api | grep -i error
```

### Monitoring Setup (Optional)

For production, consider setting up:

1. **ELK Stack** (Elasticsearch, Logstash, Kibana)
2. **Prometheus** + **Grafana** for metrics
3. **Sentry** for error tracking
4. **DataDog** or **New Relic** for APM

---

## 🔐 Security Operations

### JWT Secret Rotation

```bash
# Generate new JWT secret
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Update .env
JWT_SECRET_KEY=<new-secret>

# Restart API
docker-compose restart api

# All existing tokens become invalid - users must re-login
```

### Database Password Rotation

```bash
# Update password in environment
# Update DATABASE_URL in .env
# For PostgreSQL Docker:
# Edit docker-compose.yml - POSTGRES_PASSWORD value

# Restart services
docker-compose down
docker-compose up -d --build

# Verify connection
docker-compose exec api python -c "from sqlalchemy import create_engine; \
  engine = create_engine(os.environ['DATABASE_URL']); \
  with engine.connect() as conn: print('Connected successfully')"
```

### API Rate Limiting

Current implementation supports rate limiting. To enable:

```python
# In app/main.py, uncomment rate limiting middleware
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# Apply to endpoints as needed
@app.post("/api/v1/sos/trigger")
@limiter.limit("5/minute")
async def trigger_sos(request: Request, ...):
    ...
```

---

## 🆘 Troubleshooting

### API Not Responding

```bash
# Check if container is running
docker-compose ps

# If not running, start it
docker-compose up -d api

# Check logs for errors
docker-compose logs api

# Verify database connection
docker-compose exec api python -c \
  "from app.database import SessionLocal; \
   db = SessionLocal(); \
   print(f'Connected: {db.execute(text(\"SELECT 1\")).fetchone()}')"

# Check API health
curl http://localhost:8000/health
```

### Database Connection Issues

```bash
# Check if database is running
docker-compose ps db

# If not, start it
docker-compose up -d db

# Verify connection string
echo $DATABASE_URL

# Test connection
docker-compose exec db psql -U $DB_USER -c "SELECT 1"

# View database logs
docker-compose logs db
```

### Dashboard Not Loading

```bash
# Check if dashboard is running
docker-compose ps dashboard

# If not, start it
docker-compose up -d dashboard

# Check logs
docker-compose logs dashboard

# Verify API proxy
curl http://localhost:3000/api/v1/auth/me

# Check browser console for errors
# Press F12 in browser → Console tab
```

### Performance Issues

```bash
# Check resource usage
docker stats

# If memory high, increase Docker limits
# Edit docker-compose.yml:
services:
  api:
    deploy:
      resources:
        limits:
          memory: 2G

# Restart with new limits
docker-compose up -d --build

# Check database queries
docker-compose exec api python -c \
  "import logging; \
   logging.basicConfig(level=logging.DEBUG); \
   from app.database import engine; \
   from sqlalchemy.pool import NullPool; \
   engine = create_engine(DATABASE_URL, echo=True)"
```

---

## 📈 Scaling Considerations

### Horizontal Scaling

For production with high load:

```yaml
# docker-compose.yml - Run multiple API instances

version: '3.8'
services:
  api-1:
    image: oceanguardian-api
    ports: ["8001:8000"]
  api-2:
    image: oceanguardian-api
    ports: ["8002:8000"]
  api-3:
    image: oceanguardian-api
    ports: ["8003:8000"]
  
  nginx:
    image: nginx:latest
    ports: ["80:80", "443:443"]
    volumes:
      - ./nginx-lb.conf:/etc/nginx/nginx.conf
    depends_on:
      - api-1
      - api-2
      - api-3
```

### Database Optimization

```sql
-- Add indices for common queries
CREATE INDEX idx_sos_status ON sos_alerts(status);
CREATE INDEX idx_sos_created ON sos_alerts(created_at);
CREATE INDEX idx_location_user ON location_pings(user_id);
CREATE INDEX idx_location_created ON location_pings(created_at);
CREATE INDEX idx_trips_active ON trips(fisherman_id) WHERE status = 'active';
```

### Caching Strategy

```python
# Add Redis caching (optional)
import redis
from functools import wraps

redis_client = redis.Redis(host='redis', port=6379, db=0)

def cache_result(ttl=300):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{args}:{kwargs}"
            cached = redis_client.get(key)
            if cached:
                return json.loads(cached)
            result = await func(*args, **kwargs)
            redis_client.setex(key, ttl, json.dumps(result))
            return result
        return wrapper
    return decorator
```

---

## 🔄 Maintenance Schedule

### Daily Tasks
- ✅ Monitor health endpoints
- ✅ Check error logs
- ✅ Verify backup completion

### Weekly Tasks
- ✅ Review application metrics
- ✅ Check database size
- ✅ Verify backup integrity
- ✅ Update Docker images

### Monthly Tasks
- ✅ Security audit
- ✅ Performance analysis
- ✅ Dependency updates
- ✅ Capacity planning

### Quarterly Tasks
- ✅ Load testing
- ✅ Disaster recovery drill
- ✅ Security penetration test
- ✅ Architecture review

---

## 📞 Support & Escalation

### Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| API timeout | Increase timeout in nginx.conf, check DB performance |
| Memory leak | Restart containers, review logs for large payloads |
| Disk space | Archive old logs, cleanup old backups |
| High CPU | Check for missing indices, add caching |
| SSL certificate expiration | Use Let's Encrypt with auto-renewal |

### Escalation Path

1. **Level 1:** Check health endpoints and logs
2. **Level 2:** Restart affected services
3. **Level 3:** Check database connectivity
4. **Level 4:** Review recent changes/deployments
5. **Level 5:** Engage development team

---

## 🚀 Continuous Deployment

### GitHub Actions Workflow (Optional)

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run tests
        run: cd backend && python -m pytest tests/ -v

  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Deploy to server
        run: |
          ssh deploy@server "cd /app && \
            git pull && \
            docker-compose up -d --build && \
            docker-compose exec api alembic upgrade head"
```

---

## ✅ Production Readiness Verification

```bash
#!/bin/bash
# Run this script before going live

echo "🔍 Checking system requirements..."
docker --version
docker-compose --version

echo "✅ Checking services..."
docker-compose ps

echo "✅ Checking health endpoints..."
curl -f http://localhost:8000/health || exit 1
curl -f http://localhost:3000 || exit 1

echo "✅ Running tests..."
docker-compose exec api python -m pytest tests/ -v

echo "✅ Checking backups..."
ls -lh /backups/ | tail -5

echo "✅ All checks passed! Ready for production."
```

---

## 📋 Go-Live Checklist

- [ ] All tests passing (12/12)
- [ ] Health checks operational
- [ ] Database backed up
- [ ] SSL certificate installed
- [ ] Environment variables configured
- [ ] Firewall rules in place
- [ ] Monitoring enabled
- [ ] Alerting configured
- [ ] Backup automation active
- [ ] Runbooks documented
- [ ] On-call rotation established
- [ ] Incident response plan ready

---

**End of Deployment Guide**

For questions or issues, refer to:
- API Docs: `/docs` endpoint
- Audit Report: `PHASE2_AUDIT_REPORT.md`
- Implementation Summary: `IMPLEMENTATION_SUMMARY.md`
- Main README: `README.md`
