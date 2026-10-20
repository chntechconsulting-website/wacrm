from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class EmployeeBase(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    username: str
    role: str = "EMPLOYEE"  # ADMIN, MANAGER, EMPLOYEE
    status: str = "ACTIVE"  # ACTIVE, INACTIVE

class EmployeeCreate(EmployeeBase):
    password: str

class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    password: Optional[str] = None

class EmployeeOut(EmployeeBase):
    id: int
    user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
