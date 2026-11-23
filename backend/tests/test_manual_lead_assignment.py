"""Manual lead assignment regression coverage.

Every lead created through the authenticated manual-create endpoint must have
an owner. The creator is the default owner; an authorized user may choose a
different active Sales Manager. Re-inquiries preserve an existing owner and
fill in the creator only when the original lead was never assigned.

Isolated in-memory SQLite only. No live CRM record is read or written.
"""

import os
import sys
import unittest
from datetime import datetime, timedelta

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401 - registers every model on Base.metadata
from database import Base
from models.employee import Employee
from models.lead import AutoAssignConfig, Lead, LeadAssignment
from models.user import User
from routers.leads import create_lead, list_leads
from schemas.lead import LeadCreate
from services.lead_assignment_service import auto_assign_pending_leads


class ManualLeadAssignmentTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db = Session()
        self._phone_counter = 9333300000

        self.admin_user, self.admin_emp = self._make_person(
            "manual_admin", "ADMIN", "ADMINISTRATION"
        )
        self.manager_user, self.manager_emp = self._make_person(
            "manual_sales_manager", "SALES_MANAGER", "SALES"
        )
        self.other_manager_user, self.other_manager_emp = self._make_person(
            "manual_sales_manager_b", "SALES_MANAGER", "SALES"
        )
        self.exec_a_user, self.exec_a_emp = self._make_person(
            "manual_sales_exec_a",
            "SALES_EXECUTIVE",
            "SALES",
            manager_emp=self.manager_emp,
        )
        self.exec_b_user, self.exec_b_emp = self._make_person(
            "manual_sales_exec_b",
            "SALES_EXECUTIVE",
            "SALES",
            manager_emp=self.manager_emp,
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

    def _next_phone(self):
        self._phone_counter += 1
        return str(self._phone_counter)

    def _create(self, user, assigned_to=None, phone=None, source="MANUAL", status="NEW LEAD"):
        payload = LeadCreate(
            first_name="Manual",
            last_name="Assignment",
            name="Manual Assignment Lead",
            phone=phone or self._next_phone(),
            source=source,
            status=status,
            assigned_to=assigned_to,
        )
        return create_lead(payload, db=self.db, current_user=user)

    def _make_existing_lead(self, phone, assigned_to=None, source="MANUAL"):
        lead = Lead(
            name="Existing Manual Lead",
            phone=phone,
            source=source,
            status="NEW",
            assigned_to=assigned_to,
        )
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        return lead

    def _assignments(self, lead_id):
        return (
            self.db.query(LeadAssignment)
            .filter(LeadAssignment.lead_id == lead_id)
            .all()
        )

    # ------------------------------------------------------------------
    # New manual leads
    # ------------------------------------------------------------------
    def test_sales_exec_creation_defaults_to_creator(self):
        result = self._create(self.exec_a_user)

        self.assertEqual(result.assigned_to, self.exec_a_emp.id)
        self.assertEqual(result.assigned_employee_name, self.exec_a_emp.name)

        lead = self.db.query(Lead).filter(Lead.id == result.id).one()
        self.assertEqual(lead.assigned_to, self.exec_a_emp.id)
        self.assertEqual(lead.assigned_by, self.exec_a_emp.id)
        self.assertIsNotNone(lead.assigned_at)

        assignments = self._assignments(lead.id)
        self.assertEqual(len(assignments), 1)
        self.assertEqual(assignments[0].assigned_to, self.exec_a_emp.id)
        self.assertEqual(assignments[0].assigned_by, self.exec_a_emp.id)

    def test_two_employees_receive_their_own_creator_assignment(self):
        phone_a = self._next_phone()
        phone_b = self._next_phone()

        result_a = self._create(self.exec_a_user, phone=phone_a)
        result_b = self._create(self.exec_b_user, phone=phone_b)

        self.assertEqual(result_a.assigned_to, self.exec_a_emp.id)
        self.assertEqual(result_a.assigned_employee_name, self.exec_a_emp.name)
        self.assertEqual(result_b.assigned_to, self.exec_b_emp.id)
        self.assertEqual(result_b.assigned_employee_name, self.exec_b_emp.name)

        page = list_leads(
            search=phone_a,
            status_filter="ALL",
            source_filter="MANUAL",
            page=1,
            page_size=50,
            skip=0,
            limit=None,
            db=self.db,
            current_user=self.admin_user,
        )
        listed = [item for item in page["items"] if item.id == result_a.id]
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0].assigned_to, self.exec_a_emp.id)
        self.assertEqual(listed[0].assigned_employee_name, self.exec_a_emp.name)

    def test_admin_and_manager_creation_default_to_creator(self):
        admin_result = self._create(self.admin_user)
        manager_result = self._create(self.manager_user)

        self.assertEqual(admin_result.assigned_to, self.admin_emp.id)
        self.assertEqual(admin_result.assigned_employee_name, self.admin_emp.name)
        self.assertEqual(manager_result.assigned_to, self.manager_emp.id)
        self.assertEqual(manager_result.assigned_employee_name, self.manager_emp.name)

    def test_user_without_employee_record_cannot_create_unassigned_manual_lead(self):
        user = User(
            username="manual_no_employee",
            hashed_password="not-used-in-tests",
            role="ADMIN",
            department="ADMINISTRATION",
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        phone = self._next_phone()
        payload = LeadCreate(
            first_name="No",
            last_name="Employee",
            name="No Employee Lead",
            phone=phone,
            source="MANUAL",
            status="NEW",
        )

        with self.assertRaises(HTTPException) as ctx:
            create_lead(payload, db=self.db, current_user=user)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(
            self.db.query(Lead).filter(Lead.phone == phone).count(),
            0,
        )

    def test_authorized_manager_can_assign_another_active_manager_on_create(self):
        result = self._create(
            self.manager_user,
            assigned_to=self.other_manager_emp.id,
        )

        self.assertEqual(result.assigned_to, self.other_manager_emp.id)
        self.assertEqual(result.assigned_employee_name, self.other_manager_emp.name)

    def test_sales_exec_cannot_assign_another_employee_on_create(self):
        result = self._create(
            self.exec_a_user,
            assigned_to=self.exec_b_emp.id,
        )

        self.assertEqual(result.assigned_to, self.exec_a_emp.id)
        self.assertEqual(result.assigned_employee_name, self.exec_a_emp.name)

    # ------------------------------------------------------------------
    # Re-inquiries
    # ------------------------------------------------------------------
    def test_manual_reinquiry_assigns_unassigned_lead_to_creator(self):
        phone = self._next_phone()
        existing = self._make_existing_lead(phone, assigned_to=None)

        result = self._create(self.exec_b_user, phone=phone)

        self.assertTrue(result.is_reinquiry)
        self.assertEqual(result.id, existing.id)
        self.assertEqual(result.assigned_to, self.exec_b_emp.id)
        self.assertEqual(result.assigned_employee_name, self.exec_b_emp.name)

        self.db.refresh(existing)
        self.assertEqual(existing.assigned_to, self.exec_b_emp.id)
        self.assertEqual(existing.assigned_by, self.exec_b_emp.id)
        self.assertEqual(len(self._assignments(existing.id)), 1)

    def test_manual_reinquiry_preserves_existing_assignment(self):
        phone = self._next_phone()
        existing = self._make_existing_lead(
            phone, assigned_to=self.exec_a_emp.id
        )

        result = self._create(self.exec_b_user, phone=phone)

        self.assertTrue(result.is_reinquiry)
        self.assertEqual(result.id, existing.id)
        self.assertEqual(result.assigned_to, self.exec_a_emp.id)
        self.assertEqual(result.assigned_employee_name, self.exec_a_emp.name)

        self.db.refresh(existing)
        self.assertEqual(existing.assigned_to, self.exec_a_emp.id)
        self.assertEqual(self._assignments(existing.id), [])

    # ------------------------------------------------------------------
    # Timeout safety
    # ------------------------------------------------------------------
    def test_timeout_scheduler_does_not_overwrite_assigned_manual_lead(self):
        config = AutoAssignConfig(
            id=1,
            enabled=True,
            waiting_time_minutes=0,
            assignment_method="LEAST_ASSIGNED",
            eligible_roles="SALES_MANAGER,SALES_EXECUTIVE",
            working_hours_enabled=False,
            working_hours_start="00:00",
            working_hours_end="23:59",
        )
        self.db.add(config)
        self.db.commit()

        manual_result = self._create(self.exec_a_user)
        manual_lead = self.db.query(Lead).filter(Lead.id == manual_result.id).one()
        manual_assignments_before = len(self._assignments(manual_lead.id))

        # Control row: an unassigned non-manual lead older than the timeout.
        # The scheduler must process it, proving the timeout path ran.
        control = Lead(
            name="Website Timeout Control",
            phone=self._next_phone(),
            source="WEBSITE",
            status="NEW",
            assigned_to=None,
            created_at=datetime.utcnow() - timedelta(hours=2),
        )
        self.db.add(control)
        self.db.commit()

        assigned_count = auto_assign_pending_leads(
            self.db, override_timeout_minutes=0
        )

        self.assertEqual(assigned_count, 1)
        self.db.refresh(control)
        self.assertIsNotNone(control.assigned_to)

        self.db.refresh(manual_lead)
        self.assertEqual(manual_lead.assigned_to, self.exec_a_emp.id)
        self.assertEqual(
            len(self._assignments(manual_lead.id)),
            manual_assignments_before,
        )


if __name__ == "__main__":
    unittest.main()
