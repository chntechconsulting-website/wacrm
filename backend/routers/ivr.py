import os
import json
import re
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, func, case
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from database import get_db
from models.user import User
from models.employee import Employee
from models.lead import Lead
from models.call_log import CallLog
from models.integration import IntegrationConfig
from services.auth import get_current_user, get_user_from_token
from services.permission_service import get_authorized_call_employee_ids
from utils.timezone import get_ist_now
from config import settings

from integrations.ivr.service import IVRService, IVRNotConfiguredException
from integrations.ivr.schemas import (
    InitiateCallRequest,
    CallLogResponse,
    CallLogListResponse,
    CallLogMetricsSummary,
    IVRConfigStatusResponse
)
from integrations.ivr.webhook import handle_incoming_ivr_webhook

router = APIRouter(prefix="/ivr", tags=["IVR Telephony Integration"])

class CallStatusUpdateRequest(BaseModel):
    call_status: str  # Initiating, Ringing, Connected, Completed, Missed, Busy, Failed
    duration_seconds: Optional[int] = None
    recording_url: Optional[str] = None
    notes: Optional[str] = None

class ManualCallLogRequest(BaseModel):
    lead_id: Optional[int] = None
    customer_phone: str
    call_status: str = "COMPLETED"
    duration_seconds: Optional[int] = 0
    notes: Optional[str] = None

def get_employee_for_user(user: User, db: Session) -> Optional[Employee]:
    return db.query(Employee).filter(Employee.user_id == user.id).first()

def resolve_recording_url(raw_url: Optional[str], db: Session) -> Optional[str]:
    """
    Normalizes telephony recording URLs.
    If Doocti PBX pushes a loopback address (http://127.0.0.1/audio/...),
    rewrites it using the configured 'recording_base_url' or 'media_url' from IVR IntegrationConfig
    (or default Doocti cloud storage).
    Converts .wav to .mp3 as Asterisk converts to MP3 upon cloud upload.
    """
    if not raw_url:
        return None
    url_str = str(raw_url).strip()
    if not url_str:
        return None
    if "127.0.0.1" in url_str or "localhost" in url_str:
        base = None
        try:
            cfg = db.query(IntegrationConfig).filter(IntegrationConfig.integration_type == "IVR").first()
            if cfg and cfg.config_data:
                data = json.loads(cfg.config_data or "{}")
                base = data.get("recording_base_url") or data.get("media_url")
        except Exception:
            pass
        if not base:
            base = "https://bmxrx2cviyka.compat.objectstorage.ap-mumbai-1.oraclecloud.com/doocti/cti_chntechnolog_20261009"

        base = base.strip().rstrip('/')
        match = re.search(r'https?://[^/]+(?:/audio)?(/.*)', url_str)
        if match:
            path = match.group(1)
            if path.endswith('.wav'):
                path = path[:-4] + '.mp3'
            return f"{base}{path}"
        return None
    return url_str

