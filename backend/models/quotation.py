from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Quotation(Base):
    __tablename__ = "quotations"

    id = Column(Integer, primary_key=True, index=True)
    doc_type = Column(String(50), default="quotation", nullable=False)  # quotation, proforma, invoice, po
    selected_bundle = Column(String(100), nullable=True)                 # hr_atm, hr_payroll, hr_atm_payroll
    product_category = Column(String(50), default="wahrms", nullable=True) # wahrms, biometric
    doc_number = Column(String(100), unique=True, index=True, nullable=False)
    status = Column(String(50), default="issued", nullable=False)        # draft, issued, cancelled, converted
    payment_status = Column(String(50), default="unpaid", nullable=False) # paid, unpaid, partial
    
    # Linked entities
    lead_id = Column(Integer, ForeignKey("leads.id"), index=True, nullable=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), index=True, nullable=True)
    source_quotation_id = Column(Integer, ForeignKey("quotations.id"), index=True, nullable=True)
    source_quotation_number = Column(String(100), nullable=True)
    created_by = Column(Integer, ForeignKey("employees.id"), index=True, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    assigned_to = Column(Integer, ForeignKey("employees.id"), index=True, nullable=True)
    
    creator_employee = relationship("Employee", foreign_keys=[created_by])
    creator_user = relationship("User", foreign_keys=[created_by_user_id])
    assigned_employee = relationship("Employee", foreign_keys=[assigned_to])
    
    # Customer snapshot
    customer_name = Column(String(150), nullable=False)
    company_name = Column(String(150), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(100), nullable=True)
    address = Column(String(255), nullable=True)
    state = Column(String(100), default="Tamil Nadu", nullable=True)
    state_code = Column(String(10), default="33", nullable=True)
    gstin = Column(String(50), nullable=True)
    
    # Financial details
    tax_mode = Column(String(20), default="intra", nullable=False) # intra (CGST+SGST), inter (IGST)
    subtotal = Column(Float, default=0.0, nullable=False)
    cgst = Column(Float, default=0.0, nullable=False)
    sgst = Column(Float, default=0.0, nullable=False)
    igst = Column(Float, default=0.0, nullable=False)
    tax_total = Column(Float, default=0.0, nullable=False)
    round_off = Column(Float, default=0.0, nullable=False)
    grand_total = Column(Float, default=0.0, nullable=False)
    amount_paid = Column(Float, default=0.0, nullable=False)
    
    # Structured Line Items & Meta
    line_items = Column(JSON, nullable=True)
    terms_and_conditions = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    prepared_by = Column(String(150), nullable=True)
    pdf_url = Column(String(500), nullable=True)

    # Destination Website / ERP Sync Tracking
    destination_sync_status = Column(String(50), default="PENDING", nullable=False) # PENDING, SYNCED, FAILED
    external_client_id = Column(String(100), nullable=True)                          # Mapped external client ID in destination ERP
    external_proforma_id = Column(String(100), nullable=True)                        # Mapped external proforma ID in destination ERP
    destination_synced_at = Column(DateTime, nullable=True)
    destination_sync_error = Column(Text, nullable=True)
    destination_sync_attempts = Column(Integer, default=0, nullable=False)
    destination_sync_response = Column(JSON, nullable=True)
    
    # Dates
    issue_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    valid_till = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class WAHRMSBundle(Base):
    __tablename__ = "wahrms_bundles"

    id = Column(Integer, primary_key=True, index=True)
    bundle_code = Column(String(50), unique=True, index=True, nullable=False)  # hr_atm, hr_payroll, hr_atm_payroll, bio_standard...
    category = Column(String(50), default="WAHRMS", nullable=False)            # WAHRMS, BIOMETRIC
    name = Column(String(100), nullable=False)
    tagline = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    badge = Column(String(50), nullable=True)
    features = Column(JSON, nullable=True)
    items = Column(JSON, nullable=False)
    is_active = Column(Integer, default=1, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

