"""
Meta Click-to-WhatsApp (CTWA) lead capture service.

Responsibilities:
  * Validate X-Hub-Signature-256 on the raw webhook body.
  * Verify the Meta webhook subscription challenge.
  * Extract incoming message + referral (ad click) details.
  * Create normal CRM leads/enquiries through ReInquiryService (no duplicate
    lead system) and apply the existing assignment configuration.
  * Store ad attribution separately and resolve campaign/ad names later via
    the Meta Marketing API (ads_read permission) when authorized.
  * Record every processed event for idempotency and auditing.
"""

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import SessionLocal
from models.whatsapp_ad_lead import WhatsAppAdAttribution, WhatsAppWebhookEvent
from services.lead_assignment_service import assign_lead_immediately
from services.reinquiry_service import ReInquiryService
from utils.timezone import IST_TIMEZONE, get_ist_now

from .config import WhatsAppAdConfig

logger = logging.getLogger("whatsapp_ads")

SOURCE = "WHATSAPP_ADS"
SOURCE_LABEL = "WhatsApp Ads"

_MEDIA_REFERRAL_FIELDS = ("image_url", "video_url", "thumbnail_url")


def _json_dumps(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


def _safe_epoch_to_ist(value: Any) -> Optional[datetime]:
    """Meta timestamps are UTC epoch seconds. CRM stores naive IST datetimes."""
    try:
        if value is None or str(value).strip() == "":
            return None
        return datetime.fromtimestamp(int(float(value)), tz=IST_TIMEZONE).replace(
            tzinfo=None
        )
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def verify_signature(raw_body: bytes, signature_header: Optional[str]) -> bool:
    """
    Validate Meta's X-Hub-Signature-256 header against the raw request body.

    Fails closed when no app secret is configured: an unauthenticated public
    endpoint must never be able to create CRM leads.
    """
    secret = WhatsAppAdConfig.get_app_secret()
    if not secret:
        logger.error(
            "WhatsApp Ad webhook rejected: no app secret configured "
            "(set WHATSAPP_AD_APP_SECRET or META_APP_SECRET)."
        )
        return False
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        secret.encode("utf-8"), raw_body or b"", hashlib.sha256
    ).hexdigest()
    provided = signature_header.split("=", 1)[1].strip()
    return hmac.compare_digest(expected, provided)


def verify_challenge(mode: Optional[str], token: Optional[str]) -> bool:
    if (mode or "") != "subscribe" or not token:
        return False
    expected = WhatsAppAdConfig.get_verify_token()
    return bool(expected) and hmac.compare_digest(str(token), str(expected))


def extract_message_text(message: Dict[str, Any]) -> str:
    """Human-readable first message for the CRM and the listing page."""
    msg_type = (message.get("type") or "text").lower()
    if msg_type == "text":
        return (message.get("text") or {}).get("body") or ""
    if msg_type in {"image", "video", "document", "audio"}:
        media = message.get(msg_type) or {}
        caption = media.get("caption") or ""
        filename = media.get("filename") or ""
        label = f"[{msg_type.title()} message]"
        return f"{label} {caption or filename}".strip()
    if msg_type == "button":
        return (message.get("button") or {}).get("text") or "[Button reply]"
    if msg_type == "interactive":
        interactive = message.get("interactive") or {}
        reply = interactive.get("button_reply") or interactive.get("list_reply") or {}
        return reply.get("title") or "[Interactive reply]"
    if msg_type == "location":
        location = message.get("location") or {}
        lat = location.get("latitude")
        lon = location.get("longitude")
        return f"[Location] {lat}, {lon}".strip()
    if msg_type == "contacts":
        return "[Contact card]"
    if msg_type == "sticker":
        return "[Sticker]"
    if msg_type == "reaction":
        return (message.get("reaction") or {}).get("emoji") or "[Reaction]"
    return f"[{msg_type.title()} message]"


def _contact_names(value: Dict[str, Any]) -> Dict[str, str]:
    names: Dict[str, str] = {}
    for contact in value.get("contacts") or []:
        wa_id = str(contact.get("wa_id") or "").strip()
        name = ((contact.get("profile") or {}).get("name") or "").strip()
        if wa_id and name:
            names[wa_id] = name
    return names


