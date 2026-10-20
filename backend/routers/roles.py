from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from database import get_db
from models.role import Role, RolePermission
from models.user import User
from schemas.role import RoleCreateRequest, RoleUpdateRequest, RoleOut, ModuleMeta, PermissionItem
from services.auth import get_current_user, require_admin, require_permission
from services.audit import log_audit
from services.permission_catalog import SYSTEM_MODULES, MODULE_KEYS
from services.permission_service import get_role_permissions_map

router = APIRouter(prefix="/roles", tags=["Role & Permission Management"])

@router.get("/modules", response_model=List[ModuleMeta])
def get_system_modules(
    current_user: User = Depends(get_current_user)
):
    """
    Returns full metadata for all system modules and supported actions/scopes.
    Used by frontend permission matrix for role creation and editing.
    """
    return [
        ModuleMeta(
            key=m["key"],
            label=m["label"],
            category=m["category"],
            description=m.get("description", "")
        )
        for m in SYSTEM_MODULES
    ]

@router.get("", response_model=List[RoleOut])
def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all configured roles with user counts and dynamic permissions.
    """
    # Verify permission to view roles module
    if current_user.role != "ADMIN":
        from services.permission_service import user_has_permission
        if not user_has_permission(current_user, "roles", "view", db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not have permission to view roles."
            )

    roles = db.query(Role).order_by(Role.is_system.desc(), Role.id.asc()).all()
    user_counts = {}
    for r in roles:
        count = db.query(User).filter(User.role == r.name).count()
        user_counts[r.name] = count

    output = []
    for r in roles:
        # Build complete permission list for all 19 modules
        db_perms = {p.module.lower(): p for p in r.permissions}
        perm_items = []
        is_admin_role = (r.name.upper() == "ADMIN")

        for m in SYSTEM_MODULES:
            k = m["key"].lower()
            p = db_perms.get(k)
            if is_admin_role:
                perm_items.append(
                    PermissionItem(
                        module=k,
                        has_access=True,
                        can_view=True,
                        can_create=True,
                        can_edit=True,
                        can_delete=True,
                        can_export=True,
                        can_approve=True,
                        can_assign=True,
                        can_call=True,
                        can_whatsapp=True,
                        view_scope="company"
                    )
                )
            elif p:
                perm_items.append(
                    PermissionItem(
                        module=k,
                        has_access=p.has_access,
                        can_view=p.can_view,
                        can_create=p.can_create,
                        can_edit=p.can_edit,
                        can_delete=p.can_delete,
                        can_export=p.can_export,
                        can_approve=p.can_approve,
                        can_assign=p.can_assign,
                        can_call=p.can_call,
                        can_whatsapp=p.can_whatsapp,
                        view_scope=p.view_scope or "own"
                    )
                )
            else:
                perm_items.append(
                    PermissionItem(
                        module=k,
                        has_access=False,
                        can_view=False,
                        can_create=False,
                        can_edit=False,
                        can_delete=False,
                        can_export=False,
                        can_approve=False,
                        can_assign=False,
                        can_call=False,
                        can_whatsapp=False,
                        view_scope="none"
                    )
                )

        output.append(
            RoleOut(
                id=r.id,
                name=r.name,
                display_name=r.display_name,
                description=r.description,
                is_system=r.is_system,
                is_active=r.is_active,
                user_count=user_counts.get(r.name, 0),
                permissions=perm_items,
                created_at=r.created_at,
                updated_at=r.updated_at
            )
        )

    return output

@router.get("/{role_id}", response_model=RoleOut)
def get_role_detail(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a single role by ID with its permission matrix.
    """
    if current_user.role != "ADMIN":
        from services.permission_service import user_has_permission
        if not user_has_permission(current_user, "roles", "view", db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not have permission to view roles."
            )

    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found.")

    user_count = db.query(User).filter(User.role == role.name).count()
    db_perms = {p.module.lower(): p for p in role.permissions}
    perm_items = []
    is_admin_role = (role.name.upper() == "ADMIN")

    for m in SYSTEM_MODULES:
        k = m["key"].lower()
        p = db_perms.get(k)
        if is_admin_role:
            perm_items.append(
                PermissionItem(
                    module=k,
                    has_access=True,
                    can_view=True,
                    can_create=True,
                    can_edit=True,
                    can_delete=True,
                    can_export=True,
                    can_approve=True,
                    can_assign=True,
                    can_call=True,
                    can_whatsapp=True,
                    view_scope="company"
                )
            )
        elif p:
            perm_items.append(
                PermissionItem(
                    module=k,
                    has_access=p.has_access,
                    can_view=p.can_view,
                    can_create=p.can_create,
                    can_edit=p.can_edit,
                    can_delete=p.can_delete,
                    can_export=p.can_export,
                    can_approve=p.can_approve,
                    can_assign=p.can_assign,
                    can_call=p.can_call,
                    can_whatsapp=p.can_whatsapp,
                    view_scope=p.view_scope or "own"
                )
            )
        else:
            perm_items.append(
                PermissionItem(
                    module=k,
                    has_access=False,
                    can_view=False,
                    can_create=False,
                    can_edit=False,
                    can_delete=False,
                    can_export=False,
                    can_approve=False,
                    can_assign=False,
                    can_call=False,
                    can_whatsapp=False,
                    view_scope="none"
                )
            )

    return RoleOut(
        id=role.id,
        name=role.name,
        display_name=role.display_name,
        description=role.description,
        is_system=role.is_system,
        is_active=role.is_active,
        user_count=user_count,
        permissions=perm_items,
        created_at=role.created_at,
        updated_at=role.updated_at
    )

