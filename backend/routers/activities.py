from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc

from database import get_db
from models import LeadActivity, Lead, Customer, Employee, User
from services.auth import get_current_user
from services.activity_visibility_service import (
    apply_activity_visibility_filter,
    apply_admin_activity_department_filter,
    apply_support_lead_scope,
    user_activity_department,
)
from services.hierarchy_service import ROLE_ADMIN, normalize_role

router = APIRouter(prefix="/activities", tags=["Activities"])

@router.get("", response_model=List[dict])
@router.get("/", response_model=List[dict])
def get_activities(
    lead_id: Optional[int] = Query(None, description="Filter activities by Lead ID"),
    customer_id: Optional[int] = Query(None, description="Filter activities by Customer ID"),
    employee_id: Optional[int] = Query(None, description="Filter activities by Employee ID"),
    type: Optional[str] = Query(None, alias="activity_type", description="Filter by activity type (CALL, FOLLOWUP, WHATSAPP, STATUS_CHANGED, etc.)"),
    activity_type: Optional[str] = Query(None, description="Alternative alias for activity_type"),
    source: Optional[str] = Query(None, description="Filter by Lead Source (META, WEBSITE, MANUAL, EXCEL)"),
    scope: Optional[str] = Query(None, description="Activity Scope (MY, MANAGER, ADMIN, ALL)"),
    department: Optional[str] = Query(None, description="Admin-only department filter (SALES, SUPPORT)"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Contextual, role-scoped, and filterable Activity Audit Stream API.
    Supports filtering by lead_id, customer_id, employee_id, activity_type, source, and scope.
    """
    query = db.query(LeadActivity).outerjoin(Lead, LeadActivity.lead_id == Lead.id)

    # 0. Strict department isolation. This runs before every user-supplied
    # filter and cannot be bypassed with scope=ALL or employee_id.
    query = apply_activity_visibility_filter(query, current_user, db)
    query = apply_support_lead_scope(query, current_user, db)

    if department is not None and str(department).strip():
        if normalize_role(current_user.role) != ROLE_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Department filtering is available to Administrators only.",
            )
        try:
            query = apply_admin_activity_department_filter(query, db, department)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    # 1. Lead ID Filter
    if lead_id is not None:
        query = query.filter(LeadActivity.lead_id == lead_id)

    # 2. Customer ID Filter
    if customer_id is not None:
        query = query.filter(
            or_(
                LeadActivity.customer_id == customer_id,
                and_(LeadActivity.related_entity_type == "CUSTOMER", LeadActivity.related_entity_id == customer_id)
            )
        )

    # 3. Employee ID Filter
    if employee_id is not None:
        query = query.filter(
            or_(
                LeadActivity.performed_by == employee_id,
                LeadActivity.employee_id == employee_id,
                Lead.assigned_to == employee_id
            )
        )

    # 4. Activity Type / Category Filter
    target_type = (type or activity_type or "").upper().strip()
    if target_type:
        if target_type == "CALL":
            query = query.filter(
                or_(
                    LeadActivity.activity_type.ilike("%CALL%"),
                    LeadActivity.related_entity_type == "CALL"
                )
            )
        elif target_type in ["FOLLOWUP", "FOLLOW_UP"]:
            query = query.filter(
                or_(
                    LeadActivity.activity_type.ilike("%FOLLOW%"),
                    LeadActivity.related_entity_type == "FOLLOWUP"
                )
            )
        elif target_type == "WHATSAPP":
            query = query.filter(
                or_(
                    LeadActivity.activity_type.ilike("%WHATSAPP%"),
                    LeadActivity.related_entity_type == "WHATSAPP"
                )
            )
        elif target_type in ["FIELD_VISIT", "VISIT"]:
            query = query.filter(
                or_(
                    LeadActivity.activity_type.ilike("%VISIT%"),
                    LeadActivity.related_entity_type == "FIELD_VISIT"
                )
            )
        else:
            query = query.filter(
                or_(
                    LeadActivity.activity_type.ilike(f"%{target_type}%"),
                    LeadActivity.related_entity_type == target_type
                )
            )

    # 5. Lead Source Filter (META, WEBSITE, MANUAL, EXCEL)
    if source and source.strip():
        src_upper = source.upper().strip()
        if src_upper in ["META", "META ADS", "META_ADS"]:
            query = query.filter(
                or_(
                    Lead.source.ilike("%META%"),
                    Lead.source == "INSTAGRAM",
                    Lead.source == "Instagram",
                )
            )
        else:
            query = query.filter(Lead.source.ilike(f"%{src_upper}%"))

    # 6. Role & Scope Enforcement (Backend Level Authorization)
    user_role = (current_user.role or "").upper()
    emp_id = current_user.employee.id if (hasattr(current_user, 'employee') and current_user.employee) else None

    target_scope = (scope or "").upper()
    if target_scope == "MY" or (user_role == "EMPLOYEE" and target_scope != "ALL"):
        if emp_id:
            query = query.filter(
                or_(
                    LeadActivity.performed_by == emp_id,
                    LeadActivity.employee_id == emp_id,
                    Lead.assigned_to == emp_id
                )
            )
    elif target_scope == "MANAGER" or user_role == "MANAGER":
        if emp_id:
            subordinates = db.query(Employee.id).filter(Employee.manager_id == emp_id).all()
            sub_ids = [s[0] for s in subordinates]
            sub_ids.append(emp_id)
            query = query.filter(
                or_(
                    LeadActivity.performed_by.in_(sub_ids),
                    LeadActivity.employee_id.in_(sub_ids),
                    Lead.assigned_to.in_(sub_ids)
                )
            )

    # 7. Execution & Pagination
    activities = query.order_by(desc(LeadActivity.created_at)).offset(offset).limit(limit).all()

    return [act.to_dict() for act in activities]


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_activity(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Log a new custom activity record.
    """
    act_type = payload.get("activity_type") or "NOTE_ADDED"
    desc = payload.get("description")
    if not desc or not desc.strip():
        raise HTTPException(status_code=400, detail="Activity description is required.")

    lead_id = payload.get("lead_id")
    customer_id = payload.get("customer_id")
    emp_id = current_user.employee.id if (hasattr(current_user, 'employee') and current_user.employee) else None
    employee_id = payload.get("employee_id") or emp_id
    related_type = payload.get("related_entity_type")
    related_id = payload.get("related_entity_id")

    new_act = LeadActivity(
        lead_id=lead_id,
        customer_id=customer_id,
        employee_id=employee_id,
        performed_by=emp_id,
        activity_type=act_type,
        related_entity_type=related_type,
        related_entity_id=related_id,
        department=user_activity_department(current_user, db),
        description=desc.strip()
    )
    db.add(new_act)
    db.commit()
    db.refresh(new_act)

    return new_act.to_dict()
