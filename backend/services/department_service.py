"""
Centralized Admin department segregation logic.

Sales and Support records are attributed strictly through existing Employee
relationships and IDs. Nothing in this module creates duplicate employees,
changes reporting hierarchies, or mutates Sales/Support workflow data.

Department rules:
- Employee.department is authoritative when present.
- Legacy rows with a missing department fall back to the department implied by
  their role, using the existing hierarchy_service normalization.
- Teams are existing manager-led Employee.manager_id hierarchies. The Team
  table only registers a name under a department/manager.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from sqlalchemy import and_, case, false, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.call_log import CallLog
from models.employee import Employee
from models.followup import Followup
from models.lead import Lead
from models.team import Team
from models.workflow import SupportHandoff
from services.hierarchy_service import (
    DEPT_SALES,
    DEPT_SUPPORT,
    get_department_for_role,
    normalize_department,
    normalize_role,
)

ADMIN_DEPARTMENTS: Sequence[str] = (DEPT_SALES, DEPT_SUPPORT)
ADMIN_MANAGER_ROLES = {"SALES_MANAGER", "MANAGER", "SUPPORT_MANAGER"}
ADMIN_EXECUTIVE_ROLES = {"SALES_EXECUTIVE", "SALES", "EMPLOYEE", "SUPPORT_EXECUTIVE", "SUPPORT"}

DEPARTMENT_LABELS = {
    DEPT_SALES: "Sales",
    DEPT_SUPPORT: "Support",
    "COMPANY": "Company-wide",
    "COMBINED": "Sales + Support",
}

CONNECTED_CALL_STATUSES = ("%COMPLETED%", "%CONNECTED%", "%ANSWERED%")
MISSED_CALL_STATUSES = ("%MISSED%", "%BUSY%", "%FAILED%", "%NO_ANSWER%", "%NO ANSWER%")


def department_label(department: Optional[str]) -> str:
    return DEPARTMENT_LABELS.get((department or "").upper(), department or "All Departments")


def parse_admin_department(value: Optional[str]) -> Optional[str]:
    """
    Normalize an Admin department filter.

    Returns None for an absent / 'ALL' filter. Raises ValueError for anything
    outside the Admin Sales/Support segregation scope.
    """
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned or cleaned.upper() in {"ALL", "ALL_DEPARTMENTS", "COMPANY"}:
        return None
    normalized = normalize_department(cleaned)
    if normalized not in ADMIN_DEPARTMENTS:
        raise ValueError("Department must be one of: ALL, SALES, SUPPORT.")
    return normalized


def employee_department(employee: Optional[Employee]) -> Optional[str]:
    """Resolve an employee's effective department without mutating the row."""
    if not employee:
        return None
    explicit = normalize_department(getattr(employee, "department", None))
    if explicit:
        return explicit
    return normalize_department(get_department_for_role(getattr(employee, "role", None)))


def _employees_for_departments(
    db: Session, departments: Optional[Iterable[str]] = None
) -> List[Employee]:
    target = (
        {normalize_department(d) for d in departments if normalize_department(d)}
        if departments
        else set(ADMIN_DEPARTMENTS)
    )
    employees = db.query(Employee).all()
    return [e for e in employees if employee_department(e) in target]


def get_department_employees(
    db: Session, department: str
) -> List[Employee]:
    normalized = normalize_department(department)
    return _employees_for_departments(db, [normalized])


def get_department_employee_ids(db: Session, department: str) -> List[int]:
    return [e.id for e in get_department_employees(db, department)]


def get_all_employee_ids(db: Session) -> List[int]:
    return [emp_id for (emp_id,) in db.query(Employee.id).all()]


