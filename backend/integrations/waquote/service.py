import logging
import httpx
import json
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session

from models.lead import Lead
from models.activity import LeadActivity
from models.integration import IntegrationLog
from integrations.waquote.config import WAQuoteConfig

logger = logging.getLogger("waquote_service")

class WAQuoteService:
    """
    REST Integration Service for WA Quote (Billing & Invoicing ERP).
    Connects to https://waquote.chnindia.com via x-api-key authentication.
    """

    @staticmethod
    def _get_headers(db: Optional[Session] = None) -> Dict[str, str]:
        api_key = WAQuoteConfig.get_api_key(db)
        return {
            "x-api-key": api_key,
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    @staticmethod
    def test_connection(db: Optional[Session] = None) -> Tuple[bool, str, Optional[str]]:
        """
        Tests connection to WA Quote REST API by fetching CRM summary metrics.
        """
        base_url = WAQuoteConfig.get_base_url(db)
        api_key = WAQuoteConfig.get_api_key(db)

        if not api_key:
            return False, "WA Quote API key is missing. Please configure it in Settings -> Integrations -> WA Quote.", None

        headers = WAQuoteService._get_headers(db)
        url = f"{base_url}/api/v1/crm/summary"

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    metrics = data.get("metrics") or data.get("data") or {}
                    fin = metrics.get("financials", {})
                    rev = fin.get("totalBilled") or metrics.get("totalRevenue", 0)
                    docs_cnt = metrics.get("quotations", {}).get("totalCount", 0)
                    return True, f"Connected to WA Quote ERP! Total Billed: Rs. {rev:,.0f} ({docs_cnt} quotations).", None
                elif resp.status_code in [401, 403]:
                    return False, "Invalid or unauthorized WA Quote API Key.", resp.text
                else:
                    return False, f"WA Quote returned HTTP {resp.status_code}.", resp.text
        except Exception as e:
            logger.error(f"WA Quote connection failed: {e}")
            return False, f"Failed to connect to WA Quote at {base_url}: {str(e)}", str(e)

    @staticmethod
    def get_summary(db: Optional[Session] = None, company_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetches aggregated financial summary metrics from WA Quote.
        """
        base_url = WAQuoteConfig.get_base_url(db)
        headers = WAQuoteService._get_headers(db)
        url = f"{base_url}/api/v1/crm/summary"
        params = {}
        if company_id:
            params["companyId"] = company_id

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url, headers=headers, params=params)
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(f"WA Quote get_summary returned status {resp.status_code}: {resp.text}")
                return {"ok": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            logger.error(f"Error fetching WA Quote summary: {e}")
            return {"ok": False, "error": str(e)}

    @staticmethod
    def get_documents(
        db: Optional[Session] = None,
        doc_type: str = "all",
        payment_status: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        Search and list billing documents from WA Quote.
        """
        base_url = WAQuoteConfig.get_base_url(db)
        headers = WAQuoteService._get_headers(db)
        url = f"{base_url}/api/v1/crm/documents"

        params: Dict[str, Any] = {
            "docType": doc_type or "all",
            "limit": limit,
            "page": page
        }
        if payment_status and payment_status != "all":
            params["paymentStatus"] = payment_status
        if status and status != "all":
            params["status"] = status
        if search:
            params["search"] = search

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url, headers=headers, params=params)
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(f"WA Quote get_documents returned status {resp.status_code}: {resp.text}")
                return {"ok": False, "documents": [], "pagination": {"total": 0}}
        except Exception as e:
            logger.error(f"Error fetching WA Quote documents: {e}")
            return {"ok": False, "documents": [], "error": str(e)}

    @staticmethod
    def get_document_by_id(db: Optional[Session] = None, doc_id: str = "") -> Optional[Dict[str, Any]]:
        """
        Fetches a single document by Firestore ID or human-readable number (e.g. CHN/QT/2627/0001).
        """
        base_url = WAQuoteConfig.get_base_url(db)
        headers = WAQuoteService._get_headers(db)
        url = f"{base_url}/api/v1/crm/documents/{doc_id}"

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("document")
                return None
        except Exception as e:
            logger.error(f"Error fetching WA Quote doc {doc_id}: {e}")
            return None

    @staticmethod
    def get_lead_documents(db: Session, lead: Lead) -> List[Dict[str, Any]]:
        """
        Finds all WA Quote documents matching the lead by phone, email, or customer name.
        """
        matched_docs: Dict[str, Dict[str, Any]] = {}

        # 1. Search by phone number (strip spaces/plus to maximize matching)
        search_terms = []
        if lead.phone:
            clean_phone = lead.phone.replace("+", "").replace(" ", "").replace("-", "").strip()
            if len(clean_phone) >= 10:
                search_terms.append(clean_phone[-10:])
            search_terms.append(lead.phone.strip())

        if lead.email and "@" in lead.email:
            search_terms.append(lead.email.strip())

        if lead.name and len(lead.name.strip()) >= 3:
            search_terms.append(lead.name.strip())

        for term in search_terms:
            res = WAQuoteService.get_documents(db, search=term, limit=20)
            for doc in res.get("documents", []):
                doc_id = doc.get("id") or doc.get("number")
                if doc_id and doc_id not in matched_docs:
                    matched_docs[doc_id] = doc

        return list(matched_docs.values())

    @staticmethod
    def sync_lead_quotation_status(
        db: Session,
        lead: Lead,
        target_doc_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Syncs quotation and invoice status from WA Quote directly onto the CRM Lead.
        """
        doc = None
        if target_doc_id:
            doc = WAQuoteService.get_document_by_id(db, target_doc_id)

        if not doc and lead.quotetask_quotation_number:
            doc = WAQuoteService.get_document_by_id(db, lead.quotetask_quotation_number)

        if not doc and lead.quotetask_quotation_id:
            doc = WAQuoteService.get_document_by_id(db, lead.quotetask_quotation_id)

        if not doc:
            # Search by phone / name
            docs = WAQuoteService.get_lead_documents(db, lead)
            if docs:
                # Prefer latest quotation or proforma
                doc = docs[0]

        if not doc:
            return {
                "success": False,
                "message": f"No matching documents found in WA Quote for {lead.name} ({lead.phone}).",
                "lead_id": lead.id
            }

        # Map document details
        doc_id = doc.get("id") or ""
        doc_number = doc.get("number") or ""
        doc_status = (doc.get("status") or "ISSUED").upper()
        financials = doc.get("financials") or {}
        grand_total = float(financials.get("grandTotal") or doc.get("grandTotal") or 0.0)
        drive_url = doc.get("driveUrl") or doc.get("pdfUrl") or f"https://waquote.chnindia.com"

        payment_info = doc.get("payment") or {}
        payment_status = (payment_info.get("status") or doc.get("paymentStatus") or "UNPAID").upper()

        now = datetime.utcnow()
        lead.quotetask_quotation_id = str(doc_id)
        lead.quotetask_quotation_number = str(doc_number)
        lead.quotetask_quotation_status = doc_status
        lead.quotetask_quotation_amount = grand_total
        lead.quotetask_quotation_url = drive_url
        lead.quotetask_po_number = str(doc.get("docType") or "QUOTATION").upper()
        lead.quotetask_po_status = payment_status
        lead.quotetask_synced_at = now

        # If quotation converted/paid, advance lead status if appropriate
        if payment_status == "PAID" and lead.status not in ["CONVERTED", "WON"]:
            lead.status = "CONVERTED"

        activity = LeadActivity(
            lead_id=lead.id,
            performed_by=None,
            activity_type="WAQUOTE_SYNCED",
            description=f"Synced with WA Quote {doc.get('docType', 'doc').upper()} #{doc_number}: Amount Rs. {grand_total:,.2f} | Status: {doc_status} | Payment: {payment_status}",
            created_at=now
        )
        db.add(activity)
        db.commit()
        db.refresh(lead)

        return {
            "success": True,
            "message": f"Synced document #{doc_number} from WA Quote.",
            "quotation_id": lead.quotetask_quotation_id,
            "quotation_number": lead.quotetask_quotation_number,
            "quotation_status": lead.quotetask_quotation_status,
            "quotation_amount": lead.quotetask_quotation_amount,
            "quotation_url": lead.quotetask_quotation_url,
            "payment_status": lead.quotetask_po_status,
            "doc_type": lead.quotetask_po_number
        }
