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
        return val or "v26.0"

    @staticmethod
    def get_graph_base() -> str:
        return f"https://graph.facebook.com/{MetaConfig.get_api_version()}"

    @staticmethod
    def get_public_base_url() -> str:
        return (
            os.getenv("PUBLIC_BASE_URL")
            or getattr(settings, "PUBLIC_BASE_URL", "")
            or "https://www.wapluscrm.in"
        ).rstrip("/")

    @staticmethod
    def get_oauth_redirect_uri() -> str:
        """Backend OAuth callback. Must match the Meta App's Valid OAuth URI."""
        explicit = os.getenv("META_OAUTH_REDIRECT_URI", "").strip()
        if explicit:
            return explicit
        return f"{MetaConfig.get_public_base_url()}/api/integrations/meta/oauth/callback"

    @staticmethod
    def get_frontend_redirect_uri() -> str:
        explicit = os.getenv("META_OAUTH_FRONTEND_REDIRECT", "").strip()
        if explicit:
            return explicit
        return f"{MetaConfig.get_public_base_url()}/settings/integrations/meta"

    @staticmethod
    def get_oauth_scopes() -> str:
        """Comma separated OAuth scopes. Override with META_OAUTH_SCOPES."""
        explicit = os.getenv("META_OAUTH_SCOPES", "").strip()
        if explicit:
            return explicit
        return ",".join([
            "pages_show_list",
            "pages_read_engagement",
            "pages_manage_metadata",
            "leads_retrieval",
            "ads_read",
            "instagram_basic",
        ])

    @staticmethod
    def get_webhook_url() -> str:
        explicit = os.getenv("META_WEBHOOK_URL", "").strip()
        if explicit:
            return explicit
        return f"{MetaConfig.get_public_base_url()}/api/integrations/meta/webhook"

    @staticmethod
    def signature_verification_configured() -> bool:
        return bool(MetaConfig.get_app_secret())

    @staticmethod
    def oauth_configured() -> bool:
        return bool(MetaConfig.get_app_id() and MetaConfig.get_app_secret())

    @staticmethod
    def is_configured() -> bool:
        token = MetaConfig.get_access_token()
        page_id = MetaConfig.get_page_id()
        return bool(token and page_id and len(token) > 10)
