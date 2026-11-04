"""Request/response schemas for the coexistence admin API."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SessionLogIn(BaseModel):
    type: str = "WA_EMBEDDED_SIGNUP"
    event: str
    data: Dict[str, Any] = Field(default_factory=dict)


class ExchangeCodeIn(BaseModel):
    code: str
    waba_id: str
    phone_number_id: Optional[str] = None
    business_id: Optional[str] = None
    session_event: Optional[str] = None


class SyncRequestIn(BaseModel):
    sync_type: str  # contacts | history


class TemplateComponentIn(BaseModel):
    type: str = "BODY"
    text: str


class TemplateCreateIn(BaseModel):
    name: str
    language: str = "en_US"
    category: str = "UTILITY"
    body_text: str
    footer_text: Optional[str] = None


class ConnectionOut(BaseModel):
    id: int
    waba_id: str
    phone_number_id: str
    business_id: Optional[str] = None
    display_phone_number: Optional[str] = None
    verified_name: Optional[str] = None
    quality_rating: Optional[str] = None

    status: str
    onboarding_status: str
    is_on_biz_app: Optional[bool] = None
    platform_type: Optional[str] = None
    webhook_subscribed: bool = False
    webhook_fields: List[str] = Field(default_factory=list)

    contacts_sync_requested_at: Optional[datetime] = None
    history_sync_requested_at: Optional[datetime] = None
    sync_deadline_at: Optional[datetime] = None
    history_progress: int = 0
    history_phase: Optional[int] = None
    messages_synced: int = 0
    contacts_synced: int = 0

    last_webhook_at: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None
    last_error: Optional[str] = None
    onboarded_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class StatusOut(BaseModel):
    config: dict
    connection: Optional[ConnectionOut] = None
    webhook: dict
    server_time: datetime


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    status: str
    detail: Optional[str] = None
    created_at: datetime
    processed_at: Optional[datetime] = None


class TemplateOut(BaseModel):
    id: Optional[str] = None
    name: str
    status: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = None
    components: Optional[Any] = None
