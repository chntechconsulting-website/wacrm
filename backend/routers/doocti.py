import os
import json
import re
import datetime
import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, or_, and_

from database import get_db
from models import Lead, LeadActivity, Customer, Employee, CallLog, Followup
from models.lead import LeadAssignment
from models.user import User
from models.integration import IntegrationConfig
from services.auth import get_current_user
from utils.timezone import get_ist_now, IST_TIMEZONE
from utils.phone import normalize_phone, find_existing_lead_by_phone, find_existing_customer_by_phone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/doocti", tags=["Doocti IVR Connector"])

# -------------------------------------------------------------
# Telephony Configuration Dynamic Defaults (Loaded from IntegrationConfig)
# -------------------------------------------------------------
DOOCTI_DIDS: List[str] = ["07969659985", "7969659985", "07969671855", "07969671856", "07969671857"]
ADMIN_EXTENSION = ""
AGENT_EXTENSIONS: List[str] = []
ALL_EXTENSIONS: List[str] = []

# -------------------------------------------------------------
# Helpers
# -------------------------------------------------------------
def get_doocti_config(db: Session) -> Dict[str, Any]:
    """Retrieve active Doocti config dynamically from database (configured via Admin page)."""
    cfg = db.query(IntegrationConfig).filter(IntegrationConfig.integration_type == "IVR").first()
    data = {}
    if cfg and cfg.config_data:
        try:
            data = json.loads(cfg.config_data) if isinstance(cfg.config_data, str) else dict(cfg.config_data)
        except Exception:
            data = {}

    dids = data.get("did_numbers") or DOOCTI_DIDS
    if isinstance(dids, str):
        dids = [d.strip() for d in dids.split(",") if d.strip()]

    ext_map = data.get("extension_mapping")
    if ext_map is None:
        ext_map = {}

    admin_ext = data.get("admin_extension") or ADMIN_EXTENSION
    agent_exts = data.get("agent_extensions") or AGENT_EXTENSIONS
    if isinstance(agent_exts, str):
        agent_exts = [e.strip() for e in agent_exts.split(",") if e.strip()]

    return {
        "provider": data.get("provider", "DOOCTI"),
        "webhook_url": data.get("webhook_url", "https://www.wapluscrm.in/api/doocti/call-log"),
        "did_numbers": dids,
        "admin_extension": admin_ext,
        "agent_extensions": agent_exts,
        "extension_mapping": ext_map,
        "api_url": (data.get("api_url") or "").strip() or "https://beta3-app.doocti.com/",
        "account_id": (data.get("account_id") or "").strip() or "chntechnolog",
        "recording_base_url": data.get("recording_base_url", "https://bmxrx2cviyka.compat.objectstorage.ap-mumbai-1.oraclecloud.com/doocti/cti_chntechnolog_20261009"),
        "secret_token": data.get("secret_token")
    }

def clean_phone(phone: Optional[Any]) -> str:
    """Normalize phone string extracting standard 10-digit number."""
    return normalize_phone(phone)

def is_did_number(number: Optional[Any], did_list: Optional[List[str]] = None) -> bool:
    """Check if given number matches any configured DID."""
    if not number:
        return False
    clean_target = clean_phone(number)
    if not clean_target:
        return False
    dids = list(did_list or DOOCTI_DIDS)
    # Ensure all company DIDs from Doocti portal are recognized
    for extra_did in ["7969659985", "07969659985", "7969671855", "07969671855", "7969671856", "07969671856", "7969671857", "07969671857"]:
        if extra_did not in dids:
            dids.append(extra_did)
    for did in dids:
        clean_d = clean_phone(did)
        if clean_d and (clean_target == clean_d or clean_target.endswith(clean_d) or clean_d.endswith(clean_target)):
            return True
    return False

def is_extension_number(number: Optional[Any], ext_list: Optional[List[str]] = None, ext_map: Optional[Dict[str, Any]] = None) -> bool:
    """Check if number is one of configured WebRTC extensions in database."""
    if not number:
        return False
    st = str(number).strip()
    if ext_map and st in ext_map:
        return True
    if ext_list and st in ext_list:
        return True
    return len(st) in [3, 4, 5] and st.isdigit()

