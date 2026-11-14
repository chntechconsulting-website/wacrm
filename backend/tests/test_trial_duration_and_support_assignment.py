"""Trial duration, Trial Support assignment and reminder coverage.

Isolated in-memory (or temp file) SQLite only. No live CRM record is read or
written.

Scenarios map 1:1 to the requested acceptance checks:
 1. 7 days  -> end date calculates correctly (start + 7).
 2. 14 days -> end date recalculates immediately on every change.
 3. Start date defaults to the current date (Asia/Kolkata).
 4. The selected Support employee receives the assignment, is projected in the
    customer profile and appears on Support Assigned Leads.
 5. Sales Manager and Support Employee receive the T-3 / T-1 / expiry-day
    reminders with every required field.
 6. Changing the trial duration updates the scheduled reminders without
    duplicating a notification.
 7. Expired / expiring-soon trials are identified correctly and the Sales and
    Support statuses are never overwritten.
 8. Existing Sales (WON) and Support (handoff) workflows stay unaffected.
 9. RBAC: Sales can read the Support dropdown, Support cannot change it, and
    non-Support employees cannot be assigned.
10. End-to-end HTTP: PUT /api/leads/{id} with trial_duration_days and GET
    /api/leads/trial/support-options.
"""

import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from types import SimpleNamespace

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401 - registers every model on Base.metadata
from database import Base, get_db
from models.audit_log import AuditLog  # noqa: F401
from models.employee import Employee
from models.lead import Lead, LeadAssignment
from models.notification import Notification
from models.user import User
from routers.leads import (
    build_lead_out,
    get_support_assigned_leads,
    get_trial_support_options,
    update_lead,
)
from schemas.lead import LeadUpdate
from services.auth import get_current_user
from services.permission_service import (
    get_support_authorized_lead_ids,
    is_support_lead_authorized,
)
from services.trial_reminder_service import check_and_send_trial_reminders
from utils.lead_status import (
    STATUS_WON,
    trial_status_for,
)
from utils.timezone import get_ist_now


class TrialDurationAndSupportAssignmentTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db = Session()
        self._phone_counter = 9600000000

        self.admin_user, self.admin_emp = self._make_person(
            "tds_admin", "ADMIN", "ADMINISTRATION"
        )
        self.sales_manager_user, self.sales_manager_emp = self._make_person(
            "tds_sales_mgr", "SALES_MANAGER", "SALES"
        )
        self.sales_exec_user, self.sales_exec_emp = self._make_person(
            "tds_sales_exec",
            "SALES_EXECUTIVE",
            "SALES",
            manager_emp=self.sales_manager_emp,
        )
        self.support_manager_user, self.support_manager_emp = self._make_person(
            "tds_support_mgr", "SUPPORT_MANAGER", "SUPPORT"
        )
        self.support_exec_user, self.support_exec_emp = self._make_person(
            "tds_support_exec",
            "SUPPORT_EXECUTIVE",
            "SUPPORT",
            manager_emp=self.support_manager_emp,
        )
        self.other_support_exec_user, self.other_support_exec_emp = self._make_person(
            "tds_other_support_exec",
            "SUPPORT_EXECUTIVE",
            "SUPPORT",
            manager_emp=self.support_manager_emp,
        )
        self.inactive_support_user, self.inactive_support_emp = self._make_person(
            "tds_inactive_support",
            "SUPPORT_EXECUTIVE",
            "SUPPORT",
            status="INACTIVE",
            manager_emp=self.support_manager_emp,
        )

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    # ------------------------------------------------------------------
    # Fixtures
    # ------------------------------------------------------------------
    def _make_person(self, username, role, department, status="ACTIVE", manager_emp=None):
        user = User(
            username=username,
            hashed_password="not-used-in-tests",
            role=role,
            department=department,
            is_active=status == "ACTIVE",
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        employee = Employee(
            user_id=user.id,
            manager_id=manager_emp.id if manager_emp else None,
            department=department,
            name=username.replace("_", " ").title(),
            email=f"{username}@example.test",
            phone="9800000000",
            username=username,
            role=role,
            status=status,
        )
        self.db.add(employee)
        self.db.commit()
        self.db.refresh(employee)
        return user, employee

    def _make_lead(self, status="NEW", assigned_to=None):
        self._phone_counter += 1
        lead = Lead(
            name=f"Trial Duration Lead {self._phone_counter}",
            phone=str(self._phone_counter),
            email=f"tds{self._phone_counter}@example.com",
            company=f"Trial Duration Co {self._phone_counter}",
            source="MANUAL",
            status=status,
            assigned_to=assigned_to if assigned_to is not None else self.sales_exec_emp.id,
        )
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        return lead

    def _set_trial(self, lead, duration_days, user=None, start_date=None, support_id="omit"):
        """Drive PUT /leads/{id} exactly like the modal does."""
        payload = {
            "status": "TRIAL",
            "trial_duration_days": duration_days,
        }
        if start_date is not None:
            payload["trial_start_date"] = start_date
        if support_id != "omit":
            payload["trial_support_employee_id"] = support_id
        return update_lead(
            lead_id=lead.id,
            lead_in=LeadUpdate(**payload),
            db=self.db,
            current_user=user or self.admin_user,
        )

    def _today(self):
        return get_ist_now().date()

    # ------------------------------------------------------------------
    # 1 + 3. 7 days calculates the end date; start defaults to today
    # ------------------------------------------------------------------
    def test_01_seven_days_calculates_end_date_and_start_defaults_to_today(self):
        lead = self._make_lead()
        today = self._today()

        projection = self._set_trial(lead, 7)
        self.db.refresh(lead)

        self.assertEqual(lead.trial_start_date, today)
        self.assertEqual(lead.trial_end_date, today + timedelta(days=7))
        self.assertEqual(projection.trial_start_date, today)
        self.assertEqual(projection.trial_end_date, today + timedelta(days=7))
        self.assertEqual(projection.trial_duration_days, 7)
        self.assertEqual(projection.status, "TRIAL")
        self.assertEqual(projection.trial_days_remaining, 7)

    # ------------------------------------------------------------------
    # 2. 14 days recalculates immediately (and again when changed)
    # ------------------------------------------------------------------
    def test_02_duration_change_recalculates_end_date_immediately(self):
        lead = self._make_lead()
        today = self._today()

        self._set_trial(lead, 14)
        self.db.refresh(lead)
        self.assertEqual(lead.trial_end_date, today + timedelta(days=14))

        # Same start date, different duration -> only the end date moves.
        self._set_trial(lead, 3)
        self.db.refresh(lead)
        self.assertEqual(lead.trial_start_date, today)
        self.assertEqual(lead.trial_end_date, today + timedelta(days=3))

        projection = build_lead_out(lead, self.admin_user, self.db)
        self.assertEqual(projection.trial_duration_days, 3)
        self.assertEqual(projection.trial_end_date, today + timedelta(days=3))

    # ------------------------------------------------------------------
    # 9a. Invalid durations are rejected by the server
    # ------------------------------------------------------------------
    def test_03_invalid_trial_durations_are_rejected(self):
        lead = self._make_lead()
        for bad in (0, -5, 500):
            with self.assertRaises(HTTPException) as ctx:
                self._set_trial(lead, bad)
            self.assertEqual(ctx.exception.status_code, 400)

        # A legacy request without a duration must still be accepted and must
        # never recalculate the existing end date.
        self.db.rollback()
        lead.trial_start_date = date(2026, 1, 1)
        lead.trial_end_date = date(2026, 1, 15)
        self.db.commit()
        update_lead(
            lead_id=lead.id,
            lead_in=LeadUpdate(status="TRIAL"),
            db=self.db,
            current_user=self.admin_user,
        )
        self.db.refresh(lead)
        self.assertEqual(lead.trial_end_date, date(2026, 1, 15))

    # ------------------------------------------------------------------
    # 4. Support employee assignment is saved and displayed
    # ------------------------------------------------------------------
    def test_04_support_employee_is_assigned_and_projected(self):
        lead = self._make_lead()
        self._set_trial(lead, 14, support_id=self.support_exec_emp.id)
        self.db.refresh(lead)

        self.assertEqual(lead.trial_support_employee_id, self.support_exec_emp.id)

        projection = build_lead_out(lead, self.admin_user, self.db)
        self.assertEqual(projection.trial_support_employee_id, self.support_exec_emp.id)
        self.assertEqual(
            projection.trial_support_employee_name, self.support_exec_emp.name
        )
        # The customer profile "Support Assigned To" projection picks it up.
        self.assertEqual(projection.support_assigned_to, self.support_exec_emp.id)
        self.assertEqual(
            projection.support_assigned_to_name, self.support_exec_emp.name
        )
        # The Sales owner is untouched.
        self.assertEqual(projection.assigned_to, self.sales_exec_emp.id)
        self.assertEqual(
            projection.assigned_employee_name, self.sales_exec_emp.name
        )

        # Auditable assignment row (reuses the existing LeadAssignment table).
        methods = [
            (a.assignment_method, a.assigned_to) for a in lead.assignments
        ]
        self.assertIn(("TRIAL_SUPPORT", self.support_exec_emp.id), methods)

        # Re-submitting the same employee must not duplicate the history row.
        self._set_trial(lead, 14, support_id=self.support_exec_emp.id)
        self.db.refresh(lead)
        rows = [
            a for a in lead.assignments
            if a.assignment_method == "TRIAL_SUPPORT"
            and a.assigned_to == self.support_exec_emp.id
        ]
        self.assertEqual(len(rows), 1)

    def test_04b_support_assignment_pending_when_not_selected(self):
        lead = self._make_lead()
        self._set_trial(lead, 7, support_id=None)
        self.db.refresh(lead)
        self.assertIsNone(lead.trial_support_employee_id)

        projection = build_lead_out(lead, self.admin_user, self.db)
        self.assertIsNone(projection.trial_support_employee_id)
        self.assertIsNone(projection.trial_support_employee_name)
        self.assertIsNone(projection.support_assigned_to)

        # Explicitly clearing an existing assignment returns it to pending.
        self._set_trial(lead, 7, support_id=self.support_exec_emp.id)
        self.db.refresh(lead)
        self.assertEqual(lead.trial_support_employee_id, self.support_exec_emp.id)
        self._set_trial(lead, 7, support_id=None)
        self.db.refresh(lead)
        self.assertIsNone(lead.trial_support_employee_id)

    # ------------------------------------------------------------------
    # 9b. Only active Support Executives can be assigned; RBAC on the API
    # ------------------------------------------------------------------
    def test_05_only_active_support_executives_can_be_assigned(self):
        lead = self._make_lead()

        with self.assertRaises(HTTPException) as ctx:
            self._set_trial(lead, 14, support_id=self.sales_exec_emp.id)
        self.assertEqual(ctx.exception.status_code, 400)

        with self.assertRaises(HTTPException) as ctx:
            self._set_trial(lead, 14, support_id=self.support_manager_emp.id)
        self.assertEqual(ctx.exception.status_code, 400)

        with self.assertRaises(HTTPException) as ctx:
            self._set_trial(lead, 14, support_id=self.inactive_support_emp.id)
        self.assertEqual(ctx.exception.status_code, 400)

        with self.assertRaises(HTTPException) as ctx:
            self._set_trial(lead, 14, support_id=999999)
        self.assertEqual(ctx.exception.status_code, 404)

        self.db.refresh(lead)
        self.assertIsNone(lead.trial_support_employee_id)

    def test_05b_support_users_cannot_change_the_trial_support_assignment(self):
        lead = self._make_lead()
        with self.assertRaises(HTTPException) as ctx:
            self._set_trial(
                lead, 14, user=self.support_exec_user,
                support_id=self.other_support_exec_emp.id,
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.db.refresh(lead)
        self.assertIsNone(lead.trial_support_employee_id)

    def test_05c_support_options_endpoint_is_sales_and_admin_only(self):
        options = get_trial_support_options(
            db=self.db, current_user=self.sales_exec_user
        )
        ids = [o["id"] for o in options]
        self.assertIn(self.support_exec_emp.id, ids)
        self.assertIn(self.other_support_exec_emp.id, ids)
        # No hardcoded ids/names: only active Support Executives come back.
        self.assertNotIn(self.inactive_support_emp.id, ids)
        self.assertNotIn(self.support_manager_emp.id, ids)
        self.assertNotIn(self.sales_exec_emp.id, ids)
        for option in options:
            self.assertEqual(option["department"], "SUPPORT")
            self.assertEqual(option["status"], "ACTIVE")

        options_mgr = get_trial_support_options(
            db=self.db, current_user=self.sales_manager_user
        )
        self.assertIn(self.support_exec_emp.id, [o["id"] for o in options_mgr])

        with self.assertRaises(HTTPException) as ctx:
            get_trial_support_options(
                db=self.db, current_user=self.support_exec_user
            )
        self.assertEqual(ctx.exception.status_code, 403)

    # ------------------------------------------------------------------
    # 4b. Support Assigned Leads visibility
    # ------------------------------------------------------------------
    def test_06_trial_support_assignment_appears_on_support_assigned_leads(self):
        lead = self._make_lead()
        self._set_trial(lead, 14, support_id=self.support_exec_emp.id)

        # Admin view of the Support queue contains the trial customer with the
        # selected Support employee.
        page = get_support_assigned_leads(
            search=None,
            status=None,
            priority=None,
            source=None,
            assigned_agent_id=None,
            skip=0,
            limit=50,
            db=self.db,
            current_user=self.admin_user,
        )
        item = next((i for i in page["items"] if i["lead_id"] == lead.id), None)
        self.assertIsNotNone(item, "Trial customer missing from Support queue")
        self.assertEqual(
            item["assigned_support_executive_id"], self.support_exec_emp.id
        )
        self.assertEqual(
            item["assigned_support_executive_name"], self.support_exec_emp.name
        )
        self.assertEqual(item["trial_status"], "TRIAL_ACTIVE")

        # The assigned Support employee's own queue contains the lead; the
        # other Support employee's queue does not.
        authorized = get_support_authorized_lead_ids(self.support_exec_user, self.db)
        self.assertIn(lead.id, authorized)
        other_authorized = get_support_authorized_lead_ids(
            self.other_support_exec_user, self.db
        )
        self.assertNotIn(lead.id, other_authorized)

        self.assertTrue(
            is_support_lead_authorized(lead, self.support_exec_user, self.db)
        )
        self.assertFalse(
            is_support_lead_authorized(lead, self.other_support_exec_user, self.db)
        )

        # Filtering the queue by that agent also returns the trial customer.
        filtered = get_support_assigned_leads(
            search=None,
            status=None,
            priority=None,
            source=None,
            assigned_agent_id=self.support_exec_emp.id,
            skip=0,
            limit=50,
            db=self.db,
            current_user=self.admin_user,
        )
        self.assertIn(lead.id, [i["lead_id"] for i in filtered["items"]])

    # ------------------------------------------------------------------
    # 5. Reminders for Sales Manager + Support Employee with all fields
    # ------------------------------------------------------------------
    def test_07_reminders_reach_sales_manager_and_support_with_all_fields(self):
        lead = self._make_lead()
        self._set_trial(
            lead, 3, support_id=self.support_exec_emp.id
        )  # end date = today + 3 -> T-3 milestone today
        self.db.refresh(lead)

        result = check_and_send_trial_reminders(self.db, today=self._today())
        self.assertEqual(result["errors"], 0)
        self.assertEqual(result["notifications_created"], 2)

        sales_notes = (
            self.db.query(Notification)
            .filter(Notification.user_id == self.sales_manager_user.id)
            .all()
        )
        support_notes = (
            self.db.query(Notification)
            .filter(Notification.user_id == self.support_exec_user.id)
            .all()
        )
        self.assertEqual(len(sales_notes), 1)
        self.assertEqual(len(support_notes), 1)

        message = sales_notes[0].message
        # Customer name, trial start, trial end, remaining days, assignees.
        self.assertIn(lead.name, message)
        self.assertIn(
            get_ist_now().date().strftime("%d %b %Y"), message
        )  # trial start date
        self.assertIn(
            (self._today() + timedelta(days=3)).strftime("%d %b %Y"), message
        )  # trial end date
        self.assertIn("Remaining Trial Days: 3", message)
        self.assertIn("Assigned Support Employee:", message)
        self.assertIn(self.support_exec_emp.name, message)

        support_message = support_notes[0].message
        self.assertIn("Assigned Sales Manager:", support_message)
        self.assertIn(self.sales_manager_emp.name, support_message)
        self.assertIn(
            (self._today() + timedelta(days=3)).strftime("%d %b %Y"), support_message
        )

        # No notification for anyone else, and no duplicate on a re-run.
        self.assertEqual(
            self.db.query(Notification)
            .filter(Notification.user_id == self.other_support_exec_user.id)
            .count(),
            0,
        )
        rerun = check_and_send_trial_reminders(self.db, today=self._today())
        self.assertEqual(rerun["notifications_created"], 0)
        self.assertGreaterEqual(rerun["duplicates_skipped"], 2)

    # ------------------------------------------------------------------
    # 6. Changing the trial duration updates the scheduled reminders
    # ------------------------------------------------------------------
    def test_08_changing_duration_updates_reminders_without_duplicates(self):
        lead = self._make_lead()
        self._set_trial(lead, 3, support_id=self.support_exec_emp.id)
        self.db.refresh(lead)

        first = check_and_send_trial_reminders(self.db, today=self._today())
        self.assertEqual(first["notifications_created"], 2)
        self.assertEqual(
            self.db.query(Notification).filter(
                Notification.notification_type == "TRIAL_EXPIRY"
            ).count(),
            2,
        )

        # Shorten the trial: end date moves from today+3 to today+1. The T-1
        # milestone for the NEW end date is scheduled; the already-delivered
        # T-3 row for the old end date is kept as history (never re-sent).
        self._set_trial(lead, 1, support_id=self.support_exec_emp.id)
        self.db.refresh(lead)
        self.assertEqual(lead.trial_end_date, self._today() + timedelta(days=1))

        second = check_and_send_trial_reminders(self.db, today=self._today())
        self.assertEqual(second["notifications_created"], 2)

        all_notes = (
            self.db.query(Notification)
            .filter(Notification.notification_type == "TRIAL_EXPIRY")
            .all()
        )
        self.assertEqual(len(all_notes), 4)
        new_end_label = (self._today() + timedelta(days=1)).strftime("%d %b %Y")
        old_end_label = (self._today() + timedelta(days=3)).strftime("%d %b %Y")
        # The two new-cycle notices carry the new end date, the two earlier
        # notices keep the end date they were actually delivered for.
        self.assertEqual(
            sum(1 for n in all_notes if new_end_label in n.message), 2
        )
        self.assertEqual(
            sum(1 for n in all_notes if old_end_label in n.message), 2
        )

        # Re-running the scheduler never duplicates a delivery.
        third = check_and_send_trial_reminders(self.db, today=self._today())
        self.assertEqual(third["notifications_created"], 0)
        self.assertEqual(
            self.db.query(Notification)
            .filter(Notification.notification_type == "TRIAL_EXPIRY")
            .count(),
            4,
        )

        # Reverting to an end date that was already delivered does NOT send a
        # second copy: the delivery key is (lead, user, milestone, end date).
        self._set_trial(lead, 3, support_id=self.support_exec_emp.id)
        self.db.refresh(lead)
        fourth = check_and_send_trial_reminders(self.db, today=self._today())
        self.assertEqual(fourth["notifications_created"], 0)
        self.assertGreaterEqual(fourth["duplicates_skipped"], 2)
        self.assertEqual(
            self.db.query(Notification)
            .filter(Notification.notification_type == "TRIAL_EXPIRY")
            .count(),
            4,
        )

    # ------------------------------------------------------------------
    # 7. Trial statuses are derived without touching Sales/Support status
    # ------------------------------------------------------------------
    def test_09_trial_statuses_are_derived_correctly(self):
        lead = self._make_lead()
        today = self._today()

        self._set_trial(lead, 10, support_id=self.support_exec_emp.id)
        self.db.refresh(lead)
        self.assertEqual(trial_status_for("TRIAL", today + timedelta(days=10)), "TRIAL_ACTIVE")
        self.assertEqual(trial_status_for("TRIAL", today + timedelta(days=3)), "TRIAL_EXPIRING_SOON")
        self.assertEqual(trial_status_for("TRIAL", today + timedelta(days=1)), "TRIAL_EXPIRING_SOON")
        self.assertEqual(trial_status_for("TRIAL", today), "TRIAL_EXPIRING_SOON")
        self.assertEqual(trial_status_for("TRIAL", today - timedelta(days=1)), "TRIAL_EXPIRED")
        self.assertEqual(trial_status_for("WON", today + timedelta(days=5)), "TRIAL_CONVERTED")
        self.assertEqual(trial_status_for("NOT_INTERESTED", today), "TRIAL_CANCELLED")
        self.assertIsNone(trial_status_for("NEW", None))
        self.assertIsNone(trial_status_for("FOLLOW-UP", today + timedelta(days=5)))

        # Expired trial: status flag + projection, Sales status untouched.
        lead.trial_end_date = today - timedelta(days=2)
        lead.trial_start_date = today - timedelta(days=16)
        self.db.commit()
        projection = build_lead_out(lead, self.admin_user, self.db)
        self.assertEqual(projection.status, "TRIAL")
        self.assertTrue(projection.is_trial_expired)
        self.assertEqual(projection.trial_status, "TRIAL_EXPIRED")
        self.assertEqual(projection.trial_days_remaining, -2)
        # Support assignment/status columns are untouched by expiry handling.
        self.assertEqual(
            projection.support_assigned_to, self.support_exec_emp.id
        )
        self.assertEqual(projection.support_assignment_status, "AWAITING_CONVERSION")

        # Leaving the Trial workflow keeps the historical dates but reports no
        # active trial status.
        lead.status = "FOLLOW-UP"
        self.db.commit()
        projection = build_lead_out(lead, self.admin_user, self.db)
        self.assertEqual(projection.status, "FOLLOW-UP")
        self.assertIsNone(projection.trial_status)
        self.assertIsNotNone(projection.trial_end_date)

    # ------------------------------------------------------------------
    # 8. Existing Sales / Support workflows stay unaffected
    # ------------------------------------------------------------------
    def test_10_won_and_support_handoff_workflows_are_unchanged(self):
        # (a) A plain WON lead without a trial is unaffected.
        won_lead = self._make_lead(status=STATUS_WON)
        projection = build_lead_out(won_lead, self.admin_user, self.db)
        self.assertEqual(projection.status, STATUS_WON)
        self.assertIsNone(projection.trial_status)
        self.assertIsNone(projection.trial_days_remaining)
        self.assertFalse(projection.is_trial_expired)
        self.assertEqual(projection.support_assignment_status, "AWAITING_CONVERSION")

        # (b) A converted lead keeps its handoff owner even when a trial
        #     Support employee is recorded (handoff always wins).
        from models.customer import Customer
        from models.workflow import SupportHandoff

        trial_lead = self._make_lead()
        self._set_trial(trial_lead, 14, support_id=self.support_exec_emp.id)
        trial_lead.status = "CONVERTED_TO_SUPPORT"
        customer = Customer(
            company_name=trial_lead.company,
            contact_name=trial_lead.name,
            phone=trial_lead.phone,
        )
        self.db.add(customer)
        self.db.commit()
        self.db.refresh(customer)
        handoff = SupportHandoff(
            lead_id=trial_lead.id,
            customer_id=customer.id,
            customer_name=trial_lead.name,
            company_name=trial_lead.company,
            assigned_agent_id=self.other_support_exec_emp.id,
            assigned_agent_name=self.other_support_exec_emp.name,
        )
        self.db.add(handoff)
        self.db.commit()
        self.db.refresh(trial_lead)

        projection = build_lead_out(trial_lead, self.admin_user, self.db)
        self.assertEqual(projection.status, "CONVERTED_TO_SUPPORT")
        self.assertEqual(
            projection.support_assigned_to, self.other_support_exec_emp.id
        )
        self.assertEqual(
            projection.support_assigned_to_name, self.other_support_exec_emp.name
        )
        # The trial Support employee is still reported on its own field.
        self.assertEqual(
            projection.trial_support_employee_id, self.support_exec_emp.id
        )
        self.assertEqual(projection.trial_status, "TRIAL_CONVERTED")

    # ------------------------------------------------------------------
    # 10. End-to-end over HTTP (real FastAPI routing + serialization)
    # ------------------------------------------------------------------
    def test_11_http_set_trial_period_and_support_options(self):
        from main import app

        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        db_path = os.path.join(temp_dir.name, "trial_duration_http_test.db")
        engine = create_engine(
            f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
        )
        # Registered after the temp-dir cleanup so it runs FIRST (LIFO) and
        # releases the SQLite file handle before the directory is deleted.
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)

        def override_db():
            db = Session()
            try:
                yield db
            finally:
                db.close()

        admin = SimpleNamespace(
            id=1, role="ADMIN", username="http_admin",
            department="ADMINISTRATION", employee_id=1, is_active=True,
        )
        saved_overrides = dict(app.dependency_overrides)
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: admin

        def restore_overrides():
            app.dependency_overrides.clear()
            app.dependency_overrides.update(saved_overrides)

        self.addCleanup(restore_overrides)

        seed = Session()
        seed.add(Employee(
            id=1, user_id=1, name="HTTP Admin", email="http_admin@example.test",
            username="http_admin", phone="9800000001", department="ADMINISTRATION",
            role="ADMIN", status="ACTIVE",
        ))
        seed.add(Employee(
            user_id=2, name="HTTP Support Exec", email="http_support@example.test",
            username="http_support", phone="9800000002", department="SUPPORT",
            role="SUPPORT_EXECUTIVE", status="ACTIVE",
        ))
        seed.add(User(
            id=2, username="http_support", hashed_password="x",
            role="SUPPORT_EXECUTIVE", department="SUPPORT", is_active=True,
        ))
        seed.add(Employee(
            user_id=3, name="HTTP Inactive Support", email="http_inactive@example.test",
            username="http_inactive", phone="9800000003", department="SUPPORT",
            role="SUPPORT_EXECUTIVE", status="INACTIVE",
        ))
        seed.add(User(
            id=3, username="http_inactive", hashed_password="x",
            role="SUPPORT_EXECUTIVE", department="SUPPORT", is_active=False,
        ))
        lead = Lead(
            name="HTTP Trial Customer", phone="9811112222",
            email="http_trial@example.com", company="HTTP Trial Co",
            source="MANUAL", status="NEW",
        )
        seed.add(lead)
        seed.commit()
        lead_id = lead.id
        support_id = seed.query(Employee).filter(
            Employee.username == "http_support"
        ).one().id
        seed.close()

        client = TestClient(app)
        today = get_ist_now().date()

        # 1. The route resolves as its own path (not /{lead_id}).
        resp = client.get("/api/leads/trial/support-options")
        self.assertEqual(resp.status_code, 200, resp.text)
        options = resp.json()
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0]["name"], "HTTP Support Exec")
        self.assertNotIn("HTTP Inactive Support", [o["name"] for o in options])

        # 2. 7 days -> start today, end today + 7, Support employee assigned.
        resp = client.put(
            f"/api/leads/{lead_id}",
            json={
                "status": "TRIAL",
                "trial_duration_days": 7,
                "trial_support_employee_id": support_id,
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["status"], "TRIAL")
        self.assertEqual(body["trial_start_date"], today.isoformat())
        self.assertEqual(
            body["trial_end_date"], (today + timedelta(days=7)).isoformat()
        )
        self.assertEqual(body["trial_duration_days"], 7)
        self.assertEqual(body["trial_status"], "TRIAL_ACTIVE")
        self.assertEqual(body["trial_support_employee_id"], support_id)
        self.assertEqual(body["trial_support_employee_name"], "HTTP Support Exec")
        self.assertEqual(body["support_assigned_to"], support_id)
        self.assertEqual(body["support_assigned_to_name"], "HTTP Support Exec")

        # 3 days -> Expiring Soon is reported automatically.
        resp = client.put(
            f"/api/leads/{lead_id}",
            json={"status": "TRIAL", "trial_duration_days": 3},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(
            body["trial_end_date"], (today + timedelta(days=3)).isoformat()
        )
        self.assertEqual(body["trial_status"], "TRIAL_EXPIRING_SOON")

        # 14 days -> recalculated immediately.
        resp = client.put(
            f"/api/leads/{lead_id}",
            json={"status": "TRIAL", "trial_duration_days": 14},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(
            body["trial_end_date"], (today + timedelta(days=14)).isoformat()
        )
        self.assertEqual(body["trial_duration_days"], 14)
        self.assertEqual(body["trial_status"], "TRIAL_ACTIVE")
        # The Support assignment from the previous save is preserved.
        self.assertEqual(body["trial_support_employee_id"], support_id)

        # 4. Invalid duration -> 400.
        resp = client.put(
            f"/api/leads/{lead_id}",
            json={"status": "TRIAL", "trial_duration_days": 0},
        )
        self.assertEqual(resp.status_code, 400, resp.text)


if __name__ == "__main__":
    unittest.main()