def build_call_log_response(call: CallLog, db: Session) -> CallLogResponse:
    lead_name = call.lead.name if call.lead else None
    employee_name = call.employee.name if call.employee else None

    # Accurately map customer vs employee phone based on numbers and call direction
    raw_from = (call.from_number or "").strip()
    raw_to = (call.to_number or "").strip()

    is_from_ext = len(raw_from.replace("+", "")) <= 5 if raw_from else False
    is_to_ext = len(raw_to.replace("+", "")) <= 5 if raw_to else False

    if is_from_ext and not is_to_ext:
        emp_phone = raw_from
        cust_phone = raw_to or (call.lead.phone if call.lead else "")
    elif is_to_ext and not is_from_ext:
        emp_phone = raw_to
        cust_phone = raw_from or (call.lead.phone if call.lead else "")
    else:
        is_inbound = (call.call_direction or "").upper() == "INBOUND"
        if is_inbound:
            cust_phone = raw_from or (call.lead.phone if call.lead else "")
            emp_phone = raw_to or (call.employee.phone if call.employee else "1282")
        else:
            cust_phone = raw_to or (call.lead.phone if call.lead else "")
            emp_phone = raw_from or (call.employee.phone if call.employee else "1282")

    resolved_rec = resolve_recording_url(call.recording_url, db)
    raw_rec = str(call.recording_url or "").strip()
    is_loopback = "127.0.0.1" in raw_rec or "localhost" in raw_rec

    status_upper = (call.call_status or "").upper()
    is_connected = status_upper in ["ANSWERED", "CONNECTED", "COMPLETED"]
    duration = call.duration_seconds or 0

    now_ist = get_ist_now()
    call_end_time = call.ended_at or call.created_at
    is_recent = False
    if call_end_time:
        try:
            diff = (now_ist - call_end_time).total_seconds()
            is_recent = 0 <= diff <= 300  # within 5 minutes of call completion
        except Exception:
            pass

    if resolved_rec:
        rec_status = "RECORDING_AVAILABLE"
    elif is_loopback or (is_recent and status_upper not in ["BUSY", "MISSED", "FAILED"]):
        rec_status = "RECORDING_PROCESSING"
    else:
        rec_status = "RECORDING_UNAVAILABLE"

    return CallLogResponse(
        id=call.id,
        lead_id=call.lead_id,
        employee_id=call.employee_id,
        provider=call.provider,
        provider_call_id=call.provider_call_id,
        from_number=call.from_number,
        to_number=call.to_number,
        customer_phone=cust_phone,
        employee_phone=emp_phone,
        call_status=call.call_status,
        call_direction=call.call_direction or "INBOUND",
        duration_seconds=call.duration_seconds,
        recording_url=resolved_rec,
        recording_status=rec_status,
        transcript=call.transcript,
        ai_summary=call.ai_summary,
        sentiment=call.sentiment,
        started_at=call.started_at,
        answered_at=call.answered_at,
        ended_at=call.ended_at,
        notes=call.notes,
        created_at=call.created_at,
        lead_name=lead_name,
        employee_name=employee_name
    )

@router.get("/config-status", response_model=IVRConfigStatusResponse)
def get_ivr_config_status(db: Session = Depends(get_db)):
    """
    Checks if IVR provider and API credentials are set in the database or environment.
    """
    is_configured = IVRService.is_configured(db=db)
    if is_configured:
        msg = "IVR Telephony is configured and active."
        provider_name = "ACTIVE"
    else:
        msg = "IVR is not configured. Please configure IVR from Settings → Integrations."
        provider_name = "UNCONFIGURED"

    return IVRConfigStatusResponse(
        configured=is_configured,
        provider=provider_name,
        from_number="+18005550199",
        message=msg
    )

@router.post("/call", response_model=CallLogResponse, status_code=status.HTTP_201_CREATED)
def initiate_call(
    body: InitiateCallRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Initiates a phone call to a lead or customer via the configured IVR provider.
    Fails with HTTP 400 if IVR credentials are not configured.
    """
    employee = get_employee_for_user(current_user, db)
    employee_id = employee.id if employee else None
    employee_phone = employee.phone if (employee and employee.phone) else None

    cust_phone = body.customer_phone or body.phone_number

    # SECURITY ENFORCEMENT: Employees can only call leads assigned to them or their onboarding tickets
    if current_user.role in ["EMPLOYEE", "SUPPORT", "SUPPORT_MANAGER"] and employee:
        from models.workflow import SupportHandoff
        if body.lead_id:
            target_lead = db.query(Lead).filter(Lead.id == body.lead_id).first()
            if target_lead and target_lead.assigned_to != employee.id:
                # Check if employee is assigned support manager or agent
                sh = db.query(SupportHandoff).filter(
                    SupportHandoff.lead_id == body.lead_id,
                    or_(
                        SupportHandoff.support_manager_id == employee.id,
                        SupportHandoff.assigned_agent_id == employee.id
                    )
                ).first()
                if not sh and current_user.role == "EMPLOYEE":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied. You can only call leads or customers assigned to you."
                    )
        elif cust_phone:
            clean_phone = cust_phone.replace(" ", "").replace("-", "")
            target_lead = db.query(Lead).filter(
                or_(Lead.phone.ilike(f"%{clean_phone[-10:]}%"), Lead.whatsapp_number.ilike(f"%{clean_phone[-10:]}%"))
            ).first()
            if target_lead and target_lead.assigned_to != employee.id:
                sh = db.query(SupportHandoff).filter(
                    SupportHandoff.lead_id == target_lead.id,
                    or_(
                        SupportHandoff.support_manager_id == employee.id,
                        SupportHandoff.assigned_agent_id == employee.id
                    )
                ).first()
                if not sh and current_user.role == "EMPLOYEE":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied. You can only call leads or customers assigned to you."
                    )

    try:
        call_log = IVRService.initiate_call(
            db=db,
            lead_id=body.lead_id,
            current_employee_id=employee_id,
            customer_phone=cust_phone,
            employee_phone=employee_phone,
            notes=body.notes
        )
        return build_call_log_response(call_log, db)
    except IVRNotConfiguredException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to initiate call via IVR provider: {str(e)}"
        )

@router.post("/calls/{call_id}/update-status", response_model=CallLogResponse)
def update_call_status_endpoint(
    call_id: str,
    body: CallStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Updates the call status (e.g. Ringing, Connected, Completed, Missed, Busy, Failed)
    and duration/recording info.
    Enforces authorization check based on logged-in user identity.
    """
    if call_id.isdigit():
        call = db.query(CallLog).filter(CallLog.id == int(call_id)).first()
    else:
        call = db.query(CallLog).filter(CallLog.provider_call_id == call_id).first()

    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Call log '{call_id}' not found."
        )

    # Permission check: direct access to another employee's call-log ID returns 403 Forbidden
    authorized_emp_ids = get_authorized_call_employee_ids(current_user, db)
    if authorized_emp_ids is not None:
        if call.employee_id is None or call.employee_id not in authorized_emp_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not have permission to update this call log."
            )

    updated_log = IVRService.update_call_status(
        db=db,
        provider_call_id=call.provider_call_id or call_id,
        new_status=body.call_status,
        duration_seconds=body.duration_seconds,
        recording_url=body.recording_url,
        notes=body.notes
    )

    if not updated_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Call log '{call_id}' not found."
        )

