import logging
from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException, status
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, asc
from typing import List, Optional
from datetime import datetime

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
from schemas.workflow import DealWonRequest
from services.auth import get_current_user, require_roles, require_permission
from services.permission_service import (
    user_has_permission, 
    get_user_view_scope, 
    get_authorized_call_employee_ids,
    get_authorized_followup_employee_ids
)
from services.delete_request_service import handle_entity_deletion
from services.audit import log_audit
from services.reinquiry_service import ReInquiryService
from services.hierarchy_service import (
    get_team_employee_ids_from_user,
    normalize_role,
    ROLE_SUPPORT_MANAGER,
    ROLE_SUPPORT_EXECUTIVE,
    ROLE_SALES_EXECUTIVE
)
from services.excel_service import (
    generate_excel_template,
    parse_and_validate_excel_leads,
    generate_error_rows_excel
)

router = APIRouter(prefix="/leads", tags=["Leads"])

def get_employee_for_user(user: User, db: Session) -> Optional[Employee]:
    return db.query(Employee).filter(Employee.user_id == user.id).first()

def get_team_employee_ids(manager_emp_id: int, db: Session) -> List[int]:
    team = db.query(Employee).filter(Employee.manager_id == manager_emp_id).all()
    return [e.id for e in team] + [manager_emp_id]

def log_lead_activity(db: Session, lead_id: int, performed_by_id: Optional[int], activity_type: str, description: str):
    activity = LeadActivity(
        lead_id=lead_id,
        performed_by=performed_by_id,
        activity_type=activity_type,
        description=description,
        created_at=datetime.utcnow()
    )
    db.add(activity)

def build_lead_out(lead: Lead) -> LeadOut:
    activities_out = []
    for act in lead.activities:
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
    for asgn in lead.assignments:
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
    for enq in (lead.enquiries or []):
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
        followup_date=lead.followup_date,
        followup_time=lead.followup_time,
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
        activities=activities_out,
        assignments=assignments_out,
        enquiries=enquiries_out
    )

