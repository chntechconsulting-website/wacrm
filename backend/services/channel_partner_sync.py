"""Read-only synchronisation and webhook processing for WA HRMS partners.

Design rules
------------
* WA HRMS is the system of record; CRM writes never flow back.
* Every local row stores the WA HRMS UUID and a sanitised raw payload.
* Webhooks provide timely updates, polling recovers missed events.
* Webhook event IDs are unique in the database, so retries are idempotent.
* Out-of-order events never overwrite newer local state.
* Full PAN, Aadhaar, bank account numbers and signed document links are never
  persisted. PAN is stored masked; documents are fetched on demand.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import re
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import SessionLocal
from integrations.wahrms_channel_partner.client import (
    ChannelPartnerAPIError,
    ChannelPartnerClient,
    ChannelPartnerNotConfigured,
)
from integrations.wahrms_channel_partner.config import (
    EffectiveConfig,
    get_integration_row,
    load_effective_config,
)
from integrations.wahrms_channel_partner.normalizers import (
    as_bool,
    as_int,
    as_json,
    as_text,
    extract_list,
    extract_object,
    external_id_of,
    first_present,
    get_path,
    ist_iso,
    mask_pan,
    pan_last4,
    parse_date,
    parse_datetime_ist,
    sanitise_document_metadata,
    sanitise_payload,
    scan_related_ids,
    status_value,
)
from models.channel_partner import (
    ChannelPartner,
    ChannelPartnerApplication,
    ChannelPartnerClientAttribution,
    ChannelPartnerCommission,
    ChannelPartnerCoupon,
    ChannelPartnerIntegration,
    ChannelPartnerLead,
    ChannelPartnerLogin,
    ChannelPartnerPayout,
    ChannelPartnerSyncCheckpoint,
    ChannelPartnerSyncRun,
    ChannelPartnerWebhookEvent,
    ChannelPartnerWebhookRejection,
)
from models.lead import Lead, LeadStatusHistory
from models.activity import LeadActivity
from utils.timezone import get_ist_now

logger = logging.getLogger("wacrm.channel_partner")

PARTNER_STATUSES = ("active", "suspended", "terminated")
APPLICATION_STATUSES = ("pending", "approved", "rejected")
LEAD_STATUSES = ("submitted", "qualified", "converted", "rejected", "lost")
COMMISSION_STATUSES = ("on_hold", "available", "in_payout", "paid", "cancelled")
PAYOUT_STATUSES = ("draft", "approved", "paid", "cancelled")

# Channel Partner leads in the main CRM pipeline use their own source value so
# they are never mistaken for Website, Meta Ads, Excel or Manual leads.
CHANNEL_PARTNER_SOURCE = "CHANNEL_PARTNER"

# External status -> initial CRM workflow status. This mapping is applied only
# when the CRM lead is first created. After that the CRM status is owned by CRM
# users and synchronization never overwrites it; the WA HRMS status is kept in
# Lead.channel_partner_status instead.
CHANNEL_PARTNER_INITIAL_CRM_STATUS = {
    "submitted": "NEW",
    "qualified": "QUALIFIED",
    "converted": "WON",
    "rejected": "LOST",
    "lost": "LOST",
}

# CRM -> WA HRMS. Only statuses whose meaning matches a documented external
# status are mapped. Everything else stays a CRM-only workflow state and is
# never sent upstream.
CHANNEL_PARTNER_STATUSES = ("submitted", "qualified", "converted", "rejected", "lost")

# Keys are the output of ``normalize_crm_status`` (spaces/hyphens become
# underscores), so "NEW LEAD" is stored as "NEW_LEAD" and must be listed in
# that form or the mapping silently falls through to "no WA HRMS equivalent".
CRM_TO_CHANNEL_PARTNER_STATUS = {
    "NEW": "submitted",
    "NEW_LEAD": "submitted",
    "SUBMITTED": "submitted",
    # INTERESTED is a distinct internal CRM stage, but WA HRMS has no
    # equivalent: both INTERESTED and QUALIFIED represent the qualified
    # partner lifecycle state.
    "INTERESTED": "qualified",
    "QUALIFIED": "qualified",
    "WON": "converted",
    "CONVERTED": "converted",
    "CONVERTED_TO_SUPPORT": "converted",
    "REJECTED": "rejected",
    "LOST": "lost",
}

# WA HRMS -> CRM for inbound webhook/poll updates. ``rejected`` is kept as a
# distinct CRM value so the rejection reason remains visible in the pipeline.
CHANNEL_PARTNER_TO_CRM_STATUS = {
    "submitted": "NEW",
    "qualified": "QUALIFIED",
    "converted": "WON",
    "rejected": "REJECTED",
    "lost": "LOST",
}

# Statuses that must never be overwritten by an inbound external update.
CHANNEL_PARTNER_TERMINAL_CRM_STATUSES = {
    "WON",
    "CONVERTED",
    "CONVERTED_TO_SUPPORT",
    "LOST",
    "REJECTED",
    "JUNK",
}

# Only these CRM statuses may be downgraded back to the initial submitted state.
# Values are compared after ``normalize_crm_status`` so the underscore form of
# "NEW LEAD" must be present.
CHANNEL_PARTNER_EARLY_CRM_STATUSES = {
    "NEW",
    "NEW_LEAD",
    "SUBMITTED",
    "ASSIGNED",
    "",
}

CHANNEL_PARTNER_REVIEW_NOTE_MAX_LENGTH = 500

SYNC_STATUS_SYNCED = "SYNCED"
SYNC_STATUS_PENDING = "PENDING"
SYNC_STATUS_FAILED = "FAILED"
SYNC_STATUS_NOT_SYNCED = "NOT_SYNCED"


class ChannelPartnerStatusSyncError(Exception):
    """Raised when a CRM status cannot be mapped or validated for WA HRMS."""

    def __init__(self, message: str, *, status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def normalize_crm_status(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"[\s\-]+", "_", str(value).strip().upper())


def map_crm_status_to_channel_partner(value: Optional[str]) -> Optional[str]:
    return CRM_TO_CHANNEL_PARTNER_STATUS.get(normalize_crm_status(value))


def _clean_review_note(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    if len(cleaned) > CHANNEL_PARTNER_REVIEW_NOTE_MAX_LENGTH:
        raise ChannelPartnerStatusSyncError(
            f"Review note must be {CHANNEL_PARTNER_REVIEW_NOTE_MAX_LENGTH} characters or fewer."
        )
    return cleaned


def validate_channel_partner_status_change(
    crm_status: Optional[str],
    review_note: Optional[str],
) -> Tuple[Optional[str], Optional[str]]:
    """Validate a CRM -> WA HRMS status change.

    Returns ``(external_status, review_note)``. ``external_status`` is ``None``
    when the CRM status has no documented WA HRMS equivalent; the caller must
    keep the CRM change but skip the external PATCH.
    """
    external_status = map_crm_status_to_channel_partner(crm_status)
    cleaned_note = _clean_review_note(review_note)
    if external_status is None:
        return None, cleaned_note
    if external_status in {"rejected", "lost"} and not cleaned_note:
        raise ChannelPartnerStatusSyncError(
            "A review note is required when marking a Channel Partner lead as "
            "rejected or lost. The note is shown to the partner."
        )
    return external_status, cleaned_note


def validate_channel_partner_transition(
    lead: Lead,
    crm_status: Optional[str],
) -> None:
    """Validate a CRM status transition for a mapped partner lead.

    WA HRMS keeps ``rejected`` and ``lost`` as separate external states and
    refuses a ``rejected -> lost`` PATCH. The CRM treats both as the same
    closed outcome, so the local transition is allowed and
    ``push_channel_partner_status`` skips the invalid upstream PATCH. WA HRMS
    remains the system of record for the external status.
    """
    return None


def _confirmed_external_status(response: Any, fallback: str) -> str:
    """Read and validate the status returned by PATCH /leads/{id}."""
    confirmed: Any = None
    if isinstance(response, dict):
        for container in (response, response.get("data"), response.get("lead")):
            if not isinstance(container, dict):
                continue
            lead_obj = container.get("lead")
            if isinstance(lead_obj, dict):
                confirmed = lead_obj.get("status")
                if confirmed:
                    break
            confirmed = container.get("status")
            if confirmed:
                break
    status = status_value(confirmed) if confirmed else None
    if status and status not in CHANNEL_PARTNER_STATUSES:
        raise ChannelPartnerStatusSyncError(
            f"WA HRMS returned an unsupported lead status '{status}'."
        )
    return status or fallback


def _api_error_message(exc: Exception) -> str:
    if isinstance(exc, ChannelPartnerAPIError):
        message = exc.message or "WA HRMS rejected the update."
        if exc.status_code in (401, 403):
            message = (
                f"{message} Verify that the configured API key has write scope "
                "and that its creator has Channel Partner edit permission in WA HRMS."
            )
        if exc.errors:
            details = "; ".join(
                f"{key}: {value}" for key, value in exc.errors.items()
            )
            message = f"{message} ({details})"
        return message
    if isinstance(exc, ChannelPartnerStatusSyncError):
        return exc.message
    return str(exc) or exc.__class__.__name__


def _mirror_confirmed_status(
    db: Session,
    lead: Lead,
    *,
    external_status: str,
    review_note: Optional[str],
    synced_at: datetime,
) -> None:
    """Keep the Partner Leads mirror aligned with a confirmed CRM push."""
    mirror = (
        db.query(ChannelPartnerLead)
        .filter(ChannelPartnerLead.external_id == lead.channel_partner_lead_id)
        .first()
    )
    if mirror is None:
        return
    mirror.status = external_status
    if review_note is not None:
        mirror.review_note = review_note
    mirror.source_updated_at = synced_at
    mirror.synced_at = synced_at
    raw = dict(mirror.raw_data) if isinstance(mirror.raw_data, dict) else {}
    raw["status"] = external_status
    if review_note is not None:
        raw["reviewNote"] = review_note
    raw["updatedAt"] = synced_at.isoformat()
    mirror.raw_data = _sanitised(raw)


def push_channel_partner_status(
    db: Session,
    lead: Lead,
    *,
    crm_status: Optional[str] = None,
    review_note: Optional[str] = None,
    commit: bool = True,
) -> Dict[str, Any]:
    """Push one CRM status change to WA HRMS using PATCH /leads/{id}.

    The CRM status is already committed by the caller. This function records
    ``PENDING`` before the network call, then stores ``SYNCED`` only after WA
    HRMS confirms the new status. Failures keep the previous confirmed
    external status and the pending values so they can be retried.
    """
    target_crm_status = crm_status or lead.status
    if not lead.channel_partner_lead_id:
        return {
            "success": False,
            "skipped": True,
            "syncStatus": SYNC_STATUS_NOT_SYNCED,
            "message": "This lead is not mapped to a WA HRMS Channel Partner lead.",
        }

    external_status, cleaned_note = validate_channel_partner_status_change(
        target_crm_status, review_note
    )
    if external_status is None:
        message = (
            f"CRM status '{target_crm_status}' has no WA HRMS equivalent, so the "
            "external status was not changed. Supported mappings: NEW/NEW LEAD "
            "-> submitted, INTERESTED/QUALIFIED -> qualified, WON/CONVERTED -> "
            "converted, REJECTED -> rejected, LOST -> lost."
        )
        logger.info(
            "WAHRMS lead status sync skipped external_id=%s crm_lead_id=%s "
            "crm_status=%s reason=no_external_mapping",
            lead.channel_partner_lead_id,
            lead.id,
            target_crm_status,
        )
        lead.channel_partner_sync_status = SYNC_STATUS_NOT_SYNCED
        lead.channel_partner_pending_status = None
        lead.channel_partner_pending_review_note = None
        lead.channel_partner_last_sync_error = None
        if commit:
            db.commit()
        return {
            "success": False,
            "skipped": True,
            "syncStatus": SYNC_STATUS_NOT_SYNCED,
            "externalStatus": lead.channel_partner_status,
            "message": message,
        }

    previous_external_status = status_value(lead.channel_partner_status)

    # Duplicate guard: a repeated click or render for the same confirmed
    # status must not send another PATCH. A new/changed partner note still
    # counts as an update and is sent.
    current_note = None
    if isinstance(lead.channel_partner_details_json, dict):
        current_note = as_text(lead.channel_partner_details_json.get("reviewNote"))
    if (
        (lead.channel_partner_sync_status or "").upper() == SYNC_STATUS_SYNCED
        and status_value(lead.channel_partner_status) == external_status
        and (cleaned_note is None or cleaned_note == current_note)
    ):
        return {
            "success": True,
            "skipped": True,
            "syncStatus": SYNC_STATUS_SYNCED,
            "externalStatus": external_status,
            "message": "CRM and WA HRMS are already synchronized for this status.",
        }

    # WA HRMS keeps rejected and lost as distinct external states and refuses
    # a rejected -> lost PATCH. The CRM treats both as the same closed outcome,
    # so record the local change without sending an invalid transition.
    current_external = status_value(lead.channel_partner_status)
    if (
        current_external in {"rejected", "lost"}
        and external_status in {"rejected", "lost"}
        and current_external != external_status
    ):
        synced_at = get_ist_now()
        lead.channel_partner_sync_status = SYNC_STATUS_SYNCED
        lead.channel_partner_last_synced_at = synced_at
        lead.channel_partner_last_sync_error = None
        lead.channel_partner_pending_status = None
        lead.channel_partner_pending_review_note = None
        if commit:
            db.commit()
        return {
            "success": True,
            "skipped": True,
            "syncStatus": SYNC_STATUS_SYNCED,
            "externalStatus": current_external,
            "requestedStatus": external_status,
            "message": (
                "CRM status saved. WA HRMS keeps this lead as "
                f"{current_external}; rejected and lost are treated as the "
                "same closed outcome, so no upstream status change was sent."
            ),
        }

    # Converted is a supported CRM -> WA HRMS transition and must be attempted
    # for every WON/converted lead. The previous implementation silently
    # blocked it unless the mirror already had organization/subscription
    # references, which meant a newly won partner deal could never sync. WA
    # HRMS is now the authority: if it requires additional references it
    # returns a validation error, which is stored as FAILED and shown to the
    # user instead of being skipped.
    validate_channel_partner_transition(lead, target_crm_status)

    # Record PENDING before the network call so a crash cannot leave the UI
    # claiming the two systems are synchronized.
    lead.channel_partner_sync_status = SYNC_STATUS_PENDING
    lead.channel_partner_pending_status = external_status
    lead.channel_partner_pending_review_note = cleaned_note
    lead.channel_partner_last_sync_error = None
    if commit:
        db.commit()

    config = load_effective_config(db)
    if not config.configured:
        message = "WA HRMS Channel Partner API credentials are not configured."
        logger.warning(
            "WAHRMS lead status sync failed external_id=%s crm_lead_id=%s "
            "previous_status=%s crm_status=%s external_status=%s reason=%s",
            lead.channel_partner_lead_id,
            lead.id,
            previous_external_status,
            target_crm_status,
            external_status,
            message,
        )
        lead.channel_partner_sync_status = SYNC_STATUS_FAILED
        lead.channel_partner_last_sync_error = message
        if commit:
            db.commit()
        return {
            "success": False,
            "skipped": False,
            "syncStatus": SYNC_STATUS_FAILED,
            "externalStatus": lead.channel_partner_status,
            "message": message,
        }

    response: Any = None
    try:
        with ChannelPartnerClient(config) as client:
            response = client.update_lead(
                lead.channel_partner_lead_id,
                status=external_status,
                review_note=cleaned_note,
            )
        confirmed_status = _confirmed_external_status(response, external_status)
    except Exception as exc:
        message = _api_error_message(exc)
        logger.warning(
            "WAHRMS lead status sync failed external_id=%s crm_lead_id=%s "
            "previous_status=%s crm_status=%s external_status=%s "
            "http_status=%s response=%s error=%s",
            lead.channel_partner_lead_id,
            lead.id,
            previous_external_status,
            target_crm_status,
            external_status,
            getattr(exc, "status_code", None),
            getattr(exc, "payload", None),
            message,
        )
        lead.channel_partner_sync_status = SYNC_STATUS_FAILED
        lead.channel_partner_last_sync_error = message
        if commit:
            db.commit()
        return {
            "success": False,
            "skipped": False,
            "syncStatus": SYNC_STATUS_FAILED,
            "externalStatus": lead.channel_partner_status,
            "requestedStatus": external_status,
            "message": message,
        }

    synced_at = get_ist_now()
    lead.channel_partner_status = confirmed_status
    lead.channel_partner_sync_status = SYNC_STATUS_SYNCED
    lead.channel_partner_last_synced_at = synced_at
    lead.channel_partner_last_sync_error = None
    lead.channel_partner_pending_status = None
    lead.channel_partner_pending_review_note = None
    lead.channel_partner_status_updated_at = synced_at
    details = dict(lead.channel_partner_details_json) if isinstance(lead.channel_partner_details_json, dict) else {}
    details["status"] = confirmed_status
    if cleaned_note is not None:
        details["reviewNote"] = cleaned_note
    details["updatedAt"] = synced_at.isoformat()
    lead.channel_partner_details_json = details
    _mirror_confirmed_status(
        db,
        lead,
        external_status=confirmed_status,
        review_note=cleaned_note,
        synced_at=synced_at,
    )
    if commit:
        db.commit()
    logger.info(
        "WAHRMS lead status sync succeeded external_id=%s crm_lead_id=%s "
        "previous_status=%s crm_status=%s external_status=%s "
        "confirmed_status=%s",
        lead.channel_partner_lead_id,
        lead.id,
        previous_external_status,
        target_crm_status,
        external_status,
        confirmed_status,
    )
    return {
        "success": True,
        "skipped": False,
        "syncStatus": SYNC_STATUS_SYNCED,
        "externalStatus": confirmed_status,
        "requestedStatus": external_status,
        "message": f"WA HRMS lead status updated to {confirmed_status}.",
    }


def sync_channel_partner_status_for_lead(
    db: Session,
    lead: Lead,
    *,
    crm_status: Optional[str] = None,
    review_note: Optional[str] = None,
    commit: bool = True,
) -> Dict[str, Any]:
    """Common status-sync entry point used by every CRM status-change endpoint.

    Keeping this wrapper in one place guarantees that Admin, Manager, Sales,
    WON, conversion, rejection/loss and retry flows all use the same mapping,
    duplicate guard, response handling and error feedback. It never raises for
    a mapped partner lead: failures are recorded as ``FAILED`` on the lead so
    the caller can return the CRM change together with the sync result.
    """
    if not getattr(lead, "channel_partner_lead_id", None):
        return {
            "success": False,
            "skipped": True,
            "syncStatus": SYNC_STATUS_NOT_SYNCED,
            "message": "This lead is not mapped to a WA HRMS Channel Partner lead.",
        }

    try:
        result = push_channel_partner_status(
            db,
            lead,
            crm_status=crm_status,
            review_note=review_note,
            commit=commit,
        )
    except ChannelPartnerStatusSyncError as exc:
        message = exc.message
    except Exception as exc:  # never break the CRM status change itself
        message = _api_error_message(exc)
        logger.exception(
            "WAHRMS lead status sync crashed external_id=%s crm_lead_id=%s "
            "crm_status=%s",
            getattr(lead, "channel_partner_lead_id", None),
            getattr(lead, "id", None),
            crm_status or getattr(lead, "status", None),
        )
    else:
        lead._channel_partner_sync_message = result.get("message")
        return result

    lead.channel_partner_sync_status = SYNC_STATUS_FAILED
    lead.channel_partner_last_sync_error = message
    if commit:
        db.commit()
    result = {
        "success": False,
        "skipped": False,
        "syncStatus": SYNC_STATUS_FAILED,
        "externalStatus": status_value(lead.channel_partner_status),
        "requestedStatus": map_crm_status_to_channel_partner(
            crm_status or lead.status
        ),
        "message": message,
    }
    lead._channel_partner_sync_message = result.get("message")
    return result


def retry_channel_partner_status_sync(db: Session, lead: Lead) -> Dict[str, Any]:
    """Retry the last pending/failed Channel Partner status push."""
    if not lead.channel_partner_lead_id:
        raise ChannelPartnerStatusSyncError(
            "This lead is not mapped to a WA HRMS Channel Partner lead."
        )
    pending_status = status_value(lead.channel_partner_pending_status)
    if pending_status:
        if pending_status not in CHANNEL_PARTNER_STATUSES:
            raise ChannelPartnerStatusSyncError(
                f"Pending WA HRMS status '{pending_status}' is not supported."
            )
        retry_crm_status = CHANNEL_PARTNER_TO_CRM_STATUS.get(pending_status)
    else:
        retry_crm_status = lead.status
    if not map_crm_status_to_channel_partner(retry_crm_status):
        raise ChannelPartnerStatusSyncError(
            f"CRM status '{lead.status}' has no WA HRMS equivalent to retry."
        )
    # The CRM status is the source of truth for a retry; reuse the pending
    # partner-safe note when the user already supplied one.
    return push_channel_partner_status(
        db,
        lead,
        crm_status=retry_crm_status,
        review_note=lead.channel_partner_pending_review_note,
    )

WEBHOOK_EVENT_TYPES = (
    "application.submitted",
    "application.approved",
    "application.rejected",
    "partner.created",
    "partner.updated",
    "partner.status_changed",
    "partner.user_invited",
    "lead.created",
    "lead.updated",
    "lead.converted",
    "client.assigned",
    "client.unassigned",
    "coupon.assigned",
    "coupon.removed",
    "commission.earned",
    "commission.reversed",
    "commission.adjusted",
    "payout.created",
    "payout.approved",
    "payout.paid",
    "payout.cancelled",
    "ping",
)


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------
def _put(values: Dict[str, Any], key: str, value: Any, *, allow_false: bool = True):
    """Add a mapped value only when the API actually supplied it."""
    if value is None:
        return
    if isinstance(value, str) and not value.strip():
        return
    if isinstance(value, bool):
        if not allow_false and not value:
            return
    values[key] = value


def _first(raw: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    return first_present(raw, list(keys), default=default)


def _source_timestamp(raw: Dict[str, Any], fallback: Optional[datetime] = None):
    return (
        parse_datetime_ist(
            _first(raw, "updatedAt", "updated_at", "modifiedAt", "lastUpdatedAt")
        )
        or fallback
        or parse_datetime_ist(_first(raw, "createdAt", "created_at"))
    )


def _is_stale(
    existing_source_time: Optional[datetime], incoming_time: Optional[datetime]
) -> bool:
    # MySQL DATETIME columns have no fractional seconds, so a source timestamp
    # such as 12:49:07.837 can come back as 12:49:08. Without tolerance, every
    # later sync of the same record would look older and be skipped forever.
    return bool(
        existing_source_time
        and incoming_time
        and incoming_time < existing_source_time - timedelta(seconds=1)
    )


def _record_key(*parts: Any) -> str:
    text = ":".join(str(part) for part in parts if part not in (None, ""))
    if len(text) <= 150:
        return text
    return f"sha1:{hashlib.sha1(text.encode('utf-8')).hexdigest()}"


def _sanitised(raw: Any) -> Any:
    return as_json(sanitise_payload(raw))


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def get_checkpoint(db: Session, key: str = "events") -> ChannelPartnerSyncCheckpoint:
    checkpoint = (
        db.query(ChannelPartnerSyncCheckpoint)
        .filter(ChannelPartnerSyncCheckpoint.checkpoint_key == key)
        .first()
    )
    if checkpoint is None:
        checkpoint = ChannelPartnerSyncCheckpoint(
            checkpoint_key=key, last_after=0
        )
        db.add(checkpoint)
        try:
            db.commit()
            db.refresh(checkpoint)
        except IntegrityError:
            db.rollback()
            checkpoint = (
                db.query(ChannelPartnerSyncCheckpoint)
                .filter(ChannelPartnerSyncCheckpoint.checkpoint_key == key)
                .first()
            )
    return checkpoint


# ---------------------------------------------------------------------------
# Mapping: partners
# ---------------------------------------------------------------------------
def _partner_values(raw: Dict[str, Any]) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    _put(values, "name", as_text(_first(raw, "name", "partnerName", "businessName")))
    _put(values, "code", as_text(_first(raw, "code", "partnerCode")))
    _put(values, "entity_type", as_text(_first(raw, "entityType", "entity_type")))
    _put(values, "legal_name", as_text(_first(raw, "legalName", "legal_name")))
    _put(values, "email", as_text(_first(raw, "email", "contactEmail")))
    _put(values, "phone", as_text(_first(raw, "phone", "mobile", "contactPhone")))
    _put(values, "address_line1", as_text(_first(raw, "addressLine1", "address_line_1")))
    _put(values, "address_line2", as_text(_first(raw, "addressLine2", "address_line_2")))
    _put(values, "city", as_text(_first(raw, "city")))
    _put(values, "state", as_text(_first(raw, "state")))
    _put(values, "state_code", as_text(_first(raw, "stateCode", "state_code")))
    _put(values, "pincode", as_text(_first(raw, "pincode", "pinCode")))

    pan_value = as_text(_first(raw, "pan", "panNumber"))
    if pan_value:
        values["pan_masked"] = mask_pan(pan_value)
        values["pan_last4"] = pan_last4(pan_value)
        values["pan_present"] = True
    elif _first(raw, "panLast4", "pan_last4") is not None or _first(
        raw, "panMasked", "pan_masked"
    ):
        values["pan_masked"] = as_text(_first(raw, "panMasked", "pan_masked"))
        values["pan_last4"] = as_text(_first(raw, "panLast4", "pan_last4"))
        values["pan_present"] = True
    elif _first(raw, "panPresent", "pan_present") is not None:
        values["pan_present"] = bool(_first(raw, "panPresent", "pan_present"))

    _put(values, "gst_registered", as_bool(_first(raw, "gstRegistered", "gst_registered")))
    _put(values, "gstin", as_text(_first(raw, "gstin", "gstNumber")))
    _put(values, "gst_rate_bps", as_int(_first(raw, "gstRateBps", "gst_rate_bps")))
    _put(
        values,
        "commission_rate_bps",
        as_int(_first(raw, "commissionRateBps", "commission_rate_bps")),
    )
    _put(values, "payout_frequency", as_text(_first(raw, "payoutFrequency", "payout_frequency")))
    _put(values, "hold_days", as_int(_first(raw, "holdDays", "hold_days")))
    _put(
        values,
        "min_payout_paise",
        as_int(_first(raw, "minPayoutPaise", "min_payout_paise")),
    )
    _put(
        values,
        "first_client_discount_bps",
        as_int(_first(raw, "firstClientDiscountBps", "first_client_discount_bps")),
    )
    _put(
        values,
        "tds_certificate_rate_bps",
        as_int(_first(raw, "tdsCertificateRateBps", "tds_certificate_rate_bps")),
    )
    _put(
        values,
        "tds_certificate_number",
        as_text(_first(raw, "tdsCertificateNumber", "tds_certificate_number")),
    )
    _put(
        values,
        "tds_certificate_valid_until",
        parse_date(_first(raw, "tdsCertificateValidUntil", "tds_certificate_valid_until")),
    )
    _put(values, "status", status_value(_first(raw, "status")))
    _put(values, "notes", as_text(_first(raw, "notes")))
    return values


def _detail_sections(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the documented partner-detail sections without inventing keys."""
    sections: Dict[str, Any] = {}

    def store(attr: str, *keys: str):
        for key in keys:
            if key in payload and payload.get(key) is not None:
                if attr == "application_documents_json":
                    sections[attr] = sanitise_document_metadata(payload.get(key))
                else:
                    sections[attr] = _sanitised(payload.get(key))
                return

    store("balances_json", "balances", "balance")
    store(
        "monthly_commission_series_json",
        "series",
        "monthlyCommissionSeries",
        "monthlyCommissions",
        "monthlySeries",
        "commissionSeries",
    )
    store("tds_status_json", "tdsStatus", "tds")
    store("inactivity_status_json", "inactivityStatus", "inactivity")
    store("first_client_offer_json", "firstClientOffer", "firstClientOfferDetails")
    store(
        "application_documents_json",
        "applicationDocuments",
        "documents",
    )
    # The live partner detail nests the application (and its document
    # metadata) under an ``application`` object.
    application = first_present(payload, ["application"], default=None)
    if isinstance(application, dict):
        documents = first_present(
            application, ["documents", "documentMetadata"], default=None
        )
        if documents is not None:
            sections["application_documents_json"] = sanitise_document_metadata(
                documents
            )
    return sections


