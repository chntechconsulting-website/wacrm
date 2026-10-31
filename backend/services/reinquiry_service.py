import re
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from models.lead import Lead, LeadEnquiry, LeadAssignment, LeadStatusHistory
from models.customer import Customer
from models.activity import LeadActivity

from utils.timezone import get_ist_now
from utils.phone import normalize_email

logger = logging.getLogger("reinquiry_service")

class ReInquiryService:
    """
    Centralized Re-Inquiry Detection & Management Service for WaCRM.
    
    Automatically identifies returning prospects across all channels (Website, Meta, Excel, Manual),
    prevents duplicate lead proliferation, preserves complete historical interactions, 
    and maintains an immutable multi-channel enquiry lifecycle.
    """

    @staticmethod
    def normalize_phone(phone: Optional[str]) -> str:
        """
        Normalizes any phone string to clean digits.
        Extracts the standard 10-digit mobile number for Indian/standard formats.
        """
        if not phone:
            return ""
        digits = re.sub(r"\D", "", str(phone))
        # If 12 digits starting with 91 (India country code)
        if len(digits) == 12 and digits.startswith("91"):
            return digits[2:]
        # If 11 digits starting with 0 (trunk prefix)
        if len(digits) == 11 and digits.startswith("0"):
            return digits[1:]
        # Standard 10-digit number
        if len(digits) >= 10:
            return digits[-10:]
        return digits

    @staticmethod
    def find_existing_lead(
        db: Session,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        exclude_lead_ids: Optional[Any] = None
    ) -> Optional[Lead]:
        """
        Searches for an existing lead or customer.

        Matching rules (all exact, never fuzzy):
        - Phone: normalized digits only, matched against the lead's phone and
          whatsapp number. Requires at least 7 digits, so empty/short values
          can never match.
        - Email: only a syntactically valid address is used, compared
          case-insensitively. Blank/placeholder emails never match.

        ``exclude_lead_ids`` skips leads created earlier in the same import
        batch so an upload cannot turn its own rows into re-inquiries.
        """
        clean_phone = ReInquiryService.normalize_phone(phone)
        clean_email = normalize_email(email)
        excluded = set(exclude_lead_ids or [])

        # 1. Primary Match: Phone number
        if clean_phone and len(clean_phone) >= 7:
            from utils.phone import find_existing_lead_by_phone, find_existing_customer_by_phone
            matched = find_existing_lead_by_phone(db, phone, exclude_lead_ids=excluded)
            if matched:
                logger.info(f"Re-Inquiry match by PHONE: incoming '{phone}' matched Lead #{matched.id} ('{matched.phone}').")
                return matched

            # Also check Customers table (converted customers who submit new inquiries)
            matched_cust = find_existing_customer_by_phone(db, phone)
            if matched_cust:
                if matched_cust.converted_from_lead:
                    lead = db.query(Lead).filter(Lead.id == matched_cust.converted_from_lead).first()
                    if lead and lead.id not in excluded:
                        logger.info(f"Re-Inquiry match by CUSTOMER PHONE: Customer #{matched_cust.id} linked to Lead #{lead.id}.")
                        return lead
                elif matched_cust.lead and matched_cust.lead.id not in excluded:
                    return matched_cust.lead

        # 2. Secondary Match: Email address (valid addresses only)
        if clean_email:
            email_query = db.query(Lead).filter(
                func.lower(func.trim(Lead.email)) == clean_email
            )
            if excluded:
                email_query = email_query.filter(~Lead.id.in_(list(excluded)))
            email_lead = email_query.order_by(Lead.id.desc()).first()

            if email_lead:
                logger.info(f"Re-Inquiry match by EMAIL: incoming '{email}' matched Lead #{email_lead.id}.")
                return email_lead

            # Check Customer email
            cust = db.query(Customer).filter(
                func.lower(func.trim(Customer.email)) == clean_email
            ).first()
            if cust:
                if cust.converted_from_lead:
                    lead = db.query(Lead).filter(Lead.id == cust.converted_from_lead).first()
                    if lead and lead.id not in excluded:
                        logger.info(f"Re-Inquiry match by CUSTOMER EMAIL: Customer #{cust.id} linked to Lead #{lead.id}.")
                        return lead
                elif cust.lead and cust.lead.id not in excluded:
                    return cust.lead

        return None

    @staticmethod
    def register_enquiry(
        db: Session,
        enquiry_data: Dict[str, Any],
        creator_emp_id: Optional[int] = None,
        creator_name: Optional[str] = None,
        commit: bool = True,
        exclude_lead_ids: Optional[Any] = None
    ) -> Tuple[Lead, bool, LeadEnquiry]:
        """
        Processes an incoming enquiry.
        - If matching lead exists: Marks as RE-INQUIRY, increments count, records history, preserves original data.
        - If first-time enquiry: Marks as NEW LEAD, initializes re-inquiry counters.
        
        Returns: (lead, is_reinquiry, enquiry_record)
        """
        raw_phone = enquiry_data.get("phone", "")
        raw_email = enquiry_data.get("email", "")
        src = (enquiry_data.get("source") or "MANUAL").strip().upper()
        if src in ["META ADS", "META_ADS"]:
            src = "META"

        now = get_ist_now()
        existing_lead = ReInquiryService.find_existing_lead(
            db,
            phone=raw_phone,
            email=raw_email,
            exclude_lead_ids=exclude_lead_ids
        )

        if existing_lead:
            # =========================================================================
            # RE-INQUIRY DETECTED
            # =========================================================================
            existing_lead.is_reinquiry = True
            existing_lead.reinquiry_count = (existing_lead.reinquiry_count or 0) + 1
            existing_lead.total_enquiries = (existing_lead.total_enquiries or 1) + 1
            existing_lead.latest_enquiry_date = now
            if not existing_lead.first_enquiry_date:
                existing_lead.first_enquiry_date = existing_lead.created_at or now

            # Append source if new to previous sources
            prev_sources = [s.strip().upper() for s in (existing_lead.previous_sources or existing_lead.source or "").split(",") if s.strip()]
            if src not in prev_sources:
                prev_sources.append(src)
            existing_lead.previous_sources = ", ".join(prev_sources)
            existing_lead.latest_source = src
            existing_lead.updated_at = now

            # Preserve original lead information; fill in missing profile data only
            if not existing_lead.email and raw_email:
                existing_lead.email = raw_email
            if not existing_lead.company and enquiry_data.get("company"):
                existing_lead.company = enquiry_data["company"].strip()
            if not existing_lead.designation and enquiry_data.get("designation"):
                existing_lead.designation = enquiry_data["designation"].strip()
            if not existing_lead.company_size and enquiry_data.get("company_size"):
                existing_lead.company_size = str(enquiry_data["company_size"]).strip()
            if not existing_lead.industry and enquiry_data.get("industry"):
                existing_lead.industry = enquiry_data["industry"].strip()
            if not existing_lead.location and enquiry_data.get("location"):
                existing_lead.location = enquiry_data["location"].strip()
            if not existing_lead.city and enquiry_data.get("city"):
                existing_lead.city = enquiry_data["city"].strip()
            if not existing_lead.state and enquiry_data.get("state"):
                existing_lead.state = enquiry_data["state"].strip()

            # Record website attribution if present
            if enquiry_data.get("website_id"):
                existing_lead.website_id = enquiry_data["website_id"]
            if enquiry_data.get("website_name"):
                existing_lead.website_name = enquiry_data["website_name"]
            if enquiry_data.get("landing_page"):
                existing_lead.landing_page = enquiry_data["landing_page"]

            # If Meta attribution
            if enquiry_data.get("meta_lead_id") and not existing_lead.meta_lead_id:
                existing_lead.meta_lead_id = enquiry_data["meta_lead_id"]
            if enquiry_data.get("meta_form_id"):
                existing_lead.meta_form_id = enquiry_data["meta_form_id"]

            # If lead was previously closed as LOST or NOT_INTERESTED, re-activate
            if existing_lead.status in ["LOST", "NOT_INTERESTED", "NOT INTERESTED"]:
                old_st = existing_lead.status
                existing_lead.status = "RE-INQUIRY"
                status_hist = LeadStatusHistory(
                    lead_id=existing_lead.id,
                    old_status=old_st,
                    new_status="RE-INQUIRY",
                    changed_by=creator_emp_id,
                    changed_at=now
                )
                db.add(status_hist)

            # Insert immutable enquiry record into lead_enquiries
            req_notes = enquiry_data.get("requirement_notes") or enquiry_data.get("message")
            if req_notes:
                req_notes_clean = req_notes.strip()
                if not existing_lead.requirement_notes:
                    existing_lead.requirement_notes = req_notes_clean
                elif req_notes_clean not in existing_lead.requirement_notes:
                    existing_lead.requirement_notes = f"{existing_lead.requirement_notes}\n\n[Re-Inquiry #{existing_lead.reinquiry_count} ({now.strftime('%d %b %Y %H:%M')} UTC) via {src}]: {req_notes_clean}"

            enquiry_record = LeadEnquiry(
                lead_id=existing_lead.id,
                enquiry_number=existing_lead.total_enquiries,
                enquiry_type="RE-INQUIRY",
                source=src,
                campaign_name=enquiry_data.get("campaign_name"),
                website_name=enquiry_data.get("website_name") or existing_lead.website_name,
                landing_page=enquiry_data.get("landing_page") or existing_lead.landing_page,
                requirement_notes=req_notes,
                created_at=now
            )
            db.add(enquiry_record)

            # Insert Re-Inquiry event to LeadActivity timeline
            msg_snippet = f" | Notes: {req_notes}" if req_notes else ""
            activity = LeadActivity(
                lead_id=existing_lead.id,
                performed_by=creator_emp_id,
                activity_type="RE_INQUIRY",
                description=f"🔁 RE-INQUIRY #{existing_lead.reinquiry_count} received via {src}. Total Enquiries: {existing_lead.total_enquiries}{msg_snippet}",
                created_at=now
            )
            db.add(activity)

            if commit:
                db.commit()
                db.refresh(existing_lead)

            logger.info(f"Registered RE-INQUIRY for Lead #{existing_lead.id} ({existing_lead.name}, Total: {existing_lead.total_enquiries}).")
            return existing_lead, True, enquiry_record

        # =========================================================================
        # FIRST-TIME ENQUIRY -> NEW LEAD
        # =========================================================================
        full_name = enquiry_data.get("name")
        if not full_name:
            fn = enquiry_data.get("first_name", "")
            ln = enquiry_data.get("last_name", "")
            full_name = f"{fn} {ln}".strip()
        if not full_name:
            full_name = enquiry_data.get("company") or f"Lead {raw_phone[-6:] if len(raw_phone) >= 6 else raw_phone}"

        req_notes = enquiry_data.get("requirement_notes") or enquiry_data.get("message")
        assigned_to_id = enquiry_data.get("assigned_to")

        new_lead = Lead(
            first_name=enquiry_data.get("first_name"),
            last_name=enquiry_data.get("last_name"),
            name=full_name,
            phone=raw_phone,
            whatsapp_number=enquiry_data.get("whatsapp_number") or raw_phone,
            email=raw_email or None,
            designation=enquiry_data.get("designation"),
            company=enquiry_data.get("company"),
            industry=enquiry_data.get("industry"),
            website=enquiry_data.get("website"),
            company_size=enquiry_data.get("company_size"),
            city=enquiry_data.get("city"),
            state=enquiry_data.get("state"),
            country=enquiry_data.get("country") or "India",
            location=enquiry_data.get("location"),
            source=src,
            status=enquiry_data.get("status") or ("ASSIGNED" if assigned_to_id else "NEW"),
            campaign_name=enquiry_data.get("campaign_name"),
            website_id=enquiry_data.get("website_id"),
            website_name=enquiry_data.get("website_name"),
            landing_page=enquiry_data.get("landing_page"),
            meta_lead_id=enquiry_data.get("meta_lead_id"),
            meta_form_id=enquiry_data.get("meta_form_id"),
            rating=enquiry_data.get("rating") or "Warm",
            priority=enquiry_data.get("priority") or "MEDIUM",
            requirement_notes=req_notes,
            followup_date=enquiry_data.get("followup_date"),
            followup_time=enquiry_data.get("followup_time"),
            assigned_to=assigned_to_id,
            assigned_by=creator_emp_id if assigned_to_id else None,
            assigned_at=now if assigned_to_id else None,
            # Re-Inquiry initial values
            is_reinquiry=False,
            reinquiry_count=0,
            total_enquiries=1,
            first_enquiry_date=now,
            latest_enquiry_date=now,
            previous_sources=src,
            latest_source=src,
            created_at=now,
            updated_at=now
        )
        db.add(new_lead)
        db.flush()

        # Initial LeadEnquiry
        enquiry_record = LeadEnquiry(
            lead_id=new_lead.id,
            enquiry_number=1,
            enquiry_type="INITIAL",
            source=src,
            campaign_name=enquiry_data.get("campaign_name"),
            website_name=enquiry_data.get("website_name"),
            landing_page=enquiry_data.get("landing_page"),
            requirement_notes=req_notes,
            created_at=now
        )
        db.add(enquiry_record)

        # Initial LeadActivity
        activity = LeadActivity(
            lead_id=new_lead.id,
            performed_by=creator_emp_id,
            activity_type="CREATED",
            description=f"New enquiry created from {src}" + (f" by {creator_name}" if creator_name else "") + (f": {req_notes}" if req_notes else "."),
            created_at=now
        )
        db.add(activity)

        if assigned_to_id:
            asgn = LeadAssignment(
                lead_id=new_lead.id,
                assigned_to=assigned_to_id,
                assigned_by=creator_emp_id,
                assigned_at=now,
                assignment_method="MANUAL" if creator_emp_id else "AUTOMATIC",
                notes="Initial assignment upon creation"
            )
            db.add(asgn)

        if commit:
            db.commit()
            db.refresh(new_lead)

        logger.info(f"Created NEW LEAD #{new_lead.id} ({new_lead.name}, Source: {src}).")
        return new_lead, False, enquiry_record
