"""Isolated tests for WhatsApp Business App coexistence onboarding.

These tests use an in-memory SQLite database and never touch the live CRM
database, the live Meta app, or WhatsApp number 7547900900.
"""

import hashlib
import hmac
import json
import os
import sys
import unittest
from datetime import datetime
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
from integrations.meta.crypto import encrypt_token
from integrations.whatsapp.config import WhatsAppConfig
from integrations.whatsapp_coexistence.config import WhatsAppCoexistenceConfig
from integrations.whatsapp_coexistence.router import router as coexistence_router
from integrations.whatsapp_coexistence.service import (
    WhatsAppCoexistenceError,
    WhatsAppCoexistenceService,
)
from integrations.whatsapp_ads.router import router as ad_crm_router
from integrations.whatsapp_ads.webhook import router as ad_webhook_router
from models.lead import Lead
from models.user import User
from models.whatsapp import Conversation, WhatsAppMessage
from models.whatsapp_coexistence import (
    WhatsAppCoexistenceConnection,
    WhatsAppCoexistenceEvent,
    WhatsAppSmbContact,
)
from services.auth import get_current_user

APP_SECRET = "test-whatsapp-ad-secret"
VERIFY_TOKEN = "test-whatsapp-ad-verify"
WABA_ID = "123456789012345"
PHONE_NUMBER_ID = "phone-coexist-test"
BUSINESS_PHONE = "919999999999"
CUSTOMER_PHONE = "9876543210"
PLAIN_TOKEN = "EAAG-coexistence-test-token"


