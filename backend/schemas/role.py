from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class PermissionItem(BaseModel):
    module: str
    has_access: bool = False
    can_view: bool = False
    can_create: bool = False
    can_edit: bool = False
    can_delete: bool = False
    can_export: bool = False
    can_approve: bool = False
    can_assign: bool = False
    can_call: bool = False
    can_whatsapp: bool = False
    view_scope: str = "own" # "none" | "own" | "team" | "department" | "company"

    class Config:
        from_attributes = True

class RoleCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=50) # Unique key, e.g. "SALES"
    display_name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    permissions: List[PermissionItem] = []

class RoleUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    permissions: Optional[List[PermissionItem]] = None

class RoleOut(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str] = None
    is_system: bool = False
    is_active: bool = True
    user_count: int = 0
    permissions: List[PermissionItem] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ModuleMeta(BaseModel):
    key: str
    label: str
    category: str
    description: Optional[str] = None
    supported_actions: List[str] = [
        "view", "create", "edit", "delete", "export", "approve", "assign", "call", "whatsapp"
    ]
    supported_scopes: List[str] = [
        "none", "own", "team", "department", "company"
    ]
