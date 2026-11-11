"""
Regression tests for the shared Sales KPI calculation.

Every Sales surface (dashboard, Sales Overview, Sales Revenue and employee
monitoring) must derive converted/won counts, payment counts and revenue from
the same deduplicated transaction set:

  * Only confirmed paid/partially-paid invoices and genuinely won leads count.
  * A won lead that already has a confirmed invoice is counted once, through
    the invoice.
  * Zero-value documents never inflate conversion, payment or transaction
    counters.
  * Company/team scopes include confirmed invoices recorded without a Sales
    attribution; an individual's own scope never borrows that revenue.

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
from models.lead import Lead
from models.quotation import Quotation
from models.user import User
from routers.employee_monitoring import get_monitoring_overview
from routers.reports import (
    dashboard_stats,
    sales_overview_report,
    sales_revenue_report,
)
from routers.sales_targets import get_companies_revenue
from services.permission_service import seed_default_roles_if_needed
from services.revenue_service import RevenueService


class SalesKpiConsistencyTests(unittest.TestCase):
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
            "kpi_admin", "ADMIN", "ADMINISTRATION", name="KPI Admin"
        )
        self.manager_user, self.manager_emp = self._make_person(
            "kpi_manager",
            "SALES_MANAGER",
            "SALES",
            name="KPI Sales Manager",
            manager_user=self.admin_user,
            manager_emp=self.admin_emp,
        )
        self.sales_a_user, self.sales_a_emp = self._make_person(
            "kpi_sales_a",
            "SALES_EXECUTIVE",
            "SALES",
            name="KPI Sales A",
            manager_user=self.manager_user,
            manager_emp=self.manager_emp,
        )
        self.sales_b_user, self.sales_b_emp = self._make_person(
            "kpi_sales_b",
            "SALES_EXECUTIVE",
            "SALES",
            name="KPI Sales B",
            manager_user=self.manager_user,
            manager_emp=self.manager_emp,
        )

        self.customer = Customer(
            company_name="KPI Consistency Client",
            contact_name="KPI Contact",
            phone="9400000001",
        )
        self.db.add(self.customer)
        self.db.commit()
        self.db.refresh(self.customer)

        # Invoice 1: assigned to Sales A, fully paid.
        self.assigned_invoice = Quotation(
            doc_type="invoice",
            doc_number="KPI/INV/26/0001",
            status="issued",
            payment_status="paid",
            customer_id=self.customer.id,
            assigned_to=self.sales_a_emp.id,
            created_by=self.sales_a_emp.id,
            customer_name="KPI Assigned Client",
            company_name="KPI Assigned Client",
            grand_total=25000.0,
            amount_paid=25000.0,
            issue_date=datetime(2026, 10, 7, 9, 10, 48),
            created_at=datetime(2026, 10, 7, 9, 10, 48),
        )
        # Invoice 2: recorded by Finance without any salesperson attribution.
        self.unassigned_invoice = Quotation(
            doc_type="invoice",
            doc_number="KPI/INV/26/0002",
            status="issued",
            payment_status="paid",
            customer_id=self.customer.id,
            assigned_to=None,
            created_by=None,
            created_by_user_id=None,
            prepared_by="finance_login",
            customer_name="KPI Finance Client",
            company_name="KPI Finance Client",
            grand_total=41300.0,
            amount_paid=41300.0,
            issue_date=datetime(2026, 11, 6, 8, 25, 48),
            created_at=datetime(2026, 11, 6, 8, 25, 48),
        )
        # Invoice 3: zero-value paid invoice, not a sale or a payment.
        self.zero_invoice = Quotation(
            doc_type="invoice",
            doc_number="KPI/INV/26/0003",
            status="issued",
            payment_status="paid",
            customer_id=self.customer.id,
            assigned_to=self.sales_a_emp.id,
            created_by=self.sales_a_emp.id,
            customer_name="KPI Zero Client",
            company_name="KPI Zero Client",
            grand_total=0.0,
            amount_paid=0.0,
            issue_date=datetime(2026, 10, 8, 7, 17, 53),
            created_at=datetime(2026, 10, 8, 7, 17, 53),
        )
        self.db.add_all([
            self.assigned_invoice,
            self.unassigned_invoice,
            self.zero_invoice,
        ])
        self.db.commit()
        for invoice in (
            self.assigned_invoice,
            self.unassigned_invoice,
            self.zero_invoice,
        ):
            self.db.refresh(invoice)

        self.db.add_all([
            Payment(
                payment_number="PAY-KPI-0001",
                customer_id=self.customer.id,
                invoice_id=self.assigned_invoice.id,
                amount=25000.0,
                status="PAID",
                payment_method="BANK_TRANSFER",
                payment_type="MANUAL",
                transaction_reference="KPI-UTR-0001",
                payment_date=datetime(2026, 10, 7, 9, 10, 48),
            ),
            Payment(
                payment_number="PAY-KPI-0002",
                customer_id=self.customer.id,
                invoice_id=self.unassigned_invoice.id,
                amount=41300.0,
                status="PAID",
                payment_method="BANK_TRANSFER",
                payment_type="MANUAL",
                transaction_reference="KPI-UTR-0002",
                payment_date=datetime(2026, 11, 6, 8, 25, 48),
            ),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _make_person(
        self,
        username,
        role,
        department,
        name=None,
        manager_user=None,
        manager_emp=None,
    ):
        user = User(
            username=username,
            hashed_password="not-used-in-tests",
            role=role,
            department=department,
            reporting_manager_id=manager_user.id if manager_user else None,
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        employee = Employee(
            user_id=user.id,
            manager_id=manager_emp.id if manager_emp else None,
            reporting_manager_id=manager_user.id if manager_user else None,
            department=department,
            name=name or username.replace("_", " ").title(),
            email=f"{username}@example.test",
            phone=f"94{user.id:08d}"[:10],
            username=username,
            role=role,
            status="ACTIVE",
        )
        self.db.add(employee)
        self.db.commit()
        self.db.refresh(employee)
        return user, employee

    def _dashboard(self, user):
        return dashboard_stats(db=self.db, current_user=user)

    def _overview(self, user):
        return sales_overview_report(
            start_date=self.START_DATE,
            end_date=self.END_DATE,
            team=None,
            salesperson_id=None,
            source=None,
            db=self.db,
            current_user=user,
        )

    def _revenue(self, user):
        return sales_revenue_report(
            start_date=self.START_DATE,
            end_date=self.END_DATE,
            team=None,
            salesperson_id=None,
            db=self.db,
            current_user=user,
        )

    def _assert_company_kpis(self):
        """All company-wide Sales surfaces must agree on 2 deals / ₹66,300."""
        dashboard = self._dashboard(self.admin_user)
        self.assertEqual(dashboard["converted_leads"], 2)

        overview = self._overview(self.admin_user)
        self.assertEqual(overview["kpis"]["won_deals"]["value"], 2)
        self.assertEqual(overview["kpis"]["total_revenue"]["value"], 66300.0)
        self.assertEqual(overview["kpis"]["conversion_rate"]["value"], 0.0)
        won_stage = next(
            stage for stage in overview["sales_funnel"] if stage["stage"] == "Won"
        )
        self.assertEqual(won_stage["count"], 2)
        self.assertEqual(
            {row["name"]: (row["won_deals"], row["revenue"])
             for row in overview["top_salespersons"]},
            {
                self.sales_a_emp.name: (1, "₹25,000"),
                self.sales_b_emp.name: (0, "₹0"),
                self.manager_emp.name: (0, "₹0"),
            },
        )

        revenue = self._revenue(self.admin_user)
        kpi = revenue["kpis"]["total_revenue"]
        self.assertEqual(kpi["payments_count"], 2)
        self.assertEqual(kpi["transactions_count"], 2)
        self.assertEqual(kpi["raw_val"], 0.66)
        self.assertEqual(kpi["collected_raw"], 0.66)
        self.assertEqual(kpi["value"], "₹66,300")
        self.assertEqual(kpi["collected_revenue"], "₹66,300")
        self.assertIn("2 payments", kpi["vs_label"])

        monitoring = get_monitoring_overview(db=self.db, current_user=self.admin_user)
        self.assertEqual(monitoring["total_converted_leads"], 2)

        # Zero-value invoice must never appear in the won transaction details.
        won_rows = [
            row for row in revenue["deals_details"] if row["origin"] != "PIPELINE"
        ]
        self.assertEqual(
            {row["invoice_id"] for row in won_rows},
            {self.assigned_invoice.id, self.unassigned_invoice.id},
        )
        self.assertEqual(sum(float(row["raw_amount"]) for row in won_rows), 66300.0)

        # The unassigned Finance invoice is company revenue but is not silently
        # attributed to any salesperson. Only Sales A's ₹25,000 is ranked.
        attributed = {
            row["name"]: row["revenue"]
            for row in revenue["revenue_by_salesperson"]
        }
        self.assertEqual(attributed[self.sales_a_emp.name], 0.25)
        self.assertEqual(sum(attributed.values()), 0.25)

    def test_two_paid_invoices_are_consistent_across_all_sales_surfaces(self):
        self._assert_company_kpis()

    def test_manager_sees_team_plus_unassigned_but_executive_sees_own_only(self):
        manager_dashboard = self._dashboard(self.manager_user)
        self.assertEqual(manager_dashboard["converted_leads"], 2)
        manager_overview = self._overview(self.manager_user)
        self.assertEqual(manager_overview["kpis"]["won_deals"]["value"], 2)
        manager_revenue = self._revenue(self.manager_user)
        self.assertEqual(
            manager_revenue["kpis"]["total_revenue"]["payments_count"], 2
        )
        self.assertEqual(
            manager_revenue["kpis"]["total_revenue"]["raw_val"], 0.66
        )

        # A manager's company-revenue view is a team view and therefore also
        # includes the confirmed Finance-recorded invoice without attribution.
        manager_companies = get_companies_revenue(
            search=None,
            customer_id=None,
            db=self.db,
            current_user=self.manager_user,
        )
        self.assertEqual(
            sum(row.total_confirmed_revenue for row in manager_companies),
            66300.0,
        )

        # Sales A owns the ₹25,000 invoice; the unassigned ₹41,300 invoice must
        # not leak into a personal scope.
        sales_a_dashboard = self._dashboard(self.sales_a_user)
        self.assertEqual(sales_a_dashboard["converted_leads"], 1)
        sales_a_overview = self._overview(self.sales_a_user)
        self.assertEqual(sales_a_overview["kpis"]["won_deals"]["value"], 1)
        sales_a_revenue = self._revenue(self.sales_a_user)
        sales_a_kpi = sales_a_revenue["kpis"]["total_revenue"]
        self.assertEqual(sales_a_kpi["payments_count"], 1)
        self.assertEqual(sales_a_kpi["transactions_count"], 1)
        self.assertEqual(sales_a_kpi["raw_val"], 0.25)
        self.assertEqual(
            {row["name"]: row["won_deals"]
             for row in sales_a_overview["top_salespersons"]},
            {self.sales_a_emp.name: 1},
        )

        # Sales B has no attributed sale at all.
        sales_b_dashboard = self._dashboard(self.sales_b_user)
        self.assertEqual(sales_b_dashboard["converted_leads"], 0)
        self.assertEqual(
            self._overview(self.sales_b_user)["kpis"]["won_deals"]["value"], 0
        )
        self.assertEqual(
            self._revenue(self.sales_b_user)["kpis"]["total_revenue"][
                "payments_count"
            ],
            0,
        )

        # Personal company-revenue listings never include the unassigned sale.
        sales_a_companies = get_companies_revenue(
            search=None,
            customer_id=None,
            db=self.db,
            current_user=self.sales_a_user,
        )
        self.assertEqual(
            sum(row.total_confirmed_revenue for row in sales_a_companies),
            25000.0,
        )

    def test_won_lead_with_invoice_is_counted_once(self):
        won_lead = Lead(
            name="KPI Won Lead With Invoice",
            phone="9400000002",
            status="WON",
            source="Referral",
            company="KPI Deduped Client",
            assigned_to=self.sales_b_emp.id,
            created_at=datetime(2026, 10, 15, 10, 0, 0),
            updated_at=datetime(2026, 10, 20, 10, 0, 0),
        )
        self.db.add(won_lead)
        self.db.commit()
        self.db.refresh(won_lead)

        linked_invoice = Quotation(
            doc_type="invoice",
            doc_number="KPI/INV/26/0004",
            status="issued",
            payment_status="paid",
            customer_id=self.customer.id,
            lead_id=won_lead.id,
            assigned_to=self.sales_b_emp.id,
            created_by=self.sales_b_emp.id,
            customer_name=won_lead.name,
            company_name=won_lead.company,
            grand_total=10000.0,
            amount_paid=10000.0,
            issue_date=datetime(2026, 10, 21, 10, 0, 0),
            created_at=datetime(2026, 10, 21, 10, 0, 0),
        )
        self.db.add(linked_invoice)
        self.db.commit()
        self.db.refresh(linked_invoice)

        summary = RevenueService.get_sales_summary(
            db=self.db,
            employee_ids_filter=[
                self.manager_emp.id,
                self.sales_a_emp.id,
                self.sales_b_emp.id,
            ],
            include_unassigned=True,
        )

        # Two invoices plus the unassigned invoice = 3 unique deals. The won
        # lead is represented by its invoice and must not be counted twice.
        self.assertEqual(summary["converted_count"], 3)
        self.assertEqual(summary["sales_transactions_count"], 3)
        self.assertEqual(summary["successful_payments_count"], 3)
        self.assertEqual(summary["total_revenue"], 76300.0)

        lead_transactions = [
            transaction
            for transaction in summary["transactions"]
            if transaction.get("lead_id") == won_lead.id
        ]
        self.assertEqual(len(lead_transactions), 1)
        self.assertEqual(lead_transactions[0]["origin"], "INVOICE")
        self.assertEqual(lead_transactions[0]["amount"], 10000.0)

        # And the API surfaces agree with the shared service.
        self.assertEqual(self._dashboard(self.admin_user)["converted_leads"], 3)
        self.assertEqual(
            self._overview(self.admin_user)["kpis"]["won_deals"]["value"], 3
        )
        revenue_kpi = self._revenue(self.admin_user)["kpis"]["total_revenue"]
        self.assertEqual(revenue_kpi["payments_count"], 3)
        self.assertEqual(revenue_kpi["transactions_count"], 3)
        self.assertEqual(revenue_kpi["raw_val"], 0.76)

        # Sales B now owns exactly one deduplicated deal.
        sales_b_summary = RevenueService.get_sales_summary(
            db=self.db,
            employee_ids_filter=[self.sales_b_emp.id],
            include_unassigned=False,
        )
        self.assertEqual(sales_b_summary["converted_count"], 1)
        self.assertEqual(sales_b_summary["total_revenue"], 10000.0)

    def test_won_lead_without_invoice_counts_as_conversion_not_revenue(self):
        won_lead = Lead(
            name="KPI Won Lead Without Invoice",
            phone="9400000003",
            status="CONVERTED",
            source="Meta Ads",
            company="KPI Lead Only Client",
            assigned_to=self.sales_b_emp.id,
            quotetask_quotation_amount=0.0,
            created_at=datetime(2026, 10, 18, 10, 0, 0),
            updated_at=datetime(2026, 10, 25, 10, 0, 0),
        )
        self.db.add(won_lead)
        self.db.commit()
        self.db.refresh(won_lead)

        summary = RevenueService.get_sales_summary(
            db=self.db,
            employee_ids_filter=[
                self.manager_emp.id,
                self.sales_a_emp.id,
                self.sales_b_emp.id,
            ],
            include_unassigned=True,
        )

        # The won lead is a real conversion even without a monetary amount.
        self.assertEqual(summary["converted_count"], 3)
        # ...but it is not a payment, a transaction or revenue.
        self.assertEqual(summary["sales_transactions_count"], 2)
        self.assertEqual(summary["successful_payments_count"], 2)
        self.assertEqual(summary["total_revenue"], 66300.0)

        lead_transactions = [
            transaction
            for transaction in summary["transactions"]
            if transaction.get("lead_id") == won_lead.id
        ]
        self.assertEqual(len(lead_transactions), 1)
        self.assertEqual(lead_transactions[0]["origin"], "LEAD_WON")
        self.assertEqual(lead_transactions[0]["amount"], 0.0)

        self.assertEqual(self._dashboard(self.admin_user)["converted_leads"], 3)
        overview = self._overview(self.admin_user)
        self.assertEqual(overview["kpis"]["won_deals"]["value"], 3)
        won_stage = next(
            stage for stage in overview["sales_funnel"] if stage["stage"] == "Won"
        )
        self.assertEqual(won_stage["count"], 3)

        revenue_kpi = self._revenue(self.admin_user)["kpis"]["total_revenue"]
        self.assertEqual(revenue_kpi["payments_count"], 2)
        self.assertEqual(revenue_kpi["transactions_count"], 2)
        self.assertEqual(revenue_kpi["raw_val"], 0.66)

        sales_b_summary = RevenueService.get_sales_summary(
            db=self.db,
            employee_ids_filter=[self.sales_b_emp.id],
            include_unassigned=False,
        )
        self.assertEqual(sales_b_summary["converted_count"], 1)
        self.assertEqual(sales_b_summary["total_revenue"], 0.0)
        self.assertEqual(sales_b_summary["successful_payments_count"], 0)

    def test_zero_value_invoice_does_not_hide_linked_won_lead(self):
        won_lead = Lead(
            name="KPI Won Lead With Zero Invoice",
            phone="9400000004",
            status="WON",
            source="Website",
            company="KPI Zero Invoice Client",
            assigned_to=self.sales_b_emp.id,
            created_at=datetime(2026, 10, 19, 10, 0, 0),
            updated_at=datetime(2026, 10, 26, 10, 0, 0),
        )
        self.db.add(won_lead)
        self.db.commit()
        self.db.refresh(won_lead)

        zero_linked_invoice = Quotation(
            doc_type="invoice",
            doc_number="KPI/INV/26/0005",
            status="issued",
            payment_status="paid",
            customer_id=self.customer.id,
            lead_id=won_lead.id,
            assigned_to=self.sales_b_emp.id,
            created_by=self.sales_b_emp.id,
            customer_name=won_lead.name,
            company_name=won_lead.company,
            grand_total=0.0,
            amount_paid=0.0,
            issue_date=datetime(2026, 10, 27, 10, 0, 0),
            created_at=datetime(2026, 10, 27, 10, 0, 0),
        )
        self.db.add(zero_linked_invoice)
        self.db.commit()
        self.db.refresh(zero_linked_invoice)

        summary = RevenueService.get_sales_summary(
            db=self.db,
            employee_ids_filter=[
                self.manager_emp.id,
                self.sales_a_emp.id,
                self.sales_b_emp.id,
            ],
            include_unassigned=True,
        )

        # The zero-value invoice is excluded, but it must not suppress the
        # linked won lead's genuine conversion.
        self.assertEqual(summary["converted_count"], 3)
        self.assertEqual(summary["sales_transactions_count"], 2)
        self.assertEqual(summary["successful_payments_count"], 2)
        self.assertEqual(summary["total_revenue"], 66300.0)

        lead_transactions = [
            transaction
            for transaction in summary["converted_transactions"]
            if transaction.get("lead_id") == won_lead.id
        ]
        self.assertEqual(len(lead_transactions), 1)
        self.assertEqual(lead_transactions[0]["origin"], "LEAD_WON")

        revenue_for_lead = [
            transaction
            for transaction in summary["revenue_transactions"]
            if transaction.get("lead_id") == won_lead.id
        ]
        self.assertEqual(revenue_for_lead, [])

        self.assertEqual(self._dashboard(self.admin_user)["converted_leads"], 3)
        self.assertEqual(
            self._overview(self.admin_user)["kpis"]["won_deals"]["value"], 3
        )
        revenue_kpi = self._revenue(self.admin_user)["kpis"]["total_revenue"]
        self.assertEqual(revenue_kpi["payments_count"], 2)
        self.assertEqual(revenue_kpi["transactions_count"], 2)
        self.assertEqual(revenue_kpi["raw_val"], 0.66)

        sales_b_summary = RevenueService.get_sales_summary(
            db=self.db,
            employee_ids_filter=[self.sales_b_emp.id],
            include_unassigned=False,
        )
        self.assertEqual(sales_b_summary["converted_count"], 1)
        self.assertEqual(sales_b_summary["total_revenue"], 0.0)


if __name__ == "__main__":
    unittest.main()
