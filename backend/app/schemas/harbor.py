from pydantic import BaseModel


class HarborOut(BaseModel):
    id: int
    name: str
    region: str
    state: str
    latitude: float
    longitude: float
    contact_phone: str | None
    description: str | None

    model_config = {"from_attributes": True}


class NearestHarborOut(BaseModel):
    harbor: HarborOut
    distance_km: float
    bearing_degrees: float
