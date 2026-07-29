# Boat Management Audit Report
**OceanGuardian AI — Engineering Team Review**
**Date:** 2025 | **Status:** Pre-Implementation Audit

---

## 1. Executive Summary

The existing Boat Management module is a functional but minimal CRUD scaffold. It was built as a Phase 2 addition to support trip management and is not designed as a standalone, production-grade module. It lacks the depth required for government adoption, Coast Guard integration, or fisheries department use. This audit documents every gap, risk, and technical debt item before redesign begins.

---

## 2. Current Functionality Inventory

### 2.1 What Exists

| Component | Location | Status |
|---|---|---|
| Boat model (SQLAlchemy) | `backend/app/models/boat.py` | Minimal — 10 fields |
| Boat router (CRUD) | `backend/app/routers/boats.py` | 4 endpoints only |
| Boat schema (Pydantic) | `backend/app/schemas/boat.py` | Basic — no validation depth |
| Boat health service | `backend/app/services/boat_health.py` | Fuel + maintenance scoring |
| Boat health router (v2) | `backend/app/routers/v2/boat_health.py` | 6 endpoints |
| Phase 5 models | `backend/app/models/phase5.py` | BoatFuelLog, BoatMaintenance, BoatHealthStatus, FuelPrediction |
| Alembic migration 002 | `alembic/versions/002_...` | Creates boats table |
| Boat health tests | `tests/test_boat_health_service.py` | 9 tests — fuel + maintenance + health score |
| Flutter mobile | `mobile/lib/` | **No boat management screens exist** |
| Rescue dashboard | `rescue-dashboard/src/` | Shows `boat_name` from user profile only — no boat entity |

### 2.2 Current API Endpoints

| Method | URL | Purpose |
|---|---|---|
| POST | `/api/v1/boats/` | Register boat |
| GET | `/api/v1/boats/` | List my boats |
| GET | `/api/v1/boats/{id}` | Get boat |
| PATCH | `/api/v1/boats/{id}` | Update boat |
| POST | `/api/v2/boat-health/fuel-log` | Log fuel |
| GET | `/api/v2/boat-health/{id}/fuel-summary` | Fuel summary |
| POST | `/api/v2/boat-health/maintenance` | Create maintenance record |
| GET | `/api/v2/boat-health/{id}/maintenance-due` | Maintenance due |
| GET | `/api/v2/boat-health/{id}/health-score` | Health score |
| POST | `/api/v2/boat-health/{id}/update-engine-hours` | Update engine hours |

---

## 3. Missing Functionality

### 3.1 Critical Missing Features (P0)

| # | Missing Feature | Impact |
|---|---|---|
| 1 | Boat status lifecycle (Active/Inactive/Maintenance/Emergency/Lost/Damaged/Decommissioned) | Cannot block unsafe trips |
| 2 | Boat documents (registration certificate, fishing license, insurance) | No compliance enforcement |
| 3 | Crew management (assign/remove crew, roles) | No crew safety tracking |
| 4 | Trip readiness gate (pre-trip validation against boat state) | Unsafe trips can start |
| 5 | Boat ownership transfer workflow | No legal ownership chain |
| 6 | Boat verification by authority | No government validation path |
| 7 | Emergency contacts bound to boat | SOS chain incomplete |
| 8 | Boat audit log | No immutable change history |
| 9 | Soft delete (decommission) | Hard deletes break trip history |
| 10 | DELETE endpoint | Cannot deactivate a boat |

### 3.2 High Priority Missing Features (P1)

| # | Missing Feature | Impact |
|---|---|---|
| 11 | Insurance record management | Cannot enforce insurance validity |
| 12 | Fishing license management | Cannot enforce license validity |
| 13 | Safety equipment checklist (structured, not free-text JSON) | No compliance verification |
| 14 | Boat inspection records | No inspection history |
| 15 | Boat photos | No visual identification |
| 16 | QR code generation per boat | No field identification |
| 17 | Boat status history | No audit trail for status changes |
| 18 | Vessel risk profile (computed from incident history) | No risk-aware trip gating |
| 19 | Operator/rescue dashboard boat view | Operators see only user.boat_name |
| 20 | Flutter boat management screens | Zero mobile boat management UI |

### 3.3 Medium Priority Missing Features (P2)

