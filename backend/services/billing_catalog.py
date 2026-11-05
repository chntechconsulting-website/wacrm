"""Central catalogue for WA! HRMS subscription packages and plans.

This module is the backend source of truth for package/plan pricing. The
bundle master rows are seeded from it, and the quote router uses it to enrich
legacy bundle records with plan metadata. Saved quotation line items keep
their own stored rates, so historical documents are never repriced by changes
made here.
"""

from typing import Any, Dict, Iterable, List, Optional
import copy
import re

BILLING_PLANS: List[Dict[str, Any]] = [
    {"code": "pro", "name": "Pro", "isCustom": False},
    {"code": "business", "name": "Business", "isCustom": False},
    {"code": "custom", "name": "Custom", "isCustom": True},
]


def build_plan_options(pro_rate: float, business_rate: float) -> List[Dict[str, Any]]:
    """Return the three selectable plans for a per-employee subscription."""
    return [
        {"code": "pro", "name": "Pro", "rate": float(pro_rate), "isCustom": False},
        {"code": "business", "name": "Business", "rate": float(business_rate), "isCustom": False},
        {"code": "custom", "name": "Custom", "rate": None, "isCustom": True},
    ]


DEFAULT_WAHRMS_BUNDLES: List[Dict[str, Any]] = [
    {
        "bundle_code": "hr_atm",
        "category": "WAHRMS",
        "name": "HR + ATM",
        "tagline": "Core HR with attendance & time.",
        "description": "Integrated employee directory, leave management, and real-time biometric attendance capture.",
        "badge": None,
        "features": [
            "Core HR & Employee Directory",
            "Attendance & Time Tracking",
            "Leave & Holiday Management",
            "Biometric Device Integration",
        ],
        "items": [
            {
                "item_code": "HR_ATM_SUB",
                "name": "WAHRMS HR + ATM Subscription",
                "description": "WAHRMS HR + ATM Subscription",
                "hsn": "998314",
                "qty": 120,
                "rate": 40.0,
                "gstRate": 0.18,
                "discount": 0.0,
                "billingBasis": "employee_month",
                "plans": build_plan_options(40, 55),
            },
            {
                "item_code": "BIO_INTEGRATION",
                "name": "Biometric Integration",
                "description": "Biometric Integration",
                "hsn": "998314",
                "qty": 1,
                "rate": 4999.0,
                "gstRate": 0.18,
                "discount": 0.0,
            },
        ],
        "sort_order": 1,
        "is_active": 1,
    },
    {
        "bundle_code": "hr_payroll",
        "category": "WAHRMS",
        "name": "HR + Payroll",
        "tagline": "Core HR with payroll & statutory.",
        "description": "Comprehensive employee records paired with full salary computation, payslips, PF, ESI, TDS, and statutory compliance.",
        "badge": None,
        "features": [
            "Core HR & Employee Profiles",
            "Statutory Payroll Engine",
            "PF, ESI, PT & TDS Filings",
            "One-Click Payslips & Direct Bank Advice",
        ],
        "items": [
            {
                "item_code": "HR_PAYROLL_SUB",
                "name": "WAHRMS HR + Payroll Subscription",
                "description": "WAHRMS HR + Payroll Subscription",
                "hsn": "998314",
                "qty": 120,
                "rate": 45.0,
                "gstRate": 0.18,
                "discount": 0.0,
                "billingBasis": "employee_month",
                "plans": build_plan_options(45, 60),
            },
            {
                "item_code": "PAYROLL_SETUP",
                "name": "WA Payroll Cloud Setup & Deployment",
                "description": "WA Payroll Cloud Setup & Deployment",
                "hsn": "998315",
                "qty": 1,
                "rate": 5000.0,
                "gstRate": 0.18,
                "discount": 0.0,
            },
        ],
        "sort_order": 2,
        "is_active": 1,
    },
    {
        "bundle_code": "hr_atm_payroll",
        "category": "WAHRMS",
        "name": "HR + ATM + Payroll",
        "tagline": "The full suite.",
        "description": "The complete all-in-one workforce powerhouse: Core HR, biometric attendance, statutory payroll, and self-service.",
        "badge": "Full Suite • Best Value",
        "features": [
            "Core HR & Lifecycle Management",
            "Biometric Attendance Sync",
            "Statutory Payroll & Compliance Engine",
            "One-Click Payslips & Direct Bank Advice",
        ],
        "items": [
            {
                "item_code": "HR_ATM_PAYROLL_SUB",
                "name": "WAHRMS HR + ATM + Payroll Subscription",
                "description": "WAHRMS HR + ATM + Payroll Subscription",
                "hsn": "998314",
                "qty": 120,
                "rate": 50.0,
                "gstRate": 0.18,
                "discount": 0.0,
                "billingBasis": "employee_month",
                "plans": build_plan_options(50, 70),
            },
            {
                "item_code": "BIO_PAYROLL_PACKAGE",
                "name": "bio & payroll Integrated Package",
                "description": "bio & payroll Integrated Package",
                "hsn": "85437099",
                "qty": 1,
                "rate": 24500.0,
                "gstRate": 0.18,
                "discount": 0.0,
            },
        ],
        "sort_order": 3,
        "is_active": 1,
    },
    {
        "bundle_code": "bio_payroll",
        "category": "WAHRMS",
        "name": "Biometric + Payroll",
        "tagline": "Biometric attendance with statutory payroll.",
        "description": "Biometric device integration and attendance management paired with payroll processing, statutory compliance, and payslip generation.",
        "badge": None,
        "features": [
            "Biometric Device Integration",
            "Attendance Management",
            "Payroll Processing",
            "PF, ESI & Statutory Compliance",
            "Payslip Generation",
        ],
        "items": [
            {
                "item_code": "BIO_PAYROLL_SUB",
                "name": "WAHRMS Biometric + Payroll Subscription",
                "description": "WAHRMS Biometric + Payroll Subscription",
                "hsn": "998314",
                "qty": 120,
                "rate": 45.0,
                "gstRate": 0.18,
                "discount": 0.0,
                "billingBasis": "employee_month",
                "plans": build_plan_options(45, 60),
            }
        ],
        "sort_order": 4,
        "is_active": 1,
    },
]

