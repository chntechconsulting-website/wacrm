import os
import json
import re
import datetime
import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, or_

from database import get_db
from models import Lead, LeadActivity, Customer, Employee, CallLog
from models.integration import IntegrationConfig
from utils.timezone import get_ist_now, IST_TIMEZONE

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/doocti", tags=["Doocti IVR Connector"])

# -------------------------------------------------------------
# Helpers
# -------------------------------------------------------------
def parse_doocti_time(val: Any) -> Optional[datetime.datetime]:
    if not val:
        return None
    if isinstance(val, datetime.datetime):
        if val.tzinfo:
            return val.astimezone(IST_TIMEZONE).replace(tzinfo=None)
        return val
    if isinstance(val, (int, float)):
        try:
            ts = float(val) / 1000.0 if float(val) > 1e11 else float(val)
            return datetime.datetime.fromtimestamp(ts, tz=IST_TIMEZONE).replace(tzinfo=None)
        except Exception:
            return None
    val_str = str(val).strip()
    if not val_str:
        return None
    if val_str.isdigit():
        try:
            ts = float(val_str) / 1000.0 if float(val_str) > 1e11 else float(val_str)
            return datetime.datetime.fromtimestamp(ts, tz=IST_TIMEZONE).replace(tzinfo=None)
        except Exception:
            pass
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            parsed = datetime.datetime.strptime(val_str, fmt)
            if fmt.endswith("Z"):
                parsed = parsed.replace(tzinfo=datetime.timezone.utc).astimezone(IST_TIMEZONE).replace(tzinfo=None)
            return parsed
        except ValueError:
            continue
    try:
        from dateutil import parser
        parsed = parser.parse(val_str)
        if parsed.tzinfo:
            return parsed.astimezone(IST_TIMEZONE).replace(tzinfo=None)
        return parsed
    except Exception:
        return None

# -------------------------------------------------------------
# Schemas
# -------------------------------------------------------------
class DooctiCallLogPayload(BaseModel):
    model_config = {"extra": "ignore"}

    # Official DooCTI Push Call Log specification fields:
    uniqueid: Optional[str] = None
    phone_number: Optional[str] = None
    start_time: Optional[Any] = None
    station: Optional[Any] = None
    agent: Optional[str] = None
    status: Optional[str] = None
    end_time: Optional[Any] = None
    duration: Optional[Any] = None
    recording_path: Optional[str] = None

    # Alternative / backward-compatible aliases:
    call_id: Optional[str] = None
    provider_call_id: Optional[str] = None
    from_number: Optional[str] = None
    to_number: Optional[str] = None
    customer_number: Optional[str] = None
    agent_number: Optional[str] = None
    agent_email: Optional[str] = None
    call_status: Optional[str] = None
    call_direction: Optional[str] = "OUTBOUND"  # INBOUND, OUTBOUND
    duration_seconds: Optional[Any] = None
    recording_url: Optional[str] = None
    disposition: Optional[str] = None
    call_purpose: Optional[str] = None
    lead_stage: Optional[str] = None
    notes: Optional[str] = None
    entity_id: Optional[str] = None
    entity_type: Optional[str] = "Lead"

class DooctiLeadUpdatePayload(BaseModel):
    model_config = {"extra": "ignore"}
    lead_id: int
    status: Optional[str] = None
    call_notes: Optional[str] = None
    call_purpose: Optional[str] = None
    lead_stage: Optional[str] = None
    agent_email: Optional[str] = None

# Helper to normalize phone numbers for matching
def clean_phone(phone: Optional[str]) -> str:
    if not phone:
        return ""
    # Strip spaces, hyphens, parentheses, and leading plus
    cleaned = "".join(filter(str.isdigit, str(phone)))
    # If starts with country code 91 and has 12 digits, extract last 10 digits
    if len(cleaned) == 12 and cleaned.startswith("91"):
        cleaned = cleaned[2:]
    elif len(cleaned) > 10:
        cleaned = cleaned[-10:]
    return cleaned

