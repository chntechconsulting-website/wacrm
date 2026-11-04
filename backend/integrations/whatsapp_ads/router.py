"""CRM API for the WhatsApp Ad Leads listing, details, filters and export."""

import io
import json
import math
from datetime import datetime, time as dt_time
from typing import Any, List, Optional

import openpyxl
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from database import get_db
from integrations.whatsapp_ads.schemas import (
    WhatsAppAdFilterOptionsOut,
    WhatsAppAdLeadDetailOut,
    WhatsAppAdLeadOut,
    WhatsAppAdLeadPage,
    WhatsAppAdResolveResponse,
    WhatsAppAdSummaryOut,
)
from integrations.whatsapp_ads.service import SOURCE_LABEL, WhatsAppAdLeadService
from models.activity import LeadActivity
from models.employee import Employee
from models.lead import Lead
from models.user import User
from models.whatsapp_ad_lead import WhatsAppAdAttribution
from services.auth import require_permission
from services.hierarchy_service import (
    ROLE_SUPPORT_EXECUTIVE,
    ROLE_SUPPORT_MANAGER,
    get_team_employee_ids_from_user,
    normalize_role,
)
from services.permission_service import get_user_view_scope, user_has_permission

router = APIRouter(prefix="/whatsapp-ad-leads", tags=["WhatsApp Ad Leads"])

MODULE = "leads"


# ---------------------------------------------------------------------------
# Scope + filters
# ---------------------------------------------------------------------------
def _base_scoped_query(db: Session, current_user: User):
    """
    Attribution rows visible to the current user, using the exact same
    permission module, support-team exclusion and view scope as Leads.
    """
    norm_role = normalize_role(current_user.role)
    if norm_role in {ROLE_SUPPORT_MANAGER, ROLE_SUPPORT_EXECUTIVE}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Support team cannot access Sales leads.",
        )

    if not user_has_permission(current_user, MODULE, "view", db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You do not have permission to view leads.",
        )

    query = db.query(WhatsAppAdAttribution).join(
        Lead, Lead.id == WhatsAppAdAttribution.lead_id
    )
    scope = get_user_view_scope(current_user, MODULE, db)

    if scope == "none":
        return query.filter(False)

    if scope == "own":
        employee = db.query(Employee).filter(Employee.user_id == current_user.id).first()
        if not employee:
            return query.filter(False)
        return query.filter(Lead.assigned_to == employee.id)

    if scope == "team":
        team_ids = get_team_employee_ids_from_user(current_user, db)
        if not team_ids:
            return query.filter(False)
        return query.filter(
            or_(Lead.assigned_to.in_(team_ids), Lead.assigned_to.is_(None))
        )

    return query


def _parse_date_bound(value: Optional[str], end_of_day: bool = False) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.strptime(value.strip()[:10], "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date '{value}'. Use YYYY-MM-DD.",
        )
    return datetime.combine(
        parsed.date(), dt_time.max if end_of_day else dt_time.min
    )


