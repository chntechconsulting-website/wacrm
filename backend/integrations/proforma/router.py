import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.orm import Session

from database import get_db
from models.quotation import Quotation
from .schemas import (
    ProformaIntegrationPayload,
    ProformaIntegrationResponse,
    AuthoritativeFinancialSummary
)
from .auth import verify_proforma_integration_auth
from .service import ProformaIntegrationService

logger = logging.getLogger("proforma_integration_router")

router = APIRouter(
    prefix="/integrations/proforma",
    tags=["External Proforma Integration API"]
)


@router.options("")
@router.options("/")
@router.options("/{id_or_number}")
def options_proforma_integration():
    """CORS Preflight endpoint."""
    return {"status": "ok"}


@router.post(
    "",
    response_model=ProformaIntegrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Receive or Authoritatively Synchronize Proforma Invoice",
    description="""
    Receives client profile and Proforma Invoice data from another website or external ERP.
    
    ### Security:
    - Requires `X-API-Key: <KEY>` or `Authorization: Bearer <KEY>`.
    - Protected with sliding window rate limiting (120 requests/minute).
    
    ### Authoritative Enforcement:
    - Never blindly trusts arbitrary client totals: subtotal, CGST, SGST, IGST, and grand totals are verified and calculated server-side.
    - Idempotent: repeated submissions with the same idempotency key or proforma number will not duplicate documents.
    """
)
def submit_proforma_integration(
    payload: ProformaIntegrationPayload,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_proforma_integration_auth),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key")
):
    return ProformaIntegrationService.process_proforma_payload(
        db=db,
        payload=payload,
        header_idempotency_key=x_idempotency_key
    )


@router.get(
    "/{id_or_number}",
    response_model=ProformaIntegrationResponse,
    summary="Fetch Proforma by Document ID or Number",
    description="Allows external website to verify or poll an existing Proforma Invoice and its authoritative totals."
)
def get_proforma_integration(
    id_or_number: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_proforma_integration_auth)
):
    return ProformaIntegrationService.get_proforma_by_id_or_number(
        db=db,
        identifier=id_or_number
    )


@router.get(
    "",
    summary="List Authoritative Proforma Invoices",
    description="Allows external website to query Proformas issued in CRM with optional date and client filters."
)
def list_proforma_integrations(
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    customer_id: Optional[int] = Query(None, description="Filter by CRM customer ID"),
    search: Optional[str] = Query(None, description="Search by customer name, phone, or proforma number"),
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_proforma_integration_auth)
):
    from sqlalchemy import or_
    from services.product_validation_service import ProductValidationService

    # Only query proformas that are not explicitly marked NOT_APPLICABLE or biometric
    query = db.query(Quotation).filter(
        Quotation.doc_type == "proforma",
        Quotation.destination_sync_status != "NOT_APPLICABLE",
        or_(Quotation.product_category == None, Quotation.product_category != "biometric")
    )

    if customer_id:
        query = query.filter(Quotation.customer_id == customer_id)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            (Quotation.doc_number.ilike(term)) |
            (Quotation.customer_name.ilike(term)) |
            (Quotation.company_name.ilike(term)) |
            (Quotation.phone.ilike(term))
        )

    docs = query.order_by(Quotation.id.desc()).all()

    # Authoritative product-level exclusion of any biometric or mixed documents
    eligible_docs = []
    for d in docs:
        is_eligible, _, _ = ProductValidationService.is_eligible_for_external_sync(d, db)
        if is_eligible:
            eligible_docs.append(d)

    total = len(eligible_docs)
    paged_docs = eligible_docs[skip : skip + limit]

    items = []
    for d in paged_docs:
        items.append({
            "proformaId": d.id,
            "proformaNumber": d.doc_number,
            "quotationNumber": d.source_quotation_number,
            "customerId": d.customer_id,
            "customerName": d.customer_name,
            "companyName": d.company_name,
            "phone": d.phone,
            "email": d.email,
            "productCategory": d.product_category,
            "selectedBundle": d.selected_bundle,
            "subtotal": float(d.subtotal or 0.0),
            "taxTotal": float(d.tax_total or 0.0),
            "grandTotal": float(d.grand_total or 0.0),
            "status": d.status,
            "paymentStatus": d.payment_status,
            "pdfUrl": f"/api/integrations/waquote/proformas/{d.id}/download",
            "createdAt": d.created_at.isoformat() if d.created_at else None
        })

    return {
        "ok": True,
        "total": total,
        "limit": limit,
        "skip": skip,
        "proformas": items
    }
