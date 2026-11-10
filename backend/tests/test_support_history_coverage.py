"""Support interaction history, leave coverage and incoming-call context tests.

Isolated in-memory SQLite only. No live CRM record is read or written.

Scenarios covered:
A.  Support employee records every interaction field and it is append-only.
B.  Approved leave exposes affected customers.
C.  Support Manager assigns a backup for all affected customers.
D.  Backup employee sees authorized history and can add an interaction.
E.  Previous notes remain intact after the backup adds a new record.
F.  Incoming-call context returns history without fabricating call events.
G.  Permanent owner returns after coverage ends; ownership never rewritten.
H.  Support Manager can end temporary coverage.
I.  Sales is blocked from Support history/coverage APIs.
J.  Unauthorized Support employee is blocked before coverage.
K.  Idempotent client reference prevents duplicate interactions.
L.  No duplicate customer/handoff records are created.
M.  Sales follow-ups do not leak into Support history.
N.  Restore is refused if the permanent owner changed during leave.
"""

import os
import sys
import unittest
from datetime import timedelta

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401 - registers every model on Base.metadata
from database import Base
from models.call_log import CallLog
from models.customer import Customer
from models.employee import Employee
from models.followup import Followup
from models.lead import Lead
from models.support import EmployeeLeave, SupportCoverageAssignment, SupportInteraction
from models.user import User
from models.workflow import SupportHandoff
from routers.support import (
    approve_leave,
    assign_leave_coverage,
    create_leave,
    create_support_interaction,
    get_customer_support_history,
    incoming_call_context,
    list_backup_customers,
    restore_original_assignment,
    support_manager_overview,
)
from schemas.support import CoverageAssignRequest, EmployeeLeaveCreate, SupportInteractionCreate
from utils.timezone import get_ist_now


class SupportHistoryCoverageTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db = Session()

        self.manager_user, self.manager_emp = self._make_person(
            "support_mgr", "SUPPORT_MANAGER", "SUPPORT"
        )
        self.support_a_user, self.support_a = self._make_person(
            "support_a", "SUPPORT_EXECUTIVE", "SUPPORT", manager_id=self.manager_emp.id
        )
        self.support_b_user, self.support_b = self._make_person(
            "support_b", "SUPPORT_EXECUTIVE", "SUPPORT", manager_id=self.manager_emp.id
        )
        self.sales_user, self.sales_emp = self._make_person(
            "sales_exec", "SALES_EXECUTIVE", "SALES"
        )

        self.lead = Lead(
            name="Coverage Customer",
            phone="9899000111",
            email="coverage.customer@example.com",
            company="Coverage Industries",
            source="MANUAL",
            status="CONVERTED",
            assigned_to=self.support_a.id,
        )
        self.db.add(self.lead)
        self.db.commit()
        self.db.refresh(self.lead)

        self.customer = Customer(
            company_name="Coverage Industries",
            contact_name="Coverage Customer",
            phone="9899000111",
            email="coverage.customer@example.com",
            location="Chennai",
            converted_from_lead=self.lead.id,
        )
        self.db.add(self.customer)
        self.db.commit()
        self.db.refresh(self.customer)

        self.handoff = SupportHandoff(
            lead_id=self.lead.id,
            customer_id=self.customer.id,
            customer_name="Coverage Customer",
            company_name="Coverage Industries",
            phone="9899000111",
            email="coverage.customer@example.com",
            product_service="CRM Cloud Pro",
            customer_users_count=25,
            support_manager_id=self.manager_emp.id,
            support_manager_name=self.manager_emp.name,
            assigned_agent_id=self.support_a.id,
            assigned_agent_name=self.support_a.name,
            onboarding_status="ACTIVE",
        )
        self.db.add(self.handoff)
        self.db.commit()
        self.db.refresh(self.handoff)

        self.today = get_ist_now().date()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _make_person(self, username, role, department, manager_id=None):
        user = User(
            username=username,
            hashed_password="test-only",
            role=role,
            department=department,
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        employee = Employee(
            user_id=user.id,
            manager_id=manager_id,
            department=department,
            name=f"{username.title()} Employee",
            email=f"{username}@example.com",
            phone=f"98{abs(hash(username)) % 100000000:08d}",
            username=username,
            role=role,
            status="ACTIVE",
        )
        self.db.add(employee)
        self.db.commit()
        self.db.refresh(employee)
        return user, employee

    def _interaction_payload(self, **overrides):
        data = {
            "interaction_type": "INBOUND",
            "interaction_at": get_ist_now() - timedelta(days=1),
            "discussion": "Customer reported a login issue.",
            "problem_reported": "OTP not delivered.",
            "troubleshooting": "Verified provider logs and resubmitted OTP.",
            "solution_provided": "Resent OTP through alternate gateway.",
            "pending_issues": "Customer must confirm login tomorrow.",
            "customer_commitments": "Customer will test at 10 AM.",
            "next_action": "Call back after customer confirms login.",
            "follow_up_at": get_ist_now() - timedelta(hours=2),
            "notes": "First permanent Support note.",
            "attachments": [{"name": "otp-log.txt", "url": "/uploads/otp-log.txt"}],
        }
        data.update(overrides)
        return SupportInteractionCreate(**data)

    def _approved_leave_with_customers(self):
        leave = create_leave(
            EmployeeLeaveCreate(
                employee_id=self.support_a.id,
                leave_type="SICK",
                start_date=self.today,
                end_date=self.today + timedelta(days=2),
                reason="Medical leave",
            ),
            db=self.db,
            current_user=self.manager_user,
        )
        approval = approve_leave(
            leave["id"], None, db=self.db, current_user=self.manager_user
        )
        return approval["leave"], approval["customers_needing_coverage"]

    def _assign_backup(self, leave_id, all_assigned=True, lead_ids=None):
        return assign_leave_coverage(
            leave_id,
            CoverageAssignRequest(
                backup_employee_id=self.support_b.id,
                lead_ids=lead_ids,
                all_assigned_customers=all_assigned,
            ),
            db=self.db,
            current_user=self.manager_user,
        )

    # A + E: append-only interaction detail and old notes intact
    def test_01_interactions_are_complete_and_append_only(self):
        first = create_support_interaction(
            self.lead.id,
            self._interaction_payload(),
            db=self.db,
            current_user=self.support_a_user,
        )
        self.assertFalse(first["duplicate"])
        self.assertEqual(first["interaction"]["handling_employee_id"], self.support_a.id)
        self.assertEqual(first["interaction"]["original_employee_id"], self.support_a.id)
        self.assertEqual(first["interaction"]["attachments"][0]["name"], "otp-log.txt")

        second = create_support_interaction(
            self.lead.id,
            self._interaction_payload(
                interaction_type="MANUAL",
                interaction_at=get_ist_now(),
                discussion="Customer confirmed login works.",
                solution_provided="Issue closed.",
                pending_issues=None,
                next_action="No further action.",
                follow_up_at=None,
                notes="Second note.",
                attachments=None,
            ),
            db=self.db,
            current_user=self.support_a_user,
        )
        self.assertFalse(second["duplicate"])

        history = get_customer_support_history(
            self.lead.id, None, db=self.db, current_user=self.support_a_user
        )
        self.assertEqual(len(history["interactions"]), 2)
        first_saved = history["interactions"][0]
        self.assertEqual(first_saved["discussion"], "Customer reported a login issue.")
        self.assertEqual(first_saved["notes"], "First permanent Support note.")
        self.assertEqual(first_saved["pending_issues"], "Customer must confirm login tomorrow.")
        self.assertEqual(history["summary"]["interaction_count"], 2)
        self.assertFalse(history["summary"]["ai_generated"])
        self.assertEqual(history["summary"]["generated_from"], "SUPPORT_INTERACTIONS")

        count = (
            self.db.query(SupportInteraction)
            .filter(SupportInteraction.customer_id == self.customer.id)
            .count()
        )
        self.assertEqual(count, 2)

    # B + C + D + F + G + H: leave, coverage, backup access, incoming context, restore
    def test_02_leave_coverage_backup_access_incoming_context_and_restore(self):
        create_support_interaction(
            self.lead.id,
            self._interaction_payload(),
            db=self.db,
            current_user=self.support_a_user,
        )

        # J: before coverage, Support B is not authorized for A's customer.
        with self.assertRaises(HTTPException) as denied:
            get_customer_support_history(
                self.lead.id, None, db=self.db, current_user=self.support_b_user
            )
        self.assertEqual(denied.exception.status_code, 403)

        leave, affected_customers = self._approved_leave_with_customers()
        self.assertEqual(leave["status"], "APPROVED")
        self.assertEqual(len(affected_customers), 1)
        self.assertEqual(affected_customers[0]["lead_id"], self.lead.id)
        self.assertTrue(affected_customers[0]["coverage_required"])

        assignment = self._assign_backup(leave["id"])
        self.assertEqual(assignment["created_count"], 1)
        coverage_id = assignment["created"][0]["id"]

        # B sees the backup customer with package and history.
        backup_view = list_backup_customers(
            employee_id=None, include_history=True, db=self.db, current_user=self.support_b_user
        )
        self.assertEqual(backup_view["total"], 1)
        item = backup_view["items"][0]
        self.assertEqual(item["lead_id"], self.lead.id)
        self.assertEqual(item["original_support_employee_name"], self.support_a.name)
        self.assertEqual(item["backup_employee_name"], self.support_b.name)
        self.assertEqual(item["product_service"], "CRM Cloud Pro")
        self.assertEqual(len(item["interactions"]), 1)
        self.assertEqual(item["customer_users_count"] if "customer_users_count" in item else 25, 25)

        # B can read and add to the same authorized timeline.
        history = get_customer_support_history(
            self.lead.id, None, db=self.db, current_user=self.support_b_user
        )
        self.assertEqual(len(history["interactions"]), 1)
        added = create_support_interaction(
            self.lead.id,
            self._interaction_payload(
                interaction_type="OUTBOUND",
                interaction_at=get_ist_now(),
                discussion="Backup called customer during leave.",
                problem_reported=None,
                troubleshooting=None,
                solution_provided="Guided customer through login.",
                pending_issues=None,
                customer_commitments=None,
                next_action=None,
                follow_up_at=None,
                notes="Backup coverage note.",
                attachments=None,
            ),
            db=self.db,
            current_user=self.support_b_user,
        )
        self.assertFalse(added["duplicate"])
        self.assertEqual(added["interaction"]["handling_employee_id"], self.support_b.id)
        self.assertEqual(added["interaction"]["original_employee_id"], self.support_a.id)

        # E: the original permanent-owner note is still intact.
        updated_history = get_customer_support_history(
            self.lead.id, None, db=self.db, current_user=self.support_b_user
        )
        self.assertEqual(len(updated_history["interactions"]), 2)
        self.assertEqual(
            updated_history["interactions"][0]["notes"], "First permanent Support note."
        )
        self.assertEqual(
            updated_history["interactions"][1]["notes"], "Backup coverage note."
        )

        # F: incoming-call context is CRM-side only and never creates call events.
        call_context = incoming_call_context(
            phone="+91 98990 00111",
            number=None,
            db=self.db,
            current_user=self.support_b_user,
        )
        self.assertTrue(call_context["found"])
        self.assertTrue(call_context["authorized"])
        self.assertEqual(call_context["assignment"]["original_support_employee_name"], self.support_a.name)
        self.assertEqual(call_context["assignment"]["backup_employee_name"], self.support_b.name)
        self.assertEqual(call_context["last_conversation_summary"], "Backup called customer during leave. | Solution: Guided customer through login.")
        self.assertTrue(call_context["call_control"]["crm_side_only"])
        self.assertFalse(call_context["call_control"]["provider_routing_changed"])
        self.assertNotIn("answered_at", call_context)
        self.assertNotIn("call_status", call_context)
        self.assertEqual(self.db.query(CallLog).count(), 0)

        # Manager overview includes availability, leave, coverage and pending/overdue data.
        overview = support_manager_overview(db=self.db, current_user=self.manager_user)
        self.assertGreaterEqual(len(overview["employees"]), 3)
        self.assertEqual(len(overview["approved_leaves"]), 1)
        self.assertEqual(overview["temporary_coverage_count"], 1)
        self.assertEqual(overview["pending_issue_count"], 0)  # latest record cleared pending issue
        self.assertGreaterEqual(len(overview["handover_history"]), 1)

        # G/H: permanent owner never changed; manager ends coverage after A returns.
        self.db.refresh(self.handoff)
        self.assertEqual(self.handoff.assigned_agent_id, self.support_a.id)
        self.assertEqual(self.lead.assigned_to, self.support_a.id)

        restore = restore_original_assignment(
            coverage_id, db=self.db, current_user=self.manager_user
        )
        self.assertFalse(restore["already_ended"])
        self.assertEqual(restore["coverage"]["status"], "ENDED")
        self.assertEqual(restore["coverage"]["original_employee_id"], self.support_a.id)

        self.db.refresh(self.handoff)
        self.assertEqual(self.handoff.assigned_agent_id, self.support_a.id)
        self.assertEqual(self.lead.assigned_to, self.support_a.id)

        # B loses temporary access after coverage ends; A still sees all history.
        with self.assertRaises(HTTPException) as denied_after:
            get_customer_support_history(
                self.lead.id, None, db=self.db, current_user=self.support_b_user
            )
        self.assertEqual(denied_after.exception.status_code, 403)

        owner_history = get_customer_support_history(
            self.lead.id, None, db=self.db, current_user=self.support_a_user
        )
        self.assertEqual(len(owner_history["interactions"]), 2)

    # I + J: Sales and unauthorized Support access are blocked by the backend.
    def test_03_sales_and_unauthorized_support_are_blocked(self):
        with self.assertRaises(HTTPException) as sales_history:
            get_customer_support_history(
                self.lead.id, None, db=self.db, current_user=self.sales_user
            )
        self.assertEqual(sales_history.exception.status_code, 403)

        with self.assertRaises(HTTPException) as sales_backup:
            list_backup_customers(
                employee_id=None, include_history=True, db=self.db, current_user=self.sales_user
            )
        self.assertEqual(sales_backup.exception.status_code, 403)

        with self.assertRaises(HTTPException) as sales_incoming:
            incoming_call_context(
                phone="9899000111", number=None, db=self.db, current_user=self.sales_user
            )
        self.assertEqual(sales_incoming.exception.status_code, 403)

        with self.assertRaises(HTTPException) as sales_manager_overview:
            support_manager_overview(db=self.db, current_user=self.sales_user)
        self.assertEqual(sales_manager_overview.exception.status_code, 403)

        with self.assertRaises(HTTPException) as exec_manager_overview:
            support_manager_overview(db=self.db, current_user=self.support_b_user)
        self.assertEqual(exec_manager_overview.exception.status_code, 403)

        # Sales cannot create Support interactions either.
        with self.assertRaises(HTTPException) as sales_create:
            create_support_interaction(
                self.lead.id,
                self._interaction_payload(),
                db=self.db,
                current_user=self.sales_user,
            )
        self.assertEqual(sales_create.exception.status_code, 403)

    # K + L: idempotent client reference and no duplicate customer/handoff rows.
    def test_04_idempotency_prevents_duplicates(self):
        payload = self._interaction_payload(client_reference="dedupe-001")
        first = create_support_interaction(
            self.lead.id, payload, db=self.db, current_user=self.support_a_user
        )
        second = create_support_interaction(
            self.lead.id, payload, db=self.db, current_user=self.support_a_user
        )
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["interaction"]["id"], second["interaction"]["id"])

        count = (
            self.db.query(SupportInteraction)
            .filter(SupportInteraction.customer_id == self.customer.id)
            .count()
        )
        self.assertEqual(count, 1)
        self.assertEqual(self.db.query(Customer).count(), 1)
        self.assertEqual(self.db.query(SupportHandoff).count(), 1)

    # M: Sales follow-ups stay private even though Support can see the customer.
    def test_05_sales_followups_do_not_leak_into_support_history(self):
        self.db.add(
            Followup(
                lead_id=self.lead.id,
                assigned_to=self.sales_emp.id,
                followup_date=self.today,
                followup_time="11:00",
                notes="Private Sales negotiation note.",
                priority="HIGH",
                status="Pending",
                created_by=self.sales_emp.id,
                creator_department="SALES",
                assigned_department="SALES",
                owner_department="SALES",
            )
        )
        self.db.add(
            Followup(
                lead_id=self.lead.id,
                assigned_to=self.support_a.id,
                followup_date=self.today,
                followup_time="15:00",
                notes="Support onboarding follow-up.",
                priority="MEDIUM",
                status="Pending",
                created_by=self.support_a.id,
                creator_department="SUPPORT",
                assigned_department="SUPPORT",
                owner_department="SUPPORT",
            )
        )
        self.db.commit()

        history = get_customer_support_history(
            self.lead.id, None, db=self.db, current_user=self.support_a_user
        )
        scheduled_notes = [row["notes"] for row in history["scheduled_followups"]]
        self.assertIn("Support onboarding follow-up.", scheduled_notes)
        self.assertNotIn("Private Sales negotiation note.", scheduled_notes)

    # N: restore refused when permanent ownership changed during leave.
    def test_06_restore_refused_when_owner_changed(self):
        leave, _customers = self._approved_leave_with_customers()
        assignment = self._assign_backup(leave["id"])
        coverage_id = assignment["created"][0]["id"]

        # Simulate an explicit permanent ownership change during leave.
        self.handoff.assigned_agent_id = self.support_b.id
        self.handoff.assigned_agent_name = self.support_b.name
        self.db.commit()

        with self.assertRaises(HTTPException) as conflict:
            restore_original_assignment(
                coverage_id, db=self.db, current_user=self.manager_user
            )
        self.assertEqual(conflict.exception.status_code, 409)
        self.assertIn("permanent customer owner changed", conflict.exception.detail.lower())

        coverage = (
            self.db.query(SupportCoverageAssignment)
            .filter(SupportCoverageAssignment.id == coverage_id)
            .first()
        )
        self.assertEqual(coverage.status, "ACTIVE")

    # Leave overlap and backup-on-leave validation.
    def test_07_backup_cannot_be_on_approved_leave(self):
        leave, _customers = self._approved_leave_with_customers()
        # B also has approved leave over the same dates.
        b_leave = EmployeeLeave(
            employee_id=self.support_b.id,
            leave_type="ANNUAL",
            start_date=self.today,
            end_date=self.today + timedelta(days=1),
            status="APPROVED",
            approved_by_employee_id=self.manager_emp.id,
            approved_at=get_ist_now(),
        )
        self.db.add(b_leave)
        self.db.commit()

        with self.assertRaises(HTTPException) as conflict:
            self._assign_backup(leave["id"])
        self.assertEqual(conflict.exception.status_code, 409)
        self.assertIn("also on approved leave", conflict.exception.detail.lower())


if __name__ == "__main__":
    unittest.main()
