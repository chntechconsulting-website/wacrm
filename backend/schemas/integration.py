from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

class IntegrationConfigSave(BaseModel):
    integration_type: Optional[str] = Field(None, example="META") # META, WHATSAPP, IVR, WEBSITE
    config_data: Dict[str, Any] = Field(..., example={"app_id": "123456", "access_token": "secret"})

class IntegrationStatusOut(BaseModel):
    integration_type: str
    name: str
    description: str
    status: str # CONNECTED, NOT_CONNECTED, ERROR, DISCONNECTED, TESTING
    last_tested_at: Optional[datetime] = None
    masked_config: Dict[str, Any] = {}
    webhook_url: Optional[str] = None

class IntegrationTestResponse(BaseModel):
    success: bool
    status: str
    message: str
    last_tested_at: datetime
    error_details: Optional[str] = None

class WebsiteKeyGenerateRequest(BaseModel):
    allowed_domains: List[str] = Field(default_factory=list, example=["https://company.com", "https://www.company.com"])

class IntegrationLogOut(BaseModel):
    id: int
    integration_type: str
    event_type: str
    status: str
    message: str
    created_at: datetime

    class Config:
        from_attributes = True
