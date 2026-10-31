from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base
from utils.timezone import get_ist_now

class CallLog(Base):
    __tablename__ = "call_logs"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)
    
    provider = Column(String(50), nullable=False)
    provider_call_id = Column(String(100), unique=True, index=True, nullable=False)
    
    from_number = Column(String(30), nullable=False)
    to_number = Column(String(30), nullable=False)
    
    # Statuses: INITIATED, RINGING, ANSWERED, MISSED, BUSY, FAILED, COMPLETED
    call_status = Column(String(30), nullable=False, default="INITIATED", index=True)
    
    # Directions: OUTBOUND, INBOUND
    call_direction = Column(String(20), nullable=False, default="OUTBOUND")
    
    duration_seconds = Column(Integer, default=0, nullable=False)
    recording_url = Column(Text, nullable=True)
    
    # Call Transcription & AI Summary
    transcript = Column(Text, nullable=True)
    ai_summary = Column(Text, nullable=True)
    sentiment = Column(String(50), nullable=True)
    
    started_at = Column(DateTime, nullable=True)
    answered_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    
    notes = Column(Text, nullable=True)
    product_category = Column(String(50), nullable=True)  # BIOMETRIC, WAHRMS, UNCLASSIFIED

    # Mobile SIM (device dialer) metadata. Null for PBX/IVR calls.
    sim_account_id = Column(String(100), nullable=True)
    sim_label = Column(String(100), nullable=True)
    sim_slot = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=get_ist_now, nullable=False, index=True)

    lead = relationship("Lead", backref="call_logs")
    employee = relationship("Employee", backref="call_logs")
