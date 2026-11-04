"""Configuration for WhatsApp Business App coexistence onboarding.

Nothing here changes the live WhatsApp account. The feature stays locked until
``WHATSAPP_COEXISTENCE_ENABLED=true`` and a Facebook Login for Business
configuration ID are present.
"""

import os

from typing import Optional


def _env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return default


class WhatsAppCoexistenceConfig:
    # Webhook fields Meta requires for coexistence in addition to ``messages``.
    REQUIRED_WEBHOOK_FIELDS = (
        "messages",
        "account_update",
        "history",
        "smb_app_state_sync",
        "smb_message_echoes",
    )

    # Public configuration IDs are owned by exactly one Meta app. Keep the
    # known owner here so a stale META_APP_ID cannot make the status page claim
    # onboarding is ready when Meta would reject the Embedded Signup exchange.
    KNOWN_CONFIG_APP_IDS = {
        # Staging/test app. Kept for diagnostics and backwards compatibility.
        "1698501728618095": "1158185796552320",
        # Production WhatsApp app "Wacrmwap".
        "2372647743564644": "2041712130118952",
    }

    @staticmethod
    def get_app_id() -> str:
        value = _env("WHATSAPP_COEXISTENCE_APP_ID", "META_APP_ID")
        if value:
            return value
        try:
            from config import settings

            return settings.META_APP_ID or ""
        except Exception:
            return ""

    @staticmethod
    def get_app_secret() -> str:
        explicit = _env("WHATSAPP_COEXISTENCE_APP_SECRET")
        if explicit:
            return explicit

        # ``META_APP_SECRET`` belongs to ``META_APP_ID``. If coexistence points
        # at a different Meta app (for example, a dedicated review app), using
        # the legacy secret would guarantee an OAuth signature failure. Require
        # the matching secret instead of silently reusing the wrong one.
        app_id = WhatsAppCoexistenceConfig.get_app_id()
        meta_app_id = _env("META_APP_ID")
        if app_id and meta_app_id and app_id != meta_app_id:
            return ""

        value = _env("META_APP_SECRET")
        if value:
            return value
        try:
            from config import settings

            if settings.META_APP_SECRET:
                return settings.META_APP_SECRET
        except Exception:
            pass
        try:
            from integrations.whatsapp_ads.config import WhatsAppAdConfig

            return WhatsAppAdConfig.get_app_secret() or ""
        except Exception:
            return ""

    @staticmethod
    def get_config_id() -> str:
        """Facebook Login for Business configuration ID (Embedded Signup v4/v5).

        Configuration IDs are public identifiers, not secrets. The current
        WaCRM Embedded Signup configuration is used as the default so a
        deployment cannot silently lose it; ``WHATSAPP_COEXISTENCE_CONFIG_ID``
        still overrides it for another environment.
        """
        return _env(
            "WHATSAPP_COEXISTENCE_CONFIG_ID",
            default="2372647743564644",
        )

    @staticmethod
    def get_config_owner_app_id() -> str:
        """Return the known owner app for a public configuration ID, if any."""
        return WhatsAppCoexistenceConfig.KNOWN_CONFIG_APP_IDS.get(
            WhatsAppCoexistenceConfig.get_config_id(), ""
        )

    @staticmethod
    def get_api_version() -> str:
        return _env("WHATSAPP_COEXISTENCE_API_VERSION", default="v26.0")

    @staticmethod
    def get_verify_token() -> str:
        try:
            from integrations.whatsapp_ads.config import WhatsAppAdConfig

            fallback = WhatsAppAdConfig.get_verify_token()
        except Exception:
            fallback = "wa_crm_verify_token_2026"
        return _env(
            "WHATSAPP_COEXISTENCE_VERIFY_TOKEN",
            "WHATSAPP_AD_VERIFY_TOKEN",
            "WHATSAPP_VERIFY_TOKEN",
            default=fallback,
        )

    @staticmethod
    def get_callback_url() -> str:
        value = _env("WHATSAPP_COEXISTENCE_CALLBACK_URL")
        if value:
            return value
        try:
            from config import settings

            return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/api/webhook/whatsapp"
        except Exception:
            return ""

    @staticmethod
    def get_sync_deadline_hours() -> int:
        raw = _env("WHATSAPP_COEXISTENCE_SYNC_DEADLINE_HOURS", default="24")
        try:
            return max(1, int(raw))
        except (TypeError, ValueError):
            return 24

    @staticmethod
    def is_enabled() -> bool:
        """Hard safety gate: onboarding must be explicitly enabled."""
        raw = os.getenv("WHATSAPP_COEXISTENCE_ENABLED", "false")
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def is_configured() -> bool:
        app_id = WhatsAppCoexistenceConfig.get_app_id()
        owner_app_id = WhatsAppCoexistenceConfig.get_config_owner_app_id()
        if owner_app_id and app_id != owner_app_id:
            return False
        return bool(
            app_id
            and WhatsAppCoexistenceConfig.get_app_secret()
            and WhatsAppCoexistenceConfig.get_config_id()
        )

    @staticmethod
    def onboarding_ready() -> bool:
        return WhatsAppCoexistenceConfig.is_enabled() and WhatsAppCoexistenceConfig.is_configured()

    @staticmethod
    def graph_url(path: str) -> str:
        return (
            f"https://graph.facebook.com/{WhatsAppCoexistenceConfig.get_api_version()}/"
            f"{path.lstrip('/')}"
        )

    @staticmethod
    def public_config() -> dict:
        """Safe configuration for the admin UI. Never includes the app secret."""
        warnings = []
        if not WhatsAppCoexistenceConfig.is_enabled():
            warnings.append(
                "Onboarding is locked. Set WHATSAPP_COEXISTENCE_ENABLED=true only "
                "when you are ready to connect a real WhatsApp Business App number."
            )
        app_id = WhatsAppCoexistenceConfig.get_app_id()
        owner_app_id = WhatsAppCoexistenceConfig.get_config_owner_app_id()
        if not app_id:
            warnings.append("META_APP_ID / WHATSAPP_COEXISTENCE_APP_ID is missing.")
        elif owner_app_id and app_id != owner_app_id:
            warnings.append(
                f"Facebook Login configuration "
                f"{WhatsAppCoexistenceConfig.get_config_id()} belongs to Meta "
                f"app {owner_app_id}, but this server is using {app_id}. Set "
                "WHATSAPP_COEXISTENCE_APP_ID and WHATSAPP_COEXISTENCE_APP_SECRET "
                f"for app {owner_app_id}."
            )
        if not WhatsAppCoexistenceConfig.get_app_secret():
            app_id = WhatsAppCoexistenceConfig.get_app_id()
            meta_app_id = _env("META_APP_ID")
            if (
                app_id
                and meta_app_id
                and app_id != meta_app_id
                and not _env("WHATSAPP_COEXISTENCE_APP_SECRET")
            ):
                warnings.append(
                    "WHATSAPP_COEXISTENCE_APP_ID differs from META_APP_ID. Set "
                    "WHATSAPP_COEXISTENCE_APP_SECRET to the secret for the "
                    "coexistence app; the legacy META_APP_SECRET is not reused "
                    "across apps."
                )
            else:
                warnings.append(
                    "META_APP_SECRET / WHATSAPP_COEXISTENCE_APP_SECRET is missing."
                )
        if not WhatsAppCoexistenceConfig.get_config_id():
            warnings.append(
                "WHATSAPP_COEXISTENCE_CONFIG_ID is missing. Create a Facebook "
                "Login for Business configuration with WhatsApp Embedded Signup."
            )

        return {
            "enabled": WhatsAppCoexistenceConfig.is_enabled(),
            "configured": WhatsAppCoexistenceConfig.is_configured(),
            "ready": WhatsAppCoexistenceConfig.onboarding_ready(),
            "app_id": WhatsAppCoexistenceConfig.get_app_id() or None,
            "config_id": WhatsAppCoexistenceConfig.get_config_id() or None,
            "api_version": WhatsAppCoexistenceConfig.get_api_version(),
            "callback_url": WhatsAppCoexistenceConfig.get_callback_url() or None,
            "sync_deadline_hours": WhatsAppCoexistenceConfig.get_sync_deadline_hours(),
            "required_webhook_fields": list(
                WhatsAppCoexistenceConfig.REQUIRED_WEBHOOK_FIELDS
            ),
            "warnings": warnings,
        }

    @staticmethod
    def masked_secret(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:2]}***{value[-2:]}"
