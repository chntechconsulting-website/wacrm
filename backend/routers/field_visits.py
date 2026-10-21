import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, and_

from database import get_db
from models.user import User
from models.employee import Employee
from models.lead import Lead
from models.customer import Customer
from models.followup import Followup
from models.activity import LeadActivity
from models.monitoring import FieldVisit, EmployeeActivityLog
from services.auth import get_current_user
from services.hierarchy_service import get_authorized_performance_employee_ids
from routers.employee_monitoring import authorize_employee_access

logger = logging.getLogger("field_visits_router")

router = APIRouter(prefix="/field-visits", tags=["Field Visits"])

def get_employee_for_user(db: Session, user: User) -> Optional[Employee]:
    return db.query(Employee).filter(Employee.user_id == user.id).first()

def handle_field_visit_submission(
    data: Dict[str, Any],
    db: Session,
    current_user: User
) -> Dict[str, Any]:
    emp = get_employee_for_user(db, current_user)
    if not emp:
        # Fallback to employee mapped via User ID or first employee for admin
        emp = db.query(Employee).filter(Employee.id == getattr(current_user, "employee_id", None)).first()
        if not emp and current_user.role == "ADMIN":
            emp = db.query(Employee).first()

    if not emp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only registered employees with an active profile can record field visits."
        )

    # 1. Idempotency & Duplicate Prevention
    client_token = data.get("client_token")
    if client_token:
        existing = db.query(FieldVisit).filter(
            FieldVisit.client_token == client_token,
            FieldVisit.employee_id == emp.id
        ).first()
        if existing:
            return existing.to_dict()

    # Prevent rapid double-clicks (same employee, same customer/lead within 30 seconds)
    lead_id = data.get("lead_id")
    customer_id = data.get("customer_id")
    customer_name = (data.get("customer_name") or "").strip()

    lead = None
    if lead_id:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if lead and not customer_name:
            customer_name = lead.name or lead.company or f"Lead #{lead.id}"

    customer = None
    if customer_id:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if customer and not customer_name:
            customer_name = customer.company_name or customer.contact_name

    now = datetime.utcnow()
    recent_dup = db.query(FieldVisit).filter(
        FieldVisit.employee_id == emp.id,
        FieldVisit.customer_name == customer_name,
        FieldVisit.checkin_time >= (now - timedelta(seconds=30))
    ).first()
    if recent_dup and not client_token:
        return recent_dup.to_dict()

    # 2. Extract Data
    checkin_lat = str(data.get("checkin_lat") or "")
    checkin_lng = str(data.get("checkin_lng") or "")
    checkin_address = data.get("checkin_address") or data.get("location_name")
    photo_url = data.get("company_board_photo") or data.get("photo_url")
    visiting_card_url = data.get("visiting_card_photo") or data.get("visiting_card_url")
    customer_requirements = data.get("customer_requirements") or data.get("requirements")
    visit_outcome = data.get("visit_outcome") or "Completed"
    notes = data.get("notes") or ""

    visit_time = now
    raw_visit_time = data.get("visit_time") or data.get("checkin_time")
    if raw_visit_time:
        try:
            if isinstance(raw_visit_time, str):
                visit_time = datetime.fromisoformat(raw_visit_time.replace("Z", "+00:00"))
            elif isinstance(raw_visit_time, datetime):
                visit_time = raw_visit_time
        except Exception:
            visit_time = now

    # 3. Create Field Visit Record
    visit = FieldVisit(
        employee_id=emp.id,
        lead_id=lead_id,
        customer_id=customer_id,
        customer_name=customer_name or "Client",
        checkin_lat=checkin_lat,
        checkin_lng=checkin_lng,
        checkin_address=checkin_address,
        checkin_time=visit_time,
        checkout_time=now,
        photo_url=photo_url,
        visiting_card_url=visiting_card_url,
        customer_requirements=customer_requirements,
        visit_outcome=visit_outcome,
        notes=notes,
        client_token=client_token,
        status="COMPLETED"
    )
    db.add(visit)
    db.flush()

    # 4. Automatic CRM Activity Creation
    desc_parts = [f"Field Visit completed for {visit.customer_name} by {emp.name}."]
    desc_parts.append(f"Outcome: {visit.visit_outcome}")
    if visit.checkin_address or (visit.checkin_lat and visit.checkin_lng):
        loc_str = visit.checkin_address or f"GPS: {visit.checkin_lat}, {visit.checkin_lng}"
        desc_parts.append(f"Location: {loc_str}")
    if visit.customer_requirements:
        desc_parts.append(f"Requirements: {visit.customer_requirements}")
    if visit.notes:
        desc_parts.append(f"Notes: {visit.notes}")
    if visit.photo_url:
        desc_parts.append(f"Company Board Photo: {visit.photo_url}")
    if visit.visiting_card_url:
        desc_parts.append(f"Visiting Card: {visit.visiting_card_url}")

    activity_description = "\n".join(desc_parts)

    activity = LeadActivity(
        lead_id=lead_id,
        customer_id=customer_id,
        employee_id=emp.id,
        performed_by=emp.id,
        activity_type="FIELD_VISIT",
        related_entity_type="FIELD_VISIT",
        related_entity_id=visit.id,
        description=activity_description,
        created_at=now
    )
    db.add(activity)

    emp_log = EmployeeActivityLog(
        employee_id=emp.id,
        activity_type="FIELD_VISIT",
        entity_type="FIELD_VISIT",
        entity_id=visit.id,
        description=f"Field visit at {visit.customer_name} ({visit.visit_outcome})"
    )
    db.add(emp_log)

    # 5. Follow-up Scheduling (Optional)
    schedule_followup = data.get("schedule_followup", False)
    followup_date_str = data.get("followup_date")

    if schedule_followup and followup_date_str and lead_id:
        try:
            fu_date = datetime.strptime(str(followup_date_str).strip(), "%Y-%m-%d").date()
        except ValueError:
            fu_date = date.today() + timedelta(days=2)

        fu_time = data.get("followup_time") or "10:00 AM"
        fu_priority = (data.get("followup_priority") or "MEDIUM").upper()
        fu_notes = data.get("followup_notes") or f"Follow-up after field visit ({visit.visit_outcome})"

        # Check existing pending followup for this lead to avoid duplicates
        existing_fu = db.query(Followup).filter(
            Followup.lead_id == lead_id,
            Followup.status == "Pending"
        ).first()

        if existing_fu:
            existing_fu.followup_date = fu_date
            existing_fu.followup_time = fu_time
            existing_fu.priority = fu_priority
            existing_fu.notes = fu_notes
            existing_fu.assigned_to = emp.id
            existing_fu.reminder_sent = False
            existing_fu.reminder_sent_at = None
            existing_fu.snoozed_until = None
            existing_fu.reminder_dismissed = False
            visit.followup_id = existing_fu.id
            target_fu = existing_fu
        else:
            new_fu = Followup(
                lead_id=lead_id,
                assigned_to=emp.id,
                followup_date=fu_date,
                followup_time=fu_time,
                priority=fu_priority,
                notes=fu_notes,
                status="Pending",
                created_by=emp.id,
                reminder_sent=False,
                reminder_dismissed=False
            )
            db.add(new_fu)
            db.flush()
            visit.followup_id = new_fu.id
            target_fu = new_fu

        # Sync Lead status
        if lead:
            lead.status = "FOLLOW-UP"
            lead.followup_date = fu_date
            lead.followup_time = fu_time

        # Create Follow-up Activity
        fu_activity = LeadActivity(
            lead_id=lead_id,
            customer_id=customer_id,
            employee_id=emp.id,
            performed_by=emp.id,
            activity_type="FOLLOW_UP_SCHEDULED",
            related_entity_type="FOLLOWUP",
            related_entity_id=target_fu.id,
            description=f"Follow-up scheduled for {fu_date} at {fu_time} ({fu_priority} Priority) following field visit. Notes: {fu_notes}",
            created_at=now
        )
        db.add(fu_activity)

    db.commit()
    db.refresh(visit)
    return visit.to_dict()


