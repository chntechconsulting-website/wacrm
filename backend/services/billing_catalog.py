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


# ---------------------------------------------------------------------------
# Biometric hardware catalogue
# ---------------------------------------------------------------------------
# Dealer Price List 2026. Every device is exposed as a selectable BIOMETRIC
# bundle so quotations can use the exact model and dealer price. GST is always
# added separately at 18% (the price list explicitly says "18% Extra").

BIOMETRIC_DEVICE_GROUPS: List[Dict[str, Any]] = [
    {"code": "face_finger", "name": "Face + Finger"},
    {"code": "finger", "name": "Fingerprint"},
    {"code": "reader", "name": "Reader Devices"},
]

DEFAULT_BIOMETRIC_DEVICES: List[Dict[str, Any]] = [
    # Face + Finger models
    {"code": "bio_dev_ai_mercury", "name": "AI MERCURY", "group": "face_finger", "features": ["Face"], "connectivity": "Wi-Fi", "price": 10722.0},
    {"code": "bio_dev_ai_urans", "name": "AI URANS", "group": "face_finger", "features": ["Face", "Fingerprint", "RFID", "Password"], "connectivity": "LAN", "price": 10722.0},
    {"code": "bio_dev_ai_neptune", "name": "AI NEPTUNE", "group": "face_finger", "features": ["Face", "RFID"], "connectivity": "LAN", "price": 13809.0},
    {"code": "bio_dev_ai_neptune_bat", "name": "AI NEPTUNE+BAT", "group": "face_finger", "features": ["Face", "RFID"], "connectivity": "Wi-Fi + LAN + Battery", "price": 14732.0},
    {"code": "bio_dev_ai_pluto", "name": "AI PLUTO", "group": "face_finger", "features": ["Face", "RFID"], "connectivity": "Wi-Fi + LAN", "price": 19130.0},
    {"code": "bio_dev_ai_mars", "name": "AI MARS", "group": "face_finger", "features": ["Face", "RFID"], "connectivity": "LAN", "price": 23038.0},
    {"code": "bio_dev_ai_mars_wifi", "name": "AI MARS-WIFI", "group": "face_finger", "features": ["Face", "RFID"], "connectivity": "Wi-Fi + LAN", "price": 23571.0},
    {"code": "bio_dev_ai_mars_palm", "name": "AI MARS-PALM", "group": "face_finger", "features": ["Face", "RFID", "Password", "Palm"], "connectivity": "Wi-Fi + LAN", "price": 25539.0},
    {"code": "bio_dev_ai_jupiter", "name": "AI JUPITER", "group": "face_finger", "features": ["Face", "Fingerprint", "RFID"], "connectivity": "Wi-Fi + LAN", "price": 33420.0},
    {"code": "bio_dev_ai_orcus", "name": "AI ORCUS", "group": "face_finger", "features": ["Face", "Fingerprint", "RFID", "Password"], "connectivity": "Wi-Fi + LAN", "price": 13949.0},
    {"code": "bio_dev_ai_magnum_lite", "name": "AI MAGNUM LITE", "group": "face_finger", "features": ["Face", "RFID"], "connectivity": "Wi-Fi + LAN", "price": 15151.0},
    {"code": "bio_dev_ai_magnum", "name": "AI MAGNUM", "group": "face_finger", "features": ["Face", "Fingerprint", "RFID"], "connectivity": "LAN", "price": 18307.0},
    {"code": "bio_dev_ai_magnum_wifi", "name": "AI MAGNUM-WIFI", "group": "face_finger", "features": ["Face", "Fingerprint", "RFID"], "connectivity": "Wi-Fi + LAN", "price": 20718.0},
    {"code": "bio_dev_mb160", "name": "MB160", "group": "face_finger", "features": ["Face", "Fingerprint", "RFID"], "connectivity": "LAN", "price": 12800.0},
    {"code": "bio_dev_mb160_bat", "name": "MB160 -BAT", "group": "face_finger", "features": ["Face", "Fingerprint", "RFID"], "connectivity": "LAN + Battery", "price": 13785.0},
    {"code": "bio_dev_mb160_bat_wifi_lan_bat", "name": "MB160 -BAT (WIFI+LAN+BAT)", "group": "face_finger", "features": ["Face", "Fingerprint", "RFID"], "connectivity": "Wi-Fi + LAN + Battery", "price": 16151.0},
    {"code": "bio_dev_mb20", "name": "MB20", "group": "face_finger", "features": ["Face", "Fingerprint", "RFID"], "connectivity": "LAN", "price": 10722.0},
    {"code": "bio_dev_uface302", "name": "UFACE302", "group": "face_finger", "features": ["Face", "Fingerprint", "RFID"], "connectivity": "LAN", "price": 25804.0},
    {"code": "bio_dev_silkbio_101tc_id_bat", "name": "SILKBIO-101TC+ID+BAT", "group": "face_finger", "features": ["Face", "Fingerprint", "RFID"], "connectivity": "LAN", "price": 18181.0},
    {"code": "bio_dev_ai_eris", "name": "AI ERIS", "group": "face_finger", "features": ["Face", "Fingerprint", "RFID"], "connectivity": "Wi-Fi + LAN", "price": 26724.0},
    {"code": "bio_dev_ai_arion", "name": "AI ARION", "group": "face_finger", "features": ["Face", "Fingerprint", "RFID"], "connectivity": "Wi-Fi + LAN", "price": 34315.0},
    # Fingerprint models
    {"code": "bio_dev_k30_bat", "name": "K30 + BAT", "group": "finger", "features": ["Fingerprint", "RFID"], "connectivity": "LAN + Battery", "price": 6841.0},
    {"code": "bio_dev_k30_wifi_bat", "name": "K30 - WIFI+BAT", "group": "finger", "features": ["Fingerprint", "RFID"], "connectivity": "Wi-Fi + LAN + Battery", "price": 8633.0},
    {"code": "bio_dev_k90", "name": "K90", "group": "finger", "features": ["Fingerprint", "RFID"], "connectivity": "LAN + Battery", "price": 6553.0},
    {"code": "bio_dev_f22_wifi", "name": "F22 - WIFI", "group": "finger", "features": ["Fingerprint", "RFID"], "connectivity": "Wi-Fi / LAN", "price": 12322.0},
    {"code": "bio_dev_x990", "name": "X990", "group": "finger", "features": ["Fingerprint", "RFID"], "connectivity": "LAN", "price": 15012.0},
    {"code": "bio_dev_iclock_990", "name": "ICLOCK 990", "group": "finger", "features": ["Fingerprint", "RFID"], "connectivity": "LAN", "price": 23149.0},
    # Reader models
    {"code": "bio_dev_fr1200", "name": "FR1200", "group": "reader", "features": ["Fingerprint"], "connectivity": "LAN", "price": 6194.0},
    {"code": "bio_dev_kr500_e", "name": "KR500-E", "group": "reader", "features": ["RFID"], "connectivity": "LAN", "price": 1651.0},
    {"code": "bio_dev_x7", "name": "X7", "group": "reader", "features": ["Fingerprint", "RFID", "Password"], "connectivity": "LAN", "price": 4009.0},
    {"code": "bio_dev_f_18", "name": "F-18", "group": "reader", "features": ["Fingerprint", "RFID"], "connectivity": "LAN", "price": 16927.0},
    {"code": "bio_dev_sf_100", "name": "SF-100", "group": "reader", "features": ["Fingerprint", "RFID"], "connectivity": "LAN", "price": 10253.0},
    {"code": "bio_dev_sc_405", "name": "SC-405", "group": "reader", "features": ["RFID"], "connectivity": "LAN", "price": 11684.0},
]


