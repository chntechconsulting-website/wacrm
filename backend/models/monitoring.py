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
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    
    customer_name = Column(String(150), nullable=True)
    checkin_lat = Column(String(50), nullable=True)
    checkin_lng = Column(String(50), nullable=True)
    checkin_address = Column(String(255), nullable=True)
    checkin_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    checkout_lat = Column(String(50), nullable=True)
    checkout_lng = Column(String(50), nullable=True)
    checkout_time = Column(DateTime, nullable=True)
    
    photo_url = Column(Text, nullable=True)  # Company board photo
    visiting_card_url = Column(Text, nullable=True)  # Visiting card photo
    customer_requirements = Column(Text, nullable=True)
    visit_outcome = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    
    followup_id = Column(Integer, ForeignKey("followups.id"), nullable=True, index=True)
    client_token = Column(String(100), nullable=True, index=True)
    
    # CHECKED_IN, COMPLETED
    status = Column(String(30), default="COMPLETED", nullable=False)

    employee = relationship("Employee", backref="field_visits")
    lead = relationship("Lead", backref="field_visits")
    customer = relationship("Customer", foreign_keys=[customer_id])
    followup = relationship("Followup", foreign_keys=[followup_id])

    def to_dict(self):
        emp_name = self.employee.name if self.employee else None
        lead_name = self.lead.name if self.lead else (self.customer.contact_name if self.customer else self.customer_name)
        fu_info = None
        if self.followup:
            fu_info = {
                "id": self.followup.id,
                "followup_date": str(self.followup.followup_date),
                "followup_time": self.followup.followup_time,
                "priority": self.followup.priority,
                "status": self.followup.status,
                "notes": self.followup.notes
            }

        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "employee_name": emp_name or "Field Agent",
            "lead_id": self.lead_id,
            "lead_name": lead_name,
            "customer_id": self.customer_id,
            "customer_name": self.customer_name or lead_name or "Customer",
            "checkin_time": self.checkin_time.isoformat() if self.checkin_time else None,
            "checkout_time": self.checkout_time.isoformat() if self.checkout_time else None,
            "checkin_lat": self.checkin_lat,
            "checkin_lng": self.checkin_lng,
            "checkin_address": self.checkin_address,
            "checkout_lat": self.checkout_lat,
            "checkout_lng": self.checkout_lng,
            "photo_url": self.photo_url,
            "visiting_card_url": self.visiting_card_url,
            "customer_requirements": self.customer_requirements,
            "visit_outcome": self.visit_outcome,
            "notes": self.notes,
            "status": self.status,
            "followup_id": self.followup_id,
            "followup": fu_info,
            "client_token": self.client_token
        }

class MonitoringSetting(Base):
    __tablename__ = "monitoring_settings"

    id = Column(Integer, primary_key=True, index=True)
    activity_retention_days = Column(Integer, default=90, nullable=False)
    call_retention_days = Column(Integer, default=180, nullable=False)
    field_retention_days = Column(Integer, default=180, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
