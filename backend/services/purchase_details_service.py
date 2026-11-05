"""Support-facing purchase detail projection.

The Support team must receive the exact package, plan, duration and add-ons
that Sales handed over, without any internal Sales negotiation data. The
projection in this module is read-only and is built from records that already
exist in the CRM:

* ``support_handoffs.purchase_snapshot`` - immutable snapshot written at WON.
* ``quotations`` (proforma/invoice/quotation) - historical line-item prices.
* ``finance_handoffs`` - issued invoice reference.

No customer, quotation, package or add-on record is created here. When a
snapshot exists it always wins for package/plan/quantity/pricing so later
catalogue or document changes cannot rewrite the purchase the customer made.
"""

from __future__ import annotations

import calendar
import json
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from models.quotation import Quotation
from models.workflow import FinanceHandoff, SupportHandoff
from services.billing_catalog import extract_plan_code, get_default_bundle

PACKAGE_LABELS: Dict[str, str] = {
    "hr_atm": "HR + ATM",
    "hr_payroll": "HR + Payroll",
    "hr_atm_payroll": "HR + ATM + Payroll",
    "bio_payroll": "Biometric + Payroll",
    "bio_standard": "Biometric Standard (MB160)",
    "bio_atm": "WA ATM Biometric Hardware",
    "bio_enterprise": "Biometric Multi-Location Suite",
}

PLAN_LABELS: Dict[str, str] = {
    "pro": "Pro",
    "business": "Business",
    "custom": "Custom",
}

_DURATION_RE = re.compile(r"Duration\s*:?\s*(\d+(?:\.\d+)?)", re.I)
_ONBOARDING_RE = re.compile(
    r"No\.?\s*Of\s*Onboardings?\s*:?\s*(\d+(?:\.\d+)?)", re.I
)
_PLAN_NAME_RE = re.compile(r"(?:^|\n)\s*Plan\s*:?\s*([^\n]+)", re.I)

_ONE_TIME_MARKERS = (
    "setup",
    "installation",
    "install",
    "deployment",
    "one-time",
    "one time",
    "training",
    "hardware",
    "device setup",
)


def _positive_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0 or not number.is_integer():
        return None
    return int(number)


