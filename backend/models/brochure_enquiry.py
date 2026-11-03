from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from database import Base
from utils.timezone import get_ist_now


class BrochureEnquiry(Base):
    """
    Dedicated record for a brochure download submitted through the company
    website. These rows intentionally live outside the normal Lead pipeline so
    marketing brochure downloads do not pollute the Leads listing.

    An optional reference to an existing Lead/Customer is stored when the same
    contact already exists in the CRM. No Lead or Customer is created here.
    """

    __tablename__ = "brochure_enquiries"

    id = Column(Integer, primary_key=True, index=True)

    # Contact snapshot captured from the brochure form
    name = Column(String(150), nullable=False)
    phone = Column(String(50), nullable=False, index=True)
    whatsapp_number = Column(String(50), nullable=True, index=True)
    country_code = Column(String(10), nullable=True)
    email = Column(String(150), nullable=True, index=True)

    # Product / brochure details. IDs are whatever the website sends, never
    # hardcoded CRM values.
    product_name = Column(String(200), nullable=True, index=True)
    product_id = Column(String(100), nullable=True)
    brochure_name = Column(String(255), nullable=True, index=True)
    brochure_id = Column(String(100), nullable=True)

    # Download / submission metadata
    download_at = Column(DateTime, default=get_ist_now, nullable=False, index=True)
    last_submitted_at = Column(DateTime, default=get_ist_now, nullable=False)
    submission_count = Column(Integer, default=1, nullable=False)
    dedupe_key = Column(String(64), unique=True, nullable=False, index=True)

    # Website attribution
    source = Column(String(50), default="WEBSITE_BROCHURE", nullable=False, index=True)
    form_type = Column(String(60), nullable=True)
    website_id = Column(String(50), nullable=True)
    website_name = Column(String(100), nullable=True)
    landing_page = Column(String(500), nullable=True)
    campaign = Column(String(150), nullable=True)
    message = Column(Text, nullable=True)

    # Follow-up ownership and state (managed only on this module)
    assigned_to = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)
    assigned_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    assigned_at = Column(DateTime, nullable=True)
    followup_status = Column(String(30), default="PENDING", nullable=False, index=True)
    next_followup_date = Column(Date, nullable=True)
    next_followup_time = Column(String(20), nullable=True)
    notes = Column(Text, nullable=True)
    last_contacted_at = Column(DateTime, nullable=True)
    converted_at = Column(DateTime, nullable=True)

    # Optional links to existing CRM records. These are lookup references only;
    # the brochure module never inserts into leads/customers.
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)

    created_at = Column(DateTime, default=get_ist_now, nullable=False, index=True)
    updated_at = Column(DateTime, default=get_ist_now, onupdate=get_ist_now, nullable=False)

    assigned_employee = relationship("Employee", foreign_keys=[assigned_to])
    assigned_by_employee = relationship("Employee", foreign_keys=[assigned_by])
    lead = relationship("Lead", foreign_keys=[lead_id])
    customer = relationship("Customer", foreign_keys=[customer_id])

    @property
    def display_phone(self):
        return self.whatsapp_number or self.phone
