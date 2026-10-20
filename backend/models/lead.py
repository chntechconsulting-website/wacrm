from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

from utils.timezone import get_ist_now

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(50), nullable=True)
    last_name = Column(String(50), nullable=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(30), index=True, nullable=False)
    whatsapp_number = Column(String(30), nullable=True)
    email = Column(String(100), index=True, nullable=True)
    designation = Column(String(100), nullable=True)

    company = Column(String(100), nullable=True)
    industry = Column(String(100), nullable=True)
    website = Column(String(150), nullable=True)
    company_size = Column(String(50), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    location = Column(String(150), nullable=True)

    meta_lead_id = Column(String(100), unique=True, index=True, nullable=True)
    meta_form_id = Column(String(100), nullable=True)

    website_id = Column(String(50), nullable=True, index=True)
    website_name = Column(String(100), nullable=True)
    landing_page = Column(String(255), nullable=True)

    source = Column(String(50), index=True, default="Manual", nullable=False)  # META, EXCEL, MANUAL, WEBSITE, REFERRAL
    status = Column(String(50), index=True, default="NEW", nullable=False)     # NEW, ASSIGNED, CONTACTED, INTERESTED, FOLLOW_UP, QUALIFIED, CONVERTED, NOT_INTERESTED, LOST
    campaign_name = Column(String(100), nullable=True)
    rating = Column(String(50), default="Warm", nullable=True)                  # Hot, Warm, Cold
    priority = Column(String(20), default="MEDIUM", nullable=True)              # High, Medium, Low
    requirement_notes = Column(Text, nullable=True)

    followup_date = Column(Date, nullable=True)
    followup_time = Column(String(20), nullable=True)

    assigned_to = Column(Integer, ForeignKey("employees.id"), index=True, nullable=True)
    assigned_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    assigned_at = Column(DateTime, nullable=True)

    # QuoteTask Integration Mapping Fields
    quotetask_quotation_id = Column(String(100), index=True, nullable=True)
    quotetask_quotation_number = Column(String(100), nullable=True)
    quotetask_quotation_status = Column(String(50), nullable=True)
    quotetask_quotation_amount = Column(Float, nullable=True)
    quotetask_quotation_url = Column(String(255), nullable=True)
    quotetask_po_id = Column(String(100), nullable=True)
    quotetask_po_number = Column(String(100), nullable=True)
    quotetask_po_status = Column(String(50), nullable=True)
    quotetask_synced_at = Column(DateTime, nullable=True)

    # Re-Inquiry Tracking Fields
    is_reinquiry = Column(Boolean, default=False, nullable=False, index=True)
    reinquiry_count = Column(Integer, default=0, nullable=False)
    total_enquiries = Column(Integer, default=1, nullable=False)
    first_enquiry_date = Column(DateTime, default=get_ist_now, nullable=False)
    latest_enquiry_date = Column(DateTime, default=get_ist_now, nullable=False)
    previous_sources = Column(String(255), nullable=True)
    latest_source = Column(String(50), nullable=True)

    created_at = Column(DateTime, default=get_ist_now, index=True, nullable=False)
    updated_at = Column(DateTime, default=get_ist_now, onupdate=get_ist_now, nullable=False)

    assigned_employee = relationship("Employee", foreign_keys=[assigned_to])
    assigned_by_employee = relationship("Employee", foreign_keys=[assigned_by])
    activities = relationship("LeadActivity", back_populates="lead", cascade="all, delete-orphan")
    assignments = relationship("LeadAssignment", back_populates="lead", cascade="all, delete-orphan")
    status_history = relationship("LeadStatusHistory", back_populates="lead", cascade="all, delete-orphan")
    followups = relationship("Followup", back_populates="lead", cascade="all, delete-orphan")
    customer = relationship("Customer", back_populates="lead", uselist=False)
    enquiries = relationship("LeadEnquiry", back_populates="lead", cascade="all, delete-orphan", order_by="LeadEnquiry.created_at.desc()")

class LeadEnquiry(Base):
    __tablename__ = "lead_enquiries"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    enquiry_number = Column(Integer, default=1, nullable=False)
    enquiry_type = Column(String(50), default="INITIAL", nullable=False)  # INITIAL or RE-INQUIRY
    source = Column(String(50), nullable=False)  # META, WEBSITE, EXCEL, MANUAL
    campaign_name = Column(String(100), nullable=True)
    website_name = Column(String(100), nullable=True)
    landing_page = Column(String(255), nullable=True)
    requirement_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=get_ist_now, nullable=False)

    lead = relationship("Lead", back_populates="enquiries")

class LeadAssignment(Base):
    __tablename__ = "lead_assignments"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    assigned_to = Column(Integer, ForeignKey("employees.id"), nullable=False)
    assigned_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    assignment_method = Column(String(50), default="MANUAL", nullable=False)  # MANUAL or AUTOMATIC
    notes = Column(Text, nullable=True)

    lead = relationship("Lead", back_populates="assignments")
    assigned_to_employee = relationship("Employee", foreign_keys=[assigned_to])
    assigned_by_employee = relationship("Employee", foreign_keys=[assigned_by])

class LeadStatusHistory(Base):
    __tablename__ = "lead_status_history"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    old_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=False)
    changed_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    changed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    lead = relationship("Lead", back_populates="status_history")
    changed_by_employee = relationship("Employee", foreign_keys=[changed_by])

class AutoAssignConfig(Base):
    __tablename__ = "auto_assign_configs"

    id = Column(Integer, primary_key=True, index=True)
    enabled = Column(Boolean, default=True, nullable=False)
    waiting_time_minutes = Column(Integer, default=60, nullable=False)  # Configurable: 15, 30, 60, 120, etc.
    assignment_method = Column(String(50), default="LEAST_ASSIGNED", nullable=False)  # LEAST_ASSIGNED, ROUND_ROBIN, HIERARCHICAL
    eligible_roles = Column(String(100), default="EMPLOYEE,MANAGER", nullable=False)
    working_hours_enabled = Column(Boolean, default=False, nullable=False)
    working_hours_start = Column(String(10), default="09:00", nullable=False)
    working_hours_end = Column(String(10), default="18:00", nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
