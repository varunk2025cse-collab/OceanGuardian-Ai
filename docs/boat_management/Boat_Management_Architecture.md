# Boat Management Architecture
**OceanGuardian AI — Engineering Design**
**Version:** 1.0 | **Status:** Approved for Implementation

---

## 1. Design Philosophy

The Boat Management module is not a CRUD service. It is the **vessel identity and safety compliance layer** of the OceanGuardian platform. Every other module — Trip Management, GPS Tracking, SOS, Family Portal, Rescue Operations, Government Reporting — depends on the boat record being accurate, verified, and current.

Every design decision answers: **"Will this improve safety, reliability, maintainability, or usability for fishermen?"**

---

## 2. Module Boundaries

```
┌─────────────────────────────────────────────────────────────────┐
│                    BOAT MANAGEMENT MODULE                        │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Vessel      │  │  Compliance  │  │  Health & Operations │  │
│  │  Identity    │  │  & Documents │  │                      │  │
│  │              │  │              │  │  - Fuel tracking     │  │
│  │  - Register  │  │  - License   │  │  - Maintenance       │  │
│  │  - Verify    │  │  - Insurance │  │  - Engine hours      │  │
│  │  - Transfer  │  │  - Inspection│  │  - Health score      │  │
│  │  - Status    │  │  - Equipment │  │  - Trip readiness    │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Crew        │  │  Audit &     │  │  AI & Intelligence   │  │
│  │  Management  │  │  History     │  │                      │  │
│  │              │  │              │  │  - Health prediction │  │
│  │  - Assign    │  │  - Audit log │  │  - Maintenance pred. │  │
│  │  - Roles     │  │  - Status    │  │  - Risk score        │  │
│  │  - Remove    │  │    history   │  │  - Trip readiness    │  │
│  │  - Emergency │  │  - QR/NFC    │  │    score             │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
   Trip Management      SOS / Rescue        Government
   (trip readiness      (boat context       Reporting
    gate)               in incidents)       (compliance
                                            export)
```

---

## 3. Boat Status Lifecycle

```
                    ┌─────────────┐
                    │  REGISTERED │ (initial state — pending verification)
                    └──────┬──────┘
                           │ verified by authority
                           ▼
                    ┌─────────────┐
              ┌────►│   ACTIVE    │◄────────────────────┐
              │     └──────┬──────┘                     │
              │            │                            │
              │     ┌──────┴──────┐                     │
              │     │             │                     │
              │     ▼             ▼                     │
              │ ┌──────────┐ ┌──────────┐               │
              │ │MAINTENANCE│ │EMERGENCY │               │
              │ └────┬─────┘ └────┬─────┘               │
              │      │            │                     │
              └──────┘            │ resolved            │
                                  └─────────────────────┘
                    │
              ┌─────┴──────┐
              │             │
              ▼             ▼
         ┌────────┐   ┌──────────┐
         │  LOST  │   │ DAMAGED  │
         └────┬───┘   └────┬─────┘
              │            │
              └─────┬──────┘
                    │ beyond repair / retired
                    ▼
             ┌─────────────┐
             │DECOMMISSIONED│ (soft delete — data preserved)
             └─────────────┘

Also valid from ACTIVE:
  ACTIVE → INACTIVE (owner suspends operations)
  INACTIVE → ACTIVE (owner resumes)
```

**State Transition Rules:**
- Only `ACTIVE` boats can start a trip
- `MAINTENANCE` boats cannot start a trip
- `EMERGENCY` state is set by the system when an SOS is active on this boat
- `DECOMMISSIONED` is a soft delete — all historical data is preserved
- All transitions are recorded in `boat_status_history`

---

## 4. Trip Readiness Gate

Before any trip can start, the system evaluates the boat against these rules:

```
TRIP READINESS CHECK
─────────────────────────────────────────────────────────
Rule                          | Block | Warn | Skip
─────────────────────────────────────────────────────────
Boat status = ACTIVE          | YES   |      |
Fishing license not expired   | YES   |      |
Insurance not expired         | YES   |      |
Last safety inspection < 1yr  |       | YES  |
Safety equipment checklist    |       | YES  |
Fuel level > 20%              |       | YES  |
Engine not marked DAMAGED     | YES   |      |
Crew minimum (≥1 person)      |       | YES  |
GPS device available          |       | YES  |
─────────────────────────────────────────────────────────
BLOCK = trip cannot start
WARN  = trip can start with user acknowledgment
SKIP  = not checked (data unavailable)
```

**Business Rule:** Manual SOS is NEVER blocked by trip readiness. Safety-critical paths do not depend on compliance state.

---

## 5. Component Architecture

