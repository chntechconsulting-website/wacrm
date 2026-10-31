"""
Regression tests for call-recording identity.

The bug being guarded against: a recording belonging to one call was shown /
played under another call. The cause was heuristic matching (time windows,
file-size scoring, phone-only dedup) and a webhook adoption path that merged
concurrent calls to the same number.

Every test here asserts the new contract:
  * a recording is linked only through an authoritative provider call id,
  * an ambiguous identity leaves the recording unlinked,
  * duplicate artifacts are never attached twice,
  * legacy wrong links can be repaired without deleting call rows or files.
"""

import datetime
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401  (registers every table on Base.metadata)
from database import Base, get_db
from main import app
from models.call_log import CallLog
from models.integration import IntegrationConfig
from routers.ivr import build_call_log_response
from services.doocti_recording_service import (
    DooctiRecordingService,
    extract_recording_metadata,
)
from utils.timezone import get_ist_now

DID = "07969671855"
EXTENSION = "1282"
BASE = "https://storage.example.com/doocti/cti_test"


def storage_url(call_id: str, day: str = "2026-10-31") -> str:
    return f"{BASE}/{day}/{call_id}.mp3"


class RecordingTestBase(unittest.TestCase):
    engine = None
    Session = None
    client = None

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

        def override_db():
            db = cls.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        cls.client = TestClient(app)

        cfg = IntegrationConfig(
            integration_type="IVR",
            status="CONNECTED",
        )
        cfg.config_data = json.dumps(
            {
                "did_numbers": [DID],
                "admin_extension": EXTENSION,
                "agent_extensions": [EXTENSION],
                "extension_mapping": {
                    EXTENSION: {"employee_id": 1, "name": "Test Agent"}
                },
                "recording_base_url": BASE,
            }
        )
        db = cls.Session()
        db.add(cfg)
        db.commit()
        db.close()

        # Never touch the real object storage from unit tests.
        cls._patchers = [
            mock.patch.object(
                DooctiRecordingService,
                "fetch_bucket_recordings_for_date",
                lambda d, b: [],
            ),
            mock.patch.object(
                DooctiRecordingService,
                "url_exists",
                lambda url, min_size=500: False,
            ),
        ]
        for patcher in cls._patchers:
            patcher.start()

    @classmethod
    def tearDownClass(cls):
        for patcher in getattr(cls, "_patchers", []):
            patcher.stop()
        app.dependency_overrides.clear()
        if cls.engine is not None:
            cls.engine.dispose()

    def setUp(self):
        db = self.Session()
        db.query(CallLog).delete()
        db.commit()
        db.close()

    # helpers -----------------------------------------------------

    def db(self):
        return self.Session()

    def add_call(self, call_id, **kwargs):
        defaults = dict(
            provider="DOOCTI",
            provider_call_id=call_id,
            from_number=EXTENSION,
            to_number="9876543210",
            call_status="COMPLETED",
            call_direction="OUTBOUND",
            duration_seconds=30,
            started_at=get_ist_now() - datetime.timedelta(minutes=10),
            ended_at=get_ist_now() - datetime.timedelta(minutes=5),
        )
        defaults.update(kwargs)
        db = self.db()
        call = CallLog(**defaults)
        db.add(call)
        db.commit()
        db.refresh(call)
        db.close()
        return call_id

    def get_call(self, call_id):
        db = self.db()
        call = db.query(CallLog).filter(CallLog.provider_call_id == call_id).first()
        if call is not None:
            db.expunge(call)
        db.close()
        return call

    def load_call(self, db, call_id):
        return (
            db.query(CallLog)
            .filter(CallLog.provider_call_id == call_id)
            .first()
        )

    def count_calls(self, call_id):
        db = self.db()
        try:
            return db.query(CallLog).filter(CallLog.provider_call_id == call_id).count()
        finally:
            db.close()

    def post_cdr(self, payload):
        response = self.client.post("/api/doocti/call-log", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()


class TestRecordingIdentityHelpers(RecordingTestBase):
    def test_authoritative_ids_only(self):
        for good in ("1793333301.131253490", "1793333301", "12345678901"):
            self.assertTrue(DooctiRecordingService.is_authoritative_call_id(good), good)

        for bad in (
            "doocti_1282_9876543210_1",
            "call_1282_9876543210_1",
            "SIM_1723456789",
            "cs_call_1",
            "test_doocti_1",
            "",
            None,
            "not-a-call-id",
        ):
            self.assertFalse(DooctiRecordingService.is_authoritative_call_id(bad), bad)

    def test_recording_id_comes_from_filename(self):
        self.assertEqual(
            DooctiRecordingService.recording_id_from_url(
                "https://x/y/2026-10-31/1793333301.131253490.mp3?token=1"
            ),
            "1793333301.131253490",
        )
        self.assertEqual(
            DooctiRecordingService.recording_id_from_url("/uploads/recordings/4/call_4.m4a"),
            "call_4",
        )
        self.assertIsNone(DooctiRecordingService.recording_id_from_url(None))

    def test_extract_recording_metadata(self):
        rec_id, duration = extract_recording_metadata(
            {
                "recording_uniqueid": "1793333301.131253490",
                "recording_duration": "41",
                "recording_path": storage_url("1793333301.131253490"),
            },
            storage_url("1793333301.131253490"),
        )
        self.assertEqual(rec_id, "1793333301.131253490")
        self.assertEqual(duration, 41)

        rec_id, duration = extract_recording_metadata(
            {"recording_path": storage_url("1793333301.999")},
            storage_url("1793333301.999"),
        )
        self.assertEqual(rec_id, "1793333301.999")
        self.assertIsNone(duration)


class TestExactRecordingMatching(RecordingTestBase):
    def test_matches_only_same_uniqueid(self):
        call_id = "1793333301.131253490"
        self.add_call(call_id)
        same_url = storage_url(call_id)
        other_url = storage_url("1793333301.999999999")

        db = self.db()
        call = self.load_call(db, call_id)
        with mock.patch.object(
            DooctiRecordingService,
            "fetch_bucket_recordings_for_date",
            lambda d, b: [
                {"uniqueid": "1793333301.999999999", "url": other_url, "size": 90000},
                {"uniqueid": call_id, "url": same_url, "size": 90000},
            ],
        ), mock.patch.object(
            DooctiRecordingService,
            "url_exists",
            lambda url, min_size=500: url == same_url,
        ):
            matched = DooctiRecordingService.match_recording_for_call(call, db)
        db.close()

        self.assertEqual(matched, same_url)
        stored = self.get_call(call_id)
        self.assertEqual(stored.recording_url, same_url)
        self.assertEqual(stored.recording_id, call_id)
        self.assertIsNotNone(stored.recording_attached_at)

    def test_never_falls_back_to_time_or_size_heuristics(self):
        # A call one second after another has completed. The other call's audio
        # is a size/duration "good match" - the old algorithm would take it.
        target_id = "1793333301.131253490"
        self.add_call(
            target_id,
            started_at=get_ist_now() - datetime.timedelta(minutes=10),
        )
        neighbour_id = "1793333301.131253491"
        neighbour_url = storage_url(neighbour_id)

        db = self.db()
        target = self.load_call(db, target_id)
        with mock.patch.object(
            DooctiRecordingService,
            "fetch_bucket_recordings_for_date",
            lambda d, b: [
                {"uniqueid": neighbour_id, "url": neighbour_url, "size": 31000}
            ],
        ), mock.patch.object(
            DooctiRecordingService,
            "url_exists",
            lambda url, min_size=500: url == neighbour_url,
        ):
            matched = DooctiRecordingService.match_recording_for_call(target, db)
        db.close()

        self.assertIsNone(matched)
        stored = self.get_call(target_id)
        self.assertIsNone(stored.recording_url)
        self.assertIsNone(stored.recording_id)

    def test_failed_or_unanswered_call_gets_no_recording(self):
        call_id = "1793333301.131253492"
        self.add_call(
            call_id,
            call_status="FAILED",
            duration_seconds=0,
            answered_at=None,
        )
        url = storage_url(call_id)

        db = self.db()
        call = self.load_call(db, call_id)
        with mock.patch.object(
            DooctiRecordingService,
            "fetch_bucket_recordings_for_date",
            lambda d, b: [{"uniqueid": call_id, "url": url, "size": 9000}],
        ), mock.patch.object(
            DooctiRecordingService,
            "url_exists",
            lambda u, min_size=500: u == url,
        ):
            self.assertIsNone(
                DooctiRecordingService.match_recording_for_call(call, db)
            )
        db.close()

        stored = self.get_call(call_id)
        self.assertIsNone(stored.recording_url)

    def test_claim_requires_authoritative_id(self):
        synthetic_id = "doocti_1282_9876543210_1"
        self.add_call(
            synthetic_id,
            call_status="COMPLETED",
            duration_seconds=30,
        )
        db = self.db()
        synthetic = self.load_call(db, synthetic_id)
        self.assertIsNone(
            DooctiRecordingService.claim_unambiguous_recording(synthetic, db)
        )
        db.close()

        real_id = "1793333301.131253493"
        self.add_call(real_id)
        url = storage_url(real_id)
        db = self.db()
        real = self.load_call(db, real_id)
        with mock.patch.object(
            DooctiRecordingService,
            "fetch_bucket_recordings_for_date",
            lambda d, b: [{"uniqueid": real_id, "url": url, "size": 9000}],
        ), mock.patch.object(
            DooctiRecordingService,
            "url_exists",
            lambda u, min_size=500: u == url,
        ):
            self.assertEqual(
                DooctiRecordingService.claim_unambiguous_recording(real, db), url
            )
        db.close()

    def test_read_guard_hides_another_calls_audio(self):
        owner_id = "1793333301.131253500"
        wrong_id = "1793333301.131253501"
        self.add_call(owner_id)
        self.add_call(wrong_id, recording_url=storage_url(owner_id))

        db = self.db()
        attached = self.load_call(db, wrong_id)
        self.assertFalse(
            DooctiRecordingService._recording_belongs_to_call(
                attached, attached.recording_url, db
            )
        )
        response = build_call_log_response(attached, db)
        db.close()

        self.assertIsNone(response.recording_url)


class TestDuplicatePrevention(RecordingTestBase):
    def test_same_url_is_not_attached_to_two_calls(self):
        first_id = "1793333301.131253510"
        second_id = "1793333301.131253511"
        self.add_call(first_id)
        self.add_call(second_id)
        url = storage_url(first_id)

        db = self.db()
        first = self.load_call(db, first_id)
        second = self.load_call(db, second_id)
        self.assertTrue(DooctiRecordingService.attach_recording(first, db, url))
        self.assertFalse(DooctiRecordingService.attach_recording(second, db, url))
        db.close()

        self.assertEqual(self.get_call(first_id).recording_url, url)
        self.assertIsNone(self.get_call(second_id).recording_url)

    def test_same_recording_id_with_different_url_is_rejected(self):
        first_id = "1793333301.131253512"
        second_id = "1793333301.131253513"
        self.add_call(first_id)
        self.add_call(second_id)
        rec_id = first_id

        db = self.db()
        first = self.load_call(db, first_id)
        second = self.load_call(db, second_id)
        self.assertTrue(
            DooctiRecordingService.attach_recording(
                first, db, storage_url(rec_id), recording_id=rec_id
            )
        )
        self.assertFalse(
            DooctiRecordingService.attach_recording(
                second,
                db,
                f"https://mirror.example.com/{rec_id}.mp3",
                recording_id=rec_id,
            )
        )
        db.close()

        self.assertIsNone(self.get_call(second_id).recording_url)

    def test_webhook_refuses_recording_owned_by_another_call(self):
        owner_id = "1793333301.131253514"
        target_id = "1793333301.131253515"
        self.add_call(owner_id)
        self.add_call(target_id, recording_url=None)
        url = storage_url(owner_id)

        db = self.db()
        owner = self.load_call(db, owner_id)
        DooctiRecordingService.attach_recording(owner, db, url)
        db.close()

        self.post_cdr(
            {
                "uniqueid": target_id,
                "caller": EXTENSION,
                "destination": "9876543210",
                "status": "COMPLETED",
                "duration": 30,
                "recording_path": url,
            }
        )

        self.assertIsNone(self.get_call(target_id).recording_url)
        self.assertEqual(self.get_call(owner_id).recording_url, url)


class TestLegacyRepair(RecordingTestBase):
    def test_moves_link_to_rightful_owner_without_deleting_rows(self):
        owner_id = "1793333301.131253520"
        wrong_id = "1793333301.131253521"
        self.add_call(owner_id)
        self.add_call(wrong_id, recording_url=storage_url(owner_id))

        db = self.db()
        repaired = DooctiRecordingService.repair_misassigned_recordings(db)
        db.close()

        self.assertEqual(repaired, 1)
        self.assertEqual(self.get_call(owner_id).recording_url, storage_url(owner_id))
        self.assertIsNone(self.get_call(wrong_id).recording_url)
        # Both call rows still exist - only the incorrect link moved.
        self.assertIsNotNone(self.get_call(owner_id))
        self.assertIsNotNone(self.get_call(wrong_id))

    def test_clears_wrong_link_when_owner_already_has_audio(self):
        owner_id = "1793333301.131253522"
        wrong_id = "1793333301.131253523"
        owner_url = "https://other.example.com/owner.mp3"
        self.add_call(owner_id, recording_url=owner_url)
        self.add_call(wrong_id, recording_url=storage_url(owner_id))

        db = self.db()
        DooctiRecordingService.repair_misassigned_recordings(db)
        db.close()

        self.assertEqual(self.get_call(owner_id).recording_url, owner_url)
        self.assertIsNone(self.get_call(wrong_id).recording_url)


class TestWebhookCallBatches(RecordingTestBase):
    def _outbound_payload(self, index):
        call_id = f"179333340{index}.13120000{index}"
        return {
            "uniqueid": call_id,
            "caller": EXTENSION,
            "station": EXTENSION,
            "destination": f"98765000{index:02d}",
            "status": "COMPLETED",
            "duration": 30 + index,
            "recording_path": storage_url(call_id),
            "recording_duration": 30 + index,
        }

    def _inbound_payload(self, index):
        call_id = f"179333350{index}.13120001{index}"
        return {
            "uniqueid": call_id,
            "caller": f"98766000{index:02d}",
            "destination": DID,
            "status": "COMPLETED",
            "duration": 20 + index,
            "recording_path": storage_url(call_id),
            "recording_duration": 20 + index,
        }

    def _assert_batch(self, payloads, direction):
        seen_urls = {}
        for index, payload in enumerate(payloads):
            self.post_cdr(payload)
            call = self.get_call(payload["uniqueid"])
            self.assertIsNotNone(call, payload["uniqueid"])
            self.assertEqual(call.call_direction, direction)
            self.assertEqual(call.recording_id, payload["uniqueid"])
            self.assertEqual(call.recording_url, payload["recording_path"])
            self.assertEqual(call.recording_duration_seconds, 30 + index if direction == "OUTBOUND" else 20 + index)
            self.assertNotIn(call.recording_url, seen_urls)
            seen_urls[call.recording_url] = payload["uniqueid"]

        self.assertEqual(len(seen_urls), 10)

    def test_ten_consecutive_outbound_calls_map_one_to_one(self):
        self._assert_batch([self._outbound_payload(i) for i in range(10)], "OUTBOUND")

    def test_ten_consecutive_inbound_calls_map_one_to_one(self):
        self._assert_batch([self._inbound_payload(i) for i in range(10)], "INBOUND")

    def test_delayed_recording_updates_exact_call_only(self):
        call_id = "1793333601.131200020"
        self.post_cdr(
            {
                "uniqueid": call_id,
                "caller": EXTENSION,
                "destination": "9876500099",
                "status": "COMPLETED",
                "duration": 42,
            }
        )
        self.assertIsNone(self.get_call(call_id).recording_url)

        self.post_cdr(
            {
                "uniqueid": call_id,
                "recording_path": storage_url(call_id),
                "recording_duration": 41,
                "status": "COMPLETED",
            }
        )

        call = self.get_call(call_id)
        self.assertEqual(call.recording_url, storage_url(call_id))
        self.assertEqual(call.recording_id, call_id)
        self.assertEqual(call.recording_duration_seconds, 41)
        self.assertEqual(self.count_calls(call_id), 1)

        # A second identical delivery must not create a duplicate artifact link.
        self.post_cdr(
            {
                "uniqueid": call_id,
                "recording_path": storage_url(call_id),
                "recording_duration": 41,
                "status": "COMPLETED",
            }
        )
        self.assertEqual(self.count_calls(call_id), 1)
        self.assertEqual(
            self.get_call(call_id).recording_url, storage_url(call_id)
        )

    def test_concurrent_same_phone_calls_are_not_merged(self):
        phone = "9876500077"
        now = get_ist_now()
        db = self.db()
        db.add_all(
            [
                CallLog(
                    provider="DOOCTI",
                    provider_call_id=f"doocti_{EXTENSION}_{phone}_{i}",
                    from_number=EXTENSION,
                    to_number=phone,
                    call_status="CONNECTING",
                    call_direction="OUTBOUND",
                    duration_seconds=0,
                    started_at=now,
                    created_at=now,
                )
                for i in range(2)
            ]
        )
        db.commit()
        db.close()

        first_id = "1793333701.131200030"
        second_id = "1793333701.131200031"
        self.post_cdr(
            {
                "uniqueid": first_id,
                "caller": EXTENSION,
                "destination": phone,
                "status": "COMPLETED",
                "duration": 31,
                "recording_path": storage_url(first_id),
            }
        )
        self.post_cdr(
            {
                "uniqueid": second_id,
                "caller": EXTENSION,
                "destination": phone,
                "status": "COMPLETED",
                "duration": 32,
                "recording_path": storage_url(second_id),
            }
        )

        first = self.get_call(first_id)
        second = self.get_call(second_id)
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(first.recording_url, storage_url(first_id))
        self.assertEqual(second.recording_url, storage_url(second_id))
        self.assertNotEqual(first.id, second.id)

        db = self.db()
        synthetic = (
            db.query(CallLog)
            .filter(CallLog.provider_call_id.like(f"doocti_{EXTENSION}_{phone}_%"))
            .all()
        )
        self.assertEqual(len(synthetic), 2)
        self.assertTrue(all(c.recording_url is None for c in synthetic))
        db.close()


if __name__ == "__main__":
    unittest.main()
