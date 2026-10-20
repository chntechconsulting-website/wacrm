import logging
import httpx
from typing import Dict, Any, Optional
from ..config import WhatsAppConfig
from .base import BaseWhatsAppProvider

logger = logging.getLogger("whatsapp_cloud_api")

class MetaWhatsAppCloudProvider(BaseWhatsAppProvider):
    """
    Implementation of Meta WhatsApp Business Cloud API Provider.
    Sends text, template, and media messages using graph.facebook.com endpoints.
    """

    def _get_url(self) -> str:
        version = WhatsAppConfig.get_api_version()
        phone_id = WhatsAppConfig.get_phone_number_id()
        return f"https://graph.facebook.com/{version}/{phone_id}/messages"

    def _get_headers(self) -> Dict[str, str]:
        token = WhatsAppConfig.get_api_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def _clean_phone(self, phone: str) -> str:
        cleaned = "".join(filter(str.isdigit, phone))
        return cleaned

    def send_text_message(self, to_phone: str, text: str) -> Dict[str, Any]:
        if not WhatsAppConfig.is_configured():
            logger.warning("WhatsApp API token/phone ID is not configured in .env")
            return {"success": False, "error": "WhatsApp credentials not configured in .env"}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self._clean_phone(to_phone),
            "type": "text",
            "text": {
                "preview_url": True,
                "body": text
            }
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(self._get_url(), headers=self._get_headers(), json=payload)
                resp_json = resp.json()
                if resp.status_code == 200:
                    msg_id = resp_json.get("messages", [{}])[0].get("id")
                    return {"success": True, "message_id": msg_id, "response": resp_json}
                else:
                    err_msg = resp_json.get("error", {}).get("message", "API Error")
                    logger.error(f"WhatsApp API Error ({resp.status_code}): {resp_json}")
                    return {"success": False, "error": err_msg, "response": resp_json}
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message to {to_phone}: {e}")
            return {"success": False, "error": str(e)}

    def send_template_message(
        self, 
        to_phone: str, 
        template_name: str, 
        language_code: str = "en_US",
        components: Optional[list] = None
    ) -> Dict[str, Any]:
        if not WhatsAppConfig.is_configured():
            return {"success": False, "error": "WhatsApp credentials not configured in .env"}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self._clean_phone(to_phone),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code}
            }
        }
        if components:
            payload["template"]["components"] = components

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(self._get_url(), headers=self._get_headers(), json=payload)
                resp_json = resp.json()
                if resp.status_code == 200:
                    msg_id = resp_json.get("messages", [{}])[0].get("id")
                    return {"success": True, "message_id": msg_id, "response": resp_json}
                else:
                    err_msg = resp_json.get("error", {}).get("message", "API Error")
                    return {"success": False, "error": err_msg}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def send_media_message(
        self, 
        to_phone: str, 
        media_type: str, 
        media_url: str, 
        caption: Optional[str] = None
    ) -> Dict[str, Any]:
        if not WhatsAppConfig.is_configured():
            return {"success": False, "error": "WhatsApp credentials not configured in .env"}

        m_type = media_type.lower()
        if m_type not in ["image", "document", "audio", "video"]:
            m_type = "document"

        media_obj = {"link": media_url}
        if caption and m_type in ["image", "document", "video"]:
            media_obj["caption"] = caption

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self._clean_phone(to_phone),
            "type": m_type,
            m_type: media_obj
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(self._get_url(), headers=self._get_headers(), json=payload)
                resp_json = resp.json()
                if resp.status_code == 200:
                    msg_id = resp_json.get("messages", [{}])[0].get("id")
                    return {"success": True, "message_id": msg_id, "response": resp_json}
                else:
                    err_msg = resp_json.get("error", {}).get("message", "API Error")
                    return {"success": False, "error": err_msg}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def verify_webhook(self, mode: str, token: str, challenge: str) -> Optional[str]:
        expected_token = WhatsAppConfig.get_verify_token()
        if mode == "subscribe" and token == expected_token:
            return challenge
        return None
