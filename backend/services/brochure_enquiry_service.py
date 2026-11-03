import hashlib
import logging
import re
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.brochure_enquiry import BrochureEnquiry
from models.customer import Customer
from models.lead import Lead
from utils.phone import (
    find_existing_customer_by_phone,
    find_existing_lead_by_phone,
    normalize_email,
    normalize_phone,
)
from utils.timezone import get_ist_now

logger = logging.getLogger("brochure_enquiry_service")

BROCHURE_TYPE_TOKENS = (
    "brochure",
    "catalogue",
    "catalog",
    "prospectus",
    "datasheet",
    "data sheet",
    "download",
    "document",
    "pdf",
)

BROCHURE_TYPE_FIELDS = (
    "enquiry_type",
    "enquiryType",
    "form_type",
    "formType",
    "form_name",
    "formName",
    "request_type",
    "requestType",
    "lead_type",
    "leadType",
    "type",
)

BROCHURE_NAME_FIELDS = (
    "brochure_name",
    "brochureName",
    "brochure",
    "document_name",
    "documentName",
)

PRODUCT_NAME_FIELDS = (
    "product_name",
    "productName",
    "product",
)

PRODUCT_ID_FIELDS = (
    "product_id",
    "productId",
)

BROCHURE_ID_FIELDS = (
    "brochure_id",
    "brochureId",
)

COPYABLE_FIELDS = (
    "name",
    "phone",
    "whatsapp_number",
    "country_code",
    "email",
    "product_name",
    "product_id",
    "brochure_name",
    "brochure_id",
    "form_type",
    "website_id",
    "website_name",
    "landing_page",
    "campaign",
    "message",
)


def _first_value(*values: Any) -> Optional[str]:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _canonical_text(value: Optional[str]) -> str:
    if not value:
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"\.(pdf|docx?|pptx?|xlsx?|zip|jpe?g|png)$", "", text)
    text = re.sub(r"[\s_\-]+", " ", text)
    return text.strip()


def _value_is_brochure_marker(value: Optional[str]) -> bool:
    if not value:
        return False
    lowered = str(value).strip().lower()
    return any(token in lowered for token in BROCHURE_TYPE_TOKENS)


def is_brochure_submission(payload: Any) -> bool:
    """
    Explicitly detect a brochure download form.

    Contact details (name/phone/email) are never used as signals. A submission
    must either identify itself as a brochure/download form, or carry explicit
    brochure/product fields.
    """
    for field in BROCHURE_TYPE_FIELDS:
        if _value_is_brochure_marker(getattr(payload, field, None)):
            return True

    for field in BROCHURE_NAME_FIELDS:
        if _first_value(getattr(payload, field, None)):
            return True

    for field in PRODUCT_NAME_FIELDS + PRODUCT_ID_FIELDS + BROCHURE_ID_FIELDS:
        if _first_value(getattr(payload, field, None)):
            return True

    return False


