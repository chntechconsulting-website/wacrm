from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
    JSON,
    Boolean,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    payment_number = Column(String(100), unique=True, index=True, nullable=False) # e.g. PAY-2026-0001
    
    # Linked entities
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    invoice_id = Column(Integer, ForeignKey("quotations.id"), nullable=True, index=True)
    finance_handoff_id = Column(Integer, ForeignKey("finance_handoffs.id"), nullable=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True, index=True)
    
    # Financial details
    amount = Column(Float, default=0.0, nullable=False)
    currency = Column(String(10), default="INR", nullable=False)
    
    # Payment method & Type
    # method: RAZORPAY, BANK_TRANSFER, NEFT_RTGS, UPI, CHEQUE, CASH, CARD
    payment_method = Column(String(50), default="BANK_TRANSFER", nullable=False)
    # type: MANUAL, ONLINE
    payment_type = Column(String(30), default="MANUAL", nullable=False)
    # status: PAID, PENDING, FAILED, PARTIAL, REFUNDED
    status = Column(String(30), default="PAID", nullable=False, index=True)
    
    # References & Gateway Data
    transaction_reference = Column(String(150), nullable=True, index=True) # UTR, Cheque No, or Razorpay payment_id
    bank_name = Column(String(100), nullable=True)
    razorpay_order_id = Column(String(100), nullable=True, index=True)
    razorpay_payment_id = Column(String(100), nullable=True, index=True)
    razorpay_signature = Column(String(255), nullable=True)
    
    # Metadata & Notes
    payment_date = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    notes = Column(Text, nullable=True)
    recorded_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    customer = relationship("Customer", foreign_keys=[customer_id])
    invoice = relationship("Quotation", foreign_keys=[invoice_id])
    finance_handoff = relationship("FinanceHandoff", foreign_keys=[finance_handoff_id])
    lead = relationship("Lead", foreign_keys=[lead_id])
    recorded_by = relationship("User", foreign_keys=[recorded_by_id])
    refunds = relationship("RefundRequest", back_populates="payment", cascade="all, delete-orphan")


class CustomerSubscription(Base):
    __tablename__ = "customer_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    subscription_number = Column(String(100), unique=True, index=True, nullable=False) # e.g. SUB-2026-0001
    
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True, index=True)
    finance_handoff_id = Column(Integer, ForeignKey("finance_handoffs.id"), nullable=True, index=True)
    
    # Subscription Specification
    plan_code = Column(String(50), default="business", nullable=False) # business, pro, custom
    plan_name = Column(String(100), default="WAHRMS Business", nullable=False)
    bundle_code = Column(String(50), default="hr_atm_payroll", nullable=True)
    product_category = Column(String(50), default="WAHRMS", nullable=False)
    billing_cycle = Column(String(30), default="yearly", nullable=False) # monthly, quarterly, yearly
    licence_count = Column(Integer, default=1, nullable=False)
    
    # Financials
    subscription_amount = Column(Float, default=0.0, nullable=False) # Base amount
    tax_amount = Column(Float, default=0.0, nullable=False)          # GST
    total_amount = Column(Float, default=0.0, nullable=False)        # Final total
    
    # Status: ACTIVE, UPCOMING_RENEWAL, EXPIRED, UPGRADED, DOWNGRADED, CANCELLED
    status = Column(String(30), default="ACTIVE", nullable=False, index=True)
    
    # Dates
    start_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    renewal_date = Column(DateTime, nullable=False, index=True)
    cancelled_at = Column(DateTime, nullable=True)
    
    # Add-ons: JSON array of objects [{name, code, amount, qty}]
    addons_data = Column(JSON, nullable=True)
    
    # Attribution & Notes
    sales_employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    customer = relationship("Customer", foreign_keys=[customer_id])
    sales_employee = relationship("Employee", foreign_keys=[sales_employee_id])
    history = relationship("SubscriptionHistory", back_populates="subscription", cascade="all, delete-orphan")


