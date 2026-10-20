from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class SendMessageRequest(BaseModel):
    phone: Optional[str] = Field(None, example="919876543210")
    lead_id: Optional[int] = Field(None, example=1)
    message_type: str = Field("TEXT", example="TEXT")  # TEXT, TEMPLATE, IMAGE, DOCUMENT
    body: Optional[str] = Field(None, example="Hello from WaCRM!")
    media_url: Optional[str] = Field(None, example="https://example.com/doc.pdf")
    caption: Optional[str] = Field(None, example="Product Catalog")
    template_name: Optional[str] = Field(None, example="hello_world")
    language_code: Optional[str] = Field("en_US", example="en_US")

class WhatsAppMessageOut(BaseModel):
    id: int
    conversation_id: int
    lead_id: Optional[int] = None
    sender_employee_id: Optional[int] = None
    sender_employee_name: Optional[str] = None
    direction: str
    message_type: str
    body: Optional[str] = None
    media_url: Optional[str] = None
    caption: Optional[str] = None
    template_name: Optional[str] = None
    provider_message_id: Optional[str] = None
    status: str
    sent_at: datetime
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ConversationOut(BaseModel):
    id: int
    lead_id: Optional[int] = None
    lead_name: Optional[str] = None
    phone: str
    contact_name: Optional[str] = None
    assigned_to: Optional[int] = None
    assigned_employee_name: Optional[str] = None
    unread_count: int
    is_archived: bool
    last_message_text: Optional[str] = None
    last_message_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ConversationDetailOut(ConversationOut):
    messages: List[WhatsAppMessageOut] = []
