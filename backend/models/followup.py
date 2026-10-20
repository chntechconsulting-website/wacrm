from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Followup(Base):
    __tablename__ = "followups"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    assigned_to = Column(Integer, ForeignKey("employees.id"), nullable=False)
    followup_date = Column(Date, nullable=False)
    followup_time = Column(String(20), nullable=True)
    notes = Column(Text, nullable=True)
    priority = Column(String(20), default="MEDIUM", nullable=False)  # LOW, MEDIUM, HIGH
    status = Column(String(20), default="Pending", nullable=False)  # Pending, Completed, Cancelled
    created_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    
    # 1-Hour Reminder tracking
    reminder_sent = Column(Boolean, default=False, nullable=False)
    reminder_sent_at = Column(DateTime, nullable=True)
    snoozed_until = Column(DateTime, nullable=True)
    reminder_dismissed = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    lead = relationship("Lead", back_populates="followups")
    assigned_employee = relationship("Employee", foreign_keys=[assigned_to])
    creator_employee = relationship("Employee", foreign_keys=[created_by])
