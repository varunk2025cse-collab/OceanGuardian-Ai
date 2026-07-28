# OceanGuardian AI — Phase 5 Architecture
## AI Intelligence Layer

**Status:** Planning & Design  
**Date:** June 24, 2024  
**Goal:** Transform MVP into Intelligent Marine Assistant Platform

---

## 🎯 Vision

Evolve OceanGuardian AI from a **reactive** marine safety system into a **proactive, intelligent** assistant that:
- Predicts risks before they occur
- Provides AI-powered guidance
- Monitors safety automatically
- Offers smart recommendations
- Learns from incidents

---

## 📋 Phase 5 Components

### 1. AI Marine Copilot 🤖

**Purpose:** Conversational AI assistant for Tamil-speaking fishermen

**Capabilities:**
- Tamil voice input (speech-to-text)
- Response generation (contextual)
- Tamil voice output (text-to-speech)
- English fallback
- Real-time weather explanation
- Risk assessment explanation
- Navigation guidance
- Scheme information

**Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│                     AI COPILOT SERVICE                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ Voice Layer (Mobile)                                │ │
│  │ - Audio recording (flutter_sound)                   │ │
│  │ - Audio transmission (WebSocket)                    │ │
│  └─────────────────────┬────────────────────────────────┘ │
│                        │                                    │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ Speech-to-Text                                      │ │
│  │ - Google Cloud Speech-to-Text API                   │ │
│  │ - Tamil language support                            │ │
│  │ - Real-time streaming                               │ │
│  └─────────────────────┬────────────────────────────────┘ │
│                        │                                    │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ Intent & Context Processing                         │ │
│  │ - NLP parsing (spaCy/Rasa)                           │ │
│  │ - Intent classification                             │ │
│  │ - Entity extraction                                 │ │
│  │ - Context management (Redis)                        │ │
│  └─────────────────────┬────────────────────────────────┘ │
│                        │                                    │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ Response Generation                                 │ │
│  │ - Template-based responses                          │ │
│  │ - Context-aware suggestions                         │ │
│  │ - Real-time data integration                        │ │
│  └─────────────────────┬────────────────────────────────┘ │
│                        │                                    │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ Text-to-Speech                                      │ │
│  │ - Google Cloud Text-to-Speech API                   │ │
│  │ - Natural Tamil pronunciation                       │ │
│  │ - Audio streaming                                   │ │
│  └─────────────────────┬────────────────────────────────┘ │
│                        │                                    │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ Voice Output (Mobile)                               │ │
│  │ - Audio playback                                    │ │
│  │ - Real-time streaming                               │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**API Endpoints:**

```python
POST   /api/v2/copilot/voice/start      # Start voice session
POST   /api/v2/copilot/voice/stream     # WebSocket for real-time
GET    /api/v2/copilot/audio/{session}  # Get response audio
POST   /api/v2/copilot/text             # Text-based query
GET    /api/v2/copilot/context          # Get conversation context
DELETE /api/v2/copilot/session           # End session
```

**Database Schema:**

```sql
CREATE TABLE copilot_sessions (
  id UUID PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  language VARCHAR(10) DEFAULT 'ta',
  context JSONB,
  created_at TIMESTAMP,
  ended_at TIMESTAMP,
  duration_seconds INTEGER
);

CREATE TABLE copilot_conversations (
  id UUID PRIMARY KEY,
  session_id UUID REFERENCES copilot_sessions(id),
  user_message TEXT,
  ai_response TEXT,
  intent VARCHAR(50),
  entities JSONB,
  confidence FLOAT,
  timestamp TIMESTAMP
);
```

---

### 2. Smart Risk Prediction Engine 🔮

**Purpose:** ML-based risk prediction beyond Green/Yellow/Red

**Upgrade from current:**
- Current: Static risk rules (Green/Yellow/Red)
- New: Dynamic ML-based predictions
- Current: No history analysis
- New: Learns from incidents

**Architecture:**

