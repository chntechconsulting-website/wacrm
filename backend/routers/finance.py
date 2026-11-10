import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from models.employee import Employee
from services.auth import get_current_user
from services.hierarchy_service import normalize_role, normalize_department, ROLE_ADMIN
from services.finance_service import FinanceService
from utils.document_status import invoice_document_status

logger = logging.getLogger("finance_router")

router = APIRouter(prefix="/finance", tags=["Finance Management"])

def require_finance_or_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """
    Enforces strict role-based authorization for the Finance dashboard and APIs.
    Only users with role ADMIN or department/role FINANCE are permitted.
    Sales and Support employees receive HTTP 403 Forbidden.
    """
    user_role = normalize_role(current_user.role)
    user_dept = normalize_department(current_user.department)

    # Check employee record if user department isn't explicit
    emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
    emp_role = normalize_role(emp.role) if emp else ""
    emp_dept = normalize_department(emp.department) if emp else ""

    is_admin = user_role == ROLE_ADMIN or emp_role == ROLE_ADMIN
    is_finance = (
        user_role == "FINANCE" or
        emp_role == "FINANCE" or
        user_dept == "FINANCE" or
        emp_dept == "FINANCE"
    )

    if not (is_admin or is_finance):
        logger.warning(f"Forbidden finance access attempt by user {current_user.username} (role: {user_role}, dept: {user_dept})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You do not have permission to access the Finance module."
        )

    return current_user


# =============================================================================
# SCHEMAS
# =============================================================================
class InvoiceItemInput(BaseModel):
    description: str
    qty: float = 1.0
    rate: float = 0.0
    amount: Optional[float] = None

class CreateInvoiceRequest(BaseModel):
    customer_id: Optional[int] = None
    customer_name: Optional[str] = "Valued Client"
    company_name: Optional[str] = ""
    phone: Optional[str] = ""
    email: Optional[str] = ""
    address: Optional[str] = ""
    state: Optional[str] = "Tamil Nadu"
    state_code: Optional[str] = "33"
    gstin: Optional[str] = ""
    invoice_number: Optional[str] = None
    line_items: List[InvoiceItemInput] = []
    terms_and_conditions: Optional[str] = None
    notes: Optional[str] = None
    issue_date: Optional[str] = None
    due_date: Optional[str] = None
    amount_paid: Optional[float] = 0.0
    payment_method: Optional[str] = "BANK_TRANSFER"
    transaction_reference: Optional[str] = None
    bank_name: Optional[str] = None

class RecordPaymentRequest(BaseModel):
    customer_id: Optional[int] = None
    invoice_id: Optional[int] = None
    finance_handoff_id: Optional[int] = None
    lead_id: Optional[int] = None
    amount: float
    payment_method: str = "BANK_TRANSFER"
    transaction_reference: Optional[str] = None
    bank_name: Optional[str] = None
    payment_date: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = "PAID"

class RazorpayVerifyRequest(BaseModel):
    customer_id: Optional[int] = None
    invoice_id: Optional[int] = None
    finance_handoff_id: Optional[int] = None
    amount: float
    razorpay_order_id: Optional[str] = None
    razorpay_payment_id: str
    razorpay_signature: Optional[str] = None
    notes: Optional[str] = None

class ChangePlanRequest(BaseModel):
    plan_code: str
    licence_count: int = 1

class AddAddonRequest(BaseModel):
    name: str
    code: str
    amount: float
    qty: int = 1

class RenewalRequest(BaseModel):
    payment_method: str = "BANK_TRANSFER"
    transaction_reference: Optional[str] = None

class CreateRefundRequest(BaseModel):
    customer_id: int
    amount: float
    reason: str
    payment_id: Optional[int] = None
    invoice_id: Optional[int] = None

class UpdateRefundStatusRequest(BaseModel):
    status: str # APPROVED, REJECTED, PROCESSED
    transaction_reference: Optional[str] = None
    rejection_reason: Optional[str] = None


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/dashboard/stats")
def get_dashboard_stats(
    period: str = Query("month"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_finance_or_admin)
):
    """
    Returns verified KPI metrics, monthly trend, and breakdown for Finance Dashboard.
    """
    try:
        return FinanceService.get_dashboard_kpis(db=db, period=period)
    except Exception as e:
        logger.error(f"Error computing finance dashboard stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load finance dashboard KPIs.")


# --- INVOICES ---
@router.get("/invoices")
def list_invoices(
    status: Optional[str] = Query("all"),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_finance_or_admin)
):
    """List invoices with filters and pagination."""
    return FinanceService.list_invoices(
        db=db,
        status_filter=status,
        search=search,
        limit=limit,
        page=page
    )

