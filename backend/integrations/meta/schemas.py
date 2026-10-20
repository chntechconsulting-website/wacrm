from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class MetaLeadgenValue(BaseModel):
    ad_id: Optional[str] = None
    form_id: Optional[str] = None
    leadgen_id: str
    created_time: Optional[int] = None
    page_id: Optional[str] = None
    adgroup_id: Optional[str] = None

class MetaLeadgenChange(BaseModel):
    value: MetaLeadgenValue
    field: str

class MetaLeadgenEntry(BaseModel):
    id: str
    time: int
    changes: List[MetaLeadgenChange]

class MetaWebhookPayload(BaseModel):
    object: str
    entry: List[MetaLeadgenEntry]

class MetaPageCreate(BaseModel):
    page_id: str
    page_name: Optional[str] = None
    access_token: str

class MetaPageRefresh(BaseModel):
    access_token: Optional[str] = None

class MetaPageOut(BaseModel):
    id: int
    page_id: str
    page_name: str
    status: str
    masked_token: str
    category: Optional[str] = None
    lead_count: int = 0
    last_synced_at: Optional[datetime] = None
    last_webhook_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class MetaPageActionResponse(BaseModel):
    success: bool
    message: str
    page: Optional[MetaPageOut] = None
    error_details: Optional[str] = None

class MetaIntegrationStatusResponse(BaseModel):
    configured: bool
    status: str
    page_id: Optional[str] = None
    app_id: Optional[str] = None
    api_version: str
    total_meta_leads: int = 0
    total_pages_connected: int = 0
    pages: List[MetaPageOut] = []
    last_webhook_received: Optional[str] = None
    last_sync: Optional[str] = None
    message: str

class MetaLeadDetails(BaseModel):
    leadgen_id: str
    form_id: Optional[str] = None
    created_time: Optional[datetime] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    city: Optional[str] = None
    company: Optional[str] = None
    raw_field_data: Optional[Dict[str, Any]] = None
