"""Support customer history, leave coverage and incoming-call context APIs.

Backend authorization is the security boundary. Every endpoint below rejects
Sales/Finance users and verifies the concrete Support customer assignment
(including an explicit active leave-coverage row) before returning interaction
history or purchase information.
"""

from __future__ import annotations

import os
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.activity import LeadActivity
from models.customer import Customer
from models.employee import Employee
from models.lead import Lead
from models.support import EmployeeLeave, SupportCoverageAssignment, SupportInteraction
from models.user import User
from models.workflow import SupportHandoff
from schemas.support import (
    VALID_INTERACTION_TYPES,
    VALID_LEAVE_STATUSES,
    VALID_LEAVE_TYPES,
    CoverageAssignRequest,
    EmployeeLeaveCreate,
    EmployeeLeaveDecision,
    SupportInteractionCreate,
)
from services.auth import get_current_user
from services.hierarchy_service import normalize_role
from services.permission_service import (
    get_team_employee_ids,
    is_support_lead_authorized,
)
from services.support_service import (
    active_coverage_for_lead,
    active_coverage_query,
    build_customer_history,
    build_support_summary,
    employee_on_approved_leave,
    get_employee_availability,
    get_employee_for_user,
    get_interactions_for_customer,
    is_support_actor,
    is_support_manager_or_admin,
    permanent_owner_id,
    resolve_support_customer,
    serialize_coverage,
    serialize_customer_profile,
    serialize_leave,
    today_ist,
)
from utils.phone import find_existing_customer_by_phone, find_existing_lead_by_phone
from utils.timezone import get_ist_now

router = APIRouter(prefix="/support", tags=["Support History & Coverage"])

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024


def _actor_role(user: User) -> str:
    return normalize_role((user.role or "").strip().upper())


def _require_support_access(
    current_user: User,
    db: Session,
    manager_only: bool = False,
) -> Optional[Employee]:
    """Return the actor employee row, or raise a backend 403.

    Admin is allowed according to existing permission rules. Sales and Finance
    are always rejected so Support history cannot leak through direct API use.
    """
    role = _actor_role(current_user)
    employee = get_employee_for_user(current_user, db)

    if role == "ADMIN":
        return employee

    if not is_support_actor(current_user, employee):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Support interaction history is restricted to authorized Support employees.",
        )

    if manager_only and not is_support_manager_or_admin(current_user, employee):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Support Manager or Admin permission required.",
        )

    if employee is None and role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: No employee profile is linked to this account.",
        )
    return employee


def _require_actor_employee(current_user: User, db: Session) -> Employee:
    employee = _require_support_access(current_user, db)
    if employee is None:
        employee = get_employee_for_user(current_user, db)
    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An employee profile is required to record Support interactions.",
        )
    return employee


def _assert_customer_access(
    lead: Lead,
    current_user: User,
    db: Session,
) -> None:
    if _actor_role(current_user) == "ADMIN":
        return
    if not is_support_lead_authorized(lead, current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: This customer is not assigned to your Support scope.",
        )