# -------------------------------------------------------------
# 1. Lead Retrieval by Phone Number (PDF Page 4 & 6)
# Checks Leads -> Contacts -> Auto-creates Lead if absent
# -------------------------------------------------------------
@router.get("/lead-by-number")
@router.get("/leads/search")
def get_lead_by_number(
    number: Optional[str] = Query(None),
    phone: Optional[str] = Query(None),
    auto_create: bool = Query(False, description="Auto-create lead if not found (defaults to False)"),
    db: Session = Depends(get_db)
):
    target_num = clean_phone(number or phone)
    if not target_num:
        raise HTTPException(status_code=400, detail="Phone number is required.")

    # 1. Search in Leads table (ordered descending by ID/creation date)
    matched_lead = db.query(Lead).filter(
        or_(
            Lead.phone.like(f"%{target_num}%"),
            Lead.whatsapp_number.like(f"%{target_num}%")
        )
    ).order_by(desc(Lead.id)).first()

    if matched_lead:
        lead_owner_name = "Unassigned"
        if matched_lead.assigned_to:
            emp = db.query(Employee).filter(Employee.id == matched_lead.assigned_to).first()
            if emp:
                lead_owner_name = emp.name or f"{emp.first_name or ''} {emp.last_name or ''}".strip()

        lead_data = {
            "id": matched_lead.id,
            "customer_id": matched_lead.id,
            "name": matched_lead.name or "Unnamed Lead",
            "customer_name": matched_lead.name or "Unnamed Lead",
            "phone": matched_lead.phone,
            "customer_number": matched_lead.phone,
            "customer_id_str": str(matched_lead.id),
            "lead_owner": lead_owner_name,
            "status": matched_lead.status,
            "lead_status": matched_lead.status,
            "queue": "Default",
            "company": matched_lead.company or "",
            "entity_type": "Lead",
            "created_at": matched_lead.created_at.isoformat() if hasattr(matched_lead, 'created_at') and matched_lead.created_at else None
        }

        return {
            "status": "success",
            "success": True,
            "exists": True,
            "entity_type": "Lead",
            "lead": lead_data,
            "data": lead_data
        }

    # 2. Search in Contacts / Customers table
    matched_customer = db.query(Customer).filter(
        Customer.phone.like(f"%{target_num}%")
    ).order_by(desc(Customer.id)).first()

    if matched_customer:
        contact_data = {
            "id": matched_customer.id,
            "customer_id": matched_customer.id,
            "name": matched_customer.contact_name or matched_customer.company_name or "Contact",
            "customer_name": matched_customer.contact_name or matched_customer.company_name or "Contact",
            "phone": matched_customer.phone,
            "customer_number": matched_customer.phone,
            "customer_id_str": str(matched_customer.id),
            "lead_owner": "Existing Customer",
            "status": "CUSTOMER",
            "lead_status": "CUSTOMER",
            "queue": "Default",
            "company": matched_customer.company_name or "",
            "entity_type": "Contact",
            "created_at": matched_customer.created_at.isoformat() if matched_customer.created_at else None
        }

        return {
            "status": "success",
            "success": True,
            "exists": True,
            "entity_type": "Contact",
            "lead": contact_data,
            "data": contact_data
        }

    # 3. Not found: If auto_create is True AND the number is a full valid phone (>= 10 digits)
    if auto_create and len(target_num) >= 10:
        raw_display_num = number or phone or target_num
        new_lead = Lead(
            name=f"Inbound Caller ({raw_display_num})",
            phone=raw_display_num,
            source="DOOCTI_INBOUND",
            status="NEW",
            priority="MEDIUM",
            rating="Warm",
            requirement_notes="Lead automatically created via Doocti Inbound Call retrieval."
        )
        db.add(new_lead)
        db.commit()
        db.refresh(new_lead)

        # Log Activity
        activity = LeadActivity(
            lead_id=new_lead.id,
            activity_type="SYSTEM",
            description=f"Auto-created lead from Doocti inbound telephony lookup for {raw_display_num}."
        )
        db.add(activity)
        db.commit()

        lead_data = {
            "id": new_lead.id,
            "customer_id": new_lead.id,
            "name": new_lead.name,
            "customer_name": new_lead.name,
            "phone": new_lead.phone,
            "customer_number": new_lead.phone,
            "customer_id_str": str(new_lead.id),
            "lead_owner": "Unassigned",
            "status": new_lead.status,
            "lead_status": new_lead.status,
            "queue": "Default",
            "company": "",
            "entity_type": "Lead",
            "created_at": datetime.datetime.utcnow().isoformat()
        }

        return {
            "status": "success",
            "success": True,
            "exists": False,
            "auto_created": True,
            "entity_type": "Lead",
            "lead": lead_data,
            "data": lead_data
        }

    return {
        "status": "not_found",
        "success": False,
        "exists": False,
        "lead": None,
        "data": None,
        "message": f"No lead or contact found matching {target_num}."
    }