class WhatsAppCoexistenceTests(unittest.TestCase):
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
                "WHATSAPP_AD_BUSINESS_ACCOUNT_ID": WABA_ID,
                "WHATSAPP_AD_ACCESS_TOKEN": "",
                "WHATSAPP_AD_MIRROR_INBOX": "false",
                "META_MARKETING_ACCESS_TOKEN": "",
                "WHATSAPP_COEXISTENCE_ENABLED": "false",
                "WHATSAPP_COEXISTENCE_APP_ID": "test-meta-app-id",
                "WHATSAPP_COEXISTENCE_APP_SECRET": "test-meta-app-secret",
                "WHATSAPP_COEXISTENCE_CONFIG_ID": "test-config-id",
                "WHATSAPP_COEXISTENCE_API_VERSION": "v26.0",
                "WHATSAPP_API_TOKEN": "",
                "WHATSAPP_PHONE_NUMBER_ID": "",
                "WHATSAPP_BUSINESS_ACCOUNT_ID": "",
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
        cls.app.include_router(ad_webhook_router, prefix="/api")
        cls.app.include_router(ad_crm_router, prefix="/api")
        cls.app.include_router(coexistence_router, prefix="/api")
        cls.app.dependency_overrides[get_db] = override_db
        cls.app.dependency_overrides[get_current_user] = lambda: cls.current_user
        cls.client = TestClient(cls.app)

    @classmethod
    def tearDownClass(cls):
        cls.env_patcher.stop()

    def setUp(self):
        type(self).current_user = self.admin
        os.environ["WHATSAPP_COEXISTENCE_ENABLED"] = "false"
        db = self.Session()
        try:
            db.query(WhatsAppCoexistenceEvent).delete()
            db.query(WhatsAppSmbContact).delete()
            db.query(WhatsAppCoexistenceConnection).delete()
            db.query(WhatsAppMessage).delete()
            db.query(Conversation).delete()
            db.query(Lead).delete()
            db.query(User).delete()
            db.commit()
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def db_session(self):
        return self.Session()

    def create_connection(self, status="CONNECTED", waba_id=WABA_ID):
        db = self.db_session()
        try:
            connection = WhatsAppCoexistenceConnection(
                waba_id=waba_id,
                phone_number_id=PHONE_NUMBER_ID,
                business_id="business-test",
                display_phone_number="+91 99999 99999",
                verified_name="Test Business",
                status=status,
                onboarding_status="COMPLETE" if status == "SYNC_COMPLETE" else "SYNC_REQUESTED",
                encrypted_access_token=encrypt_token(PLAIN_TOKEN),
                webhook_subscribed=True,
                history_progress=40,
                contacts_synced=0,
                messages_synced=0,
                onboarded_at=datetime.utcnow(),
            )
            db.add(connection)
            db.commit()
            db.refresh(connection)
            connection_id = connection.id
        finally:
            db.close()
        return connection_id

    def signed_post(self, payload):
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(
            APP_SECRET.encode("utf-8"), body, hashlib.sha256
        ).hexdigest()
        return self.client.post(
            "/api/webhook/whatsapp",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": f"sha256={signature}",
            },
        )

    @staticmethod
    def envelope(field, value, entry_id=WABA_ID, entry_time=1762000000):
        return {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": entry_id,
                    "time": entry_time,
                    "changes": [{"field": field, "value": value}],
                }
            ],
        }

    @staticmethod
    def history_payload(message_id="wamid.history.1", progress=50, message=None):
        if message is None:
            message = {
                "from": CUSTOMER_PHONE,
                "id": message_id,
                "timestamp": "1762000000",
                "type": "text",
                "text": {"body": "Hello from history"},
            }
        return {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": WABA_ID,
                    "changes": [
                        {
                            "field": "history",
                            "value": {
                                "messaging_product": "whatsapp",
                                "history": [
                                    {
                                        "metadata": {
                                            "phase": 0,
                                            "chunk_order": 1,
                                            "progress": progress,
                                        },
                                        "threads": [
                                            {
                                                "id": CUSTOMER_PHONE,
                                                "messages": [message],
                                            }
                                        ],
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }

    @staticmethod
    def history_media_follow_up_payload(message):
        """Meta's second history webhook for a media message uses value.messages."""
        return {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": WABA_ID,
                    "changes": [
                        {
                            "field": "history",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "+91 99999 99999",
                                    "phone_number_id": PHONE_NUMBER_ID,
                                },
                                "messages": [message],
                            },
                        }
                    ],
                }
            ],
        }

    @staticmethod
    def contact_payload(timestamp="1762000100", action="add"):
        return {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": WABA_ID,
                    "changes": [
                        {
                            "field": "smb_app_state_sync",
                            "value": {
                                "messaging_product": "whatsapp",
                                "state_sync": [
                                    {
                                        "action": action,
                                        "contact": {
                                            "full_name": "Asha Verma",
                                            "first_name": "Asha",
                                            "phone_number": CUSTOMER_PHONE,
                                        },
                                        "metadata": {"timestamp": timestamp},
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }

    @staticmethod
    def echo_payload(wamid="wamid.echo.1", text="Sent from the Business App"):
        return {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": WABA_ID,
                    "time": 1762000200,
                    "changes": [
                        {
                            "field": "smb_message_echoes",
                            "value": {
                                "messaging_product": "whatsapp",
                                "message_echoes": [
                                    {
                                        "from": BUSINESS_PHONE,
                                        "to": CUSTOMER_PHONE,
                                        "id": wamid,
                                        "timestamp": "1762000200",
                                        "type": "text",
                                        "text": {"body": text},
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }

    # ------------------------------------------------------------------
    # Safety gate + configuration
    # ------------------------------------------------------------------
    def test_onboarding_is_locked_by_default(self):
        self.assertFalse(WhatsAppCoexistenceConfig.is_enabled())
        self.assertFalse(WhatsAppCoexistenceConfig.onboarding_ready())

        response = self.client.post(
            "/api/whatsapp/coexistence/exchange",
            json={
                "code": "one-time-code",
                "waba_id": WABA_ID,
                "phone_number_id": PHONE_NUMBER_ID,
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("locked", response.json()["detail"].lower())

    def test_exchange_rejects_missing_configuration_when_enabled(self):
        os.environ["WHATSAPP_COEXISTENCE_ENABLED"] = "true"
        with patch.dict(
            os.environ,
            {
                "WHATSAPP_COEXISTENCE_CONFIG_ID": "",
                "WHATSAPP_COEXISTENCE_APP_ID": "",
                "META_APP_ID": "",
                "WHATSAPP_COEXISTENCE_APP_SECRET": "",
                "META_APP_SECRET": "",
            },
        ), patch.object(
            WhatsAppCoexistenceConfig, "get_config_id", return_value=""
        ), patch.object(
            WhatsAppCoexistenceConfig, "get_app_id", return_value=""
        ), patch.object(
            WhatsAppCoexistenceConfig, "get_app_secret", return_value=""
        ):
            response = self.client.post(
                "/api/whatsapp/coexistence/exchange",
                json={
                    "code": "one-time-code",
                    "waba_id": WABA_ID,
                    "phone_number_id": PHONE_NUMBER_ID,
                },
            )
        self.assertEqual(response.status_code, 503)
        self.assertIn("not configured", response.json()["detail"].lower())

    def test_default_configuration_id_is_available_without_env(self):
        with patch.dict(
            os.environ, {"WHATSAPP_COEXISTENCE_CONFIG_ID": ""}, clear=False
        ):
            self.assertEqual(
                WhatsAppCoexistenceConfig.get_config_id(),
                "2372647743564644",
            )

    def test_secret_is_not_reused_for_a_different_coexistence_app(self):
        with patch.dict(
            os.environ,
            {
                "WHATSAPP_COEXISTENCE_APP_ID": "app-for-coexistence",
                "META_APP_ID": "legacy-app",
                "WHATSAPP_COEXISTENCE_APP_SECRET": "",
                "META_APP_SECRET": "legacy-secret",
            },
            clear=False,
        ):
            self.assertEqual(WhatsAppCoexistenceConfig.get_app_secret(), "")
            config = WhatsAppCoexistenceConfig.public_config()
            self.assertFalse(config["configured"])
            self.assertTrue(
                any("differs from META_APP_ID" in warning for warning in config["warnings"])
            )

    def test_explicit_coexistence_secret_is_used_for_a_different_app(self):
        with patch.dict(
            os.environ,
            {
                "WHATSAPP_COEXISTENCE_APP_ID": "app-for-coexistence",
                "META_APP_ID": "legacy-app",
                "WHATSAPP_COEXISTENCE_APP_SECRET": "coexistence-secret",
                "META_APP_SECRET": "legacy-secret",
            },
            clear=False,
        ):
            self.assertEqual(
                WhatsAppCoexistenceConfig.get_app_secret(), "coexistence-secret"
            )

    def test_known_config_requires_its_owning_app(self):
        with patch.dict(
            os.environ,
            {
                "WHATSAPP_COEXISTENCE_CONFIG_ID": "1698501728618095",
                "WHATSAPP_COEXISTENCE_APP_ID": "1797499357941817",
                "WHATSAPP_COEXISTENCE_APP_SECRET": "legacy-secret",
            },
            clear=False,
        ):
            self.assertFalse(WhatsAppCoexistenceConfig.is_configured())
            warnings = WhatsAppCoexistenceConfig.public_config()["warnings"]
            self.assertTrue(
                any(
                    "belongs to Meta app 1158185796552320" in warning
                    for warning in warnings
                )
            )

    def test_known_config_is_configured_with_its_owning_app(self):
        with patch.dict(
            os.environ,
            {
                "WHATSAPP_COEXISTENCE_CONFIG_ID": "1698501728618095",
                "WHATSAPP_COEXISTENCE_APP_ID": "1158185796552320",
                "WHATSAPP_COEXISTENCE_APP_SECRET": "review-app-secret",
            },
            clear=False,
        ):
            self.assertTrue(WhatsAppCoexistenceConfig.is_configured())

    def test_production_config_requires_the_wacrmwap_app(self):
        with patch.dict(
            os.environ,
            {
                "WHATSAPP_COEXISTENCE_CONFIG_ID": "2372647743564644",
                "WHATSAPP_COEXISTENCE_APP_ID": "1797499357941817",
                "WHATSAPP_COEXISTENCE_APP_SECRET": "legacy-secret",
            },
            clear=False,
        ):
            self.assertFalse(WhatsAppCoexistenceConfig.is_configured())
            warnings = WhatsAppCoexistenceConfig.public_config()["warnings"]
            self.assertTrue(
                any(
                    "belongs to Meta app 2041712130118952" in warning
                    for warning in warnings
                )
            )

    def test_production_config_is_configured_with_the_wacrmwap_app(self):
        with patch.dict(
            os.environ,
            {
                "WHATSAPP_COEXISTENCE_CONFIG_ID": "2372647743564644",
                "WHATSAPP_COEXISTENCE_APP_ID": "2041712130118952",
                "WHATSAPP_COEXISTENCE_APP_SECRET": "wacrmwap-app-secret",
            },
            clear=False,
        ):
            self.assertTrue(WhatsAppCoexistenceConfig.is_configured())

    def test_public_config_never_returns_secrets(self):
        config = WhatsAppCoexistenceConfig.public_config()
        serialized = json.dumps(config)
        self.assertNotIn("test-meta-app-secret", serialized)
        self.assertNotIn("app_secret", serialized)
        self.assertIn("required_webhook_fields", config)
        for field in (
            "messages",
            "account_update",
            "history",
            "smb_app_state_sync",
            "smb_message_echoes",
        ):
            self.assertIn(field, config["required_webhook_fields"])

    # ------------------------------------------------------------------
    # Session logging + status APIs
    # ------------------------------------------------------------------
    def test_session_log_redacts_code_and_status_hides_token(self):
        self.create_connection()

        log_response = self.client.post(
            "/api/whatsapp/coexistence/session-log",
            json={
                "type": "WA_EMBEDDED_SIGNUP",
                "event": "FINISH",
                "data": {
                    "waba_id": WABA_ID,
                    "phone_number_id": PHONE_NUMBER_ID,
                    "business_id": "business-test",
                    "code": "must-not-be-stored",
                },
            },
        )
        self.assertEqual(log_response.status_code, 200)
        self.assertTrue(log_response.json()["logged"])

        db = self.db_session()
        try:
            event = (
                db.query(WhatsAppCoexistenceEvent)
                .filter(WhatsAppCoexistenceEvent.event_type == "SESSION_LOG")
                .order_by(WhatsAppCoexistenceEvent.id.desc())
                .first()
            )
            self.assertIsNotNone(event)
            self.assertNotIn("must-not-be-stored", event.payload or "")
            self.assertIn(WABA_ID, event.payload or "")
        finally:
            db.close()

        status_response = self.client.get("/api/whatsapp/coexistence/status")
        self.assertEqual(status_response.status_code, 200)
        body = status_response.json()
        serialized = json.dumps(body)
        self.assertNotIn(PLAIN_TOKEN, serialized)
        self.assertNotIn("encrypted_access_token", serialized)
        self.assertNotIn("app_secret", serialized)
        self.assertEqual(body["connection"]["waba_id"], WABA_ID)
        self.assertEqual(body["connection"]["phone_number_id"], PHONE_NUMBER_ID)

        events_response = self.client.get("/api/whatsapp/coexistence/events")
        self.assertEqual(events_response.status_code, 200)
        self.assertNotIn(PLAIN_TOKEN, json.dumps(events_response.json()))
        self.assertNotIn("payload", events_response.json()[0])

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------
    def test_history_is_imported_once_and_never_creates_leads(self):
        self.create_connection()
        db = self.db_session()
        try:
            first = WhatsAppCoexistenceService.process_payload(
                db, self.history_payload()
            )
            second = WhatsAppCoexistenceService.process_payload(
                db, self.history_payload()
            )

            self.assertEqual(first["history_messages"], 1)
            self.assertEqual(second["history_messages"], 0)
            self.assertEqual(db.query(WhatsAppMessage).count(), 1)
            self.assertEqual(db.query(Conversation).count(), 1)
            self.assertEqual(db.query(Lead).count(), 0)

            message = db.query(WhatsAppMessage).first()
            self.assertEqual(message.provider_message_id, "wamid.history.1")
            self.assertEqual(message.direction, "INBOUND")
            self.assertEqual(message.body, "Hello from history")

            connection = db.query(WhatsAppCoexistenceConnection).first()
            self.assertEqual(connection.history_progress, 50)
            self.assertEqual(connection.messages_synced, 1)
        finally:
            db.close()

    def test_history_completion_marks_connection_synced(self):
        self.create_connection(status="SYNCING")
        db = self.db_session()
        try:
            WhatsAppCoexistenceService.process_payload(
                db, self.history_payload("wamid.history.2", progress=100)
            )
            connection = db.query(WhatsAppCoexistenceConnection).first()
            self.assertEqual(connection.status, "SYNC_COMPLETE")
            self.assertEqual(connection.onboarding_status, "COMPLETE")
            self.assertIsNone(connection.sync_deadline_at)
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Contacts
    # ------------------------------------------------------------------
    def test_business_app_contacts_sync_without_creating_leads(self):
        self.create_connection()
        db = self.db_session()
        try:
            first = WhatsAppCoexistenceService.process_payload(
                db, self.contact_payload()
            )
            second = WhatsAppCoexistenceService.process_payload(
                db, self.contact_payload()
            )

            self.assertEqual(first["contacts_synced"], 1)
            self.assertEqual(second["contacts_synced"], 0)
            contact = db.query(WhatsAppSmbContact).first()
            self.assertIsNotNone(contact)
            self.assertEqual(contact.phone_number, CUSTOMER_PHONE)
            self.assertEqual(contact.full_name, "Asha Verma")
            self.assertEqual(contact.last_action, "add")
            self.assertEqual(db.query(Lead).count(), 0)
        finally:
            db.close()

    def test_contact_remove_updates_state_without_deleting_history(self):
        self.create_connection()
        db = self.db_session()
        try:
            WhatsAppCoexistenceService.process_payload(db, self.contact_payload())
            WhatsAppCoexistenceService.process_payload(
                db, self.contact_payload(timestamp="1762000300", action="remove")
            )
            contact = db.query(WhatsAppSmbContact).first()
            self.assertIsNotNone(contact)
            self.assertEqual(contact.last_action, "remove")
            self.assertEqual(db.query(WhatsAppSmbContact).count(), 1)
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Business App echoes
    # ------------------------------------------------------------------
    def test_business_app_echo_is_mirrored_once(self):
        self.create_connection()
        db = self.db_session()
        try:
            first = WhatsAppCoexistenceService.process_payload(
                db, self.echo_payload()
            )
            second = WhatsAppCoexistenceService.process_payload(
                db, self.echo_payload()
            )

            self.assertEqual(first["echoes"], 1)
            self.assertEqual(second["echoes"], 0)
            self.assertEqual(db.query(WhatsAppMessage).count(), 1)
            message = db.query(WhatsAppMessage).first()
            self.assertEqual(message.direction, "OUTBOUND")
            self.assertEqual(message.provider_message_id, "wamid.echo.1")
            self.assertEqual(message.body, "Sent from the Business App")
            self.assertEqual(db.query(Lead).count(), 0)
        finally:
            db.close()

    def test_signed_webhook_routes_coexistence_fields(self):
        self.create_connection()
        response = self.signed_post(self.echo_payload("wamid.echo.signed"))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "received")
        self.assertEqual(body["coexistence"]["echoes"], 1)

        db = self.db_session()
        try:
            message = (
                db.query(WhatsAppMessage)
                .filter(WhatsAppMessage.provider_message_id == "wamid.echo.signed")
                .first()
            )
            self.assertIsNotNone(message)
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Account lifecycle
    # ------------------------------------------------------------------
    def test_account_update_disconnects_and_reconnects(self):
        self.create_connection()
        db = self.db_session()
        try:
            WhatsAppCoexistenceService.process_payload(
                db,
                self.envelope(
                    "account_update",
                    {
                        "messaging_product": "whatsapp",
                        "event": "PARTNER_REMOVED",
                        "disconnection_info": {
                            "reason": "USER_INITIATED",
                            "initiated_by": "BUSINESS",
                        },
                    },
                    entry_time=1762000400,
                ),
            )
            connection = db.query(WhatsAppCoexistenceConnection).first()
            self.assertEqual(connection.status, "DISCONNECTED")
            self.assertFalse(connection.webhook_subscribed)
            self.assertIn("PARTNER_REMOVED", connection.last_error)

            WhatsAppCoexistenceService.process_payload(
                db,
                self.envelope(
                    "account_update",
                    {"messaging_product": "whatsapp", "event": "ACCOUNT_RECONNECTED"},
                    entry_time=1762000500,
                ),
            )
            db.refresh(connection)
            self.assertEqual(connection.status, "CONNECTED")
            self.assertIsNone(connection.last_error)
        finally:
            db.close()

    # ------------------------------------------------------------------
    # WhatsAppConfig integration
    # ------------------------------------------------------------------
    def test_whatsapp_config_prefers_active_coexistence_connection(self):
        self.create_connection(status="SYNC_COMPLETE")
        with patch("database.SessionLocal", self.Session):
            self.assertEqual(WhatsAppConfig.get_phone_number_id(), PHONE_NUMBER_ID)
            self.assertEqual(WhatsAppConfig.get_business_account_id(), WABA_ID)
            self.assertEqual(WhatsAppConfig.get_api_token(), PLAIN_TOKEN)
            self.assertTrue(WhatsAppConfig.is_configured())

    # ------------------------------------------------------------------
    # Templates
    # ------------------------------------------------------------------
    def test_template_validation_happens_before_any_network_call(self):
        self.create_connection()
        db = self.db_session()
        try:
            with self.assertRaises(WhatsAppCoexistenceError) as ctx:
                WhatsAppCoexistenceService.create_template(
                    db,
                    name="Invalid Name!",
                    language="en_US",
                    category="UTILITY",
                    body_text="Hello",
                )
            self.assertIn("lowercase letters", str(ctx.exception))
        finally:
            db.close()

    def test_template_creation_requires_active_connection(self):
        db = self.db_session()
        try:
            with self.assertRaises(WhatsAppCoexistenceError) as ctx:
                WhatsAppCoexistenceService.create_template(
                    db,
                    name="valid_name",
                    language="en_US",
                    category="UTILITY",
                    body_text="Hello",
                )
            self.assertEqual(ctx.exception.status_code, 404)
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Meta edge cases
    # ------------------------------------------------------------------
    def test_exchange_resolves_phone_number_id_when_session_omits_it(self):
        os.environ["WHATSAPP_COEXISTENCE_ENABLED"] = "true"
        calls = []

        def fake_graph(method, path, token=None, params=None, json_body=None):
            calls.append((method, path))
            if path == "oauth/access_token":
                return {"access_token": PLAIN_TOKEN}
            if path == f"{WABA_ID}/phone_numbers":
                return {
                    "data": [
                        {"id": "phone-other", "is_on_biz_app": False},
                        {"id": PHONE_NUMBER_ID, "is_on_biz_app": True},
                    ]
                }
            if path == PHONE_NUMBER_ID:
                return {
                    "id": PHONE_NUMBER_ID,
                    "display_phone_number": "+91 99999 99999",
                    "verified_name": "Test Business",
                    "quality_rating": "GREEN",
                    "is_on_biz_app": True,
                    "platform_type": "SMB_APP",
                    "whatsapp_business_account": {"id": WABA_ID},
                }
            if path == WABA_ID:
                return {
                    "id": WABA_ID,
                    "name": "Test Business",
                    "account_review_status": "APPROVED",
                }
            if path == f"{WABA_ID}/subscribed_apps":
                return {"success": True}
            if path == f"{PHONE_NUMBER_ID}/smb_app_data":
                return {"request_id": "sync-request-1"}
            raise AssertionError(f"Unexpected Graph call: {method} {path}")

        db = self.db_session()
        try:
            with patch.object(
                WhatsAppCoexistenceService, "graph_request", side_effect=fake_graph
            ):
                result = WhatsAppCoexistenceService.exchange_code(
                    db,
                    code="one-time-code",
                    waba_id=WABA_ID,
                    phone_number_id=None,
                )

            self.assertEqual(result["phone_number_id"], PHONE_NUMBER_ID)
            connection = db.query(WhatsAppCoexistenceConnection).first()
            self.assertIsNotNone(connection)
            self.assertEqual(connection.phone_number_id, PHONE_NUMBER_ID)
            self.assertNotEqual(connection.encrypted_access_token, PLAIN_TOKEN)
            self.assertEqual(connection.status, "SYNCING")
            self.assertIsNotNone(connection.contacts_sync_requested_at)
            self.assertIsNotNone(connection.history_sync_requested_at)
            self.assertIn(("GET", f"{WABA_ID}/phone_numbers"), calls)
        finally:
            db.close()

    def test_exchange_refuses_to_guess_between_ambiguous_phone_numbers(self):
        os.environ["WHATSAPP_COEXISTENCE_ENABLED"] = "true"

        def fake_graph(method, path, token=None, params=None, json_body=None):
            if path == "oauth/access_token":
                return {"access_token": PLAIN_TOKEN}
            if path == f"{WABA_ID}/phone_numbers":
                return {
                    "data": [
                        {"id": "phone-a", "is_on_biz_app": True},
                        {"id": "phone-b", "is_on_biz_app": True},
                    ]
                }
            raise AssertionError(f"Unexpected Graph call: {method} {path}")

        db = self.db_session()
        try:
            with patch.object(
                WhatsAppCoexistenceService, "graph_request", side_effect=fake_graph
            ):
                with self.assertRaises(WhatsAppCoexistenceError) as ctx:
                    WhatsAppCoexistenceService.exchange_code(
                        db,
                        code="one-time-code",
                        waba_id=WABA_ID,
                        phone_number_id=None,
                    )
            self.assertIn("could not be identified", str(ctx.exception))
            self.assertEqual(db.query(WhatsAppCoexistenceConnection).count(), 0)
        finally:
            db.close()

    def test_account_update_resolves_waba_from_waba_info(self):
        self.create_connection()
        db = self.db_session()
        try:
            WhatsAppCoexistenceService.process_payload(
                db,
                self.envelope(
                    "account_update",
                    {
                        "messaging_product": "whatsapp",
                        "event": "PARTNER_REMOVED",
                        "waba_info": {"waba_id": WABA_ID},
                        "disconnection_info": {
                            "reason": "USER_INITIATED",
                            "initiated_by": "BUSINESS",
                        },
                    },
                    entry_id="partner-business-id",
                    entry_time=1762000600,
                ),
            )
            connection = db.query(WhatsAppCoexistenceConnection).first()
            self.assertEqual(connection.status, "DISCONNECTED")
            self.assertFalse(connection.webhook_subscribed)
            self.assertIn("PARTNER_REMOVED", connection.last_error)

            WhatsAppCoexistenceService.process_payload(
                db,
                self.envelope(
                    "account_update",
                    {
                        "messaging_product": "whatsapp",
                        "event": "ACCOUNT_RECONNECTED",
                        "waba_info": {"waba_id": WABA_ID},
                    },
                    entry_id="partner-business-id",
                    entry_time=1762000700,
                ),
            )
            db.refresh(connection)
            self.assertEqual(connection.status, "CONNECTED")
            self.assertIsNone(connection.last_error)
        finally:
            db.close()

    def test_history_media_placeholder_is_upgraded_by_follow_up(self):
        self.create_connection()
        placeholder = {
            "from": CUSTOMER_PHONE,
            "id": "wamid.history.media",
            "timestamp": "1762000000",
            "type": "media_placeholder",
        }
        follow_up = {
            "from": CUSTOMER_PHONE,
            "id": "wamid.history.media",
            "timestamp": "1762000000",
            "type": "image",
            "image": {"id": "media-id-123", "caption": "Product photo"},
        }
        db = self.db_session()
        try:
            first = WhatsAppCoexistenceService.process_payload(
                db,
                self.history_payload(
                    message_id="wamid.history.media", message=placeholder
                ),
            )
            self.assertEqual(first["history_messages"], 1)
            message = db.query(WhatsAppMessage).first()
            self.assertEqual(message.body, "[Media message]")
            self.assertIsNone(message.media_url)
        finally:
            db.close()

        response = self.signed_post(
            self.history_media_follow_up_payload(follow_up)
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["coexistence"]["history_messages"], 0)

        db = self.db_session()
        try:
            self.assertEqual(db.query(WhatsAppMessage).count(), 1)
            message = db.query(WhatsAppMessage).first()
            self.assertEqual(message.message_type, "IMAGE")
            self.assertEqual(message.body, "Product photo")
            self.assertEqual(message.media_url, "media-id-123")

            connection = db.query(WhatsAppCoexistenceConnection).first()
            self.assertEqual(connection.messages_synced, 1)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
