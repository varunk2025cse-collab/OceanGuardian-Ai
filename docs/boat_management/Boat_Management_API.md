# Boat Management API Design
**OceanGuardian AI — RESTful API Specification**
**Version:** v2 | **Base:** `/api/v2/boats`

---

## 1. API Design Principles

- All endpoints versioned under `/api/v2/`
- Consistent response envelope: `{ "data": ..., "meta": ..., "error": null }`
- All errors return: `{ "error": { "code": "BOAT_NOT_FOUND", "message": "...", "field": null } }`
- Idempotency key header `X-Idempotency-Key` supported on POST endpoints
- Rate limiting: 60 req/min per user on standard endpoints, 10 req/min on registration
- All timestamps in ISO 8601 UTC
- Pagination via `?page=1&page_size=20`

---

## 2. Authentication & Authorization

All endpoints require `Authorization: Bearer <jwt_token>`.

| Role | Boats Access |
|---|---|
| `fisherman` | Own boats only (CRUD) |
| `family` | Read linked fisherman's boats |
| `operator` | Read all boats, update status |
| `admin` | Full access including verification |
| `government` | Read all boats, export |

---

## 3. Core Boat Endpoints

### POST `/api/v2/boats`
Register a new boat.

**Auth:** fisherman, admin
**Rate limit:** 10/min

**Request:**
```json
{
  "name": "Murugan Kadal",
  "registration_number": "TN-MFB-2024-001",
  "vessel_class": "mechanized",
  "hull_material": "wood",
  "color": "blue",
  "length_meters": 8.5,
  "beam_meters": 2.1,
  "draft_meters": 0.8,
  "year_built": 2018,
  "engine_type": "diesel",
  "engine_make": "Kirloskar",
  "engine_model": "KD-10",
  "engine_serial_number": "KD10-2018-4521",
  "engine_horsepower": 40,
  "fuel_capacity_liters": 120.0,
  "home_harbor_id": 3
}
```

**Validation:**
- `name`: required, 1–120 chars
- `registration_number`: optional but unique (case-insensitive) if provided
- `vessel_class`: must be valid enum value
- `year_built`: 1900 to current year + 1
- `engine_horsepower`: > 0 if provided
- `fuel_capacity_liters`: > 0 if provided

**Response 201:**
```json
{
  "data": {
    "id": 42,
    "name": "Murugan Kadal",
    "registration_number": "TN-MFB-2024-001",
    "status": "registered",
    "verification_status": "unverified",
    "qr_code_token": "OG-BOAT-42-a3f9c2",
    "owner_id": 7,
    "created_at": "2025-01-15T06:30:00Z"
  }
}
```

**Errors:**
- `409 REGISTRATION_NUMBER_CONFLICT` — registration number already in use
- `400 INVALID_VESSEL_CLASS` — unrecognized vessel class
- `403 FORBIDDEN` — non-fisherman attempting registration

---

### GET `/api/v2/boats`
List boats. Fishermen see their own. Operators/admins see all.

**Auth:** all roles
**Query params:** `page`, `page_size`, `status`, `harbor_id`, `owner_id`, `search`

**Response 200:**
```json
{
  "data": [
    {
      "id": 42,
      "name": "Murugan Kadal",
      "registration_number": "TN-MFB-2024-001",
      "status": "active",
      "verification_status": "verified",
      "owner_name": "Murugan K",
      "home_harbor": "Nagapattinam",
      "health_score": 82.5,
      "active_trip_id": null,
      "last_trip_at": "2025-01-10T05:00:00Z"
    }
  ],
  "meta": { "total": 1, "page": 1, "page_size": 20 }
}
```

---

### GET `/api/v2/boats/{boat_id}`
Get full boat details.

**Auth:** owner, operator, admin, linked family

**Response 200:**
```json
{
  "data": {
    "id": 42,
    "name": "Murugan Kadal",
    "registration_number": "TN-MFB-2024-001",
    "status": "active",
    "vessel_class": "mechanized",
    "hull_material": "wood",
    "color": "blue",
    "length_meters": 8.5,
    "beam_meters": 2.1,
    "draft_meters": 0.8,
    "year_built": 2018,
    "engine_type": "diesel",
    "engine_make": "Kirloskar",
    "engine_model": "KD-10",
    "engine_horsepower": 40,
    "fuel_capacity_liters": 120.0,
    "home_harbor_id": 3,
    "home_harbor_name": "Nagapattinam",
    "verification_status": "verified",
    "verified_at": "2025-01-02T10:00:00Z",
    "qr_code_token": "OG-BOAT-42-a3f9c2",
    "health_score": 82.5,
    "owner_id": 7,
    "owner_name": "Murugan K",
    "created_at": "2025-01-01T06:00:00Z",
    "updated_at": "2025-01-15T08:00:00Z",
    "version": 3
  }
}
```

