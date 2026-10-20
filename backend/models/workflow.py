from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class FinanceHandoff(Base):
    __tablename__ = "finance_handoffs"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), index=True, nullable=False)
    quotation_id = Column(Integer, ForeignKey("quotations.id"), nullable=True)
    
    # Customer and quotation/proforma references
    quotation_number = Column(String(100), nullable=True)
    quotation_url = Column(String(500), nullable=True)
    proforma_id = Column(Integer, ForeignKey("quotations.id"), nullable=True)
    proforma_number = Column(String(100), nullable=True)
    selected_bundle = Column(String(100), nullable=True)
    product_category = Column(String(50), nullable=True)
    licence_count = Column(Integer, nullable=True)
    addons_summary = Column(JSON, nullable=True)
    biometric_device_count = Column(Integer, default=0, nullable=True)
    deal_adjustment_reason = Column(Text, nullable=True)
    customer_name = Column(String(150), nullable=False)
    company_name = Column(String(150), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(100), nullable=True)
    address = Column(String(255), nullable=True)
    
    # Sales info
    sales_employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    sales_employee_name = Column(String(100), nullable=True)
    
    # Items & Amounts
    products_services = Column(JSON, nullable=True)
    final_amount = Column(Float, default=0.0, nullable=False)
    paid_amount = Column(Float, default=0.0, nullable=False)
    
    # Finance Processing Status
    status = Column(String(50), default="PAYMENT_PENDING", nullable=False) # PAYMENT_PENDING, PAID, REJECTED, CANCELLED
    payment_status = Column(String(50), default="PAYMENT_PENDING", nullable=False) # PAYMENT_PENDING, PARTIALLY_PAID, PAID
    payment_mode = Column(String(50), nullable=True) # Bank Transfer, UPI, Cheque, Card, Cash
    invoice_number = Column(String(100), nullable=True)
    invoice_url = Column(String(500), nullable=True)
    payment_date = Column(DateTime, nullable=True)
    customer_requirements = Column(Text, nullable=True)
    
    # SENSITIVE Finance fields (Protected from Support and unauthorized roles)
    bank_reference = Column(String(150), nullable=True) # UTR / Transaction Ref / Cheque No
    bank_name = Column(String(100), nullable=True)
    internal_finance_notes = Column(Text, nullable=True)
    payment_credentials = Column(Text, nullable=True) # Sensitive internal payment data
    
    # Audit info
    confirmed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    lead = relationship("Lead", foreign_keys=[lead_id])
    customer = relationship("Customer", foreign_keys=[customer_id])
    sales_employee = relationship("Employee", foreign_keys=[sales_employee_id])
    confirmed_by_user = relationship("User", foreign_keys=[confirmed_by_user_id])
    support_handoff = relationship("SupportHandoff", back_populates="finance_handoff", uselist=False, cascade="all, delete-orphan")


class SupportHandoff(Base):
    __tablename__ = "support_handoffs"

    id = Column(Integer, primary_key=True, index=True)
    finance_handoff_id = Column(Integer, ForeignKey("finance_handoffs.id"), unique=True, index=True, nullable=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), index=True, nullable=False)
    deal_id = Column(Integer, nullable=True, index=True)

    # Support / Onboarding scoped customer information
    customer_name = Column(String(150), nullable=False)
    company_name = Column(String(150), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(100), nullable=True)
    
    # Purchased products / services (sanitized for onboarding)
    product_service = Column(String(255), nullable=True) # Specific deal product/service e.g. "CRM Subscription"
    customer_users_count = Column(Integer, default=1, nullable=True) # Number of Customer Employees/Users
    total_deal_amount = Column(Float, default=0.0, nullable=False) # Deal Amount e.g. 500000.0
    purchased_products = Column(JSON, nullable=True) # [{name, qty, package, amount}]
    quotation_number = Column(String(100), nullable=True)
    quotation_url = Column(String(500), nullable=True)
    proforma_id = Column(Integer, ForeignKey("quotations.id"), nullable=True)
    proforma_number = Column(String(100), nullable=True)
    selected_bundle = Column(String(100), nullable=True)
    product_category = Column(String(50), nullable=True)
    addons_summary = Column(JSON, nullable=True)
    biometric_device_count = Column(Integer, default=0, nullable=True)
    deal_adjustment_reason = Column(Text, nullable=True)
    invoice_number = Column(String(100), nullable=True)
    
    # Payment status snapshot
    paid_amount = Column(Float, default=0.0, nullable=False)
    payment_status = Column(String(50), default="PAID", nullable=False)
    payment_date = Column(DateTime, nullable=True)
    
    # Sales attribution
    sales_employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    sales_employee_name = Column(String(100), nullable=True)
    customer_requirements = Column(Text, nullable=True)
    
    # Assigned Support Manager (Required on Deal WON)
    support_manager_id = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)
    support_manager_name = Column(String(100), nullable=True)
    won_at = Column(DateTime, nullable=True)

    # Support Lifecycle: PENDING_ONBOARDING -> CONTACTED -> ONBOARDING_IN_PROGRESS -> COMPLETED
    onboarding_status = Column(String(50), default="PENDING_ONBOARDING", nullable=False)
    assigned_agent_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    assigned_agent_name = Column(String(100), nullable=True)
    support_notes = Column(Text, nullable=True)
    
    # Timestamps
    contacted_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    finance_handoff = relationship("FinanceHandoff", back_populates="support_handoff")
    lead = relationship("Lead", foreign_keys=[lead_id])
    customer = relationship("Customer", foreign_keys=[customer_id])
    support_manager = relationship("Employee", foreign_keys=[support_manager_id])
    assigned_agent = relationship("Employee", foreign_keys=[assigned_agent_id])


class WorkflowTimelineEvent(Base):
    __tablename__ = "workflow_timeline_events"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), index=True, nullable=True)
    
    stage = Column(String(50), nullable=False) # SALES, FINANCE, SUPPORT
    previous_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=False)
    
    performed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    performed_by_name = Column(String(100), nullable=True)
    role = Column(String(50), nullable=True)
    
    title = Column(String(150), nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    lead = relationship("Lead", foreign_keys=[lead_id])
    customer = relationship("Customer", foreign_keys=[customer_id])
    performed_by_user = relationship("User", foreign_keys=[performed_by_id])
