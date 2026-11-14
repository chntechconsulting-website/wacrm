import logging
import math
from types import SimpleNamespace
from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException, status
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_, desc, asc, func, select, case
from typing import List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger("leads_router")

from utils.timezone import get_ist_now, format_ist_datetime, format_ist_date, format_ist_time

from database import get_db
from models.user import User
from models.employee import Employee
from models.lead import Lead, LeadAssignment, LeadStatusHistory
from models.activity import LeadActivity
from models.customer import Customer
from models.followup import Followup
from models.call_log import CallLog

from schemas.lead import (
    LeadCreate,
    LeadUpdate,
    LeadOut,
    LeadAssignRequest,
    LeadStatusRequest,
    LeadNoteRequest,
    LeadActivityOut,
    LeadAssignmentOut,
    LeadEnquiryOut,
    AutoAssignConfigOut,
    AutoAssignConfigUpdate,
    QuoteTaskQuotationCreateRequest
)
from schemas.workflow import DealWonRequest, SupportHandoffOut, SupportStatusUpdateRequest
from services.auth import get_current_user, require_roles, require_permission
from services.billing_terms import WAHRMS_TERMS_AND_CONDITIONS
from utils.document_status import invoice_document_status
from utils.payment_status import FINANCE_STATUS_PAID, normalize_finance_status
from services.permission_service import (
    user_has_permission, 
    get_user_view_scope, 
    get_authorized_call_employee_ids,
    is_support_lead_authorized,
    get_support_authorized_lead_ids
)
from services.delete_request_service import handle_entity_deletion
from services.audit import log_audit
from services.reinquiry_service import ReInquiryService
from services.followup_visibility_service import apply_followup_visibility_filter
from services.purchase_details_service import build_support_purchase_details
from services.hierarchy_service import (
    get_team_employee_ids_from_user,
    normalize_role,
    ROLE_ADMIN,
    ROLE_SALES_MANAGER,
    ROLE_SALES_EXECUTIVE,
    ROLE_SUPPORT_MANAGER,
    ROLE_SUPPORT_EXECUTIVE,
    SUPPORT_MANAGER_ROLES
)
from services.excel_service import (
    generate_excel_template,
    parse_and_validate_excel_leads,
    generate_error_rows_excel
)
from services.activity_visibility_service import can_view_activity
from utils.support_status import (
    InvalidSupportStatusError,
    require_support_status,
    support_status_storage_values,
)
from utils.lead_status import (
    STATUS_CONVERTED_TO_SUPPORT,
    STATUS_TRIAL,
    is_converted_to_support_status,
    is_trial_status,
    is_won_or_converted_status,
    is_won_status,
    normalize_lead_status,
    trial_status_for,
)

router = APIRouter(prefix="/leads", tags=["Leads"])

SUPPORT_ROLES = {ROLE_SUPPORT_MANAGER, ROLE_SUPPORT_EXECUTIVE}


def _is_support_actor(user: User) -> bool:
    """True for Support employees/managers, including legacy SUPPORT labels."""
    if not user:
        return False
    if normalize_role(user.role) in SUPPORT_ROLES:
        return True
    return (user.department or "").strip().upper() == "SUPPORT"

def get_employee_for_user(user: User, db: Session) -> Optional[Employee]:
    return db.query(Employee).filter(Employee.user_id == user.id).first()

def get_team_employee_ids(manager_emp_id: int, db: Session) -> List[int]:
    team = db.query(Employee).filter(Employee.manager_id == manager_emp_id).all()
    return [e.id for e in team] + [manager_emp_id]


def _employee_user_is_active(emp: Employee, db: Session) -> bool:
    """Employees without a linked user are allowed only when the employee
    record itself is active. A linked inactive user always disqualifies."""
    if not emp or (emp.status or "").strip().upper() != "ACTIVE":
        return False
    if not emp.user_id:
        return True
    user = db.query(User).filter(User.id == emp.user_id).first()
    return bool(user and user.is_active)


def is_active_sales_manager(emp: Optional[Employee], db: Session) -> bool:
    """Manual Sales assignment targets must be active Sales Managers.

    Sales Executives, Support Managers/Executives, Admins and inactive
    employees are not valid Sales owners for the manual assignment workflow.
    """
    if not emp:
        return False
    if normalize_role(emp.role) != ROLE_SALES_MANAGER:
        return False
    if not _employee_user_is_active(emp, db):
        return False
    dept = (emp.department or "").strip().upper()
    return dept in ("", "SALES", "SALE")


def is_active_support_executive(emp: Optional[Employee], db: Session) -> bool:
    """Support assignment targets must be active Support Executives.

    Support Managers, Admins, Sales employees, inactive users and employees
    from other departments are intentionally rejected.
    """
    if not emp:
        return False
    if normalize_role(emp.role) != ROLE_SUPPORT_EXECUTIVE:
        return False
    if not _employee_user_is_active(emp, db):
        return False
    return (emp.department or "").strip().upper() == "SUPPORT"


def is_active_support_manager(emp: Optional[Employee], db: Session) -> bool:
    """Trial Support assignment targets must be active Support Managers.

    The manager is identified through the CRM's canonical role and
    department mapping (``SUPPORT_MANAGER_ROLES`` plus the Support
    department), never by matching a name or designation string. The linked
    login must carry the same manager role so the assignment always points
    at a real Support Manager account. Support Executives, Admins, Sales
    employees, other departments and inactive records are rejected.
    """
    if not emp:
        return False
    if normalize_role(emp.role) != ROLE_SUPPORT_MANAGER:
        return False
    if not _employee_user_is_active(emp, db):
        return False
    if (emp.department or "").strip().upper() != "SUPPORT":
        return False
    if emp.user_id:
        user = db.query(User).filter(User.id == emp.user_id).first()
        if user and normalize_role(user.role) != ROLE_SUPPORT_MANAGER:
            return False
    return True


def _resolve_employee_manager(emp: Employee, db: Session) -> Optional[Employee]:
    """Resolve the reporting manager of an employee without assuming whether
    the manager_id/reporting_manager_id points at employees or users."""
    if not emp:
        return None

    if emp.manager_id:
        manager = db.query(Employee).filter(Employee.id == emp.manager_id).first()
        if manager:
            return manager

    if emp.reporting_manager_id:
        manager = db.query(Employee).filter(Employee.id == emp.reporting_manager_id).first()
        if manager:
            return manager
        manager_user = db.query(User).filter(User.id == emp.reporting_manager_id).first()
        if manager_user:
            manager = db.query(Employee).filter(Employee.user_id == manager_user.id).first()
            if manager:
                return manager
            # Fall back to a synthetic employee-shaped object so the caller can
            # still display the username as the manager name.
            if manager_user.username:
                return Employee(id=manager_user.id, name=manager_user.username,
                                email="", username=manager_user.username,
                                role=manager_user.role or "")

    return None


def resolve_sales_manager(lead: Lead, db: Session) -> Optional[Employee]:
    """Return the Sales Manager responsible for a lead's Sales owner."""
    assigned = lead.assigned_employee
    if assigned:
        if normalize_role(assigned.role) == ROLE_SALES_MANAGER:
            return assigned
        manager = _resolve_employee_manager(assigned, db)
        if manager:
            return manager

    # Preserve attribution when the lead was assigned by a Sales Manager even
    # if the current owner no longer has a reporting manager configured.
    assigner = lead.assigned_by_employee
    if assigner and normalize_role(assigner.role) == ROLE_SALES_MANAGER:
        return assigner
    return None


def get_latest_support_handoff(db: Session, lead_id: int):
    from models.workflow import SupportHandoff
    return (
        db.query(SupportHandoff)
        .filter(SupportHandoff.lead_id == lead_id)
        .order_by(desc(SupportHandoff.id))
        .first()
    )


def build_support_handoff_map(db: Session, lead_ids: List[int]) -> dict:
    """Fetch the latest Support handoff for many leads in one query."""
    if not lead_ids:
        return {}
    from models.workflow import SupportHandoff

    handoffs = (
        db.query(SupportHandoff)
        .filter(SupportHandoff.lead_id.in_(lead_ids))
        .order_by(desc(SupportHandoff.id))
        .all()
    )
    latest = {}
    for handoff in handoffs:
        latest.setdefault(handoff.lead_id, handoff)
    return latest


def build_sales_manager_map(db: Session, leads: List[Lead]) -> dict:
    """Batch-resolve Sales Managers for a page of leads.

    Mirrors ``resolve_sales_manager`` exactly but replaces the per-row
    employee/user lookups with a handful of set-based queries.
    """
    if not leads:
        return {}

    employee_ids = set()
    user_fallback_ids = set()
    for lead in leads:
        assigned = lead.assigned_employee
        if assigned:
            if normalize_role(assigned.role) == ROLE_SALES_MANAGER:
                continue
            if assigned.manager_id:
                employee_ids.add(assigned.manager_id)
            if assigned.reporting_manager_id:
                employee_ids.add(assigned.reporting_manager_id)
                user_fallback_ids.add(assigned.reporting_manager_id)

    employees_by_id = {}
    if employee_ids:
        employees_by_id = {
            emp.id: emp
            for emp in db.query(Employee).filter(Employee.id.in_(employee_ids)).all()
        }

    # reporting_manager_id may point to a User rather than an Employee. Resolve
    # that legacy shape in two set-based queries instead of per lead.
    users_by_id = {}
    if user_fallback_ids:
        from models.user import User

        users_by_id = {
            user.id: user
            for user in db.query(User).filter(User.id.in_(user_fallback_ids)).all()
        }
        unresolved_user_ids = [
            user_id for user_id in user_fallback_ids
            if user_id not in employees_by_id and user_id in users_by_id
        ]
        if unresolved_user_ids:
            for emp in db.query(Employee).filter(Employee.user_id.in_(unresolved_user_ids)).all():
                employees_by_id.setdefault(emp.user_id, emp)

    result = {}
    for lead in leads:
        manager = None
        assigned = lead.assigned_employee
        if assigned:
            if normalize_role(assigned.role) == ROLE_SALES_MANAGER:
                manager = assigned
            else:
                if assigned.manager_id:
                    manager = employees_by_id.get(assigned.manager_id)
                if manager is None and assigned.reporting_manager_id:
                    manager = employees_by_id.get(assigned.reporting_manager_id)
                    if manager is None:
                        manager_user = users_by_id.get(assigned.reporting_manager_id)
                        if manager_user and manager_user.username:
                            manager = SimpleNamespace(
                                id=manager_user.id,
                                name=manager_user.username,
                            )

        if manager is None:
            assigner = lead.assigned_by_employee
            if assigner and normalize_role(assigner.role) == ROLE_SALES_MANAGER:
                manager = assigner

        result[lead.id] = manager
    return result


def log_lead_activity(db: Session, lead_id: int, performed_by_id: Optional[int], activity_type: str, description: str):
    activity = LeadActivity(
        lead_id=lead_id,
        performed_by=performed_by_id,
        activity_type=activity_type,
        description=description,
        created_at=datetime.utcnow()
    )
    db.add(activity)