def _number(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _as_mapping(value: Any) -> Dict[str, Any]:
    """Normalise a JSON column that may arrive as a dict or a raw string."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError):
            return {}
    return {}


def _as_list(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return [item for item in parsed if isinstance(item, dict)] if isinstance(parsed, list) else []
        except (TypeError, ValueError):
            return []
    return []


def _iso_date(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _package_block(code_or_name: Any) -> Dict[str, Any]:
    raw = str(code_or_name or "").strip()
    if not raw:
        return {"code": None, "name": None, "category": None}

    # Handover data may carry either the stable bundle code (hr_atm) or the
    # already-formatted display label (HR + ATM). Resolve the label to its
    # stable code without changing the stored handoff value.
    label_to_code = {
        label.strip().lower(): code for code, label in PACKAGE_LABELS.items()
    }
    normalized = raw.lower().replace(" ", "_").replace("-", "_")
    code = label_to_code.get(raw.strip().lower(), normalized)

    alphanumeric = re.sub(r"[^a-z0-9]", "", raw.lower())
    alphanumeric_to_code = {
        "hratm": "hr_atm",
        "hrpayroll": "hr_payroll",
        "hratmpayroll": "hr_atm_payroll",
        "biopayroll": "bio_payroll",
        "biometricpayroll": "bio_payroll",
        "biostandard": "bio_standard",
        "bioatm": "bio_atm",
        "bioenterprise": "bio_enterprise",
    }
    if not PACKAGE_LABELS.get(code) and alphanumeric in alphanumeric_to_code:
        code = alphanumeric_to_code[alphanumeric]

    name = PACKAGE_LABELS.get(code)
    if not name:
        bundle = get_default_bundle(code)
        if bundle:
            name = bundle.get("name")
    if not name:
        # A saved display label such as "HR + ATM" is already correct.
        name = raw
    return {"code": code, "name": name, "category": None}


def _plan_block(code: Any, explicit_name: Any = None) -> Dict[str, Any]:
    normalized = str(code or "").strip().lower()
    name = str(explicit_name or "").strip()
    if normalized in PLAN_LABELS:
        name = PLAN_LABELS[normalized]
    elif not name and normalized:
        name = normalized.replace("_", " ").title()
    return {"code": normalized or None, "name": name or None}


def _line_details(item: Dict[str, Any]) -> Dict[str, Any]:
    description = str(item.get("description") or item.get("name") or "")
    plan_code = str(item.get("planCode") or item.get("plan_code") or "").strip().lower()
    plan_name = str(item.get("planName") or item.get("plan_name") or "").strip()
    if not plan_code:
        try:
            plan_code = (extract_plan_code(item) or "").strip().lower()
        except Exception:
            plan_code = ""
    if not plan_name:
        match = _PLAN_NAME_RE.search(description)
        if match:
            plan_name = match.group(1).strip()

    duration = _positive_int(
        _first_present(item.get("durationMonths"), item.get("duration_months"))
    )
    if duration is None:
        match = _DURATION_RE.search(description)
        if match:
            duration = _positive_int(match.group(1))

    onboarding = _positive_int(
        _first_present(item.get("onboardingCount"), item.get("onboarding_count"))
    )
    if onboarding is None:
        match = _ONBOARDING_RE.search(description)
        if match:
            onboarding = _positive_int(match.group(1))

    return {
        "plan_code": plan_code,
        "plan_name": plan_name,
        "duration_months": duration,
        "onboarding_count": onboarding,
        "is_subscription": bool(
            item.get("isBundleDetail")
            or item.get("is_bundle_detail")
            or item.get("bundleId")
            or item.get("bundle")
            or plan_code
            or duration
            or onboarding
        ),
    }


def _subscription_values(
    line_items: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    """Pick the purchased subscription values from saved quotation lines."""
    candidates: List[Dict[str, Any]] = []
    for item in line_items:
        details = _line_details(item)
        if details["is_subscription"]:
            candidates.append({"item": item, "details": details})

    # Prefer a line that carries the structured subscription values.
    ordered = sorted(
        candidates,
        key=lambda entry: (
            1 if entry["details"]["onboarding_count"] else 0,
            1 if entry["details"]["duration_months"] else 0,
            1 if entry["details"]["plan_code"] else 0,
        ),
        reverse=True,
    )
    chosen = ordered[0] if ordered else None

    plan_code = chosen["details"]["plan_code"] if chosen else ""
    plan_name = chosen["details"]["plan_name"] if chosen else ""
    duration = chosen["details"]["duration_months"] if chosen else None
    onboarding = chosen["details"]["onboarding_count"] if chosen else None

    # Legacy documents may split values across more than one line.
    for entry in ordered:
        if not plan_code and entry["details"]["plan_code"]:
            plan_code = entry["details"]["plan_code"]
            plan_name = entry["details"]["plan_name"]
        if duration is None and entry["details"]["duration_months"]:
            duration = entry["details"]["duration_months"]
        if onboarding is None and entry["details"]["onboarding_count"]:
            onboarding = entry["details"]["onboarding_count"]

    return {
        "plan_code": plan_code,
        "plan_name": plan_name,
        "duration_months": duration,
        "onboarding_count": onboarding,
    }


def _normalise_addon(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    name = str(
        _first_present(
            item.get("name"),
            (str(item.get("description") or "").split("\n")[0] or "").strip(),
        )
        or ""
    ).strip()
    code = str(
        _first_present(
            item.get("addon_code"),
            item.get("addonCode"),
            item.get("item_code"),
            item.get("itemCode"),
        )
        or ""
    ).strip().lower()

    if not name and not code:
        return None

    quantity = _positive_int(_first_present(item.get("qty"), item.get("quantity")))
    unit_price = _number(
        _first_present(
            item.get("rate"),
            item.get("unit_price"),
            item.get("unitPrice"),
            item.get("price"),
        )
    )
    pricing_type = str(
        _first_present(item.get("pricing_type"), item.get("pricingType")) or ""
    ).strip().lower()
    billing_unit = str(
        _first_present(item.get("billing_unit"), item.get("billingUnit")) or ""
    ).strip().lower()

    text = f"{code} {name}".lower()
    if not pricing_type:
        if billing_unit == "employee":
            pricing_type = "per_employee"
        elif any(marker in text for marker in _ONE_TIME_MARKERS):
            pricing_type = "one_time"

    if pricing_type == "one_time":
        classification = "One-time setup"
    elif pricing_type == "per_employee":
        classification = "Recurring (per employee)"
    elif not pricing_type:
        # Legacy rows pre-date pricing metadata. Setup/installation/training
        # names are treated as one-time above; the remaining catalogue
        # add-ons are recurring subscriptions.
        classification = "Recurring"
    else:
        classification = "Not specified"

    line_total = _number(
        _first_present(
            item.get("subtotal"),
            item.get("line_total"),
            item.get("total"),
            item.get("amount"),
        )
    )

    return {
        "code": code or None,
        "name": name,
        "quantity": quantity,
        "unit_price": unit_price,
        "pricing_type": pricing_type or None,
        "billing_unit": billing_unit or None,
        "classification": classification,
        "line_total": line_total,
    }


def _addons_from_sources(
    handoff: SupportHandoff, line_items: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    summary = _as_list(handoff.addons_summary)
    raw_addons = [
        item
        for item in line_items
        if bool(
            item.get("is_addon")
            or item.get("isAddon")
            or item.get("addon_code")
            or item.get("addonCode")
        )
    ]
    source = summary if summary else raw_addons

    addons: List[Dict[str, Any]] = []
    seen = set()
    for item in source:
        normalized = _normalise_addon(item)
        if not normalized:
            continue
        key = (
            normalized["code"],
            normalized["name"],
            normalized["quantity"],
            normalized["unit_price"],
        )
        if key in seen:
            continue
        seen.add(key)
        addons.append(normalized)
    return addons


def _purchase_core(
    handoff: SupportHandoff, proforma: Optional[Quotation]
) -> Dict[str, Any]:
    line_items = _as_list(proforma.line_items) if proforma else []
    subscription = _subscription_values(line_items)

    package_raw = _first_present(
        handoff.selected_bundle,
        proforma.selected_bundle if proforma else None,
    )
    package = _package_block(package_raw)
    if proforma and proforma.product_category:
        package["category"] = proforma.product_category
    if handoff.product_category and not package["category"]:
        package["category"] = handoff.product_category

    employee_quantity = (
        subscription["onboarding_count"]
        or _positive_int(handoff.customer_users_count)
    )
    duration = subscription["duration_months"]

    start_source = handoff.won_at or (proforma.issue_date if proforma else None)
    start_date = start_source.date() if isinstance(start_source, datetime) else (
        start_source if isinstance(start_source, date) else None
    )
    end_date = _add_months(start_date, duration) if (start_date and duration) else None

    return {
        "package": package,
        "plan": _plan_block(subscription["plan_code"], subscription["plan_name"]),
        "employee_quantity": employee_quantity,
        "biometric_device_count": _positive_int(handoff.biometric_device_count) or 0,
        "subscription": {
            "duration_months": duration,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "start_basis": (
                "deal_won_date"
                if isinstance(start_source, datetime) and handoff.won_at
                else "proforma_issue_date"
                if start_date
                else None
            ),
        },
        "addons": _addons_from_sources(handoff, line_items),
        "purchase_amount": _number(
            _first_present(handoff.total_deal_amount, handoff.paid_amount)
        ),
    }


def _get_proforma(db: Session, handoff: SupportHandoff) -> Optional[Quotation]:
    if handoff.proforma_id:
        doc = db.query(Quotation).filter(Quotation.id == handoff.proforma_id).first()
        if doc:
            return doc

    doc_number = (handoff.proforma_number or "").strip()
    if doc_number:
        doc = db.query(Quotation).filter(Quotation.doc_number == doc_number).first()
        if doc:
            return doc

    if handoff.lead_id:
        doc = (
            db.query(Quotation)
            .filter(
                Quotation.lead_id == handoff.lead_id,
                Quotation.doc_type == "proforma",
                Quotation.status != "cancelled",
            )
            .order_by(Quotation.created_at.desc())
            .first()
        )
        if doc:
            return doc

    if handoff.customer_id:
        return (
            db.query(Quotation)
            .filter(
                Quotation.customer_id == handoff.customer_id,
                Quotation.doc_type.in_(["proforma", "quotation", "po"]),
                Quotation.status != "cancelled",
            )
            .order_by(Quotation.created_at.desc())
            .first()
        )
    return None


def _get_finance_handoff(
    db: Session, handoff: SupportHandoff
) -> Optional[FinanceHandoff]:
    if handoff.finance_handoff_id:
        doc = (
            db.query(FinanceHandoff)
            .filter(FinanceHandoff.id == handoff.finance_handoff_id)
            .first()
        )
        if doc:
            return doc
    if handoff.lead_id:
        return (
            db.query(FinanceHandoff)
            .filter(FinanceHandoff.lead_id == handoff.lead_id)
            .order_by(FinanceHandoff.created_at.desc())
            .first()
        )
    return None


def _doc_url(doc: Optional[Quotation], kind: str) -> Optional[str]:
    if doc and doc.pdf_url:
        return _normalize_doc_url(doc.pdf_url)
    if not doc or not doc.id:
        return None
    if kind == "proforma":
        return f"/api/integrations/waquote/proformas/{doc.id}/download"
    if kind == "quotation":
        return f"/api/integrations/waquote/quotations/{doc.id}/download"
    if kind == "invoice":
        number = (doc.doc_number or str(doc.id)).replace("/", "-")
        return f"/api/integrations/waquote/invoices/{number}/download"
    return None


def _normalize_doc_url(url: Optional[str]) -> Optional[str]:
    """Keep stored document links on the mounted ``/api`` route and normalized plural paths.

    Some legacy quotation rows were saved with an obsolete ``/api/v1``
    prefix or singular `/proforma/` path.
    """
    if not url:
        return None
    cleaned = str(url).strip()
    if cleaned.startswith("/api/v1/"):
        cleaned = "/api/" + cleaned[len("/api/v1/"):]
    cleaned = cleaned.replace("/waquote/proforma/", "/waquote/proformas/")
    cleaned = cleaned.replace("/waquote/quotation/", "/waquote/quotations/")
    cleaned = cleaned.replace("/waquote/invoice/", "/waquote/invoices/")
    return cleaned


def _document(
    *,
    doc_type: str,
    label: str,
    number: Optional[str],
    url: Optional[str],
    date_value: Any = None,
    status: Optional[str] = None,
    payment_status: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "type": doc_type,
        "label": label,
        "number": number or None,
        "url": _normalize_doc_url(url),
        "date": _iso_date(date_value),
        "status": status or None,
        "payment_status": payment_status or None,
    }


def _documents(
    db: Session,
    handoff: SupportHandoff,
    proforma: Optional[Quotation],
    finance: Optional[FinanceHandoff],
) -> List[Dict[str, Any]]:
    documents: List[Dict[str, Any]] = []

    # Issued quotation (the document the proforma was converted from).
    quotation_doc: Optional[Quotation] = None
    if proforma and proforma.source_quotation_id:
        quotation_doc = (
            db.query(Quotation)
            .filter(Quotation.id == proforma.source_quotation_id)
            .first()
        )
    elif proforma and proforma.source_quotation_number:
        quotation_doc = (
            db.query(Quotation)
            .filter(Quotation.doc_number == proforma.source_quotation_number)
            .first()
        )
    quotation_number = (
        (quotation_doc.doc_number if quotation_doc else None)
        or (proforma.source_quotation_number if proforma else None)
    )
    if quotation_number or quotation_doc:
        documents.append(
            _document(
                doc_type="quotation",
                label="Issued Quotation",
                number=quotation_number,
                url=_doc_url(quotation_doc, "quotation"),
                date_value=quotation_doc.issue_date if quotation_doc else None,
                status=quotation_doc.status if quotation_doc else None,
                payment_status=quotation_doc.payment_status if quotation_doc else None,
            )
        )

    # Approved proforma invoice / confirmed purchase record.
    proforma_number = (
        (proforma.doc_number if proforma else None)
        or handoff.proforma_number
        or handoff.quotation_number
    )
    if proforma_number or proforma:
        documents.append(
            _document(
                doc_type="proforma",
                label="Approved Proforma Invoice",
                number=proforma_number,
                url=(handoff.quotation_url or _doc_url(proforma, "proforma")),
                date_value=proforma.issue_date if proforma else handoff.won_at,
                status=proforma.status if proforma else None,
                payment_status=proforma.payment_status if proforma else handoff.payment_status,
            )
        )

    # Final tax invoice, when Finance has issued one.
    invoice_doc: Optional[Quotation] = None
    invoice_number = (finance.invoice_number if finance else None) or handoff.invoice_number
    if invoice_number:
        invoice_doc = (
            db.query(Quotation)
            .filter(Quotation.doc_number == invoice_number)
            .first()
        )
    if invoice_number or (finance and finance.invoice_url):
        documents.append(
            _document(
                doc_type="invoice",
                label="Final Tax Invoice",
                number=invoice_number,
                url=(finance.invoice_url if finance else None)
                or _doc_url(invoice_doc, "invoice"),
                date_value=(
                    invoice_doc.issue_date
                    if invoice_doc
                    else finance.payment_date if finance else None
                ),
                status=invoice_doc.status if invoice_doc else None,
                payment_status=(
                    invoice_doc.payment_status
                    if invoice_doc
                    else finance.payment_status if finance else None
                ),
            )
        )

    return documents


def _customer_block(handoff: SupportHandoff) -> Dict[str, Any]:
    customer = handoff.customer
    lead = handoff.lead
    return {
        "name": handoff.customer_name
        or (customer.contact_name if customer else None)
        or (lead.name if lead else None),
        "company_name": handoff.company_name
        or (customer.company_name if customer else None)
        or (lead.company if lead else None),
        "phone": handoff.phone
        or (customer.phone if customer else None)
        or (lead.phone if lead else None),
        "email": handoff.email
        or (customer.email if customer else None)
        or (lead.email if lead else None),
        "customer_id": handoff.customer_id,
    }


def _handover_block(
    handoff: SupportHandoff, proforma: Optional[Quotation]
) -> Dict[str, Any]:
    won_at = handoff.won_at or handoff.created_at
    proforma_number = (
        (proforma.doc_number if proforma else None)
        or handoff.proforma_number
        or handoff.quotation_number
    )
    reference = proforma_number or (
        f"Handover #{handoff.id}" if handoff.id else None
    )
    assigned_agent_name = handoff.assigned_agent_name
    if not assigned_agent_name and handoff.assigned_agent:
        assigned_agent_name = handoff.assigned_agent.name

    support_manager_name = handoff.support_manager_name
    if not support_manager_name and handoff.support_manager:
        support_manager_name = handoff.support_manager.name

    sales_employee_name = handoff.sales_employee_name
    if not sales_employee_name and handoff.lead and handoff.lead.assigned_employee:
        sales_employee_name = handoff.lead.assigned_employee.name

    return {
        "support_handoff_id": handoff.id,
        "finance_handoff_id": handoff.finance_handoff_id,
        "handover_date": _iso_date(won_at),
        "won_at": _iso_date(won_at),
        "sales_handover_reference": reference,
        "proforma_number": proforma_number,
        "quotation_number": handoff.quotation_number,
        "sales_employee_id": handoff.sales_employee_id,
        "sales_employee_name": sales_employee_name,
        "support_manager_id": handoff.support_manager_id,
        "support_manager_name": support_manager_name,
        "assigned_agent_id": handoff.assigned_agent_id,
        "assigned_agent_name": assigned_agent_name,
        "sales_status": handoff.lead.status if handoff.lead else None,
        "support_status": handoff.support_status,
    }


def build_purchase_snapshot(
    handoff: SupportHandoff,
    proforma: Optional[Quotation] = None,
    finance_handoff: Optional[FinanceHandoff] = None,
) -> Dict[str, Any]:
    """Capture the immutable purchase values at the Sales -> Support handover."""
    core = _purchase_core(handoff, proforma)
    return {
        "version": 1,
        "captured_at": datetime.utcnow().isoformat(),
        "customer": _customer_block(handoff),
        **core,
        "source": {
            "proforma_id": proforma.id if proforma else handoff.proforma_id,
            "proforma_number": (
                (proforma.doc_number if proforma else None)
                or handoff.proforma_number
                or handoff.quotation_number
            ),
            "finance_handoff_id": (
                finance_handoff.id if finance_handoff else handoff.finance_handoff_id
            ),
            "sales_employee_id": handoff.sales_employee_id,
            "sales_employee_name": handoff.sales_employee_name,
            "won_at": _iso_date(handoff.won_at or handoff.created_at),
        },
    }


def build_support_purchase_details(
    db: Session, handoff: Optional[SupportHandoff]
) -> Optional[Dict[str, Any]]:
    """Return the complete Support-facing purchase projection for one handover."""
    if not handoff:
        return None

    proforma = _get_proforma(db, handoff)
    finance = _get_finance_handoff(db, handoff)
    snapshot = _as_mapping(handoff.purchase_snapshot)

    if snapshot:
        core = {
            "package": snapshot.get("package") or _package_block(handoff.selected_bundle),
            "plan": snapshot.get("plan") or _plan_block(""),
            "employee_quantity": snapshot.get("employee_quantity"),
            "biometric_device_count": snapshot.get("biometric_device_count") or 0,
            "subscription": snapshot.get("subscription") or {},
            "addons": snapshot.get("addons") or [],
            "purchase_amount": snapshot.get("purchase_amount"),
        }
        source = "saved_purchase_snapshot"
    else:
        core = _purchase_core(handoff, proforma)
        source = "linked_proforma" if proforma else "handoff_snapshot"

    customer = _customer_block(handoff)
    if not customer.get("name") and snapshot.get("customer"):
        customer = snapshot["customer"]

    return {
        "snapshot_version": snapshot.get("version"),
        "customer": customer,
        **core,
        "documents": _documents(db, handoff, proforma, finance),
        "handover": _handover_block(handoff, proforma),
        "source": source,
    }


def backfill_support_purchase_snapshots(db: Session) -> int:
    """Create snapshots for handovers that pre-date the additive column."""
    pending = (
        db.query(SupportHandoff)
        .filter(SupportHandoff.purchase_snapshot.is_(None))
        .all()
    )
    if not pending:
        return 0

    updated = 0
    for handoff in pending:
        proforma = _get_proforma(db, handoff)
        finance = _get_finance_handoff(db, handoff)
        handoff.purchase_snapshot = build_purchase_snapshot(handoff, proforma, finance)
        updated += 1

    if updated:
        db.commit()
    return updated
