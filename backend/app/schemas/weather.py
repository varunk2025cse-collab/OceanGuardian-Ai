from datetime import datetime
from pydantic import BaseModel


class WeatherAlertOut(BaseModel):
    id: int
    title: str
    description: str
    hazard_type: str
    severity: str
    center_latitude: float
    center_longitude: float
    radius_km: float
    valid_from: datetime
    valid_until: datetime
    source: str | None

    model_config = {"from_attributes": True}
