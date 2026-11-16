"""Quotation-to-lead linking tests.

Covers the two requested flows at the API boundary: matching suggestions and
linking an already-created quotation to a lead without creating duplicates or
changing the quotation's financial identity.
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
from models.activity import LeadActivity
from models.audit_log import AuditLog
from models.lead import Lead
from models.quotation import Quotation
from models.user import User
from services.auth import get_current_user


class QuotationLeadLinkingApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db = self.Session()

        self.admin = User(
            username="quotation_link_admin",
            hashed_password="test",
            role="ADMIN",
            department="ADMIN",
            is_active=True,
        )
        self.db.add(self.admin)
        self.db.commit()
        self.db.refresh(self.admin)

        self.app = FastAPI()
        self.app.include_router(waquote_router, prefix="/api/v1")

        def override_db():
            yield self.db

        self.app.dependency_overrides[get_db] = override_db
        self.app.dependency_overrides[get_current_user] = lambda: self.admin
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _lead(self, name, phone, email=None, company=None):
        lead = Lead(
            name=name,
            phone=phone,
            email=email,
            company=company,
            source="MANUAL",
            status="NEW",
        )
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        return lead

    def _quotation(
        self,
        number="CHN/QT/TEST/0001",
        *,
        lead_id=None,
        status="issued",
        customer_name="Original Customer",
        company_name="Original Company",
        phone="9876543210",
        email="original@example.com",
        address="Original Address",
        state="Tamil Nadu",
        state_code="33",
        grand_total=1000.0,
        created_at=None,
    ):
        quotation = Quotation(
            doc_type="quotation",
            doc_number=number,
            status=status,
            payment_status="unpaid",
            lead_id=lead_id,
            customer_name=customer_name,
            company_name=company_name,
            phone=phone,
            email=email,
            address=address,
            state=state,
            state_code=state_code,
            subtotal=grand_total,
            grand_total=grand_total,
            line_items=[],
            created_at=created_at or datetime.utcnow(),
        )
        self.db.add(quotation)
        self.db.commit()
        self.db.refresh(quotation)
        return quotation

    def _matches(self, quotation, search=None):
        params = {}
        if search:
            params["search"] = search
        response = self.client.get(
            f"/api/v1/integrations/waquote/documents/{quotation.id}/lead-matches",
            params=params,
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_match_suggestions_use_mobile_email_and_company(self):
        phone_lead = self._lead("Phone Match", "+91 98765 43210")
        email_lead = self._lead(
            "Email Match", "9000000001", "original@example.com"
        )
        company_lead = self._lead(
            "Company Match", "9000000002", "other@example.com", "Original Company"
        )
        quotation = self._quotation()

        payload = self._matches(quotation)
        suggestions = {item["lead"]["id"]: item for item in payload["suggestions"]}

        self.assertEqual(payload["matchCount"], 3)
        self.assertIsNone(payload["suggestedLeadId"])
        self.assertIn("Mobile number", suggestions[phone_lead.id]["matchReasons"])
        self.assertIn("Email", suggestions[email_lead.id]["matchReasons"])
        self.assertIn("Company name", suggestions[company_lead.id]["matchReasons"])
        self.assertTrue(payload["requiresConfirmation"])

        # No suggestion is applied automatically.
        self.db.refresh(quotation)
        self.assertIsNone(quotation.lead_id)

    def test_single_exact_match_is_suggested_and_searchable(self):
        lead = self._lead(
            "Unique Contact",
            "+91 98765 43210",
            "unique@example.com",
            "Unique Industries",
        )
        quotation = self._quotation()

        payload = self._matches(quotation)
        self.assertEqual(payload["matchCount"], 1)
        self.assertEqual(payload["suggestedLeadId"], lead.id)
        self.assertEqual(payload["suggestions"][0]["lead"]["email"], "unique@example.com")

        search_payload = self._matches(quotation, search="Unique Industries")
        self.assertIn(
            lead.id,
            [item["lead"]["id"] for item in search_payload["suggestions"]],
        )
        self.db.refresh(quotation)
        self.assertIsNone(quotation.lead_id)

    def test_link_updates_relationship_and_safe_snapshot_fields(self):
        lead = self._lead(
            "New CRM Name",
            "+91 98765 43210",
            "new@example.com",
            "New CRM Company",
        )
        quotation = self._quotation()
        original_id = quotation.id
        original_total = quotation.grand_total
        original_status = quotation.status
        original_created_at = quotation.created_at
        lead_count = self.db.query(Lead).count()
        quotation_count = self.db.query(Quotation).count()

        response = self.client.post(
            f"/api/v1/integrations/waquote/documents/{quotation.id}/link-lead",
            json={"lead_id": lead.id},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertFalse(body["alreadyLinked"])
        self.assertEqual(body["lead"]["id"], lead.id)
        self.assertEqual(body["document"]["lead"]["id"], lead.id)

        self.db.refresh(quotation)
        self.db.refresh(lead)
        self.assertEqual(quotation.id, original_id)
        self.assertEqual(quotation.lead_id, lead.id)
        self.assertEqual(quotation.customer_name, "New CRM Name")
        self.assertEqual(quotation.company_name, "New CRM Company")
        self.assertEqual(quotation.phone, "+91 98765 43210")
        self.assertEqual(quotation.email, "new@example.com")
        self.assertEqual(quotation.grand_total, original_total)
        self.assertEqual(quotation.status, original_status)
        self.assertEqual(quotation.created_at, original_created_at)

        # Address was empty on the lead, so the quotation snapshot is preserved.
        self.assertEqual(quotation.address, "Original Address")
        self.assertEqual(quotation.state, "Tamil Nadu")
        self.assertEqual(quotation.state_code, "33")

        self.assertEqual(lead.quotetask_quotation_id, str(quotation.id))
        self.assertEqual(lead.quotetask_quotation_number, quotation.doc_number)
        self.assertEqual(lead.quotetask_quotation_status, "issued")
        self.assertEqual(lead.quotetask_quotation_amount, original_total)
        self.assertIsNotNone(lead.quotetask_synced_at)
        # Linking must not overwrite the lead's own contact fields.
        self.assertEqual(lead.email, "new@example.com")
        self.assertEqual(lead.phone, "+91 98765 43210")

        self.assertEqual(self.db.query(Lead).count(), lead_count)
        self.assertEqual(self.db.query(Quotation).count(), quotation_count)

        activity = (
            self.db.query(LeadActivity)
            .filter(LeadActivity.lead_id == lead.id)
            .order_by(LeadActivity.id.desc())
            .first()
        )
        self.assertIsNotNone(activity)
        self.assertEqual(activity.activity_type, "PROPOSAL_LINKED")
        self.assertIn(quotation.doc_number, activity.description)
        self.assertIn("1,000.00", activity.description)

        audit = (
            self.db.query(AuditLog)
            .filter(AuditLog.action == "QUOTATION_LINKED")
            .order_by(AuditLog.id.desc())
            .first()
        )
        self.assertIsNotNone(audit)
        self.assertEqual(audit.entity_id, str(quotation.id))

    def test_link_is_idempotent_and_rejects_a_different_lead(self):
        first_lead = self._lead("First Lead", "9876543210")
        second_lead = self._lead("Second Lead", "9000000009")
        quotation = self._quotation(lead_id=first_lead.id)

        first = self.client.post(
            f"/api/v1/integrations/waquote/documents/{quotation.id}/link-lead",
            json={"lead_id": first_lead.id},
        )
        self.assertEqual(first.status_code, 200, first.text)
        self.assertTrue(first.json()["alreadyLinked"])
        activity_count = (
            self.db.query(LeadActivity)
            .filter(LeadActivity.lead_id == first_lead.id)
            .count()
        )
        self.assertEqual(activity_count, 0)

        conflict = self.client.post(
            f"/api/v1/integrations/waquote/documents/{quotation.id}/link-lead",
            json={"lead_id": second_lead.id},
        )
        self.assertEqual(conflict.status_code, 409, conflict.text)
        self.db.refresh(quotation)
        self.assertEqual(quotation.lead_id, first_lead.id)

    def test_draft_link_does_not_replace_an_issued_lead_reference(self):
        lead = self._lead("Draft Lead", "9876543210")
        issued = self._quotation("CHN/QT/TEST/ISSUED", lead_id=lead.id)
        lead.quotetask_quotation_id = str(issued.id)
        lead.quotetask_quotation_number = issued.doc_number
        lead.quotetask_quotation_status = "issued"
        lead.quotetask_quotation_amount = issued.grand_total
        self.db.commit()

        draft = self._quotation(
            "CHN/QT/TEST/DRAFT",
            status="draft",
            customer_name="Draft Customer",
        )
        response = self.client.post(
            f"/api/v1/integrations/waquote/documents/{draft.id}/link-lead",
            json={"lead_id": lead.id},
        )
        self.assertEqual(response.status_code, 200, response.text)

        self.db.refresh(lead)
        self.assertEqual(lead.quotetask_quotation_id, str(issued.id))
        self.assertEqual(lead.quotetask_quotation_number, issued.doc_number)
        self.assertEqual(lead.quotetask_quotation_amount, issued.grand_total)


if __name__ == "__main__":
    unittest.main()
