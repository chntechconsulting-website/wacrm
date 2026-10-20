import re
import logging
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session
from dataclasses import dataclass

from models.quotation import Quotation, WAHRMSBundle

logger = logging.getLogger("product_validation_service")

@dataclass
class ProductCategoryValidationResult:
    resolved_category: str       # "WAHRMS", "BIOMETRIC", "MIXED", or "UNKNOWN"
    is_wahrms_only: bool          # True ONLY if 100% WAHRMS software with ZERO biometric products
    has_biometric: bool           # True if any biometric hardware, terminal, or hardware service is present
    has_wahrms: bool              # True if any WAHRMS software module, subscription, or software setup is present
    is_mixed: bool                # True if both WAHRMS and Biometric products exist
    licence_count: Optional[int]  # Extracted user / employee / licence count
    biometric_device_count: int   # Count of physical biometric terminals
    reasons: List[str]            # Detailed audit reasons explaining the classification
    primary_reason: str           # User-facing summary explanation


class ProductValidationService:
    """
    Authoritative Product Category and Document Eligibility Validation Service.
    
    Enforces the strict business rule:
    - Only 100% WAHRMS documents may be synchronized to external websites/ERPs.
    - Any document containing Biometric hardware, terminals, or installation services
      must remain EXCLUSIVELY inside Wa CRM and must NEVER be transferred externally.
    - Mixed documents (WAHRMS + Biometric) are strictly blocked from external synchronization.
    
    Validation is multi-factored and authoritative:
    1. Bundle Master Table (`wahrms_bundles`): Authoritative category of the selected bundle.
    2. HSN / SAC statutory codes:
       - 8543... -> Chapter 85 (Electrical machines/biometric apparatus) = BIOMETRIC
       - 9983... -> Chapter 99 (Information technology software services) = WAHRMS / Software
    3. Item SKU / Codes: BIO, MB160, TERMINAL, DEVICE vs HR, PAYROLL, ATM.
    4. Text descriptions: Hardware terminal keywords vs software subscription keywords.
    """

    # Biometric hardware HSN prefixes (Statutory GST classification)
    BIOMETRIC_HSN_PREFIXES = ("8543", "8471", "8528", "8536")

    # Software & Professional services SAC prefixes
    SOFTWARE_SAC_PREFIXES = ("9983", "9984", "9987")

    # Known biometric bundle codes
    BIOMETRIC_BUNDLE_CODES = {
        "bio_standard",
        "bio_atm",
        "bio_enterprise"
    }

    # Known WAHRMS bundle codes
    WAHRMS_BUNDLE_CODES = {
        "hr_atm",
        "hr_payroll",
        "hr_atm_payroll"  # Note: hr_atm_payroll bundle contains a biometric hardware package, making it mixed!
    }

    # Explicit physical biometric hardware keywords
    BIOMETRIC_HARDWARE_KEYWORDS = [
        "biometric device",
        "biometric terminal",
        "biometric machine",
        "biometric hardware",
        "attendance terminal",
        "attendance machine",
        "hardware terminal",
        "fingerprint",
        "face scanner",
        "facial recognition",
        "mb160",
        "zkteco",
        "access control",
        "rfid reader",
        "rfid card",
        "power supply 12v",
        "mount kit",
        "mounting bracket",
        "iot data sim",
        "4g sim"
    ]

    # Biometric hardware installation & onsite service keywords
    BIOMETRIC_INSTALLATION_KEYWORDS = [
        "onsite device mounting",
        "device mounting",
        "hardware installation",
        "terminal hardware",
        "terminal configuration",
        "device deployment",
        "technician support",
        "onsite hardware"
    ]

    # Pure software keywords
    WAHRMS_SOFTWARE_KEYWORDS = [
        "wahrms",
        "payroll cloud",
        "core hr",
        "attendance and time management",
        "attendance subscription",
        "leave workflow",
        "shift roster",
        "live tracking",
        "workforce management",
        "salary processing",
        "salary structure",
        "statutory compliance",
        "user license",
        "employee onboard",
        "onboarding license"
    ]

    @classmethod
    def classify_line_item(cls, item: Dict[str, Any], db: Optional[Session] = None) -> Tuple[bool, bool, str]:
        """
        Classifies a single line item.
        Returns: (is_biometric: bool, is_wahrms: bool, description_reason: str)
        """
        hsn = str(item.get("hsn") or item.get("hsn_code") or item.get("hsnCode") or "").strip()
        item_code = str(item.get("item_code") or item.get("itemCode") or "").upper().strip()
        name = str(item.get("name") or "").strip()
        desc = str(item.get("description") or "").strip()
        full_text = f"{name} {desc}".lower()

        is_biometric = False
        is_wahrms = False
        reasons = []

        # 1. HSN Check
        if any(hsn.startswith(prefix) for prefix in cls.BIOMETRIC_HSN_PREFIXES):
            is_biometric = True
            reasons.append(f"Statutory HSN code '{hsn}' signifies physical biometric/electronic apparatus")

        # 2. Item Code Check
        if any(code in item_code for code in ["MB160", "BIO_STD", "BIO_ATM", "BIO_ENT", "BIO_DEVICE", "BIO_SETUP", "BIO_INSTALL", "BIO_PAYROLL_PACKAGE"]):
            is_biometric = True
            reasons.append(f"Item code '{item_code}' indicates biometric hardware/service")

        # 3. Hardware / Device Text Keywords
        if any(kw in full_text for kw in cls.BIOMETRIC_HARDWARE_KEYWORDS):
            is_biometric = True
            reasons.append("Contains physical biometric hardware terminal / device keywords")

        if any(kw in full_text for kw in cls.BIOMETRIC_INSTALLATION_KEYWORDS):
            is_biometric = True
            reasons.append("Contains biometric hardware installation / mounting service keywords")

        # 4. WAHRMS Software Check
        if any(hsn.startswith(prefix) for prefix in cls.SOFTWARE_SAC_PREFIXES):
            # Check if this is software vs hardware service
            if not is_biometric:
                is_wahrms = True
                reasons.append(f"SAC code '{hsn}' indicates software / cloud subscription")

        if any(code in item_code for code in ["HR_ATM_SUB", "HR_PAYROLL_SUB", "PAYROLL_SETUP", "WAHRMS_"]):
            is_wahrms = True
            reasons.append(f"Item code '{item_code}' indicates WAHRMS cloud software module")

        if any(kw in full_text for kw in cls.WAHRMS_SOFTWARE_KEYWORDS):
            is_wahrms = True
            reasons.append("Contains WAHRMS software subscription / workforce module keywords")

        # Biometric API / software integration module for WAHRMS
        # (e.g., 'Biometric Integration & Cloud Auto-Sync Module' with SAC 998314)
        if "biometric integration" in full_text and hsn.startswith("9983") and not any(kw in full_text for kw in ["mb160", "terminal", "device", "mounting", "hardware machine"]):
            # This is a software API connector module for WAHRMS
            is_wahrms = True

        reason_str = "; ".join(reasons) if reasons else "Generic product item"
        return is_biometric, is_wahrms, reason_str

    @classmethod
    def validate_document_products(
        cls,
        doc_or_payload: Any,
        db: Optional[Session] = None
    ) -> ProductCategoryValidationResult:
        """
        Authoritatively validates all line items, bundles, and product categories
        for a quotation or proforma document or external request payload.
        """
        # 1. Extract raw line items
        line_items: List[Dict[str, Any]] = []
        if hasattr(doc_or_payload, "line_items"):
            line_items = doc_or_payload.line_items or []
        elif isinstance(doc_or_payload, dict):
            line_items = doc_or_payload.get("line_items") or doc_or_payload.get("lineItems") or []
        elif hasattr(doc_or_payload, "lineItems"):
            line_items = getattr(doc_or_payload, "lineItems") or []

        # 2. Extract selected bundle and product category
        selected_bundle = None
        if hasattr(doc_or_payload, "selected_bundle"):
            selected_bundle = doc_or_payload.selected_bundle
        elif isinstance(doc_or_payload, dict):
            selected_bundle = doc_or_payload.get("selected_bundle") or doc_or_payload.get("selectedBundle")
        elif hasattr(doc_or_payload, "selectedBundle"):
            selected_bundle = getattr(doc_or_payload, "selectedBundle")

        declared_category = ""
        if hasattr(doc_or_payload, "product_category"):
            declared_category = str(doc_or_payload.product_category or "").lower().strip()
        elif isinstance(doc_or_payload, dict):
            declared_category = str(doc_or_payload.get("product_category") or doc_or_payload.get("productCategory") or "").lower().strip()
        elif hasattr(doc_or_payload, "productCategory"):
            declared_category = str(getattr(doc_or_payload, "productCategory") or "").lower().strip()

        all_reasons: List[str] = []
        has_biometric = False
        has_wahrms = False
        biometric_devices = 0
        extracted_licences: Optional[int] = None

        # 3. Check Authoritative Bundle Master in DB
        bundle_record = None
        if selected_bundle and db is not None:
            try:
                bundle_record = db.query(WAHRMSBundle).filter(
                    WAHRMSBundle.bundle_code == str(selected_bundle).strip()
                ).first()
            except Exception as e:
                logger.warning(f"Error checking WAHRMSBundle master: {e}")

        if bundle_record:
            bundle_cat = (bundle_record.category or "").upper().strip()
            if bundle_cat == "BIOMETRIC":
                has_biometric = True
                all_reasons.append(f"Authoritative Bundle Master records '{bundle_record.bundle_code}' as category 'BIOMETRIC'")
            elif bundle_cat == "WAHRMS":
                has_wahrms = True
                all_reasons.append(f"Authoritative Bundle Master records '{bundle_record.bundle_code}' as category 'WAHRMS'")
        else:
            # Fallback to known bundle dictionary
            norm_bcode = str(selected_bundle or "").lower().strip()
            if norm_bcode in cls.BIOMETRIC_BUNDLE_CODES:
                has_biometric = True
                all_reasons.append(f"Selected bundle '{norm_bcode}' is a known Biometric Hardware bundle")
            elif norm_bcode in cls.WAHRMS_BUNDLE_CODES:
                has_wahrms = True
                all_reasons.append(f"Selected bundle '{norm_bcode}' is a known WAHRMS Cloud bundle")

        # 4. Authoritative check on every line item
        for idx, itm in enumerate(line_items):
            is_item_bio, is_item_wahrms, reason = cls.classify_line_item(itm, db)
            desc = itm.get("description") or itm.get("name") or f"Item #{idx+1}"
            qty = int(itm.get("qty") or itm.get("quantity") or 1)

            if is_item_bio:
                has_biometric = True
                all_reasons.append(f"Line item #{idx+1} ('{desc[:40]}...'): {reason}")
                # Count physical terminal hardware (excluding pure installation/mounting services)
                is_service = any(kw in desc.lower() for kw in ["installation", "mounting", "calibration", "setup", "deployment", "technician support", "onsite service"])
                if not is_service and any(w in desc.lower() for w in ["terminal", "mb160", "machine", "device", "face scanner", "hardware device", "fingerprint reader"]):
                    biometric_devices += qty

            if is_item_wahrms:
                has_wahrms = True
                all_reasons.append(f"Line item #{idx+1} ('{desc[:40]}...'): {reason}")

            # Extract user licence count
            lic_match = re.search(r'(?:No\s+Of\s+onboardings?|onboardings?|licen[cs]es?|users?|employees?|staff)[:\s]+(\d+)', desc, re.I)
            if not lic_match:
                lic_match = re.search(r'(\d+)\s*(?:users?|employees?|onboardings?|licen[cs]es?)', desc, re.I)
            if lic_match:
                count = int(lic_match.group(1))
                if extracted_licences is None or count > extracted_licences:
                    extracted_licences = count

        # 5. Check declared category as safety net
        if declared_category == "biometric":
            has_biometric = True
            all_reasons.append("Document explicitly declared as Biometric category")

        # 6. Resolve final classification
        is_mixed = has_biometric and has_wahrms
        is_wahrms_only = has_wahrms and not has_biometric and declared_category != "biometric"

        if is_mixed:
            resolved_category = "MIXED"
            primary_reason = (
                "Document contains mixed WAHRMS software and Biometric products. "
                "Per business policy, mixed documents are strictly excluded from external website synchronization."
            )
        elif has_biometric:
            resolved_category = "BIOMETRIC"
            primary_reason = (
                "Document contains Biometric hardware or installation services. "
                "Biometric quotations and Proforma Invoices must remain exclusively within our CRM and are never transferred externally."
            )
        elif is_wahrms_only:
            resolved_category = "WAHRMS"
            primary_reason = "Document is verified WAHRMS-only and eligible for external website synchronization."
        else:
            # Fallback if no specific products could be parsed
            if declared_category == "wahrms":
                resolved_category = "WAHRMS"
                is_wahrms_only = True
                primary_reason = "Document is declared as WAHRMS software with no biometric items detected."
            else:
                resolved_category = "BIOMETRIC" if declared_category == "biometric" else "UNKNOWN"
                is_wahrms_only = False
                primary_reason = "Document category cannot be confirmed as WAHRMS-only. Blocked from external sync as safety measure."

        return ProductCategoryValidationResult(
            resolved_category=resolved_category,
            is_wahrms_only=is_wahrms_only,
            has_biometric=has_biometric,
            has_wahrms=has_wahrms,
            is_mixed=is_mixed,
            licence_count=extracted_licences,
            biometric_device_count=biometric_devices,
            reasons=all_reasons,
            primary_reason=primary_reason
        )

    @classmethod
    def is_eligible_for_external_sync(
        cls,
        doc_or_payload: Any,
        db: Optional[Session] = None
    ) -> Tuple[bool, str, ProductCategoryValidationResult]:
        """
        Convenience method: returns (is_eligible: bool, reason: str, validation_result).
        """
        res = cls.validate_document_products(doc_or_payload, db)
        return res.is_wahrms_only, res.primary_reason, res