def _team_member_ids(db: Session, manager_id: int) -> List[int]:
    """All direct/indirect reportees of a manager (manager excluded)."""
    members: List[int] = []
    seen: Set[int] = set()
    queue: List[int] = [manager_id]
    while queue:
        current = queue.pop(0)
        reportees = db.query(Employee.id).filter(Employee.manager_id == current).all()
        for (reportee_id,) in reportees:
            if reportee_id in seen:
                continue
            seen.add(reportee_id)
            members.append(reportee_id)
            queue.append(reportee_id)
    return members


def _employee_payload(db: Session, employee: Employee) -> Dict[str, Any]:
    manager = None
    if employee.manager_id:
        manager = db.query(Employee).filter(Employee.id == employee.manager_id).first()

    registered_team = (
        db.query(Team).filter(Team.manager_id == employee.id, Team.status == "ACTIVE").first()
    )
    reporting_manager_user_id = getattr(employee, "reporting_manager_id", None)
    if not reporting_manager_user_id and manager:
        reporting_manager_user_id = manager.user_id

    return {
        "id": employee.id,
        "user_id": employee.user_id,
        "name": employee.name,
        "email": employee.email,
        "phone": employee.phone,
        "username": employee.username,
        "photo_url": employee.photo_url,
        "role": normalize_role(employee.role),
        "raw_role": employee.role,
        "department": employee_department(employee),
        "status": (employee.status or "ACTIVE").upper(),
        "manager_id": manager.id if manager else None,
        "manager_name": manager.name if manager else None,
        "reporting_manager_id": reporting_manager_user_id,
        "reporting_manager_name": manager.name if manager else None,
        "direct_reports_count": db.query(Employee)
        .filter(Employee.manager_id == employee.id, Employee.status == "ACTIVE")
        .count(),
        "is_manager": normalize_role(employee.role) in ADMIN_MANAGER_ROLES,
        "team_id": registered_team.id if registered_team else None,
        "team_name": registered_team.name if registered_team else None,
    }


def _team_payload(
    db: Session,
    manager: Employee,
    members: List[Employee],
    *,
    team: Optional[Team] = None,
) -> Dict[str, Any]:
    department = (
        normalize_department(team.department)
        if team is not None
        else employee_department(manager)
    )
    return {
        "id": team.id if team else None,
        "key": f"team-{team.id}" if team else f"implicit-{manager.id}",
        "name": team.name if team else f"{manager.name}'s Team",
        "department": department,
        "department_label": department_label(department),
        "registered": team is not None,
        "description": team.description if team else None,
        "status": (team.status if team else "ACTIVE"),
        "manager_id": manager.id,
        "manager_name": manager.name,
        "manager_role": normalize_role(manager.role),
        "manager": {
            "id": manager.id,
            "user_id": manager.user_id,
            "name": manager.name,
            "email": manager.email,
            "phone": manager.phone,
            "role": normalize_role(manager.role),
            "department": employee_department(manager),
            "status": (manager.status or "ACTIVE").upper(),
        },
        "members": [_employee_payload(db, member) for member in members],
        "member_count": len(members),
        "total_people": len(members) + 1,
        "created_at": team.created_at.isoformat() if team and team.created_at else None,
        "updated_at": team.updated_at.isoformat() if team and team.updated_at else None,
    }


