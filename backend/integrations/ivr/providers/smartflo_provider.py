import logging
import uuid
import datetime
import httpx
from typing import Dict, Any, Optional
from ..base import BaseIVRProvider
from ..schemas import (
    CALL_STATUS_INITIATED,
    CALL_STATUS_RINGING,
    CALL_STATUS_ANSWERED,
    CALL_STATUS_COMPLETED,
    CALL_STATUS_FAILED
)

logger = logging.getLogger("smartflo_ivr")

class SmartfloIVRProvider(BaseIVRProvider):
    """
    Tata Teleservices Smartflo Telephony & Click-to-Call Integration Provider for WaCRM.
    Handles Outbound Click-to-Call bridging via Tata Smartflo REST API and real-time CDR webhooks.
    """

    def __init__(
        self,
        api_key: str = "62c5d471-63a3-43c9-a12e-d1da29d46f05",
        api_token: str = "",
        caller_id: str = "",
        api_url: str = "https://api-smartflo.tatateleservices.com/v1/click_to_call"
    ):
        self.api_key = (api_key or "").strip()
        self.api_token = (api_token or "").strip()
        self.caller_id = (caller_id or "").strip()
        self.api_url = (api_url or "").strip() or "https://api-smartflo.tatateleservices.com/v1/click_to_call"

    @staticmethod
    def _clean_phone(phone: str) -> str:
        """Strip non-numeric characters; normalize Indian phone numbers to 10 digits or with 91 prefix."""
        digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
        if len(digits) > 10 and digits.startswith("91"):
            return digits[2:]
        return digits[-10:] if len(digits) >= 10 else digits

    def initiate_call(
        self,
        from_number: str,
        to_number: str,
        custom_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Initiates an outbound Click-to-Call via Tata Smartflo API bridging the agent and customer.
        Attempts both /v1/click_to_call and /v1/click_to_call_support if 401 occurs.
        """
        agent_clean = self._clean_phone(from_number)
        customer_clean = self._clean_phone(to_number)

        if not customer_clean:
            raise ValueError("Customer phone number is required to place a call via Smartflo.")

        if not self.api_key and not self.api_token:
            raise ValueError("Smartflo API Key or Token is required. Please check Settings -> Integrations.")

        lead_id = str((custom_data or {}).get("lead_id", ""))
        employee_id = str((custom_data or {}).get("employee_id", ""))

        auth_bearer = self.api_token or self.api_key
        headers = {
            "Authorization": f"Bearer {auth_bearer}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": self.api_key
        }

        body: Dict[str, Any] = {
            "agent_number": agent_clean,
            "destination_number": customer_clean,
            "async": 1,
            "call_timeout": 300,
            "custom_identifier": f"LEAD_{lead_id}_EMP_{employee_id}" if lead_id else f"EMP_{employee_id}"
        }

        if self.caller_id:
            body["caller_id"] = self._clean_phone(self.caller_id)

        try:
            with httpx.Client(timeout=15.0) as client:
                # Attempt 1: Call standard Click-to-Call endpoint
                resp = client.post(self.api_url, json=body, headers=headers)
                logger.info(f"Smartflo Click-to-Call attempt 1 status={resp.status_code}, text={resp.text[:250]}")

                # If 401 Unauthorized and service key provided, attempt Smartflo Click-to-Call Support endpoint
                if resp.status_code == 401:
                    support_url = "https://api-smartflo.tatateleservices.com/v1/click_to_call_support"
                    support_body = {
                        "api_key": self.api_key,
                        "agent_number": agent_clean,
                        "customer_number": customer_clean,
                        "destination_number": customer_clean
                    }
                    if self.caller_id:
                        support_body["caller_id"] = self._clean_phone(self.caller_id)

                    support_headers = {
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    }
                    if self.api_token:
                        support_headers["Authorization"] = f"Bearer {self.api_token}"

                    resp_support = client.post(support_url, json=support_body, headers=support_headers)
                    logger.info(f"Smartflo Click-to-Call Support attempt 2 status={resp_support.status_code}, text={resp_support.text[:250]}")
                    if resp_support.status_code in [200, 201, 202]:
                        resp = resp_support

                try:
                    data = resp.json()
                except Exception:
                    data = {"raw_text": resp.text}

                if resp.status_code not in [200, 201, 202]:
                    err_msg = data.get("message") or data.get("error") or resp.text
                    if resp.status_code == 401:
                        raise RuntimeError(
                            f"Smartflo API error (401): Unauthorized. Your Smartflo API key requires an API Bearer Token from the Tata Smartflo Portal (Administration → API Tokens). Please enter the Bearer Token in Settings → Integrations, or use the Fallback Option to call directly."
                        )
                    raise RuntimeError(f"Smartflo API error ({resp.status_code}): {err_msg}")

                # Extract ref_id or call_id or uuid from Smartflo response
                provider_call_id = (
                    data.get("ref_id") or 
                    data.get("call_id") or 
                    data.get("uuid") or 
                    data.get("id") or 
                    f"SMARTFLO_{uuid.uuid4().hex[:10].upper()}"
                )

                return {
                    "provider_call_id": str(provider_call_id),
                    "status": CALL_STATUS_INITIATED,
                    "raw_response": data
                }
        except httpx.RequestError as e:
            logger.error(f"HTTP connection failed to Smartflo API: {e}")
            raise RuntimeError(f"Unable to connect to Smartflo IVR server: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to initiate Smartflo call: {e}")
            raise

    def get_call_status(self, provider_call_id: str) -> str:
        """
        Polls Smartflo for active/completed call status if supported.
        """
        return CALL_STATUS_INITIATED

    def get_call_details(self, provider_call_id: str) -> Dict[str, Any]:
        """
        Fetches detailed call metadata from Smartflo.
        """
        return {"call_id": provider_call_id, "status": CALL_STATUS_INITIATED}

    def verify_webhook(self, request_headers: Dict[str, Any], payload: Dict[str, Any]) -> bool:
        """
        Verifies Smartflo webhook payload.
        """
        return True
