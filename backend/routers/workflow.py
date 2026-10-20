import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from database import get_db
from models.user import User
from models.employee import Employee
from models.lead import Lead
from models.workflow import FinanceHandoff, SupportHandoff, WorkflowTimelineEvent
from schemas.workflow import (
    FinanceHandoffOut,
    SupportHandoffOut,
    WorkflowTimelineEventOut,
    FinancePaymentConfirmRequest,
    SupportStatusUpdateRequest,
    SupportManagerOut,
    DealWonRequest,
    SupportReassignRequest
)
from services.auth import get_current_user, require_permission
from services.permission_service import user_has_permission, get_user_view_scope
from services.workflow_service import WorkflowService
from services.hierarchy_service import (
    normalize_role,
    get_team_employee_ids_from_user,
    ROLE_ADMIN,
    ROLE_SALES_MANAGER,
    ROLE_SALES_EXECUTIVE,
    ROLE_SUPPORT_MANAGER,
    ROLE_SUPPORT_EXECUTIVE
)

logger = logging.getLogger("workflow_router")

router = APIRouter(prefix="/workflow", tags=["Sales -> Finance -> Support Workflow"])

def get_employee_for_user(user: User, db: Session) -> Optional[Employee]:
    return db.query(Employee).filter(Employee.user_id == user.id).first()

def get_team_employee_ids(manager_emp_id: int, db: Session) -> List[int]:
    subordinates = db.query(Employee.id).filter(Employee.manager_id == manager_emp_id).all()
    sub_ids = [s[0] for s in subordinates]
    return [manager_emp_id] + sub_ids

# ============================================================================
# FINANCE WORKFLOW ENDPOINTS
# ============================================================================