@router.get("")
@router.get("/")
def list_leads(
    search: Optional[str] = None,
    status_filter: Optional[str] = None,
    status: Optional[str] = None,
    source_filter: Optional[str] = None,
    source: Optional[str] = None,
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
    limit: int = 100,
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
        return {"total": 0, "items": []}
    elif scope == "own":
        if current_emp:
            query = query.filter(Lead.assigned_to == current_emp.id)
        else:
            return {"total": 0, "items": []}
    elif scope == "team":
        team_ids = get_team_employee_ids_from_user(current_user, db)
        if eff_assigned_to:
            if eff_assigned_to not in team_ids and current_user.role != "ADMIN":
                return {"total": 0, "items": []}
            query = query.filter(Lead.assigned_to == eff_assigned_to)
        else:
            query = query.filter(or_(Lead.assigned_to.in_(team_ids), Lead.assigned_to == None))
    else:  # "department" or "company"
        if eff_assigned_to:
            query = query.filter(Lead.assigned_to == eff_assigned_to)

    if search:
        search_fmt = f"%{search}%"
        query = query.filter(
            or_(
                Lead.name.ilike(search_fmt),
                Lead.first_name.ilike(search_fmt),
                Lead.last_name.ilike(search_fmt),
                Lead.phone.ilike(search_fmt),
                Lead.email.ilike(search_fmt),
                Lead.company.ilike(search_fmt)
            )
        )

    eff_status = status_filter or status
    if eff_status and eff_status.upper() != "ALL":
        st_clean = eff_status.strip().upper()
        if st_clean in ["RE-INQUIRY", "REINQUIRY"]:
            query = query.filter(or_(Lead.status == "RE-INQUIRY", Lead.is_reinquiry == True))
        elif st_clean in ["NEW", "NEW LEAD", "NEW_LEAD"]:
            query = query.filter(or_(Lead.status == "NEW", Lead.status == "NEW LEAD", Lead.status == "NEW_LEAD"))
        elif st_clean in ["IN_PROGRESS", "IN PROGRESS"]:
            query = query.filter(or_(Lead.status == "IN_PROGRESS", Lead.status == "IN PROGRESS", Lead.status == "CONTACTED", Lead.status == "INTERESTED"))
        elif st_clean in ["WON", "CONVERTED"]:
            query = query.filter(or_(Lead.status == "WON", Lead.status == "CONVERTED"))
        elif st_clean in ["FOLLOW-UP", "FOLLOW_UP"]:
            query = query.filter(or_(Lead.status == "FOLLOW-UP", Lead.status == "FOLLOW_UP"))
        elif st_clean in ["DEMO", "MEETING", "DEMO / MEETING", "DEMO/MEETING"]:
            query = query.filter(or_(Lead.status == "DEMO / MEETING", Lead.status == "DEMO", Lead.status == "MEETING"))
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

    # Dynamic Sorting by Lead Received Date/Time (default desc: latest first)
    is_asc = bool(sort_order and sort_order.lower() == "asc")
    order_clause = asc(Lead.created_at) if is_asc else desc(Lead.created_at)
    leads = query.order_by(order_clause, desc(Lead.id) if not is_asc else asc(Lead.id)).offset(skip).limit(limit).all()

    items = [build_lead_out(l) for l in leads]
    return {"total": total, "items": items}

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

    # Strictly scope follow-ups count to authorized employees
    authorized_fu_emp_ids = get_authorized_followup_employee_ids(current_user, db)
    if authorized_fu_emp_ids is not None:
        if not authorized_fu_emp_ids:
            followups_query = followups_query.filter(Followup.id == -1)
        else:
            followups_query = followups_query.filter(
                or_(
                    Followup.assigned_to.in_(authorized_fu_emp_ids),
                    Followup.created_by.in_(authorized_fu_emp_ids)
                )
            )

    if only_my or scope == "own":
        if current_emp:
            base_query = base_query.filter(Lead.assigned_to == current_emp.id)
        else:
            return {
                "allLeads": 0, "metaLeads": 0, "websiteLeads": 0, "manualLeads": 0,
                "excelLeads": 0, "reinquiryLeads": 0, "myLeads": 0, "callLogs": 0, "followups": 0
            }
    elif scope == "team" and current_emp:
        team_ids = get_team_employee_ids(current_emp.id, db)
        base_query = base_query.filter(or_(Lead.assigned_to.in_(team_ids), Lead.assigned_to == None))

    all_count = base_query.count()
    meta_count = base_query.filter(or_(Lead.source == "META", Lead.source == "Meta Ads", Lead.source == "Meta")).count()
    website_count = base_query.filter(or_(Lead.source == "WEBSITE", Lead.source == "Website")).count()
    manual_count = base_query.filter(or_(Lead.source == "MANUAL", Lead.source == "Manual")).count()
    excel_count = base_query.filter(or_(Lead.source == "EXCEL", Lead.source == "Excel")).count()
    reinquiry_count = base_query.filter(Lead.is_reinquiry == True).count()
    new_count = base_query.filter(or_(Lead.status == "NEW", Lead.status == "NEW LEAD", Lead.status == "New")).count()
    in_progress_count = base_query.filter(or_(Lead.status == "IN_PROGRESS", Lead.status == "IN PROGRESS", Lead.status == "CONTACTED", Lead.status == "INTERESTED")).count()
    hot_count = base_query.filter(or_(Lead.rating.ilike("Hot"), Lead.priority.ilike("High"), Lead.priority.ilike("Hot"))).count()
    won_count = base_query.filter(or_(Lead.status == "WON", Lead.status == "CONVERTED", Lead.status == "Won")).count()

    my_count = 0
    if current_emp:
        my_count = db.query(Lead).filter(Lead.assigned_to == current_emp.id).count()

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
        "wonLeads": won_count,
        "myLeads": my_count,
        "callLogs": call_logs_count,
        "followups": followups_count
    }

