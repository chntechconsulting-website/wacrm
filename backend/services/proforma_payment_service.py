"""External Proforma payment -> CRM Lead WON workflow.

The WA Quote / WAHRMS ERP is the system of record for the customer-facing
Proforma Invoice.  When the ERP confirms that money was actually received it
calls one of the CRM webhook endpoints.  This module is the single place that
turns that event into the existing CRM Finance workflow:

* the exact Proforma is resolved from the stored external identifiers
  (``Quotation.external_proforma_id``, ``metadata.crmProformaId`` or the
  Proforma number) and never by customer name/phone;
* one ``Payment`` row is written per confirmed transaction, with the external
  transaction ID used for idempotency;
* the Proforma's ``amount_paid``/``payment_status`` and the outstanding balance
  are updated for full, partial and multiple payments;
* the Lead is moved to ``WON`` (unless it is already WON or has advanced to
  ``CONVERTED_TO_SUPPORT``), with a ``LeadStatusHistory`` row preserving the
  previous status;
* the existing ``FinanceHandoff`` and ``SupportHandoff`` records are created or
  updated, and Sales / Finance / Support are notified;
* the payment is written to the CRM activity timeline and workflow timeline.

Everything for one event is committed in a single transaction.  A duplicate
event therefore leaves no partial payment, handoff or status change behind.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from sqlalchemy import desc, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.activity import LeadActivity
from models.audit_log import AuditLog
from models.customer import Customer
from models.employee import Employee
from models.finance import Payment, ProformaPaymentEvent
from models.integration import IntegrationLog
from models.lead import Lead, LeadStatusHistory
from models.notification import Notification
from models.quotation import Quotation
from models.user import User
from models.workflow import FinanceHandoff, SupportHandoff, WorkflowTimelineEvent
from services.purchase_details_service import build_purchase_snapshot
from utils.lead_status import (
    STATUS_NEW,
    STATUS_WON,
    WON_OR_CONVERTED_STATUSES,
    normalize_lead_status,
)
from utils.payment_status import PAYMENT_STATUS_PAID, PAYMENT_STATUS_PARTIALLY_PAID
from utils.support_status import SUPPORT_STATUS_NEW

logger = logging.getLogger("proforma_payment_service")

PROVIDER = "WAQUOTE"

# Status values that mean money has actually been received.  Pending, failed,
# cancelled, refunded and unverified states are deliberately absent.
_SUCCESS_TOKENS = {
    "PAID",
    "PAYMENT_RECEIVED",
    "RECEIVED",
    "SUCCESS",
    "SUCCESSFUL",
    "SUCCEEDED",
    "CAPTURED",
    "SETTLED",
    "COMPLETED",
    "CONFIRMED",
    "PAYMENT_SUCCESS",
    "PAYMENT_SUCCESSFUL",
    "PAYMENT_SUCCEEDED",
    "PAYMENT_CAPTURED",
    "PAYMENT_SETTLED",
    "PAYMENT_COMPLETED",
    "PAYMENT_CONFIRMED",
    "PAYMENT_RECEIVED",
    "PARTIALLY_PAID",
    "PARTIAL",
    "PARTIAL_PAYMENT",
    "PART_PAYMENT",
    "PARTLY_PAID",
}

_IGNORE_TOKENS = {
    "FAILED",
    "FAILURE",
    "PAYMENT_FAILED",
    "CANCELLED",
    "CANCELED",
    "PAYMENT_CANCELLED",
    "PAYMENT_CANCELED",
    "PENDING",
    "PAYMENT_PENDING",
    "PROCESSING",
    "PAYMENT_PROCESSING",
    "INITIATED",
    "PAYMENT_INITIATED",
    "REFUNDED",
    "REFUND",
    "PAYMENT_REFUNDED",
    "UNVERIFIED",
    "PAYMENT_UNVERIFIED",
    "REJECTED",
    "DECLINED",
    "EXPIRED",
    "VOID",
    "VOIDED",
    "UNPAID",
    "NOT_PAID",
    "DRAFT",
    "SENT",
    "ISSUED",
    "CREATED",
    "UPDATED",
    "DELETED",
    "PROFORMA_CREATED",
    "PROFORMA_SENT",
    "PROFORMA_UPDATED",
    "DOCUMENT_CREATED",
    "DOCUMENT_SENT",
    "DOCUMENT_UPDATED",
}

_PARTIAL_TOKENS = {
    "PARTIALLY_PAID",
    "PARTIAL",
    "PARTIAL_PAYMENT",
    "PART_PAYMENT",
    "PARTLY_PAID",
}

# Generic lifecycle values that are never evidence of a payment on their own.
_DOCUMENT_LIFECYCLE_TOKENS = {
    "DRAFT",
    "ISSUED",
    "SENT",
    "CREATED",
    "UPDATED",
    "DELETED",
    "PROFORMA_CREATED",
    "PROFORMA_SENT",
    "PROFORMA_UPDATED",
    "DOCUMENT_CREATED",
    "DOCUMENT_SENT",
    "DOCUMENT_UPDATED",
}

# Tokens that unambiguously describe payment state (unlike a bare "SUCCESS",
# which some ERPs also use as a webhook-delivery status).
_PAYMENT_SPECIFIC_TOKENS = {
    "PAID",
    "UNPAID",
    "NOT_PAID",
    "PARTIALLY_PAID",
    "PARTIAL",
    "PARTIAL_PAYMENT",
    "PART_PAYMENT",
    "PARTLY_PAID",
    "REFUNDED",
    "PAYMENT_RECEIVED",
    "PAYMENT_SUCCESS",
    "PAYMENT_SUCCESSFUL",
    "PAYMENT_SUCCEEDED",
    "PAYMENT_CAPTURED",
    "PAYMENT_SETTLED",
    "PAYMENT_COMPLETED",
    "PAYMENT_CONFIRMED",
    "PAYMENT_FAILED",
    "PAYMENT_CANCELLED",
    "PAYMENT_CANCELED",
    "PAYMENT_PENDING",
    "PAYMENT_PROCESSING",
    "PAYMENT_INITIATED",
    "PAYMENT_REFUNDED",
    "PAYMENT_UNVERIFIED",
}


@dataclass
class ParsedPaymentEvent:
    """Normalised view of one provider webhook payload."""

    event_id: str
    event_type: str
    raw_status: str
    status_token: str
    is_success: bool
    status_reason: str
    has_payment_context: bool

    crm_proforma_id: Optional[int] = None
    external_proforma_id: Optional[str] = None
    proforma_number: Optional[str] = None

    transaction_id: Optional[str] = None
    external_payment_id: Optional[str] = None

    amount: Optional[float] = None
    cumulative_paid: Optional[float] = None
    currency: str = "INR"
    payment_method: str = "BANK_TRANSFER"
    bank_name: Optional[str] = None
    payment_date: datetime = None  # type: ignore[assignment]
    is_partial_hint: bool = False

    def __post_init__(self) -> None:
        if self.payment_date is None:
            self.payment_date = datetime.utcnow()


class ProformaPaymentService:
    """Process confirmed ERP payment events against the CRM Proforma/Lead."""

    # ------------------------------------------------------------------
    # Payload normalisation helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _key(value: Any) -> str:
        return re.sub(r"[^a-z0-9]", "", str(value or "").lower())

    @classmethod
    def _get(cls, mapping: Any, *names: str) -> Any:
        if not isinstance(mapping, dict):
            return None
        normalised = {cls._key(key): value for key, value in mapping.items()}
        for name in names:
            if name in mapping:
                value = mapping.get(name)
                if value not in (None, ""):
                    return value
            value = normalised.get(cls._key(name))
            if value not in (None, ""):
                return value
        return None

    @classmethod
    def _first(cls, mappings: Iterable[Any], *names: str) -> Any:
        for mapping in mappings:
            value = cls._get(mapping, *names)
            if value not in (None, ""):
                return value
        return None

    @classmethod
    def _first_text(cls, mappings: Iterable[Any], *names: str) -> Optional[str]:
        value = cls._first(mappings, *names)
        if value is None or isinstance(value, (dict, list, tuple, set)):
            return None
        text = str(value).strip()
        return text or None

    @classmethod
    def _first_number(cls, mappings: Iterable[Any], *names: str) -> Optional[float]:
        value = cls._first(mappings, *names)
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(",", "").replace("₹", "").replace("Rs.", "").replace("INR", "")
        if not text:
            return None
        try:
            return float(text)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _mapping(value: Any) -> Dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @classmethod
    def _mappings(cls, payload: Mapping[str, Any]) -> Dict[str, Any]:
        data = cls._mapping(cls._get(payload, "data", "payload", "eventData", "event_data", "body"))
        document = cls._mapping(cls._get(payload, "document", "proforma", "invoice", "doc", "bill"))
        data_document = cls._mapping(
            cls._get(data, "document", "proforma", "invoice", "doc", "bill")
        )
        payment = cls._mapping(
            cls._get(
                payload,
                "payment",
                "paymentDetails",
                "payment_details",
                "transaction",
                "transactionDetails",
                "transaction_details",
            )
        )
        data_payment = cls._mapping(
            cls._get(
                data,
                "payment",
                "paymentDetails",
                "payment_details",
                "transaction",
                "transactionDetails",
                "transaction_details",
            )
        )
        document_payment = cls._mapping(
            cls._get(document, "payment", "paymentDetails", "payment_details", "transaction")
        )
        data_document_payment = cls._mapping(
            cls._get(data_document, "payment", "paymentDetails", "payment_details", "transaction")
        )

        metadata: Dict[str, Any] = {}
        for candidate in (
            cls._mapping(cls._get(payload, "metadata", "meta")),
            cls._mapping(cls._get(data, "metadata", "meta")),
            cls._mapping(cls._get(document, "metadata", "meta")),
        ):
            for key, value in candidate.items():
                metadata.setdefault(key, value)

        return {
            "data": data,
            "document": document,
            "data_document": data_document,
            "payment": payment,
            "data_payment": data_payment,
            "document_payment": document_payment,
            "data_document_payment": data_document_payment,
            "metadata": metadata,
        }

    @staticmethod
    def _normalise_token(value: Any) -> str:
        return re.sub(r"[^A-Z0-9]+", "_", str(value or "").upper()).strip("_")

    @classmethod
    def _classify_status(cls, raw_status: str, event_type: str) -> Tuple[bool, str]:
        status_token = cls._normalise_token(raw_status)
        event_token = cls._normalise_token(event_type)

        # An explicit negative/pending signal always wins.  A failed,
        # cancelled, pending or refunded event must never mark a deal WON even
        # when the document itself still carries a stale ``PAID`` status from
        # an earlier transaction.
        if status_token in _IGNORE_TOKENS:
            return False, f"non_success_status:{status_token}"
        if event_token in _IGNORE_TOKENS:
            return False, f"non_success_event:{event_token}"

        if status_token in _SUCCESS_TOKENS:
            return True, "success"
        if status_token and "PAID" in status_token and not (
            "UNPAID" in status_token or "NOT_PAID" in status_token
        ):
            return True, "success"

        if event_token in _SUCCESS_TOKENS:
            return True, "success"
        if (
            event_token
            and "PAID" in event_token
            and "UNPAID" not in event_token
            and "NOT_PAID" not in event_token
        ):
            return True, "success"
        if "PAYMENT" in event_token and any(
            token in event_token for token in ("SUCCESS", "SUCCEED", "CAPTUR", "RECEIV", "SETTLE")
        ):
            return True, "success"

        if status_token:
            return False, f"unverified_status:{status_token}"
        if event_token:
            return False, f"not_a_payment_event:{event_token}"
        return False, "missing_payment_status"

    @classmethod
    def _parse_datetime(cls, value: Any) -> Optional[datetime]:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            timestamp = float(value)
            if timestamp > 1_000_000_000_000:
                timestamp /= 1000.0
            try:
                return datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=None)
            except (OverflowError, OSError, ValueError):
                return None
        text = str(value).strip()
        if not text:
            return None
        if text.isdigit():
            return cls._parse_datetime(int(text))
        cleaned = text.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(cleaned)
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed
        except ValueError:
            pass
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
            "%d-%m-%Y %H:%M:%S",
            "%d-%m-%Y",
        ):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        return None

    @classmethod
    def _payment_method(cls, value: Any) -> str:
        token = cls._normalise_token(value)
        if not token:
            return "BANK_TRANSFER"
        if "RAZORPAY" in token:
            return "RAZORPAY"
        if "UPI" in token:
            return "UPI"
        if "NEFT" in token or "RTGS" in token or "IMPS" in token:
            return "NEFT_RTGS"
        if "CARD" in token:
            return "CARD"
        if "CASH" in token:
            return "CASH"
        if "CHEQUE" in token or "CHECK" in token:
            return "CHEQUE"
        if "BANK" in token or "TRANSFER" in token:
            return "BANK_TRANSFER"
        return token[:50]

    @staticmethod
    def _clean(value: Any, limit: int) -> Optional[str]:
        if value is None or isinstance(value, (dict, list, tuple, set)):
            return None
        text = str(value).strip()
        if not text:
            return None
        return text[:limit]

    @classmethod
    def _header_event_id(cls, headers: Optional[Mapping[str, Any]]) -> Optional[str]:
        if not headers:
            return None
        normalised = {str(key).lower(): value for key, value in headers.items()}
        for name in (
            "x-waquote-event-id",
            "x-webhook-event-id",
            "x-webhook-id",
            "x-event-id",
            "x-delivery-id",
            "waquote-event-id",
        ):
            value = normalised.get(name)
            if value:
                return str(value).strip()
        return None

    @classmethod
    def parse_payment_event(
        cls,
        payload: Mapping[str, Any],
        headers: Optional[Mapping[str, Any]] = None,
    ) -> ParsedPaymentEvent:
        payload = payload if isinstance(payload, dict) else {}
        maps = cls._mappings(payload)
        data = maps["data"]
        document = maps["document"]
        data_document = maps["data_document"]
        payment = maps["payment"]
        data_payment = maps["data_payment"]
        document_payment = maps["document_payment"]
        data_document_payment = maps["data_document_payment"]
        metadata = maps["metadata"]

        payment_maps = [payment, data_payment, document_payment, data_document_payment]
        document_maps = [document, data_document]
        status_maps = payment_maps + document_maps + [data, payload]

        event_type = cls._first_text(
            [payload, data], "event", "eventType", "event_type", "type", "action"
        ) or ""

        explicit_payment_status = cls._first_text(
            status_maps,
            "paymentStatus",
            "payment_status",
            "paymentState",
            "payment_state",
        )
        generic_status = cls._first_text(status_maps, "status")

        event_token = cls._normalise_token(event_type)
        event_mentions_payment = "PAYMENT" in event_token or "PAID" in event_token
        document_event = (
            any(
                marker in event_token
                for marker in ("PROFORMA", "DOCUMENT", "QUOTATION", "INVOICE")
            )
            and not event_mentions_payment
        )

        raw_status = explicit_payment_status or ""
        if not raw_status and generic_status:
            generic_token = cls._normalise_token(generic_status)
            # A document lifecycle status ("issued", "sent", ...) must not be
            # mistaken for a payment status.  When the event itself describes
            # a payment, let the event type drive the decision instead.
            if generic_token not in _DOCUMENT_LIFECYCLE_TOKENS:
                raw_status = generic_status

        status_token = cls._normalise_token(raw_status)

        amount = cls._first_number(
            payment_maps,
            "amount",
            "paidAmount",
            "paid_amount",
            "amountPaid",
            "amount_paid",
            "receivedAmount",
            "received_amount",
            "transactionAmount",
            "transaction_amount",
            "paymentAmount",
            "payment_amount",
            "value",
        )
        if amount is None:
            amount = cls._first_number(
                [data, payload],
                "paymentAmount",
                "payment_amount",
                "transactionAmount",
                "transaction_amount",
                "amount",
            )

        cumulative_paid = cls._first_number(
            document_maps + [data, payload],
            "totalPaid",
            "total_paid",
            "cumulativePaid",
            "cumulative_paid",
            "amountPaid",
            "amount_paid",
            "paidAmount",
            "paid_amount",
        )

        transaction_id = cls._first_text(
            payment_maps,
            "transactionId",
            "transaction_id",
            "transactionReference",
            "transaction_reference",
            "gatewayPaymentId",
            "gateway_payment_id",
            "razorpayPaymentId",
            "razorpay_payment_id",
            "utr",
            "utrNumber",
            "utr_number",
            "bankReference",
            "bank_reference",
            "paymentReference",
            "payment_reference",
            "referenceId",
            "reference_id",
            "reference",
            "txnId",
            "txn_id",
            "paymentId",
            "payment_id",
            "id",
        )
        if not transaction_id:
            transaction_id = cls._first_text(
                [data, payload, metadata],
                "transactionId",
                "transaction_id",
                "transactionReference",
                "transaction_reference",
                "gatewayPaymentId",
                "gateway_payment_id",
                "razorpayPaymentId",
                "razorpay_payment_id",
                "utr",
                "utrNumber",
                "utr_number",
                "bankReference",
                "bank_reference",
                "paymentReference",
                "payment_reference",
                "externalPaymentId",
                "external_payment_id",
                "paymentId",
                "payment_id",
                "txnId",
                "txn_id",
            )

        external_payment_id = cls._first_text(
            payment_maps + [data, payload, metadata],
            "externalPaymentId",
            "external_payment_id",
            "paymentId",
            "payment_id",
            "gatewayPaymentId",
            "gateway_payment_id",
            "razorpayPaymentId",
            "razorpay_payment_id",
            "transactionId",
            "transaction_id",
        )

        crm_proforma_raw = cls._first(
            [metadata, payload, data, document],
            "crmProformaId",
            "crm_proforma_id",
        )
        crm_proforma_id = None
        if crm_proforma_raw is not None:
            try:
                crm_proforma_id = int(str(crm_proforma_raw).strip().replace("local_", ""))
            except (TypeError, ValueError):
                crm_proforma_id = None

        external_proforma_id = cls._first_text(
            document_maps + [data, payload, metadata],
            "externalProformaId",
            "external_proforma_id",
            "proformaId",
            "proforma_id",
            "documentId",
            "document_id",
            "docId",
            "doc_id",
        )
        if not external_proforma_id:
            external_proforma_id = cls._first_text(
                document_maps,
                "id",
            )
        if not external_proforma_id:
            proforma_obj = cls._mapping(cls._get(payload, "proforma"))
            external_proforma_id = cls._first_text(
                [proforma_obj], "id", "proformaId", "proforma_id", "externalId", "external_id"
            )

        proforma_number = cls._first_text(
            document_maps + [data, payload, metadata],
            "proformaNumber",
            "proforma_number",
            "crmProformaNumber",
            "crm_proforma_number",
            "documentNumber",
            "document_number",
            "docNumber",
            "doc_number",
            "docNo",
            "doc_no",
            "number",
        )

        # A bare top-level numeric id is not treated as a Proforma id.  The
        # external document id is the only safe mapping; CRM ids must be sent
        # explicitly as crmProformaId/metadata.crmProformaId.
        if external_proforma_id:
            external_proforma_id = cls._clean(external_proforma_id, 100)

        is_success, status_reason = cls._classify_status(raw_status, event_type)
        partial_hint = status_token in _PARTIAL_TOKENS or event_token in _PARTIAL_TOKENS

        has_payment_context = bool(
            payment
            or data_payment
            or document_payment
            or data_document_payment
            or explicit_payment_status
            or event_mentions_payment
            or transaction_id
            or status_token in _PAYMENT_SPECIFIC_TOKENS
        )
        if document_event and not (
            payment
            or data_payment
            or document_payment
            or data_document_payment
            or transaction_id
        ):
            # e.g. "proforma.sent" carrying status=SUCCESS and the document
            # total: that is a delivery event, not proof of money received.
            # A bare document-level paymentStatus is not enough on a
            # lifecycle event because it may simply reflect the document's
            # current state (or an advance paid before the document existed).
            has_payment_context = False
        if (
            not has_payment_context
            and not event_type
            and status_token in _SUCCESS_TOKENS
            and amount is not None
        ):
            # A minimal callback may omit the event name and send only
            # status=SUCCESS with an amount.
            has_payment_context = True

        payment_date = cls._first(
            payment_maps + [data, payload],
            "paymentDate",
            "payment_date",
            "paidAt",
            "paid_at",
            "transactionDate",
            "transaction_date",
        )
        if payment_date is None:
            payment_date = cls._first(payment_maps, "date", "createdAt", "created_at")
        parsed_payment_date = cls._parse_datetime(payment_date)

        bank_name = cls._first_text(
            payment_maps + [data, payload],
            "bankName",
            "bank_name",
            "bank",
        )
        currency = cls._first_text(
            payment_maps + [data, payload, document],
            "currency",
            "currencyCode",
            "currency_code",
        ) or "INR"

        method_raw = cls._first(
            payment_maps + [data, payload],
            "paymentMethod",
            "payment_method",
            "method",
            "paymentMode",
            "payment_mode",
            "mode",
            "gateway",
        )

        event_id = (
            cls._header_event_id(headers)
            or cls._first_text(
                [payload, data, metadata],
                "eventId",
                "event_id",
                "webhookId",
                "webhook_id",
                "deliveryId",
                "delivery_id",
                "idempotencyKey",
                "idempotency_key",
            )
        )

        return ParsedPaymentEvent(
            event_id=cls._clean(event_id, 191) or "",
            event_type=event_type[:100],
            raw_status=raw_status,
            status_token=status_token,
            is_success=is_success,
            status_reason=status_reason,
            has_payment_context=has_payment_context,
            crm_proforma_id=crm_proforma_id,
            external_proforma_id=external_proforma_id,
            proforma_number=cls._clean(proforma_number, 100),
            transaction_id=cls._clean(transaction_id, 150),
            external_payment_id=cls._clean(external_payment_id, 150),
            amount=amount,
            cumulative_paid=cumulative_paid,
            currency=(currency or "INR")[:10],
            payment_method=cls._payment_method(method_raw),
            bank_name=cls._clean(bank_name, 100),
            payment_date=parsed_payment_date or datetime.utcnow(),
            is_partial_hint=partial_hint,
        )

    # ------------------------------------------------------------------
    # Resolution helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _lookup_proforma(
        db: Session,
        *,
        crm_id: Optional[int] = None,
        external_id: Optional[str] = None,
        number: Optional[str] = None,
    ) -> Optional[Quotation]:
        if crm_id is not None:
            doc = (
                db.query(Quotation)
                .filter(Quotation.id == crm_id, Quotation.doc_type == "proforma")
                .first()
            )
            if doc:
                return doc
        if external_id:
            doc = (
                db.query(Quotation)
                .filter(
                    Quotation.external_proforma_id == external_id,
                    Quotation.doc_type == "proforma",
                )
                .first()
            )
            if doc:
                return doc
            # Some deployments prefix the stored value with "local_".
            if external_id.startswith("local_"):
                doc = (
                    db.query(Quotation)
                    .filter(
                        Quotation.external_proforma_id == external_id.replace("local_", "", 1),
                        Quotation.doc_type == "proforma",
                    )
                    .first()
                )
                if doc:
                    return doc
        if number:
            doc = (
                db.query(Quotation)
                .filter(
                    Quotation.doc_number == number,
                    Quotation.doc_type == "proforma",
                )
                .first()
            )
            if doc:
                return doc
        return None

    @classmethod
    def resolve_proforma(cls, db: Session, parsed: ParsedPaymentEvent) -> Optional[Quotation]:
        """Resolve the exact Proforma, rejecting ambiguous identifier sets.

        Every identifier supplied by the provider must point at the same CRM
        Proforma.  If the external document id points at one Proforma while the
        document number or ``crmProformaId`` points at another, the event is
        rejected instead of guessing.  This is what prevents a payment from
        being applied to the wrong Lead.
        """
        resolved: Dict[int, Quotation] = {}
        for doc in (
            cls._lookup_proforma(db, crm_id=parsed.crm_proforma_id)
            if parsed.crm_proforma_id is not None
            else None,
            cls._lookup_proforma(db, external_id=parsed.external_proforma_id)
            if parsed.external_proforma_id
            else None,
            cls._lookup_proforma(db, number=parsed.proforma_number)
            if parsed.proforma_number
            else None,
        ):
            if doc is not None:
                resolved[doc.id] = doc

        if len(resolved) > 1:
            return None
        if not resolved:
            return None
        return next(iter(resolved.values()))

    @staticmethod
    def _resolve_lead(db: Session, proforma: Quotation) -> Optional[Lead]:
        if proforma.lead_id:
            lead = db.query(Lead).filter(Lead.id == proforma.lead_id).first()
            if lead:
                return lead
        if proforma.customer_id:
            customer = db.query(Customer).filter(Customer.id == proforma.customer_id).first()
            if customer and customer.converted_from_lead:
                return db.query(Lead).filter(Lead.id == customer.converted_from_lead).first()
        return None

    @staticmethod
    def _resolve_customer(
        db: Session, proforma: Quotation, lead: Lead, now: datetime
    ) -> Customer:
        if proforma.customer_id:
            customer = db.query(Customer).filter(Customer.id == proforma.customer_id).first()
            if customer:
                return customer
        customer = (
            db.query(Customer)
            .filter(Customer.converted_from_lead == lead.id)
            .first()
        )
        if customer:
            return customer
        customer = Customer(
            company_name=lead.company or lead.name or "Valued Customer",
            contact_name=lead.name or "Valued Customer",
            phone=lead.phone or "9999999999",
            email=lead.email,
            location=lead.location or lead.city,
            converted_from_lead=lead.id,
            created_at=now,
        )
        db.add(customer)
        db.flush()
        return customer

    # ------------------------------------------------------------------
    # Financial calculation
    # ------------------------------------------------------------------
    @staticmethod
    def _calculate_amounts(
        proforma: Quotation, parsed: ParsedPaymentEvent
    ) -> Tuple[float, float, float, bool]:
        """Return (transaction_amount, total_paid, outstanding, fully_paid)."""
        grand_total = float(proforma.grand_total or 0.0)
        existing_paid = float(proforma.amount_paid or 0.0)

        if parsed.amount is not None:
            transaction_amount = float(parsed.amount)
            total_paid = existing_paid + transaction_amount
            if parsed.cumulative_paid is not None:
                total_paid = max(total_paid, float(parsed.cumulative_paid))
        elif parsed.cumulative_paid is not None:
            total_paid = max(existing_paid, float(parsed.cumulative_paid))
            transaction_amount = total_paid - existing_paid
        else:
            # A PAID event without an amount is treated as payment of the
            # remaining balance.  A PARTIALLY_PAID event without an amount is
            # ambiguous and must not invent a number.
            if parsed.is_partial_hint:
                transaction_amount = 0.0
                total_paid = existing_paid
            else:
                transaction_amount = max(0.0, grand_total - existing_paid)
                total_paid = existing_paid + transaction_amount

        total_paid = round(max(existing_paid, total_paid), 2)
        transaction_amount = round(max(0.0, transaction_amount), 2)
        outstanding = round(max(0.0, grand_total - total_paid), 2)
        fully_paid = grand_total <= 0.0 or total_paid >= grand_total - 0.01
        return transaction_amount, total_paid, outstanding, fully_paid

    @staticmethod
    def _fingerprint_transaction(
        parsed: ParsedPaymentEvent, proforma: Quotation, amount: float
    ) -> str:
        # Deliberately excludes the payment date: an ERP retry may arrive on a
        # later day without a transaction id, and it must still be recognised
        # as the same payment rather than double-counted.
        seed = "|".join(
            [
                PROVIDER,
                str(proforma.id),
                str(proforma.external_proforma_id or ""),
                parsed.status_token,
                f"{amount:.2f}",
            ]
        )
        return "AUTO-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:40]

    @staticmethod
    def _event_id_for(parsed: ParsedPaymentEvent, proforma: Quotation, txn_id: str) -> str:
        if parsed.event_id:
            return parsed.event_id
        seed = f"{PROVIDER}|{proforma.id}|{txn_id}|{parsed.status_token}"
        return "evt_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:56]

    # ------------------------------------------------------------------
    # Notification / timeline helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _add_notification(
        db: Session,
        user_id: Optional[int],
        *,
        title: str,
        message: str,
        notification_type: str,
        link_url: Optional[str],
        now: datetime,
    ) -> None:
        if not user_id:
            return
        db.add(
            Notification(
                user_id=user_id,
                title=title[:150],
                message=message,
                notification_type=notification_type,
                link_url=(link_url or "")[:255] or None,
                is_read=False,
                created_at=now,
            )
        )

    @staticmethod
    def _users_for_roles_or_department(
        db: Session, roles: Sequence[str], department: str
    ) -> List[User]:
        return (
            db.query(User)
            .filter(
                User.is_active == True,  # noqa: E712 - SQLAlchemy expression
                or_(User.role.in_(list(roles)), User.department == department),
            )
            .all()
        )

    @staticmethod
    def _log_integration(
        db: Session,
        *,
        status: str,
        message: str,
        event_type: str = "PAYMENT_WEBHOOK",
    ) -> None:
        db.add(
            IntegrationLog(
                integration_type=PROVIDER,
                event_type=event_type,
                status=status,
                message=message[:2000],
                created_at=datetime.utcnow(),
            )
        )

    @staticmethod
    def _add_timeline(
        db: Session,
        *,
        lead: Lead,
        customer: Customer,
        stage: str,
        previous_status: Optional[str],
        new_status: str,
        title: str,
        description: str,
        now: datetime,
    ) -> None:
        db.add(
            WorkflowTimelineEvent(
                lead_id=lead.id,
                customer_id=customer.id,
                stage=stage,
                previous_status=previous_status,
                new_status=new_status,
                performed_by_id=None,
                performed_by_name="WA Quote ERP",
                role="SYSTEM",
                title=title[:150],
                description=description,
                created_at=now,
            )
        )

    # ------------------------------------------------------------------
    # Handoff upserts
    # ------------------------------------------------------------------
    @classmethod
    def _upsert_finance_handoff(
        cls,
        db: Session,
        *,
        proforma: Quotation,
        lead: Lead,
        customer: Customer,
        total_paid: float,
        fully_paid: bool,
        parsed: ParsedPaymentEvent,
        transaction_id: str,
        now: datetime,
    ) -> Tuple[FinanceHandoff, str]:
        handoff = (
            db.query(FinanceHandoff)
            .filter(FinanceHandoff.proforma_id == proforma.id)
            .order_by(desc(FinanceHandoff.id))
            .first()
        )
        if not handoff:
            # A handoff created before the Proforma was linked can still be
            # reused, but a handoff belonging to a *different* Proforma on the
            # same Lead must never be updated by this payment.
            handoff = (
                db.query(FinanceHandoff)
                .filter(
                    FinanceHandoff.lead_id == lead.id,
                    FinanceHandoff.proforma_id.is_(None),
                )
                .order_by(desc(FinanceHandoff.id))
                .first()
            )
        old_status = handoff.status if handoff else "PAYMENT_PENDING"

        sales_employee_id = lead.assigned_to
        sales_employee_name = None
        if sales_employee_id:
            employee = db.query(Employee).filter(Employee.id == sales_employee_id).first()
            if employee:
                sales_employee_name = employee.name

        grand_total = float(proforma.grand_total or 0.0)
        if not handoff:
            handoff = FinanceHandoff(
                lead_id=lead.id,
                customer_id=customer.id,
                quotation_id=proforma.source_quotation_id or proforma.id,
                quotation_number=proforma.source_quotation_number or proforma.doc_number,
                quotation_url=proforma.pdf_url,
                proforma_id=proforma.id,
                proforma_number=proforma.doc_number,
                selected_bundle=proforma.selected_bundle,
                product_category=proforma.product_category,
                customer_name=proforma.customer_name or lead.name,
                company_name=proforma.company_name or lead.company,
                phone=proforma.phone or lead.phone,
                email=proforma.email or lead.email,
                address=proforma.address,
                sales_employee_id=sales_employee_id,
                sales_employee_name=sales_employee_name or "Unassigned Sales",
                products_services=proforma.line_items or [],
                final_amount=grand_total,
                paid_amount=0.0,
                status="PAYMENT_PENDING",
                payment_status="PAYMENT_PENDING",
                customer_requirements=lead.requirement_notes,
                created_at=now,
            )
            db.add(handoff)
            db.flush()
        else:
            if not handoff.proforma_id:
                handoff.proforma_id = proforma.id
            if not handoff.proforma_number:
                handoff.proforma_number = proforma.doc_number
            if not handoff.quotation_id:
                handoff.quotation_id = proforma.source_quotation_id or proforma.id
            if not handoff.quotation_number:
                handoff.quotation_number = (
                    proforma.source_quotation_number or proforma.doc_number
                )
            if not handoff.quotation_url:
                handoff.quotation_url = proforma.pdf_url
            if not handoff.customer_name:
                handoff.customer_name = proforma.customer_name or lead.name
            if not handoff.company_name:
                handoff.company_name = proforma.company_name or lead.company
            if not handoff.phone:
                handoff.phone = proforma.phone or lead.phone
            if not handoff.email:
                handoff.email = proforma.email or lead.email
            if not handoff.sales_employee_id:
                handoff.sales_employee_id = sales_employee_id
            if not handoff.sales_employee_name:
                handoff.sales_employee_name = sales_employee_name or "Unassigned Sales"
            if not handoff.products_services:
                handoff.products_services = proforma.line_items or []
            if not handoff.final_amount or float(handoff.final_amount) <= 0:
                handoff.final_amount = grand_total

        effective_paid = max(float(handoff.paid_amount or 0.0), float(total_paid))
        handoff.paid_amount = round(effective_paid, 2)
        handoff.payment_mode = parsed.payment_method
        handoff.bank_reference = transaction_id
        handoff.bank_name = parsed.bank_name
        handoff.payment_date = parsed.payment_date
        handoff.confirmed_at = now
        handoff.payment_status = (
            PAYMENT_STATUS_PAID if fully_paid else PAYMENT_STATUS_PARTIALLY_PAID
        )
        handoff.status = (
            "PAID"
            if fully_paid or effective_paid >= float(handoff.final_amount or 0.0) - 0.01
            else "PAYMENT_PENDING"
        )
        return handoff, old_status

    @classmethod
    def _upsert_support_handoff(
        cls,
        db: Session,
        *,
        proforma: Quotation,
        lead: Lead,
        customer: Customer,
        finance_handoff: FinanceHandoff,
        total_paid: float,
        fully_paid: bool,
        parsed: ParsedPaymentEvent,
        now: datetime,
    ) -> Tuple[SupportHandoff, bool]:
        support = (
            db.query(SupportHandoff)
            .filter(SupportHandoff.finance_handoff_id == finance_handoff.id)
            .first()
        )
        if not support:
            support = (
                db.query(SupportHandoff)
                .filter(SupportHandoff.proforma_id == proforma.id)
                .order_by(desc(SupportHandoff.id))
                .first()
            )
        if not support:
            # Only reuse a Lead-level onboarding record that is not already
            # tied to a different Proforma/purchase.
            support = (
                db.query(SupportHandoff)
                .filter(
                    SupportHandoff.lead_id == lead.id,
                    SupportHandoff.proforma_id.is_(None),
                )
                .order_by(desc(SupportHandoff.id))
                .first()
            )

        created = False
        payment_status = (
            PAYMENT_STATUS_PAID if fully_paid else PAYMENT_STATUS_PARTIALLY_PAID
        )
        if not support:
            created = True
            support = SupportHandoff(
                finance_handoff_id=finance_handoff.id,
                lead_id=lead.id,
                customer_id=customer.id,
                deal_id=lead.id,
                customer_name=proforma.customer_name or lead.name,
                company_name=proforma.company_name or lead.company,
                phone=proforma.phone or lead.phone,
                email=proforma.email or lead.email,
                product_service=(
                    proforma.selected_bundle
                    or proforma.product_category
                    or "CRM Subscription"
                ),
                customer_users_count=1,
                total_deal_amount=float(proforma.grand_total or 0.0),
                purchased_products=proforma.line_items or [],
                quotation_number=(
                    proforma.source_quotation_number or proforma.doc_number
                ),
                quotation_url=proforma.pdf_url,
                proforma_id=proforma.id,
                proforma_number=proforma.doc_number,
                selected_bundle=proforma.selected_bundle,
                product_category=proforma.product_category,
                paid_amount=float(total_paid),
                payment_status=payment_status,
                payment_date=parsed.payment_date,
                sales_employee_id=finance_handoff.sales_employee_id,
                sales_employee_name=finance_handoff.sales_employee_name,
                customer_requirements=lead.requirement_notes,
                onboarding_status=SUPPORT_STATUS_NEW,
                won_at=now,
                created_at=now,
            )
            db.add(support)
            db.flush()
        else:
            if not support.finance_handoff_id:
                support.finance_handoff_id = finance_handoff.id
            if not support.customer_id:
                support.customer_id = customer.id
            if not support.proforma_id:
                support.proforma_id = proforma.id
            if not support.proforma_number:
                support.proforma_number = proforma.doc_number
            support.paid_amount = round(
                max(float(support.paid_amount or 0.0), float(total_paid)), 2
            )
            support.payment_status = payment_status
            support.payment_date = parsed.payment_date
            if not support.won_at:
                support.won_at = now

        if not support.purchase_snapshot:
            support.purchase_snapshot = build_purchase_snapshot(
                support, proforma, finance_handoff
            )
        return support, created

    # ------------------------------------------------------------------
    # Result helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _duplicate_result(
        db: Session,
        *,
        proforma: Optional[Quotation],
        lead: Optional[Lead],
        parsed: ParsedPaymentEvent,
        transaction_id: Optional[str],
        reason: str,
    ) -> Dict[str, Any]:
        ProformaPaymentService._log_integration(
            db,
            status="INFO",
            message=(
                f"Duplicate payment event ignored for Proforma "
                f"#{proforma.doc_number if proforma else 'unknown'} "
                f"(txn={transaction_id or 'n/a'}, event={parsed.event_id or 'n/a'})."
            ),
        )
        db.commit()
        return {
            "ok": True,
            "status": "duplicate",
            "duplicate": True,
            "reason": reason,
            "proforma_id": proforma.id if proforma else None,
            "proforma_number": proforma.doc_number if proforma else None,
            "lead_id": lead.id if lead else None,
            "lead_status": lead.status if lead else None,
            "transaction_id": transaction_id,
        }

    @staticmethod
    def _ignored_result(
        db: Session,
        *,
        parsed: ParsedPaymentEvent,
        reason: str,
        proforma: Optional[Quotation] = None,
        lead: Optional[Lead] = None,
        status: str = "ignored",
    ) -> Dict[str, Any]:
        ProformaPaymentService._log_integration(
            db,
            status="INFO",
            message=(
                f"Payment webhook {status}: {reason} "
                f"(event={parsed.event_id or 'n/a'}, "
                f"proforma={proforma.doc_number if proforma else parsed.external_proforma_id or 'unknown'}, "
                f"status={parsed.raw_status or 'none'})."
            ),
        )
        db.commit()
        return {
            "ok": True,
            "status": status,
            "duplicate": False,
            "reason": reason,
            "proforma_id": proforma.id if proforma else None,
            "proforma_number": proforma.doc_number if proforma else None,
            "lead_id": lead.id if lead else None,
            "lead_status": lead.status if lead else None,
            "transaction_id": parsed.transaction_id,
        }

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    @classmethod
    def process_webhook(
        cls,
        db: Session,
        payload: Mapping[str, Any],
        headers: Optional[Mapping[str, Any]] = None,
        *,
        source: str = PROVIDER,
        auth_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process one authenticated payment webhook delivery.

        The method always acknowledges an event it intentionally ignores so a
        provider does not retry forever.  Authentication failures are raised by
        the router before this method is called.
        """
        parsed = cls.parse_payment_event(payload, headers)

        if not parsed.has_payment_context:
            return cls._ignored_result(
                db,
                parsed=parsed,
                reason=parsed.status_reason or "not_a_payment_event",
            )

        if not parsed.is_success:
            return cls._ignored_result(
                db,
                parsed=parsed,
                reason=parsed.status_reason or "non_success_payment_status",
            )

        proforma = cls.resolve_proforma(db, parsed)
        if not proforma:
            return cls._ignored_result(
                db,
                parsed=parsed,
                reason="proforma_not_found_or_ambiguous",
            )

        lead = cls._resolve_lead(db, proforma)
        if not lead:
            return cls._ignored_result(
                db,
                parsed=parsed,
                reason="lead_not_found_for_proforma",
                proforma=proforma,
            )

        transaction_amount, total_paid, outstanding, fully_paid = cls._calculate_amounts(
            proforma, parsed
        )
        if transaction_amount <= 0:
            return cls._duplicate_result(
                db,
                proforma=proforma,
                lead=lead,
                parsed=parsed,
                transaction_id=parsed.transaction_id,
                reason="no_new_amount_to_apply",
            )

        transaction_id = parsed.transaction_id or cls._fingerprint_transaction(
            parsed, proforma, transaction_amount
        )
        event_id = cls._event_id_for(parsed, proforma, transaction_id)
        now = datetime.utcnow()

        # ---- Idempotency pre-checks -------------------------------------
        existing_event = (
            db.query(ProformaPaymentEvent)
            .filter(ProformaPaymentEvent.event_id == event_id)
            .first()
        )
        if existing_event:
            return cls._duplicate_result(
                db,
                proforma=proforma,
                lead=lead,
                parsed=parsed,
                transaction_id=transaction_id,
                reason="duplicate_event_id",
            )
        existing_transaction = (
            db.query(ProformaPaymentEvent)
            .filter(
                ProformaPaymentEvent.provider == PROVIDER,
                ProformaPaymentEvent.transaction_id == transaction_id,
            )
            .first()
        )
        if existing_transaction:
            return cls._duplicate_result(
                db,
                proforma=proforma,
                lead=lead,
                parsed=parsed,
                transaction_id=transaction_id,
                reason="duplicate_transaction_id",
            )
        existing_payment = (
            db.query(Payment)
            .filter(
                Payment.invoice_id == proforma.id,
                Payment.transaction_reference == transaction_id,
            )
            .first()
        )
        if existing_payment:
            return cls._duplicate_result(
                db,
                proforma=proforma,
                lead=lead,
                parsed=parsed,
                transaction_id=transaction_id,
                reason="payment_already_recorded",
            )

        payment_status = (
            PAYMENT_STATUS_PAID if fully_paid else PAYMENT_STATUS_PARTIALLY_PAID
        )

        try:
            # ---- Idempotency row (unique event + transaction) -----------
            event = ProformaPaymentEvent(
                event_id=event_id,
                provider=PROVIDER,
                event_type=parsed.event_type,
                status="PROCESSED",
                external_proforma_id=proforma.external_proforma_id,
                proforma_number=proforma.doc_number,
                external_payment_id=parsed.external_payment_id,
                transaction_id=transaction_id,
                quotation_id=proforma.id,
                lead_id=lead.id,
                amount=transaction_amount,
                currency=parsed.currency,
                payment_method=parsed.payment_method,
                payment_status=payment_status,
                raw_payload=dict(payload),
                created_at=now,
                processed_at=now,
            )
            db.add(event)
            db.flush()

            # ---- Proforma financials -----------------------------------
            old_paid = float(proforma.amount_paid or 0.0)
            proforma.amount_paid = round(max(old_paid, total_paid), 2)
            proforma.payment_status = "paid" if fully_paid else "partial"
            if not proforma.external_proforma_id and parsed.external_proforma_id:
                proforma.external_proforma_id = parsed.external_proforma_id

            customer = cls._resolve_customer(db, proforma, lead, now)

            # ---- Finance / Support handoffs ----------------------------
            finance_handoff, old_finance_status = cls._upsert_finance_handoff(
                db,
                proforma=proforma,
                lead=lead,
                customer=customer,
                total_paid=total_paid,
                fully_paid=fully_paid,
                parsed=parsed,
                transaction_id=transaction_id,
                now=now,
            )
            support_handoff, support_created = cls._upsert_support_handoff(
                db,
                proforma=proforma,
                lead=lead,
                customer=customer,
                finance_handoff=finance_handoff,
                total_paid=total_paid,
                fully_paid=fully_paid,
                parsed=parsed,
                now=now,
            )

            # ---- Payment row -------------------------------------------
            # Derive the number from the unique event row instead of the last
            # Payment id.  Two concurrent ERP deliveries must never collide on
            # payment_number, because a collision would roll back a legitimate
            # payment and be reported to the provider as a duplicate.
            payment_number = f"PAY-{now.year}-WQ{event.id:04d}"
            payment = Payment(
                payment_number=payment_number,
                customer_id=customer.id,
                invoice_id=proforma.id,
                finance_handoff_id=finance_handoff.id,
                lead_id=lead.id,
                amount=transaction_amount,
                currency=parsed.currency,
                payment_method=parsed.payment_method,
                payment_type="ONLINE",
                status="PAID",
                transaction_reference=transaction_id,
                bank_name=parsed.bank_name,
                payment_date=parsed.payment_date,
                notes=(
                    f"External payment received via WA Quote ERP for Proforma "
                    f"#{proforma.doc_number}. Transaction: {transaction_id}. "
                    f"Total paid: Rs. {total_paid:,.2f}; "
                    f"Balance: Rs. {outstanding:,.2f}."
                ),
                created_at=now,
            )
            db.add(payment)
            db.flush()
            event.payment_id = payment.id

            # ---- Lead status -> WON ------------------------------------
            old_lead_status = lead.status or STATUS_NEW
            canonical_old = normalize_lead_status(old_lead_status)
            status_changed = False
            if canonical_old not in WON_OR_CONVERTED_STATUSES:
                lead.status = STATUS_WON
                status_changed = True
                db.add(
                    LeadStatusHistory(
                        lead_id=lead.id,
                        old_status=old_lead_status,
                        new_status=STATUS_WON,
                        changed_by=None,
                        changed_at=now,
                    )
                )
            # An existing WON or CONVERTED_TO_SUPPORT status is left untouched.
            # CONVERTED_TO_SUPPORT is a later lifecycle state, so a late
            # payment must not downgrade it back to WON.

            # Keep the legacy QuoteTask mirrors in step with the Proforma.
            lead.quotetask_quotation_status = payment_status
            lead.quotetask_po_status = payment_status
            lead.quotetask_quotation_number = proforma.doc_number
            lead.quotetask_po_number = proforma.doc_number
            lead.quotetask_quotation_amount = float(proforma.grand_total or 0.0)
            lead.quotetask_synced_at = now

            # ---- Activity timeline -------------------------------------
            payment_description = (
                f"Payment received via WA Quote ERP: Rs. {transaction_amount:,.2f} "
                f"({parsed.payment_method.replace('_', ' ').title()}), "
                f"Transaction ID: {transaction_id}. "
                f"Proforma #{proforma.doc_number}. "
                f"Total paid: Rs. {total_paid:,.2f}; "
                f"Outstanding: Rs. {outstanding:,.2f}. "
                f"Status: {'PAID' if fully_paid else 'PARTIALLY PAID'}."
            )
            db.add(
                LeadActivity(
                    lead_id=lead.id,
                    customer_id=customer.id,
                    employee_id=None,
                    performed_by=None,
                    activity_type="PAYMENT_RECEIVED",
                    related_entity_type="PROFORMA",
                    related_entity_id=proforma.id,
                    department="SALES",
                    description=payment_description,
                    created_at=now,
                )
            )
            if status_changed:
                db.add(
                    LeadActivity(
                        lead_id=lead.id,
                        customer_id=customer.id,
                        employee_id=None,
                        performed_by=None,
                        activity_type="STATUS_CHANGED",
                        related_entity_type="LEAD",
                        related_entity_id=lead.id,
                        department="SALES",
                        description=(
                            f"Lead status changed automatically from "
                            f"{old_lead_status} -> {STATUS_WON} after verified "
                            f"payment of Rs. {transaction_amount:,.2f} "
                            f"(Proforma #{proforma.doc_number})."
                        ),
                        created_at=now,
                    )
                )

            # ---- Workflow timeline -------------------------------------
            cls._add_timeline(
                db,
                lead=lead,
                customer=customer,
                stage="FINANCE",
                previous_status=old_finance_status,
                new_status=payment_status,
                title="External Payment Received & Verified",
                description=(
                    f"WA Quote ERP confirmed Rs. {transaction_amount:,.2f} via "
                    f"{parsed.payment_method.replace('_', ' ').title()} "
                    f"(Txn {transaction_id}) for Proforma #{proforma.doc_number}. "
                    f"Total paid Rs. {total_paid:,.2f}, balance Rs. {outstanding:,.2f}."
                ),
                now=now,
            )
            if status_changed:
                cls._add_timeline(
                    db,
                    lead=lead,
                    customer=customer,
                    stage="SALES",
                    previous_status=old_lead_status,
                    new_status=STATUS_WON,
                    title="Deal Marked WON by Verified Payment",
                    description=(
                        f"Deal #{lead.id} automatically moved from "
                        f"{old_lead_status} to {STATUS_WON} after the external "
                        f"payment was verified. Sales ownership is unchanged."
                    ),
                    now=now,
                )
            if support_created:
                cls._add_timeline(
                    db,
                    lead=lead,
                    customer=customer,
                    stage="SUPPORT",
                    previous_status=None,
                    new_status=SUPPORT_STATUS_NEW,
                    title="Support Onboarding Handoff Created",
                    description=(
                        f"Customer handed to Support for onboarding after the "
                        f"verified payment on Proforma #{proforma.doc_number}."
                    ),
                    now=now,
                )

            # ---- Notifications -----------------------------------------
            sales_user_id = None
            if lead.assigned_to:
                sales_employee = (
                    db.query(Employee).filter(Employee.id == lead.assigned_to).first()
                )
                if sales_employee:
                    sales_user_id = sales_employee.user_id
            cls._add_notification(
                db,
                sales_user_id,
                title=f"Payment received for Deal #{lead.id} ({lead.name})",
                message=(
                    f"Rs. {transaction_amount:,.2f} received via WA Quote ERP for "
                    f"Proforma #{proforma.doc_number}. "
                    f"Outstanding: Rs. {outstanding:,.2f}. "
                    f"The deal has been marked {'WON' if status_changed else lead.status}."
                ),
                notification_type="PAYMENT_CONFIRMED",
                link_url=f"/leads/{lead.id}",
                now=now,
            )

            finance_message = (
                f"Rs. {transaction_amount:,.2f} received for Proforma "
                f"#{proforma.doc_number} ({proforma.customer_name}). "
                f"Txn: {transaction_id}. Total paid: Rs. {total_paid:,.2f}; "
                f"balance: Rs. {outstanding:,.2f}."
            )
            for finance_user in cls._users_for_roles_or_department(
                db, ["FINANCE", "FINANCE_MANAGER", "FINANCE_EXECUTIVE"], "FINANCE"
            ):
                cls._add_notification(
                    db,
                    finance_user.id,
                    title=f"External payment received: Proforma #{proforma.doc_number}",
                    message=finance_message,
                    notification_type="FINANCE_PAYMENT_RECEIVED",
                    link_url=f"/finance/queue?handoff_id={finance_handoff.id}",
                    now=now,
                )

            if support_created:
                support_message = (
                    f"Payment verified for {proforma.customer_name or lead.name} "
                    f"(Proforma #{proforma.doc_number}). "
                    f"Please initiate onboarding."
                )
                for support_user in cls._users_for_roles_or_department(
                    db,
                    ["SUPPORT", "SUPPORT_MANAGER", "SUPPORT_EXECUTIVE"],
                    "SUPPORT",
                ):
                    cls._add_notification(
                        db,
                        support_user.id,
                        title=(
                            f"New customer ready for onboarding: "
                            f"{proforma.customer_name or lead.name}"
                        ),
                        message=support_message,
                        notification_type="SUPPORT_ONBOARDING",
                        link_url=f"/support?onboarding_id={support_handoff.id}",
                        now=now,
                    )

            # ---- Audit / integration log -------------------------------
            db.add(
                AuditLog(
                    user_id=None,
                    username="WAQuote ERP",
                    action="EXTERNAL_PAYMENT_RECEIVED",
                    entity_type="PROFORMA",
                    entity_id=str(proforma.id),
                    details=(
                        f"Verified payment Rs. {transaction_amount:,.2f} "
                        f"(txn {transaction_id}) for Proforma "
                        f"#{proforma.doc_number}. Lead #{lead.id} "
                        f"{old_lead_status} -> {lead.status}. "
                        f"Total paid Rs. {total_paid:,.2f}; "
                        f"balance Rs. {outstanding:,.2f}."
                    ),
                    created_at=now,
                )
            )
            cls._log_integration(
                db,
                status="SUCCESS",
                message=(
                    f"Processed {source} payment for Proforma "
                    f"#{proforma.doc_number} (lead #{lead.id}, "
                    f"txn {transaction_id}, amount Rs. {transaction_amount:,.2f}, "
                    f"total Rs. {total_paid:,.2f})."
                ),
            )

            db.commit()
        except IntegrityError:
            # A concurrent delivery may have won the unique event/transaction
            # race.  Only acknowledge as a duplicate when that is actually the
            # case; any other integrity failure must reach the provider as a
            # retryable error instead of silently dropping a real payment.
            db.rollback()
            duplicate_event = (
                db.query(ProformaPaymentEvent)
                .filter(ProformaPaymentEvent.event_id == event_id)
                .first()
            )
            duplicate_transaction = (
                db.query(ProformaPaymentEvent)
                .filter(
                    ProformaPaymentEvent.provider == PROVIDER,
                    ProformaPaymentEvent.transaction_id == transaction_id,
                )
                .first()
            )
            if duplicate_event or duplicate_transaction:
                return cls._duplicate_result(
                    db,
                    proforma=proforma,
                    lead=lead,
                    parsed=parsed,
                    transaction_id=transaction_id,
                    reason="concurrent_duplicate",
                )
            logger.exception(
                "Integrity error while processing external payment for Proforma #%s",
                proforma.doc_number,
            )
            cls._log_integration(
                db,
                status="ERROR",
                message=(
                    f"Integrity error while processing payment webhook for "
                    f"Proforma #{proforma.doc_number} (txn {transaction_id})."
                ),
            )
            db.commit()
            raise
        except Exception:
            db.rollback()
            logger.exception(
                "Failed to process external payment for Proforma #%s",
                proforma.doc_number,
            )
            cls._log_integration(
                db,
                status="ERROR",
                message=(
                    f"Failed to process payment webhook for Proforma "
                    f"#{proforma.doc_number} (txn {transaction_id})."
                ),
            )
            db.commit()
            raise

        db.refresh(proforma)
        db.refresh(lead)

        return {
            "ok": True,
            "status": "processed",
            "duplicate": False,
            "reason": None,
            "proforma_id": proforma.id,
            "proforma_number": proforma.doc_number,
            "lead_id": lead.id,
            "lead_status": lead.status,
            "lead_status_changed": status_changed,
            "payment_id": payment.id,
            "payment_number": payment.payment_number,
            "transaction_id": transaction_id,
            "amount_received": transaction_amount,
            "total_paid": float(proforma.amount_paid or 0.0),
            "outstanding_balance": outstanding,
            "payment_status": payment_status,
            "finance_handoff_id": finance_handoff.id,
            "support_handoff_id": support_handoff.id,
            "support_handoff_created": support_created,
            "auth_mode": auth_mode,
            "source": source,
        }

    # ------------------------------------------------------------------
    # Read API used by the Proforma detail / payment history endpoints
    # ------------------------------------------------------------------
    @staticmethod
    def payment_history(db: Session, proforma: Quotation, limit: int = 100) -> Dict[str, Any]:
        payments = (
            db.query(Payment)
            .filter(Payment.invoice_id == proforma.id)
            .order_by(desc(Payment.payment_date), desc(Payment.id))
            .limit(limit)
            .all()
        )
        events = (
            db.query(ProformaPaymentEvent)
            .filter(ProformaPaymentEvent.quotation_id == proforma.id)
            .order_by(desc(ProformaPaymentEvent.id))
            .limit(limit)
            .all()
        )
        event_by_payment = {
            event.payment_id: event for event in events if event.payment_id
        }

        items = []
        for payment in payments:
            event = event_by_payment.get(payment.id)
            items.append(
                {
                    "payment_id": payment.id,
                    "payment_number": payment.payment_number,
                    "amount": float(payment.amount or 0.0),
                    "currency": payment.currency,
                    "payment_method": payment.payment_method,
                    "payment_type": payment.payment_type,
                    "status": payment.status,
                    "transaction_id": payment.transaction_reference,
                    "bank_name": payment.bank_name,
                    "payment_date": (
                        payment.payment_date.isoformat()
                        if payment.payment_date
                        else None
                    ),
                    "external_proforma_id": (
                        event.external_proforma_id if event else None
                    ),
                    "external_payment_id": (
                        event.external_payment_id if event else None
                    ),
                    "source": "WA_QUOTE_ERP",
                    "notes": payment.notes,
                }
            )

        grand_total = float(proforma.grand_total or 0.0)
        amount_paid = float(proforma.amount_paid or 0.0)
        return {
            "ok": True,
            "proforma_id": proforma.id,
            "proforma_number": proforma.doc_number,
            "lead_id": proforma.lead_id,
            "currency": "INR",
            "grand_total": grand_total,
            "amount_paid": amount_paid,
            "outstanding_balance": round(max(0.0, grand_total - amount_paid), 2),
            "payment_status": proforma.payment_status,
            "payment_count": len(items),
            "payments": items,
        }
