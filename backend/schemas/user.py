from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class UserCreateRequest(BaseModel):
    name: str
    email: str
    username: str
    password: str
    role: str = "SALES_EXECUTIVE"
    department: Optional[str] = None
    reporting_manager_id: Optional[int] = None
    manager_id: Optional[int] = None  # Backward-compatibility alias
    phone: Optional[str] = None
    status: str = "ACTIVE"

class UserUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    reporting_manager_id: Optional[int] = None
    manager_id: Optional[int] = None  # Backward-compatibility alias
    status: Optional[str] = None  # ACTIVE, INACTIVE
    phone: Optional[str] = None
    password: Optional[str] = None

class ReassignReportsRequest(BaseModel):
    new_manager_id: int

class PasswordResetRequest(BaseModel):
    new_password: str

class UserDetailOut(BaseModel):
    id: int
    employee_id: Optional[int] = None
    name: str
    email: str
    username: str
    role: str
    department: Optional[str] = None
    reporting_manager_id: Optional[int] = None
    reporting_manager_name: Optional[str] = None
    reporting_manager_role: Optional[str] = None
    manager_id: Optional[int] = None
    manager_name: Optional[str] = None
    direct_reports_count: int = 0
    status: str
    is_active: bool
    phone: Optional[str] = None
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True

class AuditLogOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    ip_address: Optional[str] = None
    details: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