@router.post("", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new custom role with a complete permission matrix.
    Enforces audit logging.
    """
    if current_user.role != "ADMIN":
        from services.permission_service import user_has_permission
        if not user_has_permission(current_user, "roles", "create", db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not have permission to create roles."
            )

    # Clean and normalize role name
    norm_name = payload.name.strip().upper().replace(" ", "_")
    if not norm_name.replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Role name must be alphanumeric.")

    # Check if name already exists
    existing = db.query(Role).filter(Role.name == norm_name).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Role with identifier '{norm_name}' already exists."
        )

    # Create Role record
    new_role = Role(
        name=norm_name,
        display_name=payload.display_name.strip(),
        description=payload.description.strip() if payload.description else None,
        is_system=False,
        is_active=True
    )
    db.add(new_role)
    db.commit()
    db.refresh(new_role)

    # Process and save permissions
    provided_map = {p.module.lower(): p for p in payload.permissions}
    for mod in SYSTEM_MODULES:
        k = mod["key"].lower()
        p = provided_map.get(k)
        if p and p.has_access:
            role_perm = RolePermission(
                role_id=new_role.id,
                module=k,
                has_access=True,
                can_view=p.can_view,
                can_create=p.can_create,
                can_edit=p.can_edit,
                can_delete=p.can_delete,
                can_export=p.can_export,
                can_approve=p.can_approve,
                can_assign=p.can_assign,
                can_call=p.can_call,
                can_whatsapp=p.can_whatsapp,
                view_scope=p.view_scope if p.view_scope in ["none", "own", "team", "department", "company"] else "own"
            )
        else:
            role_perm = RolePermission(
                role_id=new_role.id,
                module=k,
                has_access=False,
                can_view=False,
                can_create=False,
                can_edit=False,
                can_delete=False,
                can_export=False,
                can_approve=False,
                can_assign=False,
                can_call=False,
                can_whatsapp=False,
                view_scope="none"
            )
        db.add(role_perm)

    db.commit()
    db.refresh(new_role)

    # Record Audit Log
    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action="CREATE_ROLE",
        entity_type="ROLE",
        entity_id=str(new_role.id),
        details=f"Created role '{new_role.name}' ({new_role.display_name}) with {len(payload.permissions)} configured permissions.",
        ip_address=client_ip
    )

    return get_role_detail(new_role.id, db, current_user)

@router.put("/{role_id}", response_model=RoleOut)
def update_role(
    role_id: int,
    payload: RoleUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update role metadata and permission matrix.
    Changes immediately take effect for all users assigned to this role.
    Enforces audit logging.
    """
    if current_user.role != "ADMIN":
        from services.permission_service import user_has_permission
        if not user_has_permission(current_user, "roles", "edit", db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not have permission to edit roles."
            )

    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found.")

    changes = []
    if payload.display_name is not None and payload.display_name.strip() != role.display_name:
        changes.append(f"display_name: '{role.display_name}' -> '{payload.display_name.strip()}'")
        role.display_name = payload.display_name.strip()

    if payload.description is not None:
        role.description = payload.description.strip()

    if payload.is_active is not None and not role.is_system:
        if role.is_active != payload.is_active:
            changes.append(f"is_active: {role.is_active} -> {payload.is_active}")
            role.is_active = payload.is_active

    # Update permissions if supplied and role is not ADMIN
    if payload.permissions is not None:
        if role.is_system and role.name.upper() == "ADMIN":
            pass # ADMIN always retains all system permissions
        else:
            provided_map = {p.module.lower(): p for p in payload.permissions}
            # Delete existing permissions for this role and re-insert cleanly
            db.query(RolePermission).filter(RolePermission.role_id == role.id).delete()

            for mod in SYSTEM_MODULES:
                k = mod["key"].lower()
                p = provided_map.get(k)
                if p and p.has_access:
                    role_perm = RolePermission(
                        role_id=role.id,
                        module=k,
                        has_access=True,
                        can_view=p.can_view,
                        can_create=p.can_create,
                        can_edit=p.can_edit,
                        can_delete=p.can_delete,
                        can_export=p.can_export,
                        can_approve=p.can_approve,
                        can_assign=p.can_assign,
                        can_call=p.can_call,
                        can_whatsapp=p.can_whatsapp,
                        view_scope=p.view_scope if p.view_scope in ["none", "own", "team", "department", "company"] else "own"
                    )
                else:
                    role_perm = RolePermission(
                        role_id=role.id,
                        module=k,
                        has_access=False,
                        can_view=False,
                        can_create=False,
                        can_edit=False,
                        can_delete=False,
                        can_export=False,
                        can_approve=False,
                        can_assign=False,
                        can_call=False,
                        can_whatsapp=False,
                        view_scope="none"
                    )
                db.add(role_perm)

            changes.append(f"updated permissions for {len(payload.permissions)} modules")

    db.commit()
    db.refresh(role)

    # Record Audit Log
    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action="UPDATE_ROLE",
        entity_type="ROLE",
        entity_id=str(role.id),
        details=f"Updated role '{role.name}' ({role.display_name}). Changes: {'; '.join(changes) if changes else 'No changes'}",
        ip_address=client_ip
    )

    return get_role_detail(role.id, db, current_user)

