"""Canonical Support lifecycle statuses.

Sales status is stored on ``leads.status`` and is owned by the Sales workflow.
Support status is stored independently on ``support_handoffs.onboarding_status``.

This module is the single source of truth for the Support status vocabulary so
that backend validation, reporting, API filtering and the dashboards cannot
silently drift apart. Existing handovers keep their historical values; reads
normalise those legacy values without mutating or deleting the stored data.
"""

from typing import Dict, Optional, Set


SUPPORT_STATUS_NEW = "NEW"
SUPPORT_STATUS_ONBOARDING = "ONBOARDING"
SUPPORT_STATUS_INSTALLATION_PENDING = "INSTALLATION_PENDING"
SUPPORT_STATUS_INSTALLATION_COMPLETED = "INSTALLATION_COMPLETED"
SUPPORT_STATUS_TRAINING = "TRAINING"
SUPPORT_STATUS_ACTIVE = "ACTIVE"
SUPPORT_STATUS_ISSUE_RAISED = "ISSUE_RAISED"
SUPPORT_STATUS_RESOLVED = "RESOLVED"

# Ordered for dashboards, filters and reports.
SUPPORT_STATUS_ORDER = [
    SUPPORT_STATUS_NEW,
    SUPPORT_STATUS_ONBOARDING,
    SUPPORT_STATUS_INSTALLATION_PENDING,
    SUPPORT_STATUS_INSTALLATION_COMPLETED,
    SUPPORT_STATUS_TRAINING,
    SUPPORT_STATUS_ACTIVE,
    SUPPORT_STATUS_ISSUE_RAISED,
    SUPPORT_STATUS_RESOLVED,
]

SUPPORT_STATUS_VALUES = set(SUPPORT_STATUS_ORDER)

SUPPORT_STATUS_META: Dict[str, Dict[str, str]] = {
    SUPPORT_STATUS_NEW: {
        "label": "New",
        "color": "#f59e0b",
        "bucket": "pending",
    },
    SUPPORT_STATUS_ONBOARDING: {
        "label": "Onboarding",
        "color": "#3b82f6",
        "bucket": "open",
    },
    SUPPORT_STATUS_INSTALLATION_PENDING: {
        "label": "Installation Pending",
        "color": "#8b5cf6",
        "bucket": "open",
    },
    SUPPORT_STATUS_INSTALLATION_COMPLETED: {
        "label": "Installation Completed",
        "color": "#0ea5e9",
        "bucket": "open",
    },
    SUPPORT_STATUS_TRAINING: {
        "label": "Training",
        "color": "#6366f1",
        "bucket": "open",
    },
    SUPPORT_STATUS_ACTIVE: {
        "label": "Active",
        "color": "#10b981",
        "bucket": "active",
    },
    SUPPORT_STATUS_ISSUE_RAISED: {
        "label": "Issue Raised",
        "color": "#ef4444",
        "bucket": "open",
    },
    SUPPORT_STATUS_RESOLVED: {
        "label": "Resolved",
        "color": "#15803d",
        "bucket": "resolved",
    },
}

