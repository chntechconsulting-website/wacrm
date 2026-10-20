import os
import json

class WhatsAppConfig:
    @classmethod
    def _get_db_config(cls) -> dict:
        try:
            from database import SessionLocal
            from models.integration import IntegrationConfig
            db = SessionLocal()
            try:
                cfg = db.query(IntegrationConfig).filter(IntegrationConfig.integration_type == "WHATSAPP").first()
                if cfg and cfg.config_data:
                    return json.loads(cfg.config_data)
            finally:
                db.close()
        except Exception:
            pass
        return {}

    @staticmethod
    def get_api_token() -> str:
        val = os.getenv("WHATSAPP_API_TOKEN", "")
        if not val:
            val = WhatsAppConfig._get_db_config().get("access_token", "")
        return val

    @staticmethod
    def get_phone_number_id() -> str:
        val = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
        if not val:
            val = WhatsAppConfig._get_db_config().get("phone_number_id", "")
        return val

    @staticmethod
    def get_business_account_id() -> str:
        val = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID", "")
        if not val:
            val = WhatsAppConfig._get_db_config().get("business_account_id", "")
        return val

    @staticmethod
    def get_verify_token() -> str:
        val = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
        if not val:
            val = WhatsAppConfig._get_db_config().get("verify_token", "")
        return val or "wa_crm_verify_token_2026"

    @staticmethod
    def get_api_version() -> str:
        val = os.getenv("WHATSAPP_API_VERSION", "")
        if not val:
            val = WhatsAppConfig._get_db_config().get("api_version", "")
        return val or "v20.0"

    @classmethod
    def is_configured(cls) -> bool:
        return bool(cls.get_api_token() and cls.get_phone_number_id())
