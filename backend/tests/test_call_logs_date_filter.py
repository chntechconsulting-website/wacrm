import os
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
import models  # noqa: F401 - register every model/table for create_all
from models.call_log import CallLog
from models.employee import Employee
from models.user import User
from routers.ivr import list_call_logs


class CallLogDateFilterTest(unittest.TestCase):
    """Inclusive date-range filtering for GET /ivr/calls."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        db_path = os.path.join(cls.temp_dir.name, "call_log_date_filter_test.db")
        cls.engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

        db = cls.Session()
        db.add_all([
            User(id=1, username="admin", hashed_password="x", role="ADMIN",
                 department="ADMINISTRATION", is_active=True),
            User(id=2, username="sales_exec", hashed_password="x", role="SALES_EXECUTIVE",
                 department="SALES", is_active=True),
        ])
        db.add_all([
            Employee(id=1, user_id=1, name="System Administrator", email="admin@test.local",
                     username="admin", role="ADMIN", department="ADMINISTRATION",
                     status="ACTIVE"),
            Employee(id=2, user_id=2, name="Sales Executive", email="sales@test.local",
                     username="sales_exec", role="SALES_EXECUTIVE", department="SALES",
                     status="ACTIVE", manager_id=1),
        ])

        # (id, employee_id, status, duration, started_at, created_at)
        # started_at is the timestamp shown by the Call Logs table. When it is
        # absent the endpoint must fall back to created_at.
        calls = [
            (1, 2, "COMPLETED", 10, datetime(2026, 10, 1, 0, 0, 0), datetime(2026, 10, 1, 0, 0, 0)),
            (2, 2, "COMPLETED", 20, datetime(2026, 10, 1, 23, 59, 59), datetime(2026, 10, 1, 23, 59, 59)),
            (3, 1, "MISSED", 0, datetime(2026, 10, 2, 0, 0, 0), datetime(2026, 10, 2, 0, 0, 0)),
            (4, 1, "COMPLETED", 30, datetime(2026, 9, 30, 23, 59, 59), datetime(2026, 9, 30, 23, 59, 59)),
            (5, 1, "FAILED", 0, None, datetime(2026, 10, 10, 12, 0, 0)),
            (6, 2, "COMPLETED", 40, datetime(2026, 10, 3, 9, 0, 0), datetime(2026, 10, 5, 18, 0, 0)),
            (7, 2, "COMPLETED", 50, datetime(2026, 10, 1, 12, 0, 0), datetime(2026, 10, 1, 12, 0, 0)),
        ]
        for call_id, emp_id, status, duration, started_at, created_at in calls:
            db.add(CallLog(
                id=call_id,
                employee_id=emp_id,
                provider="DOOCTI",
                provider_call_id=f"date-filter-{call_id}",
                from_number="1282",
                to_number=f"90000000{call_id:02d}",
                call_status=status,
                call_direction="OUTBOUND",
                duration_seconds=duration,
                started_at=started_at,
                created_at=created_at,
            ))
        db.commit()
        db.close()

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        cls.temp_dir.cleanup()

    def setUp(self):
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def _user(self, username):
        return self.db.query(User).filter(User.username == username).first()

    def _list(self, username, **params):
        return list_call_logs(
            response=Response(),
            db=self.db,
            current_user=self._user(username),
            **params,
        )

    @staticmethod
    def _ids(body):
        return {item.id for item in body.items}

    def test_01_date_range_is_inclusive_on_both_boundaries(self):
        body = self._list("admin", start_date="2026-10-01", end_date="2026-10-01", limit=50)
        self.assertEqual(body.total, 3)
        self.assertEqual(self._ids(body), {1, 2, 7})

        body = self._list("admin", start_date="2026-10-01", end_date="2026-10-02", limit=50)
        self.assertEqual(body.total, 4)
        self.assertEqual(self._ids(body), {1, 2, 3, 7})

    def test_02_start_and_end_dates_can_be_used_independently(self):
        start_only = self._list("admin", start_date="2026-10-02", limit=50)
        self.assertEqual(self._ids(start_only), {3, 5, 6})

        end_only = self._list("admin", end_date="2026-10-01", limit=50)
        self.assertEqual(self._ids(end_only), {1, 2, 4, 7})

    def test_03_started_at_is_used_and_created_at_is_the_fallback(self):
        # Call 6 was created on 5 Oct but happened on 3 Oct (the visible date).
        oct_3 = self._list("admin", start_date="2026-10-03", end_date="2026-10-03", limit=50)
        self.assertEqual(self._ids(oct_3), {6})

        # Call 5 has no started_at, so its created_at date is used.
        oct_10 = self._list("admin", start_date="2026-10-10", end_date="2026-10-10", limit=50)
        self.assertEqual(self._ids(oct_10), {5})
        self.assertEqual(oct_10.total, 1)

    def test_04_metrics_cover_the_filtered_set_across_pages(self):
        body = self._list("admin", start_date="2026-10-01", end_date="2026-10-01", page=1, limit=1)
        self.assertEqual(body.total, 3)
        self.assertEqual(len(body.items), 1)
        self.assertEqual(body.metrics.total_calls, 3)
        self.assertEqual(body.metrics.connected_calls, 3)
        self.assertEqual(body.metrics.missed_calls, 0)
        self.assertEqual(body.metrics.total_duration_seconds, 80)
        self.assertEqual(body.metrics.avg_duration_seconds, 27)

    def test_05_existing_employee_scope_is_preserved_under_date_filter(self):
        own = self._list("sales_exec", start_date="2026-10-01", end_date="2026-10-02", limit=50)
        self.assertEqual(self._ids(own), {1, 2, 7})

        with self.assertRaises(HTTPException) as ctx:
            self._list("sales_exec", employee_id=1, start_date="2026-10-01")
        self.assertEqual(ctx.exception.status_code, 403)

    def test_06_invalid_or_reversed_date_ranges_are_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            self._list("admin", start_date="10/01/2026")
        self.assertEqual(ctx.exception.status_code, 400)

        with self.assertRaises(HTTPException) as ctx:
            self._list("admin", end_date="2026-13-01")
        self.assertEqual(ctx.exception.status_code, 400)

        with self.assertRaises(HTTPException) as ctx:
            self._list("admin", start_date="2026-10-02", end_date="2026-10-01")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_07_empty_date_values_mean_no_date_filter(self):
        body = self._list("admin", start_date="", end_date="   ", limit=50)
        self.assertEqual(body.total, 7)
        self.assertEqual(self._ids(body), {1, 2, 3, 4, 5, 6, 7})

    def test_08_admin_department_filter_combines_with_date_range(self):
        body = self._list(
            "admin",
            department="SALES",
            start_date="2026-10-01",
            end_date="2026-10-02",
            limit=50,
        )
        self.assertEqual(self._ids(body), {1, 2, 7})
        self.assertEqual(body.total, 3)


if __name__ == "__main__":
    unittest.main()