def resolve_display_phone(raw_phone: Optional[str], raw_code: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Preserve the number exactly as submitted by the website while ensuring the
    country code is present for display when the form sends it separately.
    """
    raw = (raw_phone or "").strip()
    code = (raw_code or "").strip()
    if not raw:
        return None, None

    raw_digits = re.sub(r"\D", "", raw)
    code_digits = re.sub(r"\D", "", code)
    country_code = f"+{code_digits}" if code_digits else None

    if raw.startswith("+"):
        # Keep existing international format. If the form also supplied a
        # country code, preserve that separately for WhatsApp deep links.
        return raw, country_code or (f"+{raw_digits}" if raw_digits else None)

    if code_digits:
        if raw_digits.startswith(code_digits) and len(raw_digits) > len(code_digits):
            return f"+{raw_digits}", country_code
        return f"+{code_digits} {raw}", country_code

    return raw, None


def build_dedupe_key(name: Optional[str], phone: Optional[str], email: Optional[str], product: Optional[str], brochure: Optional[str]) -> str:
    """
    One record per contact + product/brochure. Repeated submissions update the
    existing row instead of inserting duplicates.
    """
    phone_norm = normalize_phone(phone)
    email_norm = normalize_email(email)
    item = _canonical_text(brochure) or _canonical_text(product)

    if phone_norm and len(phone_norm) >= 7:
        identity = f"phone:{phone_norm}"
    elif email_norm:
        identity = f"email:{email_norm}"
    else:
        identity = f"name:{_canonical_text(name)}"

    return hashlib.sha256(f"{identity}|item:{item}".encode("utf-8")).hexdigest()


def normalize_followup_status(value: Optional[str]) -> str:
    status = (value or "").strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "NEW": "PENDING",
        "PENDING": "PENDING",
        "FOLLOW_UP": "FOLLOW_UP",
        "FOLLOWUP": "FOLLOW_UP",
        "INTERESTED": "FOLLOW_UP",
        "CONTACTED": "CONTACTED",
        "CONVERTED": "CONVERTED",
        "WON": "CONVERTED",
        "NOT_INTERESTED": "NOT_INTERESTED",
        "LOST": "NOT_INTERESTED",
    }
    if status not in aliases:
        raise ValueError(
            "Invalid follow-up status. Use PENDING, FOLLOW_UP, CONTACTED, CONVERTED or NOT_INTERESTED."
        )
    return aliases[status]


class BrochureEnquiryService:
    @staticmethod
    def extract_payload_data(payload: Any) -> Dict[str, Any]:
        first_name = _first_value(getattr(payload, "firstName", None), getattr(payload, "first_name", None))
        last_name = _first_value(getattr(payload, "lastName", None), getattr(payload, "last_name", None))
        full_name = _first_value(getattr(payload, "name", None))
        if not full_name:
            full_name = _first_value(f"{first_name or ''} {last_name or ''}".strip())

        raw_phone = _first_value(getattr(payload, "phone", None))
        raw_whatsapp = _first_value(
            getattr(payload, "whatsapp_number", None),
            getattr(payload, "whatsapp", None),
            getattr(payload, "whatsappNumber", None),
        )
        raw_code = _first_value(
            getattr(payload, "countryCode", None),
            getattr(payload, "country_code", None),
        )

        primary_raw = raw_phone or raw_whatsapp
        whatsapp_raw = raw_whatsapp or raw_phone
        phone_display, country_code = resolve_display_phone(primary_raw, raw_code)
        whatsapp_display, whatsapp_code = resolve_display_phone(whatsapp_raw, raw_code)
        country_code = country_code or whatsapp_code

        product_name = _first_value(*[getattr(payload, f, None) for f in PRODUCT_NAME_FIELDS])
        product_id = _first_value(*[getattr(payload, f, None) for f in PRODUCT_ID_FIELDS])
        brochure_name = _first_value(*[getattr(payload, f, None) for f in BROCHURE_NAME_FIELDS])
        brochure_id = _first_value(*[getattr(payload, f, None) for f in BROCHURE_ID_FIELDS])

        form_type = _first_value(*[getattr(payload, f, None) for f in BROCHURE_TYPE_FIELDS])

        email = _first_value(getattr(payload, "email", None))
        if email:
            email = email.lower()

        website_id = _first_value(getattr(payload, "website_id", None))
        website_name = _first_value(getattr(payload, "website_name", None))
        landing_page = _first_value(getattr(payload, "landing_page", None), getattr(payload, "page_url", None))
        campaign = _first_value(getattr(payload, "campaign", None), getattr(payload, "campaign_name", None))
        message = _first_value(getattr(payload, "message", None))

        now = get_ist_now()
        return {
            "name": full_name or "Website Visitor",
            "phone": phone_display or whatsapp_display or "",
            "whatsapp_number": whatsapp_display or phone_display or "",
            "country_code": country_code,
            "email": email,
            "product_name": product_name,
            "product_id": product_id,
            "brochure_name": brochure_name,
            "brochure_id": brochure_id,
            "source": "WEBSITE_BROCHURE",
            "form_type": form_type,
            "website_id": website_id,
            "website_name": website_name,
            "landing_page": landing_page,
            "campaign": campaign,
            "message": message,
            "download_at": now,
            "last_submitted_at": now,
            "submission_count": 1,
            "followup_status": "PENDING",
        }

    @staticmethod
    def _find_existing_links(db: Session, phone: Optional[str], email: Optional[str]) -> Dict[str, Any]:
        lead = find_existing_lead_by_phone(db, phone)
        customer = find_existing_customer_by_phone(db, phone)

        if not lead and email:
            lead = (
                db.query(Lead)
                .filter(func.lower(Lead.email) == email.strip().lower())
                .order_by(Lead.id.desc())
                .first()
            )
        if not customer and email:
            customer = (
                db.query(Customer)
                .filter(func.lower(Customer.email) == email.strip().lower())
                .order_by(Customer.id.desc())
                .first()
            )

        links: Dict[str, Any] = {}
        if lead:
            links["lead_id"] = lead.id
            if lead.assigned_to:
                links["assigned_to"] = lead.assigned_to
                links["assigned_at"] = get_ist_now()
            if not customer and lead.customer:
                customer = lead.customer
        if customer:
            links["customer_id"] = customer.id
            if not lead and customer.converted_from_lead:
                links["lead_id"] = customer.converted_from_lead

        return links

    @staticmethod
    def _merge_existing(existing: BrochureEnquiry, data: Dict[str, Any]) -> BrochureEnquiry:
        now = data.get("last_submitted_at") or get_ist_now()
        existing.download_at = data.get("download_at") or now
        existing.last_submitted_at = now
        existing.submission_count = (existing.submission_count or 1) + 1

        for field in COPYABLE_FIELDS:
            new_value = data.get(field)
            if new_value not in (None, ""):
                setattr(existing, field, new_value)

        # Fill optional links/ownership only when they are still empty.
        for field in ("lead_id", "customer_id", "assigned_to"):
            if not getattr(existing, field) and data.get(field):
                setattr(existing, field, data[field])
                if field == "assigned_to":
                    existing.assigned_at = data.get("assigned_at") or now

        existing.updated_at = now
        return existing

    @staticmethod
    def record_submission(db: Session, payload: Any) -> Tuple[BrochureEnquiry, bool]:
        data = BrochureEnquiryService.extract_payload_data(payload)
        links = BrochureEnquiryService._find_existing_links(db, data.get("phone"), data.get("email"))
        data.update({k: v for k, v in links.items() if v is not None})

        dedupe_key = build_dedupe_key(
            data.get("name"),
            data.get("phone"),
            data.get("email"),
            data.get("product_name"),
            data.get("brochure_name"),
        )

        existing = db.query(BrochureEnquiry).filter(BrochureEnquiry.dedupe_key == dedupe_key).first()
        if existing:
            BrochureEnquiryService._merge_existing(existing, data)
            db.commit()
            db.refresh(existing)
            logger.info(
                "Repeated brochure submission updated enquiry #%s (%s), submission_count=%s.",
                existing.id,
                existing.name,
                existing.submission_count,
            )
            return existing, True

        record = BrochureEnquiry(dedupe_key=dedupe_key, **data)
        db.add(record)
        try:
            db.commit()
            db.refresh(record)
            logger.info(
                "Brochure enquiry #%s created for %s (%s).",
                record.id,
                record.name,
                record.brochure_name or record.product_name or "Brochure",
            )
            return record, False
        except IntegrityError:
            # A simultaneous double-submit can race the unique key. Merge into
            # the row that won instead of returning an error to the website.
            db.rollback()
            existing = db.query(BrochureEnquiry).filter(BrochureEnquiry.dedupe_key == dedupe_key).first()
            if not existing:
                raise
            BrochureEnquiryService._merge_existing(existing, data)
            db.commit()
            db.refresh(existing)
            return existing, True

    @staticmethod
    def to_out_dict(record: BrochureEnquiry) -> Dict[str, Any]:
        return {
            "id": record.id,
            "name": record.name,
            "phone": record.phone,
            "whatsapp_number": record.whatsapp_number,
            "country_code": record.country_code,
            "email": record.email,
            "product_name": record.product_name,
            "product_id": record.product_id,
            "brochure_name": record.brochure_name,
            "brochure_id": record.brochure_id,
            "download_at": record.download_at,
            "last_submitted_at": record.last_submitted_at,
            "submission_count": record.submission_count,
            "source": record.source,
            "form_type": record.form_type,
            "website_id": record.website_id,
            "website_name": record.website_name,
            "landing_page": record.landing_page,
            "campaign": record.campaign,
            "message": record.message,
            "assigned_to": record.assigned_to,
            "assigned_employee_name": record.assigned_employee.name if record.assigned_employee else None,
            "followup_status": record.followup_status,
            "next_followup_date": record.next_followup_date,
            "next_followup_time": record.next_followup_time,
            "notes": record.notes,
            "last_contacted_at": record.last_contacted_at,
            "converted_at": record.converted_at,
            "lead_id": record.lead_id,
            "customer_id": record.customer_id,
            "linked_lead_name": record.lead.name if record.lead else None,
            "linked_customer_name": record.customer.contact_name if record.customer else None,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
