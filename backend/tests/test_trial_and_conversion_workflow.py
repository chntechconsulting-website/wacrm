"""Trial, Won, Converted to Support and assignment workflow coverage.

Isolated in-memory SQLite only. No live CRM record is read or written.

The ten scenarios map directly to the requested acceptance criteria:
1.  TRIAL is a first-class Sales status (display/filter/stats aliases).
2.  Sales projections expose the read-only Sales Manager and Support owner.
3.  Manual Sales assignment accepts only active Sales Managers.
4.  Support assignment lists and accepts only active Support Executives.
5.  WON stays a Sales milestone: no Support owner and no Support notification.
6.  Support assignment is blocked until an explicit Converted to Support step.
7.  Conversion is restricted, audited, recorded once and cannot be duplicated.
8.  Support assignment never overwrites the Sales owner or duplicates history.
9.  RBAC blocks Sales from Support actions and Support from Sales status edits.
10. Legacy CONVERTED / SUPPORT aliases remain compatible.
"""

import os
import sys
import unittest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401 - registers every model on Base.metadata
from database import Base
from models.audit_log import AuditLog
from models.employee import Employee
from models.lead import Lead, LeadAssignment, LeadStatusHistory
from models.notification import Notification
from models.user import User
from models.workflow import SupportHandoff, WorkflowTimelineEvent
from routers.leads import (
    assign_lead,
    assign_support_lead,
    build_lead_out,
    change_lead_status,
    get_leads_stats,
    get_sales_managers,
    get_support_team_members,
    list_leads,
)
from schemas.lead import LeadAssignRequest, LeadStatusRequest
from services.workflow_service import WorkflowService
from utils.lead_status import normalize_lead_status


class TrialAndConversionWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db = Session()
        self._phone_counter = 9900000000

        self.admin_user, self.admin_emp = self._make_person(
            "conv_admin", "ADMIN", "ADMINISTRATION"
        )
        self.sales_manager_user, self.sales_manager_emp = self._make_person(
            "conv_sales_mgr", "SALES_MANAGER", "SALES"
        )
        self.inactive_sales_manager_user, self.inactive_sales_manager_emp = self._make_person(
            "conv_inactive_sales_mgr", "SALES_MANAGER", "SALES", status="INACTIVE"
        )
        self.sales_exec_user, self.sales_exec_emp = self._make_person(
            "conv_sales_exec",
            "SALES_EXECUTIVE",
            "SALES",
            manager_emp=self.sales_manager_emp,
        )
        self.support_manager_user, self.support_manager_emp = self._make_person(
            "conv_support_mgr", "SUPPORT_MANAGER", "SUPPORT"
        )
        self.support_exec_user, self.support_exec_emp = self._make_person(
            "conv_support_exec",
            "SUPPORT_EXECUTIVE",
            "SUPPORT",
            manager_emp=self.support_manager_emp,
        )
        self.support_exec_b_user, self.support_exec_b_emp = self._make_person(
            "conv_support_exec_b",
            "SUPPORT_EXECUTIVE",
            "SUPPORT",
            manager_emp=self.support_manager_emp,
        )
        self.inactive_support_user, self.inactive_support_emp = self._make_person(
            "conv_inactive_support",
            "SUPPORT_EXECUTIVE",
            "SUPPORT",
            status="INACTIVE",
            manager_emp=self.support_manager_emp,
        )
        self.legacy_support_user, self.legacy_support_emp = self._make_person(
            "conv_legacy_support", "SUPPORT", "SUPPORT"
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

    def _make_lead(self, status="NEW", assigned_to=None, name=None):
        self._phone_counter += 1
        lead = Lead(
            name=name or f"Workflow Lead {self._phone_counter}",
            phone=str(self._phone_counter),
            email=f"lead{self._phone_counter}@example.com",
            company="Workflow Industries",
            source="MANUAL",
            status=status,
            assigned_to=assigned_to,
        )
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        return lead

    def _mark_won(self, lead):
        result = WorkflowService.complete_deal_won_workflow(
            db=self.db,
            lead_id=lead.id,
            won_data={
                "total_deal_amount": 100000,
                "product_service": "WaCRM Test Plan",
                "payment_status": "PAYMENT_PENDING",
            },
            current_user=self.sales_exec_user,
        )
        self.db.refresh(lead)
        return result

    def _handoff(self, lead):
        return (
            self.db.query(SupportHandoff)
            .filter(SupportHandoff.lead_id == lead.id)
            .one()
        )

    def _won_and_converted_lead(self):
        lead = self._make_lead(assigned_to=self.sales_exec_emp.id)
        self._mark_won(lead)
        WorkflowService.convert_to_support(
            db=self.db,
            lead_id=lead.id,
            current_user=self.sales_manager_user,
        )
        self.db.refresh(lead)
        return lead

    # ------------------------------------------------------------------
    # 1. TRIAL status
    # ------------------------------------------------------------------
    def test_01_trial_status_is_filterable_and_counted(self):
        lead = self._make_lead(status="TRIAL", assigned_to=self.sales_exec_emp.id)
        self.assertEqual(normalize_lead_status("Trial Lead"), "TRIAL")
        self.assertEqual(normalize_lead_status("TRIAL_LEAD"), "TRIAL")

        page = list_leads(
            status_filter="TRIAL",
            page=1,
            page_size=50,
            skip=0,
            limit=None,
            db=self.db,
            current_user=self.admin_user,
        )
        self.assertIn(lead.id, [item.id for item in page["items"]])

        stats = get_leads_stats(
            only_my=False, db=self.db, current_user=self.admin_user
        )
        self.assertGreaterEqual(stats["trialLeads"], 1)

        projection = build_lead_out(lead, self.admin_user, self.db)
        self.assertEqual(projection.status, "TRIAL")

    # ------------------------------------------------------------------
    # 2. Read-only Sales Manager / Support projections
    # ------------------------------------------------------------------
    def test_02_sales_projection_is_read_only_and_complete(self):
        lead = self._won_and_converted_lead()
        handoff = self._handoff(lead)
        assign_support_lead(
            lead_id=lead.id,
            payload={"assigned_agent_id": self.support_exec_emp.id},
            db=self.db,
            current_user=self.support_manager_user,
        )

        projection = build_lead_out(lead, self.sales_exec_user, self.db)
        self.assertEqual(projection.sales_manager_name, self.sales_manager_emp.name)
        self.assertEqual(projection.support_assigned_to, self.support_exec_emp.id)
        self.assertEqual(projection.support_assigned_to_name, self.support_exec_emp.name)
        self.assertEqual(projection.support_manager_name, self.support_manager_emp.name)
        self.assertEqual(projection.support_assignment_status, "ASSIGNED")
        self.assertTrue(projection.is_converted_to_support)
        self.assertEqual(projection.converted_to_support_by, self.sales_manager_emp.id)
        self.assertEqual(projection.support_handoff_id, handoff.id)
        # The read-only Support owner never replaces the Sales owner.
        self.assertEqual(lead.assigned_to, self.sales_exec_emp.id)
        self.assertEqual(projection.assigned_to, self.sales_exec_emp.id)

    # ------------------------------------------------------------------
    # 3. Manual Sales assignment is Manager-only
    # ------------------------------------------------------------------
    def test_03_sales_assignment_accepts_only_active_sales_managers(self):
        managers = get_sales_managers(db=self.db, current_user=self.admin_user)
        manager_ids = [m["id"] for m in managers]
        self.assertIn(self.sales_manager_emp.id, manager_ids)
        self.assertNotIn(self.inactive_sales_manager_emp.id, manager_ids)
        self.assertNotIn(self.sales_exec_emp.id, manager_ids)
        self.assertNotIn(self.support_manager_emp.id, manager_ids)

        lead = self._make_lead()

        for invalid_employee in (
            self.sales_exec_emp,
            self.support_manager_emp,
            self.inactive_sales_manager_emp,
        ):
            with self.assertRaises(HTTPException) as blocked:
                assign_lead(
                    lead_id=lead.id,
                    assign_req=LeadAssignRequest(assigned_to=invalid_employee.id),
                    db=self.db,
                    current_user=self.admin_user,
                )
            self.assertEqual(blocked.exception.status_code, 400)

        assigned = assign_lead(
            lead_id=lead.id,
            assign_req=LeadAssignRequest(assigned_to=self.sales_manager_emp.id),
            db=self.db,
            current_user=self.admin_user,
        )
        self.assertEqual(assigned.assigned_to, self.sales_manager_emp.id)
        self.assertEqual(assigned.sales_manager_id, self.sales_manager_emp.id)

    # ------------------------------------------------------------------
    # 4. Support assignment is active Support Executive only
    # ------------------------------------------------------------------
    def test_04_support_assignment_accepts_only_active_support_executives(self):
        members = get_support_team_members(
            db=self.db, current_user=self.support_manager_user
        )
        member_ids = [m["id"] for m in members]
        self.assertIn(self.support_exec_emp.id, member_ids)
        self.assertIn(self.support_exec_b_emp.id, member_ids)
        self.assertIn(self.legacy_support_emp.id, member_ids)
        self.assertNotIn(self.inactive_support_emp.id, member_ids)
        self.assertNotIn(self.support_manager_emp.id, member_ids)
        self.assertNotIn(self.sales_exec_emp.id, member_ids)

        lead = self._won_and_converted_lead()
        for invalid_employee in (
            self.sales_exec_emp,
            self.support_manager_emp,
            self.inactive_support_emp,
        ):
            with self.assertRaises(HTTPException) as blocked:
                assign_support_lead(
                    lead_id=lead.id,
                    payload={"assigned_agent_id": invalid_employee.id},
                    db=self.db,
                    current_user=self.support_manager_user,
                )
            self.assertEqual(blocked.exception.status_code, 400)

        assigned = assign_support_lead(
            lead_id=lead.id,
            payload={"assigned_agent_id": self.support_exec_emp.id},
            db=self.db,
            current_user=self.support_manager_user,
        )
        self.assertTrue(assigned["success"])
        self.assertEqual(assigned["assigned_agent_id"], self.support_exec_emp.id)

    # ------------------------------------------------------------------
    # 5. WON is Sales-only
    # ------------------------------------------------------------------
    def test_05_won_does_not_assign_or_notify_support(self):
        lead = self._make_lead(assigned_to=self.sales_exec_emp.id)
        result = self._mark_won(lead)

        self.assertTrue(result["success"])
        self.assertFalse(result["converted_to_support"])
        self.assertEqual(lead.status, "WON")

        handoff = self._handoff(lead)
        self.assertIsNone(handoff.assigned_agent_id)
        self.assertIsNone(handoff.support_manager_id)
        self.assertEqual(
            self.db.query(Notification)
            .filter(Notification.user_id == self.support_manager_user.id)
            .count(),
            0,
        )
        self.assertEqual(
            self.db.query(Notification)
            .filter(Notification.notification_type == "SUPPORT_ASSIGNMENT")
            .count(),
            0,
        )

    # ------------------------------------------------------------------
    # 6. Conversion gates Support assignment
    # ------------------------------------------------------------------
    def test_06_support_assignment_requires_explicit_conversion(self):
        lead = self._make_lead(assigned_to=self.sales_exec_emp.id)
        self._mark_won(lead)

        with self.assertRaises(HTTPException) as blocked:
            assign_support_lead(
                lead_id=lead.id,
                payload={"assigned_agent_id": self.support_exec_emp.id},
                db=self.db,
                current_user=self.support_manager_user,
            )
        self.assertEqual(blocked.exception.status_code, 409)

        WorkflowService.convert_to_support(
            db=self.db,
            lead_id=lead.id,
            current_user=self.sales_manager_user,
        )
        self.db.refresh(lead)
        self.assertEqual(lead.status, "CONVERTED_TO_SUPPORT")

        assigned = assign_support_lead(
            lead_id=lead.id,
            payload={"assigned_agent_id": self.support_exec_emp.id},
            db=self.db,
            current_user=self.support_manager_user,
        )
        self.assertTrue(assigned["success"])

    # ------------------------------------------------------------------
    # 7. Conversion RBAC, audit and idempotency
    # ------------------------------------------------------------------
    def test_07_conversion_is_restricted_audited_and_not_duplicated(self):
        lead = self._make_lead(assigned_to=self.sales_exec_emp.id)

        with self.assertRaises(ValueError):
            WorkflowService.convert_to_support(
                db=self.db,
                lead_id=lead.id,
                current_user=self.sales_manager_user,
            )

        self._mark_won(lead)

        with self.assertRaises(PermissionError):
            WorkflowService.convert_to_support(
                db=self.db,
                lead_id=lead.id,
                current_user=self.sales_exec_user,
            )
        with self.assertRaises(PermissionError):
            WorkflowService.convert_to_support(
                db=self.db,
                lead_id=lead.id,
                current_user=self.support_manager_user,
            )

        converted = WorkflowService.convert_to_support(
            db=self.db,
            lead_id=lead.id,
            current_user=self.sales_manager_user,
            note="Sales handover complete",
        )
        self.assertTrue(converted["success"])

        history = (
            self.db.query(LeadStatusHistory)
            .filter(
                LeadStatusHistory.lead_id == lead.id,
                LeadStatusHistory.new_status == "CONVERTED_TO_SUPPORT",
            )
            .one()
        )
        self.assertEqual(history.changed_by, self.sales_manager_emp.id)
        self.assertEqual(
            self.db.query(AuditLog)
            .filter(AuditLog.action == "CONVERT_TO_SUPPORT")
            .filter(AuditLog.entity_id == str(lead.id))
            .count(),
            1,
        )
        self.assertEqual(
            self.db.query(WorkflowTimelineEvent)
            .filter(WorkflowTimelineEvent.lead_id == lead.id)
            .filter(WorkflowTimelineEvent.new_status == "CONVERTED_TO_SUPPORT")
            .count(),
            1,
        )
        self.assertEqual(self._handoff(lead).assigned_agent_id, None)

        with self.assertRaises(ValueError):
            WorkflowService.convert_to_support(
                db=self.db,
                lead_id=lead.id,
                current_user=self.sales_manager_user,
            )

    # ------------------------------------------------------------------
    # 8. Support assignment preserves Sales ownership and history
    # ------------------------------------------------------------------
    def test_08_support_assignment_preserves_sales_owner_and_is_idempotent(self):
        lead = self._won_and_converted_lead()
        sales_owner_before = lead.assigned_to
        history_before = (
            self.db.query(LeadStatusHistory)
            .filter(LeadStatusHistory.lead_id == lead.id)
            .count()
        )

        first = assign_support_lead(
            lead_id=lead.id,
            payload={
                "assigned_agent_id": self.support_exec_emp.id,
                "remarks": "Priority onboarding requested by Sales.",
            },
            db=self.db,
            current_user=self.support_manager_user,
        )
        self.assertFalse(first["already_assigned"])
        self.assertEqual(first["sales_owner_id"], sales_owner_before)
        self.assertEqual(first["conversion_remarks"], "Priority onboarding requested by Sales.")
        self.db.refresh(lead)
        self.assertEqual(lead.assigned_to, sales_owner_before)
        handoff = self._handoff(lead)
        self.assertIn("Priority onboarding requested by Sales.", handoff.support_notes)
        assignment_row = (
            self.db.query(LeadAssignment)
            .filter(LeadAssignment.lead_id == lead.id)
            .filter(LeadAssignment.assignment_method == "MANUAL_SUPPORT")
            .order_by(LeadAssignment.id.desc())
            .first()
        )
        self.assertIn("Priority onboarding requested by Sales.", assignment_row.notes)

        duplicate = assign_support_lead(
            lead_id=lead.id,
            payload={"assigned_agent_id": self.support_exec_emp.id},
            db=self.db,
            current_user=self.support_manager_user,
        )
        self.assertTrue(duplicate["already_assigned"])
        self.assertEqual(
            self.db.query(LeadAssignment)
            .filter(LeadAssignment.lead_id == lead.id)
            .filter(LeadAssignment.assignment_method == "MANUAL_SUPPORT")
            .count(),
            1,
        )

        reassigned = assign_support_lead(
            lead_id=lead.id,
            payload={"assigned_agent_id": self.support_exec_b_emp.id},
            db=self.db,
            current_user=self.support_manager_user,
        )
        self.assertEqual(reassigned["assigned_agent_id"], self.support_exec_b_emp.id)
        self.db.refresh(lead)
        self.assertEqual(lead.assigned_to, sales_owner_before)
        self.assertEqual(
            self.db.query(LeadStatusHistory)
            .filter(LeadStatusHistory.lead_id == lead.id)
            .count(),
            history_before,
            "Support assignment must not write Sales status history",
        )

    # ------------------------------------------------------------------
    # 9. RBAC
    # ------------------------------------------------------------------
    def test_09_rbac_blocks_cross_department_actions(self):
        lead = self._won_and_converted_lead()

        with self.assertRaises(HTTPException) as sales_assign:
            assign_support_lead(
                lead_id=lead.id,
                payload={"assigned_agent_id": self.support_exec_emp.id},
                db=self.db,
                current_user=self.sales_manager_user,
            )
        self.assertEqual(sales_assign.exception.status_code, 403)

        with self.assertRaises(HTTPException) as support_status:
            change_lead_status(
                lead_id=lead.id,
                status_req=LeadStatusRequest(status="LOST"),
                db=self.db,
                current_user=self.support_manager_user,
            )
        self.assertEqual(support_status.exception.status_code, 403)

        # Admin may perform the Support assignment.
        admin_assigned = assign_support_lead(
            lead_id=lead.id,
            payload={"assigned_agent_id": self.support_exec_emp.id},
            db=self.db,
            current_user=self.admin_user,
        )
        self.assertTrue(admin_assigned["success"])

    # ------------------------------------------------------------------
    # 10. Legacy compatibility
    # ------------------------------------------------------------------
    def test_10_legacy_converted_status_and_support_alias_remain_supported(self):
        # Legacy CONVERTED is still a won deal and can be explicitly converted.
        legacy = self._make_lead(status="CONVERTED", assigned_to=self.sales_exec_emp.id)
        self.assertEqual(normalize_lead_status("CONVERTED"), "CONVERTED")
        converted = WorkflowService.convert_to_support(
            db=self.db,
            lead_id=legacy.id,
            current_user=self.sales_manager_user,
        )
        self.assertTrue(converted["success"])
        self.db.refresh(legacy)
        self.assertEqual(legacy.status, "CONVERTED_TO_SUPPORT")

        # Legacy SUPPORT role is normalized and accepted as Support Executive.
        members = get_support_team_members(
            db=self.db, current_user=self.support_manager_user
        )
        self.assertIn(self.legacy_support_emp.id, [m["id"] for m in members])

        # Existing unconverted deals are projected as awaiting conversion.
        waiting = self._make_lead(status="WON", assigned_to=self.sales_exec_emp.id)
        self._mark_won(waiting)
        projection = build_lead_out(waiting, self.admin_user, self.db)
        self.assertFalse(projection.is_converted_to_support)
        self.assertEqual(projection.support_assignment_status, "AWAITING_CONVERSION")


if __name__ == "__main__":
    unittest.main(verbosity=2)