def build_lead_out(
    lead: Lead,
    current_user: Optional[User] = None,
    db: Optional[Session] = None,
    support_handoff=None,
    sales_manager=None,
    include_timeline: bool = True
) -> LeadOut:
    """Serialize a lead.

    ``include_timeline=False`` is used by list endpoints. The table only needs
    the lead row fields, so loading every activity, assignment and enquiry for
    each row is pure overhead (and the largest source of N+1 queries on the
    Leads screen). Detail endpoints keep the full timeline.
    """
    activities_out = []
    for act in (lead.activities if include_timeline else []):
        # Department isolation is enforced on every embedded activity list, not
        # only on the shared /activities feed. Sales users never receive
        # Support onboarding notes and vice versa.
        if not can_view_activity(act, current_user, db):
            continue
        perf_name = act.performed_by_employee.name if act.performed_by_employee else "System"
        activities_out.append(LeadActivityOut(
            id=act.id,
            performed_by=act.performed_by,
            performed_by_name=perf_name,
            activity_type=act.activity_type,
            description=act.description,
            created_at=act.created_at
        ))

    assignments_out = []
    for asgn in (lead.assignments if include_timeline else []):
        to_name = asgn.assigned_to_employee.name if asgn.assigned_to_employee else f"Employee #{asgn.assigned_to}"
        by_name = asgn.assigned_by_employee.name if asgn.assigned_by_employee else "System (Automatic)"
        assignments_out.append(LeadAssignmentOut(
            id=asgn.id,
            lead_id=asgn.lead_id,
            assigned_to=asgn.assigned_to,
            assigned_to_name=to_name,
            assigned_by=asgn.assigned_by,
            assigned_by_name=by_name,
            assigned_at=asgn.assigned_at,
            assignment_method=getattr(asgn, "assignment_method", "MANUAL") or "MANUAL",
            notes=asgn.notes
        ))

    full_name = lead.name
    if not full_name and (lead.first_name or lead.last_name):
        full_name = f"{lead.first_name or ''} {lead.last_name or ''}".strip()

    loc = lead.location
    if not loc and (lead.city or lead.state):
        loc = f"{lead.city or ''}, {lead.state or ''}".strip(', ')

    enquiries_out = []
    for enq in ((lead.enquiries if include_timeline else []) or []):
        enquiries_out.append(LeadEnquiryOut(
            id=enq.id,
            lead_id=enq.lead_id,
            enquiry_number=enq.enquiry_number,
            enquiry_type=enq.enquiry_type,
            source=enq.source,
            campaign_name=enq.campaign_name,
            website_name=enq.website_name,
            landing_page=enq.landing_page,
            requirement_notes=enq.requirement_notes,
            created_at=enq.created_at
        ))

    # ------------------------------------------------------------------
    # Sales Manager / Support assignment / conversion projections
    # ------------------------------------------------------------------
    if include_timeline:
        sales_manager = resolve_sales_manager(lead, db) if db else sales_manager
        if support_handoff is None and db:
            support_handoff = get_latest_support_handoff(db, lead.id)

    support_assigned_to = None
    support_assigned_to_name = None
    support_manager_id = None
    support_manager_name = None
    support_assigned_at = None
    support_handoff_id = None

    if support_handoff:
        support_handoff_id = support_handoff.id
        support_assigned_to = support_handoff.assigned_agent_id
        support_assigned_to_name = support_handoff.assigned_agent_name
        support_manager_id = support_handoff.support_manager_id
        support_manager_name = support_handoff.support_manager_name

    # Legacy rows assigned a Support employee directly still display correctly
    # in the read-only Sales projection. New assignments never overwrite
    # Lead.assigned_to, so this fallback is strictly backwards compatible.
    if not support_assigned_to and lead.assigned_employee:
        legacy_emp = lead.assigned_employee
        if normalize_role(legacy_emp.role) == ROLE_SUPPORT_EXECUTIVE:
            support_assigned_to = legacy_emp.id
            support_assigned_to_name = legacy_emp.name
            if not support_manager_id:
                legacy_manager = _resolve_employee_manager(legacy_emp, db) if db else None
                if legacy_manager:
                    support_manager_id = legacy_manager.id
                    support_manager_name = legacy_manager.name

    # Support assignment timestamp is recorded on the auditable LeadAssignment
    # row, keeping both Sales and Support attribution intact.
    support_assignment_rows = [
        a for a in ((lead.assignments if include_timeline else []) or [])
        if (getattr(a, "assignment_method", "") or "").upper() == "MANUAL_SUPPORT"
    ]
    if support_assignment_rows:
        latest_support_assignment = max(
            support_assignment_rows,
            key=lambda a: a.assigned_at or datetime.min
        )
        support_assigned_at = latest_support_assignment.assigned_at
        if not support_assigned_to:
            support_assigned_to = latest_support_assignment.assigned_to
            support_assigned_to_name = (
                latest_support_assignment.assigned_to_employee.name
                if latest_support_assignment.assigned_to_employee else None
            )
    elif support_handoff and support_assigned_to:
        support_assigned_at = support_handoff.updated_at

    # A trial customer can receive a Support owner before the deal is ever
    # converted. That assignment lives on leads.trial_support_employee_id and
    # is only a display/reminder fallback: a Support handoff, a legacy direct
    # Support owner or a MANUAL_SUPPORT row always win, and no Support status
    # is written from here.
    trial_support_emp = None
    trial_support_id = getattr(lead, "trial_support_employee_id", None)
    if trial_support_id and db:
        trial_support_emp = (
            db.query(Employee).filter(Employee.id == trial_support_id).first()
        )
    if not trial_support_emp:
        trial_support_id = None
    if trial_support_emp and not support_assigned_to:
        support_assigned_to = trial_support_emp.id
        support_assigned_to_name = trial_support_emp.name
        if normalize_role(trial_support_emp.role) == ROLE_SUPPORT_MANAGER:
            # The trial contact is itself the Support Manager, so it must not
            # be projected as somebody else's (e.g. the Admin's) manager.
            support_manager_id = trial_support_emp.id
            support_manager_name = trial_support_emp.name
        elif not support_manager_id:
            trial_support_manager = _resolve_employee_manager(trial_support_emp, db)
            if trial_support_manager:
                support_manager_id = trial_support_manager.id
                support_manager_name = trial_support_manager.name

    conversion_event = None
    for history in ((lead.status_history if include_timeline else []) or []):
        if normalize_lead_status(history.new_status) == STATUS_CONVERTED_TO_SUPPORT:
            if conversion_event is None or (history.changed_at or datetime.min) > (conversion_event.changed_at or datetime.min):
                conversion_event = history

    is_converted = normalize_lead_status(lead.status) == STATUS_CONVERTED_TO_SUPPORT
    if is_converted:
        support_assignment_status = "ASSIGNED" if support_assigned_to else "NOT_ASSIGNED"
    else:
        support_assignment_status = "AWAITING_CONVERSION"

    trial_end_date = getattr(lead, "trial_end_date", None)
    trial_start_date = getattr(lead, "trial_start_date", None)
    trial_days_remaining = (
        (trial_end_date - get_ist_now().date()).days
        if trial_end_date else None
    )
    is_trial_expired = bool(
        is_trial_status(lead.status)
        and trial_end_date
        and trial_end_date < get_ist_now().date()
    )
    # Derived, never persisted: keeps Sales and Support statuses untouched
    # while still reporting Trial Active / Expiring Soon / Expired / etc.
    trial_duration_days = (
        (trial_end_date - trial_start_date).days
        if trial_end_date and trial_start_date else None
    )
    trial_status = trial_status_for(lead.status, trial_end_date)

    return LeadOut(
        id=lead.id,
        first_name=lead.first_name,
        last_name=lead.last_name,
        name=full_name or "Unnamed Lead",
        phone=lead.phone,
        whatsapp_number=lead.whatsapp_number,
        email=lead.email,
        designation=lead.designation,
        company=lead.company,
        industry=lead.industry,
        website=lead.website,
        company_size=lead.company_size,
        city=lead.city,
        state=lead.state,
        country=getattr(lead, 'country', 'India') or 'India',
        location=loc,
        source=lead.source,
        status=lead.status,
        campaign_name=lead.campaign_name,
        website_id=lead.website_id,
        website_name=lead.website_name,
        landing_page=lead.landing_page,
        rating=lead.rating,
        priority=lead.priority,
        requirement_notes=lead.requirement_notes,
        product_category=getattr(lead, 'product_category', None) or 'UNCLASSIFIED',
        product_category_confirmed=bool(getattr(lead, 'product_category_confirmed', False)),
        followup_date=lead.followup_date,
        followup_time=lead.followup_time,
        trial_start_date=getattr(lead, "trial_start_date", None),
        trial_end_date=trial_end_date,
        trial_days_remaining=trial_days_remaining,
        is_trial_expired=is_trial_expired,
        trial_duration_days=trial_duration_days,
        trial_status=trial_status,
        trial_support_employee_id=trial_support_id,
        trial_support_employee_name=(
            trial_support_emp.name if trial_support_emp else None
        ),
        trial_support_employee_role=(
            trial_support_emp.role if trial_support_emp else None
        ),
        assigned_to=lead.assigned_to,
        assigned_employee_name=lead.assigned_employee.name if lead.assigned_employee else None,
        assigned_by=lead.assigned_by,
        assigned_at=lead.assigned_at,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
        lead_received_at=lead.created_at,
        lead_received_formatted=format_ist_datetime(lead.created_at),
        lead_received_date=format_ist_date(lead.created_at),
        lead_received_time=format_ist_time(lead.created_at),
        # Re-Inquiry Tracking Fields
        is_reinquiry=bool(getattr(lead, "is_reinquiry", False)),
        reinquiry_count=getattr(lead, "reinquiry_count", 0) or 0,
        total_enquiries=getattr(lead, "total_enquiries", 1) or 1,
        first_enquiry_date=getattr(lead, "first_enquiry_date", None) or lead.created_at,
        latest_enquiry_date=getattr(lead, "latest_enquiry_date", None) or lead.created_at,
        previous_sources=getattr(lead, "previous_sources", None) or lead.source,
        latest_source=getattr(lead, "latest_source", None) or lead.source,
        # QuoteTask Integration Mapping Fields
        quotetask_quotation_id=lead.quotetask_quotation_id,
        quotetask_quotation_number=lead.quotetask_quotation_number,
        quotetask_quotation_status=lead.quotetask_quotation_status,
        quotetask_quotation_amount=lead.quotetask_quotation_amount,
        quotetask_quotation_url=lead.quotetask_quotation_url,
        quotetask_po_id=lead.quotetask_po_id,
        quotetask_po_number=lead.quotetask_po_number,
        quotetask_po_status=lead.quotetask_po_status,
        quotetask_synced_at=lead.quotetask_synced_at,
        # Sales Manager / Support assignment / conversion projections
        sales_manager_id=sales_manager.id if sales_manager else None,
        sales_manager_name=sales_manager.name if sales_manager else None,
        support_assigned_to=support_assigned_to,
        support_assigned_to_name=support_assigned_to_name,
        support_assigned_at=support_assigned_at,
        support_manager_id=support_manager_id,
        support_manager_name=support_manager_name,
        support_assignment_status=support_assignment_status,
        is_converted_to_support=is_converted,
        converted_to_support_at=conversion_event.changed_at if conversion_event else None,
        converted_to_support_by=conversion_event.changed_by if conversion_event else None,
        converted_to_support_by_name=(
            conversion_event.changed_by_employee.name
            if conversion_event and conversion_event.changed_by_employee else None
        ),
        support_handoff_id=support_handoff_id,
        activities=activities_out,
        assignments=assignments_out,
        enquiries=enquiries_out
    )

# Server-side pagination defaults for the Leads list
DEFAULT_LEADS_PAGE_SIZE = 150