WAHRMS_PACKAGE_CODES = [bundle["bundle_code"] for bundle in DEFAULT_WAHRMS_BUNDLES]

_PLAN_LINE_RE = re.compile(r"(?:^|\n)\s*Plan\s*:?\s*([^\n]+)", re.IGNORECASE)


def get_default_bundle(bundle_code: str) -> Optional[Dict[str, Any]]:
    """Return a defensive copy of one default bundle definition."""
    for bundle in DEFAULT_WAHRMS_BUNDLES:
        if bundle["bundle_code"] == bundle_code:
            return copy.deepcopy(bundle)
    return None


def get_catalog_plans(bundle_code: str) -> List[Dict[str, Any]]:
    """Return the central plan list for a package code."""
    bundle = get_default_bundle(bundle_code)
    if not bundle:
        return []
    for item in bundle.get("items") or []:
        plans = item.get("plans")
        if isinstance(plans, list) and plans:
            return copy.deepcopy(plans)
    return []


def _is_subscription_item(item: Dict[str, Any]) -> bool:
    item_code = str(item.get("item_code") or item.get("itemCode") or "").upper()
    if item_code.endswith("_SUB"):
        return True
    return "subscription" in str(item.get("name") or "").lower()


def _catalog_item_for_code(bundle_code: str, item_code: str) -> Optional[Dict[str, Any]]:
    bundle = get_default_bundle(bundle_code)
    if not bundle:
        return None
    for item in bundle.get("items") or []:
        catalog_code = str(item.get("item_code") or item.get("itemCode") or "").upper()
        if catalog_code == str(item_code or "").upper():
            return item
    return None


def enrich_bundle_items_with_plans(bundle_code: str, items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge central plan metadata into legacy bundle items.

    Existing admin-authored data is preserved. Only the fields needed for plan
    selection and per-employee pricing are filled in when they are missing.
    """
    enriched: List[Dict[str, Any]] = []
    for source in items or []:
        item = copy.deepcopy(source)
        if not isinstance(item, dict) or not _is_subscription_item(item):
            enriched.append(item)
            continue

        catalog_item = _catalog_item_for_code(bundle_code, item.get("item_code") or item.get("itemCode"))
        if catalog_item:
            if not item.get("billingBasis"):
                item["billingBasis"] = catalog_item.get("billingBasis", "employee_month")
            if not isinstance(item.get("plans"), list) or not item.get("plans"):
                item["plans"] = copy.deepcopy(catalog_item.get("plans") or [])
        enriched.append(item)
    return enriched


def get_bundle_plans(bundle_code: str, items: Optional[Iterable[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Resolve the plan list from bundle items, falling back to the catalogue."""
    for item in items or []:
        if isinstance(item, dict) and _is_subscription_item(item):
            plans = item.get("plans")
            if isinstance(plans, list) and plans:
                return copy.deepcopy(plans)
    return get_catalog_plans(bundle_code)


def _normalize_plan_code(value: Any) -> str:
    return str(value or "").strip().lower()


def extract_plan_code(item: Dict[str, Any]) -> str:
    """Read a plan code from explicit fields or a saved ``Plan:`` line."""
    code = _normalize_plan_code(item.get("planCode") or item.get("plan_code"))
    if code:
        return code

    name = _normalize_plan_code(item.get("planName") or item.get("plan_name"))
    if name in {"pro", "business", "custom"}:
        return name

    description = str(item.get("description") or "")
    match = _PLAN_LINE_RE.search(description)
    if match:
        parsed_name = match.group(1).strip().lower()
        if parsed_name in {"pro", "business", "custom"}:
            return parsed_name

    return ""


def validate_custom_plan_items(line_items: Iterable[Dict[str, Any]]) -> Optional[str]:
    """Block Custom plan lines that have no negotiated per-employee rate."""
    for item in line_items or []:
        if not isinstance(item, dict):
            continue
        if extract_plan_code(item) != "custom":
            continue

        raw_rate = item.get("rate")
        try:
            rate = float(raw_rate)
        except (TypeError, ValueError):
            rate = 0.0
        if rate <= 0:
            return (
                "Enter a negotiated per-employee rate greater than zero for the "
                "Custom plan before issuing this document."
            )
    return None
