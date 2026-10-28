"""
Unified Revenue Service for Wa CRM.
Enforces strict revenue recognition and deduplication business logic:
1. Total Revenue: Only actual sales marked as 'Won' or 'Closed Won'.
   - Final confirmed sales/deal amount linked to the company.
   - Quotation amounts (doc_type='quotation'), draft quotations, pending deals, or lost deals are EXCLUDED.
   - Count each won sale only once.
   - When a won deal amount is edited, recalculates accurately.
   - If a won deal is changed to Lost or reopened, removes its amount from won revenue.
2. Deduplication Priority:
   - Primary: Confirmed Invoices (doc_type='invoice', status in ['issued', 'paid'], payment_status in ['paid', 'partial'], status != 'cancelled').
   - Secondary: Deals/Leads marked WON (Lead.status in ['WON', 'CONVERTED', 'CLOSED WON', 'Closed Won'] or FinanceHandoff).
   - If a deal has both a confirmed invoice and a WON lead/handoff, the invoice amount takes precedence and is counted ONLY ONCE.
3. Target & Achievement:
   - Achievement (%) = (Won Sales Revenue / Assigned Target) * 100
   - Remaining Target = MAX(0, Assigned Target - Won Sales Revenue)
"""

from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, desc

from models.lead import Lead
from models.quotation import Quotation
from models.workflow import FinanceHandoff, SupportHandoff
from models.employee import Employee
from models.customer import Customer
from models.sales_target import SalesTarget


WON_LEAD_STATUSES = {"WON", "CONVERTED", "CLOSED WON", "CLOSED_WON"}


def is_lead_won(status_str: Optional[str]) -> bool:
    if not status_str:
        return False
    return status_str.strip().upper() in WON_LEAD_STATUSES


