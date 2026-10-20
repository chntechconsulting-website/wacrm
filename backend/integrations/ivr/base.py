from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseIVRProvider(ABC):
    """
    Abstract IVR Provider Interface.
    Any telemetry/IVR provider (Twilio, Exotel, Knowlarity, Mock, etc.)
    must implement these methods to be plugged into WaCRM.
    """

    @abstractmethod
    def initiate_call(
        self, 
        from_number: str, 
        to_number: str, 
        custom_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Initiates a outbound call.
        Must return a dict with:
          - provider_call_id: str
          - status: str (INITIATED, RINGING, etc.)
          - raw_response: dict
        """
        pass

    @abstractmethod
    def get_call_status(self, provider_call_id: str) -> str:
        """
        Returns normalized call status string:
        INITIATED, RINGING, ANSWERED, MISSED, BUSY, FAILED, COMPLETED
        """
        pass

    @abstractmethod
    def get_call_details(self, provider_call_id: str) -> Dict[str, Any]:
        """
        Fetches detailed call metadata from provider API.
        """
        pass

    @abstractmethod
    def verify_webhook(self, request_headers: Dict[str, Any], payload: Dict[str, Any]) -> bool:
        """
        Verifies signature/authenticity of incoming webhook request.
        """
        pass
