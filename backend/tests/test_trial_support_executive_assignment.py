"""Trial Support Executive allocation regression coverage.

The Set Trial Period modal selects a **Support Manager**
(``Lead.trial_support_employee_id``). This suite covers the separate,
explicit Support Manager/Admin action that allocates an **active Support
Executive** to the same customer while the Sales deal is still ``TRIAL``.

Isolated in-memory SQLite only. No live CRM record is read or written.

Scenarios map 1:1 to the acceptance checks:
 1. A Support Manager allocates an Executive during TRIAL without converting
    the deal, moving Sales ownership or rewriting the Trial Manager.
 2. The allocation is transactional/idempotent and a reassignment requires a
    reason and closes the previous active row.
 3. Only active Support Executives are valid trial targets; non-trial leads
    without a handoff still return 409.
 4. Manager scope is enforced by trial-manager identity + managed team; Admin
    can allocate any active Support Executive across teams.
 5. Queue/list projections keep the Executive and the Trial Manager visible
    and hide the customer from unrelated Executives.
 6. `/support-assignment` enables the action for TRIAL, reports the trial
    manager attribution and stays read-only for unauthorized users.
 7. Conversion carries the pre-allocated trial Executive into the handoff and
    attaches the active assignment row to the real handoff/customer.
 8. A trial with no Executive still converts to an unassigned Support handoff.
 9. Trial reminders keep going to the Trial Support Manager, not the allocated
    Executive, and never duplicate.
"""

import os
import sys
import unittest
from datetime import timedelta
from types import SimpleNamespace

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401 - registers every model on Base.metadata
from database import Base
from models.customer import Customer
from models.employee import Employee
from models.lead import Lead, LeadAssignment
from models.notification import Notification
from models.support import SupportClientAssignment
from models.user import User
from models.workflow import SupportHandoff
from routers.leads import (
    assign_support_lead,
    build_lead_out,
    get_support_assignment,
    get_support_assigned_leads,
)
from services.permission_service import (
    get_support_authorized_lead_ids,
    is_support_lead_authorized,
)
from services.trial_reminder_service import check_and_send_trial_reminders
from services.workflow_service import WorkflowService
from utils.lead_status import STATUS_WON
from utils.timezone import get_ist_now


class TrialSupportExecutiveAssignmentTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db = Session()
        self._phone_counter = 9700000000

        self.admin_user, self.admin_emp = self._make_person(
            "tse_admin", "ADMIN", "ADMINISTRATION"
        )
        self.sales_manager_user, self.sales_manager_emp = self._make_person(
            "tse_sales_mgr", "SALES_MANAGER", "SALES"
        )
        self.sales_exec_user, self.sales_exec_emp = self._make_person(
            "tse_sales_exec",
            "SALES_EXECUTIVE",
            "SALES",
            manager_emp=self.sales_manager_emp,
        )
        self.support_manager_user, self.support_manager_emp = self._make_person(
            "tse_support_mgr", "SUPPORT_MANAGER", "SUPPORT"
        )
        self.support_exec_user, self.support_exec_emp = self._make_person(
            "tse_support_exec",
            "SUPPORT_EXECUTIVE",
            "SUPPORT",
            manager_emp=self.support_manager_emp,
        )
        self.second_exec_user, self.second_exec_emp = self._make_person(
            "tse_support_exec_b",
            "SUPPORT_EXECUTIVE",
            "SUPPORT",
            manager_emp=self.support_manager_emp,
        )
        self.other_manager_user, self.other_manager_emp = self._make_person(
            "tse_other_support_mgr", "SUPPORT_MANAGER", "SUPPORT"
        )
        self.outsider_exec_user, self.outsider_exec_emp = self._make_person(
            "tse_outsider_exec",
            "SUPPORT_EXECUTIVE",
            "SUPPORT",
            manager_emp=self.other_manager_emp,
        )
        self.inactive_exec_user, self.inactive_exec_emp = self._make_person(
            "tse_inactive_exec",
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

    def _today(self):
        return get_ist_now().date()

    def _make_trial_lead(self, days_left=10, trial_manager_id="default"):
        """Create a TRIAL lead owned by Sales and managed by Support."""
        self._phone_counter += 1
        today = self._today()
        lead = Lead(
            name=f"Trial Executive Lead {self._phone_counter}",
            phone=str(self._phone_counter),
            email=f"tse{self._phone_counter}@example.com",
            company=f"Trial Executive Co {self._phone_counter}",
            source="MANUAL",
            status="TRIAL",
            assigned_to=self.sales_exec_emp.id,
            trial_start_date=today,
            trial_end_date=today + timedelta(days=days_left),
            trial_support_employee_id=(
                self.support_manager_emp.id
                if trial_manager_id == "default"
                else trial_manager_id
            ),
        )
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        return lead

    def _make_plain_lead(self, status="NEW", assigned_to=None):
        self._phone_counter += 1
        lead = Lead(
            name=f"Ordinary Lead {self._phone_counter}",
            phone=str(self._phone_counter),
            email=f"ordinary{self._phone_counter}@example.com",
            company=f"Ordinary Co {self._phone_counter}",
            source="MANUAL",
            status=status,
            assigned_to=(
                assigned_to if assigned_to is not None else self.sales_exec_emp.id
            ),
        )
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        return lead

    def _assign(self, lead, employee, user=None, reason=None, remarks=None):
        payload = {"assigned_agent_id": employee.id}
        if reason is not None:
            payload["reason"] = reason
        if remarks is not None:
            payload["remarks"] = remarks
        return assign_support_lead(
            lead.id,
            payload,
            db=self.db,
            current_user=user or self.admin_user,
        )

    def _active_rows(self, lead):
        return (
            self.db.query(SupportClientAssignment)
            .filter(
                SupportClientAssignment.lead_id == lead.id,
                SupportClientAssignment.status == "ACTIVE",
            )
            .all()
        )

    def _all_rows(self, lead):
        return (
            self.db.query(SupportClientAssignment)
            .filter(SupportClientAssignment.lead_id == lead.id)
            .order_by(SupportClientAssignment.id.asc())
            .all()
        )

    def _queue(self, user):
        page = get_support_assigned_leads(
            search=None,
            status=None,
            priority=None,
            source=None,
            assigned_agent_id=None,
            skip=0,
            limit=200,
            db=self.db,
            current_user=user,
        )
        return {item["id"]: item for item in page["items"]}

    # ------------------------------------------------------------------
    # 1. Trial allocation does not convert the deal
    # ------------------------------------------------------------------
    def test_01_manager_allocates_executive_during_trial(self):
        lead = self._make_trial_lead()

        result = self._assign(
            lead, self.support_exec_emp, user=self.support_manager_user
        )

        self.assertTrue(result["success"])
        self.assertFalse(result["already_assigned"])
        self.assertFalse(result["reassigned"])
        self.assertIsNone(result["support_handoff_id"])
        self.assertEqual(result["assigned_agent_id"], self.support_exec_emp.id)
        self.assertEqual(result["support_manager_id"], self.support_manager_emp.id)
        self.assertEqual(result["sales_owner_id"], self.sales_exec_emp.id)
        self.assertEqual(result["assignment_scope"], "TRIAL")

        self.db.expire_all()
        lead = self.db.query(Lead).filter(Lead.id == lead.id).one()
        # The Sales deal is untouched: still TRIAL, same Sales owner.
        self.assertEqual(lead.status, "TRIAL")
        self.assertEqual(lead.assigned_to, self.sales_exec_emp.id)
        # The Executive is allocated while the Trial Manager stays attributed.
        self.assertEqual(lead.support_employee_id, self.support_exec_emp.id)
        self.assertEqual(
            lead.trial_support_employee_id, self.support_manager_emp.id
        )
        # No premature conversion/handoff/customer was created.
        self.assertEqual(self.db.query(SupportHandoff).count(), 0)
        self.assertEqual(self.db.query(Customer).count(), 0)

        rows = self._all_rows(lead)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, "ACTIVE")
        self.assertEqual(rows[0].employee_id, self.support_exec_emp.id)
        self.assertEqual(rows[0].source, "TRIAL_ASSIGN")
        self.assertIsNone(rows[0].support_handoff_id)
        self.assertIsNone(rows[0].customer_id)
        self.assertIsNone(rows[0].previous_employee_id)
        self.assertEqual(
            rows[0].assigned_by_employee_id, self.support_manager_emp.id
        )
        self.assertEqual(rows[0].assigned_by_user_id, self.support_manager_user.id)

        methods = [
            (row.assignment_method, row.assigned_to) for row in lead.assignments
        ]
        self.assertIn(
            ("TRIAL_SUPPORT_EXECUTIVE", self.support_exec_emp.id), methods
        )
        # Never use MANUAL_SUPPORT: trial reminders must keep targeting the
        # Trial Support Manager, not the allocated Executive.
        self.assertNotIn("MANUAL_SUPPORT", [m for m, _ in methods])

        # Assignment notifications reach the new Executive and the Trial
        # Manager only.
        exec_notes = (
            self.db.query(Notification)
            .filter(Notification.user_id == self.support_exec_user.id)
            .all()
        )
        manager_notes = (
            self.db.query(Notification)
            .filter(Notification.user_id == self.support_manager_user.id)
            .all()
        )
        self.assertEqual(len(exec_notes), 1)
        self.assertEqual(len(manager_notes), 1)
        self.assertEqual(exec_notes[0].notification_type, "SUPPORT_ASSIGNMENT")
        self.assertIn("Trial Client Assigned", exec_notes[0].title)
        self.assertIn(lead.name, exec_notes[0].message)
        self.assertEqual(
            self.db.query(Notification)
            .filter(Notification.user_id == self.second_exec_user.id)
            .count(),
            0,
        )

        # The Sales projection still points the Support columns at the
        # Executive while manager attribution remains the Trial Manager.
        projection = build_lead_out(lead, self.sales_manager_user, self.db)
        self.assertEqual(projection.status, "TRIAL")
        self.assertEqual(projection.assigned_to, self.sales_exec_emp.id)
        self.assertEqual(projection.support_assigned_to, self.support_exec_emp.id)
        self.assertEqual(
            projection.support_assigned_to_name, self.support_exec_emp.name
        )
        self.assertEqual(projection.support_manager_id, self.support_manager_emp.id)
        self.assertEqual(
            projection.support_manager_name, self.support_manager_emp.name
        )
        self.assertIsNotNone(projection.support_assigned_at)
        self.assertEqual(projection.support_assignment_status, "AWAITING_CONVERSION")
        self.assertEqual(projection.trial_status, "TRIAL_ACTIVE")

    # ------------------------------------------------------------------
    # 2. Idempotency, reason requirement and reassignment history
    # ------------------------------------------------------------------
    def test_02_idempotent_assignment_and_reassignment_reason(self):
        lead = self._make_trial_lead()
        self._assign(lead, self.support_exec_emp, user=self.support_manager_user)

        # Re-submitting the same Executive is a no-op: no second active row,
        # no duplicate audit feed and no duplicate notification.
        repeat = self._assign(
            lead, self.support_exec_emp, user=self.support_manager_user
        )
        self.assertTrue(repeat["already_assigned"])
        self.assertFalse(repeat["reassigned"])
        self.assertEqual(len(self._all_rows(lead)), 1)
        self.assertEqual(
            self.db.query(LeadAssignment)
            .filter(
                LeadAssignment.lead_id == lead.id,
                LeadAssignment.assignment_method == "TRIAL_SUPPORT_EXECUTIVE",
            )
            .count(),
            1,
        )
        self.assertEqual(
            self.db.query(Notification)
            .filter(Notification.user_id == self.support_exec_user.id)
            .count(),
            1,
        )

        # Moving the trial client to another Executive requires a reason.
        with self.assertRaises(HTTPException) as ctx:
            self._assign(
                lead, self.second_exec_emp, user=self.support_manager_user
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.db.expire_all()
        lead = self.db.query(Lead).filter(Lead.id == lead.id).one()
        self.assertEqual(lead.support_employee_id, self.support_exec_emp.id)
        self.assertEqual(
            [row.employee_id for row in self._active_rows(lead)],
            [self.support_exec_emp.id],
        )

        result = self._assign(
            lead,
            self.second_exec_emp,
            user=self.support_manager_user,
            reason="Trial workload balance",
        )
        self.assertTrue(result["reassigned"])
        self.assertFalse(result["already_assigned"])
        self.assertEqual(result["previous_agent_id"], self.support_exec_emp.id)
        self.assertEqual(result["reason"], "Trial workload balance")
        self.assertEqual(result["assignment_scope"], "TRIAL")

        self.db.expire_all()
        lead = self.db.query(Lead).filter(Lead.id == lead.id).one()
        self.assertEqual(lead.status, "TRIAL")
        self.assertEqual(lead.support_employee_id, self.second_exec_emp.id)
        self.assertEqual(
            lead.trial_support_employee_id, self.support_manager_emp.id
        )

        rows = self._all_rows(lead)
        self.assertEqual(len(rows), 2)
        ended, active = rows
        self.assertEqual(ended.status, "ENDED")
        self.assertEqual(ended.employee_id, self.support_exec_emp.id)
        self.assertEqual(ended.end_reason, "REASSIGNED")
        self.assertEqual(active.status, "ACTIVE")
        self.assertEqual(active.employee_id, self.second_exec_emp.id)
        self.assertEqual(active.previous_employee_id, self.support_exec_emp.id)
        self.assertEqual(active.source, "TRIAL_REASSIGN")
        self.assertEqual(active.reason, "Trial workload balance")
        self.assertIsNone(active.support_handoff_id)
        self.assertIsNone(active.customer_id)

        # The previous Executive and the Trial Manager are notified.
        for user in (
            self.second_exec_user,
            self.support_exec_user,
            self.support_manager_user,
        ):
            notes = (
                self.db.query(Notification)
                .filter(
                    Notification.user_id == user.id,
                    Notification.notification_type == "SUPPORT_REASSIGNMENT",
                )
                .all()
            )
            self.assertEqual(len(notes), 1)
            self.assertIn("Trial Client Reassigned", notes[0].title)
            self.assertIn(self.second_exec_emp.name, notes[0].message)

    # ------------------------------------------------------------------
    # 3. Target validation and non-trial gating
    # ------------------------------------------------------------------
    def test_03_only_active_support_executives_and_trial_gate(self):
        lead = self._make_trial_lead()

        # Support Managers cannot be allocated as trial Executives.
        for manager_emp in (self.support_manager_emp, self.other_manager_emp):
            with self.assertRaises(HTTPException) as ctx:
                self._assign(lead, manager_emp, user=self.support_manager_user)
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertIn("active Support Executive", ctx.exception.detail)

        # Sales employees and inactive Support Executives are rejected.
        for invalid_emp in (self.sales_exec_emp, self.inactive_exec_emp):
            with self.assertRaises(HTTPException) as ctx:
                self._assign(lead, invalid_emp)
            self.assertEqual(ctx.exception.status_code, 400)

        with self.assertRaises(HTTPException) as ctx:
            self._assign(lead, SimpleNamespace(id=999999))
        self.assertEqual(ctx.exception.status_code, 404)

        # Support Executives cannot assign anybody.
        with self.assertRaises(HTTPException) as ctx:
            self._assign(
                lead, self.second_exec_emp, user=self.support_exec_user
            )
        self.assertEqual(ctx.exception.status_code, 403)

        # Nothing was written by the rejected calls.
        self.db.expire_all()
        lead = self.db.query(Lead).filter(Lead.id == lead.id).one()
        self.assertIsNone(lead.support_employee_id)
        self.assertEqual(self._all_rows(lead), [])

        # A non-trial lead without a handoff is still not assignable.
        ordinary = self._make_plain_lead(status="NEW")
        with self.assertRaises(HTTPException) as ctx:
            self._assign(ordinary, self.support_exec_emp)
        self.assertEqual(ctx.exception.status_code, 409)

        # Executive allocations during trial do not make ordinary Sales leads
        # assignable for a Support Manager either.
        with self.assertRaises(HTTPException) as ctx:
            self._assign(
                ordinary, self.support_exec_emp, user=self.support_manager_user
            )
        self.assertEqual(ctx.exception.status_code, 409)

    # ------------------------------------------------------------------
    # 4 + 5. Trial-manager scope, Admin global access, queue visibility
    # ------------------------------------------------------------------
    def test_04_manager_scope_admin_cross_team_and_queue_projections(self):
        lead = self._make_trial_lead()

        # Another Support Manager cannot allocate to their own Executive: only
        # the Trial Support Manager may do so.
        with self.assertRaises(HTTPException) as ctx:
            self._assign(
                lead, self.outsider_exec_emp, user=self.other_manager_user
            )
        self.assertEqual(ctx.exception.status_code, 403)

        # The Trial Manager cannot allocate outside their managed team.
        with self.assertRaises(HTTPException) as ctx:
            self._assign(
                lead, self.outsider_exec_emp, user=self.support_manager_user
            )
        self.assertEqual(ctx.exception.status_code, 403)

        # Before any allocation only the Trial Manager can see the trial lead.
        self.assertTrue(
            is_support_lead_authorized(lead, self.support_manager_user, self.db)
        )
        self.assertFalse(
            is_support_lead_authorized(lead, self.other_manager_user, self.db)
        )
        self.assertNotIn(lead.id, self._queue(self.other_manager_user))

        # Admin can allocate any active Support Executive, including another
        # team's Executive.
        self._assign(lead, self.outsider_exec_emp)
        self.db.expire_all()
        lead = self.db.query(Lead).filter(Lead.id == lead.id).one()
        self.assertEqual(lead.support_employee_id, self.outsider_exec_emp.id)
        self.assertEqual(
            lead.trial_support_employee_id, self.support_manager_emp.id
        )

        # The Trial Manager retains access to the trial customer even though
        # Admin allocated a cross-team Executive.
        self.assertTrue(
            is_support_lead_authorized(lead, self.support_manager_user, self.db)
        )
        self.assertIn(
            lead.id,
            get_support_authorized_lead_ids(self.support_manager_user, self.db),
        )
        # The other manager gains read access through their own allocated
        # Executive but still may not allocate (only the Trial Manager may).
        self.assertTrue(
            is_support_lead_authorized(lead, self.other_manager_user, self.db)
        )
        # The allocated Executive sees the customer; other Executives do not.
        self.assertTrue(
            is_support_lead_authorized(lead, self.outsider_exec_user, self.db)
        )
        self.assertFalse(
            is_support_lead_authorized(lead, self.support_exec_user, self.db)
        )
        self.assertFalse(
            is_support_lead_authorized(lead, self.second_exec_user, self.db)
        )

        admin_queue = self._queue(self.admin_user)
        item = admin_queue.get(lead.id)
        self.assertIsNotNone(item)
        self.assertEqual(item["support_employee_id"], self.outsider_exec_emp.id)
        self.assertEqual(
            item["assigned_support_executive_id"], self.outsider_exec_emp.id
        )
        self.assertEqual(
            item["assigned_support_executive_name"], self.outsider_exec_emp.name
        )
        # Trial Manager attribution survives the cross-team allocation.
        self.assertEqual(
            item["assigned_support_manager_id"], self.support_manager_emp.id
        )
        self.assertEqual(
            item["assigned_support_manager_name"], self.support_manager_emp.name
        )
        self.assertEqual(item["trial_status"], "TRIAL_ACTIVE")
        self.assertEqual(item["sales_status"], "TRIAL")
        self.assertEqual(
            item["trial_support_employee_id"], self.support_manager_emp.id
        )

        self.assertIn(lead.id, self._queue(self.support_manager_user))
        self.assertIn(lead.id, self._queue(self.outsider_exec_user))
        self.assertIn(lead.id, self._queue(self.other_manager_user))
        self.assertNotIn(lead.id, self._queue(self.support_exec_user))
        self.assertNotIn(lead.id, self._queue(self.second_exec_user))

        # Filtering by the Trial Manager or by the allocated Executive both
        # return the trial customer.
        for filter_id in (
            self.support_manager_emp.id,
            self.outsider_exec_emp.id,
        ):
            page = get_support_assigned_leads(
                search=None,
                status=None,
                priority=None,
                source=None,
                assigned_agent_id=filter_id,
                skip=0,
                limit=50,
                db=self.db,
                current_user=self.admin_user,
            )
            self.assertIn(lead.id, [i["id"] for i in page["items"]])

        # Admin can now reassign the cross-team Executive globally.
        result = self._assign(
            lead,
            self.support_exec_emp,
            user=self.admin_user,
            reason="Reallocated to the Trial Manager's team",
        )
        self.assertTrue(result["reassigned"])
        self.assertEqual(result["previous_agent_id"], self.outsider_exec_emp.id)
        self.db.expire_all()
        lead = self.db.query(Lead).filter(Lead.id == lead.id).one()
        self.assertEqual(lead.support_employee_id, self.support_exec_emp.id)
        self.assertIn(lead.id, self._queue(self.support_exec_user))
        self.assertNotIn(lead.id, self._queue(self.outsider_exec_user))

    # ------------------------------------------------------------------
    # 6. `/support-assignment` state for TRIAL
    # ------------------------------------------------------------------
    def test_05_support_assignment_state_enables_trial_allocation(self):
        lead = self._make_trial_lead()

        # Before allocation the Trial Manager can start the assignment; an
        # unrelated Support Manager cannot.
        state = get_support_assignment(
            lead.id, db=self.db, current_user=self.support_manager_user
        )
        self.assertTrue(state["is_trial"])
        self.assertTrue(state["assignment_enabled"])
        self.assertEqual(state["assignment_scope"], "TRIAL")
        self.assertTrue(state["can_reassign"])
        self.assertIsNone(state["support_employee_id"])
        self.assertEqual(
            state["support_manager_id"], self.support_manager_emp.id
        )
        self.assertFalse(state["is_converted_to_support"])

        with self.assertRaises(HTTPException) as ctx:
            get_support_assignment(
                lead.id, db=self.db, current_user=self.other_manager_user
            )
        self.assertEqual(ctx.exception.status_code, 403)

        self._assign(lead, self.support_exec_emp, user=self.support_manager_user)

        state = get_support_assignment(
            lead.id, db=self.db, current_user=self.support_manager_user
        )
        self.assertTrue(state["assignment_enabled"])
        self.assertTrue(state["can_reassign"])
        self.assertEqual(state["support_employee_id"], self.support_exec_emp.id)
        self.assertEqual(
            state["support_employee_name"], self.support_exec_emp.name
        )
        self.assertEqual(
            state["support_manager_id"], self.support_manager_emp.id
        )
        self.assertTrue(state["reason_required"])
        self.assertIsNotNone(state["current"])
        self.assertEqual(state["current"]["employee_id"], self.support_exec_emp.id)
        self.assertEqual(state["current"]["source"], "TRIAL_ASSIGN")
        self.assertEqual(len(state["history"]), 1)

        # The allocated Executive can inspect their own trial assignment.
        exec_state = get_support_assignment(
            lead.id, db=self.db, current_user=self.support_exec_user
        )
        self.assertEqual(
            exec_state["support_employee_id"], self.support_exec_emp.id
        )
        # Unrelated users cannot inspect the trial assignment.
        with self.assertRaises(HTTPException) as ctx:
            get_support_assignment(
                lead.id, db=self.db, current_user=self.second_exec_user
            )
        self.assertEqual(ctx.exception.status_code, 403)

        # Sales users remain blocked from the Support endpoint.
        with self.assertRaises(HTTPException) as ctx:
            get_support_assignment(
                lead.id, db=self.db, current_user=self.sales_exec_user
            )
        self.assertEqual(ctx.exception.status_code, 403)

        # Admin may allocate a cross-team Executive. The Trial Manager can
        # still inspect the customer but must reassign within their own team;
        # the other manager sees it through their Executive yet is not the
        # Trial Manager, so the trial allocation stays blocked for them.
        self._assign(
            lead,
            self.outsider_exec_emp,
            user=self.admin_user,
            reason="Cross-team trial coverage",
        )
        manager_state = get_support_assignment(
            lead.id, db=self.db, current_user=self.support_manager_user
        )
        self.assertTrue(manager_state["is_trial"])
        self.assertFalse(manager_state["can_reassign"])
        self.assertIn(
            "outside your managed Support team",
            manager_state["reassign_blocked_reason"],
        )

        other_state = get_support_assignment(
            lead.id, db=self.db, current_user=self.other_manager_user
        )
        self.assertFalse(other_state["can_reassign"])
        self.assertIn(
            "Trial Support Manager", other_state["reassign_blocked_reason"]
        )

    # ------------------------------------------------------------------
    # 7. Conversion carries the pre-allocated Executive forward
    # ------------------------------------------------------------------
    def test_06_conversion_carries_trial_executive_into_handoff(self):
        lead = self._make_trial_lead()
        self._assign(lead, self.support_exec_emp, user=self.support_manager_user)

        # Sales marks the trial commercial deal WON before Support conversion.
        lead.status = STATUS_WON
        self.db.commit()

        converted = WorkflowService.convert_to_support(
            self.db,
            lead.id,
            self.sales_manager_user,
            note="Trial converted after customer sign-off",
        )
        self.assertTrue(converted["success"])
        self.assertEqual(converted["status"], "CONVERTED_TO_SUPPORT")
        self.assertTrue(converted["support_assigned"])
        self.assertEqual(converted["support_assigned_to"], self.support_exec_emp.id)
        self.assertEqual(
            converted["support_assigned_to_name"], self.support_exec_emp.name
        )

        self.db.expire_all()
        lead = self.db.query(Lead).filter(Lead.id == lead.id).one()
        handoff = (
            self.db.query(SupportHandoff)
            .filter(SupportHandoff.lead_id == lead.id)
            .one()
        )
        self.assertEqual(lead.status, "CONVERTED_TO_SUPPORT")
        self.assertEqual(lead.support_employee_id, self.support_exec_emp.id)
        # Sales ownership survives conversion unchanged.
        self.assertEqual(lead.assigned_to, self.sales_exec_emp.id)
        # The trial Executive becomes the real handoff owner and the Trial
        # Manager becomes the handoff manager.
        self.assertEqual(handoff.assigned_agent_id, self.support_exec_emp.id)
        self.assertEqual(handoff.assigned_agent_name, self.support_exec_emp.name)
        self.assertEqual(handoff.support_manager_id, self.support_manager_emp.id)
        self.assertEqual(
            handoff.support_manager_name, self.support_manager_emp.name
        )

        rows = self._all_rows(lead)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, "ACTIVE")
        self.assertEqual(rows[0].employee_id, self.support_exec_emp.id)
        self.assertEqual(rows[0].support_handoff_id, handoff.id)
        self.assertEqual(rows[0].customer_id, handoff.customer_id)
        self.assertIsNotNone(handoff.customer_id)

        projection = build_lead_out(lead, self.sales_manager_user, self.db)
        self.assertEqual(projection.status, "CONVERTED_TO_SUPPORT")
        self.assertEqual(projection.support_assigned_to, self.support_exec_emp.id)
        self.assertEqual(
            projection.support_manager_id, self.support_manager_emp.id
        )
        self.assertEqual(projection.support_assignment_status, "ASSIGNED")
        self.assertEqual(projection.trial_status, "TRIAL_CONVERTED")

        # The converted queue keeps the same owner and manager attribution.
        item = self._queue(self.admin_user)[lead.id]
        self.assertEqual(
            item["assigned_support_executive_id"], self.support_exec_emp.id
        )
        self.assertEqual(
            item["assigned_support_manager_id"], self.support_manager_emp.id
        )
        self.assertEqual(item["support_status"], "NEW")
        self.assertEqual(item["sales_status"], "CONVERTED_TO_SUPPORT")
        self.assertIn(lead.id, self._queue(self.support_manager_user))
        self.assertIn(lead.id, self._queue(self.support_exec_user))
        self.assertNotIn(lead.id, self._queue(self.second_exec_user))

        state = get_support_assignment(
            lead.id, db=self.db, current_user=self.support_manager_user
        )
        self.assertFalse(state["is_trial"])
        self.assertEqual(state["assignment_scope"], "SUPPORT")
        self.assertTrue(state["can_reassign"])
        self.assertTrue(state["assignment_enabled"])
        self.assertEqual(state["support_employee_id"], self.support_exec_emp.id)

    def test_07_conversion_without_trial_executive_stays_unassigned(self):
        lead = self._make_trial_lead()
        lead.status = STATUS_WON
        self.db.commit()

        converted = WorkflowService.convert_to_support(
            self.db, lead.id, self.sales_manager_user
        )
        self.assertFalse(converted["support_assigned"])
        self.assertIsNone(converted["support_assigned_to"])

        self.db.expire_all()
        lead = self.db.query(Lead).filter(Lead.id == lead.id).one()
        handoff = (
            self.db.query(SupportHandoff)
            .filter(SupportHandoff.lead_id == lead.id)
            .one()
        )
        self.assertEqual(lead.status, "CONVERTED_TO_SUPPORT")
        self.assertIsNone(lead.support_employee_id)
        self.assertIsNone(handoff.assigned_agent_id)
        # Manager attribution still follows the explicit trial selection.
        self.assertEqual(handoff.support_manager_id, self.support_manager_emp.id)
        self.assertEqual(self._all_rows(lead), [])

        # The unassigned converted customer is visible to the Trial Manager
        # (and any Support Manager, as with the normal post-conversion queue).
        self.assertIn(lead.id, self._queue(self.support_manager_user))
        self.assertIn(lead.id, self._queue(self.other_manager_user))
        self.assertNotIn(lead.id, self._queue(self.support_exec_user))

    def test_08_newer_handoff_assignment_supersedes_trial_allocation(self):
        lead = self._make_trial_lead()
        self._assign(lead, self.support_exec_emp, user=self.support_manager_user)

        lead.status = STATUS_WON
        self.db.commit()

        # A handoff created after Won was explicitly assigned to another
        # Executive before conversion. That newer decision wins.
        customer = Customer(
            company_name=lead.company,
            contact_name=lead.name,
            phone=lead.phone,
            email=lead.email,
            converted_from_lead=lead.id,
        )
        self.db.add(customer)
        self.db.commit()
        self.db.refresh(customer)
        handoff = SupportHandoff(
            lead_id=lead.id,
            customer_id=customer.id,
            customer_name=lead.name,
            company_name=lead.company,
            assigned_agent_id=self.second_exec_emp.id,
            assigned_agent_name=self.second_exec_emp.name,
        )
        self.db.add(handoff)
        self.db.commit()
        self.db.refresh(handoff)

        converted = WorkflowService.convert_to_support(
            self.db, lead.id, self.admin_user
        )
        self.assertTrue(converted["support_assigned"])
        self.assertEqual(
            converted["support_assigned_to"], self.second_exec_emp.id
        )

        self.db.expire_all()
        lead = self.db.query(Lead).filter(Lead.id == lead.id).one()
        handoff = (
            self.db.query(SupportHandoff)
            .filter(SupportHandoff.lead_id == lead.id)
            .one()
        )
        self.assertEqual(handoff.assigned_agent_id, self.second_exec_emp.id)
        self.assertEqual(handoff.support_manager_id, self.support_manager_emp.id)
        self.assertEqual(lead.support_employee_id, self.second_exec_emp.id)
        self.assertEqual(lead.assigned_to, self.sales_exec_emp.id)

        rows = self._all_rows(lead)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].employee_id, self.support_exec_emp.id)
        self.assertEqual(rows[0].status, "ENDED")
        self.assertEqual(rows[0].end_reason, "SUPERSEDED_BY_HANDOFF")
        self.assertEqual(self._active_rows(lead), [])

        item = self._queue(self.admin_user)[lead.id]
        self.assertEqual(
            item["assigned_support_executive_id"], self.second_exec_emp.id
        )
        self.assertEqual(
            item["assigned_support_manager_id"], self.support_manager_emp.id
        )
        self.assertIn(lead.id, self._queue(self.second_exec_user))
        self.assertNotIn(lead.id, self._queue(self.support_exec_user))

        state = get_support_assignment(
            lead.id, db=self.db, current_user=self.support_manager_user
        )
        self.assertEqual(state["support_employee_id"], self.second_exec_emp.id)
        self.assertEqual(state["history"][0]["end_reason"], "SUPERSEDED_BY_HANDOFF")

    # ------------------------------------------------------------------
    # 9. Trial reminders stay with the Trial Support Manager
    # ------------------------------------------------------------------
    def test_09_trial_reminders_stay_with_trial_manager(self):
        lead = self._make_trial_lead(days_left=3)
        self._assign(lead, self.support_exec_emp, user=self.support_manager_user)

        result = check_and_send_trial_reminders(self.db, today=self._today())
        self.assertEqual(result["errors"], 0)
        self.assertEqual(result["notifications_created"], 2)

        manager_notes = (
            self.db.query(Notification)
            .filter(
                Notification.user_id == self.support_manager_user.id,
                Notification.notification_type == "TRIAL_EXPIRY",
            )
            .all()
        )
        sales_notes = (
            self.db.query(Notification)
            .filter(
                Notification.user_id == self.sales_manager_user.id,
                Notification.notification_type == "TRIAL_EXPIRY",
            )
            .all()
        )
        self.assertEqual(len(manager_notes), 1)
        self.assertEqual(len(sales_notes), 1)
        self.assertIn("Assigned Support Manager:", sales_notes[0].message)
        self.assertIn(self.support_manager_emp.name, sales_notes[0].message)

        # The allocated Executive must not hijack the trial reminder.
        for user in (
            self.support_exec_user,
            self.second_exec_user,
            self.outsider_exec_user,
        ):
            self.assertEqual(
                self.db.query(Notification)
                .filter(
                    Notification.user_id == user.id,
                    Notification.notification_type == "TRIAL_EXPIRY",
                )
                .count(),
                0,
            )

        # Scheduler re-runs never duplicate the reminder.
        rerun = check_and_send_trial_reminders(self.db, today=self._today())
        self.assertEqual(rerun["notifications_created"], 0)
        self.assertGreaterEqual(rerun["duplicates_skipped"], 2)

        # The trial state is unchanged by reminders.
        self.db.expire_all()
        lead = self.db.query(Lead).filter(Lead.id == lead.id).one()
        self.assertEqual(lead.status, "TRIAL")
        self.assertEqual(lead.support_employee_id, self.support_exec_emp.id)
        self.assertEqual(
            lead.trial_support_employee_id, self.support_manager_emp.id
        )


if __name__ == "__main__":
    unittest.main()
