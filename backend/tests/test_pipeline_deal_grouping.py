"""
Regression tests for deal-level grouping across Sales reports.

A deal that has a quotation, a proforma and a paid invoice must appear once,
at its latest stage, on every report surface. Multiple genuine deals for the
same customer must stay separate, and multiple invoices for the same deal must
not create multiple "Won" rows.

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
from integrations.proforma.schemas import ProformaIntegrationPayload
from integrations.proforma.service import ProformaIntegrationService
from models.customer import Customer
from models.employee import Employee
from models.lead import Lead
from models.quotation import Quotation
from models.user import User
from routers.reports import sales_overview_report, sales_revenue_report
from services.deal_grouping import build_deal_groups
from services.permission_service import seed_default_roles_if_needed


class PipelineDealGroupingTests(unittest.TestCase):
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
            "grouping_admin", "ADMIN", "ADMINISTRATION", name="Grouping Admin"
        )
        self.sales_user, self.sales_emp = self._make_person(
            "grouping_sales", "SALES_EXECUTIVE", "SALES", name="Grouping Sales"
        )

        self.customer = Customer(
            company_name="Grouping Client",
            contact_name="Grouping Contact",
            phone="9500000001",
        )
        self.db.add(self.customer)
        self.db.commit()
        self.db.refresh(self.customer)

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
            phone=f"96{user.id:08d}"[:10],
            username=username,
            role=role,
            status="ACTIVE",
        )
        self.db.add(employee)
        self.db.commit()
        self.db.refresh(employee)
        return user, employee

    def _make_lead(self, name, status="PROPOSAL SENT"):
        lead = Lead(
            name=name,
            phone=f"95{self.db.query(Lead).count() + 1:08d}"[:10],
            company=name,
            status=status,
            assigned_to=self.sales_emp.id,
            created_at=datetime(2026, 10, 1, 9, 0, 0),
            updated_at=datetime(2026, 10, 1, 9, 0, 0),
        )
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        return lead

    def _make_document(
        self,
        doc_type,
        doc_number,
        grand_total,
        day,
        lead=None,
        source=None,
        payment_status="unpaid",
        amount_paid=0.0,
        created_by=True,
    ):
        timestamp = datetime(2026, 10, day, 10, 0, 0)
        doc = Quotation(
            doc_type=doc_type,
            doc_number=doc_number,
            status="issued",
            payment_status=payment_status,
            lead_id=lead.id if lead is not None else None,
            customer_id=self.customer.id,
            customer_name=self.customer.company_name,
            company_name=self.customer.company_name,
            assigned_to=self.sales_emp.id,
            created_by=self.sales_emp.id if created_by else None,
            source_quotation_id=source.id if source is not None else None,
            source_quotation_number=source.doc_number if source is not None else None,
            grand_total=grand_total,
            amount_paid=amount_paid,
            issue_date=timestamp,
            created_at=timestamp,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def _revenue_report(self):
        return sales_revenue_report(
            start_date=self.START_DATE,
            end_date=self.END_DATE,
            team=None,
            salesperson_id=None,
            db=self.db,
            current_user=self.admin_user,
        )

    def _overview(self):
        return sales_overview_report(
            start_date=self.START_DATE,
            end_date=self.END_DATE,
            team=None,
            salesperson_id=None,
            source=None,
            db=self.db,
            current_user=self.admin_user,
        )

    @staticmethod
    def _stage_amount(report, stage):
        return next(
            row["amount"]
            for row in report["deal_status_by_revenue"]
            if row["stage"] == stage
        )

    def test_quotation_and_proforma_are_one_open_deal(self):
        lead = self._make_lead("Grouped Open Deal")
        quotation = self._make_document(
            "quotation", "GRP/QT/0001", 10000.0, 1, lead=lead
        )
        proforma = self._make_document(
            "proforma", "GRP/PI/0001", 12000.0, 2, lead=lead, source=quotation
        )

        report = self._revenue_report()
        pipeline_rows = [
            row for row in report["deals_details"] if row["origin"] == "PIPELINE"
        ]

        self.assertEqual(len(pipeline_rows), 1)
        self.assertEqual(pipeline_rows[0]["lead_id"], lead.id)
        self.assertEqual(pipeline_rows[0]["id"], proforma.id)
        self.assertEqual(pipeline_rows[0]["status"], "Negotiation")
        self.assertEqual(pipeline_rows[0]["raw_amount"], 12000.0)

        # The revised proforma replaces, not adds to, the quotation amount.
        self.assertEqual(report["kpis"]["pipeline_value"]["raw_val"], 0.12)
        self.assertEqual(self._stage_amount(report, "Negotiation"), "₹12,000")
        self.assertEqual(self._stage_amount(report, "Proposal Sent"), "₹0")

        # The Sales Overview funnel counts deals, not documents.
        overview = self._overview()
        funnel = {stage["stage"]: stage["count"] for stage in overview["sales_funnel"]}
        self.assertEqual(funnel["Proposal Sent"], 0)
        self.assertEqual(funnel["Negotiation"], 1)

    def test_won_deal_does_not_remain_in_pipeline(self):
        lead = self._make_lead("Grouped Won Deal", status="WON")
        quotation = self._make_document(
            "quotation", "GRP/QT/0002", 10000.0, 3, lead=lead
        )
        proforma = self._make_document(
            "proforma", "GRP/PI/0002", 12000.0, 4, lead=lead, source=quotation
        )
        invoice = self._make_document(
            "invoice",
            "GRP/INV/0001",
            12500.0,
            5,
            lead=lead,
            source=proforma,
            payment_status="paid",
            amount_paid=12500.0,
        )

        report = self._revenue_report()
        won_rows = [
            row for row in report["deals_details"] if row["origin"] != "PIPELINE"
        ]
        pipeline_rows = [
            row for row in report["deals_details"] if row["origin"] == "PIPELINE"
        ]

        self.assertEqual(len(won_rows), 1)
        self.assertEqual(won_rows[0]["lead_id"], lead.id)
        self.assertEqual(won_rows[0]["invoice_id"], invoice.id)
        self.assertEqual(won_rows[0]["raw_amount"], 12500.0)
        self.assertEqual(pipeline_rows, [])

        # The deal is only in Won; its quotation/proforma no longer inflate the
        # open pipeline totals.
        self.assertEqual(report["kpis"]["pipeline_value"]["raw_val"], 0.0)
        self.assertEqual(self._stage_amount(report, "Won (Billed)"), "₹12,500")
        self.assertEqual(self._stage_amount(report, "Proposal Sent"), "₹0")
        self.assertEqual(self._stage_amount(report, "Negotiation"), "₹0")

        overview = self._overview()
        funnel = {stage["stage"]: stage["count"] for stage in overview["sales_funnel"]}
        self.assertEqual(funnel["Won"], 1)
        self.assertEqual(funnel["Proposal Sent"], 0)
        self.assertEqual(funnel["Negotiation"], 0)

    def test_separate_deals_for_same_customer_are_not_merged(self):
        first = self._make_document("quotation", "GRP/QT/0003", 10000.0, 6)
        second = self._make_document("quotation", "GRP/QT/0004", 20000.0, 7)

        groups = build_deal_groups([first, second])
        self.assertEqual(len(groups), 2)

        report = self._revenue_report()
        pipeline_rows = [
            row for row in report["deals_details"] if row["origin"] == "PIPELINE"
        ]
        self.assertEqual(
            {row["id"] for row in pipeline_rows}, {first.id, second.id}
        )
        self.assertEqual(report["kpis"]["pipeline_value"]["raw_val"], 0.30)

    def test_multiple_invoices_for_one_deal_are_a_single_won_row(self):
        lead = self._make_lead("Multi Invoice Deal", status="WON")
        first_invoice = self._make_document(
            "invoice",
            "GRP/INV/0002",
            5000.0,
            8,
            lead=lead,
            payment_status="paid",
            amount_paid=5000.0,
        )
        second_invoice = self._make_document(
            "invoice",
            "GRP/INV/0003",
            7000.0,
            9,
            lead=lead,
            payment_status="paid",
            amount_paid=7000.0,
        )

        report = self._revenue_report()
        won_rows = [
            row for row in report["deals_details"] if row["origin"] != "PIPELINE"
        ]

        self.assertEqual(len(won_rows), 1)
        self.assertEqual(won_rows[0]["lead_id"], lead.id)
        self.assertEqual(won_rows[0]["raw_amount"], 12000.0)
        self.assertEqual(
            set(won_rows[0]["invoice_ids"]),
            {first_invoice.id, second_invoice.id},
        )
        self.assertEqual(report["kpis"]["total_revenue"]["raw_val"], 0.12)
        # Payment/transaction KPIs still count the two confirmed invoices.
        self.assertEqual(report["kpis"]["total_revenue"]["transactions_count"], 2)

    def test_external_proforma_inherits_lead_and_source_quotation(self):
        lead = self._make_lead("External Proforma Deal")
        quotation = self._make_document(
            "quotation", "GRP/QT/0005", 10000.0, 10, lead=lead
        )

        payload = ProformaIntegrationPayload(
            customerId=self.customer.id,
            companyName=self.customer.company_name,
            contactPerson=self.customer.contact_name,
            phone=self.customer.phone,
            productCategory="wahrms",
            selectedBundle="hr_payroll",
            quotationNumber=quotation.doc_number,
            lineItems=[
                {
                    "name": "HR Payroll",
                    "qty": 1,
                    "rate": 10000.0,
                    "gstRate": 18,
                }
            ],
        )
        response = ProformaIntegrationService.process_proforma_payload(
            self.db, payload
        )

        created = (
            self.db.query(Quotation)
            .filter(Quotation.id == response.proformaId)
            .first()
        )
        self.assertIsNotNone(created)
        self.assertEqual(created.lead_id, lead.id)
        self.assertEqual(created.source_quotation_id, quotation.id)
        self.assertEqual(created.source_quotation_number, quotation.doc_number)


if __name__ == "__main__":
    unittest.main()
