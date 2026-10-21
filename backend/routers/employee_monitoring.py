from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_, desc
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, date

from database import get_db
from models.user import User
from models.employee import Employee
from models.lead import Lead, LeadAssignment, LeadStatusHistory
from models.call_log import CallLog
from models.followup import Followup
from models.monitoring import EmployeeActivityLog, EmployeePresence, FieldVisit, MonitoringSetting
from services.auth import get_current_user
from services.permission_service import get_authorized_call_employee_ids
from services.hierarchy_service import get_authorized_performance_employee_ids
from routers.ivr import resolve_recording_url

router = APIRouter(prefix="/employee-monitoring", tags=["Employee Monitoring"])

def get_employee_for_user(db: Session, user: User) -> Optional[Employee]:
    return db.query(Employee).filter(Employee.user_id == user.id).first()

def authorize_employee_access(current_user: User, target_emp_id: int, db: Session):
    authorized_emp_ids = get_authorized_performance_employee_ids(current_user, db)
    if authorized_emp_ids is None:
        return True
    if target_emp_id not in authorized_emp_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not have permission to view performance details for this employee."
        )
    return True

def get_date_range(date_filter: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None):
    now = datetime.utcnow()
    start_dt = None
    end_dt = now

    if not date_filter or date_filter in ["ALL", "ALL_TIME", "NONE"]:
        return None, None
    elif date_filter == "TODAY":
        start_dt = datetime(now.year, now.month, now.day, 0, 0, 0)
    elif date_filter == "YESTERDAY":
        yesterday = now - timedelta(days=1)
        start_dt = datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, 0)
        end_dt = datetime(yesterday.year, yesterday.month, yesterday.day, 23, 59, 59)
    elif date_filter == "THIS_WEEK":
        start_dt = now - timedelta(days=now.weekday())
        start_dt = datetime(start_dt.year, start_dt.month, start_dt.day, 0, 0, 0)
    elif date_filter == "THIS_MONTH":
        start_dt = datetime(now.year, now.month, 1, 0, 0, 0)
    elif date_filter == "CUSTOM" and start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            if end_date:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
        except Exception:
            pass

    return start_dt, end_dt