@router.post("", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
def create_field_visit(
    data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submits a new Field Visit record with:
    - Automatic CRM Activity creation linked to lead/customer and employee
    - Optional follow-up scheduling with 1-hour automated reminder tracking
    - Idempotent duplicate prevention via client_token
    - Full synchronization across mobile app and web CRM
    """
    return handle_field_visit_submission(data, db, current_user)


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_field_visits(
    employee_id: Optional[int] = Query(None, description="Filter by Employee ID"),
    lead_id: Optional[int] = Query(None, description="Filter by Lead ID"),
    customer_id: Optional[int] = Query(None, description="Filter by Customer ID"),
    status: Optional[str] = Query(None, description="Filter by status (COMPLETED, CHECKED_IN)"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves Field Visits respecting backend hierarchy and role permissions:
    - Admin: View all company-wide field visits
    - Sales Manager: View team field visits
    - Sales Executive: Strictly view their own field visits
    """
    authorized_emp_ids = get_authorized_performance_employee_ids(current_user, db)
    if authorized_emp_ids is not None and len(authorized_emp_ids) == 0:
        return []

    query = db.query(FieldVisit)

    if employee_id is not None and isinstance(employee_id, int):
        authorize_employee_access(current_user, employee_id, db)
        query = query.filter(FieldVisit.employee_id == employee_id)
    elif authorized_emp_ids is not None:
        query = query.filter(FieldVisit.employee_id.in_(authorized_emp_ids))

    if lead_id is not None and isinstance(lead_id, int):
        query = query.filter(FieldVisit.lead_id == lead_id)

    if customer_id is not None and isinstance(customer_id, int):
        query = query.filter(FieldVisit.customer_id == customer_id)

    if status is not None and isinstance(status, str):
        query = query.filter(FieldVisit.status == status.upper())

    limit_val = limit if isinstance(limit, int) else 100
    offset_val = offset if isinstance(offset, int) else 0
    visits = query.order_by(desc(FieldVisit.checkin_time)).offset(offset_val).limit(limit_val).all()
    return [v.to_dict() for v in visits]


@router.get("/{visit_id}", response_model=Dict[str, Any])
def get_field_visit_by_id(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    visit = db.query(FieldVisit).filter(FieldVisit.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Field visit not found")

    authorize_employee_access(current_user, visit.employee_id, db)
    return visit.to_dict()
