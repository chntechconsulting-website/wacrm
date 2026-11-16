"""Helpers for linking existing quotations to CRM leads.

The link is deliberately additive. It writes the existing ``quotations.lead_id``
foreign key, refreshes the quotation's customer snapshot from the lead, and
mirrors the quotation reference back onto the lead. It never creates or
deletes a quotation/lead and never rewrites quotation financial data.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from models.activity import LeadActivity
from models.audit_log import AuditLog
from models.customer import Customer
from models.lead import Lead
from models.quotation import Quotation
from services.activity_visibility_service import user_activity_department


def normalize_phone(value: Any) -> str:
    """Return the comparable 10-digit form of an Indian phone number."""
    digits = re.sub(r"\D", "", str(value or ""))
    return digits[-10:] if len(digits) > 10 else digits


def normalize_email(value: Any) -> str:
    return str(value or "").strip().lower()


def normalize_company(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def lead_display_name(lead: Lead) -> str:
    name = (lead.name or "").strip()
    if name:
        return name
    return f"{lead.first_name or ''} {lead.last_name or ''}".strip() or "Unnamed Lead"


def serialize_lead_brief(lead: Optional[Lead]) -> Optional[Dict[str, Any]]:
    if not lead:
        return None
    return {
        "id": lead.id,
        "name": lead_display_name(lead),
        "company": lead.company or "",
        "phone": lead.phone or "",
        "email": lead.email or "",
        "status": lead.status or "",
        "productCategory": getattr(lead, "product_category", None) or "UNCLASSIFIED",
    }


def match_reasons(quotation: Quotation, lead: Lead) -> List[str]:
    """Return the fields that connect a quotation to a lead.

    Mobile, email and company are the only supported automatic signals. The
    frontend treats any match as a suggestion and always requires a manual
    confirmation before linking.
    """
    reasons: List[str] = []

    quotation_phone = normalize_phone(quotation.phone)
    lead_phones = {
        normalize_phone(lead.phone),
        normalize_phone(getattr(lead, "whatsapp_number", None)),
    }
    lead_phones.discard("")
    if quotation_phone and quotation_phone in lead_phones:
        reasons.append("Mobile number")

    quotation_email = normalize_email(quotation.email)
    if quotation_email and quotation_email == normalize_email(lead.email):
        reasons.append("Email")

    quotation_company = normalize_company(quotation.company_name)
    if quotation_company and quotation_company == normalize_company(lead.company):
        reasons.append("Company name")

    return reasons


def _match_score(reasons: Iterable[str]) -> int:
    scores = {"Mobile number": 100, "Email": 90, "Company name": 80}
    return sum(scores.get(reason, 0) for reason in reasons)


def find_matching_leads(
    db: Session,
    quotation: Quotation,
    base_query,
    search: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Find leads for the quotation picker.

    With a search term the visible CRM leads are searched by name, company,
    mobile and email. Without one, the quotation's own mobile/email/company are
    used to surface potential matches. Every result carries its match reasons
    so the user can see why it was suggested.
    """
    query = base_query
    term = (search or "").strip()

    if term:
        like = f"%{term}%"
        conditions = [
            Lead.name.ilike(like),
            Lead.first_name.ilike(like),
            Lead.last_name.ilike(like),
            Lead.phone.ilike(like),
            Lead.whatsapp_number.ilike(like),
            Lead.email.ilike(like),
            Lead.company.ilike(like),
        ]
        digits = "".join(filter(str.isdigit, term))
        if len(digits) >= 4:
            # Phone numbers may be stored with spaces, dashes or a +91 prefix;
            # the last four digits are a safe SQL pre-filter before exact
            # normalization/scoring in Python.
            conditions.append(Lead.phone.ilike(f"%{digits[-4:]}%"))
            conditions.append(Lead.whatsapp_number.ilike(f"%{digits[-4:]}%"))
        query = query.filter(or_(*conditions))
    else:
        conditions = []
        quotation_phone = normalize_phone(quotation.phone)
        if len(quotation_phone) >= 7:
            conditions.append(Lead.phone.ilike(f"%{quotation_phone[-4:]}%"))
            conditions.append(Lead.whatsapp_number.ilike(f"%{quotation_phone[-4:]}%"))

        quotation_email = normalize_email(quotation.email)
        if quotation_email:
            conditions.append(Lead.email.ilike(quotation_email))

        quotation_company = (quotation.company_name or "").strip()
        if quotation_company:
            conditions.append(Lead.company.ilike(quotation_company))

        if not conditions:
            return []
        query = query.filter(or_(*conditions))

    # Fetch a slightly wider window so scoring can rank exact matches before
    # the caller's page limit is applied.
    candidates = (
        query.order_by(Lead.created_at.desc(), Lead.id.desc())
        .limit(max(limit * 5, 50))
        .all()
    )

    results: List[Dict[str, Any]] = []
    for lead in candidates:
        reasons = match_reasons(quotation, lead)
        results.append(
            {
                "lead": serialize_lead_brief(lead),
                "matchReasons": reasons,
                "matchScore": _match_score(reasons),
            }
        )

    results.sort(
        key=lambda item: (
            -item["matchScore"],
            (item["lead"] or {}).get("name", "").lower(),
            (item["lead"] or {}).get("id", 0),
        )
    )
    return results[:limit]


