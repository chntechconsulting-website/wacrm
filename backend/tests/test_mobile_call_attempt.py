import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from integrations.ivr.service import IVRService
from models.call_log import CallLog


class TestMobileCallAttemptLifecycle(unittest.TestCase):
    """The device flow must create one row, then update it in place."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        CallLog.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.call_id = "SIM_TEST_ATTEMPT"
        self.phone = "+919876543210"

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _attempt(self, **overrides):
        values = dict(
            db=self.db,
            current_employee_id=None,
            customer_phone=self.phone,
            employee_phone="+919111122233",
            call_status="INITIATED",
            duration_seconds=0,
            client_call_id=self.call_id,
            call_direction="OUTBOUND",
            started_at=datetime.now(),
            call_source="MOBILE_SIM",
            sim_label="Airtel SIM 2",
            sim_account_id="subId:2",
        )
        values.update(overrides)
        return IVRService.log_manual_call(**values)

    def test_attempt_is_pending_and_not_completed(self):
        call = self._attempt()
        self.assertEqual(call.call_status, "INITIATED")
        self.assertEqual(call.duration_seconds, 0)
        self.assertIsNone(call.answered_at)
        self.assertIsNone(call.ended_at)
        self.assertEqual(call.provider, "MOBILE_SIM")

    def test_final_result_updates_the_same_row_without_duplicate(self):
        attempt = self._attempt()
        attempt_id = attempt.id
        started = datetime.now() - timedelta(seconds=42)
        ended = datetime.now()

        final = self._attempt(
            call_status="COMPLETED",
            duration_seconds=42,
            started_at=started,
            ended_at=ended,
        )

        self.assertEqual(final.id, attempt_id)
        self.assertEqual(final.call_status, "COMPLETED")
        self.assertEqual(final.duration_seconds, 42)
        self.assertIsNotNone(final.answered_at)
        self.assertEqual(self.db.query(CallLog).count(), 1)

    def test_late_attempt_never_downgrades_a_completed_call(self):
        self._attempt()
        self._attempt(
            call_status="COMPLETED",
            duration_seconds=12,
            ended_at=datetime.now(),
        )

        late = self._attempt()
        self.assertEqual(late.call_status, "COMPLETED")
        self.assertEqual(late.duration_seconds, 12)

    def test_final_result_does_not_erase_an_existing_recording(self):
        self._attempt(recording_url="/uploads/recordings/1/call.mp3")
        final = self._attempt(
            call_status="COMPLETED",
            duration_seconds=9,
            recording_url=None,
            ended_at=datetime.now(),
        )
        self.assertEqual(final.recording_url, "/uploads/recordings/1/call.mp3")

    def test_unverified_mobile_status_is_failed_not_completed(self):
        call = self._attempt(call_status="SOMETHING_UNKNOWN")
        self.assertEqual(call.call_status, "FAILED")


if __name__ == "__main__":
    unittest.main()

