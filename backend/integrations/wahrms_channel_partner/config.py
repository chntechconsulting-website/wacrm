"""Effective, server-side-only configuration for the WA HRMS integration."""

from __future__ import annotations

import base64
import hashlib
import logging
from dataclasses import dataclass
from typing import Optional, Tuple
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from config import settings
from models.channel_partner import ChannelPartnerIntegration

logger = logging.getLogger("wacrm.channel_partner")

INTEGRATION_ROW_ID = 1
DEFAULT_BASE_URL = "https://api.wahrms.com/api/v1/integrations/channel-partners"
WEBHOOK_PATH = "/webhooks/wahrms"


def _fernet() -> Fernet:
    """Derive a stable Fernet key from the application SECRET_KEY.

    The database stores only ciphertext. If SECRET_KEY is rotated, the stored
    key cannot be decrypted and the integration falls back to the environment
    key (an admin can simply re-enter it in Integration Settings).
    """
    digest = hashlib.sha256(
        f"wahrms-channel-partner:{settings.SECRET_KEY}".encode("utf-8")
    ).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        logger.warning(
            "Stored WAHRMS Channel Partner API key could not be decrypted; "
            "falling back to the environment value."
        )
        return None


def mask_secret(value: Optional[str], visible: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= visible:
        return "•" * len(value)
    return ("•" * max(4, min(12, len(value) - visible))) + value[-visible:]


def normalise_base_url(value: Optional[str]) -> Optional[str]:
    """Validate an admin-provided base URL and remove a trailing slash."""
    if not value:
        return None
    candidate = value.strip().rstrip("/")
    parsed = urlparse(candidate)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("API base URL must be an absolute http(s) URL.")
    return candidate


@dataclass
class EffectiveConfig:
    base_url: str
    api_key: str
    base_url_source: str
    api_key_source: str

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key)


def env_base_url() -> str:
    return (
        (settings.WAHRMS_CHANNEL_PARTNER_BASE_URL or DEFAULT_BASE_URL)
        .strip()
        .rstrip("/")
    )


def env_api_key() -> str:
    return (settings.WAHRMS_CHANNEL_PARTNER_API_KEY or "").strip()


def env_webhook_secret() -> str:
    return (settings.WAHRMS_CHANNEL_PARTNER_WEBHOOK_SECRET or "").strip()


def effective_webhook_secret(db: Session) -> Tuple[str, str]:
    """Return the active signing secret and where it came from.

    The value saved from Integration Settings takes precedence over the
    environment variable. Both are server-side only; the UI receives only the
    masked last four characters.
    """
    row = get_integration_row(db)
    db_secret = decrypt_secret(row.webhook_secret_encrypted) if row else None
    if db_secret:
        return db_secret, "database"
    env_secret = env_webhook_secret()
    return env_secret, ("environment" if env_secret else "none")


def load_webhook_secret(db: Session) -> str:
    return effective_webhook_secret(db)[0]


def get_integration_row(
    db: Session, create: bool = True
) -> Optional[ChannelPartnerIntegration]:
    row = (
        db.query(ChannelPartnerIntegration)
        .filter(ChannelPartnerIntegration.id == INTEGRATION_ROW_ID)
        .first()
    )
    if row is None and create:
        row = ChannelPartnerIntegration(id=INTEGRATION_ROW_ID)
        db.add(row)
        try:
            db.commit()
            db.refresh(row)
        except Exception:
            # Another worker may have created the singleton first.
            db.rollback()
            row = (
                db.query(ChannelPartnerIntegration)
                .filter(ChannelPartnerIntegration.id == INTEGRATION_ROW_ID)
                .first()
            )
    return row


def load_effective_config(db: Session) -> EffectiveConfig:
    row = get_integration_row(db)
    db_api_key = decrypt_secret(row.api_key_encrypted) if row else None
    api_key = db_api_key or env_api_key()
    base_url = (row.base_url if row and row.base_url else env_base_url()).rstrip("/")
    return EffectiveConfig(
        base_url=base_url,
        api_key=api_key,
        base_url_source="database" if row and row.base_url else "environment",
        api_key_source="database" if db_api_key else ("environment" if env_api_key() else "none"),
    )


def get_webhook_url() -> str:
    configured = (settings.WAHRMS_CHANNEL_PARTNER_WEBHOOK_URL or "").strip()
    if configured:
        return configured
    origin = (settings.PUBLIC_BASE_URL or "").strip().rstrip("/")
    return f"{origin}{WEBHOOK_PATH}" if origin else WEBHOOK_PATH


def save_configuration(
    db: Session,
    *,
    base_url: Optional[str] = None,
    set_base_url: bool = False,
    api_key: Optional[str] = None,
    clear_api_key: bool = False,
    webhook_secret: Optional[str] = None,
    clear_webhook_secret: bool = False,
) -> ChannelPartnerIntegration:
    row = get_integration_row(db)
    if set_base_url:
        row.base_url = normalise_base_url(base_url)
    if clear_api_key:
        row.api_key_encrypted = None
        row.api_key_last4 = None
    elif api_key is not None and api_key.strip():
        value = api_key.strip()
        row.api_key_encrypted = encrypt_secret(value)
        row.api_key_last4 = value[-4:]
    if clear_webhook_secret:
        row.webhook_secret_encrypted = None
        row.webhook_secret_last4 = None
    elif webhook_secret is not None and webhook_secret.strip():
        value = webhook_secret.strip()
        row.webhook_secret_encrypted = encrypt_secret(value)
        row.webhook_secret_last4 = value[-4:]
    db.commit()
    db.refresh(row)
    return row
