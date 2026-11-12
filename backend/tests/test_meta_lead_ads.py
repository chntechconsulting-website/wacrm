"""Isolated tests for the Facebook & Instagram Lead Ads integration.

Uses an in-memory SQLite database. No live Meta account or production CRM
database is touched. Graph API calls are patched at the service boundary.
"""

import hashlib
import hmac
import json
import os
import sys
import threading
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

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
from integrations.meta.admin import (
    create_oauth_state,
    router as admin_router,
    verify_oauth_state,
)
from integrations.meta.config import MetaConfig
from integrations.meta.crypto import encrypt_token
from integrations.meta.service import (
    MetaGraphError,
    MetaLeadService,
    verify_webhook_signature,
)
from integrations.meta.webhook import router as webhook_router
from models.activity import LeadActivity
from models.employee import Employee
from models.lead import AutoAssignConfig, Lead, LeadAssignment, LeadEnquiry
from models.meta_connection import (
    MetaConnection,
    MetaImportJob,
    MetaLeadEvent,
    MetaLeadForm,
)
from models.meta_page import MetaPage
from models.notification import Notification
from models.user import User
from services.auth import get_current_user
from utils.timezone import get_ist_now

APP_ID = "test-meta-app-id"
APP_SECRET = "test-meta-app-secret"
VERIFY_TOKEN = "test-meta-verify-token"


def sample_lead_payload(
    leadgen_id="leadgen-1001",
    platform="fb",
    created_time=None,
    email="ravi@example.com",
):
    created = created_time or (datetime.utcnow() - timedelta(minutes=30))
    return {
        "id": leadgen_id,
        "created_time": created.strftime("%Y-%m-%dT%H:%M:%S+0000"),
        "field_data": [
            {"name": "full_name", "values": ["Ravi Sharma"]},
            {"name": "phone_number", "values": ["9876500011"]},
            {"name": "email", "values": [email]},
            {"name": "city", "values": ["Mumbai"]},
            {"name": "What is your budget?", "values": ["50k"]},
        ],
        "form_id": "form-1001",
        "platform": platform,
        "campaign_id": "camp-1001",
        "campaign_name": "Diwali Campaign",
        "adset_id": "adset-1001",
        "adset_name": "Mumbai Audience",
        "ad_id": "ad-1001",
        "ad_name": "Creative 1",
    }


class MetaLeadAdsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.Session = sessionmaker(bind=cls.engine, autoflush=False, autocommit=False)
        MetaLeadService.SESSION_FACTORY = cls.Session

        cls.env_patcher = patch.dict(
            os.environ,
            {
                "META_APP_ID": APP_ID,
                "META_APP_SECRET": APP_SECRET,
                "META_VERIFY_TOKEN": VERIFY_TOKEN,
                "META_API_VERSION": "v26.0",
                "META_ACCESS_TOKEN": "",
                "META_PAGE_ID": "",
                "PUBLIC_BASE_URL": "http://localhost:5173",
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
        cls.app.include_router(admin_router, prefix="/api")
        cls.app.dependency_overrides[get_db] = override_db
        cls.app.dependency_overrides[get_current_user] = lambda: cls.current_user
        cls.client = TestClient(cls.app)

    @classmethod
    def tearDownClass(cls):
        MetaLeadService.SESSION_FACTORY = None
        cls.env_patcher.stop()

    def setUp(self):
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self._seed_crm()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _seed_crm(self):
        db = self.Session()
        try:
            user = User(
                username="admin",
                hashed_password="not-used",
                role="ADMIN",
                department="SALES",
                is_active=True,
            )
            db.add(user)
            db.flush()
            employee = Employee(
                user_id=user.id,
                name="Sales One",
                email="sales1@example.com",
                username="sales1",
                role="EMPLOYEE",
                department="SALES",
                status="ACTIVE",
            )
            db.add(employee)
            db.add(
                AutoAssignConfig(
                    id=1,
                    enabled=True,
                    waiting_time_minutes=60,
                    assignment_method="LEAST_ASSIGNED",
                    eligible_roles="EMPLOYEE,MANAGER",
                    working_hours_enabled=False,
                )
            )
            page = MetaPage(
                page_id="page-1001",
                page_name="CHN India",
                encrypted_access_token=encrypt_token("page-token"),
                status="CONNECTED",
                lead_count=0,
                is_selected=True,
                auto_sync_enabled=True,
                webhook_subscribed=True,
            )
            db.add(page)
            db.flush()
            db.add(
                MetaLeadForm(
                    form_id="form-1001",
                    page_id=page.page_id,
                    page_db_id=page.id,
                    name="Diwali Offer Form",
                    status="ACTIVE",
                    is_selected=True,
                )
            )
            db.commit()
        finally:
            db.close()

    def db(self):
        return self.Session()

    @staticmethod
    def sign(raw: bytes, secret=APP_SECRET):
        return "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()

    def webhook_payload(self, leadgen_id="leadgen-1001", form_id="form-1001"):
        return {
            "object": "page",
            "entry": [
                {
                    "id": "page-1001",
                    "time": 1762000000,
                    "changes": [
                        {
                            "field": "leadgen",
                            "value": {
                                "leadgen_id": leadgen_id,
                                "form_id": form_id,
                                "page_id": "page-1001",
                                "created_time": 1762000000,
                            },
                        }
                    ],
                }
            ],
        }

    def post_webhook(self, payload, signature=None, secret=APP_SECRET):
        raw = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "X-Hub-Signature-256": (
                signature if signature is not None else self.sign(raw, secret)
            ),
        }
        return self.client.post(
            "/api/integrations/meta/webhook", content=raw, headers=headers
        )

    # ------------------------------------------------------------------
    # OAuth state / signature
    # ------------------------------------------------------------------
    def test_oauth_state_round_trip_and_tamper(self):
        user = SimpleNamespace(id=7, username="admin")
        state = create_oauth_state(
            user,
            "http://localhost:8000/api/integrations/meta/oauth/callback",
            "http://localhost:5173/settings/integrations/meta",
        )
        parsed = verify_oauth_state(state)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["uid"], 7)

        tampered = state[:-1] + ("0" if state[-1] != "0" else "1")
        self.assertIsNone(verify_oauth_state(tampered))

    def test_oauth_state_expiry(self):
        user = SimpleNamespace(id=7, username="admin")
        with patch("integrations.meta.admin.time.time", return_value=1000):
            state = create_oauth_state(
                user, "http://localhost/cb", "http://localhost/front"
            )
        with patch("integrations.meta.admin.time.time", return_value=1000 + 601):
            self.assertIsNone(verify_oauth_state(state))

    def test_webhook_signature_validation(self):
        raw = b'{"object":"page"}'
        self.assertTrue(verify_webhook_signature(raw, self.sign(raw)))
        self.assertFalse(verify_webhook_signature(raw, self.sign(raw, "wrong")))
        self.assertFalse(verify_webhook_signature(raw, None))

    # ------------------------------------------------------------------
    # Webhook lead creation
    # ------------------------------------------------------------------
    @patch.object(
        MetaLeadService,
        "fetch_lead_details",
        return_value=sample_lead_payload(),
    )
    def test_webhook_creates_lead_with_attribution_and_assignment(self, _fetch):
        response = self.post_webhook(self.webhook_payload())
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["processed"], 1)

        db = self.db()
        try:
            lead = db.query(Lead).filter(Lead.meta_lead_id == "leadgen-1001").one()
            self.assertEqual(lead.source, "META")
            self.assertEqual(lead.name, "Ravi Sharma")
            self.assertEqual(lead.phone, "9876500011")
            self.assertEqual(lead.city, "Mumbai")
            self.assertEqual(lead.meta_page_id, "page-1001")
            self.assertEqual(lead.meta_page_name, "CHN India")
            self.assertEqual(lead.meta_form_id, "form-1001")
            self.assertEqual(lead.meta_form_name, "Diwali Offer Form")
            self.assertEqual(lead.meta_campaign_id, "camp-1001")
            self.assertEqual(lead.meta_adset_id, "adset-1001")
            self.assertEqual(lead.meta_ad_id, "ad-1001")
            self.assertEqual(lead.meta_platform, "facebook")
            self.assertIn("What is your budget?", lead.meta_custom_answers or "")
            self.assertIsNotNone(lead.assigned_to)
            self.assertTrue(
                db.query(Notification)
                .filter(Notification.user_id == 1)
                .count()
                >= 1
            )
            event = db.query(MetaLeadEvent).one()
            self.assertEqual(event.status, "PROCESSED")
            self.assertEqual(event.lead_id, lead.id)
        finally:
            db.close()

    @patch.object(
        MetaLeadService,
        "fetch_lead_details",
        return_value=sample_lead_payload(platform="ig"),
    )
    def test_instagram_lead_uses_instagram_source(self, _fetch):
        response = self.post_webhook(self.webhook_payload("leadgen-ig"))
        self.assertEqual(response.status_code, 200, response.text)
        db = self.db()
        try:
            lead = db.query(Lead).filter(Lead.meta_lead_id == "leadgen-ig").one()
            self.assertEqual(lead.source, "INSTAGRAM")
            self.assertEqual(lead.meta_platform, "instagram")
        finally:
            db.close()

    @patch.object(
        MetaLeadService,
        "fetch_lead_details",
        return_value=sample_lead_payload(),
    )
    def test_duplicate_webhook_does_not_create_second_lead(self, _fetch):
        first = self.post_webhook(self.webhook_payload())
        second = self.post_webhook(self.webhook_payload())
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["duplicates"], 1)
        db = self.db()
        try:
            self.assertEqual(db.query(Lead).count(), 1)
            self.assertEqual(db.query(MetaLeadEvent).count(), 1)
        finally:
            db.close()

    def test_invalid_signature_is_rejected(self):
        response = self.post_webhook(self.webhook_payload(), signature="sha256=bad")
        self.assertEqual(response.status_code, 403)
        db = self.db()
        try:
            self.assertEqual(db.query(Lead).count(), 0)
            self.assertEqual(db.query(MetaLeadEvent).count(), 0)
        finally:
            db.close()

    @patch.object(
        MetaLeadService,
        "fetch_lead_details",
        return_value=sample_lead_payload(),
    )
    def test_unselected_form_is_ignored(self, _fetch):
        db = self.db()
        try:
            form = db.query(MetaLeadForm).one()
            form.is_selected = False
            db.commit()
        finally:
            db.close()

        response = self.post_webhook(self.webhook_payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ignored"], 1)
        db = self.db()
        try:
            self.assertEqual(db.query(Lead).count(), 0)
            self.assertEqual(db.query(MetaLeadEvent).one().status, "IGNORED")
        finally:
            db.close()

    @patch.object(
        MetaLeadService,
        "fetch_lead_details",
        return_value=sample_lead_payload(),
    )
    def test_disabled_page_auto_sync_is_ignored(self, _fetch):
        db = self.db()
        try:
            page = db.query(MetaPage).one()
            page.auto_sync_enabled = False
            db.commit()
        finally:
            db.close()

        response = self.post_webhook(self.webhook_payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ignored"], 1)
        db = self.db()
        try:
            self.assertEqual(db.query(Lead).count(), 0)
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Retry
    # ------------------------------------------------------------------
    @patch.object(
        MetaLeadService,
        "fetch_lead_details",
        side_effect=MetaGraphError("Network unavailable", code="NETWORK"),
    )
    def test_failed_fetch_is_queued_and_can_be_retried(self, _fetch):
        response = self.post_webhook(self.webhook_payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["failed"], 1)
        db = self.db()
        try:
            event = db.query(MetaLeadEvent).one()
            self.assertEqual(event.status, "RETRYING")
            self.assertIsNotNone(event.next_retry_at)
            event_id = event.id
        finally:
            db.close()

        with patch.object(
            MetaLeadService,
            "fetch_lead_details",
            return_value=sample_lead_payload(),
        ):
            db = self.db()
            try:
                ok, message = MetaLeadService.retry_event(db, event_id)
                self.assertTrue(ok, message)
                self.assertEqual(db.query(Lead).count(), 1)
                self.assertEqual(db.query(MetaLeadEvent).one().status, "PROCESSED")
            finally:
                db.close()

    # ------------------------------------------------------------------
    # Historical import
    # ------------------------------------------------------------------
    def test_historical_import_and_dedupe(self):
        leads = [
            sample_lead_payload("import-1", created_time=datetime.utcnow() - timedelta(hours=2)),
            sample_lead_payload("import-2", created_time=datetime.utcnow() - timedelta(hours=3)),
        ]
        # Distinct people so the re-inquiry engine does not merge the two
        # imported Meta leads into one CRM lead.
        leads[0]["field_data"][1]["values"] = ["9876500101"]
        leads[0]["field_data"][2]["values"] = ["import1@example.com"]
        leads[1]["field_data"][1]["values"] = ["9876500102"]
        leads[1]["field_data"][2]["values"] = ["import2@example.com"]
        with patch.object(
            MetaLeadService, "_graph_paginate", return_value=leads
        ) as paginate:
            db = self.db()
            try:
                job = MetaLeadService.create_import_job(
                    db,
                    user_id=1,
                    preset="24H",
                    page_ids=["page-1001"],
                    form_ids=["form-1001"],
                )
                job_id = job.id
            finally:
                db.close()

            MetaLeadService.run_import_job_sync(job_id)
            self.assertTrue(paginate.called)

        db = self.db()
        try:
            job = db.query(MetaImportJob).filter(MetaImportJob.id == job_id).one()
            self.assertIn(job.status, {"COMPLETED", "PARTIAL"})
            self.assertEqual(job.imported, 2)
            self.assertEqual(job.duplicates, 0)
            self.assertEqual(db.query(Lead).count(), 2)
        finally:
            db.close()

        # Re-running must only create duplicates, never new leads.
        with patch.object(
            MetaLeadService, "_graph_paginate", return_value=leads
        ):
            MetaLeadService.run_import_job_sync(job_id)
        db = self.db()
        try:
            self.assertEqual(db.query(Lead).count(), 2)
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Forms / dashboard admin API
    # ------------------------------------------------------------------
    def test_form_selection_endpoint(self):
        response = self.client.post(
            "/api/integrations/meta/forms/selection",
            json={"form_ids": ["form-1001"], "selected": False},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["updated"], 1)
        db = self.db()
        try:
            self.assertFalse(db.query(MetaLeadForm).one().is_selected)
        finally:
            db.close()

    @patch.object(
        MetaLeadService,
        "fetch_lead_details",
        return_value=sample_lead_payload(),
    )
    def test_dashboard_reports_counts(self, _fetch):
        self.post_webhook(self.webhook_payload())
        response = self.client.get("/api/integrations/meta/dashboard")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["stats"]["total_pages"], 1)
        self.assertEqual(data["stats"]["total_forms"], 1)
        self.assertGreaterEqual(data["stats"]["total_leads"], 1)
        self.assertEqual(data["webhook_status"], "ACTIVE")

    def test_parse_field_data_custom_answers(self):
        parsed = MetaLeadService.parse_field_data(sample_lead_payload())
        self.assertEqual(parsed["name"], "Ravi Sharma")
        self.assertEqual(parsed["phone"], "9876500011")
        self.assertEqual(parsed["city"], "Mumbai")
        self.assertEqual(
            parsed["custom_answers"].get("What is your budget?"), "50k"
        )

    # ------------------------------------------------------------------
    # OAuth connection / settings / security
    # ------------------------------------------------------------------
    def test_oauth_start_and_callback_connect_flow(self):
        backend_cb = "http://localhost:8000/api/integrations/meta/oauth/callback"
        frontend_cb = "http://localhost:5173/settings/integrations/meta"
        with patch.object(
            MetaConfig, "get_oauth_redirect_uri", return_value=backend_cb
        ), patch.object(
            MetaConfig, "get_frontend_redirect_uri", return_value=frontend_cb
        ):
            start = self.client.get("/api/integrations/meta/oauth/start")
            self.assertEqual(start.status_code, 200, start.text)
            start_data = start.json()
            self.assertIn("facebook.com", start_data["authorize_url"])
            self.assertIn("state=", start_data["authorize_url"])
            self.assertIn("leads_retrieval", start_data["authorize_url"])

            state = create_oauth_state(
                SimpleNamespace(id=1, username="admin"), backend_cb, frontend_cb
            )
            token_data = {
                "access_token": "long-lived-user-token",
                "token_expires_at": datetime.utcnow() + timedelta(days=60),
                "token_issued_at": datetime.utcnow(),
                "scopes": ["leads_retrieval", "pages_manage_metadata"],
                "user_id": "fb-user-1",
                "user_name": "CHN Admin",
            }
            with patch.object(
                MetaLeadService,
                "exchange_oauth_code",
                return_value=token_data,
            ), patch.object(
                MetaLeadService,
                "sync_connection_assets",
                return_value={
                    "pages": 1,
                    "forms": 2,
                    "subscribed_pages": 1,
                    "pages_with_errors": 0,
                    "instagram_assets": 0,
                },
            ):
                callback = self.client.get(
                    f"/api/integrations/meta/oauth/callback?code=code-1&state={state}",
                    follow_redirects=False,
                )

        self.assertIn(callback.status_code, (302, 307))
        self.assertIn("meta_oauth=success", callback.headers["location"])
        db = self.db()
        try:
            connection = db.query(MetaConnection).one()
            self.assertEqual(connection.fb_user_id, "fb-user-1")
            self.assertEqual(connection.status, "CONNECTED")
            self.assertNotEqual(
                connection.encrypted_access_token, "long-lived-user-token"
            )
            self.assertIn("leads_retrieval", connection.scopes)
        finally:
            db.close()

    def test_oauth_callback_rejects_tampered_state(self):
        callback = self.client.get(
            "/api/integrations/meta/oauth/callback?code=code-1&state=not-a-valid-state",
            follow_redirects=False,
        )
        self.assertIn(callback.status_code, (302, 307))
        self.assertIn("meta_oauth=error", callback.headers["location"])
        db = self.db()
        try:
            self.assertEqual(db.query(MetaConnection).count(), 0)
        finally:
            db.close()

    def test_connection_auto_sync_and_disconnect(self):
        db = self.db()
        try:
            db.add(
                MetaConnection(
                    fb_user_id="fb-user-settings",
                    fb_user_name="Settings Admin",
                    encrypted_access_token=encrypt_token("user-token"),
                    status="CONNECTED",
                    auto_sync_enabled=True,
                )
            )
            db.commit()
        finally:
            db.close()

        response = self.client.post(
            "/api/integrations/meta/connection/auto-sync", json={"enabled": False}
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["enabled"])

        response = self.client.post("/api/integrations/meta/connection/disconnect")
        self.assertEqual(response.status_code, 200, response.text)
        db = self.db()
        try:
            connection = db.query(MetaConnection).one()
            self.assertEqual(connection.status, "DISCONNECTED")
            self.assertFalse(connection.auto_sync_enabled)
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Asset / form discovery + Sync Now
    # ------------------------------------------------------------------
    def test_sync_now_discovers_pages_instagram_and_forms(self):
        db = self.db()
        try:
            connection = MetaConnection(
                fb_user_id="fb-user-assets",
                fb_user_name="Assets Admin",
                encrypted_access_token=encrypt_token("user-token"),
                status="CONNECTED",
                auto_sync_enabled=True,
            )
            db.add(connection)
            db.flush()
            db.add(
                MetaPage(
                    page_id="page-2002",
                    page_name="Removed Page",
                    encrypted_access_token=encrypt_token("old-page-token"),
                    status="CONNECTED",
                    connection_id=connection.id,
                )
            )
            db.commit()
        finally:
            db.close()

        asset = {
            "id": "page-1001",
            "name": "CHN India",
            "category": "Business",
            "access_token": "page-token-2",
            "picture": {"data": {"url": "https://cdn.example.com/page.png"}},
            "instagram_business_account": {
                "id": "ig-1",
                "username": "chnindia",
            },
        }
        form_payload = {
            "id": "form-1001",
            "name": "Diwali Offer Form",
            "status": "ACTIVE",
            "locale": "en_US",
            "questions": [],
            "leads_count": 3,
        }

        def fake_graph(method, path, params=None, token=None, retries=2, timeout=30.0):
            if method == "POST" and "subscribed_apps" in path:
                return {"success": True}
            if method == "GET" and "leadgen_forms" in path:
                return {"data": [form_payload]}
            raise AssertionError(f"Unexpected Graph call: {method} {path}")

        with patch.object(
            MetaLeadService, "fetch_authorized_assets", return_value=[asset]
        ), patch(
            "integrations.meta.service.MetaLeadService._graph_request",
            side_effect=fake_graph,
        ):
            db = self.db()
            try:
                summary = MetaLeadService.sync_now(db)
            finally:
                db.close()

        self.assertEqual(summary["mode"], "oauth")
        self.assertEqual(summary["pages"], 1)
        self.assertEqual(summary["forms"], 1)
        self.assertEqual(summary["subscribed_pages"], 1)
        self.assertEqual(summary["instagram_assets"], 1)
        self.assertIn("last_sync_at", summary)

        db = self.db()
        try:
            page = db.query(MetaPage).filter(MetaPage.page_id == "page-1001").one()
            self.assertEqual(page.instagram_account_id, "ig-1")
            self.assertEqual(page.instagram_username, "chnindia")
            self.assertTrue(page.webhook_subscribed)
            self.assertEqual(page.page_picture_url, "https://cdn.example.com/page.png")
            removed = db.query(MetaPage).filter(MetaPage.page_id == "page-2002").one()
            self.assertEqual(removed.status, "ACCESS_REMOVED")
            form = db.query(MetaLeadForm).filter(
                MetaLeadForm.form_id == "form-1001"
            ).one()
            self.assertEqual(form.leads_count, 3)
        finally:
            db.close()

    def test_select_all_forms_for_page(self):
        db = self.db()
        try:
            db.add(
                MetaLeadForm(
                    form_id="form-1002",
                    page_id="page-1001",
                    name="Second Form",
                    status="ACTIVE",
                    is_selected=True,
                )
            )
            db.commit()
        finally:
            db.close()

        response = self.client.post(
            "/api/integrations/meta/forms/selection",
            json={
                "page_id": "page-1001",
                "select_all_for_page": True,
                "selected": False,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["updated"], 2)

        db = self.db()
        try:
            self.assertEqual(
                db.query(MetaLeadForm).filter(MetaLeadForm.is_selected.is_(True)).count(),
                0,
            )
        finally:
            db.close()

        response = self.client.post(
            "/api/integrations/meta/forms/selection",
            json={
                "page_id": "page-1001",
                "select_all_for_page": True,
                "selected": True,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        db = self.db()
        try:
            self.assertEqual(
                db.query(MetaLeadForm).filter(MetaLeadForm.is_selected.is_(True)).count(),
                2,
            )
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Failure scenarios
    # ------------------------------------------------------------------
    def test_expired_page_token_queues_event_for_retry(self):
        db = self.db()
        try:
            page = db.query(MetaPage).one()
            page.status = "TOKEN_EXPIRED"
            db.commit()
        finally:
            db.close()

        response = self.post_webhook(self.webhook_payload("leadgen-expired"))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["failed"], 1)

        db = self.db()
        try:
            self.assertEqual(db.query(Lead).count(), 0)
            event = db.query(MetaLeadEvent).one()
            self.assertEqual(event.status, "RETRYING")
            self.assertIn("expired", (event.last_error or "").lower())
        finally:
            db.close()

    @patch.object(
        MetaLeadService,
        "fetch_lead_details",
        side_effect=MetaGraphError("Permission missing", code=10),
    )
    def test_permission_error_marks_page_and_queues_retry(self, _fetch):
        response = self.post_webhook(self.webhook_payload("leadgen-permission"))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["failed"], 1)

        db = self.db()
        try:
            page = db.query(MetaPage).one()
            self.assertEqual(page.status, "ERROR")
            self.assertEqual(page.last_error_code, "PERMISSION_MISSING")
            event = db.query(MetaLeadEvent).one()
            self.assertEqual(event.status, "RETRYING")
        finally:
            db.close()

    def test_page_access_removed_is_ignored(self):
        db = self.db()
        try:
            page = db.query(MetaPage).one()
            page.status = "ACCESS_REMOVED"
            db.commit()
        finally:
            db.close()

        response = self.post_webhook(self.webhook_payload("leadgen-removed"))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["ignored"], 1)
        db = self.db()
        try:
            self.assertEqual(db.query(Lead).count(), 0)
            self.assertEqual(db.query(MetaLeadEvent).one().status, "IGNORED")
        finally:
            db.close()

    def test_graph_rate_limit_is_retried(self):
        class FakeResponse:
            def __init__(self, status_code, payload):
                self.status_code = status_code
                self._payload = payload

            def json(self):
                return self._payload

        responses = [
            FakeResponse(429, {"error": {"message": "Rate limit", "code": 4}}),
            FakeResponse(200, {"ok": True}),
        ]

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def get(self, *args, **kwargs):
                return responses.pop(0)

            def request(self, *args, **kwargs):
                return responses.pop(0)

        with patch("integrations.meta.service.httpx.Client", FakeClient), patch(
            "integrations.meta.service.time.sleep", return_value=None
        ):
            data = MetaLeadService._graph_request("GET", "me", token="token")

        self.assertEqual(data, {"ok": True})
        self.assertEqual(responses, [])

    def test_webhook_fails_closed_without_app_secret(self):
        with patch.object(MetaConfig, "get_app_secret", return_value=""):
            response = self.post_webhook(self.webhook_payload("leadgen-nosecret"))
        self.assertEqual(response.status_code, 503)
        db = self.db()
        try:
            self.assertEqual(db.query(Lead).count(), 0)
            self.assertEqual(db.query(MetaLeadEvent).count(), 0)
        finally:
            db.close()

    def test_meta_created_time_and_lead_time_are_preserved(self):
        fixed_payload = sample_lead_payload(
            "leadgen-time", created_time=datetime(2026, 1, 5, 10, 30)
        )
        with patch.object(
            MetaLeadService, "fetch_lead_details", return_value=fixed_payload
        ):
            response = self.post_webhook(self.webhook_payload("leadgen-time"))
        self.assertEqual(response.status_code, 200, response.text)

        db = self.db()
        try:
            lead = db.query(Lead).filter(Lead.meta_lead_id == "leadgen-time").one()
            expected = datetime(2026, 1, 5, 16, 0, 0)  # 10:30 UTC -> IST
            self.assertEqual(lead.meta_created_at, expected)
            self.assertEqual(lead.created_at, expected)
            enquiry = db.query(LeadEnquiry).filter(
                LeadEnquiry.lead_id == lead.id
            ).one()
            self.assertEqual(enquiry.created_at, expected)
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Security / roles / activity
    # ------------------------------------------------------------------
    def test_tokens_are_never_exposed_to_frontend(self):
        pages_response = self.client.get("/api/integrations/meta/pages")
        dashboard_response = self.client.get("/api/integrations/meta/dashboard")
        self.assertEqual(pages_response.status_code, 200)
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertNotIn("page-token", pages_response.text)
        self.assertNotIn("page-token", dashboard_response.text)
        self.assertNotIn("access_token", pages_response.json()[0])
        self.assertNotIn("encrypted_access_token", dashboard_response.text)

    def test_manager_can_read_but_cannot_change_integration(self):
        original = type(self).current_user
        type(self).current_user = SimpleNamespace(
            id=99, role="MANAGER", username="manager", is_active=True
        )
        try:
            self.assertEqual(
                self.client.get("/api/integrations/meta/dashboard").status_code, 200
            )
            self.assertEqual(
                self.client.post(
                    "/api/integrations/meta/forms/selection",
                    json={"form_ids": ["form-1001"], "selected": False},
                ).status_code,
                403,
            )
            self.assertEqual(
                self.client.post(
                    "/api/integrations/meta/connection/disconnect"
                ).status_code,
                403,
            )
        finally:
            type(self).current_user = original

    @patch.object(
        MetaLeadService,
        "fetch_lead_details",
        return_value=sample_lead_payload("leadgen-activity"),
    )
    def test_activity_log_lists_lead_events(self, _fetch):
        self.post_webhook(self.webhook_payload("leadgen-activity"))
        response = self.client.get("/api/integrations/meta/activity?limit=20")
        self.assertEqual(response.status_code, 200, response.text)
        activity = response.json()["activity"]
        self.assertTrue(
            any(item["source"] == "lead_event" for item in activity), activity
        )

    # ------------------------------------------------------------------
    # Imports run off the request thread
    # ------------------------------------------------------------------
    def test_import_job_runs_in_background_thread(self):
        done = threading.Event()

        def fake_worker(job_id):
            done.set()

        with patch.object(
            MetaLeadService, "run_import_job_sync", side_effect=fake_worker
        ):
            MetaLeadService.start_import_job(12345)
            self.assertTrue(done.wait(2.0))

    @patch.object(MetaLeadService, "start_import_job")
    def test_import_endpoint_queues_background_job(self, starter):
        response = self.client.post(
            "/api/integrations/meta/import", json={"range": "24H"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        job = response.json()["job"]
        self.assertEqual(job["status"], "PENDING")
        starter.assert_called_once_with(job["id"])


if __name__ == "__main__":
    unittest.main()
