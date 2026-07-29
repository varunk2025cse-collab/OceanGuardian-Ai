# Boat Management Security Design
**OceanGuardian AI — Security Architecture**
**Version:** 1.0

---

## 1. Threat Model

| Threat | Vector | Impact | Mitigation |
|---|---|---|---|
| Fraudulent boat registration | API abuse | False identity in rescue ops | Rate limiting, registration_number uniqueness, verification workflow |
| Unauthorized boat modification | Stolen JWT | Corrupt vessel data | Owner-only writes, audit log, version conflict detection |
| Document forgery | File upload | False compliance | File hash (SHA-256), authority verification workflow |
| Ownership spoofing | API manipulation | Illegal ownership transfer | Transfer approval workflow, admin authorization required |
| Boat data exfiltration | Unauthorized API access | Privacy breach | RBAC, family access limited to linked fisherman only |
| QR code spoofing | Physical forgery | Rescue misdirection | QR token tied to boat_id + server-side validation |
| Duplicate registration | Race condition | Conflicting records | DB unique constraint + case-insensitive index |
| Audit log tampering | Admin abuse | Evidence destruction | Append-only table, no UPDATE/DELETE permissions on audit tables |
| Trip start on unsafe boat | Business logic bypass | Fisherman at risk | Server-side readiness gate — client cannot bypass |

---

## 2. Authorization Matrix

```
Operation                    | fisherman | family | operator | admin | government
─────────────────────────────────────────────────────────────────────────────────
Register boat                | own       | —      | —        | any   | —
View boat list               | own       | linked | all      | all   | all
View boat detail             | own       | linked | all      | all   | all
Update boat                  | own       | —      | —        | any   | —
Change boat status           | own*      | —      | any      | any   | —
Decommission boat            | own       | —      | —        | any   | —
Verify boat                  | —         | —      | yes      | yes   | yes
Upload document              | own       | —      | —        | any   | —
Verify document              | —         | —      | yes      | yes   | yes
Assign crew                  | own       | —      | —        | any   | —
Remove crew                  | own       | —      | —        | any   | —
Add inspection               | own       | —      | yes      | yes   | yes
View audit log               | —         | —      | yes      | yes   | yes
Initiate transfer            | own       | —      | —        | any   | —
Approve transfer             | —         | —      | —        | yes   | yes
Export fleet report          | —         | —      | yes      | yes   | yes
─────────────────────────────────────────────────────────────────────────────────
* fisherman: active↔inactive, active→maintenance only
```

**Family access rule:** A family member can only view boats belonging to the fisherman they are explicitly linked to via `family_links` table. This is enforced at the query level, not just the route level.

---

## 3. Input Validation Rules

| Field | Rule |
|---|---|
| `registration_number` | Alphanumeric + hyphens only, max 60 chars, normalized to UPPER before uniqueness check |
| `name` | 1–120 chars, no HTML/script tags, trimmed |
| `year_built` | Integer, 1900 ≤ year ≤ current_year + 1 |
| `engine_horsepower` | Integer, 1–10000 |
| `fuel_capacity_liters` | Float, 0.1–100000 |
| `length_meters` | Float, 0.5–200 |
| `phone_number` (crew) | E.164 format validation |
| `file` (documents) | Max 10MB, allowed types: PDF, JPG, PNG, WEBP only |
| `status` | Must be valid enum — server rejects unknown values |
| `document_type` | Must be valid enum |

---

## 4. Document Security

```
Upload flow:
  1. Client uploads file to POST /api/v2/boats/{id}/documents
  2. Server validates file type (magic bytes, not just extension)
  3. Server computes SHA-256 hash of file content
  4. File stored in object storage (S3-compatible) with private ACL
  5. `file_hash` stored in boat_documents table
  6. Signed URL generated for download (expires in 1 hour)

Integrity verification:
  - On download, server re-computes hash and compares to stored hash
  - Mismatch triggers alert and returns 409 DOCUMENT_INTEGRITY_FAILURE

Access control:
  - Direct file URLs are never exposed — always via signed URL endpoint
  - Signed URLs expire in 1 hour
  - Download events logged in boat_audit_logs
```

---

## 5. QR Code Security

```
QR token format: OG-BOAT-{boat_id}-{random_hex_6}

Properties:
  - Generated once on registration
  - Regenerated on ownership transfer (old token invalidated)
  - Server validates token on scan — returns 404 if invalid/decommissioned
  - QR payload contains only non-sensitive data (no GPS, no financial data)
  - Emergency contact in QR is the primary crew contact only

Scan validation endpoint:
  GET /api/v2/boats/scan/{qr_token}
  - Public endpoint (no auth required — for Coast Guard field use)
  - Returns: boat name, registration, owner name, emergency contact only
  - Rate limited: 30 req/min per IP
```

---

## 6. Audit Log Security

```
boat_audit_logs table:
  - INSERT only — no UPDATE, no DELETE permissions granted to application user
  - PostgreSQL row-level security enforces this
  - Separate read-only DB user for audit log queries
  - Logs retained for minimum 7 years (government requirement)
  - Log entries include: actor_id, ip_address, user_agent, correlation_id

boat_status_history table:
  - Same INSERT-only policy
  - Cannot be modified after creation
```

---

## 7. Rate Limiting

| Endpoint | Limit | Window |
|---|---|---|
| POST `/api/v2/boats` | 10 requests | per user per minute |
| POST `/api/v2/boats/{id}/documents` | 20 requests | per user per minute |
| GET `/api/v2/boats/scan/{token}` | 30 requests | per IP per minute |
| PATCH `/api/v2/boats/{id}/status` | 20 requests | per user per minute |
| POST `/api/v2/boats/{id}/transfer` | 5 requests | per user per hour |

SOS-related endpoints are **never** rate limited.

---

## 8. Known Security Gaps (To Be Addressed)

| Gap | Priority | Plan |
|---|---|---|
| No virus scanning on uploaded documents | P1 | Integrate ClamAV or cloud AV on upload |
| No MFA for ownership transfer | P1 | Require step-up auth for transfer approval |
| No anomaly detection on registration patterns | P2 | Flag bulk registrations from same IP |
| No field-level encryption for sensitive columns | P2 | Encrypt `engine_serial_number`, `aadhaar_last4` at rest |