def _find_customer_for_lead(db: Session, lead: Lead) -> Optional[Customer]:
    customer = getattr(lead, "customer", None)
    if customer:
        return customer
    customer = (
        db.query(Customer)
        .filter(Customer.converted_from_lead == lead.id)
        .first()
    )
    if customer:
        return customer
    if lead.phone:
        return db.query(Customer).filter(Customer.phone == lead.phone).first()
    return None


def _lead_address(lead: Lead) -> str:
    address = (lead.location or "").strip()
    if address:
        return address
    return ", ".join(filter(None, [lead.city, lead.state])).strip(", ")


def link_quotation_to_lead(
    db: Session,
    quotation: Quotation,
    lead: Lead,
    actor_user=None,
    actor_employee=None,
) -> Dict[str, Any]:
    """Link one quotation to one lead and synchronize the safe fields.

    The quotation's id, number, amount, status, issue date and line items are
    never changed. Contact fields are copied from the lead only when the lead
    actually has a value, so an empty lead field can never erase quotation
    data. The lead's existing contact data is never overwritten.
    """
    if quotation.lead_id and quotation.lead_id != lead.id:
        raise ValueError(
            f"Quotation #{quotation.doc_number} is already linked to Lead #{quotation.lead_id}."
        )

    already_linked = quotation.lead_id == lead.id
    changed_fields: List[str] = []

    def sync_quotation_field(attribute: str, value: Optional[str]) -> None:
        cleaned = (value or "").strip()
        if cleaned and getattr(quotation, attribute) != cleaned:
            setattr(quotation, attribute, cleaned)
            changed_fields.append(attribute)

    # The lead owns the current CRM contact details; the quotation keeps a
    # snapshot for the printed document. Empty lead fields are ignored.
    sync_quotation_field("customer_name", lead_display_name(lead))
    sync_quotation_field("company_name", lead.company)
    sync_quotation_field("phone", lead.phone)
    sync_quotation_field("email", lead.email)
    sync_quotation_field("address", _lead_address(lead))

    customer = _find_customer_for_lead(db, lead)
    if customer and not quotation.customer_id:
        quotation.customer_id = customer.id
        changed_fields.append("customer_id")

    if quotation.lead_id != lead.id:
        quotation.lead_id = lead.id
        changed_fields.append("lead_id")

    # Mirror the linked quotation onto the lead's existing official-quotation
    # fields. Only issued quotations are treated as the official reference;
    # drafts stay visible in the linked-documents list without replacing an
    # already-issued reference.
    quotation_status = (quotation.status or "").lower()
    if (quotation.doc_type or "").lower() == "quotation" and quotation_status == "issued":
        reference_changed = False
        if lead.quotetask_quotation_id != str(quotation.id):
            lead.quotetask_quotation_id = str(quotation.id)
            reference_changed = True
        if lead.quotetask_quotation_number != quotation.doc_number:
            lead.quotetask_quotation_number = quotation.doc_number
            reference_changed = True
        if lead.quotetask_quotation_status != quotation.status:
            lead.quotetask_quotation_status = quotation.status
            reference_changed = True
        amount = float(quotation.grand_total or 0.0)
        # A zero-valued quotation must not wipe a previously synced amount.
        if amount > 0 and lead.quotetask_quotation_amount != amount:
            lead.quotetask_quotation_amount = amount
            reference_changed = True
        if quotation.pdf_url and lead.quotetask_quotation_url != quotation.pdf_url:
            lead.quotetask_quotation_url = quotation.pdf_url
            reference_changed = True
        if reference_changed:
            lead.quotetask_synced_at = datetime.utcnow()

    if not already_linked:
        employee_id = actor_employee.id if actor_employee else None
        activity = LeadActivity(
            lead_id=lead.id,
            employee_id=employee_id,
            performed_by=employee_id,
            activity_type="PROPOSAL_LINKED",
            related_entity_type="QUOTATION",
            related_entity_id=quotation.id,
            department=user_activity_department(actor_user, db),
            description=(
                f"Linked existing {quotation.doc_type.capitalize()} "
                f"#{quotation.doc_number} "
                f"({(quotation.product_category or 'WAHRMS').upper()}) "
                f"worth Rs. {float(quotation.grand_total or 0.0):,.2f} to this lead."
            ),
        )
        db.add(activity)

        db.add(
            AuditLog(
                user_id=actor_user.id if actor_user else None,
                username=actor_user.username if actor_user else "SYSTEM",
                action="QUOTATION_LINKED",
                entity_type="QUOTATION",
                entity_id=str(quotation.id),
                details=(
                    f"Linked Quotation #{quotation.doc_number} to Lead #{lead.id} "
                    f"({lead_display_name(lead)}). Customer snapshot synchronized; "
                    f"amount/status/issue date preserved."
                ),
            )
        )

    db.commit()
    db.refresh(quotation)
    db.refresh(lead)

    return {
        "alreadyLinked": already_linked,
        "changedFields": changed_fields,
        "quotation": quotation,
        "lead": lead,
    }
