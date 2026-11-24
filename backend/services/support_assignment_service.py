"""Transactional Support client assignment / reassignment.

The Support owner of a converted customer is authoritative in
``Lead.support_employee_id`` and mirrored on the latest ``SupportHandoff`` and
the active ``SupportClientAssignment`` row. Reassignments happen in a single
database transaction:

* the lead and handoff rows are locked,
* the previous active assignment is closed,
* the new active assignment is inserted,
* ``Lead.support_employee_id`` and the handoff owner are updated,
* an auditable ``LeadAssignment`` / activity / audit row is written,
* the new employee, the previous employee and the Support Manager are
  notified.

``Lead.assigned_to`` is the Sales owner and is only touched when it still
mirrors the Support owner (legacy rows), so a Support reassignment can never
hijack the Sales pipeline.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc
from sqlalchemy.orm import Session

from models.activity import LeadActivity
from models.audit_log import AuditLog
from models.employee import Employee
from models.lead import Lead, LeadAssignment
from models.notification import Notification
from models.support import SupportClientAssignment
from models.user import User
from models.workflow import SupportHandoff
from services.hierarchy_service import (
    ROLE_SUPPORT_EXECUTIVE,
    ROLE_SUPPORT_MANAGER,
    normalize_role,
)
from utils.lead_status import is_trial_status
from utils.timezone import get_ist_now


SUPPORT_OWNER_ROLES = {ROLE_SUPPORT_EXECUTIVE, ROLE_SUPPORT_MANAGER, "SUPPORT"}


def _employee_name(db: Session, employee_id: Optional[int]) -> Optional[str]:
    if not employee_id:
        return None
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    return employee.name if employee else None


def _employee_user_id(db: Session, employee_id: Optional[int]) -> Optional[int]:
    if not employee_id:
        return None
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    return employee.user_id if employee else None


def resolve_employee_manager(
    db: Session, employee: Optional[Employee]
) -> Optional[Employee]:
    """Resolve the reporting Support Manager for an employee."""
    if not employee:
        return None
    if employee.manager_id:
        manager = (
            db.query(Employee)
            .filter(Employee.id == employee.manager_id)
            .first()
        )
        if manager:
            return manager
    return None


def resolve_trial_manager(
    db: Session, lead: Optional[Lead]
) -> Optional[Employee]:
    """Resolve the Support Manager responsible for a trial customer.

    ``leads.trial_support_employee_id`` is written by the Set Trial Period
    modal and normally points at a Support Manager. A legacy row may still
    point at a Support Executive; in that case the reporting manager is used
    so trial attribution is never lost.
    """
    if not lead:
        return None
    trial_support_id = getattr(lead, "trial_support_employee_id", None)
    if not trial_support_id:
        return None
    employee = db.query(Employee).filter(Employee.id == trial_support_id).first()
    if not employee:
        return None
    if normalize_role(employee.role) == ROLE_SUPPORT_MANAGER:
        return employee
    return resolve_employee_manager(db, employee)


def get_latest_handoff(db: Session, lead_id: int) -> Optional[SupportHandoff]:
    return (
        db.query(SupportHandoff)
        .filter(SupportHandoff.lead_id == lead_id)
        .order_by(desc(SupportHandoff.id))
        .first()
    )


def get_active_assignment(
    db: Session, lead_id: int
) -> Optional[SupportClientAssignment]:
    return (
        db.query(SupportClientAssignment)
        .filter(
            SupportClientAssignment.lead_id == lead_id,
            SupportClientAssignment.status == "ACTIVE",
        )
        .order_by(desc(SupportClientAssignment.id))
        .first()
    )


def resolve_current_support_owner(
    db: Session,
    lead: Lead,
    handoff: Optional[SupportHandoff] = None,
) -> Tuple[Optional[int], str]:
    """Return ``(employee_id, source)`` for the current Support owner.

    The active assignment row wins, then the dedicated lead column, then the
    latest handoff. ``Lead.assigned_to`` is used only as a legacy fallback and
    only when that employee is actually a Support employee.
    """
    active = get_active_assignment(db, lead.id)
    if active:
        return active.employee_id, "ACTIVE_ASSIGNMENT"
    if getattr(lead, "support_employee_id", None):
        return lead.support_employee_id, "LEAD_SUPPORT_EMPLOYEE"
    if not handoff:
        handoff = get_latest_handoff(db, lead.id)
    if handoff and handoff.assigned_agent_id:
        return handoff.assigned_agent_id, "SUPPORT_HANDOFF"
    if lead.assigned_to:
        legacy = db.query(Employee).filter(Employee.id == lead.assigned_to).first()
        if legacy and normalize_role(legacy.role) in SUPPORT_OWNER_ROLES:
            return legacy.id, "LEGACY_ASSIGNED_TO"
    return None, "UNASSIGNED"


def _serialize_row(
    db: Session, row: SupportClientAssignment
) -> Dict[str, Any]:
    return {
        "id": row.id,
        "lead_id": row.lead_id,
        "customer_id": row.customer_id,
        "support_handoff_id": row.support_handoff_id,
        "employee_id": row.employee_id,
        "employee_name": (
            row.employee.name if row.employee else _employee_name(db, row.employee_id)
        ),
        "previous_employee_id": row.previous_employee_id,
        "previous_employee_name": (
            row.previous_employee.name
            if row.previous_employee
            else _employee_name(db, row.previous_employee_id)
        ),
        "assigned_by_employee_id": row.assigned_by_employee_id,
        "assigned_by_employee_name": (
            row.assigned_by_employee.name
            if row.assigned_by_employee
            else _employee_name(db, row.assigned_by_employee_id)
        ),
        "assigned_by_user_id": row.assigned_by_user_id,
        "assigned_by_username": (
            row.assigned_by_user.username if row.assigned_by_user else None
        ),
        "reason": row.reason,
        "source": row.source,
        "status": row.status,
        "assigned_at": row.assigned_at.isoformat() if row.assigned_at else None,
        "ended_at": row.ended_at.isoformat() if row.ended_at else None,
        "end_reason": row.end_reason,
    }


def get_assignment_state(
    db: Session,
    lead: Lead,
    handoff: Optional[SupportHandoff] = None,
) -> Dict[str, Any]:
    """Read-only current assignment plus full reassignment history."""
    if not handoff:
        handoff = get_latest_handoff(db, lead.id)

    owner_id, owner_source = resolve_current_support_owner(db, lead, handoff)
    owner = (
        db.query(Employee).filter(Employee.id == owner_id).first()
        if owner_id
        else None
    )

    rows = (
        db.query(SupportClientAssignment)
        .filter(SupportClientAssignment.lead_id == lead.id)
        .order_by(SupportClientAssignment.assigned_at.asc(), SupportClientAssignment.id.asc())
        .all()
    )
    history = [_serialize_row(db, row) for row in rows]

    active = next((row for row in rows if row.status == "ACTIVE"), None)
    current = _serialize_row(db, active) if active else None

    # Legacy customers have ownership on the handoff only. Surface it as a
    # synthetic current assignment so the UI always shows who owns the client
    # and the history panel is never blank.
    if current is None and owner_id:
        current = {
            "id": None,
            "lead_id": lead.id,
            "customer_id": handoff.customer_id if handoff else None,
            "support_handoff_id": handoff.id if handoff else None,
            "employee_id": owner_id,
            "employee_name": owner.name if owner else None,
            "previous_employee_id": None,
            "previous_employee_name": None,
            "assigned_by_employee_id": (
                handoff.support_manager_id if handoff else None
            ),
            "assigned_by_employee_name": (
                handoff.support_manager_name if handoff else None
            ),
            "assigned_by_user_id": None,
            "assigned_by_username": None,
            "reason": None,
            "source": owner_source,
            "status": "ACTIVE",
            "assigned_at": (
                handoff.updated_at.isoformat()
                if handoff and handoff.updated_at
                else (lead.assigned_at.isoformat() if lead.assigned_at else None)
            ),
            "ended_at": None,
            "end_reason": None,
            "synthetic": True,
        }

    support_manager_id = handoff.support_manager_id if handoff else None
    support_manager_name = handoff.support_manager_name if handoff else None
    trial_manager = None if handoff else resolve_trial_manager(db, lead)
    if trial_manager:
        # During a trial the manager attribution comes from the Set Trial
        # Period selection, never from the assigned Executive's reporting line.
        support_manager_id = trial_manager.id
        support_manager_name = trial_manager.name
    elif not support_manager_name and owner:
        if normalize_role(owner.role) == ROLE_SUPPORT_MANAGER:
            # The Support owner is itself a Manager: keep the projection on
            # that manager instead of resolving their reporting Admin.
            support_manager_id = owner.id
            support_manager_name = owner.name
        else:
            manager = resolve_employee_manager(db, owner)
            if manager:
                support_manager_id = manager.id
                support_manager_name = manager.name

    is_trial = is_trial_status(lead.status)

    return {
        "lead_id": lead.id,
        "customer_id": (
            handoff.customer_id if handoff else getattr(lead, "customer_id", None)
        ),
        "support_handoff_id": handoff.id if handoff else None,
        "sales_status": lead.status,
        "support_employee_id": owner_id,
        "support_employee_name": owner.name if owner else None,
        "support_manager_id": support_manager_id,
        "support_manager_name": support_manager_name,
        "current": current,
        "history": history,
        "history_count": len(history),
        "reason_required": bool(owner_id),
        "is_trial": is_trial,
        "assignment_scope": "TRIAL" if is_trial and not handoff else "SUPPORT",
    }


def _assignment_message(
    *,
    client_name: str,
    company_name: Optional[str],
    previous_name: Optional[str],
    new_name: str,
    reassigned_by: str,
    when: datetime,
    is_reassignment: bool = True,
) -> str:
    action = "Reassigned" if is_reassignment else "Assigned"
    date_label = "Reassignment" if is_reassignment else "Assignment"
    return (
        f"Client Name: {client_name}\n"
        f"Company Name: {company_name or 'N/A'}\n"
        f"Previous Employee: {previous_name or 'Unassigned'}\n"
        f"Newly Assigned Employee: {new_name}\n"
        f"{action} By: {reassigned_by}\n"
        f"{date_label} Date & Time: {when.strftime('%d %b %Y, %I:%M %p')}"
    )


def _add_assignment_notifications(
    db: Session,
    *,
    lead: Lead,
    new_employee: Employee,
    previous_employee_id: Optional[int],
    manager_employee_id: Optional[int],
    reassigned_by: str,
    when: datetime,
    client_name: str,
    company_name: Optional[str],
    notification_type: str,
    title: str,
    is_reassignment: bool,
) -> List[int]:
    """Queue assignment notifications inside the caller's transaction."""
    if not manager_employee_id:
        manager = resolve_employee_manager(db, new_employee)
        manager_employee_id = manager.id if manager else None

    targets: List[Tuple[str, Optional[int]]] = [
        ("new", new_employee.user_id),
        ("previous", _employee_user_id(db, previous_employee_id)),
        ("manager", _employee_user_id(db, manager_employee_id)),
    ]

    seen = set()
    created: List[int] = []
    message = _assignment_message(
        client_name=client_name,
        company_name=company_name,
        previous_name=_employee_name(db, previous_employee_id),
        new_name=new_employee.name,
        reassigned_by=reassigned_by,
        when=when,
        is_reassignment=is_reassignment,
    )

    for _recipient_kind, user_id in targets:
        if not user_id or user_id in seen:
            continue
        seen.add(user_id)
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            link_url=f"/support/assigned?openLeadId={lead.id}",
            is_read=False,
            created_at=datetime.utcnow(),
        )
        db.add(notification)
        db.flush()
        created.append(notification.id)

    return created


