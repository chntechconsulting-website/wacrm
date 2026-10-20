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

logger = logging.getLogger("cloudshope_ivr")

class CloudShopeIVRProvider(BaseIVRProvider):
    """
    Native CloudShope Telephony & Click-to-Call Integration Provider for WaCRM.
    Handles Outbound Click-to-Call bridging via CloudShope API and CDR webhooks.
    """

    def __init__(
        self,
        api_key: str = "",
        virtual_number: str = "1204362938",
        api_url: str = "",
        account_sid: str = ""
    ):
        self.api_key = api_key.strip()
        self.virtual_number = virtual_number.strip() or "1204362938"
        self.api_url = (api_url or "").strip() or "http://yourmessageapi.com/clicktocall.php"
        self.account_sid = account_sid.strip() or "cloudshope"

    @staticmethod
    def _clean_phone(phone: str) -> str:
        """Strip non-numeric characters, return standard 10-digit Indian number if possible"""
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
        Initiates an outbound Click-to-Call bridging the agent and the customer
        via CloudShope's Click-to-Call API.
        """
        agent_clean = self._clean_phone(from_number)
        customer_clean = self._clean_phone(to_number)

        if not customer_clean:
            raise ValueError("Customer phone number is required to place a call.")

        # Check if real outbound API credentials are provided
        has_real_key = bool(self.api_key and not self.api_key.startswith("http") and "%" not in self.api_key)
        has_real_url = bool(self.api_url and not "yourmessageapi.com" in self.api_url and self.api_url.startswith("http"))

        if not has_real_key or not has_real_url:
            raise ValueError(
                "CloudShope Outbound Click-to-Call requires your account's Click-to-Call API URL and Auth Key "
                "in Settings -> Integrations. (Note: The Webhook URL in your screenshot is for INCOMING calls only)."
            )

        params = {
            "authkey": self.api_key,
            "api_key": self.api_key,
            "agent": agent_clean,
            "agent_number": agent_clean,
            "customer": customer_clean,
            "customer_number": customer_clean,
            "caller_id": self.virtual_number,
            "did": self.virtual_number,
            "custom": (custom_data or {}).get("lead_id", "")
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(self.api_url, params=params)
                logger.info(f"CloudShope Click-to-Call response status={resp.status_code}, body={resp.text[:200]}")
                
                data = {}
                try:
                    data = resp.json()
                except Exception:
                    data = {"text": resp.text}

                # Extract unique call id if returned by CloudShope
                unique_id = (
                    data.get("uniqueid") or 
                    data.get("call_id") or 
                    data.get("id") or 
                    f"CS_{uuid.uuid4().hex[:10].upper()}"
                )

                return {
                    "provider_call_id": str(unique_id),
                    "status": CALL_STATUS_INITIATED,
                    "raw_response": data
                }
        except Exception as e:
            logger.error(f"CloudShope API request failed: {e}")
            raise ValueError(f"CloudShope Click-to-Call request failed: {str(e)}")

    def get_call_status(self, provider_call_id: str) -> str:
        return CALL_STATUS_ANSWERED

    def get_call_details(self, provider_call_id: str) -> Dict[str, Any]:
        return {
            "provider_call_id": provider_call_id,
            "status": CALL_STATUS_ANSWERED
        }

    def verify_webhook(self, request_headers: Dict[str, Any], payload: Dict[str, Any]) -> bool:
        return True
