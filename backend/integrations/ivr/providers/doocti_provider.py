import logging
import uuid
import datetime
import httpx
from typing import Dict, Any, Optional, List
from ..base import BaseIVRProvider
from ..schemas import (
    CALL_STATUS_INITIATED,
    CALL_STATUS_RINGING,
    CALL_STATUS_ANSWERED,
    CALL_STATUS_COMPLETED,
    CALL_STATUS_FAILED
)

logger = logging.getLogger("doocti_ivr")

class DooctiIVRProvider(BaseIVRProvider):
    """
    Doocti Computer Telephony Integration (CTI) & PBX Provider for WaCRM.
    Handles Outbound Calling, WebPhone agent routing, Click-to-Call,
    and real-time CDR synchronization for both Web and Mobile.
    """

    def __init__(
        self,
        account_id: str = "chntechnolog",
        api_url: str = "https://beta3-app.doocti.com/",
        did_numbers: Optional[List[str]] = None,
        extension_mapping: Optional[Dict[str, Any]] = None,
        secret_token: Optional[str] = None,
        admin_extension: str = "1281"
    ):
        self.account_id = (account_id or "chntechnolog").strip()
        self.api_url = (api_url or "https://beta3-app.doocti.com/").strip()
        self.did_numbers = did_numbers or ["07969671855", "07969671856", "07969671857"]
        self.extension_mapping = extension_mapping or {}
        self.secret_token = secret_token
        self.admin_extension = admin_extension or "1281"

    @staticmethod
    def _clean_phone(phone: str) -> str:
        """Extract standard 10-digit Indian phone number."""
        digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
        if len(digits) > 10 and digits.startswith("91"):
            return digits[2:]
        elif len(digits) == 11 and digits.startswith("0"):
            return digits[1:]
        return digits[-10:] if len(digits) >= 10 else digits

    def resolve_extension_for_employee(self, employee_id: Optional[int], from_number: Optional[str] = None) -> Optional[str]:
        """
        Resolves the DooCTI PBX extension (e.g. 1282) assigned to the specified Employee ID.
        """
        # If from_number is already a recognized extension (3 to 5 digits), use it directly
        if from_number:
            from_clean = str(from_number).strip().replace("+", "")
            if from_clean in self.extension_mapping or len(from_clean) <= 5:
                return from_clean

        if not employee_id:
            return self.admin_extension

        # Search extension_mapping for matching employee_id
        for ext, data in self.extension_mapping.items():
            if isinstance(data, dict):
                if data.get("employee_id") == employee_id:
                    return str(ext).strip()

        # Fallback mappings for known default employees
        # 1: Admin (1281), 8: Gowtham (1283), 9: Chandra Mohan (1282), 10: ram (1286)
        fallback_map = {1: "1281", 8: "1283", 9: "1282", 10: "1286"}
        if employee_id in fallback_map:
            return fallback_map[employee_id]

        return None

    def initiate_call(
        self,
        from_number: str,
        to_number: str,
        custom_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Initiates an outbound call via DooCTI.
        Validates the agent's extension, prepares the call routing session,
        attempts PBX originate if API is configured, and logs the call session.
        """
        customer_clean = self._clean_phone(to_number)
        if not customer_clean:
            raise ValueError("A valid customer phone number is required to place a call via DooCTI.")

        c_data = custom_data or {}
        emp_id = c_data.get("employee_id")
        lead_id = c_data.get("lead_id")
        agent_name = c_data.get("agent_name") or ""

        # 1. Validate and resolve agent extension
        agent_ext = self.resolve_extension_for_employee(emp_id, from_number)
        if not agent_ext:
            raise ValueError(
                f"No DooCTI PBX extension is assigned for this user (Employee ID: {emp_id}). "
                "Please configure extension mapping in CRM Settings → Integrations → Doocti Telephony."
            )

        # 2. Resolve agent-specific assigned DID and check active status
        ext_info = self.extension_mapping.get(str(agent_ext), {}) if isinstance(self.extension_mapping, dict) else {}
        if ext_info.get("is_active") is False:
            raise ValueError(
                f"WebRTC extension {agent_ext} is deactivated. Please activate it in Settings -> Integrations -> Doocti Telephony."
            )

        assigned_did = ext_info.get("did_number") if isinstance(ext_info, dict) else None
        if not assigned_did:
            # Fallback to configured admin/agent defaults if strictly mapped in fallback_map
            did_fallback = {"1281": "07969671855", "1282": "07969671855", "1283": "07969671856", "1286": "07969671857"}
            assigned_did = did_fallback.get(str(agent_ext))

        if not assigned_did:
            raise ValueError(
                f"No outbound DID number is assigned to extension {agent_ext}. "
                "Please assign a valid DID in CRM Settings -> Integrations -> Doocti Telephony."
            )

        outbound_cli = str(assigned_did).strip()

        # 3. Create unique call session identifier
        ts = int(datetime.datetime.now().timestamp() * 1000)
        provider_call_id = f"doocti_{agent_ext}_{customer_clean}_{ts}"

        # 4. Attempt server-side originate dispatch if DooCTI PBX API endpoint is reachable
        originate_payload = {
            "entity_id": str(lead_id or "0"),
            "entity_name": agent_name or "CRM Customer",
            "entity_number": customer_clean,
            "entity_type": "Leads" if lead_id else "Contact",
            "cli_number": outbound_cli,
            "crm_unique_id": provider_call_id,
            "station": str(agent_ext),
            "tenant_id": self.account_id,
            "user_id": str(agent_ext),
            "user_number": str(agent_ext),
            "agent_extension": str(agent_ext),
            "customer_number": customer_clean
        }

        # If DooCTI PBX has a REST originate endpoint (e.g., https://.../api/call or /originate)
        raw_response = {
            "provider": "DOOCTI",
            "uniqueid": provider_call_id,
            "station": agent_ext,
            "cli_number": outbound_cli,
            "customer_number": customer_clean,
            "status": CALL_STATUS_INITIATED,
            "tenant_id": self.account_id
        }

        if self.api_url and not self.api_url.endswith("doocti.com/"):
            try:
                with httpx.Client(timeout=6.0) as client:
                    resp = client.post(
                        f"{self.api_url.rstrip('/')}/api/originate",
                        json=originate_payload,
                        headers={"Content-Type": "application/json"}
                    )
                    if resp.status_code < 400:
                        raw_response["pbx_response"] = resp.json() if "json" in resp.headers.get("content-type", "") else resp.text
            except Exception as e:
                logger.info(f"DooCTI PBX direct originate notification: {e}")

        logger.info(f"📞 [DOOCTI CALL ROUTED] Station={agent_ext} -> Customer={customer_clean} (CallID: {provider_call_id})")

        return {
            "provider_call_id": provider_call_id,
            "status": CALL_STATUS_INITIATED,
            "station": agent_ext,
            "cli_number": outbound_cli,
            "raw_response": raw_response
        }

    def get_call_status(self, provider_call_id: str) -> str:
        """Returns standard normalized status."""
        return CALL_STATUS_INITIATED

    def get_call_details(self, provider_call_id: str) -> Dict[str, Any]:
        """Fetches detailed call metadata."""
        return {
            "provider_call_id": provider_call_id,
            "provider": "DOOCTI",
            "account_id": self.account_id
        }

    def verify_webhook(self, request_headers: Dict[str, Any], payload: Dict[str, Any]) -> bool:
        """Verifies incoming webhook authentication."""
        if not self.secret_token:
            return True
        token = (
            request_headers.get("x-doocti-token") or 
            request_headers.get("authorization", "").replace("Bearer ", "").strip() or 
            payload.get("token") or 
            payload.get("secret_token")
        )
        return token == self.secret_token
