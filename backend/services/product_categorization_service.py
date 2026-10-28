"""
Product Categorization Service for Wa CRM.
Provides automatic product classification, suggestion, and persistence logic across leads,
calls, enquiries, and quotations.

Categories:
- BIOMETRIC: Physical biometric devices, fingerprint scanners, facial terminals, attendance hardware, etc.
- WAHRMS: Cloud HRMS software, payroll modules, employee self-service, leave/attendance software.
- UNCLASSIFIED: Unknown, ambiguous, or no signals detected.
"""

import re
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from models.lead import Lead
from models.call_log import CallLog

logger = logging.getLogger("product_categorization_service")

# Keywords for Biometric Hardware
BIOMETRIC_KEYWORDS = [
    r"biometric",
    r"fingerprint",
    r"face\s*scanner",
    r"facial\s*recognition",
    r"mb160",
    r"zkteco",
    r"attendance\s*machine",
    r"attendance\s*terminal",
    r"hardware\s*terminal",
    r"rfid",
    r"access\s*control",
    r"card\s*reader",
    r"punching\s*machine",
    r"device",
    r"hardware"
]

# Keywords for WAHRMS Software
WAHRMS_KEYWORDS = [
    r"wahrms",
    r"hrms",
    r"payroll",
    r"hr\s*software",
    r"leave\s*management",
    r"salary\s*calculation",
    r"payslip",
    r"employee\s*portal",
    r"saas",
    r"cloud\s*hr",
    r"recruitment",
    r"performance\s*management",
    r"software\s*subscription",
    r"licence",
    r"license"
]


class ProductCategorizationService:

    @staticmethod
    def detect_category_from_text(text: Optional[str]) -> str:
        """
        Analyzes free text (notes, requirements, campaign names, form titles, etc.)
        and returns 'BIOMETRIC', 'WAHRMS', or 'UNCLASSIFIED'.
        """
        if not text or not isinstance(text, str):
            return "UNCLASSIFIED"

        clean_text = text.lower()

        bio_score = 0
        for pattern in BIOMETRIC_KEYWORDS:
            matches = re.findall(pattern, clean_text)
            bio_score += len(matches)

        wahrms_score = 0
        for pattern in WAHRMS_KEYWORDS:
            matches = re.findall(pattern, clean_text)
            wahrms_score += len(matches)

        if bio_score > 0 and wahrms_score == 0:
            return "BIOMETRIC"
        elif wahrms_score > 0 and bio_score == 0:
            return "WAHRMS"
        elif bio_score > 0 and wahrms_score > 0:
            # If both, choose the stronger signal or WAHRMS if equal
            return "BIOMETRIC" if bio_score > wahrms_score else "WAHRMS"

        return "UNCLASSIFIED"

    @staticmethod
    def suggest_category_for_lead(lead: Optional[Lead], additional_text: Optional[str] = None) -> Dict[str, Any]:
        """
        Suggests product category for a lead:
        - If lead already has a manually confirmed category, returns that confirmed category.
        - Otherwise, evaluates lead's requirement notes, campaign name, previous notes, enquiries, and additional_text.
        - Falls back to 'UNCLASSIFIED' if ambiguous or unknown.
        """
        if not lead:
            detected = ProductCategorizationService.detect_category_from_text(additional_text)
            return {
                "suggested_category": detected,
                "is_confirmed": False,
                "source": "TEXT_ANALYSIS"
            }

        # 1. If manually confirmed previously, preserve it!
        if lead.product_category_confirmed and lead.product_category in ["BIOMETRIC", "WAHRMS"]:
            return {
                "suggested_category": lead.product_category,
                "is_confirmed": True,
                "source": "MANUAL_CONFIRMED"
            }

        # 2. If lead has an existing unconfirmed category, use it if not UNCLASSIFIED
        if lead.product_category in ["BIOMETRIC", "WAHRMS"]:
            return {
                "suggested_category": lead.product_category,
                "is_confirmed": False,
                "source": "LEAD_RECORD"
            }

        # 3. Detect from lead metadata & notes
        signals = [
            lead.requirement_notes or "",
            lead.campaign_name or "",
            lead.source or "",
            additional_text or ""
        ]

        # Check latest enquiry notes if available
        if hasattr(lead, "enquiries") and lead.enquiries:
            for enq in lead.enquiries:
                signals.append(enq.requirement_notes or "")
                signals.append(enq.campaign_name or "")

        combined_text = " ".join(signals)
        detected = ProductCategorizationService.detect_category_from_text(combined_text)

        return {
            "suggested_category": detected,
            "is_confirmed": False,
            "source": "AUTOMATIC_DETECTION"
        }

    @staticmethod
    def save_lead_category(
        db: Session,
        lead_id: int,
        category: str,
        is_manual_confirmation: bool = True,
        call_id: Optional[str] = None
    ) -> Optional[Lead]:
        """
        Saves category to Lead and optionally syncs to CallLog.
        If employee manually confirms or changes the category, sets product_category_confirmed = True.
        """
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            return None

        clean_cat = category.strip().upper() if category else "UNCLASSIFIED"
        if clean_cat not in ["BIOMETRIC", "WAHRMS", "UNCLASSIFIED"]:
            clean_cat = "UNCLASSIFIED"

        lead.product_category = clean_cat
        if is_manual_confirmation and clean_cat in ["BIOMETRIC", "WAHRMS"]:
            lead.product_category_confirmed = True

        # Sync to CallLog if call_id provided
        if call_id:
            call_log = db.query(CallLog).filter(
                (CallLog.provider_call_id == call_id) | (CallLog.id == call_id)
            ).first()
            if call_log:
                call_log.product_category = clean_cat

        db.commit()
        db.refresh(lead)
        return lead
