"""Isolated tests for the WA HRMS Channel Partner read-only integration.

These tests use an in-memory SQLite database and a local mock HTTP/webhook
surface. They never contact WA HRMS, never use production credentials and never
write to the live CRM database.
"""

import hashlib
import hmac
import json
import os
import sys
import time
import unittest
from datetime import datetime
from unittest.mock import patch

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401 - registers every model on Base.metadata
from database import Base
from integrations.wahrms_channel_partner.client import ChannelPartnerAPIError
from integrations.wahrms_channel_partner.config import (
    decrypt_secret,
    effective_webhook_secret,
    encrypt_secret,
    mask_secret,
    save_configuration,
)
from integrations.wahrms_channel_partner.normalizers import (
    extract_list,
    mask_pan,
    sanitise_document_metadata,
    sanitise_payload,
)
from integrations.wahrms_channel_partner.webhook import webhook_router
from models.channel_partner import (
    ChannelPartner,
    ChannelPartnerApplication,
    ChannelPartnerIntegration,
    ChannelPartnerLead,
    ChannelPartnerSyncCheckpoint,
    ChannelPartnerWebhookEvent,
    ChannelPartnerWebhookRejection,
)
from models.lead import Lead
from models.user import User
from schemas.lead import LeadUpdate
from routers.channel_partners import (
    _lead_payload,
    _page_meta,
    require_channel_partner_document_access,
    require_channel_partner_view,
)
from services.channel_partner_sync import (
    CHANNEL_PARTNER_STATUSES,
    CRM_TO_CHANNEL_PARTNER_STATUS,
    ChannelPartnerStatusSyncError,
    _application_values,
    _detail_sections,
    _is_stale,
    apply_event,
    get_checkpoint,
    mark_event,
    poll_events_once,
    process_webhook_event,
    push_channel_partner_status,
    retry_channel_partner_status_sync,
    store_webhook_event,
    sync_channel_partner_leads_to_crm,
    upsert_application,
    upsert_lead,
    upsert_partner,
    validate_channel_partner_status_change,
    validate_channel_partner_transition,
    verify_webhook_signature,
)
from services.permission_catalog import MODULE_KEYS, SYSTEM_MODULES
from services.permission_service import (
    get_default_role_permissions,
    user_has_permission,
)

WEBHOOK_SECRET = "test-wahrms-webhook-secret"


def sign(body: bytes, timestamp: int, secret: str = WEBHOOK_SECRET) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.".encode("utf-8") + body,
        hashlib.sha256,
    ).hexdigest()
    return f"t={timestamp},v1={digest}"


class FakeChannelPartnerConfig:
    configured = True


class FakeChannelPartnerClient:
    """Stand-in for the HTTP client so tests never reach WA HRMS."""

    calls = []
    error = None

    def __init__(self, config):
        self.config = config

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def update_lead(self, lead_id, *, status=None, review_note=None):
        type(self).calls.append(
            {"lead_id": lead_id, "status": status, "review_note": review_note}
        )
        if type(self).error is not None:
            raise type(self).error
        return {"data": {"lead": {"id": lead_id, "status": status}}}


class ChannelPartnerIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=cls.engine)
        cls.Session = sessionmaker(
            bind=cls.engine, autoflush=False, autocommit=False
        )

    def setUp(self):
        self.db = self.Session()
        for model in (
            ChannelPartnerWebhookRejection,
            ChannelPartnerWebhookEvent,
            ChannelPartnerApplication,
            ChannelPartnerLead,
            ChannelPartner,
            ChannelPartnerSyncCheckpoint,
            ChannelPartnerIntegration,
            Lead,
        ):
            self.db.query(model).delete()
        self.db.commit()

    def tearDown(self):
        self.db.close()

    # ------------------------------------------------------------------
    # Signature verification
    # ------------------------------------------------------------------
    def test_valid_webhook_signature(self):
        body = b'{"id":"evt_1","type":"ping","data":{}}'
        timestamp = int(time.time())
        ok, reason = verify_webhook_signature(
            body, sign(body, timestamp), WEBHOOK_SECRET
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")

    def test_stale_webhook_timestamp_is_rejected(self):
        body = b'{"id":"evt_1","type":"ping"}'
        timestamp = int(time.time()) - 600
        ok, reason = verify_webhook_signature(
            body, sign(body, timestamp), WEBHOOK_SECRET
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "timestamp_out_of_tolerance")

    def test_tampered_webhook_body_is_rejected(self):
        timestamp = int(time.time())
        signed_body = b'{"id":"evt_1","type":"ping"}'
        tampered_body = b'{"id":"evt_1","type":"partner.created"}'
        ok, reason = verify_webhook_signature(
            tampered_body, sign(signed_body, timestamp), WEBHOOK_SECRET
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "signature_mismatch")

    def test_missing_webhook_secret_is_rejected(self):
        ok, reason = verify_webhook_signature(b"{}", "t=1,v1=abc", "")
        self.assertFalse(ok)
        self.assertEqual(reason, "webhook_secret_not_configured")

    # ------------------------------------------------------------------
    # Sanitisation and masking
    # ------------------------------------------------------------------
    def test_pan_and_bank_details_are_never_exposed(self):
        payload = {
            "businessName": "Acme Partners",
            "pan": "ABCDE1234F",
            "bankAccountNumber": "123456789012",
            "ifsc": "HDFC0001234",
            "apiKey": "super-secret-key",
            "documents": {
                "pan": {
                    "filename": "pan.pdf",
                    "url": "https://storage.example.com/pan.pdf?token=abc",
                }
            },
        }
        sanitised = sanitise_payload(payload)
        self.assertEqual(sanitised["businessName"], "Acme Partners")
        self.assertEqual(sanitised["pan"], "••••••234F")
        self.assertNotIn("123456789012", json.dumps(sanitised))
        self.assertNotIn("HDFC0001234", json.dumps(sanitised))
        self.assertNotIn("super-secret-key", json.dumps(sanitised))
        self.assertNotIn("storage.example.com", json.dumps(sanitised))
        self.assertEqual(sanitised["documents"]["pan"]["filename"], "pan.pdf")

    def test_pan_mask_and_secret_mask(self):
        self.assertEqual(mask_pan("ABCDE1234F"), "••••••234F")
        masked = mask_secret("abcdef123456")
        self.assertTrue(masked.endswith("3456"))
        self.assertNotIn("abcdef", masked)

    def test_settings_secret_round_trip(self):
        ciphertext = encrypt_secret("read-only-api-key")
        self.assertNotIn("read-only-api-key", ciphertext)
        self.assertEqual(decrypt_secret(ciphertext), "read-only-api-key")

    def test_webhook_secret_round_trip_prefers_database(self):
        save_configuration(self.db, webhook_secret="whsec_test_secret_1234")
        secret, source = effective_webhook_secret(self.db)
        self.assertEqual(secret, "whsec_test_secret_1234")
        self.assertEqual(source, "database")
        masked = mask_secret(secret)
        self.assertTrue(masked.endswith("1234"))
        self.assertNotIn("whsec_test_secret", masked)

        save_configuration(self.db, clear_webhook_secret=True)
        with patch(
            "integrations.wahrms_channel_partner.config.env_webhook_secret",
            return_value="",
        ):
            secret, source = effective_webhook_secret(self.db)
        self.assertEqual(secret, "")
        self.assertEqual(source, "none")

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------
    def test_partner_upsert_masks_pan_and_sanitises_raw_payload(self):
        raw = {
            "partnerId": "partner-1",
            "name": "Acme Partners",
            "code": "ACME01",
            "email": "partner@example.com",
            "status": "active",
            "commissionRateBps": 1500,
            "pan": "ABCDE1234F",
            "bankAccountNumber": "999888777666",
            "createdAt": "2026-01-02T10:00:00Z",
            "updatedAt": "2026-01-03T10:00:00Z",
        }
        partner = upsert_partner(
            self.db, raw, list_raw=raw, commit=True
        )
        self.assertIsNotNone(partner)
        self.assertEqual(partner.external_id, "partner-1")
        self.assertEqual(partner.status, "active")
        self.assertEqual(partner.pan_masked, "••••••234F")
        self.assertEqual(partner.pan_last4, "234F")
        stored = json.dumps(partner.list_raw)
        self.assertNotIn("ABCDE1234F", stored)
        self.assertNotIn("999888777666", stored)

    def test_application_mapping_keeps_masked_pan_only(self):
        raw = {
            "applicationId": "app-1",
            "businessName": "Beta Consulting",
            "contactName": "Ravi",
            "email": "ravi@example.com",
            "status": "pending",
            "pan": "ZYXWV9876Q",
            "aadhaar": "123412341234",
            "documents": {
                "pan": {
                    "filename": "pan.pdf",
                    "url": "https://storage.example.com/pan.pdf",
                }
            },
        }
        application = upsert_application(self.db, raw, commit=True)
        self.assertIsNotNone(application)
        self.assertEqual(application.business_name, "Beta Consulting")
        self.assertEqual(application.pan_masked, "••••••876Q")
        self.assertEqual(application.pan_last4, "876Q")
        self.assertEqual(application.document_metadata_json["pan"]["filename"], "pan.pdf")
        stored = json.dumps(application.raw_data)
        self.assertNotIn("ZYXWV9876Q", stored)
        self.assertNotIn("123412341234", stored)
        self.assertNotIn("storage.example.com", stored)

    def test_live_application_shape_maps_pan_last4_and_consent_at(self):
        values = _application_values(
            {
                "id": "app-live-1",
                "status": "approved",
                "businessName": "Live Shape Ltd",
                "panLast4": "4321",
                "consentAt": "2026-11-16T07:12:48.516Z",
            }
        )
        self.assertEqual(values["pan_last4"], "4321")
        self.assertTrue(values["pan_present"])
        self.assertTrue(values["consent"])

    def test_live_partner_detail_shape_maps_series_and_documents(self):
        sections = _detail_sections(
            {
                "partner": {"id": "partner-live-1"},
                "series": [
                    {"month": "2026-01", "earnedPaise": 0, "revenuePaise": 0}
                ],
                "application": {
                    "documents": {"pan": None, "aadhaar": None}
                },
            }
        )
        self.assertEqual(len(sections["monthly_commission_series_json"]), 1)
        self.assertIn("pan", sections["application_documents_json"])

    def test_stale_check_tolerates_mysql_second_rounding(self):
        existing = datetime(2026, 1, 1, 12, 0, 0)
        rounded_up = datetime(2026, 1, 1, 11, 59, 59, 837000)
        clearly_older = datetime(2026, 1, 1, 11, 59, 57)
        self.assertFalse(_is_stale(existing, rounded_up))
        self.assertTrue(_is_stale(existing, clearly_older))

    def test_missing_documents_remain_null_instead_of_redacted(self):
        documents = sanitise_document_metadata(
            {
                "pan": None,
                "aadhaar": None,
                "panUrl": "https://storage.example.com/pan.pdf?token=abc",
            }
        )
        self.assertIsNone(documents["pan"])
        self.assertIsNone(documents["aadhaar"])
        self.assertNotIn("storage.example.com", json.dumps(documents))

    # ------------------------------------------------------------------
    # Event ingestion / dedupe
    # ------------------------------------------------------------------
    def test_duplicate_event_id_is_stored_once(self):
        first, duplicate_first = store_webhook_event(
            self.db,
            event_id="evt_duplicate",
            event_type="ping",
            payload={"id": "evt_duplicate", "type": "ping"},
            headers={},
        )
        second, duplicate_second = store_webhook_event(
            self.db,
            event_id="evt_duplicate",
            event_type="ping",
            payload={"id": "evt_duplicate", "type": "ping"},
            headers={},
        )
        self.assertFalse(duplicate_first)
        self.assertTrue(duplicate_second)
        self.assertEqual(first.id, second.id)
        count = (
            self.db.query(ChannelPartnerWebhookEvent)
            .filter(ChannelPartnerWebhookEvent.event_id == "evt_duplicate")
            .count()
        )
        self.assertEqual(count, 1)

    def test_background_processing_applies_partner_event(self):
        event, _ = store_webhook_event(
            self.db,
            event_id="evt_partner_created",
            event_type="partner.created",
            payload={
                "id": "evt_partner_created",
                "type": "partner.created",
                "data": {
                    "partner": {
                        "partnerId": "partner-webhook-1",
                        "name": "Webhook Partner",
                        "status": "active",
                    }
                },
            },
            headers={},
        )
        with patch("services.channel_partner_sync.SessionLocal", self.Session):
            process_webhook_event(event.id)

        refreshed = self.db.get(ChannelPartnerWebhookEvent, event.id)
        self.db.refresh(refreshed)
        self.assertEqual(refreshed.status, "processed")
        partner = (
            self.db.query(ChannelPartner)
            .filter(ChannelPartner.external_id == "partner-webhook-1")
            .first()
        )
        self.assertIsNotNone(partner)
        self.assertEqual(partner.name, "Webhook Partner")

    # ------------------------------------------------------------------
    # Polling checkpoint + duplicate prevention
    # ------------------------------------------------------------------
    def test_poll_events_advances_checkpoint_and_dedupes(self):
        existing, _ = store_webhook_event(
            self.db,
            event_id="evt_existing",
            event_type="ping",
            payload={"id": "evt_existing", "type": "ping"},
            headers={},
            source="poll",
        )
        mark_event(self.db, existing, "processed")

        class FakeClient:
            def __init__(self):
                self.calls = []

            def list_events(self, after=0, limit=500, event_type=None):
                self.calls.append((after, limit))
                return {
                    "events": [
                        {"id": "evt_existing", "type": "ping", "seq": 3},
                        {
                            "id": "evt_new",
                            "type": "ping",
                            "seq": 4,
                            "createdAt": "2026-02-01T10:00:00Z",
                        },
                    ],
                    "nextAfter": 4,
                    "hasMore": False,
                }

        client = FakeClient()
        result = poll_events_once(self.db, client, batch_size=50)

        self.assertEqual(client.calls[0][0], 0)
        self.assertEqual(result["after"], 4)
        self.assertEqual(result["duplicates"], 1)
        self.assertGreaterEqual(result["processed"], 1)

        checkpoint = get_checkpoint(self.db, "events")
        self.assertEqual(int(checkpoint.last_after), 4)
        self.assertIsNotNone(checkpoint.last_success_at)

        ids = {
            row.event_id
            for row in self.db.query(ChannelPartnerWebhookEvent).all()
        }
        self.assertEqual(ids, {"evt_existing", "evt_new"})

        # A second poll at the new checkpoint must not re-create records.
        class EmptyClient:
            def list_events(self, after=0, limit=500, event_type=None):
                self.after = after
                return {"events": [], "nextAfter": after, "hasMore": False}

        empty = EmptyClient()
        poll_events_once(self.db, empty, batch_size=50)
        self.assertEqual(empty.after, 4)

    # ------------------------------------------------------------------
    # Permissions
    # ------------------------------------------------------------------
    def test_channel_partner_permission_module_exists(self):
        self.assertIn("channel_partners", MODULE_KEYS)
        admin_defaults = get_default_role_permissions("ADMIN")
        self.assertTrue(admin_defaults["channel_partners"]["has_access"])
        sales_defaults = get_default_role_permissions("SALES_EXECUTIVE")
        self.assertFalse(sales_defaults["channel_partners"]["has_access"])
        modules = {module["key"] for module in SYSTEM_MODULES}
        self.assertIn("channel_partners", modules)

    def test_view_permission_requires_module_access(self):
        admin = User(username="admin", role="ADMIN", is_active=True)
        sales = User(username="sales", role="SALES_EXECUTIVE", is_active=True)
        self.assertIs(
            require_channel_partner_view(current_user=admin, db=self.db), admin
        )
        with self.assertRaises(HTTPException) as ctx:
            require_channel_partner_view(current_user=sales, db=self.db)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_document_permission_requires_edit_or_approve(self):
        admin = User(username="admin", role="ADMIN", is_active=True)
        sales = User(username="sales", role="SALES_EXECUTIVE", is_active=True)
        self.assertIs(
            require_channel_partner_document_access(
                current_user=admin, db=self.db
            ),
            admin,
        )
        with self.assertRaises(HTTPException) as ctx:
            require_channel_partner_document_access(
                current_user=sales, db=self.db
            )
        self.assertEqual(ctx.exception.status_code, 403)

    # ------------------------------------------------------------------
    # Pagination / envelopes
    # ------------------------------------------------------------------
    def test_pagination_metadata(self):
        meta = _page_meta(total=51, page=3, limit=25)
        self.assertEqual(meta["pages"], 3)
        self.assertFalse(meta["hasNext"])
        self.assertTrue(meta["hasPrev"])
        self.assertEqual(meta["total"], 51)

    def test_response_envelope_extraction(self):
        payload = {"data": {"events": [{"id": "evt_1"}]}, "nextAfter": 1}
        self.assertEqual(extract_list(payload, ["events"]), [{"id": "evt_1"}])
        self.assertEqual(extract_list({"items": [1, 2]}, ["events"]), [1, 2])

    # ------------------------------------------------------------------
    # Webhook endpoint (signature -> store -> dedupe -> background)
    # ------------------------------------------------------------------
    def test_webhook_endpoint_accepts_valid_and_dedupes_duplicate(self):
        app = FastAPI()
        app.include_router(webhook_router)
        client = TestClient(app)
        body = json.dumps(
            {"id": "evt_http_1", "type": "ping", "createdAt": "2026-03-01T10:00:00Z"}
        ).encode("utf-8")

        with patch(
            "integrations.wahrms_channel_partner.webhook.load_webhook_secret",
            return_value=WEBHOOK_SECRET,
        ), patch(
            "integrations.wahrms_channel_partner.webhook.SessionLocal",
            self.Session,
        ), patch(
            "services.channel_partner_sync.SessionLocal",
            self.Session,
        ):
            headers = {
                "Content-Type": "application/json",
                "WAHRMS-Signature": sign(body, int(time.time())),
                "WAHRMS-Event-Id": "evt_http_1",
                "WAHRMS-Event": "ping",
            }
            first = client.post("/webhooks/wahrms", content=body, headers=headers)
            second = client.post("/webhooks/wahrms", content=body, headers=headers)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["status"], "accepted")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["status"], "duplicate")
        count = (
            self.db.query(ChannelPartnerWebhookEvent)
            .filter(ChannelPartnerWebhookEvent.event_id == "evt_http_1")
            .count()
        )
        self.assertEqual(count, 1)

    def test_webhook_endpoint_rejects_bad_signature(self):
        app = FastAPI()
        app.include_router(webhook_router)
        client = TestClient(app)
        body = b'{"id":"evt_http_bad","type":"ping"}'

        with patch(
            "integrations.wahrms_channel_partner.webhook.load_webhook_secret",
            return_value=WEBHOOK_SECRET,
        ), patch(
            "integrations.wahrms_channel_partner.webhook.SessionLocal",
            self.Session,
        ):
            response = client.post(
                "/webhooks/wahrms",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "WAHRMS-Signature": f"t={int(time.time())},v1=deadbeef",
                    "WAHRMS-Event-Id": "evt_http_bad",
                    "WAHRMS-Event": "ping",
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["reason"], "signature_mismatch")
        rejection = self.db.query(ChannelPartnerWebhookRejection).first()
        self.assertIsNotNone(rejection)
        self.assertEqual(rejection.reason, "signature_mismatch")

    # ------------------------------------------------------------------
    # Main CRM All Leads mapping
    # ------------------------------------------------------------------
    def _partner_lead_payload(self, *, status="submitted", **overrides):
        payload = {
            "id": "lead-cp-1",
            "partnerId": "partner-cp-1",
            "partnerName": "Krish",
            "partnerCode": "KRISH385",
            "status": status,
            "companyName": "WACRM",
            "contactName": "Krishneshwaran D",
            "contactEmail": "krish@example.com",
            "contactPhone": "989943213",
            "city": "Coimbatore",
            "notes": "Interested in WA HRMS",
            "leadStage": "new",
            "createdAt": "2026-11-19T06:31:05.051Z",
            "updatedAt": "2026-11-19T06:31:05.051Z",
            "protectedUntil": "2027-02-17T06:31:05.050Z",
        }
        payload.update(overrides)
        return payload

    def test_channel_partner_lead_appears_in_all_leads(self):
        upsert_partner(
            self.db,
            {
                "partnerId": "partner-cp-1",
                "name": "Krish",
                "code": "KRISH385",
                "status": "active",
            },
            commit=True,
        )
        mirrored = upsert_lead(
            self.db, self._partner_lead_payload(), commit=True
        )
        self.assertIsNotNone(mirrored)

        lead = (
            self.db.query(Lead)
            .filter(Lead.channel_partner_lead_id == "lead-cp-1")
            .first()
        )
        self.assertIsNotNone(lead)
        self.assertEqual(lead.source, "CHANNEL_PARTNER")
        self.assertEqual(lead.status, "NEW")
        self.assertEqual(lead.name, "Krishneshwaran D")
        self.assertEqual(lead.phone, "989943213")
        self.assertEqual(lead.email, "krish@example.com")
        self.assertEqual(lead.company, "WACRM")
        self.assertEqual(lead.city, "Coimbatore")
        self.assertEqual(lead.requirement_notes, "Interested in WA HRMS")
        self.assertEqual(lead.channel_partner_id, "partner-cp-1")
        self.assertEqual(lead.channel_partner_name, "Krish")
        self.assertEqual(lead.channel_partner_code, "KRISH385")
        self.assertEqual(lead.channel_partner_status, "submitted")
        self.assertEqual(
            lead.channel_partner_details_json.get("partnerCode"), "KRISH385"
        )
        self.assertEqual(
            lead.created_at.replace(microsecond=0),
            datetime(2026, 11, 19, 12, 1, 5),
        )

    def test_channel_partner_update_is_idempotent_and_reflects_external_status(self):
        upsert_partner(
            self.db,
            {
                "partnerId": "partner-cp-1",
                "name": "Krish",
                "code": "KRISH385",
                "status": "active",
            },
            commit=True,
        )
        upsert_lead(self.db, self._partner_lead_payload(), commit=True)
        lead = (
            self.db.query(Lead)
            .filter(Lead.channel_partner_lead_id == "lead-cp-1")
            .first()
        )
        lead.status = "QUALIFIED"
        lead.assigned_to = 42
        self.db.commit()

        updated_payload = self._partner_lead_payload(
            status="converted",
            companyName="Casio",
            updatedAt="2026-11-20T07:00:00.000Z",
        )
        upsert_lead(self.db, updated_payload, commit=True)
        upsert_lead(self.db, updated_payload, commit=True)

        rows = (
            self.db.query(Lead)
            .filter(Lead.channel_partner_lead_id == "lead-cp-1")
            .all()
        )
        self.assertEqual(len(rows), 1)
        refreshed = rows[0]
        self.assertEqual(refreshed.source, "CHANNEL_PARTNER")
        # The newer external status is reflected into the CRM workflow.
        self.assertEqual(refreshed.status, "WON")
        self.assertEqual(refreshed.assigned_to, 42)
        self.assertEqual(refreshed.company, "Casio")
        self.assertEqual(refreshed.channel_partner_status, "converted")

    def test_channel_partner_webhook_updates_same_all_leads_row(self):
        upsert_partner(
            self.db,
            {
                "partnerId": "partner-cp-1",
                "name": "Krish",
                "code": "KRISH385",
                "status": "active",
            },
            commit=True,
        )
        created_event, duplicate = store_webhook_event(
            self.db,
            event_id="evt_lead_created_1",
            event_type="lead.created",
            payload={
                "id": "evt_lead_created_1",
                "type": "lead.created",
                "data": {"lead": self._partner_lead_payload()},
            },
            headers={},
        )
        self.assertFalse(duplicate)
        with patch("services.channel_partner_sync.SessionLocal", self.Session):
            process_webhook_event(created_event.id)

        duplicate_event, duplicate = store_webhook_event(
            self.db,
            event_id="evt_lead_created_1",
            event_type="lead.created",
            payload={
                "id": "evt_lead_created_1",
                "type": "lead.created",
                "data": {"lead": self._partner_lead_payload()},
            },
            headers={},
        )
        self.assertTrue(duplicate)
        with patch("services.channel_partner_sync.SessionLocal", self.Session):
            process_webhook_event(duplicate_event.id)

        lead = (
            self.db.query(Lead)
            .filter(Lead.channel_partner_lead_id == "lead-cp-1")
            .first()
        )
        self.assertIsNotNone(lead)
        self.assertEqual(
            self.db.query(Lead)
            .filter(Lead.channel_partner_lead_id == "lead-cp-1")
            .count(),
            1,
        )

        status = apply_event(
            self.db,
            event_type="lead.converted",
            payload={
                "type": "lead.converted",
                "data": {
                    "lead": self._partner_lead_payload(
                        status="converted",
                        updatedAt="2026-11-20T07:00:00.000Z",
                    )
                },
            },
        )
        self.assertEqual(status, "processed")
        self.db.refresh(lead)
        self.assertEqual(lead.channel_partner_status, "converted")
        self.assertEqual(lead.source, "CHANNEL_PARTNER")
        # The external conversion is reflected into the CRM workflow. The
        # Channel Partner source and assignment remain unchanged.
        self.assertEqual(lead.status, "WON")

    def test_historical_channel_partner_mirror_rows_are_backfilled(self):
        self.db.add(
            ChannelPartnerLead(
                external_id="lead-historical-1",
                partner_external_id="partner-cp-1",
                partner_name="Krish",
                status="submitted",
                company_name="Legacy Co",
                contact_name="Legacy Contact",
                email="legacy@example.com",
                phone="9000000000",
                raw_data={
                    "id": "lead-historical-1",
                    "partnerId": "partner-cp-1",
                    "partnerName": "Krish",
                    "partnerCode": "KRISH385",
                    "status": "submitted",
                    "companyName": "Legacy Co",
                    "contactName": "Legacy Contact",
                    "createdAt": "2026-10-01T05:00:00.000Z",
                },
            )
        )
        self.db.commit()

        stats = sync_channel_partner_leads_to_crm(self.db)
        self.assertEqual(stats["crmLeadsCreated"], 1)
        lead = (
            self.db.query(Lead)
            .filter(Lead.channel_partner_lead_id == "lead-historical-1")
            .first()
        )
        self.assertIsNotNone(lead)
        self.assertEqual(lead.source, "CHANNEL_PARTNER")
        self.assertEqual(lead.company, "Legacy Co")
        self.assertEqual(lead.channel_partner_code, "KRISH385")

        # Running the backfill again must not duplicate the lead.
        stats_again = sync_channel_partner_leads_to_crm(self.db)
        self.assertEqual(stats_again["crmLeadsCreated"], 0)
        self.assertEqual(
            self.db.query(Lead)
            .filter(Lead.channel_partner_lead_id == "lead-historical-1")
            .count(),
            1,
        )


    # ------------------------------------------------------------------
    # Two-way status synchronization
    # ------------------------------------------------------------------
    def _seed_partner_lead(self, *, external_status="submitted"):
        upsert_partner(
            self.db,
            {
                "partnerId": "partner-cp-1",
                "name": "Krish",
                "code": "KRISH385",
                "status": "active",
            },
            commit=True,
        )
        upsert_lead(
            self.db,
            self._partner_lead_payload(status=external_status),
            commit=True,
        )
        lead = (
            self.db.query(Lead)
            .filter(Lead.channel_partner_lead_id == "lead-cp-1")
            .first()
        )
        mirror = (
            self.db.query(ChannelPartnerLead)
            .filter(ChannelPartnerLead.external_id == "lead-cp-1")
            .first()
        )
        return lead, mirror

    def _patch_client(self):
        return patch(
            "services.channel_partner_sync.load_effective_config",
            return_value=FakeChannelPartnerConfig(),
        ), patch(
            "services.channel_partner_sync.ChannelPartnerClient",
            FakeChannelPartnerClient,
        )

    def test_status_mapping_only_uses_documented_external_statuses(self):
        self.assertEqual(
            set(CRM_TO_CHANNEL_PARTNER_STATUS.values()),
            set(CHANNEL_PARTNER_STATUSES),
        )
        self.assertEqual(
            validate_channel_partner_status_change("NEW", None),
            ("submitted", None),
        )
        self.assertEqual(
            validate_channel_partner_status_change("QUALIFIED", "  "),
            ("qualified", None),
        )
        # Unmapped CRM statuses keep the CRM-only workflow and skip the PATCH.
        self.assertEqual(
            validate_channel_partner_status_change("CONTACTED", None),
            (None, None),
        )
        with self.assertRaises(ChannelPartnerStatusSyncError):
            validate_channel_partner_status_change("REJECTED", "")
        with self.assertRaises(ChannelPartnerStatusSyncError):
            validate_channel_partner_status_change("LOST", "   ")

    def test_generic_update_accepts_partner_visible_review_note(self):
        update = LeadUpdate(status="LOST", review_note="Not eligible for this programme.")
        self.assertEqual(
            validate_channel_partner_status_change(update.status, update.review_note),
            ("lost", "Not eligible for this programme."),
        )
        # Whitespace is treated as missing, so the backend still blocks the
        # rejection/loss instead of sending an empty partner-facing note.
        blank = LeadUpdate(status="REJECTED", review_note="   ")
        self.assertIsNone(blank.review_note)
        with self.assertRaises(ChannelPartnerStatusSyncError):
            validate_channel_partner_status_change(blank.status, blank.review_note)

    def test_rejected_to_lost_is_recorded_locally_without_a_patch(self):
        lead, _ = self._seed_partner_lead(external_status="rejected")
        FakeChannelPartnerClient.calls = []
        FakeChannelPartnerClient.error = None

        # The CRM treats rejected and lost as the same closed outcome, so the
        # local status change is accepted without an invalid upstream PATCH.
        validate_channel_partner_transition(lead, "LOST")
        result = push_channel_partner_status(
            self.db,
            lead,
            crm_status="LOST",
            review_note="Final review completed.",
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["skipped"])
        self.assertEqual(result["syncStatus"], "SYNCED")
        self.assertEqual(result["externalStatus"], "rejected")
        self.assertEqual(result["requestedStatus"], "lost")
        self.assertIn("same closed outcome", result["message"])
        self.assertEqual(FakeChannelPartnerClient.calls, [])

        self.db.refresh(lead)
        # The external status stays rejected; the CRM status change is
        # recorded as synchronized without pretending WA HRMS changed.
        self.assertEqual(lead.channel_partner_status, "rejected")
        self.assertEqual(lead.channel_partner_sync_status, "SYNCED")
        self.assertIsNone(lead.channel_partner_pending_status)
        self.assertIsNone(lead.channel_partner_last_sync_error)

        # Other transitions remain valid for the mapping layer.
        validate_channel_partner_transition(lead, "REJECTED")
        validate_channel_partner_transition(lead, "QUALIFIED")

    def test_push_success_records_confirmed_status_and_updates_mirror(self):
        lead, mirror = self._seed_partner_lead()
        FakeChannelPartnerClient.calls = []
        FakeChannelPartnerClient.error = None
        config_patch, client_patch = self._patch_client()
        with config_patch, client_patch:
            result = push_channel_partner_status(
                self.db,
                lead,
                crm_status="QUALIFIED",
                review_note="Qualified after discussion",
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["syncStatus"], "SYNCED")
        self.assertEqual(result["externalStatus"], "qualified")
        self.assertEqual(
            FakeChannelPartnerClient.calls,
            [{
                "lead_id": "lead-cp-1",
                "status": "qualified",
                "review_note": "Qualified after discussion",
            }],
        )
        self.db.refresh(lead)
        self.db.refresh(mirror)
        self.assertEqual(lead.channel_partner_status, "qualified")
        self.assertEqual(lead.channel_partner_sync_status, "SYNCED")
        self.assertIsNotNone(lead.channel_partner_last_synced_at)
        self.assertIsNone(lead.channel_partner_last_sync_error)
        self.assertIsNone(lead.channel_partner_pending_status)
        self.assertEqual(mirror.status, "qualified")
        self.assertEqual(mirror.review_note, "Qualified after discussion")

    def test_push_failure_preserves_confirmed_status_and_retry_succeeds(self):
        lead, _ = self._seed_partner_lead()
        FakeChannelPartnerClient.calls = []
        FakeChannelPartnerClient.error = ChannelPartnerAPIError(
            "Request validation failed.",
            status_code=422,
            errors={"status": ["invalid status"]},
        )
        config_patch, client_patch = self._patch_client()
        with config_patch, client_patch:
            result = push_channel_partner_status(
                self.db,
                lead,
                crm_status="REJECTED",
                review_note="Duplicate partner lead",
            )

        self.assertFalse(result["success"])
        self.assertEqual(result["syncStatus"], "FAILED")
        self.db.refresh(lead)
        # The last confirmed external status is preserved for display.
        self.assertEqual(lead.channel_partner_status, "submitted")
        self.assertEqual(lead.channel_partner_sync_status, "FAILED")
        self.assertIn("Request validation failed", lead.channel_partner_last_sync_error)
        self.assertIn("status", lead.channel_partner_last_sync_error)
        self.assertEqual(lead.channel_partner_pending_status, "rejected")
        self.assertEqual(
            lead.channel_partner_pending_review_note, "Duplicate partner lead"
        )

        FakeChannelPartnerClient.error = None
        config_patch, client_patch = self._patch_client()
        with config_patch, client_patch:
            retry = retry_channel_partner_status_sync(self.db, lead)

        self.assertTrue(retry["success"])
        self.db.refresh(lead)
        self.assertEqual(lead.channel_partner_status, "rejected")
        self.assertEqual(lead.channel_partner_sync_status, "SYNCED")
        self.assertIsNone(lead.channel_partner_pending_status)
        self.assertIsNone(lead.channel_partner_pending_review_note)
        self.assertEqual(FakeChannelPartnerClient.calls[-1]["status"], "rejected")
        self.assertEqual(
            FakeChannelPartnerClient.calls[-1]["review_note"], "Duplicate partner lead"
        )

    def test_webhook_confirmation_clears_pending_without_outbound_patch(self):
        lead, _ = self._seed_partner_lead()
        lead.status = "QUALIFIED"
        lead.channel_partner_sync_status = "PENDING"
        lead.channel_partner_pending_status = "qualified"
        lead.channel_partner_pending_review_note = "Qualified after discussion"
        self.db.commit()

        FakeChannelPartnerClient.calls = []
        FakeChannelPartnerClient.error = AssertionError(
            "Inbound webhook confirmation must not send another PATCH"
        )
        config_patch, client_patch = self._patch_client()
        with config_patch, client_patch:
            upsert_lead(
                self.db,
                self._partner_lead_payload(
                    status="qualified",
                    updatedAt="2026-11-20T07:00:00.000Z",
                ),
                commit=True,
            )

        self.assertEqual(FakeChannelPartnerClient.calls, [])
        self.db.refresh(lead)
        self.assertEqual(lead.channel_partner_sync_status, "SYNCED")
        self.assertIsNone(lead.channel_partner_pending_status)
        self.assertEqual(lead.status, "QUALIFIED")
        self.assertEqual(lead.channel_partner_status, "qualified")

    def test_out_of_order_external_updates_do_not_roll_back_status(self):
        lead, _ = self._seed_partner_lead()
        upsert_lead(
            self.db,
            self._partner_lead_payload(
                status="qualified",
                updatedAt="2026-11-20T07:00:00.000Z",
            ),
            commit=True,
        )
        # A delayed event older than the applied one must be ignored.
        upsert_lead(
            self.db,
            self._partner_lead_payload(
                status="submitted",
                updatedAt="2026-11-19T08:00:00.000Z",
            ),
            commit=True,
        )
        self.db.refresh(lead)
        self.assertEqual(lead.channel_partner_status, "qualified")
        self.assertEqual(lead.status, "QUALIFIED")

    def test_inbound_update_never_downgrades_terminal_crm_status(self):
        lead, _ = self._seed_partner_lead()
        lead.status = "WON"
        lead.channel_partner_status = "converted"
        self.db.commit()

        upsert_lead(
            self.db,
            self._partner_lead_payload(
                status="submitted",
                updatedAt="2026-11-20T07:00:00.000Z",
            ),
            commit=True,
        )

        self.db.refresh(lead)
        self.assertEqual(lead.status, "WON")
        self.assertEqual(lead.channel_partner_status, "submitted")
        self.assertEqual(lead.channel_partner_sync_status, "NOT_SYNCED")
        self.assertIn("terminal", lead.channel_partner_last_sync_error)

    def test_converted_push_requires_organization_and_subscription_order(self):
        lead, mirror = self._seed_partner_lead()
        lead.status = "WON"
        self.db.commit()

        FakeChannelPartnerClient.calls = []
        FakeChannelPartnerClient.error = None
        config_patch, client_patch = self._patch_client()
        with config_patch, client_patch:
            blocked = push_channel_partner_status(
                self.db, lead, crm_status="WON", review_note=None
            )

        self.assertFalse(blocked["success"])
        self.assertEqual(blocked["syncStatus"], "FAILED")
        self.assertIn("organization", blocked["message"])
        self.assertEqual(FakeChannelPartnerClient.calls, [])
        self.db.refresh(lead)
        self.assertEqual(lead.channel_partner_pending_status, "converted")

        mirror.organization_id = "org-1"
        mirror.subscription_order_id = "sub-1"
        self.db.commit()

        config_patch, client_patch = self._patch_client()
        with config_patch, client_patch:
            converted = push_channel_partner_status(
                self.db, lead, crm_status="WON", review_note=None
            )

        self.assertTrue(converted["success"])
        self.assertEqual(converted["externalStatus"], "converted")
        self.assertEqual(FakeChannelPartnerClient.calls[-1]["status"], "converted")

    def test_partner_lead_payload_exposes_crm_sync_fields(self):
        lead, mirror = self._seed_partner_lead()
        lead.channel_partner_sync_status = "FAILED"
        lead.channel_partner_last_sync_error = "HTTP 422: invalid status"
        lead.channel_partner_pending_status = "qualified"
        self.db.commit()

        payload = _lead_payload(mirror, crm_lead=lead)
        self.assertEqual(payload["crmLeadId"], lead.id)
        self.assertEqual(payload["crmStatus"], "NEW")
        self.assertEqual(payload["syncStatus"], "FAILED")
        self.assertEqual(payload["lastSyncError"], "HTTP 422: invalid status")
        self.assertEqual(payload["pendingStatus"], "qualified")


if __name__ == "__main__":
    unittest.main()
