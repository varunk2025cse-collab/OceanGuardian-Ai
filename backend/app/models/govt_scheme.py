"""Government welfare / subsidy schemes for fishermen, used by the Schemes screen."""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, func
from app.database import Base


class GovtScheme(Base):
    __tablename__ = "govt_schemes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    category = Column(String(60), nullable=False)  # subsidy, insurance, loan, relief, training
    region = Column(String(120), nullable=False, default="National")
    description = Column(Text, nullable=False)
    eligibility = Column(Text, nullable=False)
    how_to_apply = Column(Text, nullable=False)
    contact_info = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
