"""Canonical Finance payment and handoff statuses.

Proforma invoices store ``payment_status`` in lower-case (``unpaid`` / ``paid``)
while the Finance workflow uses upper-case constants. Older handoffs may also
carry those lower-case values or short aliases. Keep one normaliser so the
Finance queue, filters and the confirm-payment action always agree.
"""

from typing import Dict, List, Set


PAYMENT_STATUS_PENDING = "PAYMENT_PENDING"
PAYMENT_STATUS_PARTIALLY_PAID = "PARTIALLY_PAID"
PAYMENT_STATUS_PAID = "PAID"

FINANCE_STATUS_PENDING = "PAYMENT_PENDING"
FINANCE_STATUS_PAID = "PAID"
FINANCE_STATUS_REJECTED = "REJECTED"
FINANCE_STATUS_CANCELLED = "CANCELLED"


def _normalize_label(value) -> str:
    return " ".join(str(value or "").split()).upper().replace("-", "_").replace(" ", "_")


_PAID_ALIASES = {
    "PAID",
    "PAYMENT_RECEIVED",
    "RECEIVED",
    "SUCCESS",
    "SUCCEEDED",
    "CONFIRMED",
    "COMPLETED",
    "SETTLED",
}

_PARTIAL_ALIASES = {
    "PARTIALLY_PAID",
    "PARTIALLY PAID",
    "PARTIAL",
    "PARTIAL_PAYMENT",
    "PART_PAYMENT",
    "PARTLY_PAID",
}

_REJECTED_ALIASES = {
    "REJECTED",
    "DECLINED",
    "FAILED",
}

_CANCELLED_ALIASES = {
    "CANCELLED",
    "CANCELED",
    "VOID",
}

# Aliases that may be stored in finance_handoffs.status for each canonical
# state. The values are compared against an upper-cased SQL expression with
# spaces/hyphens replaced by underscores.
FINANCE_STATUS_ALIASES: Dict[str, Set[str]] = {
    FINANCE_STATUS_PENDING: {
        "",
        "PAYMENT_PENDING",
        "PAYMENT PENDING",
        "PENDING",
        "UNPAID",
        "NOT_PAID",
        "NOT PAID",
        "PARTIALLY_PAID",
        "PARTIALLY PAID",
        "PARTIAL",
    },
    FINANCE_STATUS_PAID: set(_PAID_ALIASES),
    FINANCE_STATUS_REJECTED: set(_REJECTED_ALIASES),
    FINANCE_STATUS_CANCELLED: set(_CANCELLED_ALIASES),
}

_NORMALIZED_FINANCE_ALIASES = {
    canonical: {_normalize_label(alias) for alias in aliases}
    for canonical, aliases in FINANCE_STATUS_ALIASES.items()
}


def normalize_payment_status(value) -> str:
    """Return the canonical payment status used by Finance documents."""
    label = _normalize_label(value)
    if label in _PAID_ALIASES:
        return PAYMENT_STATUS_PAID
    if label in _PARTIAL_ALIASES:
        return PAYMENT_STATUS_PARTIALLY_PAID
    return PAYMENT_STATUS_PENDING


def normalize_finance_status(value) -> str:
    """Return the canonical Finance handoff lifecycle status."""
    label = _normalize_label(value)
    if label in _PAID_ALIASES:
        return FINANCE_STATUS_PAID
    if label in _REJECTED_ALIASES:
        return FINANCE_STATUS_REJECTED
    if label in _CANCELLED_ALIASES:
        return FINANCE_STATUS_CANCELLED
    return FINANCE_STATUS_PENDING


def finance_status_filter_values(status) -> List[str]:
    """Return every stored alias that represents ``status``."""
    canonical = normalize_finance_status(status)
    return sorted(_NORMALIZED_FINANCE_ALIASES[canonical])
