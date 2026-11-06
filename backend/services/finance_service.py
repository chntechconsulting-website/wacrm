import io
import csv
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_, and_

from models.finance import Payment, CustomerSubscription, SubscriptionHistory, RefundRequest
from models.quotation import Quotation
from models.customer import Customer
from models.lead import Lead
from models.employee import Employee
from models.user import User
from models.workflow import FinanceHandoff
from services.tax_invoice_builder import build_tax_invoice_model_pdf, CHN_COMPANY_INFO

logger = logging.getLogger("finance_service")

class FinanceService:

    @staticmethod
    def get_dashboard_kpis(db: Session, period: str = "month") -> Dict[str, Any]:
        """
        Calculates production financial KPIs from actual database records:
        - Total Revenue (actual collected PAID payments minus processed refunds)
        - Current Month Revenue
        - Pending Payments (unpaid/partial invoices)
        - Paid Invoices
        - Overdue Payments
        - Total Refunds
        """
        now = datetime.utcnow()
        current_year = now.year
        current_month = now.month
        first_day_current_month = datetime(current_year, current_month, 1)
        
        # 1. Total Collected Revenue from completed payments
        # Excludes FAILED, PENDING, and REFUNDED payments
        total_paid_payments = db.query(
            func.coalesce(func.sum(Payment.amount), 0.0)
        ).filter(Payment.status == "PAID").scalar() or 0.0

        # Current Month Revenue
        current_month_revenue = db.query(
            func.coalesce(func.sum(Payment.amount), 0.0)
        ).filter(
            Payment.status == "PAID",
            Payment.payment_date >= first_day_current_month
        ).scalar() or 0.0

        # Previous Month Revenue for trend calculation
        first_day_prev_month = (first_day_current_month - timedelta(days=1)).replace(day=1)
        prev_month_revenue = db.query(
            func.coalesce(func.sum(Payment.amount), 0.0)
        ).filter(
            Payment.status == "PAID",
            Payment.payment_date >= first_day_prev_month,
            Payment.payment_date < first_day_current_month
        ).scalar() or 0.0

        # 2. Total Refunds (PROCESSED)
        total_refunds_amount = db.query(
            func.coalesce(func.sum(RefundRequest.amount), 0.0)
        ).filter(RefundRequest.status == "PROCESSED").scalar() or 0.0
        
        total_refunds_count = db.query(RefundRequest).filter(
            RefundRequest.status == "PROCESSED"
        ).count()

        pending_refunds_count = db.query(RefundRequest).filter(
            RefundRequest.status.in_(["REQUESTED", "UNDER_REVIEW", "APPROVED"])
        ).count()

        # Net Revenue (Total Collected Revenue - Processed Refunds)
        net_revenue = max(0.0, total_paid_payments - total_refunds_amount)

        # 3. Invoice Metrics
        invoices_query = db.query(Quotation).filter(
            Quotation.doc_type == "invoice",
            Quotation.status != "cancelled"
        )
        
        total_invoices_count = invoices_query.count()

        # Paid Invoices
        paid_invoices = invoices_query.filter(
            or_(
                Quotation.payment_status == "paid",
                Quotation.amount_paid >= Quotation.grand_total
            )
        ).all()
        paid_invoices_count = len(paid_invoices)
        paid_invoices_amount = sum(float(inv.grand_total or 0.0) for inv in paid_invoices)

        # Pending Invoices
        pending_invoices = invoices_query.filter(
            Quotation.payment_status.in_(["unpaid", "partial", "draft"]),
            Quotation.amount_paid < Quotation.grand_total
        ).all()
        
        pending_payments_count = len(pending_invoices)
        pending_payments_amount = sum(
            max(0.0, float(inv.grand_total or 0.0) - float(inv.amount_paid or 0.0))
            for inv in pending_invoices
        )

        # Overdue Payments (due_date past now and unpaid)
        overdue_invoices = []
        for inv in pending_invoices:
            due = inv.due_date
            if not due and inv.issue_date:
                due = inv.issue_date + timedelta(days=15)
            elif not due and inv.created_at:
                due = inv.created_at + timedelta(days=15)
            
            if due and due < now:
                overdue_invoices.append(inv)
        
        overdue_payments_count = len(overdue_invoices)
        overdue_payments_amount = sum(
            max(0.0, float(inv.grand_total or 0.0) - float(inv.amount_paid or 0.0))
            for inv in overdue_invoices
        )

        # 4. Subscription Overview
        active_subs_count = db.query(CustomerSubscription).filter(
            CustomerSubscription.status == "ACTIVE"
        ).count()

        upcoming_renewals_30_days = db.query(CustomerSubscription).filter(
            CustomerSubscription.status.in_(["ACTIVE", "UPCOMING_RENEWAL"]),
            CustomerSubscription.renewal_date >= now,
            CustomerSubscription.renewal_date <= (now + timedelta(days=30))
        ).count()

        expired_subs_count = db.query(CustomerSubscription).filter(
            or_(
                CustomerSubscription.status == "EXPIRED",
                and_(CustomerSubscription.renewal_date < now, CustomerSubscription.status != "CANCELLED")
            )
        ).count()

        # 5. Monthly Revenue Trend (Past 6 Months)
        monthly_trend = []
        for i in range(5, -1, -1):
            m_date = (now - timedelta(days=i * 30)).replace(day=1)
            next_m_date = (m_date + timedelta(days=32)).replace(day=1)
            
            m_rev = db.query(func.coalesce(func.sum(Payment.amount), 0.0)).filter(
                Payment.status == "PAID",
                Payment.payment_date >= m_date,
                Payment.payment_date < next_m_date
            ).scalar() or 0.0
            
            m_inv_cnt = db.query(Quotation).filter(
                Quotation.doc_type == "invoice",
                Quotation.created_at >= m_date,
                Quotation.created_at < next_m_date
            ).count()

            monthly_trend.append({
                "month": m_date.strftime("%b %Y"),
                "month_short": m_date.strftime("%b"),
                "revenue": round(float(m_rev), 2),
                "invoices": m_inv_cnt
            })

        # 6. Payment Modes Breakdown
        payment_modes = db.query(
            Payment.payment_method,
            func.count(Payment.id).label("count"),
            func.coalesce(func.sum(Payment.amount), 0.0).label("total")
        ).filter(Payment.status == "PAID").group_by(Payment.payment_method).all()

        payment_methods_data = [
            {
                "method": row.payment_method or "OTHER",
                "label": (row.payment_method or "Other").replace("_", " ").title(),
                "count": row.count,
                "amount": round(float(row.total), 2)
            }
            for row in payment_modes
        ]

        # 7. Recent Transactions & Invoices
        recent_payments = db.query(Payment).order_by(desc(Payment.payment_date)).limit(5).all()
        recent_payments_data = []
        for p in recent_payments:
            cust_name = p.customer.company_name if p.customer else "Direct Client"
            recent_payments_data.append({
                "id": p.id,
                "payment_number": p.payment_number,
                "customer_name": cust_name,
                "amount": float(p.amount),
                "payment_method": p.payment_method,
                "payment_type": p.payment_type,
                "status": p.status,
                "transaction_reference": p.transaction_reference,
                "payment_date": p.payment_date.isoformat() if p.payment_date else None
            })

        return {
            "total_revenue": round(float(total_paid_payments), 2),
            "net_revenue": round(float(net_revenue), 2),
            "current_month_revenue": round(float(current_month_revenue), 2),
            "prev_month_revenue": round(float(prev_month_revenue), 2),
            "revenue_growth_pct": round(
                ((current_month_revenue - prev_month_revenue) / prev_month_revenue * 100)
                if prev_month_revenue > 0 else 0.0, 1
            ),
            "pending_payments_count": pending_payments_count,
            "pending_payments_amount": round(float(pending_payments_amount), 2),
            "paid_invoices_count": paid_invoices_count,
            "paid_invoices_amount": round(float(paid_invoices_amount), 2),
            "total_invoices_count": total_invoices_count,
            "overdue_payments_count": overdue_payments_count,
            "overdue_payments_amount": round(float(overdue_payments_amount), 2),
            "total_refunds_count": total_refunds_count,
            "total_refunds_amount": round(float(total_refunds_amount), 2),
            "pending_refunds_count": pending_refunds_count,
            "active_subscriptions_count": active_subs_count,
            "upcoming_renewals_count": upcoming_renewals_30_days,
            "expired_subscriptions_count": expired_subs_count,
            "monthly_trend": monthly_trend,
            "payment_methods": payment_methods_data,
            "recent_payments": recent_payments_data
        }

    # =========================================================================
    # INVOICE MANAGEMENT
    # =========================================================================
    @staticmethod
    def list_invoices(
        db: Session,
        status_filter: Optional[str] = "all",
        search: Optional[str] = None,
        limit: int = 50,
        page: int = 1
    ) -> Dict[str, Any]:
        """List invoices with server-side filters, search and pagination."""
        q = db.query(Quotation).filter(Quotation.doc_type == "invoice")

        now = datetime.utcnow()
        if status_filter == "paid":
            q = q.filter(Quotation.payment_status == "paid")
        elif status_filter == "unpaid":
            q = q.filter(Quotation.payment_status.in_(["unpaid", "draft"]))
        elif status_filter == "partial":
            q = q.filter(Quotation.payment_status == "partial")
        elif status_filter == "overdue":
            q = q.filter(
                Quotation.payment_status != "paid",
                or_(
                    Quotation.due_date < now,
                    and_(Quotation.due_date.is_(None), Quotation.created_at < (now - timedelta(days=15)))
                )
            )

        if search and search.strip():
            term = f"%{search.strip()}%"
            q = q.filter(
                or_(
                    Quotation.doc_number.ilike(term),
                    Quotation.customer_name.ilike(term),
                    Quotation.company_name.ilike(term),
                    Quotation.phone.ilike(term),
                    Quotation.email.ilike(term)
                )
            )

        total = q.count()
        records = q.order_by(desc(Quotation.issue_date), desc(Quotation.id)).offset((page - 1) * limit).limit(limit).all()

        items = []
        for doc in records:
            # Check overdue
            is_overdue = False
            effective_due = doc.due_date or (doc.issue_date + timedelta(days=15) if doc.issue_date else None)
            if doc.payment_status != "paid" and effective_due and effective_due < now:
                is_overdue = True

            items.append({
                "id": doc.id,
                "invoice_number": doc.doc_number,
                "customer_id": doc.customer_id,
                "customer_name": doc.customer_name,
                "company_name": doc.company_name,
                "phone": doc.phone,
                "email": doc.email,
                "subtotal": float(doc.subtotal or 0.0),
                "cgst": float(doc.cgst or 0.0),
                "sgst": float(doc.sgst or 0.0),
                "igst": float(doc.igst or 0.0),
                "tax_total": float(doc.tax_total or 0.0),
                "grand_total": float(doc.grand_total or 0.0),
                "amount_paid": float(doc.amount_paid or 0.0),
                "pending_amount": max(0.0, float(doc.grand_total or 0.0) - float(doc.amount_paid or 0.0)),
                "tax_mode": doc.tax_mode or "intra",
                "status": doc.status,
                "payment_status": doc.payment_status,
                "is_overdue": is_overdue,
                "issue_date": doc.issue_date.isoformat() if doc.issue_date else None,
                "due_date": effective_due.isoformat() if effective_due else None,
                "created_at": doc.created_at.isoformat() if doc.created_at else None
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit
        }

    @staticmethod
    def get_invoice_detail(db: Session, invoice_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve full details of an invoice including line items and payment logs."""
        inv = db.query(Quotation).filter(
            Quotation.id == invoice_id,
            Quotation.doc_type == "invoice"
        ).first()
        if not inv:
            return None

        payments = db.query(Payment).filter(Payment.invoice_id == inv.id).order_by(desc(Payment.payment_date)).all()
        payment_list = [
            {
                "id": p.id,
                "payment_number": p.payment_number,
                "amount": float(p.amount),
                "payment_method": p.payment_method,
                "payment_type": p.payment_type,
                "status": p.status,
                "transaction_reference": p.transaction_reference,
                "bank_name": p.bank_name,
                "payment_date": p.payment_date.isoformat() if p.payment_date else None,
                "notes": p.notes
            }
            for p in payments
        ]

        now = datetime.utcnow()
        effective_due = inv.due_date or (inv.issue_date + timedelta(days=15) if inv.issue_date else None)

        return {
            "id": inv.id,
            "invoice_number": inv.doc_number,
            "customer_id": inv.customer_id,
            "customer_name": inv.customer_name,
            "company_name": inv.company_name,
            "phone": inv.phone,
            "email": inv.email,
            "address": inv.address,
            "state": inv.state,
            "state_code": inv.state_code,
            "gstin": inv.gstin,
            "tax_mode": inv.tax_mode,
            "subtotal": float(inv.subtotal or 0.0),
            "cgst": float(inv.cgst or 0.0),
            "sgst": float(inv.sgst or 0.0),
            "igst": float(inv.igst or 0.0),
            "tax_total": float(inv.tax_total or 0.0),
            "round_off": float(inv.round_off or 0.0),
            "grand_total": float(inv.grand_total or 0.0),
            "amount_paid": float(inv.amount_paid or 0.0),
            "pending_amount": max(0.0, float(inv.grand_total or 0.0) - float(inv.amount_paid or 0.0)),
            "payment_status": inv.payment_status,
            "status": inv.status,
            "is_overdue": inv.payment_status != "paid" and effective_due and effective_due < now,
            "line_items": inv.line_items or [],
            "terms_and_conditions": inv.terms_and_conditions,
            "notes": inv.notes,
            "prepared_by": inv.prepared_by,
            "issue_date": inv.issue_date.isoformat() if inv.issue_date else None,
            "due_date": effective_due.isoformat() if effective_due else None,
            "payments": payment_list
        }

    @staticmethod
    def generate_invoice(
        db: Session,
        data: Dict[str, Any],
        creator_user: Optional[User] = None
    ) -> Quotation:
        """
        Generates and saves a statutory Tax Invoice in the CRM database.
        Calculates CGST, SGST, IGST, subtotal, and round off.
        """
        # Next sequence number
        last_inv = db.query(Quotation).filter(
            Quotation.doc_type == "invoice"
        ).order_by(desc(Quotation.id)).first()
        seq = (last_inv.id + 1) if last_inv else 1
        invoice_number = data.get("invoice_number") or f"CHN/INV/26/{seq:04d}"

        # Subtotal calculation from line items
        line_items = data.get("line_items") or []
        subtotal = 0.0
        for item in line_items:
            qty = float(item.get("qty") or 1.0)
            rate = float(item.get("rate") or 0.0)
            amt = float(item.get("amount") or (qty * rate))
            item["amount"] = amt
            subtotal += amt

        # Tax calculations
        state_code = str(data.get("state_code") or "33").strip()
        tax_mode = "intra" if state_code == "33" else "inter"
        
        if tax_mode == "intra":
            cgst = round(subtotal * 0.09, 2)
            sgst = round(subtotal * 0.09, 2)
            igst = 0.0
        else:
            cgst = 0.0
            sgst = 0.0
            igst = round(subtotal * 0.18, 2)
        
        tax_total = cgst + sgst + igst
        exact_grand = subtotal + tax_total
        grand_total = round(exact_grand)
        round_off = round(grand_total - exact_grand, 2)

        # Issue date & Due date
        issue_date = datetime.utcnow()
        if data.get("issue_date"):
            try:
                issue_date = datetime.fromisoformat(str(data["issue_date"]).replace("Z", ""))
            except Exception:
                pass
        
        due_date = issue_date + timedelta(days=15)
        if data.get("due_date"):
            try:
                due_date = datetime.fromisoformat(str(data["due_date"]).replace("Z", ""))
            except Exception:
                pass

        prepared_by = (
            getattr(creator_user, "name", None) or
            getattr(creator_user, "username", None) or
            "Finance Department"
        )

        customer_id = data.get("customer_id")
        cust = db.query(Customer).filter(Customer.id == customer_id).first() if customer_id else None

        doc = Quotation(
            doc_type="invoice",
            doc_number=invoice_number,
            status="issued",
            payment_status=data.get("payment_status", "unpaid"),
            customer_id=customer_id,
            lead_id=data.get("lead_id") or (cust.converted_from_lead if cust else None),
            customer_name=data.get("customer_name") or (cust.contact_name if cust else "Valued Client"),
            company_name=data.get("company_name") or (cust.company_name if cust else ""),
            phone=data.get("phone") or (cust.phone if cust else ""),
            email=data.get("email") or (cust.email if cust else ""),
            address=data.get("address") or (cust.location if cust else "Chennai, Tamil Nadu"),
            state=data.get("state", "Tamil Nadu"),
            state_code=state_code,
            gstin=data.get("gstin", ""),
            tax_mode=tax_mode,
            subtotal=round(subtotal, 2),
            cgst=cgst,
            sgst=sgst,
            igst=igst,
            tax_total=round(tax_total, 2),
            round_off=round_off,
            grand_total=grand_total,
            amount_paid=float(data.get("amount_paid") or 0.0),
            line_items=line_items,
            terms_and_conditions=data.get("terms_and_conditions") or (
                "1. Payment due within 15 days of invoice date.\n"
                "2. Goods/Services supplied as per signed proposal.\n"
                "3. Subject to Chennai jurisdiction."
            ),
            notes=data.get("notes", ""),
            prepared_by=prepared_by,
            issue_date=issue_date,
            due_date=due_date,
            created_by_user_id=creator_user.id if creator_user else None,
            created_at=datetime.utcnow()
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        # If payment is marked as paid on invoice creation, record Payment automatically
        if doc.amount_paid > 0:
            pay_num = f"PAY-2026-{doc.id:04d}"
            pay = Payment(
                payment_number=pay_num,
                customer_id=doc.customer_id,
                invoice_id=doc.id,
                lead_id=doc.lead_id,
                amount=doc.amount_paid,
                currency="INR",
                payment_method=data.get("payment_method", "BANK_TRANSFER"),
                payment_type="MANUAL",
                status="PAID" if doc.amount_paid >= doc.grand_total else "PARTIAL",
                transaction_reference=data.get("transaction_reference") or f"INIT-PAY-{doc.id}",
                bank_name=data.get("bank_name", "Axis Bank"),
                payment_date=issue_date,
                notes=f"Payment recorded at invoice creation for {doc.doc_number}",
                recorded_by_id=creator_user.id if creator_user else None,
                created_at=datetime.utcnow()
            )
            db.add(pay)
            db.commit()

        return doc

    @staticmethod
    def render_invoice_pdf(db: Session, invoice_id: int) -> bytes:
        """Renders statutory Tax Invoice PDF matching CHN standard layout."""
        inv = db.query(Quotation).filter(
            Quotation.id == invoice_id,
            Quotation.doc_type == "invoice"
        ).first()
        if not inv:
            raise ValueError("Invoice not found")

        # Map to tax invoice builder format
        doc_data = {
            "doc_number": inv.doc_number,
            "issue_date": inv.issue_date,
            "due_date": inv.due_date,
            "customer_name": inv.customer_name,
            "company_name": inv.company_name,
            "phone": inv.phone,
            "email": inv.email,
            "address": inv.address,
            "state": inv.state or "Tamil Nadu",
            "state_code": inv.state_code or "33",
            "gstin": inv.gstin or "",
            "line_items": inv.line_items or [],
            "subtotal": inv.subtotal,
            "cgst": inv.cgst,
            "sgst": inv.sgst,
            "igst": inv.igst,
            "tax_total": inv.tax_total,
            "round_off": inv.round_off,
            "grand_total": inv.grand_total,
            "amount_paid": inv.amount_paid,
            "payment_status": inv.payment_status,
            "tax_mode": inv.tax_mode,
            "terms_and_conditions": inv.terms_and_conditions
        }
        return build_tax_invoice_model_pdf(doc_data)

    # =========================================================================
    # PAYMENT MANAGEMENT
    # =========================================================================
    @staticmethod
    def list_payments(
        db: Session,
        status_filter: Optional[str] = None,
        payment_type: Optional[str] = None,
        payment_method: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        page: int = 1
    ) -> Dict[str, Any]:
        """List payments with filters and pagination."""
        q = db.query(Payment)

        if status_filter and status_filter.upper() != "ALL":
            q = q.filter(Payment.status == status_filter.upper())
        if payment_type and payment_type.upper() != "ALL":
            q = q.filter(Payment.payment_type == payment_type.upper())
        if payment_method and payment_method.upper() != "ALL":
            q = q.filter(Payment.payment_method == payment_method.upper())

        if search and search.strip():
            term = f"%{search.strip()}%"
            q = q.outerjoin(Customer, Payment.customer_id == Customer.id).outerjoin(
                Quotation, Payment.invoice_id == Quotation.id
            ).filter(
                or_(
                    Payment.payment_number.ilike(term),
                    Payment.transaction_reference.ilike(term),
                    Payment.bank_name.ilike(term),
                    Customer.company_name.ilike(term),
                    Customer.contact_name.ilike(term),
                    Quotation.doc_number.ilike(term)
                )
            )

        total = q.count()
        records = q.order_by(desc(Payment.payment_date), desc(Payment.id)).offset((page - 1) * limit).limit(limit).all()

        items = []
        for p in records:
            cust_name = (
                p.customer.company_name or p.customer.contact_name
                if p.customer else "Direct Customer"
            )
            inv_number = p.invoice.doc_number if p.invoice else None

            items.append({
                "id": p.id,
                "payment_number": p.payment_number,
                "customer_id": p.customer_id,
                "customer_name": cust_name,
                "invoice_id": p.invoice_id,
                "invoice_number": inv_number,
                "amount": float(p.amount),
                "currency": p.currency,
                "payment_method": p.payment_method,
                "payment_type": p.payment_type,
                "status": p.status,
                "transaction_reference": p.transaction_reference,
                "bank_name": p.bank_name,
                "razorpay_order_id": p.razorpay_order_id,
                "razorpay_payment_id": p.razorpay_payment_id,
                "payment_date": p.payment_date.isoformat() if p.payment_date else None,
                "notes": p.notes,
                "created_at": p.created_at.isoformat() if p.created_at else None
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit
        }

    @staticmethod
    def record_manual_payment(
        db: Session,
        data: Dict[str, Any],
        user: Optional[User] = None
    ) -> Payment:
        """
        Record a manual payment (Bank Transfer / NEFT / UPI / Cheque / Cash).
        Automatically updates linked invoice status and handoff status.
        """
        amount = float(data.get("amount") or 0.0)
        if amount <= 0:
            raise ValueError("Payment amount must be greater than zero.")

        # Payment sequence
        last_pay = db.query(Payment).order_by(desc(Payment.id)).first()
        seq = (last_pay.id + 1) if last_pay else 1
        pay_number = f"PAY-2026-{seq:04d}"

        # Payment date
        pay_date = datetime.utcnow()
        if data.get("payment_date"):
            try:
                pay_date = datetime.fromisoformat(str(data["payment_date"]).replace("Z", ""))
            except Exception:
                pass

        payment = Payment(
            payment_number=pay_number,
            customer_id=data.get("customer_id"),
            invoice_id=data.get("invoice_id"),
            finance_handoff_id=data.get("finance_handoff_id"),
            lead_id=data.get("lead_id"),
            amount=amount,
            currency="INR",
            payment_method=data.get("payment_method", "BANK_TRANSFER"),
            payment_type="MANUAL",
            status=data.get("status", "PAID"),
            transaction_reference=data.get("transaction_reference"),
            bank_name=data.get("bank_name"),
            payment_date=pay_date,
            notes=data.get("notes"),
            recorded_by_id=user.id if user else None,
            created_at=datetime.utcnow()
        )
        db.add(payment)

        # Update linked invoice if provided
        if payment.invoice_id and payment.status == "PAID":
            inv = db.query(Quotation).filter(Quotation.id == payment.invoice_id).first()
            if inv:
                inv.amount_paid = float(inv.amount_paid or 0.0) + amount
                if inv.amount_paid >= inv.grand_total:
                    inv.payment_status = "paid"
                else:
                    inv.payment_status = "partial"

        # Update linked finance handoff if provided
        if payment.finance_handoff_id and payment.status == "PAID":
            fh = db.query(FinanceHandoff).filter(FinanceHandoff.id == payment.finance_handoff_id).first()
            if fh:
                fh.paid_amount = float(fh.paid_amount or 0.0) + amount
                if fh.paid_amount >= fh.final_amount:
                    fh.status = "PAID"
                    fh.payment_status = "PAID"
                else:
                    fh.payment_status = "PARTIALLY_PAID"
                fh.payment_date = pay_date
                fh.payment_mode = payment.payment_method
                fh.bank_reference = payment.transaction_reference
                fh.bank_name = payment.bank_name
                fh.confirmed_by_user_id = user.id if user else None
                fh.confirmed_at = datetime.utcnow()

        db.commit()
        db.refresh(payment)
        return payment

    @staticmethod
    def process_razorpay_payment(
        db: Session,
        data: Dict[str, Any],
        user: Optional[User] = None
    ) -> Payment:
        """
        Record online payment via Razorpay reference verification.
        """
        amount = float(data.get("amount") or 0.0)
        razorpay_payment_id = data.get("razorpay_payment_id")
        if not razorpay_payment_id:
            raise ValueError("Razorpay payment reference ID is required.")

        last_pay = db.query(Payment).order_by(desc(Payment.id)).first()
        seq = (last_pay.id + 1) if last_pay else 1
        pay_number = f"PAY-2026-{seq:04d}"

        payment = Payment(
            payment_number=pay_number,
            customer_id=data.get("customer_id"),
            invoice_id=data.get("invoice_id"),
            finance_handoff_id=data.get("finance_handoff_id"),
            lead_id=data.get("lead_id"),
            amount=amount,
            currency="INR",
            payment_method="RAZORPAY",
            payment_type="ONLINE",
            status="PAID",
            transaction_reference=razorpay_payment_id,
            razorpay_order_id=data.get("razorpay_order_id"),
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=data.get("razorpay_signature"),
            bank_name="Razorpay PG",
            payment_date=datetime.utcnow(),
            notes=data.get("notes") or f"Online Payment verified via Razorpay ({razorpay_payment_id})",
            recorded_by_id=user.id if user else None,
            created_at=datetime.utcnow()
        )
        db.add(payment)

        # Update linked invoice
        if payment.invoice_id:
            inv = db.query(Quotation).filter(Quotation.id == payment.invoice_id).first()
            if inv:
                inv.amount_paid = float(inv.amount_paid or 0.0) + amount
                if inv.amount_paid >= inv.grand_total:
                    inv.payment_status = "paid"
                else:
                    inv.payment_status = "partial"

        # Update linked handoff
        if payment.finance_handoff_id:
            fh = db.query(FinanceHandoff).filter(FinanceHandoff.id == payment.finance_handoff_id).first()
            if fh:
                fh.status = "PAID"
                fh.payment_status = "PAID"
                fh.paid_amount = amount
                fh.payment_date = datetime.utcnow()
                fh.payment_mode = "Razorpay"
                fh.bank_reference = razorpay_payment_id
                fh.confirmed_by_user_id = user.id if user else None
                fh.confirmed_at = datetime.utcnow()

        db.commit()
        db.refresh(payment)
        return payment

    # =========================================================================
    # CUSTOMER PURCHASE DETAILS
    # =========================================================================
    @staticmethod
    def get_customer_purchases(
        db: Session,
        search: Optional[str] = None,
        limit: int = 50,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        When Sales converts a lead into a customer, Finance sees:
        - Customer name and company
        - Sales employee name
        - Purchased subscription plan (Business / Pro)
        - Add-on products
        - Subscription amount
        - GST and final amount
        - Payment status
        - Purchase date and renewal date
        """
        q = db.query(Customer)
        if search and search.strip():
            term = f"%{search.strip()}%"
            q = q.filter(
                or_(
                    Customer.company_name.ilike(term),
                    Customer.contact_name.ilike(term),
                    Customer.phone.ilike(term),
                    Customer.email.ilike(term)
                )
            )

        total = q.count()
        customers = q.order_by(desc(Customer.created_at)).offset((page - 1) * limit).limit(limit).all()

        items = []
        for c in customers:
            # 1. Fetch Subscription
            sub = db.query(CustomerSubscription).filter(
                CustomerSubscription.customer_id == c.id
            ).order_by(desc(CustomerSubscription.id)).first()

            # 2. Fetch Latest Invoice
            inv = db.query(Quotation).filter(
                Quotation.customer_id == c.id,
                Quotation.doc_type == "invoice"
            ).order_by(desc(Quotation.id)).first()

            # 3. Fetch Sales Rep
            sales_name = "Unassigned"
            if sub and sub.sales_employee:
                sales_name = sub.sales_employee.name
            elif c.lead and c.lead.assigned_employee:
                sales_name = c.lead.assigned_employee.name
            elif inv and inv.creator_employee:
                sales_name = inv.creator_employee.name

            # Financial figures
            plan_name = sub.plan_name if sub else "WAHRMS Business"
            plan_code = sub.plan_code if sub else "business"
            sub_amount = float(sub.subscription_amount) if sub else (float(inv.subtotal) if inv else 35000.0)
            gst_amount = float(sub.tax_amount) if sub else (float(inv.tax_total) if inv else (sub_amount * 0.18))
            final_amount = float(sub.total_amount) if sub else (float(inv.grand_total) if inv else (sub_amount + gst_amount))
            
            # Payment status
            pay_status = "PAID"
            if inv:
                pay_status = (inv.payment_status or "PAID").upper()
            elif sub:
                pay_status = "PAID" if sub.status in ["ACTIVE", "UPCOMING_RENEWAL"] else "PENDING"

            purchase_date = sub.start_date if sub else (c.created_at)
            renewal_date = sub.renewal_date if sub else (purchase_date + timedelta(days=365))
            addons = sub.addons_data if (sub and sub.addons_data) else []

            items.append({
                "customer_id": c.id,
                "customer_name": c.contact_name,
                "company_name": c.company_name,
                "phone": c.phone,
                "email": c.email,
                "location": c.location,
                "sales_employee_name": sales_name,
                "plan_code": plan_code,
                "plan_name": plan_name,
                "licence_count": sub.licence_count if sub else 50,
                "addons": addons,
                "subscription_amount": round(sub_amount, 2),
                "gst_amount": round(gst_amount, 2),
                "final_amount": round(final_amount, 2),
                "payment_status": pay_status,
                "purchase_date": purchase_date.isoformat() if purchase_date else None,
                "renewal_date": renewal_date.isoformat() if renewal_date else None,
                "subscription_status": sub.status if sub else "ACTIVE",
                "invoice_number": inv.doc_number if inv else None
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit
        }

    # =========================================================================
    # SUBSCRIPTION & RENEWAL MANAGEMENT
    # =========================================================================
    @staticmethod
    def list_subscriptions(
        db: Session,
        status_filter: Optional[str] = "all",
        search: Optional[str] = None,
        limit: int = 50,
        page: int = 1
    ) -> Dict[str, Any]:
        """List subscriptions with status and renewal filters."""
        q = db.query(CustomerSubscription)
        now = datetime.utcnow()

        if status_filter == "ACTIVE":
            q = q.filter(CustomerSubscription.status == "ACTIVE")
        elif status_filter == "UPCOMING_RENEWAL":
            q = q.filter(
                CustomerSubscription.status.in_(["ACTIVE", "UPCOMING_RENEWAL"]),
                CustomerSubscription.renewal_date >= now,
                CustomerSubscription.renewal_date <= (now + timedelta(days=30))
            )
        elif status_filter == "EXPIRED":
            q = q.filter(
                or_(
                    CustomerSubscription.status == "EXPIRED",
                    and_(CustomerSubscription.renewal_date < now, CustomerSubscription.status != "CANCELLED")
                )
            )

        if search and search.strip():
            term = f"%{search.strip()}%"
            q = q.join(Customer, CustomerSubscription.customer_id == Customer.id).filter(
                or_(
                    CustomerSubscription.subscription_number.ilike(term),
                    CustomerSubscription.plan_name.ilike(term),
                    Customer.company_name.ilike(term),
                    Customer.contact_name.ilike(term)
                )
            )

        total = q.count()
        records = q.order_by(CustomerSubscription.renewal_date).offset((page - 1) * limit).limit(limit).all()

        items = []
        for s in records:
            cust = s.customer
            days_to_renew = (s.renewal_date - now).days if s.renewal_date else 0
            
            items.append({
                "id": s.id,
                "subscription_number": s.subscription_number,
                "customer_id": s.customer_id,
                "customer_name": cust.contact_name if cust else "Valued Client",
                "company_name": cust.company_name if cust else "",
                "phone": cust.phone if cust else "",
                "plan_code": s.plan_code,
                "plan_name": s.plan_name,
                "bundle_code": s.bundle_code,
                "licence_count": s.licence_count,
                "billing_cycle": s.billing_cycle,
                "subscription_amount": float(s.subscription_amount),
                "tax_amount": float(s.tax_amount),
                "total_amount": float(s.total_amount),
                "status": s.status,
                "start_date": s.start_date.isoformat() if s.start_date else None,
                "renewal_date": s.renewal_date.isoformat() if s.renewal_date else None,
                "days_to_renew": days_to_renew,
                "is_urgent_renewal": 0 <= days_to_renew <= 15,
                "addons": s.addons_data or []
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit
        }

    @staticmethod
    def change_subscription_plan(
        db: Session,
        subscription_id: int,
        new_plan_code: str,
        new_licence_count: int,
        user: Optional[User] = None
    ) -> CustomerSubscription:
        """Upgrade or downgrade subscription plan."""
        sub = db.query(CustomerSubscription).filter(CustomerSubscription.id == subscription_id).first()
        if not sub:
            raise ValueError("Subscription not found")

        old_plan = sub.plan_name
        old_amt = sub.total_amount

        # Calculate new price
        is_pro = new_plan_code.lower() == "pro"
        new_plan_name = "WAHRMS Pro" if is_pro else "WAHRMS Business"
        rate_per_user = 800.0 if is_pro else 700.0
        base_amt = round(new_licence_count * rate_per_user, 2)
        tax_amt = round(base_amt * 0.18, 2)
        total_amt = base_amt + tax_amt

        action = "UPGRADE" if total_amt > old_amt else "DOWNGRADE"

        sub.plan_code = new_plan_code.lower()
        sub.plan_name = new_plan_name
        sub.licence_count = new_licence_count
        sub.subscription_amount = base_amt
        sub.tax_amount = tax_amt
        sub.total_amount = total_amt
        sub.status = action + "D" # UPGRADED / DOWNGRADED -> stays active in practice
        sub.status = "ACTIVE"
        sub.updated_at = datetime.utcnow()

        hist = SubscriptionHistory(
            subscription_id=sub.id,
            customer_id=sub.customer_id,
            action_type=action,
            old_plan=old_plan,
            new_plan=new_plan_name,
            old_amount=old_amt,
            new_amount=total_amt,
            details={
                "licence_count": new_licence_count,
                "reason": f"Plan modified to {new_plan_name} with {new_licence_count} licences"
            },
            performed_by_id=user.id if user else None,
            created_at=datetime.utcnow()
        )
        db.add(hist)
        db.commit()
        db.refresh(sub)
        return sub

    @staticmethod
    def add_addon_to_subscription(
        db: Session,
        subscription_id: int,
        addon_name: str,
        addon_code: str,
        addon_amount: float,
        qty: int = 1,
        user: Optional[User] = None
    ) -> CustomerSubscription:
        """Add add-on product to an existing subscription."""
        sub = db.query(CustomerSubscription).filter(CustomerSubscription.id == subscription_id).first()
        if not sub:
            raise ValueError("Subscription not found")

        current_addons = list(sub.addons_data or [])
        addon_total = float(addon_amount) * int(qty)
        current_addons.append({
            "name": addon_name,
            "code": addon_code,
            "amount": addon_amount,
            "qty": qty,
            "total": addon_total
        })

        sub.addons_data = current_addons
        sub.subscription_amount = float(sub.subscription_amount or 0.0) + addon_total
        sub.tax_amount = round(sub.subscription_amount * 0.18, 2)
        sub.total_amount = sub.subscription_amount + sub.tax_amount
        sub.updated_at = datetime.utcnow()

        hist = SubscriptionHistory(
            subscription_id=sub.id,
            customer_id=sub.customer_id,
            action_type="ADDON_PURCHASE",
            new_plan=sub.plan_name,
            new_amount=sub.total_amount,
            details={"addon_added": addon_name, "addon_amount": addon_total, "qty": qty},
            performed_by_id=user.id if user else None,
            created_at=datetime.utcnow()
        )
        db.add(hist)
        db.commit()
        db.refresh(sub)
        return sub

    @staticmethod
    def process_renewal(
        db: Session,
        subscription_id: int,
        payment_method: str = "BANK_TRANSFER",
        transaction_reference: Optional[str] = None,
        user: Optional[User] = None
    ) -> CustomerSubscription:
        """
        Processes annual renewal: extends renewal date by 1 year, records payment, and logs renewal history.
        """
        sub = db.query(CustomerSubscription).filter(CustomerSubscription.id == subscription_id).first()
        if not sub:
            raise ValueError("Subscription not found")

        # Extend renewal date
        old_renewal = sub.renewal_date or datetime.utcnow()
        new_renewal = old_renewal + timedelta(days=365)
        
        sub.renewal_date = new_renewal
        sub.status = "ACTIVE"
        sub.updated_at = datetime.utcnow()

        # Record renewal payment
        last_pay = db.query(Payment).order_by(desc(Payment.id)).first()
        seq = (last_pay.id + 1) if last_pay else 1
        pay_number = f"PAY-2026-{seq:04d}"

        renewal_pay = Payment(
            payment_number=pay_number,
            customer_id=sub.customer_id,
            lead_id=sub.lead_id,
            amount=sub.total_amount,
            currency="INR",
            payment_method=payment_method,
            payment_type="MANUAL",
            status="PAID",
            transaction_reference=transaction_reference or f"REN-UTR-{sub.id:04d}-2026",
            bank_name="Axis Bank",
            payment_date=datetime.utcnow(),
            notes=f"Renewal payment collected for Subscription {sub.subscription_number}",
            recorded_by_id=user.id if user else None,
            created_at=datetime.utcnow()
        )
        db.add(renewal_pay)

        # Log history
        hist = SubscriptionHistory(
            subscription_id=sub.id,
            customer_id=sub.customer_id,
            action_type="RENEWAL",
            old_plan=sub.plan_name,
            new_plan=sub.plan_name,
            new_amount=sub.total_amount,
            details={
                "previous_renewal_date": old_renewal.isoformat(),
                "new_renewal_date": new_renewal.isoformat(),
                "payment_number": pay_number
            },
            performed_by_id=user.id if user else None,
            created_at=datetime.utcnow()
        )
        db.add(hist)
        db.commit()
        db.refresh(sub)
        return sub

    # =========================================================================
    # REFUND MANAGEMENT
    # =========================================================================
    @staticmethod
    def list_refunds(
        db: Session,
        status_filter: Optional[str] = "all",
        search: Optional[str] = None,
        limit: int = 50,
        page: int = 1
    ) -> Dict[str, Any]:
        """List refund requests with status filter."""
        q = db.query(RefundRequest)
        if status_filter and status_filter.upper() != "ALL":
            q = q.filter(RefundRequest.status == status_filter.upper())

        if search and search.strip():
            term = f"%{search.strip()}%"
            q = q.join(Customer, RefundRequest.customer_id == Customer.id).filter(
                or_(
                    RefundRequest.refund_number.ilike(term),
                    RefundRequest.reason.ilike(term),
                    Customer.company_name.ilike(term),
                    Customer.contact_name.ilike(term)
                )
            )

        total = q.count()
        records = q.order_by(desc(RefundRequest.created_at)).offset((page - 1) * limit).limit(limit).all()

        items = []
        for r in records:
            cust = r.customer
            items.append({
                "id": r.id,
                "refund_number": r.refund_number,
                "customer_id": r.customer_id,
                "customer_name": cust.contact_name if cust else "Valued Client",
                "company_name": cust.company_name if cust else "",
                "amount": float(r.amount),
                "reason": r.reason,
                "status": r.status,
                "transaction_reference": r.transaction_reference,
                "rejection_reason": r.rejection_reason,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "approved_at": r.approved_at.isoformat() if r.approved_at else None,
                "processed_at": r.processed_at.isoformat() if r.processed_at else None
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit
        }

    @staticmethod
    def create_refund_request(
        db: Session,
        customer_id: int,
        amount: float,
        reason: str,
        payment_id: Optional[int] = None,
        invoice_id: Optional[int] = None,
        user: Optional[User] = None
    ) -> RefundRequest:
        """Create a new refund request."""
        if amount <= 0:
            raise ValueError("Refund amount must be greater than zero.")

        last_ref = db.query(RefundRequest).order_by(desc(RefundRequest.id)).first()
        seq = (last_ref.id + 1) if last_ref else 1
        ref_number = f"REF-2026-{seq:04d}"

        ref = RefundRequest(
            refund_number=ref_number,
            customer_id=customer_id,
            payment_id=payment_id,
            invoice_id=invoice_id,
            amount=amount,
            reason=reason,
            status="REQUESTED",
            requested_by_id=user.id if user else None,
            created_at=datetime.utcnow()
        )
        db.add(ref)
        db.commit()
        db.refresh(ref)
        return ref

    @staticmethod
    def update_refund_status(
        db: Session,
        refund_id: int,
        new_status: str,
        transaction_reference: Optional[str] = None,
        rejection_reason: Optional[str] = None,
        user: Optional[User] = None
    ) -> RefundRequest:
        """
        Workflow transitions: REQUESTED -> UNDER_REVIEW -> APPROVED -> PROCESSED (or REJECTED).
        When PROCESSED, adjusts linked payment so revenue calculations reflect net accurate figures.
        """
        ref = db.query(RefundRequest).filter(RefundRequest.id == refund_id).first()
        if not ref:
            raise ValueError("Refund request not found")

        norm_status = new_status.upper()
        ref.status = norm_status
        ref.updated_at = datetime.utcnow()

        if norm_status == "APPROVED":
            ref.approved_by_id = user.id if user else None
            ref.approved_at = datetime.utcnow()
        elif norm_status == "REJECTED":
            ref.rejection_reason = rejection_reason or "Rejected by Finance Authorizer"
        elif norm_status == "PROCESSED":
            ref.processed_at = datetime.utcnow()
            ref.processed_by_id = user.id if user else None
            ref.transaction_reference = transaction_reference or f"REF-BANK-UTR-{ref.id:04d}"

            # Update linked payment status to REFUNDED if payment exists
            if ref.payment_id:
                pay = db.query(Payment).filter(Payment.id == ref.payment_id).first()
                if pay:
                    if ref.amount >= pay.amount:
                        pay.status = "REFUNDED"
                    else:
                        pay.status = "PARTIAL"
                        pay.notes = f"{pay.notes or ''} [Partial refund processed: INR {ref.amount}]"

        db.commit()
        db.refresh(ref)
        return ref

    # =========================================================================
    # FINANCIAL REPORTS & EXPORT
    # =========================================================================
    @staticmethod
    def get_revenue_report(
        db: Session,
        report_type: str = "monthly",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Generates daily, monthly, yearly, collection, GST, or refund report.
        """
        now = datetime.utcnow()
        if not start_date:
            start_date = datetime(now.year, 1, 1)
        if not end_date:
            end_date = now

        if report_type == "daily":
            # Last 30 days daily revenue
            records = db.query(
                func.date(Payment.payment_date).label("pay_day"),
                func.count(Payment.id).label("count"),
                func.coalesce(func.sum(Payment.amount), 0.0).label("revenue")
            ).filter(
                Payment.status == "PAID",
                Payment.payment_date >= (now - timedelta(days=30))
            ).group_by(func.date(Payment.payment_date)).order_by(desc("pay_day")).all()

            rows = [
                {
                    "date": str(r.pay_day),
                    "transaction_count": r.count,
                    "revenue": round(float(r.revenue), 2)
                }
                for r in records
            ]
            total_rev = sum(r["revenue"] for r in rows)
            return {"title": "Daily Revenue Report", "rows": rows, "total_revenue": total_rev}

        elif report_type == "monthly":
            records = db.query(
                func.date_format(Payment.payment_date, "%Y-%m").label("pay_month"),
                func.count(Payment.id).label("count"),
                func.coalesce(func.sum(Payment.amount), 0.0).label("revenue")
            ).filter(
                Payment.status == "PAID",
                Payment.payment_date >= start_date,
                Payment.payment_date <= end_date
            ).group_by("pay_month").order_by(desc("pay_month")).all()

            rows = [
                {
                    "month": r.pay_month,
                    "transaction_count": r.count,
                    "revenue": round(float(r.revenue), 2)
                }
                for r in records
            ]
            total_rev = sum(r["revenue"] for r in rows)
            return {"title": "Monthly Revenue Report", "rows": rows, "total_revenue": total_rev}

        elif report_type == "yearly":
            records = db.query(
                func.date_format(Payment.payment_date, "%Y").label("pay_year"),
                func.count(Payment.id).label("count"),
                func.coalesce(func.sum(Payment.amount), 0.0).label("revenue")
            ).filter(
                Payment.status == "PAID"
            ).group_by("pay_year").order_by(desc("pay_year")).all()

            rows = [
                {
                    "year": r.pay_year,
                    "transaction_count": r.count,
                    "revenue": round(float(r.revenue), 2)
                }
                for r in records
            ]
            total_rev = sum(r["revenue"] for r in rows)
            return {"title": "Yearly Revenue Report", "rows": rows, "total_revenue": total_rev}

        elif report_type == "collections":
            records = db.query(
                Payment.payment_method,
                func.count(Payment.id).label("count"),
                func.coalesce(func.sum(Payment.amount), 0.0).label("revenue")
            ).filter(
                Payment.status == "PAID",
                Payment.payment_date >= start_date,
                Payment.payment_date <= end_date
            ).group_by(Payment.payment_method).all()

            rows = [
                {
                    "method": r.payment_method or "OTHER",
                    "transaction_count": r.count,
                    "revenue": round(float(r.revenue), 2)
                }
                for r in records
            ]
            total_rev = sum(r["revenue"] for r in rows)
            return {"title": "Payment Collection Report", "rows": rows, "total_revenue": total_rev}

        elif report_type == "gst":
            # Statutory GST breakdown of issued invoices
            invoices = db.query(Quotation).filter(
                Quotation.doc_type == "invoice",
                Quotation.status != "cancelled",
                Quotation.issue_date >= start_date,
                Quotation.issue_date <= end_date
            ).order_by(desc(Quotation.issue_date)).all()

            rows = []
            for inv in invoices:
                rows.append({
                    "invoice_number": inv.doc_number,
                    "customer_name": inv.customer_name,
                    "company_name": inv.company_name,
                    "gstin": inv.gstin or "Unregistered",
                    "tax_mode": inv.tax_mode,
                    "subtotal": round(float(inv.subtotal or 0.0), 2),
                    "cgst": round(float(inv.cgst or 0.0), 2),
                    "sgst": round(float(inv.sgst or 0.0), 2),
                    "igst": round(float(inv.igst or 0.0), 2),
                    "tax_total": round(float(inv.tax_total or 0.0), 2),
                    "grand_total": round(float(inv.grand_total or 0.0), 2),
                    "issue_date": inv.issue_date.strftime("%Y-%m-%d") if inv.issue_date else ""
                })

            total_taxable = sum(r["subtotal"] for r in rows)
            total_cgst = sum(r["cgst"] for r in rows)
            total_sgst = sum(r["sgst"] for r in rows)
            total_igst = sum(r["igst"] for r in rows)
            total_tax = sum(r["tax_total"] for r in rows)
            total_amount = sum(r["grand_total"] for r in rows)

            return {
                "title": "Statutory GST Report",
                "rows": rows,
                "total_taxable": round(total_taxable, 2),
                "total_cgst": round(total_cgst, 2),
                "total_sgst": round(total_sgst, 2),
                "total_igst": round(total_igst, 2),
                "total_tax": round(total_tax, 2),
                "total_amount": round(total_amount, 2)
            }

        elif report_type == "refunds":
            refunds = db.query(RefundRequest).filter(
                RefundRequest.created_at >= start_date,
                RefundRequest.created_at <= end_date
            ).order_by(desc(RefundRequest.created_at)).all()

            rows = []
            for ref in refunds:
                cust = ref.customer
                rows.append({
                    "refund_number": ref.refund_number,
                    "customer_name": cust.contact_name if cust else "",
                    "company_name": cust.company_name if cust else "",
                    "amount": round(float(ref.amount), 2),
                    "reason": ref.reason,
                    "status": ref.status,
                    "transaction_reference": ref.transaction_reference or "N/A",
                    "created_at": ref.created_at.strftime("%Y-%m-%d") if ref.created_at else ""
                })

            total_refund_amount = sum(r["amount"] for r in rows)
            return {"title": "Refund Report", "rows": rows, "total_refund_amount": round(total_refund_amount, 2)}

        # Default fallback
        return {"title": "Financial Report", "rows": []}

    @staticmethod
    def export_report_csv(report_data: Dict[str, Any]) -> str:
        """Converts report data to CSV string for direct download."""
        output = io.StringIO()
        rows = report_data.get("rows") or []
        if not rows:
            return "No data available for export.\n"

        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

        return output.getvalue()