def _apply_filters(
    query,
    search: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    campaign: Optional[str] = None,
    employee_id: Optional[int] = None,
    status_filter: Optional[str] = None,
):
    if search:
        term = search.strip()
        fmt = f"%{term}%"
        digits = "".join(filter(str.isdigit, term))
        conditions = [
            Lead.name.ilike(fmt),
            Lead.phone.ilike(fmt),
            Lead.whatsapp_number.ilike(fmt),
            Lead.email.ilike(fmt),
            Lead.company.ilike(fmt),
            WhatsAppAdAttribution.contact_name.ilike(fmt),
            WhatsAppAdAttribution.headline.ilike(fmt),
            WhatsAppAdAttribution.ad_body.ilike(fmt),
            WhatsAppAdAttribution.campaign_name.ilike(fmt),
            WhatsAppAdAttribution.ad_name.ilike(fmt),
            WhatsAppAdAttribution.source_id.ilike(fmt),
            WhatsAppAdAttribution.ctwa_clid.ilike(fmt),
        ]
        if len(digits) >= 4:
            conditions.append(Lead.phone.ilike(f"%{digits[-10:]}%"))
            conditions.append(Lead.whatsapp_number.ilike(f"%{digits[-10:]}%"))
        query = query.filter(or_(*conditions))

    start = _parse_date_bound(date_from, end_of_day=False)
    if start:
        query = query.filter(WhatsAppAdAttribution.created_at >= start)

    end = _parse_date_bound(date_to, end_of_day=True)
    if end:
        query = query.filter(WhatsAppAdAttribution.created_at <= end)

    if campaign and campaign.strip().upper() != "ALL":
        campaign_value = campaign.strip()
        query = query.filter(
            or_(
                WhatsAppAdAttribution.campaign_id == campaign_value,
                WhatsAppAdAttribution.campaign_name == campaign_value,
            )
        )

    if employee_id:
        query = query.filter(Lead.assigned_to == employee_id)

    if status_filter and status_filter.strip().upper() != "ALL":
        st = status_filter.strip().upper()
        if st in {"RE-INQUIRY", "REINQUIRY"}:
            query = query.filter(
                or_(Lead.status == "RE-INQUIRY", Lead.is_reinquiry.is_(True))
            )
        elif st in {"NEW", "NEW LEAD", "NEW_LEAD"}:
            query = query.filter(
                Lead.status.in_(["NEW", "NEW LEAD", "NEW_LEAD", "RE-INQUIRY"])
            )
        elif st in {"ASSIGNED"}:
            query = query.filter(Lead.status == "ASSIGNED")
        elif st in {"WON", "CONVERTED"}:
            query = query.filter(Lead.status.in_(["WON", "CONVERTED"]))
        elif st in {"LOST", "NOT_INTERESTED", "NOT INTERESTED"}:
            query = query.filter(
                Lead.status.in_(["LOST", "NOT_INTERESTED", "NOT INTERESTED"])
            )
        else:
            query = query.filter(Lead.status.ilike(status_filter.strip()))

    return query


def _ordered(query):
    return query.order_by(
        WhatsAppAdAttribution.created_at.desc(),
        WhatsAppAdAttribution.id.desc(),
    )


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------
def _to_out(attribution: WhatsAppAdAttribution) -> WhatsAppAdLeadOut:
    lead = attribution.lead
    assigned_name = None
    if lead is not None and lead.assigned_employee is not None:
        assigned_name = lead.assigned_employee.name

    return WhatsAppAdLeadOut(
        id=attribution.id,
        lead_id=attribution.lead_id,
        lead_enquiry_id=attribution.lead_enquiry_id,
        customer_name=(lead.name if lead else attribution.contact_name) or "Unknown",
        phone=(lead.phone if lead else attribution.phone) or "",
        whatsapp_number=(lead.whatsapp_number if lead else attribution.phone),
        first_enquiry_message=attribution.message_text,
        message_type=attribution.message_type,
        message_timestamp=attribution.message_timestamp,
        created_at=attribution.created_at,
        source="WHATSAPP_ADS",
        source_label=SOURCE_LABEL,
        channel=attribution.channel or "WHATSAPP",
        source_type=attribution.source_type,
        source_id=attribution.source_id,
        source_url=attribution.source_url,
        headline=attribution.headline,
        ad_body=attribution.ad_body,
        ctwa_clid=attribution.ctwa_clid,
        campaign_id=attribution.campaign_id,
        campaign_name=attribution.campaign_name,
        ad_name=attribution.ad_name,
        assigned_employee_id=(lead.assigned_to if lead else None),
        assigned_employee_name=assigned_name,
        status=(lead.status if lead else "NEW") or "NEW",
        priority=(lead.priority if lead else None),
        rating=(lead.rating if lead else None),
        is_reinquiry=bool(lead.is_reinquiry) if lead else False,
        reinquiry_count=(lead.reinquiry_count or 0) if lead else 0,
        resolution_status=attribution.resolution_status or "PENDING",
    )


def _parse_json(value: Optional[str]) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def _fmt_dt(value: Optional[datetime]) -> str:
    return value.strftime("%d-%m-%Y %I:%M %p") if value else ""


