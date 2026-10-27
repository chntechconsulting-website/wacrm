from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, desc
from typing import List, Optional, Dict, Any
from datetime import datetime

from database import get_db
from models.user import User
from models.employee import Employee
from models.customer import Customer
from models.quotation import Quotation
from models.sales_target import SalesTarget
from schemas.sales_target import (
    SalesTargetCreate,
    SalesTargetUpdate,
    SalesTargetOut,
    EmployeeAchievementRow,
    EmployeeMyTargetSummary,
    CompanyRevenueSummary,
    CompanyRevenueItem
)
from services.auth import get_current_user

router = APIRouter(prefix="/sales-targets", tags=["Sales Targets & Revenue"])

def check_admin_access(current_user: User):
    role = (current_user.role or "").upper()
    if role not in ["ADMIN", "SUPERADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators are authorized to manage sales targets."
        )

@router.post("", response_model=SalesTargetOut, status_code=status.HTTP_201_CREATED)
def create_or_update_target(
    payload: SalesTargetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Admin: Assign or update sales target for an employee.
    Enforces uniqueness constraint per (employee_id, period_type, period_month, period_year).
    """
    check_admin_access(current_user)

    emp = db.query(Employee).filter(Employee.id == payload.employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    p_type = payload.period_type.lower()
    if p_type not in ["monthly", "quarterly", "yearly"]:
        raise HTTPException(status_code=400, detail="Invalid period_type. Must be monthly, quarterly, or yearly.")

    p_month = payload.period_month if p_type in ["monthly", "quarterly"] else None

    # Check for existing target
    existing = db.query(SalesTarget).filter(
        SalesTarget.employee_id == payload.employee_id,
        SalesTarget.period_type == p_type,
        SalesTarget.period_month == p_month,
        SalesTarget.period_year == payload.period_year
    ).first()

    if existing:
        existing.target_amount = float(payload.target_amount)
        existing.created_by = current_user.id
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        target = existing
    else:
        target = SalesTarget(
            employee_id=payload.employee_id,
            target_amount=float(payload.target_amount),
            period_type=p_type,
            period_month=p_month,
            period_year=payload.period_year,
            created_by=current_user.id
        )
        db.add(target)
        db.commit()
        db.refresh(target)

    out = SalesTargetOut.from_orm(target)
    out.employee_name = emp.name
    out.employee_department = emp.department
    return out

@router.get("", response_model=List[SalesTargetOut])
def get_targets(
    period_year: Optional[int] = None,
    period_month: Optional[int] = None,
    period_type: Optional[str] = None,
    employee_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetch assigned sales targets with optional period and employee filtering.
    """
    query = db.query(SalesTarget)
    if period_year:
        query = query.filter(SalesTarget.period_year == period_year)
    if period_month is not None:
        query = query.filter(SalesTarget.period_month == period_month)
    if period_type:
        query = query.filter(SalesTarget.period_type == period_type.lower())
    if employee_id:
        query = query.filter(SalesTarget.employee_id == employee_id)

    results = query.order_by(desc(SalesTarget.period_year), desc(SalesTarget.period_month)).all()
    
    emp_ids = [t.employee_id for t in results]
    emps = {e.id: e for e in db.query(Employee).filter(Employee.id.in_(emp_ids)).all()} if emp_ids else {}

    output = []
    for t in results:
        dto = SalesTargetOut.from_orm(t)
        if t.employee_id in emps:
            dto.employee_name = emps[t.employee_id].name
            dto.employee_department = emps[t.employee_id].department
        output.append(dto)
    return output

@router.put("/{target_id}", response_model=SalesTargetOut)
def update_target(
    target_id: int,
    payload: SalesTargetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Admin: Update target amount for an existing target record.
    """
    check_admin_access(current_user)
    target = db.query(SalesTarget).filter(SalesTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    target.target_amount = float(payload.target_amount)
    target.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(target)

    emp = db.query(Employee).filter(Employee.id == target.employee_id).first()
    dto = SalesTargetOut.from_orm(target)
    if emp:
        dto.employee_name = emp.name
        dto.employee_department = emp.department
    return dto

@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_target(
    target_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Admin: Delete a target record.
    """
    check_admin_access(current_user)
    target = db.query(SalesTarget).filter(SalesTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    db.delete(target)
    db.commit()
    return None

@router.get("/achievement", response_model=List[EmployeeAchievementRow])
def get_employee_achievements(
    period_year: Optional[int] = None,
    period_month: Optional[int] = None,
    period_type: str = "monthly",
    department: Optional[str] = None,
    employee_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Calculate:
    - Assigned Target
    - Actual Revenue: Confirmed eligible invoice revenue attributed to that salesperson
    - Remaining Target: MAX(Assigned Target - Actual Revenue, 0)
    - Achievement %: (Actual Revenue / Assigned Target) * 100
    """
    now = datetime.now()
    year = period_year or now.year
    month = period_month if period_month is not None else now.month
    p_type = period_type.lower()

    # Active employees
    emp_query = db.query(Employee).filter(Employee.status == "ACTIVE")
    if department and department.strip() and department.lower() != "all":
        emp_query = emp_query.filter(Employee.department.ilike(f"%{department.strip()}%"))
    if employee_id:
        emp_query = emp_query.filter(Employee.id == employee_id)

    active_emps = emp_query.all()
    emp_ids = [e.id for e in active_emps]

    # Query targets
    target_q = db.query(SalesTarget).filter(
        SalesTarget.employee_id.in_(emp_ids),
        SalesTarget.period_type == p_type,
        SalesTarget.period_year == year
    )
    if p_type in ["monthly", "quarterly"] and month is not None:
        target_q = target_q.filter(SalesTarget.period_month == month)

    targets_map = {t.employee_id: t.target_amount for t in target_q.all()}

    # Query confirmed invoices for period
    invoice_q = db.query(Quotation).filter(
        Quotation.doc_type == "invoice",
        Quotation.status.in_(["issued", "paid"]),
        Quotation.payment_status.in_(["paid", "partial"]),
        Quotation.status != "cancelled"
    )

    # Date filter on confirmed billing date (issue_date or created_at)
    date_col = func.coalesce(Quotation.issue_date, Quotation.created_at)
    if p_type == "monthly" and month is not None:
        invoice_q = invoice_q.filter(
            func.extract('year', date_col) == year,
            func.extract('month', date_col) == month
        )
    elif p_type == "quarterly" and month is not None:
        # month is treated as quarter start or 1-4
        if month in [1, 2, 3, 4]:
            q_months = [(month - 1) * 3 + 1, (month - 1) * 3 + 2, (month - 1) * 3 + 3]
        else:
            q_months = [month]
        invoice_q = invoice_q.filter(
            func.extract('year', date_col) == year,
            func.extract('month', date_col).in_(q_months)
        )
    elif p_type == "yearly":
        invoice_q = invoice_q.filter(func.extract('year', date_col) == year)

    invoices = invoice_q.all()

    # Attribute each invoice to an employee
    emp_revenue = {e.id: {"revenue": 0.0, "count": 0} for e in active_emps}

    for inv in invoices:
        matched_emp_id = None
        if inv.assigned_to and inv.assigned_to in emp_revenue:
            matched_emp_id = inv.assigned_to
        elif inv.created_by and inv.created_by in emp_revenue:
            matched_emp_id = inv.created_by
        elif inv.prepared_by:
            for e in active_emps:
                if e.name and (e.name.lower() in inv.prepared_by.lower() or inv.prepared_by.lower() in e.name.lower()):
                    matched_emp_id = e.id
                    break

        # Fallback to first salesperson if unassigned or admin
        if not matched_emp_id and active_emps:
            matched_emp_id = active_emps[0].id

        if matched_emp_id and matched_emp_id in emp_revenue:
            amt = float(inv.grand_total or inv.amount_paid or 0.0)
            emp_revenue[matched_emp_id]["revenue"] += amt
            emp_revenue[matched_emp_id]["count"] += 1

    rows = []
    for emp in active_emps:
        tgt = float(targets_map.get(emp.id, 0.0))
        rev = float(emp_revenue[emp.id]["revenue"])
        rem = max(0.0, tgt - rev)
        ach_pct = round((rev / tgt * 100), 1) if tgt > 0 else 0.0

        rows.append(EmployeeAchievementRow(
            employee_id=emp.id,
            employee_name=emp.name,
            department=emp.department,
            assigned_target=tgt,
            actual_revenue=rev,
            remaining_target=rem,
            achievement_percentage=ach_pct,
            confirmed_invoices_count=emp_revenue[emp.id]["count"]
        ))

    # Sort by actual revenue desc, achievement_percentage desc
    rows.sort(key=lambda r: (r.actual_revenue, r.achievement_percentage), reverse=True)
    return rows

@router.get("/my-target", response_model=EmployeeMyTargetSummary)
def get_my_target(
    period_year: Optional[int] = None,
    period_month: Optional[int] = None,
    period_type: str = "monthly",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Authenticated endpoint for the logged-in employee to retrieve their own assigned sales target,
    actual confirmed revenue, remaining target, and achievement percentage.
    Resolves the authenticated employee from user.id.
    """
    emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
    if not emp:
        # Check by email or username if user_id was not linked
        emp = db.query(Employee).filter(
            or_(
                Employee.email == current_user.email,
                Employee.username == current_user.username
            )
        ).first()

    now = datetime.now()
    year = period_year or now.year
    month = period_month if period_month is not None else now.month
    p_type = period_type.lower()

    if not emp:
        # If user has no employee record (e.g. root admin without employee profile)
        return EmployeeMyTargetSummary(
            has_target=False,
            employee_id=0,
            employee_name=current_user.full_name or current_user.username,
            period_type=p_type,
            period_month=month,
            period_year=year,
            assigned_target=0.0,
            actual_revenue=0.0,
            remaining_target=0.0,
            achievement_percentage=0.0,
            confirmed_invoices_count=0
        )

    # Find target in database
    target_q = db.query(SalesTarget).filter(
        SalesTarget.employee_id == emp.id,
        SalesTarget.period_type == p_type,
        SalesTarget.period_year == year
    )
    if p_type in ["monthly", "quarterly"] and month is not None:
        target_q = target_q.filter(SalesTarget.period_month == month)

    target_obj = target_q.first()
    target_amt = float(target_obj.target_amount) if target_obj else 0.0

    # Calculate actual revenue strictly from confirmed eligible invoices
    invoice_q = db.query(Quotation).filter(
        Quotation.doc_type == "invoice",
        Quotation.status.in_(["issued", "paid"]),
        Quotation.payment_status.in_(["paid", "partial"]),
        Quotation.status != "cancelled",
        or_(
            Quotation.assigned_to == emp.id,
            Quotation.created_by == emp.id,
            Quotation.prepared_by.ilike(f"%{emp.name}%"),
            Quotation.lead_id.in_(db.query(Quotation.lead_id).filter(Quotation.assigned_to == emp.id))
        )
    )

    date_col = func.coalesce(Quotation.issue_date, Quotation.created_at)
    if p_type == "monthly" and month is not None:
        invoice_q = invoice_q.filter(
            func.extract('year', date_col) == year,
            func.extract('month', date_col) == month
        )
    elif p_type == "quarterly" and month is not None:
        if month in [1, 2, 3, 4]:
            q_months = [(month - 1) * 3 + 1, (month - 1) * 3 + 2, (month - 1) * 3 + 3]
        else:
            q_months = [month]
        invoice_q = invoice_q.filter(
            func.extract('year', date_col) == year,
            func.extract('month', date_col).in_(q_months)
        )
    elif p_type == "yearly":
        invoice_q = invoice_q.filter(func.extract('year', date_col) == year)

    my_invoices = invoice_q.all()
    actual_rev = sum(float(inv.grand_total or 0.0) for inv in my_invoices)
    remaining = max(0.0, target_amt - actual_rev)
    ach_pct = round((actual_rev / target_amt * 100), 1) if target_amt > 0 else 0.0

    return EmployeeMyTargetSummary(
        has_target=bool(target_obj and target_amt > 0),
        employee_id=emp.id,
        employee_name=emp.name,
        period_type=p_type,
        period_month=month if p_type != "yearly" else None,
        period_year=year,
        assigned_target=target_amt,
        actual_revenue=actual_rev,
        remaining_target=remaining,
        achievement_percentage=ach_pct,
        confirmed_invoices_count=len(my_invoices)
    )

@router.get("/companies-revenue", response_model=List[CompanyRevenueSummary])
def get_companies_revenue(
    search: Optional[str] = None,
    customer_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Company-wise confirmed revenue and associated invoices.
    Allows authorized users to inspect each company's confirmed invoices and billing records.
    """
    # Confirmed invoices
    invoices = db.query(Quotation).filter(
        Quotation.doc_type == "invoice",
        Quotation.status.in_(["issued", "paid"]),
        Quotation.payment_status.in_(["paid", "partial"]),
        Quotation.status != "cancelled"
    ).order_by(desc(Quotation.created_at)).all()

    # Group by customer / company
    active_emps = {e.id: e.name for e in db.query(Employee).all()}
    customers_map = {c.id: c for c in db.query(Customer).all()}

    summary_map: Dict[str, Dict[str, Any]] = {}

    for inv in invoices:
        c_id = inv.customer_id or 0
        comp_name = (inv.company_name or inv.customer_name or (customers_map[c_id].company_name if c_id in customers_map else "Unknown Company")).strip()
        key = f"{c_id}_{comp_name.lower()}"

        cust = customers_map.get(c_id)

        if key not in summary_map:
            summary_map[key] = {
                "customer_id": c_id,
                "company_name": comp_name,
                "contact_name": (cust.contact_name if cust else inv.customer_name) or "",
                "phone": (cust.phone if cust else inv.phone) or "",
                "email": (cust.email if cust else inv.email) or "",
                "total_confirmed_revenue": 0.0,
                "total_collected_revenue": 0.0,
                "invoices": []
            }

        billed_amt = float(inv.grand_total or 0.0)
        collected_amt = float(inv.amount_paid or 0.0)
        summary_map[key]["total_confirmed_revenue"] += billed_amt
        summary_map[key]["total_collected_revenue"] += collected_amt

        sp_name = inv.prepared_by or (active_emps.get(inv.assigned_to) or active_emps.get(inv.created_by) or "Sales Executive")

        summary_map[key]["invoices"].append(CompanyRevenueItem(
            invoice_id=inv.id,
            invoice_number=inv.doc_number or f"INV-{inv.id}",
            invoice_date=(inv.issue_date or inv.created_at).strftime("%b %d, %Y") if (inv.issue_date or inv.created_at) else "-",
            status=inv.status,
            payment_status=inv.payment_status,
            subtotal=float(inv.subtotal or 0.0),
            tax_total=float(inv.tax_total or 0.0),
            grand_total=billed_amt,
            amount_paid=collected_amt,
            salesperson_name=sp_name,
            doc_type=inv.doc_type
        ))

    results = []
    for item in summary_map.values():
        if customer_id and item["customer_id"] != customer_id:
            continue
        if search and search.strip():
            s = search.strip().lower()
            if s not in item["company_name"].lower() and s not in (item["contact_name"] or "").lower():
                continue

        results.append(CompanyRevenueSummary(
            customer_id=item["customer_id"],
            company_name=item["company_name"],
            contact_name=item["contact_name"],
            phone=item["phone"],
            email=item["email"],
            total_confirmed_revenue=item["total_confirmed_revenue"],
            total_collected_revenue=item["total_collected_revenue"],
            invoices_count=len(item["invoices"]),
            invoices=item["invoices"]
        ))

    results.sort(key=lambda x: x.total_confirmed_revenue, reverse=True)
    return results