```
INPUTS:
┌─────────────────────────────┐
│ Historical Data             │
│ - Past SOS incidents        │
│ - Accident records          │
│ - Weather patterns          │
│ - Trip outcomes             │
└────────────┬────────────────┘
             │
┌────────────▼────────────────┐
│ Real-time Data              │
│ - Current weather           │
│ - GPS location              │
│ - Boat condition            │
│ - Trip duration             │
│ - Sea conditions            │
└────────────┬────────────────┘
             │
┌────────────▼────────────────────────────────────────┐
│ ML MODEL (XGBoost/LSTM)                             │
│ Trained on historical incidents & weather patterns │
└────────────┬─────────────────────────────────────────┘
             │
┌────────────▼────────────────┐
│ Risk Score                  │
│ - Probability (0-100%)      │
│ - Risk factors              │
│ - Recommendations           │
│ - Time to escalation        │
└────────────┬────────────────┘
             │
OUTPUTS:
┌────────────▼──────────────────┐
│ Risk Level                     │
│ - CRITICAL (>80%)             │
│ - HIGH (60-80%)               │
│ - MEDIUM (40-60%)             │
│ - LOW (20-40%)                │
│ - SAFE (<20%)                 │
└────────────────────────────────┘
```

**Database Schema:**

```sql
CREATE TABLE risk_predictions (
  id UUID PRIMARY KEY,
  trip_id INTEGER REFERENCES trips(id),
  user_id INTEGER REFERENCES users(id),
  risk_score FLOAT,
  risk_level VARCHAR(20),
  risk_factors JSONB,
  recommendations TEXT ARRAY,
  model_version VARCHAR(20),
  created_at TIMESTAMP
);

CREATE TABLE risk_incidents (
  id UUID PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  incident_type VARCHAR(50),
  severity INTEGER,
  weather_conditions JSONB,
  boat_info JSONB,
  location POINT,
  created_at TIMESTAMP
);

CREATE TABLE model_metrics (
  id UUID PRIMARY KEY,
  model_version VARCHAR(20),
  accuracy FLOAT,
  precision FLOAT,
  recall FLOAT,
  f1_score FLOAT,
  test_date TIMESTAMP
);
```

**API Endpoints:**

```python
POST   /api/v2/risk/predict           # Get risk prediction
GET    /api/v2/risk/history/{user_id} # Risk history
GET    /api/v2/risk/factors/{trip_id} # Risk factors analysis
POST   /api/v2/risk/report-incident   # Report incident (for training)
GET    /api/v2/risk/model/metrics     # Model performance
```

---

### 3. Smart Check-in System ✅

**Purpose:** Automatic safety monitoring without user intervention

**Workflow:**

```
BACKGROUND JOB (every 5 minutes):

┌─────────────────────────────────────┐
│ Check Active Trips                  │
└────────────┬────────────────────────┘
             │
┌────────────▼────────────────────────┐
│ For each trip:                      │
│ 1. Check last GPS update time       │
│ 2. Check for movement               │
│ 3. Check online/offline status      │
└────────────┬────────────────────────┘
             │
      ┌──────┴──────┐
      │             │
┌─────▼──────┐ ┌───▼──────────┐
│ All OK?    │ │ Problem?     │
└─────┬──────┘ └───┬──────────┘
      │           │
      │    ┌──────┴────────────────────┐
      │    │                           │
      │ ┌──▼──────────────┐ ┌─────────▼──────┐
      │ │ No GPS (15min)  │ │ No movement    │
      │ │ → Warning       │ │ (30min+)       │
      │ │ → Notify family │ │ → Alert        │
      │ └─────────────────┘ │ → Check-in     │
      │                     └────────────────┘
      │
      │ ┌──────────────────────────┐
      │ │ Long offline (1hr)       │
      │ │ → Emergency alert        │
      │ │ → Notify rescue          │
      │ │ → Raise SOS concern      │
      │ └──────────────────────────┘
      │
      └──► Update check_in_status
```

**Database Schema:**

