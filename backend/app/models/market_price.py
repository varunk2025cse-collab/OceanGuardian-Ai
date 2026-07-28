"""Daily fish market price reference data, used by the Market Price screen."""
from sqlalchemy import Column, Integer, Float, String, Date, DateTime, func
from app.database import Base


class MarketPrice(Base):
    __tablename__ = "market_prices"

    id = Column(Integer, primary_key=True, index=True)
    species = Column(String(80), nullable=False, index=True)
    market_name = Column(String(120), nullable=False)
    harbor_region = Column(String(120), nullable=False, index=True)
    price_per_kg = Column(Float, nullable=False)
    currency = Column(String(8), nullable=False, default="INR")
    price_date = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