@router.get("/finance/handoffs", response_model=List[FinanceHandoffOut])
def list_finance_handoffs(
    status_filter: Optional[str] = Query("all", alias="status"),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List Finance handoffs based on dynamic database permissions.
    - Users with payments/invoices view permission access the queue.
    - Scoped users (own/team) see their own/team deals with sensitive financial data redacted.
    - Users lacking permission receive HTTP 403.
    """
    can_view_payments = user_has_permission(current_user, "payments", "view", db)
    can_view_invoices = user_has_permission(current_user, "invoices", "view", db)
    can_view_leads = user_has_permission(current_user, "leads", "view", db)

    if not (can_view_payments or can_view_invoices or can_view_leads):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You do not have permission to access the Finance queue."
        )

    q = db.query(FinanceHandoff)

    scope = get_user_view_scope(current_user, "payments", db)
    if scope == "none":
        scope = get_user_view_scope(current_user, "invoices", db)
    if scope == "none":
        scope = get_user_view_scope(current_user, "leads", db)

    current_emp = get_employee_for_user(current_user, db)
    if scope == "own":
        if not current_emp:
            return []
        q = q.filter(FinanceHandoff.sales_employee_id == current_emp.id)
    elif scope == "team":
        if current_emp:
            team_ids = get_team_employee_ids(current_emp.id, db)
            q = q.filter(FinanceHandoff.sales_employee_id.in_(team_ids))
        else:
            return []
    elif scope == "none":
        return []

    if status_filter and status_filter != "all":
        q = q.filter(FinanceHandoff.status == status_filter)

    if search and search.strip():
        term = f"%{search.strip()}%"
        q = q.filter(
            or_(
                FinanceHandoff.customer_name.ilike(term),
                FinanceHandoff.company_name.ilike(term),
                FinanceHandoff.phone.ilike(term),
                FinanceHandoff.email.ilike(term),
                FinanceHandoff.quotation_number.ilike(term),
                FinanceHandoff.invoice_number.ilike(term)
            )
        )

    records = q.order_by(desc(FinanceHandoff.created_at)).offset((page - 1) * limit).limit(limit).all()

    # Sensitive finance data redacted for users without approval or edit rights on payments
    can_manage_finance = (
        user_has_permission(current_user, "payments", "approve", db) or
        user_has_permission(current_user, "payments", "edit", db) or
        user_has_permission(current_user, "invoices", "approve", db)
    )

    output = []
    for r in records:
        out_dict = FinanceHandoffOut.from_orm(r)
        if not can_manage_finance:
            out_dict.bank_reference = None
            out_dict.bank_name = None
            out_dict.internal_finance_notes = None
        output.append(out_dict)

    return output

@router.get("/finance/handoffs/{handoff_id}", response_model=FinanceHandoffOut)
def get_finance_handoff_detail(
    handoff_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get details of a specific finance handoff.
    Sensitive financial notes and bank details are redacted for non-finance managers.
    """
    can_view_payments = user_has_permission(current_user, "payments", "view", db)
    can_view_invoices = user_has_permission(current_user, "invoices", "view", db)
    can_view_leads = user_has_permission(current_user, "leads", "view", db)

    if not (can_view_payments or can_view_invoices or can_view_leads):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    handoff = db.query(FinanceHandoff).filter(FinanceHandoff.id == handoff_id).first()
    if not handoff:
        raise HTTPException(status_code=404, detail="Finance handoff not found.")

    scope = get_user_view_scope(current_user, "payments", db)
    if scope == "none":
        scope = get_user_view_scope(current_user, "invoices", db)
    if scope == "none":
        scope = get_user_view_scope(current_user, "leads", db)

    current_emp = get_employee_for_user(current_user, db)
    if scope == "own":
        if not current_emp or handoff.sales_employee_id != current_emp.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this deal.")
    elif scope == "team":
        if not current_emp:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this deal.")
        team_ids = get_team_employee_ids(current_emp.id, db)
        if handoff.sales_employee_id not in team_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this deal.")

    can_manage_finance = (
        user_has_permission(current_user, "payments", "approve", db) or
        user_has_permission(current_user, "payments", "edit", db) or
        user_has_permission(current_user, "invoices", "approve", db)
    )

    out = FinanceHandoffOut.from_orm(handoff)
    if not can_manage_finance:
        out.bank_reference = None
        out.bank_name = None
        out.internal_finance_notes = None
    return out

@router.post("/finance/handoffs/{handoff_id}/confirm-payment", response_model=FinanceHandoffOut)
def confirm_finance_payment(
    handoff_id: int,
    payload: FinancePaymentConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("payments", "approve"))
):
    """
    Finance confirms customer payment (status -> PAID).
    Requires 'approve' permission on 'payments' module.
    """
    try:
        updated_handoff = WorkflowService.confirm_finance_payment(
            db=db,
            handoff_id=handoff_id,
            payment_data=payload.dict(),
            current_user=current_user
        )
        return updated_handoff
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error confirming payment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to confirm payment: {str(e)}")

