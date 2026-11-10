"""Shared Support history / leave / coverage helpers.

All reads in this module are scoped by the calling router. The helpers never
reassign a customer by themselves; coverage rows are only created by an
explicit Support Manager request.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Session

from models.customer import Customer
from models.employee import Employee
from models.followup import Followup
from models.lead import Lead
from models.monitoring import EmployeePresence
from models.support import EmployeeLeave, SupportCoverageAssignment, SupportInteraction
from models.user import User
from models.workflow import SupportHandoff
from services.followup_visibility_service import apply_followup_department_filters
from services.hierarchy_service import DEPT_SUPPORT, normalize_role
from services.purchase_details_service import build_support_purchase_details
from utils.timezone import get_ist_now

SUPPORT_ROLES = {"SUPPORT_MANAGER", "SUPPORT_EXECUTIVE", "SUPPORT"}


def get_employee_for_user(user: Optional[User], db: Session) -> Optional[Employee]:
    if not user:
        return None
    return db.query(Employee).filter(Employee.user_id == user.id).first()


def is_support_actor(user: Optional[User], employee: Optional[Employee] = None) -> bool:
    """True for Support employees/managers, including legacy SUPPORT labels."""
    if not user and not employee:
        return False
    role = normalize_role(
        (user.role if user else None) or (employee.role if employee else None)
    )
    if role in {"SUPPORT_MANAGER", "SUPPORT_EXECUTIVE"}:
        return True
    department = (
        (user.department if user else None)
        or (employee.department if employee else None)
        or ""
    ).strip().upper()
    return department == "SUPPORT"


def is_support_manager_or_admin(user: Optional[User], employee: Optional[Employee] = None) -> bool:
    if not user:
        return False
    role = normalize_role((user.role or "").strip().upper())
    if role == "ADMIN":
        return True
    if role == "SUPPORT_MANAGER":
        return True
    return bool(
        employee
        and normalize_role(employee.role) == "SUPPORT_MANAGER"
        and is_support_actor(user, employee)
    )


def today_ist() -> date:
    return get_ist_now().date()


def active_coverage_query(db: Session, at_date: Optional[date] = None):
    """Coverage that is currently active (status + inclusive leave dates)."""
    effective_date = at_date or today_ist()
    return db.query(SupportCoverageAssignment).filter(
        SupportCoverageAssignment.status == "ACTIVE",
        SupportCoverageAssignment.start_date <= effective_date,
        SupportCoverageAssignment.end_date >= effective_date,
    )


def active_coverage_for_lead(
    db: Session,
    lead_id: int,
    at_date: Optional[date] = None,
) -> Optional[SupportCoverageAssignment]:
    return (
        active_coverage_query(db, at_date)
        .filter(SupportCoverageAssignment.lead_id == lead_id)
        .order_by(desc(SupportCoverageAssignment.id))
        .first()
    )


def active_coverage_for_backup(
    db: Session,
    employee_id: int,
    at_date: Optional[date] = None,
) -> List[SupportCoverageAssignment]:
    return (
        active_coverage_query(db, at_date)
        .filter(SupportCoverageAssignment.backup_employee_id == employee_id)
        .order_by(SupportCoverageAssignment.start_date.asc(), SupportCoverageAssignment.id.asc())
        .all()
    )


def active_covered_lead_ids(
    db: Session,
    employee_id: int,
    at_date: Optional[date] = None,
) -> List[int]:
    rows = (
        active_coverage_query(db, at_date)
        .filter(SupportCoverageAssignment.backup_employee_id == employee_id)
        .with_entities(SupportCoverageAssignment.lead_id)
        .all()
    )
    return sorted({row[0] for row in rows if row[0]})


def employee_on_approved_leave(
    db: Session,
    employee_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Optional[EmployeeLeave]:
    """Return an overlapping APPROVED leave, or None.

    With no dates, checks whether the employee is on approved leave today.
    """
    query = db.query(EmployeeLeave).filter(
        EmployeeLeave.employee_id == employee_id,
        EmployeeLeave.status == "APPROVED",
    )
    if start_date and end_date:
        query = query.filter(
            EmployeeLeave.start_date <= end_date,
            EmployeeLeave.end_date >= start_date,
        )
    else:
        current = today_ist()
        query = query.filter(
            EmployeeLeave.start_date <= current,
            EmployeeLeave.end_date >= current,
        )
    return query.order_by(EmployeeLeave.start_date.asc(), EmployeeLeave.id.asc()).first()


def get_employee_availability(db: Session, employee: Employee) -> Dict[str, Any]:
    leave = employee_on_approved_leave(db, employee.id)
    presence = (
        db.query(EmployeePresence)
        .filter(EmployeePresence.employee_id == employee.id)
        .first()
    )
    presence_status = (presence.status if presence else "OFFLINE") or "OFFLINE"
    last_seen = presence.last_seen if presence else None
    recently_seen = bool(
        last_seen and (datetime.utcnow() - last_seen) <= timedelta(minutes=5)
    )
    employee_active = (employee.status or "").strip().upper() == "ACTIVE"
    on_leave = leave is not None
    return {
        "employee_id": employee.id,
        "employee_name": employee.name,
        "role": employee.role,
        "department": employee.department,
        "employment_status": employee.status,
        "presence_status": presence_status,
        "last_seen": last_seen.isoformat() if last_seen else None,
        "online": bool(presence_status.upper() == "ONLINE" and recently_seen),
        "on_approved_leave": on_leave,
        "available": bool(employee_active and not on_leave),
        "leave": serialize_leave(leave) if leave else None,
    }


def permanent_owner_id(lead: Optional[Lead], handoff: Optional[SupportHandoff]) -> Optional[int]:
    if handoff and handoff.assigned_agent_id:
        return handoff.assigned_agent_id
    if lead and lead.assigned_to:
        return lead.assigned_to
    return None


def resolve_support_customer(
    db: Session,
    lead_id: Optional[int] = None,
    customer_id: Optional[int] = None,
) -> Tuple[Optional[Lead], Optional[Customer], Optional[SupportHandoff]]:
    """Resolve the Support customer without ever creating a duplicate record."""
    lead: Optional[Lead] = None
    customer: Optional[Customer] = None

    if lead_id is not None:
        lead = db.query(Lead).filter(Lead.id == int(lead_id)).first()
    if customer_id is not None:
        customer = db.query(Customer).filter(Customer.id == int(customer_id)).first()

    handoff = None
    if lead is not None:
        handoff = (
            db.query(SupportHandoff)
            .filter(SupportHandoff.lead_id == lead.id)
            .order_by(desc(SupportHandoff.id))
            .first()
        )
    if handoff is None and customer is not None:
        handoff = (
            db.query(SupportHandoff)
            .filter(SupportHandoff.customer_id == customer.id)
            .order_by(desc(SupportHandoff.id))
            .first()
        )
        if handoff and lead is None:
            lead = db.query(Lead).filter(Lead.id == handoff.lead_id).first()

    if customer is None and handoff is not None and handoff.customer_id:
        customer = db.query(Customer).filter(Customer.id == handoff.customer_id).first()
    if customer is None and lead is not None:
        if getattr(lead, "customer", None) is not None:
            customer = lead.customer
        else:
            customer = (
                db.query(Customer)
                .filter(Customer.converted_from_lead == lead.id)
                .first()
            )
    if customer is None and lead is not None and lead.phone:
        # Last-resort lookup for legacy handovers that stored only a phone.
        from utils.phone import find_existing_customer_by_phone

        customer = find_existing_customer_by_phone(db, lead.phone)

    if lead is None and customer is not None and customer.converted_from_lead:
        lead = db.query(Lead).filter(Lead.id == customer.converted_from_lead).first()

    if handoff is None and lead is not None:
        handoff = (
            db.query(SupportHandoff)
            .filter(SupportHandoff.lead_id == lead.id)
            .order_by(desc(SupportHandoff.id))
            .first()
        )

    # Explicit ids must refer to the same customer/handover.
    if lead_id is not None and lead is None:
        return None, customer, handoff
    if customer_id is not None and customer is None:
        return lead, None, handoff
    if handoff is not None:
        if customer is not None and handoff.customer_id and handoff.customer_id != customer.id:
            raise ValueError("customer_id does not match the Support handover.")
        if lead is not None and handoff.lead_id and handoff.lead_id != lead.id:
            raise ValueError("lead_id does not match the Support handover.")

    return lead, customer, handoff


def serialize_leave(leave: Optional[EmployeeLeave]) -> Optional[Dict[str, Any]]:
    if not leave:
        return None
    return {
        "id": leave.id,
        "employee_id": leave.employee_id,
        "employee_name": leave.employee.name if leave.employee else None,
        "leave_type": leave.leave_type,
        "start_date": leave.start_date.isoformat() if leave.start_date else None,
        "end_date": leave.end_date.isoformat() if leave.end_date else None,
        "status": leave.status,
        "reason": leave.reason,
        "manager_notes": leave.manager_notes,
        "approved_by_employee_id": leave.approved_by_employee_id,
        "approved_by_employee_name": leave.approved_by.name if leave.approved_by else None,
        "approved_at": leave.approved_at.isoformat() if leave.approved_at else None,
        "created_at": leave.created_at.isoformat() if leave.created_at else None,
    }


def serialize_coverage(coverage: Optional[SupportCoverageAssignment]) -> Optional[Dict[str, Any]]:
    return coverage.to_dict() if coverage else None


def get_interactions_for_customer(
    db: Session,
    customer_id: int,
    lead_id: Optional[int] = None,
    ascending: bool = True,
    limit: Optional[int] = None,
) -> List[SupportInteraction]:
    query = db.query(SupportInteraction).filter(
        SupportInteraction.customer_id == customer_id
    )
    if lead_id is not None:
        query = query.filter(
            or_(
                SupportInteraction.lead_id == lead_id,
                SupportInteraction.lead_id.is_(None),
            )
        )
    order = SupportInteraction.interaction_at.asc() if ascending else desc(
        SupportInteraction.interaction_at
    )
    query = query.order_by(order, SupportInteraction.id.asc() if ascending else SupportInteraction.id.desc())
    if limit:
        query = query.limit(limit)
    return query.all()


def _interaction_brief(interaction: SupportInteraction) -> Dict[str, Any]:
    return {
        "id": interaction.id,
        "interaction_type": interaction.interaction_type,
        "interaction_at": interaction.interaction_at.isoformat() if interaction.interaction_at else None,
        "discussion": interaction.discussion,
        "problem_reported": interaction.problem_reported,
        "troubleshooting": interaction.troubleshooting,
        "solution_provided": interaction.solution_provided,
        "pending_issues": interaction.pending_issues,
        "customer_commitments": interaction.customer_commitments,
        "next_action": interaction.next_action,
        "follow_up_at": interaction.follow_up_at.isoformat() if interaction.follow_up_at else None,
        "notes": interaction.notes,
        "handling_employee_id": interaction.handling_employee_id,
        "handling_employee_name": (
            interaction.handling_employee.name if interaction.handling_employee else None
        ),
        "original_employee_id": interaction.original_employee_id,
        "original_employee_name": (
            interaction.original_employee.name if interaction.original_employee else None
        ),
    }


def build_support_summary(interactions: Iterable[SupportInteraction]) -> Dict[str, Any]:
    """Deterministic summary built only from saved interaction records.

    There is no paid AI dependency in this project. This projection is the
    normal latest-interaction summary required when no AI provider exists.
    """
    rows = sorted(
        list(interactions),
        key=lambda row: (row.interaction_at or datetime.min, row.id or 0),
        reverse=True,
    )
    latest = rows[0] if rows else None
    unresolved = next((row for row in rows if (row.pending_issues or "").strip()), None)
    pending_followup = next(
        (row for row in rows if row.follow_up_at is not None),
        None,
    )
    if pending_followup and pending_followup.follow_up_at and pending_followup.follow_up_at < get_ist_now():
        overdue_rows = [row for row in rows if row.follow_up_at is not None]
        if overdue_rows:
            pending_followup = sorted(
                overdue_rows, key=lambda row: row.follow_up_at, reverse=False
            )[0]
    last_problem = next(
        (row for row in rows if (row.problem_reported or "").strip()), None
    )
    next_action = next((row for row in rows if (row.next_action or "").strip()), None)
    solutions = []
    for row in rows:
        if (row.solution_provided or "").strip():
            solutions.append(
                {
                    "interaction_id": row.id,
                    "interaction_at": row.interaction_at.isoformat() if row.interaction_at else None,
                    "solution": row.solution_provided,
                }
            )
        if len(solutions) >= 5:
            break
    commitments = []
    for row in rows:
        if (row.customer_commitments or "").strip():
            commitments.append(
                {
                    "interaction_id": row.id,
                    "interaction_at": row.interaction_at.isoformat() if row.interaction_at else None,
                    "commitment": row.customer_commitments,
                }
            )
        if len(commitments) >= 5:
            break

    latest_summary = None
    if latest:
        pieces = []
        if latest.discussion:
            pieces.append(latest.discussion.strip())
        if latest.problem_reported:
            pieces.append(f"Problem: {latest.problem_reported.strip()}")
        if latest.solution_provided:
            pieces.append(f"Solution: {latest.solution_provided.strip()}")
        latest_summary = " | ".join(pieces) or latest.notes

    return {
        "latest_interaction": _interaction_brief(latest) if latest else None,
        "last_three_interactions": [_interaction_brief(row) for row in rows[:3]],
        "last_conversation_summary": latest_summary,
        "last_reported_problem": (
            last_problem.problem_reported if last_problem else None
        ),
        "current_unresolved_issue": (
            unresolved.pending_issues if unresolved else None
        ),
        "unresolved_since": (
            unresolved.interaction_at.isoformat()
            if unresolved and unresolved.interaction_at
            else None
        ),
        "solutions_attempted": solutions,
        "customer_commitments": commitments,
        "next_recommended_action": (
            next_action.next_action if next_action else None
        ),
        "pending_follow_up": (
            {
                "interaction_id": pending_followup.id,
                "follow_up_at": pending_followup.follow_up_at.isoformat(),
                "next_action": pending_followup.next_action,
                "is_overdue": bool(pending_followup.follow_up_at < get_ist_now()),
            }
            if pending_followup and pending_followup.follow_up_at
            else None
        ),
        "interaction_count": len(rows),
        "generated_from": "SUPPORT_INTERACTIONS",
        "ai_generated": False,
    }


def serialize_customer_profile(
    db: Session,
    lead: Optional[Lead],
    customer: Optional[Customer],
    handoff: Optional[SupportHandoff],
    include_purchase: bool = True,
) -> Dict[str, Any]:
    permanent_id = permanent_owner_id(lead, handoff)
    permanent = (
        db.query(Employee).filter(Employee.id == permanent_id).first()
        if permanent_id
        else None
    )
    coverage = active_coverage_for_lead(db, lead.id) if lead else None
    handling = coverage.backup_employee if coverage else permanent

    name = (
        (customer.contact_name if customer else None)
        or (handoff.customer_name if handoff else None)
        or (lead.name if lead else None)
        or "Unknown Customer"
    )
    company = (
        (customer.company_name if customer else None)
        or (handoff.company_name if handoff else None)
        or (lead.company if lead else None)
    )
    return {
        "lead_id": lead.id if lead else (handoff.lead_id if handoff else None),
        "customer_id": (
            customer.id if customer else (handoff.customer_id if handoff else None)
        ),
        "support_handoff_id": handoff.id if handoff else None,
        "customer_name": name,
        "contact_name": name,
        "company_name": company,
        "company": company,
        "phone": (
            (customer.phone if customer else None)
            or (handoff.phone if handoff else None)
            or (lead.phone if lead else None)
        ),
        "email": (
            (customer.email if customer else None)
            or (handoff.email if handoff else None)
            or (lead.email if lead else None)
        ),
        "location": (
            (customer.location if customer else None)
            or (lead.location if lead else None)
            or (
                f"{lead.city or ''}, {lead.state or ''}".strip(", ")
                if lead and (lead.city or lead.state)
                else None
            )
        ),
        "product_service": handoff.product_service if handoff else None,
        "customer_requirements": (
            (handoff.customer_requirements if handoff else None)
            or (handoff.support_notes if handoff else None)
            or (lead.requirement_notes if lead else None)
        ),
        "support_status": handoff.support_status if handoff else None,
        "original_support_employee_id": permanent_id,
        "original_support_employee_name": permanent.name if permanent else None,
        "current_handling_employee_id": handling.id if handling else None,
        "current_handling_employee_name": handling.name if handling else None,
        "backup_employee_id": coverage.backup_employee_id if coverage else None,
        "backup_employee_name": (
            coverage.backup_employee.name if coverage and coverage.backup_employee else None
        ),
        "coverage": serialize_coverage(coverage),
        "purchase_details": (
            build_support_purchase_details(db, handoff) if handoff and include_purchase else None
        ),
    }


def build_customer_history(
    db: Session,
    lead: Lead,
    customer: Customer,
    handoff: Optional[SupportHandoff],
    include_purchase: bool = True,
) -> Dict[str, Any]:
    interactions = get_interactions_for_customer(
        db, customer.id, lead_id=lead.id, ascending=True
    )
    summary = build_support_summary(interactions)
    profile = serialize_customer_profile(
        db, lead, customer, handoff, include_purchase=include_purchase
    )
    now = get_ist_now()
    upcoming = [
        row
        for row in interactions
        if row.follow_up_at is not None and row.follow_up_at >= now
    ]
    overdue = [
        row
        for row in interactions
        if row.follow_up_at is not None and row.follow_up_at < now
    ]
    coverage_history = (
        db.query(SupportCoverageAssignment)
        .filter(SupportCoverageAssignment.lead_id == lead.id)
        .order_by(desc(SupportCoverageAssignment.id))
        .all()
    )
    # Only Support-owned follow-ups belong in the Support customer history.
    # Sales follow-up notes stay private to Sales even after a handover.
    open_followups_query = db.query(Followup).filter(
        Followup.lead_id == lead.id,
        Followup.status == "Pending",
    )
    open_followups_query = apply_followup_department_filters(
        open_followups_query, db, [DEPT_SUPPORT]
    )
    open_followups = open_followups_query.order_by(
        Followup.followup_date.asc(), Followup.id.asc()
    ).all()
    return {
        **profile,
        "interactions": [row.to_dict() for row in interactions],
        "summary": summary,
        "upcoming_follow_ups": [row.to_dict() for row in upcoming],
        "overdue_follow_ups": [row.to_dict() for row in overdue],
        "scheduled_followups": [
            {
                "id": row.id,
                "followup_date": row.followup_date.isoformat() if row.followup_date else None,
                "followup_time": row.followup_time,
                "notes": row.notes,
                "priority": row.priority,
                "status": row.status,
                "assigned_to": row.assigned_to,
            }
            for row in open_followups
        ],
        "coverage_history": [row.to_dict() for row in coverage_history],
        "unresolved_problems": (
            [summary["current_unresolved_issue"]]
            if summary.get("current_unresolved_issue")
            else []
        ),
        "pending_actions": (
            [summary["next_recommended_action"]]
            if summary.get("next_recommended_action")
            else []
        ),
    }
