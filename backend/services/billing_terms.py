"""Shared commercial terms for WAHRMS billing documents."""

WAHRMS_TERMS_AND_CONDITIONS = (
    "1. Prices are subject to applicable GST as specified.\n"
    "2. Software activation and onboarding will begin upon PO confirmation and receipt of payment.\n"
    "3. Setup, training, and technical support will be provided as agreed.\n"
    "4. The client is responsible for providing accurate employee and payroll data and verifying payroll calculations.\n"
    "5. Timely subscription renewal is required to ensure uninterrupted software access.\n"
    "6. Customization and third-party integrations may incur additional charges.\n"
    "7. Confirmation of the purchase order constitutes acceptance of the quotation and these terms."
)

# Older Proforma records may carry one of these short defaults. They should
# render the full WAHRMS terms instead of the legacy wording.
_LEGACY_PROFORMA_TERMS = (
    (
        "1. 100% advance payment against Proforma Invoice.\n"
        "2. Service will be activated upon payment confirmation.\n"
        "3. Taxes applicable as per GST guidelines."
    ),
    "1. Software access activates upon payment.\n2. Prices subject to applicable GST.",
)


def _normalize(value):
    return " ".join(str(value or "").split())


_LEGACY_NORMALIZED = {_normalize(term) for term in _LEGACY_PROFORMA_TERMS}


def resolve_billing_terms(terms, doc_type):
    """Return the WAHRMS terms for quotations/proformas when missing or legacy."""
    cleaned = str(terms or "").strip()
    if doc_type in ("quotation", "proforma"):
        if not cleaned or _normalize(cleaned) in _LEGACY_NORMALIZED:
            return WAHRMS_TERMS_AND_CONDITIONS
    return cleaned
