import os
import datetime
import json
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from config import settings
from models import Lead, LeadActivity, Employee, CallLog
from .base import BaseIVRProvider
from .providers import MockIVRProvider, TwilioIVRProvider, ExotelIVRProvider, CloudShopeIVRProvider, SmartfloIVRProvider
from .schemas import (
    CALL_STATUS_INITIATED,
    CALL_STATUS_RINGING,
    CALL_STATUS_ANSWERED,
    CALL_STATUS_COMPLETED,
    CALL_STATUS_FAILED,
    CALL_STATUS_MISSED,
    CALL_STATUS_BUSY
)

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

        # 5. Save CallLog Record in Database
        call_log = CallLog(
            lead_id=lead_id,
            employee_id=current_employee_id,
            provider=provider_name,
            provider_call_id=provider_call_id,
            from_number=emp_phone,
            to_number=target_customer_phone,
            call_status=initial_status,
            call_direction="OUTBOUND",
            started_at=datetime.datetime.utcnow(),
            notes=notes or f"Click-to-Call initiated. Employee: {emp_phone}, Customer: {target_customer_phone}"
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
    def log_manual_call(
        db: Session,
        lead_id: Optional[int] = None,
        current_employee_id: Optional[int] = None,
        customer_phone: Optional[str] = None,
        employee_phone: Optional[str] = None,
        call_status: str = "COMPLETED",
        duration_seconds: int = 0,
        notes: Optional[str] = None
    ) -> CallLog:
        """
        Logs a direct or manual phone call (device fallback / offline dial).
        Records CallLog and LeadActivity without calling cloud telecom APIs.
        """
        import uuid

        target_phone = str(customer_phone or "").strip()
        if not target_phone and lead_id:
            lead = db.query(Lead).filter(Lead.id == lead_id).first()
            if lead:
                target_phone = lead.phone or lead.whatsapp_number or ""

        if not target_phone:
            raise ValueError("Customer phone number is required to log a call.")

        emp_phone = employee_phone
        if not emp_phone and current_employee_id:
            emp = db.query(Employee).filter(Employee.id == current_employee_id).first()
            if emp and emp.phone:
                emp_phone = emp.phone
        if not emp_phone:
            emp_phone = "+919876500000"

        now = datetime.datetime.utcnow()
        start_time = now - datetime.timedelta(seconds=duration_seconds or 0)
        provider_call_id = f"DIRECT_{uuid.uuid4().hex[:10].upper()}"

        call_log = CallLog(
            lead_id=lead_id,
            employee_id=current_employee_id,
            provider="DIRECT_DIAL",
            provider_call_id=provider_call_id,
            from_number=emp_phone,
            to_number=target_phone,
            call_status=call_status.upper(),
            call_direction="OUTBOUND",
            duration_seconds=duration_seconds,
            started_at=start_time,
            answered_at=start_time if call_status.upper() in ["COMPLETED", "CONNECTED"] else None,
            ended_at=now,
            notes=notes or f"Direct Device / Manual Call ({call_status})."
        )
        db.add(call_log)
        db.commit()
        db.refresh(call_log)

        if lead_id:
            dur_msg = f" (Duration: {duration_seconds}s)" if duration_seconds else ""
            note_msg = f" Notes: {notes}" if notes else ""
            activity = LeadActivity(
                lead_id=lead_id,
                performed_by=current_employee_id,
                activity_type="CALL_LOGGED",
                description=f"Direct Phone Call logged to {target_phone} - Status: {call_status}{dur_msg}.{note_msg}"
            )
            db.add(activity)
            db.commit()

        return call_log