```sql
CREATE TABLE check_in_logs (
  id UUID PRIMARY KEY,
  trip_id INTEGER REFERENCES trips(id),
  user_id INTEGER REFERENCES users(id),
  status VARCHAR(20), -- ok, warning, alert, emergency
  last_gps_time TIMESTAMP,
  time_since_update INTEGER, -- seconds
  last_location POINT,
  check_in_reason TEXT,
  action_taken TEXT,
  notifications_sent JSONB,
  created_at TIMESTAMP
);

CREATE TABLE check_in_alerts (
  id UUID PRIMARY KEY,
  trip_id INTEGER REFERENCES trips(id),
  alert_type VARCHAR(50),
  severity INTEGER,
  recipients JSONB,
  status VARCHAR(20), -- pending, sent, acknowledged
  created_at TIMESTAMP,
  acknowledged_at TIMESTAMP
);
```

**API Endpoints:**

```python
GET    /api/v2/checkin/status/{user_id}     # Current check-in status
GET    /api/v2/checkin/history/{trip_id}    # Check-in history
POST   /api/v2/checkin/manual/{trip_id}     # Manual check-in
GET    /api/v2/checkin/alerts/{user_id}     # Pending alerts
POST   /api/v2/checkin/acknowledge/{alert}  # Acknowledge alert
```

---

### 4. Harbor Intelligence 🏖️

**Purpose:** Smart harbor recommendations and guidance

**Features:**

```
HARBOR DATABASE:
├── Location (lat, lon)
├── Name & Description
├── Services Available
│   ├── Fuel
│   ├── Medical
│   ├── Food
│   ├── Repair
│   ├── Shelter
│   └── Emergency
├── Operating Hours
├── Contact Information
├── Historical Safety Data
└── Distance from Popular Fishing Zones

SMART RECOMMENDATION LOGIC:

IF current_trip_has_risk():
    RETURN nearest_harbor_with_medical
    
IF low_fuel():
    RETURN nearest_harbor_with_fuel
    
IF emergency():
    RETURN nearest_harbor_with_emergency_services
    
IF weather_deteriorating():
    RETURN safest_harbor_ahead_in_direction
    
IF regular_trip():
    RETURN nearest_harbor_by_ETA
```

**Database Schema:**

```sql
CREATE TABLE harbors (
  id SERIAL PRIMARY KEY,
  name VARCHAR(255),
  state VARCHAR(50),
  country VARCHAR(50),
  location POINT,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  services JSONB,
  operating_hours JSONB,
  contact_info JSONB,
  medical_facility BOOLEAN,
  fuel_available BOOLEAN,
  emergency_services BOOLEAN,
  description TEXT,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE harbor_reviews (
  id SERIAL PRIMARY KEY,
  harbor_id INTEGER REFERENCES harbors(id),
  user_id INTEGER REFERENCES users(id),
  rating INTEGER,
  review_text TEXT,
  safety_rating INTEGER,
  created_at TIMESTAMP
);

CREATE TABLE harbor_visits (
  id UUID PRIMARY KEY,
  harbor_id INTEGER REFERENCES harbors(id),
  trip_id INTEGER REFERENCES trips(id),
  arrival_time TIMESTAMP,
  departure_time TIMESTAMP,
  reason VARCHAR(50),
  services_used JSONB
);
```

**API Endpoints:**

```python
GET    /api/v2/harbors/list                 # All harbors
GET    /api/v2/harbors/nearest              # Nearest harbor
GET    /api/v2/harbors/{harbor_id}          # Harbor details
GET    /api/v2/harbors/recommend            # Smart recommendation
GET    /api/v2/harbors/{id}/reviews         # Harbor reviews
POST   /api/v2/harbors/{id}/review          # Add review
GET    /api/v2/harbors/search               # Search harbors
```

---

### 5. Fuel & Boat Health System ⛽

**Purpose:** Fuel tracking and maintenance management

**Features:**

