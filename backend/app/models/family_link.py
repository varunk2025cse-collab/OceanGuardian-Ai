"""
Links a family member account to one or more fishermen they are allowed to
track. Many-to-many: a fisherman's spouse and adult child can both watch the
same boat; one family account can follow multiple boats in a household.
"""
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, func, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class FamilyLink(Base):
    __tablename__ = "family_links"
    __table_args__ = (
        UniqueConstraint("fisherman_id", "family_user_id", name="uq_family_link_pair"),
    )

    id = Column(Integer, primary_key=True, index=True)
    fisherman_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    family_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    relation = Column(String(50), nullable=True)  # e.g. "Wife", "Son"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    fisherman = relationship("User", foreign_keys=[fisherman_id])
    family_user = relationship("User", foreign_keys=[family_user_id])
