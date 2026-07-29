# Boat Management Backlog
**OceanGuardian AI — Prioritized Implementation Backlog**
**Version:** 1.0

---

## Priority Legend
- **P0** — Blocking. Must be done before any other work in this module.
- **P1** — Required for production release.
- **P2** — Important but can follow initial release.
- **P3** — Future / nice-to-have.

---

## EPIC 1: Database Foundation

| ID | Task | Priority | Effort | Dependencies | Acceptance Criteria |
|---|---|---|---|---|---|
| BM-001 | Alembic migration 009 — extend boats table | P0 | 1d | None | Runs on SQLite + PostgreSQL, no data loss |
| BM-002 | Create boat_documents table | P0 | 0.5d | BM-001 | Table exists with all constraints |
| BM-003 | Create boat_crew_members table | P0 | 0.5d | BM-001 | Table exists with all constraints |
| BM-004 | Create boat_inspections table | P1 | 0.5d | BM-001 | Table exists with all constraints |
| BM-005 | Create boat_equipment_items table | P1 | 0.5d | BM-001 | Table exists with all constraints |
| BM-006 | Create boat_status_history table | P0 | 0.5d | BM-001 | Append-only, no update/delete |
| BM-007 | Create boat_audit_logs table | P0 | 0.5d | BM-001 | Append-only, all indexes present |
| BM-008 | Create boat_ownership_transfers table | P2 | 0.5d | BM-001 | Table exists with all constraints |
| BM-009 | Fix boat_maintenance (add status, completed_by) | P1 | 0.5d | BM-001 | Existing records unaffected |
| BM-010 | Fix boat_health_status (unique constraint) | P1 | 0.5d | BM-001 | No duplicate rows possible |

---

## EPIC 2: Backend Services

| ID | Task | Priority | Effort | Dependencies | Acceptance Criteria |
|---|---|---|---|---|---|
| BM-011 | Boat service — register with QR token + audit | P0 | 1d | BM-001 | Unit tests pass, audit log created |
| BM-012 | Boat service — status state machine | P0 | 1d | BM-011 | All valid transitions work, invalid blocked |
| BM-013 | Boat service — soft decommission | P0 | 0.5d | BM-012 | deleted_at set, trips preserved |
| BM-014 | Boat service — version conflict detection | P1 | 0.5d | BM-011 | 409 on stale version |
| BM-015 | Boat service — RBAC-aware queries | P0 | 1d | BM-011 | All role combinations tested |
| BM-016 | Trip readiness service | P0 | 1d | BM-011 | All rules evaluated, SOS never blocked |
| BM-017 | Document service — upload + hash | P1 | 1d | BM-002 | SHA-256 stored, expiry detected |
| BM-018 | Document service — verification workflow | P1 | 0.5d | BM-017 | Operator can verify, fisherman cannot |
| BM-019 | Crew service — assign with role validation | P1 | 1d | BM-003 | One captain rule enforced |
| BM-020 | Crew service — soft remove | P1 | 0.5d | BM-019 | removed_at set, not hard deleted |
| BM-021 | Inspection service | P1 | 1d | BM-004 | Records created, readiness integrated |
| BM-022 | Equipment service | P1 | 1d | BM-005 | Items managed, mandatory check works |
| BM-023 | Ownership transfer service | P2 | 1d | BM-008 | Pending → approved → completed flow |
| BM-024 | AI boat health prediction | P2 | 2d | BM-011 | Confidence score, Tamil explanation |
| BM-025 | AI maintenance prediction | P2 | 1d | BM-024 | Predicted date + cost estimate |
| BM-026 | AI vessel risk score | P2 | 1d | BM-024 | Risk level with contributing factors |
| BM-027 | AI equipment recommendation | P2 | 1d | BM-022 | Regulatory requirements included |

---

## EPIC 3: API Layer

| ID | Task | Priority | Effort | Dependencies | Acceptance Criteria |
|---|---|---|---|---|---|
| BM-028 | v2 boats router — core CRUD | P0 | 1.5d | BM-015 | All endpoints, pagination, rate limiting |
| BM-029 | v2 boats router — status + verify + QR | P0 | 0.5d | BM-028 | Status transitions, QR endpoint |
| BM-030 | v2 boats router — readiness endpoint | P0 | 0.5d | BM-016 | Returns blocking/warnings/passed |
| BM-031 | v2 boats router — fleet summary | P1 | 0.5d | BM-028 | Operator/admin only, aggregated counts |
| BM-032 | v2 document router | P1 | 1d | BM-017 | Upload, list, verify endpoints |
| BM-033 | v2 crew router | P1 | 0.5d | BM-019 | Assign, list, remove endpoints |
| BM-034 | v2 inspection router | P1 | 0.5d | BM-021 | Create, list endpoints |
| BM-035 | v2 equipment router | P1 | 0.5d | BM-022 | CRUD endpoints |
| BM-036 | v2 audit/history router | P1 | 0.5d | BM-007 | Status history, audit log endpoints |
| BM-037 | v2 transfer router | P2 | 0.5d | BM-023 | Initiate, approve endpoints |
| BM-038 | Public QR scan endpoint | P1 | 0.5d | BM-029 | No auth, rate limited, safe data only |
| BM-039 | Deprecation header on v1 boats router | P1 | 0.5d | BM-028 | v1 still works, header warns of deprecation |

