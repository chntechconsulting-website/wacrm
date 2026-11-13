"""Canonical Sales lead status helpers.

The CRM stores Sales status as a free-form string for backwards compatibility.
These helpers centralise the status aliases used by the new Trial and
Converted to Support workflow without changing the database column or any
legacy status value already stored in production.
"""

from typing import Optional

STATUS_NEW = "NEW"
STATUS_TRIAL = "TRIAL"
STATUS_WON = "WON"
STATUS_CONVERTED = "CONVERTED"
STATUS_CONVERTED_TO_SUPPORT = "CONVERTED_TO_SUPPORT"

# Statuses that mean the deal has been won commercially. CONVERTED is a
# legacy spelling of WON and must continue to count as a win.
WON_LEAD_STATUSES = {
    STATUS_WON,
    STATUS_CONVERTED,
}

# A lead that has been explicitly handed over to Support. It is still a won
# deal for Sales reporting, but it is a distinct lifecycle status.
CONVERTED_TO_SUPPORT_STATUSES = {
    STATUS_CONVERTED_TO_SUPPORT,
    "CONVERTED TO SUPPORT",
    "CONVERTED-TO-SUPPORT",
    "CONVERTED TO SUPPORT STATUS",
}

# All statuses that represent a closed/won deal for reporting purposes.
WON_OR_CONVERTED_STATUSES = WON_LEAD_STATUSES | {
    STATUS_CONVERTED_TO_SUPPORT,
    "CONVERTED TO SUPPORT",
    "CONVERTED-TO-SUPPORT",
}

_ALIASES = {
    "NEW LEAD": STATUS_NEW,
    "NEW_LEAD": STATUS_NEW,
    "TRIAL LEAD": STATUS_TRIAL,
    "TRIAL_LEAD": STATUS_TRIAL,
    "FOLLOW-UP": "FOLLOW_UP",
    "DEMO / MEETING": "DEMO / MEETING",
    "DEMO/MEETING": "DEMO / MEETING",
    "CONVERTED TO SUPPORT": STATUS_CONVERTED_TO_SUPPORT,
    "CONVERTED-TO-SUPPORT": STATUS_CONVERTED_TO_SUPPORT,
}


def normalize_lead_status(value: Optional[str]) -> str:
    """Return the canonical upper-case Sales status for comparisons."""
    status = (value or "").strip().upper()
    return _ALIASES.get(status, status)


def is_trial_status(value: Optional[str]) -> bool:
    return normalize_lead_status(value) == STATUS_TRIAL


def is_won_status(value: Optional[str]) -> bool:
    """True for WON and the legacy CONVERTED status."""
    return normalize_lead_status(value) in WON_LEAD_STATUSES


def is_converted_to_support_status(value: Optional[str]) -> bool:
    return normalize_lead_status(value) == STATUS_CONVERTED_TO_SUPPORT


def is_won_or_converted_status(value: Optional[str]) -> bool:
    return normalize_lead_status(value) in WON_OR_CONVERTED_STATUSES