| # | Missing Feature | Impact |
|---|---|---|
| 21 | Equipment inventory (structured items with quantity, condition) | No equipment compliance |
| 22 | Engine details (make, model, serial number, year) | Incomplete vessel identity |
| 23 | Boat dimensions (beam, draft, hull type) | Incomplete for rescue operations |
| 24 | Home harbor binding | No harbor-boat relationship |
| 25 | Boat sharing / delegated access | Single-owner only |
| 26 | Maintenance completion workflow | Records created but never closed |
| 27 | Fuel prediction integration with trip start | Prediction exists but not gated |
| 28 | NFC tag support (future seam) | No interface defined |
| 29 | Government reporting export | No structured export |
| 30 | Fleet view for operators | No fleet-level boat dashboard |

---

## 4. Technical Debt

### 4.1 Model Layer

| Issue | Severity | Detail |
|---|---|---|
| `safety_equipment` stored as raw JSON text | High | No schema validation, no queryability, breaks on malformed input |
| No `status` enum on Boat model | Critical | Boat has only `is_active` boolean — cannot represent 7 required states |
| No `updated_by` / `version` fields | High | Cannot audit who changed what |
| No `deleted_at` soft delete | High | Hard deletes break FK integrity with trips |
| `__init__` aliasing in Boat model | Medium | Fragile compatibility shim — `boat_name`, `boat_type`, `owner` aliases |
| `registration_number` is nullable | Medium | Should be required for government-grade boats |
| No `boat_type` / `vessel_class` field | Medium | Engine type is not the same as vessel class |
| Phase 5 models in single `phase5.py` | Medium | BoatFuelLog, BoatMaintenance mixed with unrelated AI/analytics models |

### 4.2 Service Layer

| Issue | Severity | Detail |
|---|---|---|
| `BoatHealthService` uses static methods only | Medium | Not injectable, hard to mock in tests |
| Fuel efficiency calculation is approximate | Medium | `delta / 10.0` is a placeholder, not real physics |
| Health score can go below 0 before clamp | Medium | Multiple overdue items compound incorrectly |
| No transaction safety in `create_fuel_log` | Medium | Race condition possible on concurrent writes |
| `get_fuel_summary` limits to last 20 logs | Low | Arbitrary limit, not configurable |
| No authorization check in `create_fuel_prediction` | High | Any user can create a prediction for any boat |

### 4.3 Router Layer

| Issue | Severity | Detail |
|---|---|---|
| v1 boats router has no DELETE endpoint | High | Cannot deactivate a boat |
| v1 boats router has no operator/admin access | High | Operators cannot view fleet boats |
| v2 boat-health router role check uses string `"fisherman"` | Medium | Should use `UserRole.fisherman` enum |
| No pagination on `list_my_boats` | Medium | Will fail at scale |
| No rate limiting on boat registration | Medium | Duplicate registration spam possible |
| `engine_hours` passed as query param, not body | Low | Inconsistent with REST conventions |
| No `updated_at` in `BoatOut` schema | Low | Clients cannot detect stale data |

### 4.4 Database / Migration Layer

| Issue | Severity | Detail |
|---|---|---|
| No index on `boats.is_active` | Medium | Full table scan on active boat queries |
| No composite index on `(owner_id, is_active)` | Medium | Common query pattern unoptimized |
| `boat_maintenance.completed_date` never set by any service | High | Maintenance records are never closed |
| `boat_health_status` has no unique constraint on `boat_id` | Medium | Multiple health status rows possible per boat |
| No FK from `boat_fuel_logs` to `users` (who logged it) | Medium | No audit trail for fuel entries |
| Migration 002 creates boats without `status` column | Critical | Status lifecycle cannot be added without new migration |

---

## 5. Security Issues

| # | Issue | Severity | Detail |
|---|---|---|---|
| 1 | No operator/admin can view any boat | High | Rescue operators cannot see boat details during an incident |
| 2 | Family members cannot see linked fisherman's boat | Medium | Family portal shows no boat context |
| 3 | `registration_number` uniqueness check is case-sensitive | Medium | `TN-001` and `tn-001` treated as different boats |
| 4 | No rate limiting on boat registration | Medium | Spam registration possible |
| 5 | Boat ownership not verified before trip start | Critical | Any fisherman can start a trip on any boat_id |
| 6 | No audit log for boat data changes | High | Cannot detect fraudulent modifications |
| 7 | `safety_equipment` JSON not sanitized | Low | Potential injection via malformed JSON strings |
| 8 | No document integrity verification | High | Uploaded documents (future) need hash verification |

---

## 6. Performance Issues

