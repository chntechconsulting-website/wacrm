"""Immutable department ownership and visibility for lead activities.

Every ``LeadActivity`` is assigned to the department of the employee who
created it. The snapshot is written once, when the row is inserted, and is
never inferred again from the lead's current assignee. That is what keeps
Sales notes private after the customer is handed over to Support, and keeps
Support onboarding notes out of the Sales dashboard.

Visibility rules:

* Admin: company-wide.
* Sales: ``department == 'SALES'`` only.
* Support: ``department == 'SUPPORT'`` only, and only for leads the Support
  user is already authorized to access.
* Any other department / unattributed legacy record: not visible to Sales or
  Support. Admin can still audit it.

Legacy rows are backfilled from their creator employee relationship. Rows with
no attributable employee remain Admin-only rather than being guessed into the
wrong department.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import and_, false, or_, select
from sqlalchemy import event as sa_event
from sqlalchemy.orm import Session

from models.activity import LeadActivity
from models.employee import Employee
from models.user import User
from services.department_service import (
    employee_department,
    get_department_employee_ids,
    parse_admin_department,
)
from services.hierarchy_service import (
    DEPT_SALES,
    DEPT_SUPPORT,
    ROLE_ADMIN,
    get_department_for_role,
    normalize_department,
    normalize_role,
)

ACTIVITY_DEPARTMENTS = (DEPT_SALES, DEPT_SUPPORT)

_SUPPORT_ACTIVITY_PREFIXES = (
    "SUPPORT_",
    "ONBOARDING_",
    "INSTALLATION_",
    "TICKET_",
    "RESOLUTION_",
)


def _department_from_employee(employee: Optional[Employee]) -> Optional[str]:
    return employee_department(employee)


def _department_from_type(activity_type: Optional[str]) -> Optional[str]:
    """Only classify unmistakably Support-owned legacy event types.

    Sales types are never guessed from keywords because a Sales-originated
    handover event (for example ``DEAL_WON_SUPPORT_ASSIGNED``) contains the
    word SUPPORT but belongs to Sales.
    """
    normalized = (activity_type or "").strip().upper()
    if any(normalized.startswith(prefix) for prefix in _SUPPORT_ACTIVITY_PREFIXES):
        return DEPT_SUPPORT
    return None


def user_activity_department(user: Optional[User], db: Optional[Session] = None) -> Optional[str]:
    """Resolve the authenticated user's department without using lead ownership."""
    if not user:
        return None
    employee = getattr(user, "employee", None)
    if employee is None and db is not None:
        employee = db.query(Employee).filter(Employee.user_id == user.id).first()
    department = _department_from_employee(employee)
    if department:
        return department
    department = normalize_department(getattr(user, "department", None))
    if department:
        return department
    return normalize_department(get_department_for_role(getattr(user, "role", None)))


def activity_department(
    activity: LeadActivity, db: Optional[Session] = None
) -> Optional[str]:
    """Resolve an activity's immutable department, with legacy fallbacks."""
    stored = normalize_department(getattr(activity, "department", None))
    if stored:
        return stored

    employee = getattr(activity, "performed_by_employee", None) or getattr(
        activity, "employee", None
    )
    if employee is None and db is not None:
        employee_id = activity.performed_by or activity.employee_id
        if employee_id:
            employee = db.query(Employee).filter(Employee.id == employee_id).first()
    department = _department_from_employee(employee)
    if department:
        return department
    return _department_from_type(activity.activity_type)


def _is_admin(user: Optional[User]) -> bool:
    return bool(user) and normalize_role(getattr(user, "role", None)) == ROLE_ADMIN


def can_view_activity(
    activity: LeadActivity, user: Optional[User], db: Optional[Session] = None
) -> bool:
    if not activity or not user:
        return False
    if _is_admin(user):
        return True
    department = user_activity_department(user, db)
    if department not in ACTIVITY_DEPARTMENTS:
        return False
    return activity_department(activity, db) == department


def _legacy_employee_clause(db: Session, department: str):
    employee_ids = get_department_employee_ids(db, department)
    if not employee_ids:
        return false()
    return or_(
        LeadActivity.performed_by.in_(employee_ids),
        LeadActivity.employee_id.in_(employee_ids),
    )


def apply_activity_visibility_filter(query, user: User, db: Session):
    """Apply department ownership in SQL for the shared activity stream."""
    if not user:
        return query.filter(false())
    if _is_admin(user):
        return query

    department = user_activity_department(user, db)
    if department not in ACTIVITY_DEPARTMENTS:
        return query.filter(false())

    return query.filter(
        or_(
            LeadActivity.department == department,
            and_(
                LeadActivity.department.is_(None),
                _legacy_employee_clause(db, department),
            ),
        )
    )


def apply_admin_activity_department_filter(query, db: Session, department: str):
    """Admin-only explicit department filter with a legacy fallback."""
    normalized = parse_admin_department(department)
    if not normalized:
        return query
    return query.filter(
        or_(
            LeadActivity.department == normalized,
            and_(
                LeadActivity.department.is_(None),
                _legacy_employee_clause(db, normalized),
            ),
        )
    )


def apply_support_lead_scope(query, user: User, db: Session):
    """Limit Support activity queries to leads the user may already access."""
    if not user or _is_admin(user):
        return query
    if user_activity_department(user, db) != DEPT_SUPPORT:
        return query
    from services.permission_service import get_support_authorized_lead_ids

    lead_ids = get_support_authorized_lead_ids(user, db)
    if lead_ids is None:
        return query
    if not lead_ids:
        return query.filter(false())
    return query.filter(LeadActivity.lead_id.in_(lead_ids))


def backfill_activity_departments(db: Session) -> int:
    """Populate department snapshots for pre-migration activity rows only."""
    pending = (
        db.query(LeadActivity)
        .filter(LeadActivity.department.is_(None))
        .all()
    )
    if not pending:
        return 0

    employees = {employee.id: employee for employee in db.query(Employee).all()}
    updated = 0
    for activity in pending:
        employee = employees.get(activity.performed_by) or employees.get(
            activity.employee_id
        )
        department = _department_from_employee(employee) or _department_from_type(
            activity.activity_type
        )
        if department:
            activity.department = department
            updated += 1

    if updated:
        db.commit()
    return updated


@sa_event.listens_for(LeadActivity, "before_insert")
def _populate_activity_department(mapper, connection, target):
    """Write the creator's department snapshot at insert time.

    The lookup uses the flush connection instead of the ORM session so that it
    cannot trigger a recursive autoflush while the row is being inserted.
    """
    if normalize_department(getattr(target, "department", None)):
        return

    employee_id = target.performed_by or target.employee_id
    if employee_id:
        row = connection.execute(
            select(Employee.department, Employee.role).where(Employee.id == employee_id)
        ).first()
        if row:
            department = normalize_department(
                row[0]
            ) or normalize_department(get_department_for_role(row[1]))
            if department:
                target.department = department
                return

    inferred = _department_from_type(target.activity_type)
    if inferred:
        target.department = inferred
