"""Team Insights analytics service.

Single source of truth for the Team Insights dashboard and every KPI
drill-down.  All counts are derived from the CRM tables; no sample or
front-end generated values are used.

Timezone policy
---------------
Operational CRM fields are stored as naive IST (``utils.timezone.get_ist_now``):
``leads.created_at``, ``call_logs.created_at``, ``call_logs.started_at``.

Legacy audit fields use ``datetime.utcnow`` in several routers:
``followups.updated_at`` (completion time), ``lead_status_history.changed_at``.
Those are converted to IST before being shown or filtered.

``lead_assignments.assigned_at`` is mixed (some code paths write IST, some
UTC).  It is only used for the activity timeline; a record is converted from
UTC only when it would otherwise predate its lead's creation time.
"""

from __future__ import annotations

import csv
import io
import re
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session

from models.call_log import CallLog
from models.employee import Employee
from models.followup import Followup
from models.lead import Lead, LeadAssignment, LeadStatusHistory
from models.user import User
from services.hierarchy_service import (
    get_authorized_performance_employee_ids,
    normalize_department,
)
from utils.timezone import get_ist_now

try:  # pragma: no cover - import guard for lightweight test environments
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
except Exception:  # pragma: no cover
    Workbook = None  # type: ignore

IST_OFFSET = timedelta(hours=5, minutes=30)
IST_LABEL = "Asia/Kolkata"

PRESET_LABELS = {
    "TODAY": "Today",
    "YESTERDAY": "Yesterday",
    "LAST_7_DAYS": "Last 7 Days",
    "LAST_30_DAYS": "Last 30 Days",
    "THIS_MONTH": "This Month",
    "PREVIOUS_MONTH": "Previous Month",
    "CUSTOM": "Custom Range",
    "ALL_TIME": "All Time",
}

CONNECTED_CALL_STATUSES = {"ANSWERED", "COMPLETED", "CONNECTED"}
MISSED_CALL_STATUSES = {
    "MISSED",
    "NO_ANSWER",
    "NOANSWER",
    "NO_ANSWERED",
    "UNANSWERED",
    "MISSED_CALL",
}
FAILED_CALL_STATUSES = {
    "FAILED",
    "BUSY",
    "CANCEL",
    "CANCELLED",
    "ERROR",
    "REJECTED",
    "ABORTED",
}

CONVERTED_LEAD_STATUSES = {
    "WON",
    "CONVERTED",
    "CLOSED_WON",
    "PENDING_ONBOARDING",
    "ONBOARDING_IN_PROGRESS",
    "COMPLETED_ONBOARDING",
}
CONTACTED_LEAD_STATUSES = {
    "CONTACTED",
    "FOLLOW_UP",
    "RNR",
    "INTERESTED",
    "QUALIFIED",
    "DEMO",
    "DEMO_MEETING",
    "PROPOSAL_SENT",
    "NEGOTIATION",
    "PENDING_ONBOARDING",
    "ONBOARDING_IN_PROGRESS",
    "COMPLETED_ONBOARDING",
    "WON",
    "CONVERTED",
    "CLOSED_WON",
}
INTERESTED_LEAD_STATUSES = {
    "INTERESTED",
    "QUALIFIED",
    "DEMO",
    "DEMO_MEETING",
    "PROPOSAL_SENT",
    "NEGOTIATION",
    "PENDING_ONBOARDING",
    "ONBOARDING_IN_PROGRESS",
    "COMPLETED_ONBOARDING",
    "WON",
    "CONVERTED",
    "CLOSED_WON",
}
LOST_LEAD_STATUSES = {
    "LOST",
    "LOST_LEAD",
    "NOT_INTERESTED",
    "JUNK",
    "SPAM",
    "INVALID",
    "DEAD",
    "DROPPED",
}

MOBILE_PROVIDERS = {"MOBILE", "MOBILE_SIM", "DIRECT_DIAL", "SIM", "DEVICE"}
DOOCTI_PROVIDERS = {"DOOCTI"}
IVR_PROVIDERS = {"IVR", "TWILIO", "EXOTEL"}

CALL_SOURCE_OPTIONS = [
    {"value": "MOBILE", "label": "Mobile calls", "providers": ["MOBILE", "MOBILE_SIM", "DIRECT_DIAL", "SIM", "DEVICE"]},
    {"value": "DOOCTI", "label": "Doocti calls", "providers": ["DOOCTI"]},
    {"value": "IVR", "label": "IVR calls", "providers": ["IVR", "TWILIO", "EXOTEL"]},
]

METRIC_DEFINITIONS: Dict[str, str] = {
    "total_employees": "All non-test employee records in the signed-in user's performance scope (current snapshot).",
    "active_employees": "Employees with status ACTIVE whose linked user account is also active (current snapshot).",
    "total_assigned_leads": "Unique leads created in the selected period whose current owner is an employee in scope.",
    "new_leads": "Unique leads with created_at inside the selected period (IST).",
    "total_calls": "Unique call_logs rows whose effective call time (started_at, else created_at) is inside the period.",
    "connected_calls": "Calls with a connected status (ANSWERED/COMPLETED/CONNECTED) and duration_seconds > 0.",
    "converted_leads": "Unique leads in the period cohort with a converted CRM status: WON, CONVERTED, CLOSED WON, PENDING_ONBOARDING, ONBOARDING_IN_PROGRESS, COMPLETED_ONBOARDING.",
    "pending_followups": "Follow-ups currently Pending whose scheduled followup_date falls inside the selected period.",
    "assigned_leads": "Unique leads created in the period with assigned_to set to an employee in scope.",
    "unassigned_leads": "Unique leads created in the period with assigned_to NULL (company-wide scope).",
    "contacted_leads": "Unique period-cohort leads whose current CRM status is CONTACTED or later in the sales funnel.",
    "interested_leads": "Unique period-cohort leads whose current CRM status is INTERESTED/QUALIFIED/DEMO/PROPOSAL/NEGOTIATION/onboarding/WON or CONVERTED.",
    "lost_leads": "Unique period-cohort leads whose current CRM status is LOST, LOST_LEAD, NOT_INTERESTED, JUNK, SPAM, INVALID, DEAD or DROPPED.",
    "inbound_calls": "Unique calls whose stored call_direction is INBOUND.",
    "outbound_calls": "Unique calls whose stored call_direction is OUTBOUND.",
    "answered_calls": "Unique calls with a connected status, even when talk duration is zero.",
    "missed_calls": "Unique calls with MISSED/NO_ANSWER/NOANSWER/UNANSWERED status.",
    "failed_calls": "Unique calls with FAILED/BUSY/CANCEL/CANCELLED/ERROR/REJECTED status.",
    "connected_duration_seconds": "Sum of duration_seconds over calls that are connected and have duration_seconds > 0.",
    "avg_connected_duration_seconds": "connected_duration_seconds divided by connected_calls (zero-duration connected calls excluded).",
    "mobile_calls": "Calls whose provider is MOBILE_SIM/DIRECT_DIAL/MOBILE/DEVICE.",
    "doocti_calls": "Calls whose provider is DOOCTI.",
    "completed_followups": "Follow-ups currently Completed whose updated_at (converted from UTC to IST) falls inside the period. The schema has no dedicated completed_at column.",
    "overdue_followups": "Pending follow-ups whose scheduled date/time is before now (IST) and whose scheduled date falls inside the period.",
    "conversion_percentage": "converted_leads / assigned_leads × 100 for the same period cohort; zero when no assigned leads.",
}


# ---------------------------------------------------------------------------
# Small helpers


def _norm(value: Any) -> str:
    """Normalise a status/provider token for comparison only."""
    return re.sub(r"[^A-Z0-9]+", "_", str(value or "").strip().upper()).strip("_")


