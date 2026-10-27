import logging
import uuid
import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from models.call_log import CallLog
from models.lead import Lead
from models.customer import Customer
from models.employee import Employee
from models.activity import LeadActivity
from utils.phone import normalize_phone, find_existing_lead_by_phone, find_existing_customer_by_phone
from .service import (
    IVRService, 
    CALL_STATUS_COMPLETED, 
    CALL_STATUS_ANSWERED, 
    CALL_STATUS_FAILED, 
    CALL_STATUS_BUSY, 
    CALL_STATUS_MISSED,
    CALL_STATUS_RINGING
)

logger = logging.getLogger("ivr_webhook")

def _clean_phone_digits(val: Any) -> str:
    """Extract numeric digits from phone string."""
    return "".join(ch for ch in str(val or "") if ch.isdigit())

def _is_placeholder(val: Any) -> bool:
    """Check if value is a template placeholder like %uniqueid%, %from%, $uuid, $call_id."""
    s = str(val or "").strip()
    if s.startswith("%") and s.endswith("%"):
        return True
    if s.startswith("$") and len(s) > 1 and s[1:].replace("_", "").isalnum():
        return True
    return False

def handle_incoming_ivr_webhook(db: Session, payload: Dict[str, Any], headers: Dict[str, Any]) -> Dict[str, Any]:
    """
    Complete Incoming-Call Webhook Processor for CloudShope, Twilio, Exotel, and generic IVR providers.
    
    Logging Pipeline:
    Provider -> Cloudflare -> Nginx -> FastAPI -> Database -> CRM
    """
    req_id = f"REQ_{uuid.uuid4().hex[:8].upper()}"
    now_iso = datetime.datetime.utcnow().isoformat() + "Z"
    
    # -------------------------------------------------------------
    # STAGE 1: LOGGING INCOMING REQUEST (Provider -> Cloudflare -> Nginx -> FastAPI)
    # -------------------------------------------------------------
    client_ip = (
        headers.get("cf-connecting-ip") or 
        headers.get("x-forwarded-for", "").split(",")[0].strip() or 
        headers.get("x-real-ip") or 
        "127.0.0.1"
    )
    user_agent = headers.get("user-agent", "Unknown")
    referer = headers.get("referer", "Direct")

    # Sanitize payload for logging (remove passwords/tokens)
    safe_payload = {k: v for k, v in payload.items() if not any(sec in k.lower() for sec in ["secret", "token", "password", "key"])}

    logger.info(
        f"[IVR STAGE 1 - RECEIVED] ReqID={req_id} | Time={now_iso} | ClientIP={client_ip} | "
        f"Referer={referer} | ParamsCount={len(payload)} | Payload={safe_payload}"
    )
    print(
        f">>> [IVR STAGE 1 - RECEIVED] ReqID={req_id} | IP={client_ip} | Payload={safe_payload}"
    )

    # Detect provider
    is_smartflo = bool(
        payload.get("uuid") or 
        payload.get("billing_circle") or 
        payload.get("answer_agent_number") or 
        payload.get("customer_no_with_prefix") or
        payload.get("customer_number_with_prefix") or
        "smartflo" in str(payload).lower() or
        "smartflo" in str(headers).lower()
    )
    detected_provider = "Smartflo" if is_smartflo else ("CloudShope" if "cloudshope" in str(payload).lower() or "circle" in payload else "IVR")

    call_sid_from_dict = payload.get("Call", {}).get("Sid") if isinstance(payload.get("Call"), dict) else None
    raw_unique_id = (
        payload.get("uuid") or
        payload.get("call_id") or
        payload.get("ref_id") or
        payload.get("uniqueid") or 
        payload.get("unique_id") or 
        payload.get("CallSid") or 
        payload.get("sid") or 
        payload.get("provider_call_id") or
        call_sid_from_dict
    )

    # Detect if provider call ID is a placeholder from web panel test
    if not raw_unique_id or _is_placeholder(raw_unique_id):
        provider_call_id = f"SMARTFLO_CALL_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6].upper()}" if is_smartflo else f"CS_CALL_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6].upper()}"
        is_test_call = True
    else:
        provider_call_id = str(raw_unique_id).strip()
        is_test_call = False

    raw_agent = (
        payload.get("answer_agent_number") or 
        payload.get("agent_number") or 
        payload.get("agent_num") or 
        payload.get("agent")
    )
    agent_name = payload.get("agent_name") or payload.get("agent") or f"{detected_provider} Agent"

    raw_cust_explicit = (
        payload.get("customer_no_with_prefix") or 
        payload.get("customer_number_with_prefix") or 
        payload.get("customer_no") or
        payload.get("customer_number")
    )

    raw_from = (
        payload.get("caller_id_number") or 
        payload.get("from") or 
        payload.get("From") or 
        payload.get("from_number") or 
        payload.get("caller")
    )
    raw_to = (
        payload.get("call_to_number") or 
        payload.get("to") or 
        payload.get("To") or 
        payload.get("to_number")
    )

    # Handle panel test tokens (%from%, %to%, etc.)
    from_str = "Demo Prospect" if _is_placeholder(raw_from) else str(raw_from or "Unknown").strip()
    to_str = "Smartflo Pilot" if _is_placeholder(raw_to) else str(raw_to or "Unknown").strip()
    agent_str = "" if _is_placeholder(raw_agent) else str(raw_agent or "").strip()

    # Normalize Status
    raw_st = (payload.get("call_status") or payload.get("status") or payload.get("CallStatus") or "ANSWERED")
    raw_st_clean = str(raw_st).lower().strip().replace("%", "")

    if any(k in raw_st_clean for k in ["completed", "ended", "hangup", "success"]):
        call_status = CALL_STATUS_COMPLETED
    elif any(k in raw_st_clean for k in ["answered", "connected", "in-progress", "inprogress", "answer", "agent answered"]):
        call_status = CALL_STATUS_ANSWERED
    elif any(k in raw_st_clean for k in ["ringing", "ring", "dialing"]):
        call_status = CALL_STATUS_RINGING
    elif any(k in raw_st_clean for k in ["no-answer", "no_answer", "missed", "not_answered", "unanswered", "noanswer"]):
        call_status = CALL_STATUS_MISSED
    elif "busy" in raw_st_clean:
        call_status = CALL_STATUS_BUSY
    elif any(k in raw_st_clean for k in ["failed", "canceled", "cancelled", "cancel"]):
        call_status = CALL_STATUS_FAILED
    else:
        call_status = CALL_STATUS_ANSWERED if is_test_call else raw_st_clean.upper()

    # Parse Duration
    raw_dur = (
        payload.get("duration") or
        payload.get("call_duration") or
        payload.get("agent_duration") or 
        payload.get("total_duration") or 
        payload.get("CallDuration") or 
        payload.get("duration_seconds")
    )
    if raw_dur and not _is_placeholder(raw_dur) and str(raw_dur).isdigit():
        duration_sec = int(raw_dur)
    else:
        duration_sec = 45 if is_test_call else 0

    # Parse Recording
    raw_rec = payload.get("recording") or payload.get("RecordingUrl") or payload.get("recording_url") or payload.get("recording_path")
    recording_url = None if _is_placeholder(raw_rec) else (str(raw_rec).strip() if raw_rec else None)

    # -------------------------------------------------------------
    # STAGE 3: RESOLVE DIRECTION (INBOUND VS OUTBOUND)
    # -------------------------------------------------------------
    # Check if an existing call was initiated through the CRM with this provider_call_id or ref_id/uuid
    existing_call = None
    if provider_call_id and not is_test_call:
        possible_ids = [provider_call_id]
        for k in ["ref_id", "uuid", "call_id"]:
            v = payload.get(k)
            if v and not _is_placeholder(v) and str(v).strip() not in possible_ids:
                possible_ids.append(str(v).strip())
        existing_call = db.query(CallLog).filter(CallLog.provider_call_id.in_(possible_ids)).first()

    # Resolve Direction (INBOUND VS OUTBOUND)
    explicit_direction = (payload.get("direction") or "").upper().strip()
    if explicit_direction in ["INBOUND", "OUTBOUND"]:
        call_direction = explicit_direction
    elif existing_call and existing_call.call_direction:
        call_direction = existing_call.call_direction
    else:
        call_direction = "INBOUND"

    # Customer phone number resolution
    if raw_cust_explicit and not _is_placeholder(raw_cust_explicit):
        customer_phone_raw = str(raw_cust_explicit).strip()
        pilot_phone = to_str if call_direction == "INBOUND" else from_str
    elif call_direction == "INBOUND":
        customer_phone_raw = from_str
        pilot_phone = to_str
    else:
        customer_phone_raw = to_str
        pilot_phone = from_str

    cust_digits = _clean_phone_digits(customer_phone_raw)

    # Cross-provider duplicate detection: same phone + same time window (3 min) from any provider
    # Prevents double entries when both Smartflo/IVR AND Doocti fire webhooks for the same call
    if not existing_call and not is_test_call and cust_digits and len(cust_digits) >= 10:
        _now = datetime.datetime.utcnow()
        _window_start = _now - datetime.timedelta(minutes=3)
        _window_end = _now + datetime.timedelta(minutes=1)
        existing_call = (
            db.query(CallLog)
            .filter(
                or_(
                    CallLog.to_number.like(f"%{cust_digits[-10:]}%"),
                    CallLog.from_number.like(f"%{cust_digits[-10:]}%"),
                ),
                CallLog.started_at >= _window_start,
                CallLog.started_at <= _window_end,
                CallLog.call_direction == call_direction,
            )
            .order_by(CallLog.created_at.desc())
            .first()
        )
        if existing_call:
            logger.info(
                f"[IVR DEDUP] Cross-provider duplicate detected: existing CallLog ID={existing_call.id} "
                f"(provider={existing_call.provider}, call_id={existing_call.provider_call_id}) "
                f"matches phone={cust_digits[-10:]} within 3-min window. Merging."
            )

    logger.info(
        f"[IVR STAGE 2 - PARSED] ReqID={req_id} | Provider={detected_provider} | ProviderCallID={provider_call_id} | "
        f"From={from_str} | To={to_str} | Agent={agent_str} | Direction={call_direction} | "
        f"Status={call_status} | Duration={duration_sec}s"
    )
    print(
        f">>> [IVR STAGE 2 - PARSED] Provider={detected_provider} | CallID={provider_call_id} | Direction={call_direction} | "
        f"Status={call_status} | From={from_str} | To={to_str}"
    )

    # -------------------------------------------------------------
    # STAGE 4: DATABASE MATCHING & RECORD CREATION (FastAPI -> Database)
    # -------------------------------------------------------------
    lead_id = None
    emp_id = None
    target_lead = None

    # Check if existing_call already has lead_id
    if existing_call and existing_call.lead_id:
        lead_id = existing_call.lead_id
        target_lead = db.query(Lead).filter(Lead.id == lead_id).first()

    if not lead_id and customer_phone_raw:
        matched_lead = find_existing_lead_by_phone(db, customer_phone_raw)
        if matched_lead:
            lead_id = matched_lead.id
            target_lead = matched_lead
            logger.info(f"[IVR STAGE 3 - DB MATCH] Matched existing Lead ID={lead_id} ({target_lead.name}) via normalized phone {cust_digits[-10:] if len(cust_digits) >= 10 else cust_digits}")
        else:
            # Check customer table
            matched_cust = find_existing_customer_by_phone(db, customer_phone_raw)
            if matched_cust and matched_cust.converted_from_lead:
                lead_id = matched_cust.converted_from_lead
                target_lead = db.query(Lead).filter(Lead.id == lead_id).first()
            elif call_direction == "OUTBOUND":
                # OUTBOUND CALL SAFEGUARD: Outbound calls must NEVER auto-create leads
                logger.info(f"[IVR STAGE 3 - DB MATCH] Outbound call to {customer_phone_raw} did not match an existing lead. Skipping auto-creation.")
            elif len(cust_digits) >= 10:
                # INBOUND CALL ONLY: Auto-create new Lead for unassigned incoming prospect
                formatted_phone = f"+91{cust_digits[-10:]}"
                new_lead = Lead(
                    name=f"Inbound Caller ({cust_digits[-10:]})",
                    phone=formatted_phone,
                    source="IVR",
                    status="NEW",
                    requirement_notes=f"Auto-created from {detected_provider} IVR Call (Pilot Number: {pilot_phone}, Circle: {payload.get('billing_circle') or payload.get('circle', 'India')})"
                )
                db.add(new_lead)
                db.flush()
                lead_id = new_lead.id
                target_lead = new_lead
                logger.info(f"[IVR STAGE 3 - DB CREATED LEAD] Created new Lead ID={lead_id} for {formatted_phone}")

    # Agent matching & Employee linking:
    # - Outgoing: Initiating employee (preserved on existing_call)
    # - Incoming answered: Employee who actually answered/handled the call (agent number)
    # - Missed / Unanswered: Assigned/receiving employee from lead
    agent_digits = _clean_phone_digits(agent_str)
    agent_emp = None
    if len(agent_digits) >= 10:
        agent_emp = db.query(Employee).filter(Employee.phone.ilike(f"%{agent_digits[-10:]}%")).first()

    if agent_emp and call_status in [CALL_STATUS_ANSWERED, CALL_STATUS_COMPLETED]:
        emp_id = agent_emp.id
        logger.info(f"[IVR STAGE 3 - DB MATCH] Linked answered call to handling Employee ID={emp_id} ({agent_emp.name})")
    elif target_lead and target_lead.assigned_to:
        emp_id = target_lead.assigned_to
        logger.info(f"[IVR STAGE 3 - DB MATCH] Linked missed/assigned call to Employee ID={emp_id}")
    elif agent_emp:
        emp_id = agent_emp.id
        logger.info(f"[IVR STAGE 3 - DB MATCH] Linked call to Employee ID={emp_id} ({agent_emp.name})")

    # If call already exists, update status & duration
    if existing_call:
        existing_call.call_status = call_status
        existing_call.duration_seconds = duration_sec or existing_call.duration_seconds
        if recording_url:
            existing_call.recording_url = recording_url
        if call_status in [CALL_STATUS_COMPLETED, CALL_STATUS_FAILED, CALL_STATUS_BUSY, CALL_STATUS_MISSED]:
            existing_call.ended_at = datetime.datetime.utcnow()
        if lead_id and not existing_call.lead_id:
            existing_call.lead_id = lead_id
        if emp_id and not existing_call.employee_id:
            existing_call.employee_id = emp_id

        db.commit()
        db.refresh(existing_call)
        call_record_id = existing_call.id
        action_taken = "UPDATED"
    else:
        # Create new CallLog record
        try:
            new_call = CallLog(
                provider=detected_provider,
                provider_call_id=provider_call_id,
                from_number=from_str,
                to_number=to_str,
                call_status=call_status,
                call_direction=call_direction,
                duration_seconds=duration_sec,
                recording_url=recording_url,
                started_at=datetime.datetime.utcnow(),
                ended_at=datetime.datetime.utcnow() if call_status in [CALL_STATUS_COMPLETED, CALL_STATUS_FAILED, CALL_STATUS_BUSY, CALL_STATUS_MISSED] else None,
                lead_id=lead_id,
                employee_id=emp_id,
                notes=f"{detected_provider} IVR ({call_direction}) | Agent: {agent_name} | Circle: {payload.get('billing_circle') or payload.get('circle', 'N/A')} | Operator: {payload.get('operator', 'N/A')}"
            )
            db.add(new_call)
            db.commit()
            db.refresh(new_call)
            call_record_id = new_call.id
            action_taken = "CREATED"
        except Exception as insert_err:
            db.rollback()
            existing_call = db.query(CallLog).filter(CallLog.provider_call_id == provider_call_id).first()
            if existing_call:
                logger.info(f"[IVR DEDUP] Handled race condition: updated CallLog ID={existing_call.id} for provider_call_id={provider_call_id}")
                existing_call.call_status = call_status
                if duration_sec:
                    existing_call.duration_seconds = duration_sec
                if recording_url and not existing_call.recording_url:
                    existing_call.recording_url = recording_url
                if lead_id and not existing_call.lead_id:
                    existing_call.lead_id = lead_id
                if emp_id and not existing_call.employee_id:
                    existing_call.employee_id = emp_id
                db.commit()
                db.refresh(existing_call)
                call_record_id = existing_call.id
                action_taken = "UPDATED"
            else:
                logger.error(f"[IVR ERROR] Failed to create CallLog: {insert_err}")
                raise insert_err

    # Add Lead Activity entry
    if lead_id:
        dir_label = "Inbound" if call_direction == "INBOUND" else "Outbound"
        act = LeadActivity(
            lead_id=lead_id,
            performed_by=emp_id,
            activity_type=f"CALL_{call_status}",
            related_entity_type="CALL",
            related_entity_id=call_record_id,
            description=f"{dir_label} IVR call ({call_status.title()}) with {from_str}. Duration: {duration_sec}s."
        )
        db.add(act)
        db.commit()

    # -------------------------------------------------------------
    # STAGE 5: RESULT SUMMARY (Database -> CRM UI)
    # -------------------------------------------------------------
    summary_msg = (
        f"[IVR STAGE 5 - COMPLETE] ReqID={req_id} | CallRecordID={call_record_id} | "
        f"ProviderCallID={provider_call_id} | Direction={call_direction} | "
        f"Status={call_status} | LeadID={lead_id} | Action={action_taken}"
    )
    logger.info(summary_msg)
    print(f">>> {summary_msg}")

    return {
        "status": "success",
        "action": action_taken,
        "request_id": req_id,
        "message": f"Call log {action_taken.lower()} successfully",
        "call_id": call_record_id,
        "provider_call_id": provider_call_id,
        "call_direction": call_direction,
        "call_status": call_status,
        "lead_id": lead_id,
        "caller": from_str,
        "receiver": to_str
    }
