from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class SalesTarget(Base):
    __tablename__ = "sales_targets"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), index=True, nullable=False)
    target_amount = Column(Float, default=0.0, nullable=False)
    period_type = Column(String(20), default="monthly", nullable=False)  # monthly, quarterly, yearly
    period_month = Column(Integer, nullable=True)  # 1 to 12 (nullable for yearly)
    period_year = Column(Integer, nullable=False)  # e.g., 2026
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    employee = relationship("Employee", foreign_keys=[employee_id])
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        UniqueConstraint("employee_id", "period_type", "period_month", "period_year", name="uq_employee_target_period"),
    )
