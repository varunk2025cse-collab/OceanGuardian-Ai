from datetime import date, datetime
from pydantic import BaseModel


class MarketPriceOut(BaseModel):
    id: int
    species: str
    market_name: str
    harbor_region: str
    price_per_kg: float
    currency: str
    price_date: date

    model_config = {"from_attributes": True}
