import io
import math
from datetime import datetime
from typing import Optional

import openpyxl
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models.brochure_enquiry import BrochureEnquiry
from models.employee import Employee
from models.user import User
from schemas.brochure_enquiry import (
    BROCHURE_FOLLOWUP_STATUSES,
    BrochureEmployeeOption,
    BrochureEnquiryOut,
    BrochureEnquiryPage,
    BrochureEnquiryUpdate,
    BrochureFilterOptionsOut,
    BrochureSummaryOut,
)
from services.auth import require_permission
from services.brochure_enquiry_service import (
    BrochureEnquiryService,
    normalize_followup_status,
)
from services.hierarchy_service import get_team_employee_ids_from_user
from services.permission_service import get_user_view_scope, user_has_permission
from utils.phone import sql_strip_phone
from utils.timezone import get_ist_now

router = APIRouter(prefix="/brochure-enquiries", tags=["Brochure Download People"])

MODULE = "brochure_downloads"


def _current_employee(user: User, db: Session) -> Optional[Employee]:
    return db.query(Employee).filter(Employee.user_id == user.id).first()


def _scoped_query(db: Session, current_user: User, query=None):
    """
    Apply the role's view scope. Unassigned brochure enquiries remain visible to
    sales users so a shared intake queue is never hidden before assignment.
    """
    query = query if query is not None else db.query(BrochureEnquiry)
    scope = get_user_view_scope(current_user, MODULE, db)

    if scope == "none":
        return query.filter(BrochureEnquiry.id == -1)
    if scope == "own":
        employee = _current_employee(current_user, db)
        if not employee:
            return query.filter(BrochureEnquiry.id == -1)
        return query.filter(
            or_(
                BrochureEnquiry.assigned_to == employee.id,
                BrochureEnquiry.assigned_to.is_(None),
            )
        )
    if scope == "team":
        employee_ids = get_team_employee_ids_from_user(current_user, db) or [-1]
        return query.filter(
            or_(
                BrochureEnquiry.assigned_to.in_(employee_ids),
                BrochureEnquiry.assigned_to.is_(None),
            )
        )
    # Admin / company / department scope sees the full brochure queue.
    return query


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def _apply_filters(
    query,
    search: Optional[str] = None,
    brochure: Optional[str] = None,
    employee_id: Optional[int] = None,
    followup_status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    download_date: Optional[str] = None,
):
    if search:
        clean_search = search.strip()
        search_fmt = f"%{clean_search}%"
        digits = "".join(filter(str.isdigit, clean_search))
        conditions = [
            BrochureEnquiry.name.ilike(search_fmt),
            BrochureEnquiry.phone.ilike(search_fmt),
            BrochureEnquiry.whatsapp_number.ilike(search_fmt),
            BrochureEnquiry.email.ilike(search_fmt),
            BrochureEnquiry.product_name.ilike(search_fmt),
            BrochureEnquiry.brochure_name.ilike(search_fmt),
            BrochureEnquiry.campaign.ilike(search_fmt),
            BrochureEnquiry.website_name.ilike(search_fmt),
        ]
        if len(digits) >= 4:
            # Match regardless of the spacing/country-code formatting the
            # website used when it stored the number.
            last_ten = digits[-10:]
            conditions.append(sql_strip_phone(BrochureEnquiry.phone).ilike(f"%{last_ten}%"))
            conditions.append(sql_strip_phone(BrochureEnquiry.whatsapp_number).ilike(f"%{last_ten}%"))
            conditions.append(sql_strip_phone(BrochureEnquiry.phone).ilike(f"%{digits}%"))
            conditions.append(sql_strip_phone(BrochureEnquiry.whatsapp_number).ilike(f"%{digits}%"))
        query = query.filter(or_(*conditions))

    if brochure and brochure.strip().upper() != "ALL":
        value = brochure.strip().lower()
        query = query.filter(
            or_(
                func.lower(BrochureEnquiry.product_name) == value,
                func.lower(BrochureEnquiry.brochure_name) == value,
            )
        )

    if employee_id:
        query = query.filter(BrochureEnquiry.assigned_to == employee_id)

    if followup_status and followup_status.strip().upper() != "ALL":
        try:
            normalized = normalize_followup_status(followup_status)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        query = query.filter(BrochureEnquiry.followup_status == normalized)

    if download_date:
        day = _parse_date(download_date)
        if day:
            query = query.filter(
                BrochureEnquiry.download_at >= day,
                BrochureEnquiry.download_at <= day.replace(hour=23, minute=59, second=59, microsecond=999999),
            )

    start = _parse_date(date_from)
    if start:
        query = query.filter(BrochureEnquiry.download_at >= start)

    end = _parse_date(date_to)
    if end:
        query = query.filter(
            BrochureEnquiry.download_at <= end.replace(hour=23, minute=59, second=59, microsecond=999999)
        )

    return query