```
FUEL MANAGEMENT:
├── Track fuel level (liters)
├── Estimate fuel consumption
├── Predict fuel depletion time
├── Alert low fuel
├── Suggest refuel points
└── Track refueling history

BOAT HEALTH:
├── Engine hours tracking
├── Last service date
├── Maintenance schedule
├── Service history
├── Parts replacement
├── Inspection status
└── Health status
```

**Database Schema:**

```sql
CREATE TABLE boat_fuel_logs (
  id UUID PRIMARY KEY,
  boat_id INTEGER REFERENCES boats(id),
  fuel_level_liters FLOAT,
  fuel_consumption_per_hour FLOAT,
  recorded_time TIMESTAMP,
  location POINT,
  trip_id INTEGER REFERENCES trips(id)
);

CREATE TABLE fuel_predictions (
  id UUID PRIMARY KEY,
  trip_id INTEGER REFERENCES trips(id),
  current_fuel_liters FLOAT,
  consumption_rate FLOAT,
  hours_remaining FLOAT,
  depletion_time TIMESTAMP,
  alert_threshold FLOAT,
  created_at TIMESTAMP
);

CREATE TABLE boat_maintenance (
  id UUID PRIMARY KEY,
  boat_id INTEGER REFERENCES boats(id),
  engine_hours INTEGER,
  service_type VARCHAR(50),
  service_date TIMESTAMP,
  service_provider VARCHAR(255),
  cost DECIMAL,
  parts_replaced TEXT ARRAY,
  description TEXT,
  next_service_due DATE
);

CREATE TABLE boat_health_status (
  id UUID PRIMARY KEY,
  boat_id INTEGER REFERENCES boats(id),
  engine_condition VARCHAR(20),
  hull_condition VARCHAR(20),
  fuel_system_status VARCHAR(20),
  electrical_status VARCHAR(20),
  overall_status VARCHAR(20),
  last_inspection DATE,
  next_inspection_due DATE,
  notes TEXT
);
```

**API Endpoints:**

```python
POST   /api/v2/boats/{id}/fuel/log          # Log fuel level
GET    /api/v2/boats/{id}/fuel/current      # Current fuel info
GET    /api/v2/boats/{id}/fuel/prediction   # Fuel depletion prediction
POST   /api/v2/boats/{id}/maintenance       # Add maintenance record
GET    /api/v2/boats/{id}/maintenance       # Maintenance history
GET    /api/v2/boats/{id}/health            # Boat health status
POST   /api/v2/boats/{id}/inspection        # Record inspection
```

---

### 6. Advanced Family Safety Portal 👨‍👩‍👧

**Purpose:** Enhanced family member experience and safety features

**Features:**

```
FAMILY PORTAL FEATURES:

├── Real-time Location
│   ├── Live map tracking
│   ├── Last known location
│   ├── GPS history
│   └── Estimated arrival time

├── Trip Progress
│   ├── Trip status (active/completed)
│   ├── Departure time
│   ├── Estimated return time
│   ├── Current ETA
│   └── Progress timeline

├── Check-in Status
│   ├── Latest check-in time
│   ├── Status level (ok/warning/alert)
│   ├── Time since last contact
│   └── Action recommendations

├── Safety Notifications
│   ├── Real-time alerts
│   ├── Weather warnings
│   ├── Risk level changes
│   ├── Check-in warnings
│   └── SOS alerts

├── Emergency Timeline
│   ├── Incident history
│   ├── SOS activations
│   ├── Rescue actions taken
│   ├── Current status
│   └── Estimated resolution time

└── Communication
    ├── Send messages
    ├── Call fisherman
    ├── Contact rescue
    └── Emergency buttons
```

**Database Schema:**