def _lead_dict(lead: Lead) -> dict:
    return {
        "id": lead.id,
        "name": lead.name,
        "phone": lead.phone,
        "whatsapp_number": lead.whatsapp_number,
        "email": lead.email,
        "company": lead.company,
        "source": lead.source,
        "status": lead.status,
        "priority": lead.priority,
        "rating": lead.rating,
        "requirement_notes": lead.requirement_notes,
        "campaign_name": lead.campaign_name,
        "assigned_to": lead.assigned_to,
        "assigned_employee_name": (
            lead.assigned_employee.name if lead.assigned_employee else None
        ),
        "created_at": lead.created_at,
        "first_enquiry_date": lead.first_enquiry_date,
        "latest_enquiry_date": lead.latest_enquiry_date,
        "is_reinquiry": bool(lead.is_reinquiry),
        "reinquiry_count": lead.reinquiry_count or 0,
        "total_enquiries": lead.total_enquiries or 1,
        "previous_sources": lead.previous_sources,
        "latest_source": lead.latest_source,
        "meta_lead_id": lead.meta_lead_id,
        "meta_form_id": lead.meta_form_id,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("", response_model=WhatsAppAdLeadPage)
@router.get("/", response_model=WhatsAppAdLeadPage)
def list_whatsapp_ad_leads(
    search: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    campaign: Optional[str] = None,
    employee_id: Optional[int] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(MODULE, "view")),
):
    query = _base_scoped_query(db, current_user)
    query = _apply_filters(
        query,
        search=search,
        date_from=date_from,
        date_to=date_to,
        campaign=campaign,
        employee_id=employee_id,
        status_filter=status_filter,
    )

    total = query.count()
    total_pages = math.ceil(total / page_size) if total else 0
    rows = (
        _ordered(query)
        .options(
            joinedload(WhatsAppAdAttribution.lead).joinedload(Lead.assigned_employee)
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return WhatsAppAdLeadPage(
        items=[_to_out(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/summary", response_model=WhatsAppAdSummaryOut)
def get_whatsapp_ad_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(MODULE, "view")),
):
    query = _base_scoped_query(db, current_user)
    total = query.count()
    unassigned = query.filter(Lead.assigned_to.is_(None)).count()
    campaigns = (
        query.with_entities(
            func.count(func.distinct(WhatsAppAdAttribution.campaign_id))
        ).scalar()
        or 0
    )
    resolved = query.filter(
        WhatsAppAdAttribution.resolution_status == "RESOLVED"
    ).count()
    pending = query.filter(
        WhatsAppAdAttribution.resolution_status.in_(["PENDING", "FAILED"])
    ).count()

    return WhatsAppAdSummaryOut(
        total=total,
        unassigned=unassigned,
        assigned=total - unassigned,
        campaigns=campaigns,
        resolved_attribution=resolved,
        pending_attribution=pending,
    )


@router.get("/filter-options", response_model=WhatsAppAdFilterOptionsOut)
def get_whatsapp_ad_filter_options(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(MODULE, "view")),
):
    query = _base_scoped_query(db, current_user)

    campaign_rows = (
        query.with_entities(
            WhatsAppAdAttribution.campaign_id,
            WhatsAppAdAttribution.campaign_name,
        )
        .filter(
            or_(
                WhatsAppAdAttribution.campaign_id.isnot(None),
                WhatsAppAdAttribution.campaign_name.isnot(None),
            )
        )
        .distinct()
        .all()
    )
    campaigns = []
    seen = set()
    for campaign_id, campaign_name in campaign_rows:
        value = (campaign_id or campaign_name or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        campaigns.append(
            {
                "id": value,
                "name": campaign_name or campaign_id or value,
            }
        )
    campaigns.sort(key=lambda item: item["name"].lower())

    employee_rows = (
        query.with_entities(Employee.id, Employee.name)
        .join(Employee, Employee.id == Lead.assigned_to)
        .distinct()
        .all()
    )
    employees = [
        {"id": employee_id, "name": name}
        for employee_id, name in employee_rows
        if employee_id and name
    ]
    employees.sort(key=lambda item: item["name"].lower())

    status_rows = (
        query.with_entities(Lead.status).filter(Lead.status.isnot(None)).distinct().all()
    )
    statuses = sorted({row[0] for row in status_rows if row[0]})

    return WhatsAppAdFilterOptionsOut(
        campaigns=campaigns,
        employees=employees,
        statuses=statuses,
    )


@router.get("/export")
def export_whatsapp_ad_leads(
    search: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    campaign: Optional[str] = None,
    employee_id: Optional[int] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(MODULE, "export")),
):
    query = _base_scoped_query(db, current_user)
    query = _apply_filters(
        query,
        search=search,
        date_from=date_from,
        date_to=date_to,
        campaign=campaign,
        employee_id=employee_id,
        status_filter=status_filter,
    )
    rows = (
        _ordered(query)
        .options(
            joinedload(WhatsAppAdAttribution.lead).joinedload(Lead.assigned_employee)
        )
        .limit(50000)
        .all()
    )

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "WhatsApp Ad Leads"

    headers = [
        "Lead ID",
        "Customer Name",
        "Phone",
        "First Enquiry Message",
        "Lead Source",
        "Campaign ID",
        "Campaign Name",
        "Ad ID",
        "Ad Name",
        "Source Type",
        "Source URL",
        "Headline",
        "Ad Body",
        "CTWA Click ID",
        "Enquiry Time",
        "Created At",
        "Assigned Employee",
        "Status",
        "Re-inquiry",
    ]
    sheet.append(headers)

    header_fill = PatternFill("solid", fgColor="1E40AF")
    header_font = Font(color="FFFFFF", bold=True)
    for cell in sheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for row in rows:
        item = _to_out(row)
        sheet.append(
            [
                item.lead_id,
                item.customer_name,
                item.phone,
                (item.first_enquiry_message or "")[:32000],
                "WhatsApp Ads",
                item.campaign_id or "",
                item.campaign_name or "",
                item.source_id or "",
                item.ad_name or "",
                item.source_type or "",
                item.source_url or "",
                (item.headline or "")[:32000],
                (item.ad_body or "")[:32000],
                item.ctwa_clid or "",
                _fmt_dt(item.message_timestamp),
                _fmt_dt(item.created_at),
                item.assigned_employee_name or "Unassigned",
                item.status,
                "Yes" if item.is_reinquiry else "No",
            ]
        )

    widths = [10, 24, 16, 42, 16, 16, 24, 18, 24, 14, 34, 34, 42, 26, 20, 20, 22, 16, 12]
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:S{max(sheet.max_row, 1)}"

    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    filename = f"WhatsApp_Ad_Leads_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        buffer,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{attribution_id}", response_model=WhatsAppAdLeadDetailOut)
def get_whatsapp_ad_lead(
    attribution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(MODULE, "view")),
):
    attribution = (
        _base_scoped_query(db, current_user)
        .options(
            joinedload(WhatsAppAdAttribution.lead).joinedload(Lead.assigned_employee)
        )
        .filter(WhatsAppAdAttribution.id == attribution_id)
        .first()
    )
    if not attribution:
        raise HTTPException(status_code=404, detail="WhatsApp Ad lead not found.")

    base = _to_out(attribution)
    lead = attribution.lead
    enquiries = []
    activities = []
    if lead is not None:
        for enquiry in lead.enquiries or []:
            enquiries.append(
                {
                    "id": enquiry.id,
                    "enquiry_number": enquiry.enquiry_number,
                    "enquiry_type": enquiry.enquiry_type,
                    "source": enquiry.source,
                    "campaign_name": enquiry.campaign_name,
                    "requirement_notes": enquiry.requirement_notes,
                    "created_at": enquiry.created_at,
                }
            )
        activity_rows = (
            db.query(LeadActivity)
            .filter(LeadActivity.lead_id == lead.id)
            .order_by(LeadActivity.created_at.desc())
            .limit(50)
            .all()
        )
        activities = [
            {
                "id": activity.id,
                "activity_type": activity.activity_type,
                "description": activity.description,
                "performed_by": activity.performed_by,
                "created_at": activity.created_at,
            }
            for activity in activity_rows
        ]

    return WhatsAppAdLeadDetailOut(
        **base.model_dump(),
        lead=_lead_dict(lead) if lead is not None else {},
        enquiries=enquiries,
        activities=activities,
        raw_referral=_parse_json(attribution.raw_referral),
        resolution_error=attribution.resolution_error,
        resolved_at=attribution.resolved_at,
    )


@router.post("/{attribution_id}/resolve-attribution", response_model=WhatsAppAdResolveResponse)
def resolve_whatsapp_ad_attribution(
    attribution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(MODULE, "edit")),
):
    attribution = (
        _base_scoped_query(db, current_user)
        .filter(WhatsAppAdAttribution.id == attribution_id)
        .first()
    )
    if not attribution:
        raise HTTPException(status_code=404, detail="WhatsApp Ad lead not found.")

    success = WhatsAppAdLeadService.resolve_attribution(db, attribution)
    db.refresh(attribution)
    return WhatsAppAdResolveResponse(
        success=success,
        resolution_status=attribution.resolution_status,
        campaign_id=attribution.campaign_id,
        campaign_name=attribution.campaign_name,
        ad_name=attribution.ad_name,
        error=attribution.resolution_error,
    )
