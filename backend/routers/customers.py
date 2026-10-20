from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from typing import List, Optional
from datetime import datetime

from database import get_db
from models.user import User
from models.customer import Customer
from models.lead import Lead
from services.auth import get_current_user

router = APIRouter(prefix="/customers", tags=["Customers"])

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
            lead_data = {
                "id": lead.id,
                "source": lead.source,
                "campaign_name": lead.campaign_name,
                "created_at": lead.created_at,
                "activities_count": len(lead.activities)
            }

    return {
        "id": c.id,
        "company_name": c.company_name,
        "contact_name": c.contact_name,
        "phone": c.phone,
        "email": c.email,
        "location": c.location,
        "converted_from_lead": c.converted_from_lead,
        "created_at": c.created_at,
        "lead": lead_data
    }

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