def _login_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    users = extract_list(
        payload,
        [
            "users",
            "logins",
            "partnerUsers",
            "partnerLogins",
            "owner",
        ],
    )
    if not users:
        # `owner` may be a single object.
        owner = first_present(payload, ["owner"], default=None)
        if isinstance(owner, dict):
            users = [owner]
    return [item for item in users if isinstance(item, dict)]


def upsert_partner(
    db: Session,
    raw: Dict[str, Any],
    *,
    detail_payload: Optional[Dict[str, Any]] = None,
    source_time: Optional[datetime] = None,
    list_raw: Any = None,
    detail_raw: Any = None,
    commit: bool = False,
) -> Optional[ChannelPartner]:
    if not isinstance(raw, dict):
        return None
    external_id = external_id_of(raw, "partnerId", "partner_id")
    if not external_id:
        return None

    values = _partner_values(raw)
    incoming_time = _source_timestamp(raw, fallback=source_time)
    partner = (
        db.query(ChannelPartner)
        .filter(ChannelPartner.external_id == external_id)
        .first()
    )
    created = partner is None
    if created:
        partner = ChannelPartner(external_id=external_id)
        db.add(partner)
        db.flush()

    stale = _is_stale(partner.source_updated_at, incoming_time)
    if not stale:
        for key, value in values.items():
            setattr(partner, key, value)
        if detail_payload is not None:
            for key, value in _detail_sections(detail_payload).items():
                setattr(partner, key, value)
        created_at = parse_datetime_ist(
            _first(raw, "createdAt", "created_at")
        )
        if created_at:
            partner.source_created_at = created_at
        if incoming_time and (
            partner.source_updated_at is None
            or incoming_time >= partner.source_updated_at
        ):
            partner.source_updated_at = incoming_time

    if list_raw is not None:
        partner.list_raw = _sanitised(list_raw)
    if detail_raw is not None:
        partner.detail_raw = _sanitised(detail_raw)
    partner.synced_at = get_ist_now()

    if commit:
        db.commit()
        db.refresh(partner)
    return partner


