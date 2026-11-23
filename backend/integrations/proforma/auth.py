import os
import time
import hmac
import hashlib
import logging
import json
from typing import Optional, Tuple
from collections import defaultdict
from fastapi import Request, HTTPException, status, Header, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.integration import IntegrationConfig

logger = logging.getLogger("proforma_api_auth")

# Default developer fallback key (used if no environment variable or DB config is set)
DEFAULT_INTEGRATION_KEY = "wacrm_ext_live_8849204128f73a0e691823c91"

# In-memory sliding window rate limiter: client_id -> list of timestamps
_RATE_LIMIT_BUCKETS = defaultdict(list)
RATE_LIMIT_MAX_REQUESTS = 120  # requests per minute
RATE_LIMIT_WINDOW_SECONDS = 60


def sanitize_secret(text: str) -> str:
    """Removes API keys, bearer tokens, and secrets from logs and error strings."""
    if not text:
        return ""
    import re
    cleaned = re.sub(r'(Bearer\s+)[A-Za-z0-9_\-\.]{8,}', r'\1[REDACTED]', text, flags=re.IGNORECASE)
    cleaned = re.sub(r'([?&](?:api_key|token|key|secret)=)[^&\s]+', r'\1[REDACTED]', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'(wacrm_[A-Za-z0-9_\-]{8,})', r'[REDACTED_API_KEY]', cleaned)
    return cleaned


def get_authorized_keys(db: Optional[Session] = None) -> list:
    """
    Resolves authoritative API keys configured for external integration.
    Checks:
    1. Environment variables: CRM_EXTERNAL_API_KEY, INTEGRATION_API_KEY, DESTINATION_ERP_API_KEY, WAQUOTE_API_KEY
    2. Database IntegrationConfig: EXTERNAL_API, PROFORMA_API, DESTINATION_ERP, WAQUOTE
    3. Default system fallback
    """
    keys = []
    
    # 1. Environment variables
    for env_var in ["CRM_EXTERNAL_API_KEY", "INTEGRATION_API_KEY", "DESTINATION_ERP_API_KEY", "WAQUOTE_API_KEY"]:
        val = os.getenv(env_var)
        if val and val.strip():
            keys.append(val.strip())

    # 2. Database IntegrationConfig
    if db:
        try:
            configs = db.query(IntegrationConfig).filter(
                IntegrationConfig.integration_type.in_(["EXTERNAL_API", "PROFORMA_API", "DESTINATION_ERP", "WAQUOTE"])
            ).all()
            for cfg in configs:
                if cfg and getattr(cfg, "config_data", None):
                    try:
                        cdata = json.loads(cfg.config_data) if isinstance(cfg.config_data, str) else cfg.config_data
                        for k in ["api_key", "secret", "token", "apiKey"]:
                            if cdata.get(k):
                                keys.append(str(cdata[k]).strip())
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Error reading integration keys from DB: {e}")

    # 3. Default fallback if nothing configured
    if not keys:
        keys.append(DEFAULT_INTEGRATION_KEY)

    return list(set(keys))


def apply_rate_limit(client_identifier: str):
    """Enforces sliding-window rate limit (120 req / 60 sec)."""
    now = time.time()
    timestamps = _RATE_LIMIT_BUCKETS[client_identifier]
    
    # Purge timestamps outside window
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    _RATE_LIMIT_BUCKETS[client_identifier] = [t for t in timestamps if t > cutoff]
    
    if len(_RATE_LIMIT_BUCKETS[client_identifier]) >= RATE_LIMIT_MAX_REQUESTS:
        logger.warning(f"Rate limit exceeded for client: {client_identifier}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Maximum 120 requests per minute allowed."
        )
    
    _RATE_LIMIT_BUCKETS[client_identifier].append(now)


