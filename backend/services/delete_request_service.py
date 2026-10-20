from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, Callable

from models.user import User
from models.employee import Employee
from models.deletion_request import DeletionRequest
from models.audit_log import AuditLog
from models.notification import Notification

def log_audit_entry(db: Session, user_id: int, username: str, action: str, entity_type: str, entity_id: str, details: str):
    log = AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        details=details
    )
    db.add(log)
    db.commit()

def handle_entity_deletion(
    db: Session,
    current_user: User,
    entity_type: str,
    entity_id: int,
    entity_name: str,
    delete_fn: Callable[[], None],
    reason: Optional[str] = None
):
    """
    Dynamic RBAC Delete Handler:
    - Checks user's 'delete' and 'approve' permissions for the module in the database.
    - If user has 'approve' right or is ADMIN: Permanently deletes immediately.
    - If user has 'delete' right without 'approve': Submits DeletionRequest for approval.
    - If user lacks 'delete' right: HTTP 403 Forbidden.
    """
    from services.permission_service import user_has_permission

    module_key = {
        "LEAD": "leads",
        "CUSTOMER": "customers",
        "FOLLOWUP": "followups",
        "EMPLOYEE": "employees",
        "USER": "users",
    }.get(entity_type.upper(), "settings")

    can_delete = user_has_permission(current_user, module_key, "delete", db)
    can_approve = user_has_permission(current_user, module_key, "approve", db) or (current_user.role.upper() == "ADMIN")

    if not can_delete and not can_approve:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You do not have permission to delete {entity_type.lower()} records."
        )

    # Helper to get user display name
    user_emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
    user_display_name = user_emp.name if user_emp else (current_user.employee_name or current_user.username)

    # If user has approval authority, delete permanently now
    if can_approve:
        delete_fn()
        log_audit_entry(
            db=db,
            user_id=current_user.id,
            username=current_user.username,
            action=f"{entity_type.upper()}_DELETED",
            entity_type=entity_type.upper(),
            entity_id=str(entity_id),
            details=f"User {current_user.username} ({user_display_name}) permanently deleted {entity_type} '{entity_name}'."
        )
        return {
            "status": "deleted",
            "message": f"{entity_type} '{entity_name}' has been permanently deleted."
        }

    # Otherwise, submit request for approval
    existing_req = db.query(DeletionRequest).filter(
        DeletionRequest.entity_type == entity_type.upper(),
        DeletionRequest.entity_id == entity_id,
        DeletionRequest.status == "PENDING"
    ).first()

    if existing_req:
        return {
            "status": "pending_approval",
            "message": f"A deletion request for {entity_type} '{entity_name}' is already pending approval.",
            "request_id": existing_req.id
        }

    req_record = DeletionRequest(
        entity_type=entity_type.upper(),
        entity_id=entity_id,
        entity_name=entity_name,
        requested_by_user_id=current_user.id,
        requested_by_name=user_display_name,
        requested_by_role=current_user.role,
        reason=reason or f"Request to delete {entity_type} #{entity_id}",
        status="PENDING"
    )
    db.add(req_record)
    db.commit()
    db.refresh(req_record)

    # Create notification for Admin
    admin_notif = Notification(
        user_id=1,  # Admin user
        title="Deletion Approval Required",
        message=f"{user_display_name} requested deletion of {entity_type} '{entity_name}'.",
        type="DELETE_REQUEST",
        link="/organization/delete-requests"
    )
    db.add(admin_notif)
    db.commit()

    log_audit_entry(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action=f"{entity_type.upper()}_DELETE_REQUESTED",
        entity_type=entity_type.upper(),
        entity_id=str(entity_id),
        details=f"{user_display_name} requested deletion of {entity_type} '{entity_name}' (Pending Approval)."
    )

    return {
        "status": "pending_approval",
        "message": f"Deletion request for {entity_type} '{entity_name}' has been submitted for approval.",
        "request_id": req_record.id
    }
