"""
Follow-up department ownership and visibility rules.

Follow-ups carry immutable ownership snapshots:

``creator_department``
    Department of the employee who created the follow-up.
``assigned_department``
    Department of the employee the follow-up was assigned to at creation time.
``owner_department``
    The department that owns the follow-up. A Sales/Support creator owns the
    record in their own department. Admin-created records are owned by the
    assignee's department.

Visibility is always resolved in SQL from those snapshots. The lead's current
``assigned_to`` value is deliberately never used to infer ownership, because a
Sales -> Support handover must not transfer historical Sales follow-ups.
"""

from __future__ import annotations

from typing import Iterable, Optional, Tuple

from sqlalchemy import and_, false, or_
from sqlalchemy.orm import Session

from models.employee import Employee
from models.followup import Followup
from models.user import User
from services.department_service import (
    ADMIN_DEPARTMENTS,
    employee_department,
    get_department_employee_ids,
    normalize_department,
    parse_admin_department,
)
from services.hierarchy_service import (
    DEPT_SALES,
    DEPT_SUPPORT,
    ROLE_ADMIN,
    normalize_role,
)
from services.permission_service import get_authorized_followup_employee_ids

FOLLOWUP_DEPARTMENTS: Tuple[str, ...] = (DEPT_SALES, DEPT_SUPPORT)


def _owner_department_for(
    creator_department: Optional[str],
    assigned_department: Optional[str],
) -> Optional[str]:
    """Return the owning department snapshot for a follow-up."""
    creator = normalize_department(creator_department)
    if creator in FOLLOWUP_DEPARTMENTS:
        return creator
    assigned = normalize_department(assigned_department)
    if assigned:
        # Admin-created records are owned by the assignee's department, even
        # when that department is not Sales/Support (e.g. Administration).
        return assigned
    return None


