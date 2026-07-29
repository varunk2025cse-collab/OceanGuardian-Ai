# Boat Management Implementation Plan
**OceanGuardian AI — Phased Delivery Plan**
**Version:** 1.0

---

## Phase 1 — Foundation (Week 1–2)
*Goal: Solid database and backend core. No UI yet.*

### Task 1.1 — Database Migration 009
**Priority:** P0 | **Effort:** 1 day | **Dependencies:** None

Extend `boats` table and create new tables:
- Add `status`, `vessel_class`, `hull_material`, `year_built`, `engine_make/model/serial`, `home_harbor_id`, `verification_status`, `qr_code_token`, `deleted_at`, `version`, `created_by`, `updated_by` to `boats`
- Create `boat_documents`, `boat_crew_members`, `boat_inspections`, `boat_equipment_items`, `boat_status_history`, `boat_audit_logs`, `boat_ownership_transfers`
- Fix `boat_maintenance` (add `status`, `completed_by`)
- Fix `boat_health_status` (add unique constraint)
- Add all indexes

**Acceptance criteria:**
- `alembic upgrade head` runs cleanly on both SQLite and PostgreSQL
- All existing tests still pass
- No existing data is lost or corrupted

---

### Task 1.2 — Extended Boat Model
**Priority:** P0 | **Effort:** 0.5 days | **Dependencies:** Task 1.1

Update `backend/app/models/boat.py`:
- Add all new columns
- Add `status` property with enum validation
- Add `is_trip_ready` computed property
- Add relationships to new tables

**Acceptance criteria:**
- Model reflects all new columns
- Existing `__init__` aliases preserved for backward compat

---

### Task 1.3 — Boat Service (Core)
**Priority:** P0 | **Effort:** 2 days | **Dependencies:** Task 1.2

Create `backend/app/services/boat_service.py`:
- `register_boat()` — with duplicate check (case-insensitive), QR token generation, audit log
- `update_boat()` — with version conflict detection, audit log
- `change_status()` — with state machine validation, status history, audit log
- `decommission_boat()` — soft delete with active trip check
- `verify_boat()` — operator/admin only
- `get_boat_for_user()` — RBAC-aware query

**Acceptance criteria:**
- All unit tests in `test_boat_service.py` pass
- Every write operation creates an audit log entry
- Status transitions enforce the state machine

---

### Task 1.4 — Trip Readiness Service
**Priority:** P0 | **Effort:** 1 day | **Dependencies:** Task 1.3

Create `backend/app/services/boat_readiness_service.py`:
- Evaluate all readiness rules
- Return structured `TripReadinessResult` with blocking issues, warnings, passed checks
- Integrate with existing `trip_service.py` to gate trip start

**Acceptance criteria:**
- All readiness tests pass
- Trip start blocked when blocking issues exist
- SOS never blocked by readiness check

---

### Task 1.5 — v2 Boats Router
**Priority:** P0 | **Effort:** 1.5 days | **Dependencies:** Task 1.3, 1.4

Create `backend/app/routers/v2/boats.py`:
- All 10 core endpoints (register, list, get, update, delete, status, verify, qr, readiness, fleet summary)
- Consistent response envelope
- Pagination on list endpoint
- Rate limiting on registration

**Acceptance criteria:**
- All API integration tests pass
- All authorization tests pass for all roles
- Swagger docs complete with descriptions

---

### Task 1.6 — Document Service & Router
**Priority:** P1 | **Effort:** 1.5 days | **Dependencies:** Task 1.1

Create `backend/app/services/boat_document_service.py` and `backend/app/routers/v2/boat_documents.py`:
- Upload with file hash computation
- List with expiry status
- Verify endpoint
- Expiry detection for readiness check integration

**Acceptance criteria:**
- Document upload stores file hash
- Expired documents flagged in readiness check
- Operator can verify documents

---

### Task 1.7 — Crew Service & Router
**Priority:** P1 | **Effort:** 1 day | **Dependencies:** Task 1.1

Create `backend/app/services/boat_crew_service.py` and `backend/app/routers/v2/boat_crew.py`:
- Assign crew with role validation (one captain rule)
- Remove crew (soft remove)
- List active crew

**Acceptance criteria:**
- One captain constraint enforced
- Crew visible to operator and linked family
- Removal sets `removed_at`, not hard delete

---