---

### PATCH `/api/v2/boats/{boat_id}`
Update boat details. All fields optional.

**Auth:** owner, admin
**Body:** any subset of registration fields (same shape as POST)

**Response 200:** Updated boat object

**Errors:**
- `409 REGISTRATION_NUMBER_CONFLICT`
- `409 VERSION_CONFLICT` — if `version` in body doesn't match current (optimistic lock)
- `403 FORBIDDEN`

---

### DELETE `/api/v2/boats/{boat_id}`
Soft-decommission a boat. Sets `status=decommissioned`, `deleted_at=now()`.

**Auth:** owner, admin
**Body:** `{ "reason": "sold" }`

**Business rules:**
- Cannot decommission a boat with an active trip
- Cannot decommission a boat with an active SOS incident

**Response 200:** `{ "data": { "id": 42, "status": "decommissioned" } }`

---

### PATCH `/api/v2/boats/{boat_id}/status`
Change boat status with reason.

**Auth:** owner (limited transitions), operator/admin (all transitions)

**Request:**
```json
{
  "status": "maintenance",
  "reason": "Engine overhaul scheduled"
}
```

**Valid transitions by role:**
- `fisherman`: active↔inactive, active→maintenance
- `operator/admin`: any transition
- `system`: active→emergency (SOS trigger), emergency→active (SOS resolved)

**Response 200:** Updated boat object with new status

---

### POST `/api/v2/boats/{boat_id}/verify`
Mark a boat as verified by an authority.

**Auth:** operator, admin, government

**Request:**
```json
{
  "verification_status": "verified",
  "notes": "Documents checked at Nagapattinam harbor"
}
```

**Response 200:** Updated boat object

---

### GET `/api/v2/boats/{boat_id}/qr-code`
Get QR code data for a boat.

**Auth:** owner, operator, admin

**Response 200:**
```json
{
  "data": {
    "qr_token": "OG-BOAT-42-a3f9c2",
    "qr_payload": {
      "boat_id": 42,
      "registration_number": "TN-MFB-2024-001",
      "owner_name": "Murugan K",
      "emergency_contact": "+91-9876543210",
      "platform": "oceanguardian",
      "version": "1"
    },
    "qr_image_url": "/api/v2/boats/42/qr-code/image"
  }
}
```

---

### GET `/api/v2/boats/{boat_id}/readiness`
Evaluate trip readiness for a boat.

**Auth:** owner, operator

**Response 200:**
```json
{
  "data": {
    "boat_id": 42,
    "is_ready": false,
    "readiness_score": 65,
    "blocking_issues": [
      {
        "rule": "fishing_license_expired",
        "severity": "block",
        "message": "Fishing license expired on 2024-12-31",
        "message_ta": "மீன்பிடி உரிமம் 2024-12-31 அன்று காலாவதியானது",
        "action": "Renew license before starting trip"
      }
    ],
    "warnings": [
      {
        "rule": "fuel_below_threshold",
        "severity": "warn",
        "message": "Fuel level at 18% — below recommended 20%",
        "message_ta": "எரிபொருள் அளவு 18% — பரிந்துரைக்கப்பட்ட 20%க்கு கீழே"
      }
    ],
    "passed_checks": ["boat_status_active", "insurance_valid", "crew_assigned"],
    "ai_recommendation": "Address license renewal before next trip. Fuel up at Nagapattinam harbor.",
    "confidence_score": 0.94
  }
}
```

---

## 4. Document Endpoints

### POST `/api/v2/boats/{boat_id}/documents`
Upload a boat document.

**Auth:** owner, admin
**Content-Type:** `multipart/form-data`

**Form fields:**
- `document_type`: required enum
- `document_number`: optional
- `issuing_authority`: optional
- `issue_date`: optional date
- `expiry_date`: optional date
- `file`: optional file upload (max 10MB, PDF/JPG/PNG)
- `notes`: optional

**Response 201:** Document object with `file_hash`

---

### GET `/api/v2/boats/{boat_id}/documents`
List all documents for a boat.

**Auth:** owner, operator, admin
**Query:** `?document_type=fishing_license&include_expired=false`

**Response 200:** Array of document objects

---

### PATCH `/api/v2/boats/{boat_id}/documents/{doc_id}/verify`
Mark a document as verified.

**Auth:** operator, admin, government

---

## 5. Crew Endpoints

### POST `/api/v2/boats/{boat_id}/crew`
Assign a crew member.

**Auth:** owner, admin

