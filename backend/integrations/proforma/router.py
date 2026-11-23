import json
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from database import get_db
from models.quotation import Quotation
from .schemas import (
    ProformaIntegrationPayload,
    ProformaIntegrationResponse,
    AuthoritativeFinancialSummary
)
from .auth import (
    authenticate_proforma_webhook,
    verify_proforma_integration_auth,
)
from .service import ProformaIntegrationService
from services.proforma_payment_service import ProformaPaymentService

logger = logging.getLogger("proforma_integration_router")

router = APIRouter(
    prefix="/integrations/proforma",
    tags=["External Proforma Integration API"]
)


@router.options("")
@router.options("/")
@router.options("/{id_or_number}")
@router.options("/payments/webhook")
@router.options("/payments/callback")
@router.options("/webhook")
def options_proforma_integration():
    """CORS Preflight endpoint."""
    return {"status": "ok"}


@router.post(
    "/payments/webhook",
    summary="Receive Confirmed Payment from External ERP",
    description="""
    Receives a verified payment notification from the WA Quote / WAHRMS ERP.

    ### Authentication
    - Preferred: `X-WAQuote-Signature: t=<unix>,v1=<hex>` (HMAC-SHA256 over
      `<unix>.<raw body>`) or `X-Hub-Signature-256: sha256=<hex>`.
    - Fallback: `X-API-Key: <KEY>` or `Authorization: Bearer <KEY>`.

    ### Idempotency
    The external Proforma is resolved from `metadata.crmProformaId`,
    `Quotation.external_proforma_id` or the Proforma number. The transaction ID
    (or a deterministic fingerprint when the ERP omits one) prevents a retry
    from recording a second payment.

    A confirmed successful payment, including a partial payment, marks the
    linked Lead `WON`, updates the Proforma balance and creates/updates the
    Finance and Support handoffs. Pending, failed, cancelled, refunded and
    unverified events are acknowledged but do not change the Lead.
    """,
)
@router.post("/payments/callback", include_in_schema=False)
@router.post("/webhook", include_in_schema=False)
async def receive_proforma_payment_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    raw_body = await request.body()
    auth_mode = authenticate_proforma_webhook(request, raw_body, db)

    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning(f"Invalid payment webhook JSON: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload.",
        )

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment webhook payload must be a JSON object.",
        )

    try:
        return ProformaPaymentService.process_webhook(
            db=db,
            payload=payload,
            headers=dict(request.headers),
            source="PROFORMA_API",
            auth_mode=auth_mode,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to process external Proforma payment webhook.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process payment webhook.",
        )


@router.get(
    "/{id_or_number}/payments",
    summary="List Payment History for a Proforma",
    description=(
        "Returns every payment recorded for the Proforma, including the "
        "external transaction ID, amount paid, total paid and outstanding "
        "balance. Use the numeric CRM Proforma ID or the Proforma number."
    ),
)
def get_proforma_payment_history(
    id_or_number: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_proforma_integration_auth),
):
    clean_id = id_or_number.strip().replace("local_", "")
    doc: Optional[Quotation] = None
    if clean_id.isdigit():
        doc = (
            db.query(Quotation)
            .filter(Quotation.id == int(clean_id), Quotation.doc_type == "proforma")
            .first()
        )
    if not doc:
        doc = (
            db.query(Quotation)
            .filter(
                Quotation.doc_number == id_or_number.strip(),
                Quotation.doc_type == "proforma",
            )
            .first()
        )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proforma '{id_or_number}' was not found.",
        )
    return ProformaPaymentService.payment_history(db, doc)


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
