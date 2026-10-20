from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime

class FollowupBase(BaseModel):
    lead_id: int
    assigned_to: Optional[int] = None
    followup_date: date
    followup_time: Optional[str] = "10:00 AM"
    notes: Optional[str] = None
    priority: str = "MEDIUM"  # LOW, MEDIUM, HIGH
    status: str = "Pending"   # Pending, Completed, Cancelled

class FollowupCreate(FollowupBase):
    pass

class FollowupUpdate(BaseModel):
    followup_date: Optional[date] = None
    followup_time: Optional[str] = None
    notes: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[int] = None

class FollowupOut(FollowupBase):
    id: int
    lead_name: str
    lead_phone: str
    assigned_employee_name: str
    created_by: Optional[int] = None
    created_at: datetime
    reminder_sent: Optional[bool] = False
    reminder_dismissed: Optional[bool] = False

    class Config:
        from_attributes = True

class FollowupSnoozeRequest(BaseModel):
    minutes: int = 15

class FollowupReminderOut(BaseModel):
    id: int
    lead_id: int
    lead_name: str
    lead_phone: str
    followup_date: str
    followup_time: Optional[str] = None
    scheduled_datetime: str
    display_time: str
    notes: Optional[str] = None
    priority: str = "MEDIUM"
    status: str
    assigned_to: int
    assigned_employee_name: str
    reminder_sent: bool
    snoozed_until: Optional[datetime] = None
    reminder_dismissed: bool
