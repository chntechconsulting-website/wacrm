"""Finance dashboard KPI regression tests.

Isolated in-memory SQLite only. These tests cover the two sources of truth the
Finance dashboard must reconcile:

* Payment ledger rows (manual / gateway payments)
* Workflow-confirmed invoices and Finance handoffs (no Payment row is created)

The same deal must never be counted twice.
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
from models.finance import Payment
from models.quotation import Quotation
from models.workflow import FinanceHandoff
from services.finance_service import FinanceService


class FinanceDashboardKpiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db = Session()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _invoice(self, **overrides):
        data = {
            "doc_type": "invoice",
            "doc_number": "CHN/INV/26/0003",
            "status": "issued",
            "payment_status": "paid",
            "customer_name": "Vinoth / Elangovan & brothers",
            "grand_total": 37594.0,
            "amount_paid": 37594.0,
            "issue_date": datetime.utcnow(),
        }
        data.update(overrides)
        invoice = Quotation(**data)
        self.db.add(invoice)
        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def _handoff(self, **overrides):
        data = {
            "lead_id": 1,
            "customer_id": 1,
            "customer_name": "Vinoth / Elangovan & brothers",
            "final_amount": 10000.0,
            "paid_amount": 0.0,
            "status": "PAYMENT_PENDING",
            "payment_status": "PAYMENT_PENDING",
            "created_at": datetime.utcnow(),
        }
        data.update(overrides)
        handoff = FinanceHandoff(**data)
        self.db.add(handoff)
        self.db.commit()
        self.db.refresh(handoff)
        return handoff

    def test_workflow_confirmed_invoice_counts_as_revenue(self):
        self._invoice()

        stats = FinanceService.get_dashboard_kpis(self.db)

        self.assertEqual(stats["total_revenue"], 37594.0)
        self.assertEqual(stats["current_month_revenue"], 37594.0)
        self.assertEqual(stats["paid_invoices_count"], 1)
        self.assertEqual(stats["paid_invoices_amount"], 37594.0)
        self.assertEqual(stats["pending_payments_count"], 0)
        self.assertEqual(stats["recent_payments"][0]["payment_number"], "CHN/INV/26/0003")

    def test_payment_linked_invoice_is_not_counted_twice(self):
        invoice = self._invoice()
        self.db.add(
            Payment(
                payment_number="PAY-TEST-0001",
                invoice_id=invoice.id,
                amount=37594.0,
                status="PAID",
                payment_method="BANK_TRANSFER",
                payment_date=datetime.utcnow(),
            )
        )
        self.db.commit()

        stats = FinanceService.get_dashboard_kpis(self.db)

        self.assertEqual(stats["total_revenue"], 37594.0)
        self.assertEqual(stats["current_month_revenue"], 37594.0)

    def test_pending_handoff_is_included_in_pending_payments(self):
        self._handoff(status="unpaid", payment_status="unpaid")

        stats = FinanceService.get_dashboard_kpis(self.db)

        self.assertEqual(stats["pending_payments_count"], 1)
        self.assertEqual(stats["pending_payments_amount"], 10000.0)
        self.assertEqual(stats["pending_handoffs_count"], 1)
        self.assertEqual(stats["pending_handoffs_amount"], 10000.0)

    def test_pending_handoff_and_its_invoice_are_not_double_counted(self):
        self._handoff(lead_id=7, invoice_number="CHN/INV/26/0004")
        self._invoice(
            lead_id=7,
            doc_number="CHN/INV/26/0004",
            payment_status="unpaid",
            amount_paid=0.0,
            grand_total=10000.0,
        )

        stats = FinanceService.get_dashboard_kpis(self.db)

        self.assertEqual(stats["pending_payments_count"], 1)
        self.assertEqual(stats["pending_payments_amount"], 10000.0)
        self.assertEqual(stats["pending_handoffs_count"], 0)

    def test_partially_paid_handoff_counts_only_the_balance(self):
        self._handoff(
            final_amount=10000.0,
            paid_amount=4000.0,
            status="PARTIALLY_PAID",
            payment_status="PARTIALLY_PAID",
        )

        stats = FinanceService.get_dashboard_kpis(self.db)

        self.assertEqual(stats["pending_payments_count"], 1)
        self.assertEqual(stats["pending_payments_amount"], 6000.0)

    def test_paid_handoff_without_invoice_counts_as_revenue(self):
        self._handoff(
            status="PAID",
            payment_status="PAID",
            paid_amount=8000.0,
            final_amount=8000.0,
            payment_mode="UPI",
            payment_date=datetime.utcnow(),
        )

        stats = FinanceService.get_dashboard_kpis(self.db)

        self.assertEqual(stats["total_revenue"], 8000.0)
        self.assertEqual(stats["current_month_revenue"], 8000.0)
        self.assertEqual(stats["pending_payments_count"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