def sanitize_payload_for_logging(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Mask sensitive tokens, passwords and secrets before writing to logs."""
    sensitive_keys = {"secret", "token", "password", "key", "authorization", "auth", "secret_token", "api_key"}
    sanitized = {}
    for k, v in payload.items():
        if any(sk in str(k).lower() for sk in sensitive_keys):
            sanitized[k] = "***REDACTED***"
        elif isinstance(v, dict):
            sanitized[k] = sanitize_payload_for_logging(v)
        else:
            sanitized[k] = v
    return sanitized

def extract_string_val(val: Any) -> str:
    """Safely extracts string value even if Doocti sends a dict/object."""
    if not val:
        return ""
    if isinstance(val, dict):
        return str(val.get("value") or val.get("name") or val.get("identity") or val.get("id") or "").strip()
    return str(val).strip()

def resolve_employee_for_call(
    db: Session,
    station: Optional[str] = None,
    agent_name: Optional[str] = None,
    agent_email: Optional[str] = None,
    explicit_emp_id: Optional[Any] = None,
    extension_map: Optional[Dict[str, Any]] = None
) -> Optional[int]:
    """
    Accurately maps the call event to a WA!CRM Employee ID:
    1. Explicit employee_id from payload (if valid)
    2. Dynamic extension mapping from database configuration
    3. Employee database email lookup
    4. Employee database username or extension/phone lookup
    """
    if explicit_emp_id and str(explicit_emp_id).isdigit():
        emp = db.query(Employee).filter(Employee.id == int(explicit_emp_id)).first()
        if emp:
            return emp.id

    ext_mapping = extension_map if extension_map is not None else get_doocti_config(db).get("extension_mapping", {})
    st_clean = str(station).strip() if station else ""
    st_digits = "".join(filter(str.isdigit, st_clean))

    # 1. Match from extension mapping dictionary (exact or numeric digits)
    target_ext = st_clean if st_clean in ext_mapping else (st_digits if st_digits in ext_mapping else None)
    if target_ext:
        mapped_emp_id = ext_mapping[target_ext].get("employee_id")
        if mapped_emp_id:
            emp = db.query(Employee).filter(Employee.id == mapped_emp_id).first()
            if emp:
                return emp.id

    # 2. Match from agent_email
    if agent_email:
        clean_email = agent_email.strip().lower()
        emp = db.query(Employee).filter(Employee.email.ilike(clean_email)).first()
        if emp:
            return emp.id

    # 3. Match from station / extension in Employee table (phone or username)
    if st_clean:
        clean_st = clean_phone(st_clean)
        emp = db.query(Employee).filter(
            or_(
                Employee.username == st_clean,
                Employee.phone == st_clean,
                Employee.phone.like(f"%{clean_st}%") if clean_st else False
            )
        ).first()
        if emp:
            return emp.id

    # 4. Match from agent_name
    if agent_name:
        emp = db.query(Employee).filter(
            or_(
                Employee.name.ilike(f"%{agent_name.strip()}%"),
                Employee.username.ilike(agent_name.strip())
            )
        ).first()
        if emp:
            return emp.id

    # 5. Fallback mapping for recognized WebRTC extensions
    if st_clean in ext_mapping:
        return ext_mapping[st_clean].get("employee_id")

    return None

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
    employee_id: Optional[int] = None
    product_category: Optional[str] = None
    call_id: Optional[str] = None
    followup_date: Optional[date] = None
    followup_time: Optional[str] = None
    followup_priority: Optional[str] = "MEDIUM"

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
    uniqueid: Optional[str] = Query(None, description="Optional incoming PBX call unique ID"),
    call_id: Optional[str] = Query(None),
    station: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    raw_input_phone = number or phone
    target_num = clean_phone(raw_input_phone)
    if not target_num:
        raise HTTPException(status_code=400, detail="Phone number is required.")

    # 1. Search in Leads table using robust normalized phone search
    matched_lead = find_existing_lead_by_phone(db, raw_input_phone)

    if matched_lead:
        lead_owner_name = "Unassigned"
        if matched_lead.assigned_to:
            emp = db.query(Employee).filter(Employee.id == matched_lead.assigned_to).first()
            if emp:
                lead_owner_name = emp.name or f"{emp.first_name or ''} {emp.last_name or ''}".strip()

        from services.product_categorization_service import ProductCategorizationService
        cat_info = ProductCategorizationService.suggest_category_for_lead(matched_lead)

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
            "product_category": matched_lead.product_category or cat_info.get("suggested_category") or "UNCLASSIFIED",
            "suggested_product_category": cat_info.get("suggested_category") or "UNCLASSIFIED",
            "product_category_confirmed": bool(matched_lead.product_category_confirmed),
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

    # 2. Search in Contacts / Customers table using robust normalized phone search
    matched_customer = find_existing_customer_by_phone(db, raw_input_phone)

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
        raw_display_num = raw_input_phone or target_num
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
            "product_category": "UNCLASSIFIED",
            "suggested_product_category": "UNCLASSIFIED",
            "product_category_confirmed": False,
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
# 3. Status & Disposition APIs (PDF Page 8 & 9)
# Endpoints called by Doocti WebPhone & Proxy Engine
# -------------------------------------------------------------
@router.get("/lead-statuses")
@router.get("/get/leadstatus")
@router.get("/leadstatus")
@router.get("/crm/get/leadstatus")
def get_lead_statuses(module: Optional[str] = None):
    statuses = [
        {"label": "New Lead", "value": "NEW", "code": "NEW", "name": "New Lead"},
        {"label": "Assigned", "value": "ASSIGNED", "code": "ASSIGNED", "name": "Assigned"},
        {"label": "Contacted", "value": "CONTACTED", "code": "CONTACTED", "name": "Contacted"},
        {"label": "Interested", "value": "INTERESTED", "code": "INTERESTED", "name": "Interested"},
        {"label": "Follow Up", "value": "FOLLOW_UP", "code": "FOLLOW_UP", "name": "Follow Up"},
        {"label": "RNR", "value": "RNR", "code": "RNR", "name": "RNR"},
        {"label": "Junk", "value": "JUNK", "code": "JUNK", "name": "Junk"},
        {"label": "Converted", "value": "CONVERTED", "code": "CONVERTED", "name": "Converted"},
        {"label": "Not Interested", "value": "NOT_INTERESTED", "code": "NOT_INTERESTED", "name": "Not Interested"},
        {"label": "Lost", "value": "LOST", "code": "LOST", "name": "Lost"}
    ]
    return {
        "status": "success",
        "statusCode": 200,
        "data": statuses,
        "statuses": statuses
    }

@router.get("/call-statuses")
@router.get("/dispostion")
@router.get("/disposition")
@router.get("/crm/dispostion")
@router.get("/crm/disposition")
def get_call_statuses(module: Optional[str] = None):
    dispos = [
        {"label": "Completed", "value": "COMPLETED", "code": "COMPLETED", "name": "Completed"},
        {"label": "Missed", "value": "MISSED", "code": "MISSED", "name": "Missed"},
        {"label": "Interested", "value": "INTERESTED", "code": "INTERESTED", "name": "Interested"},
        {"label": "Follow Up", "value": "FOLLOW_UP", "code": "FOLLOW_UP", "name": "Follow Up"},
        {"label": "Not Interested", "value": "NOT_INTERESTED", "code": "NOT_INTERESTED", "name": "Not Interested"},
        {"label": "Busy", "value": "BUSY", "code": "BUSY", "name": "Busy"},
        {"label": "No Answer", "value": "NO_ANSWER", "code": "NO_ANSWER", "name": "No Answer"},
        {"label": "Wrong Number", "value": "WRONG_NUMBER", "code": "WRONG_NUMBER", "name": "Wrong Number"},
        {"label": "Call Back Later", "value": "CALL_BACK", "code": "CALL_BACK", "name": "Call Back Later"}
    ]
    return {
        "status": "success",
        "statusCode": 200,
        "data": dispos,
        "statuses": dispos
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
    # 0. Ingest raw data from any format (JSON, Form Data, Query Params, or request.state payload)
    raw_payload = getattr(getattr(request, "state", None), "cdr_payload", None)
    raw_data: Dict[str, Any] = dict(raw_payload) if isinstance(raw_payload, dict) else {}
    content_type = request.headers.get("content-type", "").lower()
    client_ip = request.client.host if request.client else "unknown"

    if not raw_data and request.method == "POST":
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

    # Retrieve live telephony configuration & active DIDs / extension mapping
    doocti_cfg = get_doocti_config(db)
    configured_dids = doocti_cfg.get("did_numbers") or DOOCTI_DIDS
    ext_mapping = doocti_cfg.get("extension_mapping") or {}
    valid_extensions = list(ext_mapping.keys()) or ALL_EXTENSIONS

    # Optional webhook token authentication if secret_token is explicitly configured in Doocti
    expected_token = doocti_cfg.get("secret_token")
    if expected_token and isinstance(expected_token, str) and expected_token.strip():
        auth_hdr = str(request.headers.get("Authorization") or "").strip()
        is_authenticated_crm_user = False
        if auth_hdr.startswith("Bearer "):
            raw_jwt = auth_hdr[7:].strip()
            try:
                from services.auth import decode_access_token
                token_data = decode_access_token(raw_jwt)
                if token_data and token_data.username:
                    is_authenticated_crm_user = True
            except Exception:
                is_authenticated_crm_user = False

        if not is_authenticated_crm_user:
            provided_token = (
                request.headers.get("X-Doocti-Token") or 
                request.query_params.get("token") or 
                raw_data.get("token") or 
                raw_data.get("secret_token")
            )
            # Only validate if a token was provided; if standard Doocti webhook arrives without token, allow ingestion
            if provided_token and str(provided_token).strip() != str(expected_token).strip():
                logger.warning(f"⛔ [DOOCTI CDR] Webhook authentication token mismatch from IP={client_ip}")
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Doocti webhook token")

    # Sanitize payload for log auditing to prevent credential leakage
    safe_payload = sanitize_payload_for_logging(raw_data)
    logger.info(f"☎️ [DOOCTI CALL EVENT INGESTED] Method={request.method} Content-Type='{content_type}' Client={client_ip}")
    logger.info(f"   Payload: {safe_payload}")

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

    # Pre-lookup active call if call_id is an Asterisk PBX uniqueid and initial call was logged via in-app session
    if not existing_log:
        raw_cust = extract_string_val(
            raw_data.get("phone_number") or raw_data.get("customer_number") or 
            raw_data.get("destination") or raw_data.get("to_number") or 
            raw_data.get("caller") or raw_data.get("from_number")
        )
        clean_cust = clean_phone(raw_cust)
        if clean_cust and len(clean_cust) >= 6:
            existing_log = (
                db.query(CallLog)
                .filter(
                    or_(
                        CallLog.to_number.like(f"%{clean_cust}%"),
                        CallLog.from_number.like(f"%{clean_cust}%"),
                    ),
                    CallLog.call_status.in_(["RINGING", "CONNECTING", "ANSWERED", "INITIATED", "INITIATING"]),
                )
                .order_by(desc(CallLog.id))
                .first()
            )

    # 2. Agent & Station extraction (handling both scalar and dict values)
    agent_name = extract_string_val(
        raw_data.get("agent") or 
        raw_data.get("agent_name") or 
        raw_data.get("user_name") or 
        raw_data.get("user")
    )
    station_str = extract_string_val(
        raw_data.get("station") or 
        raw_data.get("agent_number") or 
        raw_data.get("extension") or 
        raw_data.get("ext")
    )
    agent_email = extract_string_val(
        raw_data.get("agent_email") or 
        raw_data.get("user_email") or 
        raw_data.get("email")
    )

    # 3. Direction & DID detection
    explicit_dir = (raw_data.get("call_direction") or raw_data.get("direction") or "").strip().upper()
    dest_val = extract_string_val(raw_data.get("destination") or raw_data.get("to_number") or raw_data.get("callee"))
    caller_val = extract_string_val(raw_data.get("caller") or raw_data.get("from_number") or raw_data.get("source"))
    did_val = extract_string_val(raw_data.get("did") or raw_data.get("did_number"))

    # Match active DID number if present
    matched_did = None
    for cand in [did_val, dest_val, caller_val, raw_data.get("phone_number")]:
        if cand and is_did_number(cand, configured_dids):
            matched_did = cand
            break

    if explicit_dir in ["INBOUND", "OUTBOUND"]:
        call_dir = explicit_dir
    elif is_did_number(dest_val, configured_dids) or is_did_number(did_val, configured_dids):
        call_dir = "INBOUND"
    elif is_did_number(caller_val, configured_dids) or (station_str and is_extension_number(caller_val, valid_extensions)):
        call_dir = "OUTBOUND"
    elif existing_log and existing_log.call_direction:
        call_dir = existing_log.call_direction
    else:
        call_dir = "OUTBOUND"

    # Identify if caller or destination was an extension
    if not station_str:
        if is_extension_number(caller_val, valid_extensions):
            station_str = caller_val
        elif is_extension_number(dest_val, valid_extensions):
            station_str = dest_val

    clean_station = clean_phone(station_str)

    # 4. Identify target customer phone number
    if call_dir == "INBOUND":
        customer_phone = extract_string_val(
            raw_data.get("customer_number") or 
            raw_data.get("phone_number") or 
            raw_data.get("from_number") or 
            raw_data.get("caller") or 
            (existing_log.from_number if existing_log else "")
        )
    else:
        customer_phone = extract_string_val(
            raw_data.get("phone_number") or 
            raw_data.get("customer_number") or 
            raw_data.get("destination") or 
            raw_data.get("to_number") or 
            raw_data.get("callee") or 
            raw_data.get("phone") or 
            raw_data.get("number") or 
            (existing_log.to_number if existing_log else "")
        )
    clean_target = clean_phone(customer_phone)

    # 4b. REJECT GHOST CALLS: Prevent self-extension loop, empty phone numbers, or invalid internal loops
    # ONLY reject if it is a NEW call (no existing CallLog matches this uniqueid/call_id)
    if not existing_log:
        if (
            not clean_target or 
            len(clean_target) < 6 or 
            (clean_station and clean_target == clean_station) or 
            is_extension_number(clean_target, valid_extensions)
        ):
            logger.warning(f"⚠️ [DOOCTI CDR] Ignored ghost/invalid call log payload: clean_target='{clean_target}', station='{station_str}', dir={call_dir}")
            return {
                "status": "ignored",
                "message": "Ghost call rejected: Customer number is missing or equals agent extension",
                "clean_target": clean_target
            }

    # 5. Fallback call_id generation if none provided
    if not call_id:
        st_tag = station_str or "doocti"
        ph_tag = clean_target or "unknown"
        call_id = f"doocti_{st_tag}_{ph_tag}_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"

    # 6. Duration parsing (seconds)
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

    # 7. Timestamp parsing (Indian Standard Time Asia/Kolkata)
    started_at = parse_doocti_time(raw_data.get("start_time") or raw_data.get("started_at")) or (existing_log.started_at if existing_log else None)
    answered_at = parse_doocti_time(raw_data.get("answer_time") or raw_data.get("answered_at")) or (existing_log.answered_at if existing_log else None)
    ended_at = parse_doocti_time(raw_data.get("end_time") or raw_data.get("ended_at")) or (existing_log.ended_at if existing_log else None)
    now_ist = get_ist_now()
    if not ended_at:
        ended_at = now_ist
    if not started_at:
        started_at = ended_at - datetime.timedelta(seconds=dur_sec) if dur_sec > 0 else ended_at

    # 8. Recording path / URL
    rec_url = str(
        raw_data.get("recording_path") or 
        raw_data.get("recording_url") or 
        raw_data.get("recording") or 
        ""
    ).strip() or None

    # 8b. Answered / Connected verification:
    # A call is definitively answered if it has positive duration, a valid recording, or answered_at
    # Note: Dummy recording URLs with duration 0 on failed/missed calls do NOT count as answered!
    has_positive_duration = dur_sec > 0 or bool(existing_log and existing_log.duration_seconds and existing_log.duration_seconds > 0)
    has_recording = bool((rec_url and dur_sec > 0) or (existing_log and existing_log.recording_url and existing_log.duration_seconds and existing_log.duration_seconds > 0))
    was_previously_answered = bool(existing_log and (existing_log.answered_at or ((existing_log.call_status or '').upper() in ["ANSWERED", "CONNECTED"] and existing_log.duration_seconds and existing_log.duration_seconds > 0)))

    # 9. Call Status normalization
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
        # Protection: If the call has real audio recording, positive talk duration, or was confirmed answered,
        # it CANNOT be classified as NO_ANSWER!
        if has_positive_duration or was_previously_answered:
            status_str = "COMPLETED"
        else:
            status_str = "MISSED" if call_dir == "INBOUND" else "NO_ANSWER"
            dur_sec = 0
            answered_at = None
    elif any(k in raw_upper for k in ["MISSED", "UNANSWERED", "DECLINED", "REJECTED", "ABANDON", "ABANDONED", "NOANSWER"]):
        if has_positive_duration or was_previously_answered:
            status_str = "COMPLETED"
        else:
            status_str = "MISSED"
            dur_sec = 0
            answered_at = None
    elif any(k in raw_upper for k in ["BUSY", "ENGAGED"]):
        if has_positive_duration or was_previously_answered:
            status_str = "COMPLETED"
        else:
            status_str = "BUSY"
            dur_sec = 0
            answered_at = None
    elif any(k in raw_upper for k in ["FAIL", "ERROR"]):
        if has_positive_duration or was_previously_answered:
            status_str = "COMPLETED"
        else:
            # An incoming call that was not answered or got disconnected is a MISSED call, not FAILED!
            if call_dir == "INBOUND" and dur_sec == 0 and not answered_at:
                status_str = "MISSED"
            else:
                status_str = "FAILED"
            dur_sec = 0
            answered_at = None
    elif any(k in raw_upper for k in ["SUCCESS", "ANSWERED", "CONNECTED"]):
        if not answered_at:
            answered_at = started_at or now_ist
        if ended_at and answered_at and ended_at >= answered_at:
            dur_sec = max(0, int((ended_at - answered_at).total_seconds()))
        # If the call has already ended or has duration, save final status as COMPLETED
        if ended_at or dur_sec > 0 or has_explicit_duration or rec_url:
            status_str = "COMPLETED"
        else:
            status_str = "ANSWERED"  # Internal active in-call state while talking
    elif any(k in raw_upper for k in ["COMPLETED", "COMPLETE", "HANGUP", "DISCONNECTED", "ENDED"]):
        # Disconnect / Complete event:
        # If provider explicitly reports COMPLETE / COMPLETED, it is a completed call!
        if raw_upper in ["COMPLETE", "COMPLETED"]:
            status_str = "COMPLETED"
        elif call_dir == "INBOUND" and dur_sec == 0 and not answered_at and not was_previously_answered:
            # If inbound call has 0 duration and was not answered, it is a MISSED call!
            status_str = "MISSED"
            dur_sec = 0
            answered_at = None
        elif dur_sec > 0 or has_positive_duration:
            status_str = "COMPLETED"
        elif answered_at and ended_at and ended_at >= answered_at:
            dur_sec = max(0, int((ended_at - answered_at).total_seconds()))
            status_str = "COMPLETED" if dur_sec > 0 else ("MISSED" if call_dir == "INBOUND" else "NO_ANSWER")
        elif was_previously_answered:
            status_str = "COMPLETED"
        else:
            status_str = "MISSED" if call_dir == "INBOUND" else "NO_ANSWER"
            dur_sec = 0
            answered_at = None
    else:
        status_str = raw_upper or ("RINGING" if call_dir == "INBOUND" and dur_sec == 0 else "COMPLETED")

    # 9. Compile Notes early (to preserve original provider status & allow lead categorization)
    notes_parts = []
    if agent_name:
        notes_parts.append(f"Agent: {agent_name}")
    if station_str:
        notes_parts.append(f"Station: {station_str}")
    if matched_did:
        notes_parts.append(f"DID: {matched_did}")
    if raw_status:
        notes_parts.append(f"DooCTI Status: {raw_status}")
    if raw_data.get("disposition"):
        notes_parts.append(f"Disposition: {raw_data['disposition']}")
    if raw_data.get("call_purpose"):
        notes_parts.append(f"Purpose: {raw_data['call_purpose']}")
    if raw_data.get("notes"):
        notes_parts.append(f"Notes: {raw_data['notes']}")
    combined_notes = " | ".join(notes_parts) if notes_parts else "DooCTI Call completed."

    # 10. Resolve Employee (Agent) - Determine calling/answering agent early
    explicit_emp_id = raw_data.get("employee_id")
    resolved_emp_id = resolve_employee_for_call(
        db=db,
        station=station_str,
        agent_name=agent_name,
        agent_email=agent_email,
        explicit_emp_id=explicit_emp_id,
        extension_map=ext_mapping
    )

    # 11. Resolve or Auto-create Lead
    resolved_lead_id = None
    entity_id_val = raw_data.get("entity_id") or raw_data.get("lead_id")
    if entity_id_val and str(entity_id_val).isdigit() and int(entity_id_val) > 0:
        # Verify entity_id actually exists in Lead table
        lead_candidate = db.query(Lead).filter(Lead.id == int(entity_id_val)).first()
        if lead_candidate:
            resolved_lead_id = lead_candidate.id

    # If not resolved by explicit entity_id, search by normalized phone number
    if not resolved_lead_id and clean_target:
        matched = find_existing_lead_by_phone(db, customer_phone or clean_target)
        if matched:
            resolved_lead_id = matched.id
        else:
            # Check Customer table
            matched_cust = find_existing_customer_by_phone(db, customer_phone or clean_target)
            if matched_cust and matched_cust.converted_from_lead:
                resolved_lead_id = matched_cust.converted_from_lead
            elif len(clean_target) >= 10:
                raw_display = customer_phone or clean_target
                if call_dir == "OUTBOUND":
                    # OUTBOUND CALL AUTO-CREATION:
                    # When an agent dials a new phone number that doesn't exist in CRM,
                    # automatically create a new lead and assign to the logged-in/calling agent.
                    calling_agent_str = agent_name or station_str or f"Agent #{resolved_emp_id}" if resolved_emp_id else "Agent"
                    from services.product_categorization_service import ProductCategorizationService
                    init_cat = ProductCategorizationService.detect_category_from_text(combined_notes or "")
                    new_lead = Lead(
                        name=f"Call Lead ({raw_display})",
                        phone=raw_display,
                        source="DOOCTI",
                        status="NEW LEAD",
                        priority="MEDIUM",
                        product_category=init_cat,
                        product_category_confirmed=False,
                        assigned_to=resolved_emp_id,
                        assigned_by=resolved_emp_id,
                        assigned_at=now_ist if resolved_emp_id else None,
                        requirement_notes=f"Auto-created from outbound DooCTI call by {calling_agent_str}."
                    )
                    db.add(new_lead)
                    db.commit()
                    db.refresh(new_lead)
                    resolved_lead_id = new_lead.id

                    # Record LeadAssignment audit log
                    if resolved_emp_id:
                        assignment_record = LeadAssignment(
                            lead_id=new_lead.id,
                            assigned_to=resolved_emp_id,
                            assigned_by=resolved_emp_id,
                            assigned_at=now_ist,
                            assignment_method="OUTBOUND_CALL",
                            notes=f"Auto-assigned to calling agent ({calling_agent_str}) on outbound call"
                        )
                        db.add(assignment_record)
                        db.commit()

                    logger.info(
                        f"✨ [DOOCTI CDR] Auto-created new Lead ID={resolved_lead_id} for outbound call to {raw_display}. "
                        f"Assigned to Employee ID={resolved_emp_id}."
                    )
                else:
                    # INBOUND CALL: Auto-create lead so caller is tracked in CRM
                    from services.product_categorization_service import ProductCategorizationService
                    init_cat = ProductCategorizationService.detect_category_from_text(combined_notes or "")
                    new_lead = Lead(
                        name=f"Call Lead ({raw_display})",
                        phone=raw_display,
                        source="DOOCTI",
                        status="CONTACTED" if status_str in ["ANSWERED", "COMPLETED"] else "NEW LEAD",
                        priority="MEDIUM",
                        product_category=init_cat,
                        product_category_confirmed=False,
                        assigned_to=resolved_emp_id,
                        assigned_by=resolved_emp_id if resolved_emp_id else None,
                        assigned_at=now_ist if resolved_emp_id else None,
                        requirement_notes=f"Auto-created from DooCTI Inbound Call. Station: {station_str or 'Unassigned'}, Agent: {agent_name or 'DooCTI'}"
                    )
                    db.add(new_lead)
                    db.commit()
                    db.refresh(new_lead)
                    resolved_lead_id = new_lead.id
                    logger.info(f"✨ [DOOCTI CDR] Auto-created new Lead ID={resolved_lead_id} for incoming caller: {raw_display}")

    # If employee still not resolved, check if lead is assigned to an employee
    if not resolved_emp_id and resolved_lead_id:
        target_lead = db.query(Lead).filter(Lead.id == resolved_lead_id).first()
        if target_lead and target_lead.assigned_to:
            resolved_emp_id = target_lead.assigned_to

    if not resolved_emp_id:
        logger.warning(
            f"⚠️ [DOOCTI CDR] Agent identity could not be resolved from payload "
            f"(station='{station_str}', agent='{agent_name}', email='{agent_email}', explicit_emp_id='{explicit_emp_id}'). "
            f"Leaving unassigned instead of assigning to Admin."
        )

    # Direction
    call_dir = (raw_data.get("call_direction") or raw_data.get("direction") or call_dir or "OUTBOUND").upper()

    # 12. Check if CallLog already exists for this call_id (handling idempotency / updates)
    if not existing_log and call_id:
        existing_log = db.query(CallLog).filter(CallLog.provider_call_id == call_id).first()

    # Cross-provider & PBX duplicate detection:
    # 1. Same phone + currently active call (RINGING, CONNECTING, ANSWERED, INITIATED) within past 4 hours.
    #    When an agent answers and speaks for >4 minutes (e.g. 5, 10, 30 mins), the initial record
    #    might have been created with a synthetic ID (e.g. doocti_1282_phone_timestamp) while the CDR
    #    webhook arrives with the PBX uniqueid (e.g. 1792669919.123839191) at call completion.
    #    Matching active calls by customer number connects the CDR to the active session regardless of duration.
    if not existing_log and clean_target:
        four_hours_ago = (started_at or now_ist) - datetime.timedelta(hours=4)
        active_match = (
            db.query(CallLog)
            .filter(
                or_(
                    CallLog.to_number.like(f"%{clean_target}%"),
                    CallLog.from_number.like(f"%{clean_target}%"),
                ),
                CallLog.call_status.in_(["RINGING", "CONNECTING", "ANSWERED", "INITIATED", "INITIATING"]),
                CallLog.created_at >= four_hours_ago,
            )
            .order_by(desc(CallLog.id))
            .first()
        )
        if active_match:
            existing_log = active_match
            logger.info(
                f"🔁 [DOOCTI CDR] Matched active call in progress: CallLog ID={existing_log.id} "
                f"(provider={existing_log.provider}, call_id={existing_log.provider_call_id}) "
                f"for phone={clean_target}. Updating with final CDR outcome."
            )

    # 2. Same phone + time window matching:
    #    Accommodates calls of any duration (up to 4 hours) by checking both started_at and created_at.
    if not existing_log and clean_target and started_at:
        # Window spans from started_at minus 10 minutes to started_at plus max(dur_sec + 300, 600) seconds
        margin_sec = max(dur_sec + 600, 1800)
        window_start = started_at - datetime.timedelta(minutes=10)
        window_end = started_at + datetime.timedelta(seconds=margin_sec)
        existing_log = (
            db.query(CallLog)
            .filter(
                or_(
                    CallLog.to_number.like(f"%{clean_target}%"),
                    CallLog.from_number.like(f"%{clean_target}%"),
                ),
                or_(
                    and_(CallLog.started_at >= window_start, CallLog.started_at <= window_end),
                    and_(CallLog.created_at >= window_start, CallLog.created_at <= window_end),
                ),
                CallLog.call_direction == call_dir,
            )
            .order_by(desc(CallLog.created_at))
            .first()
        )
        if existing_log:
            logger.info(
                f"🔁 [DOOCTI CDR] Duplicate/prior session detected: "
                f"existing CallLog ID={existing_log.id} (provider={existing_log.provider}, "
                f"call_id={existing_log.provider_call_id}) matches phone={clean_target}. "
                f"Merging instead of creating duplicate."
            )

    if existing_log:
        curr_status = (existing_log.call_status or "").upper()
        # State machine protection:
        # 1. If payload didn't explicitly specify status, preserve existing status
        # 2. Do not revert an ANSWERED/CONNECTED/COMPLETED call to RINGING/CONNECTING
        # 3. Do not revert a call that was answered, has positive duration, or has a recording to NO_ANSWER/MISSED/BUSY/FAILED
        # 4. If an incoming call was RINGING and ends without answer / duration 0, mark as MISSED
        has_prior_answer = (
            (curr_status in ["ANSWERED", "CONNECTED", "COMPLETED"] and bool(existing_log.duration_seconds and existing_log.duration_seconds > 0)) or 
            bool(existing_log.answered_at) or 
            bool(existing_log.duration_seconds and existing_log.duration_seconds > 0)
        )

        if not has_explicit_status:
            logger.info(f"Preserving existing status '{curr_status}' (no explicit status in payload) for CallLog ID={existing_log.id}")
        elif curr_status in ["ANSWERED", "CONNECTED"] and status_str in ["RINGING", "CONNECTING"]:
            logger.info(f"Preserving active status '{curr_status}', ignoring stale '{status_str}' for CallLog ID={existing_log.id}")
        elif has_prior_answer and status_str in ["NO_ANSWER", "NO ANSWER", "MISSED", "BUSY", "FAILED"]:
            logger.info(f"🛡️ Preserving answered/completed state for CallLog ID={existing_log.id} (status='{curr_status}', dur={existing_log.duration_seconds}s), ignoring late '{status_str}'")
            if curr_status in ["ANSWERED", "CONNECTED"]:
                existing_log.call_status = "COMPLETED"
        elif curr_status == "COMPLETED" and status_str in ["RINGING", "CONNECTING", "ANSWERED"]:
            logger.info(f"Preserving COMPLETED status, ignoring subsequent '{status_str}' for CallLog ID={existing_log.id}")
        elif curr_status == "RINGING" and status_str in ["FAILED", "NO_ANSWER", "MISSED", "COMPLETED", "HANGUP", "DISCONNECTED", "ENDED"]:
            # Ringing inbound call that terminated without answer
            if not has_prior_answer and dur_sec == 0:
                existing_log.call_status = "MISSED" if (existing_log.call_direction or call_dir) == "INBOUND" else "NO_ANSWER"
            else:
                existing_log.call_status = status_str
        else:
            existing_log.call_status = status_str

        # Duration preservation: never overwrite positive duration with 0
        if dur_sec > 0:
            existing_log.duration_seconds = dur_sec
        elif not existing_log.duration_seconds:
            existing_log.duration_seconds = 0

        # If call was completed or has positive talk duration, status MUST be COMPLETED
        if (existing_log.duration_seconds and existing_log.duration_seconds > 0) or has_prior_answer:
            if existing_log.call_status in ["NO_ANSWER", "NO ANSWER", "MISSED", "BUSY", "FAILED", "RINGING", "CONNECTING", "ANSWERED", "CONNECTED"]:
                existing_log.call_status = "COMPLETED"

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
        elif has_explicit_status and status_str in ["NO_ANSWER", "MISSED", "BUSY", "FAILED"] and not existing_log.answered_at and not has_prior_answer:
            existing_log.answered_at = None
            existing_log.duration_seconds = 0

        if has_explicit_status and (status_str in ["COMPLETED", "MISSED", "NO_ANSWER", "BUSY", "FAILED"] or has_prior_answer):
            existing_log.ended_at = ended_at or now_ist

        if combined_notes and combined_notes not in (existing_log.notes or ""):
            existing_log.notes = f"{existing_log.notes or ''}\n{combined_notes}".strip()
        if resolved_lead_id and not existing_log.lead_id:
            existing_log.lead_id = resolved_lead_id
        if resolved_emp_id:
            # Update employee_id if previously unset, or if incoming event carries verified agent extension/email
            if not existing_log.employee_id or (station_str or agent_email or explicit_emp_id):
                existing_log.employee_id = resolved_emp_id
        db.commit()
        db.refresh(existing_log)
        call_entry = existing_log
        logger.info(f"✅ [DOOCTI CDR] Updated CallLog ID={call_entry.id} uniqueid='{call_id}' Status='{existing_log.call_status}' Duration={existing_log.duration_seconds}s EmpID={resolved_emp_id}")
    else:
        if call_dir == "INBOUND":
            from_num = customer_phone or clean_target
            to_num = matched_did or station_str or (configured_dids[0] if configured_dids else "")
        else:
            from_num = matched_did or station_str or (configured_dids[0] if configured_dids else "")
            to_num = customer_phone or clean_target

        try:
            # Sync product_category from Lead or payload if present
            lead_cat = None
            if resolved_lead_id:
                ld = db.query(Lead).filter(Lead.id == resolved_lead_id).first()
                if ld:
                    lead_cat = ld.product_category
            if not lead_cat:
                from services.product_categorization_service import ProductCategorizationService
                lead_cat = ProductCategorizationService.detect_category_from_text(combined_notes or "")

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
                notes=combined_notes,
                product_category=lead_cat
            )
            db.add(call_entry)
            db.commit()
            db.refresh(call_entry)
            logger.info(f"✅ [DOOCTI CDR] Created CallLog ID={call_entry.id} uniqueid='{call_id}' Status='{status_str}' Duration={dur_sec}s EmpID={resolved_emp_id}")
        except Exception as insert_err:
            db.rollback()
            # Handle race condition where provider_call_id was concurrently inserted
            existing_log = db.query(CallLog).filter(CallLog.provider_call_id == call_id).first()
            if existing_log:
                logger.info(f"🔁 [DOOCTI CDR] Handled concurrent insertion race condition for CallLog uniqueid='{call_id}'. Updating ID={existing_log.id}.")
                if has_explicit_status:
                    existing_log.call_status = status_str
                if dur_sec > 0:
                    existing_log.duration_seconds = dur_sec
                if rec_url and not existing_log.recording_url:
                    existing_log.recording_url = rec_url
                if resolved_lead_id and not existing_log.lead_id:
                    existing_log.lead_id = resolved_lead_id
                if resolved_emp_id and not existing_log.employee_id:
                    existing_log.employee_id = resolved_emp_id
                db.commit()
                db.refresh(existing_log)
                call_entry = existing_log
            else:
                logger.error(f"❌ [DOOCTI CDR] Failed to insert CallLog for uniqueid='{call_id}': {insert_err}")
                raise insert_err

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

    lead_product_cat = None
    if resolved_lead_id:
        ld = db.query(Lead).filter(Lead.id == resolved_lead_id).first()
        if ld:
            lead_product_cat = ld.product_category

    return {
        "status": "success",
        "message": "Call log processed and saved successfully",
        "uniqueid": call_id,
        "call_log_id": call_entry.id,
        "employee_id": resolved_emp_id,
        "lead_id": resolved_lead_id,
        "product_category": call_entry.product_category or lead_product_cat or "UNCLASSIFIED",
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

    # 1. Resolve employee ID
    resolved_emp_id = None
    if payload.employee_id and str(payload.employee_id).isdigit():
        emp = db.query(Employee).filter(Employee.id == int(payload.employee_id)).first()
        if emp:
            resolved_emp_id = emp.id
    if not resolved_emp_id and payload.agent_email:
        clean_email = payload.agent_email.strip().lower()
        emp = db.query(Employee).filter(Employee.email.ilike(clean_email)).first()
        if emp:
            resolved_emp_id = emp.id
    if not resolved_emp_id and lead.assigned_to:
        resolved_emp_id = lead.assigned_to

    norm_status = (payload.status or "").strip().upper().replace(" ", "_")
    
    # 2. Update Lead status
    if payload.status:
        lead.status = payload.status.upper()
    
    # 3. Update requirement notes
    if payload.call_notes:
        existing = lead.requirement_notes or ""
        lead.requirement_notes = f"{existing}\n[Doocti Call Notes]: {payload.call_notes}".strip()

    # 4. Save product category
    if payload.product_category:
        from services.product_categorization_service import ProductCategorizationService
        ProductCategorizationService.save_lead_category(
            db=db,
            lead_id=lead.id,
            category=payload.product_category,
            is_manual_confirmation=True,
            call_id=payload.call_id
        )

    # 5. Update or link CallLog
    call_log = None
    if payload.call_id:
        c_id = str(payload.call_id).strip()
        call_log = db.query(CallLog).filter(
            or_(CallLog.provider_call_id == c_id, CallLog.id == int(c_id) if c_id.isdigit() else False)
        ).first()

    if not call_log:
        # Check for the latest call log belonging to this lead
        call_log = db.query(CallLog).filter(CallLog.lead_id == lead.id).order_by(desc(CallLog.id)).first()

    if call_log:
        if payload.call_notes:
            call_log.notes = payload.call_notes
        if payload.product_category:
            call_log.product_category = payload.product_category
        if resolved_emp_id and not call_log.employee_id:
            call_log.employee_id = resolved_emp_id
        if not call_log.lead_id:
            call_log.lead_id = lead.id
        if norm_status in ["COMPLETED", "CONTACTED", "INTERESTED", "FOLLOW_UP", "FOLLOW-UP", "RNR", "NOT_INTERESTED", "JUNK"]:
            call_log.call_status = "COMPLETED"
    elif payload.call_notes or payload.call_id:
        # Create a CallLog so it appears in Lead call history
        new_call_id = payload.call_id or f"manual-disp-{int(datetime.utcnow().timestamp())}"
        call_log = CallLog(
            lead_id=lead.id,
            employee_id=resolved_emp_id,
            provider="DOOCTI",
            provider_call_id=new_call_id,
            from_number="TELEPHONY",
            to_number=lead.phone or "UNKNOWN",
            call_status="COMPLETED",
            call_direction="OUTBOUND",
            duration_seconds=0,
            notes=payload.call_notes,
            product_category=payload.product_category or getattr(lead, 'product_category', None) or "UNCLASSIFIED",
            created_at=get_ist_now()
        )
        db.add(call_log)

    # 6. Follow-up handling
    is_followup_status = norm_status in ["FOLLOW_UP", "FOLLOW-UP", "FOLLOWUP", "CALL_BACK"]
    if is_followup_status:
        # Target followup date (payload or fallback to tomorrow)
        f_date = payload.followup_date or (datetime.utcnow() + datetime.timedelta(days=1)).date()
        f_time = payload.followup_time or "10:00 AM"
        f_priority = (payload.followup_priority or "MEDIUM").upper()

        lead.followup_date = f_date
        lead.followup_time = f_time

        target_emp = resolved_emp_id or lead.assigned_to

        # Look for existing pending followup for this lead to avoid duplicates
        existing_fu = db.query(Followup).filter(
            Followup.lead_id == lead.id,
            Followup.status == "Pending"
        ).order_by(desc(Followup.id)).first()

        if existing_fu:
            existing_fu.followup_date = f_date
            existing_fu.followup_time = f_time
            existing_fu.priority = f_priority
            if payload.call_notes:
                existing_fu.notes = payload.call_notes
            if target_emp:
                existing_fu.assigned_to = target_emp
        else:
            if not target_emp:
                # Default to first available employee if none assigned
                first_emp = db.query(Employee).first()
                target_emp = first_emp.id if first_emp else None

            if target_emp:
                new_fu = Followup(
                    lead_id=lead.id,
                    assigned_to=target_emp,
                    followup_date=f_date,
                    followup_time=f_time,
                    notes=payload.call_notes or f"Follow-up scheduled via call disposition: {lead.status}",
                    priority=f_priority,
                    status="Pending",
                    created_by=resolved_emp_id or target_emp
                )
                db.add(new_fu)

    # 7. Log LeadActivity
    cat_str = f" | Product Category: {lead.product_category}" if getattr(lead, 'product_category', None) else ""
    act_type = "FOLLOW_UP_CREATED" if is_followup_status else "CALL"
    activity = LeadActivity(
        lead_id=lead.id,
        employee_id=resolved_emp_id,
        performed_by=resolved_emp_id,
        activity_type=act_type,
        related_entity_type="CALL",
        related_entity_id=call_log.id if call_log else None,
        description=f"Call disposition recorded: {lead.status}{cat_str}. Notes: {payload.call_notes or 'None'}"
    )
    db.add(activity)

    db.commit()

    return {
        "status": "success",
        "message": "Lead disposition updated successfully",
        "lead_id": lead.id,
        "current_status": lead.status,
        "product_category": lead.product_category,
        "call_log_id": call_log.id if call_log else None,
        "followup_scheduled": is_followup_status
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
    has_prior_answer = (
        bool(call.answered_at) or 
        bool(call.duration_seconds and call.duration_seconds > 0) or 
        (call.call_status or "").upper() in ["ANSWERED", "CONNECTED", "COMPLETED"] or
        bool(call.recording_url)
    )

    if action == "reject" and not has_prior_answer:
        new_status = "MISSED" if (call.call_direction or "").upper() == "INBOUND" else "NO_ANSWER"
    elif is_ringing and not has_prior_answer:
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

# -------------------------------------------------------------
# 7. Integration Telephony Configuration APIs
# -------------------------------------------------------------
class DooctiConfigUpdatePayload(BaseModel):
    model_config = {"extra": "ignore"}
    did_numbers: Optional[List[str]] = None
    admin_extension: Optional[str] = None
    agent_extensions: Optional[List[str]] = None
    extension_mapping: Optional[Dict[str, Any]] = None
    api_url: Optional[str] = None
    account_id: Optional[str] = None
    recording_base_url: Optional[str] = None
    secret_token: Optional[str] = None
    webhook_url: Optional[str] = None

@router.get("/config")
def get_doocti_telephony_config(db: Session = Depends(get_db)):
    """Returns active Doocti telephony configuration including DIDs and extension mappings."""
    cfg = get_doocti_config(db)
    # Mask secret token in response
    if cfg.get("secret_token"):
        cfg["secret_token"] = "***REDACTED***"
    return {
        "status": "success",
        **cfg
    }

@router.put("/config")
def update_doocti_telephony_config(
    payload: DooctiConfigUpdatePayload,
    db: Session = Depends(get_db)
):
    """Updates Doocti telephony configuration in IntegrationConfig."""
    cfg_row = db.query(IntegrationConfig).filter(IntegrationConfig.integration_type == "IVR").first()
    if not cfg_row:
        cfg_row = IntegrationConfig(
            integration_type="IVR",
            provider="DOOCTI",
            name="Doocti Telephony",
            is_active=True,
            status="ACTIVE",
            webhook_url="https://www.wapluscrm.in/api/doocti/call-log",
            config_data=json.dumps({})
        )
        db.add(cfg_row)
        db.commit()
        db.refresh(cfg_row)

    data = {}
    if cfg_row.config_data:
        try:
            data = json.loads(cfg_row.config_data) if isinstance(cfg_row.config_data, str) else dict(cfg_row.config_data)
        except Exception:
            data = {}

    if payload.did_numbers is not None:
        data["did_numbers"] = [str(d).strip() for d in payload.did_numbers if str(d).strip()]
    if payload.admin_extension is not None:
        data["admin_extension"] = str(payload.admin_extension).strip()
    if payload.agent_extensions is not None:
        data["agent_extensions"] = [str(e).strip() for e in payload.agent_extensions if str(e).strip()]
    if payload.extension_mapping is not None:
        data["extension_mapping"] = payload.extension_mapping
    if payload.api_url is not None:
        data["api_url"] = payload.api_url
    if payload.account_id is not None:
        data["account_id"] = payload.account_id
    if payload.recording_base_url is not None:
        data["recording_base_url"] = str(payload.recording_base_url).strip().rstrip('/')
    if payload.secret_token is not None:
        data["secret_token"] = payload.secret_token
    if payload.webhook_url is not None:
        data["webhook_url"] = payload.webhook_url
        cfg_row.webhook_url = payload.webhook_url

    cfg_row.provider = "DOOCTI"
    cfg_row.config_data = json.dumps(data)
    cfg_row.updated_at = get_ist_now()
    db.commit()

    return {
        "status": "success",
        "message": "Doocti telephony configuration updated successfully",
        "config": get_doocti_config(db)
    }

# -------------------------------------------------------------
# 8. Agent Extension & Call Initiation for Mobile / Web Clients
# -------------------------------------------------------------
@router.get("/agent-extension")
@router.get("/my-agent-extension")
def get_my_doocti_agent_extension(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Validates and retrieves the current authenticated user's assigned DooCTI PBX extension,
    outbound CLI (DID), and telephony session configuration for mobile and web dialers.
    """
    cfg = get_doocti_config(db)
    ext_mapping = cfg.get("extension_mapping") or {}
    dids = cfg.get("did_numbers") or []
    primary_did = dids[0] if dids else None

    emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
    emp_id = emp.id if emp else None
    emp_name = emp.name if emp else (current_user.name or current_user.username)

    # Find extension mapped to this employee strictly from database configuration
    found_ext = None
    assigned_did = None
    is_active = True
    if emp_id:
        for ext, data in ext_mapping.items():
            if isinstance(data, dict) and data.get("employee_id") == emp_id:
                found_ext = str(ext).strip()
                assigned_did = data.get("did_number")
                if data.get("is_active") is False:
                    is_active = False
                break

    # If admin and still no extension, check if an admin extension is configured
    if not found_ext and (current_user.role == "ADMIN" or getattr(current_user, "is_admin", False)):
        found_ext = cfg.get("admin_extension")
        if found_ext and found_ext in ext_mapping and isinstance(ext_mapping[found_ext], dict):
            assigned_did = ext_mapping[found_ext].get("did_number")

    # If ext found in mapping, recheck its assigned did and active status
    if found_ext and found_ext in ext_mapping and isinstance(ext_mapping[found_ext], dict):
        assigned_did = ext_mapping[found_ext].get("did_number") or assigned_did
        if ext_mapping[found_ext].get("is_active") is False:
            is_active = False

    # Dynamic fallback to primary DID if not individually assigned on extension
    if found_ext and not assigned_did and dids:
        assigned_did = dids[0]

    if found_ext and is_active and assigned_did:
        return {
            "status": "success",
            "has_extension": True,
            "has_valid_did": True,
            "is_active": True,
            "extension": found_ext,
            "agent_name": emp_name,
            "employee_id": emp_id,
            "cli_number": assigned_did,
            "assigned_did": assigned_did,
            "did_numbers": dids,
            "tenant_id": cfg.get("account_id", ""),
            "webphone_url": cfg.get("api_url", ""),
            "provider": "DOOCTI"
        }
    elif found_ext and not is_active:
        return {
            "status": "warning",
            "has_extension": True,
            "has_valid_did": False,
            "is_active": False,
            "extension": found_ext,
            "agent_name": emp_name,
            "employee_id": emp_id,
            "cli_number": None,
            "assigned_did": None,
            "did_numbers": dids,
            "tenant_id": cfg.get("account_id", ""),
            "webphone_url": cfg.get("api_url", ""),
            "provider": "DOOCTI",
            "message": f"WebRTC extension {found_ext} is currently deactivated. Please contact Administrator."
        }
    elif found_ext and not assigned_did:
        return {
            "status": "warning",
            "has_extension": True,
            "has_valid_did": False,
            "is_active": True,
            "extension": found_ext,
            "agent_name": emp_name,
            "employee_id": emp_id,
            "cli_number": None,
            "assigned_did": None,
            "did_numbers": dids,
            "tenant_id": cfg.get("account_id", ""),
            "webphone_url": cfg.get("api_url", ""),
            "provider": "DOOCTI",
            "message": f"Extension {found_ext} does not have an outbound DID assigned. Please assign an outbound DID in Admin Settings."
        }
    else:
        return {
            "status": "warning",
            "has_extension": False,
            "has_valid_did": False,
            "is_active": False,
            "extension": None,
            "agent_name": emp_name,
            "employee_id": emp_id,
            "cli_number": None,
            "assigned_did": None,
            "did_numbers": dids,
            "tenant_id": cfg.get("account_id", ""),
            "webphone_url": cfg.get("api_url", ""),
            "provider": "DOOCTI",
            "message": f"User '{emp_name}' does not have an assigned DooCTI PBX extension. Please configure in Settings → Integrations."
        }

@router.post("/call", status_code=status.HTTP_201_CREATED)
def initiate_doocti_call(
    body: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Initiates an outbound phone call via DooCTI from mobile app or web CRM.
    Routes through DooCTI telephony provider, creates call log, and synchronizes status.
    """
    from integrations.ivr.service import IVRService, IVRNotConfiguredException
    from routers.ivr import build_call_log_response

    emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
    emp_id = emp.id if emp else None
    emp_phone = emp.phone if (emp and emp.phone) else None

    cust_phone = body.get("customer_phone") or body.get("phone") or body.get("phone_number")
    lead_id = body.get("lead_id")
    notes = body.get("notes")

    try:
        call_log = IVRService.initiate_call(
            db=db,
            lead_id=lead_id,
            current_employee_id=emp_id,
            customer_phone=cust_phone,
            employee_phone=emp_phone,
            notes=notes
        )
        return build_call_log_response(call_log, db)
    except IVRNotConfiguredException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to initiate DooCTI call: {str(e)}")


