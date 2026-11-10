"""Invoice document status regression tests.

Invoices are issued documents: ``status`` describes the document lifecycle and
``payment_status`` / ``amount_paid`` describe payment. These tests cover the
Finance API, the WA Quote billing-document API and legacy records that stored a
payment value in the invoice status column.
"""

import os
import sys
import unittest
from datetime import datetime

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401 - registers every model on Base.metadata
from database import Base, get_db
from integrations.waquote.router import router as waquote_router
from models.quotation import Quotation
from models.user import User
from routers.finance import router as finance_router
from routers.sales_targets import router as sales_targets_router
from services.auth import get_current_user
from services.finance_service import FinanceService
from utils.document_status import normalize_invoice_document_status


class InvoiceDocumentStatusApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db = self.Session()

        self.finance_user = User(
            username="invoice_status_finance",
            hashed_password="test",
            role="FINANCE",
            department="FINANCE",
            is_active=True,
        )
        self.admin_user = User(
            username="invoice_status_admin",
            hashed_password="test",
            role="ADMIN",
            department="ADMIN",
            is_active=True,
        )
        self.db.add_all([self.finance_user, self.admin_user])
        self.db.commit()
        self.db.refresh(self.finance_user)
        self.db.refresh(self.admin_user)

        self.app = FastAPI()
        self.app.include_router(finance_router, prefix="/api")
        self.app.include_router(waquote_router, prefix="/api/v1")
        self.app.include_router(sales_targets_router, prefix="/api/v1")

        def override_db():
            yield self.db

        self.app.dependency_overrides[get_db] = override_db
        self.app.dependency_overrides[get_current_user] = lambda: self.finance_user
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _document(
        self,
        number,
        *,
        doc_type="invoice",
        status="issued",
        payment_status="unpaid",
        total=1000.0,
        paid=0.0,
        customer_name="Invoice Status Test",
    ):
        doc = Quotation(
            doc_type=doc_type,
            doc_number=number,
            status=status,
            payment_status=payment_status,
            customer_name=customer_name,
            subtotal=total,
            grand_total=total,
            amount_paid=paid,
            issue_date=datetime.utcnow(),
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def _finance_invoice(self, number):
        response = self.client.get("/api/finance/invoices", params={"limit": 100})
        self.assertEqual(response.status_code, 200, response.text)
        return next(
            item for item in response.json()["items"]
            if item["invoice_number"] == number
        )

    def _waquote_document(self, raw_id):
        response = self.client.get("/api/v1/integrations/waquote/documents")
        self.assertEqual(response.status_code, 200, response.text)
        return next(
            item for item in response.json()["documents"]
            if item["rawId"] == raw_id
        )

    def test_issued_invoices_keep_issued_status_for_all_payment_states(self):
        unpaid = self._document(
            "CHN/INV/TEST/1001", payment_status="unpaid", total=1000.0, paid=0.0
        )
        partial = self._document(
            "CHN/INV/TEST/1002", payment_status="partial", total=1000.0, paid=400.0
        )
        paid = self._document(
            "CHN/INV/TEST/1003", payment_status="paid", total=1000.0, paid=1000.0
        )

        expected = {
            "CHN/INV/TEST/1001": ("unpaid", 0.0, 1000.0),
            "CHN/INV/TEST/1002": ("partial", 400.0, 600.0),
            "CHN/INV/TEST/1003": ("paid", 1000.0, 0.0),
        }
        for number, (payment_status, amount_paid, pending_amount) in expected.items():
            item = self._finance_invoice(number)
            self.assertEqual(item["status"], "issued")
            self.assertEqual(item["payment_status"], payment_status)
            self.assertEqual(item["amount_paid"], amount_paid)
            self.assertEqual(item["pending_amount"], pending_amount)

        for invoice, expected_payment in (
            (unpaid, "unpaid"),
            (partial, "partial"),
            (paid, "paid"),
        ):
            response = self.client.get(f"/api/finance/invoices/{invoice.id}")
            self.assertEqual(response.status_code, 200, response.text)
            detail = response.json()
            self.assertEqual(detail["status"], "issued")
            self.assertEqual(detail["payment_status"], expected_payment)

        stats = FinanceService.get_dashboard_kpis(self.db)
        self.assertEqual(stats["paid_invoices_count"], 1)
        self.assertEqual(stats["paid_invoices_amount"], 1000.0)
        self.assertEqual(stats["total_revenue"], 1000.0)

    def test_legacy_paid_document_status_is_exposed_as_issued_without_db_rewrite(self):
        legacy = self._document(
            "CHN/INV/TEST/1101",
            status="paid",
            payment_status="paid",
            total=750.0,
            paid=750.0,
        )

        item = self._finance_invoice("CHN/INV/TEST/1101")
        self.assertEqual(item["status"], "issued")
        self.assertEqual(item["payment_status"], "paid")
        self.assertEqual(item["amount_paid"], 750.0)
        self.assertEqual(item["pending_amount"], 0.0)

        response = self.client.get(f"/api/finance/invoices/{legacy.id}")
        self.assertEqual(response.status_code, 200, response.text)
        detail = response.json()
        self.assertEqual(detail["status"], "issued")
        self.assertEqual(detail["payment_status"], "paid")

        wa_doc = self._waquote_document(legacy.id)
        self.assertEqual(wa_doc["status"], "issued")
        self.assertEqual(wa_doc["paymentStatus"], "paid")
        self.assertEqual(wa_doc["financials"]["totalPaid"], 750.0)
        self.assertEqual(wa_doc["financials"]["balance"], 0.0)

        response = self.client.get(
            f"/api/v1/integrations/waquote/documents/{legacy.id}"
        )
        self.assertEqual(response.status_code, 200, response.text)
        single_doc = response.json()["document"]
        self.assertEqual(single_doc["status"], "issued")
        self.assertEqual(single_doc["paymentStatus"], "paid")

        # The API projects the legacy value; it must not rewrite stored history.
        self.db.expire_all()
        stored = self.db.query(Quotation).filter(Quotation.id == legacy.id).one()
        self.assertEqual(stored.status, "paid")
        self.assertEqual(stored.payment_status, "paid")

    def test_draft_proforma_and_cancelled_statuses_are_not_changed(self):
        quotation = self._document(
            "CHN/QT/TEST/2001",
            doc_type="quotation",
            status="draft",
            total=500.0,
        )
        proforma = self._document(
            "CHN/PI/TEST/2002",
            doc_type="proforma",
            status="sent",
            total=600.0,
        )
        cancelled_invoice = self._document(
            "CHN/INV/TEST/2003",
            status="cancelled",
            total=700.0,
        )

        self.assertEqual(self._waquote_document(quotation.id)["status"], "draft")
        self.assertEqual(self._waquote_document(proforma.id)["status"], "sent")
        self.assertEqual(
            self._waquote_document(cancelled_invoice.id)["status"], "cancelled"
        )

        self.assertEqual(normalize_invoice_document_status("draft"), "draft")
        self.assertEqual(normalize_invoice_document_status("cancelled"), "cancelled")
        self.assertEqual(normalize_invoice_document_status("PAID"), "issued")
        self.assertEqual(normalize_invoice_document_status("partially-paid"), "issued")
        self.assertEqual(normalize_invoice_document_status(None), "issued")

    def test_invoice_create_and_update_cannot_store_payment_status_as_document_status(self):
        create_response = self.client.post(
            "/api/v1/integrations/waquote/documents",
            json={
                "doc_type": "invoice",
                "doc_number": "CHN/INV/TEST/3001",
                "status": "paid",
                "payment_status": "paid",
                "customer_name": "Source Guard Client",
                "subtotal": 1000.0,
                "tax_total": 180.0,
                "grand_total": 1180.0,
                "amount_paid": 1180.0,
                "line_items": [
                    {
                        "description": "WA! HRMS Subscription",
                        "qty": 1,
                        "rate": 1000.0,
                        "amount": 1000.0,
                    }
                ],
            },
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        created = create_response.json()["document"]
        self.assertEqual(created["status"], "issued")

        self.db.expire_all()
        invoice = (
            self.db.query(Quotation)
            .filter(Quotation.doc_number == "CHN/INV/TEST/3001")
            .one()
        )
        self.assertEqual(invoice.status, "issued")
        self.assertEqual(invoice.payment_status, "paid")
        self.assertEqual(invoice.amount_paid, 1180.0)

        update_response = self.client.put(
            f"/api/v1/integrations/waquote/documents/{invoice.id}",
            json={
                "doc_type": "invoice",
                "doc_number": "CHN/INV/TEST/3001",
                "status": "paid",
                "payment_status": "partial",
                "customer_name": "Source Guard Client",
                "subtotal": 1000.0,
                "tax_total": 180.0,
                "grand_total": 1180.0,
            },
        )
        self.assertEqual(update_response.status_code, 200, update_response.text)
        self.assertEqual(update_response.json()["document"]["status"], "issued")

        self.db.expire_all()
        updated = self.db.query(Quotation).filter(Quotation.id == invoice.id).one()
        self.assertEqual(updated.status, "issued")
        self.assertEqual(updated.payment_status, "partial")

    def test_companies_revenue_exposes_invoice_document_status_separately(self):
        legacy = self._document(
            "CHN/INV/TEST/4001",
            status="paid",
            payment_status="paid",
            total=750.0,
            paid=750.0,
            customer_name="Companies Revenue Client",
        )

        self.app.dependency_overrides[get_current_user] = lambda: self.admin_user
        try:
            response = self.client.get(
                "/api/v1/sales-targets/companies-revenue"
            )
        finally:
            self.app.dependency_overrides[get_current_user] = lambda: self.finance_user

        self.assertEqual(response.status_code, 200, response.text)
        summary = next(
            row for row in response.json()
            if any(inv["invoice_id"] == legacy.id for inv in row["invoices"])
        )
        invoice = next(
            inv for inv in summary["invoices"] if inv["invoice_id"] == legacy.id
        )
        self.assertEqual(invoice["status"], "issued")
        self.assertEqual(invoice["payment_status"], "PAID")
        self.assertEqual(invoice["amount_paid"], 750.0)
        self.assertEqual(invoice["grand_total"], 750.0)
        self.assertGreaterEqual(summary["total_confirmed_revenue"], 750.0)
        self.assertGreaterEqual(summary["total_collected_revenue"], 750.0)

        # Revenue projection must not rewrite the stored lifecycle value either.
        self.db.expire_all()
        stored = self.db.query(Quotation).filter(Quotation.id == legacy.id).one()
        self.assertEqual(stored.status, "paid")
        self.assertEqual(stored.payment_status, "paid")


if __name__ == "__main__":
    unittest.main(verbosity=2)
