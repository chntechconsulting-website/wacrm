import os
import logging
import httpx
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session

from models.quotation import Quotation
from models.customer import Customer
from models.lead import Lead
from models.activity import LeadActivity
from models.integration import IntegrationConfig, IntegrationLog
from integrations.waquote.config import WAQuoteConfig
from services.product_validation_service import ProductValidationService

logger = logging.getLogger("destination_sync_service")

class DestinationSyncService:
    """
    Secure Server-to-Server synchronization service between Wa CRM and
    the destination Billing / ERP system (WA Quote ERP).
    
    Synchronizes:
    - Client / Customer profiles (Idempotent reuse via external_client_id or business identifiers)
    - Proforma Invoices (Line items, taxes, totals, and quotation references)
    """

    @staticmethod
    def get_credentials(db: Optional[Session] = None) -> Tuple[str, str, str]:
        """
        Retrieves destination ERP base URL, API key, and company ID.
        Checks environment variables first, then database IntegrationConfig.
        """
        # 1. Environment variables
        env_base_url = os.getenv("DESTINATION_ERP_BASE_URL") or os.getenv("WAQUOTE_BASE_URL")
        env_api_key = os.getenv("DESTINATION_ERP_API_KEY") or os.getenv("WAQUOTE_API_KEY")
        env_company_id = os.getenv("DESTINATION_ERP_COMPANY_ID") or os.getenv("WAQUOTE_COMPANY_ID")

        if env_base_url and env_api_key:
            return (
                env_base_url.rstrip("/"),
                env_api_key.strip(),
                (env_company_id or "chnindia").strip()
            )

        # 2. Database IntegrationConfig
        if db:
            try:
                cfg = db.query(IntegrationConfig).filter(
                    IntegrationConfig.integration_type.in_(["WAQUOTE", "DESTINATION_ERP", "QUOTETASK"])
                ).first()
                if cfg and getattr(cfg, "config_data", None):
                    cdata = json.loads(cfg.config_data)
                    db_url = cdata.get("base_url") or cdata.get("api_url")
                    db_key = cdata.get("api_key")
                    db_company = cdata.get("company_id")
                    if db_url and db_key:
                        return db_url.rstrip("/"), db_key.strip(), (db_company or "chnindia").strip()
            except Exception as e:
                logger.warning(f"Error parsing integration config from DB: {e}")

        # 3. Fallbacks from WAQuoteConfig
        fallback_url = WAQuoteConfig.get_base_url(db)
        fallback_key = WAQuoteConfig.get_api_key(db)
        return fallback_url.rstrip("/"), fallback_key.strip(), "chnindia"

    @staticmethod
    def _get_headers(api_key: str) -> Dict[str, str]:
        return {
            "x-api-key": api_key,
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "WaCRM-Server-Sync/1.0"
        }

    @staticmethod
    def _sanitize_error(error_str: str) -> str:
        """Strip sensitive tokens or passwords from error strings before logging / storing."""
        if not error_str:
            return "Unknown error occurred during synchronization."
        clean = str(error_str)
        # Redact any tokens/keys
        for token_prefix in ["ed_live_", "Bearer ", "key="]:
            if token_prefix in clean:
                parts = clean.split(token_prefix)
                clean = parts[0] + token_prefix + "[REDACTED]"
        return clean[:500]

    @staticmethod
    def find_or_create_client(
        db: Session,
        proforma: Quotation,
        client: httpx.Client,
        base_url: str,
        headers: Dict[str, str]
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Finds the corresponding client in destination ERP using:
        1. Existing mapped customer.external_client_id
        2. Business identifier lookup (GSTIN, Phone, Email, Company Name)
        3. If not found, creates the client in destination ERP via API.
        
        Returns: (external_client_id, error_message)
        """
        # Step 1: Check existing local customer mapping
        linked_customer = None
        if proforma.customer_id:
            linked_customer = db.query(Customer).filter(Customer.id == proforma.customer_id).first()
            if linked_customer and linked_customer.external_client_id:
                logger.info(f"Reusing existing mapped external client ID {linked_customer.external_client_id} for Customer #{linked_customer.id}")
                return linked_customer.external_client_id, None

        if proforma.external_client_id:
            logger.info(f"Reusing external client ID {proforma.external_client_id} stored on Proforma #{proforma.doc_number}")
            return proforma.external_client_id, None

        # Step 2: Search in destination ERP by unique identifiers (GSTIN, Phone, Email)
        search_terms = []
        if proforma.gstin and len(proforma.gstin.strip()) >= 5:
            search_terms.append(proforma.gstin.strip())
        if proforma.phone and len(proforma.phone.strip()) >= 10:
            clean_phone = proforma.phone.replace("+", "").replace(" ", "").replace("-", "").strip()
            search_terms.append(clean_phone[-10:])
        if proforma.email and "@" in proforma.email:
            search_terms.append(proforma.email.strip().lower())

        found_client_id = None

        for term in search_terms:
            try:
                # First try documented customers search endpoint
                resp = client.get(f"{base_url}/api/v1/crm/customers", headers=headers, params={"search": term, "limit": 5})
                if resp.status_code == 200:
                    data = resp.json()
                    customers_list = data.get("customers") or data.get("data") or []
                    if isinstance(customers_list, list) and len(customers_list) > 0:
                        found_client_id = str(customers_list[0].get("id") or customers_list[0].get("customerId"))
                        if found_client_id:
                            logger.info(f"Matched client in destination ERP: {found_client_id} via term '{term}'")
                            break
            except Exception as e:
                logger.debug(f"Search term '{term}' lookup check returned error: {e}")

        # If still not found, check existing documents by search term to discover client ID
        if not found_client_id:
            for term in search_terms:
                try:
                    resp = client.get(f"{base_url}/api/v1/crm/documents", headers=headers, params={"search": term, "limit": 5})
                    if resp.status_code == 200:
                        data = resp.json()
                        docs = data.get("documents") or []
                        for d in docs:
                            cust_obj = d.get("customer") or {}
                            cid = cust_obj.get("customerId") or cust_obj.get("id") or d.get("customerId")
                            if cid:
                                found_client_id = str(cid)
                                break
                    if found_client_id:
                        break
                except Exception:
                    pass

        if found_client_id:
            # Save mapping to local customer if linked
            if linked_customer:
                linked_customer.external_client_id = found_client_id
                linked_customer.destination_synced_at = datetime.utcnow()
                db.commit()
            return found_client_id, None

        # Step 3: Create new client in destination ERP
        client_payload = {
            "name": proforma.customer_name.strip(),
            "companyName": (proforma.company_name or proforma.customer_name).strip(),
            "email": (proforma.email or "").strip().lower(),
            "phone": (proforma.phone or "").strip(),
            "gstin": (proforma.gstin or "").strip().upper(),
            "billingAddress": {
                "line1": proforma.address or "Address on file",
                "state": proforma.state or "Tamil Nadu",
                "stateCode": proforma.state_code or "33",
                "country": "India"
            },
            "shippingAddress": {
                "line1": proforma.address or "Address on file",
                "state": proforma.state or "Tamil Nadu",
                "stateCode": proforma.state_code or "33",
                "country": "India"
            },
            "shippingSameAsBilling": True,
            "notes": f"Created via Wa CRM Sync from Proforma #{proforma.doc_number}"
        }

        try:
            resp = client.post(f"{base_url}/api/v1/crm/customers", headers=headers, json=client_payload)
            if resp.status_code in [200, 201]:
                res_data = resp.json()
                created_id = str(
                    res_data.get("id") or 
                    res_data.get("customerId") or 
                    (res_data.get("customer") or {}).get("id") or
                    (res_data.get("data") or {}).get("id")
                )
                if created_id and created_id != "None":
                    logger.info(f"Successfully registered client #{created_id} in destination ERP.")
                    if linked_customer:
                        linked_customer.external_client_id = created_id
                        linked_customer.destination_synced_at = datetime.now(timezone.utc)
                        db.commit()
                    return created_id, None
            
            # If endpoint returned 404/501 (missing in remote ERP), synthesize fallback identifier with customer hash
            if resp.status_code in [404, 501, 503]:
                err_text = f"Destination ERP client creation endpoint returned HTTP {resp.status_code}: {resp.text}"
                return None, err_text
            else:
                return None, f"Destination ERP rejected client creation (HTTP {resp.status_code}): {resp.text}"
        except Exception as e:
            logger.error(f"Failed to call client creation API: {e}")
            return None, f"Client creation connection failed: {str(e)}"

    @staticmethod
    def sync_proforma_to_destination(
        db: Session,
        proforma_id: int,
        force_retry: bool = False
    ) -> Dict[str, Any]:
        """
        Executes server-to-server synchronization of a Proforma Invoice to the destination ERP.
        Enforces idempotency, tracks status, updates MySQL, and never deletes/invalidates the local document on failure.
        """
        proforma = db.query(Quotation).filter(Quotation.id == proforma_id).first()
        if not proforma:
            return {"success": False, "error": f"Proforma document #{proforma_id} not found."}

        # Validate that document is indeed a proforma
        if proforma.doc_type != "proforma":
            return {"success": False, "error": f"Document #{proforma.doc_number} is of type '{proforma.doc_type}', not 'proforma'."}

        # -------------------------------------------------------------
        # STRICT PRODUCT-CATEGORY FILTERING:
        # Only 100% WAHRMS documents may be synchronized to the external website.
        # Biometric and mixed documents must remain exclusively within our CRM.
        # -------------------------------------------------------------
        is_eligible, block_reason, val_result = ProductValidationService.is_eligible_for_external_sync(proforma, db)
        if not is_eligible:
            logger.info(
                f"Proforma #{proforma.doc_number} (ID: {proforma.id}) is BLOCKED from external sync. "
                f"Category: {val_result.resolved_category}. Reason: {block_reason}"
            )
            # Mark integration as NOT_APPLICABLE and do NOT enqueue/send external transfer
            now_utc = datetime.now(timezone.utc)
            proforma.destination_sync_status = "NOT_APPLICABLE"
            proforma.destination_sync_error = None
            proforma.destination_sync_response = {
                "eligible": False,
                "status": "NOT_APPLICABLE",
                "resolved_category": val_result.resolved_category,
                "has_biometric": val_result.has_biometric,
                "has_wahrms": val_result.has_wahrms,
                "is_mixed": val_result.is_mixed,
                "biometric_device_count": val_result.biometric_device_count,
                "licence_count": val_result.licence_count,
                "reason": block_reason,
                "reasons_detail": val_result.reasons,
                "evaluated_at": now_utc.isoformat()
            }
            db.commit()

            DestinationSyncService._log_event(
                db=db,
                event_type="PROFORMA_SYNC_EXCLUDED_BIOMETRIC",
                status="NOT_APPLICABLE",
                message=f"Proforma #{proforma.doc_number} excluded from external sync ({val_result.resolved_category}). {block_reason}"
            )

            return {
                "ok": True,
                "success": True,
                "status": "NOT_APPLICABLE",
                "sync_status": "NOT_APPLICABLE",
                "skipped": True,
                "eligible": False,
                "product_category": val_result.resolved_category,
                "has_biometric": val_result.has_biometric,
                "is_mixed": val_result.is_mixed,
                "reason": block_reason,
                "message": f"Biometric document #{proforma.doc_number} is excluded from external website synchronization (Status: NOT_APPLICABLE)."
            }

        # Deterministic Idempotency Key based on local WAHRMS Proforma ID and document number
        idempotency_key = f"CRM-PROFORMA-{proforma.id}-{proforma.doc_number.replace('/', '-')}"

        # Idempotency check: if already SYNCED and has external ID, return without duplicate API call
        if proforma.destination_sync_status == "SYNCED" and proforma.external_proforma_id and not force_retry:
            logger.info(f"Proforma #{proforma.doc_number} is already synced to ERP (External ID: {proforma.external_proforma_id}). Skipping duplicate sync.")
            return {
                "ok": True,
                "success": True,
                "status": "SYNCED",
                "skipped": True,
                "already_synced": True,
                "sync_status": "SYNCED",
                "idempotency_key": idempotency_key,
                "external_client_id": proforma.external_client_id,
                "external_proforma_id": proforma.external_proforma_id,
                "synced_at": proforma.destination_synced_at.isoformat() if proforma.destination_synced_at else None,
                "message": f"Proforma #{proforma.doc_number} is already synced to destination ERP."
            }

        proforma.destination_sync_attempts = (proforma.destination_sync_attempts or 0) + 1
        db.commit()

        base_url, api_key, company_id = DestinationSyncService.get_credentials(db)

        if not api_key or not base_url:
            error_msg = "Destination ERP API credentials not configured. Please set DESTINATION_ERP_BASE_URL and DESTINATION_ERP_API_KEY."
            proforma.destination_sync_status = "FAILED"
            proforma.destination_sync_error = error_msg
            db.commit()
            return {"success": False, "error": error_msg}

        headers = DestinationSyncService._get_headers(api_key)
        # Attach authoritative idempotency key to prevent any duplicate creation on retry
        headers["Idempotency-Key"] = idempotency_key
        headers["X-Idempotency-Key"] = idempotency_key

        try:
            with httpx.Client(timeout=15.0) as client:
                # 1. Test connectivity first or attempt client resolution
                external_client_id, client_err = DestinationSyncService.find_or_create_client(
                    db=db,
                    proforma=proforma,
                    client=client,
                    base_url=base_url,
                    headers=headers
                )

                if not external_client_id:
                    error_msg = f"Client sync failed: {client_err or 'Could not find or create client in destination ERP.'}"
                    proforma.destination_sync_status = "FAILED"
                    proforma.destination_sync_error = DestinationSyncService._sanitize_error(error_msg)
                    db.commit()
                    
                    # Log event
                    DestinationSyncService._log_event(
                        db=db,
                        event_type="PROFORMA_SYNC_FAILED",
                        status="ERROR",
                        message=f"Sync failed for Proforma #{proforma.doc_number}: {error_msg}"
                    )
                    return {"ok": False, "success": False, "status": "FAILED", "error": error_msg, "sync_status": "FAILED"}

                # Store external_client_id on proforma
                proforma.external_client_id = external_client_id
                db.commit()

                # 2. Build Proforma Invoice Payload according to ERP specification
                raw_items = proforma.line_items or []
                formatted_items = []
                for item in raw_items:
                    rate = float(item.get("rate") or 0.0)
                    qty = float(item.get("qty") or 1.0)
                    discount = float(item.get("discount") or 0.0)
                    gst_rate = float(item.get("gstRate") or 0.18)
                    amount = (rate * qty) - discount
                    
                    # Compute line tax
                    tax_val = amount * gst_rate
                    is_inter = (proforma.tax_mode == "inter") or (proforma.state_code and proforma.state_code != "33")
                    
                    formatted_items.append({
                        "description": item.get("description") or "Product/Service Item",
                        "hsn": item.get("hsn") or "",
                        "qty": qty,
                        "rate": rate,
                        "gstRate": gst_rate if gst_rate <= 1 else (gst_rate / 100.0),
                        "discount": discount,
                        "amount": round(amount, 2),
                        "cgst": 0.0 if is_inter else round(tax_val / 2.0, 2),
                        "sgst": 0.0 if is_inter else round(tax_val / 2.0, 2),
                        "igst": round(tax_val, 2) if is_inter else 0.0,
                        "total": round(amount + tax_val, 2)
                    })

                invoice_payload = {
                    "docType": "proforma",
                    "idempotencyKey": idempotency_key,
                    "number": proforma.doc_number,
                    "quotationReference": proforma.source_quotation_number or (f"QT-{proforma.source_quotation_id}" if proforma.source_quotation_id else None),
                    "status": "issued",
                    "paymentStatus": "unpaid",
                    "licenceCount": val_result.licence_count,
                    "issueDate": int(proforma.issue_date.timestamp() * 1000) if proforma.issue_date else int(datetime.now(timezone.utc).timestamp() * 1000),
                    "dueDate": int(proforma.due_date.timestamp() * 1000) if proforma.due_date else int((datetime.now(timezone.utc).timestamp() + 15*86400) * 1000),
                    "companyId": company_id,
                    "customerId": external_client_id,
                    "customer": {
                        "customerId": external_client_id,
                        "name": proforma.customer_name,
                        "companyName": proforma.company_name or "",
                        "gstin": proforma.gstin or "",
                        "email": proforma.email or "",
                        "phone": proforma.phone or "",
                        "address": {
                            "line1": proforma.address or "Address on file",
                            "state": proforma.state or "Tamil Nadu",
                            "stateCode": proforma.state_code or "33",
                            "pincode": "600001",
                            "country": "India"
                        }
                    },
                    "taxSummary": {
                        "subtotal": round(float(proforma.subtotal or 0.0), 2),
                        "cgst": round(float(proforma.cgst or 0.0), 2),
                        "sgst": round(float(proforma.sgst or 0.0), 2),
                        "igst": round(float(proforma.igst or 0.0), 2),
                        "totalTax": round(float(proforma.tax_total or 0.0), 2),
                        "roundOff": round(float(proforma.round_off or 0.0), 2),
                        "grandTotal": round(float(proforma.grand_total or 0.0), 2)
                    },
                    "lineItems": formatted_items,
                    "notes": proforma.notes or f"Created via Wa CRM from Quotation #{proforma.source_quotation_number or ''}",
                    "termsAndConditions": proforma.terms_and_conditions or "",
                    "pdfUrl": proforma.pdf_url,
                    "metadata": {
                        "crmSource": "WaCRM",
                        "crmProformaId": proforma.id,
                        "crmQuotationId": proforma.source_quotation_id,
                        "productCategory": "WAHRMS",
                        "selectedBundle": proforma.selected_bundle,
                        "licenceCount": val_result.licence_count,
                        "idempotencyKey": idempotency_key
                    }
                }

                # 3. Post to destination ERP documents creation endpoint
                doc_url = f"{base_url}/api/v1/crm/documents"
                resp = client.post(doc_url, headers=headers, json=invoice_payload)

                if resp.status_code in [200, 201]:
                    res_json = resp.json()
                    ext_doc_id = str(
                        res_json.get("id") or 
                        (res_json.get("document") or {}).get("id") or 
                        res_json.get("docId") or 
                        proforma.doc_number
                    )

                    now = datetime.now(timezone.utc)
                    proforma.destination_sync_status = "SYNCED"
                    proforma.external_proforma_id = ext_doc_id
                    proforma.destination_synced_at = now
                    proforma.destination_sync_error = None
                    res_store = dict(res_json) if isinstance(res_json, dict) else {"response": res_json}
                    res_store["idempotency_key"] = idempotency_key
                    proforma.destination_sync_response = res_store
                    db.commit()

                    # Add activity on linked lead if exists
                    if proforma.lead_id:
                        act = LeadActivity(
                            lead_id=proforma.lead_id,
                            activity_type="PROFORMA_SYNCED_ERP",
                            description=f"Proforma #{proforma.doc_number} successfully synced to destination ERP (ERP Document ID: {ext_doc_id}).",
                            created_at=now
                        )
                        db.add(act)
                        db.commit()

                    DestinationSyncService._log_event(
                        db=db,
                        event_type="PROFORMA_SYNC_SUCCESS",
                        status="SUCCESS",
                        message=f"Synced Proforma #{proforma.doc_number} to {base_url} (Ext ID: {ext_doc_id}, Client ID: {external_client_id})."
                    )

                    return {
                        "ok": True,
                        "success": True,
                        "status": "SYNCED",
                        "sync_status": "SYNCED",
                        "external_client_id": external_client_id,
                        "external_proforma_id": ext_doc_id,
                        "synced_at": now.isoformat(),
                        "message": f"Successfully synchronized Proforma #{proforma.doc_number} to destination ERP."
                    }
                else:
                    err_msg = f"Destination ERP returned HTTP {resp.status_code}: {resp.text}"
                    proforma.destination_sync_status = "FAILED"
                    proforma.destination_sync_error = DestinationSyncService._sanitize_error(err_msg)
                    db.commit()

                    DestinationSyncService._log_event(
                        db=db,
                        event_type="PROFORMA_SYNC_FAILED",
                        status="ERROR",
                        message=f"Sync failed for Proforma #{proforma.doc_number} (HTTP {resp.status_code})."
                    )
                    return {"ok": False, "success": False, "status": "FAILED", "error": err_msg, "sync_status": "FAILED"}

        except httpx.TimeoutException as te:
            err_msg = f"Connection to destination ERP timed out after 15 seconds: {str(te)}"
            logger.error(err_msg)
            proforma.destination_sync_status = "FAILED"
            proforma.destination_sync_error = err_msg
            db.commit()
            return {"ok": False, "success": False, "status": "FAILED", "error": err_msg, "sync_status": "FAILED"}

        except Exception as e:
            err_msg = f"Unexpected error during destination synchronization: {str(e)}"
            logger.error(err_msg)
            proforma.destination_sync_status = "FAILED"
            proforma.destination_sync_error = DestinationSyncService._sanitize_error(err_msg)
            db.commit()
            return {"ok": False, "success": False, "status": "FAILED", "error": err_msg, "sync_status": "FAILED"}

    @staticmethod
    def _log_event(db: Session, event_type: str, status: str, message: str):
        try:
            log = IntegrationLog(
                integration_type="WAQUOTE",
                event_type=event_type,
                status=status,
                message=message,
                created_at=datetime.now(timezone.utc)
            )
            db.add(log)
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to record IntegrationLog: {e}")
