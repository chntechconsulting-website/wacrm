from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    username = Column(String(100), nullable=True)
    action = Column(String(100), nullable=False, index=True)  # LOGIN, LOGOUT, LEAD_ASSIGNMENT, STATUS_CHANGE, etc.
    entity_type = Column(String(50), nullable=True)           # LEAD, CALL, WHATSAPP, USER, FOLLOWUP
    entity_id = Column(String(50), nullable=True)
    ip_address = Column(String(50), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = relationship("User", backref="audit_logs")
