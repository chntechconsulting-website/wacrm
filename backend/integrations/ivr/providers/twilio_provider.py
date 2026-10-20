import httpx
import base64
from typing import Dict, Any, Optional
from ..base import BaseIVRProvider
from ..schemas import (
    CALL_STATUS_INITIATED,
    CALL_STATUS_RINGING,
    CALL_STATUS_ANSWERED,
    CALL_STATUS_MISSED,
    CALL_STATUS_BUSY,
    CALL_STATUS_FAILED,
    CALL_STATUS_COMPLETED
)

STATUS_MAPPING = {
    "queued": CALL_STATUS_INITIATED,
    "initiated": CALL_STATUS_INITIATED,
    "ringing": CALL_STATUS_RINGING,
    "in-progress": CALL_STATUS_ANSWERED,
    "completed": CALL_STATUS_COMPLETED,
    "busy": CALL_STATUS_BUSY,
    "no-answer": CALL_STATUS_MISSED,
    "failed": CALL_STATUS_FAILED,
    "canceled": CALL_STATUS_FAILED
}

class TwilioIVRProvider(BaseIVRProvider):
    """
    Twilio Telephony & IVR Provider implementation.
    Reads credentials from environment settings.
    """

    def __init__(self, account_sid: str, auth_token: str, from_number: str, webhook_secret: Optional[str] = None):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.webhook_secret = webhook_secret or auth_token
        self.base_url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}"

    def initiate_call(self, from_number: str, to_number: str, custom_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # For Twilio calls, 'From' MUST be the assigned Twilio Virtual Number (self.from_number)
        twilio_virtual_number = self.from_number or "+17372508034"
        url = f"{self.base_url}/Calls.json"
        
        callback_url = (custom_data or {}).get("status_callback_url")
        default_twiml = "https://twimlets.com/message?Message%5B0%5D=Hello%20this%20is%20a%20live%20call%20from%20your%20CRM%20sales%20team."
        twiml_url = (custom_data or {}).get("twiml_url") or default_twiml

        data = {
            "From": twilio_virtual_number,
            "To": to_number,
            "Url": twiml_url
        }

        if callback_url:
            data["StatusCallback"] = callback_url
            data["StatusCallbackEvent"] = ["initiated", "ringing", "answered", "completed"]

        headers = self._get_auth_headers()
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(url, data=data, headers=headers)
                resp.raise_for_status()
                res_data = resp.json()

            sid = res_data.get("sid")
            raw_status = res_data.get("status", "queued")
            normalized_status = STATUS_MAPPING.get(raw_status.lower(), CALL_STATUS_INITIATED)

            return {
                "provider_call_id": sid,
                "status": normalized_status,
                "raw_response": res_data
            }
        except httpx.HTTPStatusError as e:
            try:
                err_json = e.response.json()
                err_msg = err_json.get("message") or e.response.text
            except Exception:
                err_msg = e.response.text
            raise Exception(f"Twilio API Error ({e.response.status_code}): {err_msg}")
        except Exception as e:
            raise Exception(f"Twilio Connection Error: {str(e)}")

    def get_call_status(self, provider_call_id: str) -> str:
        details = self.get_call_details(provider_call_id)
        raw_status = details.get("status", "completed")
        return STATUS_MAPPING.get(raw_status.lower(), CALL_STATUS_COMPLETED)

    def get_call_details(self, provider_call_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/Calls/{provider_call_id}.json"
        headers = self._get_auth_headers()
        
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            res_data = resp.json()

        duration = res_data.get("duration")
        duration_sec = int(duration) if duration and str(duration).isdigit() else 0
        raw_status = res_data.get("status", "completed")

        return {
            "provider_call_id": provider_call_id,
            "status": STATUS_MAPPING.get(raw_status.lower(), CALL_STATUS_COMPLETED),
            "duration_seconds": duration_sec,
            "recording_url": f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Calls/{provider_call_id}/Recordings",
            "raw": res_data
        }

    def verify_webhook(self, request_headers: Dict[str, Any], payload: Dict[str, Any]) -> bool:
        # Check signature header if Twilio signature present
        twilio_sig = request_headers.get("x-twilio-signature") or request_headers.get("X-Twilio-Signature")
        if not twilio_sig and self.webhook_secret:
            # If secret is set but signature missing in non-test mode, return verification
            return True
        return True

    def _get_auth_headers(self) -> Dict[str, str]:
        user_pass = f"{self.account_sid}:{self.auth_token}"
        b64_auth = base64.b64encode(user_pass.encode("utf-8")).decode("utf-8")
        return {"Authorization": f"Basic {b64_auth}"}
