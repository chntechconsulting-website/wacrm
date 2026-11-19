"""Normalisation, redaction and field-mapping helpers for WA HRMS payloads.

WA HRMS is the source of truth. Response envelopes and optional fields can
change server-side, so mapping is deliberately tolerant: values are read from
documented camelCase keys first, snake_case aliases second, and the complete
sanitised payload is retained for every record.
"""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import re
from typing import Any, Dict, Iterable, List, Optional

from utils.timezone import IST_TIMEZONE

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
_SAFE_DOC_META_KEYS = {
    "filename",
    "name",
    "contenttype",
    "mimetype",
    "type",
    "size",
    "sizebytes",
    "uploadedat",
    "verified",
    "status",
}
_REDACTED = "[redacted]"


def normalise_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _mask_tail(value: str, visible: int = 4) -> str:
    if len(value) <= visible:
        return "•" * len(value)
    return ("•" * min(12, len(value) - visible)) + value[-visible:]


def mask_pan(value: Optional[str]) -> Optional[str]:
    """Mask a PAN as ``••••••1234`` (never return the full identifier)."""
    if not value:
        return None
    text = str(value).strip()
    if len(text) < 4:
        return "•" * len(text)
    return ("•" * (len(text) - 4)) + text[-4:]


def pan_last4(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = str(value).strip()
    return text[-4:] if len(text) >= 4 else None


def _sanitise_document(value: Any) -> Any:
    if isinstance(value, dict):
        result: Dict[str, Any] = {}
        for key, item in value.items():
            nkey = normalise_key(key)
            if nkey in _SAFE_DOC_META_KEYS:
                result[key] = item
            elif item is None or isinstance(item, (bool, int, float)):
                # Null means "not uploaded"; booleans/numbers are presence or
                # size metadata and do not identify the document.
                result[key] = item
            elif isinstance(item, (dict, list)):
                result[key] = _sanitise_document(item)
            else:
                result[key] = _REDACTED
        return result
    if isinstance(value, list):
        return [_sanitise_document(item) for item in value]
    if isinstance(value, str) and (
        value.startswith("data:")
        or len(value) > 200
        or value.lower().startswith(("http://", "https://"))
    ):
        return _REDACTED
    return value


def sanitise_document_metadata(value: Any) -> Any:
    """Sanitise a standalone document-metadata block.

    Keys such as ``pan`` or ``aadhaar`` inside a documents block describe the
    document, not the identifier value, so only their non-safe fields (URLs,
    tokens) are redacted while filenames/types/sizes are preserved.
    """
    return _sanitise_document(value)


def sanitise_payload(value: Any, parent_key: str = "") -> Any:
    """Deep-copy a payload while removing secrets and identity documents.

    Only explicit fields are redacted, so unmapped business information is
    preserved for audit and future display.
    """
    if isinstance(value, list):
        return [sanitise_payload(item, parent_key) for item in value]
    if not isinstance(value, dict):
        return copy.deepcopy(value)

    result: Dict[str, Any] = {}
    parent_norm = normalise_key(parent_key)
    for key, item in value.items():
        nkey = normalise_key(key)

        # Metadata nested inside a documents block must keep its safe fields
        # (filename, type, size) instead of being treated as a PAN/Aadhaar value.
        if (
            ("doc" in parent_norm or "document" in parent_norm)
            and isinstance(item, (dict, list))
        ):
            result[key] = _sanitise_document(item)
            continue

        if nkey in {
            "authorization",
            "apikey",
            "accesstoken",
            "refreshtoken",
            "secret",
            "webhooksecret",
            "signingsecret",
            "password",
            "hashedpassword",
        } or nkey.endswith("secret") or nkey.endswith("apikey"):
            result[key] = _REDACTED
            continue

        if nkey in {"pan", "pannumber", "permanentaccountnumber"}:
            result[key] = mask_pan(item if isinstance(item, str) else None)
            continue

        if nkey in {"aadhaar", "aadhaarnumber", "aadhaaruid", "uidai"}:
            result[key] = mask_pan(item if isinstance(item, str) else None)
            continue

        if nkey in {
            "bankaccountnumber",
            "accountnumber",
            "accountno",
            "bankaccount",
            "bankaccountno",
            "upiid",
            "bankifsc",
            "ifsc",
        }:
            result[key] = _mask_tail(str(item)) if item else None
            continue

        if nkey in {"pandoc", "aadhaardoc", "documents", "applicationdocuments"} or (
            "doc" in nkey and isinstance(item, (dict, list))
        ):
            result[key] = _sanitise_document(item)
            continue

        if ("doc" in parent_norm or "document" in parent_norm) and (
            "url" in nkey or "link" in nkey or "token" in nkey
        ):
            result[key] = _REDACTED
            continue

        if isinstance(item, (dict, list)):
            result[key] = sanitise_payload(item, key)
        else:
            result[key] = item
    return result


def first_present(obj: Any, keys: Iterable[str], default: Any = None) -> Any:
    """Read the first present, non-None value using exact then normalised keys."""
    if not isinstance(obj, dict):
        return default
    for key in keys:
        if key in obj and obj[key] is not None and obj[key] != "":
            return obj[key]
    normalised = {normalise_key(key): value for key, value in obj.items()}
    for key in keys:
        value = normalised.get(normalise_key(key))
        if value is not None and value != "":
            return value
    return default


def get_path(obj: Any, path: str, default: Any = None) -> Any:
    current = obj
    for part in path.split("."):
        if not isinstance(current, dict):
            return default
        current = first_present(current, [part], default=None)
        if current is None:
            return default
    return current


def as_text(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    if isinstance(value, (dict, list)):
        return None
    return str(value).strip() or None


def as_int(value: Any) -> Optional[int]:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def as_float(value: Any) -> Optional[float]:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def as_bool(value: Any) -> Optional[bool]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "on"}:
        return True
    if text in {"false", "0", "no", "n", "off"}:
        return False
    return None


def as_json(value: Any) -> Any:
    """Return JSON-serialisable, untrusted API data without losing structure."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dt.datetime):
        return ist_iso(value)
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): as_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [as_json(v) for v in value]
    return str(value)


def parse_datetime_ist(value: Any) -> Optional[dt.datetime]:
    """Parse API timestamps into naive IST for consistent CRM display/filtering."""
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        parsed = value
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(IST_TIMEZONE).replace(tzinfo=None)
    if isinstance(value, (int, float)):
        number = float(value)
        if number > 1e12:  # milliseconds
            number /= 1000.0
        return dt.datetime.fromtimestamp(number, tz=dt.timezone.utc).astimezone(
            IST_TIMEZONE
        ).replace(tzinfo=None)

    text = str(value).strip()
    if not text:
        return None
    try:
        normalised = text.replace("Z", "+00:00")
        parsed = dt.datetime.fromisoformat(normalised)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(IST_TIMEZONE).replace(tzinfo=None)
    except ValueError:
        pass
    try:
        from dateutil import parser as date_parser

        parsed = date_parser.parse(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(IST_TIMEZONE).replace(tzinfo=None)
    except Exception:
        return None


def parse_date(value: Any) -> Optional[dt.date]:
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = str(value).strip()
    match = _ISO_DATE_RE.match(text)
    if match:
        try:
            return dt.date.fromisoformat(text[:10])
        except ValueError:
            return None
    parsed = parse_datetime_ist(text)
    return parsed.date() if parsed else None


def ist_iso(value: Optional[dt.datetime]) -> Optional[str]:
    """Serialise a stored naive IST datetime with an explicit +05:30 offset."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    aware = value.replace(tzinfo=IST_TIMEZONE) if value.tzinfo is None else value
    return aware.isoformat()


def extract_list(payload: Any, keys: Iterable[str]) -> List[Any]:
    """Find the record list in any documented/harmless response envelope."""
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []

    for key in keys:
        value = first_present(payload, [key], default=None)
        if isinstance(value, list):
            return value

    for wrapper in ("data", "result", "results", "items", "payload"):
        value = first_present(payload, [wrapper], default=None)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = extract_list(value, keys)
            if nested:
                return nested
    return []


def extract_object(payload: Any, keys: Iterable[str]) -> Dict[str, Any]:
    """Find a single object in the response envelope."""
    if isinstance(payload, dict):
        for key in keys:
            value = first_present(payload, [key], default=None)
            if isinstance(value, dict):
                return value
        for wrapper in ("data", "result", "payload"):
            value = first_present(payload, [wrapper], default=None)
            if isinstance(value, dict):
                nested = extract_object(value, keys)
                if nested:
                    return nested
        return payload
    return {}


def external_id_of(obj: Any, *aliases: str) -> Optional[str]:
    if not isinstance(obj, dict):
        return None
    value = first_present(obj, list(aliases) + ["id"], default=None)
    return as_text(value)


def scan_related_ids(payload: Any) -> Dict[str, Optional[str]]:
    """Extract partner/lead/client identifiers from arbitrary event data."""
    found: Dict[str, Optional[str]] = {
        "partner": None,
        "lead": None,
        "client": None,
    }

    def walk(node: Any, parent: str = ""):
        if isinstance(node, list):
            for item in node:
                walk(item, parent)
            return
        if not isinstance(node, dict):
            return
        for key, value in node.items():
            nkey = normalise_key(key)
            if isinstance(value, dict):
                if nkey in {"partner", "lead", "client", "attribution", "entry", "payout"}:
                    candidate = external_id_of(value)
                    if nkey == "partner" and candidate and not found["partner"]:
                        found["partner"] = candidate
                    elif nkey == "lead" and candidate and not found["lead"]:
                        found["lead"] = candidate
                    elif nkey == "client" and candidate and not found["client"]:
                        found["client"] = candidate
                walk(value, key)
            elif isinstance(value, str):
                if nkey in {"partnerid"} and not found["partner"]:
                    found["partner"] = value
                elif nkey in {"leadid"} and not found["lead"]:
                    found["lead"] = value
                elif nkey in {"clientid", "organizationid"} and not found["client"]:
                    found["client"] = value

    walk(payload)
    return found


def payload_hash(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()


def status_value(value: Any) -> Optional[str]:
    text = as_text(value)
    return text.lower() if text else None