async def verify_proforma_integration_auth(
    request: Request,
    db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_signature: Optional[str] = Header(None, alias="X-Signature-SHA256")
) -> str:
    """
    FastAPI Dependency to authenticate server-to-server requests:
    - Extracts token from 'X-API-Key' or 'Authorization: Bearer <key>'
    - Compares using constant-time comparison
    - Applies client rate limiting
    """
    client_ip = request.client.host if request.client else "unknown"
    apply_rate_limit(client_ip)

    extracted_key: Optional[str] = None

    # 1. Check X-API-Key header
    if x_api_key and x_api_key.strip():
        extracted_key = x_api_key.strip()

    # 2. Check Authorization header
    if not extracted_key:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.strip():
            parts = auth_header.strip().split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                extracted_key = parts[1].strip()
            elif len(parts) == 1:
                extracted_key = parts[0].strip()

    if not extracted_key:
        logger.warning(f"Unauthorized external integration call from IP {client_ip}: Missing credentials.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing server-to-server authentication. Provide 'X-API-Key: <key>' or 'Authorization: Bearer <key>'.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    valid_keys = get_authorized_keys(db)
    is_valid = any(hmac.compare_digest(extracted_key, k) for k in valid_keys)

    if not is_valid:
        logger.warning(f"Unauthorized external integration call from IP {client_ip}: Invalid API key.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key or unauthorized integration credential."
        )

    return extracted_key


# ---------------------------------------------------------------------------
# Payment webhook authentication
# ---------------------------------------------------------------------------
WEBHOOK_SECRET_ENV_VARS = (
    "WAQUOTE_WEBHOOK_SECRET",
    "PROFORMA_WEBHOOK_SECRET",
    "CRM_WEBHOOK_SECRET",
)

WEBHOOK_SIGNATURE_HEADERS = (
    "X-WAQuote-Signature",
    "X-Webhook-Signature",
    "X-Signature-SHA256",
    "X-Hub-Signature-256",
    "X-Signature",
)

WEBHOOK_SIGNATURE_TOLERANCE_SECONDS = 300


def get_webhook_secrets(db: Optional[Session] = None) -> list:
    """Resolve configured webhook signing secrets (env first, then DB)."""
    secrets = []
    for env_var in WEBHOOK_SECRET_ENV_VARS:
        value = os.getenv(env_var)
        if value and value.strip():
            secrets.append(value.strip())

    if db:
        try:
            configs = (
                db.query(IntegrationConfig)
                .filter(
                    IntegrationConfig.integration_type.in_(
                        [
                            "WAQUOTE",
                            "QUOTETASK",
                            "PROFORMA_API",
                            "EXTERNAL_API",
                            "DESTINATION_ERP",
                        ]
                    )
                )
                .all()
            )
            for cfg in configs:
                if not cfg or not getattr(cfg, "config_data", None):
                    continue
                try:
                    cdata = (
                        json.loads(cfg.config_data)
                        if isinstance(cfg.config_data, str)
                        else cfg.config_data
                    )
                    for key in (
                        "webhook_secret",
                        "webhookSecret",
                        "signing_secret",
                        "signingSecret",
                        "hmac_secret",
                        "hmacSecret",
                    ):
                        value = cdata.get(key) if isinstance(cdata, dict) else None
                        if value and str(value).strip():
                            secrets.append(str(value).strip())
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Error reading webhook secrets from DB: {e}")

    # Preserve order while removing duplicates.
    return list(dict.fromkeys(secrets))


def _split_signature_header(signature_header: str) -> dict:
    parts = {}
    for piece in str(signature_header or "").split(","):
        if "=" not in piece:
            continue
        key, value = piece.split("=", 1)
        parts[key.strip().lower()] = value.strip()
    return parts


def verify_webhook_signature(
    raw_body: bytes,
    signature_header: Optional[str],
    secret: Optional[str],
    *,
    tolerance_seconds: int = WEBHOOK_SIGNATURE_TOLERANCE_SECONDS,
    now: Optional[float] = None,
) -> Tuple[bool, str]:
    """Verify ``t=...,v1=...`` or ``sha256=<hex>`` over the raw body.

    Both common ERP formats are accepted:

    * ``X-WAQuote-Signature: t=<unix>,v1=<hex>`` signs ``<t>.<raw body>``
      and must be inside the five-minute replay window.
    * ``X-Hub-Signature-256: sha256=<hex>`` (or a bare hex header) signs the
      raw body only.
    """
    if not secret:
        return False, "webhook_secret_not_configured"
    if not signature_header:
        return False, "missing_signature"

    parts = _split_signature_header(signature_header)
    timestamp_raw = parts.get("t") or parts.get("timestamp")
    provided = (
        parts.get("v1")
        or parts.get("sha256")
        or parts.get("signature")
        or parts.get("v0")
    )
    if not provided:
        provided = str(signature_header).strip()
    if provided.lower().startswith("sha256="):
        provided = provided.split("=", 1)[1].strip()
    if not provided:
        return False, "missing_signature"

    payload = raw_body
    if timestamp_raw:
        try:
            timestamp = float(timestamp_raw)
        except (TypeError, ValueError):
            return False, "invalid_timestamp"
        if timestamp > 1_000_000_000_000:
            timestamp /= 1000.0
        current = time.time() if now is None else now
        if abs(current - timestamp) > tolerance_seconds:
            return False, "timestamp_out_of_tolerance"
        payload = f"{timestamp_raw}.".encode("utf-8") + raw_body

    expected = hmac.new(
        str(secret).encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    if hmac.compare_digest(expected.lower(), str(provided).strip().lower()):
        return True, "verified"
    return False, "invalid_signature"


def _extract_webhook_signature(headers) -> Optional[str]:
    for header_name in WEBHOOK_SIGNATURE_HEADERS:
        value = headers.get(header_name)
        if value and str(value).strip():
            return str(value).strip()
    return None


def authenticate_proforma_webhook(
    request: Request,
    raw_body: bytes,
    db: Optional[Session] = None,
) -> str:
    """Authenticate a payment webhook.

    A valid HMAC signature is preferred.  The existing server-to-server API
    key remains a fallback for ERPs that have not been configured with a
    signing secret yet.  A signature header that is present but invalid is
    always rejected, even if an API key is also supplied.
    """
    client_ip = request.client.host if request.client else "unknown"
    apply_rate_limit(client_ip)

    signature_header = _extract_webhook_signature(request.headers)
    secrets = get_webhook_secrets(db)

    if signature_header:
        if not secrets:
            logger.warning(
                f"Rejected signed webhook from IP {client_ip}: no webhook secret configured."
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "A webhook signature was supplied but no signing secret is "
                    "configured. Set WAQUOTE_WEBHOOK_SECRET or the integration "
                    "webhook_secret."
                ),
            )
        for secret in secrets:
            valid, reason = verify_webhook_signature(
                raw_body, signature_header, secret
            )
            if valid:
                return "signature"
        logger.warning(f"Rejected webhook from IP {client_ip}: invalid signature.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature.",
        )

    # API-key fallback.
    extracted_key: Optional[str] = None
    api_key_header = request.headers.get("X-API-Key")
    if api_key_header and api_key_header.strip():
        extracted_key = api_key_header.strip()
    if not extracted_key:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.strip():
            parts = auth_header.strip().split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                extracted_key = parts[1].strip()
            elif len(parts) == 1:
                extracted_key = parts[0].strip()

    if not extracted_key:
        logger.warning(
            f"Unauthorized payment webhook from IP {client_ip}: missing credentials."
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Missing webhook authentication. Provide a valid signature or "
                "'X-API-Key: <key>' / 'Authorization: Bearer <key>'."
            ),
            headers={"WWW-Authenticate": "Bearer"},
        )

    valid_keys = get_authorized_keys(db)
    if not any(hmac.compare_digest(extracted_key, key) for key in valid_keys):
        logger.warning(
            f"Unauthorized payment webhook from IP {client_ip}: invalid API key."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key or unauthorized integration credential.",
        )
    return "api_key"
