import logging
import httpx
import datetime
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session
from models.lead import Lead
from models.activity import LeadActivity
from models.meta_page import MetaPage
from services.reinquiry_service import ReInquiryService
from .config import MetaConfig
from .crypto import encrypt_token, decrypt_token, mask_token

logger = logging.getLogger("meta_integration")

# In-memory tracking for last webhook received & last sync time
_last_webhook_received: Optional[datetime.datetime] = None
_last_sync: Optional[datetime.datetime] = None

class MetaLeadService:
    """
    Service layer handling Meta Lead Ads Graph API communication,
    multi-page token management, lead extraction, duplicate prevention, and DB persistence.
    """

    @staticmethod
    def get_last_webhook_time() -> Optional[str]:
        return _last_webhook_received.isoformat() if _last_webhook_received else None

    @staticmethod
    def get_last_sync_time() -> Optional[str]:
        return _last_sync.isoformat() if _last_sync else None

    @staticmethod
    def get_page_by_id(db: Session, page_id: str) -> Optional[MetaPage]:
        """
        Finds a connected Meta Page record by Facebook Page ID.
        """
        if not page_id:
            return None
        return db.query(MetaPage).filter(MetaPage.page_id == str(page_id).strip()).first()

    @staticmethod
    def get_all_pages(db: Session) -> List[MetaPage]:
        """
        Retrieves all configured Meta Pages ordered by last updated.
        """
        return db.query(MetaPage).order_by(MetaPage.created_at.desc()).all()

    @staticmethod
    def verify_page_token(page_id: str, access_token: str, version: Optional[str] = None) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Calls Meta Graph API to verify that the provided Page Access Token is valid
        for the given Page ID, and retrieves page name/category.
        Endpoint: GET https://graph.facebook.com/{version}/{page_id}?fields=id,name,category&access_token={token}
        """
        ver = version or MetaConfig.get_api_version()
        url = f"https://graph.facebook.com/{ver}/{page_id}"
        params = {
            "fields": "id,name,category",
            "access_token": access_token.strip()
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    return True, data, None
                else:
                    err_json = resp.json()
                    err_msg = err_json.get("error", {}).get("message", f"HTTP {resp.status_code}")
                    return False, {}, err_msg
        except Exception as e:
            logger.error(f"Error verifying Meta Page token for page {page_id}: {e}")
            return False, {}, str(e)

    @staticmethod
    def connect_or_add_page(
        db: Session,
        page_id: str,
        access_token: str,
        page_name: Optional[str] = None
    ) -> Tuple[bool, str, Optional[MetaPage], Optional[str]]:
        """
        Connects a new Facebook Page or updates existing page token.
        Encrypted Page Access Token is stored in meta_pages table.
        """
        clean_id = str(page_id).strip()
        clean_token = str(access_token).strip()

        if not clean_id or not clean_token:
            return False, "Page ID and Page Access Token are required.", None, "Missing fields"

        # Verify token against Graph API
        is_valid, page_info, err_msg = MetaLeadService.verify_page_token(clean_id, clean_token)
        verified_name = page_info.get("name") or (page_name.strip() if page_name else f"Facebook Page #{clean_id[-4:]}")
        category = page_info.get("category")

        encrypted_tok = encrypt_token(clean_token)
        now = datetime.datetime.utcnow()

        existing = db.query(MetaPage).filter(MetaPage.page_id == clean_id).first()
        if existing:
            existing.page_name = verified_name
            existing.encrypted_access_token = encrypted_tok
            existing.status = "CONNECTED" if is_valid else "ERROR"
            existing.error_message = None if is_valid else (err_msg or "Token verification failed")
            existing.last_synced_at = now
            if category:
                existing.category = category
            db.commit()
            db.refresh(existing)
            msg = f"Page '{existing.page_name}' updated and connected successfully!" if is_valid else f"Page updated with warnings: {err_msg}"
            return is_valid, msg, existing, err_msg
        else:
            new_page = MetaPage(
                page_id=clean_id,
                page_name=verified_name,
                encrypted_access_token=encrypted_tok,
                status="CONNECTED" if is_valid else "ERROR",
                category=category,
                lead_count=0,
                last_synced_at=now,
                error_message=None if is_valid else (err_msg or "Token verification failed"),
                created_at=now,
                updated_at=now
            )
            db.add(new_page)
            db.commit()
            db.refresh(new_page)
            msg = f"Page '{new_page.page_name}' connected successfully!" if is_valid else f"Page saved with warnings: {err_msg}"
            return is_valid, msg, new_page, err_msg

    @staticmethod
    def sync_page(db: Session, page_id: str) -> Tuple[bool, str, Optional[MetaPage], Optional[str]]:
        """
        Synchronizes / tests connection for a specific Page using its encrypted token.
        """
        page = MetaLeadService.get_page_by_id(db, page_id)
        if not page:
            return False, f"Page ID '{page_id}' not found.", None, "Not found"

        token = decrypt_token(page.encrypted_access_token)
        if not token:
            page.status = "ERROR"
            page.error_message = "No access token configured."
            db.commit()
            return False, "Page access token is missing or corrupted.", page, "Empty token"

        is_valid, page_info, err_msg = MetaLeadService.verify_page_token(page.page_id, token)
        now = datetime.datetime.utcnow()
        page.last_synced_at = now

        if is_valid:
            if page_info.get("name"):
                page.page_name = page_info["name"]
            if page_info.get("category"):
                page.category = page_info["category"]
            page.status = "CONNECTED"
            page.error_message = None
            db.commit()
            db.refresh(page)
            return True, f"Page '{page.page_name}' synced successfully with Meta Graph API!", page, None
        else:
            page.status = "ERROR"
            page.error_message = err_msg or "Graph API rejected Page Access Token"
            db.commit()
            db.refresh(page)
            return False, f"Sync failed for '{page.page_name}': {err_msg}", page, err_msg

    @staticmethod
    def disconnect_page(db: Session, page_id: str) -> Tuple[bool, str, Optional[MetaPage]]:
        """
        Disconnects a Page (pauses lead retrieval).
        """
        page = MetaLeadService.get_page_by_id(db, page_id)
        if not page:
            return False, f"Page ID '{page_id}' not found.", None

        page.status = "DISCONNECTED"
        page.updated_at = datetime.datetime.utcnow()
        db.commit()
        db.refresh(page)
        return True, f"Page '{page.page_name}' has been disconnected.", page

    @staticmethod
    def reconnect_page(db: Session, page_id: str) -> Tuple[bool, str, Optional[MetaPage]]:
        """
        Re-enables a disconnected Page.
        """
        page = MetaLeadService.get_page_by_id(db, page_id)
        if not page:
            return False, f"Page ID '{page_id}' not found.", None

        page.status = "CONNECTED"
        page.updated_at = datetime.datetime.utcnow()
        db.commit()
        db.refresh(page)
        return True, f"Page '{page.page_name}' is now active and connected.", page

    @staticmethod
    def refresh_page(
        db: Session,
        page_id: str,
        new_access_token: Optional[str] = None
    ) -> Tuple[bool, str, Optional[MetaPage], Optional[str]]:
        """
        Refreshes a Page configuration, optionally replacing the Page Access Token.
        """
        page = MetaLeadService.get_page_by_id(db, page_id)
        if not page:
            return False, f"Page ID '{page_id}' not found.", None, "Not found"

        token_to_use = new_access_token.strip() if new_access_token and new_access_token.strip() else decrypt_token(page.encrypted_access_token)
        if new_access_token and new_access_token.strip():
            page.encrypted_access_token = encrypt_token(token_to_use)

        is_valid, page_info, err_msg = MetaLeadService.verify_page_token(page.page_id, token_to_use)
        now = datetime.datetime.utcnow()
        page.last_synced_at = now
        page.updated_at = now

        if is_valid:
            if page_info.get("name"):
                page.page_name = page_info["name"]
            if page_info.get("category"):
                page.category = page_info["category"]
            page.status = "CONNECTED"
            page.error_message = None
            db.commit()
            db.refresh(page)
            return True, f"Page '{page.page_name}' token refreshed and verified!", page, None
        else:
            page.status = "ERROR"
            page.error_message = err_msg or "Failed to verify new Page Access Token"
            db.commit()
            db.refresh(page)
            return False, f"Refresh verification failed: {err_msg}", page, err_msg

    @staticmethod
    def delete_page(db: Session, page_id: str) -> bool:
        """
        Deletes a connected Page configuration.
        """
        page = MetaLeadService.get_page_by_id(db, page_id)
        if not page:
            return False
        db.delete(page)
        db.commit()
        return True

    @staticmethod
    def fetch_lead_details_from_graph_api(leadgen_id: str, access_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Uses Meta Graph API to fetch full lead payload for a given leadgen_id
        using the specified Page Access Token (or env fallback).
        Endpoint: GET https://graph.facebook.com/{version}/{leadgen_id}
        """
        token = access_token or MetaConfig.get_access_token()
        version = MetaConfig.get_api_version()

        if not token:
            logger.warning(f"No access token available to fetch leadgen {leadgen_id}")
            return {}

        url = f"https://graph.facebook.com/{version}/{leadgen_id}"
        params = {"access_token": token}

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch lead {leadgen_id} from Meta Graph API: {e}")
            return {}

    @staticmethod
    def parse_field_data(raw_meta_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Parses Meta's field_data array into standard key-value dictionary.
        Handles variations like 'full_name', 'first_name', 'phone_number', 'email'.
        """
        parsed = {
            "name": "Meta Lead User",
            "phone": "",
            "email": "",
            "company": "",
            "city": ""
        }

        field_data = raw_meta_data.get("field_data", [])
        first_name = ""
        last_name = ""

        for item in field_data:
            name_key = (item.get("name") or "").lower()
            values = item.get("values", [])
            val = values[0] if values else ""

            if name_key in ["full_name", "full name", "name"]:
                parsed["name"] = val
            elif name_key in ["first_name", "first name"]:
                first_name = val
            elif name_key in ["last_name", "last name"]:
                last_name = val
            elif name_key in ["phone_number", "phone number", "phone"]:
                parsed["phone"] = val
            elif name_key in ["email", "email address", "work email"]:
                parsed["email"] = val
            elif name_key in ["company_name", "company name", "company"]:
                parsed["company"] = val
            elif name_key in ["city", "location"]:
                parsed["city"] = val

        if first_name or last_name:
            parsed["name"] = f"{first_name} {last_name}".strip()

        return parsed

    @staticmethod
    def process_and_save_meta_lead(
        db: Session,
        leadgen_id: str,
        form_id: Optional[str] = None,
        page_id: Optional[str] = None,
        mock_payload: Optional[Dict[str, Any]] = None
    ) -> Lead:
        """
        Ingests a Meta leadgen event:
        1. Identifies the specific Page ID.
        2. Retrieves and decrypts that Page's Access Token.
        3. Uses that Page's token to fetch complete lead details from Meta Graph API.
        4. Checks for duplicate leadgen_id.
        5. Registers via ReInquiryService and updates Page statistics.
        """
        global _last_webhook_received, _last_sync
        now = datetime.datetime.utcnow()
        _last_webhook_received = now

        # 1. Duplicate Prevention Check using meta_lead_id
        existing_lead = db.query(Lead).filter(Lead.meta_lead_id == leadgen_id).first()
        if existing_lead:
            logger.info(f"Duplicate Meta lead skipped. meta_lead_id={leadgen_id} already exists (Lead ID: {existing_lead.id}).")
            return existing_lead

        # 2. Identify the connected Page and its decrypted token
        page_token = None
        page_name = "Meta Page"
        meta_page = MetaLeadService.get_page_by_id(db, page_id) if page_id else None

        if meta_page:
            page_name = meta_page.page_name
            page_token = decrypt_token(meta_page.encrypted_access_token)
            meta_page.lead_count = (meta_page.lead_count or 0) + 1
            meta_page.last_webhook_at = now
            if meta_page.status == "DISCONNECTED":
                logger.warning(f"Received leadgen for DISCONNECTED Page: '{page_name}' (ID: {page_id}).")
        else:
            logger.warning(f"No configured Meta Page found for Page ID '{page_id}'. Falling back to default token.")

        # 3. Retrieve details from Graph API using the Page's specific token
        raw_meta = mock_payload or MetaLeadService.fetch_lead_details_from_graph_api(
            leadgen_id=leadgen_id,
            access_token=page_token
        )
        parsed = MetaLeadService.parse_field_data(raw_meta)

        # Fallback values if API is unavailable or in mock test mode
        name = parsed["name"] or f"Meta Lead #{leadgen_id[-6:]}"
        phone = parsed["phone"] or (f"+9198{leadgen_id[-8:]}" if len(leadgen_id) >= 8 else "+919876543210")
        email = parsed["email"] or f"lead_{leadgen_id}@meta-leads.com"

        # 4. Process via ReInquiryService
        campaign_title = f"Meta Ads ({page_name})" if meta_page else (f"Meta Form #{form_id}" if form_id else "Meta Ads Campaign")
        enquiry_data = {
            "meta_lead_id": leadgen_id,
            "meta_form_id": form_id,
            "name": name,
            "phone": phone,
            "email": email,
            "company": parsed["company"] or None,
            "city": parsed["city"] or None,
            "source": "META",
            "campaign_name": campaign_title,
            "requirement_notes": f"Captured via Meta Lead Ads Webhook.\nPage: {page_name} (ID: {page_id or 'N/A'})\nForm ID: {form_id or 'N/A'}"
        }

        lead, is_reinquiry, enq = ReInquiryService.register_enquiry(
            db=db,
            enquiry_data=enquiry_data,
            creator_emp_id=None,
            creator_name=f"Meta Ads ({page_name})",
            commit=True
        )

        _last_sync = datetime.datetime.utcnow()
        logger.info(f"Successfully processed Meta lead! ID: {lead.id}, Name: {lead.name}, Page: {page_name}, is_reinquiry: {is_reinquiry}")
        return lead
