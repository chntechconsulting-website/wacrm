from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List, Any
from datetime import date, datetime

class LeadBase(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    name: Optional[str] = None
    phone: str
    whatsapp_number: Optional[str] = None
    email: Optional[EmailStr] = None
    designation: Optional[str] = None

    company: Optional[str] = None
    industry: Optional[str] = None
    website: Optional[str] = None
    company_size: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = "India"
    location: Optional[str] = None

    source: str = "Manual"  # Meta Ads, Excel, Manual, Website, Referral
    status: str = "NEW"     # NEW, ASSIGNED, CONTACTED, INTERESTED, FOLLOW_UP, QUALIFIED, CONVERTED, NOT_INTERESTED, LOST
    campaign_name: Optional[str] = None
    website_id: Optional[str] = None
    website_name: Optional[str] = None
    landing_page: Optional[str] = None
    rating: Optional[str] = "Warm"  # Hot, Warm, Cold
    priority: Optional[str] = "MEDIUM"  # High, Medium, Low
    requirement_notes: Optional[str] = None

    followup_date: Optional[date] = None
    followup_time: Optional[str] = None

    @field_validator(
        "email", "followup_date", "followup_time", "whatsapp_number",
        "first_name", "last_name", "name", "designation", "company",
        "industry", "website", "company_size", "city", "state", "country", "location",
        "campaign_name", "website_id", "website_name", "landing_page",
        "rating", "priority", "requirement_notes",
        mode="before", check_fields=False
    )
    @classmethod
    def empty_str_to_none(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            return None
        return v

class LeadCreate(LeadBase):
    assigned_to: Optional[int] = None

    @field_validator("assigned_to", mode="before")
    @classmethod
    def validate_assigned_to(cls, v: Any) -> Any:
        if v is None or v == "" or v == "null" or v == 0:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

class LeadUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    whatsapp_number: Optional[str] = None
    email: Optional[EmailStr] = None
    designation: Optional[str] = None

    company: Optional[str] = None
    industry: Optional[str] = None
    website: Optional[str] = None
    company_size: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = "India"
    location: Optional[str] = None

    source: Optional[str] = None
    status: Optional[str] = None
    campaign_name: Optional[str] = None
    rating: Optional[str] = None
    priority: Optional[str] = None
    requirement_notes: Optional[str] = None

    followup_date: Optional[date] = None
    followup_time: Optional[str] = None
    assigned_to: Optional[int] = None
    quotetask_quotation_amount: Optional[float] = None

    @field_validator(
        "email", "followup_date", "followup_time", "whatsapp_number",
        "first_name", "last_name", "name", "phone", "designation", "company",
        "industry", "website", "company_size", "city", "state", "country", "location",
        "source", "status", "campaign_name", "rating", "priority", "requirement_notes",
        mode="before", check_fields=False
    )
    @classmethod
    def empty_str_to_none(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("assigned_to", mode="before")
    @classmethod
    def validate_assigned_to(cls, v: Any) -> Any:
        if v is None or v == "" or v == "null" or v == 0:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

class LeadAssignRequest(BaseModel):
    assigned_to: int

class LeadStatusRequest(BaseModel):
    status: str

class LeadNoteRequest(BaseModel):
    note: str

class LeadActivityOut(BaseModel):
    id: int
    performed_by: Optional[int] = None
    performed_by_name: Optional[str] = None
    activity_type: str
    description: str
    created_at: datetime

    class Config:
        from_attributes = True

class LeadAssignmentOut(BaseModel):
    id: int
    lead_id: int
    assigned_to: int
    assigned_to_name: Optional[str] = None
    assigned_by: Optional[int] = None
    assigned_by_name: Optional[str] = None
    assigned_at: datetime
    assignment_method: str = "MANUAL"
    notes: Optional[str] = None

    class Config:
        from_attributes = True

class QuoteTaskQuotationCreateRequest(BaseModel):
    title: Optional[str] = None
    notes: Optional[str] = None
    estimated_amount: Optional[float] = 0.0
    items: Optional[List[dict]] = []

class LeadEnquiryOut(BaseModel):
    id: int
    lead_id: int
    enquiry_number: int
    enquiry_type: str
    source: str
    campaign_name: Optional[str] = None
    website_name: Optional[str] = None
    landing_page: Optional[str] = None
    requirement_notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class LeadOut(LeadBase):
    id: int
    assigned_to: Optional[int] = None
    assigned_employee_name: Optional[str] = None
    assigned_by: Optional[int] = None
    assigned_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Lead Received Time Fields (Strictly backend/database generated)
    lead_received_at: Optional[datetime] = None
    lead_received_formatted: Optional[str] = None
    lead_received_date: Optional[str] = None
    lead_received_time: Optional[str] = None

    # Re-Inquiry Tracking Fields
    is_reinquiry: bool = False
    reinquiry_count: int = 0
    total_enquiries: int = 1
    first_enquiry_date: Optional[datetime] = None
    latest_enquiry_date: Optional[datetime] = None
    previous_sources: Optional[str] = None
    latest_source: Optional[str] = None

    # QuoteTask Integration Mapping Fields
    quotetask_quotation_id: Optional[str] = None
    quotetask_quotation_number: Optional[str] = None
    quotetask_quotation_status: Optional[str] = None
    quotetask_quotation_amount: Optional[float] = None
    quotetask_quotation_url: Optional[str] = None
    quotetask_po_id: Optional[str] = None
    quotetask_po_number: Optional[str] = None
    quotetask_po_status: Optional[str] = None
    quotetask_synced_at: Optional[datetime] = None

    activities: List[LeadActivityOut] = []
    assignments: List[LeadAssignmentOut] = []
    enquiries: List[LeadEnquiryOut] = []

    class Config:
        from_attributes = True

class AutoAssignConfigBase(BaseModel):
    enabled: bool = True
    waiting_time_minutes: int = 60
    assignment_method: str = "LEAST_ASSIGNED"  # LEAST_ASSIGNED, ROUND_ROBIN, HIERARCHICAL
    eligible_roles: str = "EMPLOYEE,MANAGER"
    working_hours_enabled: bool = False
    working_hours_start: str = "09:00"
    working_hours_end: str = "18:00"

class AutoAssignConfigOut(AutoAssignConfigBase):
    id: int
    updated_at: datetime

    class Config:
        from_attributes = True

class AutoAssignConfigUpdate(AutoAssignConfigBase):
    pass
