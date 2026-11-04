"""
Configuration for the dedicated Meta Click-to-WhatsApp ad lead webhook.

New environment variables (preferred):
  WHATSAPP_AD_VERIFY_TOKEN
  WHATSAPP_AD_APP_SECRET
  WHATSAPP_AD_ACCESS_TOKEN
  WHATSAPP_AD_BUSINESS_ACCOUNT_ID
  WHATSAPP_AD_API_VERSION
  META_MARKETING_ACCESS_TOKEN
  WHATSAPP_AD_MIRROR_INBOX

To avoid breaking an existing WhatsApp Cloud API setup, the module falls back
to the existing WHATSAPP_* / META_* values where it is safe to do so. Secrets
are read from the environment (or the existing encrypted integration config);
they are never returned by any API response.
"""

import os
from typing import Optional


def _env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return default


class WhatsAppAdConfig:
    @staticmethod
    def get_verify_token() -> str:
        try:
            from integrations.whatsapp.config import WhatsAppConfig

            fallback = WhatsAppConfig.get_verify_token()
        except Exception:
            fallback = "wa_crm_verify_token_2026"
        return _env("WHATSAPP_AD_VERIFY_TOKEN", "WHATSAPP_VERIFY_TOKEN", default=fallback)

    @staticmethod
    def get_app_secret() -> str:
        value = _env("WHATSAPP_AD_APP_SECRET", "META_APP_SECRET")
        if value:
            return value
        try:
            from config import settings

            if settings.META_APP_SECRET:
                return settings.META_APP_SECRET
        except Exception:
            pass
        try:
            from integrations.meta.config import MetaConfig

            return MetaConfig.get_app_secret() or ""
        except Exception:
            return ""

    @staticmethod
    def get_access_token() -> str:
        value = _env("WHATSAPP_AD_ACCESS_TOKEN", "WHATSAPP_API_TOKEN", "META_ACCESS_TOKEN")
        if value:
            return value
        try:
            from integrations.whatsapp.config import WhatsAppConfig

            return WhatsAppConfig.get_api_token()
        except Exception:
            return ""

    @staticmethod
    def get_app_secrets() -> list[str]:
        """Every Meta app secret that may sign this webhook.

        Lead Ads and coexistence can run under different Meta apps (for example,
        a legacy lead app and a dedicated review app). Meta signs each delivery
        with the secret of the app subscribed to that WABA, so the shared
        endpoint must accept either configured secret.
        """
        secrets = []
        primary = WhatsAppAdConfig.get_app_secret()
        if primary:
            secrets.append(primary)
        try:
            from integrations.whatsapp_coexistence.config import (
                WhatsAppCoexistenceConfig,
            )

            coexistence = WhatsAppCoexistenceConfig.get_app_secret()
            if coexistence and coexistence not in secrets:
                secrets.append(coexistence)
        except Exception:
            pass
        return secrets

    @staticmethod
    def get_marketing_access_token() -> str:
        return _env(
            "META_MARKETING_ACCESS_TOKEN",
            "WHATSAPP_AD_ACCESS_TOKEN",
            "META_ACCESS_TOKEN",
        ) or WhatsAppAdConfig.get_access_token()

    @staticmethod
    def get_business_account_id() -> str:
        value = _env("WHATSAPP_AD_BUSINESS_ACCOUNT_ID", "WHATSAPP_BUSINESS_ACCOUNT_ID")
        if value:
            return value
        try:
            from integrations.whatsapp.config import WhatsAppConfig

            return WhatsAppConfig.get_business_account_id()
        except Exception:
            return ""

    @staticmethod
    def get_api_version() -> str:
        # Keep this module independent from the older integration defaults,
        # which may still point at retired Graph API versions. Set an explicit
        # value only when Meta changes the current version.
        return _env("WHATSAPP_AD_API_VERSION", default="v26.0")

    @staticmethod
    def get_graph_url(path: str) -> str:
        return (
            f"https://graph.facebook.com/{WhatsAppAdConfig.get_api_version()}/"
            f"{path.lstrip('/')}"
        )

    @staticmethod
    def mirror_inbox_enabled() -> bool:
        raw = os.getenv("WHATSAPP_AD_MIRROR_INBOX")
        if raw is None or str(raw).strip() == "":
            return True
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def signature_verification_configured() -> bool:
        return bool(WhatsAppAdConfig.get_app_secrets())

    @staticmethod
    def marketing_resolution_configured() -> bool:
        return bool(
            WhatsAppAdConfig.get_marketing_access_token()
            and WhatsAppAdConfig.get_api_version()
        )

    @staticmethod
    def masked_access_token() -> Optional[str]:
        token = WhatsAppAdConfig.get_access_token()
        if not token:
            return None
        if len(token) <= 8:
            return "*" * len(token)
        return f"{token[:4]}...{token[-4:]}"
