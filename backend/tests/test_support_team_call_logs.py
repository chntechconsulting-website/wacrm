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
from services.permission_service import get_support_team_call_scope

# Authoritative Support Team identity in this database:
#   Support Manager = Employee.id 11 (user "kumar")
#   Support Team members = 10 (ram), 11 (Kumar), 29 (Support Exec B)
# Employee/User timestamps are stored as naive UTC; call_logs.created_at is
# stored as naive IST (UTC+05:30).
TEAM_CREATED_UTC = datetime(2026, 10, 8, 8, 46, 19)
TEAM_CREATED_IST = datetime(2026, 10, 8, 14, 16, 19)
MEMBER_B_CREATED_UTC = datetime(2026, 10, 22, 12, 22, 46)
MEMBER_B_CREATED_IST = datetime(2026, 10, 22, 17, 52, 46)
MEMBER_A_CREATED_UTC = datetime(2026, 10, 8, 5, 59, 31)


class SupportTeamCallLogsTest(unittest.TestCase):
    """Strict Support Team scoping for GET /ivr/calls."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        db_path = os.path.join(cls.temp_dir.name, "support_team_calls_test.db")
        cls.engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

        db = cls.Session()
        db.add_all([
            User(id=1, username="admin", hashed_password="x", role="ADMIN",
                 department="ADMINISTRATION", is_active=True, created_at=datetime(2026, 9, 24, 12, 31, 13)),
            User(id=8, username="chnm030", hashed_password="x", role="SALES_MANAGER",
                 department="SALES", is_active=True, created_at=datetime(2026, 9, 30, 10, 34, 15)),
            User(id=9, username="chnm040", hashed_password="x", role="SALES_EXECUTIVE",
                 department="SALES", is_active=True, created_at=datetime(2026, 10, 1, 11, 29, 20)),
            User(id=10, username="chnm023", hashed_password="x", role="SUPPORT_EXECUTIVE",
                 department="SUPPORT", is_active=True, created_at=MEMBER_A_CREATED_UTC),
            User(id=11, username="kumar", hashed_password="x", role="SUPPORT_MANAGER",
                 department="SUPPORT", is_active=True, created_at=TEAM_CREATED_UTC),
            User(id=29, username="test_sup_b", hashed_password="x", role="SUPPORT_EXECUTIVE",
                 department="SUPPORT", is_active=True, created_at=MEMBER_B_CREATED_UTC),
        ])
        db.add_all([
            Employee(id=1, user_id=1, name="System Administrator", email="admin@test.local",
                     username="admin", role="ADMIN", department="ADMINISTRATION",
                     status="ACTIVE", created_at=datetime(2026, 9, 24, 12, 31, 13)),
            Employee(id=8, user_id=8, name="Gowtham", email="gowtham@test.local",
                     username="chnm030", role="SALES_MANAGER", department="SALES",
                     status="ACTIVE", manager_id=1, created_at=datetime(2026, 9, 30, 10, 34, 15)),
            Employee(id=9, user_id=9, name="Chandra Mohan", email="chandra@test.local",
                     username="chnm040", role="SALES_EXECUTIVE", department="SALES",
                     status="ACTIVE", manager_id=8, created_at=datetime(2026, 10, 1, 11, 29, 20)),
            Employee(id=10, user_id=10, name="ram", email="ram@test.local",
                     username="chnm023", role="SUPPORT_EXECUTIVE", department="SUPPORT",
                     status="ACTIVE", manager_id=11, created_at=MEMBER_A_CREATED_UTC),
            Employee(id=11, user_id=11, name="Kumar", email="kumar@test.local",
                     username="kumar", role="SUPPORT_MANAGER", department="SUPPORT",
                     status="ACTIVE", manager_id=1, created_at=TEAM_CREATED_UTC),
            Employee(id=29, user_id=29, name="Support Exec B", email="supb@test.local",
                     username="test_sup_b", role="SUPPORT_EXECUTIVE", department="SUPPORT",
                     status="ACTIVE", manager_id=11, created_at=MEMBER_B_CREATED_UTC),
        ])

        # (id, employee_id, direction, status, provider_call_id, created_at IST, duration)
        calls = [
            # Eligible support-team calls
            (1, 10, "OUTBOUND", "COMPLETED", "sup-visible-1", datetime(2026, 10, 8, 15, 0, 0), 120),
            (2, 10, "INBOUND", "ANSWERED", "sup-visible-2", datetime(2026, 10, 9, 10, 0, 0), 60),
            (3, 11, "OUTBOUND", "MISSED", "sup-visible-3", datetime(2026, 10, 9, 11, 0, 0), 0),
            (4, 29, "OUTBOUND", "COMPLETED", "sup-visible-4", datetime(2026, 10, 23, 10, 0, 0), 30),
            (5, 10, "OUTBOUND", "FAILED", "sup-visible-5", datetime(2026, 10, 10, 9, 0, 0), 0),
            # Historical call before team creation (13:00 IST > 08:46 naive,
            # but before the 14:16:19 IST cutoff after timezone conversion)
            (6, 10, "OUTBOUND", "COMPLETED", "sup-before-team", datetime(2026, 10, 8, 13, 0, 0), 500),
            # Different team
            (7, 9, "OUTBOUND", "COMPLETED", "sales-other-team", datetime(2026, 10, 8, 15, 30, 0), 200),
            # Unassigned / unidentifiable ownership
            (8, None, "INBOUND", "MISSED", "unassigned-inbound", datetime(2026, 10, 8, 15, 45, 0), 0),
            # Member B call before B joined the team (after team creation)
            (9, 29, "OUTBOUND", "COMPLETED", "sup-b-before-join", datetime(2026, 10, 20, 10, 0, 0), 300),
        ]
        for call_id, emp_id, direction, status, provider_call_id, created_at, duration in calls:
            db.add(CallLog(
                id=call_id,
                employee_id=emp_id,
                provider="DOOCTI",
                provider_call_id=provider_call_id,
                from_number="1282" if direction == "OUTBOUND" else f"900000000{call_id}",
                to_number=f"900000000{call_id}" if direction == "OUTBOUND" else "7969671855",
                call_status=status,
                call_direction=direction,
                duration_seconds=duration,
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

    # --------------------------------------------------------------- identity
    def test_01_support_team_identity_and_creation_timestamp(self):
        scope = get_support_team_call_scope(self._user("kumar"), self.db, None)
        self.assertIsNotNone(scope)
        self.assertEqual(scope["team_id"], 11)
        self.assertEqual(scope["team_manager_employee_id"], 11)
        self.assertEqual(scope["team_created_at_utc"], TEAM_CREATED_UTC)
        self.assertEqual(scope["team_created_at_ist"], TEAM_CREATED_IST)
        self.assertEqual(scope["employee_ids"], [10, 11, 29])
        self.assertEqual(scope["employee_cutoffs"][10], TEAM_CREATED_IST)
        self.assertEqual(scope["employee_cutoffs"][11], TEAM_CREATED_IST)
        self.assertEqual(scope["employee_cutoffs"][29], MEMBER_B_CREATED_IST)

    # ------------------------------------------------------- manager filtering
    def test_02_manager_sees_only_eligible_team_calls(self):
        body = self._list("kumar", limit=50)
        self.assertEqual(body.total, 5)
        self.assertEqual(self._ids(body), {1, 2, 3, 4, 5})
        # Explicitly prove the excluded cases.
        self.assertNotIn(6, self._ids(body))  # before team creation
        self.assertNotIn(7, self._ids(body))  # other team
        self.assertNotIn(8, self._ids(body))  # unassigned employee
        self.assertNotIn(9, self._ids(body))  # member joined later

    def test_03_metrics_use_the_same_team_filters(self):
        body = self._list("kumar", limit=2)  # metrics must cover all pages, not just page 1
        metrics = body.metrics
        self.assertEqual(metrics.total_calls, 5)
        self.assertEqual(metrics.connected_calls, 3)
        self.assertEqual(metrics.missed_calls, 2)
        self.assertEqual(metrics.total_duration_seconds, 210)
        self.assertEqual(metrics.avg_duration_seconds, 70)

    def test_04_pagination_preserves_team_scope_and_has_no_duplicates(self):
        all_ids = []
        totals = []
        for page in (1, 2, 3):
            body = self._list("kumar", page=page, limit=2)
            totals.append(body.total)
            all_ids.extend(item.id for item in body.items)
        self.assertEqual(totals, [5, 5, 5])
        self.assertEqual(len(all_ids), 5)
        self.assertEqual(len(set(all_ids)), 5)
        self.assertEqual(set(all_ids), {1, 2, 3, 4, 5})

    def test_05_direction_status_search_and_employee_filters_preserve_scope(self):
        inbound = self._list("kumar", direction="INBOUND", limit=50)
        self.assertEqual(self._ids(inbound), {2})

        outbound = self._list("kumar", direction="OUTBOUND", limit=50)
        self.assertEqual(self._ids(outbound), {1, 3, 4, 5})

        completed = self._list("kumar", call_status="Completed", limit=50)
        self.assertEqual(self._ids(completed), {1, 2, 4})

        search_visible = self._list("kumar", search="9000000005", limit=50)
        self.assertEqual(self._ids(search_visible), {5})
        self.assertEqual(search_visible.total, 1)

        # A search matching another team's call must not leak it.
        search_hidden = self._list("kumar", search="9000000007", limit=50)
        self.assertEqual(search_hidden.total, 0)
        self.assertEqual(search_hidden.items, [])

        by_provider = self._list("kumar", provider="DOOCTI", limit=50)
        self.assertEqual(self._ids(by_provider), {1, 2, 3, 4, 5})

        employee_10 = self._list("kumar", employee_id=10, limit=50)
        self.assertEqual(self._ids(employee_10), {1, 2, 5})

    def test_06_unauthorized_employee_filter_is_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            self._list("kumar", employee_id=9)
        self.assertEqual(ctx.exception.status_code, 403)

    # -------------------------------------------------------- own-scope users
    def test_07_support_executives_see_only_their_own_eligible_calls(self):
        exec_a = self._list("chnm023", limit=50)
        self.assertEqual(self._ids(exec_a), {1, 2, 5})
        self.assertEqual(exec_a.total, 3)

        exec_b = self._list("test_sup_b", limit=50)
        self.assertEqual(self._ids(exec_b), {4})
        self.assertEqual(exec_b.total, 1)

    # ---------------------------------------------------- unchanged behaviour
    def test_08_admin_keeps_company_wide_call_visibility(self):
        body = self._list("admin", limit=50)
        self.assertEqual(body.total, 9)
        self.assertEqual(self._ids(body), {1, 2, 3, 4, 5, 6, 7, 8, 9})

        # Admin employee filter must still include pre-team history.
        by_employee = self._list("admin", employee_id=10, limit=50)
        self.assertEqual(self._ids(by_employee), {1, 2, 5, 6})

    def test_09_other_teams_keep_existing_scope_including_unassigned_inbound(self):
        sales_manager = self._list("chnm030", limit=50)
        self.assertEqual(self._ids(sales_manager), {7, 8})
        self.assertEqual(sales_manager.total, 2)

        sales_exec = self._list("chnm040", limit=50)
        self.assertEqual(self._ids(sales_exec), {7, 8})
        self.assertEqual(sales_exec.total, 2)


if __name__ == "__main__":
    unittest.main()
