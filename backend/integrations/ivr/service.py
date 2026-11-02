import os
import datetime
import json
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from config import settings
from models import Lead, LeadActivity, Employee, CallLog
from utils.timezone import get_ist_now, IST_TIMEZONE
from .base import BaseIVRProvider
from .providers import MockIVRProvider, TwilioIVRProvider, ExotelIVRProvider, CloudShopeIVRProvider, SmartfloIVRProvider, DooctiIVRProvider
from .schemas import (
    CALL_STATUS_INITIATED,
    CALL_STATUS_RINGING,
    CALL_STATUS_ANSWERED,
    CALL_STATUS_COMPLETED,
    CALL_STATUS_FAILED,
    CALL_STATUS_MISSED,
    CALL_STATUS_BUSY
)

logger = logging.getLogger(__name__)

class IVRNotConfiguredException(Exception):
    def __init__(self, message: str = "IVR is not configured. Please configure IVR from Settings → Integrations."):
        self.message = message
        super().__init__(self.message)

class IVRService:
    """
    Provider-Independent IVR Service Layer for WaCRM.
    Handles provider instantiation, click-to-call execution, DB logging,
    and lead activity audit tracking.
    """

    @staticmethod
    def get_provider(db: Optional[Session] = None) -> BaseIVRProvider:
        """
        Loads the configured IVR provider based on DB IntegrationConfig or environment settings.
        Throws IVRNotConfiguredException if missing credentials or provider status is DISCONNECTED.
        """
        provider_name = ""
        account_sid = ""
        auth_token = ""
        from_number = "+18005550199"
        data = {}

        if db:
            from models.integration import IntegrationConfig
            cfg = db.query(IntegrationConfig).filter(IntegrationConfig.integration_type == "IVR").first()
            if cfg:
                if cfg.status in ["DISCONNECTED", "NOT_CONNECTED"] and not os.getenv("IVR_PROVIDER"):
                    raise IVRNotConfiguredException("IVR is not configured. Please configure IVR from Settings → Integrations.")
                
                if cfg.config_data:
                    try:
                        data = json.loads(cfg.config_data or "{}")
                        provider_name = (data.get("provider") or "").upper().strip()
                        account_sid = data.get("account_id") or data.get("api_key") or ""
                        auth_token = data.get("api_secret") or data.get("api_key") or ""
                        from_number = data.get("phone_number") or from_number
                    except Exception:
                        pass

        if not provider_name:
            provider_name = (os.getenv("IVR_PROVIDER") or "").upper().strip() or "MOCK"

        account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID") or os.getenv("IVR_ACCOUNT_SID") or settings.IVR_API_KEY
        auth_token = auth_token or os.getenv("TWILIO_AUTH_TOKEN") or os.getenv("IVR_AUTH_TOKEN") or settings.IVR_API_SECRET
        from_number = from_number or os.getenv("TWILIO_PHONE_NUMBER") or os.getenv("IVR_FROM_NUMBER") or "+18005550199"

        if provider_name == "TWILIO":
            tw_account_sid = data.get("account_id") or os.getenv("TWILIO_ACCOUNT_SID") or ""
            tw_auth_token = data.get("api_key") or data.get("api_secret") or os.getenv("TWILIO_AUTH_TOKEN")
            tw_from_number = data.get("phone_number") or os.getenv("TWILIO_PHONE_NUMBER") or ""

            if not tw_account_sid or not tw_auth_token:
                raise IVRNotConfiguredException("Twilio Auth Token missing. Please configure Twilio Auth Token in Settings → Integrations.")
            return TwilioIVRProvider(account_sid=tw_account_sid, auth_token=tw_auth_token, from_number=tw_from_number)

        elif provider_name == "EXOTEL":
            ex_account_sid = data.get("account_id") or data.get("account_sid") or os.getenv("EXOTEL_ACCOUNT_SID") or "chntechnologies1"
            ex_api_key = data.get("api_key") or os.getenv("EXOTEL_API_KEY") or "87a53dbe68e08daf13602496e7c380f0d252ef4ae9b2f615"
            ex_api_token = data.get("api_secret") or data.get("api_token") or os.getenv("EXOTEL_API_TOKEN") or "f1a423ea03db8834b9ea2bf8bfaea22f6b58030b89b6f02a"
            ex_from_number = data.get("phone_number") or from_number or os.getenv("EXOTEL_CALLER_ID") or ""
            ex_subdomain = data.get("subdomain") or os.getenv("EXOTEL_SUBDOMAIN") or "api.exotel.com"

            if not ex_account_sid or not ex_api_key or not ex_api_token:
                raise IVRNotConfiguredException("Exotel API credentials missing. Please configure Exotel in Settings → Integrations.")

            return ExotelIVRProvider(
                account_sid=ex_account_sid,
                auth_token=ex_api_token,
                from_number=ex_from_number,
                api_key=ex_api_key,
                api_token=ex_api_token,
                subdomain=ex_subdomain
            )

        elif provider_name in ["CLOUDSHOPE", "CLOUDSHPE", "CLOUD_SHOPE"]:
            data_dict = data if "data" in locals() and isinstance(data, dict) else {}
            cs_api_key = data_dict.get("api_key") or data_dict.get("api_secret") or os.getenv("CLOUDSHOPE_API_KEY") or auth_token
            cs_virtual_number = data_dict.get("phone_number") or os.getenv("CLOUDSHOPE_VIRTUAL_NUMBER") or from_number or "1204362938"
            cs_api_url = data_dict.get("api_url") or os.getenv("CLOUDSHOPE_API_URL") or "http://yourmessageapi.com/clicktocall.php"
            cs_account_sid = data_dict.get("account_id") or os.getenv("CLOUDSHOPE_ACCOUNT_SID") or "cloudshope"
            return CloudShopeIVRProvider(
                api_key=cs_api_key or "",
                virtual_number=cs_virtual_number,
                api_url=cs_api_url,
                account_sid=cs_account_sid
            )

        elif provider_name in ["SMARTFLO", "TATA_SMARTFLO", "TATA", "TATASMARTFLO", "TATA_TELESERVICES"]:
            data_dict = data if "data" in locals() and isinstance(data, dict) else {}
            sf_api_key = data_dict.get("api_key") or data_dict.get("api_secret") or os.getenv("SMARTFLO_API_KEY") or auth_token or "62c5d471-63a3-43c9-a12e-d1da29d46f05"
            sf_api_token = data_dict.get("api_token") or data_dict.get("access_token") or os.getenv("SMARTFLO_API_TOKEN") or ""
            sf_caller_id = data_dict.get("phone_number") or data_dict.get("caller_id") or os.getenv("SMARTFLO_CALLER_ID") or from_number or ""
            sf_api_url = data_dict.get("api_url") or os.getenv("SMARTFLO_API_URL") or "https://api-smartflo.tatateleservices.com/v1/click_to_call"
            return SmartfloIVRProvider(
                api_key=sf_api_key,
                api_token=sf_api_token,
                caller_id=sf_caller_id,
                api_url=sf_api_url
            )

        elif provider_name in ["DOOCTI", "DOOCTI_IVR", "DOOCTI_TELEPHONY"]:
            data_dict = data if "data" in locals() and isinstance(data, dict) else {}
            doocti_account_id = data_dict.get("account_id") or ""
            doocti_api_url = data_dict.get("api_url") or ""
            dids = data_dict.get("did_numbers") or []
            if isinstance(dids, str):
                dids = [d.strip() for d in dids.split(",") if d.strip()]
            ext_map = data_dict.get("extension_mapping") or {}
            admin_ext = data_dict.get("admin_extension") or ""
            secret_token = data_dict.get("secret_token")
            return DooctiIVRProvider(
                account_id=doocti_account_id,
                api_url=doocti_api_url,
                did_numbers=dids,
                extension_mapping=ext_map,
                secret_token=secret_token,
                admin_extension=admin_ext
            )

        elif provider_name in ["MOCK", "CUSTOM", "MYOPERATOR"]:
            return MockIVRProvider(account_sid=account_sid or "mock_sid", auth_token=auth_token or "mock_token", from_number=from_number)

        raise IVRNotConfiguredException("IVR is not configured. Please configure IVR from Settings → Integrations.")

    @staticmethod
    def is_configured(db: Optional[Session] = None) -> bool:
        try:
            IVRService.get_provider(db=db)
            return True
        except IVRNotConfiguredException:
            return False

    @staticmethod
    def initiate_call(
        db: Session, 
        lead_id: Optional[int] = None, 
        current_employee_id: Optional[int] = None, 
        customer_phone: Optional[str] = None,
        employee_phone: Optional[str] = None,
        notes: Optional[str] = None
    ) -> CallLog:
        """
        Initiates a Click-to-Call bridging the employee's phone and the customer's phone.
        Records entry in database and lead activity log.
        """
        # 1. Resolve Lead & Customer Phone
        lead = None
        if lead_id:
            lead = db.query(Lead).filter(Lead.id == lead_id).first()

        target_customer_phone = str(customer_phone or (lead.phone if lead else "")).strip()
        if not target_customer_phone:
            raise ValueError("A valid customer phone number is required to initiate call.")

        # E.164 Auto-Formatting: Prepend +91 for 10-digit Indian numbers if + is missing
        clean_phone = target_customer_phone.replace(" ", "").replace("-", "")
        if not clean_phone.startswith("+"):
            if len(clean_phone) == 10 and clean_phone[0] in ["6", "7", "8", "9"]:
                target_customer_phone = f"+91{clean_phone}"
            elif len(clean_phone) == 12 and clean_phone.startswith("91"):
                target_customer_phone = f"+{clean_phone}"

        # 2. Resolve Logged-In Employee & Registered Employee Phone Number
        emp_phone = employee_phone
        if not emp_phone and current_employee_id:
            emp = db.query(Employee).filter(Employee.id == current_employee_id).first()
            if emp and emp.phone:
                emp_phone = emp.phone

        if not emp_phone:
            emp_phone = "+919876500000"

        # 3. Instantiate Provider (Raises IVRNotConfiguredException if missing)
        provider = IVRService.get_provider(db=db)
        
        # Determine provider name
        provider_name = "IVR_SERVICE"
        if hasattr(provider, "__class__"):
            provider_name = provider.__class__.__name__.replace("IVRProvider", "").upper()

        # 4. Execute Click-to-Call Request with Provider
        call_res = provider.initiate_call(
            from_number=emp_phone,
            to_number=target_customer_phone,
            custom_data={"lead_id": lead_id, "employee_id": current_employee_id}
        )

        provider_call_id = call_res.get("provider_call_id")
        initial_status = call_res.get("status", CALL_STATUS_INITIATED)
        active_from_number = call_res.get("station") or emp_phone

        # 5. Save CallLog Record in Database
        call_log = CallLog(
            lead_id=lead_id,
            employee_id=current_employee_id,
            provider=provider_name,
            provider_call_id=provider_call_id,
            from_number=active_from_number,
            to_number=target_customer_phone,
            call_status=initial_status,
            call_direction="OUTBOUND",
            started_at=datetime.datetime.utcnow(),
            notes=notes or f"Click-to-Call initiated via {provider_name}. Station: {active_from_number}, Customer: {target_customer_phone}"
        )
        db.add(call_log)
        db.commit()
        db.refresh(call_log)

        # 6. Record Lead Activity Entry if lead_id present
        if lead_id:
            activity = LeadActivity(
                lead_id=lead_id,
                performed_by=current_employee_id,
                activity_type="CALL_INITIATED",
                description=f"Outbound Click-to-Call initiated via {provider_name} to {target_customer_phone} (Call ID: {provider_call_id})."
            )
            db.add(activity)
            db.commit()

        return call_log

    @staticmethod
    def update_call_status(
        db: Session,
        provider_call_id: str,
        new_status: str,
        duration_seconds: Optional[int] = None,
        recording_url: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Optional[CallLog]:
        """
        Updates an existing call log when status changes (e.g. from Webhook, Polling, or Simulation).
        Also appends to Lead Activity History.
        """
        call_log = db.query(CallLog).filter(
            (CallLog.provider_call_id == provider_call_id) | (CallLog.id == int(provider_call_id) if provider_call_id.isdigit() else False)
        ).first()

        if not call_log:
            return None

        old_status = call_log.call_status
        call_log.call_status = new_status.upper()

        if duration_seconds is not None:
            call_log.duration_seconds = duration_seconds
        if recording_url:
            call_log.recording_url = recording_url
        if notes:
            call_log.notes = notes

        now = datetime.datetime.utcnow()

        if new_status.upper() in ["ANSWERED", "CONNECTED"] and not call_log.answered_at:
            call_log.answered_at = now

        if new_status.upper() in ["COMPLETED", "FAILED", "MISSED", "BUSY", "NO_ANSWER"]:
            call_log.ended_at = now
            if new_status.upper() == "COMPLETED":
                if call_log.answered_at and call_log.ended_at >= call_log.answered_at:
                    call_log.duration_seconds = max(1, int((call_log.ended_at - call_log.answered_at).total_seconds()))
                elif not call_log.duration_seconds and call_log.started_at:
                    call_log.duration_seconds = max(1, int((now - call_log.started_at).total_seconds()))
            elif new_status.upper() in ["MISSED", "BUSY", "FAILED", "NO_ANSWER"]:
                call_log.duration_seconds = 0
                call_log.answered_at = None

        db.commit()
        db.refresh(call_log)

        # Log Activity if status changed
        if old_status != new_status and call_log.lead_id:
            dur_str = f" Duration: {call_log.duration_seconds}s." if call_log.duration_seconds else ""
            rec_str = f" Recording: {call_log.recording_url}" if call_log.recording_url else ""
            activity = LeadActivity(
                lead_id=call_log.lead_id,
                performed_by=call_log.employee_id,
                activity_type="CALL_STATUS_UPDATE",
                description=f"Call status updated to {new_status}.{dur_str}{rec_str}"
            )
            db.add(activity)
            db.commit()

        return call_log

    @staticmethod
    def _naive_ist(value: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
        """
        Normalizes an optional datetime for the CRM's MySQL DATETIME convention:
        naive Asia/Kolkata (IST). Aware values (mobile sends UTC ISO strings) are
        converted to IST; naive values are assumed to already be IST.
        """
        if value is None:
            return None
        if value.tzinfo is not None:
            value = value.astimezone(IST_TIMEZONE).replace(tzinfo=None)
        return value

    @staticmethod
    def log_manual_call(
        db: Session,
        lead_id: Optional[int] = None,
        current_employee_id: Optional[int] = None,
        customer_phone: Optional[str] = None,
        employee_phone: Optional[str] = None,
        call_status: str = "COMPLETED",
        duration_seconds: int = 0,
        notes: Optional[str] = None,
        client_call_id: Optional[str] = None,
        call_direction: Optional[str] = None,
        started_at: Optional[datetime.datetime] = None,
        answered_at: Optional[datetime.datetime] = None,
        ended_at: Optional[datetime.datetime] = None,
        recording_url: Optional[str] = None,
        sim_account_id: Optional[str] = None,
        sim_subscription_id: Optional[int] = None,
        sim_label: Optional[str] = None,
        sim_slot: Optional[int] = None,
        sim_phone_number: Optional[str] = None,
        call_source: Optional[str] = None,
        native_call_reference: Optional[str] = None
    ) -> CallLog:
        """
        Logs a direct or manual phone call (device fallback / mobile SIM dial).
        Records CallLog and LeadActivity without calling cloud telecom APIs.

        Mobile SIM calls send a stable `client_call_id`; the same ID is used as
        `provider_call_id` so retries from the device cannot create duplicates.
        """
        import uuid

        ATTEMPT_STATUSES = {
            "INITIATED",
            "INITIATING",
            "PENDING",
            "DIALING",
            "RINGING",
            "CONNECTING",
        }
        TERMINAL_STATUSES = {
            "COMPLETED",
            "CONNECTED",
            "MISSED",
            "REJECTED",
            "NO_ANSWER",
            "BUSY",
            "FAILED",
            "CANCELLED",
        }
        UNANSWERED_STATUSES = {
            "MISSED",
            "REJECTED",
            "NO_ANSWER",
            "BUSY",
            "FAILED",
            "CANCELLED",
        }

        client_call_id = str(client_call_id or "").strip()
        native_ref = str(native_call_reference or "").strip()
        if native_ref and len(native_ref) > 100:
            raise ValueError("native_call_reference must be 100 characters or fewer.")
        # For device-history sync the native row id is the idempotency key. A
        # retry of the same native row updates the same CRM record.
        if native_ref and not client_call_id:
            client_call_id = native_ref

        is_mobile_sim = (
            str(call_source or "").strip().upper() == "MOBILE_SIM"
            or bool(native_ref)
            or bool(sim_account_id or sim_label)
            or sim_subscription_id is not None
            or sim_slot is not None
        )

        requested_direction = str(call_direction or "").strip().upper()
        if requested_direction not in ("INBOUND", "OUTBOUND"):
            requested_direction = None
        # Never invent a direction for a device call. An existing row keeps its
        # stored (native) direction; a new device row must supply one. Only
        # non-device legacy/manual calls retain the historical OUTBOUND default.
        direction = requested_direction or ("OUTBOUND" if not is_mobile_sim else None)

        status = str(call_status or "COMPLETED").strip().upper().replace(" ", "_")
        if status == "UNANSWERED":
            status = "NO_ANSWER"
        # Keep the historic API behaviour for clients that send ANSWERED.
        if status == "ANSWERED":
            status = "COMPLETED"
        if status not in ATTEMPT_STATUSES and status not in TERMINAL_STATUSES:
            # Never invent a completed call for a device flow we cannot verify.
            status = "FAILED" if is_mobile_sim else "COMPLETED"

        is_attempt = status in ATTEMPT_STATUSES

        try:
            duration_seconds = max(0, int(duration_seconds or 0))
        except (TypeError, ValueError):
            duration_seconds = 0

        if is_attempt or status in UNANSWERED_STATUSES:
            duration_seconds = 0

        now = get_ist_now()
        start_arg = IVRService._naive_ist(started_at)
        end_arg = IVRService._naive_ist(ended_at)
        answered_arg = IVRService._naive_ist(answered_at)

        target_phone = str(customer_phone or "").strip()
        if not target_phone and lead_id:
            lead = db.query(Lead).filter(Lead.id == lead_id).first()
            if lead:
                target_phone = lead.phone or lead.whatsapp_number or ""

        # Device call-history rows do not know the CRM lead. Match the existing
        # lead by normalized phone so mobile, web and admin views stay unified.
        if lead_id is None and target_phone:
            try:
                from sqlalchemy import inspect as sa_inspect
                from utils.phone import find_existing_lead_by_phone

                if sa_inspect(db.get_bind()).has_table("leads"):
                    matched_lead = find_existing_lead_by_phone(db, target_phone)
                    if matched_lead is not None:
                        lead_id = matched_lead.id
            except Exception:
                # Phone enrichment is best-effort and must never block logging.
                try:
                    db.rollback()
                except Exception:
                    pass

        emp_phone = str(sim_phone_number or employee_phone or "").strip()
        if not emp_phone and current_employee_id:
            emp = db.query(Employee).filter(Employee.id == current_employee_id).first()
            if emp and emp.phone:
                emp_phone = emp.phone
        if not emp_phone:
            emp_phone = "+919876500000"

        def validate_existing(existing: CallLog) -> None:
            if (existing.provider or "").upper() not in ("MOBILE_SIM", "DIRECT_DIAL"):
                raise ValueError("This call id is already used by another telephony record.")
            if (
                current_employee_id is not None
                and existing.employee_id != current_employee_id
            ):
                raise ValueError("This call record belongs to another employee.")

        def find_tracked_duplicate() -> Optional[CallLog]:
            """
            Finds the single in-app tracked SIM attempt that the same native
            call-log row represents. Strict phone + direction + start-time
            matching means a history row can never absorb an unrelated call.
            The native row is authoritative for duration/status, so the tracked
            row is updated in place instead of creating a duplicate.
            """
            if not native_ref or not target_phone or start_arg is None:
                return None
            if direction not in ("INBOUND", "OUTBOUND"):
                # Without a proven direction the native row could match an
                # unrelated attempt; refuse to reconcile instead of guessing.
                return None
            if current_employee_id is None:
                return None
            try:
                from utils.phone import normalize_phone

                clean_target = normalize_phone(target_phone)
                if not clean_target:
                    return None
                window_start = start_arg - datetime.timedelta(seconds=60)
                window_end = start_arg + datetime.timedelta(seconds=60)
                candidates = (
                    db.query(CallLog)
                    .filter(
                        CallLog.employee_id == current_employee_id,
                        CallLog.provider.in_(["MOBILE_SIM", "DIRECT_DIAL"]),
                        CallLog.provider_call_id != client_call_id,
                        CallLog.call_direction == direction,
                        CallLog.started_at.isnot(None),
                        CallLog.started_at >= window_start,
                        CallLog.started_at <= window_end,
                    )
                    .all()
                )
                matches = []
                for candidate in candidates:
                    candidate_phone = (
                        candidate.to_number
                        if direction == "OUTBOUND"
                        else candidate.from_number
                    )
                    if normalize_phone(candidate_phone) == clean_target:
                        matches.append(candidate)
                if len(matches) == 1:
                    return matches[0]
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
            return None

        # Idempotency: a device retry must reuse the already-saved call record.
        # Final results update the pending attempt in place; a late attempt event
        # must never downgrade a completed call.
        if client_call_id:
            existing = db.query(CallLog).filter(
                CallLog.provider_call_id == client_call_id
            ).first()
            if not existing and native_ref:
                existing = find_tracked_duplicate()
            if existing:
                validate_existing(existing)

                previous_status = str(existing.call_status or "").upper()
                existing_is_attempt = previous_status in ATTEMPT_STATUSES
                if is_attempt and not existing_is_attempt:
                    return existing

                stored_direction = str(existing.call_direction or "").strip().upper()
                effective_direction = (
                    requested_direction or stored_direction or "OUTBOUND"
                )
                # INBOUND is sticky: a later retry that claims OUTBOUND must not
                # relabel a call that was already proven inbound by the device.
                # The reverse correction (OUTBOUND -> INBOUND) is allowed when
                # newer native evidence supplies INBOUND.
                if stored_direction == "INBOUND" and requested_direction == "OUTBOUND":
                    effective_direction = "INBOUND"
                if target_phone:
                    if effective_direction == "INBOUND":
                        existing.from_number = target_phone
                        if emp_phone:
                            existing.to_number = emp_phone
                    else:
                        existing.to_number = target_phone
                if lead_id is not None:
                    existing.lead_id = lead_id
                existing.call_status = status
                existing.duration_seconds = duration_seconds
                if requested_direction and effective_direction == requested_direction:
                    existing.call_direction = requested_direction

                if is_attempt:
                    existing.started_at = start_arg or existing.started_at or now
                    existing.answered_at = None
                    existing.ended_at = None
                else:
                    end_dt = end_arg or now
                    if start_arg:
                        existing.started_at = start_arg
                    if not existing.started_at:
                        existing.started_at = end_dt - datetime.timedelta(
                            seconds=duration_seconds
                        )
                    if existing.started_at > end_dt:
                        existing.started_at = end_dt - datetime.timedelta(
                            seconds=duration_seconds
                        )
                    existing.ended_at = end_dt
                    if status in ("COMPLETED", "CONNECTED"):
                        existing.answered_at = (
                            answered_arg
                            or end_dt - datetime.timedelta(seconds=duration_seconds)
                        )
                    else:
                        existing.answered_at = None

                if recording_url is not None:
                    existing.recording_url = str(recording_url).strip() or None
                if sim_account_id:
                    existing.sim_account_id = str(sim_account_id).strip() or None
                if sim_label:
                    existing.sim_label = str(sim_label).strip() or None
                if sim_slot is not None:
                    existing.sim_slot = sim_slot
                if notes is not None:
                    existing.notes = notes

                try:
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
                db.refresh(existing)
                logger.info(
                    "mobile call direction saved id=%s native=%s "
                    "requested=%s stored=%s",
                    existing.id,
                    native_ref or "-",
                    requested_direction or "-",
                    str(existing.call_direction or "").upper() or "-",
                )

                # Log a lead activity only on the pending -> final transition,
                # so retries of the same final result do not duplicate activity.
                activity_lead_id = lead_id if lead_id is not None else existing.lead_id
                if activity_lead_id and existing_is_attempt and not is_attempt:
                    dur_msg = f" (Duration: {duration_seconds}s)" if duration_seconds else ""
                    sim_msg = f" via {sim_label or existing.sim_label}" if (sim_label or existing.sim_label) else ""
                    db.add(LeadActivity(
                        lead_id=activity_lead_id,
                        performed_by=current_employee_id,
                        activity_type="CALL_LOGGED",
                        description=(
                            f"Mobile SIM call{sim_msg} to {target_phone or existing.to_number} - "
                            f"Status: {status}{dur_msg}."
                        ),
                    ))
                    db.commit()

                return existing

        if is_mobile_sim and requested_direction is None:
            # No native/device direction: refuse to create a row. Silently
            # defaulting to OUTBOUND is what mislabels incoming calls.
            raise ValueError(
                "call_direction is required for mobile/device calls and must "
                "be INBOUND or OUTBOUND."
            )

        if not target_phone:
            raise ValueError("Customer phone number is required to log a call.")

        provider_name = "MOBILE_SIM" if is_mobile_sim else "DIRECT_DIAL"
        provider_call_id = client_call_id or f"DIRECT_{uuid.uuid4().hex[:10].upper()}"

        if is_attempt:
            start_dt = start_arg or now
            end_dt = None
            answered_dt = None
        else:
            end_dt = end_arg or now
            if start_arg:
                start_dt = start_arg
            else:
                start_dt = end_dt - datetime.timedelta(seconds=duration_seconds)
            if not start_dt or start_dt > end_dt:
                start_dt = end_dt - datetime.timedelta(seconds=duration_seconds)
            answered_dt = answered_arg
            if status in ("COMPLETED", "CONNECTED"):
                if not answered_dt:
                    answered_dt = end_dt - datetime.timedelta(seconds=duration_seconds)
            else:
                answered_dt = None

        if is_mobile_sim:
            default_note = "Mobile SIM call from device dialer."
            if sim_label:
                default_note = f"Mobile SIM call via {sim_label}."
            if is_attempt:
                default_note = "Mobile SIM call attempt placed from the device dialer."
        else:
            default_note = f"Direct Device / Manual Call ({status})."

        call_log = CallLog(
            lead_id=lead_id,
            employee_id=current_employee_id,
            provider=provider_name,
            provider_call_id=provider_call_id,
            from_number=(target_phone if direction == "INBOUND" else emp_phone),
            to_number=(emp_phone if direction == "INBOUND" else target_phone),
            call_status=status,
            call_direction=direction,
            duration_seconds=duration_seconds,
            recording_url=(str(recording_url).strip() or None) if recording_url else None,
            started_at=start_dt,
            answered_at=answered_dt,
            ended_at=end_dt,
            sim_account_id=(str(sim_account_id).strip() or None) if sim_account_id else None,
            sim_label=(str(sim_label).strip() or None) if sim_label else None,
            sim_slot=sim_slot,
            notes=notes or default_note
        )
        db.add(call_log)
        try:
            db.commit()
        except IntegrityError:
            # Concurrent retry with the same client_call_id: reuse the winner.
            db.rollback()
            if client_call_id:
                existing = db.query(CallLog).filter(
                    CallLog.provider_call_id == client_call_id
                ).first()
                if existing:
                    validate_existing(existing)
                    return existing
            raise
        db.refresh(call_log)

        logger.info(
            "mobile call direction saved id=%s native=%s requested=%s stored=%s",
            call_log.id,
            native_ref or "-",
            requested_direction or "-",
            str(call_log.call_direction or "").upper() or "-",
        )

        if lead_id and not is_attempt:
            dur_msg = f" (Duration: {duration_seconds}s)" if duration_seconds else ""
            note_msg = f" Notes: {notes}" if notes else ""
            if is_mobile_sim:
                sim_msg = f" via {sim_label}" if sim_label else ""
                description = (
                    f"Mobile SIM call{sim_msg} to {target_phone} - "
                    f"Status: {status}{dur_msg}.{note_msg}"
                )
                activity_type = "CALL_LOGGED"
            else:
                description = (
                    f"Direct Phone Call logged to {target_phone} - "
                    f"Status: {status}{dur_msg}.{note_msg}"
                )
                activity_type = "CALL_LOGGED"
            activity = LeadActivity(
                lead_id=lead_id,
                performed_by=current_employee_id,
                activity_type=activity_type,
                description=description
            )
            db.add(activity)
            db.commit()

        return call_log
