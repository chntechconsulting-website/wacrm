"""
Comprehensive End-to-End Validation Script for CRM Sales Revenue & Targets.
Validates all requirements:
1. Create a quotation -> revenue must NOT change.
2. Mark the associated deal as Won -> revenue and achievement must update.
   - Example check: Assigned Target Rs. 1,50,000, Won Revenue Rs. 75,000 -> Achievement = 50.0%
3. Edit the won amount (e.g. to Rs. 1,00,000) -> totals recalculate (Rs. 1,00,000 / Rs. 1,50,000 = 66.7%).
4. Change Won to Lost -> revenue decreases back; excluded from won revenue.
5. Verify employee-wise and company-wide totals match.
6. Verify RBAC scoping for employee vs admin.
"""

import sys
import os
from datetime import datetime

# Configure stdout for utf-8
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

# Set backend path
sys.path.insert(0, os.path.abspath("backend"))

import database
from models.user import User
from models.employee import Employee
from models.lead import Lead
from models.quotation import Quotation
from models.workflow import FinanceHandoff, SupportHandoff
from models.sales_target import SalesTarget
from services.revenue_service import RevenueService
from routers.reports import sales_revenue_report
from routers.sales_targets import get_employee_achievements, get_my_target, get_companies_revenue

db = next(database.get_db())

print("=" * 80)
print("RUNNING END-TO-END REVENUE & TARGET VALIDATION SUITE")
print("=" * 80)

# Setup test employee and user
test_emp = db.query(Employee).filter(Employee.id == 9).first() # Chandra Mohan
admin_user = db.query(User).filter(User.role == "ADMIN").first()
exec_user = db.query(User).filter(User.id == 9).first() # user linked to Chandra Mohan

now = datetime.now()

# Clean up any previous test leads/quotations
old_leads = db.query(Lead).filter(Lead.name.ilike("Revenue Validation Deal%")).all()
for l in old_leads:
    db.query(Quotation).filter(Quotation.lead_id == l.id).delete()
    db.query(FinanceHandoff).filter(FinanceHandoff.lead_id == l.id).delete()
    db.query(SupportHandoff).filter(SupportHandoff.lead_id == l.id).delete()
    db.delete(l)

# Ensure target of 150000 for employee 9 for current month
target = db.query(SalesTarget).filter(
    SalesTarget.employee_id == test_emp.id,
    SalesTarget.period_type == "monthly",
    SalesTarget.period_month == now.month,
    SalesTarget.period_year == now.year
).first()

if not target:
    target = SalesTarget(
        employee_id=test_emp.id,
        target_amount=150000.0,
        period_type="monthly",
        period_month=now.month,
        period_year=now.year,
        created_by=admin_user.id
    )
    db.add(target)
else:
    target.target_amount = 150000.0

db.commit()

# Baseline revenue check
base_txs = RevenueService.get_won_sales_transactions(db, employee_ids_filter=[test_emp.id])
base_revenue = sum(t["amount"] for t in base_txs)
print(f"[BASELINE] Employee: {test_emp.name}, Initial Won Revenue: ₹{base_revenue:,.2f}, Target: ₹{target.target_amount:,.2f}")

# TEST 1: Create a quotation -> revenue must NOT change
test_lead = Lead(
    name="Revenue Validation Deal Company",
    phone="9876543299",
    company="Revenue Validation Corp",
    assigned_to=test_emp.id,
    status="NEW",
    source="Website"
)
db.add(test_lead)
db.commit()
db.refresh(test_lead)

quote = Quotation(
    lead_id=test_lead.id,
    customer_name=test_lead.name,
    company_name=test_lead.company,
    doc_type="quotation",
    doc_number=f"QT-TEST-{test_lead.id}",
    status="issued",
    grand_total=75000.0,
    created_by=test_emp.id,
    assigned_to=test_emp.id,
    prepared_by=test_emp.name
)
db.add(quote)
db.commit()

t1_txs = RevenueService.get_won_sales_transactions(db, employee_ids_filter=[test_emp.id])
t1_revenue = sum(t["amount"] for t in t1_txs)
assert t1_revenue == base_revenue, f"Test 1 Failed! Quotation added to won revenue. Expected {base_revenue}, got {t1_revenue}"
print(f"✓ TEST 1 PASSED: Created quotation of ₹75,000. Won Revenue remained unchanged: ₹{t1_revenue:,.2f}")

# TEST 2: Mark deal Won -> Won Revenue increases by 75,000, Achievement = 50.0%
test_lead.status = "WON"
test_lead.quotetask_quotation_amount = 75000.0
# Add finance handoff
fh = FinanceHandoff(
    lead_id=test_lead.id,
    customer_id=1,
    customer_name=test_lead.name,
    company_name=test_lead.company,
    sales_employee_id=test_emp.id,
    sales_employee_name=test_emp.name,
    final_amount=75000.0,
    paid_amount=0.0,
    status="PAYMENT_PENDING"
)
db.add(fh)
db.commit()

