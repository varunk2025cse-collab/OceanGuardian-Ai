import json
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class BoatCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    registration_number: str | None = Field(default=None, max_length=60)
    color: str | None = None
    length_meters: float | None = None
    engine_type: str | None = None
    engine_horsepower: int | None = None
    fuel_capacity_liters: float | None = None
    safety_equipment: list[str] | None = None  # stored as JSON string in DB


class BoatUpdate(BaseModel):
    name: str | None = None
    registration_number: str | None = None
    color: str | None = None
    length_meters: float | None = None
    engine_type: str | None = None
    engine_horsepower: int | None = None
    fuel_capacity_liters: float | None = None
    safety_equipment: list[str] | None = None
    is_active: bool | None = None


class BoatOut(BaseModel):
    id: int
    owner_id: int
    name: str
    registration_number: str | None
    color: str | None
    length_meters: float | None
    engine_type: str | None
    engine_horsepower: int | None
    fuel_capacity_liters: float | None
    safety_equipment: list[str] | None
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
