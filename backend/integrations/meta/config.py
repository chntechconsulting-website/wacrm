import os
import json
from config import settings

class MetaConfig:
    """
    Configuration manager for Meta Lead Ads integration.
    Centralizes credentials loaded from database IntegrationConfig table or .env fallback.
    """
    @classmethod
    def _get_db_config(cls) -> dict:
        try:
            from database import SessionLocal
            from models.integration import IntegrationConfig
            db = SessionLocal()
            try:
                cfg = db.query(IntegrationConfig).filter(IntegrationConfig.integration_type == "META").first()
                if cfg and cfg.config_data:
                    return json.loads(cfg.config_data)
            finally:
                db.close()
        except Exception:
            pass
        return {}

    @staticmethod
    def get_app_id() -> str:
        val = os.getenv("META_APP_ID") or settings.META_APP_ID
        if not val:
            val = MetaConfig._get_db_config().get("app_id", "")
        return val

    @staticmethod
    def get_app_secret() -> str:
        val = os.getenv("META_APP_SECRET") or settings.META_APP_SECRET
        if not val:
            val = MetaConfig._get_db_config().get("app_secret", "")
        return val

    @staticmethod
    def get_access_token() -> str:
        val = os.getenv("META_ACCESS_TOKEN") or settings.META_ACCESS_TOKEN
        if not val:
            val = MetaConfig._get_db_config().get("access_token", "")
        return val

    @staticmethod
    def get_verify_token() -> str:
        val = os.getenv("META_VERIFY_TOKEN") or settings.META_VERIFY_TOKEN
        if not val:
            val = MetaConfig._get_db_config().get("verify_token", "")
        return val or "wacrm_meta_verify_secret"

    @staticmethod
    def get_page_id() -> str:
        val = os.getenv("META_PAGE_ID") or settings.META_PAGE_ID
        if not val:
            val = MetaConfig._get_db_config().get("page_id", "")
        return val

    @staticmethod
    def get_api_version() -> str:
        val = os.getenv("META_API_VERSION") or getattr(settings, "META_API_VERSION", "")
        if not val:
            val = MetaConfig._get_db_config().get("api_version", "")
        return val or "v20.0"

    @staticmethod
    def is_configured() -> bool:
        token = MetaConfig.get_access_token()
        page_id = MetaConfig.get_page_id()
        return bool(token and page_id and len(token) > 10)