---

## EPIC 4: Flutter Mobile

| ID | Task | Priority | Effort | Dependencies | Acceptance Criteria |
|---|---|---|---|---|---|
| BM-040 | Boat Dart model + serialization | P0 | 0.5d | BM-028 | fromJson/toJson, all fields |
| BM-041 | Boat SQLite repository (offline cache) | P0 | 1d | BM-040 | Read/write/outbox queue |
| BM-042 | Boat Flutter service (API + offline) | P0 | 1d | BM-041 | Online/offline transparent |
| BM-043 | Boat List Screen | P0 | 1d | BM-042 | Status badges, offline banner, Tamil |
| BM-044 | Boat Detail Screen | P0 | 1.5d | BM-043 | Quick actions, health score, doc status |
| BM-045 | Register Boat Screen (4-step wizard) | P0 | 1.5d | BM-042 | Offline queue, harbor selector |
| BM-046 | Edit Boat Screen | P1 | 0.5d | BM-044 | Pre-filled form, version conflict handling |
| BM-047 | Boat Documents Screen | P1 | 1d | BM-044 | Expiry alerts, upload, verify status |
| BM-048 | Crew Management Screen | P1 | 1d | BM-044 | Assign, remove, role display |
| BM-049 | Equipment Checklist Screen | P1 | 1d | BM-044 | Condition badges, mandatory items |
| BM-050 | Maintenance Records Screen | P1 | 1d | BM-044 | Overdue alerts, complete action |
| BM-051 | QR Code Screen | P1 | 0.5d | BM-044 | Offline-capable, share/print |
| BM-052 | Trip Readiness Screen | P0 | 1d | BM-044 | Blocking/warning/passed display |
| BM-053 | Trip Start — boat selector integration | P0 | 0.5d | BM-052 | Boat picker, readiness gate |
| BM-054 | Inspection Status Screen | P2 | 0.5d | BM-044 | List inspections, next due date |
| BM-055 | Tamil l10n strings for all boat screens | P0 | 0.5d | BM-043 | Native speaker reviewed |
| BM-056 | Accessibility audit — all boat screens | P1 | 1d | BM-054 | WCAG 2.1 AA, TalkBack tested |

---

## EPIC 5: Rescue Dashboard

| ID | Task | Priority | Effort | Dependencies | Acceptance Criteria |
|---|---|---|---|---|---|
| BM-057 | Fleet View page (BoatsPage.jsx) | P1 | 2d | BM-031 | Summary cards, boat grid, filters |
| BM-058 | BoatStatusBadge component | P1 | 0.5d | BM-057 | Color + icon + text, no color-only |
| BM-059 | BoatReadinessPanel component | P1 | 1d | BM-057 | Blocking/warning display for operators |
| BM-060 | BoatDocumentStatus component | P1 | 0.5d | BM-057 | Expiry indicators |
| BM-061 | Update FishermenPage to use boats table | P1 | 0.5d | BM-057 | Replace user.boat_name with boats entity |

---

## EPIC 6: Testing

| ID | Task | Priority | Effort | Dependencies | Acceptance Criteria |
|---|---|---|---|---|---|
| BM-062 | Backend unit tests — boat service | P0 | 1d | BM-015 | All test cases from testing doc pass |
| BM-063 | Backend unit tests — readiness service | P0 | 0.5d | BM-016 | All readiness rules tested |
| BM-064 | Backend unit tests — document service | P1 | 0.5d | BM-017 | Hash, expiry, verification tested |
| BM-065 | Backend unit tests — crew service | P1 | 0.5d | BM-019 | Role constraints tested |
| BM-066 | API integration tests — all endpoints | P0 | 2d | BM-039 | 100% endpoint coverage |
| BM-067 | Authorization tests — all role combinations | P0 | 1d | BM-066 | Every role × every endpoint tested |
| BM-068 | Security tests — injection, file upload | P1 | 1d | BM-066 | All security test cases pass |
| BM-069 | Flutter widget tests — all screens | P1 | 2d | BM-056 | All screens have widget tests |
| BM-070 | Offline tests — Flutter | P1 | 1d | BM-056 | All offline scenarios tested |
| BM-071 | Performance tests | P2 | 1d | BM-066 | All targets met |

---

## Production Readiness Score (Target)

| Dimension | Current | Target |
|---|---|---|
| Production Readiness | 2/10 | 8.5/10 |
| Engineering Quality | 3/10 | 9/10 |
| Security | 3/10 | 8.5/10 |
| Accessibility | 0/10 | 8/10 |
| Scalability | 4/10 | 8.5/10 |
| Government Readiness | 1/10 | 8/10 |
| Innovation | 4/10 | 8.5/10 |

---

## Awaiting Approval

This backlog is ready for team review. Upon approval, implementation begins with **BM-001** (database migration).

No code will be generated until this backlog is approved.