# Historical values previously written to support_handoffs.onboarding_status,
# plus values used by the mobile Support client. Keys are already normalised
# to upper-case with spaces/hyphens converted to underscores.
LEGACY_SUPPORT_STATUS_ALIASES: Dict[str, str] = {
    "PENDING_ONBOARDING": SUPPORT_STATUS_NEW,
    "PENDING_CONTACT": SUPPORT_STATUS_NEW,
    "NOT_CONTACTED": SUPPORT_STATUS_NEW,
    "NEW_LEAD": SUPPORT_STATUS_NEW,
    "CONTACTED": SUPPORT_STATUS_ONBOARDING,
    "ONBOARDING_IN_PROGRESS": SUPPORT_STATUS_ONBOARDING,
    "ONBOARDING": SUPPORT_STATUS_ONBOARDING,
    "IN_PROGRESS": SUPPORT_STATUS_ONBOARDING,
    "INSTALLATION_PENDING": SUPPORT_STATUS_INSTALLATION_PENDING,
    "INSTALLATION_IN_PROGRESS": SUPPORT_STATUS_INSTALLATION_PENDING,
    "INSTALLATION_COMPLETED": SUPPORT_STATUS_INSTALLATION_COMPLETED,
    "INSTALLATION_COMPLETE": SUPPORT_STATUS_INSTALLATION_COMPLETED,
    "INSTALLATION_DONE": SUPPORT_STATUS_INSTALLATION_COMPLETED,
    "TRAINING": SUPPORT_STATUS_TRAINING,
    "IN_TRAINING": SUPPORT_STATUS_TRAINING,
    "ACTIVE": SUPPORT_STATUS_ACTIVE,
    "LIVE": SUPPORT_STATUS_ACTIVE,
    "ISSUE_RAISED": SUPPORT_STATUS_ISSUE_RAISED,
    "ISSUE": SUPPORT_STATUS_ISSUE_RAISED,
    "RESOLVED": SUPPORT_STATUS_RESOLVED,
    "COMPLETED": SUPPORT_STATUS_RESOLVED,
    "COMPLETE": SUPPORT_STATUS_RESOLVED,
    "DONE": SUPPORT_STATUS_RESOLVED,
}

SUPPORT_PENDING_STATUSES = {SUPPORT_STATUS_NEW}
SUPPORT_OPEN_STATUSES = {
    SUPPORT_STATUS_ONBOARDING,
    SUPPORT_STATUS_INSTALLATION_PENDING,
    SUPPORT_STATUS_INSTALLATION_COMPLETED,
    SUPPORT_STATUS_TRAINING,
    SUPPORT_STATUS_ISSUE_RAISED,
}
SUPPORT_RESOLVED_STATUSES = {SUPPORT_STATUS_RESOLVED}


class InvalidSupportStatusError(ValueError):
    """Raised when a Support status is not part of the canonical vocabulary."""


def _status_key(value: str) -> str:
    return (
        str(value)
        .strip()
        .upper()
        .replace("-", "_")
        .replace(" ", "_")
    )


def normalize_support_status(value: Optional[str]) -> Optional[str]:
    """Return the canonical Support status for a stored/client value.

    Returns ``None`` when the value is empty or unknown so callers can decide
    whether to reject it or fall back to a default.
    """
    if value is None:
        return None
    key = _status_key(value)
    if not key:
        return None
    canonical = LEGACY_SUPPORT_STATUS_ALIASES.get(key, key)
    return canonical if canonical in SUPPORT_STATUS_VALUES else None


def require_support_status(value: Optional[str]) -> str:
    """Return a canonical Support status or raise a validation error."""
    canonical = normalize_support_status(value)
    if not canonical:
        raise InvalidSupportStatusError(
            f"Invalid Support status '{value}'. Allowed values: "
            + ", ".join(SUPPORT_STATUS_ORDER)
        )
    return canonical


def support_status_label(value: Optional[str]) -> str:
    canonical = normalize_support_status(value)
    if canonical:
        return SUPPORT_STATUS_META[canonical]["label"]
    return (value or "Unknown").replace("_", " ").title()


def support_status_color(value: Optional[str]) -> str:
    canonical = normalize_support_status(value)
    if canonical:
        return SUPPORT_STATUS_META[canonical]["color"]
    return "#94a3b8"


def support_status_bucket(value: Optional[str]) -> str:
    canonical = normalize_support_status(value)
    if canonical:
        return SUPPORT_STATUS_META[canonical]["bucket"]
    return "open"


def support_status_storage_values(value: Optional[str]) -> Set[str]:
    """All stored spellings that normalise to the requested Support status."""
    canonical = normalize_support_status(value)
    if not canonical:
        return set()
    values = {canonical}
    values.update(
        legacy for legacy, mapped in LEGACY_SUPPORT_STATUS_ALIASES.items() if mapped == canonical
    )
    return values
