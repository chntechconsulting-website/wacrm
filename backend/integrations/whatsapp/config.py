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
    def _get_coexistence_connection() -> dict:
        """Return the active coexistence connection, if one exists.

        The fields are copied out while the session is open so callers never
        receive a detached ORM instance. The token stays encrypted here.
        """
        try:
            from sqlalchemy import desc

            from database import SessionLocal
            from models.whatsapp_coexistence import WhatsAppCoexistenceConnection

            db = SessionLocal()
            try:
                row = (
                    db.query(WhatsAppCoexistenceConnection)
                    .filter(
                        WhatsAppCoexistenceConnection.status.in_(
                            ["CONNECTED", "SYNCING", "SYNC_COMPLETE"]
                        )
                    )
                    .order_by(desc(WhatsAppCoexistenceConnection.id))
                    .first()
                )
                if not row:
                    return {}
                return {
                    "waba_id": row.waba_id,
                    "phone_number_id": row.phone_number_id,
                    "encrypted_access_token": row.encrypted_access_token,
                }
            finally:
                db.close()
        except Exception:
            return {}

    @staticmethod
    def _coexistence_token() -> str:
        connection = WhatsAppConfig._get_coexistence_connection()
        if not connection:
            return ""
        try:
            from integrations.meta.crypto import decrypt_token

            return decrypt_token(connection.get("encrypted_access_token") or "")
        except Exception:
            return ""

    @staticmethod
    def get_api_token() -> str:
        # A coexisting number must use its own business token for both sending
        # and account calls. Mixing it with an env token would target the wrong
        # WABA, so the active connection wins.
        coexistence_token = WhatsAppConfig._coexistence_token()
        if coexistence_token:
            return coexistence_token
        val = os.getenv("WHATSAPP_API_TOKEN", "")
        if not val:
            val = WhatsAppConfig._get_db_config().get("access_token", "")
        return val

    @staticmethod
    def get_phone_number_id() -> str:
        connection = WhatsAppConfig._get_coexistence_connection()
        if connection:
            return connection.get("phone_number_id") or ""
        val = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
        if not val:
            val = WhatsAppConfig._get_db_config().get("phone_number_id", "")
        return val

    @staticmethod
    def get_business_account_id() -> str:
        connection = WhatsAppConfig._get_coexistence_connection()
        if connection:
            return connection.get("waba_id") or ""
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
        connection = WhatsAppConfig._get_coexistence_connection()
        if connection:
            try:
                from integrations.whatsapp_coexistence.config import (
                    WhatsAppCoexistenceConfig,
                )

                return WhatsAppCoexistenceConfig.get_api_version()
            except Exception:
                pass
        val = os.getenv("WHATSAPP_API_VERSION", "")
        if not val:
            val = WhatsAppConfig._get_db_config().get("api_version", "")
        return val or "v26.0"

    @classmethod
    def is_configured(cls) -> bool:
        if cls._get_coexistence_connection():
            return True
        return bool(cls.get_api_token() and cls.get_phone_number_id())