def _load_support_customer(
    db: Session,
    lead_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    require_customer: bool = True,
):
    try:
        lead, customer, handoff = resolve_support_customer(
            db, lead_id=lead_id, customer_id=customer_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if lead is None and customer is None:
        raise HTTPException(status_code=404, detail="Support customer not found.")
    if require_customer and customer is None:
        raise HTTPException(
            status_code=400,
            detail="No customer profile is linked to this Support record.",
        )
    if lead is None:
        raise HTTPException(status_code=404, detail="Linked Support lead not found.")
    return lead, customer, handoff


def _support_team_ids(current_user: User, actor: Optional[Employee], db: Session) -> Optional[List[int]]:
    """None means company-wide (Admin); otherwise the Support manager's team."""
    if _actor_role(current_user) == "ADMIN":
        return None
    if actor and normalize_role(actor.role) == "SUPPORT_MANAGER":
        ids = get_team_employee_ids(actor.id, db)
        if actor.id not in ids:
            ids.append(actor.id)
        return ids
    return [actor.id] if actor else []


def _support_employee_query(db: Session):
    return db.query(Employee).filter(
        Employee.status == "ACTIVE",
        or_(
            Employee.department == "SUPPORT",
            Employee.role.in_(["SUPPORT_MANAGER", "SUPPORT_EXECUTIVE", "SUPPORT"]),
        ),
    )


def _validate_backup_employee(
    db: Session,
    backup: Optional[Employee],
    leave: EmployeeLeave,
):
    if not backup:
        raise HTTPException(status_code=404, detail="Backup Support employee not found.")
    if not is_support_actor(None, backup):
        raise HTTPException(status_code=400, detail="Selected employee is not a Support employee.")
    if (backup.status or "").upper() != "ACTIVE":
        raise HTTPException(status_code=400, detail="Selected backup employee is not active.")
    if backup.id == leave.employee_id:
        raise HTTPException(status_code=400, detail="The employee on leave cannot be their own backup.")
    overlapping_leave = employee_on_approved_leave(
        db, backup.id, leave.start_date, leave.end_date
    )
    if overlapping_leave:
        raise HTTPException(
            status_code=409,
            detail="Selected backup employee is also on approved leave during these dates.",
        )


def _assigned_customers_for_employee(db: Session, employee_id: int) -> List[Dict[str, Any]]:
    """Customers whose permanent Support owner is this employee.

    Returns one row per lead, using the latest handover when legacy data has
    more than one. No customer or handover row is created.
    """
    handoffs = (
        db.query(SupportHandoff)
        .outerjoin(Lead, SupportHandoff.lead_id == Lead.id)
        .filter(
            or_(
                SupportHandoff.assigned_agent_id == employee_id,
                Lead.assigned_to == employee_id,
            )
        )
        .order_by(desc(SupportHandoff.id))
        .all()
    )
    seen = set()
    results: List[Dict[str, Any]] = []
    for handoff in handoffs:
        if handoff.lead_id in seen:
            continue
        lead = db.query(Lead).filter(Lead.id == handoff.lead_id).first()
        if not lead:
            continue
        owner = permanent_owner_id(lead, handoff)
        if owner != employee_id:
            continue
        seen.add(handoff.lead_id)
        customer = None
        if handoff.customer_id:
            customer = db.query(Customer).filter(Customer.id == handoff.customer_id).first()
        if customer is None and getattr(lead, "customer", None) is not None:
            customer = lead.customer
        if customer is None:
            customer = db.query(Customer).filter(Customer.converted_from_lead == lead.id).first()
        if customer is None:
            continue
        profile = serialize_customer_profile(db, lead, customer, handoff, include_purchase=True)
        results.append(profile)
    return results


def _coverage_overlapping(
    db: Session,
    lead_id: int,
    start_date: date,
    end_date: date,
    exclude_id: Optional[int] = None,
):
    query = db.query(SupportCoverageAssignment).filter(
        SupportCoverageAssignment.lead_id == lead_id,
        SupportCoverageAssignment.status == "ACTIVE",
        SupportCoverageAssignment.start_date <= end_date,
        SupportCoverageAssignment.end_date >= start_date,
    )
    if exclude_id:
        query = query.filter(SupportCoverageAssignment.id != exclude_id)
    return query.order_by(desc(SupportCoverageAssignment.id)).first()


def _customers_needing_coverage(
    db: Session,
    leave: EmployeeLeave,
) -> List[Dict[str, Any]]:
    rows = _assigned_customers_for_employee(db, leave.employee_id)
    for row in rows:
        coverage = _coverage_overlapping(
            db, row["lead_id"], leave.start_date, leave.end_date
        )
        row["existing_coverage"] = serialize_coverage(coverage)
        row["coverage_required"] = coverage is None
    return rows


def _add_support_audit_activity(
    db: Session,
    lead_id: int,
    employee_id: Optional[int],
    activity_type: str,
    description: str,
    customer_id: Optional[int] = None,
    related_entity_type: str = "CUSTOMER",
    related_entity_id: Optional[int] = None,
):
    db.add(
        LeadActivity(
            lead_id=lead_id,
            customer_id=customer_id,
            employee_id=employee_id,
            performed_by=employee_id,
            activity_type=activity_type,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            department="SUPPORT",
            description=description,
        )
    )


def _normalise_attachments(raw: Optional[List[Any]]) -> List[Dict[str, Any]]:
    if not raw:
        return []
    if not isinstance(raw, list):
        raise HTTPException(status_code=400, detail="attachments must be a list.")
    if len(raw) > 20:
        raise HTTPException(status_code=400, detail="A maximum of 20 attachments is allowed.")
    result: List[Dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            text = item.strip()
            if text:
                result.append({"name": os.path.basename(text), "url": text})
        elif isinstance(item, dict):
            url = str(item.get("url") or "").strip()
            name = str(item.get("name") or os.path.basename(url) or "attachment").strip()
            if url:
                result.append(
                    {
                        "name": name[:255],
                        "url": url,
                        "content_type": item.get("content_type"),
                        "size": item.get("size"),
                    }
                )
        else:
            raise HTTPException(status_code=400, detail="Invalid attachment entry.")
    return result


def _normalise_datetime(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is not None:
        from utils.timezone import IST_TIMEZONE

        value = value.astimezone(IST_TIMEZONE).replace(tzinfo=None)
    return value


def _leave_in_scope(
    leave: EmployeeLeave,
    current_user: User,
    actor: Optional[Employee],
    db: Session,
) -> bool:
    if _actor_role(current_user) == "ADMIN":
        return True
    if actor is None:
        return False
    if leave.employee_id == actor.id:
        return True
    if normalize_role(actor.role) == "SUPPORT_MANAGER":
        return leave.employee_id in get_team_employee_ids(actor.id, db)
    return False


def _serialize_employee(employee: Employee, db: Session) -> Dict[str, Any]:
    data = get_employee_availability(db, employee)
    data["assigned_customer_count"] = (
        db.query(SupportHandoff)
        .filter(SupportHandoff.assigned_agent_id == employee.id)
        .count()
    )
    data["temporary_coverage_count"] = (
        active_coverage_query(db)
        .filter(SupportCoverageAssignment.backup_employee_id == employee.id)
        .count()
    )
    return data


# ---------------------------------------------------------------------------
# Employee availability / leave management
# ---------------------------------------------------------------------------
@router.get("/employees")
def list_support_employees(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    actor = _require_support_access(current_user, db)
    team_ids = _support_team_ids(current_user, actor, db)
    query = _support_employee_query(db)
    if team_ids is not None:
        query = query.filter(Employee.id.in_(team_ids))
    employees = query.order_by(Employee.name.asc()).all()
    return [_serialize_employee(employee, db) for employee in employees]


@router.get("/leaves")
def list_leaves(
    status_filter: Optional[str] = Query(None, alias="status"),
    employee_id: Optional[int] = Query(None),
    include_past: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    actor = _require_support_access(current_user, db)
    role = _actor_role(current_user)
    query = db.query(EmployeeLeave)

    if role != "ADMIN":
        if actor is None:
            raise HTTPException(status_code=403, detail="Employee profile required.")
        if normalize_role(actor.role) == "SUPPORT_MANAGER":
            allowed_ids = get_team_employee_ids(actor.id, db)
            if actor.id not in allowed_ids:
                allowed_ids.append(actor.id)
            query = query.filter(EmployeeLeave.employee_id.in_(allowed_ids))
        else:
            query = query.filter(EmployeeLeave.employee_id == actor.id)

    if employee_id:
        if role != "ADMIN" and actor:
            if normalize_role(actor.role) == "SUPPORT_MANAGER":
                allowed_ids = get_team_employee_ids(actor.id, db)
                if actor.id not in allowed_ids:
                    allowed_ids.append(actor.id)
            else:
                allowed_ids = [actor.id]
            if employee_id not in allowed_ids:
                raise HTTPException(status_code=403, detail="Access denied to this employee's leave records.")
        query = query.filter(EmployeeLeave.employee_id == employee_id)

    if status_filter:
        normalized = status_filter.strip().upper()
        if normalized not in VALID_LEAVE_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid leave status filter.")
        query = query.filter(EmployeeLeave.status == normalized)

    if not include_past:
        query = query.filter(EmployeeLeave.end_date >= today_ist())

    leaves = query.order_by(EmployeeLeave.start_date.desc(), EmployeeLeave.id.desc()).all()
    return [serialize_leave(leave) for leave in leaves]


@router.post("/leaves", status_code=status.HTTP_201_CREATED)
def create_leave(
    payload: EmployeeLeaveCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    actor = _require_support_access(current_user, db)
    role = _actor_role(current_user)
    target_id = payload.employee_id or (actor.id if actor else None)
    if not target_id:
        raise HTTPException(status_code=400, detail="employee_id is required.")

    target = db.query(Employee).filter(Employee.id == target_id).first()
    if not target or not is_support_actor(None, target):
        raise HTTPException(status_code=400, detail="Selected employee is not a Support employee.")

    if role != "ADMIN":
        if actor is None:
            raise HTTPException(status_code=403, detail="Employee profile required.")
        if normalize_role(actor.role) == "SUPPORT_MANAGER":
            allowed_ids = get_team_employee_ids(actor.id, db)
            if target.id not in allowed_ids and target.id != actor.id:
                raise HTTPException(status_code=403, detail="Access denied to this employee.")
        elif target.id != actor.id:
            raise HTTPException(status_code=403, detail="You can only request leave for yourself.")

    leave_type = (payload.leave_type or "CASUAL").strip().upper()
    if leave_type not in VALID_LEAVE_TYPES:
        raise HTTPException(status_code=400, detail="Invalid leave type.")
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="Leave end date cannot be before the start date.")

    duplicate = (
        db.query(EmployeeLeave)
        .filter(
            EmployeeLeave.employee_id == target.id,
            EmployeeLeave.status.in_(["PENDING", "APPROVED"]),
            EmployeeLeave.start_date <= payload.end_date,
            EmployeeLeave.end_date >= payload.start_date,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=f"An overlapping {duplicate.status.lower()} leave already exists for this employee.",
        )

    leave = EmployeeLeave(
        employee_id=target.id,
        leave_type=leave_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
        status="PENDING",
        reason=payload.reason,
        manager_notes=payload.manager_notes,
        created_by_employee_id=actor.id if actor else None,
    )
    db.add(leave)
    db.commit()
    db.refresh(leave)
    return serialize_leave(leave)


@router.get("/leaves/{leave_id}")
def get_leave(
    leave_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    actor = _require_support_access(current_user, db)
    leave = db.query(EmployeeLeave).filter(EmployeeLeave.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave record not found.")
    if not _leave_in_scope(leave, current_user, actor, db):
        raise HTTPException(status_code=403, detail="Access denied to this leave record.")
    return serialize_leave(leave)


@router.post("/leaves/{leave_id}/approve")
def approve_leave(
    leave_id: int,
    payload: Optional[EmployeeLeaveDecision] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    actor = _require_support_access(current_user, db, manager_only=True)
    leave = db.query(EmployeeLeave).filter(EmployeeLeave.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave record not found.")
    if not _leave_in_scope(leave, current_user, actor, db):
        raise HTTPException(status_code=403, detail="Access denied to this leave record.")

    if leave.status == "APPROVED":
        return {
            "leave": serialize_leave(leave),
            "customers_needing_coverage": _customers_needing_coverage(db, leave),
            "already_approved": True,
        }
    if leave.status in {"REJECTED", "CANCELLED"}:
        raise HTTPException(status_code=409, detail=f"Cannot approve a {leave.status.lower()} leave.")

    overlap = (
        db.query(EmployeeLeave)
        .filter(
            EmployeeLeave.id != leave.id,
            EmployeeLeave.employee_id == leave.employee_id,
            EmployeeLeave.status == "APPROVED",
            EmployeeLeave.start_date <= leave.end_date,
            EmployeeLeave.end_date >= leave.start_date,
        )
        .first()
    )
    if overlap:
        raise HTTPException(status_code=409, detail="Another approved leave overlaps these dates.")

    leave.status = "APPROVED"
    leave.approved_by_employee_id = actor.id if actor else None
    leave.approved_at = get_ist_now()
    if payload and payload.manager_notes:
        leave.manager_notes = payload.manager_notes
    db.commit()
    db.refresh(leave)

    return {
        "leave": serialize_leave(leave),
        "customers_needing_coverage": _customers_needing_coverage(db, leave),
        "already_approved": False,
    }


@router.post("/leaves/{leave_id}/reject")
def reject_leave(
    leave_id: int,
    payload: Optional[EmployeeLeaveDecision] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    actor = _require_support_access(current_user, db, manager_only=True)
    leave = db.query(EmployeeLeave).filter(EmployeeLeave.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave record not found.")
    if not _leave_in_scope(leave, current_user, actor, db):
        raise HTTPException(status_code=403, detail="Access denied to this leave record.")
    if leave.status == "APPROVED":
        raise HTTPException(status_code=409, detail="Approved leave cannot be rejected; cancel coverage first.")
    leave.status = "REJECTED"
    leave.approved_by_employee_id = actor.id if actor else None
    leave.approved_at = get_ist_now()
    if payload and payload.manager_notes:
        leave.manager_notes = payload.manager_notes
    db.commit()
    db.refresh(leave)
    return serialize_leave(leave)


@router.post("/leaves/{leave_id}/cancel")
def cancel_leave(
    leave_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    actor = _require_support_access(current_user, db)
    leave = db.query(EmployeeLeave).filter(EmployeeLeave.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave record not found.")
    if not _leave_in_scope(leave, current_user, actor, db):
        raise HTTPException(status_code=403, detail="Access denied to this leave record.")
    active_coverages = (
        db.query(SupportCoverageAssignment)
        .filter(
            SupportCoverageAssignment.leave_id == leave.id,
            SupportCoverageAssignment.status == "ACTIVE",
        )
        .count()
    )
    if active_coverages:
        raise HTTPException(
            status_code=409,
            detail="End active coverage assignments before cancelling this leave.",
        )
    leave.status = "CANCELLED"
    db.commit()
    db.refresh(leave)
    return serialize_leave(leave)


@router.get("/leaves/{leave_id}/customers")
def leave_customers(
    leave_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    actor = _require_support_access(current_user, db)
    leave = db.query(EmployeeLeave).filter(EmployeeLeave.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave record not found.")
    if not _leave_in_scope(leave, current_user, actor, db):
        raise HTTPException(status_code=403, detail="Access denied to this leave record.")
    return {
        "leave": serialize_leave(leave),
        "customers": _customers_needing_coverage(db, leave),
    }


@router.post("/leaves/{leave_id}/coverage")
def assign_leave_coverage(
    leave_id: int,
    payload: CoverageAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    actor = _require_support_access(current_user, db, manager_only=True)
    leave = db.query(EmployeeLeave).filter(EmployeeLeave.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave record not found.")
    if not _leave_in_scope(leave, current_user, actor, db):
        raise HTTPException(status_code=403, detail="Access denied to this leave record.")
    if leave.status != "APPROVED":
        raise HTTPException(status_code=409, detail="Coverage can only be assigned for an approved leave.")

    backup = db.query(Employee).filter(Employee.id == payload.backup_employee_id).first()
    _validate_backup_employee(db, backup, leave)

    assigned = _assigned_customers_for_employee(db, leave.employee_id)
    assigned_by_lead = {row["lead_id"]: row for row in assigned}

    selected_leads: List[int] = []
    if payload.all_assigned_customers:
        selected_leads = [row["lead_id"] for row in assigned]
    else:
        requested = list(payload.lead_ids or [])
        if payload.customer_ids:
            for customer_id in payload.customer_ids:
                try:
                    lead, _customer, _handoff = resolve_support_customer(
                        db, customer_id=customer_id
                    )
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc
                if lead:
                    requested.append(lead.id)
        selected_leads = list(dict.fromkeys(requested))

    if not selected_leads:
        raise HTTPException(
            status_code=400,
            detail="Select at least one customer or set all_assigned_customers=true.",
        )

    # Pre-validate every customer before creating any row so a bulk request
    # cannot partially assign an invalid customer.
    plan = []
    skipped = []
    for lead_id in selected_leads:
        row = assigned_by_lead.get(lead_id)
        if not row:
            raise HTTPException(
                status_code=400,
                detail=f"Customer #{lead_id} is not currently assigned to the employee on leave.",
            )
        existing = _coverage_overlapping(db, lead_id, leave.start_date, leave.end_date)
        if existing:
            skipped.append(
                {
                    "lead_id": lead_id,
                    "reason": "ACTIVE_COVERAGE_EXISTS",
                    "existing_coverage": serialize_coverage(existing),
                }
            )
            continue
        plan.append(row)

    created = []
    for row in plan:
        coverage = SupportCoverageAssignment(
            customer_id=row["customer_id"],
            lead_id=row["lead_id"],
            support_handoff_id=row.get("support_handoff_id"),
            leave_id=leave.id,
            original_employee_id=leave.employee_id,
            backup_employee_id=backup.id,
            assigned_by_employee_id=actor.id if actor else None,
            start_date=leave.start_date,
            end_date=leave.end_date,
            status="ACTIVE",
        )
        db.add(coverage)
        db.flush()
        _add_support_audit_activity(
            db,
            lead_id=row["lead_id"],
            employee_id=actor.id if actor else None,
            customer_id=row["customer_id"],
            activity_type="SUPPORT_BACKUP_COVERAGE_ASSIGNED",
            description=(
                f"Temporary Support coverage assigned to {backup.name} for "
                f"{leave.start_date.isoformat()} to {leave.end_date.isoformat()} "
                f"while {row.get('original_support_employee_name') or 'the permanent owner'} is on leave."
            ),
            related_entity_type="SUPPORT_COVERAGE",
            related_entity_id=coverage.id,
        )
        created.append(coverage)

    db.commit()
    for coverage in created:
        db.refresh(coverage)

    return {
        "leave": serialize_leave(leave),
        "backup_employee_id": backup.id,
        "backup_employee_name": backup.name,
        "created": [serialize_coverage(row) for row in created],
        "skipped": skipped,
        "created_count": len(created),
        "skipped_count": len(skipped),
    }


@router.post("/coverage/{coverage_id}/restore")
def restore_original_assignment(
    coverage_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    actor = _require_support_access(current_user, db, manager_only=True)
    coverage = (
        db.query(SupportCoverageAssignment)
        .filter(SupportCoverageAssignment.id == coverage_id)
        .first()
    )
    if not coverage:
        raise HTTPException(status_code=404, detail="Coverage assignment not found.")
    if _actor_role(current_user) != "ADMIN" and actor:
        allowed = get_team_employee_ids(actor.id, db)
        if actor.id not in allowed:
            allowed.append(actor.id)
        if not ({coverage.original_employee_id, coverage.backup_employee_id} & set(allowed)):
            raise HTTPException(status_code=403, detail="Access denied to this coverage assignment.")
    if coverage.status == "ENDED":
        return {"coverage": serialize_coverage(coverage), "already_ended": True}

    lead = db.query(Lead).filter(Lead.id == coverage.lead_id).first()
    handoff = (
        db.query(SupportHandoff)
        .filter(SupportHandoff.id == coverage.support_handoff_id)
        .first()
        if coverage.support_handoff_id
        else db.query(SupportHandoff)
        .filter(SupportHandoff.lead_id == coverage.lead_id)
        .order_by(desc(SupportHandoff.id))
        .first()
    )
    current_owner = permanent_owner_id(lead, handoff)
    if current_owner != coverage.original_employee_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The permanent customer owner changed during the leave period. "
                "Automatic restore was refused. Review the handover history and "
                "assign the permanent owner explicitly."
            ),
        )

    coverage.status = "ENDED"
    coverage.ended_at = get_ist_now()
    coverage.ended_by_employee_id = actor.id if actor else None
    coverage.end_reason = "EMPLOYEE_RETURNED"
    _add_support_audit_activity(
        db,
        lead_id=coverage.lead_id,
        employee_id=actor.id if actor else None,
        customer_id=coverage.customer_id,
        activity_type="SUPPORT_BACKUP_COVERAGE_ENDED",
        description=(
            f"Temporary Support coverage ended. Permanent owner "
            f"#{coverage.original_employee_id} remains unchanged."
        ),
        related_entity_type="SUPPORT_COVERAGE",
        related_entity_id=coverage.id,
    )
    db.commit()
    db.refresh(coverage)
    return {"coverage": serialize_coverage(coverage), "already_ended": False}


# ---------------------------------------------------------------------------
# Interactions / customer history
# ---------------------------------------------------------------------------
@router.get("/customers/{lead_id}/history")
def get_customer_support_history(
    lead_id: int,
    customer_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_support_access(current_user, db)
    lead, customer, handoff = _load_support_customer(
        db, lead_id=lead_id, customer_id=customer_id, require_customer=True
    )
    _assert_customer_access(lead, current_user, db)
    return build_customer_history(db, lead, customer, handoff)


@router.post("/customers/{lead_id}/interactions", status_code=status.HTTP_201_CREATED)
def create_support_interaction(
    lead_id: int,
    payload: SupportInteractionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    actor = _require_actor_employee(current_user, db)
    _require_support_access(current_user, db)
    lead, customer, handoff = _load_support_customer(
        db, lead_id=lead_id, customer_id=payload.customer_id, require_customer=True
    )
    _assert_customer_access(lead, current_user, db)

    if payload.client_reference:
        existing = (
            db.query(SupportInteraction)
            .filter(
                SupportInteraction.customer_id == customer.id,
                SupportInteraction.client_reference == payload.client_reference,
            )
            .first()
        )
        if existing:
            return {
                "interaction": existing.to_dict(),
                "summary": build_support_summary(
                    get_interactions_for_customer(db, customer.id, lead.id)
                ),
                "duplicate": True,
            }

    interaction_type = (payload.interaction_type or "MANUAL").strip().upper()
    if interaction_type not in VALID_INTERACTION_TYPES:
        raise HTTPException(
            status_code=400,
            detail="interaction_type must be INBOUND, OUTBOUND or MANUAL.",
        )

    content_fields = [
        payload.discussion,
        payload.problem_reported,
        payload.troubleshooting,
        payload.solution_provided,
        payload.pending_issues,
        payload.customer_commitments,
        payload.next_action,
        payload.notes,
    ]
    if not any(str(value or "").strip() for value in content_fields):
        raise HTTPException(
            status_code=400,
            detail="At least one interaction detail, note, problem or action is required.",
        )

    interaction_at = _normalise_datetime(payload.interaction_at) or get_ist_now()
    follow_up_at = _normalise_datetime(payload.follow_up_at)
    if follow_up_at and follow_up_at < interaction_at:
        raise HTTPException(
            status_code=400,
            detail="Follow-up date/time cannot be before the interaction date/time.",
        )

    owner_id = permanent_owner_id(lead, handoff)
    interaction = SupportInteraction(
        customer_id=customer.id,
        lead_id=lead.id,
        support_handoff_id=handoff.id if handoff else None,
        interaction_type=interaction_type,
        interaction_at=interaction_at,
        discussion=(payload.discussion or "").strip() or None,
        problem_reported=(payload.problem_reported or "").strip() or None,
        troubleshooting=(payload.troubleshooting or "").strip() or None,
        solution_provided=(payload.solution_provided or "").strip() or None,
        pending_issues=(payload.pending_issues or "").strip() or None,
        customer_commitments=(payload.customer_commitments or "").strip() or None,
        next_action=(payload.next_action or "").strip() or None,
        follow_up_at=follow_up_at,
        notes=(payload.notes or "").strip() or None,
        attachments=_normalise_attachments(payload.attachments),
        original_employee_id=owner_id,
        handling_employee_id=actor.id,
        created_by_employee_id=actor.id,
        department="SUPPORT",
        client_reference=(payload.client_reference or "").strip() or None,
    )
    db.add(interaction)
    db.flush()

    _add_support_audit_activity(
        db,
        lead_id=lead.id,
        employee_id=actor.id,
        customer_id=customer.id,
        activity_type="SUPPORT_INTERACTION",
        description=(
            f"Support interaction recorded by {actor.name} "
            f"({interaction_type}) at {interaction_at.strftime('%d %b %Y, %I:%M %p')}."
        ),
        related_entity_type="SUPPORT_INTERACTION",
        related_entity_id=interaction.id,
    )
    db.commit()
    db.refresh(interaction)

    all_interactions = get_interactions_for_customer(db, customer.id, lead.id)
    return {
        "interaction": interaction.to_dict(),
        "summary": build_support_summary(all_interactions),
        "duplicate": False,
    }


@router.post("/interactions/{interaction_id}/attachments")
def upload_interaction_attachment(
    interaction_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    actor = _require_actor_employee(current_user, db)
    _require_support_access(current_user, db)
    interaction = (
        db.query(SupportInteraction)
        .filter(SupportInteraction.id == interaction_id)
        .first()
    )
    if not interaction:
        raise HTTPException(status_code=404, detail="Support interaction not found.")
    lead = db.query(Lead).filter(Lead.id == interaction.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Linked Support lead not found.")
    _assert_customer_access(lead, current_user, db)

    filename = os.path.basename(file.filename or "attachment")
    suffix = Path(filename).suffix.lower()[:20]
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    directory = Path(settings.UPLOAD_DIR) / "support_interactions" / str(interaction.id)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / stored_name

    size = 0
    try:
        with target.open("wb") as buffer:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_ATTACHMENT_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="Attachment exceeds the 10 MB limit.",
                    )
                buffer.write(chunk)
    except HTTPException:
        if target.exists():
            target.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()

    existing = list(interaction.attachments or [])
    existing.append(
        {
            "name": filename[:255],
            "url": f"/uploads/support_interactions/{interaction.id}/{stored_name}",
            "content_type": file.content_type,
            "size": size,
            "uploaded_by_employee_id": actor.id,
            "uploaded_at": get_ist_now().isoformat(),
        }
    )
    interaction.attachments = existing
    db.commit()
    db.refresh(interaction)
    return interaction.to_dict()


@router.get("/interactions/{interaction_id}")
def get_support_interaction(
    interaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_support_access(current_user, db)
    interaction = (
        db.query(SupportInteraction)
        .filter(SupportInteraction.id == interaction_id)
        .first()
    )
    if not interaction:
        raise HTTPException(status_code=404, detail="Support interaction not found.")
    lead = db.query(Lead).filter(Lead.id == interaction.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Linked Support lead not found.")
    _assert_customer_access(lead, current_user, db)
    return interaction.to_dict()


# ---------------------------------------------------------------------------
# Backup employee view
# ---------------------------------------------------------------------------
@router.get("/backup-customers")
def list_backup_customers(
    employee_id: Optional[int] = Query(None),
    include_history: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    actor = _require_support_access(current_user, db)
    query = active_coverage_query(db)

    if _actor_role(current_user) != "ADMIN":
        if actor is None:
            raise HTTPException(status_code=403, detail="Employee profile required.")
        if normalize_role(actor.role) == "SUPPORT_MANAGER":
            team_ids = get_team_employee_ids(actor.id, db)
            if actor.id not in team_ids:
                team_ids.append(actor.id)
            if employee_id:
                if employee_id not in team_ids:
                    raise HTTPException(status_code=403, detail="Access denied to this employee.")
                query = query.filter(SupportCoverageAssignment.backup_employee_id == employee_id)
            else:
                query = query.filter(SupportCoverageAssignment.backup_employee_id.in_(team_ids))
        else:
            if employee_id and employee_id != actor.id:
                raise HTTPException(status_code=403, detail="You can only view your own backup customers.")
            query = query.filter(SupportCoverageAssignment.backup_employee_id == actor.id)

    coverages = query.order_by(
        SupportCoverageAssignment.start_date.asc(), SupportCoverageAssignment.id.asc()
    ).all()

    results = []
    for coverage in coverages:
        lead = db.query(Lead).filter(Lead.id == coverage.lead_id).first()
        customer = db.query(Customer).filter(Customer.id == coverage.customer_id).first()
        if not lead or not customer:
            continue
        handoff = (
            db.query(SupportHandoff)
            .filter(SupportHandoff.id == coverage.support_handoff_id)
            .first()
            if coverage.support_handoff_id
            else db.query(SupportHandoff)
            .filter(SupportHandoff.lead_id == lead.id)
            .order_by(desc(SupportHandoff.id))
            .first()
        )
        history = build_customer_history(
            db, lead, customer, handoff, include_purchase=True
        )
        results.append(
            {
                **history,
                "coverage_id": coverage.id,
                "coverage": serialize_coverage(coverage),
                "leave": serialize_leave(coverage.leave) if coverage.leave else None,
                "interactions": (
                    history["interactions"] if include_history else []
                ),
            }
        )
    return {
        "total": len(results),
        "items": results,
    }


# ---------------------------------------------------------------------------
# Incoming call customer information panel
# ---------------------------------------------------------------------------
@router.get("/incoming-call-context")
def incoming_call_context(
    phone: Optional[str] = Query(None),
    number: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return authorized Support context for a caller.

    This endpoint does not answer, connect or route calls. It only joins the
    existing DooCTI caller phone number to CRM Support records for the
    authenticated agent. DooCTI keeps ownership of answer/hangup controls.
    """
    actor = _require_support_access(current_user, db)
    raw_phone = phone or number
    if not raw_phone:
        raise HTTPException(status_code=400, detail="phone is required.")

    lead = find_existing_lead_by_phone(db, raw_phone)
    customer = find_existing_customer_by_phone(db, raw_phone)
    if lead is None and customer is None:
        return {
            "found": False,
            "authorized": False,
            "phone": raw_phone,
            "message": "No CRM customer is linked to this phone number.",
            "call_control": {
                "provider": "DOOCTI",
                "crm_side_only": True,
                "note": "This panel does not answer, connect, reject or hang up calls.",
            },
        }

    try:
        if lead is None and customer is not None:
            lead, customer, handoff = resolve_support_customer(
                db, customer_id=customer.id
            )
        else:
            lead, customer, handoff = resolve_support_customer(db, lead_id=lead.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    authorized = bool(
        _actor_role(current_user) == "ADMIN"
        or (lead is not None and is_support_lead_authorized(lead, current_user, db))
    )

    if not authorized:
        return {
            "found": True,
            "authorized": False,
            "phone": raw_phone,
            "message": "Customer found, but this Support employee is not authorized for the customer history.",
            "customer": {
                "lead_id": lead.id if lead else None,
                "customer_id": customer.id if customer else None,
                "customer_name": (
                    (customer.contact_name if customer else None)
                    or (lead.name if lead else None)
                ),
                "company_name": (
                    (customer.company_name if customer else None)
                    or (lead.company if lead else None)
                ),
                "phone": (
                    (customer.phone if customer else None)
                    or (lead.phone if lead else None)
                ),
            },
            "call_control": {
                "provider": "DOOCTI",
                "crm_side_only": True,
                "note": "This panel does not answer, connect, reject or hang up calls.",
            },
        }

    if lead is None or customer is None:
        return {
            "found": True,
            "authorized": True,
            "phone": raw_phone,
            "customer": {
                "customer_id": customer.id if customer else None,
                "customer_name": customer.contact_name if customer else None,
                "company_name": customer.company_name if customer else None,
                "phone": customer.phone if customer else raw_phone,
            },
            "message": "Customer found, but no Support handover exists yet.",
            "call_control": {
                "provider": "DOOCTI",
                "crm_side_only": True,
                "note": "This panel does not answer, connect, reject or hang up calls.",
            },
        }

    history = build_customer_history(db, lead, customer, handoff, include_purchase=True)
    summary = history["summary"]
    original_employee = (
        db.query(Employee)
        .filter(Employee.id == history["original_support_employee_id"])
        .first()
        if history.get("original_support_employee_id")
        else None
    )
    coverage = active_coverage_for_lead(db, lead.id)
    backup_employee = coverage.backup_employee if coverage else None
    current_handler = (
        backup_employee
        if backup_employee
        else original_employee
    )
    receiver = actor

    return {
        "found": True,
        "authorized": True,
        "phone": raw_phone,
        "customer": {
            "lead_id": lead.id,
            "customer_id": customer.id,
            "customer_name": history["customer_name"],
            "company_name": history["company_name"],
            "phone": history["phone"],
            "email": history["email"],
            "location": history["location"],
        },
        "assignment": {
            "original_support_employee_id": (
                original_employee.id if original_employee else None
            ),
            "original_support_employee_name": (
                original_employee.name if original_employee else None
            ),
            "current_handling_employee_id": (
                current_handler.id if current_handler else None
            ),
            "current_handling_employee_name": (
                current_handler.name if current_handler else None
            ),
            "backup_employee_id": backup_employee.id if backup_employee else None,
            "backup_employee_name": backup_employee.name if backup_employee else None,
            "coverage": serialize_coverage(coverage),
        },
        "employee_availability": {
            "original": (
                get_employee_availability(db, original_employee)
                if original_employee
                else None
            ),
            "backup": (
                get_employee_availability(db, backup_employee)
                if backup_employee
                else None
            ),
            "call_receiver": get_employee_availability(db, receiver) if receiver else None,
        },
        "last_conversation_summary": summary.get("last_conversation_summary"),
        "last_reported_problem": summary.get("last_reported_problem"),
        "unresolved_issue": summary.get("current_unresolved_issue"),
        "pending_follow_up": summary.get("pending_follow_up"),
        "latest_interaction": summary.get("latest_interaction"),
        "last_three_interactions": summary.get("last_three_interactions"),
        "summary": summary,
        "purchase_details": history.get("purchase_details"),
        "interaction_count": len(history.get("interactions") or []),
        "call_control": {
            "provider": "DOOCTI",
            "crm_side_only": True,
            "provider_routing_changed": False,
            "note": (
                "CRM-side customer history visibility only. The existing DooCTI "
                "provider controls answer, connect, reject and hangup events; "
                "no CONNECTED/ANSWERED event is created by this endpoint."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Support Manager overview / handover history
# ---------------------------------------------------------------------------
@router.get("/manager/overview")
def support_manager_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    actor = _require_support_access(current_user, db, manager_only=True)
    role = _actor_role(current_user)
    team_ids = _support_team_ids(current_user, actor, db)

    employees_query = _support_employee_query(db)
    if team_ids is not None:
        employees_query = employees_query.filter(Employee.id.in_(team_ids))
    employees = employees_query.order_by(Employee.name.asc()).all()
    availability = [_serialize_employee(employee, db) for employee in employees]

    leave_query = db.query(EmployeeLeave).filter(EmployeeLeave.status == "APPROVED")
    if team_ids is not None:
        leave_query = leave_query.filter(EmployeeLeave.employee_id.in_(team_ids))
    approved_leaves = (
        leave_query.filter(EmployeeLeave.end_date >= today_ist())
        .order_by(EmployeeLeave.start_date.asc(), EmployeeLeave.id.asc())
        .all()
    )

    coverage_query = active_coverage_query(db)
    history_query = db.query(SupportCoverageAssignment)
    if team_ids is not None:
        coverage_query = coverage_query.filter(
            SupportCoverageAssignment.backup_employee_id.in_(team_ids)
        )
        history_query = history_query.filter(
            or_(
                SupportCoverageAssignment.original_employee_id.in_(team_ids),
                SupportCoverageAssignment.backup_employee_id.in_(team_ids),
            )
        )
    active_coverages = coverage_query.order_by(SupportCoverageAssignment.id.desc()).all()
    handover_history = history_query.order_by(
        desc(SupportCoverageAssignment.created_at), desc(SupportCoverageAssignment.id)
    ).limit(100).all()

    def coverage_row(coverage):
        data = coverage.to_dict()
        customer = (
            db.query(Customer).filter(Customer.id == coverage.customer_id).first()
        )
        data["customer_name"] = (
            customer.contact_name if customer else None
        ) or (coverage.lead.name if coverage.lead else None)
        data["company_name"] = (
            customer.company_name if customer else None
        ) or (coverage.lead.company if coverage.lead else None)
        return data

    # Latest interaction per customer/lead determines the current unresolved
    # issue and overdue follow-up. A later interaction without pending issues
    # clears the previous pending flag without rewriting history.
    from services.permission_service import get_support_authorized_lead_ids

    if role == "ADMIN":
        lead_ids = None
    else:
        lead_ids = get_support_authorized_lead_ids(current_user, db) or []
    interaction_query = db.query(SupportInteraction)
    if lead_ids is not None:
        if not lead_ids:
            interaction_query = interaction_query.filter(SupportInteraction.id == -1)
        else:
            interaction_query = interaction_query.filter(
                SupportInteraction.lead_id.in_(lead_ids)
            )
    interactions = interaction_query.order_by(
        SupportInteraction.interaction_at.desc(), SupportInteraction.id.desc()
    ).all()
    latest_by_lead: Dict[int, SupportInteraction] = {}
    for row in interactions:
        key = row.lead_id or -(row.customer_id or 0)
        if key not in latest_by_lead:
            latest_by_lead[key] = row

    now = get_ist_now()
    pending_issue_rows = [
        row
        for row in latest_by_lead.values()
        if (row.pending_issues or "").strip()
    ]
    overdue_rows = [
        row
        for row in latest_by_lead.values()
        if row.follow_up_at is not None and row.follow_up_at < now
    ]
    upcoming_followup_rows = [
        row
        for row in interactions
        if row.follow_up_at is not None and row.follow_up_at >= now
    ]
    upcoming_followup_rows.sort(key=lambda row: row.follow_up_at)

    return {
        "employees": availability,
        "approved_leaves": [serialize_leave(leave) for leave in approved_leaves],
        "active_coverage": [coverage_row(row) for row in active_coverages],
        "temporary_coverage_count": len(active_coverages),
        "handover_history": [coverage_row(row) for row in handover_history],
        "pending_issues": [
            {
                "interaction_id": row.id,
                "lead_id": row.lead_id,
                "customer_id": row.customer_id,
                "customer_name": (
                    row.customer.contact_name if row.customer else None
                ) or (row.lead.name if row.lead else None),
                "pending_issues": row.pending_issues,
                "handling_employee_id": row.handling_employee_id,
                "handling_employee_name": (
                    row.handling_employee.name if row.handling_employee else None
                ),
                "interaction_at": (
                    row.interaction_at.isoformat() if row.interaction_at else None
                ),
            }
            for row in pending_issue_rows
        ],
        "pending_issue_count": len(pending_issue_rows),
        "overdue_follow_ups": [
            {
                "interaction_id": row.id,
                "lead_id": row.lead_id,
                "customer_id": row.customer_id,
                "customer_name": (
                    row.customer.contact_name if row.customer else None
                ) or (row.lead.name if row.lead else None),
                "follow_up_at": (
                    row.follow_up_at.isoformat() if row.follow_up_at else None
                ),
                "next_action": row.next_action,
                "handling_employee_name": (
                    row.handling_employee.name if row.handling_employee else None
                ),
            }
            for row in overdue_rows
        ],
        "overdue_follow_up_count": len(overdue_rows),
        "upcoming_follow_ups": [
            {
                "interaction_id": row.id,
                "lead_id": row.lead_id,
                "customer_id": row.customer_id,
                "customer_name": (
                    row.customer.contact_name if row.customer else None
                ) or (row.lead.name if row.lead else None),
                "follow_up_at": (
                    row.follow_up_at.isoformat() if row.follow_up_at else None
                ),
                "next_action": row.next_action,
                "handling_employee_name": (
                    row.handling_employee.name if row.handling_employee else None
                ),
            }
            for row in upcoming_followup_rows[:25]
        ],
    }