| # | Issue | Severity | Detail |
|---|---|---|---|
| 1 | `list_my_boats` has no pagination | Medium | Unbounded query |
| 2 | `calculate_health_score` makes 3 DB queries per call | Medium | Should be batched or cached |
| 3 | `get_fuel_summary` loads 20 logs into memory | Low | Should use DB aggregation |
| 4 | No caching on health score | Medium | Called on every trip readiness check |
| 5 | No index on `boat_maintenance.scheduled_date` | Medium | Overdue query does full scan |
| 6 | `boat_health_status` queried by `boat_id` without unique index | Medium | May return multiple rows |

---

## 7. UI / UX Issues

### 7.1 Flutter Mobile
- **Zero boat management screens exist.** The `StartTripScreen` explicitly comments: *"the mobile app has no boat management UI yet (that's a separate, not-yet-built feature)"*
- No boat list, boat detail, boat registration, or boat status screen
- Trip start does not select a boat — `boat_id` is always null from mobile
- No offline boat data cache

### 7.2 Rescue Dashboard
- `FishermenPagePremium.jsx` shows `fisherman.boat_name` from the user profile (legacy field), not from the boats table
- No boat detail view, no fleet map boat overlay, no boat status indicator
- No maintenance or inspection status visible to operators

---

## 8. Accessibility Issues

| # | Issue |
|---|---|
| 1 | No boat management UI exists to audit |
| 2 | When built, must meet WCAG 2.1 AA minimum |
| 3 | Safety equipment checklist must be screen-reader compatible |
| 4 | Status indicators must not rely on color alone |
| 5 | Tamil language strings not defined for any boat management copy |

---

## 9. Offline Capability

| # | Issue |
|---|---|
| 1 | No offline boat data model in Flutter (`mobile/lib/models/` has no boat model) |
| 2 | No SQLite outbox for boat registration or updates |
| 3 | No sync service for boat data |
| 4 | Boat health data not cached locally |
| 5 | Trip start cannot validate boat state offline |

---

## 10. API Quality

| Dimension | Score | Notes |
|---|---|---|
| Versioning | 3/10 | v1 and v2 split is inconsistent — boats on v1, health on v2 |
| Consistency | 4/10 | Mixed response shapes, no envelope |
| Documentation | 5/10 | FastAPI auto-docs exist but no descriptions on most fields |
| Error handling | 5/10 | Basic HTTPException, no structured error codes |
| Idempotency | 2/10 | No idempotency keys on registration |
| Pagination | 2/10 | Only list endpoint — no pagination |
| Rate limiting | 1/10 | None on boat endpoints |
| Authorization | 4/10 | Owner-only, no operator/admin/family access |

---

## 11. Database Quality

| Dimension | Score | Notes |
|---|---|---|
| Normalization | 5/10 | `safety_equipment` as JSON text is denormalized |
| Indexes | 4/10 | Missing composite and partial indexes |
| Constraints | 4/10 | Missing NOT NULL, CHECK constraints |
| Audit fields | 3/10 | `created_at`/`updated_at` exist, no `updated_by`, no `version` |
| Soft delete | 2/10 | `is_active` boolean only — no `deleted_at` |
| Referential integrity | 6/10 | FKs exist but no cascade rules on boat deletion |
| Versioning | 1/10 | No row versioning |

---

## 12. Testing Quality

| Dimension | Score | Notes |
|---|---|---|
| Unit tests | 6/10 | 9 tests cover fuel, maintenance, health score |
| Integration tests | 2/10 | No API-level boat tests |
| Security tests | 0/10 | No authorization tests |
| Offline tests | 0/10 | No offline boat tests |
| Edge case coverage | 3/10 | Missing: duplicate registration, invalid owner, concurrent updates |
| Flutter tests | 0/10 | No boat widget tests (no screens exist) |

---

## 13. Summary Scores

| Dimension | Score |
|---|---|
| Functionality completeness | 2/10 |
| Technical debt | 4/10 (high debt) |
| Security | 3/10 |
| Performance | 4/10 |
| UI/UX | 0/10 (not built) |
| Accessibility | 0/10 (not built) |
| Offline capability | 0/10 |
| API quality | 3/10 |
| Database quality | 4/10 |
| Testing quality | 3/10 |
| **Overall** | **2.3/10** |

---

## 14. Conclusion

The existing Boat Management module is a Phase 2 CRUD scaffold that was never intended to be production-grade. It provides a foundation (the `boats` table, basic CRUD, and a health scoring service) but is missing the majority of features required for a government-grade, safety-critical vessel management system.

**The module must be redesigned from the database up, while preserving backward compatibility with existing trips and SOS data.**

The redesign must not break:
- Existing `boats` table FK references from `trips`
- Existing `boat_fuel_logs`, `boat_maintenance`, `boat_health_status` tables
- Existing API contracts at `/api/v1/boats/`