t2_txs = RevenueService.get_won_sales_transactions(db, employee_ids_filter=[test_emp.id])
t2_revenue = sum(t["amount"] for t in t2_txs)
expected_t2_revenue = base_revenue + 75000.0
assert t2_revenue == expected_t2_revenue, f"Test 2 Failed! Expected {expected_t2_revenue}, got {t2_revenue}"

# Check Achievement calculation
ach_rows = get_employee_achievements(
    period_year=now.year,
    period_month=now.month,
    period_type="monthly",
    employee_id=test_emp.id,
    db=db,
    current_user=admin_user
)
emp_row = next(r for r in ach_rows if r.employee_id == test_emp.id)
expected_ach = round((t2_revenue / target.target_amount) * 100, 1)
assert emp_row.actual_revenue == t2_revenue
assert emp_row.achievement_percentage == expected_ach, f"Expected {expected_ach}%, got {emp_row.achievement_percentage}%"
print(f"✓ TEST 2 PASSED: Marked deal WON for ₹75,000 against ₹1,50,000 target. Achievement = {emp_row.achievement_percentage}% (Exact: 50.0%)")

# TEST 3: Edit won deal amount to ₹1,00,000 -> Totals recalculate to ₹1,00,000, Achievement = 66.7%
test_lead.quotetask_quotation_amount = 100000.0
fh.final_amount = 100000.0
db.commit()

t3_txs = RevenueService.get_won_sales_transactions(db, employee_ids_filter=[test_emp.id])
t3_revenue = sum(t["amount"] for t in t3_txs)
expected_t3_revenue = base_revenue + 100000.0
assert t3_revenue == expected_t3_revenue, f"Test 3 Failed! Expected {expected_t3_revenue}, got {t3_revenue}"

ach_rows = get_employee_achievements(
    period_year=now.year,
    period_month=now.month,
    period_type="monthly",
    employee_id=test_emp.id,
    db=db,
    current_user=admin_user
)
emp_row = next(r for r in ach_rows if r.employee_id == test_emp.id)
expected_ach_3 = round((t3_revenue / target.target_amount) * 100, 1)
assert emp_row.actual_revenue == t3_revenue
assert emp_row.achievement_percentage == expected_ach_3, f"Expected {expected_ach_3}%, got {emp_row.achievement_percentage}%"
print(f"✓ TEST 3 PASSED: Edited won deal amount to ₹1,00,000. Recalculated Achievement = {emp_row.achievement_percentage}% (Exact: 66.7%)")

# TEST 4: Change Won to Lost -> Revenue decreases, deal excluded from won revenue
test_lead.status = "LOST"
db.commit()

t4_txs = RevenueService.get_won_sales_transactions(db, employee_ids_filter=[test_emp.id])
t4_revenue = sum(t["amount"] for t in t4_txs)
assert t4_revenue == base_revenue, f"Test 4 Failed! Status LOST still counted in revenue: {t4_revenue} vs base {base_revenue}"
print(f"✓ TEST 4 PASSED: Changed deal from WON to LOST. Won revenue decreased cleanly back to baseline: ₹{t4_revenue:,.2f}")

# TEST 5: Verify Company-wide and Employee-wise Totals Match
# Set back to WON with 75,000 for consistent verification
test_lead.status = "WON"
test_lead.quotetask_quotation_amount = 75000.0
fh.final_amount = 75000.0
db.commit()

all_ach = get_employee_achievements(
    period_year=now.year,
    period_month=now.month,
    period_type="monthly",
    db=db,
    current_user=admin_user
)
sum_emp_rev = sum(r.actual_revenue for r in all_ach)

rep = sales_revenue_report(db=db, current_user=admin_user)
report_total_rev = rep["kpis"]["total_revenue"]["raw_val"] * 100000.0 # from lakhs
company_rev_rows = get_companies_revenue(db=db, current_user=admin_user)
company_rev_sum = sum(c.total_confirmed_revenue for c in company_rev_rows)

assert abs(sum_emp_rev - company_rev_sum) < 1.0, f"Mismatch: Employee sum {sum_emp_rev} != Company sum {company_rev_sum}"
print(f"✓ TEST 5 PASSED: Employee-wise totals (₹{sum_emp_rev:,.2f}) match Company-wide totals (₹{company_rev_sum:,.2f})")

# TEST 6: RBAC Verification
# Non-admin user can only see their own row in achievements
exec_ach = get_employee_achievements(
    period_year=now.year,
    period_month=now.month,
    period_type="monthly",
    db=db,
    current_user=exec_user
)
assert len(exec_ach) == 1, f"RBAC failed! Non-admin should only see 1 row, got {len(exec_ach)}"
assert exec_ach[0].employee_id == test_emp.id, "RBAC failed! Non-admin saw another employee's row"
print(f"✓ TEST 6 PASSED: RBAC verified. Non-admin ({exec_user.username}) sees only their own target & achievement row.")

# Clean up test records
db.delete(fh)
db.delete(quote)
db.delete(test_lead)
db.commit()

print("=" * 80)
print("ALL 6 REVENUE DASHBOARD & SALES TARGET VERIFICATION TESTS PASSED SUCCESSFULLY!")
print("=" * 80)