```sql
CREATE TABLE family_portal_access (
  id UUID PRIMARY KEY,
  family_user_id INTEGER REFERENCES users(id),
  fisherman_id INTEGER REFERENCES users(id),
  access_level VARCHAR(50), -- view_all, view_summary, view_emergency_only
  notification_preferences JSONB,
  created_at TIMESTAMP
);

CREATE TABLE family_safety_events (
  id UUID PRIMARY KEY,
  family_user_id INTEGER REFERENCES users(id),
  fisherman_id INTEGER REFERENCES users(id),
  event_type VARCHAR(50),
  event_description TEXT,
  severity INTEGER,
  notification_sent BOOLEAN,
  read BOOLEAN,
  created_at TIMESTAMP,
  read_at TIMESTAMP
);

CREATE TABLE family_notifications (
  id UUID PRIMARY KEY,
  family_user_id INTEGER REFERENCES users(id),
  notification_type VARCHAR(50),
  title TEXT,
  message TEXT,
  data JSONB,
  delivery_method VARCHAR(20), -- push, email, sms
  delivery_status VARCHAR(20),
  created_at TIMESTAMP,
  delivered_at TIMESTAMP
);
```

**API Endpoints:**

```python
GET    /api/v2/family/dashboard             # Family dashboard data
GET    /api/v2/family/{fisherman_id}/location # Live location
GET    /api/v2/family/{fisherman_id}/trip   # Trip progress
GET    /api/v2/family/{fisherman_id}/checkin # Check-in status
GET    /api/v2/family/{fisherman_id}/alerts # Recent alerts
POST   /api/v2/family/message               # Send message
GET    /api/v2/family/notifications         # Get notifications
POST   /api/v2/family/emergency             # Emergency contact
```

---

### 7. Analytics Engine 📊

**Purpose:** Comprehensive analytics dashboard for insights

**Metrics:**

```
SOS ANALYTICS:
├── Total SOS incidents (monthly/yearly)
├── SOS trends
├── Average response time
├── Resolution rate
├── By location
├── By time of day
├── By weather conditions
└── By incident type

RISK ANALYTICS:
├── Risk level distribution
├── High-risk areas
├── High-risk times
├── Risk factors correlation
├── Trend analysis
└── Predictive risk

TRIP ANALYTICS:
├── Total trips
├── Average duration
├── Active trips
├── Completion rate
├── Popular fishing zones
├── Trip distance distribution
└── Seasonal trends

HARBOR ANALYTICS:
├── Most visited harbors
├── Services usage
├── Usage by time
├── Popular routes
└── Emergency usage

FAMILY ANALYTICS:
├── Active family members
├── Notification usage
├── Portal engagement
├── Check-in patterns
└── Alert response times
```

**Database Schema:**

```sql
CREATE TABLE analytics_sos_events (
  id UUID PRIMARY KEY,
  sos_id INTEGER REFERENCES sos_alerts(id),
  user_id INTEGER REFERENCES users(id),
  event_type VARCHAR(50),
  location POINT,
  weather_conditions JSONB,
  response_time_minutes INTEGER,
  resolution_status VARCHAR(20),
  created_at TIMESTAMP
);

CREATE TABLE analytics_trips (
  id UUID PRIMARY KEY,
  trip_id INTEGER REFERENCES trips(id),
  duration_minutes INTEGER,
  distance_km FLOAT,
  start_location POINT,
  end_location POINT,
  catch_info JSONB,
  fuel_consumed_liters FLOAT,
  risk_level_average VARCHAR(20),
  incidents_count INTEGER,
  created_at TIMESTAMP
);

CREATE TABLE analytics_dashboard_metrics (
  id UUID PRIMARY KEY,
  metric_date DATE,
  total_active_users INTEGER,
  total_active_trips INTEGER,
  total_sos_events INTEGER,
  average_response_time FLOAT,
  high_risk_areas JSONB,
  weather_alerts_sent INTEGER,
  check_in_warnings INTEGER,
  family_portal_active_users INTEGER
);
```

**API Endpoints:**

```python
GET    /api/v2/analytics/sos               # SOS analytics
GET    /api/v2/analytics/risk              # Risk analytics
GET    /api/v2/analytics/trips             # Trip analytics
GET    /api/v2/analytics/harbors           # Harbor analytics
GET    /api/v2/analytics/family            # Family analytics
GET    /api/v2/analytics/dashboard         # Dashboard metrics
GET    /api/v2/analytics/export            # Export data
```

