"""Isolated tests for Meta Click-to-WhatsApp ad lead capture.

These tests use an in-memory SQLite database and never touch the live CRM
database or the live Meta/WhatsApp accounts.
"""

import hashlib
import hmac
import io
import json
import os
import sys
import unittest
from datetime import datetime
from types import SimpleNamespace

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import openpyxl
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401 - registers every model on Base.metadata
from database import Base, get_db
from integrations.whatsapp_ads.router import router as crm_router
from integrations.whatsapp_ads.webhook import router as webhook_router
from models.activity import LeadActivity
from models.employee import Employee
from models.lead import (
    AutoAssignConfig,
    Lead,
    LeadAssignment,
    LeadEnquiry,
    LeadStatusHistory,
)
from models.user import User
from models.whatsapp import Conversation, WhatsAppMessage
from models.whatsapp_ad_lead import WhatsAppAdAttribution, WhatsAppWebhookEvent
from services.auth import get_current_user
from unittest.mock import patch

APP_SECRET = "test-whatsapp-ad-secret"
VERIFY_TOKEN = "test-whatsapp-ad-verify"


class WhatsAppAdLeadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=cls.engine)
        cls.Session = sessionmaker(bind=cls.engine, autoflush=False, autocommit=False)

        cls.env_patcher = patch.dict(
            os.environ,
            {
                "WHATSAPP_AD_APP_SECRET": APP_SECRET,
                "WHATSAPP_AD_VERIFY_TOKEN": VERIFY_TOKEN,
                "WHATSAPP_AD_MIRROR_INBOX": "true",
                "WHATSAPP_AD_BUSINESS_ACCOUNT_ID": "waba-test-1",
                "WHATSAPP_AD_ACCESS_TOKEN": "",
                "META_MARKETING_ACCESS_TOKEN": "",
            },
            clear=False,
        )
        cls.env_patcher.start()

        def override_db():
            db = cls.Session()
            try:
                yield db
            finally:
                db.close()

        cls.admin = SimpleNamespace(
            id=1, role="ADMIN", username="admin", is_active=True
        )
        cls.current_user = cls.admin
        cls.app = FastAPI()
        cls.app.include_router(webhook_router, prefix="/api")
        cls.app.include_router(webhook_router)
        cls.app.include_router(crm_router, prefix="/api")
        cls.app.dependency_overrides[get_db] = override_db
        cls.app.dependency_overrides[get_current_user] = lambda: cls.current_user
        cls.client = TestClient(cls.app)

    @classmethod
    def tearDownClass(cls):
        cls.env_patcher.stop()

    def setUp(self):
        type(self).current_user = self.admin
        db = self.Session()
        try:
            db.query(WhatsAppWebhookEvent).delete()
            db.query(WhatsAppAdAttribution).delete()
            db.query(LeadActivity).delete()
            db.query(LeadAssignment).delete()
            db.query(LeadStatusHistory).delete()
            db.query(LeadEnquiry).delete()
            db.query(Lead).delete()
            db.query(Employee).delete()
            db.query(User).delete()
            db.query(AutoAssignConfig).delete()
            db.query(WhatsAppMessage).delete()
            db.query(Conversation).delete()
            db.commit()
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def build_payload(
        wamid="wamid.ctwa.1",
        phone="9876543210",
        text="I saw your ad. Please share pricing.",
        ctwa_clid="click-1",
        ad_id="120210000000000001",
        ad_headline="HRMS for growing teams",
        ad_body="Automate HR operations",
        timestamp="1762000000",
        contact_name="Ravi Sharma",
        source_type="ad",
        include_referral=True,
    ):
        message = {
            "from": phone,
            "id": wamid,
            "timestamp": timestamp,
            "type": "text",
            "text": {"body": text},
        }
        if include_referral:
            message["referral"] = {
                "source_url": f"https://fb.me/{ad_id}",
                "source_id": ad_id,
                "source_type": source_type,
                "headline": ad_headline,
                "body": ad_body,
                "media_type": "image",
                "image_url": "https://cdn.example.com/ad.jpg",
                "ctwa_clid": ctwa_clid,
            }
            if ctwa_clid is None:
                message["referral"].pop("ctwa_clid", None)
        return {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba-test-1",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "919999999999",
                                    "phone_number_id": "phone-number-test-1",
                                },
                                "contacts": [
                                    {
                                        "profile": {"name": contact_name},
                                        "wa_id": phone,
                                    }
                                ],
                                "messages": [message],
                            },
                        }
                    ],
                }
            ],
        }

    @staticmethod
    def sign(raw_body: bytes) -> str:
        return "sha256=" + hmac.new(
            APP_SECRET.encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()

    def post_webhook(self, payload, signature=None):
        raw = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        headers["X-Hub-Signature-256"] = (
            signature if signature is not None else self.sign(raw)
        )
        return self.client.post("/api/webhook/whatsapp", content=raw, headers=headers)

    def create_user_and_employee(self, role, username, name, reporting_manager_id=None):
        db = self.Session()
        try:
            user = User(
                username=username,
                hashed_password="not-used",
                role=role,
                department="SALES",
                reporting_manager_id=reporting_manager_id,
                is_active=True,
            )
            db.add(user)
            db.flush()
            employee = Employee(
                user_id=user.id,
                name=name,
                email=f"{username}@example.com",
                username=username,
                role=role,
                department="SALES",
                status="ACTIVE",
            )
            db.add(employee)
            db.commit()
            return user.id, employee.id
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Webhook verification + signature
    # ------------------------------------------------------------------
    def test_webhook_verification_returns_challenge(self):
        response = self.client.get(
            "/api/webhook/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": VERIFY_TOKEN,
                "hub.challenge": "challenge-123",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.text, "challenge-123")

        direct = self.client.get(
            "/webhook/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": VERIFY_TOKEN,
                "hub.challenge": "direct-456",
            },
        )
        self.assertEqual(direct.status_code, 200, direct.text)
        self.assertEqual(direct.text, "direct-456")

        bad = self.client.get(
            "/api/webhook/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong",
                "hub.challenge": "x",
            },
        )
        self.assertEqual(bad.status_code, 403)

    def test_missing_or_invalid_signature_is_rejected(self):
        payload = self.build_payload()
        missing = self.post_webhook(payload, signature="")
        self.assertEqual(missing.status_code, 403)

        invalid = self.post_webhook(payload, signature="sha256=" + ("0" * 64))
        self.assertEqual(invalid.status_code, 403)

        db = self.Session()
        try:
            self.assertEqual(db.query(Lead).count(), 0)
            self.assertEqual(db.query(WhatsAppAdAttribution).count(), 0)
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Lead capture
    # ------------------------------------------------------------------
    def test_referral_message_creates_normal_lead_and_attribution(self):
        response = self.post_webhook(self.build_payload())
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["processed"], 1)

        db = self.Session()
        try:
            lead = db.query(Lead).one()
            self.assertEqual(lead.source, "WHATSAPP_ADS")
            self.assertEqual(lead.name, "Ravi Sharma")
            self.assertEqual(lead.phone, "9876543210")
            self.assertEqual(lead.whatsapp_number, "9876543210")
            self.assertIn("share pricing", lead.requirement_notes)
            self.assertEqual(lead.total_enquiries, 1)
            self.assertFalse(lead.is_reinquiry)

            attribution = db.query(WhatsAppAdAttribution).one()
            self.assertEqual(attribution.lead_id, lead.id)
            self.assertEqual(attribution.source_id, "120210000000000001")
            self.assertEqual(attribution.ctwa_clid, "click-1")
            self.assertEqual(attribution.source_type, "ad")
            self.assertEqual(attribution.channel, "WHATSAPP")
            self.assertEqual(attribution.business_account_id, "waba-test-1")
            self.assertEqual(attribution.phone_number_id, "phone-number-test-1")
            self.assertEqual(attribution.headline, "HRMS for growing teams")
            self.assertEqual(attribution.ad_body, "Automate HR operations")
            self.assertEqual(attribution.resolution_status, "PENDING")
            self.assertEqual(
                attribution.message_timestamp.date().isoformat(), "2025-11-01"
            )
            self.assertIn("hrms", attribution.raw_referral.lower())

            event = db.query(WhatsAppWebhookEvent).one()
            self.assertEqual(event.status, "PROCESSED")
            self.assertEqual(event.lead_id, lead.id)
            self.assertEqual(event.attribution_id, attribution.id)
            self.assertEqual(event.wamid, "wamid.ctwa.1")
        finally:
            db.close()

    def test_duplicate_webhook_delivery_does_not_duplicate_lead(self):
        payload = self.build_payload()
        first = self.post_webhook(payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["processed"], 1)

        second = self.post_webhook(payload)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["duplicates"], 1)

        db = self.Session()
        try:
            self.assertEqual(db.query(Lead).count(), 1)
            self.assertEqual(db.query(WhatsAppAdAttribution).count(), 1)
            self.assertEqual(db.query(WhatsAppWebhookEvent).count(), 1)
            self.assertEqual(db.query(LeadEnquiry).count(), 1)
        finally:
            db.close()

    def test_duplicate_ctwa_click_with_new_wamid_is_ignored(self):
        self.post_webhook(self.build_payload(wamid="wamid.first", ctwa_clid="same-click"))
        second = self.post_webhook(
            self.build_payload(wamid="wamid.second", ctwa_clid="same-click")
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["duplicates"], 1)

        db = self.Session()
        try:
            self.assertEqual(db.query(Lead).count(), 1)
            self.assertEqual(db.query(WhatsAppAdAttribution).count(), 1)
            duplicate_event = (
                db.query(WhatsAppWebhookEvent)
                .filter(WhatsAppWebhookEvent.status == "SKIPPED_DUPLICATE")
                .one()
            )
            self.assertEqual(duplicate_event.wamid, "wamid.second")
        finally:
            db.close()

    def test_same_phone_new_ad_click_is_reinquiry_not_new_lead(self):
        first = self.post_webhook(
            self.build_payload(wamid="wamid.one", ctwa_clid="click-one", ad_id="ad-one")
        )
        self.assertEqual(first.status_code, 200)

        second = self.post_webhook(
            self.build_payload(
                wamid="wamid.two",
                ctwa_clid="click-two",
                ad_id="ad-two",
                text="Actually, I need the WhatsApp API too.",
                timestamp="1762003600",
            )
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["processed"], 1)

        db = self.Session()
        try:
            self.assertEqual(db.query(Lead).count(), 1)
            lead = db.query(Lead).one()
            self.assertTrue(lead.is_reinquiry)
            self.assertEqual(lead.reinquiry_count, 1)
            self.assertEqual(lead.total_enquiries, 2)
            self.assertEqual(lead.latest_source, "WHATSAPP_ADS")
            self.assertIn("WHATSAPP_ADS", lead.previous_sources)
            self.assertEqual(db.query(WhatsAppAdAttribution).count(), 2)
            self.assertEqual(db.query(LeadEnquiry).count(), 2)
        finally:
            db.close()

    def test_existing_manual_lead_is_reused_and_source_preserved(self):
        db = self.Session()
        try:
            existing = Lead(
                name="Existing Customer",
                phone="9876543210",
                source="MANUAL",
                status="CONTACTED",
                total_enquiries=1,
                previous_sources="MANUAL",
                latest_source="MANUAL",
            )
            db.add(existing)
            db.commit()
        finally:
            db.close()

        response = self.post_webhook(self.build_payload())
        self.assertEqual(response.status_code, 200)

        db = self.Session()
        try:
            self.assertEqual(db.query(Lead).count(), 1)
            lead = db.query(Lead).one()
            self.assertEqual(lead.source, "MANUAL")
            self.assertEqual(lead.latest_source, "WHATSAPP_ADS")
            self.assertTrue(lead.is_reinquiry)
            attribution = db.query(WhatsAppAdAttribution).one()
            self.assertEqual(attribution.lead_id, lead.id)
        finally:
            db.close()

    def test_status_only_webhook_creates_no_lead(self):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba-test-1",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "metadata": {"phone_number_id": "phone-number-test-1"},
                                "statuses": [
                                    {
                                        "id": "wamid.outbound.1",
                                        "status": "delivered",
                                        "timestamp": "1762000000",
                                        "recipient_id": "9876543210",
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }
        response = self.post_webhook(payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status_updates"], 1)

        db = self.Session()
        try:
            self.assertEqual(db.query(Lead).count(), 0)
            self.assertEqual(db.query(WhatsAppAdAttribution).count(), 0)
            self.assertEqual(db.query(WhatsAppWebhookEvent).count(), 0)
        finally:
            db.close()

    def test_message_without_referral_creates_no_lead(self):
        response = self.post_webhook(self.build_payload(include_referral=False))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["skipped"], 1)

        db = self.Session()
        try:
            self.assertEqual(db.query(Lead).count(), 0)
            self.assertEqual(db.query(WhatsAppAdAttribution).count(), 0)
        finally:
            db.close()

    def test_missing_ctwa_clid_still_creates_lead(self):
        response = self.post_webhook(
            self.build_payload(
                wamid="wamid.status-placement",
                ctwa_clid=None,
                source_type="status",
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["processed"], 1)

        db = self.Session()
        try:
            lead = db.query(Lead).one()
            attribution = db.query(WhatsAppAdAttribution).one()
            self.assertEqual(attribution.lead_id, lead.id)
            self.assertIsNone(attribution.ctwa_clid)
            self.assertEqual(attribution.source_type, "status")
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Assignment
    # ------------------------------------------------------------------
    def test_ctwa_lead_uses_existing_assignment_configuration(self):
        _, employee_id = self.create_user_and_employee(
            "SALES_EXECUTIVE", "exec.assign", "Assignment Executive"
        )
        db = self.Session()
        try:
            db.add(
                AutoAssignConfig(
                    id=1,
                    enabled=True,
                    waiting_time_minutes=60,
                    assignment_method="LEAST_ASSIGNED",
                    eligible_roles="SALES_EXECUTIVE",
                    working_hours_enabled=False,
                    working_hours_start="09:00",
                    working_hours_end="18:00",
                )
            )
            db.commit()
        finally:
            db.close()

        response = self.post_webhook(self.build_payload())
        self.assertEqual(response.status_code, 200)

        db = self.Session()
        try:
            lead = db.query(Lead).one()
            self.assertEqual(lead.assigned_to, employee_id)
            self.assertEqual(lead.status, "ASSIGNED")
            self.assertEqual(db.query(LeadAssignment).count(), 1)
            self.assertTrue(
                db.query(LeadAssignment).one().assignment_method == "AUTOMATIC"
            )
        finally:
            db.close()

    # ------------------------------------------------------------------
    # CRM listing, detail and export
    # ------------------------------------------------------------------
    def _seed_listing_records(self):
        manager_user_id, manager_emp_id = self.create_user_and_employee(
            "SALES_MANAGER", "manager.scope", "Scope Manager"
        )
        exec1_user_id, exec1_emp_id = self.create_user_and_employee(
            "SALES_EXECUTIVE",
            "exec.scope.one",
            "Scope Executive One",
            reporting_manager_id=manager_user_id,
        )
        exec2_user_id, exec2_emp_id = self.create_user_and_employee(
            "SALES_EXECUTIVE",
            "exec.scope.two",
            "Scope Executive Two",
            reporting_manager_id=manager_user_id,
        )

        db = self.Session()
        try:
            lead1 = Lead(
                name="Ad Lead One",
                phone="9000000001",
                source="WHATSAPP_ADS",
                status="ASSIGNED",
                assigned_to=exec1_emp_id,
                total_enquiries=1,
            )
            lead2 = Lead(
                name="Ad Lead Two",
                phone="9000000002",
                source="WHATSAPP_ADS",
                status="ASSIGNED",
                assigned_to=exec2_emp_id,
                total_enquiries=1,
            )
            db.add_all([lead1, lead2])
            db.flush()
            db.add_all(
                [
                    WhatsAppAdAttribution(
                        lead_id=lead1.id,
                        phone=lead1.phone,
                        contact_name=lead1.name,
                        message_text="Campaign A enquiry",
                        source_id="ad-a",
                        source_type="ad",
                        ctwa_clid="scope-click-a",
                        campaign_id="campaign-a",
                        campaign_name="Campaign A",
                        ad_name="Ad A",
                        resolution_status="RESOLVED",
                    ),
                    WhatsAppAdAttribution(
                        lead_id=lead2.id,
                        phone=lead2.phone,
                        contact_name=lead2.name,
                        message_text="Campaign B enquiry",
                        source_id="ad-b",
                        source_type="ad",
                        ctwa_clid="scope-click-b",
                        campaign_id="campaign-b",
                        campaign_name="Campaign B",
                        ad_name="Ad B",
                        resolution_status="RESOLVED",
                    ),
                ]
            )
            db.commit()

            manager = db.query(User).filter(User.id == manager_user_id).one()
            exec1 = db.query(User).filter(User.id == exec1_user_id).one()
            exec2 = db.query(User).filter(User.id == exec2_user_id).one()
            return lead1.id, manager, exec1, exec2
        finally:
            db.close()

    def test_listing_respects_admin_manager_and_own_scope(self):
        lead1_id, manager, exec1, exec2 = self._seed_listing_records()

        self.current_user = self.admin
        type(self).current_user = self.admin
        admin_res = self.client.get("/api/whatsapp-ad-leads")
        self.assertEqual(admin_res.status_code, 200, admin_res.text)
        self.assertEqual(admin_res.json()["total"], 2)

        self.current_user = manager
        type(self).current_user = manager
        manager_res = self.client.get("/api/whatsapp-ad-leads")
        self.assertEqual(manager_res.status_code, 200, manager_res.text)
        self.assertEqual(manager_res.json()["total"], 2)

        self.current_user = exec1
        type(self).current_user = exec1
        exec_res = self.client.get("/api/whatsapp-ad-leads")
        self.assertEqual(exec_res.status_code, 200, exec_res.text)
        body = exec_res.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["items"][0]["lead_id"], lead1_id)
        self.assertEqual(body["items"][0]["source_label"], "WhatsApp Ads")

        # Executive 2 sees only their own row too.
        self.current_user = exec2
        type(self).current_user = exec2
        exec2_res = self.client.get("/api/whatsapp-ad-leads")
        self.assertEqual(exec2_res.json()["total"], 1)

        # Filters work inside the scoped list.
        self.current_user = self.admin
        type(self).current_user = self.admin
        filtered = self.client.get(
            "/api/whatsapp-ad-leads", params={"campaign": "campaign-a"}
        )
        self.assertEqual(filtered.json()["total"], 1)
        searched = self.client.get(
            "/api/whatsapp-ad-leads", params={"search": "Campaign B"}
        )
        self.assertEqual(searched.json()["total"], 1)

        # Summary and filter options are scoped to the same visible rows.
        summary = self.client.get("/api/whatsapp-ad-leads/summary")
        self.assertEqual(summary.status_code, 200, summary.text)
        self.assertEqual(summary.json()["campaigns"], 2)

        options = self.client.get("/api/whatsapp-ad-leads/filter-options")
        self.assertEqual(options.status_code, 200, options.text)
        option_body = options.json()
        self.assertEqual(
            {item["name"] for item in option_body["campaigns"]},
            {"Campaign A", "Campaign B"},
        )
        self.assertEqual(
            {item["name"] for item in option_body["employees"]},
            {"Scope Executive One", "Scope Executive Two"},
        )

        # An executive's options contain only their own assignment/campaign.
        self.current_user = exec1
        type(self).current_user = exec1
        exec_options = self.client.get("/api/whatsapp-ad-leads/filter-options")
        self.assertEqual(exec_options.status_code, 200, exec_options.text)
        exec_option_body = exec_options.json()
        self.assertEqual(
            [item["name"] for item in exec_option_body["campaigns"]],
            ["Campaign A"],
        )
        self.assertEqual(
            [item["name"] for item in exec_option_body["employees"]],
            ["Scope Executive One"],
        )
        exec_summary = self.client.get("/api/whatsapp-ad-leads/summary")
        self.assertEqual(exec_summary.json()["campaigns"], 1)

    def test_meta_instant_form_leads_are_isolation_safe(self):
        db = self.Session()
        try:
            db.add(
                Lead(
                    name="Instant Form Lead",
                    phone="9111111111",
                    source="META",
                    meta_lead_id="meta-form-lead-1",
                    meta_form_id="form-1",
                )
            )
            db.commit()
        finally:
            db.close()

        response = self.client.get("/api/whatsapp-ad-leads")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 0)

    def test_detail_and_excel_export(self):
        self.post_webhook(self.build_payload())
        db = self.Session()
        try:
            attribution_id = db.query(WhatsAppAdAttribution.id).scalar()
        finally:
            db.close()

        detail = self.client.get(f"/api/whatsapp-ad-leads/{attribution_id}")
        self.assertEqual(detail.status_code, 200, detail.text)
        body = detail.json()
        self.assertEqual(body["customer_name"], "Ravi Sharma")
        self.assertEqual(body["source_id"], "120210000000000001")
        self.assertEqual(body["lead"]["phone"], "9876543210")
        self.assertIsInstance(body["raw_referral"], dict)
        self.assertEqual(body["raw_referral"]["ctwa_clid"], "click-1")

        export = self.client.get("/api/whatsapp-ad-leads/export")
        self.assertEqual(export.status_code, 200, export.text)
        workbook = openpyxl.load_workbook(io.BytesIO(export.content))
        sheet = workbook.active
        headers = [cell.value for cell in sheet[1]]
        self.assertIn("Customer Name", headers)
        self.assertIn("Campaign Name", headers)
        self.assertIn("Ad ID", headers)
        self.assertIn("CTWA Click ID", headers)
        self.assertEqual(sheet.cell(row=2, column=2).value, "Ravi Sharma")
        self.assertEqual(sheet.cell(row=2, column=8).value, "120210000000000001")

        summary = self.client.get("/api/whatsapp-ad-leads/summary")
        self.assertEqual(summary.status_code, 200, summary.text)
        self.assertEqual(summary.json()["total"], 1)
        self.assertEqual(summary.json()["unassigned"], 1)

        options = self.client.get("/api/whatsapp-ad-leads/filter-options")
        self.assertEqual(options.status_code, 200, options.text)
        self.assertEqual(options.json()["statuses"], ["NEW"])


if __name__ == "__main__":
    unittest.main()