def _referral_media(referral: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    for field in _MEDIA_REFERRAL_FIELDS:
        url = referral.get(field)
        if url:
            return (referral.get("media_type") or field.replace("_url", "")), str(url)
    return (referral.get("media_type"), None)


def _event_key_for_message(message: Dict[str, Any], referral: Dict[str, Any]) -> str:
    wamid = str(message.get("id") or "").strip()
    if wamid:
        return f"msg:{wamid}"
    fingerprint = "|".join(
        str(part or "")
        for part in (
            message.get("from"),
            message.get("timestamp"),
            referral.get("source_id"),
            referral.get("ctwa_clid"),
            extract_message_text(message),
        )
    )
    return "msgfp:" + hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()


class WhatsAppAdLeadService:
    """Stateless service used by the webhook router, CRM router and scheduler."""

    # ------------------------------------------------------------------
    # Payload processing
    # ------------------------------------------------------------------
    @classmethod
    def process_payload(
        cls, db: Session, payload: Dict[str, Any], raw_body: bytes = b""
    ) -> Dict[str, int]:
        summary = {
            "processed": 0,
            "skipped": 0,
            "duplicates": 0,
            "failed": 0,
            "status_updates": 0,
        }
        if not isinstance(payload, dict):
            return summary

        waba_filter = WhatsAppAdConfig.get_business_account_id()
        mirror_entries = []

        for entry in payload.get("entry") or []:
            business_account_id = str(entry.get("id") or "").strip()
            if waba_filter and business_account_id and business_account_id != waba_filter:
                logger.warning(
                    "Ignoring WhatsApp webhook entry for unexpected WABA %s "
                    "(configured %s).",
                    business_account_id,
                    waba_filter,
                )
                continue

            mirror_entries.append(entry)
            for change in entry.get("changes") or []:
                value = change.get("value") or {}
                metadata = value.get("metadata") or {}
                phone_number_id = metadata.get("phone_number_id")
                contact_names = _contact_names(value)

                for message in value.get("messages") or []:
                    referral = message.get("referral")
                    if not isinstance(referral, dict) or not referral:
                        # Ordinary conversation message: no ad click to capture.
                        summary["skipped"] += 1
                        continue
                    outcome = cls._safe_process_message(
                        db=db,
                        entry=entry,
                        value=value,
                        message=message,
                        referral=referral,
                        contact_names=contact_names,
                        phone_number_id=phone_number_id,
                        business_account_id=business_account_id,
                    )
                    summary[outcome] = summary.get(outcome, 0) + 1

                # Status-only events never create leads. They are only mirrored
                # into the existing WhatsApp inbox for delivery/read receipts.
                summary["status_updates"] += len(value.get("statuses") or [])

        # Mirror the same payload into the existing WhatsApp inbox so normal
        # two-way conversations continue to appear under Communication >
        # WhatsApp. This never creates leads on its own.
        if mirror_entries and WhatsAppAdConfig.mirror_inbox_enabled():
            try:
                from integrations.whatsapp.service import WhatsAppService

                WhatsAppService.process_inbound_webhook_payload(
                    db,
                    {
                        "object": payload.get("object"),
                        "entry": mirror_entries,
                    },
                )
            except Exception as exc:  # mirroring must never block lead capture
                db.rollback()
                logger.error("WhatsApp inbox mirror failed: %s", exc, exc_info=True)

        return summary

    @classmethod
    def _safe_process_message(
        cls,
        db: Session,
        entry: Dict[str, Any],
        value: Dict[str, Any],
        message: Dict[str, Any],
        referral: Dict[str, Any],
        contact_names: Dict[str, str],
        phone_number_id: Optional[str],
        business_account_id: Optional[str],
    ) -> str:
        event_key = _event_key_for_message(message, referral)
        try:
            return cls._process_message(
                db=db,
                entry=entry,
                value=value,
                message=message,
                referral=referral,
                contact_names=contact_names,
                phone_number_id=phone_number_id,
                business_account_id=business_account_id,
                event_key=event_key,
            )
        except Exception as exc:
            db.rollback()
            logger.error(
                "Failed to process WhatsApp Ad message event %s: %s",
                event_key,
                exc,
                exc_info=True,
            )
            cls._record_failed_event(
                db=db,
                event_key=event_key,
                message=message,
                value=value,
                business_account_id=business_account_id,
                error=str(exc),
            )
            return "failed"

    @classmethod
    def _process_message(
        cls,
        db: Session,
        entry: Dict[str, Any],
        value: Dict[str, Any],
        message: Dict[str, Any],
        referral: Dict[str, Any],
        contact_names: Dict[str, str],
        phone_number_id: Optional[str],
        business_account_id: Optional[str],
        event_key: str,
    ) -> str:
        wamid = str(message.get("id") or "").strip() or None

        existing_event = (
            db.query(WhatsAppWebhookEvent)
            .filter(WhatsAppWebhookEvent.event_key == event_key)
            .first()
        )
        if existing_event:
            logger.info("Duplicate WhatsApp Ad webhook event ignored: %s", event_key)
            return "duplicates"

        ctwa_clid = str(referral.get("ctwa_clid") or "").strip() or None
        if ctwa_clid:
            existing_attribution = (
                db.query(WhatsAppAdAttribution)
                .filter(WhatsAppAdAttribution.ctwa_clid == ctwa_clid)
                .first()
            )
            if existing_attribution:
                cls._create_event(
                    db=db,
                    event_key=event_key,
                    event_type="MESSAGE",
                    wamid=wamid,
                    phone_number_id=phone_number_id,
                    business_account_id=business_account_id,
                    sender_phone=str(message.get("from") or ""),
                    status="SKIPPED_DUPLICATE",
                    payload=cls._event_payload(entry, value, message),
                    lead_id=existing_attribution.lead_id,
                    attribution_id=existing_attribution.id,
                    error="Same ctwa_clid was already captured.",
                )
                db.commit()
                logger.info(
                    "Duplicate CTWA click %s ignored for Lead #%s.",
                    ctwa_clid,
                    existing_attribution.lead_id,
                )
                return "duplicates"

        phone = str(message.get("from") or "").strip()
        contact_name = contact_names.get(phone) or None
        message_text = extract_message_text(message)
        message_timestamp = _safe_epoch_to_ist(message.get("timestamp")) or get_ist_now()
        source_type = str(referral.get("source_type") or "").strip() or None
        source_id = str(referral.get("source_id") or "").strip() or None
        source_url = str(referral.get("source_url") or "").strip() or None
        headline = str(referral.get("headline") or "").strip() or None
        ad_body = str(referral.get("body") or "").strip() or None
        media_type, media_url = _referral_media(referral)
        welcome_message = str(referral.get("welcome_message") or "").strip() or None

        enquiry_data = {
            "name": contact_name,
            "phone": phone,
            "whatsapp_number": phone,
            "source": SOURCE,
            "requirement_notes": message_text,
            "campaign_name": None,  # not present in referral payload
            "rating": "Warm",
            "priority": "MEDIUM",
        }

        # Existing re-inquiry rules do all the dedupe / merge / history work.
        # commit=False keeps lead creation and attribution atomic.
        lead, is_reinquiry, enquiry_record = ReInquiryService.register_enquiry(
            db=db,
            enquiry_data=enquiry_data,
            creator_emp_id=None,
            creator_name=SOURCE_LABEL,
            commit=False,
        )
        db.flush()

        # Apply the existing assignment configuration to the new/unassigned
        # lead. No global scheduler run is triggered for a single enquiry.
        assignee = assign_lead_immediately(
            db,
            lead,
            notes=(
                "Auto-assigned immediately on WhatsApp Ad enquiry using "
                "the configured assignment strategy."
            ),
        )

        resolution_status = "PENDING" if source_id else "SKIPPED"
        attribution = WhatsAppAdAttribution(
            lead_id=lead.id,
            lead_enquiry_id=getattr(enquiry_record, "id", None),
            wamid=wamid,
            phone=phone,
            contact_name=contact_name,
            message_text=message_text,
            message_type=(message.get("type") or "text"),
            message_timestamp=message_timestamp,
            channel="WHATSAPP",
            business_account_id=business_account_id,
            phone_number_id=phone_number_id,
            ctwa_clid=ctwa_clid,
            source_type=source_type,
            source_id=source_id,
            source_url=source_url,
            headline=headline,
            ad_body=ad_body,
            media_type=media_type,
            media_url=media_url,
            welcome_message=welcome_message,
            resolution_status=resolution_status,
            resolution_error=(
                None if source_id else "Referral did not include an ad/source ID."
            ),
            raw_referral=_json_dumps(referral),
        )
        db.add(attribution)
        db.flush()

        cls._create_event(
            db=db,
            event_key=event_key,
            event_type="MESSAGE",
            wamid=wamid,
            phone_number_id=phone_number_id,
            business_account_id=business_account_id,
            sender_phone=phone,
            status="PROCESSED",
            payload=cls._event_payload(entry, value, message),
            lead_id=lead.id,
            attribution_id=attribution.id,
        )

        db.commit()

        logger.info(
            "Captured WhatsApp Ad %s for Lead #%s (%s, ad=%s, campaign=%s, assigned=%s).",
            "re-inquiry" if is_reinquiry else "lead",
            lead.id,
            phone,
            source_id,
            attribution.campaign_id,
            assignee.name if assignee else "unassigned",
        )
        return "processed"

    @staticmethod
    def _event_payload(
        entry: Dict[str, Any], value: Dict[str, Any], message: Dict[str, Any]
    ) -> str:
        return _json_dumps(
            {
                "business_account_id": entry.get("id"),
                "metadata": value.get("metadata"),
                "contacts": value.get("contacts"),
                "message": message,
            }
        )

    @staticmethod
    def _create_event(
        db: Session,
        event_key: str,
        event_type: str,
        wamid: Optional[str],
        phone_number_id: Optional[str],
        business_account_id: Optional[str],
        sender_phone: Optional[str],
        status: str,
        payload: Optional[str],
        lead_id: Optional[int] = None,
        attribution_id: Optional[int] = None,
        error: Optional[str] = None,
    ) -> WhatsAppWebhookEvent:
        event = WhatsAppWebhookEvent(
            event_key=event_key,
            event_type=event_type,
            wamid=wamid,
            phone_number_id=phone_number_id,
            business_account_id=business_account_id,
            sender_phone=sender_phone,
            status=status,
            lead_id=lead_id,
            attribution_id=attribution_id,
            error=error[:4000] if error else None,
            payload=payload,
            received_at=get_ist_now(),
            processed_at=get_ist_now(),
        )
        db.add(event)
        return event

    @classmethod
    def _record_failed_event(
        cls,
        db: Session,
        event_key: str,
        message: Dict[str, Any],
        value: Dict[str, Any],
        business_account_id: Optional[str],
        error: str,
    ) -> None:
        try:
            metadata = value.get("metadata") or {}
            event = WhatsAppWebhookEvent(
                event_key=event_key,
                event_type="MESSAGE",
                wamid=str(message.get("id") or "") or None,
                phone_number_id=metadata.get("phone_number_id"),
                business_account_id=business_account_id,
                sender_phone=str(message.get("from") or "") or None,
                status="FAILED",
                error=(error or "")[:4000],
                payload=_json_dumps(
                    {"metadata": metadata, "message": message}
                ),
                received_at=get_ist_now(),
                processed_at=get_ist_now(),
            )
            db.add(event)
            db.commit()
        except IntegrityError:
            db.rollback()
        except Exception:
            db.rollback()
            logger.error("Could not persist failed WhatsApp Ad webhook event.", exc_info=True)

    # ------------------------------------------------------------------
    # Marketing API campaign/ad name resolution
    # ------------------------------------------------------------------
    @staticmethod
    def resolve_attribution(db: Session, attribution: WhatsAppAdAttribution) -> bool:
        """
        Resolve ad name + campaign id/name for one attribution.

        Campaign/ad names are not part of the WhatsApp referral payload; they
        require the Marketing API and an `ads_read` token. Failures stay
        non-fatal and can be retried later.
        """
        if attribution is None:
            return False
        attribution_id = attribution.id
        if attribution.resolution_status == "RESOLVED" and attribution.ad_name:
            return True

        ad_id = (attribution.source_id or "").strip()
        if not ad_id:
            attribution.resolution_status = "SKIPPED"
            attribution.resolution_error = "Referral did not include an ad/source ID."
            attribution.resolved_at = get_ist_now()
            db.commit()
            return False

        token = WhatsAppAdConfig.get_marketing_access_token()
        if not token:
            attribution.resolution_status = "PENDING"
            attribution.resolution_error = (
                "Marketing API token not configured "
                "(set META_MARKETING_ACCESS_TOKEN)."
            )
            db.commit()
            return False

        url = WhatsAppAdConfig.get_graph_url(ad_id)
        try:
            response = httpx.get(
                url,
                params={
                    "fields": "id,name,campaign{id,name}",
                    "access_token": token,
                },
                timeout=8.0,
            )
            if response.status_code >= 400:
                attribution.resolution_status = "FAILED"
                attribution.resolution_error = (
                    f"Meta Marketing API HTTP {response.status_code}: "
                    f"{response.text[:1000]}"
                )
                attribution.resolved_at = get_ist_now()
                db.commit()
                logger.warning(
                    "Could not resolve ad %s (HTTP %s).",
                    ad_id,
                    response.status_code,
                )
                return False

            data = response.json() or {}
            campaign = data.get("campaign") or {}
            attribution.ad_name = (data.get("name") or "").strip() or attribution.ad_name
            attribution.campaign_id = (
                str(campaign.get("id") or "").strip() or attribution.campaign_id
            )
            attribution.campaign_name = (
                (campaign.get("name") or "").strip() or attribution.campaign_name
            )
            attribution.resolution_status = "RESOLVED"
            attribution.resolution_error = None
            attribution.resolved_at = get_ist_now()
            db.commit()
            logger.info(
                "Resolved WhatsApp Ad %s -> ad '%s', campaign %s '%s'.",
                ad_id,
                attribution.ad_name,
                attribution.campaign_id,
                attribution.campaign_name,
            )
            return True
        except Exception as exc:
            db.rollback()
            attribution = (
                db.query(WhatsAppAdAttribution)
                .filter(WhatsAppAdAttribution.id == attribution_id)
                .first()
            )
            if attribution is not None:
                attribution.resolution_status = "FAILED"
                attribution.resolution_error = f"Marketing API request failed: {exc}"[:4000]
                attribution.resolved_at = get_ist_now()
                db.commit()
            logger.warning("Marketing API resolution failed for ad %s: %s", ad_id, exc)
            return False

    @classmethod
    def resolve_pending_attributions(cls, db: Session, limit: int = 25) -> int:
        if not WhatsAppAdConfig.marketing_resolution_configured():
            return 0
        rows = (
            db.query(WhatsAppAdAttribution)
            .filter(
                WhatsAppAdAttribution.resolution_status == "PENDING",
                WhatsAppAdAttribution.source_id.isnot(None),
                WhatsAppAdAttribution.source_id != "",
            )
            .order_by(WhatsAppAdAttribution.created_at.asc())
            .limit(limit)
            .all()
        )
        resolved = 0
        for row in rows:
            if cls.resolve_attribution(db, row):
                resolved += 1
        return resolved


async def start_attribution_resolver(interval_seconds: int = 300):
    """Background retry loop for campaign/ad name resolution."""
    logger.info(
        "Starting WhatsApp Ad attribution resolver (interval: %ss).",
        interval_seconds,
    )
    # Give the app time to finish startup before the first pass.
    await asyncio.sleep(min(30, max(5, interval_seconds)))
    while True:
        try:
            if WhatsAppAdConfig.marketing_resolution_configured():
                db = SessionLocal()
                try:
                    resolved = WhatsAppAdLeadService.resolve_pending_attributions(db)
                    if resolved:
                        logger.info(
                            "Resolved attribution for %s WhatsApp Ad lead(s).",
                            resolved,
                        )
                finally:
                    db.close()
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            logger.info("WhatsApp Ad attribution resolver cancelled.")
            break
        except Exception as exc:
            logger.error(
                "Error in WhatsApp Ad attribution resolver: %s", exc, exc_info=True
            )
            await asyncio.sleep(interval_seconds)
