from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base
from utils.timezone import get_ist_now

class CallLog(Base):
    __tablename__ = "call_logs"
    __table_args__ = (
        Index("ix_call_logs_lead_created", "lead_id", "created_at"),
    )

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

    # Recording identity. A recording may only be linked to a call through its
    # own provider uniqueid (or an explicit recording URL delivered for that
    # exact call) - never by phone number, list position or timestamp guesses.
    recording_id = Column(String(150), nullable=True, index=True)
    recording_duration_seconds = Column(Integer, nullable=True)
    recording_source = Column(String(30), nullable=True)  # DOOCTI, UPLOAD, DEVICE
    recording_attached_at = Column(DateTime, nullable=True)
    # Canonical recording sync status shared by mobile and web:
    # AVAILABLE, PENDING_SYNC, RECORDING_UNAVAILABLE, UPLOAD_FAILED,
    # VERIFICATION_FAILED.
    recording_status = Column(String(40), nullable=True)
    recording_status_detail = Column(String(255), nullable=True)
    recording_checksum = Column(String(64), nullable=True)
    recording_verified_at = Column(DateTime, nullable=True)
    recording_consent_at = Column(DateTime, nullable=True)
    
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

    # Stable identity of the exact Android CallLog row. The device-history sync
    # and the live in-app result both carry this value, so whichever request
    # arrives first wins and the other updates that same CRM row. The unique
    # index is the database-level guard against concurrent duplicate inserts.
    # NULL is allowed for PBX/IVR calls, legacy rows and live results that were
    # produced before Android had written its call-log row.
    native_call_reference = Column(
        String(100), nullable=True, unique=True, index=True
    )
    created_at = Column(DateTime, default=get_ist_now, nullable=False, index=True)

    lead = relationship("Lead", backref="call_logs")
    employee = relationship("Employee", backref="call_logs")