def resolve_employee_departments(
    creator: Optional[Employee], assignee: Optional[Employee]
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Resolve (creator, assigned, owner) departments from employee records."""
    creator_department = employee_department(creator)
    assigned_department = employee_department(assignee)
    return (
        creator_department,
        assigned_department,
        _owner_department_for(creator_department, assigned_department),
    )


def build_followup_ownership(creator: Optional[Employee], assignee: Optional[Employee]):
    """Populate the three immutable ownership snapshots on a Followup."""
    creator_department, assigned_department, owner_department = (
        resolve_employee_departments(creator, assignee)
    )
    return {
        "creator_department": creator_department,
        "assigned_department": assigned_department,
        "owner_department": owner_department,
    }


def department_ownership_clause(department: str):
    """
    SQL clause for one Admin department filter.

    Rows written after this change have ``owner_department``. Legacy rows that
    pre-date the additive migration fall back to their creator's department
    first, then their assignee's department. This keeps existing records
    visible without guessing from the lead's current owner.
    """
    normalized = parse_admin_department(department)
    if not normalized:
        return None
    return or_(
        Followup.owner_department == normalized,
        and_(
            Followup.owner_department.is_(None),
            Followup.creator_department == normalized,
        ),
        and_(
            Followup.owner_department.is_(None),
            Followup.creator_department.is_(None),
            Followup.assigned_department == normalized,
        ),
    )


def apply_followup_department_filter(query, db: Session, department: str):
    """Apply the Admin department scope to an existing Followup query."""
    normalized = parse_admin_department(department)
    if not normalized:
        return query
    clause = _department_scope_clause(db, normalized)
    if clause is None:
        return query
    return query.filter(clause)


def _department_scope_clause(db: Session, department: str):
    """Stored snapshot ownership + legacy employee fallback for one dept."""
    stored = department_ownership_clause(department)
    legacy = legacy_department_clause(db, department)
    if stored is None and legacy is None:
        return None
    if stored is None:
        return legacy
    if legacy is None:
        return stored
    return or_(stored, legacy)


def apply_followup_department_filters(
    query, db: Session, departments: Optional[Iterable[str]]
):
    """Apply a Union of Sales/Support ownership scopes to a query."""
    if departments is None:
        return query
    normalized = {
        dept
        for dept in (normalize_department(item) for item in departments)
        if dept in ADMIN_DEPARTMENTS
    }
    if not normalized:
        return query.filter(false())
    clauses = [
        clause
        for clause in (_department_scope_clause(db, dept) for dept in normalized)
        if clause is not None
    ]
    if not clauses:
        return query
    return query.filter(or_(*clauses))


def legacy_department_clause(db: Session, department: str):
    """
    Legacy fallback by employee relationship, used only when all immutable
    snapshots are missing. New rows never hit this branch.
    """
    normalized = parse_admin_department(department)
    if not normalized:
        return None
    employee_ids = get_department_employee_ids(db, normalized)
    if not employee_ids:
        return false()
    return and_(
        Followup.owner_department.is_(None),
        Followup.creator_department.is_(None),
        Followup.assigned_department.is_(None),
        or_(
            Followup.created_by.in_(employee_ids),
            and_(
                Followup.created_by.is_(None),
                Followup.assigned_to.in_(employee_ids),
            ),
        ),
    )


def apply_admin_followup_department_filter(query, db: Session, department: str):
    """
    Admin-only department filter with a safe legacy fallback.

    Stored ownership always takes precedence. Employee relationships are only
    consulted for pre-migration rows whose snapshot columns are still NULL.
    """
    normalized = parse_admin_department(department)
    if not normalized:
        return query
    clause = _department_scope_clause(db, normalized)
    if clause is None:
        return query
    return query.filter(clause)


def apply_followup_visibility_filter(query, user: User, db: Session):
    """
    Apply authenticated department + employee ownership scope in SQL.

    Admin: unrestricted (the caller may still apply an explicit department
    filter). Sales/Support users: only records owned by their department where
    they are the assignee, the creator, or an authorised team member.
    """
    if not user:
        return query.filter(false())

    norm_role = normalize_role(user.role)
    if norm_role == ROLE_ADMIN:
        return query

    employee = db.query(Employee).filter(Employee.user_id == user.id).first()
    department = employee_department(employee)
    if department not in FOLLOWUP_DEPARTMENTS:
        return query.filter(false())

    authorized_ids = get_authorized_followup_employee_ids(user, db)
    if not authorized_ids:
        return query.filter(false())

    # Snapshot ownership is authoritative. NULL snapshots are only possible for
    # pre-migration rows. For those rows, creator membership is used before
    # assignee membership so a cross-department legacy row cannot leak into the
    # other department while the backfill runs.
    owner_clause = or_(
        Followup.owner_department == department,
        and_(
            Followup.owner_department.is_(None),
            Followup.creator_department == department,
        ),
        and_(
            Followup.owner_department.is_(None),
            Followup.creator_department.is_(None),
            or_(
                Followup.created_by.in_(authorized_ids),
                and_(
                    Followup.created_by.is_(None),
                    Followup.assigned_to.in_(authorized_ids),
                ),
            ),
        ),
    )
    employee_clause = or_(
        Followup.assigned_to.in_(authorized_ids),
        Followup.created_by.in_(authorized_ids),
    )
    return query.filter(owner_clause, employee_clause)


def backfill_followup_departments(db: Session) -> int:
    """
    Populate ownership snapshots for existing rows without deleting or
    reassigning any follow-up. Existing non-NULL snapshots are never changed.
    """
    pending = (
        db.query(Followup)
        .filter(
            or_(
                Followup.creator_department.is_(None),
                Followup.assigned_department.is_(None),
                Followup.owner_department.is_(None),
            )
        )
        .all()
    )
    if not pending:
        return 0

    employees = {
        employee.id: employee for employee in db.query(Employee).all()
    }
    updated = 0
    for followup in pending:
        creator = employees.get(followup.created_by)
        assignee = employees.get(followup.assigned_to)
        creator_department, assigned_department, owner_department = (
            resolve_employee_departments(creator, assignee)
        )
        changed = False
        if followup.creator_department is None and creator_department:
            followup.creator_department = creator_department
            changed = True
        if followup.assigned_department is None and assigned_department:
            followup.assigned_department = assigned_department
            changed = True
        if followup.owner_department is None and owner_department:
            followup.owner_department = owner_department
            changed = True
        if changed:
            updated += 1

    if updated:
        db.commit()
    return updated
