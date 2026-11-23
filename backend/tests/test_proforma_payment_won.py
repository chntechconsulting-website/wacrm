"""End-to-end tests for external Proforma payment -> Lead WON.

The suite uses an isolated in-memory SQLite database and overrides the app's
``get_db`` dependency, so it never touches the developer/live MySQL data.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import Base, get_db  # noqa: E402
from main import app  # noqa: E402
from models.activity import LeadActivity  # noqa: E402
from models.customer import Customer  # noqa: E402
from models.employee import Employee  # noqa: E402
from models.finance import Payment, ProformaPaymentEvent  # noqa: E402
from models.lead import Lead, LeadStatusHistory  # noqa: E402
from models.notification import Notification  # noqa: E402
from models.quotation import Quotation  # noqa: E402
from models.user import User  # noqa: E402
from models.workflow import FinanceHandoff, SupportHandoff  # noqa: E402
from integrations.proforma.auth import DEFAULT_INTEGRATION_KEY  # noqa: E402


class ProformaPaymentWonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=cls.engine)
        cls.Session = sessionmaker(
            autocommit=False, autoflush=False, bind=cls.engine
        )

    def setUp(self):
        # The in-memory engine uses a single shared connection (StaticPool),
        # so reset the schema for every test to keep them isolated.
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.Session()
        self._seed()
        app.dependency_overrides[get_db] = self._override_db
        self.client = TestClient(app)
        self.headers = {
            "X-API-Key": DEFAULT_INTEGRATION_KEY,
            "Content-Type": "application/json",
        }

    def tearDown(self):
        app.dependency_overrides.pop(get_db, None)
        self.client.close()
        self.db.close()

    def _override_db(self):
        try:
            yield self.db
        finally:
            pass

    # ------------------------------------------------------------------
    # Fixtures
    # ------------------------------------------------------------------
    def _seed(self):
        self.sales_user = User(
            username="sales.one",
            hashed_password="x",
            role="SALES_EXECUTIVE",
            department="SALES",
            is_active=True,
        )
        self.finance_user = User(
            username="finance.one",
            hashed_password="x",
            role="FINANCE",
            department="FINANCE",
            is_active=True,
        )
        self.support_user = User(
            username="support.one",
            hashed_password="x",
            role="SUPPORT_MANAGER",
            department="SUPPORT",
            is_active=True,
        )
        self.db.add_all(
            [self.sales_user, self.finance_user, self.support_user]
        )
        self.db.flush()

        self.sales_employee = Employee(
            user_id=self.sales_user.id,
            name="Sales One",
            email="sales.one@example.com",
            username="sales.one",
            role="SALES_EXECUTIVE",
            department="SALES",
            status="ACTIVE",
        )
        self.db.add(self.sales_employee)
        self.db.flush()

        self.lead = Lead(
            name="Acme Technologies",
            phone="9990001111",
            email="acme@example.com",
            company="Acme Technologies",
            status="NEW",
            source="WEBSITE",
            assigned_to=self.sales_employee.id,
        )
        self.other_lead = Lead(
            name="Beta Industries",
            phone="9990002222",
            email="beta@example.com",
            company="Beta Industries",
            status="NEW",
            source="WEBSITE",
        )
        self.db.add_all([self.lead, self.other_lead])
        self.db.flush()

        self.customer = Customer(
            company_name="Acme Technologies",
            contact_name="Acme Technologies",
            phone="9990001111",
            email="acme@example.com",
            converted_from_lead=self.lead.id,
        )
        self.other_customer = Customer(
            company_name="Beta Industries",
            contact_name="Beta Industries",
            phone="9990002222",
            email="beta@example.com",
            converted_from_lead=self.other_lead.id,
        )
        self.db.add_all([self.customer, self.other_customer])
        self.db.flush()

        self.proforma = Quotation(
            doc_type="proforma",
            doc_number="PI-2026-0001",
            status="issued",
            payment_status="unpaid",
            lead_id=self.lead.id,
            customer_id=self.customer.id,
            customer_name="Acme Technologies",
            company_name="Acme Technologies",
            phone="9990001111",
            email="acme@example.com",
            subtotal=84745.76,
            tax_total=15254.24,
            grand_total=100000.0,
            amount_paid=0.0,
            external_proforma_id="ERP-DOC-1",
        )
        self.other_proforma = Quotation(
            doc_type="proforma",
            doc_number="PI-2026-0002",
            status="issued",
            payment_status="unpaid",
            lead_id=self.other_lead.id,
            customer_id=self.other_customer.id,
            customer_name="Beta Industries",
            company_name="Beta Industries",
            phone="9990002222",
            email="beta@example.com",
            subtotal=42372.88,
            tax_total=7627.12,
            grand_total=50000.0,
            amount_paid=0.0,
            external_proforma_id="ERP-DOC-2",
        )
        self.db.add_all([self.proforma, self.other_proforma])
        self.db.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _post(self, payload, headers=None):
        return self.client.post(
            "/api/integrations/proforma/payments/webhook",
            json=payload,
            headers=headers or self.headers,
        )

    def _payment_payload(
        self,
        *,
        external_id="ERP-DOC-1",
        number="PI-2026-0001",
        amount=100000.0,
        txn="TXN-1001",
        status="PAID",
        event="payment.success",
    ):
        return {
            "event": event,
            "data": {
                "document": {
                    "id": external_id,
                    "number": number,
                    "paymentStatus": status,
                },
                "payment": {
                    "id": f"EXT-{txn}",
                    "transactionId": txn,
                    "amount": amount,
                    "method": "UPI",
                    "paymentDate": "2026-11-23T10:30:00+05:30",
                    "bankName": "HDFC Bank",
                },
            },
        }

    def _refresh(self, model, ident):
        return self.db.query(model).filter(model.id == ident).first()

    # ------------------------------------------------------------------
    # Required scenarios
    # ------------------------------------------------------------------
    def test_1_proforma_sent_without_payment_does_not_change_status(self):
        payload = {
            "event": "proforma.sent",
            "data": {
                "document": {
                    "id": "ERP-DOC-1",
                    "number": "PI-2026-0001",
                    "status": "issued",
                    "paymentStatus": "UNPAID",
                }
            },
        }
        response = self._post(payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "ignored")

        lead = self._refresh(Lead, self.lead.id)
        proforma = self._refresh(Quotation, self.proforma.id)
        self.assertEqual(lead.status, "NEW")
        self.assertEqual(float(proforma.amount_paid), 0.0)
        self.assertEqual(self.db.query(Payment).count(), 0)
        self.assertEqual(self.db.query(LeadStatusHistory).count(), 0)

    def test_2_successful_payment_marks_lead_won_and_records_everything(self):
        response = self._post(self._payment_payload())
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["status"], "processed")
        self.assertEqual(body["lead_status"], "WON")
        self.assertEqual(body["amount_received"], 100000.0)
        self.assertEqual(body["outstanding_balance"], 0.0)

        lead = self._refresh(Lead, self.lead.id)
        proforma = self._refresh(Quotation, self.proforma.id)
        self.assertEqual(lead.status, "WON")
        self.assertEqual(lead.assigned_to, self.sales_employee.id)
        self.assertEqual(float(proforma.amount_paid), 100000.0)
        self.assertEqual(proforma.payment_status, "paid")

        history = self.db.query(LeadStatusHistory).filter(
            LeadStatusHistory.lead_id == lead.id
        ).all()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].old_status, "NEW")
        self.assertEqual(history[0].new_status, "WON")

        payment = self.db.query(Payment).filter(Payment.invoice_id == proforma.id).one()
        self.assertEqual(payment.transaction_reference, "TXN-1001")
        self.assertEqual(float(payment.amount), 100000.0)
        self.assertEqual(payment.status, "PAID")
        self.assertEqual(payment.lead_id, lead.id)

        handoff = self.db.query(FinanceHandoff).filter(
            FinanceHandoff.lead_id == lead.id
        ).one()
        self.assertEqual(handoff.status, "PAID")
        self.assertEqual(handoff.payment_status, "PAID")
        self.assertEqual(float(handoff.paid_amount), 100000.0)

        support = self.db.query(SupportHandoff).filter(
            SupportHandoff.lead_id == lead.id
        ).one()
        self.assertEqual(support.finance_handoff_id, handoff.id)
        self.assertEqual(support.payment_status, "PAID")
        self.assertEqual(support.onboarding_status, "NEW")

        activity = self.db.query(LeadActivity).filter(
            LeadActivity.lead_id == lead.id,
            LeadActivity.activity_type == "PAYMENT_RECEIVED",
        ).first()
        self.assertIsNotNone(activity)
        self.assertIn("TXN-1001", activity.description)
        self.assertEqual(activity.department, "SALES")

        notification_users = {
            row.user_id
            for row in self.db.query(Notification).all()
        }
        self.assertIn(self.sales_user.id, notification_users)
        self.assertIn(self.finance_user.id, notification_users)
        self.assertIn(self.support_user.id, notification_users)

    def test_3_partial_payment_marks_won_and_updates_balance(self):
        response = self._post(
            self._payment_payload(amount=40000.0, txn="TXN-PARTIAL")
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["status"], "processed")
        self.assertEqual(body["lead_status"], "WON")
        self.assertEqual(body["total_paid"], 40000.0)
        self.assertEqual(body["outstanding_balance"], 60000.0)
        self.assertEqual(body["payment_status"], "PARTIALLY_PAID")

        proforma = self._refresh(Quotation, self.proforma.id)
        lead = self._refresh(Lead, self.lead.id)
        self.assertEqual(lead.status, "WON")
        self.assertEqual(float(proforma.amount_paid), 40000.0)
        self.assertEqual(proforma.payment_status, "partial")

        handoff = self.db.query(FinanceHandoff).filter(
            FinanceHandoff.lead_id == lead.id
        ).one()
        self.assertEqual(handoff.status, "PAYMENT_PENDING")
        self.assertEqual(handoff.payment_status, "PARTIALLY_PAID")
        self.assertEqual(float(handoff.paid_amount), 40000.0)

        support = self.db.query(SupportHandoff).filter(
            SupportHandoff.lead_id == lead.id
        ).one()
        self.assertEqual(support.payment_status, "PARTIALLY_PAID")
        self.assertEqual(float(support.paid_amount), 40000.0)

    def test_4_duplicate_webhook_does_not_duplicate_payment(self):
        payload = self._payment_payload(txn="TXN-DUP")
        first = self._post(payload)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["status"], "processed")

        second = self._post(payload)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json()["status"], "duplicate")

        self.assertEqual(self.db.query(Payment).count(), 1)
        self.assertEqual(self.db.query(ProformaPaymentEvent).count(), 1)
        self.assertEqual(self.db.query(LeadStatusHistory).count(), 1)
        proforma = self._refresh(Quotation, self.proforma.id)
        self.assertEqual(float(proforma.amount_paid), 100000.0)

    def test_5_failed_payment_does_not_change_status(self):
        payload = self._payment_payload(
            status="FAILED",
            event="payment.failed",
            txn="TXN-FAILED",
        )
        response = self._post(payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "ignored")

        lead = self._refresh(Lead, self.lead.id)
        proforma = self._refresh(Quotation, self.proforma.id)
        self.assertEqual(lead.status, "NEW")
        self.assertEqual(float(proforma.amount_paid), 0.0)
        self.assertEqual(self.db.query(Payment).count(), 0)
        self.assertEqual(self.db.query(LeadStatusHistory).count(), 0)

    def test_5b_failed_event_overrides_stale_paid_document_status(self):
        # The document still says PAID from an earlier transaction, but the
        # event being delivered is a failure.  It must not be treated as a
        # second successful payment or change the Lead.
        payload = self._payment_payload(
            status="PAID",
            event="payment.failed",
            txn="TXN-FAILED-STALE",
        )
        response = self._post(payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "ignored")
        self.assertIn("non_success_event", response.json()["reason"])

        self.assertEqual(self._refresh(Lead, self.lead.id).status, "NEW")
        self.assertEqual(self.db.query(Payment).count(), 0)
        self.assertEqual(self.db.query(LeadStatusHistory).count(), 0)

    def test_6_wrong_proforma_reference_does_not_touch_another_lead(self):
        # The external document id points at Proforma B while the document
        # number points at Proforma A.  This is ambiguous and must be rejected
        # rather than updating either Lead.
        payload = self._payment_payload(
            external_id="ERP-DOC-2",
            number="PI-2026-0001",
            txn="TXN-WRONG",
        )
        response = self._post(payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "ignored")
        self.assertIn("proforma", response.json()["reason"])

        lead_a = self._refresh(Lead, self.lead.id)
        lead_b = self._refresh(Lead, self.other_lead.id)
        proforma_a = self._refresh(Quotation, self.proforma.id)
        proforma_b = self._refresh(Quotation, self.other_proforma.id)
        self.assertEqual(lead_a.status, "NEW")
        self.assertEqual(lead_b.status, "NEW")
        self.assertEqual(float(proforma_a.amount_paid), 0.0)
        self.assertEqual(float(proforma_b.amount_paid), 0.0)
        self.assertEqual(self.db.query(Payment).count(), 0)

    def test_unknown_proforma_does_not_change_any_lead(self):
        payload = self._payment_payload(
            external_id="ERP-DOC-UNKNOWN",
            number="PI-UNKNOWN",
            txn="TXN-UNKNOWN",
        )
        response = self._post(payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "ignored")
        self.assertEqual(self.db.query(Payment).count(), 0)
        self.assertEqual(self._refresh(Lead, self.lead.id).status, "NEW")
        self.assertEqual(self._refresh(Lead, self.other_lead.id).status, "NEW")

    def test_conflicting_crm_proforma_id_is_rejected(self):
        # The external id/number point at Proforma B while metadata points at
        # Proforma A.  Guessing one of them could update the wrong Lead.
        payload = self._payment_payload(
            external_id="ERP-DOC-2",
            number="PI-2026-0002",
            txn="TXN-CONFLICT",
        )
        payload["metadata"] = {"crmProformaId": self.proforma.id}
        response = self._post(payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "ignored")
        self.assertIn("proforma", response.json()["reason"])
        self.assertEqual(self._refresh(Lead, self.lead.id).status, "NEW")
        self.assertEqual(self._refresh(Lead, self.other_lead.id).status, "NEW")
        self.assertEqual(self.db.query(Payment).count(), 0)

    def test_crm_proforma_id_alone_resolves_the_proforma(self):
        payload = {
            "event": "payment.success",
            "metadata": {"crmProformaId": self.proforma.id},
            "payment": {
                "transactionId": "TXN-CRM-ID",
                "amount": 100000.0,
                "method": "BANK_TRANSFER",
            },
        }
        response = self._post(payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "processed")
        self.assertEqual(response.json()["proforma_id"], self.proforma.id)
        self.assertEqual(self._refresh(Lead, self.lead.id).status, "WON")

    # ------------------------------------------------------------------
    # Reliability / lifecycle safeguards
    # ------------------------------------------------------------------
    def test_proforma_number_alone_resolves_without_polluting_external_id(self):
        payload = {
            "event": "payment.success",
            "data": {
                "document": {
                    "number": "PI-2026-0001",
                    "paymentStatus": "PAID",
                },
                "payment": {
                    "transactionId": "TXN-NUMBER-ONLY",
                    "amount": 100000.0,
                    "method": "UPI",
                },
            },
        }
        response = self._post(payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "processed")
        self.assertEqual(response.json()["proforma_id"], self.proforma.id)
        self.assertEqual(self._refresh(Lead, self.lead.id).status, "WON")
        # A Proforma number is not an external ERP document id and must never
        # overwrite the stored external identifier.
        self.assertEqual(
            self._refresh(Quotation, self.proforma.id).external_proforma_id,
            "ERP-DOC-1",
        )

    def test_proforma_created_event_with_success_delivery_status_is_ignored(self):
        payload = {
            "event": "proforma.created",
            "data": {
                "document": {
                    "id": "ERP-DOC-1",
                    "number": "PI-2026-0001",
                    "status": "SUCCESS",
                    "grandTotal": 100000.0,
                }
            },
        }
        response = self._post(payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "ignored")
        self.assertEqual(self._refresh(Lead, self.lead.id).status, "NEW")
        self.assertEqual(self.db.query(Payment).count(), 0)

    def test_proforma_sent_with_paid_document_status_is_ignored(self):
        # A lifecycle event may carry the document's current paid state, but
        # it is not a payment confirmation and must not mark the Lead WON.
        payload = {
            "event": "proforma.sent",
            "data": {
                "document": {
                    "id": "ERP-DOC-1",
                    "number": "PI-2026-0001",
                    "paymentStatus": "PAID",
                    "grandTotal": 100000.0,
                }
            },
        }
        response = self._post(payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "ignored")
        self.assertEqual(self._refresh(Lead, self.lead.id).status, "NEW")
        self.assertEqual(float(self._refresh(Quotation, self.proforma.id).amount_paid), 0.0)
        self.assertEqual(self.db.query(Payment).count(), 0)

    def test_paid_event_without_amount_pays_the_remaining_balance(self):
        payload = {
            "event": "payment.paid",
            "data": {
                "document": {"id": "ERP-DOC-1", "number": "PI-2026-0001"},
                "payment": {"transactionId": "TXN-NO-AMOUNT"},
            },
        }
        response = self._post(payload)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["status"], "processed")
        self.assertEqual(body["amount_received"], 100000.0)
        self.assertEqual(body["outstanding_balance"], 0.0)
        self.assertEqual(self._refresh(Lead, self.lead.id).status, "WON")

    def test_duplicate_event_id_with_new_transaction_id_is_rejected(self):
        first = self._payment_payload(txn="TXN-EVENT-1")
        first["eventId"] = "EVT-SAME"
        response = self._post(first)
        self.assertEqual(response.json()["status"], "processed")

        second = self._payment_payload(txn="TXN-EVENT-2")
        second["eventId"] = "EVT-SAME"
        duplicate = self._post(second)
        self.assertEqual(duplicate.status_code, 200, duplicate.text)
        self.assertEqual(duplicate.json()["status"], "duplicate")
        self.assertEqual(duplicate.json()["reason"], "duplicate_event_id")
        self.assertEqual(self.db.query(Payment).count(), 1)

    def test_duplicate_transaction_id_with_new_event_id_is_rejected(self):
        first = self._payment_payload(txn="TXN-SAME")
        first["eventId"] = "EVT-ONE"
        self.assertEqual(self._post(first).json()["status"], "processed")

        second = self._payment_payload(txn="TXN-SAME")
        second["eventId"] = "EVT-TWO"
        duplicate = self._post(second)
        self.assertEqual(duplicate.status_code, 200, duplicate.text)
        self.assertEqual(duplicate.json()["status"], "duplicate")
        self.assertEqual(duplicate.json()["reason"], "duplicate_transaction_id")
        self.assertEqual(self.db.query(Payment).count(), 1)

    def test_multiple_partial_payments_accumulate(self):
        first = self._post(
            self._payment_payload(amount=40000.0, txn="TXN-MULTI-1")
        )
        self.assertEqual(first.status_code, 200, first.text)
        second = self._post(
            self._payment_payload(
                amount=60000.0,
                txn="TXN-MULTI-2",
                status="PARTIALLY_PAID",
            )
        )
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json()["status"], "processed")
        self.assertEqual(second.json()["total_paid"], 100000.0)
        self.assertEqual(second.json()["outstanding_balance"], 0.0)

        proforma = self._refresh(Quotation, self.proforma.id)
        self.assertEqual(float(proforma.amount_paid), 100000.0)
        self.assertEqual(proforma.payment_status, "paid")
        self.assertEqual(
            self.db.query(Payment).filter(Payment.invoice_id == proforma.id).count(),
            2,
        )
        handoff = self.db.query(FinanceHandoff).filter(
            FinanceHandoff.lead_id == self.lead.id
        ).one()
        self.assertEqual(handoff.status, "PAID")
        self.assertEqual(handoff.payment_status, "PAID")

    def test_converted_to_support_status_is_preserved(self):
        lead = self._refresh(Lead, self.lead.id)
        lead.status = "CONVERTED_TO_SUPPORT"
        self.db.commit()

        response = self._post(
            self._payment_payload(txn="TXN-LATE-PAYMENT")
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "processed")
        self.assertEqual(response.json()["lead_status"], "CONVERTED_TO_SUPPORT")

        lead = self._refresh(Lead, self.lead.id)
        self.assertEqual(lead.status, "CONVERTED_TO_SUPPORT")
        self.assertEqual(self.db.query(LeadStatusHistory).count(), 0)

    # ------------------------------------------------------------------
    # Authentication / signature
    # ------------------------------------------------------------------
    def test_missing_credentials_are_rejected(self):
        response = self.client.post(
            "/api/integrations/proforma/payments/webhook",
            json=self._payment_payload(),
        )
        self.assertEqual(response.status_code, 401)

    def test_invalid_api_key_is_rejected(self):
        response = self._post(
            self._payment_payload(),
            headers={"X-API-Key": "definitely-wrong"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self._refresh(Lead, self.lead.id).status, "NEW")

    def test_valid_hmac_signature_is_accepted(self):
        payload = self._payment_payload(txn="TXN-SIGNED")
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        timestamp = int(time.time())
        secret = "test-webhook-secret"
        signature = hmac.new(
            secret.encode("utf-8"),
            f"{timestamp}.".encode("utf-8") + raw,
            hashlib.sha256,
        ).hexdigest()

        with patch.dict(
            os.environ,
            {"WAQUOTE_WEBHOOK_SECRET": secret},
            clear=False,
        ):
            response = self.client.post(
                "/api/integrations/proforma/payments/webhook",
                content=raw,
                headers={
                    "Content-Type": "application/json",
                    "X-WAQuote-Signature": f"t={timestamp},v1={signature}",
                },
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "processed")
        self.assertEqual(self._refresh(Lead, self.lead.id).status, "WON")

    def test_invalid_hmac_signature_is_rejected(self):
        payload = self._payment_payload(txn="TXN-BAD-SIGNATURE")
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        timestamp = int(time.time())

        with patch.dict(
            os.environ,
            {"WAQUOTE_WEBHOOK_SECRET": "test-webhook-secret"},
            clear=False,
        ):
            response = self.client.post(
                "/api/integrations/proforma/payments/webhook",
                content=raw,
                headers={
                    "Content-Type": "application/json",
                    "X-WAQuote-Signature": f"t={timestamp},v1=deadbeef",
                },
            )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self._refresh(Lead, self.lead.id).status, "NEW")
        self.assertEqual(self.db.query(Payment).count(), 0)

    def test_waquote_webhook_alias_uses_the_same_processor(self):
        response = self.client.post(
            "/api/integrations/waquote/webhook",
            json=self._payment_payload(txn="TXN-ALIAS"),
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "processed")
        self.assertEqual(self._refresh(Lead, self.lead.id).status, "WON")

    def test_payment_history_endpoint_returns_recorded_payment(self):
        self._post(self._payment_payload(txn="TXN-HISTORY"))
        response = self.client.get(
            f"/api/integrations/proforma/{self.proforma.id}/payments",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["amount_paid"], 100000.0)
        self.assertEqual(body["outstanding_balance"], 0.0)
        self.assertEqual(len(body["payments"]), 1)
        self.assertEqual(body["payments"][0]["transaction_id"], "TXN-HISTORY")


if __name__ == "__main__":
    unittest.main()