class RevenueService:

    @staticmethod
    def get_won_sales_transactions(
        db: Session,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        period_year: Optional[int] = None,
        period_month: Optional[int] = None,
        period_type: str = "monthly",
        salesperson_id: Optional[int] = None,
        employee_ids_filter: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """
        Gathers all confirmed won sales transactions across Invoices, Finance Handoffs, and Won Leads.
        Strictly prevents double counting:
        - If an invoice is linked to a lead_id, the lead is not counted separately.
        - If a finance handoff is linked to a lead_id, it is deduplicated against any invoice or lead record.
        - Quotations (doc_type='quotation') and unclosed proformas are strictly excluded.
        """
        # 1. Fetch all confirmed invoices
        inv_query = db.query(Quotation).filter(
            Quotation.doc_type == "invoice",
            Quotation.status.in_(["issued", "paid"]),
            Quotation.payment_status.in_(["paid", "partial"]),
            Quotation.status != "cancelled"
        )
        invoices = inv_query.all()

        # 2. Fetch all leads that are WON or CONVERTED
        won_leads = db.query(Lead).filter(
            func.upper(Lead.status).in_(list(WON_LEAD_STATUSES))
        ).all()

        # 3. Fetch finance handoffs
        handoffs = db.query(FinanceHandoff).filter(
            FinanceHandoff.status != "CANCELLED",
            FinanceHandoff.status != "REJECTED"
        ).all()

        # Map active employees
        all_emps = {e.id: e for e in db.query(Employee).all()}
        all_custs = {c.id: c for c in db.query(Customer).all()}
        handoff_by_lead = {h.lead_id: h for h in handoffs if h.lead_id}

        transactions: List[Dict[str, Any]] = []
        seen_lead_ids: Set[int] = set()

        # Step A: Process Confirmed Invoices
        for inv in invoices:
            dt = inv.issue_date or inv.created_at or datetime.min
            if not RevenueService._matches_date_filter(dt, start_date, end_date, period_year, period_month, period_type):
                continue

            lead_id = inv.lead_id
            customer_id = inv.customer_id
            lead_obj = db.query(Lead).filter(Lead.id == lead_id).first() if lead_id else None

            # Attribute salesperson
            emp_id = None
            if inv.assigned_to and inv.assigned_to in all_emps:
                emp_id = inv.assigned_to
            elif inv.created_by and inv.created_by in all_emps:
                emp_id = inv.created_by
            elif lead_obj and lead_obj.assigned_to in all_emps:
                emp_id = lead_obj.assigned_to
            elif inv.prepared_by:
                for eid, e in all_emps.items():
                    if e.name and (e.name.lower() in inv.prepared_by.lower() or inv.prepared_by.lower() in e.name.lower()):
                        emp_id = eid
                        break

            # Check filters
            if salesperson_id and salesperson_id > 0 and emp_id != salesperson_id:
                continue
            if employee_ids_filter is not None and emp_id not in employee_ids_filter:
                continue

            # Amount
            amt = float(inv.grand_total or 0.0)
            collected = float(inv.amount_paid or 0.0)
            comp_name = inv.company_name or inv.customer_name or (all_custs.get(customer_id).company_name if customer_id in all_custs else None) or (lead_obj.company if lead_obj else None) or "Valued Customer"

            # Lead source
            source = (lead_obj.source if lead_obj else None) or "Direct"

            transactions.append({
                "deal_key": f"lead_{lead_id}" if lead_id else f"invoice_{inv.id}",
                "invoice_id": inv.id,
                "lead_id": lead_id,
                "customer_id": customer_id,
                "customer_name": inv.customer_name or (lead_obj.name if lead_obj else "Customer"),
                "company_name": comp_name,
                "deal_name": f"{inv.doc_number or 'Invoice'} (Confirmed Tax Invoice)",
                "amount": amt,
                "collected_amount": collected,
                "salesperson_id": emp_id,
                "salesperson_name": all_emps[emp_id].name if emp_id and emp_id in all_emps else (inv.prepared_by or "Sales Executive"),
                "source": source,
                "date": dt,
                "status": "Won",
                "doc_type": "invoice",
                "origin": "INVOICE"
            })

            if lead_id:
                seen_lead_ids.add(lead_id)

        # Step B: Process Won Leads / Finance Handoffs not already counted via confirmed invoice
        for lead in won_leads:
            if lead.id in seen_lead_ids:
                continue

            handoff = handoff_by_lead.get(lead.id)
            # Determine won date
            dt = (handoff.created_at if handoff else None) or lead.updated_at or lead.created_at or datetime.min
            if not RevenueService._matches_date_filter(dt, start_date, end_date, period_year, period_month, period_type):
                continue

            # Salesperson
            emp_id = lead.assigned_to
            if not emp_id and handoff and handoff.sales_employee_id:
                emp_id = handoff.sales_employee_id

            if salesperson_id and salesperson_id > 0 and emp_id != salesperson_id:
                continue
            if employee_ids_filter is not None and emp_id not in employee_ids_filter:
                continue

            # Amount determination: confirmed handoff final_amount or lead.quotetask_quotation_amount
            amt = 0.0
            if handoff and handoff.final_amount and float(handoff.final_amount) > 0:
                amt = float(handoff.final_amount)
            elif lead.quotetask_quotation_amount and float(lead.quotetask_quotation_amount) > 0:
                amt = float(lead.quotetask_quotation_amount)

            # If amount is still 0, check linked support handoff
            if amt <= 0:
                sup = db.query(SupportHandoff).filter(SupportHandoff.lead_id == lead.id).first()
                if sup and sup.total_deal_amount:
                    amt = float(sup.total_deal_amount)

            collected = float(handoff.paid_amount or 0.0) if handoff else (amt if is_lead_won(lead.status) and getattr(lead, 'quotetask_quotation_status', None) == 'PAID' else 0.0)
            comp_name = (handoff.company_name if handoff else None) or lead.company or lead.name or "Valued Customer"
            customer_name = (handoff.customer_name if handoff else None) or lead.name
            sp_name = all_emps[emp_id].name if emp_id and emp_id in all_emps else (handoff.sales_employee_name if handoff else "Sales Executive")

            transactions.append({
                "deal_key": f"lead_{lead.id}",
                "invoice_id": None,
                "lead_id": lead.id,
                "customer_id": handoff.customer_id if handoff else None,
                "customer_name": customer_name,
                "company_name": comp_name,
                "deal_name": f"Deal #{lead.id} - {comp_name} (Won Deal)",
                "amount": amt,
                "collected_amount": collected,
                "salesperson_id": emp_id,
                "salesperson_name": sp_name,
                "source": lead.source or "Direct",
                "date": dt,
                "status": "Won",
                "doc_type": "deal",
                "origin": "LEAD_WON"
            })
            seen_lead_ids.add(lead.id)

        return transactions

    @staticmethod
    def _matches_date_filter(
        dt: datetime,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        period_year: Optional[int],
        period_month: Optional[int],
        period_type: str
    ) -> bool:
        if not dt or dt == datetime.min:
            return True

        if start_date and dt < start_date:
            return False
        if end_date and dt >= end_date:
            return False

        if period_year:
            if dt.year != period_year:
                return False
            if period_type == "monthly" and period_month is not None:
                if dt.month != period_month:
                    return False
            elif period_type == "quarterly" and period_month is not None:
                q = (dt.month - 1) // 3 + 1
                if q != period_month:
                    return False

        return True
