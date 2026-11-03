from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from .schemas import WebsiteLeadRequest, WebsiteLeadResponse
from .service import WebsiteLeadService

router = APIRouter(prefix="/integrations/website", tags=["Website Lead Capture Integration"])


def _resolve_name(payload: WebsiteLeadRequest) -> str:
    resolved_name = (payload.name or "").strip()
    if not resolved_name:
        fname = (payload.firstName or payload.first_name or "").strip()
        lname = (payload.lastName or payload.last_name or "").strip()
        resolved_name = f"{fname} {lname}".strip()
    return resolved_name


def _resolve_phone(payload: WebsiteLeadRequest) -> str:
    resolved_phone = (payload.phone or "").strip()
    if not resolved_phone:
        resolved_phone = (
            payload.whatsapp_number
            or payload.whatsapp
            or payload.whatsappNumber
            or ""
        ).strip()

    code = (payload.countryCode or payload.country_code or "").strip()
    if code and resolved_phone and not resolved_phone.startswith("+"):
        if not code.startswith("+"):
            code = f"+{code}"
        resolved_phone = f"{code} {resolved_phone}"
    return resolved_phone


@router.options("/leads")
@router.options("/lead")
@router.options("/brochures")
@router.options("/brochure")
def options_website_lead():
    return {"status": "ok"}


@router.post("/brochures", response_model=WebsiteLeadResponse, status_code=status.HTTP_201_CREATED)
@router.post("/brochure", response_model=WebsiteLeadResponse, status_code=status.HTTP_201_CREATED)
def submit_website_brochure(
    payload: WebsiteLeadRequest,
    db: Session = Depends(get_db)
):
    """
    Public Endpoint: Receive brochure download form submissions from the
    company website.

    The endpoint is itself an explicit brochure marker, so every successful
    submission is stored in the dedicated brochure_enquiries table. It never
    creates a normal Lead. The browser's actual file download is independent
    of this request and is not blocked by it.
    """
    resolved_name = _resolve_name(payload)
    if not resolved_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contact name is required."
        )
    payload.name = resolved_name

    resolved_phone = _resolve_phone(payload)
    if not resolved_phone and not (payload.email or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A phone/WhatsApp number or email address is required."
        )
    if resolved_phone:
        payload.phone = resolved_phone

    # Preserve any structured fields the website includes in the message,
    # exactly like the normal website lead endpoint does.
    extra_parts = []
    ts = payload.teamSize or payload.team_size
    if ts:
        extra_parts.append(f"Team Size: {ts}")
    fa = payload.functionalArea or payload.functional_area
    if fa:
        extra_parts.append(f"Department: {fa}")
    if extra_parts:
        detail_header = " | ".join(extra_parts)
        if payload.message and payload.message.strip():
            payload.message = f"{detail_header}\n{payload.message.strip()}"
        else:
            payload.message = detail_header

    try:
        return WebsiteLeadService.process_website_brochure(db, payload)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process brochure download: {str(e)}"
        )


@router.post("/leads", response_model=WebsiteLeadResponse, status_code=status.HTTP_201_CREATED)
@router.post("/lead", response_model=WebsiteLeadResponse, status_code=status.HTTP_201_CREATED)
def submit_website_lead(
    payload: WebsiteLeadRequest,
    db: Session = Depends(get_db)
):
    """
    Public Endpoint: Receive contact form submissions from any website.

    Backend Enforcement:
    - source = "WEBSITE" (ignoring any payload override attempt)
    - status = "NEW"
    - assigned_to = NULL
    - Deduplicates by phone or email
    - Records LeadActivity timeline entry

    Explicit brochure/download submissions are routed to the dedicated
    brochure_enquiries table instead of the normal Leads pipeline.
    """
    resolved_name = _resolve_name(payload)
    if not resolved_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contact name is required."
        )
    payload.name = resolved_name

    resolved_phone = _resolve_phone(payload)
    if not resolved_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number is required."
        )
    payload.phone = resolved_phone

    # Resolve department / teamSize into message if provided
    extra_parts = []
    ts = payload.teamSize or payload.team_size
    if ts:
        extra_parts.append(f"Team Size: {ts}")
    fa = payload.functionalArea or payload.functional_area
    if fa:
        extra_parts.append(f"Department: {fa}")

    if extra_parts:
        detail_header = " | ".join(extra_parts)
        if payload.message and payload.message.strip():
            payload.message = f"{detail_header}\n{payload.message.strip()}"
        else:
            payload.message = detail_header

    try:
        if WebsiteLeadService.is_brochure_submission(payload):
            return WebsiteLeadService.process_website_brochure(db, payload)
        res = WebsiteLeadService.process_website_lead(db, payload)
        return res
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process website lead: {str(e)}"
        )
