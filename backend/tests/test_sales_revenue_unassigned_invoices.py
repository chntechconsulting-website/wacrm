"""
Regression tests for paid invoices that have no salesperson attribution.

Finance can record a confirmed invoice/payment without an assigned Sales
employee (for example, a bank-transfer invoice prepared by the Finance login).
Those documents are real won revenue and must appear in company-wide Sales
Revenue totals exactly once. They must still be excluded from an individual
salesperson's own-scope report and must never be attributed to someone else.

These tests use an in-memory SQLite database and synthetic rows only.
"""

import os
import sys
import unittest
from datetime import datetime

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401 - registers every model on Base.metadata
from database import Base
from models.customer import Customer
from models.employee import Employee
from models.finance import Payment
from models.quotation import Quotation
from models.user import User
from routers.reports import sales_revenue_report
from services.permission_service import seed_default_roles_if_needed
from services.revenue_service import RevenueService


class SalesRevenueUnassignedInvoiceTests(unittest.TestCase):
    START_DATE = "2026-10-01"
    END_DATE = "2026-11-30"

    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(
            bind=self.engine, autoflush=False, autocommit=False
        )
        self.db = self.Session()
        seed_default_roles_if_needed(self.db)

        self.admin_user, self.admin_emp = self._make_person(
            "revenue_admin", "ADMIN", "ADMINISTRATION", name="Revenue Admin"
        )
        self.sales_user, self.sales_emp = self._make_person(
            "revenue_sales", "SALES_EXECUTIVE", "SALES", name="Revenue Sales"
        )

        self.customer = Customer(
            company_name="Unassigned Revenue Client",
            contact_name="Unassigned Contact",
            phone="9300000001",
        )
        self.db.add(self.customer)
        self.db.commit()
        self.db.refresh(self.customer)

        # Invoice 1: attributed to the Sales executive.
        self.assigned_invoice = Quotation(
            doc_type="invoice",
            doc_number="TEST/INV/26/0001",
            status="issued",
            payment_status="paid",
            customer_id=self.customer.id,
            assigned_to=self.sales_emp.id,
            created_by=self.sales_emp.id,
            customer_name="Assigned Client",
            company_name="Assigned Client",
            grand_total=25000.0,
            amount_paid=25000.0,
            issue_date=datetime(2026, 10, 7, 9, 10, 48),
            created_at=datetime(2026, 10, 20, 8, 56, 9),
        )
        # Invoice 2: confirmed by Finance with no employee attribution. This is
        # the document that used to disappear from company-wide revenue.
        self.unassigned_invoice = Quotation(
            doc_type="invoice",
            doc_number="TEST/INV/26/0002",
            status="issued",
            payment_status="paid",
            customer_id=self.customer.id,
            assigned_to=None,
            created_by=None,
            created_by_user_id=None,
            prepared_by="finance_login",
            customer_name="Finance Recorded Client",
            company_name="Finance Recorded Client",
            grand_total=41300.0,
            amount_paid=41300.0,
            issue_date=datetime(2026, 11, 6, 8, 25, 48),
            created_at=datetime(2026, 11, 6, 8, 25, 48),
        )
        # Invoice 3: zero-value paid invoice must not inflate payment counts.
        self.zero_invoice = Quotation(
            doc_type="invoice",
            doc_number="TEST/INV/26/0003",
            status="issued",
            payment_status="paid",
            customer_id=self.customer.id,
            assigned_to=self.sales_emp.id,
            created_by=self.sales_emp.id,
            customer_name="Zero Value Client",
            company_name="Zero Value Client",
            grand_total=0.0,
            amount_paid=0.0,
            issue_date=datetime(2026, 10, 7, 7, 17, 53),
            created_at=datetime(2026, 10, 20, 8, 55, 15),
        )
        self.db.add_all([
            self.assigned_invoice,
            self.unassigned_invoice,
            self.zero_invoice,
        ])
        self.db.commit()
        for inv in (
            self.assigned_invoice,
            self.unassigned_invoice,
            self.zero_invoice,
        ):
            self.db.refresh(inv)

        self.db.add_all([
            Payment(
                payment_number="PAY-TEST-0001",
                customer_id=self.customer.id,
                invoice_id=self.assigned_invoice.id,
                amount=25000.0,
                status="PAID",
                payment_method="BANK_TRANSFER",
                payment_type="MANUAL",
                transaction_reference="AXIS-UTR-0001",
                payment_date=datetime(2026, 10, 7, 9, 10, 48),
            ),
            Payment(
                payment_number="PAY-TEST-0002",
                customer_id=self.customer.id,
                invoice_id=self.unassigned_invoice.id,
                amount=41300.0,
                status="PAID",
                payment_method="BANK_TRANSFER",
                payment_type="MANUAL",
                transaction_reference="UTRTEST0002",
                payment_date=datetime(2026, 11, 6, 8, 25, 48),
            ),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _make_person(self, username, role, department, name=None):
        user = User(
            username=username,
            hashed_password="not-used-in-tests",
            role=role,
            department=department,
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        employee = Employee(
            user_id=user.id,
            department=department,
            name=name or username.replace("_", " ").title(),
            email=f"{username}@example.test",
            phone=f"97{user.id:08d}"[:10],
            username=username,
            role=role,
            status="ACTIVE",
        )
        self.db.add(employee)
        self.db.commit()
        self.db.refresh(employee)
        return user, employee

    def _report(self, user, start_date=None, end_date=None):
        return sales_revenue_report(
            start_date=start_date,
            end_date=end_date,
            team=None,
            salesperson_id=None,
            db=self.db,
            current_user=user,
        )

    def test_company_report_includes_unassigned_paid_invoice_once(self):
        report = self._report(self.admin_user, self.START_DATE, self.END_DATE)
        revenue_kpi = report["kpis"]["total_revenue"]

        # Two successful payments: 25,000 + 41,300. The zero-value invoice is
        # not a payment and must not be counted or listed.
        paid_payments = (
            self.db.query(Payment).filter(Payment.status == "PAID").all()
        )
        self.assertEqual(len(paid_payments), 2)
        self.assertEqual(
            sum(float(payment.amount) for payment in paid_payments), 66300.0
        )
        self.assertEqual(revenue_kpi["payments_count"], len(paid_payments))
        self.assertEqual(revenue_kpi["transactions_count"], 2)
        self.assertEqual(revenue_kpi["raw_val"], 0.66)
        self.assertEqual(revenue_kpi["collected_raw"], 0.66)
        self.assertEqual(revenue_kpi["value"], "₹66,300")
        self.assertEqual(revenue_kpi["collected_revenue"], "₹66,300")
        self.assertIn("2 payments", revenue_kpi["vs_label"])

        won_rows = [
            row for row in report["deals_details"] if row["origin"] != "PIPELINE"
        ]
        self.assertEqual(
            {row["invoice_id"] for row in won_rows},
            {self.assigned_invoice.id, self.unassigned_invoice.id},
        )
        self.assertEqual(
            sum(float(row["raw_amount"]) for row in won_rows), 66300.0
        )

        # Unassigned revenue must not be silently attributed to a salesperson.
        salesperson_names = {
            row["name"] for row in report["revenue_by_salesperson"]
        }
        self.assertEqual(salesperson_names, {self.sales_emp.name})

    def test_own_scope_still_excludes_unassigned_invoice(self):
        report = self._report(self.sales_user, self.START_DATE, self.END_DATE)
        revenue_kpi = report["kpis"]["total_revenue"]

        self.assertEqual(revenue_kpi["payments_count"], 1)
        self.assertEqual(revenue_kpi["transactions_count"], 1)
        self.assertEqual(revenue_kpi["raw_val"], 0.25)
        won_rows = [
            row for row in report["deals_details"] if row["origin"] != "PIPELINE"
        ]
        self.assertEqual(
            {row["invoice_id"] for row in won_rows},
            {self.assigned_invoice.id},
        )

    def test_report_date_range_uses_invoice_issue_date(self):
        november_only = self._report(self.admin_user, "2026-11-01", "2026-11-30")
        revenue_kpi = november_only["kpis"]["total_revenue"]

        self.assertEqual(revenue_kpi["payments_count"], 1)
        self.assertEqual(revenue_kpi["transactions_count"], 1)
        self.assertEqual(revenue_kpi["raw_val"], 0.41)

    def test_service_filter_behavior_for_unassigned_revenue(self):
        roster_only = RevenueService.get_won_sales_transactions(
            db=self.db,
            start_date=datetime(2026, 10, 1),
            end_date=datetime(2026, 12, 1),
            employee_ids_filter=[self.sales_emp.id],
        )
        self.assertEqual(
            {tx["invoice_id"] for tx in roster_only},
            {self.assigned_invoice.id, self.zero_invoice.id},
        )

        with_unassigned = RevenueService.get_won_sales_transactions(
            db=self.db,
            start_date=datetime(2026, 10, 1),
            end_date=datetime(2026, 12, 1),
            employee_ids_filter=[self.sales_emp.id],
            include_unassigned=True,
        )
        self.assertEqual(
            {tx["invoice_id"] for tx in with_unassigned},
            {
                self.assigned_invoice.id,
                self.unassigned_invoice.id,
                self.zero_invoice.id,
            },
        )
        self.assertEqual(
            sum(tx["amount"] for tx in with_unassigned), 66300.0
        )


if __name__ == "__main__":
    unittest.main()
