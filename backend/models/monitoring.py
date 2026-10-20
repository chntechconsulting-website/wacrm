from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class EmployeeActivityLog(Base):
    __tablename__ = "employee_activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    
    # LOGIN, LOGOUT, LEAD_CREATED, LEAD_ASSIGNED, LEAD_VIEWED, LEAD_UPDATED, 
    # STATUS_CHANGED, FOLLOWUP_CREATED, FOLLOWUP_COMPLETED, CALL_STARTED, CALL_COMPLETED, 
    # WHATSAPP_SENT, CUSTOMER_CONVERTED, LEAD_LOST
    activity_type = Column(String(50), nullable=False, index=True)
    
    entity_type = Column(String(50), nullable=True)  # LEAD, CALL, FOLLOWUP, CUSTOMER, SYSTEM
    entity_id = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    employee = relationship("Employee", backref="activity_logs")

class EmployeePresence(Base):
    __tablename__ = "employee_presence"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), unique=True, nullable=False, index=True)
    
    # ONLINE, OFFLINE
    status = Column(String(20), default="OFFLINE", nullable=False)
    last_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_activity_type = Column(String(50), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    employee = relationship("Employee", backref="presence")

class FieldVisit(Base):
    __tablename__ = "field_visits"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True, index=True)
    
    customer_name = Column(String(150), nullable=True)
    checkin_lat = Column(String(50), nullable=True)
    checkin_lng = Column(String(50), nullable=True)
    checkin_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    checkout_lat = Column(String(50), nullable=True)
    checkout_lng = Column(String(50), nullable=True)
    checkout_time = Column(DateTime, nullable=True)
    
    notes = Column(Text, nullable=True)
    photo_url = Column(Text, nullable=True)
    
    # CHECKED_IN, COMPLETED
    status = Column(String(30), default="CHECKED_IN", nullable=False)

    employee = relationship("Employee", backref="field_visits")
    lead = relationship("Lead", backref="field_visits")

class MonitoringSetting(Base):
    __tablename__ = "monitoring_settings"

    id = Column(Integer, primary_key=True, index=True)
    activity_retention_days = Column(Integer, default=90, nullable=False)
    call_retention_days = Column(Integer, default=180, nullable=False)
    field_retention_days = Column(Integer, default=180, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