def upsert_partner_login(
    db: Session,
    partner_external_id: str,
    raw: Dict[str, Any],
    *,
    commit: bool = False,
) -> Optional[ChannelPartnerLogin]:
    if not isinstance(raw, dict):
        return None
    user_external_id = external_id_of(raw, "userId", "user_id")
    email = as_text(_first(raw, "email"))
    key = _record_key(partner_external_id, user_external_id or email or _first(raw, "name"))

    login = (
        db.query(ChannelPartnerLogin)
        .filter(ChannelPartnerLogin.record_key == key)
        .first()
    )
    if login is None:
        login = ChannelPartnerLogin(record_key=key, partner_external_id=partner_external_id)
        db.add(login)

    login.external_id = user_external_id or login.external_id
    values = {
        "name": as_text(_first(raw, "name")),
        "email": email,
        "phone": as_text(_first(raw, "phone", "mobile")),
        "role": as_text(_first(raw, "role")),
        "is_active": as_bool(_first(raw, "isActive", "is_active", "active")),
        "invite_status": as_text(
            _first(raw, "inviteStatus", "invite_status", "status")
        ),
        "invited_at": parse_datetime_ist(
            _first(raw, "invitedAt", "invited_at", "createdAt")
        ),
        "last_login_at": parse_datetime_ist(
            _first(raw, "lastLoginAt", "last_login_at", "lastLogin")
        ),
    }
    for field, value in values.items():
        if value is not None:
            setattr(login, field, value)
    login.raw_data = _sanitised(raw)
    login.synced_at = get_ist_now()
    if commit:
        db.commit()
        db.refresh(login)
    return login


