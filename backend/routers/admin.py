"""Admin-only department segregation endpoints.

These endpoints never create duplicate employees or mutate Sales/Support
dashboard/workflow data. Employee transfers reuse the existing
``PUT /users/{user_id}`` validation path.
"""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from services.auth import require_admin
from services.department_service import (
    create_department_team,
    get_admin_overview,
    get_admin_reports,
    get_company_statistics,
    get_department_statistics,
    list_admin_employees,
    list_department_managers,
    list_department_teams,
    list_support_handovers,
    parse_admin_department,
)

router = APIRouter(prefix="/admin", tags=["Admin Department Segregation"])


class TeamCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    department: str
    manager_id: int
    description: Optional[str] = None


def _normalize_filter(value: Optional[str]) -> Optional[str]:
    try:
        return parse_admin_department(value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _parse_date(value: Optional[str], field_name: str) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must use YYYY-MM-DD format.",
        ) from exc


@router.get("/overview")
def admin_department_overview(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Sales/Support department cards plus combined and company-wide totals.

    Every count is derived from the same Employee.department relationships and
    IDs used by the call-log/follow-up record filters.
    """
    parsed_from = _parse_date(date_from, "date_from")
    parsed_to = _parse_date(date_to, "date_to")
    if parsed_from and parsed_to and parsed_from > parsed_to:
        raise HTTPException(status_code=400, detail="date_from cannot be after date_to.")
    return get_admin_overview(db, parsed_from, parsed_to)


@router.get("/departments")
def admin_departments(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    parsed_from = _parse_date(date_from, "date_from")
    parsed_to = _parse_date(date_to, "date_to")
    if parsed_from and parsed_to and parsed_from > parsed_to:
        raise HTTPException(status_code=400, detail="date_from cannot be after date_to.")
    return {
        "departments": [
            get_department_statistics(db, "SALES", parsed_from, parsed_to),
            get_department_statistics(db, "SUPPORT", parsed_from, parsed_to),
        ],
        "company": get_company_statistics(db, parsed_from, parsed_to),
    }


@router.get("/employees")
def admin_employees(
    department: Optional[str] = Query(None, description="ALL, SALES or SUPPORT"),
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List Sales/Support employees from existing Employee records only."""
    normalized = _normalize_filter(department)
    items = list_admin_employees(
        db,
        department=normalized,
        status=status_filter,
        search=search,
    )
    return {
        "total": len(items),
        "department": normalized or "ALL",
        "items": items,
    }


@router.get("/managers")
def admin_managers(
    department: str = Query(..., description="SALES or SUPPORT"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    normalized = _normalize_filter(department)
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A specific department (SALES or SUPPORT) is required.",
        )
    try:
        items = list_department_managers(db, normalized)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"department": normalized, "items": items, "total": len(items)}


@router.get("/teams")
def admin_teams(
    department: Optional[str] = Query(None, description="ALL, SALES or SUPPORT"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    normalized = _normalize_filter(department)
    teams = list_department_teams(db, [normalized] if normalized else None)
    return {
        "total": len(teams),
        "department": normalized or "ALL",
        "items": teams,
    }


@router.post("/teams", status_code=status.HTTP_201_CREATED)
def admin_create_team(
    payload: TeamCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Register a team under an existing Sales/Support manager.

    Membership is derived from Employee.manager_id, so no employee records are
    created, copied, deleted or reassigned by this endpoint.
    """
    try:
        return create_department_team(
            db,
            name=payload.name,
            department=payload.department,
            manager_id=payload.manager_id,
            description=payload.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/handovers")
def admin_handovers(
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Read-only Sales -> Support handover monitoring.

    Existing customer/lead ownership is preserved; rows with no explicit
    handoff sales_employee_id fall back to the lead owner for display only.
    """
    return list_support_handovers(
        db,
        status=status_filter,
        search=search,
        page=page,
        limit=limit,
    )


@router.get("/reports")
def admin_reports(
    department: Optional[str] = Query(None, description="ALL, SALES or SUPPORT"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Department-wise Admin statistics with the same employee-ID scoping used by
    the Call Logs and Follow-ups department filters.
    """
    normalized = _normalize_filter(department)
    parsed_from = _parse_date(date_from, "date_from")
    parsed_to = _parse_date(date_to, "date_to")
    if parsed_from and parsed_to and parsed_from > parsed_to:
        raise HTTPException(status_code=400, detail="date_from cannot be after date_to.")
    return get_admin_reports(
        db,
        department=normalized,
        date_from=parsed_from,
        date_to=parsed_to,
    )
