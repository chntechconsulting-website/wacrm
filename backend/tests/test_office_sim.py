import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import settings
from database import get_db
from main import app
from models.call_log import CallLog
from models.employee import Employee
from models.integration import IntegrationConfig
from models.office_sim import OfficeSimMapping
from routers.office_sim import canonical_identity_tokens, sim_identity_matches
from services.auth import get_current_user


def _mapping(**overrides):
    values = dict(
        employee_id=1,
        subscription_id=2,
        sim_slot=1,
        carrier_name="Airtel",
        display_name="Office",
        phone_number="+919876543210",
        phone_account_id="account-2",
        phone_account_component="com.android.phone/com.android.services.telephony.TelephonyConnectionService",
        sim_fingerprint="f" * 64,
        status="VERIFIED",
    )
    values.update(overrides)
    return OfficeSimMapping(**values)


class TestOfficeSimIdentityMatching(unittest.TestCase):
    def test_subscription_token_is_the_primary_identity(self):
        mapping = _mapping()
        tokens = canonical_identity_tokens(mapping)
        self.assertIn("subId:2", tokens)
        self.assertTrue(sim_identity_matches(mapping, "subId:2"))
        self.assertFalse(sim_identity_matches(mapping, "subId:1"))

    def test_phone_account_identity_is_supported_without_a_subscription(self):
        mapping = _mapping(subscription_id=None)
        self.assertTrue(sim_identity_matches(mapping, "phoneAccount:account-2"))
        self.assertTrue(
            sim_identity_matches(
                mapping,
                "phoneAccount:com.android.phone/com.android.services.telephony.TelephonyConnectionService#account-2",
            )
        )

    def test_slot_and_number_never_identify_a_sim(self):
        mapping = _mapping()
        self.assertFalse(sim_identity_matches(mapping, None))
        self.assertFalse(sim_identity_matches(mapping, ""))
        self.assertFalse(sim_identity_matches(mapping, "SLOT:1"))
        self.assertFalse(sim_identity_matches(mapping, "+919876543210"))
        self.assertFalse(sim_identity_matches(mapping, "phoneAccount:other"))

    def test_native_subscription_id_is_exact_identity_evidence(self):
        mapping = _mapping()
        # A row may carry only the native subscription id when Android exposed
        # no phone-account token. The exact id still proves the Office SIM.
        self.assertTrue(
            sim_identity_matches(mapping, None, sim_subscription_id=2)
        )
        self.assertFalse(
            sim_identity_matches(mapping, None, sim_subscription_id=1)
        )
        # A non-matching pair is rejected: no slot/number fallback.
        self.assertFalse(
            sim_identity_matches(mapping, "phoneAccount:other", sim_subscription_id=1)
        )


class OfficeSimApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.old_upload_dir = settings.UPLOAD_DIR
        settings.UPLOAD_DIR = cls.temp_dir.name

        db_path = os.path.join(cls.temp_dir.name, "office_sim_test.db")
        cls.engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        Employee.__table__.create(cls.engine)
        OfficeSimMapping.__table__.create(cls.engine)
        CallLog.__table__.create(cls.engine)
        IntegrationConfig.__table__.create(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

        def override_db():
            db = cls.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id=1, role="ADMIN", username="admin"
        )
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        settings.UPLOAD_DIR = cls.old_upload_dir
        cls.engine.dispose()
        cls.temp_dir.cleanup()

    def setUp(self):
        db = self.Session()
        db.query(OfficeSimMapping).delete()
        db.query(CallLog).delete()
        db.query(Employee).delete()
        db.add(
            Employee(
                id=1,
                user_id=1,
                name="Office User",
                email="office@example.com",
                username="office",
                phone="+919876543210",
            )
        )
        db.commit()
        db.close()

    def _mapping_body(self, **overrides):
        body = {
            "subscription_id": 2,
            "sim_slot": 1,
            "carrier_name": "Airtel",
            "display_name": "Office",
            "phone_number": "+919876543210",
            "phone_account_id": "account-2",
            "phone_account_component": "com.android.phone/TelephonyConnectionService",
            "sim_fingerprint": "f" * 64,
        }
        body.update(overrides)
        return body


