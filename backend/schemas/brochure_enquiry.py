from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


BROCHURE_FOLLOWUP_STATUSES = [
    "PENDING",
    "FOLLOW_UP",
    "CONTACTED",
    "CONVERTED",
    "NOT_INTERESTED",
]


class BrochureEnquiryOut(BaseModel):
    id: int
    name: str
    phone: str
    whatsapp_number: Optional[str] = None
    country_code: Optional[str] = None
    email: Optional[str] = None

    product_name: Optional[str] = None
    product_id: Optional[str] = None
    brochure_name: Optional[str] = None
    brochure_id: Optional[str] = None

    download_at: datetime
    last_submitted_at: datetime
    submission_count: int = 1

    source: str
    form_type: Optional[str] = None
    website_id: Optional[str] = None
    website_name: Optional[str] = None
    landing_page: Optional[str] = None
    campaign: Optional[str] = None
    message: Optional[str] = None

    assigned_to: Optional[int] = None
    assigned_employee_name: Optional[str] = None
    followup_status: str
    next_followup_date: Optional[date] = None
    next_followup_time: Optional[str] = None
    notes: Optional[str] = None
    last_contacted_at: Optional[datetime] = None
    converted_at: Optional[datetime] = None

    lead_id: Optional[int] = None
    customer_id: Optional[int] = None
    linked_lead_name: Optional[str] = None
    linked_customer_name: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BrochureEnquiryPage(BaseModel):
    items: List[BrochureEnquiryOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class BrochureEnquiryUpdate(BaseModel):
    followup_status: Optional[str] = None
    notes: Optional[str] = None
    note: Optional[str] = Field(
        None,
        description="Appends a timestamped note instead of replacing the existing notes.",
    )
    assigned_to: Optional[int] = None
    next_followup_date: Optional[date] = None
    next_followup_time: Optional[str] = Field(None, max_length=20)


class BrochureSummaryOut(BaseModel):
    total_downloads: int
    pending_followups: int
    contacted_customers: int
    converted_customers: int
    not_interested: int


class BrochureEmployeeOption(BaseModel):
    id: int
    name: str
    role: Optional[str] = None
    department: Optional[str] = None


class BrochureFilterOptionsOut(BaseModel):
    brochures: List[str]
    employees: List[BrochureEmployeeOption]
    statuses: List[str]


class BrochureEnquiryCreateResponse(BaseModel):
    success: bool = True
    message: str = "Brochure enquiry recorded successfully"
    enquiry_id: Optional[int] = None
    record_type: str = "BROCHURE_ENQUIRY"
    is_duplicate: bool = False
    submission_count: Optional[int] = None