def reassign_support_owner(
    db: Session,
    *,
    lead: Lead,
    handoff: SupportHandoff,
    new_employee: Employee,
    actor_user: User,
    actor_employee: Optional[Employee],
    reason: Optional[str],
    source: str = "MANUAL_REASSIGN",
) -> Dict[str, Any]:
    """Assign or reassign the Support owner of a customer atomically.

    The caller validates role/target/team scope. This function locks the
    affected rows, prevents duplicate active assignments, writes the history
    and notifications, then commits once.
    """
    try:
        locked_lead = (
            db.query(Lead)
            .filter(Lead.id == lead.id)
            .with_for_update()
            .first()
        )
        locked_handoff = (
            db.query(SupportHandoff)
            .filter(SupportHandoff.id == handoff.id)
            .with_for_update()
            .first()
        )
        if not locked_lead or not locked_handoff:
            raise ValueError("Lead or Support handoff no longer exists.")

        active_rows = (
            db.query(SupportClientAssignment)
            .filter(
                SupportClientAssignment.lead_id == locked_lead.id,
                SupportClientAssignment.status == "ACTIVE",
            )
            .with_for_update()
            .all()
        )

        previous_employee_id, _ = resolve_current_support_owner(
            db, locked_lead, locked_handoff
        )
        previous_name = _employee_name(db, previous_employee_id)
        now = get_ist_now()

        # Idempotent re-submit: never create a second active row or a
        # duplicate history entry.
        if previous_employee_id == new_employee.id:
            if not locked_lead.support_employee_id:
                locked_lead.support_employee_id = new_employee.id
            if locked_handoff.assigned_agent_id != new_employee.id:
                locked_handoff.assigned_agent_id = new_employee.id
                locked_handoff.assigned_agent_name = new_employee.name
            if normalize_role(new_employee.role) == ROLE_SUPPORT_MANAGER:
                # An idempotent re-submit must still leave the manager
                # projection on the assigned manager, including legacy rows
                # that previously resolved their reporting Admin.
                locked_handoff.support_manager_id = new_employee.id
                locked_handoff.support_manager_name = new_employee.name
            if not active_rows:
                active_row = SupportClientAssignment(
                    lead_id=locked_lead.id,
                    customer_id=locked_handoff.customer_id,
                    support_handoff_id=locked_handoff.id,
                    employee_id=new_employee.id,
                    previous_employee_id=None,
                    assigned_by_employee_id=(
                        actor_employee.id if actor_employee else None
                    ),
                    assigned_by_user_id=actor_user.id if actor_user else None,
                    source="SYNC",
                    reason=reason,
                    status="ACTIVE",
                    assigned_at=now,
                )
                db.add(active_row)
                db.commit()
                db.refresh(active_row)
                active = active_row
            else:
                active = active_rows[0]
                db.commit()
            return {
                "success": True,
                "already_assigned": True,
                "reassigned": False,
                "lead_id": locked_lead.id,
                "support_handoff_id": locked_handoff.id,
                "assignment_id": active.id,
                "assigned_agent_id": new_employee.id,
                "assigned_agent_name": new_employee.name,
                "previous_agent_id": previous_employee_id,
                "previous_agent_name": previous_name,
                "support_assigned_at": (
                    active.assigned_at.isoformat()
                    if active.assigned_at
                    else now.isoformat()
                ),
                "reassigned_at": None,
                "reassigned_by_id": (
                    actor_employee.id if actor_employee else None
                ),
                "reassigned_by_name": (
                    actor_employee.name
                    if actor_employee
                    else (actor_user.username if actor_user else None)
                ),
                "reassigned_by_username": (
                    actor_user.username if actor_user else None
                ),
                "reason": active.reason,
                "support_manager_id": locked_handoff.support_manager_id,
                "support_manager_name": locked_handoff.support_manager_name,
                "sales_owner_id": locked_lead.assigned_to,
            }

        # Close every stale active row defensively; there must only be one
        # active assignment per lead after this transaction.
        for row in active_rows:
            row.status = "ENDED"
            row.ended_at = now
            row.end_reason = "REASSIGNED"

        locked_lead.support_employee_id = new_employee.id

        # ``Lead.assigned_to`` belongs to Sales. Only mirror it when it points
        # at the previous Support owner or at a Support employee from the
        # legacy direct-assignment flow.
        current_assignee = (
            db.query(Employee)
            .filter(Employee.id == locked_lead.assigned_to)
            .first()
            if locked_lead.assigned_to
            else None
        )
        should_mirror = bool(
            locked_lead.assigned_to
            and (
                locked_lead.assigned_to == previous_employee_id
                or (
                    current_assignee
                    and normalize_role(current_assignee.role) in SUPPORT_OWNER_ROLES
                )
            )
        )
        if should_mirror:
            locked_lead.assigned_to = new_employee.id
            if actor_employee:
                locked_lead.assigned_by = actor_employee.id
            locked_lead.assigned_at = now

        locked_handoff.assigned_agent_id = new_employee.id
        locked_handoff.assigned_agent_name = new_employee.name

        # The Support Manager follows the customer's team. Admins reassigning
        # across teams must move manager ownership as well, otherwise the old
        # manager would still see the client and never receive the notice.
        if normalize_role(new_employee.role) == ROLE_SUPPORT_MANAGER:
            # The assigned owner is itself the Support Manager, so it owns the
            # manager projection. Never resolve their reporting Admin.
            locked_handoff.support_manager_id = new_employee.id
            locked_handoff.support_manager_name = new_employee.name
        else:
            new_manager = resolve_employee_manager(db, new_employee)
            if new_manager:
                locked_handoff.support_manager_id = new_manager.id
                locked_handoff.support_manager_name = new_manager.name
            elif not locked_handoff.support_manager_id and actor_employee:
                if normalize_role(actor_employee.role) == ROLE_SUPPORT_MANAGER:
                    locked_handoff.support_manager_id = actor_employee.id
                    locked_handoff.support_manager_name = actor_employee.name

        if reason:
            existing_notes = (locked_handoff.support_notes or "").strip()
            note_line = f"Reassignment: {reason}"
            if note_line not in existing_notes:
                locked_handoff.support_notes = (
                    f"{existing_notes}\n{note_line}".strip()
                    if existing_notes
                    else note_line
                )

        assignment_row = SupportClientAssignment(
            lead_id=locked_lead.id,
            customer_id=locked_handoff.customer_id,
            support_handoff_id=locked_handoff.id,
            employee_id=new_employee.id,
            previous_employee_id=previous_employee_id,
            assigned_by_employee_id=actor_employee.id if actor_employee else None,
            assigned_by_user_id=actor_user.id if actor_user else None,
            source=source,
            reason=reason,
            status="ACTIVE",
            assigned_at=now,
        )
        db.add(assignment_row)

        actor_label = (
            actor_employee.name
            if actor_employee
            else (actor_user.username if actor_user else "System")
        )
        audit_note = (
            f"Support client reassigned from {previous_name or 'Unassigned'} "
            f"to {new_employee.name} by {actor_label}."
            + (f" Reason: {reason}" if reason else "")
        )

        # Keep the existing auditable Sales/Support assignment feed intact.
        db.add(
            LeadAssignment(
                lead_id=locked_lead.id,
                assigned_to=new_employee.id,
                assigned_by=actor_employee.id if actor_employee else None,
                assigned_at=now,
                assignment_method="MANUAL_SUPPORT",
                notes=audit_note,
            )
        )
        db.add(
            LeadActivity(
                lead_id=locked_lead.id,
                customer_id=locked_handoff.customer_id,
                performed_by=actor_employee.id if actor_employee else None,
                activity_type="SUPPORT_REASSIGNED",
                department="SUPPORT",
                description=audit_note,
                created_at=now,
            )
        )
        db.add(
            AuditLog(
                user_id=actor_user.id if actor_user else None,
                username=actor_user.username if actor_user else "system",
                action="SUPPORT_REASSIGN",
                entity_type="LEAD",
                entity_id=str(locked_lead.id),
                details=audit_note,
                created_at=now,
            )
        )

        client_name = (
            locked_handoff.customer_name
            or locked_lead.name
            or f"Lead #{locked_lead.id}"
        )
        company_name = locked_handoff.company_name or locked_lead.company
        _add_assignment_notifications(
            db,
            lead=locked_lead,
            new_employee=new_employee,
            previous_employee_id=previous_employee_id,
            manager_employee_id=locked_handoff.support_manager_id,
            reassigned_by=actor_label,
            when=now,
            client_name=client_name,
            company_name=company_name,
            notification_type="SUPPORT_REASSIGNMENT",
            title=f"Support Client Reassigned: {client_name}",
            is_reassignment=True,
        )

        db.commit()
        db.refresh(assignment_row)

        return {
            "success": True,
            "already_assigned": False,
            "reassigned": True,
            "lead_id": locked_lead.id,
            "support_handoff_id": locked_handoff.id,
            "assignment_id": assignment_row.id,
            "assigned_agent_id": new_employee.id,
            "assigned_agent_name": new_employee.name,
            "previous_agent_id": previous_employee_id,
            "previous_agent_name": previous_name,
            "support_assigned_at": now.isoformat(),
            "reassigned_at": now.isoformat(),
            "reassigned_by_id": actor_employee.id if actor_employee else None,
            "reassigned_by_name": actor_label,
            "reassigned_by_username": (
                actor_user.username if actor_user else None
            ),
            "reason": reason,
            "support_manager_id": locked_handoff.support_manager_id,
            "support_manager_name": locked_handoff.support_manager_name,
            "sales_owner_id": locked_lead.assigned_to,
        }
    except Exception:
        db.rollback()
        raise


