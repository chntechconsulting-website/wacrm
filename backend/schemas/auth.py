from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class LoginRequest(BaseModel):
    username: str
    password: str

class UserOut(BaseModel):
    id: int
    employee_id: Optional[int] = None
    name: Optional[str] = None
    email: Optional[str] = None
    username: str
    role: str
    status: str = "ACTIVE"
    is_active: bool = True
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    employee_name: Optional[str] = None
    employee_email: Optional[str] = None
    permissions: Optional[dict] = None

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

TokenResponse.model_rebuild()