def resolve_leads_pagination(page: Optional[int], page_size: Optional[int], skip: int, limit: Optional[int]):
    """Resolve the requested page window.

    - `page` + `page_size` (web Leads table) selects the page window directly.
    - `page` + `limit` (mobile app) keeps the caller's page size.
    - Legacy `skip`/`limit` callers keep behaving exactly as before.
    Returns (page, page_size, offset).
    """
    eff_limit = limit if limit is not None and limit > 0 else None

    if page is not None and not (skip and skip > 0):
        # Server-side pagination mode
        eff_page_size = page_size or eff_limit or DEFAULT_LEADS_PAGE_SIZE
        offset = ((page if page > 0 else 1) - 1) * eff_page_size
    else:
        # Legacy offset mode (skip / limit)
        eff_page_size = eff_limit or 100
        offset = skip if skip and skip > 0 else 0

    eff_page = (offset // eff_page_size) + 1
    return eff_page, eff_page_size, offset


def leads_page_response(total: int, items: list, page: int, page_size: int) -> dict:
    """Standard paginated payload: items, total, page, page_size, total_pages."""
    total_pages = math.ceil(total / page_size) if page_size and page_size > 0 else 0
    return {
        "total": total,
        "items": items,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


def empty_leads_response(page: Optional[int], page_size: Optional[int], skip: int, limit: Optional[int]) -> dict:
    eff_page, eff_page_size, _ = resolve_leads_pagination(page, page_size, skip, limit)
    return leads_page_response(0, [], eff_page, eff_page_size)


@router.get("")
@router.get("/")
def list_leads(
    search: Optional[str] = None,
    status_filter: Optional[str] = None,
    status_val: Optional[str] = Query(None, alias="status"),
    source_filter: Optional[str] = None,
    source: Optional[str] = None,
    product_category: Optional[str] = None,
    product_category_filter: Optional[str] = None,
    priority_filter: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to_filter: Optional[int] = None,
    assigned_to: Optional[int] = None,
    is_reinquiry_filter: Optional[bool] = None,
    sort_by: Optional[str] = "created_at",
    sort_order: Optional[str] = "desc",
    date_filter: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    skip: int = 0,
    limit: Optional[int] = Query(None, description="Legacy page size: used with `skip`, or as the page size when `page` is provided"),
    page: Optional[int] = Query(None, ge=1, description="1-based page number (server-side pagination)"),
    page_size: Optional[int] = Query(None, ge=1, le=1000, description="Records per page, used together with `page`"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Lead)
    current_emp = get_employee_for_user(current_user, db)

    # BACKEND DYNAMIC RBAC VISIBILITY ENFORCEMENT
    norm_role = normalize_role(current_user.role)
    if norm_role in [ROLE_SUPPORT_MANAGER, ROLE_SUPPORT_EXECUTIVE]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Support team cannot access Sales leads."
        )

    if not user_has_permission(current_user, "leads", "view", db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You do not have permission to view leads."
        )

    eff_assigned_to = assigned_to_filter if assigned_to_filter is not None else assigned_to

    scope = get_user_view_scope(current_user, "leads", db)
    if scope == "none":
        return empty_leads_response(page, page_size, skip, limit)
    elif scope == "own":
        if current_emp:
            query = query.filter(Lead.assigned_to == current_emp.id)
        else:
            return empty_leads_response(page, page_size, skip, limit)
    elif scope == "team":
        team_ids = get_team_employee_ids_from_user(current_user, db)
        if eff_assigned_to:
            if eff_assigned_to not in team_ids and current_user.role != "ADMIN":
                return empty_leads_response(page, page_size, skip, limit)
            query = query.filter(Lead.assigned_to == eff_assigned_to)
        else:
            query = query.filter(or_(Lead.assigned_to.in_(team_ids), Lead.assigned_to == None))
    else:  # "department" or "company"
        if eff_assigned_to:
            query = query.filter(Lead.assigned_to == eff_assigned_to)

    if search:
        clean_s = search.strip()
        search_fmt = f"%{clean_s}%"
        # If user searches phone with or without spaces/dashes/prefixes, extract digits
        digits_only = "".join(filter(str.isdigit, clean_s))
        conditions = [
            Lead.name.ilike(search_fmt),
            Lead.first_name.ilike(search_fmt),
            Lead.last_name.ilike(search_fmt),
            Lead.phone.ilike(search_fmt),
            Lead.whatsapp_number.ilike(search_fmt),
            Lead.email.ilike(search_fmt),
            Lead.company.ilike(search_fmt)
        ]
        if len(digits_only) >= 4:
            conditions.append(Lead.phone.ilike(f"%{digits_only[-10:]}%"))
            conditions.append(Lead.whatsapp_number.ilike(f"%{digits_only[-10:]}%"))
        query = query.filter(or_(*conditions))

    eff_status = status_filter or status_val
    if eff_status and eff_status.upper() != "ALL":
        st_clean = eff_status.strip().upper()
        if st_clean in ["RE-INQUIRY", "REINQUIRY"]:
            query = query.filter(or_(Lead.status == "RE-INQUIRY", Lead.is_reinquiry == True))
        elif st_clean in ["NEW", "NEW LEAD", "NEW_LEAD"]:
            query = query.filter(or_(Lead.status == "NEW", Lead.status == "NEW LEAD", Lead.status == "NEW_LEAD"))
        elif st_clean in ["IN_PROGRESS", "IN PROGRESS"]:
            query = query.filter(or_(Lead.status == "IN_PROGRESS", Lead.status == "IN PROGRESS", Lead.status == "CONTACTED", Lead.status == "INTERESTED"))
        elif st_clean in ["TRIAL", "TRIAL_LEAD", "TRIAL LEAD"]:
            query = query.filter(or_(Lead.status == "TRIAL", Lead.status == "TRIAL LEAD", Lead.status == "TRIAL_LEAD"))
        elif st_clean in ["CONVERTED_TO_SUPPORT", "CONVERTED TO SUPPORT", "CONVERTED-TO-SUPPORT"]:
            query = query.filter(or_(
                Lead.status == "CONVERTED_TO_SUPPORT",
                Lead.status == "CONVERTED TO SUPPORT",
                Lead.status == "CONVERTED-TO-SUPPORT"
            ))
        elif st_clean in ["WON", "CONVERTED"]:
            query = query.filter(or_(Lead.status == "WON", Lead.status == "CONVERTED"))
        elif st_clean in ["FOLLOW-UP", "FOLLOW_UP"]:
            query = query.filter(or_(Lead.status == "FOLLOW-UP", Lead.status == "FOLLOW_UP"))
        elif st_clean in ["DEMO", "MEETING", "DEMO / MEETING", "DEMO/MEETING"]:
            query = query.filter(or_(Lead.status == "DEMO / MEETING", Lead.status == "DEMO", Lead.status == "MEETING"))
        elif st_clean in ["RNR", "RINGING_NO_RESPONSE", "RINGING NO RESPONSE"]:
            query = query.filter(or_(Lead.status == "RNR", Lead.status == "RINGING NO RESPONSE", Lead.status == "RINGING_NO_RESPONSE"))
        elif st_clean in ["JUNK", "SPAM", "INVALID"]:
            query = query.filter(or_(Lead.status == "JUNK", Lead.status == "SPAM", Lead.status == "INVALID"))
        else:
            query = query.filter(Lead.status.ilike(eff_status.strip()))

    if is_reinquiry_filter is not None:
        query = query.filter(Lead.is_reinquiry == is_reinquiry_filter)

    eff_source = source_filter or source
    if eff_source and eff_source.upper() != "ALL":
        src_upper = eff_source.strip().upper()
        if src_upper in ["META", "META ADS", "META_ADS"]:
            query = query.filter(or_(Lead.source == "META", Lead.source == "Meta Ads", Lead.source == "Meta"))
        elif src_upper in ["WEBSITE", "WEB"]:
            query = query.filter(or_(Lead.source == "WEBSITE", Lead.source == "Website"))
        elif src_upper in ["MANUAL"]:
            query = query.filter(or_(Lead.source == "MANUAL", Lead.source == "Manual"))
        elif src_upper in ["EXCEL", "IMPORT"]:
            query = query.filter(or_(Lead.source == "EXCEL", Lead.source == "Excel"))
        else:
            query = query.filter(Lead.source.ilike(eff_source))

    eff_category = product_category_filter or product_category
    if eff_category and eff_category.upper() != "ALL":
        cat_clean = eff_category.strip().upper()
        if cat_clean == "UNCLASSIFIED":
            query = query.filter(or_(Lead.product_category == None, Lead.product_category == "", Lead.product_category == "UNCLASSIFIED"))
        else:
            query = query.filter(Lead.product_category == cat_clean)

    eff_priority = priority_filter or priority
    if eff_priority and eff_priority.upper() != "ALL":
        p_clean = eff_priority.strip().upper()
        if p_clean in ["HOT", "HIGH"]:
            query = query.filter(or_(Lead.priority.ilike("HOT"), Lead.priority.ilike("HIGH"), Lead.rating.ilike("HOT")))
        elif p_clean in ["WARM", "MEDIUM"]:
            query = query.filter(or_(Lead.priority.ilike("WARM"), Lead.priority.ilike("MEDIUM"), Lead.rating.ilike("WARM")))
        elif p_clean in ["COLD", "LOW"]:
            query = query.filter(or_(Lead.priority.ilike("COLD"), Lead.priority.ilike("LOW"), Lead.rating.ilike("COLD")))
        else:
            query = query.filter(or_(Lead.priority.ilike(eff_priority.strip()), Lead.rating.ilike(eff_priority.strip())))

    # Lead Received Date / Time Filtering (Exact IST Date or Date Range)
    if date_filter:
        try:
            target_date = datetime.strptime(date_filter.strip(), "%Y-%m-%d")
            day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            query = query.filter(Lead.created_at >= day_start, Lead.created_at <= day_end)
        except Exception:
            pass

    if start_date:
        try:
            s_date = datetime.strptime(start_date.strip(), "%Y-%m-%d").replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.filter(Lead.created_at >= s_date)
        except Exception:
            pass

    if end_date:
        try:
            e_date = datetime.strptime(end_date.strip(), "%Y-%m-%d").replace(hour=23, minute=59, second=59, microsecond=999999)
            query = query.filter(Lead.created_at <= e_date)
        except Exception:
            pass

    total = query.count()

    # Server-side pagination window (page/page_size, or legacy skip/limit)
    eff_page, eff_page_size, offset = resolve_leads_pagination(page, page_size, skip, limit)

    # Dynamic Sorting by Lead Received Date/Time (default desc: latest first)
    is_asc = bool(sort_order and sort_order.lower() == "asc")
    order_clause = asc(Lead.created_at) if is_asc else desc(Lead.created_at)
    leads = (
        query
        .options(
            selectinload(Lead.assigned_employee),
            selectinload(Lead.assigned_by_employee),
        )
        .order_by(order_clause, desc(Lead.id) if not is_asc else asc(Lead.id))
        .offset(offset)
        .limit(eff_page_size)
        .all()
    )

    # List rows do not need embedded timelines. Batch the two projections that
    # would otherwise issue per-lead queries, and return a compact payload.
    lead_ids = [lead.id for lead in leads]
    support_handoffs = build_support_handoff_map(db, lead_ids)
    sales_managers = build_sales_manager_map(db, leads)
    items = [
        build_lead_out(
            lead,
            current_user,
            db,
            support_handoff=support_handoffs.get(lead.id),
            sales_manager=sales_managers.get(lead.id),
            include_timeline=False,
        )
        for lead in leads
    ]
    return leads_page_response(total, items, eff_page, eff_page_size)

@router.get("/stats")
def get_leads_stats(
    only_my: Optional[bool] = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    current_emp = get_employee_for_user(current_user, db)
    
    base_query = db.query(Lead)
    call_logs_query = db.query(CallLog)
    followups_query = db.query(Followup).join(Lead, Followup.lead_id == Lead.id)

    scope = get_user_view_scope(current_user, "leads", db)

    # Strictly scope follow-ups to the authenticated department and team
    followups_query = apply_followup_visibility_filter(
        followups_query, current_user, db
    )

    if only_my or scope == "own":
        if current_emp:
            base_query = base_query.filter(Lead.assigned_to == current_emp.id)
        else:
            return {
                "allLeads": 0, "metaLeads": 0, "websiteLeads": 0, "manualLeads": 0,
                "excelLeads": 0, "reinquiryLeads": 0, "myLeads": 0, "callLogs": 0, "followups": 0
            }
    elif scope == "team":
        team_ids = get_team_employee_ids_from_user(current_user, db)
        base_query = base_query.filter(or_(Lead.assigned_to.in_(team_ids), Lead.assigned_to == None))

    # One aggregate query replaces twelve sequential COUNT(*) round-trips.
    # The Leads screen polls these counters, so keeping this endpoint cheap is
    # important for both the API and the database.
    my_count_case = (
        case((Lead.assigned_to == current_emp.id, 1), else_=0)
        if current_emp else case((False, 1), else_=0)
    )
    metrics = base_query.with_entities(
        func.count(Lead.id).label("all_count"),
        func.coalesce(func.sum(case((or_(
            Lead.source == "META", Lead.source == "Meta Ads", Lead.source == "Meta"
        ), 1), else_=0)), 0).label("meta_count"),
        func.coalesce(func.sum(case((or_(
            Lead.source == "WEBSITE", Lead.source == "Website"
        ), 1), else_=0)), 0).label("website_count"),
        func.coalesce(func.sum(case((or_(
            Lead.source == "MANUAL", Lead.source == "Manual"
        ), 1), else_=0)), 0).label("manual_count"),
        func.coalesce(func.sum(case((or_(
            Lead.source == "EXCEL", Lead.source == "Excel"
        ), 1), else_=0)), 0).label("excel_count"),
        func.coalesce(func.sum(case((Lead.is_reinquiry.is_(True), 1), else_=0)), 0).label("reinquiry_count"),
        func.coalesce(func.sum(case((or_(
            Lead.status == "NEW", Lead.status == "NEW LEAD", Lead.status == "New"
        ), 1), else_=0)), 0).label("new_count"),
        func.coalesce(func.sum(case((or_(
            Lead.status == "IN_PROGRESS",
            Lead.status == "IN PROGRESS",
            Lead.status == "CONTACTED",
            Lead.status == "INTERESTED",
        ), 1), else_=0)), 0).label("in_progress_count"),
        func.coalesce(func.sum(case((or_(
            Lead.rating.ilike("Hot"),
            Lead.priority.ilike("High"),
            Lead.priority.ilike("Hot"),
        ), 1), else_=0)), 0).label("hot_count"),
        func.coalesce(func.sum(case((or_(
            Lead.status == "TRIAL", Lead.status == "Trial", Lead.status == "TRIAL LEAD"
        ), 1), else_=0)), 0).label("trial_count"),
        func.coalesce(func.sum(case((or_(
            Lead.status == "CONVERTED_TO_SUPPORT",
            Lead.status == "CONVERTED TO SUPPORT",
            Lead.status == "CONVERTED-TO-SUPPORT",
        ), 1), else_=0)), 0).label("converted_to_support_count"),
        func.coalesce(func.sum(case((or_(
            Lead.status == "WON", Lead.status == "CONVERTED", Lead.status == "Won",
            Lead.status == "CONVERTED_TO_SUPPORT", Lead.status == "CONVERTED TO SUPPORT",
            Lead.status == "CONVERTED-TO-SUPPORT",
        ), 1), else_=0)), 0).label("won_count"),
        func.coalesce(func.sum(my_count_case), 0).label("my_count"),
    ).one()

    all_count = int(metrics.all_count or 0)
    meta_count = int(metrics.meta_count or 0)
    website_count = int(metrics.website_count or 0)
    manual_count = int(metrics.manual_count or 0)
    excel_count = int(metrics.excel_count or 0)
    reinquiry_count = int(metrics.reinquiry_count or 0)
    new_count = int(metrics.new_count or 0)
    in_progress_count = int(metrics.in_progress_count or 0)
    hot_count = int(metrics.hot_count or 0)
    trial_count = int(metrics.trial_count or 0)
    converted_to_support_count = int(metrics.converted_to_support_count or 0)
    won_count = int(metrics.won_count or 0)
    my_count = int(metrics.my_count or 0)

    # Calculate call logs count strictly scoped by user call permissions
    authorized_call_emps = get_authorized_call_employee_ids(current_user, db)
    if authorized_call_emps is not None:
        if len(authorized_call_emps) == 0:
            call_logs_count = 0
        elif len(authorized_call_emps) == 1:
            call_logs_count = db.query(CallLog).filter(CallLog.employee_id == authorized_call_emps[0]).count()
        else:
            call_logs_count = db.query(CallLog).filter(CallLog.employee_id.in_(authorized_call_emps)).count()
    else:
        call_logs_count = db.query(CallLog).count()

    followups_count = followups_query.filter(Followup.status == "Pending").count()

    support_count = 0
    norm_role = normalize_role(current_user.role)
    if norm_role in [ROLE_SUPPORT_MANAGER, ROLE_SUPPORT_EXECUTIVE, ROLE_ADMIN]:
        support_lead_ids = get_support_authorized_lead_ids(current_user, db)
        if support_lead_ids is not None:
            support_count = len(support_lead_ids)
        else:
            from models.workflow import SupportHandoff
            support_count = db.query(SupportHandoff.lead_id).distinct().count()

    return {
        "allLeads": all_count,
        "metaLeads": meta_count,
        "websiteLeads": website_count,
        "manualLeads": manual_count,
        "excelLeads": excel_count,
        "reinquiryLeads": reinquiry_count,
        "newLeads": new_count,
        "inProgressLeads": in_progress_count,
        "hotLeads": hot_count,
        "trialLeads": trial_count,
        "convertedToSupportLeads": converted_to_support_count,
        "wonLeads": won_count,
        "myLeads": my_count,
        "callLogs": call_logs_count,
        "followups": followups_count,
        "supportLeads": support_count
    }

@router.get("/my")
def list_my_leads(
    search: Optional[str] = None,
    status_filter: Optional[str] = None,
    source_filter: Optional[str] = None,
    skip: int = 0,
    limit: Optional[int] = Query(None, description="Legacy page size: used with `skip`, or as the page size when `page` is provided"),
    page: Optional[int] = Query(None, ge=1, description="1-based page number (server-side pagination)"),
    page_size: Optional[int] = Query(None, ge=1, le=1000, description="Records per page, used together with `page`"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    current_emp = get_employee_for_user(current_user, db)
    if not current_emp:
        return empty_leads_response(page, page_size, skip, limit)
    
    query = db.query(Lead).filter(Lead.assigned_to == current_emp.id)

    if search:
        clean_s = search.strip()
        search_fmt = f"%{clean_s}%"
        # If user searches phone with or without spaces/dashes/prefixes, extract digits
        digits_only = "".join(filter(str.isdigit, clean_s))
        conditions = [
            Lead.name.ilike(search_fmt),
            Lead.first_name.ilike(search_fmt),
            Lead.last_name.ilike(search_fmt),
            Lead.phone.ilike(search_fmt),
            Lead.whatsapp_number.ilike(search_fmt),
            Lead.email.ilike(search_fmt),
            Lead.company.ilike(search_fmt)
        ]
        if len(digits_only) >= 4:
            conditions.append(Lead.phone.ilike(f"%{digits_only[-10:]}%"))
            conditions.append(Lead.whatsapp_number.ilike(f"%{digits_only[-10:]}%"))
        query = query.filter(or_(*conditions))

    if status_filter:
        query = query.filter(Lead.status == status_filter)

    if source_filter:
        src_upper = source_filter.strip().upper()
        if src_upper in ["META", "META ADS", "META_ADS"]:
            query = query.filter(or_(Lead.source == "META", Lead.source == "Meta Ads", Lead.source == "Meta"))
        elif src_upper in ["WEBSITE", "WEB"]:
            query = query.filter(or_(Lead.source == "WEBSITE", Lead.source == "Website"))
        elif src_upper in ["MANUAL"]:
            query = query.filter(or_(Lead.source == "MANUAL", Lead.source == "Manual"))
        elif src_upper in ["EXCEL", "IMPORT"]:
            query = query.filter(or_(Lead.source == "EXCEL", Lead.source == "Excel"))
        else:
            query = query.filter(Lead.source.ilike(source_filter))

    total = query.count()

    # Server-side pagination window (page/page_size, or legacy skip/limit)
    eff_page, eff_page_size, offset = resolve_leads_pagination(page, page_size, skip, limit)
    leads = (
        query
        .options(
            selectinload(Lead.assigned_employee),
            selectinload(Lead.assigned_by_employee),
        )
        .order_by(desc(Lead.created_at))
        .offset(offset)
        .limit(eff_page_size)
        .all()
    )

    lead_ids = [lead.id for lead in leads]
    support_handoffs = build_support_handoff_map(db, lead_ids)
    sales_managers = build_sales_manager_map(db, leads)
    items = [
        build_lead_out(
            lead,
            current_user,
            db,
            support_handoff=support_handoffs.get(lead.id),
            sales_manager=sales_managers.get(lead.id),
            include_timeline=False,
        )
        for lead in leads
    ]
    return leads_page_response(total, items, eff_page, eff_page_size)

@router.get("/export/template")
def download_excel_template():
    stream = generate_excel_template()
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Lead_Import_Template.xlsx"}
    )

@router.post("/import/excel")
@router.post("/import")
async def import_leads_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("leads", "create"))
):
    # Bulk import is a bulk lead-create operation, so it uses the same dynamic
    # permission as single lead creation instead of a hardcoded role list. Sales
    # executives (and any custom role granted leads:create) can therefore import.
    if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an Excel (.xlsx) file.")

    contents = await file.read()
    current_emp = get_employee_for_user(current_user, db)
    creator_id = current_emp.id if current_emp else None
    creator_name = current_emp.name if current_emp else current_user.username

    # Assigning a lead to somebody else is a separate privilege (leads:assign).
    # Without it (e.g. a sales executive) the imported leads belong to the
    # importer, otherwise a restricted role could hand leads to any employee.
    can_assign_imports = user_has_permission(current_user, "leads", "assign", db)

    try:
        results = parse_and_validate_excel_leads(contents, db)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    valid_leads = results["valid_leads"]
    created_count = 0
    reinquiry_count = 0
    now = get_ist_now()
    # Every lead created by this import. They are excluded from duplicate
    # matching so that a row can never be classified as a re-inquiry of a row
    # created moments earlier in the same file.
    created_lead_ids = set()
    for lead_data in valid_leads:
        # The parser defaults the source to EXCEL; an explicit Source column is kept.
        if not lead_data.get("source"):
            lead_data["source"] = "EXCEL"
        # Users without assignment rights may only import leads for themselves.
        # This keeps a sales executive from using the importer to assign leads to
        # arbitrary employees (their view scope is "own" anyway).
        if not can_assign_imports:
            lead_data["assigned_to"] = creator_id
            if creator_id and str(lead_data.get("status") or "NEW").upper() == "NEW":
                lead_data["status"] = "ASSIGNED"
        lead, is_reinquiry, enq = ReInquiryService.register_enquiry(
            db=db,
            enquiry_data=lead_data,
            creator_emp_id=creator_id,
            creator_name=creator_name,
            commit=False,
            exclude_lead_ids=created_lead_ids
        )
        if is_reinquiry:
            reinquiry_count += 1
        else:
            created_count += 1
            created_lead_ids.add(lead.id)
            assigned_emp_id = lead_data.get("assigned_to")
            if assigned_emp_id:
                asgn = LeadAssignment(
                    lead_id=lead.id,
                    assigned_to=assigned_emp_id,
                    assigned_by=creator_id,
                    assigned_at=now,
                    assignment_method="EXCEL_IMPORT",
                    notes="Assigned during Excel import"
                )
                db.add(asgn)

    db.commit()

    log_audit(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action="IMPORT_EXCEL",
        entity_type="LEAD",
        entity_id=None,
        details=f"Imported {created_count} new leads and {reinquiry_count} re-inquiries from Excel '{file.filename}'."
    )

    return {
        "filename": file.filename,
        "total_rows": results["total_rows"],
        "imported": created_count,
        "reinquiries": reinquiry_count,
        "duplicates": results["duplicates"],
        "invalid": results["invalid"],
        "invalid_rows": results["invalid_rows"]
    }

@router.post("/import/download-errors")
def download_import_errors(invalid_rows: List[dict]):
    stream = generate_error_rows_excel(invalid_rows)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Import_Errors.xlsx"}
    )

@router.post("", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
def create_lead(
    lead_in: LeadCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("leads", "create"))
):
    current_emp = get_employee_for_user(current_user, db)
    creator_emp_id = current_emp.id if current_emp else None
    creator_name = current_emp.name if current_emp else current_user.username

    lead_data = lead_in.dict()
    trial_start = lead_data.get("trial_start_date")
    trial_end = lead_data.get("trial_end_date")
    if trial_start and trial_end and trial_end < trial_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trial End Date cannot be before Trial Start Date.",
        )
    # Users without assign permission can only assign to themselves on creation
    has_assign_permission = user_has_permission(current_user, "leads", "assign", db)
    if not has_assign_permission:
        lead_data["assigned_to"] = creator_emp_id
    else:
        # Manual Sales assignment is Manager-only. Reject Sales Executives,
        # Support users, Admins and inactive employees explicitly.
        target_id = lead_data.get("assigned_to")
        if target_id:
            target_emp = db.query(Employee).filter(Employee.id == target_id).first()
            if not target_emp:
                raise HTTPException(status_code=404, detail="Target employee not found")
            if not is_active_sales_manager(target_emp, db):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Manual Sales assignment allows only active Sales Managers. "
                        "Sales Executives, Support users, Managers/Admins and inactive "
                        "employees are not eligible."
                    )
                )

    lead, is_reinquiry, enq = ReInquiryService.register_enquiry(
        db=db,
        enquiry_data=lead_data,
        creator_emp_id=creator_emp_id,
        creator_name=creator_name,
        commit=True
    )

    action_str = "RE_INQUIRY_CREATED" if is_reinquiry else "LEAD_CREATE"
    details_str = (
        f"Re-inquiry #{lead.reinquiry_count} registered for #{lead.id} ({lead.name}) via {lead.latest_source or lead.source} by {current_user.username}."
        if is_reinquiry else
        f"Lead #{lead.id} ({lead.name}) created by {current_user.username}."
    )
    log_audit(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action=action_str,
        entity_type="LEAD",
        entity_id=lead.id,
        details=details_str
    )

    return build_lead_out(lead, current_user, db)