@router.get("/finance/handoffs/{handoff_id}/download-invoice")
def download_finance_handoff_invoice(
    handoff_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Downloads official statutory Tax Invoice PDF for a finance handoff record.
    Accessible to authorized users (Finance, Admin, Managers).
    If an official Quotation record is missing, it dynamically synthesizes and records it.
    """
    can_view = (
        user_has_permission(current_user, "invoices", "view", db) or
        user_has_permission(current_user, "payments", "view", db) or
        user_has_permission(current_user, "leads", "view", db)
    )
    if not can_view:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    handoff = db.query(FinanceHandoff).filter(FinanceHandoff.id == handoff_id).first()
    if not handoff:
        raise HTTPException(status_code=404, detail="Finance handoff not found.")

    from models.quotation import Quotation
    doc = None
    if handoff.invoice_number:
        doc = db.query(Quotation).filter(Quotation.doc_number == handoff.invoice_number.strip()).first()
    if not doc and handoff.lead_id:
        doc = db.query(Quotation).filter(
            Quotation.lead_id == handoff.lead_id,
            Quotation.doc_type == "invoice"
        ).order_by(desc(Quotation.created_at)).first()

    if not doc:
        # Reconstruct and persist the statutory Tax Invoice from handoff
        invoice_num = handoff.invoice_number or f"CHN/INV/26/{handoff.id:04d}"
        paid_amt = float(handoff.paid_amount or handoff.final_amount or 0.0)
        sub_val = round(paid_amt / 1.18, 2)
        tax_val = round(paid_amt - sub_val, 2)
        cgst_val = round(tax_val / 2.0, 2)
        sgst_val = round(tax_val / 2.0, 2)

        line_items_data = handoff.products_services or [
            {
                "description": handoff.customer_requirements or "WAHRMS Business Solution Subscription",
                "qty": 1,
                "rate": paid_amt,
                "amount": paid_amt
            }
        ]

        doc = Quotation(
            doc_type="invoice",
            doc_number=invoice_num,
            status="issued",
            payment_status="paid" if handoff.status == "PAID" else "unpaid",
            lead_id=handoff.lead_id,
            customer_id=handoff.customer_id,
            customer_name=handoff.customer_name or "Valued Client",
            company_name=handoff.company_name or "",
            phone=handoff.phone or "",
            email=handoff.email or "",
            address=handoff.address or "Chennai, Tamil Nadu",
            state="Tamil Nadu",
            state_code="33",
            tax_mode="intra",
            subtotal=sub_val,
            cgst=cgst_val,
            sgst=sgst_val,
            igst=0.0,
            tax_total=tax_val,
            grand_total=paid_amt,
            amount_paid=paid_amt if handoff.status == "PAID" else 0.0,
            line_items=line_items_data,
            terms_and_conditions="1. Payment received and verified by Finance.\n2. Goods/Services supplied as per Purchase Order.\n3. Subject to Chennai jurisdiction.",
            prepared_by=getattr(current_user, 'full_name', None) or getattr(current_user, 'name', None) or current_user.username or "Finance Department",
            issue_date=handoff.payment_date or handoff.confirmed_at or handoff.created_at or datetime.utcnow()
        )
        db.add(doc)
        handoff.invoice_number = invoice_num
        handoff.invoice_url = f"/api/integrations/waquote/invoices/{invoice_num}/download"
        db.commit()
        db.refresh(doc)

    from services.pdf_service import generate_tax_invoice_pdf
    pdf_bytes = generate_tax_invoice_pdf(doc)
    clean_num = (doc.doc_number or f"INV-{doc.id}").replace("/", "-").replace("\\", "-")
    filename = f"Tax_Invoice_{clean_num}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Document-Type": "invoice"
        }
    )

# ============================================================================
# SUPPORT ONBOARDING ENDPOINTS
# ============================================================================

# ============================================================================
# SUPPORT WORKFLOW & ASSIGNMENT ENDPOINTS
# ============================================================================

@router.get("/support-managers", response_model=List[SupportManagerOut])
def list_support_managers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns list of active users who have the Support Manager role.
    Used for the required 'Assign to Support Manager' dropdown in Sales Deal WON workflow.
    """
    managers = WorkflowService.get_active_support_managers(db)
    return managers

@router.get("/support/handoffs", response_model=List[SupportHandoffOut])
def list_support_handoffs(
    status_filter: Optional[str] = Query("all", alias="status"),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List Support onboarding queue.
    - Support Managers see their own and their Support Executives' onboarding assignments.
    - Support Executives see ONLY assignments assigned to them.
    - Admins see company-wide records.
    - Sales roles are strictly forbidden from internal support tickets.
    """
    norm_role = normalize_role(current_user.role)
    if norm_role in [ROLE_SALES_MANAGER, ROLE_SALES_EXECUTIVE]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Sales team cannot access internal Support onboarding and tickets."
        )

    if not user_has_permission(current_user, "support_tickets", "view", db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to Support onboarding queue.")

    q = db.query(SupportHandoff)
    current_emp = get_employee_for_user(current_user, db)

    if norm_role == ROLE_SUPPORT_EXECUTIVE:
        if not current_emp:
            return []
        q = q.filter(SupportHandoff.assigned_agent_id == current_emp.id)
    elif norm_role == ROLE_SUPPORT_MANAGER:
        if not current_emp:
            return []
        team_emp_ids = get_team_employee_ids_from_user(current_user, db)
        q = q.filter(
            or_(
                SupportHandoff.support_manager_id == current_emp.id,
                SupportHandoff.assigned_agent_id.in_(team_emp_ids)
            )
        )
    elif norm_role != ROLE_ADMIN:
        scope = get_user_view_scope(current_user, "support_tickets", db)
        if scope == "own":
            if not current_emp:
                return []
            q = q.filter(SupportHandoff.assigned_agent_id == current_emp.id)
        elif scope == "team":
            if not current_emp:
                return []
            team_ids = get_team_employee_ids_from_user(current_user, db)
            q = q.filter(
                or_(
                    SupportHandoff.support_manager_id.in_(team_ids),
                    SupportHandoff.assigned_agent_id.in_(team_ids)
                )
            )
        elif scope == "none":
            return []

    if status_filter and status_filter != "all":
        q = q.filter(SupportHandoff.onboarding_status == status_filter)

    if search and search.strip():
        term = f"%{search.strip()}%"
        q = q.filter(
            or_(
                SupportHandoff.customer_name.ilike(term),
                SupportHandoff.company_name.ilike(term),
                SupportHandoff.product_service.ilike(term),
                SupportHandoff.support_manager_name.ilike(term),
                SupportHandoff.phone.ilike(term),
                SupportHandoff.email.ilike(term),
                SupportHandoff.invoice_number.ilike(term),
                SupportHandoff.quotation_number.ilike(term)
            )
        )

    records = q.order_by(desc(SupportHandoff.created_at)).offset((page - 1) * limit).limit(limit).all()
    return records

@router.get("/support/handoffs/{support_id}", response_model=SupportHandoffOut)
def get_support_handoff_detail(
    support_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get Support onboarding record details.
    """
    norm_role = normalize_role(current_user.role)
    if norm_role in [ROLE_SALES_MANAGER, ROLE_SALES_EXECUTIVE]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Sales team cannot access internal Support onboarding and tickets."
        )

    if not user_has_permission(current_user, "support_tickets", "view", db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    record = db.query(SupportHandoff).filter(SupportHandoff.id == support_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Support onboarding record not found.")

    current_emp = get_employee_for_user(current_user, db)

    if norm_role == ROLE_SUPPORT_EXECUTIVE:
        if not current_emp or record.assigned_agent_id != current_emp.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: You can only view assignments given to you.")
    elif norm_role == ROLE_SUPPORT_MANAGER:
        team_emp_ids = get_team_employee_ids_from_user(current_user, db)
        if not current_emp or (record.support_manager_id != current_emp.id and record.assigned_agent_id not in team_emp_ids):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: You can only view assignments for your support team.")
    elif norm_role != ROLE_ADMIN:
        scope = get_user_view_scope(current_user, "support_tickets", db)
        if scope == "own":
            if not current_emp or record.assigned_agent_id != current_emp.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
        elif scope == "team":
            team_ids = get_team_employee_ids_from_user(current_user, db)
            if not current_emp or (record.support_manager_id not in team_ids and record.assigned_agent_id not in team_ids):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    return record

@router.put("/support/handoffs/{support_id}/status", response_model=SupportHandoffOut)
def update_support_onboarding_status(
    support_id: int,
    payload: SupportStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("support_tickets", "edit"))
):
    """
    Support team updates onboarding lifecycle.
    Support Managers can only manage assignments given to them.
    """
    record = db.query(SupportHandoff).filter(SupportHandoff.id == support_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Support onboarding record not found.")

    norm_role = (current_user.role or "").strip().upper()
    current_emp = get_employee_for_user(current_user, db)
    if norm_role in ["SUPPORT_MANAGER", "SUPPORT"]:
        if not current_emp or (record.support_manager_id != current_emp.id and record.assigned_agent_id != current_emp.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: You can only manage assignments given to you.")

    try:
        updated = WorkflowService.update_support_status(
            db=db,
            support_id=support_id,
            update_data=payload.dict(exclude_unset=True),
            current_user=current_user
        )
        return updated
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error updating support status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update support status: {str(e)}")

@router.put("/support/handoffs/{support_id}/reassign", response_model=SupportHandoffOut)
def reassign_support_manager(
    support_id: int,
    payload: SupportReassignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Admin reassigns Support Manager for an onboarding handoff.
    Restricted to Admin.
    """
    norm_role = (current_user.role or "").strip().upper()
    can_reassign = norm_role == "ADMIN" or user_has_permission(current_user, "support_tickets", "assign", db)
    if not can_reassign:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: Only Admin can reassign the Support Manager.")

    try:
        updated = WorkflowService.reassign_support_manager(
            db=db,
            support_id=support_id,
            new_manager_id=payload.support_manager_id,
            current_user=current_user
        )
        return updated
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error reassigning support manager: {e}", exc_info=True)
@router.get("/deal/{lead_id}/proformas")
@router.get("/leads/{lead_id}/proformas")
def get_deal_proformas(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetches all authoritative Proforma Invoices belonging to a lead/customer.
    Returns product details, line items, user counts, bundles, and add-ons.
    """
    try:
        return WorkflowService.get_lead_proforma_invoices(db=db, lead_id=lead_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error fetching proformas for lead {lead_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch proforma invoices: {str(e)}")

@router.post("/deal/{lead_id}/won")
def mark_deal_won_workflow(
    lead_id: int,
    payload: DealWonRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Sales marks a deal as WON and assigns it to a Support Manager.
    Requires edit permission on leads module.
    Enforces mandatory Support Manager assignment.
    """
    can_edit = user_has_permission(current_user, "leads", "edit", db) or current_user.role in ["ADMIN", "MANAGER", "SALES"]
    if not can_edit:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to close deals as WON.")

    if not payload.support_manager_id or payload.support_manager_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please assign a Support Manager before marking this deal as WON."
        )

    try:
        result = WorkflowService.complete_deal_won_workflow(
            db=db,
            lead_id=lead_id,
            won_data=payload.dict(exclude_unset=True),
            current_user=current_user
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Error marking deal won: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process deal WON workflow: {str(e)}")

# ============================================================================
# AUDIT & TIMELINE ENDPOINTS
# ============================================================================

@router.get("/deal/{lead_id}/summary")
def get_deal_workflow_summary(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Provides an integrated cross-team summary (Sales -> Finance -> Support) for a specific deal.
    """
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Deal/Lead not found.")

    finance = db.query(FinanceHandoff).filter(FinanceHandoff.lead_id == lead_id).first()
    support = db.query(SupportHandoff).filter(SupportHandoff.lead_id == lead_id).first()

    can_manage_finance = (
        user_has_permission(current_user, "payments", "approve", db) or
        user_has_permission(current_user, "payments", "edit", db) or
        user_has_permission(current_user, "invoices", "approve", db)
    )

    finance_dict = None
    if finance:
        finance_dict = FinanceHandoffOut.from_orm(finance).dict()
        if not can_manage_finance:
            finance_dict["bank_reference"] = None
            finance_dict["bank_name"] = None
            finance_dict["internal_finance_notes"] = None

    support_dict = SupportHandoffOut.from_orm(support).dict() if support else None

    return {
        "ok": True,
        "lead_id": lead.id,
        "customer_id": lead.customer.id if lead.customer else (finance.customer_id if finance else None),
        "sales_stage": lead.status,
        "finance_stage": finance.status if finance else "NOT_INITIATED",
        "support_stage": support.onboarding_status if support else "NOT_INITIATED",
        "finance": finance_dict,
        "support": support_dict
    }

@router.get("/deal/{lead_id}/timeline", response_model=List[WorkflowTimelineEventOut])
def get_deal_workflow_timeline(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns auditable timeline events across Sales, Finance, and Support for a deal.
    """
    events = db.query(WorkflowTimelineEvent).filter(
        WorkflowTimelineEvent.lead_id == lead_id
    ).order_by(desc(WorkflowTimelineEvent.created_at)).all()
    return events

@router.post("/deal/{lead_id}/handoff-to-finance")
def trigger_manual_finance_handoff(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Explicitly trigger or re-sync Finance handoff for a Deal.
    Requires edit permission on leads.
    """
    if not user_has_permission(current_user, "leads", "edit", db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    scope = get_user_view_scope(current_user, "leads", db)
    if scope == "own":
        current_emp = get_employee_for_user(current_user, db)
        if not current_emp or lead.assigned_to != current_emp.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    handoff = WorkflowService.trigger_finance_handoff_on_won(db=db, lead=lead, performed_by_user=current_user)
    return {
        "ok": True,
        "message": f"Finance handoff created for deal #{lead.id}",
        "handoff_id": handoff.id,
        "status": handoff.status
    }
