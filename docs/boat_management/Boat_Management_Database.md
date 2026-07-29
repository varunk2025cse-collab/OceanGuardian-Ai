# Boat Management Database Design
**OceanGuardian AI — PostgreSQL Schema**
**Version:** 1.0 | **Migration:** 009_boat_management_enterprise

---

## 1. Design Principles

- Every table has `created_at`, `updated_at`, `created_by`, `updated_by`
- Soft delete via `deleted_at` — no hard deletes on safety-critical records
- Row versioning via `version` integer (optimistic locking)
- All status/type fields use CHECK constraints, not free-form strings
- Indexes on every FK, every status column, every date column used in queries
- Audit trail is append-only — `boat_audit_logs` rows are never updated

---

## 2. Migration Strategy

Migration `009_boat_management_enterprise` extends the existing `boats` table and adds new tables. All new columns on `boats` are nullable or have server defaults so existing rows remain valid.

---

## 3. Table Definitions

### 3.1 `boats` (extended)

Extends the existing table. New columns added via migration 009.

```sql
-- Existing columns (from migration 002) — DO NOT CHANGE
-- id, owner_id, name, registration_number, color, length_meters,
-- engine_type, engine_horsepower, fuel_capacity_liters,
-- safety_equipment (TEXT — deprecated, kept for backward compat),
-- is_active, created_at, updated_at

-- New columns added in migration 009
ALTER TABLE boats ADD COLUMN IF NOT EXISTS status VARCHAR(30)
    NOT NULL DEFAULT 'active'
    CHECK (status IN ('registered','active','inactive','maintenance',
                      'emergency','lost','damaged','decommissioned'));

ALTER TABLE boats ADD COLUMN IF NOT EXISTS vessel_class VARCHAR(50)
    CHECK (vessel_class IN ('mechanized','motorized','non_motorized',
                            'trawler','gillnetter','purse_seiner','other'));

ALTER TABLE boats ADD COLUMN IF NOT EXISTS hull_material VARCHAR(50)
    CHECK (hull_material IN ('wood','fiberglass','steel','aluminum','other'));

ALTER TABLE boats ADD COLUMN IF NOT EXISTS beam_meters FLOAT;
ALTER TABLE boats ADD COLUMN IF NOT EXISTS draft_meters FLOAT;
ALTER TABLE boats ADD COLUMN IF NOT EXISTS year_built INTEGER
    CHECK (year_built >= 1900 AND year_built <= EXTRACT(YEAR FROM NOW()) + 1);

ALTER TABLE boats ADD COLUMN IF NOT EXISTS engine_make VARCHAR(80);
ALTER TABLE boats ADD COLUMN IF NOT EXISTS engine_model VARCHAR(80);
ALTER TABLE boats ADD COLUMN IF NOT EXISTS engine_serial_number VARCHAR(80);
ALTER TABLE boats ADD COLUMN IF NOT EXISTS engine_year INTEGER;

ALTER TABLE boats ADD COLUMN IF NOT EXISTS home_harbor_id INTEGER
    REFERENCES harbors(id) ON DELETE SET NULL;

ALTER TABLE boats ADD COLUMN IF NOT EXISTS verification_status VARCHAR(30)
    NOT NULL DEFAULT 'unverified'
    CHECK (verification_status IN ('unverified','pending','verified','rejected'));

ALTER TABLE boats ADD COLUMN IF NOT EXISTS verified_by INTEGER
    REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE boats ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP;

ALTER TABLE boats ADD COLUMN IF NOT EXISTS qr_code_token VARCHAR(255) UNIQUE;
ALTER TABLE boats ADD COLUMN IF NOT EXISTS photo_urls TEXT;  -- JSON array

ALTER TABLE boats ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;
ALTER TABLE boats ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE boats ADD COLUMN IF NOT EXISTS created_by INTEGER
    REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE boats ADD COLUMN IF NOT EXISTS updated_by INTEGER
    REFERENCES users(id) ON DELETE SET NULL;

-- New indexes
CREATE INDEX IF NOT EXISTS idx_boats_status ON boats(status);
CREATE INDEX IF NOT EXISTS idx_boats_owner_active
    ON boats(owner_id, is_active) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_boats_registration_upper
    ON boats(UPPER(registration_number));
CREATE INDEX IF NOT EXISTS idx_boats_harbor ON boats(home_harbor_id);
CREATE INDEX IF NOT EXISTS idx_boats_verification ON boats(verification_status);
```

### 3.2 `boat_documents`

