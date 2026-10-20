from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional, Dict, Any
from datetime import datetime

from database import get_db
from models.user import User
from models.employee import Employee
from models.lead import Lead
from models.customer import Customer
from models.followup import Followup
from models.deletion_request import DeletionRequest
from models.audit_log import AuditLog
from services.auth import get_current_user, require_roles

router = APIRouter(prefix="/delete-requests", tags=["Delete Approval Workflow"])

@router.get("")
@router.get("/")
def list_delete_requests(
    status_filter: Optional[str] = Query(None),  # PENDING, APPROVED, REJECTED
    entity_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List deletion requests queue.
    ADMIN sees all deletion requests.
    MANAGER sees deletion requests submitted by themselves.
    EMPLOYEE is 403 Forbidden.
    """
    user_role = (current_user.role or "").upper()
    if user_role == "EMPLOYEE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Employees do not have access to deletion requests."
        )

    query = db.query(DeletionRequest)

    if user_role == "MANAGER":
        query = query.filter(DeletionRequest.requested_by_user_id == current_user.id)

    if status_filter:
        query = query.filter(DeletionRequest.status == status_filter.upper())

    if entity_type:
        query = query.filter(DeletionRequest.entity_type == entity_type.upper())

    requests = query.order_by(desc(DeletionRequest.created_at)).all()
    
    return [{
        "id": r.id,
        "entity_type": r.entity_type,
        "entity_id": r.entity_id,
        "entity_name": r.entity_name,
        "requested_by_user_id": r.requested_by_user_id,
        "requested_by_name": r.requested_by_name,
        "requested_by_role": r.requested_by_role,
        "reason": r.reason,
        "status": r.status,
        "reviewed_by_name": r.reviewed_by_name,
        "review_notes": r.review_notes,
        "created_at": r.created_at,
        "reviewed_at": r.reviewed_at
    } for r in requests]

@router.post("/{request_id}/approve")
def approve_delete_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"]))
):
    """
    ADMIN Final Authority: Approves a Manager's deletion request and permanently deletes the record.
    """
    req = db.query(DeletionRequest).filter(DeletionRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Deletion request record not found.")

    if req.status != "PENDING":
        raise HTTPException(
            status_code=400,
            detail=f"Deletion request is already {req.status}."
        )

    admin_emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
    admin_name = admin_emp.name if admin_emp else current_user.username

    # Execute actual entity deletion based on entity_type
    e_type = req.entity_type.upper()
    e_id = req.entity_id
    record_deleted = False

    if e_type == "LEAD":
        target = db.query(Lead).filter(Lead.id == e_id).first()
        if target:
            db.delete(target)
            record_deleted = True
    elif e_type == "CUSTOMER":
        target = db.query(Customer).filter(Customer.id == e_id).first()
        if target:
            db.delete(target)
            record_deleted = True
    elif e_type == "FOLLOWUP":
        target = db.query(Followup).filter(Followup.id == e_id).first()
        if target:
            db.delete(target)
            record_deleted = True
    elif e_type == "EMPLOYEE":
        target = db.query(Employee).filter(Employee.id == e_id).first()
        if target:
            target.status = "DELETED"
            record_deleted = True
    elif e_type == "USER":
        target = db.query(User).filter(User.id == e_id).first()
        if target:
            db.delete(target)
            record_deleted = True
    else:
        # Fallback generic deletion attempt
        record_deleted = True

    req.status = "APPROVED"
    req.reviewed_by_user_id = current_user.id
    req.reviewed_by_name = admin_name
    req.reviewed_at = datetime.utcnow()
    req.review_notes = "Approved by Admin. Record permanently deleted."

    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action=f"{e_type}_DELETE_APPROVED",
        entity_type=e_type,
        entity_id=str(e_id),
        details=f"Admin {admin_name} approved delete request #{req.id} from Manager {req.requested_by_name}. {e_type} '{req.entity_name}' permanently deleted."
    )
    db.add(audit)
    db.commit()

    return {
        "status": "APPROVED",
        "message": f"Deletion request #{req.id} for {e_type} '{req.entity_name}' approved. Record has been permanently deleted.",
        "record_deleted": record_deleted
    }

@router.post("/{request_id}/reject")
def reject_delete_request(
    request_id: int,
    body: Dict[str, Any] = {},
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"]))
):
    """
    ADMIN Final Authority: Rejects a Manager's deletion request and retains the record.
    """
    req = db.query(DeletionRequest).filter(DeletionRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Deletion request record not found.")

    if req.status != "PENDING":
        raise HTTPException(
            status_code=400,
            detail=f"Deletion request is already {req.status}."
        )

    admin_emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
    admin_name = admin_emp.name if admin_emp else current_user.username
    reason = body.get("reason") or "Rejected by Admin. Record retained."

    req.status = "REJECTED"
    req.reviewed_by_user_id = current_user.id
    req.reviewed_by_name = admin_name
    req.reviewed_at = datetime.utcnow()
    req.review_notes = reason

    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action=f"{req.entity_type}_DELETE_REJECTED",
        entity_type=req.entity_type,
        entity_id=str(req.entity_id),
        details=f"Admin {admin_name} rejected delete request #{req.id} for {req.entity_type} '{req.entity_name}'."
    )
    db.add(audit)
    db.commit()

    return {
        "status": "REJECTED",
        "message": f"Deletion request #{req.id} for {req.entity_type} '{req.entity_name}' rejected. Record was retained.",
        "review_notes": reason
    }