# =========================================================================
# SUPPORT TEAM ASSIGNED LEADS ENDPOINTS
# =========================================================================

@router.get("/support/assigned")
def get_support_assigned_leads(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    assigned_agent_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Dedicated endpoint for Support Assigned Leads:
    - Support Executive: sees only support leads assigned to them.
    - Support Manager: sees support leads assigned to their authorized support team.
    - Admin: sees all company-wide support leads.
    - Sales users: Strictly 403 Forbidden.
    """
    norm_role = normalize_role(current_user.role)
    if norm_role in [ROLE_SALES_MANAGER, ROLE_SALES_EXECUTIVE]:
        raise HTTPException(
            status_code=403,
            detail="Access forbidden: Sales users cannot access Support Assigned Leads."
        )

    if norm_role not in [ROLE_ADMIN, ROLE_SUPPORT_MANAGER, ROLE_SUPPORT_EXECUTIVE]:
        raise HTTPException(
            status_code=403,
            detail="Access forbidden: Only Support team and Admin can access Support Assigned Leads."
        )

    from models.workflow import SupportHandoff

    authorized_lead_ids = get_support_authorized_lead_ids(current_user, db)

    query = db.query(Lead)

    if authorized_lead_ids is not None:
        if not authorized_lead_ids:
            return {"total": 0, "items": [], "page": 1, "limit": limit}
        query = query.filter(Lead.id.in_(authorized_lead_ids))
    else:
        # Admin: Show leads with SupportHandoff OR assigned to a Support department employee
        support_emp_ids = select(Employee.id).where(
            or_(
                Employee.department == 'SUPPORT',
                Employee.role.in_(['SUPPORT_EXECUTIVE', 'SUPPORT_MANAGER', 'SUPPORT']),
            )
        )
        handoff_lead_ids = select(SupportHandoff.lead_id).where(
            SupportHandoff.lead_id.is_not(None)
        )
        query = query.filter(
            or_(
                Lead.id.in_(handoff_lead_ids),
                Lead.assigned_to.in_(support_emp_ids),
                Lead.trial_support_employee_id.is_not(None),
            )
        )

    # Optional filter by assigned_agent_id (for Manager/Admin)
    if assigned_agent_id:
        handoff_leads_for_agent = select(SupportHandoff.lead_id).where(
            SupportHandoff.assigned_agent_id == assigned_agent_id
        )
        query = query.filter(
            or_(
                Lead.assigned_to == assigned_agent_id,
                Lead.trial_support_employee_id == assigned_agent_id,
                Lead.id.in_(handoff_leads_for_agent)
            )
        )

    # Status filter applies to the independent Support status only. Sales
    # status (Lead.status) must never be used to filter the Support queue.
    if status and status.strip().upper() != "ALL":
        try:
            canonical_status = require_support_status(status)
        except InvalidSupportStatusError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        storage_values = support_status_storage_values(canonical_status)
        handoffs_with_st = select(SupportHandoff.lead_id).where(
            func.upper(SupportHandoff.onboarding_status).in_(storage_values)
        )
        query = query.filter(Lead.id.in_(handoffs_with_st))

    # Priority filter
    if priority and priority.upper() != "ALL":
        query = query.filter(Lead.priority.ilike(priority.strip()))

    # Source filter
    if source and source.upper() != "ALL":
        query = query.filter(Lead.source.ilike(f"%{source.strip()}%"))

    # Search filter
    if search and search.strip():
        term = f"%{search.strip()}%"
        handoff_matches = select(SupportHandoff.lead_id).where(
            or_(
                SupportHandoff.customer_name.ilike(term),
                SupportHandoff.company_name.ilike(term),
                SupportHandoff.product_service.ilike(term),
                SupportHandoff.customer_requirements.ilike(term),
                SupportHandoff.phone.ilike(term),
                SupportHandoff.email.ilike(term),
            )
        )
        query = query.filter(
            or_(
                Lead.name.ilike(term),
                Lead.first_name.ilike(term),
                Lead.last_name.ilike(term),
                Lead.phone.ilike(term),
                Lead.email.ilike(term),
                Lead.company.ilike(term),
                Lead.city.ilike(term),
                Lead.state.ilike(term),
                Lead.location.ilike(term),
                Lead.requirement_notes.ilike(term),
                Lead.id.in_(handoff_matches)
            )
        )

    total = query.count()
    leads = (
        query
        .options(selectinload(Lead.assigned_employee))
        .order_by(desc(Lead.updated_at))
        .offset(skip)
        .limit(limit)
        .all()
    )

    lead_ids_list = [l.id for l in leads]

    # Latest handoff per lead in one query (a lead can have re-inquiry handovers).
    handoffs_map = build_support_handoff_map(db, lead_ids_list)

    # Batch activity counts instead of lazy-loading every activity row per lead.
    activity_counts = {}
    if lead_ids_list:
        activity_counts = dict(
            db.query(LeadActivity.lead_id, func.count(LeadActivity.id))
            .filter(LeadActivity.lead_id.in_(lead_ids_list))
            .group_by(LeadActivity.lead_id)
            .all()
        )

    # Batch-resolve support managers for the visible page.
    exec_ids = set()
    for l in leads:
        h = handoffs_map.get(l.id)
        if h and h.assigned_agent_id:
            exec_ids.add(h.assigned_agent_id)
        elif getattr(l, "trial_support_employee_id", None):
            exec_ids.add(l.trial_support_employee_id)
        elif l.assigned_employee and (
            l.assigned_employee.department == 'SUPPORT'
            or 'SUPPORT' in (l.assigned_employee.role or '')
        ):
            exec_ids.add(l.assigned_to)

    execs_by_id = {}
    if exec_ids:
        execs_by_id = {
            emp.id: emp
            for emp in db.query(Employee).filter(Employee.id.in_(exec_ids)).all()
        }
    manager_ids = {
        emp.manager_id for emp in execs_by_id.values() if emp and emp.manager_id
    }
    managers_by_id = {}
    if manager_ids:
        managers_by_id = {
            emp.id: emp
            for emp in db.query(Employee).filter(Employee.id.in_(manager_ids)).all()
        }

    items = []
    for l in leads:
        h = handoffs_map.get(l.id)
        
        assigned_exec_id = None
        assigned_exec_name = None
        trial_assignee = None
        if h and h.assigned_agent_id:
            assigned_exec_id = h.assigned_agent_id
            assigned_exec_name = h.assigned_agent_name
        elif getattr(l, "trial_support_employee_id", None):
            trial_assignee = execs_by_id.get(l.trial_support_employee_id)
            # A trial customer can be owned by a Support Manager. That person
            # is projected as the assigned manager below, never as a Support
            # Executive, so the queue never reports an executive who is not
            # actually assigned.
            if not (
                trial_assignee
                and normalize_role(trial_assignee.role) == ROLE_SUPPORT_MANAGER
            ):
                assigned_exec_id = l.trial_support_employee_id
                assigned_exec_name = (
                    trial_assignee.name if trial_assignee else None
                )
        elif l.assigned_employee and (l.assigned_employee.department == 'SUPPORT' or 'SUPPORT' in (l.assigned_employee.role or '')):
            assigned_exec_id = l.assigned_to
            assigned_exec_name = l.assigned_employee.name

        assigned_mgr_id = h.support_manager_id if h else None
        assigned_mgr_name = h.support_manager_name if h else None
        if (
            trial_assignee
            and normalize_role(trial_assignee.role) == ROLE_SUPPORT_MANAGER
        ):
            assigned_mgr_id = trial_assignee.id
            assigned_mgr_name = trial_assignee.name
        elif not assigned_mgr_name and assigned_exec_id:
            exec_emp = l.assigned_employee or execs_by_id.get(assigned_exec_id)
            if exec_emp and exec_emp.manager_id:
                mgr = managers_by_id.get(exec_emp.manager_id)
                if mgr:
                    assigned_mgr_id = mgr.id
                    assigned_mgr_name = mgr.name

        assignment_date = None
        if l.assigned_at:
            assignment_date = l.assigned_at.isoformat()
        elif h and h.won_at:
            assignment_date = h.won_at.isoformat()
        elif h and h.created_at:
            assignment_date = h.created_at.isoformat()
        elif l.created_at:
            assignment_date = l.created_at.isoformat()

        contact_person = l.name or f"{l.first_name or ''} {l.last_name or ''}".strip() or (h.customer_name if h else "Unknown")
        company_name = l.company or (h.company_name if h else None)
        product_service = (h.product_service if h else None) or l.latest_source or "Support & Services"
        support_requirements = (h.customer_requirements if h else None) or (h.support_notes if h else None) or l.requirement_notes

        trial_end = getattr(l, "trial_end_date", None)
        trial_days_rem = (trial_end - get_ist_now().date()).days if trial_end else None
        is_expired = bool(
            is_trial_status(l.status)
            and trial_end
            and trial_end < get_ist_now().date()
        )

        items.append({
            "id": l.id,
            "lead_id": l.id,
            "support_handoff_id": h.id if h else None,
            "customer_id": h.customer_id if h else None,
            "sales_employee_name": h.sales_employee_name if h else None,
            "won_at": h.won_at.isoformat() if h and h.won_at else None,
            "name": l.name,
            "first_name": l.first_name,
            "last_name": l.last_name,
            "contact_person": contact_person,
            "company_name": company_name,
            "company": company_name,
            "phone": l.phone or (h.phone if h else ""),
            "email": l.email or (h.email if h else ""),
            "city": l.city,
            "state": l.state,
            "location": l.location or (f"{l.city or ''}, {l.state or ''}".strip(', ') if (l.city or l.state) else (h.address if (h and hasattr(h, 'address')) else None)),
            "source": l.source,
            # `status` is retained for existing clients and is always the
            # read-only Sales status. Support UIs must use `support_status`.
            "status": l.status,
            "sales_status": l.status,
            "support_status": h.support_status if h else "NEW",
            "onboarding_status": h.onboarding_status if h else "PENDING_ONBOARDING",
            "priority": l.priority or "MEDIUM",
            "product_service": product_service,
            "support_requirements": support_requirements,
            "requirement_notes": l.requirement_notes,
            "assigned_support_executive_id": assigned_exec_id,
            "assigned_support_executive_name": assigned_exec_name,
            "assigned_support_manager_id": assigned_mgr_id,
            "assigned_support_manager_name": assigned_mgr_name,
            "assignment_date": assignment_date,
            "trial_start_date": l.trial_start_date.isoformat() if getattr(l, "trial_start_date", None) else None,
            "trial_end_date": l.trial_end_date.isoformat() if getattr(l, "trial_end_date", None) else None,
            "trial_days_remaining": trial_days_rem,
            "is_trial_expired": is_expired,
            "trial_status": trial_status_for(l.status, trial_end),
            "trial_support_employee_id": getattr(l, "trial_support_employee_id", None),
            "trial_support_employee_role": (
                trial_assignee.role if trial_assignee else None
            ),
            "created_at": l.created_at.isoformat() if l.created_at else None,
            "last_updated": l.updated_at.isoformat() if l.updated_at else (l.created_at.isoformat() if l.created_at else None),
            "next_followup_date": l.followup_date.isoformat() if l.followup_date else None,
            "next_followup_time": l.followup_time,
            "notes": (h.support_notes if h else None) or l.requirement_notes,
            # The drawer lazy-loads the purchase projection from
            # /leads/{id}/purchase-details. Building it for every list row
            # issued up to five extra queries per handover.
            "purchase_details": None,
            "activities_count": int(activity_counts.get(l.id, 0))
        })

    return {
        "total": total,
        "items": items,
        "page": (skip // limit) + 1,
        "limit": limit
    }


@router.get("/{lead_id}/purchase-details")
def get_lead_purchase_details(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Read-only customer purchase details for the Support handover.

    Only Admin and Support roles may call this endpoint. Sales roles are
    rejected even when they can otherwise view the lead, so the Support
    purchase view cannot become an API-level leak. The projection reuses the
    immutable handover snapshot and never creates or re-prices records.
    """
    norm_role = normalize_role(current_user.role)
    if norm_role in [ROLE_SALES_MANAGER, ROLE_SALES_EXECUTIVE]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Sales users cannot access Support purchase details."
        )
    if norm_role != ROLE_ADMIN and not _is_support_actor(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Only Support team and Admin can access purchase details."
        )

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if norm_role != ROLE_ADMIN and not is_support_lead_authorized(lead, current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: This customer is not assigned to your Support team."
        )

    from models.workflow import SupportHandoff

    handoff = (
        db.query(SupportHandoff)
        .filter(SupportHandoff.lead_id == lead.id)
        .order_by(desc(SupportHandoff.created_at))
        .first()
    )
    if not handoff:
        raise HTTPException(
            status_code=404,
            detail="No Sales handover exists for this lead yet."
        )

    details = build_support_purchase_details(db, handoff)
    if not details:
        raise HTTPException(status_code=404, detail="Purchase details are not available.")
    return details


