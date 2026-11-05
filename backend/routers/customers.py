from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from typing import List, Optional
from datetime import datetime

from database import get_db
from models.user import User
from models.customer import Customer
from models.lead import Lead
from models.workflow import SupportHandoff
from services.auth import get_current_user
from services.activity_visibility_service import can_view_activity
from services.hierarchy_service import (
    ROLE_ADMIN,
    ROLE_SALES_EXECUTIVE,
    ROLE_SALES_MANAGER,
    ROLE_SUPPORT_EXECUTIVE,
    ROLE_SUPPORT_MANAGER,
    normalize_role,
)
from services.permission_service import is_support_lead_authorized
from services.purchase_details_service import build_support_purchase_details

router = APIRouter(prefix="/customers", tags=["Customers"])

SUPPORT_ROLES = [ROLE_SUPPORT_MANAGER, ROLE_SUPPORT_EXECUTIVE]


def _is_support_actor(user: User) -> bool:
    """True for Support employees/managers, including legacy SUPPORT labels."""
    if not user:
        return False
    if normalize_role(user.role) in SUPPORT_ROLES:
        return True
    return (user.department or "").strip().upper() == "SUPPORT"

@router.get("")
@router.get("/")
def list_customers(
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Customer)

    if search:
        search_fmt = f"%{search}%"
        query = query.filter(
            or_(
                Customer.company_name.ilike(search_fmt),
                Customer.contact_name.ilike(search_fmt),
                Customer.phone.ilike(search_fmt),
                Customer.email.ilike(search_fmt),
                Customer.location.ilike(search_fmt)
            )
        )

    customers = query.order_by(desc(Customer.created_at)).all()
    
    result = []
    for c in customers:
        result.append({
            "id": c.id,
            "company_name": c.company_name,
            "contact_name": c.contact_name,
            "phone": c.phone,
            "email": c.email,
            "location": c.location,
            "converted_from_lead": c.converted_from_lead,
            "created_at": c.created_at
        })
    return result

@router.get("/{customer_id}")
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    c = db.query(Customer).filter(Customer.id == customer_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")

    lead_data = None
    if c.converted_from_lead:
        lead = db.query(Lead).filter(Lead.id == c.converted_from_lead).first()
        if lead:
            activities_count = sum(
                1 for act in (lead.activities or [])
                if can_view_activity(act, current_user, db)
            )
            lead_data = {
                "id": lead.id,
                "source": lead.source,
                "campaign_name": lead.campaign_name,
                "created_at": lead.created_at,
                "activities_count": activities_count
            }

    norm_role = normalize_role(current_user.role)
    purchase_details = None
    if norm_role == ROLE_ADMIN or _is_support_actor(current_user):
        handoff = (
            db.query(SupportHandoff)
            .filter(
                or_(
                    SupportHandoff.customer_id == c.id,
                    SupportHandoff.lead_id == c.converted_from_lead,
                )
            )
            .order_by(desc(SupportHandoff.id))
            .first()
        )
        if handoff:
            purchase_details = build_support_purchase_details(db, handoff)

    return {
        "id": c.id,
        "company_name": c.company_name,
        "contact_name": c.contact_name,
        "phone": c.phone,
        "email": c.email,
        "location": c.location,
        "converted_from_lead": c.converted_from_lead,
        "created_at": c.created_at,
        "lead": lead_data,
        "purchase_details": purchase_details,
    }


@router.get("/{customer_id}/purchase-details")
def get_customer_purchase_details(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Read-only customer purchase details for the Support customer profile.

    Only Admin and Support roles may call this endpoint. Sales roles are
    rejected with HTTP 403 Forbidden so internal Sales negotiation notes
    and private discussions remain strictly separated from Support delivery.
    """
    norm_role = normalize_role(current_user.role)
    if norm_role in [ROLE_SALES_MANAGER, ROLE_SALES_EXECUTIVE]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Sales users cannot access Support purchase details."
        )
    if norm_role != ROLE_ADMIN and not _is_support_actor(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Only Support team and Admin can access purchase details."
        )

    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    handoff = (
        db.query(SupportHandoff)
        .filter(
            or_(
                SupportHandoff.customer_id == customer.id,
                SupportHandoff.lead_id == customer.converted_from_lead
            )
        )
        .order_by(desc(SupportHandoff.id))
        .first()
    )
    if not handoff:
        raise HTTPException(
            status_code=404,
            detail="No Sales handover exists for this customer yet."
        )

    if norm_role != ROLE_ADMIN and handoff.lead_id:
        lead = db.query(Lead).filter(Lead.id == handoff.lead_id).first()
        if lead and not is_support_lead_authorized(lead, current_user, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: This customer is not assigned to your Support team."
            )

    details = build_support_purchase_details(db, handoff)
    if not details:
        raise HTTPException(status_code=404, detail="Purchase details are not available.")
    return details

@router.delete("/{customer_id}")
def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from services.delete_request_service import handle_entity_deletion
    c = db.query(Customer).filter(Customer.id == customer_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")

    def do_delete():
        db.delete(c)
        db.commit()

    return handle_entity_deletion(
        db=db,
        current_user=current_user,
        entity_type="CUSTOMER",
        entity_id=c.id,
        entity_name=c.company_name or c.contact_name or f"Customer #{c.id}",
        delete_fn=do_delete
    )
