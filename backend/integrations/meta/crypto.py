import base64
import hashlib
import logging
from cryptography.fernet import Fernet
from config import settings

logger = logging.getLogger("meta_crypto")

def _get_fernet() -> Fernet:
    """
    Derives a deterministic 32-byte urlsafe base64 key from settings.SECRET_KEY.
    """
    secret = settings.SECRET_KEY or "wa-crm-meta-default-secret-2026"
    key_material = hashlib.sha256(secret.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(key_material)
    return Fernet(fernet_key)

def encrypt_token(plain_token: str) -> str:
    """
    Encrypts a plain text Page Access Token.
    """
    if not plain_token:
        return ""
    try:
        f = _get_fernet()
        return f.encrypt(plain_token.strip().encode("utf-8")).decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to encrypt Page Access Token: {e}")
        raise ValueError("Token encryption failed") from e

def decrypt_token(encrypted_token: str) -> str:
    """
    Decrypts an encrypted Page Access Token.
    If decryption fails (e.g. if plain text was stored or altered), falls back gracefully.
    """
    if not encrypted_token:
        return ""
    try:
        f = _get_fernet()
        return f.decrypt(encrypted_token.strip().encode("utf-8")).decode("utf-8")
    except Exception:
        # Fallback if raw unencrypted token was stored
        return encrypted_token.strip()

def mask_token(token: str) -> str:
    """
    Returns a masked preview of a token for UI presentation (e.g. EAAB••••••••4x)
    """
    if not token:
        return ""
    token_str = str(token).strip()
    if len(token_str) <= 12:
        return "••••••••"
    return f"{token_str[:6]}••••••••{token_str[-4:]}"
