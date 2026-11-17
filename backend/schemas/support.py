from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


VALID_INTERACTION_TYPES = {"INBOUND", "OUTBOUND", "MANUAL"}
VALID_LEAVE_TYPES = {"CASUAL", "SICK", "ANNUAL", "MATERNITY", "UNPAID", "OTHER"}
VALID_LEAVE_STATUSES = {"PENDING", "APPROVED", "REJECTED", "CANCELLED"}
VALID_PREFERRED_CONTACT_METHODS = {"CALL", "WHATSAPP", "EMAIL"}


class CustomerPOCCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    mobile: str = Field(..., min_length=7, max_length=30)
    alternate_mobile: Optional[str] = Field(default=None, max_length=30)
    whatsapp_number: Optional[str] = Field(default=None, max_length=30)
    email: Optional[str] = Field(default=None, max_length=255)
    designation: Optional[str] = Field(default=None, max_length=120)
    department: Optional[str] = Field(default=None, max_length=120)
    preferred_contact_method: str = "CALL"
    notes: Optional[str] = None
    is_primary: bool = False


class CustomerPOCUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    mobile: Optional[str] = Field(default=None, min_length=7, max_length=30)
    alternate_mobile: Optional[str] = Field(default=None, max_length=30)
    whatsapp_number: Optional[str] = Field(default=None, max_length=30)
    email: Optional[str] = Field(default=None, max_length=255)
    designation: Optional[str] = Field(default=None, max_length=120)
    department: Optional[str] = Field(default=None, max_length=120)
    preferred_contact_method: Optional[str] = None
    notes: Optional[str] = None
    is_primary: Optional[bool] = None


class SupportInteractionCreate(BaseModel):
    customer_id: Optional[int] = None
    customer_poc_id: Optional[int] = None
    interaction_type: str = "MANUAL"
    interaction_at: Optional[datetime] = None
    discussion: Optional[str] = None
    problem_reported: Optional[str] = None
    troubleshooting: Optional[str] = None
    solution_provided: Optional[str] = None
    pending_issues: Optional[str] = None
    customer_commitments: Optional[str] = None
    next_action: Optional[str] = None
    follow_up_at: Optional[datetime] = None
    notes: Optional[str] = None
    attachments: Optional[List[Any]] = None
    client_reference: Optional[str] = Field(default=None, max_length=100)


class EmployeeLeaveCreate(BaseModel):
    employee_id: Optional[int] = None
    leave_type: str = "CASUAL"
    start_date: date
    end_date: date
    reason: Optional[str] = None
    manager_notes: Optional[str] = None


class EmployeeLeaveDecision(BaseModel):
    manager_notes: Optional[str] = None


class CoverageAssignRequest(BaseModel):
    backup_employee_id: int
    lead_ids: Optional[List[int]] = None
    customer_ids: Optional[List[int]] = None
    all_assigned_customers: bool = False