@router.get("/support/team-members")
def get_support_team_members(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the assignable Support team members.

    Only active Support Executives are assignable. Support Managers, Admins,
    Sales employees and inactive users are deliberately excluded so that the
    Support assignment dropdown and API cannot hand a customer to the wrong
    department.
    """
    norm_role = normalize_role(current_user.role)
    if norm_role in [ROLE_SALES_MANAGER, ROLE_SALES_EXECUTIVE]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Sales users cannot view Support team members."
        )

    support_emps = db.query(Employee).filter(
        Employee.department == "SUPPORT",
        Employee.status == "ACTIVE",
        Employee.role.in_(["SUPPORT_EXECUTIVE", "SUPPORT"])
    ).order_by(Employee.name.asc()).all()

    return [
        {
            "id": e.id,
            "name": e.name,
            "role": e.role,
            "department": e.department,
            "manager_id": e.manager_id,
            "status": e.status
        }
        for e in support_emps
        if is_active_support_executive(e, db)
    ]


@router.get("/sales-managers")
def get_sales_managers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the assignable Sales Managers for the manual Sales assignment
    dropdown. Only active Manager-level Sales employees are returned.
    """
    managers = db.query(Employee).filter(
        Employee.role.in_(["SALES_MANAGER", "MANAGER"]),
        Employee.status == "ACTIVE"
    ).order_by(Employee.name.asc()).all()

    result = []
    for emp in managers:
        if not is_active_sales_manager(emp, db):
            continue
        result.append({
            "id": emp.id,
            "name": emp.name,
            "role": emp.role,
            "department": emp.department,
            "manager_id": emp.manager_id,
            "status": emp.status
        })
    return result


@router.get("/trial/support-options")
def get_trial_support_options(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Active Support Managers available for a trial customer.

    The Set Trial Period modal is used by Sales (the assigned Sales employee
    or an authorised Sales Manager) and by Admin, so this variant of the
    existing Support team-members lookup is reachable for those roles only.
    Employee ids, names and roles always come from the database - nothing is
    hardcoded - and eligibility is decided by the canonical Support Manager
    role + Support department mapping. Regular Support Executives are
    deliberately excluded: they belong to the post-conversion Support
    assignment workflow, which this endpoint does not touch.
    """
    norm_role = normalize_role(current_user.role)
    if norm_role not in [ROLE_ADMIN, ROLE_SALES_MANAGER, ROLE_SALES_EXECUTIVE]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Access forbidden: only the Sales team and Admin can fetch "
                "Support options for a trial customer."
            ),
        )

    support_managers = db.query(Employee).filter(
        Employee.department == "SUPPORT",
        Employee.status == "ACTIVE",
        Employee.role.in_(sorted(SUPPORT_MANAGER_ROLES)),
    ).order_by(Employee.name.asc()).all()

    return [
        {
            "id": e.id,
            "name": e.name,
            "role": e.role,
            "department": e.department,
            "manager_id": e.manager_id,
            "status": e.status
        }
        for e in support_managers
        if is_active_support_manager(e, db)
    ]


@router.put("/{lead_id}/support-assign")
def assign_support_lead(
    lead_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Assign a Support Executive to a lead that has explicitly been converted to
    Support. Allowed for Support Managers and Admin only.

    The Sales owner (``Lead.assigned_to``) is never overwritten. Support
    assignment is written to the Support handoff and to an auditable
    ``LeadAssignment`` row using the ``MANUAL_SUPPORT`` method.
    """
    norm_role = normalize_role(current_user.role)
    if norm_role not in [ROLE_ADMIN, ROLE_SUPPORT_MANAGER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Only Support Managers and Admin can assign support leads."
        )

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if normalize_lead_status(lead.status) != STATUS_CONVERTED_TO_SUPPORT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Support assignment is available only after the deal is marked "
                "Won and then explicitly converted to Support."
            )
        )

    new_agent_id = payload.get("assigned_agent_id")
    if not new_agent_id:
        raise HTTPException(status_code=400, detail="assigned_agent_id is required")

    try:
        new_agent_id = int(new_agent_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="assigned_agent_id must be an integer")

    # Optional conversion remarks entered on the Support Assignment form.
    # They are stored on the existing Support handoff notes and the auditable
    # LeadAssignment row, so no schema change is required.
    raw_remarks = payload.get("remarks") or payload.get("conversion_remarks") or ""
    remarks = str(raw_remarks).strip()[:2000]

    agent = db.query(Employee).filter(Employee.id == new_agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Support Executive not found")
    if not is_active_support_executive(agent, db):
        raise HTTPException(
            status_code=400,
            detail=(
                "Only an active Support Executive can be assigned. Sales employees, "
                "Managers/Admins, inactive users and other departments are not allowed."
            )
        )

    from models.workflow import SupportHandoff
    handoff = (
        db.query(SupportHandoff)
        .filter(SupportHandoff.lead_id == lead.id)
        .order_by(desc(SupportHandoff.id))
        .first()
    )
    if not handoff:
        raise HTTPException(
            status_code=409,
            detail="No Support handoff exists for this lead. Convert the won deal to Support first."
        )

    current_emp = get_employee_for_user(current_user, db)
    assigner_id = current_emp.id if current_emp else None

    # Idempotency: re-submitting the same Support Executive must not create a
    # duplicate assignment history row or a second notification.
    if handoff.assigned_agent_id == agent.id:
        return {
            "success": True,
            "already_assigned": True,
            "lead_id": lead.id,
            "support_handoff_id": handoff.id,
            "assigned_agent_id": agent.id,
            "assigned_agent_name": agent.name,
            "support_assigned_at": handoff.updated_at.isoformat() if handoff.updated_at else None,
            "sales_owner_id": lead.assigned_to,
            "support_manager_id": handoff.support_manager_id,
            "support_manager_name": handoff.support_manager_name,
        }

    handoff.assigned_agent_id = agent.id
    handoff.assigned_agent_name = agent.name

    if remarks:
        existing_notes = (handoff.support_notes or "").strip()
        if remarks not in existing_notes:
            handoff.support_notes = (
                f"{existing_notes}\n{remarks}".strip() if existing_notes else remarks
            )

    # Support Manager ownership must be recorded exactly once. Prefer the
    # Support Manager performing the assignment, otherwise fall back to the
    # agent's reporting manager.
    if not handoff.support_manager_id:
        if norm_role == ROLE_SUPPORT_MANAGER and current_emp:
            handoff.support_manager_id = current_emp.id
            handoff.support_manager_name = current_emp.name
        else:
            mgr = _resolve_employee_manager(agent, db)
            if mgr:
                handoff.support_manager_id = mgr.id
                handoff.support_manager_name = mgr.name

    assignment = LeadAssignment(
        lead_id=lead.id,
        assigned_to=agent.id,
        assigned_by=assigner_id,
        assigned_at=datetime.utcnow(),
        assignment_method="MANUAL_SUPPORT",
        notes=(
            f"Assigned to Support Executive {agent.name} by {current_user.username} "
            f"after conversion to Support."
            + (f" Conversion remarks: {remarks}" if remarks else "")
        )
    )
    db.add(assignment)

    log_lead_activity(
        db=db,
        lead_id=lead.id,
        performed_by_id=assigner_id,
        activity_type="ASSIGNED_TO_SUPPORT",
        description=(
            f"Assigned to Support Executive {agent.name} by {current_user.username} "
            f"after conversion to Support."
            + (f" Conversion remarks: {remarks}" if remarks else "")
        )
    )

    db.commit()
    db.refresh(lead)

    log_audit(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action="SUPPORT_ASSIGN",
        entity_type="LEAD",
        entity_id=lead.id,
        details=(
            f"Support Executive {agent.name} assigned to converted Lead #{lead.id} "
            f"by {current_user.username}."
            + (f" Conversion remarks: {remarks}" if remarks else "")
        )
    )

    return {
        "success": True,
        "already_assigned": False,
        "lead_id": lead.id,
        "support_handoff_id": handoff.id,
        "assigned_agent_id": agent.id,
        "assigned_agent_name": agent.name,
        "support_assigned_at": assignment.assigned_at.isoformat(),
        "conversion_remarks": remarks or None,
        "sales_owner_id": lead.assigned_to,
        "support_manager_id": handoff.support_manager_id,
        "support_manager_name": handoff.support_manager_name,
    }


@router.put("/{lead_id}/support-status", response_model=SupportHandoffOut)
def update_support_lead_status(
    lead_id: int,
    payload: SupportStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update the independent Support status for a handed-over customer.

    This is the only status endpoint Support roles may use. It never writes to
    ``Lead.status`` (Sales status) or ``LeadStatusHistory``; all Support
    changes are recorded on the workflow timeline.
    """
    norm_role = normalize_role(current_user.role)
    if norm_role not in [ROLE_ADMIN, ROLE_SUPPORT_MANAGER, ROLE_SUPPORT_EXECUTIVE] and not _is_support_actor(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Only Support team and Admin can update the Support status.",
        )

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    from models.workflow import SupportHandoff

    handoff = (
        db.query(SupportHandoff)
        .filter(SupportHandoff.lead_id == lead.id)
        .order_by(desc(SupportHandoff.id))
        .first()
    )
    if not handoff:
        raise HTTPException(
            status_code=404,
            detail="No Support handover exists for this lead.",
        )

    if norm_role != ROLE_ADMIN and not is_support_lead_authorized(lead, current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You can only update Support status for customers assigned to you.",
        )

    requested_status = (
        payload.support_status or payload.onboarding_status or payload.status
    )
    if requested_status is not None:
        try:
            require_support_status(requested_status)
        except InvalidSupportStatusError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    try:
        from services.workflow_service import WorkflowService

        return WorkflowService.update_support_status(
            db=db,
            support_id=handoff.id,
            update_data=payload.dict(exclude_unset=True),
            current_user=current_user,
        )
    except InvalidSupportStatusError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{lead_id}", response_model=LeadOut)
def get_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    norm_role = normalize_role(current_user.role)
    if norm_role in [ROLE_SUPPORT_MANAGER, ROLE_SUPPORT_EXECUTIVE]:
        if not is_support_lead_authorized(lead, current_user, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: Support team cannot access this Sales lead."
            )
        return build_lead_out(lead, current_user, db)

    if not user_has_permission(current_user, "leads", "view", db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You do not have permission to view leads."
        )

    current_emp = get_employee_for_user(current_user, db)
    scope = get_user_view_scope(current_user, "leads", db)

    # DYNAMIC 403 SECURITY ENFORCEMENT
    if scope == "own":
        if not current_emp or lead.assigned_to != current_emp.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only view leads assigned to you."
            )
    elif scope == "team":
        team_ids = get_team_employee_ids_from_user(current_user, db)
        if lead.assigned_to is not None and lead.assigned_to not in team_ids and (current_emp and lead.assigned_by != current_emp.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only view leads assigned to your team or unassigned leads."
            )

    return build_lead_out(lead, current_user, db)

@router.put("/{lead_id}", response_model=LeadOut)
def update_lead(
    lead_id: int,
    lead_in: LeadUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("leads", "edit"))
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    norm_role = normalize_role(current_user.role)
    if norm_role in [ROLE_SUPPORT_MANAGER, ROLE_SUPPORT_EXECUTIVE]:
        if not is_support_lead_authorized(lead, current_user, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: Support team cannot access this Sales lead."
            )

    if lead_in.status is not None and _is_support_actor(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Support team cannot modify the Sales lead status. "
                "Use the Support status endpoint instead."
            ),
        )

    current_emp = get_employee_for_user(current_user, db)
    emp_id = current_emp.id if current_emp else None
    emp_name = current_emp.name if current_emp else current_user.username

    scope = get_user_view_scope(current_user, "leads", db)
    if norm_role not in [ROLE_SUPPORT_MANAGER, ROLE_SUPPORT_EXECUTIVE]:
        if scope == "own":
            if not current_emp or lead.assigned_to != current_emp.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied. You can only update leads assigned to you."
                )
            if not user_has_permission(current_user, "leads", "assign", db):
                lead_in.source = None
        elif scope == "team":
            team_ids = get_team_employee_ids_from_user(current_user, db)
            if lead.assigned_to is not None and lead.assigned_to not in team_ids and (current_emp and lead.assigned_by != current_emp.id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied. You can only update leads assigned to your team."
                )

    if lead_in.first_name is not None: lead.first_name = lead_in.first_name
    if lead_in.last_name is not None: lead.last_name = lead_in.last_name
    if lead_in.name is not None: lead.name = lead_in.name
    elif lead_in.first_name is not None or lead_in.last_name is not None:
        lead.name = f"{lead.first_name or ''} {lead.last_name or ''}".strip()

    if lead_in.phone is not None: lead.phone = lead_in.phone
    if lead_in.whatsapp_number is not None: lead.whatsapp_number = lead_in.whatsapp_number
    if lead_in.email is not None: lead.email = lead_in.email
    if lead_in.designation is not None: lead.designation = lead_in.designation
    if lead_in.company is not None: lead.company = lead_in.company
    if lead_in.industry is not None: lead.industry = lead_in.industry
    if lead_in.website is not None: lead.website = lead_in.website
    if lead_in.company_size is not None: lead.company_size = lead_in.company_size
    if lead_in.city is not None: lead.city = lead_in.city
    if lead_in.state is not None: lead.state = lead_in.state
    if hasattr(lead_in, 'country') and lead_in.country is not None: lead.country = lead_in.country
    old_status = lead.status
    conversion_requested = (
        lead_in.status is not None
        and normalize_lead_status(lead_in.status) == STATUS_CONVERTED_TO_SUPPORT
    )
    if lead_in.status is not None and not conversion_requested:
        lead.status = lead_in.status
        if is_trial_status(lead.status) and not getattr(lead, "trial_start_date", None):
            lead.trial_start_date = get_ist_now().date()
        if lead_in.status != old_status:
            db.add(LeadStatusHistory(
                lead_id=lead.id,
                old_status=old_status,
                new_status=lead_in.status,
                changed_by=emp_id,
                changed_at=datetime.utcnow()
            ))
        if normalize_lead_status(lead_in.status) == "WON" or normalize_lead_status(lead_in.status) == "CONVERTED":
            if old_status != lead_in.status:
                from services.workflow_service import WorkflowService
                WorkflowService.trigger_finance_handoff_on_won(
                    db=db,
                    lead=lead,
                    performed_by_user=current_user
                )
    if lead_in.campaign_name is not None: lead.campaign_name = lead_in.campaign_name
    if lead_in.rating is not None: lead.rating = lead_in.rating
    if lead_in.priority is not None: lead.priority = lead_in.priority
    if lead_in.requirement_notes is not None: lead.requirement_notes = lead_in.requirement_notes
    if lead_in.followup_date is not None: lead.followup_date = lead_in.followup_date
    if lead_in.followup_time is not None: lead.followup_time = lead_in.followup_time

    new_trial_start = (
        lead_in.trial_start_date
        if lead_in.trial_start_date is not None
        else getattr(lead, "trial_start_date", None)
    )
    new_trial_end = (
        lead_in.trial_end_date
        if lead_in.trial_end_date is not None
        else getattr(lead, "trial_end_date", None)
    )
    if new_trial_start and new_trial_end and new_trial_end < new_trial_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trial End Date cannot be before Trial Start Date.",
        )

    # Trial duration drives the expiry date. When the client sends it, the
    # server recomputes trial_end_date = trial_start_date + duration so the
    # user never has to calculate (or can never submit a wrong) end date.
    trial_fields = set(getattr(lead_in, "model_fields_set", set()) or ())
    trial_duration_days = None
    if "trial_duration_days" in trial_fields and lead_in.trial_duration_days is not None:
        try:
            trial_duration_days = int(lead_in.trial_duration_days)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Trial Duration must be a whole number of days.",
            )
        if trial_duration_days < 1 or trial_duration_days > 365:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Trial Duration must be between 1 and 365 days.",
            )

    if trial_duration_days is not None:
        duration_start = (
            lead_in.trial_start_date
            or getattr(lead, "trial_start_date", None)
            or get_ist_now().date()
        )
        lead.trial_start_date = duration_start
        lead.trial_end_date = duration_start + timedelta(days=trial_duration_days)
    else:
        if lead_in.trial_start_date is not None:
            lead.trial_start_date = lead_in.trial_start_date
        if lead_in.trial_end_date is not None:
            lead.trial_end_date = lead_in.trial_end_date

    # ------------------------------------------------------------------
    # Trial Support Manager assignment (Set Trial Period modal).
    # Reuses the same canonical role/department validation and the same
    # auditable LeadAssignment rows as the post-conversion assignment flow.
    # Sales ownership (Lead.assigned_to) and Support statuses are untouched.
    # ------------------------------------------------------------------
    if "trial_support_employee_id" in trial_fields:
        if _is_support_actor(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Support team cannot change the Trial Support assignment. "
                    "The Sales employee or Sales Manager selects the Support "
                    "Manager responsible for a trial customer."
                ),
            )
        requested_support_id = lead_in.trial_support_employee_id
        current_support_id = getattr(lead, "trial_support_employee_id", None)
        if requested_support_id is None:
            if current_support_id:
                lead.trial_support_employee_id = None
                log_lead_activity(
                    db=db,
                    lead_id=lead.id,
                    performed_by_id=emp_id,
                    activity_type="TRIAL_SUPPORT_UNASSIGNED",
                    description=(
                        f"{emp_name} cleared the Trial Support Manager "
                        f"assignment for Lead #{lead.id}."
                    ),
                )
        else:
            support_emp = (
                db.query(Employee).filter(Employee.id == requested_support_id).first()
            )
            if not support_emp:
                raise HTTPException(
                    status_code=404, detail="Support employee not found"
                )
            # A value that is already stored (written before Support Manager
            # selection was introduced) is kept untouched, so existing trial
            # assignments are never lost. Only a *new* selection has to be an
            # active Support Manager.
            if (
                support_emp.id != current_support_id
                and not is_active_support_manager(support_emp, db)
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Only an active Support Manager can be assigned to a "
                        "trial customer."
                    ),
                )
            if current_support_id != support_emp.id:
                lead.trial_support_employee_id = support_emp.id
                already_recorded = any(
                    (getattr(a, "assignment_method", "") or "").upper()
                    == "TRIAL_SUPPORT"
                    and a.assigned_to == support_emp.id
                    for a in lead.assignments
                )
                if not already_recorded:
                    db.add(LeadAssignment(
                        lead_id=lead.id,
                        assigned_to=support_emp.id,
                        assigned_by=emp_id,
                        assigned_at=datetime.utcnow(),
                        assignment_method="TRIAL_SUPPORT",
                        notes=(
                            f"Assigned to Support Manager {support_emp.name} "
                            f"for the trial period by {current_user.username}."
                        ),
                    ))
                log_lead_activity(
                    db=db,
                    lead_id=lead.id,
                    performed_by_id=emp_id,
                    activity_type="TRIAL_SUPPORT_ASSIGNED",
                    description=(
                        f"Trial Support Manager assigned to {support_emp.name} "
                        f"by {current_user.username}."
                    ),
                )

    if lead_in.quotetask_quotation_amount is not None:
        new_amt = float(lead_in.quotetask_quotation_amount)
        lead.quotetask_quotation_amount = new_amt
        # Synchronize with Finance and Support Handoffs if present
        from models.workflow import FinanceHandoff, SupportHandoff
        fh = db.query(FinanceHandoff).filter(FinanceHandoff.lead_id == lead.id).first()
        if fh:
            fh.final_amount = new_amt
        sh = db.query(SupportHandoff).filter(SupportHandoff.lead_id == lead.id).first()
        if sh:
            sh.total_deal_amount = new_amt

    if lead_in.product_category is not None:
        cat_val = lead_in.product_category.strip().upper()
        if cat_val in ['BIOMETRIC', 'WAHRMS', 'UNCLASSIFIED']:
            lead.product_category = cat_val
            if cat_val in ['BIOMETRIC', 'WAHRMS']:
                lead.product_category_confirmed = True

    if lead_in.product_category_confirmed is not None:
        lead.product_category_confirmed = lead_in.product_category_confirmed

    if conversion_requested:
        from services.workflow_service import WorkflowService
        try:
            WorkflowService.convert_to_support(
                db=db,
                lead_id=lead.id,
                current_user=current_user
            )
        except PermissionError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc)
            )
        except ValueError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc)
            )
        db.refresh(lead)
        return build_lead_out(lead, current_user, db)

    log_lead_activity(
        db=db,
        lead_id=lead.id,
        performed_by_id=emp_id,
        activity_type="UPDATED",
        description=f"{emp_name} updated lead details"
    )

    db.commit()
    db.refresh(lead)

    log_audit(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action="LEAD_UPDATE",
        entity_type="LEAD",
        entity_id=lead.id,
        details=f"Lead #{lead.id} ({lead.name}) updated by {current_user.username}."
    )

    return build_lead_out(lead, current_user, db)

@router.put("/{lead_id}/assign", response_model=LeadOut)
def assign_lead(
    lead_id: int,
    assign_req: LeadAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("leads", "assign"))
):
    """
    Only ADMIN and MANAGER can assign / reassign leads.
    """
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    target_emp = db.query(Employee).filter(Employee.id == assign_req.assigned_to).first()
    if not target_emp:
        raise HTTPException(status_code=404, detail="Target employee not found")
    if not is_active_sales_manager(target_emp, db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Manual Sales assignment allows only active Sales Managers. "
                "Sales Executives, Support users, Managers/Admins and inactive "
                "employees are not eligible."
            )
        )

    current_emp = get_employee_for_user(current_user, db)
    assigner_id = current_emp.id if current_emp else None
    assigner_name = current_emp.name if current_emp else current_user.username

    prev_emp_name = lead.assigned_employee.name if lead.assigned_employee else "Unassigned"

    lead.assigned_to = target_emp.id
    lead.assigned_by = assigner_id
    lead.assigned_at = datetime.utcnow()

    if lead.status == "NEW":
        lead.status = "ASSIGNED"

    assignment_record = LeadAssignment(
        lead_id=lead.id,
        assigned_to=target_emp.id,
        assigned_by=assigner_id,
        assigned_at=datetime.utcnow(),
        assignment_method="MANUAL",
        notes=f"Manually assigned by {assigner_name}"
    )
    db.add(assignment_record)

    log_lead_activity(
        db=db,
        lead_id=lead.id,
        performed_by_id=assigner_id,
        activity_type="ASSIGNMENT_CHANGED" if prev_emp_name != "Unassigned" else "ASSIGNED",
        description=f"Assigned to {target_emp.name} by {assigner_name}"
    )

    db.commit()

    log_audit(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action="LEAD_ASSIGNMENT",
        entity_type="LEAD",
        entity_id=lead.id,
        details=f"Lead #{lead.id} assigned to {target_emp.name} by {assigner_name}."
    )

    db.refresh(lead)
    return build_lead_out(lead, current_user, db)

@router.put("/{lead_id}/status", response_model=LeadOut)
def change_lead_status(
    lead_id: int,
    status_req: LeadStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    current_emp = get_employee_for_user(current_user, db)
    emp_id = current_emp.id if current_emp else None
    emp_name = current_emp.name if current_emp else current_user.username

    if _is_support_actor(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Support team cannot modify the Sales lead status. "
                "Use the Support status endpoint instead."
            ),
        )

    norm_role = normalize_role(current_user.role)
    if current_user.role == "EMPLOYEE" or norm_role == ROLE_SALES_EXECUTIVE:
        if not current_emp or lead.assigned_to != current_emp.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only update status for leads assigned to you."
            )

    old_status = lead.status
    new_status = status_req.status

    if normalize_lead_status(new_status) == STATUS_CONVERTED_TO_SUPPORT:
        from services.workflow_service import WorkflowService
        try:
            WorkflowService.convert_to_support(
                db=db,
                lead_id=lead.id,
                current_user=current_user
            )
        except PermissionError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc)
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc)
            )
        db.refresh(lead)
        return build_lead_out(lead, current_user, db)

    lead.status = new_status
    if is_trial_status(new_status) and not getattr(lead, "trial_start_date", None):
        # Record the first day of the trial without inventing an end date. The
        # assigned team must set trial_end_date to enable expiry reminders.
        lead.trial_start_date = get_ist_now().date()

    history = LeadStatusHistory(
        lead_id=lead.id,
        old_status=old_status,
        new_status=new_status,
        changed_by=emp_id,
        changed_at=datetime.utcnow()
    )
    db.add(history)

    log_lead_activity(
        db=db,
        lead_id=lead.id,
        performed_by_id=emp_id,
        activity_type="STATUS_CHANGED",
        description=f"{emp_name} changed status {old_status} -> {new_status}"
    )

    if normalize_lead_status(new_status) in {"CONVERTED", "WON"}:
        from services.workflow_service import WorkflowService
        WorkflowService.trigger_finance_handoff_on_won(
            db=db,
            lead=lead,
            performed_by_user=current_user
        )

    log_audit(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action="LEAD_STATUS_CHANGE",
        entity_type="LEAD",
        entity_id=lead.id,
        details=f"Status changed from {old_status} to {new_status} by {emp_name}."
    )

    db.commit()
    db.refresh(lead)
    return build_lead_out(lead, current_user, db)

@router.get("/{lead_id}/proformas")
def get_lead_proformas_list(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetches proforma invoices for this lead/deal for the Proforma-Driven WON handoff workflow.
    """
    from services.workflow_service import WorkflowService
    try:
        return WorkflowService.get_lead_proforma_invoices(db=db, lead_id=lead_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error fetching proformas for lead {lead_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{lead_id}/won")
def mark_deal_won_with_support_manager(
    lead_id: int,
    payload: DealWonRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Sales closes a Deal as WON.

    Won remains a Sales milestone: the Support handoff snapshot is prepared but
    Support is neither assigned nor notified. Support assignment only becomes
    available after an explicit Converted to Support transition.
    """
    if _is_support_actor(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Support team cannot modify the Sales lead status.",
        )

    can_edit = user_has_permission(current_user, "leads", "edit", db) or current_user.role in ["ADMIN", "MANAGER", "SALES"]
    if not can_edit:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to mark this deal as WON.")

    try:
        from services.workflow_service import WorkflowService
        result = WorkflowService.complete_deal_won_workflow(
            db=db,
            lead_id=lead_id,
            won_data=payload.dict(exclude_unset=True),
            current_user=current_user
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Error completing deal won workflow: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process deal WON: {str(e)}")

@router.post("/{lead_id}/convert-to-support")
def convert_deal_to_support(
    lead_id: int,
    payload: Optional[dict] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Explicitly convert a WON deal to the Support onboarding queue.

    Restricted to Admin and Sales Managers. The conversion records the
    converter and timestamp but never assigns Support; a Support Manager/Admin
    performs that as a separate step.
    """
    if _is_support_actor(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Support team cannot modify the Sales lead status.",
        )

    note = (payload or {}).get("note") if isinstance(payload, dict) else None
    from services.workflow_service import WorkflowService
    try:
        return WorkflowService.convert_to_support(
            db=db,
            lead_id=lead_id,
            current_user=current_user,
            note=note
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error(f"Error converting deal to Support: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to convert deal to Support: {str(exc)}")

@router.put("/{lead_id}/won-amount")
def update_won_deal_amount(
    lead_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Edits the won deal amount for a WON or active deal.
    Immediately synchronizes Lead.quotetask_quotation_amount, FinanceHandoff.final_amount,
    and SupportHandoff.total_deal_amount, triggering automatic revenue recalculations.
    """
    can_edit = user_has_permission(current_user, "leads", "edit", db) or current_user.role in ["ADMIN", "MANAGER", "SALES"]
    if not can_edit:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to edit this deal amount.")

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Deal / Lead not found")

    new_amount = payload.get("amount")
    if new_amount is None:
        raise HTTPException(status_code=400, detail="Amount is required")
    try:
        new_amount = float(new_amount)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid amount value")

    lead.quotetask_quotation_amount = new_amount

    from models.workflow import FinanceHandoff, SupportHandoff
    fh = db.query(FinanceHandoff).filter(FinanceHandoff.lead_id == lead.id).first()
    if fh:
        fh.final_amount = new_amount

    sh = db.query(SupportHandoff).filter(SupportHandoff.lead_id == lead.id).first()
    if sh:
        sh.total_deal_amount = new_amount

    current_emp = get_employee_for_user(current_user, db)
    emp_id = current_emp.id if current_emp else None
    emp_name = current_emp.name if current_emp else current_user.username

    log_lead_activity(
        db=db,
        lead_id=lead.id,
        performed_by_id=emp_id,
        activity_type="DEAL_AMOUNT_UPDATED",
        description=f"{emp_name} updated deal won amount to Rs. {new_amount:,.2f}"
    )

    db.commit()
    db.refresh(lead)

    return {
        "success": True,
        "lead_id": lead.id,
        "new_amount": new_amount,
        "message": f"Won deal amount updated to ₹{new_amount:,.2f}"
    }

@router.post("/{lead_id}/notes", response_model=LeadOut)
def add_lead_note(
    lead_id: int,
    note_req: LeadNoteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    current_emp = get_employee_for_user(current_user, db)
    emp_id = current_emp.id if current_emp else None
    emp_name = current_emp.name if current_emp else current_user.username

    if current_user.role == "EMPLOYEE":
        if not current_emp or lead.assigned_to != current_emp.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only add notes to leads assigned to you."
            )

    log_lead_activity(
        db=db,
        lead_id=lead.id,
        performed_by_id=emp_id,
        activity_type="NOTE_ADDED",
        description=f"{emp_name}: {note_req.note}"
    )

    db.commit()
    db.refresh(lead)
    return build_lead_out(lead, current_user, db)

@router.delete("/{lead_id}")
def delete_lead(
    lead_id: int,
    reason: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Unified Delete Access & Approval:
    - EMPLOYEE: 403 Forbidden
    - MANAGER: Submits pending DeletionRequest for Admin approval
    - ADMIN: Immediately permanently deletes lead
    """
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    norm_role = normalize_role(current_user.role)
    if norm_role in [ROLE_SUPPORT_MANAGER, ROLE_SUPPORT_EXECUTIVE]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Support team cannot delete Sales leads."
        )
    if norm_role == ROLE_SALES_EXECUTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Sales Executives cannot delete lead records."
        )

    def do_delete():
        db.delete(lead)
        db.commit()

    return handle_entity_deletion(
        db=db,
        current_user=current_user,
        entity_type="LEAD",
        entity_id=lead.id,
        entity_name=lead.name,
        delete_fn=do_delete,
        reason=reason
    )

@router.get("/{lead_id}/assignments", response_model=List[LeadAssignmentOut])
def get_lead_assignments(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    assignments = db.query(LeadAssignment).filter(LeadAssignment.lead_id == lead_id).order_by(desc(LeadAssignment.assigned_at)).all()
    out = []
    for asgn in assignments:
        to_name = asgn.assigned_to_employee.name if asgn.assigned_to_employee else f"Employee #{asgn.assigned_to}"
        by_name = asgn.assigned_by_employee.name if asgn.assigned_by_employee else "System (Automatic)"
        out.append(LeadAssignmentOut(
            id=asgn.id,
            lead_id=asgn.lead_id,
            assigned_to=asgn.assigned_to,
            assigned_to_name=to_name,
            assigned_by=asgn.assigned_by,
            assigned_by_name=by_name,
            assigned_at=asgn.assigned_at,
            assignment_method=getattr(asgn, "assignment_method", "MANUAL") or "MANUAL",
            notes=asgn.notes
        ))
    return out

@router.post("/trigger-auto-assign")
def trigger_auto_assignment_manually(
    timeout_minutes: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "MANAGER"]))
):
    from services.lead_assignment_service import auto_assign_pending_leads
    count = auto_assign_pending_leads(db, override_timeout_minutes=timeout_minutes)
    return {
        "message": f"Auto-assignment run completed. Assigned {count} unassigned leads.",
        "assigned_count": count,
        "timeout_minutes_override": timeout_minutes
    }

@router.get("/auto-assign/config", response_model=AutoAssignConfigOut)
def get_auto_assign_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from services.lead_assignment_service import get_or_create_auto_assign_config
    return get_or_create_auto_assign_config(db)

@router.put("/auto-assign/config", response_model=AutoAssignConfigOut)
def update_auto_assign_config(
    config_in: AutoAssignConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"]))
):
    """
    STRICT ADMIN ONLY: Update Lead Auto-Assignment Settings.
    Managers and Employees cannot change auto-assignment rules.
    """
    from services.lead_assignment_service import get_or_create_auto_assign_config
    cfg = get_or_create_auto_assign_config(db)

    cfg.enabled = config_in.enabled
    cfg.waiting_time_minutes = max(1, config_in.waiting_time_minutes)
    cfg.assignment_method = config_in.assignment_method
    cfg.eligible_roles = config_in.eligible_roles
    cfg.working_hours_enabled = config_in.working_hours_enabled
    cfg.working_hours_start = config_in.working_hours_start
    cfg.working_hours_end = config_in.working_hours_end

    db.commit()
    db.refresh(cfg)

    log_audit(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action="UPDATE_AUTO_ASSIGN_CONFIG",
        entity_type="SYSTEM_SETTINGS",
        entity_id=cfg.id,
        details=f"Admin {current_user.username} updated Auto Lead Assignment config: enabled={cfg.enabled}, waiting_time={cfg.waiting_time_minutes}m, method={cfg.assignment_method}."
    )

    return cfg

@router.get("/{lead_id}/waquote/documents")
def get_lead_waquote_documents(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    from models.quotation import Quotation
    filters = [Quotation.lead_id == lead.id]
    if lead.phone and len(lead.phone.strip()) >= 7:
        filters.append(Quotation.phone.ilike(f"%{lead.phone.strip()[-10:]}%"))
    if lead.email and "@" in lead.email:
        filters.append(Quotation.email == lead.email.strip())

    records = db.query(Quotation).filter(or_(*filters)).order_by(desc(Quotation.created_at)).all()
    formatted = []
    for r in records:
        total_val = float(r.grand_total or 0.0)
        paid_val = float(r.amount_paid or 0.0)
        balance_val = max(0.0, total_val - paid_val)
        formatted.append({
            "id": f"local_{r.id}",
            "number": r.doc_number,
            "docType": r.doc_type,
            "status": invoice_document_status(r),
            "paymentStatus": r.payment_status,
            "issueDateFormatted": r.issue_date.strftime("%d/%m/%Y") if r.issue_date else "—",
            "grandTotal": total_val,
            "financials": {
                "grandTotal": total_val,
                "totalPaid": paid_val,
                "balance": balance_val
            },
            "pdfUrl": r.pdf_url
        })
    return {"ok": True, "documents": formatted}

@router.post("/{lead_id}/waquote/sync")
def sync_lead_waquote_status(
    lead_id: int,
    doc_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    from models.quotation import Quotation
    doc = None
    if doc_id:
        clean_id = doc_id.replace("local_", "").strip()
        if clean_id.isdigit():
            doc = db.query(Quotation).filter(Quotation.id == int(clean_id)).first()
        if not doc:
            doc = db.query(Quotation).filter(Quotation.doc_number == doc_id.strip()).first()
    if not doc and lead.quotetask_quotation_id:
        clean_id = str(lead.quotetask_quotation_id).replace("local_", "").strip()
        if clean_id.isdigit():
            doc = db.query(Quotation).filter(Quotation.id == int(clean_id)).first()
    if not doc and lead.quotetask_quotation_number:
        doc = db.query(Quotation).filter(Quotation.doc_number == lead.quotetask_quotation_number).first()
    if not doc:
        doc = db.query(Quotation).filter(Quotation.lead_id == lead.id).order_by(desc(Quotation.created_at)).first()

    if doc:
        lead.quotetask_quotation_id = str(doc.id)
        lead.quotetask_quotation_number = doc.doc_number
        lead.quotetask_quotation_status = doc.status
        lead.quotetask_quotation_amount = doc.grand_total
        db.commit()
        return {"ok": True, "synced": True, "status": doc.status, "doc_number": doc.doc_number, "amount": doc.grand_total}
    return {"ok": True, "synced": False, "message": "No quotation found for lead"}

@router.post("/{lead_id}/quotetask/create-quotation")
def create_lead_quotetask_quotation(
    lead_id: int,
    req: Optional[QuoteTaskQuotationCreateRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    current_emp = get_employee_for_user(current_user, db)
    if current_user.role == "EMPLOYEE" and current_emp and lead.assigned_to != current_emp.id:
        raise HTTPException(status_code=403, detail="Access denied. You can only create quotations for leads assigned to you.")

    return sync_lead_waquote_status(lead_id=lead_id, db=db, current_user=current_user)

@router.post("/{lead_id}/quotetask/sync")
def sync_lead_quotetask_status(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return sync_lead_waquote_status(lead_id=lead_id, db=db, current_user=current_user)


@router.get("/{lead_id}/download-quotation")
def download_lead_quotation(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    current_emp = get_employee_for_user(current_user, db)
    norm_role = (current_user.role or "").strip().upper()
    if norm_role in ["SUPPORT_MANAGER", "SUPPORT_EXECUTIVE", "SUPPORT"]:
        raise HTTPException(status_code=403, detail="Access denied. Support team cannot access sales quotations.")
    if norm_role in ["SALES_EXECUTIVE", "EMPLOYEE", "SALES"]:
        if current_emp and lead.assigned_to and lead.assigned_to != current_emp.id:
            raise HTTPException(status_code=403, detail="Access denied. You can only download quotations for leads assigned to you.")
    elif norm_role in ["SALES_MANAGER", "MANAGER"]:
        from services.hierarchy_service import get_team_employee_ids_from_user
        team_ids = get_team_employee_ids_from_user(current_user, db)
        if current_emp and current_emp.id not in team_ids:
            team_ids.append(current_emp.id)
        if lead.assigned_to and lead.assigned_to not in team_ids:
            raise HTTPException(status_code=403, detail="Access denied. You can only download quotations for leads in your team.")

    from models.quotation import Quotation
    doc = db.query(Quotation).filter(Quotation.lead_id == lead.id, Quotation.doc_type == "quotation").order_by(desc(Quotation.created_at)).first()
    if not doc:
        doc = db.query(Quotation).filter(Quotation.lead_id == lead.id).order_by(desc(Quotation.created_at)).first()
    
    from services.pdf_service import generate_quotation_pdf
    if doc:
        pdf_bytes = generate_quotation_pdf(doc)
        clean_num = (doc.doc_number or f"QT-{doc.id}").replace("/", "-").replace("\\", "-")
    else:
        amt = float(lead.quotetask_quotation_amount or 15000.0)
        sub = round(amt / 1.18, 2)
        snapshot = {
            "doc_number": f"CHN/QT/2627/{lead.id:04d}",
            "customer_name": lead.name,
            "company_name": lead.company,
            "phone": lead.phone,
            "email": lead.email,
            "subtotal": sub,
            "cgst": round((amt - sub) / 2.0, 2),
            "sgst": round((amt - sub) / 2.0, 2),
            "tax_total": round(amt - sub, 2),
            "grand_total": amt,
            "line_items": [{
                "description": lead.requirement_notes or "WAHRMS Business Subscription",
                "hsn": "998314",
                "qty": 1,
                "rate": sub,
                "gstRate": 0.18
            }],
            "terms_and_conditions": WAHRMS_TERMS_AND_CONDITIONS,
            "prepared_by": (current_user.employee.name if getattr(current_user, 'employee', None) else current_user.username) or "Authorized Signatory"
        }
        pdf_bytes = generate_quotation_pdf(snapshot)
        clean_num = f"CHN-QT-2627-{lead.id:04d}"

    filename = f"Quotation_{clean_num}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Document-Type": "quotation"
        }
    )


@router.get("/{lead_id}/download-proforma")
def download_lead_proforma(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    current_emp = get_employee_for_user(current_user, db)
    norm_role = (current_user.role or "").strip().upper()
    if norm_role in ["SUPPORT_MANAGER", "SUPPORT_EXECUTIVE", "SUPPORT"]:
        raise HTTPException(status_code=403, detail="Access denied. Support team cannot access sales quotations.")
    if norm_role in ["SALES_EXECUTIVE", "EMPLOYEE", "SALES"]:
        if current_emp and lead.assigned_to and lead.assigned_to != current_emp.id:
            raise HTTPException(status_code=403, detail="Access denied. You can only download quotations for leads assigned to you.")
    elif norm_role in ["SALES_MANAGER", "MANAGER"]:
        from services.hierarchy_service import get_team_employee_ids_from_user
        team_ids = get_team_employee_ids_from_user(current_user, db)
        if current_emp and current_emp.id not in team_ids:
            team_ids.append(current_emp.id)
        if lead.assigned_to and lead.assigned_to not in team_ids:
            raise HTTPException(status_code=403, detail="Access denied. You can only download quotations for leads in your team.")

    from models.quotation import Quotation
    doc = db.query(Quotation).filter(Quotation.lead_id == lead.id, Quotation.doc_type == "proforma").order_by(desc(Quotation.created_at)).first()
    if not doc:
        doc = db.query(Quotation).filter(Quotation.lead_id == lead.id).order_by(desc(Quotation.created_at)).first()
    
    from services.pdf_service import generate_proforma_pdf
    if doc:
        pdf_bytes = generate_proforma_pdf(doc)
        clean_num = (doc.doc_number or f"PI-{doc.id}").replace("/", "-").replace("\\", "-")
    else:
        amt = float(lead.quotetask_quotation_amount or 15000.0)
        sub = round(amt / 1.18, 2)
        snapshot = {
            "doc_number": f"CHN/PI/2627/{lead.id:04d}",
            "customer_name": lead.name,
            "company_name": lead.company,
            "phone": lead.phone,
            "email": lead.email,
            "subtotal": sub,
            "cgst": round((amt - sub) / 2.0, 2),
            "sgst": round((amt - sub) / 2.0, 2),
            "tax_total": round(amt - sub, 2),
            "grand_total": amt,
            "line_items": [{
                "description": lead.requirement_notes or "WAHRMS Business Subscription",
                "hsn": "998314",
                "qty": 1,
                "rate": sub,
                "gstRate": 0.18
            }],
            "terms_and_conditions": WAHRMS_TERMS_AND_CONDITIONS,
            "prepared_by": (current_user.employee.name if getattr(current_user, 'employee', None) else current_user.username) or "Authorized Signatory"
        }
        pdf_bytes = generate_proforma_pdf(snapshot)
        clean_num = f"CHN-PI-2627-{lead.id:04d}"

    filename = f"Proforma_Invoice_{clean_num}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Document-Type": "proforma"
        }
    )


@router.get("/{lead_id}/download-invoice")
def download_lead_tax_invoice(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Downloads official Tax Invoice PDF for a lead/deal.
    Available to Sales/Finance/Admin once an invoice has been issued.
    """
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    from models.quotation import Quotation
    doc = db.query(Quotation).filter(Quotation.lead_id == lead.id, Quotation.doc_type == "invoice").order_by(desc(Quotation.created_at)).first()
    if not doc:
        # Check if Finance Handoff has invoice details
        from models.workflow import FinanceHandoff
        handoff = db.query(FinanceHandoff).filter(FinanceHandoff.lead_id == lead.id).first()
        if handoff:
            if handoff.invoice_number:
                doc = db.query(Quotation).filter(Quotation.doc_number == handoff.invoice_number.strip()).first()
            handoff_is_paid = normalize_finance_status(handoff.status) == FINANCE_STATUS_PAID
            if not doc and (handoff_is_paid or handoff.invoice_number):
                invoice_num = handoff.invoice_number or f"CHN/INV/26/{handoff.id:04d}"
                paid_amt = float(handoff.paid_amount or handoff.final_amount or 0.0)
                sub_val = round(paid_amt / 1.18, 2)
                tax_val = round(paid_amt - sub_val, 2)
                cgst_val = round(tax_val / 2.0, 2)
                sgst_val = round(tax_val / 2.0, 2)

                line_items_data = handoff.products_services or [
                    {
                        "description": handoff.customer_requirements or "WAHRMS Business Solution Subscription",
                        "qty": 1,
                        "rate": paid_amt,
                        "amount": paid_amt
                    }
                ]

                doc = Quotation(
                    doc_type="invoice",
                    doc_number=invoice_num,
                    status="issued",
                    payment_status="paid" if handoff_is_paid else "unpaid",
                    lead_id=lead.id,
                    customer_id=handoff.customer_id,
                    customer_name=handoff.customer_name or lead.name or "Valued Client",
                    company_name=handoff.company_name or lead.company or "",
                    phone=handoff.phone or lead.phone or "",
                    email=handoff.email or lead.email or "",
                    address=handoff.address or getattr(lead, 'address', '') or "Chennai, Tamil Nadu",
                    state="Tamil Nadu",
                    state_code="33",
                    tax_mode="intra",
                    subtotal=sub_val,
                    cgst=cgst_val,
                    sgst=sgst_val,
                    igst=0.0,
                    tax_total=tax_val,
                    grand_total=paid_amt,
                    amount_paid=paid_amt if handoff_is_paid else 0.0,
                    line_items=line_items_data,
                    terms_and_conditions="1. Payment received and verified by Finance.\n2. Goods/Services supplied as per Purchase Order.\n3. Subject to Chennai jurisdiction.",
                    prepared_by=getattr(current_user, 'full_name', None) or getattr(current_user, 'name', None) or current_user.username or "Finance Department",
                    issue_date=handoff.payment_date or handoff.confirmed_at or handoff.created_at or datetime.utcnow()
                )
                db.add(doc)
                handoff.invoice_number = invoice_num
                handoff.invoice_url = f"/api/integrations/waquote/invoices/{invoice_num}/download"
                db.commit()
                db.refresh(doc)
    
    if not doc:
        raise HTTPException(
            status_code=404,
            detail="Official Tax Invoice has not yet been issued by Finance for this deal. Please verify with the Finance team."
        )

    from services.pdf_service import generate_tax_invoice_pdf
    pdf_bytes = generate_tax_invoice_pdf(doc)
    clean_num = (doc.doc_number or f"INV-{doc.id}").replace("/", "-").replace("\\", "-")
    filename = f"Tax_Invoice_{clean_num}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Document-Type": "invoice"
        }
    )

