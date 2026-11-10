"""Regression tests for duplicate mobile/SIM call-log ingestion.

A real Android call can reach the CRM through two paths:

* the live in-app tracker (client id ``SIM_...``), and
* the device call-history sync (client id ``MOBILE_<androidId>_<callLogId>``).

Both paths must resolve to exactly one ``call_logs`` row for one physical
call, including when the live result was produced before Android wrote its
call-log row and therefore has no native reference.
"""

import os
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from integrations.ivr.service import IVRService
from models.call_log import CallLog


PHONE = "+919876543210"
EMPLOYEE_PHONE = "+919111122233"
EMPLOYEE_ID = 11
START = datetime(2026, 11, 10, 15, 12, 0)


class MobileCallDedupeTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        CallLog.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _log(self, **overrides):
        values = dict(
            db=self.db,
            current_employee_id=EMPLOYEE_ID,
            customer_phone=PHONE,
            employee_phone=EMPLOYEE_PHONE,
            call_status="COMPLETED",
            duration_seconds=12,
            call_direction="OUTBOUND",
            started_at=START,
            ended_at=START + timedelta(seconds=12),
            call_source="MOBILE_SIM",
            sim_account_id="subId:2",
            sim_label="Office SIM",
        )
        values.update(overrides)
        return IVRService.log_manual_call(**values)

    def _rows(self):
        return self.db.query(CallLog).order_by(CallLog.id).all()

    def test_history_first_then_refless_live_result_reuses_history_row(self):
        # Reproduces the reported duplicate: the pre-call attempt POST failed
        # (or the app was killed), the live result was built before Android
        # exposed its call-log row, and history sync logged the call first.
        history = self._log(
            client_call_id="MOBILE_DEVICE_11_5001",
            native_call_reference="MOBILE_DEVICE_11_5001",
            call_status="NO_ANSWER",
            duration_seconds=0,
            ended_at=START + timedelta(seconds=8),
        )
        live = self._log(
            client_call_id="SIM_LIVE_5001",
            call_status="NO_ANSWER",
            duration_seconds=0,
            ended_at=START + timedelta(seconds=8),
        )

        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(live.id, history.id)
        self.assertEqual(rows[0].provider, "MOBILE_SIM")
        self.assertEqual(rows[0].call_direction, "OUTBOUND")
        self.assertEqual(rows[0].call_status, "NO_ANSWER")
        self.assertEqual(rows[0].duration_seconds, 0)
        self.assertEqual(rows[0].employee_id, EMPLOYEE_ID)
        self.assertEqual(
            rows[0].native_call_reference, "MOBILE_DEVICE_11_5001"
        )

    def test_refless_live_first_then_history_attaches_native_reference(self):
        live = self._log(
            client_call_id="SIM_LIVE_5002",
            call_status="COMPLETED",
            duration_seconds=21,
            ended_at=START + timedelta(seconds=21),
        )
        history = self._log(
            client_call_id="MOBILE_DEVICE_11_5002",
            native_call_reference="MOBILE_DEVICE_11_5002",
            call_status="COMPLETED",
            duration_seconds=21,
            ended_at=START + timedelta(seconds=21),
        )

        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(history.id, live.id)
        self.assertEqual(
            rows[0].native_call_reference, "MOBILE_DEVICE_11_5002"
        )
        self.assertEqual(rows[0].duration_seconds, 21)

    def test_two_calls_same_number_with_native_refs_stay_separate(self):
        first_start = START
        second_start = START + timedelta(seconds=30)
        first_live = self._log(
            client_call_id="SIM_LIVE_A",
            native_call_reference="MOBILE_DEVICE_11_6001",
            call_status="COMPLETED",
            duration_seconds=12,
            started_at=first_start,
            ended_at=first_start + timedelta(seconds=12),
        )
        second_live = self._log(
            client_call_id="SIM_LIVE_B",
            native_call_reference="MOBILE_DEVICE_11_6002",
            call_status="COMPLETED",
            duration_seconds=25,
            started_at=second_start,
            ended_at=second_start + timedelta(seconds=25),
        )

        first_history = self._log(
            client_call_id="MOBILE_DEVICE_11_6001",
            native_call_reference="MOBILE_DEVICE_11_6001",
            call_status="COMPLETED",
            duration_seconds=12,
            started_at=first_start,
            ended_at=first_start + timedelta(seconds=12),
        )
        second_history = self._log(
            client_call_id="MOBILE_DEVICE_11_6002",
            native_call_reference="MOBILE_DEVICE_11_6002",
            call_status="COMPLETED",
            duration_seconds=25,
            started_at=second_start,
            ended_at=second_start + timedelta(seconds=25),
        )

        rows = self._rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(first_history.id, first_live.id)
        self.assertEqual(second_history.id, second_live.id)
        self.assertNotEqual(first_live.id, second_live.id)
        self.assertEqual(
            [row.native_call_reference for row in rows],
            ["MOBILE_DEVICE_11_6001", "MOBILE_DEVICE_11_6002"],
        )
        self.assertEqual([row.duration_seconds for row in rows], [12, 25])
        self.assertTrue(all(row.call_direction == "OUTBOUND" for row in rows))

    def test_two_calls_same_number_without_refs_use_closest_start(self):
        first_start = START
        # 12 seconds apart: close enough to require disambiguation, far enough
        # that the closest start is provable.
        second_start = START + timedelta(seconds=12)
        self._log(
            client_call_id="SIM_LIVE_C",
            call_status="NO_ANSWER",
            duration_seconds=0,
            started_at=first_start,
            ended_at=first_start + timedelta(seconds=5),
        )
        self._log(
            client_call_id="SIM_LIVE_D",
            call_status="NO_ANSWER",
            duration_seconds=0,
            started_at=second_start,
            ended_at=second_start + timedelta(seconds=5),
        )

        first_history = self._log(
            client_call_id="MOBILE_DEVICE_11_7001",
            native_call_reference="MOBILE_DEVICE_11_7001",
            call_status="NO_ANSWER",
            duration_seconds=0,
            started_at=first_start,
            ended_at=first_start + timedelta(seconds=5),
        )
        second_history = self._log(
            client_call_id="MOBILE_DEVICE_11_7002",
            native_call_reference="MOBILE_DEVICE_11_7002",
            call_status="NO_ANSWER",
            duration_seconds=0,
            started_at=second_start,
            ended_at=second_start + timedelta(seconds=5),
        )

        rows = self._rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(first_history.id, rows[0].id)
        self.assertEqual(second_history.id, rows[1].id)
        self.assertEqual(
            [row.native_call_reference for row in rows],
            ["MOBILE_DEVICE_11_7001", "MOBILE_DEVICE_11_7002"],
        )

    def test_inbound_missed_call_is_one_inbound_row(self):
        missed = self._log(
            client_call_id="MOBILE_DEVICE_11_8001",
            native_call_reference="MOBILE_DEVICE_11_8001",
            call_direction="INBOUND",
            call_status="MISSED",
            duration_seconds=0,
            ended_at=START + timedelta(seconds=3),
        )
        retried = self._log(
            client_call_id="MOBILE_DEVICE_11_8001",
            native_call_reference="MOBILE_DEVICE_11_8001",
            call_direction="INBOUND",
            call_status="MISSED",
            duration_seconds=0,
            ended_at=START + timedelta(seconds=3),
        )

        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(retried.id, missed.id)
        self.assertEqual(rows[0].call_direction, "INBOUND")
        self.assertEqual(rows[0].call_status, "MISSED")
        self.assertEqual(rows[0].from_number, PHONE)
        self.assertEqual(rows[0].to_number, EMPLOYEE_PHONE)
        self.assertEqual(rows[0].employee_id, EMPLOYEE_ID)

    def test_native_reference_is_persisted_and_database_unique(self):
        call = self._log(
            client_call_id="MOBILE_DEVICE_11_9001",
            native_call_reference="MOBILE_DEVICE_11_9001",
        )
        self.assertEqual(call.native_call_reference, "MOBILE_DEVICE_11_9001")

        self.db.add(
            CallLog(
                provider="MOBILE_SIM",
                provider_call_id="DIFFERENT_CLIENT_ID",
                native_call_reference="MOBILE_DEVICE_11_9001",
                from_number=EMPLOYEE_PHONE,
                to_number=PHONE,
                call_status="COMPLETED",
                call_direction="OUTBOUND",
                duration_seconds=12,
                started_at=START,
            )
        )
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()
        self.assertEqual(self.db.query(CallLog).count(), 1)

    def test_legacy_native_reference_in_provider_call_id_is_reused(self):
        legacy = self._log(
            client_call_id="MOBILE_DEVICE_11_9101",
            native_call_reference=None,
        )
        self.assertIsNone(legacy.native_call_reference)

        history = self._log(
            client_call_id="MOBILE_DEVICE_11_9101",
            native_call_reference="MOBILE_DEVICE_11_9101",
        )
        self.assertEqual(history.id, legacy.id)
        self.assertEqual(history.native_call_reference, "MOBILE_DEVICE_11_9101")
        self.assertEqual(self.db.query(CallLog).count(), 1)

    def test_native_duration_is_not_overwritten_by_refless_estimated_result(self):
        # The live tracker can estimate duration from OFFHOOK before Android
        # exposes the call-log row. The later/earlier native row is exact and
        # must remain authoritative after correlation.
        history = self._log(
            client_call_id="MOBILE_DEVICE_11_9201",
            native_call_reference="MOBILE_DEVICE_11_9201",
            call_status="COMPLETED",
            duration_seconds=18,
            ended_at=START + timedelta(seconds=18),
        )
        live = self._log(
            client_call_id="SIM_LIVE_9201",
            call_status="COMPLETED",
            duration_seconds=20,
            ended_at=START + timedelta(seconds=20),
        )

        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(live.id, history.id)
        self.assertEqual(rows[0].duration_seconds, 18)
        self.assertEqual(rows[0].call_status, "COMPLETED")
        self.assertEqual(rows[0].ended_at, START + timedelta(seconds=18))
        self.assertEqual(
            rows[0].native_call_reference, "MOBILE_DEVICE_11_9201"
        )

    def test_native_history_corrects_earlier_estimated_duration(self):
        live = self._log(
            client_call_id="SIM_LIVE_9202",
            call_status="COMPLETED",
            duration_seconds=20,
            ended_at=START + timedelta(seconds=20),
        )
        history = self._log(
            client_call_id="MOBILE_DEVICE_11_9202",
            native_call_reference="MOBILE_DEVICE_11_9202",
            call_status="COMPLETED",
            duration_seconds=18,
            ended_at=START + timedelta(seconds=18),
        )

        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(history.id, live.id)
        self.assertEqual(rows[0].duration_seconds, 18)
        self.assertEqual(rows[0].ended_at, START + timedelta(seconds=18))
        self.assertEqual(
            rows[0].native_call_reference, "MOBILE_DEVICE_11_9202"
        )

    def test_two_calls_with_close_durations_do_not_cross_merge(self):
        second_start = START + timedelta(seconds=12)
        first_live = self._log(
            client_call_id="SIM_LIVE_CLOSE_A",
            call_status="COMPLETED",
            duration_seconds=20,
            ended_at=START + timedelta(seconds=20),
        )
        second_live = self._log(
            client_call_id="SIM_LIVE_CLOSE_B",
            call_status="COMPLETED",
            duration_seconds=22,
            started_at=second_start,
            ended_at=second_start + timedelta(seconds=22),
        )
        first_history = self._log(
            client_call_id="MOBILE_DEVICE_11_9301",
            native_call_reference="MOBILE_DEVICE_11_9301",
            call_status="COMPLETED",
            duration_seconds=20,
            ended_at=START + timedelta(seconds=20),
        )
        second_history = self._log(
            client_call_id="MOBILE_DEVICE_11_9302",
            native_call_reference="MOBILE_DEVICE_11_9302",
            call_status="COMPLETED",
            duration_seconds=22,
            started_at=second_start,
            ended_at=second_start + timedelta(seconds=22),
        )

        rows = self._rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(first_history.id, first_live.id)
        self.assertEqual(second_history.id, second_live.id)
        self.assertEqual(
            [row.native_call_reference for row in rows],
            ["MOBILE_DEVICE_11_9301", "MOBILE_DEVICE_11_9302"],
        )
        self.assertEqual([row.duration_seconds for row in rows], [20, 22])


