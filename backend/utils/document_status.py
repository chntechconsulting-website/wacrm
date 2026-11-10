"""Canonical billing document statuses.

Tax invoices are issued documents. Older records may have been written with a
payment status (for example ``paid``) in the document-status column. Those
values describe payment, not the invoice lifecycle, so invoice responses expose
them as ``issued`` without rewriting the stored record.

Only invoices are normalised here. Quotations, proformas and purchase orders
keep their stored document status unchanged.
"""

from typing import Optional


INVOICE_STATUS_ISSUED = "issued"

# Values that only describe payment, never the invoice document lifecycle.
_INVOICE_PAYMENT_LIKE_STATUSES = {
    "paid",
    "unpaid",
    "partial",
    "partially_paid",
    "fully_paid",
    "paid_in_full",
    "payment_pending",
    "pending",
    "payment_received",
    "received",
    "success",
    "succeeded",
    "confirmed",
    "completed",
    "settled",
}


def _status_label(value) -> str:
    return " ".join(str(value or "").split()).strip().lower()


def normalize_invoice_document_status(value: Optional[str]) -> str:
    """Return the invoice document status to expose through APIs and the UI.

    Payment-only values and blank values become ``issued``. Lifecycle values
    such as ``draft`` or ``cancelled`` are preserved exactly (lower-cased).
    """
    label = _status_label(value)
    comparable = label.replace("-", "_").replace(" ", "_")
    if not comparable or comparable in _INVOICE_PAYMENT_LIKE_STATUSES:
        return INVOICE_STATUS_ISSUED
    return label


def invoice_document_status(doc) -> Optional[str]:
    """Normalise the document status for an invoice record.

    Non-invoice records are returned untouched so quotation, proforma and
    purchase-order statuses keep their existing behaviour.
    """
    if doc is None or str(getattr(doc, "doc_type", "") or "").lower() != "invoice":
        return getattr(doc, "status", None)
    return normalize_invoice_document_status(getattr(doc, "status", None))