@router.get("/my")
def list_my_leads(
    search: Optional[str] = None,
    status_filter: Optional[str] = None,
    source_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    current_emp = get_employee_for_user(current_user, db)
    if not current_emp:
        return {"total": 0, "items": []}
    
    query = db.query(Lead).filter(Lead.assigned_to == current_emp.id)

    if search:
        search_fmt = f"%{search}%"
        query = query.filter(
            or_(
                Lead.name.ilike(search_fmt),
                Lead.first_name.ilike(search_fmt),
                Lead.last_name.ilike(search_fmt),
                Lead.phone.ilike(search_fmt),
                Lead.email.ilike(search_fmt),
                Lead.company.ilike(search_fmt)
            )
        )

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
    leads = query.order_by(desc(Lead.created_at)).offset(skip).limit(limit).all()

    items = [build_lead_out(l) for l in leads]
    return {"total": total, "items": items}

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
    current_user: User = Depends(require_roles(["ADMIN", "MANAGER"]))
):
    if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an Excel (.xlsx) file.")

    contents = await file.read()
    current_emp = get_employee_for_user(current_user, db)
    creator_id = current_emp.id if current_emp else None
    creator_name = current_emp.name if current_emp else current_user.username

    try:
        results = parse_and_validate_excel_leads(contents, db)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    valid_leads = results["valid_leads"]
    created_count = 0
    reinquiry_count = 0
    now = get_ist_now()
    for lead_data in valid_leads:
        lead_data["source"] = "EXCEL"
        lead, is_reinquiry, enq = ReInquiryService.register_enquiry(
            db=db,
            enquiry_data=lead_data,
            creator_emp_id=creator_id,
            creator_name=creator_name,
            commit=False
        )
        if is_reinquiry:
            reinquiry_count += 1
        else:
            created_count += 1
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
    # Users without assign permission can only assign to themselves on creation
    if not user_has_permission(current_user, "leads", "assign", db):
        lead_data["assigned_to"] = creator_emp_id

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

    return build_lead_out(lead)

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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Support team cannot access Sales leads."
        )

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

    return build_lead_out(lead)

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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Support team cannot access Sales leads."
        )

    current_emp = get_employee_for_user(current_user, db)
    emp_id = current_emp.id if current_emp else None
    emp_name = current_emp.name if current_emp else current_user.username

    scope = get_user_view_scope(current_user, "leads", db)
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
    old_status = lead.status
    if lead_in.status is not None:
        lead.status = lead_in.status
        if lead_in.status in ["CONVERTED", "WON"] and old_status != lead_in.status:
            from models.workflow import SupportHandoff
            existing_handoff = db.query(SupportHandoff).filter(SupportHandoff.lead_id == lead.id).first()
            if not existing_handoff or not existing_handoff.support_manager_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Please assign a Support Manager before marking this deal as WON."
                )
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

    return build_lead_out(lead)

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
    return build_lead_out(lead)

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

    if current_user.role == "EMPLOYEE":
        if not current_emp or lead.assigned_to != current_emp.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only update status for leads assigned to you."
            )

    old_status = lead.status
    new_status = status_req.status

    lead.status = new_status

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

    if new_status in ["CONVERTED", "WON"]:
        from models.workflow import SupportHandoff
        existing_handoff = db.query(SupportHandoff).filter(SupportHandoff.lead_id == lead.id).first()
        if not existing_handoff or not existing_handoff.support_manager_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please assign a Support Manager before marking this deal as WON."
            )
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
    return build_lead_out(lead)

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
    Sales closes a Deal as WON with required Support Manager assignment.
    Validates permissions and enforces mandatory Support Manager selection.
    """
    can_edit = user_has_permission(current_user, "leads", "edit", db) or current_user.role in ["ADMIN", "MANAGER", "SALES"]
    if not can_edit:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to mark this deal as WON.")

    if not payload.support_manager_id or payload.support_manager_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please assign a Support Manager before marking this deal as WON."
        )

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
    return build_lead_out(lead)

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
            "status": r.status,
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
            if not doc and (handoff.status == "PAID" or handoff.invoice_number):
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
                    payment_status="paid" if handoff.status == "PAID" else "unpaid",
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
                    amount_paid=paid_amt if handoff.status == "PAID" else 0.0,
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

