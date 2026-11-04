"""Pydantic response schemas for the WhatsApp Ad Leads CRM API."""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class WhatsAppAdLeadOut(BaseModel):
    id: int
    lead_id: int
    lead_enquiry_id: Optional[int] = None

    customer_name: str
    phone: str
    whatsapp_number: Optional[str] = None
    first_enquiry_message: Optional[str] = None
    message_type: Optional[str] = None
    message_timestamp: Optional[datetime] = None
    created_at: datetime

    source: str = "WHATSAPP_ADS"
    source_label: str = "WhatsApp Ads"
    channel: str = "WHATSAPP"
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    headline: Optional[str] = None
    ad_body: Optional[str] = None
    ctwa_clid: Optional[str] = None

    campaign_id: Optional[str] = None
    campaign_name: Optional[str] = None
    ad_name: Optional[str] = None

    assigned_employee_id: Optional[int] = None
    assigned_employee_name: Optional[str] = None
    status: str
    priority: Optional[str] = None
    rating: Optional[str] = None
    is_reinquiry: bool = False
    reinquiry_count: int = 0

    resolution_status: str = "PENDING"


class WhatsAppAdLeadDetailOut(WhatsAppAdLeadOut):
    lead: dict = Field(default_factory=dict)
    enquiries: List[dict] = Field(default_factory=list)
    activities: List[dict] = Field(default_factory=list)
    raw_referral: Optional[Any] = None
    resolution_error: Optional[str] = None
    resolved_at: Optional[datetime] = None


class WhatsAppAdLeadPage(BaseModel):
    items: List[WhatsAppAdLeadOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class WhatsAppAdSummaryOut(BaseModel):
    total: int = 0
    unassigned: int = 0
    assigned: int = 0
    campaigns: int = 0
    resolved_attribution: int = 0
    pending_attribution: int = 0


class WhatsAppAdFilterOptionsOut(BaseModel):
    campaigns: List[dict] = Field(default_factory=list)
    employees: List[dict] = Field(default_factory=list)
    statuses: List[str] = Field(default_factory=list)


class WhatsAppAdResolveResponse(BaseModel):
    success: bool
    resolution_status: str
    campaign_id: Optional[str] = None
    campaign_name: Optional[str] = None
    ad_name: Optional[str] = None
    error: Optional[str] = None