class TestOfficeSimMappingApi(OfficeSimApiTestCase):
    def test_mapping_is_not_configured_initially(self):
        response = self.client.get("/api/office-sim")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["configured"])

    def test_save_and_read_verified_mapping(self):
        saved = self.client.put("/api/office-sim", json=self._mapping_body())
        self.assertEqual(saved.status_code, 200, saved.text)
        data = saved.json()
        self.assertTrue(data["configured"])
        self.assertEqual(data["status"], "VERIFIED")
        self.assertEqual(data["subscription_id"], 2)
        self.assertEqual(data["sim_slot"], 1)

        read = self.client.get("/api/office-sim")
        self.assertEqual(read.status_code, 200, read.text)
        self.assertEqual(read.json()["sim_fingerprint"], "f" * 64)

    def test_slot_carrier_and_number_alone_cannot_identify_a_sim(self):
        response = self.client.put(
            "/api/office-sim",
            json=self._mapping_body(subscription_id=None, phone_account_id=None),
        )
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn("not sufficient", response.text)

    def test_fingerprint_is_required(self):
        response = self.client.put(
            "/api/office-sim",
            json=self._mapping_body(sim_fingerprint=""),
        )
        self.assertEqual(response.status_code, 422, response.text)

    def test_status_transition_to_requires_verification(self):
        self.client.put("/api/office-sim", json=self._mapping_body())
        response = self.client.post(
            "/api/office-sim/status",
            json={"status": "REQUIRES_VERIFICATION", "reason": "SIM replaced"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["status"], "REQUIRES_VERIFICATION")
        self.assertEqual(data["verification_reason"], "SIM replaced")

        reverified = self.client.put("/api/office-sim", json=self._mapping_body())
        self.assertEqual(reverified.status_code, 200, reverified.text)
        self.assertEqual(reverified.json()["status"], "VERIFIED")
        self.assertIsNone(reverified.json()["verification_reason"])

    def test_delete_removes_mapping(self):
        self.client.put("/api/office-sim", json=self._mapping_body())
        response = self.client.delete("/api/office-sim")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["configured"])
        self.assertFalse(self.client.get("/api/office-sim").json()["configured"])


class TestOfficeSimCallEnforcement(OfficeSimApiTestCase):
    def _log_call(self, **overrides):
        body = {
            "customer_phone": "+919111122233",
            "call_status": "COMPLETED",
            "duration_seconds": 20,
            "client_call_id": "SIM_OFFICE_1",
            "call_direction": "OUTBOUND",
            "call_source": "MOBILE_SIM",
            "native_call_reference": "native-1",
        }
        body.update(overrides)
        return self.client.post("/api/ivr/manual-call", json=body)

    def test_office_sim_call_is_logged(self):
        self.client.put("/api/office-sim", json=self._mapping_body())
        response = self._log_call(sim_account_id="subId:2")
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["sim_account_id"], "subId:2")

    def test_native_subscription_id_alone_proves_office_sim(self):
        self.client.put("/api/office-sim", json=self._mapping_body())
        response = self._log_call(sim_subscription_id=2)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["call_direction"], "OUTBOUND")

    def test_personal_subscription_id_is_rejected(self):
        self.client.put("/api/office-sim", json=self._mapping_body())
        response = self._log_call(sim_subscription_id=1)
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn("Office SIM", response.text)

    def test_personal_sim_call_is_rejected(self):
        self.client.put("/api/office-sim", json=self._mapping_body())
        response = self._log_call(sim_account_id="subId:1")
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn("Office SIM", response.text)

        db = self.Session()
        self.assertEqual(db.query(CallLog).count(), 0)
        db.close()

    def test_missing_sim_identity_fails_closed(self):
        self.client.put("/api/office-sim", json=self._mapping_body())
        response = self._log_call()
        self.assertEqual(response.status_code, 422, response.text)

    def test_unverified_mapping_blocks_sync(self):
        self.client.put("/api/office-sim", json=self._mapping_body())
        self.client.post(
            "/api/office-sim/status",
            json={"status": "REQUIRES_VERIFICATION", "reason": "SIM changed"},
        )
        response = self._log_call(sim_account_id="subId:2")
        self.assertEqual(response.status_code, 409, response.text)

    def test_no_mapping_keeps_legacy_behaviour(self):
        response = self._log_call(sim_account_id="subId:9")
        self.assertEqual(response.status_code, 201, response.text)

    def test_direct_dial_without_identity_fails_closed(self):
        self.client.put("/api/office-sim", json=self._mapping_body())
        response = self._log_call(
            call_source="DIRECT_DIAL", sim_account_id=None
        )
        self.assertEqual(response.status_code, 422, response.text)