# ---------------------------------------------------------------------------
# Mapping: applications
# ---------------------------------------------------------------------------
def _application_values(raw: Dict[str, Any]) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    _put(values, "entity_type", as_text(_first(raw, "entityType", "entity_type")))
    _put(values, "business_name", as_text(_first(raw, "businessName", "business_name")))
    _put(values, "business_type", as_text(_first(raw, "businessType", "business_type")))
    _put(values, "team_size", as_text(_first(raw, "teamSize", "team_size")))
    _put(
        values,
        "years_in_business",
        as_text(_first(raw, "yearsInBusiness", "years_in_business")),
    )
    _put(values, "website", as_text(_first(raw, "website")))
    pan_value = as_text(_first(raw, "pan", "panNumber"))
    if pan_value:
        values["pan_masked"] = mask_pan(pan_value)
        values["pan_last4"] = pan_last4(pan_value)
        values["pan_present"] = True
    elif _first(raw, "panLast4", "pan_last4") is not None or _first(
        raw, "panMasked", "pan_masked"
    ):
        values["pan_masked"] = as_text(_first(raw, "panMasked", "pan_masked"))
        values["pan_last4"] = as_text(_first(raw, "panLast4", "pan_last4"))
        values["pan_present"] = True
    _put(values, "gstin", as_text(_first(raw, "gstin")))
    _put(values, "contact_name", as_text(_first(raw, "contactName", "contact_name")))
    _put(values, "designation", as_text(_first(raw, "designation")))
    _put(values, "email", as_text(_first(raw, "email")))
    _put(values, "phone", as_text(_first(raw, "phone", "mobile")))
    _put(values, "address_line1", as_text(_first(raw, "addressLine1", "address_line1")))
    _put(values, "address_line2", as_text(_first(raw, "addressLine2", "address_line2")))
    _put(values, "city", as_text(_first(raw, "city")))
    _put(values, "state", as_text(_first(raw, "state")))
    _put(values, "state_code", as_text(_first(raw, "stateCode", "state_code")))
    _put(values, "pincode", as_text(_first(raw, "pincode")))
    _put(values, "regions", as_text(_first(raw, "regions")))
    industries = _first(raw, "industries")
    if isinstance(industries, (list, dict)):
        values["industries_json"] = _sanitised(industries)
    elif isinstance(industries, str):
        values["industries_json"] = [
            item.strip() for item in industries.split(",") if item.strip()
        ]
    _put(values, "current_clients", as_text(_first(raw, "currentClients", "current_clients")))
    _put(
        values,
        "expected_clients",
        as_text(_first(raw, "expectedClients", "expected_clients")),
    )
    _put(values, "heard_from", as_text(_first(raw, "heardFrom", "heard_from")))
    _put(values, "message", as_text(_first(raw, "message")))
    consent_value = _first(raw, "consent")
    if consent_value is not None:
        _put(values, "consent", as_bool(consent_value))
    elif parse_datetime_ist(_first(raw, "consentAt", "consent_at")):
        # The live API reports consent as a timestamp (``consentAt``).
        values["consent"] = True
    _put(values, "status", status_value(_first(raw, "status")))
    _put(values, "review_note", as_text(_first(raw, "reviewNote", "review_note")))
    _put(
        values,
        "reviewed_at",
        parse_datetime_ist(_first(raw, "reviewedAt", "reviewed_at")),
    )
    partner_id = as_text(
        _first(raw, "partnerId", "partner_id")
        or get_path(raw, "partner.id")
    )
    _put(values, "partner_external_id", partner_id)
    docs = _first(raw, "documents", "documentMetadata")
    if docs is not None:
        values["document_metadata_json"] = sanitise_document_metadata(docs)
    _put(values, "source_created_at", parse_datetime_ist(_first(raw, "createdAt", "created_at")))
    _put(values, "source_updated_at", parse_datetime_ist(_first(raw, "updatedAt", "updated_at")))
    return values


def upsert_application(
    db: Session,
    raw: Dict[str, Any],
    *,
    source_time: Optional[datetime] = None,
    commit: bool = False,
) -> Optional[ChannelPartnerApplication]:
    if not isinstance(raw, dict):
        return None
    external_id = external_id_of(raw, "applicationId", "application_id")
    if not external_id:
        return None
    values = _application_values(raw)
    incoming_time = _source_timestamp(raw, fallback=source_time)
    row = (
        db.query(ChannelPartnerApplication)
        .filter(ChannelPartnerApplication.external_id == external_id)
        .first()
    )
    if row is None:
        row = ChannelPartnerApplication(external_id=external_id)
        db.add(row)
        db.flush()
    if not _is_stale(row.source_updated_at, incoming_time):
        for key, value in values.items():
            setattr(row, key, value)
        if incoming_time and (
            row.source_updated_at is None or incoming_time >= row.source_updated_at
        ):
            row.source_updated_at = incoming_time
    row.raw_data = _sanitised(raw)
    row.synced_at = get_ist_now()
    if commit:
        db.commit()
        db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Mapping: leads
# ---------------------------------------------------------------------------
def _lead_values(raw: Dict[str, Any]) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    partner_raw = first_present(raw, ["partner"], default=None)
    partner_id = as_text(
        _first(raw, "partnerId", "partner_id")
        or (external_id_of(partner_raw) if isinstance(partner_raw, dict) else None)
    )
    _put(values, "partner_external_id", partner_id)
    if isinstance(partner_raw, dict):
        _put(values, "partner_name", as_text(_first(partner_raw, "name")))
    if not values.get("partner_name"):
        _put(values, "partner_name", as_text(_first(raw, "partnerName", "partner_name")))
    _put(values, "status", status_value(_first(raw, "status")))
    _put(
        values,
        "company_name",
        as_text(_first(raw, "companyName", "businessName", "organizationName", "company")),
    )
    _put(values, "contact_name", as_text(_first(raw, "contactName", "name", "contactPerson")))
    _put(values, "email", as_text(_first(raw, "email", "contactEmail")))
    _put(values, "phone", as_text(_first(raw, "phone", "mobile", "contactPhone")))
    _put(values, "city", as_text(_first(raw, "city")))
    _put(values, "state", as_text(_first(raw, "state")))
    _put(values, "source", as_text(_first(raw, "source", "sourceType", "leadSource")))
    _put(values, "message", as_text(_first(raw, "message", "notes", "requirement")))
    _put(values, "review_note", as_text(_first(raw, "reviewNote", "review_note")))
    _put(values, "reviewed_at", parse_datetime_ist(_first(raw, "reviewedAt", "reviewed_at")))
    _put(
        values,
        "organization_id",
        as_text(
            _first(raw, "organizationId", "organization_id")
            or get_path(raw, "organization.id")
        ),
    )
    _put(
        values,
        "subscription_order_id",
        as_text(
            _first(
                raw,
                "subscriptionOrderId",
                "subscription_order_id",
                "orderId",
                "order_id",
            )
        ),
    )
    _put(values, "converted_at", parse_datetime_ist(_first(raw, "convertedAt", "converted_at")))
    _put(
        values,
        "protection_until",
        parse_datetime_ist(_first(raw, "protectionUntil", "protection_until")),
    )
    _put(values, "source_created_at", parse_datetime_ist(_first(raw, "createdAt", "created_at")))
    _put(values, "source_updated_at", parse_datetime_ist(_first(raw, "updatedAt", "updated_at")))
    return values


def upsert_lead(
    db: Session,
    raw: Dict[str, Any],
    *,
    source_time: Optional[datetime] = None,
    commit: bool = False,
) -> Optional[ChannelPartnerLead]:
    if not isinstance(raw, dict):
        return None
    external_id = external_id_of(raw, "leadId", "lead_id")
    if not external_id:
        return None
    values = _lead_values(raw)
    incoming_time = _source_timestamp(raw, fallback=source_time)
    row = (
        db.query(ChannelPartnerLead)
        .filter(ChannelPartnerLead.external_id == external_id)
        .first()
    )
    if row is None:
        row = ChannelPartnerLead(external_id=external_id)
        db.add(row)
        db.flush()
    stale = _is_stale(row.source_updated_at, incoming_time)
    if not stale:
        for key, value in values.items():
            setattr(row, key, value)
        if incoming_time and (
            row.source_updated_at is None or incoming_time >= row.source_updated_at
        ):
            row.source_updated_at = incoming_time
    row.raw_data = _sanitised(raw)
    row.synced_at = get_ist_now()
    # Mirror the current source state into All Leads. Stale webhook/poll
    # deliveries are ignored here too, so an out-of-order event cannot roll the
    # main CRM lead back after a newer one has already been applied.
    if not stale:
        upsert_crm_lead_from_channel_partner(db, row)
    if commit:
        db.commit()
        db.refresh(row)
    return row