---

## 🏗️ Integration Points with Existing System

### Phase 5 integrates with:

1. **Existing Trips**
   - Check-in system monitors active trips
   - Risk prediction considers trip data
   - Analytics aggregates trip metrics

2. **Existing SOS System**
   - Smart check-in may raise SOS concerns
   - Risk prediction informs SOS priority
   - Analytics tracks SOS patterns

3. **Existing Locations**
   - Check-in uses location updates
   - Risk engine uses GPS data
   - Harbor recommendations use location

4. **Existing Users**
   - Copilot provides personalized responses
   - Family portal serves family members
   - Analytics tracks user behavior

5. **Existing Boats**
   - Fuel system tracks boat consumption
   - Boat health tracks maintenance
   - Risk prediction considers boat condition

---

## 📊 Data Flow Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    MOBILE APP (Flutter)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ Voice Input │  │ GPS Updates │  │ Fuel Logs   │             │
│  └────────┬────┘  └────────┬────┘  └────────┬────┘             │
└──────────┼─────────────────┼─────────────────┼──────────────────┘
           │                 │                 │
           └─────────────────┼─────────────────┘
                             │
┌───────────────────────────▼────────────────────────────────────┐
│                    API GATEWAY (FastAPI)                        │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ WebSocket Handler│  │ REST Endpoints   │                │
│  │ - Voice streaming│  │ - Check-in      │                │
│  │ - Real-time data │  │ - Risk predict  │                │
│  └────────┬─────────┘  │ - Harbor find   │                │
│           │            │ - Fuel track    │                │
│           │            └────────┬────────┘                │
│           └─────────────┬───────┘                         │
└───────────────────────┼─────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
┌───────▼──────┐ ┌─────▼──────┐ ┌─────▼──────┐
│ Copilot      │ │ Risk Engine│ │ Check-in   │
│ Service      │ │ Service    │ │ Service    │
└───────┬──────┘ └─────┬──────┘ └─────┬──────┘
        │              │              │
        └──────────┬───┴───┬──────────┘
                   │       │
        ┌──────────▼──┬────▼─────────┐
        │             │              │
   ┌────▼────┐   ┌───▼───┐   ┌─────▼────┐
   │PostgreSQL│   │Redis  │   │Elasticsearch│
   │(Prod DB) │   │(Cache)│   │(Logs)      │
   └──────────┘   └───────┘   └────────────┘
```

---

## 🚀 Implementation Roadmap

### Week 1-2: Foundation
- [ ] Database migrations (all new tables)
- [ ] API framework setup (v2 endpoints)
- [ ] External service integrations (Google Cloud APIs)
- [ ] Background job framework (Celery)

### Week 3-4: Core Services
- [ ] Implement copilot service
- [ ] Implement risk prediction engine
- [ ] Implement check-in system
- [ ] Implement harbor intelligence

### Week 5: Enhancement Services
- [ ] Implement fuel tracking
- [ ] Implement family portal
- [ ] Implement analytics engine

### Week 6: Integration & Testing
- [ ] Integrate all services
- [ ] End-to-end testing
- [ ] Performance optimization
- [ ] Security audit

### Week 7: Deployment
- [ ] Staging deployment
- [ ] Production deployment
- [ ] Monitoring setup
- [ ] Documentation

---

## ✅ Success Criteria

- [ ] All 7 services deployed
- [ ] All APIs tested (100% endpoint coverage)
- [ ] Voice input/output working in Tamil
- [ ] Risk prediction ML model trained and validated
- [ ] Check-in system catching edge cases
- [ ] Family portal fully functional
- [ ] Analytics dashboard operational
- [ ] Backward compatibility maintained
- [ ] Performance > 95% uptime
- [ ] Zero breaking changes to existing APIs

---

**Next:** Phase 5 Implementation Details (APIs, Database Migrations, Code)
