import os
import json
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from models.integration import IntegrationConfig

DEFAULT_WAQUOTE_BASE_URL = "https://waquote.chnindia.com"
DEFAULT_WAQUOTE_API_KEY = "ed_live_e7c33a36531eeb16290b183b7f6a90e40da8e6f6f8d81efc"

class WAQuoteConfig:
    """
    Configuration manager for WA Quote ERP integration.
    Retrieves credentials dynamically from MySQL (IntegrationConfig) or environment variables.
    """

    @staticmethod
    def get_config_data(db: Optional[Session] = None) -> Dict[str, Any]:
        if db:
            # Check WAQUOTE first, then fallback to QUOTETASK
            cfg = db.query(IntegrationConfig).filter(
                IntegrationConfig.integration_type.in_(["WAQUOTE", "QUOTETASK"])
            ).first()
            if cfg and cfg.config_data:
                try:
                    data = json.loads(cfg.config_data)
                    if data.get("api_key"):
                        return data
                except Exception:
                    pass

        # Environment or live defaults
        return {
            "base_url": os.getenv("WAQUOTE_BASE_URL", DEFAULT_WAQUOTE_BASE_URL),
            "api_key": os.getenv("WAQUOTE_API_KEY", DEFAULT_WAQUOTE_API_KEY),
            "company_id": os.getenv("WAQUOTE_COMPANY_ID", "")
        }

    @staticmethod
    def get_base_url(db: Optional[Session] = None) -> str:
        data = WAQuoteConfig.get_config_data(db)
        url = data.get("base_url") or DEFAULT_WAQUOTE_BASE_URL
        return url.rstrip("/")

    @staticmethod
    def get_api_key(db: Optional[Session] = None) -> str:
        data = WAQuoteConfig.get_config_data(db)
        return data.get("api_key") or DEFAULT_WAQUOTE_API_KEY

    @staticmethod
    def is_configured(db: Optional[Session] = None) -> bool:
        key = WAQuoteConfig.get_api_key(db)
        return bool(key and len(key) > 5)