**Request:**
```json
{
  "user_id": 15,
  "full_name": "Rajan S",
  "phone_number": "+91-9876543211",
  "role": "deckhand",
  "is_primary_contact": false
}
```

**Business rules:**
- Only one `captain` per boat at a time
- Only one `is_primary_contact=true` per boat at a time
- Cannot assign inactive users

**Response 201:** Crew member object

---

### GET `/api/v2/boats/{boat_id}/crew`
List active crew members.

**Auth:** owner, operator, admin, linked family

---

### DELETE `/api/v2/boats/{boat_id}/crew/{crew_id}`
Remove a crew member (soft remove — sets `removed_at`).

**Auth:** owner, admin
**Body:** `{ "reason": "left crew" }`

---

## 6. Inspection Endpoints

### POST `/api/v2/boats/{boat_id}/inspections`
Record an inspection.

**Auth:** owner, operator, admin

**Request:**
```json
{
  "inspection_type": "annual_safety",
  "inspector_name": "Coastal Officer Ravi",
  "inspector_authority": "Tamil Nadu Fisheries Department",
  "inspection_date": "2025-01-10",
  "next_due_date": "2026-01-10",
  "result": "passed",
  "findings": "All safety equipment in order",
  "certificate_number": "TNFD-2025-001234"
}
```

**Response 201:** Inspection object

---

### GET `/api/v2/boats/{boat_id}/inspections`
List inspections, most recent first.

---

## 7. Equipment Endpoints

### POST `/api/v2/boats/{boat_id}/equipment`
Add an equipment item.

**Auth:** owner, admin

**Request:**
```json
{
  "category": "life_saving",
  "item_name": "Life jacket",
  "quantity": 6,
  "condition": "good",
  "is_mandatory": true,
  "expiry_date": "2027-01-01"
}
```

---

### GET `/api/v2/boats/{boat_id}/equipment`
List all equipment items.

**Query:** `?category=life_saving&condition=poor`

---

### PATCH `/api/v2/boats/{boat_id}/equipment/{item_id}`
Update equipment item (condition, quantity, last_checked_at).

---

## 8. Ownership Transfer Endpoints

### POST `/api/v2/boats/{boat_id}/transfer`
Initiate ownership transfer.

**Auth:** owner, admin

**Request:**
```json
{
  "to_owner_id": 22,
  "transfer_date": "2025-02-01",
  "transfer_reason": "sale",
  "notes": "Sold at Nagapattinam harbor"
}
```

**Response 201:** Transfer record with `status=pending`

---

### POST `/api/v2/boats/{boat_id}/transfer/{transfer_id}/approve`
Approve a pending transfer.

**Auth:** admin, government

---

## 9. Audit & History Endpoints

### GET `/api/v2/boats/{boat_id}/status-history`
Get status change history.

**Auth:** owner, operator, admin

---

### GET `/api/v2/boats/{boat_id}/audit-log`
Get full audit log for a boat.

**Auth:** operator, admin, government
**Query:** `?action=status_changed&from=2025-01-01&to=2025-01-31`

---

## 10. Fleet & Analytics Endpoints (Operator/Admin)

### GET `/api/v2/boats/fleet/summary`
Fleet-level summary for operators.

**Auth:** operator, admin, government

**Response 200:**
```json
{
  "data": {
    "total_boats": 142,
    "by_status": {
      "active": 98,
      "maintenance": 12,
      "inactive": 28,
      "emergency": 2,
      "decommissioned": 2
    },
    "by_verification": {
      "verified": 110,
      "unverified": 32
    },
    "documents_expiring_30_days": 8,
    "inspections_overdue": 5,
    "boats_with_active_trips": 34
  }
}
```

---

## 11. Error Code Reference

| Code | HTTP | Meaning |
|---|---|---|
| `BOAT_NOT_FOUND` | 404 | Boat does not exist or is decommissioned |
| `REGISTRATION_NUMBER_CONFLICT` | 409 | Registration number already in use |
| `BOAT_NOT_ACTIVE` | 422 | Operation requires ACTIVE boat status |
| `ACTIVE_TRIP_EXISTS` | 409 | Cannot decommission boat with active trip |
| `VERSION_CONFLICT` | 409 | Optimistic lock conflict — reload and retry |
| `DOCUMENT_TOO_LARGE` | 413 | File exceeds 10MB limit |
| `INVALID_STATUS_TRANSITION` | 422 | Status change not allowed from current state |
| `CREW_ROLE_CONFLICT` | 409 | Only one captain allowed per boat |
| `TRANSFER_PENDING` | 409 | Cannot modify boat during pending transfer |
| `FORBIDDEN` | 403 | Role does not have access to this operation |