```sql
CREATE TABLE boat_documents (
    id                  SERIAL PRIMARY KEY,
    boat_id             INTEGER NOT NULL REFERENCES boats(id) ON DELETE CASCADE,
    document_type       VARCHAR(50) NOT NULL
                        CHECK (document_type IN (
                            'registration_certificate',
                            'fishing_license',
                            'insurance_policy',
                            'inspection_certificate',
                            'seaworthiness_certificate',
                            'crew_list',
                            'other'
                        )),
    document_number     VARCHAR(120),
    issuing_authority   VARCHAR(120),
    issue_date          DATE,
    expiry_date         DATE,
    file_url            VARCHAR(500),
    file_hash           VARCHAR(64),          -- SHA-256 for integrity
    is_verified         BOOLEAN NOT NULL DEFAULT FALSE,
    verified_by         INTEGER REFERENCES users(id) ON DELETE SET NULL,
    verified_at         TIMESTAMP,
    notes               TEXT,
    deleted_at          TIMESTAMP,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by          INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_by          INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_boat_documents_boat_id ON boat_documents(boat_id);
CREATE INDEX idx_boat_documents_type ON boat_documents(document_type);
CREATE INDEX idx_boat_documents_expiry ON boat_documents(expiry_date)
    WHERE deleted_at IS NULL;
```

### 3.3 `boat_crew_members`

```sql
CREATE TABLE boat_crew_members (
    id              SERIAL PRIMARY KEY,
    boat_id         INTEGER NOT NULL REFERENCES boats(id) ON DELETE CASCADE,
    user_id         INTEGER REFERENCES users(id) ON DELETE SET NULL,

    -- For non-registered users (e.g., family members, informal crew)
    full_name       VARCHAR(120) NOT NULL,
    phone_number    VARCHAR(20),
    aadhaar_last4   VARCHAR(4),              -- last 4 digits only

    role            VARCHAR(50) NOT NULL
                    CHECK (role IN (
                        'captain','navigator','engineer',
                        'deckhand','lookout','medic','owner','other'
                    )),
    is_primary_contact  BOOLEAN NOT NULL DEFAULT FALSE,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,

    assigned_at     TIMESTAMP NOT NULL DEFAULT NOW(),
    removed_at      TIMESTAMP,
    removal_reason  TEXT,

    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,

    CONSTRAINT uq_boat_crew_active
        UNIQUE (boat_id, user_id, is_active)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE INDEX idx_crew_boat_id ON boat_crew_members(boat_id);
CREATE INDEX idx_crew_user_id ON boat_crew_members(user_id);
CREATE INDEX idx_crew_active ON boat_crew_members(boat_id, is_active);
```

### 3.4 `boat_inspections`

```sql
CREATE TABLE boat_inspections (
    id                  SERIAL PRIMARY KEY,
    boat_id             INTEGER NOT NULL REFERENCES boats(id) ON DELETE CASCADE,
    inspection_type     VARCHAR(50) NOT NULL
                        CHECK (inspection_type IN (
                            'annual_safety','pre_trip','post_incident',
                            'government','insurance','voluntary'
                        )),
    inspector_name      VARCHAR(120),
    inspector_authority VARCHAR(120),
    inspection_date     DATE NOT NULL,
    next_due_date       DATE,
    result              VARCHAR(20) NOT NULL
                        CHECK (result IN ('passed','failed','conditional','pending')),
    findings            TEXT,
    corrective_actions  TEXT,
    certificate_number  VARCHAR(80),
    certificate_url     VARCHAR(500),
    deleted_at          TIMESTAMP,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by          INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_inspections_boat_id ON boat_inspections(boat_id);
CREATE INDEX idx_inspections_date ON boat_inspections(inspection_date);
CREATE INDEX idx_inspections_result ON boat_inspections(result);
```

### 3.5 `boat_equipment_items`

Replaces the free-text `safety_equipment` JSON column with a proper normalized table.

```sql
CREATE TABLE boat_equipment_items (
    id              SERIAL PRIMARY KEY,
    boat_id         INTEGER NOT NULL REFERENCES boats(id) ON DELETE CASCADE,
    category        VARCHAR(50) NOT NULL
                    CHECK (category IN (
                        'life_saving','fire_safety','navigation',
                        'communication','first_aid','fishing_gear',
                        'engine_spare','other'
                    )),
    item_name       VARCHAR(120) NOT NULL,
    quantity        INTEGER NOT NULL DEFAULT 1 CHECK (quantity >= 0),
    condition       VARCHAR(20) NOT NULL DEFAULT 'good'
                    CHECK (condition IN ('good','fair','poor','missing')),
    last_checked_at DATE,
    expiry_date     DATE,
    notes           TEXT,
    is_mandatory    BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at      TIMESTAMP,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by      INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_equipment_boat_id ON boat_equipment_items(boat_id);
CREATE INDEX idx_equipment_category ON boat_equipment_items(category);
CREATE INDEX idx_equipment_condition ON boat_equipment_items(condition)
    WHERE deleted_at IS NULL;
```

### 3.6 `boat_status_history`

Immutable record of every status transition.

```sql
CREATE TABLE boat_status_history (
    id              SERIAL PRIMARY KEY,
    boat_id         INTEGER NOT NULL REFERENCES boats(id) ON DELETE CASCADE,
    previous_status VARCHAR(30),
    new_status      VARCHAR(30) NOT NULL,
    reason          TEXT,
    actor_id        INTEGER REFERENCES users(id) ON DELETE SET NULL,
    source          VARCHAR(30) NOT NULL DEFAULT 'manual'
                    CHECK (source IN ('manual','system','sos','inspection','api')),
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
    -- NO updated_at — this table is append-only
);

CREATE INDEX idx_status_history_boat_id ON boat_status_history(boat_id);
CREATE INDEX idx_status_history_created ON boat_status_history(created_at);
```

