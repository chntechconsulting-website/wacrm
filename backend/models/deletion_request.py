from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class DeletionRequest(Base):
    __tablename__ = "deletion_requests"

    id = Column(Integer, primary_key=True, index=True)
    
    # Target entity details (LEAD, CUSTOMER, FOLLOWUP, EMPLOYEE, USER)
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)
    entity_name = Column(String(255), nullable=True)
    
    # Request details
    requested_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    requested_by_name = Column(String(100), nullable=True)
    requested_by_role = Column(String(50), nullable=True, default="MANAGER")
    reason = Column(Text, nullable=True)
    
    # Approval workflow status: PENDING, APPROVED, REJECTED
    status = Column(String(30), nullable=False, default="PENDING", index=True)
    
    # Admin review details
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_by_name = Column(String(100), nullable=True)
    review_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    reviewed_at = Column(DateTime, nullable=True)

    requested_by_user = relationship("User", foreign_keys=[requested_by_user_id], backref="requested_deletions")
    reviewed_by_user = relationship("User", foreign_keys=[reviewed_by_user_id], backref="reviewed_deletions")
