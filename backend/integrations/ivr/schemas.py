from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

# Supported call status constants
CALL_STATUS_INITIATED = "INITIATED"
CALL_STATUS_RINGING = "RINGING"
CALL_STATUS_ANSWERED = "ANSWERED"
CALL_STATUS_MISSED = "MISSED"
CALL_STATUS_BUSY = "BUSY"
CALL_STATUS_FAILED = "FAILED"
CALL_STATUS_COMPLETED = "COMPLETED"

class InitiateCallRequest(BaseModel):
    lead_id: Optional[int] = Field(None, description="ID of the lead to call")
    customer_phone: Optional[str] = Field(None, description="Customer phone number")
    phone_number: Optional[str] = Field(None, description="Optional custom phone number")
    notes: Optional[str] = Field(None, description="Initial call notes")

class CallLogResponse(BaseModel):
    id: int
    lead_id: Optional[int] = None
    employee_id: Optional[int] = None
    provider: str
    provider_call_id: str
    from_number: str
    to_number: str
    customer_phone: Optional[str] = None
    employee_phone: Optional[str] = None
    call_status: str
    call_direction: str
    duration_seconds: int
    recording_url: Optional[str] = None
    transcript: Optional[str] = None
    ai_summary: Optional[str] = None
    sentiment: Optional[str] = None
    started_at: Optional[datetime] = None
    answered_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    notes: Optional[str] = None
    product_category: Optional[str] = None  # BIOMETRIC, WAHRMS, UNCLASSIFIED
    created_at: datetime

    # Additional expanded fields for UI
    recording_status: Optional[str] = "RECORDING_UNAVAILABLE"  # "RECORDING_AVAILABLE", "RECORDING_PROCESSING", "RECORDING_UNAVAILABLE"
    lead_name: Optional[str] = None
    employee_name: Optional[str] = None
    employee_extension: Optional[str] = None

    class Config:
        from_attributes = True

class CallLogMetricsSummary(BaseModel):
    total_calls: int = 0
    connected_calls: int = 0
    missed_calls: int = 0
    connect_rate: int = 0
    total_duration_seconds: int = 0
    avg_duration_seconds: int = 0

class CallLogListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[CallLogResponse]
    metrics: Optional[CallLogMetricsSummary] = None

class IVRConfigStatusResponse(BaseModel):
    configured: bool
    provider: str
    from_number: Optional[str] = None
    message: str

class WebhookEventPayload(BaseModel):
    provider_call_id: str
    event_type: str
    call_status: str
    duration_seconds: Optional[int] = 0
    recording_url: Optional[str] = None
    timestamp: Optional[datetime] = None
    raw_payload: Optional[Dict[str, Any]] = None
