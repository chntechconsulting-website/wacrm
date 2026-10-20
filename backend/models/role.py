from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, index=True, nullable=False) # e.g. "ADMIN", "SALES", "FINANCE", "SUPPORT", "HR"
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_system = Column(Boolean, default=False, nullable=False) # True for core ADMIN
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")


class RolePermission(Base):
    """
    Fine-grained, configurable permissions per role and module.
    Actions:
    - view, create, edit, delete, export, approve, assign, call, whatsapp
    Data Scopes:
    - view_scope: 'none' | 'own' | 'team' | 'department' | 'company'
    """
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), index=True, nullable=False)
    module = Column(String(50), index=True, nullable=False) # e.g. "leads", "quotations", "invoices", etc.

    # Module access flag
    has_access = Column(Boolean, default=False, nullable=False)

    # Granular Action permissions
    can_view = Column(Boolean, default=False, nullable=False)
    can_create = Column(Boolean, default=False, nullable=False)
    can_edit = Column(Boolean, default=False, nullable=False)
    can_delete = Column(Boolean, default=False, nullable=False)
    can_export = Column(Boolean, default=False, nullable=False)
    can_approve = Column(Boolean, default=False, nullable=False)
    can_assign = Column(Boolean, default=False, nullable=False)
    can_call = Column(Boolean, default=False, nullable=False)
    can_whatsapp = Column(Boolean, default=False, nullable=False)

    # Record Visibility Scope: 'none', 'own', 'team', 'department', 'company'
    view_scope = Column(String(30), default="own", nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    role = relationship("Role", back_populates="permissions")