# ==========================================
# 1. OVERVIEW & ADMIN DASHBOARD METRICS
# ==========================================
@router.get("/overview")
def get_monitoring_overview(
    date_filter: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    authorized_emp_ids = get_authorized_performance_employee_ids(current_user, db)
    if authorized_emp_ids is not None and len(authorized_emp_ids) == 0:
        return {
            "total_employees": 0,
            "online_now": 0,
            "total_calls": 0,
            "answered_calls": 0,
            "total_talk_time_seconds": 0,
            "total_assigned_leads": 0,
            "total_converted_leads": 0,
            "total_followups": 0,
            "total_field_visits": 0
        }

    start_dt, end_dt = get_date_range(date_filter, start_date, end_date)

    emp_q = db.query(Employee).filter(Employee.status == "ACTIVE")
    if authorized_emp_ids is not None:
        emp_q = emp_q.filter(Employee.id.in_(authorized_emp_ids))
    total_employees = emp_q.count()

    # Online Now (Presence updated in last 5 minutes)
    five_mins_ago = datetime.utcnow() - timedelta(minutes=5)
    presence_q = db.query(EmployeePresence).filter(
        EmployeePresence.last_seen >= five_mins_ago
    )
    if authorized_emp_ids is not None:
        presence_q = presence_q.filter(EmployeePresence.employee_id.in_(authorized_emp_ids))
    online_count = presence_q.count()

    # Call Metrics
    call_query = db.query(CallLog)
    if authorized_emp_ids is not None:
        call_query = call_query.filter(CallLog.employee_id.in_(authorized_emp_ids))
    if start_dt:
        call_query = call_query.filter(CallLog.created_at >= start_dt, CallLog.created_at <= end_dt)
    
    total_calls = call_query.count()
    answered_calls = call_query.filter(CallLog.call_status.in_(["ANSWERED", "COMPLETED", "CONNECTED"])).count()

    talk_time_q = db.query(func.coalesce(func.sum(CallLog.duration_seconds), 0))
    if authorized_emp_ids is not None:
        talk_time_q = talk_time_q.filter(CallLog.employee_id.in_(authorized_emp_ids))
    if start_dt:
        talk_time_q = talk_time_q.filter(CallLog.created_at >= start_dt, CallLog.created_at <= end_dt)
    total_talk_time = talk_time_q.scalar() or 0

    # Leads Metrics
    lead_query = db.query(Lead)
    if authorized_emp_ids is not None:
        lead_query = lead_query.filter(Lead.assigned_to.in_(authorized_emp_ids))
    if start_dt:
        lead_query = lead_query.filter(Lead.created_at >= start_dt, Lead.created_at <= end_dt)

    total_assigned_leads = lead_query.filter(Lead.assigned_to.isnot(None)).count()
    total_converted_leads = lead_query.filter(Lead.status.in_(["CONVERTED", "WON"])).count()

    # Follow-ups
    followup_query = db.query(Followup)
    if authorized_emp_ids is not None:
        followup_query = followup_query.filter(Followup.assigned_to.in_(authorized_emp_ids))
    if start_dt:
        followup_query = followup_query.filter(Followup.created_at >= start_dt)
    total_followups = followup_query.count()

    # Field Visits
    field_query = db.query(FieldVisit)
    if authorized_emp_ids is not None:
        field_query = field_query.filter(FieldVisit.employee_id.in_(authorized_emp_ids))
    if start_dt:
        field_query = field_query.filter(FieldVisit.checkin_time >= start_dt)
    total_field_visits = field_query.count()

    return {
        "total_employees": total_employees,
        "online_now": online_count,
        "total_calls": total_calls,
        "answered_calls": answered_calls,
        "total_talk_time_seconds": total_talk_time,
        "total_assigned_leads": total_assigned_leads,
        "total_converted_leads": total_converted_leads,
        "total_followups": total_followups,
        "total_field_visits": total_field_visits
    }

# ==========================================
# 2. EMPLOYEES MONITORING LIST & FACTUAL CARDS
# ==========================================
@router.get("/employees")
def get_monitoring_employees_list(
    date_filter: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    authorized_emp_ids = get_authorized_performance_employee_ids(current_user, db)
    if authorized_emp_ids is not None and len(authorized_emp_ids) == 0:
        return []

    query = db.query(Employee).filter(Employee.status == "ACTIVE")
    if authorized_emp_ids is not None:
        query = query.filter(Employee.id.in_(authorized_emp_ids))

    employees = query.all()
    five_mins_ago = datetime.utcnow() - timedelta(minutes=5)
    start_dt, end_dt = get_date_range(date_filter)
    result = []

    for e in employees:
        # Factual Lead Metrics
        assigned = db.query(Lead).filter(Lead.assigned_to == e.id).count()
        contacted = db.query(Lead).filter(Lead.assigned_to == e.id, Lead.status == "CONTACTED").count()
        qualified = db.query(Lead).filter(Lead.assigned_to == e.id, Lead.status == "QUALIFIED").count()
        converted = db.query(Lead).filter(Lead.assigned_to == e.id, Lead.status.in_(["CONVERTED", "WON"])).count()

        # Call Metrics from call_logs table
        calls = db.query(CallLog).filter(CallLog.employee_id == e.id)
        talk_time_q = db.query(func.coalesce(func.sum(CallLog.duration_seconds), 0)).filter(CallLog.employee_id == e.id)
        if start_dt:
            calls = calls.filter(CallLog.created_at >= start_dt, CallLog.created_at <= end_dt)
            talk_time_q = talk_time_q.filter(CallLog.created_at >= start_dt, CallLog.created_at <= end_dt)

        total_calls = calls.count()
        answered_calls = calls.filter(CallLog.call_status.in_(["ANSWERED", "COMPLETED", "CONNECTED"])).count()
        missed_calls = calls.filter(CallLog.call_status.in_(["MISSED", "NOANSWER", "BUSY", "FAILED", "CANCEL"])).count()
        talk_time = talk_time_q.scalar() or 0
        avg_duration = round(talk_time / total_calls) if total_calls > 0 else 0

        # Followups
        followups = db.query(Followup).filter(Followup.assigned_to == e.id).count()

        # Presence
        presence = db.query(EmployeePresence).filter(EmployeePresence.employee_id == e.id).first()
        is_online = presence and presence.last_seen >= five_mins_ago
        presence_status = "ONLINE" if is_online else "OFFLINE"
        last_seen = presence.last_seen if presence else e.created_at

        # Last Activity
        last_act = db.query(EmployeeActivityLog).filter(EmployeeActivityLog.employee_id == e.id).order_by(desc(EmployeeActivityLog.timestamp)).first()
        last_activity_time = last_act.timestamp if last_act else last_seen

        result.append({
            "employee_id": e.id,
            "name": e.name,
            "email": e.email,
            "role": e.role,
            "status": e.status,
            "assigned_leads": assigned,
            "contacted_leads": contacted,
            "qualified_leads": qualified,
            "converted_leads": converted,
            "total_calls": total_calls,
            "answered_calls": answered_calls,
            "missed_calls": missed_calls,
            "total_talk_time_seconds": talk_time,
            "avg_duration_seconds": avg_duration,
            "followups_count": followups,
            "online_status": presence_status,
            "last_seen": last_seen,
            "last_activity_time": last_activity_time
        })

    return result

# ==========================================
# 4. CALL ANALYTICS & DETAILED CALL HISTORY
# ==========================================
@router.get("/calls")
def get_all_employee_call_records(
    employee_id: Optional[int] = Query(None),
    call_status: Optional[str] = Query(None),
    date_filter: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Call oversight endpoint: Access call records across authorized employees with details 
    (employee name, customer name, duration, status, date/time, audio recording URL, AI transcript, & AI summary).
    """
    authorized_emp_ids = get_authorized_performance_employee_ids(current_user, db)
    if authorized_emp_ids is not None and len(authorized_emp_ids) == 0:
        return []

    query = db.query(CallLog)

    if authorized_emp_ids is not None:
        if employee_id:
            if employee_id not in authorized_emp_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: You are not authorized to view call logs for this employee."
                )
            query = query.filter(CallLog.employee_id == employee_id)
        else:
            query = query.filter(CallLog.employee_id.in_(authorized_emp_ids))
    elif employee_id:
        query = query.filter(CallLog.employee_id == employee_id)

    if call_status:
        query = query.filter(CallLog.call_status.ilike(f"%{call_status}%"))

    start_dt, end_dt = get_date_range(date_filter)
    if start_dt:
        query = query.filter(CallLog.created_at >= start_dt, CallLog.created_at <= end_dt)

    if search:
        s_fmt = f"%{search}%"
        query = query.filter(
            or_(
                CallLog.from_number.ilike(s_fmt),
                CallLog.to_number.ilike(s_fmt),
                CallLog.provider_call_id.ilike(s_fmt),
                CallLog.notes.ilike(s_fmt)
            )
        )

    calls = query.order_by(desc(CallLog.created_at)).all()
    result = []
    for c in calls:
        lead_name = c.lead.name if c.lead else "Customer Prospect"
        emp_name = c.employee.name if c.employee else "Sales Executive"
        emp_role = c.employee.role if c.employee else "Agent"
        
        # Resolve real cloud recording URL for valid calls
        rec_url = resolve_recording_url(c.recording_url, db) if (c.duration_seconds and c.duration_seconds > 0) else None
        
        result.append({
            "id": c.id,
            "lead_id": c.lead_id,
            "lead_name": lead_name,
            "employee_id": c.employee_id,
            "employee_name": emp_name,
            "employee_role": emp_role,
            "provider": c.provider,
            "provider_call_id": c.provider_call_id,
            "from_number": c.from_number,
            "to_number": c.to_number,
            "customer_phone": c.to_number or c.from_number,
            "employee_phone": c.from_number,
            "call_status": c.call_status,
            "call_direction": c.call_direction,
            "duration_seconds": c.duration_seconds,
            "recording_url": rec_url,
            "transcript": c.transcript,
            "ai_summary": c.ai_summary,
            "sentiment": c.sentiment or "Positive",
            "started_at": c.started_at,
            "ended_at": c.ended_at,
            "created_at": c.created_at
        })
    return result

@router.get("/{employee_id}/calls")
def get_employee_call_history(
    employee_id: int,
    call_status: Optional[str] = Query(None),
    date_filter: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    authorize_employee_access(current_user, employee_id, db)
    query = db.query(CallLog).filter(CallLog.employee_id == employee_id)

    if call_status:
        query = query.filter(CallLog.call_status == call_status)

    start_dt, end_dt = get_date_range(date_filter, start_date, end_date)
    if start_dt:
        query = query.filter(CallLog.created_at >= start_dt, CallLog.created_at <= end_dt)

    calls = query.order_by(desc(CallLog.created_at)).all()
    result = []
    for c in calls:
        lead_name = c.lead.name if c.lead else "Customer Prospect"
        emp_name = c.employee.name if c.employee else "Sales Executive"
        # Resolve real cloud recording URL for valid calls
        rec_url = resolve_recording_url(c.recording_url, db) if (c.duration_seconds and c.duration_seconds > 0) else None
        result.append({
            "id": c.id,
            "lead_id": c.lead_id,
            "lead_name": lead_name,
            "employee_id": c.employee_id,
            "employee_name": emp_name,
            "provider": c.provider,
            "provider_call_id": c.provider_call_id,
            "from_number": c.from_number,
            "to_number": c.to_number,
            "phone_number": c.to_number or c.from_number,
            "call_status": c.call_status,
            "call_direction": c.call_direction,
            "duration_seconds": c.duration_seconds,
            "recording_url": rec_url,
            "transcript": c.transcript,
            "ai_summary": c.ai_summary,
            "sentiment": c.sentiment or "Positive",
            "started_at": c.started_at,
            "ended_at": c.ended_at,
            "created_at": c.created_at
        })
    return result

# ==========================================
# 5. LEAD & CONVERSION ANALYTICS
# ==========================================
@router.get("/{employee_id}/leads")
@router.get("/{employee_id}/conversions")
def get_employee_leads_and_conversions(
    employee_id: int,
    status_filter: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    authorize_employee_access(current_user, employee_id, db)
    query = db.query(Lead).filter(Lead.assigned_to == employee_id)
    if status_filter:
        query = query.filter(Lead.status == status_filter)

    leads = query.order_by(desc(Lead.created_at)).all()
    return [{
        "id": l.id,
        "name": l.name,
        "phone": l.phone,
        "email": l.email,
        "company": l.company,
        "source": l.source,
        "status": l.status,
        "created_at": l.created_at,
        "updated_at": l.updated_at
    } for l in leads]

# ==========================================
# 6. BUSINESS ACTIVITY TIMELINE API
# ==========================================
@router.get("/activity")
@router.get("/{employee_id}/activities")
def get_activity_timeline(
    employee_id: Optional[int] = None,
    activity_type: Optional[str] = Query(None),
    date_filter: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    authorized_emp_ids = get_authorized_performance_employee_ids(current_user, db)
    if authorized_emp_ids is not None and len(authorized_emp_ids) == 0:
        return []

    query = db.query(EmployeeActivityLog)
    if employee_id:
        authorize_employee_access(current_user, employee_id, db)
        query = query.filter(EmployeeActivityLog.employee_id == employee_id)
    elif authorized_emp_ids is not None:
        query = query.filter(EmployeeActivityLog.employee_id.in_(authorized_emp_ids))

    if activity_type:
        query = query.filter(EmployeeActivityLog.activity_type == activity_type)

    start_dt, end_dt = get_date_range(date_filter)
    if start_dt:
        query = query.filter(EmployeeActivityLog.timestamp >= start_dt, EmployeeActivityLog.timestamp <= end_dt)

    logs = query.order_by(desc(EmployeeActivityLog.timestamp)).limit(100).all()
    result = []
    for l in logs:
        emp_name = l.employee.name if l.employee else "System User"
        result.append({
            "activity_id": l.id,
            "employee_id": l.employee_id,
            "employee_name": emp_name,
            "activity_type": l.activity_type,
            "entity_type": l.entity_type,
            "entity_id": l.entity_id,
            "description": l.description,
            "timestamp": l.timestamp
        })
    return result

# ==========================================
# 7. PRESENCE HEARTBEAT API
# ==========================================
@router.post("/presence/heartbeat")
def record_presence_heartbeat(
    activity_type: Optional[str] = "HEARTBEAT",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    emp = get_employee_for_user(db, current_user)
    if not emp:
        return {"status": "ignored", "reason": "No linked employee record"}

    presence = db.query(EmployeePresence).filter(EmployeePresence.employee_id == emp.id).first()
    now = datetime.utcnow()

    if not presence:
        presence = EmployeePresence(
            employee_id=emp.id,
            status="ONLINE",
            last_seen=now,
            last_activity_type=activity_type
        )
        db.add(presence)
    else:
        presence.status = "ONLINE"
        presence.last_seen = now
        presence.last_activity_type = activity_type

    db.commit()
    return {"status": "success", "employee_id": emp.id, "last_seen": now}

# ==========================================
# 8. FIELD VISIT CHECK-IN & CHECK-OUT API
# ==========================================
@router.post("/field-visits")
def submit_field_visit_unified(
    data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from routers.field_visits import handle_field_visit_submission
    return handle_field_visit_submission(data, db, current_user)

@router.post("/field-visits/check-in")
def field_visit_check_in(
    data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    emp = get_employee_for_user(db, current_user)
    if not emp:
        raise HTTPException(status_code=400, detail="Only registered employees can check-in for field visits.")

    visit = FieldVisit(
        employee_id=emp.id,
        lead_id=data.get("lead_id"),
        customer_name=data.get("customer_name"),
        checkin_lat=str(data.get("checkin_lat", "")),
        checkin_lng=str(data.get("checkin_lng", "")),
        checkin_address=data.get("checkin_address"),
        notes=data.get("notes"),
        photo_url=data.get("photo_url"),
        status="CHECKED_IN"
    )
    db.add(visit)

    # Log activity
    log = EmployeeActivityLog(
        employee_id=emp.id,
        activity_type="FIELD_CHECKIN",
        entity_type="FIELD_VISIT",
        entity_id=None,
        description=f"Field visit check-in for {data.get('customer_name', 'Customer')}"
    )
    db.add(log)
    db.commit()
    db.refresh(visit)
    return visit

@router.post("/field-visits/check-out")
def field_visit_check_out(
    data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    visit_id = data.get("visit_id")
    visit = db.query(FieldVisit).filter(FieldVisit.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=4404, detail="Field visit record not found.")

    visit.checkout_lat = str(data.get("checkout_lat", ""))
    visit.checkout_lng = str(data.get("checkout_lng", ""))
    visit.checkout_time = datetime.utcnow()
    visit.notes = (visit.notes or "") + "\nCheckout Note: " + str(data.get("notes", ""))
    visit.status = "COMPLETED"
    db.commit()
    return visit

@router.get("/field-visits")
def get_all_field_visits(
    employee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    authorized_emp_ids = get_authorized_performance_employee_ids(current_user, db)
    if authorized_emp_ids is not None and len(authorized_emp_ids) == 0:
        return []

    query = db.query(FieldVisit)
    if employee_id:
        authorize_employee_access(current_user, employee_id, db)
        query = query.filter(FieldVisit.employee_id == employee_id)
    elif authorized_emp_ids is not None:
        query = query.filter(FieldVisit.employee_id.in_(authorized_emp_ids))
    visits = query.order_by(desc(FieldVisit.checkin_time)).all()
    return [v.to_dict() for v in visits]

@router.get("/{employee_id}/field-visits")
def get_employee_field_visits(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    authorize_employee_access(current_user, employee_id, db)
    visits = db.query(FieldVisit).filter(FieldVisit.employee_id == employee_id).order_by(desc(FieldVisit.checkin_time)).all()
    return visits

# ==========================================
# 9. RETENTION & MONITORING SETTINGS API
# ==========================================
@router.get("/settings/retention")
def get_monitoring_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    setting = db.query(MonitoringSetting).first()
    if not setting:
        setting = MonitoringSetting()
        db.add(setting)
        db.commit()
        db.refresh(setting)
    return setting

@router.put("/settings/retention")
def update_monitoring_settings(
    data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role.upper() != "ADMIN":
        raise HTTPException(status_code=403, detail="Only ADMIN users can update data retention settings.")

    setting = db.query(MonitoringSetting).first()
    if not setting:
        setting = MonitoringSetting()
        db.add(setting)

    setting.activity_retention_days = data.get("activity_retention_days", 90)
    setting.call_retention_days = data.get("call_retention_days", 180)
    setting.field_retention_days = data.get("field_retention_days", 180)
    setting.updated_at = datetime.utcnow()

    db.commit()
    return setting

# ==========================================
# 10. INDIVIDUAL EMPLOYEE MONITORING DETAIL
# ==========================================
@router.get("/{employee_id}")
def get_employee_detail(
    employee_id: int,
    date_filter: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    authorize_employee_access(current_user, employee_id, db)
    target_emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not target_emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    start_dt, end_dt = get_date_range(date_filter, start_date, end_date)

    # Lead Stats
    lead_query = db.query(Lead).filter(Lead.assigned_to == employee_id)
    if start_dt:
        lead_query = lead_query.filter(Lead.created_at >= start_dt, Lead.created_at <= end_dt)

    assigned = lead_query.count()
    contacted = lead_query.filter(Lead.status == "CONTACTED").count()
    interested = lead_query.filter(Lead.status == "INTERESTED").count()
    qualified = lead_query.filter(Lead.status == "QUALIFIED").count()
    converted = lead_query.filter(Lead.status.in_(["CONVERTED", "WON"])).count()
    lost = lead_query.filter(or_(Lead.status == "LOST", Lead.status == "NOT_INTERESTED", Lead.status == "LOST_LEAD")).count()
    pending_followups = db.query(Followup).filter(Followup.assigned_to == employee_id, Followup.status == "PENDING").count()

    conversion_rate = round((converted / assigned * 100), 1) if assigned > 0 else 0.0

    # Call Stats
    call_query = db.query(CallLog).filter(CallLog.employee_id == employee_id)
    if start_dt:
        call_query = call_query.filter(CallLog.created_at >= start_dt, CallLog.created_at <= end_dt)

    total_calls = call_query.count()
    answered_calls = call_query.filter(CallLog.call_status.in_(["ANSWERED", "COMPLETED"])).count()
    missed_calls = call_query.filter(CallLog.call_status == "MISSED").count()
    failed_calls = call_query.filter(CallLog.call_status == "FAILED").count()

    talk_time = call_query.with_entities(func.coalesce(func.sum(CallLog.duration_seconds), 0)).scalar() or 0
    avg_duration = round(talk_time / total_calls) if total_calls > 0 else 0

    # Presence
    five_mins_ago = datetime.utcnow() - timedelta(minutes=5)
    presence = db.query(EmployeePresence).filter(EmployeePresence.employee_id == employee_id).first()
    is_online = presence and presence.last_seen >= five_mins_ago

    return {
        "employee_id": target_emp.id,
        "name": target_emp.name,
        "email": target_emp.email,
        "role": target_emp.role,
        "status": target_emp.status,
        "online_status": "ONLINE" if is_online else "OFFLINE",
        "last_seen": presence.last_seen if presence else target_emp.created_at,
        "metrics": {
            "assigned_leads": assigned,
            "contacted_leads": contacted,
            "interested_leads": interested,
            "qualified_leads": qualified,
            "converted_leads": converted,
            "lost_leads": lost,
            "pending_followups": pending_followups,
            "conversion_rate": conversion_rate,
            "total_calls": total_calls,
            "answered_calls": answered_calls,
            "missed_calls": missed_calls,
            "failed_calls": failed_calls,
            "total_talk_time_seconds": talk_time,
            "avg_duration_seconds": avg_duration
        }
    }

# ==========================================
# 11. SEED SAMPLE DATA FOR TESTING & DEMO
# ==========================================
@router.post("/seed-sample-data")
def seed_monitoring_sample_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Seed realistic sample data into monitoring, calls, leads, and presence tables."""
    now = datetime.utcnow()
    
    # 1. Ensure sample employees exist
    sample_employees_data = [
        {"name": "Alex Morgan", "email": "alex.m@company.com", "role": "Senior Sales Executive", "department": "Sales"},
        {"name": "Sarah Jenkins", "email": "sarah.j@company.com", "role": "Account Manager", "department": "Accounts"},
        {"name": "David Chen", "email": "david.c@company.com", "role": "Sales Representative", "department": "Sales"},
        {"name": "Priya Sharma", "email": "priya.s@company.com", "role": "Field Sales Specialist", "department": "Field Ops"}
    ]
    
    created_emps = []
    for emp_info in sample_employees_data:
        emp = db.query(Employee).filter(Employee.email == emp_info["email"]).first()
        if not emp:
            emp = Employee(
                name=emp_info["name"],
                email=emp_info["email"],
                role=emp_info["role"],
                department=emp_info["department"],
                status="ACTIVE"
            )
            db.add(emp)
            db.flush()
        created_emps.append(emp)
        
    db.commit()

    # 2. Add sample activities
    sample_activities = [
        (created_emps[0].id, "CALL_LOGGED", "Logged call with TechCorp Solutions (Duration: 04:35 - Connected)", now - timedelta(minutes=15)),
        (created_emps[1].id, "LEAD_STAGE_UPDATE", "Updated lead stage for Acme Industries to Proposal Sent", now - timedelta(minutes=40)),
        (created_emps[3].id, "FIELD_CHECKIN", "Completed Field Visit check-in at Cyber City, Tech Hub", now - timedelta(hours=1, minutes=20)),
        (created_emps[2].id, "FOLLOWUP_SCHEDULED", "Scheduled follow-up with Innovate Ltd for tomorrow 2:00 PM", now - timedelta(hours=2, minutes=10)),
        (created_emps[0].id, "LEAD_CONVERTED", "Converted lead Global Systems to Closed Won ($12,500 ARR)", now - timedelta(hours=3, minutes=30)),
        (created_emps[1].id, "LOGIN", "Logged in to CRM dashboard from Web Application", now - timedelta(hours=5))
    ]
    for emp_id, act_type, desc_text, ts in sample_activities:
        act = EmployeeActivityLog(
            employee_id=emp_id,
            activity_type=act_type,
            description=desc_text,
            timestamp=ts
        )
        db.add(act)

    # 3. Add sample presence
    for i, emp in enumerate(created_emps):
        presence = db.query(EmployeePresence).filter(EmployeePresence.employee_id == emp.id).first()
        if not presence:
            presence = EmployeePresence(employee_id=emp.id)
            db.add(presence)
        presence.last_seen = now if i != 2 else now - timedelta(minutes=30)
        presence.ip_address = f"192.168.1.{100 + i}"
        presence.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

    # 4. Add sample field visits
    field_samples = [
        (created_emps[0].id, "TechCorp India HQ", "13.0827", "80.2707", "Chennai Central, TN", now - timedelta(hours=2), now - timedelta(hours=1), "Discussed Enterprise plan rollout. 5 stakeholders attended."),
        (created_emps[3].id, "Apex Retail Outlets", "13.0418", "80.2341", "T. Nagar Commercial Hub", now - timedelta(hours=4), None, "Verified store display setup & collected merchant feedback.")
    ]
    for emp_id, cust_name, lat, lng, addr, checkin, checkout, notes in field_samples:
        fv = FieldVisit(
            employee_id=emp_id,
            customer_name=cust_name,
            checkin_lat=lat,
            checkin_lng=lng,
            checkin_address=addr,
            checkin_time=checkin,
            checkout_time=checkout,
            notes=notes
        )
        db.add(fv)

    # 5. Add sample call logs
    call_samples = [
        (created_emps[0].id, "+91 98765 43210", "OUTBOUND", "ANSWERED", 275, now - timedelta(minutes=15), 
         "[Alex Morgan]: Hello! This is Alex from WaCRM. Am I speaking with TechCorp Solutions?\n[TechCorp]: Hi Alex! Yes, we reviewed the Click-to-Call IVR and WhatsApp integration specs.\n[Alex Morgan]: Excellent! We can have your 18-agent sales team onboarded by Friday.\n[TechCorp]: Perfect, please send over the enterprise agreement.",
         "🎯 KEY DISCUSSION: Discussed enterprise onboarding for 18 sales agents. Customer confirmed readiness to sign agreement.\n✅ SENTIMENT: Highly Interested\n📌 ACTION ITEM: Email enterprise contract by 5:00 PM.",
         "Positive"),
        (created_emps[0].id, "+91 98765 12345", "INBOUND", "ANSWERED", 180, now - timedelta(hours=1),
         "[TechCorp Lead]: Hi Alex, quick question about call recording retention policies.\n[Alex Morgan]: We retain all call recordings for 180 days by default, configurable in Manager Settings.",
         "🎯 KEY DISCUSSION: Answered compliance questions regarding 180-day call recording data retention.\n✅ SENTIMENT: Positive\n📌 ACTION ITEM: Include data retention policy PDF with contract.",
         "Positive"),
        (created_emps[1].id, "+91 91234 56789", "OUTBOUND", "ANSWERED", 340, now - timedelta(minutes=45),
         "[Sarah Jenkins]: Good afternoon! Sarah here following up on Acme Industries' proposal.\n[Acme Rep]: Hi Sarah. The pricing looks good, but we need custom WhatsApp template approval.\n[Sarah Jenkins]: I will submit your WhatsApp templates to Meta directly today.",
         "🎯 KEY DISCUSSION: Reviewed proposal pricing. Customer requested Meta WhatsApp template verification.\n✅ SENTIMENT: Interested / Conditional\n📌 ACTION ITEM: Submit custom WhatsApp templates via Meta Business API.",
         "Neutral"),
        (created_emps[1].id, "+91 99887 76655", "OUTBOUND", "MISSED", 0, now - timedelta(hours=2), None, None, "Missed"),
        (created_emps[2].id, "+91 97766 55443", "INBOUND", "ANSWERED", 210, now - timedelta(hours=3),
         "[David Chen]: Hello! David from Sales. How can I help you today?\n[Innovate Software]: Hi David, we want a live walkthrough of the employee performance monitoring dashboard.\n[David Chen]: I would be glad to host a live screen-share demo.",
         "🎯 KEY DISCUSSION: Product demo inquiry for employee monitoring module.\n✅ SENTIMENT: Highly Interested\n📌 ACTION ITEM: Host live demo session tomorrow at 2:00 PM.",
         "Positive"),
        (created_emps[3].id, "+91 96655 44332", "OUTBOUND", "ANSWERED", 195, now - timedelta(hours=4),
         "[Priya Sharma]: Hi there! Priya here from Field Ops following up on Apex Retail Outlets.\n[Apex Outlet]: Hi Priya! Great seeing you during the onsite visit earlier.",
         "🎯 KEY DISCUSSION: Onsite visit follow-up regarding payment terminal integration.\n✅ SENTIMENT: Satisfied\n📌 ACTION ITEM: Send merchant integration guide.",
         "Positive")
    ]
    for idx, (emp_id, num, direction, status_val, duration, ts, trans_text, summary_text, sent_val) in enumerate(call_samples):
        call = CallLog(
            employee_id=emp_id,
            provider="IVR",
            provider_call_id=f"CALL-REC-{idx+101}",
            from_number="+18005550199",
            to_number=num,
            call_direction=direction,
            call_status=status_val,
            duration_seconds=duration,
            recording_url="https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3" if duration > 0 else None,
            transcript=trans_text,
            ai_summary=summary_text,
            sentiment=sent_val,
            created_at=ts
        )
        db.add(call)

    # 6. Add sample leads
    lead_samples = [
        ("TechCorp Solutions", "contact@techcorp.com", "+91 98765 43210", "QUALIFIED", created_emps[0].id),
        ("Acme Industries", "info@acme.com", "+91 91234 56789", "CONTACTED", created_emps[1].id),
        ("Global Systems Ltd", "sales@globalsys.com", "+91 99887 76655", "CONVERTED", created_emps[0].id),
        ("Innovate Software", "hi@innovate.com", "+91 97766 55443", "CONTACTED", created_emps[2].id),
        ("Apex Retail Outlets", "orders@apexretail.com", "+91 96655 44332", "CONVERTED", created_emps[3].id)
    ]
    for name, email, phone, lead_status, emp_id in lead_samples:
        existing_lead = db.query(Lead).filter(Lead.email == email).first()
        if not existing_lead:
            lead = Lead(
                name=name,
                email=email,
                phone=phone,
                status=lead_status,
                assigned_to=emp_id,
                created_at=now - timedelta(days=2)
            )
            db.add(lead)

    db.commit()
    return {"message": "Sample employee monitoring data seeded successfully!", "employees_count": len(created_emps)}

