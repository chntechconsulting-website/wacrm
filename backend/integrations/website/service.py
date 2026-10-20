import logging
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session
from models.lead import Lead
from models.activity import LeadActivity
from services.reinquiry_service import ReInquiryService
from .schemas import WebsiteLeadRequest

logger = logging.getLogger("website_integration")

class WebsiteLeadService:
    """
    Service handling website form submission ingestion, duplicate checking,
    source forcing (WEBSITE), and DB persistence.
    """

    @staticmethod
    def process_website_lead(db: Session, payload: WebsiteLeadRequest) -> Dict[str, Any]:
        # Clean basic contact fields
        phone_clean = (payload.phone or "").strip()
        email_clean = (payload.email or "").strip().lower() if payload.email else None
        whatsapp_clean = (payload.whatsapp_number or payload.whatsapp or payload.whatsappNumber or "").strip() or phone_clean

        team_size = (payload.teamSize or payload.team_size or payload.companySize or payload.company_size or "").strip() or None
        dept = (payload.designation or payload.department or payload.role or payload.jobTitle or payload.job_title or payload.functionalArea or payload.functional_area or "").strip() or None
        industry = (payload.industry or "").strip() or None
        city = (payload.city or "").strip() or None
        state = (payload.state or "").strip() or None
        location = (payload.location or "").strip() or None
        if not location and (city or state):
            location = ", ".join(filter(None, [city, state]))

        website_id = payload.website_id or "wapluscrm"
        website_name = payload.website_name or "WA Plus CRM"
        landing_page = payload.landing_page or "http://www.wapluscrm.in/solutions/demo"
        campaign = payload.campaign

        # Intelligently extract key-value data if user supplied it formatted in message
        if payload.message:
            msg = payload.message
            if not team_size and "Team Size:" in msg:
                part = msg.split("Team Size:")[1]
                team_size = part.split("|")[0].split("\n")[0].strip()
            if not dept and "Department:" in msg:
                part = msg.split("Department:")[1]
                dept = part.split("|")[0].split("\n")[0].strip()
            if not dept and "Role:" in msg:
                part = msg.split("Role:")[1]
                dept = part.split("|")[0].split("\n")[0].strip()
            if not dept and "Designation:" in msg:
                part = msg.split("Designation:")[1]
                dept = part.split("|")[0].split("\n")[0].strip()

        # Process website submission via centralized ReInquiryService
        enquiry_data = {
            "name": payload.name.strip() if payload.name else None,
            "phone": phone_clean,
            "whatsapp_number": whatsapp_clean,
            "email": email_clean,
            "company": payload.company.strip() if payload.company else None,
            "company_size": team_size,
            "designation": dept,
            "industry": industry,
            "city": city,
            "state": state,
            "location": location,
            "website_id": website_id,
            "website_name": website_name,
            "landing_page": landing_page,
            "campaign_name": campaign,
            "source": "WEBSITE",
            "requirement_notes": f"Website Message: {payload.message}" if payload.message else None,
        }

        lead, is_reinquiry, enq = ReInquiryService.register_enquiry(
            db=db,
            enquiry_data=enquiry_data,
            creator_emp_id=None,
            creator_name="Website Form",
            commit=True
        )

        logger.info(f"Website submission processed: Lead #{lead.id} ({lead.name}), is_reinquiry={is_reinquiry}, total={lead.total_enquiries}.")

        return {
            "success": True,
            "message": "Website re-inquiry recorded successfully" if is_reinquiry else "Website lead created successfully",
            "lead_id": lead.id,
            "is_reinquiry": is_reinquiry,
            "reinquiry_count": lead.reinquiry_count,
            "total_enquiries": lead.total_enquiries
        }