@router.delete("/{role_id}", status_code=status.HTTP_200_OK)
def delete_role(
    role_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a custom role.
    Cannot delete core system roles or roles currently assigned to active users.
    Enforces audit logging.
    """
    if current_user.role != "ADMIN":
        from services.permission_service import user_has_permission
        if not user_has_permission(current_user, "roles", "delete", db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not have permission to delete roles."
            )

    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found.")

    if role.is_system or role.name.upper() == "ADMIN":
        raise HTTPException(
            status_code=400,
            detail=f"System role '{role.display_name}' cannot be deleted."
        )

    # Check if any users are assigned to this role
    assigned_count = db.query(User).filter(User.role == role.name).count()
    if assigned_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete role '{role.display_name}' because {assigned_count} user(s) are currently assigned to it. Please reassign them first."
        )

    role_name = role.name
    display_name = role.display_name

    # Delete permissions and role
    db.query(RolePermission).filter(RolePermission.role_id == role.id).delete()
    db.delete(role)
    db.commit()

    # Record Audit Log
    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action="DELETE_ROLE",
        entity_type="ROLE",
        entity_id=str(role_id),
        details=f"Deleted role '{role_name}' ({display_name}).",
        ip_address=client_ip
    )

    return {"ok": True, "message": f"Role '{display_name}' deleted successfully."}