def list_department_teams(
    db: Session, departments: Optional[Iterable[str]] = None
) -> List[Dict[str, Any]]:
    """
    Returns registered teams plus implicit manager-hierarchy teams.

    A registered Team replaces the implicit entry for the same manager, so a
    team is never counted twice. Implicit teams are only created for active
    department managers who currently have at least one reportee.
    """
    target_departments = (
        {normalize_department(d) for d in departments if normalize_department(d)}
        if departments
        else set(ADMIN_DEPARTMENTS)
    )

    registered_teams = (
        db.query(Team)
        .filter(Team.department.in_(list(target_departments)))
        .order_by(Team.department.asc(), Team.name.asc())
        .all()
    )
    registered_manager_ids = {team.manager_id for team in registered_teams}

    results: List[Dict[str, Any]] = []
    for team in registered_teams:
        manager = db.query(Employee).filter(Employee.id == team.manager_id).first()
        if not manager:
            continue
        department = normalize_department(team.department)
        member_ids = _team_member_ids(db, manager.id)
        members = [
            member
            for member in db.query(Employee).filter(Employee.id.in_(member_ids)).all()
            if employee_department(member) == department
        ] if member_ids else []
        members.sort(key=lambda item: (item.name or "").lower())
        results.append(_team_payload(db, manager, members, team=team))

    for manager in _employees_for_departments(db, target_departments):
        if manager.id in registered_manager_ids:
            continue
        if normalize_role(manager.role) not in ADMIN_MANAGER_ROLES:
            continue
        if (manager.status or "ACTIVE").upper() != "ACTIVE":
            continue
        department = employee_department(manager)
        member_ids = _team_member_ids(db, manager.id)
        members = [
            member
            for member in db.query(Employee).filter(Employee.id.in_(member_ids)).all()
            if employee_department(member) == department
        ] if member_ids else []
        if not members:
            # Do not invent an empty team from every manager record.
            continue
        members.sort(key=lambda item: (item.name or "").lower())
        results.append(_team_payload(db, manager, members))

    results.sort(
        key=lambda t: (
            0 if t["registered"] else 1,
            (t.get("department") or ""),
            (t.get("name") or "").lower(),
        )
    )
    return results


