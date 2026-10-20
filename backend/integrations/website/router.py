from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from .schemas import WebsiteLeadRequest, WebsiteLeadResponse
from .service import WebsiteLeadService

router = APIRouter(prefix="/integrations/website", tags=["Website Lead Capture Integration"])

@router.options("/leads")
@router.options("/lead")
def options_website_lead():
    return {"status": "ok"}

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
    """
    # Resolve name from name or firstName + lastName
    resolved_name = (payload.name or "").strip()
    if not resolved_name:
        fname = (payload.firstName or payload.first_name or "").strip()
        lname = (payload.lastName or payload.last_name or "").strip()
        resolved_name = f"{fname} {lname}".strip()

    if not resolved_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contact name is required."
        )
    payload.name = resolved_name

    # Resolve phone number (handling country code)
    resolved_phone = (payload.phone or "").strip()
    code = (payload.countryCode or payload.country_code or "").strip()
    if code and resolved_phone and not resolved_phone.startswith("+"):
        if not code.startswith("+"):
            code = f"+{code}"
        resolved_phone = f"{code} {resolved_phone}"

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
        res = WebsiteLeadService.process_website_lead(db, payload)
        return res
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process website lead: {str(e)}"
        )
