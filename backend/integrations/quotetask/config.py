import os
import json
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from models.integration import IntegrationConfig

class QuoteTaskConfig:
    """
    Configuration manager for QuoteTask integration module.
    Loads credentials and base URLs dynamically from database (IntegrationConfig) or environment fallbacks.
    """
    @staticmethod
    def get_config_data(db: Optional[Session] = None) -> Dict[str, Any]:
        if db:
            cfg = db.query(IntegrationConfig).filter(IntegrationConfig.integration_type == "QUOTETASK").first()
            if cfg and cfg.config_data:
                try:
                    return json.loads(cfg.config_data)
                except Exception:
                    pass
        
        # Fallback to env variables
        return {
            "base_url": os.getenv("QUOTETASK_BASE_URL", "https://api.quotetask.app"),
            "api_key": os.getenv("QUOTETASK_API_KEY", ""),
            "company_id": os.getenv("QUOTETASK_COMPANY_ID", "default_company"),
            "webhook_secret": os.getenv("QUOTETASK_WEBHOOK_SECRET", "qt_webhook_sec_secret123")
        }

    @staticmethod
    def get_base_url(db: Optional[Session] = None) -> str:
        data = QuoteTaskConfig.get_config_data(db)
        return (data.get("base_url") or "https://api.quotetask.app").rstrip("/")

    @staticmethod
    def get_api_key(db: Optional[Session] = None) -> str:
        data = QuoteTaskConfig.get_config_data(db)
        return data.get("api_key") or ""

    @staticmethod
    def get_company_id(db: Optional[Session] = None) -> str:
        data = QuoteTaskConfig.get_config_data(db)
        return data.get("company_id") or "default_company"

    @staticmethod
    def get_webhook_secret(db: Optional[Session] = None) -> str:
        data = QuoteTaskConfig.get_config_data(db)
        return data.get("webhook_secret") or "qt_webhook_sec_secret123"

    @staticmethod
    def is_configured(db: Optional[Session] = None) -> bool:
        api_key = QuoteTaskConfig.get_api_key(db)
        return bool(api_key and len(api_key) > 3)