def create_department_team(
    db: Session,
    *,
    name: str,
    department: str,
    manager_id: int,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Registers a team under an existing department manager.

    Employee records are reused as-is. Nothing is duplicated or reassigned.
    """
    normalized_department = parse_admin_department(department)
    if not normalized_department:
        raise ValueError("Department is required (SALES or SUPPORT).")

    clean_name = (name or "").strip()
    if len(clean_name) < 2:
        raise ValueError("Team name must contain at least 2 characters.")
    if len(clean_name) > 100:
        raise ValueError("Team name must be 100 characters or fewer.")

    manager = db.query(Employee).filter(Employee.id == manager_id).first()
    if not manager:
        raise ValueError("Selected team manager was not found.")
    if (manager.status or "ACTIVE").upper() != "ACTIVE":
        raise ValueError("Selected team manager is inactive.")
    if employee_department(manager) != normalized_department:
        raise ValueError("Selected manager does not belong to the selected department.")

    manager_role = normalize_role(manager.role)
    allowed_roles = (
        {"SALES_MANAGER", "MANAGER"}
        if normalized_department == DEPT_SALES
        else {"SUPPORT_MANAGER"}
    )
    if manager_role not in allowed_roles:
        raise ValueError(
            "Team manager must be an active "
            + ("Sales Manager" if normalized_department == DEPT_SALES else "Support Manager")
            + "."
        )

    existing_manager_team = db.query(Team).filter(Team.manager_id == manager_id).first()
    if existing_manager_team:
        raise ValueError(
            f"Manager '{manager.name}' is already registered to team "
            f"'{existing_manager_team.name}'."
        )

    existing_name = (
        db.query(Team)
        .filter(
            Team.department == normalized_department,
            func.lower(Team.name) == clean_name.lower(),
        )
        .first()
    )
    if existing_name:
        raise ValueError(
            f"A team named '{clean_name}' already exists in "
            f"{department_label(normalized_department)}."
        )

    team = Team(
        name=clean_name,
        department=normalized_department,
        manager_id=manager_id,
        description=(description or "").strip() or None,
        status="ACTIVE",
    )
    db.add(team)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("Unable to create team: duplicate name or manager.") from exc
    db.refresh(team)

    department_employees = get_department_employees(db, normalized_department)
    employee_ids = {employee.id for employee in department_employees}
    members = [
        employee
        for employee in db.query(Employee)
        .filter(Employee.id.in_(_team_member_ids(db, manager.id)))
        .all()
        if employee.id in employee_ids
    ] if employee_ids else []
    members.sort(key=lambda item: (item.name or "").lower())
    return _team_payload(db, manager, members, team=team)


def list_department_managers(db: Session, department: str) -> List[Dict[str, Any]]:
    normalized = parse_admin_department(department)
    if not normalized:
        raise ValueError("Department is required (SALES or SUPPORT).")

    allowed_roles = (
        {"SALES_MANAGER", "MANAGER"}
        if normalized == DEPT_SALES
        else {"SUPPORT_MANAGER"}
    )
    managers = []
    for employee in get_department_employees(db, normalized):
        if (employee.status or "ACTIVE").upper() != "ACTIVE":
            continue
        if normalize_role(employee.role) not in allowed_roles:
            continue
        team = db.query(Team).filter(Team.manager_id == employee.id).first()
        managers.append(
            {
                "id": employee.id,
                "user_id": employee.user_id,
                "name": employee.name,
                "email": employee.email,
                "phone": employee.phone,
                "role": normalize_role(employee.role),
                "department": normalized,
                "team_id": team.id if team else None,
                "team_name": team.name if team else None,
                "can_create_team": team is None,
            }
        )
    managers.sort(key=lambda item: (item["name"] or "").lower())
    return managers


def list_admin_employees(
    db: Session,
    *,
    department: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
) -> List[Dict[str, Any]]:
    normalized_department = parse_admin_department(department)
    departments = [normalized_department] if normalized_department else None
    employees = _employees_for_departments(db, departments)

    status_clean = (status or "").strip().upper()
    if status_clean and status_clean != "ALL":
        employees = [
            employee
            for employee in employees
            if (employee.status or "ACTIVE").upper() == status_clean
        ]

    search_clean = (search or "").strip().lower()
    results = [_employee_payload(db, employee) for employee in employees]
    if search_clean:
        results = [
            item
            for item in results
            if any(
                search_clean in str(item.get(field) or "").lower()
                for field in (
                    "name",
                    "email",
                    "phone",
                    "username",
                    "role",
                    "department",
                    "manager_name",
                    "team_name",
                )
            )
        ]

    results.sort(
        key=lambda item: (
            item.get("department") or "",
            (item.get("name") or "").lower(),
        )
    )
    return results


def _date_bounds(
    date_from: Optional[date], date_to: Optional[date]
) -> tuple[Optional[datetime], Optional[datetime]]:
    start = datetime.combine(date_from, time.min) if date_from else None
    end = datetime.combine(date_to + timedelta(days=1), time.min) if date_to else None
    return start, end


def _call_stats(
    db: Session,
    employee_ids: Optional[Sequence[int]],
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> Dict[str, Any]:
    if employee_ids is not None and not employee_ids:
        return {
            "total": 0,
            "inbound": 0,
            "outbound": 0,
            "connected": 0,
            "missed": 0,
            "connect_rate": 0,
            "total_duration_seconds": 0,
            "avg_duration_seconds": 0,
        }

    query = db.query(CallLog)
    if employee_ids is not None:
        query = query.filter(CallLog.employee_id.in_(list(employee_ids)))
    start, end = _date_bounds(date_from, date_to)
    if start:
        query = query.filter(CallLog.created_at >= start)
    if end:
        query = query.filter(CallLog.created_at < end)

    connected_condition = or_(
        *[CallLog.call_status.ilike(pattern) for pattern in CONNECTED_CALL_STATUSES]
    )
    missed_condition = or_(
        *[CallLog.call_status.ilike(pattern) for pattern in MISSED_CALL_STATUSES]
    )

    agg = query.with_entities(
        func.count(CallLog.id).label("total"),
        func.sum(case((CallLog.call_direction == "INBOUND", 1), else_=0)).label("inbound"),
        func.sum(case((CallLog.call_direction == "OUTBOUND", 1), else_=0)).label("outbound"),
        func.sum(case((connected_condition, 1), else_=0)).label("connected"),
        func.sum(case((missed_condition, 1), else_=0)).label("missed"),
        func.sum(
            case((connected_condition, func.coalesce(CallLog.duration_seconds, 0)), else_=0)
        ).label("total_secs"),
    ).first()

    total = int(agg.total or 0)
    connected = int(agg.connected or 0)
    total_secs = int(agg.total_secs or 0)
    return {
        "total": total,
        "inbound": int(agg.inbound or 0),
        "outbound": int(agg.outbound or 0),
        "connected": connected,
        "missed": int(agg.missed or 0),
        "connect_rate": round((connected / total) * 100) if total else 0,
        "total_duration_seconds": total_secs,
        "avg_duration_seconds": round(total_secs / connected) if connected else 0,
    }


def _followup_scope_clause(employee_ids: Sequence[int]):
    """Follow-ups are owned by assignee; unassigned rows fall back to creator."""
    return or_(
        Followup.assigned_to.in_(list(employee_ids)),
        and_(Followup.assigned_to.is_(None), Followup.created_by.in_(list(employee_ids))),
    )


def _followup_stats(
    db: Session,
    employee_ids: Optional[Sequence[int]],
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> Dict[str, Any]:
    if employee_ids is not None and not employee_ids:
        return {
            "total": 0,
            "pending": 0,
            "completed": 0,
            "cancelled": 0,
            "overdue": 0,
        }

    query = db.query(Followup)
    if employee_ids is not None:
        query = query.filter(_followup_scope_clause(employee_ids))
    if date_from:
        query = query.filter(Followup.followup_date >= date_from)
    if date_to:
        query = query.filter(Followup.followup_date <= date_to)

    today = date.today()
    agg = query.with_entities(
        func.count(Followup.id).label("total"),
        func.sum(case((Followup.status == "Pending", 1), else_=0)).label("pending"),
        func.sum(case((Followup.status == "Completed", 1), else_=0)).label("completed"),
        func.sum(case((Followup.status == "Cancelled", 1), else_=0)).label("cancelled"),
        func.sum(
            case(
                (
                    and_(Followup.status == "Pending", Followup.followup_date < today),
                    1,
                ),
                else_=0,
            )
        ).label("overdue"),
    ).first()

    return {
        "total": int(agg.total or 0),
        "pending": int(agg.pending or 0),
        "completed": int(agg.completed or 0),
        "cancelled": int(agg.cancelled or 0),
        "overdue": int(agg.overdue or 0),
    }


def _lead_stats(db: Session, employee_ids: Optional[Sequence[int]]) -> Dict[str, Any]:
    if employee_ids is not None and not employee_ids:
        return {"total": 0, "converted": 0, "open": 0}

    query = db.query(Lead)
    if employee_ids is not None:
        query = query.filter(Lead.assigned_to.in_(list(employee_ids)))

    total = query.count()
    converted = query.filter(
        func.lower(Lead.status).in_(["converted", "won"])
    ).count()
    return {
        "total": total,
        "converted": converted,
        "open": max(total - converted, 0),
    }


def _handover_query(
    db: Session,
    department: Optional[str],
    employee_ids: Optional[Sequence[int]],
):
    query = db.query(SupportHandoff)
    normalized = normalize_department(department) if department else None
    if normalized == DEPT_SALES and employee_ids is not None:
        ids = list(employee_ids)
        if not ids:
            return query.filter(false())
        query = query.outerjoin(Lead, SupportHandoff.lead_id == Lead.id).filter(
            or_(
                SupportHandoff.sales_employee_id.in_(ids),
                and_(
                    SupportHandoff.sales_employee_id.is_(None),
                    Lead.assigned_to.in_(ids),
                ),
            )
        )
    elif normalized == DEPT_SUPPORT and employee_ids is not None:
        ids = list(employee_ids)
        if not ids:
            return query.filter(false())
        query = query.filter(
            or_(
                SupportHandoff.support_manager_id.in_(ids),
                SupportHandoff.assigned_agent_id.in_(ids),
            )
        )
    return query


def _handover_stats(
    db: Session,
    department: Optional[str],
    employee_ids: Optional[Sequence[int]],
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> Dict[str, Any]:
    query = _handover_query(db, department, employee_ids)
    start, end = _date_bounds(date_from, date_to)
    if start:
        query = query.filter(SupportHandoff.created_at >= start)
    if end:
        query = query.filter(SupportHandoff.created_at < end)
    total = query.count()
    completed = query.filter(
        func.upper(SupportHandoff.onboarding_status) == "COMPLETED"
    ).count()
    unassigned = query.filter(SupportHandoff.assigned_agent_id.is_(None)).count()
    return {
        "total": total,
        "pending": max(total - completed, 0),
        "completed": completed,
        "unassigned": unassigned,
    }


def _team_stats(
    db: Session, departments: Optional[Iterable[str]] = None
) -> Dict[str, Any]:
    teams = list_department_teams(db, departments)
    people: Set[int] = set()
    for team in teams:
        people.add(team["manager_id"])
        people.update(member["id"] for member in team["members"])
    registered = sum(1 for team in teams if team["registered"])
    return {
        "total": len(teams),
        "registered": registered,
        "implicit": len(teams) - registered,
        "people": len(people),
    }


def _employee_stats(employees: Sequence[Employee]) -> Dict[str, Any]:
    active = sum(1 for employee in employees if (employee.status or "ACTIVE").upper() == "ACTIVE")
    managers = sum(
        1 for employee in employees if normalize_role(employee.role) in ADMIN_MANAGER_ROLES
    )
    executives = sum(
        1 for employee in employees if normalize_role(employee.role) in ADMIN_EXECUTIVE_ROLES
    )
    return {
        "total": len(employees),
        "active": active,
        "inactive": len(employees) - active,
        "managers": managers,
        "executives": executives,
    }


def _build_statistics(
    db: Session,
    *,
    key: str,
    label: str,
    employee_ids: Optional[Sequence[int]],
    departments: Optional[Iterable[str]],
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    handover_department: Optional[str] = None,
) -> Dict[str, Any]:
    if employee_ids is None:
        employees = db.query(Employee).all()
    elif employee_ids:
        employees = db.query(Employee).filter(Employee.id.in_(list(employee_ids))).all()
    else:
        employees = []

    return {
        "key": key,
        "label": label,
        "employees": _employee_stats(employees),
        "teams": _team_stats(db, departments),
        "calls": _call_stats(db, employee_ids, date_from, date_to),
        "followups": _followup_stats(db, employee_ids, date_from, date_to),
        "leads": _lead_stats(db, employee_ids),
        "handovers": _handover_stats(
            db, handover_department, employee_ids, date_from, date_to
        ),
    }


def get_department_statistics(
    db: Session,
    department: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> Dict[str, Any]:
    normalized = parse_admin_department(department)
    if not normalized:
        raise ValueError("Department must be SALES or SUPPORT.")
    employee_ids = get_department_employee_ids(db, normalized)
    return _build_statistics(
        db,
        key=normalized,
        label=department_label(normalized),
        employee_ids=employee_ids,
        departments=[normalized],
        date_from=date_from,
        date_to=date_to,
        handover_department=normalized,
    )


def get_company_statistics(
    db: Session,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> Dict[str, Any]:
    return _build_statistics(
        db,
        key="COMPANY",
        label=department_label("COMPANY"),
        employee_ids=None,
        departments=None,
        date_from=date_from,
        date_to=date_to,
        handover_department=None,
    )


def get_combined_statistics(
    db: Session,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> Dict[str, Any]:
    employee_ids = get_department_employee_ids(db, DEPT_SALES) + get_department_employee_ids(
        db, DEPT_SUPPORT
    )
    return _build_statistics(
        db,
        key="COMBINED",
        label=department_label("COMBINED"),
        employee_ids=employee_ids,
        departments=[DEPT_SALES, DEPT_SUPPORT],
        date_from=date_from,
        date_to=date_to,
        handover_department=None,
    )


def get_admin_overview(
    db: Session,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> Dict[str, Any]:
    departments = [
        get_department_statistics(db, DEPT_SALES, date_from, date_to),
        get_department_statistics(db, DEPT_SUPPORT, date_from, date_to),
    ]
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "departments": departments,
        "combined": get_combined_statistics(db, date_from, date_to),
        "company": get_company_statistics(db, date_from, date_to),
    }


def get_admin_reports(
    db: Session,
    *,
    department: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> Dict[str, Any]:
    selected = parse_admin_department(department)
    if selected:
        departments = [get_department_statistics(db, selected, date_from, date_to)]
        scope = selected
        label = department_label(selected)
    else:
        departments = [
            get_department_statistics(db, DEPT_SALES, date_from, date_to),
            get_department_statistics(db, DEPT_SUPPORT, date_from, date_to),
        ]
        scope = "ALL"
        label = "All Departments"

    return {
        "scope": scope,
        "label": label,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "departments": departments,
        "combined": get_combined_statistics(db, date_from, date_to),
        "company": get_company_statistics(db, date_from, date_to),
    }


def apply_call_department_filter(query, db: Session, department: str):
    """Apply the Admin department scope to an existing CallLog query."""
    normalized = parse_admin_department(department)
    if not normalized:
        return query
    employee_ids = get_department_employee_ids(db, normalized)
    if not employee_ids:
        return query.filter(false())
    return query.filter(CallLog.employee_id.in_(employee_ids))


def apply_followup_department_filter(query, db: Session, department: str):
    """Apply the Admin department scope to an existing Followup query."""
    normalized = parse_admin_department(department)
    if not normalized:
        return query
    employee_ids = get_department_employee_ids(db, normalized)
    if not employee_ids:
        return query.filter(false())
    return query.filter(_followup_scope_clause(employee_ids))


def _serialize_handover(db: Session, handoff: SupportHandoff) -> Dict[str, Any]:
    lead = (
        db.query(Lead).filter(Lead.id == handoff.lead_id).first()
        if handoff.lead_id
        else None
    )
    sales_employee = None
    sales_source = "UNASSIGNED"
    if handoff.sales_employee_id:
        sales_employee = (
            db.query(Employee).filter(Employee.id == handoff.sales_employee_id).first()
        )
        sales_source = "HANDOFF"
    elif lead and lead.assigned_to:
        sales_employee = db.query(Employee).filter(Employee.id == lead.assigned_to).first()
        sales_source = "LEAD_OWNER" if sales_employee else "UNASSIGNED"

    support_manager = None
    if handoff.support_manager_id:
        support_manager = (
            db.query(Employee)
            .filter(Employee.id == handoff.support_manager_id)
            .first()
        )
    assigned_agent = None
    if handoff.assigned_agent_id:
        assigned_agent = (
            db.query(Employee).filter(Employee.id == handoff.assigned_agent_id).first()
        )

    support_employee = assigned_agent or support_manager
    lead_owner = sales_employee
    if not lead_owner and lead and lead.assigned_to:
        lead_owner = db.query(Employee).filter(Employee.id == lead.assigned_to).first()

    return {
        "id": handoff.id,
        "finance_handoff_id": handoff.finance_handoff_id,
        "lead_id": handoff.lead_id,
        "deal_id": handoff.deal_id,
        "customer_id": handoff.customer_id,
        "customer_name": handoff.customer_name,
        "company_name": handoff.company_name,
        "phone": handoff.phone,
        "email": handoff.email,
        "product_service": handoff.product_service,
        "product_category": handoff.product_category,
        "selected_bundle": handoff.selected_bundle,
        "total_deal_amount": handoff.total_deal_amount,
        "invoice_number": handoff.invoice_number,
        "quotation_number": handoff.quotation_number,
        "payment_status": handoff.payment_status,
        "onboarding_status": handoff.onboarding_status,
        "handover_date": handoff.created_at.isoformat() if handoff.created_at else None,
        "won_at": handoff.won_at.isoformat() if handoff.won_at else None,
        "contacted_at": handoff.contacted_at.isoformat() if handoff.contacted_at else None,
        "completed_at": handoff.completed_at.isoformat() if handoff.completed_at else None,
        "sales_employee_id": handoff.sales_employee_id,
        "sales_employee_name": (
            (sales_employee.name if sales_employee else None)
            or handoff.sales_employee_name
            or "Unassigned"
        ),
        "sales_employee_source": sales_source,
        "support_manager_id": support_manager.id if support_manager else handoff.support_manager_id,
        "support_manager_name": (
            (support_manager.name if support_manager else None)
            or handoff.support_manager_name
            or "Unassigned"
        ),
        "assigned_agent_id": assigned_agent.id if assigned_agent else handoff.assigned_agent_id,
        "assigned_agent_name": (
            (assigned_agent.name if assigned_agent else None)
            or handoff.assigned_agent_name
            or "Unassigned"
        ),
        "support_employee_id": support_employee.id if support_employee else None,
        "support_employee_name": (
            support_employee.name if support_employee else "Unassigned"
        ),
        "lead_owner_id": lead_owner.id if lead_owner else None,
        "lead_owner_name": lead_owner.name if lead_owner else "Unassigned",
        "lead_name": lead.name if lead else None,
        "lead_status": lead.status if lead else None,
        "customer_created_at": (
            handoff.customer.created_at.isoformat()
            if handoff.customer and handoff.customer.created_at
            else None
        ),
    }


def list_support_handovers(
    db: Session,
    *,
    status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
) -> Dict[str, Any]:
    """Read-only Admin Sales -> Support handover monitoring."""
    base_query = db.query(SupportHandoff)

    search_clean = (search or "").strip()
    if search_clean:
        term = f"%{search_clean}%"
        base_query = base_query.outerjoin(Lead, SupportHandoff.lead_id == Lead.id).filter(
            or_(
                SupportHandoff.customer_name.ilike(term),
                SupportHandoff.company_name.ilike(term),
                SupportHandoff.product_service.ilike(term),
                SupportHandoff.phone.ilike(term),
                SupportHandoff.email.ilike(term),
                SupportHandoff.sales_employee_name.ilike(term),
                SupportHandoff.support_manager_name.ilike(term),
                SupportHandoff.assigned_agent_name.ilike(term),
                SupportHandoff.invoice_number.ilike(term),
                SupportHandoff.quotation_number.ilike(term),
                Lead.name.ilike(term),
                Lead.phone.ilike(term),
            )
        )

    status_rows = (
        base_query.with_entities(
            SupportHandoff.onboarding_status,
            func.count(SupportHandoff.id),
        )
        .group_by(SupportHandoff.onboarding_status)
        .all()
    )
    status_counts = {
        (status_name or "UNKNOWN").upper(): int(count)
        for status_name, count in status_rows
    }

    status_clean = (status or "").strip()
    if status_clean and status_clean.upper() != "ALL":
        base_query = base_query.filter(
            func.upper(SupportHandoff.onboarding_status) == status_clean.upper()
        )

    total = base_query.count()

    page_num = max(int(page or 1), 1)
    limit_num = min(max(int(limit or 50), 1), 200)
    records = (
        base_query.order_by(SupportHandoff.created_at.desc(), SupportHandoff.id.desc())
        .offset((page_num - 1) * limit_num)
        .limit(limit_num)
        .all()
    )

    return {
        "total": total,
        "page": page_num,
        "limit": limit_num,
        "status_counts": status_counts,
        "items": [_serialize_handover(db, record) for record in records],
    }