```
backend/
  app/
    models/
      boat.py              ← Extended Boat model (status, soft delete, versioning)
      boat_documents.py    ← BoatDocument, BoatLicense, BoatInsurance
      boat_crew.py         ← CrewMember, CrewRole
      boat_inspection.py   ← BoatInspection, EquipmentItem
      boat_audit.py        ← BoatAuditLog, BoatStatusHistory
    schemas/
      boat.py              ← Extended schemas (BoatCreate, BoatOut, BoatDetail)
      boat_documents.py    ← Document schemas
      boat_crew.py         ← Crew schemas
      boat_readiness.py    ← TripReadinessCheck schema
    services/
      boat_service.py      ← Core boat CRUD + status transitions
      boat_document_service.py  ← Document management
      boat_crew_service.py      ← Crew assignment
      boat_readiness_service.py ← Trip readiness evaluation
      boat_health.py            ← Existing — extended
      boat_ai_service.py        ← AI health prediction, maintenance prediction
    routers/
      v2/
        boats.py           ← New v2 boat router (replaces v1)
        boat_documents.py  ← Document endpoints
        boat_crew.py       ← Crew endpoints
        boat_readiness.py  ← Readiness check endpoint
        boat_health.py     ← Existing — extended

mobile/
  lib/
    models/
      boat.dart            ← Boat model (offline-capable)
      boat_document.dart   ← Document model
      crew_member.dart     ← Crew model
    screens/
      boats/
        boat_list_screen.dart
        boat_detail_screen.dart
        boat_register_screen.dart
        boat_edit_screen.dart
        boat_documents_screen.dart
        boat_crew_screen.dart
        boat_equipment_screen.dart
        boat_maintenance_screen.dart
        boat_qr_screen.dart
    services/
      boat_service.dart    ← API client + offline cache
    repositories/
      boat_repository.dart ← SQLite local store

rescue-dashboard/
  src/
    pages/
      BoatsPage.jsx        ← Fleet view for operators
    components/
      boats/
        BoatCard.jsx
        BoatStatusBadge.jsx
        BoatReadinessPanel.jsx
        BoatDocumentStatus.jsx
```

---

## 6. Backward Compatibility Strategy

The existing `boats` table and v1 API are preserved. The redesign adds:

1. **New columns** to `boats` via Alembic migration 009 (all nullable or with defaults)
2. **New tables** for documents, crew, inspection, audit
3. **New v2 router** at `/api/v2/boats/` — v1 remains functional
4. **v1 router** gets a deprecation header but continues to work

No existing data is deleted. No existing FK relationships are broken.

---

## 7. Offline Architecture

```
Flutter App
─────────────────────────────────────────────────────────
Online Mode:
  API call → backend → response → update local SQLite cache

Offline Mode:
  Read: serve from SQLite cache (with STALE indicator)
  Write: queue in outbox table → sync when online

Outbox table (local SQLite):
  id, entity_type, entity_id, operation, payload_json,
  created_at, synced_at, retry_count, error

Conflict resolution:
  Server wins on registration_number, status, documents
  Client wins on fuel logs, maintenance notes (append-only)
  Last-write-wins with server timestamp on profile fields
```

---

## 8. Security Architecture

```
Role → Boat Access Matrix
─────────────────────────────────────────────────────────────────
                    Own Boat  Other Boats  Fleet View  Admin
─────────────────────────────────────────────────────────────────
fisherman           RW        —            —           —
family              R*        —            —           —
operator            R         R            R           —
admin               RW        RW           RW          RW
government          R         R            R           R
─────────────────────────────────────────────────────────────────
R = read, W = write, * = only linked fisherman's boat
```

**Audit:** Every write to `boats`, `boat_documents`, `boat_crew`, `boat_status_history` creates an entry in `boat_audit_logs`.

---

## 9. AI Integration Points

| AI Feature | Input | Output | Confidence |
|---|---|---|---|
| Health prediction | engine_hours, maintenance history, fuel logs | predicted_health_score, days_to_critical | Yes |
| Maintenance prediction | last_service_date, engine_hours, trip_count | next_service_date, maintenance_type | Yes |
| Trip readiness score | all readiness checks | 0–100 score + explanation | Yes |
| Risk score | incident history, maintenance state, age | vessel_risk_level | Yes |
| Equipment recommendation | vessel_class, fishing_zone, season | recommended_equipment_list | Yes |

All AI outputs include:
- `confidence_score` (0.0–1.0)
- `explanation` (plain language, Tamil + English)
- `human_override` flag
- `model_version`

---

## 10. QR Code Strategy

Each registered boat gets a unique QR code containing:
```json
{
  "boat_id": 123,
  "registration_number": "TN-MFB-2024-001",
  "owner_name": "Murugan K",
  "emergency_contact": "+91-9876543210",
  "platform": "oceanguardian",
  "version": "1"
}
```

QR code is:
- Generated on registration
- Regenerated on ownership transfer
- Scannable by Coast Guard, harbor officers, rescue teams
- Displayed in the Flutter app (offline-capable)
- Printable as a physical card

NFC support is defined as a future seam — the same payload is used.