class SubscriptionHistory(Base):
    __tablename__ = "subscription_history"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("customer_subscriptions.id"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    
    # action_type: CREATE, RENEWAL, UPGRADE, DOWNGRADE, ADDON_PURCHASE, CANCEL
    action_type = Column(String(50), nullable=False)
    old_plan = Column(String(100), nullable=True)
    new_plan = Column(String(100), nullable=True)
    old_amount = Column(Float, nullable=True)
    new_amount = Column(Float, nullable=True)
    details = Column(JSON, nullable=True)
    
    performed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    subscription = relationship("CustomerSubscription", back_populates="history")
    customer = relationship("Customer", foreign_keys=[customer_id])
    performed_by = relationship("User", foreign_keys=[performed_by_id])


class RefundRequest(Base):
    __tablename__ = "refund_requests"

    id = Column(Integer, primary_key=True, index=True)
    refund_number = Column(String(100), unique=True, index=True, nullable=False) # e.g. REF-2026-0001
    
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True, index=True)
    invoice_id = Column(Integer, ForeignKey("quotations.id"), nullable=True, index=True)
    
    amount = Column(Float, default=0.0, nullable=False)
    reason = Column(Text, nullable=False)
    # status: REQUESTED, UNDER_REVIEW, APPROVED, REJECTED, PROCESSED
    status = Column(String(30), default="REQUESTED", nullable=False, index=True)
    
    requested_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Processing & Gateway Details
    transaction_reference = Column(String(150), nullable=True) # Gateway refund id or Bank UTR
    payment_gateway_refund_id = Column(String(150), nullable=True)
    processed_at = Column(DateTime, nullable=True)
    processed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    customer = relationship("Customer", foreign_keys=[customer_id])
    payment = relationship("Payment", back_populates="refunds")
    invoice = relationship("Quotation", foreign_keys=[invoice_id])
    requested_by = relationship("User", foreign_keys=[requested_by_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    processed_by = relationship("User", foreign_keys=[processed_by_id])


class ProformaPaymentEvent(Base):
    """Idempotency and audit record for payments received from the external ERP.

    One row is written for every accepted payment. ``event_id`` is unique so a
    provider retry that reuses the same event identifier cannot be processed
    twice. ``transaction_id`` is unique per provider when the ERP supplies one,
    which protects against two different event IDs describing the same bank
    transaction.

    Rejected/ignored events are not stored here: a later retry may legitimately
    carry the same event ID with a successful status. Ignored deliveries are
    recorded in ``integration_logs`` instead.
    """

    __tablename__ = "proforma_payment_events"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "transaction_id",
            name="uq_proforma_payment_provider_transaction",
        ),
        Index(
            "ix_proforma_payment_events_quotation_created",
            "quotation_id",
            "created_at",
        ),
        Index(
            "ix_proforma_payment_events_lead_created",
            "lead_id",
            "created_at",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(191), unique=True, index=True, nullable=False)
    provider = Column(String(50), default="WAQUOTE", nullable=False, index=True)
    event_type = Column(String(100), nullable=True)

    # PROCESSED is the only value written. Kept as a column so a future
    # reconciliation job can distinguish outcomes without a migration.
    status = Column(String(30), default="PROCESSED", nullable=False, index=True)

    external_proforma_id = Column(String(100), nullable=True, index=True)
    proforma_number = Column(String(100), nullable=True)
    external_payment_id = Column(String(150), nullable=True)
    transaction_id = Column(String(150), nullable=True, index=True)

    quotation_id = Column(Integer, ForeignKey("quotations.id"), nullable=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True, index=True)

    amount = Column(Float, default=0.0, nullable=False)
    currency = Column(String(10), default="INR", nullable=False)
    payment_method = Column(String(50), nullable=True)
    payment_status = Column(String(30), nullable=True)  # PAID / PARTIALLY_PAID
    message = Column(Text, nullable=True)
    raw_payload = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    quotation = relationship("Quotation", foreign_keys=[quotation_id])
    lead = relationship("Lead", foreign_keys=[lead_id])
    payment = relationship("Payment", foreign_keys=[payment_id])