# -------------------------------------------------------------
# 2. Contact Page API (PDF Page 2)
# Sorted in ASCENDING order based on contact name
# -------------------------------------------------------------
@router.get("/contacts")
def get_doocti_contacts(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    contacts_query = db.query(Customer).order_by(asc(Customer.contact_name)).offset(offset).limit(limit).all()
    results = []
    for c in contacts_query:
        results.append({
            "id": c.id,
            "name": c.contact_name,
            "company": c.company_name,
            "phone": c.phone,
            "email": c.email or "",
            "location": c.location or ""
        })

    total_count = db.query(Customer).count()
    return {
        "status": "success",
        "total": total_count,
        "items": results
    }

# -------------------------------------------------------------
# 3. Status APIs (PDF Page 9)
# -------------------------------------------------------------
@router.get("/lead-statuses")
def get_lead_statuses():
    return {
        "status": "success",
        "statuses": [
            {"code": "NEW", "label": "New Lead"},
            {"code": "ASSIGNED", "label": "Assigned"},
            {"code": "CONTACTED", "label": "Contacted"},
            {"code": "INTERESTED", "label": "Interested"},
            {"code": "FOLLOW_UP", "label": "Follow Up"},
            {"code": "QUALIFIED", "label": "Qualified"},
            {"code": "CONVERTED", "label": "Converted to Customer"},
            {"code": "NOT_INTERESTED", "label": "Not Interested"},
            {"code": "LOST", "label": "Lost"}
        ]
    }

@router.get("/call-statuses")
def get_call_statuses():
    return {
        "status": "success",
        "statuses": [
            {"code": "ANSWERED", "label": "Answered / Connected"},
            {"code": "MISSED", "label": "Missed Call"},
            {"code": "BUSY", "label": "Busy / Line Engaged"},
            {"code": "NO_ANSWER", "label": "No Answer / Unreachable"},
            {"code": "SWITCHED_OFF", "label": "Switched Off"},
            {"code": "FAILED", "label": "Call Failed"}
        ]
    }

# -------------------------------------------------------------
# 4. Call Log Push API (DooCTI Push Call Log)
# Ingests CDR, duration, recordings, and status from DooCTI
# Supports JSON, Form-urlencoded, Query Params (GET/POST)
# -------------------------------------------------------------
@router.api_route("/call-log", methods=["GET", "POST"])
@router.api_route("/call-log/", methods=["GET", "POST"])
@router.api_route("/push-call-log", methods=["GET", "POST"])
@router.api_route("/push-call-log/", methods=["GET", "POST"])
@router.api_route("/push_call_log", methods=["GET", "POST"])
@router.api_route("/push_call_log/", methods=["GET", "POST"])
@router.api_route("/recording", methods=["GET", "POST"])
@router.api_route("/recording/", methods=["GET", "POST"])
@router.api_route("/recording-ready", methods=["GET", "POST"])
@router.api_route("/recording-ready/", methods=["GET", "POST"])
@router.api_route("/call-logs", methods=["GET", "POST"])
@router.api_route("/call-logs/", methods=["GET", "POST"])
@router.api_route("/cdr", methods=["GET", "POST"])
@router.api_route("/cdr/", methods=["GET", "POST"])
async def push_doocti_call_log(
    request: Request,
    db: Session = Depends(get_db)
):
    # 0. Ingest raw data from any format (JSON, Form Data, Query Params)
    raw_data: Dict[str, Any] = {}
    content_type = request.headers.get("content-type", "").lower()
    client_ip = request.client.host if request.client else "unknown"

    if request.method == "POST":
        if "application/json" in content_type:
            try:
                raw_data = await request.json()
            except Exception as e:
                logger.warning(f"[DOOCTI] Failed to parse JSON: {e}")
        elif "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
            try:
                form_data = await request.form()
                raw_data = dict(form_data)
            except Exception as e:
                logger.warning(f"[DOOCTI] Failed to parse form: {e}")
        else:
            # Fallback: attempt JSON, then Form, then body string
            try:
                raw_data = await request.json()
            except Exception:
                try:
                    form_data = await request.form()
                    raw_data = dict(form_data)
                except Exception:
                    try:
                        body_bytes = await request.body()
                        if body_bytes:
                            from urllib.parse import parse_qs
                            parsed_qs = parse_qs(body_bytes.decode("utf-8", errors="ignore"))
                            raw_data = {k: v[0] if len(v) == 1 else v for k, v in parsed_qs.items()}
                    except Exception:
                        pass

    # Merge query parameters (useful for GET webhooks or URL overrides)
    for k, v in request.query_params.items():
        if k not in raw_data or raw_data[k] is None or raw_data[k] == "":
            raw_data[k] = v

    logger.info(f"☎️ [DOOCTI CALL EVENT INGESTED] Method={request.method} Content-Type='{content_type}' Client={client_ip}")
    logger.info(f"   Payload: {raw_data}")

    # 1. Identify Call Session ID / uniqueid
    call_id = (
        raw_data.get("uniqueid") or 
        raw_data.get("call_id") or 
        raw_data.get("provider_call_id") or 
        raw_data.get("callid") or 
        raw_data.get("CallId") or 
        raw_data.get("session_id") or 
        raw_data.get("id")
    )
    if call_id:
        call_id = str(call_id).strip()

    # Pre-lookup existing log by provider_call_id for idempotent updates / delayed recording delivery
    existing_log = db.query(CallLog).filter(CallLog.provider_call_id == call_id).first() if call_id else None

    call_dir = (raw_data.get("call_direction") or raw_data.get("direction") or (existing_log.call_direction if existing_log else "OUTBOUND")).upper()

    # 2. Agent & Station extraction
    agent_name = str(
        raw_data.get("agent") or 
        raw_data.get("agent_name") or 
        raw_data.get("user_name") or 
        raw_data.get("user") or 
        ""
    ).strip()
    station_str = str(
        raw_data.get("station") or 
        raw_data.get("agent_number") or 
        raw_data.get("extension") or 
        raw_data.get("ext") or 
        ""
    ).strip()
    clean_station = clean_phone(station_str)
    agent_email = str(
        raw_data.get("agent_email") or 
        raw_data.get("user_email") or 
        raw_data.get("email") or 
        ""
    ).strip()

    # 3. Identify target customer phone number
    if call_dir == "INBOUND":
        customer_phone = str(
            raw_data.get("customer_number") or 
            raw_data.get("phone_number") or 
            raw_data.get("from_number") or 
            raw_data.get("caller") or 
            (existing_log.from_number if existing_log else "") or
            ""
        ).strip()
    else:
        customer_phone = str(
            raw_data.get("phone_number") or 
            raw_data.get("customer_number") or 
            raw_data.get("to_number") or 
            raw_data.get("phone") or 
            raw_data.get("number") or 
            (existing_log.to_number if existing_log else "") or
            ""
        ).strip()
    clean_target = clean_phone(customer_phone)

    # 3b. REJECT GHOST CALLS: Prevent self-extension loop, empty phone numbers, or invalid calls
    # ONLY reject if it is a NEW call (no existing CallLog matches this uniqueid/call_id)
    if not existing_log:
        if not clean_target or len(clean_target) < 6 or (clean_station and clean_target == clean_station) or clean_target in ["1282", "1283"]:
            logger.warning(f"⚠️ [DOOCTI CDR] Ignored ghost/invalid call log payload: clean_target='{clean_target}', station='{station_str}', dir={call_dir}")
            return {
                "status": "ignored",
                "message": "Ghost call rejected: Customer number is missing or equals agent extension",
                "clean_target": clean_target
            }

    # 4. Fallback call_id generation if none provided
    if not call_id:
        st_tag = station_str or "doocti"
        ph_tag = clean_target or "unknown"
        call_id = f"doocti_{st_tag}_{ph_tag}_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"

    # 5. Duration parsing (seconds)
    has_explicit_duration = any(raw_data.get(k) is not None for k in ["duration", "duration_seconds", "billsec"])
    dur_raw = (
        raw_data.get("duration") 
        if raw_data.get("duration") is not None 

        else (raw_data.get("duration_seconds") if raw_data.get("duration_seconds") is not None else raw_data.get("billsec"))
    )
    dur_sec = 0
    if dur_raw is not None:
        try:
            dur_sec = int(float(str(dur_raw).strip()))
        except (ValueError, TypeError):
            dur_sec = 0
    elif existing_log and existing_log.duration_seconds:
        dur_sec = existing_log.duration_seconds

    # 6. Timestamp parsing (Indian Standard Time Asia/Kolkata)
    started_at = parse_doocti_time(raw_data.get("start_time") or raw_data.get("started_at")) or (existing_log.started_at if existing_log else None)
    answered_at = parse_doocti_time(raw_data.get("answer_time") or raw_data.get("answered_at")) or (existing_log.answered_at if existing_log else None)
    ended_at = parse_doocti_time(raw_data.get("end_time") or raw_data.get("ended_at")) or (existing_log.ended_at if existing_log else None)
    now_ist = get_ist_now()
    if not ended_at:
        ended_at = now_ist
    if not started_at:
        started_at = ended_at - datetime.timedelta(seconds=dur_sec) if dur_sec > 0 else ended_at

    # 7. Recording path / URL
    rec_url = str(
        raw_data.get("recording_path") or 
        raw_data.get("recording_url") or 
        raw_data.get("recording") or 
        ""
    ).strip() or None

    # 8. Call Status normalization
    has_explicit_status = any(raw_data.get(k) for k in ["status", "call_status", "disposition", "call_state"])
    if not has_explicit_status and existing_log:
        status_str = existing_log.call_status or "COMPLETED"
        raw_status = status_str
    else:
        raw_status = str(
            raw_data.get("status") or 
            raw_data.get("call_status") or 
            raw_data.get("disposition") or 
            raw_data.get("call_state") or 
            "COMPLETED"
        ).strip()
    raw_upper = raw_status.upper()

    if any(k in raw_upper for k in ["RINGING", "RING", "INCOMING"]):
        status_str = "RINGING"
        dur_sec = 0
        answered_at = None
        ended_at = None
    elif any(k in raw_upper for k in ["CONNECTING", "DIALING", "INITIATED", "INITIATING"]):
        status_str = "CONNECTING"
        dur_sec = 0
        answered_at = None
        ended_at = None
    elif any(k in raw_upper for k in ["NO ANSWER", "NO_ANSWER", "NOT ANSWER", "NOT ANSWERED", "NOANSWER"]):
        status_str = "MISSED" if call_dir == "INBOUND" else "NO_ANSWER"
        dur_sec = 0
        answered_at = None
    elif any(k in raw_upper for k in ["MISSED", "UNANSWERED", "DECLINED", "REJECTED"]):
        status_str = "MISSED"
        dur_sec = 0
        answered_at = None
    elif any(k in raw_upper for k in ["BUSY", "ENGAGED"]):
        status_str = "BUSY"
        dur_sec = 0
        answered_at = None
    elif any(k in raw_upper for k in ["FAIL", "ERROR"]):
        # An incoming call that was not answered or got disconnected is a MISSED call, not FAILED!
        if call_dir == "INBOUND" and dur_sec == 0 and not answered_at:
            status_str = "MISSED"
        else:
            status_str = "FAILED"
        dur_sec = 0
        answered_at = None
    elif any(k in raw_upper for k in ["SUCCESS", "ANSWERED", "CONNECTED"]):
        status_str = "ANSWERED"
        if not answered_at:
            answered_at = started_at or now_ist
        if ended_at and answered_at and ended_at >= answered_at:
            dur_sec = max(0, int((ended_at - answered_at).total_seconds()))
    elif any(k in raw_upper for k in ["COMPLETED", "HANGUP", "DISCONNECTED", "ENDED"]):
        if answered_at and ended_at and ended_at >= answered_at:
            dur_sec = max(0, int((ended_at - answered_at).total_seconds()))
            status_str = "COMPLETED"
        elif dur_sec > 0:
            status_str = "COMPLETED"
        else:
            status_str = "MISSED" if call_dir == "INBOUND" else "NO_ANSWER"
            dur_sec = 0
            answered_at = None
    else:
        status_str = raw_upper or ("RINGING" if call_dir == "INBOUND" and dur_sec == 0 else "COMPLETED")

    # 9. Resolve or Auto-create Lead
    resolved_lead_id = None
    entity_id_val = raw_data.get("entity_id") or raw_data.get("lead_id")
    if entity_id_val and str(entity_id_val).isdigit():
        resolved_lead_id = int(entity_id_val)
    elif clean_target:
        matched = db.query(Lead).filter(
            or_(
                Lead.phone.like(f"%{clean_target}%"),
                Lead.whatsapp_number.like(f"%{clean_target}%")
            )
        ).order_by(desc(Lead.id)).first()
        if matched:
            resolved_lead_id = matched.id
        else:
            # Check Customer table
            matched_cust = db.query(Customer).filter(
                Customer.phone.like(f"%{clean_target}%")
            ).first()

            # Auto-create lead so caller is tracked in CRM
            raw_display = customer_phone or clean_target
            new_lead = Lead(
                name=f"Call Lead ({raw_display})",
                phone=raw_display,
                source="DOOCTI",
                status="CONTACTED" if status_str in ["ANSWERED", "COMPLETED"] else "NEW",
                priority="MEDIUM",
                requirement_notes=f"Auto-created from DooCTI Call. Station: {station_str or '1282'}, Agent: {agent_name or 'DooCTI'}"
            )
            db.add(new_lead)
            db.commit()
            db.refresh(new_lead)
            resolved_lead_id = new_lead.id

    # 10. Resolve Employee (Agent) - Essential for Employee Call Logs Permissions!
    explicit_emp_id = raw_data.get("employee_id")
    resolved_emp_id = None
    if explicit_emp_id and str(explicit_emp_id).isdigit():
        emp = db.query(Employee).filter(Employee.id == int(explicit_emp_id)).first()
        if emp:
            resolved_emp_id = emp.id

    if not resolved_emp_id and agent_email:
        emp = db.query(Employee).filter(Employee.email.ilike(agent_email)).first()
        if emp:
            resolved_emp_id = emp.id

    if not resolved_emp_id and agent_name:
        emp = db.query(Employee).filter(
            or_(
                Employee.name.ilike(f"%{agent_name}%"),
                Employee.username.ilike(agent_name),
                Employee.email.ilike(agent_name)
            )
        ).first()
        if emp:
            resolved_emp_id = emp.id

    if not resolved_emp_id and station_str:
        clean_st = clean_phone(station_str)
        emp = db.query(Employee).filter(
            or_(
                Employee.phone.like(f"%{clean_st}%"),
                Employee.username == station_str
            )
        ).first()
        if emp:
            resolved_emp_id = emp.id

    # If still not resolved, check if lead is assigned to an employee
    if not resolved_emp_id and resolved_lead_id:
        target_lead = db.query(Lead).filter(Lead.id == resolved_lead_id).first()
        if target_lead and target_lead.assigned_to:
            resolved_emp_id = target_lead.assigned_to

    # If still not resolved and station is 1282 or Doocti default agent, map to default employee
    if not resolved_emp_id:
        if station_str in ["1282", "1283"] or "chntechnolog_agent01" in agent_email:
            default_emp = db.query(Employee).filter(Employee.user_id == 1).first() or db.query(Employee).first()
            if default_emp:
                resolved_emp_id = default_emp.id

    # Fallback to first active employee so record is never orphaned
    if not resolved_emp_id:
        default_emp = db.query(Employee).filter(Employee.status == "ACTIVE").first()
        if default_emp:
            resolved_emp_id = default_emp.id

    # 11. Compile Notes
    notes_parts = []
    if agent_name:
        notes_parts.append(f"Agent: {agent_name}")
    if station_str:
        notes_parts.append(f"Station: {station_str}")
    if raw_status:
        notes_parts.append(f"DooCTI Status: {raw_status}")
    if raw_data.get("disposition"):
        notes_parts.append(f"Disposition: {raw_data['disposition']}")
    if raw_data.get("call_purpose"):
        notes_parts.append(f"Purpose: {raw_data['call_purpose']}")
    if raw_data.get("notes"):
        notes_parts.append(f"Notes: {raw_data['notes']}")
    combined_notes = " | ".join(notes_parts) if notes_parts else "DooCTI Call completed."

    # Direction
    call_dir = (raw_data.get("call_direction") or raw_data.get("direction") or "OUTBOUND").upper()

    # 12. Check if CallLog already exists for this call_id (handling idempotency / updates)
    if not existing_log and call_id:
        existing_log = db.query(CallLog).filter(CallLog.provider_call_id == call_id).first()

    # Cross-provider duplicate detection: same phone + same time window (3 min) from any provider
    # Prevents double entries when Doocti AND Smartflo both fire webhooks for the same physical call
    if not existing_log and clean_target and started_at:
        window_start = started_at - datetime.timedelta(minutes=3)
        window_end = started_at + datetime.timedelta(minutes=3)
        existing_log = (
            db.query(CallLog)
            .filter(
                or_(
                    CallLog.to_number.like(f"%{clean_target}%"),
                    CallLog.from_number.like(f"%{clean_target}%"),
                ),
                CallLog.started_at >= window_start,
                CallLog.started_at <= window_end,
                CallLog.call_direction == call_dir,
            )
            .order_by(desc(CallLog.created_at))
            .first()
        )
        if existing_log:
            logger.info(
                f"🔁 [DOOCTI CDR] Cross-provider duplicate detected: "
                f"existing CallLog ID={existing_log.id} (provider={existing_log.provider}, "
                f"call_id={existing_log.provider_call_id}) matches phone={clean_target} "
                f"within 3-min window. Merging instead of creating duplicate."
            )

    if existing_log:
        curr_status = (existing_log.call_status or "").upper()
        # State machine protection:
        # 1. If payload didn't explicitly specify status, preserve existing status
        # 2. Do not revert an ANSWERED/CONNECTED call to RINGING/CONNECTING
        # 3. Do not revert a COMPLETED call to prior/transient states
        if not has_explicit_status:
            logger.info(f"Preserving existing status '{curr_status}' (no explicit status in payload) for CallLog ID={existing_log.id}")
        elif curr_status in ["ANSWERED", "CONNECTED"] and status_str in ["RINGING", "CONNECTING"]:
            logger.info(f"Preserving active status '{curr_status}', ignoring stale '{status_str}' for CallLog ID={existing_log.id}")
        elif curr_status == "COMPLETED" and status_str in ["RINGING", "CONNECTING", "ANSWERED", "MISSED", "FAILED"]:
            logger.info(f"Preserving COMPLETED status, ignoring subsequent '{status_str}' for CallLog ID={existing_log.id}")
        else:
            existing_log.call_status = status_str

        # Duration preservation: never overwrite positive duration with 0
        if dur_sec > 0:
            existing_log.duration_seconds = dur_sec
        elif not existing_log.duration_seconds:
            existing_log.duration_seconds = 0

        if rec_url:
            is_new_loopback = "127.0.0.1" in rec_url or "localhost" in rec_url
            curr_rec = str(existing_log.recording_url or "").strip()
            is_curr_loopback = "127.0.0.1" in curr_rec or "localhost" in curr_rec
            # Update if existing has no recording, or is loopback, or new rec_url is a public/valid URL
            if not curr_rec or is_curr_loopback or not is_new_loopback:
                existing_log.recording_url = rec_url
        if call_id and (not existing_log.provider_call_id or existing_log.provider_call_id.startswith("doocti_") or existing_log.provider_call_id.startswith("call_")):
            existing_log.provider_call_id = call_id
        if started_at and not existing_log.started_at:
            existing_log.started_at = started_at
        if answered_at and not existing_log.answered_at:
            existing_log.answered_at = answered_at
        elif has_explicit_status and status_str in ["ANSWERED", "CONNECTED"] and not existing_log.answered_at:
            existing_log.answered_at = now_ist
        elif has_explicit_status and status_str in ["NO_ANSWER", "MISSED", "BUSY", "FAILED"] and not existing_log.answered_at:
            existing_log.answered_at = None
            existing_log.duration_seconds = 0

        if has_explicit_status and status_str in ["COMPLETED", "MISSED", "NO_ANSWER", "BUSY", "FAILED"]:
            existing_log.ended_at = ended_at or now_ist

        if combined_notes and combined_notes not in (existing_log.notes or ""):
            existing_log.notes = f"{existing_log.notes or ''}\n{combined_notes}".strip()
        if resolved_lead_id and not existing_log.lead_id:
            existing_log.lead_id = resolved_lead_id
        if resolved_emp_id and not existing_log.employee_id:
            existing_log.employee_id = resolved_emp_id
        db.commit()
        db.refresh(existing_log)
        call_entry = existing_log
        logger.info(f"✅ [DOOCTI CDR] Updated CallLog ID={call_entry.id} uniqueid='{call_id}' Status='{existing_log.call_status}' Duration={existing_log.duration_seconds}s EmpID={resolved_emp_id}")
    else:
        if call_dir == "INBOUND":
            from_num = customer_phone or clean_target
            to_num = station_str or "1282"
        else:
            from_num = station_str or "1282"
            to_num = customer_phone or clean_target

        call_entry = CallLog(
            lead_id=resolved_lead_id,
            employee_id=resolved_emp_id,
            provider="DOOCTI",
            provider_call_id=call_id,
            from_number=from_num,
            to_number=to_num,
            call_status=status_str,
            call_direction=call_dir,
            duration_seconds=dur_sec,
            recording_url=rec_url,
            started_at=started_at,
            answered_at=answered_at,
            ended_at=ended_at,
            notes=combined_notes
        )
        db.add(call_entry)
        db.commit()
        db.refresh(call_entry)
        logger.info(f"✅ [DOOCTI CDR] Created CallLog ID={call_entry.id} uniqueid='{call_id}' Status='{status_str}' Duration={dur_sec}s EmpID={resolved_emp_id}")

    # 13. Append activity to lead history
    if resolved_lead_id:
        activity = LeadActivity(
            lead_id=resolved_lead_id,
            performed_by=resolved_emp_id,
            activity_type="CALL_COMPLETED",
            description=f"DooCTI call logged: Status={raw_status} ({status_str}), Duration={dur_sec}s, Agent={agent_name or station_str or 'Agent'}. Recording: {rec_url or 'N/A'}"
        )
        db.add(activity)
        db.commit()

    return {
        "status": "success",
        "message": "Call log processed and saved successfully",
        "uniqueid": call_id,
        "call_log_id": call_entry.id,
        "employee_id": resolved_emp_id,
        "lead_id": resolved_lead_id,
        "call_status": status_str,
        "duration": dur_sec,
        "recording_path": call_entry.recording_url
    }

# -------------------------------------------------------------
# 5. Lead Update API from Disposition (PDF Page 8 & 9)
# -------------------------------------------------------------
@router.post("/lead/update")
def update_lead_from_doocti(
    payload: DooctiLeadUpdatePayload,
    db: Session = Depends(get_db)
):
    lead = db.query(Lead).filter(Lead.id == payload.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    if payload.status:
        lead.status = payload.status.upper()
    
    if payload.call_notes:
        existing = lead.requirement_notes or ""
        lead.requirement_notes = f"{existing}\n[Doocti Call Notes]: {payload.call_notes}".strip()

    db.commit()

    # Log activity
    activity = LeadActivity(
        lead_id=lead.id,
        activity_type="LEAD_UPDATED",
        description=f"Lead updated via Doocti Call Disposition. Status: {lead.status}. Notes: {payload.call_notes or 'None'}"
    )
    db.add(activity)
    db.commit()

    return {
        "status": "success",
        "message": "Lead updated successfully",
        "lead_id": lead.id,
        "current_status": lead.status
    }

# -------------------------------------------------------------
# 6. Call Control APIs (Answer / Reject / Disconnect)
# -------------------------------------------------------------
@router.post("/calls/{call_id}/disconnect")
@router.post("/calls/{call_id}/reject")
@router.post("/calls/{call_id}/hangup")
def disconnect_doocti_call(
    call_id: str,
    action: Optional[str] = Query("disconnect", description="disconnect or reject"),
    db: Session = Depends(get_db)
):
    """
    Terminates or rejects an active Doocti incoming/outbound call from CRM.
    Updates CallLog to MISSED (if ringing) or COMPLETED (if connected).
    """
    if call_id.isdigit():
        call = db.query(CallLog).filter(CallLog.id == int(call_id)).first()
    else:
        call = db.query(CallLog).filter(CallLog.provider_call_id == call_id).first()

    if not call:
        raise HTTPException(status_code=404, detail="Call record not found.")

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

    # Log activity on lead
    if call.lead_id:
        act = LeadActivity(
            lead_id=call.lead_id,
            performed_by=call.employee_id,
            activity_type="CALL_DISCONNECTED",
            related_entity_type="CALL",
            related_entity_id=call.id,
            description=f"Doocti call {new_status.lower()} from CRM. Caller: {call.from_number or call.to_number}."
        )
        db.add(act)
        db.commit()

    return {
        "status": "success",
        "message": f"Call {new_status.lower()} successfully",
        "call_id": call.id,
        "provider_call_id": call.provider_call_id,
        "call_status": call.call_status,
        "duration": call.duration_seconds or 0
    }