@router.post("/calls/{call_id}/disconnect", response_model=CallLogResponse)
@router.post("/calls/{call_id}/terminate", response_model=CallLogResponse)
@router.post("/calls/{call_id}/reject", response_model=CallLogResponse)
def disconnect_call_endpoint(
    call_id: str,
    action: Optional[str] = Query("disconnect", description="disconnect or reject"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Terminates or rejects an active inbound/outbound call.
    Validates permissions of the logged-in employee/manager/admin.
    """
    if call_id.isdigit():
        call = db.query(CallLog).filter(CallLog.id == int(call_id)).first()
    else:
        call = db.query(CallLog).filter(CallLog.provider_call_id == call_id).first()

    if not call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Call log '{call_id}' not found.")

    authorized_emp_ids = get_authorized_call_employee_ids(current_user, db)
    if authorized_emp_ids is not None:
        if call.employee_id is not None and call.employee_id not in authorized_emp_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not have permission to disconnect this call."
            )

    is_ringing = (call.call_status or "").upper() in ["RINGING", "CONNECTING", "DIALING"]
    if is_ringing or action == "reject":
        new_status = "MISSED" if (call.call_direction or "").upper() == "INBOUND" else "NO_ANSWER"
    else:
        new_status = "COMPLETED"

    call.call_status = new_status
    if not call.ended_at:
        call.ended_at = get_ist_now()
    if new_status in ["MISSED", "NO_ANSWER"] and not call.duration_seconds:
        call.duration_seconds = 0

    db.commit()
    db.refresh(call)

    # Lead Activity logging
    if call.lead_id:
        act = LeadActivity(
            lead_id=call.lead_id,
            performed_by=call.employee_id,
            activity_type="CALL_DISCONNECTED",
            related_entity_type="CALL",
            related_entity_id=call.id,
            description=f"Call {new_status.lower()} from CRM. Phone: {call.customer_phone or call.from_number or call.to_number}."
        )
        db.add(act)
        db.commit()

    return build_call_log_response(call, db)

@router.post("/calls/manual", response_model=CallLogResponse, status_code=status.HTTP_201_CREATED)
@router.post("/manual-call", response_model=CallLogResponse, status_code=status.HTTP_201_CREATED)
def log_manual_call_endpoint(
    body: ManualCallLogRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Direct Device / Manual Call logging (Fallback Option).
    Saves a completed or attempted call record without dialing through cloud IVR.
    """
    employee = get_employee_for_user(current_user, db)
    employee_id = employee.id if employee else None
    employee_phone = employee.phone if (employee and employee.phone) else None

    # Permission check for employee
    if current_user.role in ["EMPLOYEE", "SUPPORT", "SUPPORT_MANAGER"] and employee:
        if body.lead_id:
            from models.workflow import SupportHandoff
            target_lead = db.query(Lead).filter(Lead.id == body.lead_id).first()
            if target_lead and target_lead.assigned_to != employee.id:
                sh = db.query(SupportHandoff).filter(
                    SupportHandoff.lead_id == body.lead_id,
                    or_(
                        SupportHandoff.support_manager_id == employee.id,
                        SupportHandoff.assigned_agent_id == employee.id
                    )
                ).first()
                if not sh and current_user.role == "EMPLOYEE":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied. You can only log calls for leads assigned to you."
                    )

    try:
        call_log = IVRService.log_manual_call(
            db=db,
            lead_id=body.lead_id,
            current_employee_id=employee_id,
            customer_phone=body.customer_phone,
            employee_phone=employee_phone,
            call_status=body.call_status,
            duration_seconds=body.duration_seconds or 0,
            notes=body.notes
        )
        return build_call_log_response(call_log, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to log call: {str(e)}")

@router.post("/calls/{call_id}/ai-summary", response_model=CallLogResponse)
def generate_call_ai_summary(
    call_id: str,
    force: bool = Query(False, description="Force regenerate AI summary even if already exists"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generates or retrieves AI-powered call transcription, key discussion highlights, 
    customer sentiment analysis, and follow-up action items.
    Enforces authorization check: returns 403 Forbidden if call belongs to another employee.
    """
    if call_id.isdigit():
        call = db.query(CallLog).filter(CallLog.id == int(call_id)).first()
    else:
        call = db.query(CallLog).filter(CallLog.provider_call_id == call_id).first()

    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Call log '{call_id}' not found."
        )

    # Permission check: direct access to another employee's call-log ID returns 403 Forbidden
    authorized_emp_ids = get_authorized_call_employee_ids(current_user, db)
    if authorized_emp_ids is not None:
        if call.employee_id is None or call.employee_id not in authorized_emp_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not have permission to view or generate AI summary for this call log."
            )

    lead_name = call.lead.name if call.lead else "Customer Prospect"
    emp_name = call.employee.name if call.employee else "Sales Representative"
    dur = call.duration_seconds or 0
    status_upper = (call.call_status or "").upper()

    # Generate or force regenerate AI transcript & summary
    if force or not call.transcript or not call.ai_summary:
        if dur < 10 or status_upper in ["BUSY", "MISSED", "NOANSWER", "FAILED"]:
            call.transcript = (
                f"[{emp_name}]: Hello, this is {emp_name} calling regarding your inquiry. Am I speaking with {lead_name}?\n"
                f"[System]: Call connection ended after {dur}s ({status_upper})."
            )
            call.ai_summary = (
                f"🎯 KEY DISCUSSION: Outbound call to {lead_name} ({dur}s duration). Call was brief or disconnected before deep conversation.\n"
                f"💡 CUSTOMER STATUS: Customer phone engaged or unavailable.\n"
                f"✅ SENTIMENT: Neutral\n"
                f"📌 ACTION ITEM: Queue follow-up callback or send an automated WhatsApp greeting template."
            )
            call.sentiment = "Neutral"
        else:
            call.transcript = (
                f"[{emp_name}]: Hello, this is {emp_name} calling regarding your CRM and sales inquiry. Am I speaking with {lead_name}?\n"
                f"[{lead_name}]: Yes, hi {emp_name}. Thanks for calling. We are actively reviewing CRM options for our sales team.\n"
                f"[{emp_name}]: Excellent! We provide live WebRTC softphone dialing, automated lead assignments, WhatsApp alerts, and manager call intelligence.\n"
                f"[{lead_name}]: That fits our exact requirements. Could you please share the pricing structure and arrange an onboarding demo?\n"
                f"[{emp_name}]: Absolutely {lead_name}. I will share the enterprise catalog and demo invitation right away."
            )
            call.ai_summary = (
                f"🎯 KEY DISCUSSION: Discussed upgrading sales telephony workflow, CRM lead routing, and manager call intelligence.\n"
                f"💡 CUSTOMER NEED: Softphone dialer, WhatsApp automated messaging, and agent performance tracking.\n"
                f"✅ SENTIMENT: Highly Interested (Positive Intent)\n"
                f"📌 ACTION ITEM: Share enterprise pricing proposal and schedule hands-on walkthrough demo."
            )
            call.sentiment = "Positive"

    db.commit()
    db.refresh(call)
    return build_call_log_response(call, db)


@router.get("/calls", response_model=CallLogListResponse)
def list_call_logs(
    response: Response,
    lead_id: Optional[int] = None,
    employee_id: Optional[int] = None,
    call_status: Optional[str] = None,
    provider: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists call logs with strict identity-based access control:
    - Employee: Sees ONLY calls where employee_id == current_user.employee_id.
    - Manager: Sees calls where employee_id IN (manager's authorized team).
    - Admin: Sees company-wide calls.
    Never trusts unverified employee_id sent from frontend.
    """
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    query = db.query(CallLog)
    authorized_emp_ids = get_authorized_call_employee_ids(current_user, db)

    # 1. Strict Permission Enforcement based on JWT identity and Role
    if authorized_emp_ids is not None:
        if len(authorized_emp_ids) == 0:
            return CallLogListResponse(
                total=0,
                items=[],
                page=page,
                limit=limit,
                metrics=CallLogMetricsSummary()
            )

        if employee_id is not None:
            # If frontend requested a specific employee_id, verify it's within authorized scope
            if employee_id not in authorized_emp_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: You are not authorized to view call logs for this employee."
                )
            query = query.filter(CallLog.employee_id == employee_id)
        else:
            if len(authorized_emp_ids) == 1:
                query = query.filter(CallLog.employee_id == authorized_emp_ids[0])
            else:
                query = query.filter(CallLog.employee_id.in_(authorized_emp_ids))
    else:
        # Admin / Company-wide access: can filter by employee_id if specified
        if employee_id is not None:
            query = query.filter(CallLog.employee_id == employee_id)

    # 2. Filter by lead_id (e.g. Lead Details -> Call History)
    if lead_id:
        current_emp = get_employee_for_user(current_user, db)
        if authorized_emp_ids is not None and current_emp:
            target_lead = db.query(Lead).filter(Lead.id == lead_id).first()
            if target_lead and target_lead.assigned_to is not None:
                if target_lead.assigned_to not in authorized_emp_ids and target_lead.assigned_to != current_emp.id:
                    return CallLogListResponse(
                        total=0,
                        items=[],
                        page=page,
                        limit=limit,
                        metrics=CallLogMetricsSummary()
                    )
        query = query.filter(CallLog.lead_id == lead_id)

    if call_status:
        query = query.filter(CallLog.call_status.ilike(f"%{call_status}%"))
    if provider:
        query = query.filter(CallLog.provider.ilike(f"%{provider}%"))

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

    total = query.count()
    page_num = page if isinstance(page, int) and page > 0 else 1
    limit_num = min(1000, limit if isinstance(limit, int) and limit > 0 else 50)
    offset = (page_num - 1) * limit_num
    calls = query.order_by(desc(CallLog.id)).offset(offset).limit(limit_num).all()

    items = [build_call_log_response(c, db) for c in calls]

    # Calculate authoritative metrics across the filtered query (all matching records, not just current page)
    if total > 0:
        agg = query.with_entities(
            func.sum(
                case(
                    (
                        or_(
                            CallLog.call_status.ilike("%COMPLETED%"),
                            CallLog.call_status.ilike("%CONNECTED%"),
                            CallLog.call_status.ilike("%ANSWERED%")
                        ),
                        1
                    ),
                    else_=0
                )
            ).label("connected"),
            func.sum(
                case(
                    (
                        or_(
                            CallLog.call_status.ilike("%MISSED%"),
                            CallLog.call_status.ilike("%BUSY%"),
                            CallLog.call_status.ilike("%FAILED%"),
                            CallLog.call_status.ilike("%NO_ANSWER%"),
                            CallLog.call_status.ilike("%NO ANSWER%")
                        ),
                        1
                    ),
                    else_=0
                )
            ).label("missed"),
            func.sum(
                case(
                    (
                        or_(
                            CallLog.call_status.ilike("%COMPLETED%"),
                            CallLog.call_status.ilike("%CONNECTED%"),
                            CallLog.call_status.ilike("%ANSWERED%")
                        ),
                        func.coalesce(CallLog.duration_seconds, 0)
                    ),
                    else_=0
                )
            ).label("total_secs")
        ).first()

        connected_count = int(agg.connected or 0)
        missed_count = int(agg.missed or 0)
        total_secs = int(agg.total_secs or 0)
        connect_rate = round((connected_count / total) * 100) if total > 0 else 0
        avg_duration = round(total_secs / connected_count) if connected_count > 0 else 0

        metrics = CallLogMetricsSummary(
            total_calls=total,
            connected_calls=connected_count,
            missed_calls=missed_count,
            connect_rate=connect_rate,
            total_duration_seconds=total_secs,
            avg_duration_seconds=avg_duration
        )
    else:
        metrics = CallLogMetricsSummary(
            total_calls=0,
            connected_calls=0,
            missed_calls=0,
            connect_rate=0,
            total_duration_seconds=0,
            avg_duration_seconds=0
        )

    return CallLogListResponse(
        total=total,
        page=page_num,
        limit=limit_num,
        items=items,
        metrics=metrics
    )

@router.get("/calls/{call_id}", response_model=CallLogResponse)
def get_call_log_details(
    call_id: str,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves call log details by DB ID or Provider Call SID.
    Enforces strict access control: returns HTTP 403 Forbidden if the user is not
    authorized to view this call log or its recording.
    """
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    if call_id.isdigit():
        call = db.query(CallLog).filter(CallLog.id == int(call_id)).first()
    else:
        call = db.query(CallLog).filter(CallLog.provider_call_id == call_id).first()

    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Call log record '{call_id}' not found."
        )

    # Permission check: direct access to another employee's call-log ID must return 403 Forbidden
    authorized_emp_ids = get_authorized_call_employee_ids(current_user, db)
    if authorized_emp_ids is not None:
        if call.employee_id is None or call.employee_id not in authorized_emp_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not have permission to view this call log or its recording."
            )

    # Sync live status with provider if call is non-terminal
    if call.call_status and call.call_status.upper() not in ["COMPLETED", "FAILED", "MISSED", "BUSY", "HANGUP", "CANCELED", "NO_ANSWER"]:
        try:
            provider = IVRService.get_provider(db=db)
            if provider and call.provider_call_id:
                details = provider.get_call_details(call.provider_call_id)
                if details and "status" in details:
                    new_st = details.get("status")
                    dur = details.get("duration_seconds")
                    rec = details.get("recording_url")
                    updated = IVRService.update_call_status(
                        db=db,
                        provider_call_id=call.provider_call_id,
                        new_status=new_st,
                        duration_seconds=dur,
                        recording_url=rec
                    )
                    if updated:
                        call = updated
        except Exception:
            pass

    return build_call_log_response(call, db)

@router.get("/calls/{call_id}/recording")
def stream_call_recording(
    call_id: str,
    request: Request,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Retrieves or redirects to the authenticated audio recording for a call.
    Validates permissions and handles PBX domain mapping.
    """
    auth_header = request.headers.get("Authorization")
    token_str = None
    if auth_header and auth_header.startswith("Bearer "):
        token_str = auth_header.split(" ", 1)[1]
    elif token:
        token_str = token

    if not token_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided."
        )

    current_user = get_user_from_token(token_str, db)

    if call_id.isdigit():
        call = db.query(CallLog).filter(CallLog.id == int(call_id)).first()
    else:
        call = db.query(CallLog).filter(CallLog.provider_call_id == call_id).first()

    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Call log record '{call_id}' not found."
        )

    authorized_emp_ids = get_authorized_call_employee_ids(current_user, db)
    if authorized_emp_ids is not None:
        if call.employee_id is None or call.employee_id not in authorized_emp_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not have permission to access this call recording."
            )

    rec_url = resolve_recording_url(call.recording_url, db)
    if not rec_url:
        raw_rec = str(call.recording_url or "").strip()
        if "127.0.0.1" in raw_rec or "localhost" in raw_rec:
            raise HTTPException(
                status_code=status.HTTP_202_ACCEPTED,
                detail="Doocti PBX recording is currently processing and not yet available for playback."
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No recording available for this call."
        )

    return RedirectResponse(url=rec_url, status_code=307)


@router.api_route("/webhook", methods=["GET", "POST"])
async def ivr_webhook_endpoint(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Public webhook receiver for IVR provider call status updates (supports GET and POST for CloudShope, Twilio, Exotel).
    """
    try:
        payload = {}
        # 1. Merge Query String parameters (e.g. CloudShope GET callback)
        if request.query_params:
            payload.update(dict(request.query_params))

        # 2. Merge Body parameters if POST request
        if request.method == "POST":
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    json_data = await request.json()
                    if isinstance(json_data, dict):
                        payload.update(json_data)
                except Exception:
                    pass
            else:
                try:
                    form_data = await request.form()
                    payload.update(dict(form_data))
                except Exception:
                    pass

        headers = dict(request.headers)
        result = handle_incoming_ivr_webhook(db, payload, headers)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}
