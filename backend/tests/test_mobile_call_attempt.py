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

    def test_inbound_mobile_call_stores_customer_as_caller(self):
        call = self._attempt(
            client_call_id="SIM_INBOUND_1",
            call_direction="INBOUND",
            call_status="MISSED",
            duration_seconds=0,
        )
        self.assertEqual(call.call_direction, "INBOUND")
        self.assertEqual(call.from_number, self.phone)
        self.assertEqual(call.to_number, "+919111122233")

    def test_inbound_direction_is_not_overwritten_when_retry_omits_it(self):
        inbound = self._attempt(
            client_call_id="SIM_INBOUND_KEEP",
            call_direction="INBOUND",
            call_status="MISSED",
            duration_seconds=0,
        )
        # A legacy/partial retry without call_direction must keep the native
        # INBOUND value and must not flip the caller/callee numbers.
        retried = self._attempt(
            client_call_id="SIM_INBOUND_KEEP",
            call_direction=None,
            call_status="COMPLETED",
            duration_seconds=11,
            ended_at=datetime.now(),
        )
        self.assertEqual(retried.id, inbound.id)
        self.assertEqual(retried.call_direction, "INBOUND")
        self.assertEqual(retried.from_number, self.phone)
        self.assertEqual(retried.to_number, "+919111122233")

    def test_new_legacy_manual_call_without_direction_keeps_outbound_default(self):
        # Non-device manual logging (no SIM/native metadata) keeps its historic
        # behaviour. Only device rows are required to prove a direction.
        call = self._attempt(
            client_call_id="SIM_LEGACY_DEFAULT",
            call_direction=None,
            call_status="COMPLETED",
            duration_seconds=5,
            ended_at=datetime.now(),
            call_source=None,
            sim_label=None,
            sim_account_id=None,
        )
        self.assertEqual(call.call_direction, "OUTBOUND")
        self.assertEqual(call.provider, "DIRECT_DIAL")

    def test_new_mobile_call_without_direction_is_rejected(self):
        with self.assertRaises(ValueError):
            self._attempt(
                client_call_id="SIM_MISSING_DIRECTION",
                call_direction=None,
                call_status="COMPLETED",
                duration_seconds=5,
                ended_at=datetime.now(),
            )
        self.assertEqual(self.db.query(CallLog).count(), 0)

    def test_new_mobile_call_with_unknown_direction_is_rejected(self):
        with self.assertRaises(ValueError):
            self._attempt(
                client_call_id="SIM_UNKNOWN_DIRECTION",
                call_direction="UNKNOWN",
                call_status="COMPLETED",
                duration_seconds=5,
                ended_at=datetime.now(),
            )
        self.assertEqual(self.db.query(CallLog).count(), 0)

    def test_native_history_row_without_direction_is_rejected(self):
        with self.assertRaises(ValueError):
            self._attempt(
                client_call_id=None,
                native_call_reference="MOBILE_DEVICE_1_7777",
                call_direction=None,
                call_status="COMPLETED",
                duration_seconds=5,
                ended_at=datetime.now(),
            )
        self.assertEqual(self.db.query(CallLog).count(), 0)

    def test_all_incoming_types_store_inbound(self):
        for index, status in enumerate(("COMPLETED", "MISSED", "REJECTED")):
            call = self._attempt(
                client_call_id=f"SIM_INCOMING_{index}",
                call_direction="INBOUND",
                call_status=status,
                duration_seconds=10 if status == "COMPLETED" else 0,
                ended_at=datetime.now(),
            )
            self.assertEqual(call.call_direction, "INBOUND")
            self.assertEqual(call.from_number, self.phone)

    def test_all_outgoing_outcomes_store_outbound(self):
        for index, status in enumerate(("COMPLETED", "NO_ANSWER")):
            call = self._attempt(
                client_call_id=f"SIM_OUTGOING_{index}",
                call_direction="OUTBOUND",
                call_status=status,
                duration_seconds=10 if status == "COMPLETED" else 0,
                ended_at=datetime.now(),
            )
            self.assertEqual(call.call_direction, "OUTBOUND")
            self.assertEqual(call.to_number, self.phone)

    def test_inbound_is_not_overwritten_by_a_later_outbound_retry(self):
        inbound = self._attempt(
            client_call_id="SIM_INBOUND_STICKY",
            call_direction="INBOUND",
            call_status="MISSED",
            duration_seconds=0,
        )
        retried = self._attempt(
            client_call_id="SIM_INBOUND_STICKY",
            call_direction="OUTBOUND",
            call_status="COMPLETED",
            duration_seconds=9,
            ended_at=datetime.now(),
        )
        self.assertEqual(retried.id, inbound.id)
        self.assertEqual(retried.call_direction, "INBOUND")
        self.assertEqual(retried.from_number, self.phone)
        self.assertEqual(retried.to_number, "+919111122233")

    def test_outbound_row_can_be_corrected_to_inbound_by_native_evidence(self):
        wrong = self._attempt(
            client_call_id="SIM_CORRECT_ME",
            call_direction="OUTBOUND",
            call_status="COMPLETED",
            duration_seconds=9,
            ended_at=datetime.now(),
        )
        fixed = self._attempt(
            client_call_id="SIM_CORRECT_ME",
            call_direction="INBOUND",
            call_status="COMPLETED",
            duration_seconds=9,
            ended_at=datetime.now(),
        )
        self.assertEqual(fixed.id, wrong.id)
        self.assertEqual(fixed.call_direction, "INBOUND")
        self.assertEqual(fixed.from_number, self.phone)
        self.assertEqual(fixed.to_number, "+919111122233")

    def test_native_history_reference_is_idempotent(self):
        first = self._attempt(
            client_call_id=None,
            native_call_reference="MOBILE_DEVICE_1_9988",
            call_status="COMPLETED",
            duration_seconds=18,
            ended_at=datetime.now(),
        )
        second = self._attempt(
            client_call_id=None,
            native_call_reference="MOBILE_DEVICE_1_9988",
            call_status="COMPLETED",
            duration_seconds=18,
            ended_at=datetime.now(),
        )
        self.assertEqual(first.id, second.id)
        self.assertEqual(self.db.query(CallLog).count(), 1)

    def test_native_history_reuses_the_in_app_tracked_attempt(self):
        tracked = self._attempt(
            client_call_id="SIM_TRACKED_1",
            current_employee_id=7,
        )
        tracked_id = tracked.id

        native = self._attempt(
            client_call_id=None,
            native_call_reference="MOBILE_DEVICE_7_4242",
            current_employee_id=7,
            call_status="COMPLETED",
            duration_seconds=33,
            started_at=datetime.now(),
            ended_at=datetime.now(),
        )

        self.assertEqual(native.id, tracked_id)
        self.assertEqual(native.call_status, "COMPLETED")
        self.assertEqual(native.duration_seconds, 33)
        self.assertEqual(self.db.query(CallLog).count(), 1)

    def test_late_live_result_reuses_the_native_history_row(self):
        native = self._attempt(
            client_call_id=None,
            native_call_reference="MOBILE_DEVICE_9_5151",
            current_employee_id=9,
            call_status="COMPLETED",
            duration_seconds=24,
            started_at=datetime.now(),
            ended_at=datetime.now(),
        )
        native_id = native.id

        late_live = self._attempt(
            client_call_id="SIM_LATE_9",
            native_call_reference="MOBILE_DEVICE_9_5151",
            current_employee_id=9,
            call_status="COMPLETED",
            duration_seconds=24,
            started_at=datetime.now(),
            ended_at=datetime.now(),
        )

        self.assertEqual(late_live.id, native_id)
        self.assertEqual(self.db.query(CallLog).count(), 1)


if __name__ == "__main__":
    unittest.main()

