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

BIOMETRIC_TERMS_AND_CONDITIONS = (
    "1. All civil works must be done by the client.\n"
    "2. Electrical Cable and Casing Pipe, Switch & Socket as per the Cost. Charged by Electrician (Clients Scope).\n"
    "3. Cable Per Meter Rs.45/-, Cable Laying Charges Per Meter Rs.35/-\n"
    "4. Warranty: Products have one-year Manufacturer warranty. The warranty does not cover any physical damages.\n"
    "5. Device Installation Charges Rs.1000- Per Location Per Device in Chennai and Coimbatore Only (Other Cities within TN Rs.2000).\n"
    "6. Local or Remote ESSL Software Installation Charges: Chennai and Coimbatore Only: ₹1000 per location per device. Other Cities within TN: ₹1500 per location per device.\n"
    "\n"
    "Payment Terms:\n"
    "• 75% advance payment is required before mobilization and commencement of work.\n"
    "• The remaining 25% balance payment is payable immediately upon successful completion of the work."
)


def default_terms_for_category(category) -> str:
    """Return the commercial terms that match the quotation category."""
    if str(category or "").strip().upper() == "BIOMETRIC":
        return BIOMETRIC_TERMS_AND_CONDITIONS
    return WAHRMS_TERMS_AND_CONDITIONS

# Older Proforma records may carry one of these short defaults. They should
# render the full WAHRMS terms instead of the legacy wording.
_LEGACY_PROFORMA_TERMS = (
    (
        "1. Payment terms: 100% advance payment against this Proforma Invoice.\n"
        "2. Bank transfers to be credited to the Axis Bank account mentioned above.\n"
        "3. Materials will be dispatched upon payment credit receipt.\n"
        "4. Goods once sold will not be taken back."
    ),
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
_LEGACY_BIOMETRIC_PLACEHOLDERS = {"biometric terms", "biometric terms and conditions"}


def resolve_billing_terms(terms, doc_type, product_category=None):
    """Return category-aware terms for quotations.

    Proforma Invoices intentionally carry no Terms & Conditions, regardless of
    the product category or any value stored on the document.
    """
    normalized_type = str(doc_type or "").strip().lower()
    if normalized_type == "proforma":
        return ""
    cleaned = str(terms or "").strip()
    if normalized_type == "quotation":
        normalized = _normalize(cleaned)
        is_biometric = str(product_category or "").strip().upper() == "BIOMETRIC"
        if (
            not cleaned
            or normalized in _LEGACY_NORMALIZED
            or (is_biometric and normalized.lower() in _LEGACY_BIOMETRIC_PLACEHOLDERS)
        ):
            return default_terms_for_category(product_category)
    return cleaned