class MobileCallConcurrentIngestionTestCase(unittest.TestCase):
    """Live and history requests for one call must not both insert."""

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.engine = create_engine(
            f"sqlite:///{self.path}",
            connect_args={"check_same_thread": False, "timeout": 30},
        )
        CallLog.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self):
        self.engine.dispose()
        try:
            os.remove(self.path)
        except OSError:
            pass

    def _worker(self, barrier, results, errors, client_id):
        db = self.Session()
        try:
            barrier.wait(timeout=10)
            row = IVRService.log_manual_call(
                db=db,
                current_employee_id=EMPLOYEE_ID,
                customer_phone=PHONE,
                employee_phone=EMPLOYEE_PHONE,
                call_status="COMPLETED",
                duration_seconds=18,
                client_call_id=client_id,
                call_direction="OUTBOUND",
                started_at=START,
                ended_at=START + timedelta(seconds=18),
                call_source="MOBILE_SIM",
                sim_account_id="subId:2",
                native_call_reference="MOBILE_DEVICE_11_CONCURRENT",
            )
            results.append(row.id)
        except Exception as exc:  # pragma: no cover - diagnostic path
            errors.append(repr(exc))
        finally:
            db.close()

    def test_concurrent_live_and_history_create_one_row(self):
        barrier = threading.Barrier(2)
        results = []
        errors = []
        threads = [
            threading.Thread(
                target=self._worker,
                args=(barrier, results, errors, "SIM_LIVE_CONCURRENT"),
            ),
            threading.Thread(
                target=self._worker,
                args=(
                    barrier,
                    results,
                    errors,
                    "MOBILE_DEVICE_11_CONCURRENT",
                ),
            ),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)

        self.assertEqual(errors, [])
        check = self.Session()
        try:
            rows = check.query(CallLog).all()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].native_call_reference, "MOBILE_DEVICE_11_CONCURRENT")
            self.assertEqual(set(results), {rows[0].id})
        finally:
            check.close()


if __name__ == "__main__":
    unittest.main()