@router.post("/invoices")
def create_invoice(
    payload: CreateInvoiceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_finance_or_admin)
):
    """Generate and record a new statutory Tax Invoice."""
    try:
        data = payload.dict()
        doc = FinanceService.generate_invoice(db=db, data=data, creator_user=current_user)
        return {
            "success": True,
            "message": f"Tax Invoice {doc.doc_number} generated successfully.",
            "invoice_id": doc.id,
            "invoice_number": doc.doc_number,
            "grand_total": doc.grand_total,
            "status": invoice_document_status(doc),
            "payment_status": doc.payment_status
        }
    except Exception as e:
        logger.error(f"Error generating invoice: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate invoice: {str(e)}")

@router.get("/invoices/{invoice_id}")
def get_invoice_detail(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_finance_or_admin)
):
    """Get full detail of a specific invoice."""
    inv = FinanceService.get_invoice_detail(db=db, invoice_id=invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return inv

@router.get("/invoices/{invoice_id}/pdf")
def download_invoice_pdf(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_finance_or_admin)
):
    """Stream official statutory Tax Invoice PDF."""
    try:
        pdf_bytes = FinanceService.render_invoice_pdf(db=db, invoice_id=invoice_id)
        filename = f"Tax_Invoice_{invoice_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{filename}"'}
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error generating invoice PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to render invoice PDF.")


# --- PAYMENTS ---
@router.get("/payments")
def list_payments(
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    method: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_finance_or_admin)
):
    """List payment transactions."""
    return FinanceService.list_payments(
        db=db,
        status_filter=status,
        payment_type=type,
        payment_method=method,
        search=search,
        limit=limit,
        page=page
    )

@router.post("/payments/manual")
def record_manual_payment(
    payload: RecordPaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_finance_or_admin)
):
    """Record manual payment (Bank transfer, cheque, cash, UPI, card)."""
    try:
        data = payload.dict()
        pay = FinanceService.record_manual_payment(db=db, data=data, user=current_user)
        return {
            "success": True,
            "message": f"Payment {pay.payment_number} recorded successfully.",
            "payment_id": pay.id,
            "payment_number": pay.payment_number,
            "amount": pay.amount,
            "status": pay.status
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error recording payment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to record payment: {str(e)}")

@router.post("/payments/razorpay/verify")
def verify_razorpay_payment(
    payload: RazorpayVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_finance_or_admin)
):
    """Record online payment via Razorpay reference verification."""
    try:
        data = payload.dict()
        pay = FinanceService.process_razorpay_payment(db=db, data=data, user=current_user)
        return {
            "success": True,
            "message": f"Online Payment {pay.payment_number} verified and recorded.",
            "payment_id": pay.id,
            "payment_number": pay.payment_number,
            "amount": pay.amount,
            "status": pay.status
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error processing razorpay payment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to verify payment: {str(e)}")


# --- CUSTOMER PURCHASE DETAILS ---
@router.get("/customer-purchases")
def list_customer_purchases(
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_finance_or_admin)
):
    """
    List converted customer purchase details (Sales rep, plan, add-ons, GST, status, renewal date).
    """
    return FinanceService.get_customer_purchases(
        db=db,
        search=search,
        limit=limit,
        page=page
    )


# --- SUBSCRIPTIONS & RENEWALS ---
@router.get("/subscriptions")
def list_subscriptions(
    status: Optional[str] = Query("all"),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_finance_or_admin)
):
    """List active, upcoming renewal, or expired subscriptions."""
    return FinanceService.list_subscriptions(
        db=db,
        status_filter=status,
        search=search,
        limit=limit,
        page=page
    )

