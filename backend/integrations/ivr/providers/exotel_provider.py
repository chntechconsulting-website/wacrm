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
    "in-progress": CALL_STATUS_ANSWERED,
    "completed": CALL_STATUS_COMPLETED,
    "busy": CALL_STATUS_BUSY,
    "no-answer": CALL_STATUS_MISSED,
    "failed": CALL_STATUS_FAILED
}

class ExotelIVRProvider(BaseIVRProvider):
    """
    Exotel Telephony / IVR Provider implementation using official Exotel Voice API.
    """

    def __init__(
        self, 
        account_sid: str, 
        auth_token: str, 
        from_number: str = "", 
        api_key: Optional[str] = None, 
        api_token: Optional[str] = None, 
        subdomain: str = "api.exotel.com"
    ):
        self.account_sid = account_sid
        # In Exotel: API Key is HTTP Basic Auth Username, API Token is HTTP Basic Auth Password
        self.api_key = api_key or account_sid
        self.api_token = api_token or auth_token
        self.from_number = from_number
        self.subdomain = subdomain
        self.base_url = f"https://{subdomain}/v1/Accounts/{self.account_sid}"

    def initiate_call(self, from_number: str, to_number: str, custom_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/Calls/connect.json"
        
        # Exotel Click-to-Call parameters:
        # 'From': Employee phone number (or customer number to ring first)
        # 'To': Customer phone number
        # 'CallerId': ExoPhone (virtual business number)
        agent_phone = from_number
        cust_phone = to_number
        exophone = self.from_number or agent_phone
        status_cb = (custom_data or {}).get("status_callback")

        data = {
            "From": agent_phone,
            "To": cust_phone,
            "CallerId": exophone,
            "CallType": "trans"
        }
        if status_cb:
            data["StatusCallback"] = status_cb
            data["StatusCallbackContentType"] = "application/json"

        headers = self._get_auth_headers()
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(url, data=data, headers=headers)
                resp.raise_for_status()
                res_data = resp.json()

            call_data = res_data.get("Call", {})
            sid = call_data.get("Sid") or call_data.get("CallSid")
            raw_status = call_data.get("Status", "queued")

            return {
                "provider_call_id": sid,
                "status": STATUS_MAPPING.get(str(raw_status).lower(), CALL_STATUS_INITIATED),
                "raw_response": res_data
            }
        except httpx.HTTPStatusError as e:
            try:
                err_json = e.response.json()
                err_msg = err_json.get("RestException", {}).get("Message") or e.response.text
            except Exception:
                err_msg = e.response.text
            raise Exception(f"Exotel API Error ({e.response.status_code}): {err_msg}")
        except Exception as e:
            raise Exception(f"Exotel Connection Error: {str(e)}")

    def get_call_status(self, provider_call_id: str) -> str:
        details = self.get_call_details(provider_call_id)
        return details.get("status", CALL_STATUS_COMPLETED)

    def get_call_details(self, provider_call_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/Calls/{provider_call_id}.json"
        headers = self._get_auth_headers()
        
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            res_data = resp.json()

        call_data = res_data.get("Call", {})
        raw_status = call_data.get("Status", "completed")
        duration = call_data.get("Duration", 0)

        return {
            "provider_call_id": provider_call_id,
            "status": STATUS_MAPPING.get(str(raw_status).lower(), CALL_STATUS_COMPLETED),
            "duration_seconds": int(duration) if str(duration).isdigit() else 0,
            "recording_url": call_data.get("RecordingUrl"),
            "raw": res_data
        }

    def verify_webhook(self, request_headers: Dict[str, Any], payload: Dict[str, Any]) -> bool:
        return True

    def _get_auth_headers(self) -> Dict[str, str]:
        user_pass = f"{self.api_key}:{self.api_token}"
        b64_auth = base64.b64encode(user_pass.encode("utf-8")).decode("utf-8")
        return {"Authorization": f"Basic {b64_auth}"}
