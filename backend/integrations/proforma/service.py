import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from models.quotation import Quotation
from models.customer import Customer
from models.lead import Lead
from models.activity import LeadActivity
from models.integration import IntegrationLog
from .schemas import (
    ProformaIntegrationPayload,
    ProformaIntegrationResponse,
    AuthoritativeFinancialSummary
)
from .auth import sanitize_secret
from services.product_validation_service import ProductValidationService

logger = logging.getLogger("proforma_integration_service")


class ProformaIntegrationService:
    """
    Authoritative service to receive, validate, and synchronize Proforma Invoices
    and client profiles with external websites and ERP systems.
    """

    @staticmethod
    def _normalize_text(val: Optional[str]) -> str:
        return (val or "").strip()

    @staticmethod
    def _extract_address(payload: ProformaIntegrationPayload) -> Tuple[str, str, str, str]:
        """Returns (address_line, state, state_code, pincode)."""
        addr_obj = payload.billingAddress or payload.address
        if isinstance(addr_obj, dict):
            line = addr_obj.get("line1") or addr_obj.get("address") or "Address on file"
            state = addr_obj.get("state") or "Tamil Nadu"
            code = str(addr_obj.get("stateCode") or addr_obj.get("state_code") or "33")
            pin = str(addr_obj.get("pincode") or addr_obj.get("pin") or "600001")
            return line, state, code, pin
        elif hasattr(addr_obj, "line1"):
            return (
                addr_obj.line1 or "Address on file",
                addr_obj.state or "Tamil Nadu",
                str(addr_obj.stateCode or "33"),
                str(addr_obj.pincode or "600001")
            )
        elif isinstance(addr_obj, str) and addr_obj.strip():
            return addr_obj.strip(), "Tamil Nadu", "33", "600001"
        return "Address on file", "Tamil Nadu", "33", "600001"

    @staticmethod
    def process_proforma_payload(
        db: Session,
        payload: ProformaIntegrationPayload,
        header_idempotency_key: Optional[str] = None
    ) -> ProformaIntegrationResponse:
        """
        Processes external proforma integration request.
        1. Checks idempotency to prevent duplicate creation.
        2. Validates against authoritative CRM records.
        3. Authoritatively recalculates subtotals, tax distributions, and totals.
        4. Saves/updates records and maintains integration logs.
        """
        request_id = payload.requestId or payload.request_id or f"req_{uuid.uuid4().hex[:12]}"
        idempotency_key = (
            header_idempotency_key or
            payload.idempotencyKey or
            payload.idempotency_key or
            f"key_{request_id}"
        )

        now_utc = datetime.now(timezone.utc)
        warnings: List[str] = []

        # Resolve field aliases
        company_name = ProformaIntegrationService._normalize_text(payload.companyName or payload.company_name)
        contact_person = ProformaIntegrationService._normalize_text(
            payload.contactPerson or payload.contact_person or payload.customerName or payload.customer_name
        )
        email = ProformaIntegrationService._normalize_text(payload.email).lower()
        phone = ProformaIntegrationService._normalize_text(payload.phone)
        gstin = ProformaIntegrationService._normalize_text(payload.gstin).upper()
        proforma_id = payload.proformaId or payload.proforma_id
        proforma_number = ProformaIntegrationService._normalize_text(payload.proformaNumber or payload.proforma_number)
        quotation_number = ProformaIntegrationService._normalize_text(payload.quotationNumber or payload.quotation_number)
        product_category = (payload.productCategory or payload.product_category or "wahrms").lower()
        selected_bundle = payload.selectedBundle or "hr_payroll"

        raw_items = payload.lineItems if payload.lineItems else (payload.line_items or [])

        # -------------------------------------------------------------
        # STEP 1: Strict Product Category Validation (WAHRMS only)
        # -------------------------------------------------------------
        is_eligible, block_reason, val_result = ProductValidationService.is_eligible_for_external_sync(payload, db)
        if not is_eligible:
            ProformaIntegrationService._log_integration_event(
                db=db,
                event_type="INGEST_REJECTED_BIOMETRIC",
                status_val="BLOCKED",
                message=f"External synchronization rejected: {block_reason} (Category: {val_result.resolved_category})"
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"External website synchronization is restricted strictly to WAHRMS documents. {block_reason}"
            )

        # -------------------------------------------------------------
        # STEP 2: Idempotency Check
        # -------------------------------------------------------------
        existing_doc: Optional[Quotation] = None
        if proforma_id:
            try:
                pid = int(str(proforma_id).replace("local_", ""))
                existing_doc = db.query(Quotation).filter(Quotation.id == pid).first()
            except Exception:
                pass

        if not existing_doc and proforma_number:
            existing_doc = db.query(Quotation).filter(
                Quotation.doc_number == proforma_number,
                Quotation.doc_type == "proforma"
            ).first()

        # Check by idempotency key recorded in logs or response
        if not existing_doc and idempotency_key:
            recent_log = db.query(IntegrationLog).filter(
                IntegrationLog.integration_type == "PROFORMA_API",
                IntegrationLog.event_type == "INGEST_SUCCESS",
                IntegrationLog.message.contains(f"idempotency_key={idempotency_key}")
            ).first()
            if recent_log and "doc_id=" in recent_log.message:
                try:
                    import re
                    match = re.search(r'doc_id=(\d+)', recent_log.message)
                    if match:
                        existing_doc = db.query(Quotation).filter(Quotation.id == int(match.group(1))).first()
                except Exception:
                    pass

        # -------------------------------------------------------------
        # STEP 2: Handle Existing Authoritative Document
        # -------------------------------------------------------------
        if existing_doc:
            if existing_doc.doc_type != "proforma":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Document #{existing_doc.doc_number} exists in CRM but is of type '{existing_doc.doc_type}', not 'proforma'."
                )

            # Strict product validation on existing record
            is_exist_eligible, exist_reason, exist_val = ProductValidationService.is_eligible_for_external_sync(existing_doc, db)
            if not is_exist_eligible:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"CRM Proforma #{existing_doc.doc_number} contains Biometric products and cannot be synchronized externally."
                )

            # Check if caller supplied totals and verify against authoritative CRM values
            authoritative_grand = float(existing_doc.grand_total or 0.0)
            if payload.grandTotal is not None:
                client_grand = float(payload.grandTotal)
                if abs(authoritative_grand - client_grand) > 1.0:
                    warnings.append(
                        f"Supplied grandTotal (₹{client_grand:,.2f}) differed from authoritative CRM record (₹{authoritative_grand:,.2f}). Authoritative CRM total was preserved."
                    )

            # Update destination sync metadata if external reference was provided
            if payload.pdfUrl or payload.pdf_url:
                existing_doc.pdf_url = payload.pdfUrl or payload.pdf_url

            existing_doc.destination_sync_status = "SYNCED"
            existing_doc.destination_synced_at = now_utc
            db.commit()

            authoritative_summary = AuthoritativeFinancialSummary(
                taxableSubtotal=float(existing_doc.subtotal or 0.0),
                taxMode=existing_doc.tax_mode or "intra",
                cgst=float(existing_doc.cgst or 0.0),
                sgst=float(existing_doc.sgst or 0.0),
                igst=float(existing_doc.igst or 0.0),
                totalTax=float(existing_doc.tax_total or 0.0),
                roundOff=float(existing_doc.round_off or 0.0),
                grandTotal=authoritative_grand,
                lineItemsCount=len(existing_doc.line_items or [])
            )

            # Record non-sensitive audit log
            ProformaIntegrationService._log_integration_event(
                db=db,
                event_type="AUTHORITATIVE_VERIFIED",
                status_val="SUCCESS",
                message=f"Verified authoritative Proforma #{existing_doc.doc_number} (doc_id={existing_doc.id}, customer_id={existing_doc.customer_id}, idempotency_key={idempotency_key})"
            )

            return ProformaIntegrationResponse(
                success=True,
                requestId=request_id,
                idempotencyKey=idempotency_key,
                processingStatus="AUTHORITATIVE_VERIFIED",
                customerId=existing_doc.customer_id,
                customerName=existing_doc.customer_name,
                companyName=existing_doc.company_name,
                proformaId=existing_doc.id,
                proformaNumber=existing_doc.doc_number,
                quotationNumber=existing_doc.source_quotation_number,
                authoritativeSummary=authoritative_summary,
                pdfDownloadUrl=f"/api/integrations/waquote/proformas/{existing_doc.id}/download",
                syncedAt=now_utc.isoformat(),
                message=f"Authoritative Proforma #{existing_doc.doc_number} verified and synchronized.",
                warnings=warnings if warnings else None
            )

        # -------------------------------------------------------------
        # STEP 3: Validate Required Fields for New Proforma Creation
        # -------------------------------------------------------------
        if not contact_person and not company_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Either 'companyName' or 'contactPerson' is required."
            )

        if not raw_items:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="At least one valid line item is required to issue a Proforma Invoice."
            )

        # -------------------------------------------------------------
        # STEP 4: Resolve or Create Customer in CRM
        # -------------------------------------------------------------
        customer_id = payload.customerId or payload.customer_id
        customer: Optional[Customer] = None

        if customer_id:
            try:
                cid = int(str(customer_id).replace("cust_", ""))
                customer = db.query(Customer).filter(Customer.id == cid).first()
            except Exception:
                pass

        if not customer and gstin:
            customer = db.query(Customer).filter(Customer.company_name == company_name).first()

        if not customer and phone:
            customer = db.query(Customer).filter(Customer.phone == phone).first()

        addr_line, state_name, state_code, pincode = ProformaIntegrationService._extract_address(payload)

        if not customer:
            customer = Customer(
                company_name=company_name or contact_person or "Client Entity",
                contact_name=contact_person or company_name or "Primary Contact",
                phone=phone or "9999999999",
                email=email or None,
                location=f"{state_name}, India",
                created_at=now_utc
            )
            db.add(customer)
            db.flush()
            db.refresh(customer)

        # -------------------------------------------------------------
        # STEP 5: Authoritative Re-computation of Financials
        # -------------------------------------------------------------
        # Intra-state supply if state_code == "33" (Tamil Nadu), else Inter-state (IGST)
        is_intra = (state_code == "33") or ("tamil nadu" in state_name.lower())
        tax_mode = "intra" if is_intra else "inter"

        validated_items: List[Dict[str, Any]] = []
        calc_subtotal = 0.0
        calc_cgst = 0.0
        calc_sgst = 0.0
        calc_igst = 0.0

        for idx, item in enumerate(raw_items):
            rate = float(item.rate if hasattr(item, 'rate') else item.get('rate', 0.0))
            qty = float(item.qty if hasattr(item, 'qty') else item.get('qty', 1.0))
            discount = float(item.discount if hasattr(item, 'discount') else item.get('discount', 0.0))
            raw_gst = float(item.gstRate if hasattr(item, 'gstRate') else item.get('gstRate', 0.18))
            gst_rate = raw_gst if raw_gst <= 1.0 else (raw_gst / 100.0)

            line_taxable = max(0.0, (rate * qty) - discount)
            line_tax = line_taxable * gst_rate

            if is_intra:
                cgst_line = round(line_tax / 2.0, 2)
                sgst_line = round(line_tax / 2.0, 2)
                igst_line = 0.0
                calc_cgst += cgst_line
                calc_sgst += sgst_line
            else:
                cgst_line = 0.0
                sgst_line = 0.0
                igst_line = round(line_tax, 2)
                calc_igst += igst_line

            line_total = round(line_taxable + cgst_line + sgst_line + igst_line, 2)
            calc_subtotal += line_taxable

            validated_items.append({
                "id": getattr(item, 'id', None) or f"item_{idx + 1}",
                "name": getattr(item, 'name', None) or getattr(item, 'description', None) or f"Item {idx + 1}",
                "description": getattr(item, 'description', None) or getattr(item, 'name', None) or "",
                "hsn": getattr(item, 'hsn', None) or ("85437099" if product_category == "biometric" else "998314"),
                "qty": qty,
                "rate": rate,
                "discount": discount,
                "gstRate": gst_rate,
                "amount": round(line_taxable, 2),
                "cgst": cgst_line,
                "sgst": sgst_line,
                "igst": igst_line,
                "total": line_total
            })

        calc_subtotal = round(calc_subtotal, 2)
        calc_cgst = round(calc_cgst, 2)
        calc_sgst = round(calc_sgst, 2)
        calc_igst = round(calc_igst, 2)
        calc_total_tax = round(calc_cgst + calc_sgst + calc_igst, 2)
        unrounded_grand = calc_subtotal + calc_total_tax
        calc_grand_total = round(unrounded_grand)
        round_off = round(calc_grand_total - unrounded_grand, 2)

        # Check if caller supplied totals and record warning if difference exists
        if payload.grandTotal is not None:
            supplied_grand = float(payload.grandTotal)
            if abs(calc_grand_total - supplied_grand) > 1.0:
                warnings.append(
                    f"Supplied grandTotal (₹{supplied_grand:,.2f}) differed from authoritative re-computation (₹{calc_grand_total:,.2f}). Authoritative total was enforced."
                )

        # -------------------------------------------------------------
        # STEP 6: Generate Document Number & Save Proforma
        # -------------------------------------------------------------
        if not proforma_number:
            year = now_utc.year
            count = db.query(Quotation).filter(Quotation.doc_type == "proforma").count() + 1
            proforma_number = f"PI-{year}-{count:04d}"

        new_proforma = Quotation(
            doc_type="proforma",
            doc_number=proforma_number,
            status="issued",
            payment_status="unpaid",
            customer_id=customer.id,
            source_quotation_number=quotation_number or None,
            product_category=product_category,
            selected_bundle=selected_bundle,
            customer_name=customer.contact_name,
            company_name=customer.company_name,
            phone=customer.phone,
            email=customer.email,
            address=addr_line,
            state=state_name,
            state_code=state_code,
            gstin=gstin or None,
            tax_mode=tax_mode,
            subtotal=calc_subtotal,
            cgst=calc_cgst,
            sgst=calc_sgst,
            igst=calc_igst,
            tax_total=calc_total_tax,
            round_off=round_off,
            grand_total=calc_grand_total,
            amount_paid=0.0,
            line_items=validated_items,
            terms_and_conditions=payload.termsAndConditions or payload.terms_and_conditions or "1. Software access activates upon payment.\n2. Prices subject to applicable GST.",
            notes=payload.notes or f"Received via External Proforma API (Req #{request_id})",
            pdf_url=payload.pdfUrl or payload.pdf_url,
            destination_sync_status="SYNCED",
            destination_synced_at=now_utc,
            destination_sync_attempts=1,
            destination_sync_response={"idempotency_key": idempotency_key, "request_id": request_id},
            created_at=now_utc
        )

        db.add(new_proforma)
        db.commit()
        db.refresh(new_proforma)

        # Record LeadActivity if customer converted from lead
        if customer.converted_from_lead:
            try:
                act = LeadActivity(
                    lead_id=customer.converted_from_lead,
                    activity_type="PROFORMA_ISSUED_EXTERNAL",
                    description=f"Proforma #{new_proforma.doc_number} generated via External Integration API (Total: ₹{calc_grand_total:,.2f}).",
                    created_at=now_utc
                )
                db.add(act)
                db.commit()
            except Exception:
                pass

        # -------------------------------------------------------------
        # STEP 7: Audit Logging & Response Construction
        # -------------------------------------------------------------
        ProformaIntegrationService._log_integration_event(
            db=db,
            event_type="INGEST_SUCCESS",
            status_val="SUCCESS",
            message=f"Created Proforma #{new_proforma.doc_number} (doc_id={new_proforma.id}, customer_id={customer.id}, idempotency_key={idempotency_key})"
        )

        authoritative_summary = AuthoritativeFinancialSummary(
            taxableSubtotal=calc_subtotal,
            taxMode=tax_mode,
            cgst=calc_cgst,
            sgst=calc_sgst,
            igst=calc_igst,
            totalTax=calc_total_tax,
            roundOff=round_off,
            grandTotal=calc_grand_total,
            lineItemsCount=len(validated_items)
        )

        return ProformaIntegrationResponse(
            success=True,
            requestId=request_id,
            idempotencyKey=idempotency_key,
            processingStatus="CREATED",
            customerId=customer.id,
            customerName=customer.contact_name,
            companyName=customer.company_name,
            proformaId=new_proforma.id,
            proformaNumber=new_proforma.doc_number,
            quotationNumber=new_proforma.source_quotation_number,
            authoritativeSummary=authoritative_summary,
            pdfDownloadUrl=f"/api/integrations/waquote/proformas/{new_proforma.id}/download",
            syncedAt=now_utc.isoformat(),
            message=f"Proforma Invoice #{new_proforma.doc_number} successfully registered in CRM.",
            warnings=warnings if warnings else None
        )

    @staticmethod
    def get_proforma_by_id_or_number(
        db: Session,
        identifier: str
    ) -> ProformaIntegrationResponse:
        """Retrieves authoritative Proforma Invoice by numeric ID or document number."""
        clean_id = identifier.strip().replace("local_", "")
        doc: Optional[Quotation] = None

        if clean_id.isdigit():
            doc = db.query(Quotation).filter(Quotation.id == int(clean_id), Quotation.doc_type == "proforma").first()

        if not doc:
            doc = db.query(Quotation).filter(Quotation.doc_number == identifier.strip(), Quotation.doc_type == "proforma").first()

        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Proforma Invoice with identifier '{identifier}' was not found in CRM."
            )

        # Strict Category Exclusion: Biometric proformas are not exposed to external website
        is_eligible, reason, val = ProductValidationService.is_eligible_for_external_sync(doc, db)
        if not is_eligible:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Proforma Invoice with identifier '{identifier}' was not found or is not eligible for external synchronization."
            )

        summary = AuthoritativeFinancialSummary(
            taxableSubtotal=float(doc.subtotal or 0.0),
            taxMode=doc.tax_mode or "intra",
            cgst=float(doc.cgst or 0.0),
            sgst=float(doc.sgst or 0.0),
            igst=float(doc.igst or 0.0),
            totalTax=float(doc.tax_total or 0.0),
            roundOff=float(doc.round_off or 0.0),
            grandTotal=float(doc.grand_total or 0.0),
            lineItemsCount=len(doc.line_items or [])
        )

        return ProformaIntegrationResponse(
            success=True,
            requestId=f"fetch_{uuid.uuid4().hex[:10]}",
            idempotencyKey=None,
            processingStatus="AUTHORITATIVE_VERIFIED",
            customerId=doc.customer_id,
            customerName=doc.customer_name,
            companyName=doc.company_name,
            proformaId=doc.id,
            proformaNumber=doc.doc_number,
            quotationNumber=doc.source_quotation_number,
            authoritativeSummary=summary,
            pdfDownloadUrl=f"/api/integrations/waquote/proformas/{doc.id}/download",
            syncedAt=doc.destination_synced_at.isoformat() if doc.destination_synced_at else doc.created_at.isoformat(),
            message=f"Authoritative Proforma #{doc.doc_number} retrieved."
        )

    @staticmethod
    def _log_integration_event(db: Session, event_type: str, status_val: str, message: str):
        try:
            log = IntegrationLog(
                integration_type="PROFORMA_API",
                event_type=event_type,
                status=status_val,
                message=sanitize_secret(message),
                created_at=datetime.now(timezone.utc)
            )
            db.add(log)
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to record IntegrationLog: {e}")
