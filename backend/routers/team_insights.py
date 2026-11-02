"""Team Insights analytics API.

All values come from ``services.team_insights_service`` so the dashboard,
the KPI drill-downs and the exports share exactly the same definitions.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from services.auth import get_current_user
from services.team_insights_service import (
    CALL_METRICS,
    EMPLOYEE_METRICS,
    FOLLOWUP_METRICS,
    LEAD_METRICS,
    InsightsFilters,
    build_dashboard,
    build_export,
    get_metric_records,
)

router = APIRouter(prefix="/team-insights", tags=["Team Insights"])

KNOWN_METRICS = set(LEAD_METRICS) | set(CALL_METRICS) | set(FOLLOWUP_METRICS) | set(EMPLOYEE_METRICS)


def _filters(
    preset: str = Query("LAST_30_DAYS"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    employee_id: Optional[int] = Query(None),
    department: Optional[str] = Query(None),
    lead_source: Optional[str] = Query(None),
    call_source: Optional[str] = Query(None),
) -> InsightsFilters:
    return InsightsFilters(
        preset=preset,
        start_date=start_date,
        end_date=end_date,
        employee_id=employee_id,
        department=department,
        lead_source=lead_source,
        call_source=call_source,
    )


def _handle(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/dashboard")
def team_insights_dashboard(
    filters: InsightsFilters = Depends(_filters),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Single aggregated payload for the whole Team Insights page."""
    try:
        return build_dashboard(db, current_user, filters)
    except (ValueError, PermissionError) as exc:
        raise _handle(exc)


@router.get("/records")
def team_insights_records(
    metric: str = Query(..., description="KPI key, e.g. total_calls"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    filters: InsightsFilters = Depends(_filters),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Exact record list behind a KPI, using the same filters/period."""
    if metric not in KNOWN_METRICS:
        raise HTTPException(status_code=400, detail=f"Unknown metric '{metric}'.")
    try:
        return get_metric_records(db, current_user, filters, metric, limit=limit, offset=offset)
    except (ValueError, PermissionError) as exc:
        raise _handle(exc)


@router.get("/export")
def team_insights_export(
    dataset: str = Query("employees"),
    format: str = Query("csv"),
    metric: Optional[str] = Query(None),
    filters: InsightsFilters = Depends(_filters),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """CSV/XLSX export using the same aggregation as the dashboard."""
    if metric and metric not in KNOWN_METRICS:
        raise HTTPException(status_code=400, detail=f"Unknown metric '{metric}'.")
    try:
        payload, filename, media_type = build_export(db, current_user, filters, dataset, format, metric)
    except (ValueError, PermissionError) as exc:
        raise _handle(exc)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return Response(
        content=payload,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