def _serialize(record: BrochureEnquiry) -> dict:
    return BrochureEnquiryService.to_out_dict(record)


@router.get("", response_model=BrochureEnquiryPage)
@router.get("/", response_model=BrochureEnquiryPage)
def list_brochure_enquiries(
    search: Optional[str] = None,
    brochure: Optional[str] = None,
    employee_id: Optional[int] = None,
    followup_status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    download_date: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(MODULE, "view")),
):
    base_query = _scoped_query(db, current_user)
    query = _apply_filters(
        base_query,
        search=search,
        brochure=brochure,
        employee_id=employee_id,
        followup_status=followup_status,
        date_from=date_from,
        date_to=date_to,
        download_date=download_date,
    )

    total = query.count()
    total_pages = math.ceil(total / page_size) if total else 0
    records = (
        query.options(
            joinedload(BrochureEnquiry.assigned_employee),
            joinedload(BrochureEnquiry.lead),
            joinedload(BrochureEnquiry.customer),
        )
        .order_by(BrochureEnquiry.download_at.desc(), BrochureEnquiry.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "items": [_serialize(record) for record in records],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.get("/summary", response_model=BrochureSummaryOut)
def brochure_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(MODULE, "view")),
):
    base_query = _scoped_query(db, current_user)
    return {
        "total_downloads": base_query.count(),
        "pending_followups": base_query.filter(
            BrochureEnquiry.followup_status.in_(["PENDING", "FOLLOW_UP"])
        ).count(),
        "contacted_customers": base_query.filter(
            BrochureEnquiry.followup_status == "CONTACTED"
        ).count(),
        "converted_customers": base_query.filter(
            BrochureEnquiry.followup_status == "CONVERTED"
        ).count(),
        "not_interested": base_query.filter(
            BrochureEnquiry.followup_status == "NOT_INTERESTED"
        ).count(),
    }


@router.get("/filter-options", response_model=BrochureFilterOptionsOut)
def brochure_filter_options(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(MODULE, "view")),
):
    base_query = _scoped_query(db, current_user)
    product_rows = (
        base_query.with_entities(BrochureEnquiry.product_name)
        .filter(BrochureEnquiry.product_name.isnot(None), BrochureEnquiry.product_name != "")
        .distinct()
        .all()
    )
    brochure_rows = (
        base_query.with_entities(BrochureEnquiry.brochure_name)
        .filter(BrochureEnquiry.brochure_name.isnot(None), BrochureEnquiry.brochure_name != "")
        .distinct()
        .all()
    )

    names = {
        value.strip()
        for (value,) in list(product_rows) + list(brochure_rows)
        if value and value.strip()
    }

    employees = (
        db.query(Employee)
        .filter(Employee.status == "ACTIVE")
        .order_by(Employee.name.asc())
        .all()
    )

    return {
        "brochures": sorted(names, key=lambda value: value.lower()),
        "employees": [
            BrochureEmployeeOption(
                id=employee.id,
                name=employee.name,
                role=employee.role,
                department=employee.department,
            )
            for employee in employees
        ],
        "statuses": BROCHURE_FOLLOWUP_STATUSES,
    }