class TestMobileCallDirectionApi(OfficeSimApiTestCase):
    """API + database + response direction for every device call outcome."""

    def _log(self, *, direction, status, duration, client_id):
        return self.client.post(
            "/api/ivr/manual-call",
            json={
                "customer_phone": "+919111122233",
                "call_status": status,
                "duration_seconds": duration,
                "client_call_id": client_id,
                "call_direction": direction,
                "call_source": "MOBILE_SIM",
                "native_call_reference": client_id,
            },
        )

    def _assert_stored(self, client_id, expected):
        db = self.Session()
        try:
            call = (
                db.query(CallLog)
                .filter(CallLog.provider_call_id == client_id)
                .one()
            )
            self.assertEqual(call.call_direction, expected)
        finally:
            db.close()

    def test_incoming_answered_is_inbound(self):
        response = self._log(
            direction="INBOUND",
            status="COMPLETED",
            duration=25,
            client_id="MOBILE_dir_in_answered",
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["call_direction"], "INBOUND")
        self._assert_stored("MOBILE_dir_in_answered", "INBOUND")

    def test_incoming_missed_is_inbound(self):
        response = self._log(
            direction="INBOUND",
            status="MISSED",
            duration=0,
            client_id="MOBILE_dir_in_missed",
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["call_direction"], "INBOUND")
        self._assert_stored("MOBILE_dir_in_missed", "INBOUND")

    def test_incoming_rejected_is_inbound(self):
        response = self._log(
            direction="INBOUND",
            status="REJECTED",
            duration=0,
            client_id="MOBILE_dir_in_rejected",
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["call_direction"], "INBOUND")
        self._assert_stored("MOBILE_dir_in_rejected", "INBOUND")

    def test_outgoing_answered_is_outbound(self):
        response = self._log(
            direction="OUTBOUND",
            status="COMPLETED",
            duration=15,
            client_id="MOBILE_dir_out_answered",
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["call_direction"], "OUTBOUND")
        self._assert_stored("MOBILE_dir_out_answered", "OUTBOUND")

    def test_outgoing_unanswered_is_outbound(self):
        response = self._log(
            direction="OUTBOUND",
            status="NO_ANSWER",
            duration=0,
            client_id="MOBILE_dir_out_unanswered",
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["call_direction"], "OUTBOUND")
        self._assert_stored("MOBILE_dir_out_unanswered", "OUTBOUND")

    def test_missing_direction_is_rejected_not_defaulted_outbound(self):
        response = self.client.post(
            "/api/ivr/manual-call",
            json={
                "customer_phone": "+919111122233",
                "call_status": "COMPLETED",
                "duration_seconds": 10,
                "client_call_id": "MOBILE_dir_missing",
                "call_source": "MOBILE_SIM",
            },
        )
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("call_direction", response.text)
        db = self.Session()
        try:
            self.assertEqual(db.query(CallLog).count(), 0)
        finally:
            db.close()


class TestOfficeSimRecordingEnforcement(OfficeSimApiTestCase):
    def _audio_bytes(self):
        return b"ID3" + b"\x00" * 4096

    def _call(self, sim_account_id="subId:2"):
        db = self.Session()
        call = CallLog(
            employee_id=1,
            provider="MOBILE_SIM",
            provider_call_id=f"SIM_REC_{sim_account_id}_{datetime_marker()}",
            from_number="+919876543210",
            to_number="+919111122233",
            call_status="COMPLETED",
            call_direction="OUTBOUND",
            duration_seconds=30,
            sim_account_id=sim_account_id,
        )
        db.add(call)
        db.commit()
        db.refresh(call)
        call_id = call.id
        db.close()
        return call_id

    def _upload(self, call_id):
        return self.client.post(
            f"/api/ivr/calls/{call_id}/recording",
            data={
                "source": "DEVICE",
                "consent": "true",
                "duration_seconds": "30",
            },
            files={"file": ("call.mp3", self._audio_bytes(), "audio/mpeg")},
        )

    def test_office_sim_recording_upload_is_allowed(self):
        self.client.put("/api/office-sim", json=self._mapping_body())
        response = self._upload(self._call("subId:2"))
        self.assertEqual(response.status_code, 200, response.text)

    def test_personal_sim_recording_is_rejected(self):
        self.client.put("/api/office-sim", json=self._mapping_body())
        response = self._upload(self._call("subId:1"))
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn("Office SIM", response.text)

    def test_unverified_mapping_blocks_recording_import(self):
        self.client.put("/api/office-sim", json=self._mapping_body())
        self.client.post(
            "/api/office-sim/status",
            json={"status": "REQUIRES_VERIFICATION", "reason": "SIM replaced"},
        )
        response = self._upload(self._call("subId:2"))
        self.assertEqual(response.status_code, 409, response.text)


_counter = {"value": 0}


def datetime_marker():
    _counter["value"] += 1
    return _counter["value"]


if __name__ == "__main__":
    unittest.main()
