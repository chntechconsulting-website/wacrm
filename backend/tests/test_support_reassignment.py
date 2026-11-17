"""End-to-end tests for Support client assignment / reassignment.

Run from the repository root (same convention as
``test_support_assigned_leads.py``)::

    python -m pytest backend/tests/test_support_reassignment.py -q
"""

import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.abspath("backend"))

from fastapi import HTTPException

from database import SessionLocal
from models.activity import LeadActivity
from models.audit_log import AuditLog
from models.customer import Customer
from models.employee import Employee
from models.lead import Lead, LeadAssignment
from models.notification import Notification
from models.support import SupportClientAssignment
from models.user import User
from models.workflow import SupportHandoff
from routers.leads import (
    assign_support_lead,
    get_support_assignment,
    get_support_assigned_leads,
)
from services.permission_service import get_support_authorized_lead_ids


def _make_user(db, username, role, department):
    user = db.query(User).filter(User.username == username).first()
    if user:
        return user
    user = User(
        username=username,
        hashed_password="x",
        role=role,
        department=department,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_employee(db, user, name, role, department, manager_id=None):
    employee = db.query(Employee).filter(Employee.user_id == user.id).first()
    if employee:
        employee.manager_id = manager_id
        db.commit()
        return employee
    employee = Employee(
        user_id=user.id,
        name=name,
        username=user.username,
        email=f"{user.username}@reassign.test",
        phone="9000000000",
        role=role,
        department=department,
        status="ACTIVE",
        manager_id=manager_id,
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


class TestSupportReassignment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()

        cls.admin_user = cls.db.query(User).filter(User.id == 1).first()
        assert cls.admin_user is not None, "Admin user must exist"

        cls.manager_user = _make_user(
            cls.db, "e2e_reassign_mgr", "SUPPORT_MANAGER", "SUPPORT"
        )
        cls.manager_emp = _make_employee(
            cls.db,
            cls.manager_user,
            "E2E Reassign Manager",
            "SUPPORT_MANAGER",
            "SUPPORT",
            manager_id=1,
        )

        cls.exec_a_user = _make_user(
            cls.db, "e2e_reassign_a", "SUPPORT_EXECUTIVE", "SUPPORT"
        )
        cls.exec_a = _make_employee(
            cls.db,
            cls.exec_a_user,
            "E2E Reassign Exec A",
            "SUPPORT_EXECUTIVE",
            "SUPPORT",
            manager_id=cls.manager_emp.id,
        )

        cls.exec_b_user = _make_user(
            cls.db, "e2e_reassign_b", "SUPPORT_EXECUTIVE", "SUPPORT"
        )
        cls.exec_b = _make_employee(
            cls.db,
            cls.exec_b_user,
            "E2E Reassign Exec B",
            "SUPPORT_EXECUTIVE",
            "SUPPORT",
            manager_id=cls.manager_emp.id,
        )

        # A separate Support team used to prove Admin global access and that a
        # Support Manager cannot reach outside their own team.
        cls.other_manager_user = _make_user(
            cls.db, "e2e_reassign_other_mgr", "SUPPORT_MANAGER", "SUPPORT"
        )
        cls.other_manager_emp = _make_employee(
            cls.db,
            cls.other_manager_user,
            "E2E Other Manager",
            "SUPPORT_MANAGER",
            "SUPPORT",
            manager_id=1,
        )
        cls.outsider_user = _make_user(
            cls.db, "e2e_reassign_outsider", "SUPPORT_EXECUTIVE", "SUPPORT"
        )
        cls.outsider = _make_employee(
            cls.db,
            cls.outsider_user,
            "E2E Outsider Exec",
            "SUPPORT_EXECUTIVE",
            "SUPPORT",
            manager_id=cls.other_manager_emp.id,
        )

        # Sales owner that must never be overwritten by Support reassignment.
        cls.sales_user = _make_user(
            cls.db, "e2e_reassign_sales", "SALES_MANAGER", "SALES"
        )
        cls.sales_emp = _make_employee(
            cls.db,
            cls.sales_user,
            "E2E Sales Manager",
            "SALES_MANAGER",
            "SALES",
            manager_id=1,
        )

    @classmethod
    def tearDownClass(cls):
        db = cls.db
        lead_ids = [
            row[0]
            for row in db.query(Lead.id)
            .filter(Lead.name.like("[E2E REASSIGN]%"))
            .all()
        ]
        if lead_ids:
            db.query(Notification).filter(
                Notification.notification_type == "SUPPORT_REASSIGNMENT"
            ).delete(synchronize_session=False)
            db.query(SupportClientAssignment).filter(
                SupportClientAssignment.lead_id.in_(lead_ids)
            ).delete(synchronize_session=False)
            db.query(LeadAssignment).filter(
                LeadAssignment.lead_id.in_(lead_ids)
            ).delete(synchronize_session=False)
            db.query(LeadActivity).filter(
                LeadActivity.lead_id.in_(lead_ids)
            ).delete(synchronize_session=False)
            db.query(AuditLog).filter(
                AuditLog.action == "SUPPORT_REASSIGN",
                AuditLog.entity_id.in_([str(lead_id) for lead_id in lead_ids]),
            ).delete(synchronize_session=False)
            db.query(SupportHandoff).filter(
                SupportHandoff.lead_id.in_(lead_ids)
            ).delete(synchronize_session=False)
            db.query(Customer).filter(
                Customer.converted_from_lead.in_(lead_ids)
            ).delete(synchronize_session=False)
            db.query(Lead).filter(Lead.id.in_(lead_ids)).delete(
                synchronize_session=False
            )
        employee_ids = [
            cls.exec_a.id,
            cls.exec_b.id,
            cls.outsider.id,
            cls.manager_emp.id,
            cls.other_manager_emp.id,
            cls.sales_emp.id,
        ]
        user_ids = [
            cls.exec_a_user.id,
            cls.exec_b_user.id,
            cls.outsider_user.id,
            cls.manager_user.id,
            cls.other_manager_user.id,
            cls.sales_user.id,
        ]
        db.query(Notification).filter(
            Notification.user_id.in_(user_ids)
        ).delete(synchronize_session=False)
        db.query(Employee).filter(Employee.id.in_(employee_ids)).delete(
            synchronize_session=False
        )
        db.query(User).filter(User.id.in_(user_ids)).delete(
            synchronize_session=False
        )
        db.commit()
        db.close()

    def setUp(self):
        self.db = SessionLocal()
        self.lead = Lead(
            name="[E2E REASSIGN] Customer",
            phone="9111111111",
            email="reassign.customer@example.com",
            company="Reassign Test Corp",
            source="MANUAL",
            status="CONVERTED_TO_SUPPORT",
            priority="HIGH",
            assigned_to=self.sales_emp.id,
            support_employee_id=self.exec_a.id,
        )
        self.db.add(self.lead)
        self.db.commit()
        self.db.refresh(self.lead)

        self.customer = Customer(
            company_name="Reassign Test Corp",
            contact_name="Reassign Test Customer",
            phone="9111111111",
            email="reassign.customer@example.com",
            converted_from_lead=self.lead.id,
        )
        self.db.add(self.customer)
        self.db.commit()
        self.db.refresh(self.customer)

        self.handoff = SupportHandoff(
            lead_id=self.lead.id,
            customer_id=self.customer.id,
            customer_name="Reassign Test Customer",
            company_name="Reassign Test Corp",
            product_service="CRM Cloud",
            customer_requirements="Assignment test",
            support_manager_id=self.manager_emp.id,
            support_manager_name=self.manager_emp.name,
            assigned_agent_id=self.exec_a.id,
            assigned_agent_name=self.exec_a.name,
            onboarding_status="PENDING_ONBOARDING",
        )
        self.db.add(self.handoff)
        self.db.commit()
        self.db.refresh(self.handoff)

        self.db.add(
            SupportClientAssignment(
                lead_id=self.lead.id,
                customer_id=self.customer.id,
                support_handoff_id=self.handoff.id,
                employee_id=self.exec_a.id,
                source="MIGRATION",
                status="ACTIVE",
                assigned_at=datetime.utcnow(),
            )
        )
        self.db.commit()

    def tearDown(self):
        db = self.db
        db.query(Notification).filter(
            Notification.notification_type == "SUPPORT_REASSIGNMENT"
        ).delete(synchronize_session=False)
        db.query(SupportClientAssignment).filter(
            SupportClientAssignment.lead_id == self.lead.id
        ).delete(synchronize_session=False)
        db.query(LeadAssignment).filter(
            LeadAssignment.lead_id == self.lead.id
        ).delete(synchronize_session=False)
        db.query(LeadActivity).filter(
            LeadActivity.lead_id == self.lead.id
        ).delete(synchronize_session=False)
        db.query(AuditLog).filter(
            AuditLog.action == "SUPPORT_REASSIGN",
            AuditLog.entity_id == str(self.lead.id),
        ).delete(synchronize_session=False)
        db.query(SupportHandoff).filter(
            SupportHandoff.lead_id == self.lead.id
        ).delete(synchronize_session=False)
        db.query(Customer).filter(Customer.id == self.customer.id).delete(
            synchronize_session=False
        )
        db.query(Lead).filter(Lead.id == self.lead.id).delete(
            synchronize_session=False
        )
        db.commit()
        db.close()

    def _assigned_ids(self, user):
        response = get_support_assigned_leads(
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
        return {item["id"] for item in response["items"]}

    def test_admin_reassignment_updates_every_projection(self):
        result = assign_support_lead(
            self.lead.id,
            {
                "assigned_agent_id": self.exec_b.id,
                "reason": "Workload balancing",
            },
            db=self.db,
            current_user=self.admin_user,
        )

        self.assertFalse(result["already_assigned"])
        self.assertTrue(result["reassigned"])
        self.assertEqual(result["assigned_agent_id"], self.exec_b.id)
        self.assertEqual(result["previous_agent_id"], self.exec_a.id)
        self.assertEqual(result["reason"], "Workload balancing")

        self.db.expire_all()
        lead = self.db.query(Lead).filter(Lead.id == self.lead.id).first()
        handoff = (
            self.db.query(SupportHandoff)
            .filter(SupportHandoff.lead_id == self.lead.id)
            .order_by(SupportHandoff.id.desc())
            .first()
        )
        self.assertEqual(lead.support_employee_id, self.exec_b.id)
        # The Sales owner must never be overwritten by a Support reassignment.
        self.assertEqual(lead.assigned_to, self.sales_emp.id)
        self.assertEqual(handoff.assigned_agent_id, self.exec_b.id)

        rows = (
            self.db.query(SupportClientAssignment)
            .filter(SupportClientAssignment.lead_id == self.lead.id)
            .order_by(SupportClientAssignment.id.asc())
            .all()
        )
        active_rows = [row for row in rows if row.status == "ACTIVE"]
        self.assertEqual(len(active_rows), 1, "Duplicate active assignments detected")
        self.assertEqual(active_rows[0].employee_id, self.exec_b.id)
        self.assertEqual(active_rows[0].previous_employee_id, self.exec_a.id)
        self.assertEqual(active_rows[0].reason, "Workload balancing")
        self.assertEqual(active_rows[0].assigned_by_user_id, self.admin_user.id)
        ended = [row for row in rows if row.status == "ENDED"]
        self.assertEqual(len(ended), 1)
        self.assertEqual(ended[0].employee_id, self.exec_a.id)

        # Immediate visibility synchronization.
        self.assertIn(self.lead.id, self._assigned_ids(self.exec_b_user))
        self.assertNotIn(self.lead.id, self._assigned_ids(self.exec_a_user))
        self.assertIn(self.lead.id, self._assigned_ids(self.manager_user))
        self.assertIn(
            self.lead.id, get_support_authorized_lead_ids(self.exec_b_user, self.db)
        )
        self.assertNotIn(
            self.lead.id, get_support_authorized_lead_ids(self.exec_a_user, self.db)
        )

        # The history endpoint exposes current + previous + reason.
        state = get_support_assignment(
            self.lead.id, db=self.db, current_user=self.admin_user
        )
        self.assertEqual(state["support_employee_id"], self.exec_b.id)
        self.assertTrue(state["can_reassign"])
        self.assertEqual(state["history_count"], 2)
        self.assertEqual(state["current"]["employee_name"], self.exec_b.name)
        self.assertEqual(state["current"]["previous_employee_name"], self.exec_a.name)
        self.assertEqual(state["current"]["reason"], "Workload balancing")

    def test_reassignment_requires_reason(self):
        with self.assertRaises(HTTPException) as ctx:
            assign_support_lead(
                self.lead.id,
                {"assigned_agent_id": self.exec_b.id},
                db=self.db,
                current_user=self.admin_user,
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("reason", ctx.exception.detail.lower())

    def test_manager_can_reassign_within_team(self):
        result = assign_support_lead(
            self.lead.id,
            {"assigned_agent_id": self.exec_b.id, "reason": "Team rebalance"},
            db=self.db,
            current_user=self.manager_user,
        )
        self.assertEqual(result["assigned_agent_id"], self.exec_b.id)
        self.assertIn(self.lead.id, self._assigned_ids(self.exec_b_user))
        self.assertNotIn(self.lead.id, self._assigned_ids(self.exec_a_user))

        state = get_support_assignment(
            self.lead.id, db=self.db, current_user=self.manager_user
        )
        self.assertTrue(state["can_reassign"])
        self.assertEqual(state["current"]["assigned_by_employee_id"], self.manager_emp.id)

    def test_manager_cannot_reassign_outside_managed_team(self):
        with self.assertRaises(HTTPException) as ctx:
            assign_support_lead(
                self.lead.id,
                {"assigned_agent_id": self.outsider.id, "reason": "Cross team"},
                db=self.db,
                current_user=self.manager_user,
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_admin_global_reassignment_and_manager_handover(self):
        result = assign_support_lead(
            self.lead.id,
            {"assigned_agent_id": self.outsider.id, "reason": "Global transfer"},
            db=self.db,
            current_user=self.admin_user,
        )
        self.assertEqual(result["assigned_agent_id"], self.outsider.id)
        self.assertEqual(result["support_manager_id"], self.other_manager_emp.id)
        self.assertIn(self.lead.id, self._assigned_ids(self.outsider_user))
        self.assertNotIn(self.lead.id, self._assigned_ids(self.manager_user))
        self.assertNotIn(self.lead.id, self._assigned_ids(self.exec_a_user))

        with self.assertRaises(HTTPException) as ctx:
            get_support_assignment(
                self.lead.id, db=self.db, current_user=self.manager_user
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_repeated_assignment_is_idempotent(self):
        assign_support_lead(
            self.lead.id,
            {"assigned_agent_id": self.exec_b.id, "reason": "First move"},
            db=self.db,
            current_user=self.admin_user,
        )
        self.db.expire_all()
        notifications_before = (
            self.db.query(Notification)
            .filter(Notification.notification_type == "SUPPORT_REASSIGNMENT")
            .count()
        )

        result = assign_support_lead(
            self.lead.id,
            {"assigned_agent_id": self.exec_b.id},
            db=self.db,
            current_user=self.admin_user,
        )
        self.assertTrue(result["already_assigned"])
        self.assertFalse(result["reassigned"])

        rows = (
            self.db.query(SupportClientAssignment)
            .filter(
                SupportClientAssignment.lead_id == self.lead.id,
                SupportClientAssignment.status == "ACTIVE",
            )
            .all()
        )
        self.assertEqual(len(rows), 1)
        notifications_after = (
            self.db.query(Notification)
            .filter(Notification.notification_type == "SUPPORT_REASSIGNMENT")
            .count()
        )
        self.assertEqual(notifications_before, notifications_after)

    def test_notifications_include_all_assignment_details(self):
        assign_support_lead(
            self.lead.id,
            {"assigned_agent_id": self.exec_b.id, "reason": "Notification check"},
            db=self.db,
            current_user=self.admin_user,
        )
        self.db.expire_all()
        notifications = (
            self.db.query(Notification)
            .filter(Notification.notification_type == "SUPPORT_REASSIGNMENT")
            .order_by(Notification.id.asc())
            .all()
        )
        recipients = {notification.user_id for notification in notifications}
        self.assertIn(self.exec_b_user.id, recipients)
        self.assertIn(self.exec_a_user.id, recipients)
        self.assertIn(self.manager_user.id, recipients)
        for notification in notifications:
            self.assertIn("Reassign Test Customer", notification.message)
            self.assertIn("Reassign Test Corp", notification.message)
            self.assertIn(self.exec_a.name, notification.message)
            self.assertIn(self.exec_b.name, notification.message)
            self.assertIn("Reassigned By:", notification.message)
            self.assertIn("Reassignment Date & Time:", notification.message)


if __name__ == "__main__":
    unittest.main()
