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
    # Additive OAuth / asset discovery fields
    connection_id: Optional[int] = None
    page_picture_url: Optional[str] = None
    instagram_account_id: Optional[str] = None
    instagram_username: Optional[str] = None
    is_selected: bool = True
    auto_sync_enabled: bool = True
    webhook_subscribed: bool = False
    token_expires_at: Optional[datetime] = None
    forms_last_synced_at: Optional[datetime] = None
    last_lead_at: Optional[datetime] = None
    last_error_code: Optional[str] = None
    form_count: int = 0
    selected_form_count: int = 0

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


class MetaPageSelectionUpdate(BaseModel):
    selected: bool = True
    auto_sync_enabled: Optional[bool] = None


class MetaAutoSyncUpdate(BaseModel):
    enabled: bool


class MetaFormsSelectionUpdate(BaseModel):
    form_ids: List[str] = []
    selected: bool = True
    page_id: Optional[str] = None
    select_all_for_page: bool = False


class MetaImportRequest(BaseModel):
    range: str = "24H"
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    page_ids: Optional[List[str]] = None
    form_ids: Optional[List[str]] = None
