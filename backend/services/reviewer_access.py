"""Hard access boundary for the Meta App Review account.

The ``META_REVIEWER`` role exists so a Meta reviewer can test the WhatsApp
inbox and inspect the WhatsApp Connection status without seeing leads,
customers, billing, reports, users, or any other CRM data.

Role permissions already hide most of the UI, but this allowlist is enforced
for every authenticated API request. Even if somebody accidentally grants the
reviewer role more module permissions, these endpoints remain the only ones
the reviewer can call.
"""

from typing import Optional

META_REVIEWER_ROLE = "META_REVIEWER"

# Endpoints needed by the login flow, the WhatsApp inbox, and the read-only
# connection status page.
_ALLOWED_EXACT = {
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/token"),
    ("GET", "/api/auth/me"),
    ("POST", "/api/auth/logout"),
    ("GET", "/api/whatsapp/config-status"),
    ("GET", "/api/whatsapp/conversations"),
    ("POST", "/api/whatsapp/send-message"),
    ("GET", "/api/whatsapp/coexistence/status"),
    ("GET", "/api/whatsapp/coexistence/events"),
    ("GET", "/api/whatsapp/coexistence/templates"),
}

# Conversation details, mark-as-read, and archive. The WhatsApp router still
# scopes every one of these calls to conversations/leads assigned to the
# reviewer, so knowing another conversation ID is not enough.
_ALLOWED_CONVERSATION_PREFIX = "/api/whatsapp/conversations/"

_ALLOWED_METHODS = {"GET", "HEAD", "POST", "PUT"}


def is_meta_reviewer_role(role: Optional[str]) -> bool:
    return (role or "").strip().upper() == META_REVIEWER_ROLE


def _normalize_path(path: str) -> str:
    clean = (path or "").split("?", 1)[0]
    if len(clean) > 1:
        clean = clean.rstrip("/")
    return clean or "/"


def reviewer_request_allowed(method: str, path: str) -> bool:
    """Return True only for the API surface a reviewer is allowed to use."""
    verb = (method or "").strip().upper()
    if verb == "OPTIONS":
        return True
    if verb not in _ALLOWED_METHODS:
        return False

    clean_path = _normalize_path(path)
    if (verb, clean_path) in _ALLOWED_EXACT:
        return True

    if clean_path.startswith(_ALLOWED_CONVERSATION_PREFIX):
        return verb in {"GET", "HEAD", "PUT"}

    return False