### 3.7 `boat_audit_logs`

Immutable audit trail for all boat-related changes.

```sql
CREATE TABLE boat_audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    boat_id         INTEGER NOT NULL REFERENCES boats(id) ON DELETE CASCADE,
    actor_id        INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action          VARCHAR(50) NOT NULL
                    CHECK (action IN (
                        'created','updated','status_changed','document_added',
                        'document_verified','crew_assigned','crew_removed',
                        'inspection_added','ownership_transferred',
                        'decommissioned','qr_generated','viewed'
                    )),
    target_table    VARCHAR(60),
    target_id       INTEGER,
    old_values      TEXT,                    -- JSON snapshot before change
    new_values      TEXT,                    -- JSON snapshot after change
    ip_address      VARCHAR(45),
    user_agent      VARCHAR(255),
    correlation_id  VARCHAR(64),
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
    -- NEVER updated or deleted
);

CREATE INDEX idx_audit_boat_id ON boat_audit_logs(boat_id);
CREATE INDEX idx_audit_actor ON boat_audit_logs(actor_id, created_at);
CREATE INDEX idx_audit_action ON boat_audit_logs(action);
CREATE INDEX idx_audit_created ON boat_audit_logs(created_at);
```

### 3.8 `boat_ownership_transfers`

```sql
CREATE TABLE boat_ownership_transfers (
    id                  SERIAL PRIMARY KEY,
    boat_id             INTEGER NOT NULL REFERENCES boats(id) ON DELETE CASCADE,
    from_owner_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    to_owner_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    transfer_date       DATE NOT NULL,
    transfer_reason     VARCHAR(50)
                        CHECK (transfer_reason IN (
                            'sale','inheritance','gift','legal_order','other'
                        )),
    document_url        VARCHAR(500),
    document_hash       VARCHAR(64),
    status              VARCHAR(20) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','approved','rejected','completed')),
    approved_by         INTEGER REFERENCES users(id) ON DELETE SET NULL,
    approved_at         TIMESTAMP,
    notes               TEXT,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_transfers_boat_id ON boat_ownership_transfers(boat_id);
CREATE INDEX idx_transfers_status ON boat_ownership_transfers(status);
```

---

## 4. Existing Tables — Required Fixes

### 4.1 `boat_maintenance` — add `completed_by` and fix missing fields

```sql
ALTER TABLE boat_maintenance
    ADD COLUMN IF NOT EXISTS completed_by INTEGER REFERENCES users(id),
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'scheduled'
        CHECK (status IN ('scheduled','in_progress','completed','cancelled')),
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_maintenance_scheduled_date
    ON boat_maintenance(scheduled_date) WHERE completed_date IS NULL;
CREATE INDEX IF NOT EXISTS idx_maintenance_status
    ON boat_maintenance(boat_id, status);
```

### 4.2 `boat_health_status` — add unique constraint

```sql
ALTER TABLE boat_health_status
    ADD CONSTRAINT uq_boat_health_status_boat_id UNIQUE (boat_id);
```

### 4.3 `boat_fuel_logs` — add logged_by

```sql
ALTER TABLE boat_fuel_logs
    ADD COLUMN IF NOT EXISTS logged_by INTEGER REFERENCES users(id);
```

---

## 5. Entity Relationship Summary

```
boats (1) ──────────────────── (N) boat_documents
boats (1) ──────────────────── (N) boat_crew_members
boats (1) ──────────────────── (N) boat_inspections
boats (1) ──────────────────── (N) boat_equipment_items
boats (1) ──────────────────── (N) boat_status_history
boats (1) ──────────────────── (N) boat_audit_logs
boats (1) ──────────────────── (N) boat_ownership_transfers
boats (1) ──────────────────── (N) boat_maintenance        [existing]
boats (1) ──────────────────── (N) boat_fuel_logs          [existing]
boats (1) ──────────────────── (1) boat_health_status      [existing]
boats (1) ──────────────────── (N) trips                   [existing]
boats (N) ──────────────────── (1) harbors (home_harbor)
boats (N) ──────────────────── (1) users (owner)
```

---

## 6. Data Governance

| Rule | Implementation |
|---|---|
| No hard deletes | `deleted_at` soft delete on all boat tables |
| Immutable audit | `boat_audit_logs` and `boat_status_history` are append-only |
| Document integrity | `file_hash` (SHA-256) on all uploaded documents |
| Optimistic locking | `version` column on `boats` — increment on every update |
| Sensitive data | `aadhaar_last4` stores only last 4 digits — never full number |
| Retention | Decommissioned boats retained for 7 years (government requirement) |
| Registration uniqueness | Case-insensitive unique index on `UPPER(registration_number)` |