@router.get("/export")
def export_brochure_enquiries(
    search: Optional[str] = None,
    brochure: Optional[str] = None,
    employee_id: Optional[int] = None,
    followup_status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    download_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(MODULE, "export")),
):
    query = _scoped_query(db, current_user)
    query = _apply_filters(
        query,
        search=search,
        brochure=brochure,
        employee_id=employee_id,
        followup_status=followup_status,
        date_from=date_from,
        date_to=date_to,
        download_date=download_date,
    )
    records = (
        query.options(
            joinedload(BrochureEnquiry.assigned_employee),
            joinedload(BrochureEnquiry.lead),
            joinedload(BrochureEnquiry.customer),
        )
        .order_by(BrochureEnquiry.download_at.desc(), BrochureEnquiry.id.desc())
        .all()
    )

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Brochure Downloads"

    headers = [
        "Sr No",
        "Customer Name",
        "WhatsApp Number",
        "Country Code",
        "Email",
        "Product Name",
        "Brochure Name",
        "Download Date & Time",
        "Assigned Employee",
        "Follow-up Status",
        "Next Follow-up Date",
        "Next Follow-up Time",
        "Notes",
        "Website",
        "Campaign",
        "Landing Page",
        "Submission Count",
        "Linked Lead ID",
        "Linked Customer ID",
    ]
    sheet.append(headers)

    header_fill = PatternFill("solid", fgColor="1E293B")
    header_font = Font(color="FFFFFF", bold=True)
    for cell in sheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for index, record in enumerate(records, start=1):
        sheet.append([
            index,
            record.name or "",
            record.whatsapp_number or record.phone or "",
            record.country_code or "",
            record.email or "",
            record.product_name or "",
            record.brochure_name or "",
            record.download_at.strftime("%Y-%m-%d %H:%M:%S") if record.download_at else "",
            record.assigned_employee.name if record.assigned_employee else "Unassigned",
            record.followup_status or "",
            record.next_followup_date.strftime("%Y-%m-%d") if record.next_followup_date else "",
            record.next_followup_time or "",
            record.notes or "",
            record.website_name or "",
            record.campaign or "",
            record.landing_page or "",
            record.submission_count or 1,
            record.lead_id or "",
            record.customer_id or "",
        ])

    widths = [8, 24, 22, 12, 28, 26, 30, 22, 22, 18, 18, 18, 40, 24, 24, 40, 16, 14, 16]
    for idx, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(idx)].width = width
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for row in sheet.iter_rows(min_row=2, max_col=len(headers)):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    stream = io.BytesIO()
    workbook.save(stream)
    stream.seek(0)

    filename = f"Brochure_Download_People_{get_ist_now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    headers_out = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Access-Control-Expose-Headers": "Content-Disposition",
    }
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers_out,
    )


@router.get("/{enquiry_id}", response_model=BrochureEnquiryOut)
def get_brochure_enquiry(
    enquiry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(MODULE, "view")),
):
    record = (
        _scoped_query(db, current_user)
        .options(
            joinedload(BrochureEnquiry.assigned_employee),
            joinedload(BrochureEnquiry.lead),
            joinedload(BrochureEnquiry.customer),
        )
        .filter(BrochureEnquiry.id == enquiry_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brochure enquiry not found.")
    return _serialize(record)


@router.patch("/{enquiry_id}", response_model=BrochureEnquiryOut)
def update_brochure_enquiry(
    enquiry_id: int,
    payload: BrochureEnquiryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(MODULE, "edit")),
):
    record = (
        _scoped_query(db, current_user)
        .filter(BrochureEnquiry.id == enquiry_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brochure enquiry not found.")

    values = payload.model_dump(exclude_unset=True)
    now = get_ist_now()
    current_employee = _current_employee(current_user, db)

    if "followup_status" in values and values["followup_status"] is not None:
        try:
            new_status = normalize_followup_status(values["followup_status"])
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

        record.followup_status = new_status
        if new_status in ("CONTACTED", "FOLLOW_UP", "CONVERTED", "NOT_INTERESTED"):
            record.last_contacted_at = record.last_contacted_at or now
        if new_status == "CONVERTED":
            record.converted_at = record.converted_at or now

    if "notes" in values:
        record.notes = values["notes"] or None

    note_text = (values.get("note") or "").strip()
    if note_text:
        author = current_employee.name if current_employee else current_user.username
        stamped = f"[{now.strftime('%d %b %Y, %I:%M %p')} - {author}] {note_text}"
        record.notes = f"{record.notes}\n{stamped}" if record.notes else stamped

    if "next_followup_date" in values:
        record.next_followup_date = values["next_followup_date"]
    if "next_followup_time" in values:
        record.next_followup_time = values["next_followup_time"] or None

    if "assigned_to" in values:
        new_assignee = values["assigned_to"]
        if new_assignee != record.assigned_to:
            can_assign = user_has_permission(current_user, MODULE, "assign", db)
            can_claim = (
                record.assigned_to is None
                and current_employee is not None
                and new_assignee == current_employee.id
            )
            if not (can_assign or can_claim):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have permission to assign brochure enquiries.",
                )

            if new_assignee is not None:
                employee = db.query(Employee).filter(Employee.id == new_assignee).first()
                if not employee:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Selected employee does not exist.",
                    )
                record.assigned_to = employee.id
                record.assigned_at = now
                record.assigned_by = current_employee.id if current_employee else None
            else:
                record.assigned_to = None
                record.assigned_at = None
                record.assigned_by = None

    record.updated_at = now
    db.commit()
    db.refresh(record)
    return _serialize(record)