## Phase 2 — Flutter Mobile (Week 3–4)
*Goal: Complete mobile boat management UI.*

### Task 2.1 — Boat Model & Repository (Flutter)
**Priority:** P0 | **Effort:** 1 day | **Dependencies:** Phase 1 complete

Create `mobile/lib/models/boat.dart`, `crew_member.dart`, `boat_document.dart`
Create `mobile/lib/repositories/boat_repository.dart` (SQLite local store + outbox)

---

### Task 2.2 — Boat Service (Flutter)
**Priority:** P0 | **Effort:** 1 day | **Dependencies:** Task 2.1

Create `mobile/lib/services/boat_service.dart`:
- API calls with offline fallback
- Outbox queue for offline writes
- Sync on connectivity restore

---

### Task 2.3 — Boat List Screen
**Priority:** P0 | **Effort:** 1 day | **Dependencies:** Task 2.2

Implement `boat_list_screen.dart` per UI spec:
- Status badges (color + icon + text)
- Health score indicator
- Offline banner
- Tamil strings

---

### Task 2.4 — Boat Detail Screen
**Priority:** P0 | **Effort:** 1.5 days | **Dependencies:** Task 2.3

Implement `boat_detail_screen.dart`:
- Quick action grid
- Vessel details section
- Health score bar
- Document status summary
- QR code button

---

### Task 2.5 — Register Boat Screen
**Priority:** P0 | **Effort:** 1.5 days | **Dependencies:** Task 2.2

Implement `boat_register_screen.dart`:
- 4-step wizard
- Offline queuing
- Harbor selector with map

---

### Task 2.6 — Remaining Screens
**Priority:** P1 | **Effort:** 3 days | **Dependencies:** Task 2.4

Implement in parallel:
- `boat_documents_screen.dart`
- `boat_crew_screen.dart`
- `boat_equipment_screen.dart`
- `boat_maintenance_screen.dart`
- `boat_qr_screen.dart`
- `trip_readiness_screen.dart`

---

### Task 2.7 — Trip Start Integration
**Priority:** P0 | **Effort:** 0.5 days | **Dependencies:** Task 2.5, Task 1.4

Update `start_trip_screen.dart`:
- Add boat selector (list of user's active boats)
- Show readiness check before confirming trip start
- Block trip if blocking issues exist

---

## Phase 3 — Dashboard & Inspections (Week 5)
*Goal: Operator fleet view and inspection management.*

### Task 3.1 — Fleet View (React Dashboard)
**Priority:** P1 | **Effort:** 2 days | **Dependencies:** Phase 1 complete

Create `rescue-dashboard/src/pages/BoatsPage.jsx`:
- Fleet summary cards
- Boat cards grid with status, health, document status
- Filter by status, harbor
- Link to boat detail

---

### Task 3.2 — Inspection Service & Router
**Priority:** P1 | **Effort:** 1 day | **Dependencies:** Task 1.1

Create inspection service and router:
- Record inspection
- List inspections
- Integrate with readiness check

---

### Task 3.3 — Equipment Service & Router
**Priority:** P1 | **Effort:** 1 day | **Dependencies:** Task 1.1

Create equipment service and router:
- Add/update/list equipment items
- Mandatory item check for readiness

---

## Phase 4 — AI & Advanced Features (Week 6)
*Goal: AI health prediction, maintenance prediction, vessel risk score.*

### Task 4.1 — AI Boat Service
**Priority:** P2 | **Effort:** 2 days | **Dependencies:** Phase 1 complete

Create `backend/app/services/boat_ai_service.py`:
- Health prediction (rule-based + optional LLM explanation)
- Maintenance prediction
- Equipment recommendation
- Vessel risk score

---

### Task 4.2 — Ownership Transfer Workflow
**Priority:** P2 | **Effort:** 1 day | **Dependencies:** Task 1.1

Implement transfer initiation, approval, and completion.

---

## Delivery Summary

| Phase | Duration | Deliverables |
|---|---|---|
| Phase 1 | 2 weeks | Database, backend services, all APIs |
| Phase 2 | 2 weeks | Complete Flutter mobile UI |
| Phase 3 | 1 week | Dashboard fleet view, inspections, equipment |
| Phase 4 | 1 week | AI features, ownership transfer |
| **Total** | **6 weeks** | **Production-ready Boat Management module** |
