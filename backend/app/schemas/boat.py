"""Boat schemas — v1 (backward compat) + v2 (enterprise).

v1 schemas (BoatCreate, BoatUpdate, BoatOut) are unchanged — the v1
router at /api/v1/boats/ depends on them.

v2 schemas carry the full enterprise field set from migration 009.
"""
import json
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# v1 schemas — DO NOT CHANGE (v1 router depends on these)
# =============================================================================

class BoatCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    registration_number: Optional[str] = Field(default=None, max_length=60)
    color: Optional[str] = None
    length_meters: Optional[float] = None
    engine_type: Optional[str] = None
    engine_horsepower: Optional[int] = None
    fuel_capacity_liters: Optional[float] = None
    safety_equipment: Optional[list[str]] = None


class BoatUpdate(BaseModel):
    name: Optional[str] = None
    registration_number: Optional[str] = None
    color: Optional[str] = None
    length_meters: Optional[float] = None
    engine_type: Optional[str] = None
    engine_horsepower: Optional[int] = None
    fuel_capacity_liters: Optional[float] = None
    safety_equipment: Optional[list[str]] = None
    is_active: Optional[bool] = None


class BoatOut(BaseModel):
    id: int
    owner_id: int
    name: str
    registration_number: Optional[str]
    color: Optional[str]
    length_meters: Optional[float]
    engine_type: Optional[str]
    engine_horsepower: Optional[int]
    fuel_capacity_liters: Optional[float]
    safety_equipment: Optional[list[str]]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("safety_equipment", mode="before")
    @classmethod
    def parse_safety_equipment(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return []
        return v


# =============================================================================
# v2 schemas — enterprise field set
# =============================================================================

VALID_VESSEL_CLASSES = frozenset({
    "mechanized", "motorized", "non_motorized",
    "trawler", "gillnetter", "purse_seiner", "other",
})
VALID_HULL_MATERIALS = frozenset({"wood", "fiberglass", "steel", "aluminum", "other"})
VALID_STATUSES = frozenset({
    "registered", "active", "inactive", "maintenance",
    "emergency", "lost", "damaged", "decommissioned",
})
VALID_VERIFICATION_STATUSES = frozenset({"unverified", "pending", "verified", "rejected"})
VALID_DOCUMENT_TYPES = frozenset({
    "registration_certificate", "fishing_license", "insurance_policy",
    "inspection_certificate", "seaworthiness_certificate", "crew_list", "other",
})
VALID_CREW_ROLES = frozenset({
    "captain", "navigator", "engineer", "deckhand",
    "lookout", "medic", "owner", "other",
})
VALID_INSPECTION_TYPES = frozenset({
    "annual_safety", "pre_trip", "post_incident",
    "government", "insurance", "voluntary",
})
VALID_INSPECTION_RESULTS = frozenset({"passed", "failed", "conditional", "pending"})
VALID_EQUIPMENT_CATEGORIES = frozenset({
    "life_saving", "fire_safety", "navigation", "communication",
    "first_aid", "fishing_gear", "engine_spare", "other",
})
VALID_EQUIPMENT_CONDITIONS = frozenset({"good", "fair", "poor", "missing"})
VALID_TRANSFER_REASONS = frozenset({"sale", "inheritance", "gift", "legal_order", "other"})


class BoatV2Create(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    registration_number: Optional[str] = Field(default=None, max_length=60)
    vessel_class: Optional[str] = None
    hull_material: Optional[str] = None
    color: Optional[str] = Field(default=None, max_length=60)
    length_meters: Optional[float] = Field(default=None, gt=0)
    beam_meters: Optional[float] = Field(default=None, gt=0)
    draft_meters: Optional[float] = Field(default=None, gt=0)
    year_built: Optional[int] = Field(default=None, ge=1900, le=2100)
    engine_type: Optional[str] = Field(default=None, max_length=80)
    engine_make: Optional[str] = Field(default=None, max_length=80)
    engine_model: Optional[str] = Field(default=None, max_length=80)
    engine_serial_number: Optional[str] = Field(default=None, max_length=80)
    engine_year: Optional[int] = Field(default=None, ge=1900, le=2100)
    engine_horsepower: Optional[int] = Field(default=None, gt=0)
    fuel_capacity_liters: Optional[float] = Field(default=None, gt=0)
    home_harbor_id: Optional[int] = None

    @field_validator("vessel_class")
    @classmethod
    def validate_vessel_class(cls, v):
        if v is not None and v not in VALID_VESSEL_CLASSES:
            raise ValueError(f"vessel_class must be one of {sorted(VALID_VESSEL_CLASSES)}")
        return v

    @field_validator("hull_material")
    @classmethod
    def validate_hull_material(cls, v):
        if v is not None and v not in VALID_HULL_MATERIALS:
            raise ValueError(f"hull_material must be one of {sorted(VALID_HULL_MATERIALS)}")
        return v


class BoatV2Update(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    registration_number: Optional[str] = Field(default=None, max_length=60)
    vessel_class: Optional[str] = None
    hull_material: Optional[str] = None
    color: Optional[str] = None
    length_meters: Optional[float] = Field(default=None, gt=0)
    beam_meters: Optional[float] = Field(default=None, gt=0)
    draft_meters: Optional[float] = Field(default=None, gt=0)
    year_built: Optional[int] = Field(default=None, ge=1900, le=2100)
    engine_type: Optional[str] = None
    engine_make: Optional[str] = None
    engine_model: Optional[str] = None
    engine_serial_number: Optional[str] = None
    engine_year: Optional[int] = Field(default=None, ge=1900, le=2100)
    engine_horsepower: Optional[int] = Field(default=None, gt=0)
    fuel_capacity_liters: Optional[float] = Field(default=None, gt=0)
    home_harbor_id: Optional[int] = None
    is_active: Optional[bool] = None
    version: Optional[int] = None  # client must echo current version for optimistic lock

    @field_validator("vessel_class")
    @classmethod
    def validate_vessel_class(cls, v):
        if v is not None and v not in VALID_VESSEL_CLASSES:
            raise ValueError(f"vessel_class must be one of {sorted(VALID_VESSEL_CLASSES)}")
        return v

    @field_validator("hull_material")
    @classmethod
    def validate_hull_material(cls, v):
        if v is not None and v not in VALID_HULL_MATERIALS:
            raise ValueError(f"hull_material must be one of {sorted(VALID_HULL_MATERIALS)}")
        return v


class BoatV2Out(BaseModel):
    id: int
    owner_id: int
    name: str
    registration_number: Optional[str]
    status: str
    vessel_class: Optional[str]
    hull_material: Optional[str]
    color: Optional[str]
    length_meters: Optional[float]
    beam_meters: Optional[float]
    draft_meters: Optional[float]
    year_built: Optional[int]
    engine_type: Optional[str]
    engine_make: Optional[str]
    engine_model: Optional[str]
    engine_serial_number: Optional[str]
    engine_year: Optional[int]
    engine_horsepower: Optional[int]
    fuel_capacity_liters: Optional[float]
    home_harbor_id: Optional[int]
    verification_status: str
    verified_at: Optional[datetime]
    qr_code_token: Optional[str]
    is_active: bool
    version: int
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class BoatStatusUpdate(BaseModel):
    status: str
    reason: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
        return v


class BoatVerifyUpdate(BaseModel):
    verification_status: str
    notes: Optional[str] = None

    @field_validator("verification_status")
    @classmethod
    def validate_verification_status(cls, v):
        if v not in VALID_VERIFICATION_STATUSES:
            raise ValueError(f"verification_status must be one of {sorted(VALID_VERIFICATION_STATUSES)}")
        return v


class BoatDecommission(BaseModel):
    reason: Optional[str] = None


# ── Sub-resource schemas ──────────────────────────────────────────────────────

class DocumentCreate(BaseModel):
    document_type: str
    document_number: Optional[str] = Field(default=None, max_length=120)
    issuing_authority: Optional[str] = Field(default=None, max_length=120)
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    file_url: Optional[str] = Field(default=None, max_length=500)
    file_hash: Optional[str] = Field(default=None, max_length=64)
    notes: Optional[str] = None

    @field_validator("document_type")
    @classmethod
    def validate_document_type(cls, v):
        if v not in VALID_DOCUMENT_TYPES:
            raise ValueError(f"document_type must be one of {sorted(VALID_DOCUMENT_TYPES)}")
        return v


class DocumentOut(BaseModel):
    id: int
    boat_id: int
    document_type: str
    document_number: Optional[str]
    issuing_authority: Optional[str]
    issue_date: Optional[date]
    expiry_date: Optional[date]
    file_url: Optional[str]
    file_hash: Optional[str]
    is_verified: bool
    verified_at: Optional[datetime]
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class CrewMemberCreate(BaseModel):
    user_id: Optional[int] = None
    full_name: str = Field(..., min_length=1, max_length=120)
    phone_number: Optional[str] = Field(default=None, max_length=20)
    aadhaar_last4: Optional[str] = Field(default=None, min_length=4, max_length=4)
    role: str
    is_primary_contact: bool = False

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        if v not in VALID_CREW_ROLES:
            raise ValueError(f"role must be one of {sorted(VALID_CREW_ROLES)}")
        return v

    @field_validator("aadhaar_last4")
    @classmethod
    def validate_aadhaar(cls, v):
        if v is not None and not v.isdigit():
            raise ValueError("aadhaar_last4 must be 4 digits")
        return v


class CrewMemberOut(BaseModel):
    id: int
    boat_id: int
    user_id: Optional[int]
    full_name: str
    phone_number: Optional[str]
    role: str
    is_primary_contact: bool
    is_active: bool
    assigned_at: datetime
    removed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class CrewMemberRemove(BaseModel):
    reason: Optional[str] = None


class InspectionCreate(BaseModel):
    inspection_type: str
    inspector_name: Optional[str] = Field(default=None, max_length=120)
    inspector_authority: Optional[str] = Field(default=None, max_length=120)
    inspection_date: date
    next_due_date: Optional[date] = None
    result: str
    findings: Optional[str] = None
    corrective_actions: Optional[str] = None
    certificate_number: Optional[str] = Field(default=None, max_length=80)
    certificate_url: Optional[str] = Field(default=None, max_length=500)

    @field_validator("inspection_type")
    @classmethod
    def validate_inspection_type(cls, v):
        if v not in VALID_INSPECTION_TYPES:
            raise ValueError(f"inspection_type must be one of {sorted(VALID_INSPECTION_TYPES)}")
        return v

    @field_validator("result")
    @classmethod
    def validate_result(cls, v):
        if v not in VALID_INSPECTION_RESULTS:
            raise ValueError(f"result must be one of {sorted(VALID_INSPECTION_RESULTS)}")
        return v


class InspectionOut(BaseModel):
    id: int
    boat_id: int
    inspection_type: str
    inspector_name: Optional[str]
    inspector_authority: Optional[str]
    inspection_date: date
    next_due_date: Optional[date]
    result: str
    findings: Optional[str]
    corrective_actions: Optional[str]
    certificate_number: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class EquipmentItemCreate(BaseModel):
    category: str
    item_name: str = Field(..., min_length=1, max_length=120)
    quantity: int = Field(default=1, ge=0)
    condition: str = "good"
    last_checked_at: Optional[date] = None
    expiry_date: Optional[date] = None
    notes: Optional[str] = None
    is_mandatory: bool = False

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        if v not in VALID_EQUIPMENT_CATEGORIES:
            raise ValueError(f"category must be one of {sorted(VALID_EQUIPMENT_CATEGORIES)}")
        return v

    @field_validator("condition")
    @classmethod
    def validate_condition(cls, v):
        if v not in VALID_EQUIPMENT_CONDITIONS:
            raise ValueError(f"condition must be one of {sorted(VALID_EQUIPMENT_CONDITIONS)}")
        return v


class EquipmentItemUpdate(BaseModel):
    quantity: Optional[int] = Field(default=None, ge=0)
    condition: Optional[str] = None
    last_checked_at: Optional[date] = None
    expiry_date: Optional[date] = None
    notes: Optional[str] = None

    @field_validator("condition")
    @classmethod
    def validate_condition(cls, v):
        if v is not None and v not in VALID_EQUIPMENT_CONDITIONS:
            raise ValueError(f"condition must be one of {sorted(VALID_EQUIPMENT_CONDITIONS)}")
        return v


class EquipmentItemOut(BaseModel):
    id: int
    boat_id: int
    category: str
    item_name: str
    quantity: int
    condition: str
    last_checked_at: Optional[date]
    expiry_date: Optional[date]
    notes: Optional[str]
    is_mandatory: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class OwnershipTransferCreate(BaseModel):
    to_owner_id: int
    transfer_date: date
    transfer_reason: Optional[str] = None
    document_url: Optional[str] = Field(default=None, max_length=500)
    document_hash: Optional[str] = Field(default=None, max_length=64)
    notes: Optional[str] = None

    @field_validator("transfer_reason")
    @classmethod
    def validate_transfer_reason(cls, v):
        if v is not None and v not in VALID_TRANSFER_REASONS:
            raise ValueError(f"transfer_reason must be one of {sorted(VALID_TRANSFER_REASONS)}")
        return v


class OwnershipTransferOut(BaseModel):
    id: int
    boat_id: int
    from_owner_id: int
    to_owner_id: int
    transfer_date: date
    transfer_reason: Optional[str]
    status: str
    approved_at: Optional[datetime]
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class StatusHistoryOut(BaseModel):
    id: int
    boat_id: int
    previous_status: Optional[str]
    new_status: str
    reason: Optional[str]
    actor_id: Optional[int]
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogOut(BaseModel):
    id: int
    boat_id: int
    actor_id: Optional[int]
    action: str
    target_table: Optional[str]
    target_id: Optional[int]
    old_values: Optional[str]
    new_values: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class FleetSummaryOut(BaseModel):
    total_boats: int
    by_status: dict[str, int]
    by_verification: dict[str, int]
    documents_expiring_30_days: int
    boats_with_active_trips: int


class PaginatedBoats(BaseModel):
    data: list[BoatV2Out]
    meta: dict