def _lower(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _ist_now() -> datetime:
    return get_ist_now()


def _utc_to_ist(value: Optional[datetime]) -> Optional[datetime]:
    if not value:
        return None
    return value + IST_OFFSET


def _iso_ist(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    return value.strftime("%Y-%m-%dT%H:%M:%S+05:30")


def _parse_followup_time(value: Optional[str]) -> time:
    raw = (value or "").strip()
    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(raw.upper(), fmt).time()
        except Exception:
            continue
    return time(10, 0)


def _followup_scheduled_at(row: Any) -> Optional[datetime]:
    if not row or not getattr(row, "followup_date", None):
        return None
    return datetime.combine(row.followup_date, _parse_followup_time(getattr(row, "followup_time", None)))


def _pct(part: int, whole: int) -> float:
    return round((part / whole) * 100.0, 1) if whole else 0.0


def _pct_change(current: int, previous: int) -> Optional[float]:
    if previous <= 0:
        return None if current > 0 else 0.0
    return round(((current - previous) / previous) * 100.0, 1)


def _comparison(current: int, previous: int) -> Dict[str, Any]:
    change = _pct_change(current, previous)
    if change is None:
        direction = "up" if current > 0 else "flat"
    elif change > 0:
        direction = "up"
    elif change < 0:
        direction = "down"
    else:
        direction = "flat"
    return {
        "current": current,
        "previous": previous,
        "change_percentage": change,
        "direction": direction,
        "has_baseline": previous > 0,
    }


def _in_clause(column, values: Iterable[str]):
    vals = [v for v in values if v]
    return column.in_(vals) if vals else column.in_(["_never_"])


# ---------------------------------------------------------------------------
# Test/demo exclusion
#
# The CRM has no is_test flag.  These predicates intentionally match only
# unmistakable fixtures, never a normal customer/company name.


def _employee_test_clause():
    email = func.lower(func.coalesce(Employee.email, ""))
    name = func.lower(func.coalesce(Employee.name, ""))
    return or_(
        email.like("%@test.com"),
        email.like("%@example.com"),
        email.like("%@example.org"),
        email.like("%@testsupport.com"),
        name.like("test %"),
        name.like("test-%"),
        name.like("[test]%"),
        name.like("demo %"),
        name.like("sample %"),
        name.like("dummy %"),
    )


def _lead_intrinsic_test_clause():
    email = func.lower(func.coalesce(Lead.email, ""))
    name = func.lower(func.coalesce(Lead.name, ""))
    company = func.lower(func.coalesce(Lead.company, ""))
    return or_(
        email.like("%@test.com"),
        email.like("%@example.com"),
        email.like("%@example.org"),
        email.like("%@testsupport.com"),
        name.like("test %"),
        name.like("test-%"),
        name.like("[test]%"),
        name.like("demo %"),
        name.like("sample %"),
        name.like("dummy %"),
        name.like("%testing corp%"),
        company.like("test corp%"),
        company.like("% test corp%"),
        company.like("demo corp%"),
        company.like("sample corp%"),
    )


# ---------------------------------------------------------------------------
# Filters and periods


@dataclass
class InsightsFilters:
    preset: str = "LAST_30_DAYS"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    employee_id: Optional[int] = None
    department: Optional[str] = None
    lead_source: Optional[str] = None
    call_source: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "preset": self.preset,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "employee_id": self.employee_id,
            "department": self.department,
            "lead_source": self.lead_source,
            "call_source": self.call_source,
        }


@dataclass
class Period:
    preset: str
    label: str
    start: Optional[datetime]
    end: Optional[datetime]
    prev_start: Optional[datetime]
    prev_end: Optional[datetime]
    all_time: bool


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        raise ValueError("Dates must use YYYY-MM-DD format.")


def _day_start(value: date) -> datetime:
    return datetime.combine(value, time.min)


def _day_end(value: date) -> datetime:
    return datetime.combine(value, time.max)


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _month_end(value: date) -> date:
    return value.replace(day=monthrange(value.year, value.month)[1])


def resolve_period(filters: InsightsFilters, now: Optional[datetime] = None) -> Period:
    now = now or _ist_now()
    today = now.date()
    preset = (filters.preset or "LAST_30_DAYS").strip().upper()
    if preset in {"ALL", "ALL_TIME", "NONE"}:
        preset = "ALL_TIME"
    if preset not in PRESET_LABELS:
        preset = "LAST_30_DAYS"

    start: Optional[datetime] = None
    end: Optional[datetime] = None
    prev_start: Optional[datetime] = None
    prev_end: Optional[datetime] = None

    if preset == "ALL_TIME":
        return Period(preset, PRESET_LABELS[preset], None, None, None, None, True)

    if preset == "TODAY":
        start, end = _day_start(today), _day_end(today)
        prev_start, prev_end = _day_start(today - timedelta(days=1)), _day_end(today - timedelta(days=1))
    elif preset == "YESTERDAY":
        yesterday = today - timedelta(days=1)
        start, end = _day_start(yesterday), _day_end(yesterday)
        prev_start, prev_end = _day_start(yesterday - timedelta(days=1)), _day_end(yesterday - timedelta(days=1))
    elif preset == "LAST_7_DAYS":
        start, end = _day_start(today - timedelta(days=6)), _day_end(today)
        prev_start, prev_end = _day_start(today - timedelta(days=13)), _day_end(today - timedelta(days=7))
    elif preset == "LAST_30_DAYS":
        start, end = _day_start(today - timedelta(days=29)), _day_end(today)
        prev_start, prev_end = _day_start(today - timedelta(days=59)), _day_end(today - timedelta(days=30))
    elif preset == "THIS_MONTH":
        start, end = _day_start(_month_start(today)), _day_end(_month_end(today))
        prev_start = _day_start(_month_start(_month_start(today) - timedelta(days=1)))
        prev_end = _day_end(_month_end(prev_start.date()))
    elif preset == "PREVIOUS_MONTH":
        first_this_month = _month_start(today)
        last_prev = first_this_month - timedelta(days=1)
        start, end = _day_start(_month_start(last_prev)), _day_end(_month_end(last_prev))
        prev_start = _day_start(_month_start(_month_start(last_prev) - timedelta(days=1)))
        prev_end = _day_end(_month_end(prev_start.date()))
    elif preset == "CUSTOM":
        start_date = _parse_date(filters.start_date)
        end_date = _parse_date(filters.end_date)
        if not start_date or not end_date:
            raise ValueError("Custom range requires start_date and end_date.")
        if start_date > end_date:
            raise ValueError("start_date cannot be after end_date.")
        start, end = _day_start(start_date), _day_end(end_date)
        span = (end_date - start_date).days + 1
        prev_end = _day_start(start_date) - timedelta(microseconds=1)
        prev_start = _day_start((start_date - timedelta(days=span)))
    else:
        preset = "LAST_30_DAYS"
        start, end = _day_start(today - timedelta(days=29)), _day_end(today)
        prev_start, prev_end = _day_start(today - timedelta(days=59)), _day_end(today - timedelta(days=30))

    return Period(preset, PRESET_LABELS.get(preset, preset), start, end, prev_start, prev_end, False)


# ---------------------------------------------------------------------------
# Authorisation scope


@dataclass
class Scope:
    filters: InsightsFilters
    employees: List[Employee]
    employee_ids: Optional[List[int]]
    restrict_to_employees: bool
    include_unassigned: bool
    authorized_ids: Optional[List[int]]
    employee_by_id: Dict[int, Employee]
    db: Session


def _department_values(value: Optional[str]) -> List[str]:
    """All stored spellings that represent one normalised department."""
    dept = normalize_department(value) or (value or "").strip().upper()
    aliases = {
        "ADMINISTRATION": ["ADMINISTRATION", "ADMIN"],
        "FINANCE": ["FINANCE", "ACCOUNTS"],
        "SALES": ["SALES", "SALE"],
        "SUPPORT": ["SUPPORT"],
    }
    return aliases.get(dept, [dept])


def _load_scope(db: Session, user: User, filters: InsightsFilters) -> Scope:
    authorized_ids = get_authorized_performance_employee_ids(user, db)

    q = (
        db.query(Employee)
        .outerjoin(User, User.id == Employee.user_id)
        .filter(~_employee_test_clause())
    )
    if authorized_ids is not None:
        q = q.filter(Employee.id.in_(authorized_ids))
    if filters.employee_id:
        q = q.filter(Employee.id == filters.employee_id)
    if filters.department:
        values = _department_values(filters.department)
        q = q.filter(
            func.upper(
                func.coalesce(Employee.department, User.department, "")
            ).in_(values)
        )

    employees = q.order_by(Employee.name.asc()).all()

    if filters.employee_id:
        if authorized_ids is not None and filters.employee_id not in authorized_ids:
            raise PermissionError("You are not authorised to view this employee's performance.")
        if not employees:
            raise ValueError("Employee not found in your performance scope.")

    restrict = bool(filters.employee_id or filters.department or authorized_ids is not None)
    employee_ids = [e.id for e in employees] if restrict else None
    include_unassigned = not restrict

    return Scope(
        filters=filters,
        employees=employees,
        employee_ids=employee_ids,
        restrict_to_employees=restrict,
        include_unassigned=include_unassigned,
        authorized_ids=authorized_ids,
        employee_by_id={e.id: e for e in employees},
        db=db,
    )


# ---------------------------------------------------------------------------
# Query conditions


def _test_employee_subquery(db: Session):
    return db.query(Employee.id).filter(_employee_test_clause())


def _test_lead_subquery(db: Session):
    return db.query(Lead.id).filter(
        or_(
            _lead_intrinsic_test_clause(),
            Lead.assigned_to.in_(_test_employee_subquery(db)),
        )
    )


def _call_source_providers(call_source: Optional[str]) -> List[str]:
    if not call_source:
        return []
    token = _norm(call_source)
    for option in CALL_SOURCE_OPTIONS:
        if _norm(option["value"]) == token:
            return list(option["providers"])
    return [call_source]


def _effective_call_time():
    return func.coalesce(CallLog.started_at, CallLog.created_at)


def _call_source_lead_subquery(db: Session, scope: Scope, period: Period):
    """Lead ids having at least one call of the selected source in scope/period."""
    providers = _call_source_providers(scope.filters.call_source)
    if not providers:
        return None
    q = db.query(CallLog.lead_id).filter(
        CallLog.lead_id.isnot(None),
        or_(
            CallLog.employee_id.is_(None),
            ~CallLog.employee_id.in_(_test_employee_subquery(db)),
        ),
        CallLog.provider.in_(providers),
    )
    if scope.restrict_to_employees:
        q = q.filter(CallLog.employee_id.in_(scope.employee_ids or [-1]))
    if period.start and period.end:
        q = q.filter(_effective_call_time().between(period.start, period.end))
    return q.distinct()


def _lead_conditions(db: Session, scope: Scope, period: Period) -> List[Any]:
    conditions: List[Any] = [~Lead.id.in_(_test_lead_subquery(db))]
    if scope.restrict_to_employees:
        conditions.append(Lead.assigned_to.in_(scope.employee_ids or [-1]))
    if scope.filters.lead_source:
        conditions.append(func.lower(Lead.source) == _lower(scope.filters.lead_source))
    if period.start and period.end:
        conditions.append(Lead.created_at.between(period.start, period.end))
    if scope.filters.call_source:
        sub = _call_source_lead_subquery(db, scope, period)
        conditions.append(Lead.id.in_(sub))
    return conditions


def _call_conditions(db: Session, scope: Scope, period: Period) -> List[Any]:
    conditions: List[Any] = [
        or_(
            CallLog.employee_id.is_(None),
            ~CallLog.employee_id.in_(_test_employee_subquery(db)),
        ),
        or_(
            CallLog.lead_id.is_(None),
            ~CallLog.lead_id.in_(_test_lead_subquery(db)),
        ),
    ]
    if scope.restrict_to_employees:
        conditions.append(CallLog.employee_id.in_(scope.employee_ids or [-1]))
    providers = _call_source_providers(scope.filters.call_source)
    if providers:
        conditions.append(CallLog.provider.in_(providers))
    if period.start and period.end:
        conditions.append(_effective_call_time().between(period.start, period.end))
    if scope.filters.lead_source:
        lead_ids = db.query(Lead.id).filter(
            ~Lead.id.in_(_test_lead_subquery(db)),
            func.lower(Lead.source) == _lower(scope.filters.lead_source),
        )
        conditions.append(CallLog.lead_id.in_(lead_ids))
    return conditions


def _followup_conditions(db: Session, scope: Scope) -> List[Any]:
    conditions: List[Any] = [
        ~Followup.assigned_to.in_(_test_employee_subquery(db)),
        ~Followup.lead_id.in_(_test_lead_subquery(db)),
    ]
    if scope.restrict_to_employees:
        conditions.append(Followup.assigned_to.in_(scope.employee_ids or [-1]))
    if scope.filters.lead_source:
        lead_ids = db.query(Lead.id).filter(
            ~Lead.id.in_(_test_lead_subquery(db)),
            func.lower(Lead.source) == _lower(scope.filters.lead_source),
        )
        conditions.append(Followup.lead_id.in_(lead_ids))
    if scope.filters.call_source:
        sub = _call_source_lead_subquery(db, scope, Period("ALL_TIME", "All Time", None, None, None, None, True))
        conditions.append(Followup.lead_id.in_(sub))
    return conditions


# ---------------------------------------------------------------------------
# Snapshot aggregation


def _empty_lead_stats() -> Dict[str, int]:
    return {
        "new": 0,
        "assigned": 0,
        "unassigned": 0,
        "contacted": 0,
        "interested": 0,
        "converted": 0,
        "lost": 0,
    }


def _empty_call_stats() -> Dict[str, int]:
    return {
        "total": 0,
        "inbound": 0,
        "outbound": 0,
        "answered": 0,
        "connected": 0,
        "missed": 0,
        "failed": 0,
        "mobile": 0,
        "doocti": 0,
        "ivr": 0,
        "other": 0,
        "duration": 0,
    }


def _classify_lead(status: str) -> Dict[str, bool]:
    token = _norm(status)
    return {
        "contacted": token in CONTACTED_LEAD_STATUSES,
        "interested": token in INTERESTED_LEAD_STATUSES,
        "converted": token in CONVERTED_LEAD_STATUSES,
        "lost": token in LOST_LEAD_STATUSES,
    }


def _classify_call(status: str, provider: str) -> Dict[str, bool]:
    token = _norm(status)
    provider_token = _norm(provider)
    return {
        "answered": token in CONNECTED_CALL_STATUSES,
        "connected_status": token in CONNECTED_CALL_STATUSES,
        "missed": token in MISSED_CALL_STATUSES,
        "failed": token in FAILED_CALL_STATUSES,
        "mobile": provider_token in MOBILE_PROVIDERS,
        "doocti": provider_token in DOOCTI_PROVIDERS,
        "ivr": provider_token in IVR_PROVIDERS,
    }


@dataclass
class Snapshot:
    leads: Dict[str, int] = field(default_factory=_empty_lead_stats)
    lead_by_employee: Dict[int, Dict[str, int]] = field(default_factory=dict)
    lead_by_source: Dict[str, Dict[str, int]] = field(default_factory=dict)
    calls: Dict[str, int] = field(default_factory=_empty_call_stats)
    call_by_employee: Dict[int, Dict[str, int]] = field(default_factory=dict)
    followup_completed: int = 0
    followup_pending: int = 0
    followup_overdue: int = 0
    followup_by_employee: Dict[int, Dict[str, int]] = field(default_factory=dict)
    pending_rows: List[Any] = field(default_factory=list)


def _employee_id(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def _compute_snapshot(db: Session, scope: Scope, period: Period) -> Snapshot:
    snapshot = Snapshot()

    # ---- leads ---------------------------------------------------------
    lead_rows = (
        db.query(Lead.assigned_to, Lead.source, Lead.status, func.count(Lead.id))
        .filter(*_lead_conditions(db, scope, period))
        .group_by(Lead.assigned_to, Lead.source, Lead.status)
        .all()
    )
    for assigned_to, source, status, count in lead_rows:
        count = int(count or 0)
        emp_id = _employee_id(assigned_to)
        src = (source or "Unknown").strip() or "Unknown"
        flags = _classify_lead(status)

        snapshot.leads["new"] += count
        if emp_id is None:
            snapshot.leads["unassigned"] += count
        else:
            snapshot.leads["assigned"] += count
            emp = snapshot.lead_by_employee.setdefault(emp_id, _empty_lead_stats())
            emp["new"] += count
            emp["assigned"] += count
            for key in ("contacted", "interested", "converted", "lost"):
                if flags[key]:
                    emp[key] += count
        for key in ("contacted", "interested", "converted", "lost"):
            if flags[key]:
                snapshot.leads[key] += count

        src_stats = snapshot.lead_by_source.setdefault(src, _empty_lead_stats())
        src_stats["new"] += count
        if emp_id is None:
            src_stats["unassigned"] += count
        else:
            src_stats["assigned"] += count
        for key in ("contacted", "interested", "converted", "lost"):
            if flags[key]:
                src_stats[key] += count

    # ---- calls ---------------------------------------------------------
    positive_duration = case((CallLog.duration_seconds > 0, 1), else_=0)
    call_rows = (
        db.query(
            CallLog.employee_id,
            CallLog.provider,
            func.upper(CallLog.call_direction),
            func.upper(CallLog.call_status),
            positive_duration,
            func.count(CallLog.id),
            func.coalesce(func.sum(CallLog.duration_seconds), 0),
        )
        .filter(*_call_conditions(db, scope, period))
        .group_by(
            CallLog.employee_id,
            CallLog.provider,
            func.upper(CallLog.call_direction),
            func.upper(CallLog.call_status),
            positive_duration,
        )
        .all()
    )
    for emp_value, provider, direction, status, has_duration, count, duration in call_rows:
        count = int(count or 0)
        duration = int(duration or 0)
        emp_id = _employee_id(emp_value)
        flags = _classify_call(status, provider)
        direction_token = _norm(direction)
        is_connected = flags["connected_status"] and int(has_duration or 0) == 1

        targets = [snapshot.calls]
        if emp_id is not None:
            targets.append(snapshot.call_by_employee.setdefault(emp_id, _empty_call_stats()))
        for target in targets:
            target["total"] += count
            if direction_token == "INBOUND":
                target["inbound"] += count
            elif direction_token == "OUTBOUND":
                target["outbound"] += count
            if flags["connected_status"]:
                target["answered"] += count
            if is_connected:
                target["connected"] += count
                target["duration"] += duration
            if flags["missed"]:
                target["missed"] += count
            if flags["failed"]:
                target["failed"] += count
            if flags["mobile"]:
                target["mobile"] += count
            if flags["doocti"]:
                target["doocti"] += count
            if flags["ivr"]:
                target["ivr"] += count
            if not (flags["mobile"] or flags["doocti"] or flags["ivr"]):
                target["other"] += count

    # ---- follow-ups ----------------------------------------------------
    base_conditions = _followup_conditions(db, scope)

    pending_q = db.query(Followup).filter(*base_conditions, func.lower(Followup.status) == "pending")
    if period.start and period.end:
        pending_q = pending_q.filter(Followup.followup_date.between(period.start.date(), period.end.date()))
    pending = pending_q.order_by(Followup.followup_date.asc(), Followup.followup_time.asc()).all()
    now = _ist_now()
    for row in pending:
        emp_id = _employee_id(row.assigned_to)
        scheduled = _followup_scheduled_at(row)
        overdue = bool(scheduled and scheduled < now)
        snapshot.followup_pending += 1
        if overdue:
            snapshot.followup_overdue += 1
        if emp_id is not None:
            emp = snapshot.followup_by_employee.setdefault(emp_id, {"completed": 0, "pending": 0, "overdue": 0})
            emp["pending"] += 1
            if overdue:
                emp["overdue"] += 1
    snapshot.pending_rows = pending

    completed_q = db.query(Followup.assigned_to, func.count(Followup.id)).filter(
        *base_conditions, func.lower(Followup.status) == "completed"
    )
    if period.start and period.end:
        # followups.updated_at is UTC by model default.
        completed_q = completed_q.filter(
            Followup.updated_at.between(period.start - IST_OFFSET, period.end - IST_OFFSET)
        )
    for emp_value, count in completed_q.group_by(Followup.assigned_to).all():
        count = int(count or 0)
        snapshot.followup_completed += count
        emp_id = _employee_id(emp_value)
        if emp_id is not None:
            emp = snapshot.followup_by_employee.setdefault(emp_id, {"completed": 0, "pending": 0, "overdue": 0})
            emp["completed"] += count

    return snapshot


# ---------------------------------------------------------------------------
# Employee performance rows


def _employee_row_base(employee: Employee) -> Dict[str, Any]:
    department = employee.department
    if not department and employee.user:
        department = employee.user.department
    return {
        "employee_id": employee.id,
        "name": employee.name,
        "email": employee.email,
        "photo_url": employee.photo_url,
        "role": employee.role,
        "department": normalize_department(department) or department or "UNASSIGNED",
        "status": employee.status,
        "user_active": bool(employee.user.is_active) if employee.user is not None else True,
        "assigned_leads": 0,
        "contacted_leads": 0,
        "converted_leads": 0,
        "lost_leads": 0,
        "total_calls": 0,
        "inbound_calls": 0,
        "outbound_calls": 0,
        "connected_calls": 0,
        "answered_calls": 0,
        "missed_calls": 0,
        "failed_calls": 0,
        "mobile_calls": 0,
        "doocti_calls": 0,
        "followups_completed": 0,
        "pending_followups": 0,
        "overdue_followups": 0,
        "connected_duration_seconds": 0,
        "avg_duration_seconds": 0,
        "conversion_percentage": 0.0,
        "rank": 0,
        "performance_band": "No leads",
    }


def _build_employee_rows(scope: Scope, snapshot: Snapshot) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for employee in scope.employees:
        row = _employee_row_base(employee)
        lead_stats = snapshot.lead_by_employee.get(employee.id, _empty_lead_stats())
        call_stats = snapshot.call_by_employee.get(employee.id, _empty_call_stats())
        followup_stats = snapshot.followup_by_employee.get(employee.id, {"completed": 0, "pending": 0, "overdue": 0})

        row.update(
            {
                "assigned_leads": lead_stats["assigned"],
                "contacted_leads": lead_stats["contacted"],
                "converted_leads": lead_stats["converted"],
                "lost_leads": lead_stats["lost"],
                "total_calls": call_stats["total"],
                "inbound_calls": call_stats["inbound"],
                "outbound_calls": call_stats["outbound"],
                "connected_calls": call_stats["connected"],
                "answered_calls": call_stats["answered"],
                "missed_calls": call_stats["missed"],
                "failed_calls": call_stats["failed"],
                "mobile_calls": call_stats["mobile"],
                "doocti_calls": call_stats["doocti"],
                "followups_completed": followup_stats["completed"],
                "pending_followups": followup_stats["pending"],
                "overdue_followups": followup_stats["overdue"],
                "connected_duration_seconds": call_stats["duration"],
                "avg_duration_seconds": round(call_stats["duration"] / call_stats["connected"]) if call_stats["connected"] else 0,
                "conversion_percentage": _pct(lead_stats["converted"], lead_stats["assigned"]),
            }
        )
        rows.append(row)

    rows.sort(
        key=lambda r: (
            r["converted_leads"],
            r["connected_calls"],
            r["assigned_leads"],
            r["total_calls"],
            r["name"].lower(),
        ),
        reverse=True,
    )

    average_rate = round(
        sum(r["conversion_percentage"] for r in rows) / len(rows), 1
    ) if rows else 0.0

    for index, row in enumerate(rows, start=1):
        row["rank"] = index
        if row["assigned_leads"] == 0:
            row["performance_band"] = "No leads"
        elif average_rate <= 0 and row["converted_leads"] == 0:
            row["performance_band"] = "Building pipeline"
        elif row["conversion_percentage"] >= average_rate + 5:
            row["performance_band"] = "Strong"
        elif row["conversion_percentage"] <= average_rate - 5:
            row["performance_band"] = "Needs attention"
        else:
            row["performance_band"] = "On track"

    return rows


# ---------------------------------------------------------------------------
# Conversion trend


def _bucket_spec(period: Period, min_date: Optional[date], max_date: Optional[date]) -> Tuple[str, List[str]]:
    if period.all_time:
        if not min_date or not max_date:
            return "month", []
        start = _month_start(min_date)
        end = _month_start(max_date)
        months = []
        cursor = start
        while cursor <= end and len(months) < 36:
            months.append(cursor.strftime("%Y-%m"))
            cursor = _month_start((cursor.replace(day=28) + timedelta(days=4)))
        return "month", months

    assert period.start is not None and period.end is not None
    span = (period.end.date() - period.start.date()).days + 1
    if span <= 62:
        days = []
        cursor = period.start.date()
        while cursor <= period.end.date():
            days.append(cursor.strftime("%Y-%m-%d"))
            cursor += timedelta(days=1)
        return "day", days

    months = []
    cursor = _month_start(period.start.date())
    end_month = _month_start(period.end.date())
    while cursor <= end_month:
        months.append(cursor.strftime("%Y-%m"))
        cursor = _month_start(cursor.replace(day=28) + timedelta(days=4))
    return "month", months


def _build_conversion_trend(db: Session, scope: Scope, period: Period) -> List[Dict[str, Any]]:
    conditions = _lead_conditions(db, scope, period)
    min_date, max_date = db.query(func.min(Lead.created_at), func.max(Lead.created_at)).filter(*conditions).one()
    min_date = min_date.date() if isinstance(min_date, datetime) else min_date
    max_date = max_date.date() if isinstance(max_date, datetime) else max_date
    granularity, buckets = _bucket_spec(period, min_date, max_date)
    if not buckets:
        return []

    if granularity == "day":
        bucket_expr = func.date(Lead.created_at)
    else:
        bucket_expr = func.date_format(Lead.created_at, "%Y-%m")

    rows = (
        db.query(bucket_expr, Lead.status, func.count(Lead.id))
        .filter(*conditions)
        .group_by(bucket_expr, Lead.status)
        .all()
    )
    data: Dict[str, Dict[str, int]] = {
        b: {"new_leads": 0, "converted_leads": 0} for b in buckets
    }
    for bucket, status, count in rows:
        key = str(bucket)
        if key not in data:
            continue
        data[key]["new_leads"] += int(count or 0)
        if _norm(status) in CONVERTED_LEAD_STATUSES:
            data[key]["converted_leads"] += int(count or 0)

    trend = []
    for bucket in buckets:
        stats = data[bucket]
        try:
            if granularity == "day":
                label = datetime.strptime(bucket, "%Y-%m-%d").strftime("%d %b")
            else:
                label = datetime.strptime(bucket, "%Y-%m").strftime("%b %Y")
        except Exception:
            label = bucket
        trend.append(
            {
                "bucket": bucket,
                "label": label,
                "new_leads": stats["new_leads"],
                "converted_leads": stats["converted_leads"],
                "conversion_rate": _pct(stats["converted_leads"], stats["new_leads"]),
            }
        )
    return trend


# ---------------------------------------------------------------------------
# Timeline


def _timeline_timestamp(value: Optional[datetime], source: str, lead_created_at: Optional[datetime] = None) -> Optional[datetime]:
    if not value:
        return None
    if source in {"assignment", "status", "followup"}:
        # These legacy audit fields are UTC by default.
        if source == "assignment" and lead_created_at and value >= lead_created_at:
            # Several lead-creation paths write IST into assigned_at.
            return value
        return _utc_to_ist(value)
    return value


def _build_timeline(db: Session, scope: Scope, period: Period, limit: int = 60) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    lead_conditions = _lead_conditions(db, scope, period)
    call_conditions = _call_conditions(db, scope, period)
    followup_conditions = _followup_conditions(db, scope)
    test_lead_ids = _test_lead_subquery(db)

    # Lead creation
    lead_rows = (
        db.query(Lead.id, Lead.name, Lead.assigned_to, Lead.created_at, Lead.status, Lead.source)
        .filter(*lead_conditions)
        .order_by(Lead.created_at.desc())
        .limit(limit)
        .all()
    )
    for lead_id, lead_name, assigned_to, created_at, status, source in lead_rows:
        emp_id = _employee_id(assigned_to)
        employee = scope.employee_by_id.get(emp_id) if emp_id else None
        events.append(
            {
                "id": f"lead-created-{lead_id}",
                "event_type": "LEAD_CREATED",
                "timestamp": _iso_ist(_timeline_timestamp(created_at, "lead")),
                "employee_id": emp_id,
                "employee_name": employee.name if employee else "Unassigned",
                "lead_id": lead_id,
                "lead_name": lead_name,
                "title": "New lead created",
                "description": f"{lead_name} · {source or 'Unknown source'} · {status or 'NEW'}",
            }
        )

    # Lead assignment
    asg_q = (
        db.query(LeadAssignment.id, LeadAssignment.lead_id, LeadAssignment.assigned_to, LeadAssignment.assigned_at, Lead.name, Lead.created_at)
        .join(Lead, Lead.id == LeadAssignment.lead_id)
        .filter(
            ~Lead.id.in_(test_lead_ids),
            ~LeadAssignment.assigned_to.in_(_test_employee_subquery(db)),
            LeadAssignment.assigned_to.isnot(None),
        )
    )
    if scope.restrict_to_employees:
        asg_q = asg_q.filter(LeadAssignment.assigned_to.in_(scope.employee_ids or [-1]))
    if scope.filters.lead_source:
        asg_q = asg_q.filter(func.lower(Lead.source) == _lower(scope.filters.lead_source))
    if scope.filters.call_source:
        asg_q = asg_q.filter(Lead.id.in_(_call_source_lead_subquery(db, scope, period)))
    if period.start and period.end:
        asg_q = asg_q.filter(
            LeadAssignment.assigned_at.between(period.start - IST_OFFSET, period.end - IST_OFFSET)
        )
    for asg_id, lead_id, assigned_to, assigned_at, lead_name, lead_created_at in asg_q.order_by(LeadAssignment.assigned_at.desc()).limit(limit).all():
        emp_id = _employee_id(assigned_to)
        employee = scope.employee_by_id.get(emp_id) if emp_id else None
        ts = _timeline_timestamp(assigned_at, "assignment", lead_created_at)
        events.append(
            {
                "id": f"lead-assigned-{asg_id}",
                "event_type": "LEAD_ASSIGNED",
                "timestamp": _iso_ist(ts),
                "employee_id": emp_id,
                "employee_name": employee.name if employee else "Unassigned",
                "lead_id": lead_id,
                "lead_name": lead_name,
                "title": "Lead assigned",
                "description": f"{lead_name} assigned to {employee.name if employee else 'an employee'}",
            }
        )

    # Calls
    call_rows = (
        db.query(
            CallLog.id,
            CallLog.employee_id,
            CallLog.lead_id,
            CallLog.call_direction,
            CallLog.call_status,
            CallLog.provider,
            CallLog.duration_seconds,
            _effective_call_time().label("effective_at"),
        )
        .filter(*call_conditions)
        .order_by(_effective_call_time().desc())
        .limit(limit)
        .all()
    )
    for call_id, emp_value, lead_id, direction, status, provider, duration, effective_at in call_rows:
        emp_id = _employee_id(emp_value)
        employee = scope.employee_by_id.get(emp_id) if emp_id else None
        lead_name = None
        if lead_id:
            lead_name = db.query(Lead.name).filter(Lead.id == lead_id).scalar()
        events.append(
            {
                "id": f"call-{call_id}",
                "event_type": "CALL",
                "timestamp": _iso_ist(_timeline_timestamp(effective_at, "call")),
                "employee_id": emp_id,
                "employee_name": employee.name if employee else "Unattributed",
                "lead_id": lead_id,
                "lead_name": lead_name,
                "title": f"{(direction or 'OUTBOUND').title()} call · {(status or '').replace('_', ' ').title()}",
                "description": f"{provider or 'Call'} · {int(duration or 0)}s" + (f" · {lead_name}" if lead_name else ""),
            }
        )

    # Follow-up completion
    fu_q = (
        db.query(Followup.id, Followup.lead_id, Followup.assigned_to, Followup.updated_at, Lead.name)
        .join(Lead, Lead.id == Followup.lead_id)
        .filter(*followup_conditions, func.lower(Followup.status) == "completed")
    )
    if period.start and period.end:
        fu_q = fu_q.filter(Followup.updated_at.between(period.start - IST_OFFSET, period.end - IST_OFFSET))
    for fu_id, lead_id, assigned_to, updated_at, lead_name in fu_q.order_by(Followup.updated_at.desc()).limit(limit).all():
        emp_id = _employee_id(assigned_to)
        employee = scope.employee_by_id.get(emp_id) if emp_id else None
        events.append(
            {
                "id": f"followup-completed-{fu_id}",
                "event_type": "FOLLOWUP_COMPLETED",
                "timestamp": _iso_ist(_utc_to_ist(updated_at)),
                "employee_id": emp_id,
                "employee_name": employee.name if employee else "Unassigned",
                "lead_id": lead_id,
                "lead_name": lead_name,
                "title": "Follow-up completed",
                "description": f"Follow-up for {lead_name} marked completed",
            }
        )

    # Status changes
    status_q = (
        db.query(
            LeadStatusHistory.id,
            LeadStatusHistory.lead_id,
            LeadStatusHistory.old_status,
            LeadStatusHistory.new_status,
            LeadStatusHistory.changed_by,
            LeadStatusHistory.changed_at,
            Lead.name,
            Lead.assigned_to,
        )
        .join(Lead, Lead.id == LeadStatusHistory.lead_id)
        .filter(~Lead.id.in_(test_lead_ids))
    )
    if scope.restrict_to_employees:
        status_q = status_q.filter(
            or_(
                LeadStatusHistory.changed_by.in_(scope.employee_ids or [-1]),
                Lead.assigned_to.in_(scope.employee_ids or [-1]),
            )
        )
    if scope.filters.lead_source:
        status_q = status_q.filter(func.lower(Lead.source) == _lower(scope.filters.lead_source))
    if scope.filters.call_source:
        status_q = status_q.filter(Lead.id.in_(_call_source_lead_subquery(db, scope, period)))
    if period.start and period.end:
        status_q = status_q.filter(
            LeadStatusHistory.changed_at.between(period.start - IST_OFFSET, period.end - IST_OFFSET)
        )
    for hist_id, lead_id, old_status, new_status, changed_by, changed_at, lead_name, lead_assigned in status_q.order_by(LeadStatusHistory.changed_at.desc()).limit(limit).all():
        emp_id = _employee_id(changed_by) or _employee_id(lead_assigned)
        employee = scope.employee_by_id.get(emp_id) if emp_id else None
        events.append(
            {
                "id": f"status-{hist_id}",
                "event_type": "STATUS_CHANGED",
                "timestamp": _iso_ist(_utc_to_ist(changed_at)),
                "employee_id": emp_id,
                "employee_name": employee.name if employee else "Unattributed",
                "lead_id": lead_id,
                "lead_name": lead_name,
                "title": "Lead status changed",
                "description": f"{lead_name}: {old_status or '—'} → {new_status}",
            }
        )

    events.sort(key=lambda e: e.get("timestamp") or "", reverse=True)
    return events[:limit]


# ---------------------------------------------------------------------------
# Filter options and definitions


def _filter_options(db: Session, user: User) -> Dict[str, Any]:
    authorized_ids = get_authorized_performance_employee_ids(user, db)
    eq = (
        db.query(Employee)
        .outerjoin(User, User.id == Employee.user_id)
        .filter(~_employee_test_clause())
    )
    if authorized_ids is not None:
        eq = eq.filter(Employee.id.in_(authorized_ids))
    employees = eq.order_by(Employee.name.asc()).all()

    departments = sorted(
        {
            normalize_department(e.department or (e.user.department if e.user else None)) or "UNASSIGNED"
            for e in employees
        }
    )

    lq = db.query(Lead.source).filter(~Lead.id.in_(_test_lead_subquery(db)))
    if authorized_ids is not None:
        lq = lq.filter(Lead.assigned_to.in_(authorized_ids))
    lead_sources = sorted({(s or "Unknown") for (s,) in lq.distinct().all()}, key=lambda s: s.lower())

    cq = db.query(CallLog.provider).filter(
        or_(
            CallLog.employee_id.is_(None),
            ~CallLog.employee_id.in_(_test_employee_subquery(db)),
        )
    )
    if authorized_ids is not None:
        cq = cq.filter(CallLog.employee_id.in_(authorized_ids))
    providers = {_norm(p) for (p,) in cq.distinct().all() if p}

    call_sources = []
    for option in CALL_SOURCE_OPTIONS:
        if any(p in providers for p in (_norm(x) for x in option["providers"])):
            call_sources.append({"value": option["value"], "label": option["label"]})
    known = {_norm(o["value"]) for o in call_sources}
    for provider in sorted(providers):
        if provider not in known and provider not in {"MOBILE_SIM", "DIRECT_DIAL", "SIM", "DEVICE", "TWILIO", "EXOTEL"}:
            call_sources.append({"value": provider, "label": provider.replace("_", " ").title()})

    return {
        "employees": [
            {
                "id": e.id,
                "name": e.name,
                "role": e.role,
                "department": normalize_department(e.department or (e.user.department if e.user else None)) or "UNASSIGNED",
                "status": e.status,
            }
            for e in employees
        ],
        "departments": departments,
        "lead_sources": lead_sources,
        "call_sources": call_sources,
    }


# ---------------------------------------------------------------------------
# Public builder


def build_dashboard(db: Session, user: User, filters: InsightsFilters) -> Dict[str, Any]:
    period = resolve_period(filters)
    scope = _load_scope(db, user, filters)
    snapshot = _compute_snapshot(db, scope, period)
    previous = None
    if period.prev_start and period.prev_end:
        previous = _compute_snapshot(
            db,
            scope,
            Period("PREVIOUS", "Previous period", period.prev_start, period.prev_end, None, None, False),
        )

    employees = _build_employee_rows(scope, snapshot)

    active_employees = sum(
        1 for e in scope.employees if (e.status or "").upper() == "ACTIVE" and (e.user.is_active if e.user else True)
    )

    def cmp(metric: str) -> Dict[str, Any]:
        cur = int(snapshot.calls.get(metric, snapshot.leads.get(metric, 0)))
        prev = int(previous.calls.get(metric, previous.leads.get(metric, 0))) if previous else 0
        return _comparison(cur, prev)

    overview = {
        "total_employees": len(scope.employees),
        "active_employees": active_employees,
        "total_assigned_leads": snapshot.leads["assigned"],
        "new_leads": snapshot.leads["new"],
        "total_calls": snapshot.calls["total"],
        "connected_calls": snapshot.calls["connected"],
        "converted_leads": snapshot.leads["converted"],
        "pending_followups": snapshot.followup_pending,
        "comparison": {
            "new_leads": _comparison(snapshot.leads["new"], previous.leads["new"] if previous else 0),
            "total_calls": _comparison(snapshot.calls["total"], previous.calls["total"] if previous else 0),
            "connected_calls": _comparison(snapshot.calls["connected"], previous.calls["connected"] if previous else 0),
            "converted_leads": _comparison(snapshot.leads["converted"], previous.leads["converted"] if previous else 0),
            "pending_followups": _comparison(snapshot.followup_pending, previous.followup_pending if previous else 0),
        },
    }

    lead_analytics = {
        "new_leads": snapshot.leads["new"],
        "assigned_leads": snapshot.leads["assigned"],
        "unassigned_leads": snapshot.leads["unassigned"],
        "contacted_leads": snapshot.leads["contacted"],
        "interested_leads": snapshot.leads["interested"],
        "converted_leads": snapshot.leads["converted"],
        "lost_leads": snapshot.leads["lost"],
        "conversion_percentage": _pct(snapshot.leads["converted"], snapshot.leads["assigned"]),
    }

    call_analytics = {
        "total_calls": snapshot.calls["total"],
        "inbound_calls": snapshot.calls["inbound"],
        "outbound_calls": snapshot.calls["outbound"],
        "answered_calls": snapshot.calls["answered"],
        "connected_calls": snapshot.calls["connected"],
        "missed_calls": snapshot.calls["missed"],
        "failed_calls": snapshot.calls["failed"],
        "connected_duration_seconds": snapshot.calls["duration"],
        "avg_connected_duration_seconds": round(snapshot.calls["duration"] / snapshot.calls["connected"]) if snapshot.calls["connected"] else 0,
        "mobile_calls": snapshot.calls["mobile"],
        "doocti_calls": snapshot.calls["doocti"],
        "ivr_calls": snapshot.calls["ivr"],
        "other_calls": snapshot.calls["other"],
        "answer_rate": _pct(snapshot.calls["answered"], snapshot.calls["total"]),
    }

    followup_by_employee = []
    for employee in scope.employees:
        stats = snapshot.followup_by_employee.get(employee.id, {"completed": 0, "pending": 0, "overdue": 0})
        total = stats["completed"] + stats["pending"]
        followup_by_employee.append(
            {
                "employee_id": employee.id,
                "name": employee.name,
                "department": normalize_department(employee.department or (employee.user.department if employee.user else None)) or "UNASSIGNED",
                **stats,
                "completion_rate": _pct(stats["completed"], total),
            }
        )

    followup_denominator = snapshot.followup_completed + snapshot.followup_pending
    followup_analytics = {
        "completed_followups": snapshot.followup_completed,
        "pending_followups": snapshot.followup_pending,
        "overdue_followups": snapshot.followup_overdue,
        "completion_rate": _pct(snapshot.followup_completed, followup_denominator),
        "by_employee": followup_by_employee,
    }

    conversion_employees = [
        {
            "employee_id": row["employee_id"],
            "name": row["name"],
            "department": row["department"],
            "assigned_leads": row["assigned_leads"],
            "converted_leads": row["converted_leads"],
            "conversion_percentage": row["conversion_percentage"],
        }
        for row in employees
    ]
    conversion_sources = []
    for source, stats in snapshot.lead_by_source.items():
        conversion_sources.append(
            {
                "source": source,
                "assigned_leads": stats["assigned"],
                "converted_leads": stats["converted"],
                "conversion_percentage": _pct(stats["converted"], stats["assigned"]),
            }
        )
    conversion_sources.sort(key=lambda r: (r["converted_leads"], r["assigned_leads"]), reverse=True)

    conversion_analytics = {
        "employees": conversion_employees,
        "sources": conversion_sources,
        "trend": _build_conversion_trend(db, scope, period),
        "overall_conversion_percentage": _pct(snapshot.leads["converted"], snapshot.leads["assigned"]),
    }

    sum_assigned = sum(e["assigned_leads"] for e in employees)
    sum_contacted = sum(e["contacted_leads"] for e in employees)
    sum_converted = sum(e["converted_leads"] for e in employees)
    sum_calls = sum(e["total_calls"] for e in employees)
    sum_inbound = sum(e["inbound_calls"] for e in employees)
    sum_outbound = sum(e["outbound_calls"] for e in employees)
    sum_connected = sum(e["connected_calls"] for e in employees)
    sum_fu_completed = sum(e["followups_completed"] for e in employees)
    sum_fu_pending = sum(e["pending_followups"] for e in employees)

    team_totals = {
        "assigned_leads": sum_assigned,
        "contacted_leads": sum_contacted,
        "converted_leads": sum_converted,
        "total_calls": sum_calls,
        "inbound_calls": sum_inbound,
        "outbound_calls": sum_outbound,
        "connected_calls": sum_connected,
        "followups_completed": sum_fu_completed,
        "pending_followups": sum_fu_pending,
        "conversion_percentage": _pct(sum_converted, sum_assigned),
    }

    return {
        "generated_at": _iso_ist(_ist_now()),
        "timezone": IST_LABEL,
        "period": {
            "preset": period.preset,
            "label": period.label,
            "start": period.start.date().isoformat() if period.start else None,
            "end": period.end.date().isoformat() if period.end else None,
            "comparison_start": period.prev_start.date().isoformat() if period.prev_start else None,
            "comparison_end": period.prev_end.date().isoformat() if period.prev_end else None,
            "all_time": period.all_time,
        },
        "filters": filters.as_dict(),
        "filter_options": _filter_options(db, user),
        "overview": overview,
        "employees": employees,
        "team_totals": team_totals,
        "lead_analytics": lead_analytics,
        "call_analytics": call_analytics,
        "followup_analytics": followup_analytics,
        "conversion_analytics": conversion_analytics,
        "timeline": _build_timeline(db, scope, period),
        "definitions": METRIC_DEFINITIONS,
        "notes": [
            "Lead metrics are a period cohort: leads are counted when created within the selected range and classified by their current CRM status.",
            "Contacted and interested counts are cumulative funnel stages and include converted leads.",
            "Connected calls require a connected status and duration_seconds > 0; zero-duration connected calls count as answered but not connected.",
            "Pending follow-ups are current Pending records scheduled inside the selected range. Overdue is evaluated against now in Asia/Kolkata.",
            "Completed follow-ups use updated_at because the followups table has no completed_at column.",
            "Test/demo fixtures are excluded by employee/lead email domains and explicit test/demo name prefixes.",
        ],
    }


# ---------------------------------------------------------------------------
# Drill-down records


LEAD_METRICS = {
    "new_leads": ("New leads", "new"),
    "total_assigned_leads": ("Assigned leads", "assigned"),
    "assigned_leads": ("Assigned leads", "assigned"),
    "unassigned_leads": ("Unassigned leads", "unassigned"),
    "contacted_leads": ("Contacted leads", "contacted"),
    "interested_leads": ("Interested leads", "interested"),
    "converted_leads": ("Converted leads", "converted"),
    "lost_leads": ("Lost leads", "lost"),
    "conversion_percentage": ("Converted leads", "converted"),
}

CALL_METRICS = {
    "total_calls": ("Total calls", "total"),
    "inbound_calls": ("Inbound calls", "inbound"),
    "outbound_calls": ("Outbound calls", "outbound"),
    "answered_calls": ("Answered calls", "answered"),
    "connected_calls": ("Connected calls", "connected"),
    "connected_duration_seconds": ("Connected call duration", "connected"),
    "avg_connected_duration_seconds": ("Average connected call duration", "connected"),
    "missed_calls": ("Missed calls", "missed"),
    "failed_calls": ("Failed calls", "failed"),
    "mobile_calls": ("Mobile calls", "mobile"),
    "doocti_calls": ("Doocti calls", "doocti"),
}

FOLLOWUP_METRICS = {
    "completed_followups": ("Completed follow-ups", "completed"),
    "pending_followups": ("Pending follow-ups", "pending"),
    "overdue_followups": ("Overdue follow-ups", "overdue"),
}

EMPLOYEE_METRICS = {
    "total_employees": "total",
    "active_employees": "active",
}


def _employee_records(scope: Scope) -> List[Dict[str, Any]]:
    rows = []
    for employee in scope.employees:
        rows.append(
            {
                "id": employee.id,
                "name": employee.name,
                "email": employee.email,
                "role": employee.role,
                "department": normalize_department(employee.department or (employee.user.department if employee.user else None)) or "UNASSIGNED",
                "status": employee.status,
                "user_active": bool(employee.user.is_active) if employee.user is not None else True,
                "created_at": _iso_ist(employee.created_at),
            }
        )
    return rows


def _lead_record(row: Lead, employee_by_id: Dict[int, Employee]) -> Dict[str, Any]:
    employee = employee_by_id.get(row.assigned_to) if row.assigned_to else None
    return {
        "id": row.id,
        "name": row.name,
        "phone": row.phone,
        "email": row.email,
        "company": row.company,
        "status": row.status,
        "source": row.source,
        "assigned_to": row.assigned_to,
        "assigned_employee": employee.name if employee else "Unassigned",
        "created_at": _iso_ist(row.created_at),
        "updated_at": _iso_ist(row.updated_at),
    }


def _call_record(row: CallLog, lead_names: Dict[int, str], employee_by_id: Dict[int, Employee]) -> Dict[str, Any]:
    employee = employee_by_id.get(row.employee_id) if row.employee_id else None
    flags = _classify_call(row.call_status, row.provider)
    return {
        "id": row.id,
        "lead_id": row.lead_id,
        "lead_name": lead_names.get(row.lead_id, "—") if row.lead_id else "—",
        "employee_id": row.employee_id,
        "employee_name": employee.name if employee else "Unattributed",
        "call_direction": row.call_direction,
        "call_status": row.call_status,
        "provider": row.provider,
        "duration_seconds": int(row.duration_seconds or 0),
        "connected": bool(flags["connected_status"] and int(row.duration_seconds or 0) > 0),
        "started_at": _iso_ist(row.started_at or row.created_at),
        "created_at": _iso_ist(row.created_at),
    }


def _followup_record(row: Followup, lead_names: Dict[int, str], employee_by_id: Dict[int, Employee]) -> Dict[str, Any]:
    employee = employee_by_id.get(row.assigned_to) if row.assigned_to else None
    scheduled = _followup_scheduled_at(row)
    return {
        "id": row.id,
        "lead_id": row.lead_id,
        "lead_name": lead_names.get(row.lead_id, "—"),
        "assigned_to": row.assigned_to,
        "employee_name": employee.name if employee else "Unassigned",
        "followup_date": row.followup_date.isoformat() if row.followup_date else None,
        "followup_time": row.followup_time,
        "scheduled_at": _iso_ist(scheduled),
        "status": row.status,
        "priority": row.priority,
        "overdue": bool(row.status and row.status.lower() == "pending" and scheduled and scheduled < _ist_now()),
        "updated_at": _iso_ist(_utc_to_ist(row.updated_at)),
    }


def get_metric_records(
    db: Session,
    user: User,
    filters: InsightsFilters,
    metric: str,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    period = resolve_period(filters)
    scope = _load_scope(db, user, filters)
    snapshot = _compute_snapshot(db, scope, period)
    metric = (metric or "").strip()
    limit = max(1, min(int(limit or 50), 500))
    offset = max(0, int(offset or 0))

    columns: List[Dict[str, str]] = []
    items: List[Dict[str, Any]] = []
    total = 0
    label = metric.replace("_", " ").title()

    if metric in EMPLOYEE_METRICS:
        rows = _employee_records(scope)
        if EMPLOYEE_METRICS[metric] == "active":
            rows = [r for r in rows if (r["status"] or "").upper() == "ACTIVE" and r["user_active"]]
        total = len(rows)
        items = rows[offset : offset + limit]
        label = "Active employees" if EMPLOYEE_METRICS[metric] == "active" else "Total employees"
        columns = [
            {"key": "name", "label": "Employee"},
            {"key": "role", "label": "Role"},
            {"key": "department", "label": "Department"},
            {"key": "status", "label": "Status"},
            {"key": "email", "label": "Email"},
        ]

    elif metric in LEAD_METRICS:
        label, category = LEAD_METRICS[metric]
        rows = (
            db.query(Lead)
            .filter(*_lead_conditions(db, scope, period))
            .order_by(Lead.created_at.desc())
            .all()
        )
        filtered = []
        for row in rows:
            flags = _classify_lead(row.status)
            if category == "new":
                filtered.append(row)
            elif category == "assigned" and row.assigned_to:
                filtered.append(row)
            elif category == "unassigned" and not row.assigned_to:
                filtered.append(row)
            elif category in flags and flags[category]:
                filtered.append(row)
        total = len(filtered)
        page = filtered[offset : offset + limit]
        lead_emp_ids = {r.assigned_to for r in page if r.assigned_to}
        employees = {
            e.id: e
            for e in db.query(Employee).filter(Employee.id.in_(lead_emp_ids)).all()
        } if lead_emp_ids else {}
        items = [_lead_record(r, employees) for r in page]
        columns = [
            {"key": "name", "label": "Lead"},
            {"key": "phone", "label": "Phone"},
            {"key": "status", "label": "Status"},
            {"key": "source", "label": "Source"},
            {"key": "assigned_employee", "label": "Assigned to"},
            {"key": "created_at", "label": "Created (IST)"},
        ]

    elif metric in CALL_METRICS:
        label, category = CALL_METRICS[metric]
        rows = (
            db.query(CallLog)
            .filter(*_call_conditions(db, scope, period))
            .order_by(_effective_call_time().desc())
            .all()
        )
        filtered = []
        for row in rows:
            flags = _classify_call(row.call_status, row.provider)
            if category == "total":
                filtered.append(row)
            elif category in ("inbound", "outbound"):
                if _norm(row.call_direction) == category.upper():
                    filtered.append(row)
            elif category == "connected":
                if flags["connected_status"] and int(row.duration_seconds or 0) > 0:
                    filtered.append(row)
            elif category in flags and flags[category]:
                filtered.append(row)
        total = len(filtered)
        page = filtered[offset : offset + limit]
        lead_ids = {r.lead_id for r in page if r.lead_id}
        lead_names = {
            lid: name for lid, name in db.query(Lead.id, Lead.name).filter(Lead.id.in_(lead_ids)).all()
        } if lead_ids else {}
        emp_ids = {r.employee_id for r in page if r.employee_id}
        employees = {
            e.id: e for e in db.query(Employee).filter(Employee.id.in_(emp_ids)).all()
        } if emp_ids else {}
        items = [_call_record(r, lead_names, employees) for r in page]
        columns = [
            {"key": "started_at", "label": "Call time (IST)"},
            {"key": "employee_name", "label": "Employee"},
            {"key": "lead_name", "label": "Lead"},
            {"key": "call_direction", "label": "Direction"},
            {"key": "call_status", "label": "Status"},
            {"key": "provider", "label": "Source"},
            {"key": "duration_seconds", "label": "Duration (s)"},
        ]

    elif metric in FOLLOWUP_METRICS:
        label, category = FOLLOWUP_METRICS[metric]
        if category == "completed":
            q = db.query(Followup).filter(
                *_followup_conditions(db, scope),
                func.lower(Followup.status) == "completed",
            )
            if period.start and period.end:
                q = q.filter(Followup.updated_at.between(period.start - IST_OFFSET, period.end - IST_OFFSET))
            rows = q.order_by(Followup.updated_at.desc()).all()
        else:
            q = db.query(Followup).filter(
                *_followup_conditions(db, scope),
                func.lower(Followup.status) == "pending",
            )
            if period.start and period.end:
                q = q.filter(Followup.followup_date.between(period.start.date(), period.end.date()))
            rows = q.order_by(Followup.followup_date.asc(), Followup.followup_time.asc()).all()
            if category == "overdue":
                rows = [r for r in rows if (_followup_scheduled_at(r) or datetime.max) < _ist_now()]
        total = len(rows)
        page = rows[offset : offset + limit]
        lead_ids = {r.lead_id for r in page}
        lead_names = {
            lid: name for lid, name in db.query(Lead.id, Lead.name).filter(Lead.id.in_(lead_ids)).all()
        } if lead_ids else {}
        emp_ids = {r.assigned_to for r in page if r.assigned_to}
        employees = {
            e.id: e for e in db.query(Employee).filter(Employee.id.in_(emp_ids)).all()
        } if emp_ids else {}
        items = [_followup_record(r, lead_names, employees) for r in page]
        columns = [
            {"key": "scheduled_at", "label": "Scheduled (IST)"},
            {"key": "lead_name", "label": "Lead"},
            {"key": "employee_name", "label": "Assigned to"},
            {"key": "status", "label": "Status"},
            {"key": "priority", "label": "Priority"},
            {"key": "updated_at", "label": "Last updated (IST)"},
        ]

    else:
        raise ValueError(f"Unknown metric '{metric}'.")

    return {
        "metric": metric,
        "label": label,
        "definition": METRIC_DEFINITIONS.get(metric, ""),
        "total": total,
        "offset": offset,
        "limit": limit,
        "columns": columns,
        "items": items,
        "period": {
            "preset": period.preset,
            "label": period.label,
            "start": period.start.date().isoformat() if period.start else None,
            "end": period.end.date().isoformat() if period.end else None,
        },
    }


# ---------------------------------------------------------------------------
# Export


def _employee_export_rows(db: Session, user: User, filters: InsightsFilters) -> Tuple[List[str], List[List[Any]]]:
    period = resolve_period(filters)
    scope = _load_scope(db, user, filters)
    snapshot = _compute_snapshot(db, scope, period)
    rows = _build_employee_rows(scope, snapshot)
    headers = [
        "Rank", "Employee", "Role", "Department", "Assigned Leads", "Contacted Leads",
        "Total Calls", "Inbound Calls", "Outbound Calls", "Connected Calls",
        "Follow-ups Completed", "Pending Follow-ups", "Converted Leads", "Conversion %",
    ]
    data = [
        [
            r["rank"], r["name"], r["role"], r["department"], r["assigned_leads"],
            r["contacted_leads"], r["total_calls"], r["inbound_calls"], r["outbound_calls"],
            r["connected_calls"], r["followups_completed"], r["pending_followups"],
            r["converted_leads"], r["conversion_percentage"],
        ]
        for r in rows
    ]
    return headers, data


def _conversion_employee_export_rows(db: Session, user: User, filters: InsightsFilters) -> Tuple[List[str], List[List[Any]]]:
    period = resolve_period(filters)
    scope = _load_scope(db, user, filters)
    snapshot = _compute_snapshot(db, scope, period)
    headers = ["Employee", "Department", "Assigned Leads", "Converted Leads", "Conversion %"]
    data = []
    for employee in scope.employees:
        stats = snapshot.lead_by_employee.get(employee.id, _empty_lead_stats())
        data.append([
            employee.name,
            normalize_department(employee.department or (employee.user.department if employee.user else None)) or "UNASSIGNED",
            stats["assigned"],
            stats["converted"],
            _pct(stats["converted"], stats["assigned"]),
        ])
    return headers, data


def _conversion_source_export_rows(db: Session, user: User, filters: InsightsFilters) -> Tuple[List[str], List[List[Any]]]:
    period = resolve_period(filters)
    scope = _load_scope(db, user, filters)
    snapshot = _compute_snapshot(db, scope, period)
    headers = ["Lead Source", "Assigned Leads", "Converted Leads", "Conversion %"]
    data = [
        [source, stats["assigned"], stats["converted"], _pct(stats["converted"], stats["assigned"])]
        for source, stats in sorted(
            snapshot.lead_by_source.items(),
            key=lambda kv: (kv[1]["converted"], kv[1]["assigned"]),
            reverse=True,
        )
    ]
    return headers, data


def _timeline_export_rows(db: Session, user: User, filters: InsightsFilters) -> Tuple[List[str], List[List[Any]]]:
    period = resolve_period(filters)
    scope = _load_scope(db, user, filters)
    events = _build_timeline(db, scope, period, limit=1000)
    headers = ["Timestamp (IST)", "Event", "Employee", "Lead", "Description"]
    data = [
        [e["timestamp"], e["event_type"], e["employee_name"], e["lead_name"], e["description"]]
        for e in events
    ]
    return headers, data


def _records_export_rows(db: Session, user: User, filters: InsightsFilters, metric: str) -> Tuple[List[str], List[List[Any]]]:
    """Export every record behind a metric, not only the first page."""
    page_size = 500
    result = get_metric_records(db, user, filters, metric, limit=page_size, offset=0)
    headers = [c["label"] for c in result["columns"]]
    columns = result["columns"]
    items = list(result["items"])
    total = int(result["total"])
    while len(items) < total and result["items"]:
        result = get_metric_records(db, user, filters, metric, limit=page_size, offset=len(items))
        if not result["items"]:
            break
        items.extend(result["items"])
    data = [[item.get(c["key"]) for c in columns] for item in items]
    return headers, data


def build_export(
    db: Session,
    user: User,
    filters: InsightsFilters,
    dataset: str,
    fmt: str = "csv",
    metric: Optional[str] = None,
    format: Optional[str] = None,
) -> Tuple[bytes, str, str]:
    effective_fmt = format or fmt or "csv"
    dataset = (dataset or "employees").strip().lower()
    fmt = effective_fmt.strip().lower()

    if dataset == "employees":
        headers, data = _employee_export_rows(db, user, filters)
        base = "team_insights_employee_performance"
    elif dataset in {"conversions", "conversion_employees"}:
        headers, data = _conversion_employee_export_rows(db, user, filters)
        base = "team_insights_conversion_by_employee"
    elif dataset == "conversion_sources":
        headers, data = _conversion_source_export_rows(db, user, filters)
        base = "team_insights_conversion_by_source"
    elif dataset == "timeline":
        headers, data = _timeline_export_rows(db, user, filters)
        base = "team_insights_activity_timeline"
    elif dataset in {"leads", "calls", "followups"}:
        headers, data = _records_export_rows(db, user, filters, metric or dataset)
        base = f"team_insights_{dataset}"
    elif dataset in {"metric", "records"}:
        if not metric:
            raise ValueError("An export metric is required.")
        headers, data = _records_export_rows(db, user, filters, metric)
        base = f"team_insights_{metric}"
    else:
        raise ValueError(f"Unknown export dataset '{dataset}'.")

    stamp = _ist_now().strftime("%Y%m%d_%H%M%S")
    if fmt == "xlsx":
        if Workbook is None:
            raise RuntimeError("Excel export is not available on this server.")
        wb = Workbook()
        ws = wb.active
        ws.title = "Team Insights"
        header_fill = PatternFill("solid", fgColor="059669")
        header_font = Font(color="FFFFFF", bold=True)
        ws.append(headers)
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
        for row in data:
            ws.append(row)
        widths = [max(12, min(42, len(str(v)) + 2)) for v in headers]
        for idx, width in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(idx)].width = width
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        buffer = io.BytesIO()
        wb.save(buffer)
        return (
            buffer.getvalue(),
            f"{base}_{stamp}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in data:
        writer.writerow(row)
    return (
        ("\ufeff" + buffer.getvalue()).encode("utf-8"),
        f"{base}_{stamp}.csv",
        "text/csv; charset=utf-8",
    )