@router.post("/subscriptions/{subscription_id}/upgrade-downgrade")
def change_subscription_plan(
    subscription_id: int,
    payload: ChangePlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_finance_or_admin)
):
    """Upgrade or downgrade customer subscription plan."""
    try:
        sub = FinanceService.change_subscription_plan(
            db=db,
            subscription_id=subscription_id,
            new_plan_code=payload.plan_code,
            new_licence_count=payload.licence_count,
            user=current_user
        )
        return {
            "success": True,
            "message": f"Subscription plan updated to {sub.plan_name}.",
            "subscription_id": sub.id,
            "plan_name": sub.plan_name,
            "licence_count": sub.licence_count,
            "total_amount": sub.total_amount
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error modifying subscription: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to modify subscription.")

@router.post("/subscriptions/{subscription_id}/add-on")
def add_addon(
    subscription_id: int,
    payload: AddAddonRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_finance_or_admin)
):
    """Add add-on product to active subscription."""
    try:
        sub = FinanceService.add_addon_to_subscription(
            db=db,
            subscription_id=subscription_id,
            addon_name=payload.name,
            addon_code=payload.code,
            addon_amount=payload.amount,
            qty=payload.qty,
            user=current_user
        )
        return {
            "success": True,
            "message": f"Add-on '{payload.name}' added successfully.",
            "subscription_id": sub.id,
            "total_amount": sub.total_amount,
            "addons": sub.addons_data
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error adding addon: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to add add-on.")

@router.post("/subscriptions/{subscription_id}/renew")
def renew_subscription(
    subscription_id: int,
    payload: RenewalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_finance_or_admin)
):
    """Process annual subscription renewal and payment tracking."""
    try:
        sub = FinanceService.process_renewal(
            db=db,
            subscription_id=subscription_id,
            payment_method=payload.payment_method,
            transaction_reference=payload.transaction_reference,
            user=current_user
        )
        return {
            "success": True,
            "message": f"Subscription renewed successfully until {sub.renewal_date.strftime('%Y-%m-%d')}.",
            "subscription_id": sub.id,
            "renewal_date": sub.renewal_date.isoformat(),
            "status": sub.status
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error renewing subscription: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to renew subscription.")


# --- REFUNDS ---
@router.get("/refunds")
def list_refunds(
    status: Optional[str] = Query("all"),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_finance_or_admin)
):
    """List refund requests with status filter."""
    return FinanceService.list_refunds(
        db=db,
        status_filter=status,
        search=search,
        limit=limit,
        page=page
    )

@router.post("/refunds")
def create_refund_request(
    payload: CreateRefundRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_finance_or_admin)
):
    """Submit a refund request."""
    try:
        ref = FinanceService.create_refund_request(
            db=db,
            customer_id=payload.customer_id,
            amount=payload.amount,
            reason=payload.reason,
            payment_id=payload.payment_id,
            invoice_id=payload.invoice_id,
            user=current_user
        )
        return {
            "success": True,
            "message": f"Refund request {ref.refund_number} submitted.",
            "refund_id": ref.id,
            "refund_number": ref.refund_number,
            "status": ref.status
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error creating refund: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to submit refund request.")

@router.put("/refunds/{refund_id}/status")
def update_refund_status(
    refund_id: int,
    payload: UpdateRefundStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_finance_or_admin)
):
    """Update refund status (Approve, Reject, Mark Processed)."""
    try:
        ref = FinanceService.update_refund_status(
            db=db,
            refund_id=refund_id,
            new_status=payload.status,
            transaction_reference=payload.transaction_reference,
            rejection_reason=payload.rejection_reason,
            user=current_user
        )
        return {
            "success": True,
            "message": f"Refund request {ref.refund_number} updated to {ref.status}.",
            "refund_id": ref.id,
            "status": ref.status
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error updating refund status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update refund status.")


# --- FINANCIAL REPORTS ---
@router.get("/reports")
def get_financial_report(
    type: str = Query("monthly"), # daily, monthly, yearly, collections, gst, refunds
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_finance_or_admin)
):
    """Retrieve financial report data."""
    s_dt = None
    e_dt = None
    if start_date:
        try:
            s_dt = datetime.fromisoformat(start_date.replace("Z", ""))
        except Exception:
            pass
    if end_date:
        try:
            e_dt = datetime.fromisoformat(end_date.replace("Z", ""))
        except Exception:
            pass

    return FinanceService.get_revenue_report(
        db=db,
        report_type=type,
        start_date=s_dt,
        end_date=e_dt
    )

@router.get("/reports/export-csv")
def export_report_csv(
    type: str = Query("monthly"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_finance_or_admin)
):
    """Export financial report as CSV."""
    s_dt = None
    e_dt = None
    if start_date:
        try:
            s_dt = datetime.fromisoformat(start_date.replace("Z", ""))
        except Exception:
            pass
    if end_date:
        try:
            e_dt = datetime.fromisoformat(end_date.replace("Z", ""))
        except Exception:
            pass

    data = FinanceService.get_revenue_report(
        db=db,
        report_type=type,
        start_date=s_dt,
        end_date=e_dt
    )
    csv_content = FinanceService.export_report_csv(data)
    filename = f"{type}_financial_report_{datetime.utcnow().strftime('%Y%m%d')}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
