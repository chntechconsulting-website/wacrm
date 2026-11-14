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


# ---------------------------------------------------------------------------
# Trial lifecycle projection
# ---------------------------------------------------------------------------
# These statuses are *derived* from the Sales status plus the calculated trial
# end date. They are never written back to `Lead.status`, so the Sales WON
# status and every Support-specific status stay exactly as they are.
TRIAL_STATUS_ACTIVE = "TRIAL_ACTIVE"
TRIAL_STATUS_EXPIRING_SOON = "TRIAL_EXPIRING_SOON"
TRIAL_STATUS_EXPIRED = "TRIAL_EXPIRED"
TRIAL_STATUS_CONVERTED = "TRIAL_CONVERTED"
TRIAL_STATUS_CANCELLED = "TRIAL_CANCELLED"

# A trial with this many days (or fewer) left is reported as "expiring soon".
TRIAL_EXPIRING_SOON_DAYS = 3

# Sales statuses that mean the trial was abandoned before conversion.
CANCELLED_LEAD_STATUSES = {
    "NOT_INTERESTED",
    "NOT INTERESTED",
    "LOST",
    "CANCELLED",
    "CANCELED",
    "REJECTED",
    "RNR",
}


def trial_status_for(
    value: Optional[str],
    trial_end_date,
    today=None,
) -> Optional[str]:
    """Return the Trial status for a lead, or ``None`` when there is no trial.

    * ``TRIAL_CONVERTED``   - the trial lead was Won/Converted (or handed to Support)
    * ``TRIAL_CANCELLED``   - the trial lead was lost / not interested
    * ``TRIAL_EXPIRED``     - trial end date is in the past
    * ``TRIAL_EXPIRING_SOON`` - trial ends within ``TRIAL_EXPIRING_SOON_DAYS``
    * ``TRIAL_ACTIVE``      - trial running (or no end date recorded yet)

    Only a lead that carries trial dates (or is in a Trial status) gets a
    status, so ordinary leads are unaffected.
    """
    canonical = normalize_lead_status(value)
    has_trial = bool(trial_end_date) or canonical == STATUS_TRIAL
    if not has_trial:
        return None

    if canonical in WON_OR_CONVERTED_STATUSES:
        return TRIAL_STATUS_CONVERTED
    if canonical in CANCELLED_LEAD_STATUSES:
        return TRIAL_STATUS_CANCELLED

    if canonical != STATUS_TRIAL:
        # The lead left the Trial workflow (e.g. moved to FOLLOW-UP) while the
        # historical trial dates are preserved on the row.
        return None
    if not trial_end_date:
        return TRIAL_STATUS_ACTIVE

    if today is None:
        from utils.timezone import get_ist_now

        today = get_ist_now().date()

    days_left = (trial_end_date - today).days
    if days_left < 0:
        return TRIAL_STATUS_EXPIRED
    if days_left <= TRIAL_EXPIRING_SOON_DAYS:
        return TRIAL_STATUS_EXPIRING_SOON
    return TRIAL_STATUS_ACTIVE
