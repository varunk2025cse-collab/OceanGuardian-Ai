from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class UserRegister(BaseModel):
    phone_number: str = Field(..., min_length=8, max_length=20)
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2, max_length=120)
    # Public self-registration is limited to fisherman/family. Operator
    # (Rescue Dashboard) accounts are provisioned out-of-band — via seed.py
    # or a future admin-only endpoint — never through this open endpoint.
    role: str = Field(default="fisherman", pattern="^(fisherman|family)$")
    preferred_language: str = Field(default="ta", max_length=10)

    boat_name: str | None = None
    boat_registration_number: str | None = None
    home_harbor: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None

    @field_validator("phone_number")
    @classmethod
    def strip_phone(cls, v: str) -> str:
        return v.strip().replace(" ", "")


class UserLogin(BaseModel):
    phone_number: str
    password: str


class UserOut(BaseModel):
    id: int
    phone_number: str
    full_name: str
    role: str
    preferred_language: str
    boat_name: str | None = None
    boat_registration_number: str | None = None
    home_harbor: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    last_sync_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    phone_number: str


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6)