def resolve_trial_owner_id(db: Session, lead: Lead) -> Optional[int]:
    """Return the Support Executive currently assigned to a trial customer.

    The Trial Support Manager stored in ``trial_support_employee_id`` is a
    manager attribution, not a Support Executive assignment, so it is
    deliberately excluded here. ``Lead.assigned_to`` also belongs to Sales and
    is never treated as a trial Executive owner.
    """
    active = get_active_assignment(db, lead.id)
    if active:
        return active.employee_id
    return getattr(lead, "support_employee_id", None)


def assign_trial_support_owner(
    db: Session,
    *,
    lead: Lead,
    new_employee: Employee,
    actor_user: User,
    actor_employee: Optional[Employee],
    reason: Optional[str],
) -> Dict[str, Any]:
    """Assign or reassign a Support Executive while the deal is still TRIAL.

    The trial Support Manager attribution (``trial_support_employee_id``) and
    the Sales owner (``Lead.assigned_to``) are never changed. The Executive is
    stored on ``Lead.support_employee_id`` and in an active
    ``SupportClientAssignment`` row whose handoff/customer columns stay null
    until the deal is converted. Trial reminders keep resolving the Manager
    from ``trial_support_employee_id``.
    """
    try:
        locked_lead = (
            db.query(Lead)
            .filter(Lead.id == lead.id)
            .with_for_update()
            .first()
        )
        if not locked_lead:
            raise ValueError("Lead no longer exists.")
        if get_latest_handoff(db, locked_lead.id) is not None:
            raise ValueError(
                "A Support handoff already exists for this lead. Use the "
                "regular Support assignment workflow instead."
            )

        active_rows = (
            db.query(SupportClientAssignment)
            .filter(
                SupportClientAssignment.lead_id == locked_lead.id,
                SupportClientAssignment.status == "ACTIVE",
            )
            .order_by(desc(SupportClientAssignment.id))
            .with_for_update()
            .all()
        )

        previous_employee_id = (
            active_rows[0].employee_id
            if active_rows
            else getattr(locked_lead, "support_employee_id", None)
        )
        previous_name = _employee_name(db, previous_employee_id)
        manager = resolve_trial_manager(db, locked_lead)
        manager_employee_id = manager.id if manager else None
        manager_name = manager.name if manager else None
        now = get_ist_now()
        actor_label = (
            actor_employee.name
            if actor_employee
            else (actor_user.username if actor_user else "System")
        )

        # Idempotent re-submit: never create a second active row or duplicate
        # the audit feed.
        if previous_employee_id == new_employee.id:
            if not locked_lead.support_employee_id:
                locked_lead.support_employee_id = new_employee.id
            if not active_rows:
                active_row = SupportClientAssignment(
                    lead_id=locked_lead.id,
                    customer_id=None,
                    support_handoff_id=None,
                    employee_id=new_employee.id,
                    previous_employee_id=None,
                    assigned_by_employee_id=(
                        actor_employee.id if actor_employee else None
                    ),
                    assigned_by_user_id=actor_user.id if actor_user else None,
                    source="TRIAL_SYNC",
                    reason=reason,
                    status="ACTIVE",
                    assigned_at=now,
                )
                db.add(active_row)
                db.commit()
                db.refresh(active_row)
                active = active_row
            else:
                active = active_rows[0]
                db.commit()
            return {
                "success": True,
                "already_assigned": True,
                "reassigned": False,
                "lead_id": locked_lead.id,
                "support_handoff_id": None,
                "assignment_id": active.id,
                "assigned_agent_id": new_employee.id,
                "assigned_agent_name": new_employee.name,
                "previous_agent_id": previous_employee_id,
                "previous_agent_name": previous_name,
                "support_assigned_at": (
                    active.assigned_at.isoformat()
                    if active.assigned_at
                    else now.isoformat()
                ),
                "reassigned_at": None,
                "reassigned_by_id": (
                    actor_employee.id if actor_employee else None
                ),
                "reassigned_by_name": actor_label,
                "reassigned_by_username": (
                    actor_user.username if actor_user else None
                ),
                "reason": active.reason,
                "support_manager_id": manager_employee_id,
                "support_manager_name": manager_name,
                "sales_owner_id": locked_lead.assigned_to,
                "assignment_scope": "TRIAL",
            }

        for row in active_rows:
            row.status = "ENDED"
            row.ended_at = now
            row.end_reason = "REASSIGNED"

        is_reassignment = previous_employee_id is not None
        locked_lead.support_employee_id = new_employee.id

        assignment_row = SupportClientAssignment(
            lead_id=locked_lead.id,
            customer_id=None,
            support_handoff_id=None,
            employee_id=new_employee.id,
            previous_employee_id=previous_employee_id,
            assigned_by_employee_id=actor_employee.id if actor_employee else None,
            assigned_by_user_id=actor_user.id if actor_user else None,
            source="TRIAL_REASSIGN" if is_reassignment else "TRIAL_ASSIGN",
            reason=reason,
            status="ACTIVE",
            assigned_at=now,
        )
        db.add(assignment_row)

        audit_note = (
            f"Trial Support Executive assigned from {previous_name or 'Unassigned'} "
            f"to {new_employee.name} by {actor_label}."
            + (f" Reason: {reason}" if reason else "")
        )

        db.add(
            LeadAssignment(
                lead_id=locked_lead.id,
                assigned_to=new_employee.id,
                assigned_by=actor_employee.id if actor_employee else None,
                assigned_at=now,
                assignment_method="TRIAL_SUPPORT_EXECUTIVE",
                notes=audit_note,
            )
        )
        db.add(
            LeadActivity(
                lead_id=locked_lead.id,
                performed_by=actor_employee.id if actor_employee else None,
                activity_type="TRIAL_SUPPORT_EXECUTIVE_ASSIGNED",
                department="SUPPORT",
                description=audit_note,
                created_at=now,
            )
        )
        db.add(
            AuditLog(
                user_id=actor_user.id if actor_user else None,
                username=actor_user.username if actor_user else "system",
                action="TRIAL_SUPPORT_ASSIGN",
                entity_type="LEAD",
                entity_id=str(locked_lead.id),
                details=audit_note,
                created_at=now,
            )
        )

        client_name = locked_lead.name or f"Lead #{locked_lead.id}"
        company_name = locked_lead.company
        _add_assignment_notifications(
            db,
            lead=locked_lead,
            new_employee=new_employee,
            previous_employee_id=previous_employee_id,
            manager_employee_id=manager_employee_id,
            reassigned_by=actor_label,
            when=now,
            client_name=client_name,
            company_name=company_name,
            notification_type=(
                "SUPPORT_REASSIGNMENT" if is_reassignment else "SUPPORT_ASSIGNMENT"
            ),
            title=(
                f"Trial Client Reassigned: {client_name}"
                if is_reassignment
                else f"Trial Client Assigned: {client_name}"
            ),
            is_reassignment=is_reassignment,
        )

        db.commit()
        db.refresh(assignment_row)

        return {
            "success": True,
            "already_assigned": False,
            "reassigned": is_reassignment,
            "lead_id": locked_lead.id,
            "support_handoff_id": None,
            "assignment_id": assignment_row.id,
            "assigned_agent_id": new_employee.id,
            "assigned_agent_name": new_employee.name,
            "previous_agent_id": previous_employee_id,
            "previous_agent_name": previous_name,
            "support_assigned_at": now.isoformat(),
            "reassigned_at": now.isoformat() if is_reassignment else None,
            "reassigned_by_id": actor_employee.id if actor_employee else None,
            "reassigned_by_name": actor_label,
            "reassigned_by_username": (
                actor_user.username if actor_user else None
            ),
            "reason": reason,
            "support_manager_id": manager_employee_id,
            "support_manager_name": manager_name,
            "sales_owner_id": locked_lead.assigned_to,
            "assignment_scope": "TRIAL",
        }
    except Exception:
        db.rollback()
        raise