def _biometric_device_bundle(device: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Build a selectable BIOMETRIC bundle from one price-list device."""
    feature_label = " + ".join(device["features"])
    connectivity = device["connectivity"]
    price = float(device["price"])
    group = next(
        (g["name"] for g in BIOMETRIC_DEVICE_GROUPS if g["code"] == device["group"]),
        "Biometric Device",
    )
    slug = device["code"].replace("bio_dev_", "", 1).upper()
    return {
        "bundle_code": device["code"],
        "category": "BIOMETRIC",
        "name": device["name"],
        "tagline": f"{feature_label} • {connectivity}",
        "description": (
            f"{device['name']} biometric device with {feature_label.lower()} and "
            f"{connectivity} connectivity. Dealer price ₹{price:,.0f} + 18% GST."
        ),
        "badge": group,
        "features": [
            feature_label,
            f"{connectivity} Connectivity",
            "Cloud Punch Sync Ready",
            "1-Year Manufacturer Warranty",
            "GST 18% Extra",
        ],
        "items": [
            {
                "item_code": f"BIO_DEV_{slug}",
                "name": f"{device['name']} Biometric Device",
                "description": (
                    f"{device['name']} Biometric Device "
                    f"({feature_label}, {connectivity})"
                ),
                "hsn": "85437099",
                "qty": 1,
                "rate": price,
                "gstRate": 0.18,
                "discount": 0.0,
            }
        ],
        "sort_order": 100 + index,
        "is_active": 1,
    }


DEFAULT_BIOMETRIC_PACKAGES: List[Dict[str, Any]] = [
    {
        "bundle_code": "bio_standard",
        "category": "BIOMETRIC",
        "name": "Biometric Standard (MB160 Terminal)",
        "tagline": "Standalone facial & fingerprint terminal with cloud punch sync",
        "description": "Enterprise biometric terminal with face, fingerprint, and RFID recognition, bundled with 4G IoT SIM card, cloud synchronization bridge, and installation.",
        "badge": "Popular Hardware",
        "features": [
            "MB160 Face + Fingerprint + RFID Terminal",
            "1x 4G IoT SIM Card Included",
            "Hardware Protocol Bridge & Cloud Sync",
            "Standard Wall Mount & Power Brick",
            "Onsite Hardware Setup & Testing",
        ],
        "items": [
            {
                "item_code": "MB160_DEVICE",
                "name": "MB160 Biometric Device",
                "description": "MB160 Biometric Device",
                "hsn": "85437099",
                "rate": 22400.0,
                "qty": 1,
                "discount": 0.0,
                "gstRate": 0.18,
            },
            {
                "item_code": "BIO_CLOUD_SYNC",
                "name": "Hardware Cloud Sync Bridge",
                "description": "Hardware Cloud Sync Bridge",
                "hsn": "998314",
                "rate": 4999.0,
                "qty": 1,
                "discount": 0.0,
                "gstRate": 0.18,
            },
            {
                "item_code": "DEVICE_INSTALL",
                "name": "Installation & Calibration",
                "description": "Installation & Calibration",
                "hsn": "998315",
                "rate": 1000.0,
                "qty": 1,
                "discount": 0.0,
                "gstRate": 0.18,
            },
        ],
        "sort_order": 1,
        "is_active": 1,
    },
    {
        "bundle_code": "bio_atm",
        "category": "BIOMETRIC",
        "name": "WA ATM Biometric Hardware",
        "tagline": "Cost-effective optical attendance machine for offices & retail",
        "description": "WA ATM biometric terminal designed for rapid shift attendance logging, cloud software integration, and effortless deployment.",
        "badge": "Cost Effective",
        "features": [
            "WA ATM Machine & Biometric Hardware",
            "Dual Face & Optical Fingerprint Sensor",
            "TCP/IP & Cloud Sync Ready",
            "Wall Mounting & Power Adapter Included",
            "Setup & Device Training Included",
        ],
        "items": [
            {
                "item_code": "WA_ATM_HARDWARE",
                "name": "WA ATM Machine Hardware",
                "description": "WA ATM Machine Hardware",
                "hsn": "85437099",
                "rate": 18500.0,
                "qty": 1,
                "discount": 0.0,
                "gstRate": 0.18,
            },
            {
                "item_code": "WA_ATM_SETUP",
                "name": "Setup & Deployment",
                "description": "Setup & Deployment",
                "hsn": "998315",
                "rate": 1000.0,
                "qty": 1,
                "discount": 0.0,
                "gstRate": 0.18,
            },
        ],
        "sort_order": 2,
        "is_active": 1,
    },
    {
        "bundle_code": "bio_enterprise",
        "category": "BIOMETRIC",
        "name": "Biometric Multi-Location Suite",
        "tagline": "Dual terminal package for branch & multi-door deployments",
        "description": "Complete multi-location biometric setup with dual MB160 terminals, SIM cards, enterprise cloud integration bridge, and multi-device deployment.",
        "badge": "Multi-Door Enterprise",
        "features": [
            "2x MB160 Face + Fingerprint + RFID Terminals",
            "2x 4G IoT SIM Cards Included",
            "Multi-Branch Central Cloud Sync Bridge",
            "Centralized Punch Dashboard Setup",
            "Multi-Device Installation & Operator Training",
        ],
        "items": [
            {
                "item_code": "2X_MB160_DEVICES",
                "name": "2x MB160 Biometric Terminals",
                "description": "2x MB160 Biometric Terminals",
                "hsn": "85437099",
                "rate": 44800.0,
                "qty": 1,
                "discount": 0.0,
                "gstRate": 0.18,
            },
            {
                "item_code": "MULTI_CLOUD_BRIDGE",
                "name": "Multi-Location Cloud Bridge",
                "description": "Multi-Location Cloud Bridge",
                "hsn": "998314",
                "rate": 7500.0,
                "qty": 1,
                "discount": 0.0,
                "gstRate": 0.18,
            },
            {
                "item_code": "MULTI_INSTALL",
                "name": "Multi-Device Deployment",
                "description": "Multi-Device Deployment",
                "hsn": "998315",
                "rate": 2000.0,
                "qty": 1,
                "discount": 0.0,
                "gstRate": 0.18,
            },
        ],
        "sort_order": 3,
        "is_active": 1,
    },
]

DEFAULT_BIOMETRIC_BUNDLES: List[Dict[str, Any]] = (
    DEFAULT_BIOMETRIC_PACKAGES
    + [
        _biometric_device_bundle(device, index)
        for index, device in enumerate(DEFAULT_BIOMETRIC_DEVICES)
    ]
)

BIOMETRIC_DEVICE_BUNDLE_CODES = [device["code"] for device in DEFAULT_BIOMETRIC_DEVICES]
BIOMETRIC_BUNDLE_CODES = [bundle["bundle_code"] for bundle in DEFAULT_BIOMETRIC_BUNDLES]

_PLAN_LINE_RE = re.compile(r"(?:^|\n)\s*Plan\s*:?\s*([^\n]+)", re.IGNORECASE)


def get_default_bundle(bundle_code: str) -> Optional[Dict[str, Any]]:
    """Return a defensive copy of one default WAHRMS or biometric bundle."""
    for bundle in DEFAULT_WAHRMS_BUNDLES + DEFAULT_BIOMETRIC_BUNDLES:
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