def _split_contact_name(value: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    parts = (value or "").strip().split(None, 1)
    if not parts:
        return None, None
    return parts[0], parts[1] if len(parts) > 1 else None


def _apply_external_status_to_crm(lead: Lead, external_status: str, db: Session) -> bool:
    """Reflect a newer WA HRMS status into the CRM workflow.

    External updates never downgrade a progressed lead and never resurrect a
    terminal one. A ``submitted`` event only resets a lead that is still in its
    initial state. Returns ``True`` when the CRM status actually changed.
    """
    target = CHANNEL_PARTNER_TO_CRM_STATUS.get(external_status)
    if not target:
        return False
    current = normalize_crm_status(lead.status)
    target_normalized = normalize_crm_status(target)
    if current == target_normalized:
        return False
    if external_status == "submitted":
        if current not in CHANNEL_PARTNER_EARLY_CRM_STATUSES:
            return False
    elif current in CHANNEL_PARTNER_TERMINAL_CRM_STATUSES:
        return False

    old_status = lead.status
    lead.status = target
    db.add(
        LeadStatusHistory(
            lead_id=lead.id,
            old_status=old_status,
            new_status=target,
            changed_by=None,
            changed_at=get_ist_now(),
        )
    )
    db.add(
        LeadActivity(
            lead_id=lead.id,
            activity_type="STATUS_CHANGED",
            related_entity_type="LEAD",
            related_entity_id=lead.id,
            department="SALES",
            description=(
                f"WA HRMS Channel Partner status updated to {external_status}; "
                f"CRM status changed {old_status} -> {target}."
            ),
            created_at=get_ist_now(),
        )
    )
    return True


def upsert_crm_lead_from_channel_partner(
    db: Session,
    row: ChannelPartnerLead,
) -> Tuple[Optional[Lead], bool]:
    """Create/update the All Leads row mapped to a mirrored partner lead.

    The external WA HRMS lead UUID is the only lookup key, so webhook retries,
    event polling and the historical backfill all converge on the same CRM row.

    Descriptive fields and the Channel Partner mapping columns are refreshed.
    Assignment, trial and Support ownership are never touched. A newer external
    status is reflected into the CRM workflow (never downgrading or resurrecting
    a terminal status), while CRM-initiated changes are pushed separately with
    ``PATCH /leads/{id}``. Inbound events never trigger an outbound PATCH.

    Returns ``(lead, created)``.
    """
    if row is None or not row.external_id:
        return None, False

    raw = row.raw_data if isinstance(row.raw_data, dict) else {}
    partner = None
    if row.partner_external_id:
        partner = (
            db.query(ChannelPartner)
            .filter(ChannelPartner.external_id == row.partner_external_id)
            .first()
        )

    partner_name = (
        as_text(row.partner_name)
        or as_text(_first(raw, "partnerName", "partner_name"))
        or (partner.name if partner else None)
    )
    partner_code = as_text(_first(raw, "partnerCode", "partner_code")) or (
        partner.code if partner else None
    )
    contact_name = as_text(row.contact_name) or as_text(
        _first(raw, "contactName", "name", "contactPerson")
    )
    company_name = as_text(row.company_name) or as_text(
        _first(raw, "companyName", "businessName", "organizationName", "company")
    )
    display_name = contact_name or company_name or "Channel Partner Lead"
    phone = as_text(row.phone) or as_text(_first(raw, "contactPhone", "phone", "mobile"))
    email = as_text(row.email) or as_text(_first(raw, "contactEmail", "email"))
    city = as_text(row.city) or as_text(_first(raw, "city"))
    state = as_text(row.state) or as_text(_first(raw, "state"))
    message = as_text(row.message) or as_text(_first(raw, "message", "notes", "requirement"))
    external_status = status_value(row.status) or status_value(_first(raw, "status"))
    source_created_at = row.source_created_at or parse_datetime_ist(
        _first(raw, "createdAt", "created_at")
    )
    source_updated_at = row.source_updated_at or parse_datetime_ist(
        _first(raw, "updatedAt", "updated_at")
    )

    lead = (
        db.query(Lead)
        .filter(Lead.channel_partner_lead_id == row.external_id)
        .first()
    )
    created = lead is None
    previous_external = None if created else status_value(lead.channel_partner_status)
    now = get_ist_now()
    if created:
        lead = Lead(
            channel_partner_lead_id=row.external_id,
            name=display_name,
            phone=phone or "",
            source=CHANNEL_PARTNER_SOURCE,
            status=CHANNEL_PARTNER_INITIAL_CRM_STATUS.get(external_status or "", "NEW"),
            created_at=source_created_at or now,
            first_enquiry_date=source_created_at or now,
            latest_enquiry_date=source_updated_at or source_created_at or now,
            channel_partner_sync_status=SYNC_STATUS_SYNCED if external_status else None,
            channel_partner_last_synced_at=(source_updated_at or now) if external_status else None,
            channel_partner_status_updated_at=(source_updated_at or now) if external_status else None,
        )
        db.add(lead)
        db.flush()
    else:
        first_name, last_name = _split_contact_name(contact_name)
        if first_name:
            lead.first_name = first_name
        if last_name:
            lead.last_name = last_name

        if external_status:
            pending = status_value(lead.channel_partner_pending_status)
            if pending and external_status == pending:
                # The webhook confirms a CRM-initiated PATCH whose response was
                # lost. Clear the pending marker without sending another PATCH.
                lead.channel_partner_sync_status = SYNC_STATUS_SYNCED
                lead.channel_partner_last_synced_at = source_updated_at or now
                lead.channel_partner_last_sync_error = None
                lead.channel_partner_pending_status = None
                lead.channel_partner_pending_review_note = None
                lead.channel_partner_status_updated_at = source_updated_at or now
            elif previous_external != external_status:
                # A genuine external change. Reflect it into the CRM workflow
                # when it does not downgrade or resurrect a terminal status.
                applied = _apply_external_status_to_crm(lead, external_status, db)
                mapped_target = CHANNEL_PARTNER_TO_CRM_STATUS.get(external_status)
                in_sync = applied or (
                    mapped_target
                    and normalize_crm_status(lead.status)
                    == normalize_crm_status(mapped_target)
                )
                lead.channel_partner_sync_status = (
                    SYNC_STATUS_SYNCED if in_sync else SYNC_STATUS_NOT_SYNCED
                )
                lead.channel_partner_last_synced_at = source_updated_at or now
                lead.channel_partner_last_sync_error = (
                    None
                    if in_sync
                    else (
                        f"WA HRMS status '{external_status}' was not applied because "
                        f"CRM status '{lead.status}' is terminal."
                    )
                )
                lead.channel_partner_status_updated_at = source_updated_at or now

    # Descriptive source data. Empty API values never wipe an existing CRM
    # value; the CRM workflow status and assignment columns stay untouched.
    lead.name = display_name
    if phone:
        lead.phone = phone
    if email:
        lead.email = email
    if company_name:
        lead.company = company_name
    if city:
        lead.city = city
    if state:
        lead.state = state
    if message:
        lead.requirement_notes = message

    lead.source = CHANNEL_PARTNER_SOURCE
    lead.channel_partner_id = row.partner_external_id or lead.channel_partner_id
    lead.channel_partner_name = partner_name or lead.channel_partner_name
    lead.channel_partner_code = partner_code or lead.channel_partner_code
    lead.channel_partner_status = external_status or lead.channel_partner_status
    lead.channel_partner_details_json = _sanitised(raw)

    return lead, created


def sync_channel_partner_leads_to_crm(
    db: Session,
    *,
    commit: bool = True,
) -> Dict[str, Any]:
    """Backfill/refresh every mirrored partner lead in the main leads table.

    This also covers historical leads that were synchronized before the CRM
    mapping existed, without requiring another WA HRMS API call.
    """
    created = 0
    updated = 0
    for row in db.query(ChannelPartnerLead).all():
        lead, was_created = upsert_crm_lead_from_channel_partner(db, row)
        if lead is None:
            continue
        if was_created:
            created += 1
        else:
            updated += 1
    if commit:
        db.commit()
    return {"crmLeadsCreated": created, "crmLeadsUpdated": updated}


def backfill_channel_partner_leads() -> Dict[str, Any]:
    """Startup-safe historical backfill in its own database session."""
    db = SessionLocal()
    try:
        return sync_channel_partner_leads_to_crm(db)
    except Exception:
        db.rollback()
        logger.exception("WAHRMS Channel Partner CRM lead backfill failed")
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Mapping: clients / attributions
# ---------------------------------------------------------------------------
def upsert_client_attribution(
    db: Session,
    partner_external_id: str,
    raw: Dict[str, Any],
    *,
    status_override: Optional[str] = None,
    source_time: Optional[datetime] = None,
    commit: bool = False,
) -> Optional[ChannelPartnerClientAttribution]:
    if not isinstance(raw, dict) or not partner_external_id:
        return None
    external_id = external_id_of(raw, "attributionId", "attribution_id")
    org_raw = first_present(raw, ["organization"], default=None)
    organization_id = as_text(
        _first(raw, "organizationId", "organization_id")
        or (external_id_of(org_raw) if isinstance(org_raw, dict) else None)
    )
    order_id = as_text(
        _first(raw, "subscriptionOrderId", "subscription_order_id", "orderId", "order_id")
    )
    key = _record_key(
        partner_external_id,
        external_id or organization_id or order_id,
        "" if external_id or organization_id else order_id,
    )
    row = (
        db.query(ChannelPartnerClientAttribution)
        .filter(ChannelPartnerClientAttribution.record_key == key)
        .first()
    )
    if row is None:
        row = ChannelPartnerClientAttribution(
            record_key=key, partner_external_id=partner_external_id
        )
        db.add(row)

    values = {
        "external_id": external_id,
        "organization_id": organization_id,
        "organization_name": as_text(
            _first(raw, "organizationName", "companyName")
            or (external_id_of(org_raw) and _first(org_raw, "name"))
        ),
        "subscription_order_id": order_id,
        "order_number": as_text(_first(raw, "orderNumber", "subscriptionOrderNumber")),
        "status": status_override or status_value(_first(raw, "status")),
        "effective_from": parse_datetime_ist(
            _first(raw, "effectiveFrom", "effective_from", "startedAt")
        ),
        "ended_at": parse_datetime_ist(
            _first(raw, "endedAt", "ended_at", "effectiveTo", "unassignedAt")
        ),
        "end_reason": as_text(_first(raw, "reason", "endReason", "endedReason")),
    }
    for field, value in values.items():
        if value is not None:
            setattr(row, field, value)
    row.attribution_data = _sanitised(raw)
    row.raw_data = _sanitised(raw)
    incoming_time = _source_timestamp(raw, fallback=source_time)
    if incoming_time and (
        row.source_updated_at is None or incoming_time >= row.source_updated_at
    ):
        row.source_updated_at = incoming_time
    row.synced_at = get_ist_now()
    if commit:
        db.commit()
        db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Mapping: coupons
# ---------------------------------------------------------------------------
def upsert_coupon(
    db: Session,
    partner_external_id: str,
    raw: Dict[str, Any],
    *,
    status_override: Optional[str] = None,
    source_time: Optional[datetime] = None,
    commit: bool = False,
) -> Optional[ChannelPartnerCoupon]:
    if not isinstance(raw, dict) or not partner_external_id:
        return None
    coupon_raw = first_present(raw, ["coupon"], default=None)
    if isinstance(coupon_raw, dict):
        merged = dict(coupon_raw)
        if _first(raw, "partnerId", "partner_id") and "partnerId" not in merged:
            merged["partnerId"] = _first(raw, "partnerId", "partner_id")
        raw = merged
    external_id = external_id_of(raw, "couponId", "coupon_id")
    code = as_text(_first(raw, "code", "couponCode"))
    key = _record_key(partner_external_id, external_id or code)
    row = (
        db.query(ChannelPartnerCoupon)
        .filter(ChannelPartnerCoupon.record_key == key)
        .first()
    )
    if row is None:
        row = ChannelPartnerCoupon(record_key=key, partner_external_id=partner_external_id)
        db.add(row)
    values = {
        "external_id": external_id,
        "code": code,
        "status": status_override or status_value(_first(raw, "status")),
        "description": as_text(_first(raw, "description", "title")),
        "discount_bps": as_int(_first(raw, "discountBps", "discount_bps")),
        "assigned_at": parse_datetime_ist(_first(raw, "assignedAt", "createdAt")),
        "expires_at": parse_datetime_ist(
            _first(raw, "expiresAt", "validUntil", "expiryDate")
        ),
    }
    for field, value in values.items():
        if value is not None:
            setattr(row, field, value)
    row.details_json = _sanitised(raw)
    row.raw_data = _sanitised(raw)
    incoming_time = _source_timestamp(raw, fallback=source_time)
    if incoming_time and (
        row.source_updated_at is None or incoming_time >= row.source_updated_at
    ):
        row.source_updated_at = incoming_time
    row.synced_at = get_ist_now()
    if commit:
        db.commit()
        db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Mapping: commissions
# ---------------------------------------------------------------------------
def upsert_commission(
    db: Session,
    partner_external_id: Optional[str],
    raw: Dict[str, Any],
    *,
    commit: bool = False,
) -> Optional[ChannelPartnerCommission]:
    if not isinstance(raw, dict):
        return None
    entry_raw = first_present(raw, ["entry"], default=None)
    if isinstance(entry_raw, dict):
        raw = entry_raw
    external_id = external_id_of(raw, "entryId", "entry_id", "commissionId", "commission_id")
    if not external_id:
        return None
    partner_external_id = partner_external_id or as_text(
        _first(raw, "partnerId", "partner_id") or get_path(raw, "partner.id")
    )
    values = {
        "partner_external_id": partner_external_id,
        "description": as_text(_first(raw, "description", "note", "reason")),
        "amount_paise": as_int(_first(raw, "amountPaise", "amount_paise", "amount")),
        "base_paise": as_int(_first(raw, "basePaise", "base_paise", "baseAmountPaise")),
        "rate_bps": as_int(_first(raw, "rateBps", "rate_bps")),
        "status": status_value(_first(raw, "status")),
        "hold_until": parse_datetime_ist(_first(raw, "holdUntil", "hold_until")),
        "invoice_number": as_text(_first(raw, "invoiceNumber", "invoice_number")),
        "client_name": as_text(_first(raw, "clientName", "client_name")),
        "entry_type": as_text(_first(raw, "type", "entryType")),
        "reason": as_text(_first(raw, "reason")),
    }
    incoming_time = _source_timestamp(raw)
    row = (
        db.query(ChannelPartnerCommission)
        .filter(ChannelPartnerCommission.external_id == external_id)
        .first()
    )
    if row is None:
        row = ChannelPartnerCommission(external_id=external_id)
        db.add(row)
        db.flush()
    if not _is_stale(row.source_updated_at, incoming_time):
        for field, value in values.items():
            if value is not None:
                setattr(row, field, value)
        if incoming_time and (
            row.source_updated_at is None or incoming_time >= row.source_updated_at
        ):
            row.source_updated_at = incoming_time
    earned_at = parse_datetime_ist(
        _first(raw, "createdAt", "created_at", "earnedAt", "earned_at")
    )
    if earned_at:
        row.earned_at = earned_at
    row.raw_data = _sanitised(raw)
    row.synced_at = get_ist_now()
    if commit:
        db.commit()
        db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Mapping: payouts
# ---------------------------------------------------------------------------
def upsert_payout(
    db: Session,
    raw: Dict[str, Any],
    *,
    commit: bool = False,
) -> Optional[ChannelPartnerPayout]:
    if not isinstance(raw, dict):
        return None
    external_id = external_id_of(raw, "payoutId", "payout_id")
    if not external_id:
        return None
    partner_raw = first_present(raw, ["partner"], default=None)
    partner_id = as_text(
        _first(raw, "partnerId", "partner_id")
        or (external_id_of(partner_raw) if isinstance(partner_raw, dict) else None)
    )
    entries = _first(
        raw,
        "commissionEntries",
        "entries",
        "commissions",
        "commissionEntryList",
    )
    values = {
        "partner_external_id": partner_id,
        "partner_name": as_text(
            _first(raw, "partnerName")
            or (first_present(partner_raw, ["name"]) if isinstance(partner_raw, dict) else None)
        ),
        "status": status_value(_first(raw, "status")),
        "gross_paise": as_int(_first(raw, "grossPaise", "gross_paise")),
        "net_paise": as_int(_first(raw, "netPaise", "net_paise")),
        "tds_paise": as_int(_first(raw, "tdsPaise", "tds_paise")),
        "gst_paise": as_int(_first(raw, "gstPaise", "gst_paise")),
        "adjustment_paise": as_int(
            _first(raw, "adjustmentPaise", "adjustment_paise", "adjustmentsPaise")
        ),
        "payment_method": as_text(_first(raw, "method", "paymentMethod")),
        "payment_reference": as_text(
            _first(raw, "reference", "paymentReference", "utr")
        ),
        "payment_date": parse_datetime_ist(
            _first(raw, "paidAt", "paymentDate", "paid_at", "payment_date")
        ),
        "partner_invoice_number": as_text(
            _first(raw, "partnerInvoiceNumber", "invoiceNumber")
        ),
        "notes": as_text(_first(raw, "notes", "note")),
        "cancellation_reason": as_text(_first(raw, "cancelReason", "reason")),
    }
    incoming_time = _source_timestamp(raw)
    row = (
        db.query(ChannelPartnerPayout)
        .filter(ChannelPartnerPayout.external_id == external_id)
        .first()
    )
    if row is None:
        row = ChannelPartnerPayout(external_id=external_id)
        db.add(row)
        db.flush()
    if not _is_stale(row.source_updated_at, incoming_time):
        for field, value in values.items():
            if value is not None:
                setattr(row, field, value)
        if entries is not None:
            row.commission_entries_json = _sanitised(entries)
        if incoming_time and (
            row.source_updated_at is None or incoming_time >= row.source_updated_at
        ):
            row.source_updated_at = incoming_time
    created_at = parse_datetime_ist(_first(raw, "createdAt", "created_at"))
    if created_at:
        row.source_created_at = created_at
    row.raw_data = _sanitised(raw)
    row.synced_at = get_ist_now()
    if commit:
        db.commit()
        db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Sync: partners
# ---------------------------------------------------------------------------
def sync_summary(db: Session, client: ChannelPartnerClient) -> Dict[str, Any]:
    payload = client.get_summary()
    row = get_integration_row(db)
    row.summary_json = _sanitised(payload)
    row.summary_synced_at = get_ist_now()
    db.commit()
    return {"summarySynced": True}


def sync_partner_detail(
    db: Session,
    client: ChannelPartnerClient,
    partner_external_id: str,
    *,
    include_related: bool = True,
) -> Dict[str, Any]:
    detail = client.get_partner(partner_external_id)
    partner_raw = first_present(detail, ["partner"], default=None)
    if not isinstance(partner_raw, dict):
        partner_raw = detail if isinstance(detail, dict) else {}
    if not partner_raw.get("id") and not partner_raw.get("partnerId"):
        partner_raw = {**partner_raw, "id": partner_external_id}

    partner = upsert_partner(
        db,
        partner_raw,
        detail_payload=detail if isinstance(detail, dict) else {},
        detail_raw=detail,
    )
    for user in _login_rows(detail if isinstance(detail, dict) else {}):
        upsert_partner_login(db, partner_external_id, user)
    db.commit()

    result: Dict[str, Any] = {
        "partner": 1,
        "logins": len(_login_rows(detail if isinstance(detail, dict) else {})),
    }
    if include_related:
        try:
            clients_payload = client.list_partner_clients(partner_external_id)
            clients = extract_list(clients_payload, ["clients", "attributions"])
            for raw in clients:
                if isinstance(raw, dict):
                    upsert_client_attribution(
                        db,
                        partner_external_id,
                        raw,
                        source_time=get_ist_now(),
                    )
            db.commit()
            result["clients"] = len(clients)
        except ChannelPartnerAPIError as exc:
            db.rollback()
            result["clientsError"] = exc.message

        try:
            coupons_payload = client.list_partner_coupons(partner_external_id)
            coupons = extract_list(coupons_payload, ["coupons"])
            for raw in coupons:
                if isinstance(raw, dict):
                    upsert_coupon(db, partner_external_id, raw)
            db.commit()
            result["coupons"] = len(coupons)
        except ChannelPartnerAPIError as exc:
            db.rollback()
            result["couponsError"] = exc.message

        try:
            result.update(
                _sync_partner_commissions(db, client, partner_external_id)
            )
        except ChannelPartnerAPIError as exc:
            db.rollback()
            result["commissionsError"] = exc.message

    return result


def _sync_partner_commissions(
    db: Session,
    client: ChannelPartnerClient,
    partner_external_id: str,
    *,
    page_size: int = 200,
    max_pages: int = 50,
) -> Dict[str, Any]:
    seen = set()
    total = 0
    offset = 0
    for _ in range(max_pages):
        payload = client.list_partner_commissions(
            partner_external_id, limit=page_size, offset=offset
        )
        page = extract_list(payload, ["commissions", "ledger", "entries"])
        if not page:
            break
        new_in_page = 0
        for raw in page:
            if not isinstance(raw, dict):
                continue
            entry_id = external_id_of(raw, "entryId", "entry_id", "commissionId")
            if entry_id and entry_id in seen:
                continue
            if entry_id:
                seen.add(entry_id)
            upsert_commission(db, partner_external_id, raw)
            total += 1
            new_in_page += 1
        db.commit()
        if len(page) < page_size or new_in_page == 0:
            break
        offset += page_size
    return {"commissions": total}


def sync_partners(
    db: Session,
    client: ChannelPartnerClient,
    *,
    include_related: bool = True,
) -> Dict[str, Any]:
    payload = client.list_partners()
    partners = extract_list(payload, ["partners"])
    stats: Dict[str, Any] = {"partners": 0, "logins": 0, "clients": 0, "coupons": 0, "commissions": 0}
    errors: List[str] = []

    for raw in partners:
        if not isinstance(raw, dict):
            continue
        try:
            upsert_partner(db, raw, list_raw=raw)
            stats["partners"] += 1
        except Exception as exc:  # keep syncing the rest
            db.rollback()
            errors.append(f"partner: {exc}")
    db.commit()

    if include_related:
        ids = [
            external_id_of(raw, "partnerId", "partner_id")
            for raw in partners
            if isinstance(raw, dict)
        ]
        for partner_id in [pid for pid in ids if pid]:
            try:
                detail_stats = sync_partner_detail(
                    db, client, partner_id, include_related=True
                )
                for key in ("logins", "clients", "coupons", "commissions"):
                    stats[key] = stats.get(key, 0) + int(detail_stats.get(key) or 0)
                for key in ("clientsError", "couponsError", "commissionsError"):
                    if detail_stats.get(key):
                        errors.append(f"{partner_id} {key}: {detail_stats[key]}")
            except ChannelPartnerAPIError as exc:
                db.rollback()
                errors.append(f"{partner_id}: {exc.message}")
            except Exception as exc:
                db.rollback()
                errors.append(f"{partner_id}: {exc}")

    if errors:
        stats["errors"] = errors[:20]
    return stats


# ---------------------------------------------------------------------------
# Sync: applications / leads / payouts
# ---------------------------------------------------------------------------
def sync_applications(
    db: Session,
    client: ChannelPartnerClient,
    *,
    include_details: bool = True,
) -> Dict[str, Any]:
    applications: Dict[str, Dict[str, Any]] = {}
    errors: List[str] = []

    try:
        initial = client.list_applications()
        for raw in extract_list(initial, ["applications"]):
            if isinstance(raw, dict):
                external_id = external_id_of(raw, "applicationId", "application_id")
                if external_id:
                    applications[external_id] = raw
    except ChannelPartnerAPIError:
        pass

    for status in APPLICATION_STATUSES:
        try:
            payload = client.list_applications(status)
            for raw in extract_list(payload, ["applications"]):
                if isinstance(raw, dict):
                    external_id = external_id_of(raw, "applicationId", "application_id")
                    if external_id:
                        applications[external_id] = raw
        except ChannelPartnerAPIError as exc:
            errors.append(f"applications[{status}]: {exc.message}")

    if not applications and errors:
        raise ChannelPartnerAPIError(errors[0])

    details = 0
    for application_id, raw in applications.items():
        try:
            if include_details:
                try:
                    detail = client.get_application(application_id)
                except ChannelPartnerAPIError as exc:
                    errors.append(f"application {application_id} detail: {exc.message}")
                    detail = None
                if detail is not None:
                    detail_raw = first_present(detail, ["application"], default=None)
                    if not isinstance(detail_raw, dict):
                        detail_raw = raw
                    # The list payload may carry fields absent from the detail envelope.
                    merged = {**raw, **detail_raw}
                    application_raw = merged
                    docs = first_present(detail, ["documents"], default=None)
                    if docs is None and isinstance(detail_raw, dict):
                        docs = first_present(detail_raw, ["documents"], default=None)
                    if docs is not None:
                        application_raw = {**merged, "documents": docs}
                    details += 1
                else:
                    application_raw = raw
            else:
                application_raw = raw
            upsert_application(db, application_raw)
        except Exception as exc:
            db.rollback()
            errors.append(f"application {application_id}: {exc}")
    db.commit()

    stats: Dict[str, Any] = {"applications": len(applications), "applicationDetails": details}
    if errors:
        stats["errors"] = errors[:20]
    return stats


def sync_leads(db: Session, client: ChannelPartnerClient) -> Dict[str, Any]:
    leads: Dict[str, Dict[str, Any]] = {}
    errors: List[str] = []

    try:
        payload = client.list_leads()
        for raw in extract_list(payload, ["leads"]):
            if isinstance(raw, dict):
                external_id = external_id_of(raw, "leadId", "lead_id")
                if external_id:
                    leads[external_id] = raw
    except ChannelPartnerAPIError:
        pass

    for status in LEAD_STATUSES:
        try:
            payload = client.list_leads(status=status)
            for raw in extract_list(payload, ["leads"]):
                if isinstance(raw, dict):
                    external_id = external_id_of(raw, "leadId", "lead_id")
                    if external_id:
                        leads[external_id] = raw
        except ChannelPartnerAPIError as exc:
            errors.append(f"leads[{status}]: {exc.message}")

    if not leads and errors:
        raise ChannelPartnerAPIError(errors[0])

    for raw in leads.values():
        try:
            upsert_lead(db, raw)
        except Exception as exc:
            db.rollback()
            errors.append(f"lead: {exc}")
    db.commit()

    stats: Dict[str, Any] = {"leads": len(leads)}
    # Historical mirror rows that were stored before the All Leads mapping
    # existed still need a CRM lead. New rows were already mirrored by the
    # upsert above, so this pass is idempotent and only fills gaps.
    try:
        stats.update(sync_channel_partner_leads_to_crm(db, commit=False))
        db.commit()
    except Exception as exc:
        db.rollback()
        errors.append(f"crm leads: {exc}")
    if errors:
        stats["errors"] = errors[:20]
    return stats


def sync_payouts(
    db: Session,
    client: ChannelPartnerClient,
    *,
    include_details: bool = True,
) -> Dict[str, Any]:
    payouts: Dict[str, Dict[str, Any]] = {}
    errors: List[str] = []

    try:
        payload = client.list_payouts()
        for raw in extract_list(payload, ["payouts"]):
            if isinstance(raw, dict):
                external_id = external_id_of(raw, "payoutId", "payout_id")
                if external_id:
                    payouts[external_id] = raw
    except ChannelPartnerAPIError:
        pass

    for status in PAYOUT_STATUSES:
        try:
            payload = client.list_payouts(status=status)
            for raw in extract_list(payload, ["payouts"]):
                if isinstance(raw, dict):
                    external_id = external_id_of(raw, "payoutId", "payout_id")
                    if external_id:
                        payouts[external_id] = raw
        except ChannelPartnerAPIError as exc:
            errors.append(f"payouts[{status}]: {exc.message}")

    if not payouts and errors:
        raise ChannelPartnerAPIError(errors[0])

    details = 0
    for payout_id, raw in payouts.items():
        try:
            if include_details:
                try:
                    detail = client.get_payout(payout_id)
                except ChannelPartnerAPIError as exc:
                    errors.append(f"payout {payout_id} detail: {exc.message}")
                    detail = None
                if detail is not None:
                    payout_raw = first_present(detail, ["payout"], default=None)
                    if not isinstance(payout_raw, dict):
                        payout_raw = {**raw, **detail} if isinstance(detail, dict) else raw
                    details += 1
                else:
                    payout_raw = raw
            else:
                payout_raw = raw
            upsert_payout(db, payout_raw)
        except Exception as exc:
            db.rollback()
            errors.append(f"payout {payout_id}: {exc}")
    db.commit()

    stats: Dict[str, Any] = {"payouts": len(payouts), "payoutDetails": details}
    if errors:
        stats["errors"] = errors[:20]
    return stats


# ---------------------------------------------------------------------------
# Webhook verification / ingestion
# ---------------------------------------------------------------------------
def verify_webhook_signature(
    raw_body: bytes,
    signature_header: Optional[str],
    secret: Optional[str],
    *,
    tolerance_seconds: int = 300,
    now: Optional[float] = None,
) -> Tuple[bool, str]:
    """Verify ``WAHRMS-Signature: t=...,v1=...`` over the raw request bytes."""
    if not secret:
        return False, "webhook_secret_not_configured"
    if not signature_header:
        return False, "missing_signature"
    parts: Dict[str, str] = {}
    for piece in signature_header.split(","):
        if "=" not in piece:
            continue
        key, value = piece.split("=", 1)
        parts[key.strip()] = value.strip()
    try:
        timestamp = int(parts.get("t", "0"))
    except (TypeError, ValueError):
        return False, "invalid_timestamp"
    signature = parts.get("v1", "")
    if not timestamp or not signature:
        return False, "invalid_signature_header"
    current = now if now is not None else time.time()
    if abs(current - timestamp) > tolerance_seconds:
        return False, "timestamp_out_of_tolerance"

    expected = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.".encode("utf-8") + raw_body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return False, "signature_mismatch"
    return True, "ok"


def record_webhook_rejection(
    db: Session,
    *,
    reason: str,
    remote_ip: Optional[str] = None,
    signature_header: Optional[str] = None,
    raw_body: bytes = b"",
) -> None:
    try:
        db.add(
            ChannelPartnerWebhookRejection(
                reason=reason[:120],
                remote_ip=(remote_ip or "")[:80] or None,
                signature_header=(signature_header or "")[:500] or None,
                body_sha256=hashlib.sha256(raw_body).hexdigest() if raw_body else None,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not record rejected WAHRMS webhook")


def _event_headers(headers: Dict[str, str]) -> Dict[str, str]:
    allowed = {
        "wahrms-event",
        "wahrms-event-id",
        "wahrms-delivery",
        "wahrms-signature",
        "content-type",
        "user-agent",
    }
    return {
        key: value
        for key, value in headers.items()
        if key.lower() in allowed
    }


def store_webhook_event(
    db: Session,
    *,
    event_id: str,
    event_type: str,
    payload: Dict[str, Any],
    headers: Dict[str, str],
    created_at: Optional[datetime] = None,
    source: str = "webhook",
    sequence: Optional[int] = None,
) -> Tuple[Optional[ChannelPartnerWebhookEvent], bool]:
    """Store once. Returns (row, duplicate)."""
    existing = (
        db.query(ChannelPartnerWebhookEvent)
        .filter(ChannelPartnerWebhookEvent.event_id == event_id)
        .first()
    )
    if existing:
        return existing, True

    related = scan_related_ids(payload)
    event = ChannelPartnerWebhookEvent(
        event_id=event_id[:191],
        delivery_id=(headers.get("WAHRMS-Delivery") or headers.get("wahrms-delivery") or "")[:191] or None,
        event_type=(event_type or "unknown")[:80],
        event_created_at=created_at or get_ist_now(),
        sequence=sequence,
        source=source,
        status="pending",
        related_partner_external_id=related.get("partner"),
        related_lead_external_id=related.get("lead"),
        related_client_external_id=related.get("client"),
        payload=_json_dumps(_sanitised(payload)),
        headers_json=as_json(_event_headers(headers or {})),
    )
    db.add(event)
    try:
        db.commit()
        db.refresh(event)
        return event, False
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(ChannelPartnerWebhookEvent)
            .filter(ChannelPartnerWebhookEvent.event_id == event_id)
            .first()
        )
        return existing, True


def mark_event(
    db: Session,
    event: ChannelPartnerWebhookEvent,
    status: str,
    error: Optional[str] = None,
) -> None:
    event.status = status
    event.error = (error or "")[:4000] or None
    event.processed_at = get_ist_now()
    db.commit()


def process_webhook_event(event_db_id: int) -> None:
    """Background processor for a stored webhook event."""
    db = SessionLocal()
    try:
        event = (
            db.query(ChannelPartnerWebhookEvent)
            .filter(ChannelPartnerWebhookEvent.id == event_db_id)
            .first()
        )
        if not event or event.status == "processed":
            return
        try:
            payload = json.loads(event.payload or "{}")
            status = apply_event(
                db,
                event_type=event.event_type,
                payload=payload,
                source_time=event.event_created_at,
            )
            mark_event(db, event, status)
        except Exception as exc:
            db.rollback()
            logger.exception("WAHRMS webhook event processing failed")
            mark_event(db, event, "failed", str(exc))
    finally:
        db.close()


def apply_event(
    db: Session,
    *,
    event_type: str,
    payload: Dict[str, Any],
    source_time: Optional[datetime] = None,
) -> str:
    """Apply one event to the local mirror. Returns final event status."""
    event_type = (event_type or "").lower()
    data = payload.get("data") if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        data = {}
    source_time = source_time or parse_datetime_ist(
        payload.get("createdAt") if isinstance(payload, dict) else None
    )

    if event_type == "ping":
        return "processed"

    if event_type in {"application.submitted", "application.approved", "application.rejected"}:
        application_raw = first_present(data, ["application"], default=None)
        if isinstance(application_raw, dict):
            upsert_application(db, application_raw, source_time=source_time)
        partner_raw = first_present(data, ["partner"], default=None)
        if isinstance(partner_raw, dict):
            upsert_partner(db, partner_raw, source_time=source_time)
        db.commit()
        return "processed" if isinstance(application_raw, dict) else "ignored"

    if event_type in {"partner.created", "partner.updated", "partner.status_changed"}:
        partner_raw = first_present(data, ["partner"], default=None)
        if isinstance(partner_raw, dict):
            partner = upsert_partner(db, partner_raw, source_time=source_time)
            if event_type == "partner.status_changed":
                new_status = status_value(
                    first_present(data, ["status", "newStatus"], default=None)
                )
                if (
                    partner
                    and new_status
                    and (
                        not source_time
                        or not partner.source_updated_at
                        or source_time >= partner.source_updated_at
                    )
                ):
                    partner.status = new_status
                    partner.source_updated_at = source_time or get_ist_now()
        else:
            partner_id = as_text(first_present(data, ["partnerId", "partner_id"]))
            if not partner_id:
                return "ignored"
            partner = (
                db.query(ChannelPartner)
                .filter(ChannelPartner.external_id == partner_id)
                .first()
            )
            if not partner:
                return "ignored"
            new_status = status_value(
                first_present(data, ["status", "newStatus"], default=None)
            )
            if (
                new_status
                and (
                    not source_time
                    or not partner.source_updated_at
                    or source_time >= partner.source_updated_at
                )
            ):
                partner.status = new_status
                partner.source_updated_at = source_time or get_ist_now()
        db.commit()
        return "processed"

    if event_type == "partner.user_invited":
        partner_id = as_text(first_present(data, ["partnerId", "partner_id"]))
        user = first_present(data, ["user"], default=None)
        if partner_id and isinstance(user, dict):
            upsert_partner_login(db, partner_id, user)
            db.commit()
            return "processed"
        return "ignored"

    if event_type in {"lead.created", "lead.updated", "lead.converted"}:
        lead_raw = first_present(data, ["lead"], default=None)
        if isinstance(lead_raw, dict):
            upsert_lead(db, lead_raw, source_time=source_time)
            db.commit()
            return "processed"
        return "ignored"

    if event_type in {"client.assigned", "client.unassigned"}:
        attribution = first_present(data, ["attribution"], default=None)
        if not isinstance(attribution, dict):
            attribution = data
        partner_id = as_text(
            first_present(attribution, ["partnerId", "partner_id"])
            or first_present(data, ["partnerId", "partner_id"])
        )
        if not partner_id:
            return "ignored"
        upsert_client_attribution(
            db,
            partner_id,
            attribution,
            status_override="ended" if event_type == "client.unassigned" else None,
            source_time=source_time,
        )
        db.commit()
        return "processed"

    if event_type in {"coupon.assigned", "coupon.removed"}:
        partner_id = as_text(first_present(data, ["partnerId", "partner_id"]))
        if not partner_id:
            return "ignored"
        upsert_coupon(
            db,
            partner_id,
            data,
            status_override=(
                "removed" if event_type == "coupon.removed" else "assigned"
            ),
            source_time=source_time,
        )
        db.commit()
        return "processed"

    if event_type in {"commission.earned", "commission.adjusted"}:
        entry = first_present(data, ["entry"], default=None)
        if isinstance(entry, dict):
            partner_id = as_text(
                first_present(data, ["partnerId", "partner_id"])
                or first_present(entry, ["partnerId", "partner_id"])
            )
            upsert_commission(db, partner_id, entry)
            db.commit()
            return "processed"
        return "ignored"

    if event_type == "commission.reversed":
        entry_id = as_text(first_present(data, ["entryId", "entry_id"]))
        if not entry_id:
            return "ignored"
        row = (
            db.query(ChannelPartnerCommission)
            .filter(ChannelPartnerCommission.external_id == entry_id)
            .first()
        )
        if row:
            if source_time and row.source_updated_at and source_time < row.source_updated_at:
                return "processed"
            row.status = "cancelled"
            row.reason = as_text(first_present(data, ["reason"])) or row.reason
            row.source_updated_at = source_time or get_ist_now()
            db.commit()
            return "processed"
        return "ignored"

    if event_type in {
        "payout.created",
        "payout.approved",
        "payout.paid",
        "payout.cancelled",
    }:
        payout_raw = first_present(data, ["payout"], default=None)
        if not isinstance(payout_raw, dict):
            return "ignored"
        if event_type == "payout.cancelled":
            reason = as_text(first_present(data, ["reason"]))
            if reason:
                payout_raw = {**payout_raw, "cancelReason": reason}
        upsert_payout(db, payout_raw)
        db.commit()
        return "processed"

    # Documented events are handled above. Unknown/unsupported events are kept
    # for audit but marked ignored rather than failing the delivery.
    return "ignored"


# ---------------------------------------------------------------------------
# Polling
# ---------------------------------------------------------------------------
def poll_events_once(
    db: Session,
    client: ChannelPartnerClient,
    *,
    batch_size: int = 500,
    max_batches: int = 10,
) -> Dict[str, Any]:
    checkpoint = get_checkpoint(db, "events")
    checkpoint.last_attempt_at = get_ist_now()
    db.commit()

    after = int(checkpoint.last_after or 0)
    processed = 0
    duplicates = 0
    ignored = 0
    failed = 0
    batches = 0
    last_next = after

    try:
        for _ in range(max_batches):
            batches += 1
            payload = client.list_events(after=after, limit=min(batch_size, 500))
            events = extract_list(payload, ["events"])
            next_after = first_present(payload, ["nextAfter", "next_after"], default=None)
            has_more = as_bool(first_present(payload, ["hasMore", "has_more"], default=None))

            for raw in events:
                if not isinstance(raw, dict):
                    continue
                event_id = as_text(first_present(raw, ["id", "eventId"]))
                if not event_id:
                    continue
                event_type = as_text(first_present(raw, ["type"])) or "unknown"
                created_at = parse_datetime_ist(first_present(raw, ["createdAt", "created_at"]))
                sequence = as_int(first_present(raw, ["seq", "sequence"]))
                event, duplicate = store_webhook_event(
                    db,
                    event_id=event_id,
                    event_type=event_type,
                    payload=raw,
                    headers={},
                    created_at=created_at,
                    source="poll",
                    sequence=sequence,
                )
                if duplicate:
                    duplicates += 1
                    if event and event.status == "pending":
                        # A delivery may have been stored but never processed
                        # (e.g. worker restart); finish it now.
                        try:
                            status = apply_event(
                                db,
                                event_type=event.event_type,
                                payload=json.loads(event.payload or "{}"),
                                source_time=event.event_created_at,
                            )
                            mark_event(db, event, status)
                            processed += 1
                        except Exception:
                            db.rollback()
                            failed += 1
                    continue
                if not event:
                    continue
                try:
                    status = apply_event(
                        db,
                        event_type=event.event_type,
                        payload=raw,
                        source_time=event.event_created_at,
                    )
                    mark_event(db, event, status)
                    processed += 1
                    if status == "ignored":
                        ignored += 1
                except Exception as exc:
                    db.rollback()
                    mark_event(db, event, "failed", str(exc))
                    failed += 1

            if next_after is not None:
                try:
                    after = int(next_after)
                    last_next = after
                except (TypeError, ValueError):
                    pass
            elif events:
                seq_values = [
                    as_int(first_present(raw, ["seq"]))
                    for raw in events
                    if isinstance(raw, dict)
                ]
                seq_values = [value for value in seq_values if value is not None]
                if seq_values:
                    after = max(seq_values)
                    last_next = after

            if not events or not has_more:
                break

        checkpoint = get_checkpoint(db, "events")
        checkpoint.last_after = last_next
        checkpoint.last_success_at = get_ist_now()
        checkpoint.last_error = None
        integration = get_integration_row(db)
        integration.last_event_poll_at = get_ist_now()
        integration.last_event_poll_error = None
        db.commit()
    except Exception as exc:
        db.rollback()
        checkpoint = get_checkpoint(db, "events")
        checkpoint.last_error = str(exc)[:4000]
        checkpoint.last_attempt_at = get_ist_now()
        integration = get_integration_row(db)
        integration.last_event_poll_at = get_ist_now()
        integration.last_event_poll_error = str(exc)[:4000]
        db.commit()
        raise

    return {
        "after": last_next,
        "batches": batches,
        "processed": processed,
        "duplicates": duplicates,
        "ignored": ignored,
        "failed": failed,
    }


# ---------------------------------------------------------------------------
# Sync orchestration
# ---------------------------------------------------------------------------
def create_sync_run(
    db: Session,
    *,
    scope: str,
    trigger: str,
    user_id: Optional[int] = None,
) -> ChannelPartnerSyncRun:
    run = ChannelPartnerSyncRun(
        scope=scope,
        trigger=trigger,
        status="running",
        triggered_by_user_id=user_id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _apply_sync_scope(
    db: Session, client: ChannelPartnerClient, scope: str
) -> Dict[str, Any]:
    results: Dict[str, Any] = {}
    scope = (scope or "full").lower()
    if scope in ("full", "summary"):
        results["summary"] = sync_summary(db, client)
    if scope in ("full", "partners"):
        results["partners"] = sync_partners(db, client, include_related=True)
    if scope in ("full", "applications"):
        results["applications"] = sync_applications(db, client, include_details=True)
    if scope in ("full", "leads"):
        results["leads"] = sync_leads(db, client)
    if scope in ("full", "payouts"):
        results["payouts"] = sync_payouts(db, client, include_details=True)
    if scope in ("full", "events"):
        results["events"] = poll_events_once(db, client)
    return results


def execute_sync_run(run_id: int) -> None:
    """Run a full/manual synchronisation in its own database session."""
    db = SessionLocal()
    run = None
    try:
        run = (
            db.query(ChannelPartnerSyncRun)
            .filter(ChannelPartnerSyncRun.id == run_id)
            .first()
        )
        if not run:
            return
        integration = get_integration_row(db)

        try:
            config = load_effective_config(db)
            if not config.configured:
                raise ChannelPartnerNotConfigured(
                    "WA HRMS Channel Partner API credentials are not configured."
                )
            with ChannelPartnerClient(config) as client:
                stats = _apply_sync_scope(db, client, run.scope)
            run.status = "success"
            run.stats_json = _sanitised(stats)
            run.finished_at = get_ist_now()
            integration.last_sync_at = get_ist_now()
            integration.last_sync_status = "success"
            integration.last_sync_error = None
            db.commit()
        except Exception as exc:
            db.rollback()
            message = getattr(exc, "message", None) or str(exc)
            run = (
                db.query(ChannelPartnerSyncRun)
                .filter(ChannelPartnerSyncRun.id == run_id)
                .first()
            )
            if run:
                run.status = "failed"
                run.error = message[:4000]
                run.finished_at = get_ist_now()
            integration = get_integration_row(db)
            integration.last_sync_at = get_ist_now()
            integration.last_sync_status = "failed"
            integration.last_sync_error = message[:4000]
            db.commit()
            logger.exception("WAHRMS Channel Partner sync failed")
    finally:
        db.close()


def run_event_poll() -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        config = load_effective_config(db)
        if not config.configured:
            return None
        with ChannelPartnerClient(config) as client:
            return poll_events_once(db, client)
    except Exception as exc:
        logger.warning("WAHRMS event poll failed: %s", exc)
        return None
    finally:
        db.close()


async def start_channel_partner_scheduler(interval_seconds: int = 300) -> None:
    """Poll the documented event log for recovery; webhooks stay primary."""
    await asyncio.sleep(20)
    try:
        await asyncio.to_thread(_startup_sync_if_empty)
    except Exception as exc:
        logger.warning("WAHRMS startup sync skipped: %s", exc)

    # Historical mirror rows may predate the All Leads integration. Backfill
    # them once per application start; the operation is idempotent.
    try:
        await asyncio.to_thread(backfill_channel_partner_leads)
    except Exception as exc:
        logger.warning("WAHRMS Channel Partner CRM lead backfill skipped: %s", exc)

    while True:
        await asyncio.sleep(max(60, interval_seconds))
        try:
            await asyncio.to_thread(run_event_poll)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("WAHRMS scheduled event poll failed: %s", exc)


def _startup_sync_if_empty() -> None:
    db = SessionLocal()
    run_id = None
    try:
        config = load_effective_config(db)
        if not config.configured:
            return
        has_partner = db.query(ChannelPartner.id).first() is not None
        if has_partner:
            return
        run = create_sync_run(db, scope="full", trigger="startup")
        run_id = run.id
    except Exception:
        logger.exception("WAHRMS startup sync could not start")
    finally:
        db.close()
    if run_id:
        execute_sync_run(run_id)


def checkpoint_snapshot(db: Session) -> Dict[str, Any]:
    checkpoint = get_checkpoint(db, "events")
    return {
        "lastProcessedCheckpoint": int(checkpoint.last_after or 0),
        "lastSuccessfulPollAt": ist_iso(checkpoint.last_success_at),
        "lastPollAttemptAt": ist_iso(checkpoint.last_attempt_at),
        "lastPollError": checkpoint.last_error,
    }
