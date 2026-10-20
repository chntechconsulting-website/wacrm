import uuid
import datetime
from typing import Dict, Any, Optional
from ..base import BaseIVRProvider
from ..schemas import (
    CALL_STATUS_INITIATED,
    CALL_STATUS_RINGING,
    CALL_STATUS_ANSWERED,
    CALL_STATUS_COMPLETED
)

class MockIVRProvider(BaseIVRProvider):
    """
    Mock IVR Provider for development and automated testing environment.
    Generates realistic call IDs and status metadata.
    """

    def __init__(self, account_sid: str = "mock_sid", auth_token: str = "mock_token", from_number: str = "+18005550199"):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.active_calls: Dict[str, Dict[str, Any]] = {}

    def initiate_call(self, from_number: str, to_number: str, custom_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        call_id = f"MOCK_CALL_{uuid.uuid4().hex[:12].upper()}"
        call_meta = {
            "provider_call_id": call_id,
            "from_number": from_number or self.from_number,
            "to_number": to_number,
            "status": CALL_STATUS_INITIATED,
            "created_at": datetime.datetime.utcnow().isoformat(),
            "custom_data": custom_data or {}
        }
        self.active_calls[call_id] = call_meta
        return {
            "provider_call_id": call_id,
            "status": CALL_STATUS_INITIATED,
            "raw_response": call_meta
        }

    def get_call_status(self, provider_call_id: str) -> str:
        details = self.get_call_details(provider_call_id)
        return details.get("status", CALL_STATUS_COMPLETED)

    def get_call_details(self, provider_call_id: str) -> Dict[str, Any]:
        call = self.active_calls.get(provider_call_id)
        if not call:
            return {
                "provider_call_id": provider_call_id,
                "status": CALL_STATUS_COMPLETED,
                "duration_seconds": 35,
                "recording_url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
            }
        
        # Simulate status progression for dev/mock testing if call is still active
        current_status = call.get("status", CALL_STATUS_INITIATED)
        if current_status not in [CALL_STATUS_COMPLETED, "FAILED", "MISSED", "BUSY"]:
            created_at = datetime.datetime.fromisoformat(call["created_at"])
            elapsed = (datetime.datetime.utcnow() - created_at).total_seconds()
            if elapsed < 3:
                call["status"] = CALL_STATUS_INITIATED
            elif elapsed < 7:
                call["status"] = CALL_STATUS_RINGING
            else:
                call["status"] = CALL_STATUS_ANSWERED

        return call

    def verify_webhook(self, request_headers: Dict[str, Any], payload: Dict[str, Any]) -> bool:
        # Mock provider allows testing webhooks without strict HMAC signature requirement
        return True
