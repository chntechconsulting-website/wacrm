from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseWhatsAppProvider(ABC):
    @abstractmethod
    def send_text_message(self, to_phone: str, text: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def send_template_message(
        self, 
        to_phone: str, 
        template_name: str, 
        language_code: str = "en_US",
        components: Optional[list] = None
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def send_media_message(
        self, 
        to_phone: str, 
        media_type: str, 
        media_url: str, 
        caption: Optional[str] = None
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def verify_webhook(self, mode: str, token: str, challenge: str) -> Optional[str]:
        pass
