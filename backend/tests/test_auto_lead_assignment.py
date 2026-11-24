"""Auto Lead Assignment regression coverage.

Isolated in-memory SQLite only. No live CRM record is read or written.

The Settings screen originally saved ``EMPLOYEE,MANAGER`` while Employee.role
stores ``SALES_EXECUTIVE``/``SALES_MANAGER``. That mismatch made the scheduler
find zero eligible assignees. These tests pin the canonical role mapping, the
IST lead-age clock, terminal-status protection and the assignment methods.
"""

import os
import sys
import unittest
from datetime import timedelta

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401 - registers every model on Base.metadata
from database import Base
from models.activity import LeadActivity
from models.employee import Employee
from models.lead import AutoAssignConfig, Lead, LeadAssignment
from models.user import User
from routers.leads import update_auto_assign_config
from schemas.lead import AutoAssignConfigUpdate
from services.lead_assignment_service import (
    assign_lead_immediately,
    auto_assign_pending_leads,
    get_eligible_employees,
    get_or_create_auto_assign_config,
)
from utils.timezone import get_ist_now


class AutoLeadAssignmentTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(
            bind=self.engine, autoflush=False, autocommit=False
        )
        self.db = Session()
        self._phone_counter = 9444400000

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    # ------------------------------------------------------------------
    # Fixtures
    # ------------------------------------------------------------------
    def _make_employee(
        self,
        username,
        role,
        status="ACTIVE",
        user_active=True,
    ):
        user = User(
            username=username,
            hashed_password="not-used-in-tests",
            role=role,
            department="SALES",
            is_active=user_active,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        employee = Employee(
            user_id=user.id,
            department="SALES",
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
        return employee

    def _make_config(
        self,
        eligible_roles="EMPLOYEE,MANAGER",
        enabled=True,
        waiting_time_minutes=0,
        assignment_method="LEAST_ASSIGNED",
    ):
        self.db.query(AutoAssignConfig).delete()
        config = AutoAssignConfig(
            id=1,
            enabled=enabled,
            waiting_time_minutes=waiting_time_minutes,
            assignment_method=assignment_method,
            eligible_roles=eligible_roles,
            working_hours_enabled=False,
            working_hours_start="00:00",
            working_hours_end="23:59",
        )
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return config

    def _make_lead(self, status="NEW LEAD", age_minutes=120, assigned_to=None):
        self._phone_counter += 1
        lead = Lead(
            name=f"Auto Assign Lead {self._phone_counter}",
            phone=str(self._phone_counter),
            source="WEBSITE",
            status=status,
            assigned_to=assigned_to,
            created_at=get_ist_now() - timedelta(minutes=age_minutes),
        )
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        return lead

    # ------------------------------------------------------------------
    # Role eligibility
    # ------------------------------------------------------------------
    def test_legacy_employee_manager_roles_select_real_sales_roles(self):
        exec_emp = self._make_employee("auto_exec", "SALES_EXECUTIVE")
        manager_emp = self._make_employee("auto_manager", "SALES_MANAGER")
        self._make_employee("auto_support", "SUPPORT_EXECUTIVE")
        self._make_employee("auto_finance", "FINANCE")
        self._make_employee(
            "auto_inactive_employee", "SALES_EXECUTIVE", status="INACTIVE"
        )
        self._make_employee(
            "auto_disabled_user", "SALES_EXECUTIVE", user_active=False
        )

        config = self._make_config("EMPLOYEE,MANAGER")
        eligible = get_eligible_employees(self.db, config)

        self.assertEqual(
            {employee.id for employee in eligible},
            {exec_emp.id, manager_emp.id},
        )

    def test_canonical_roles_and_mixed_case_are_supported(self):
        exec_emp = self._make_employee("auto_exec_case", "SALES_EXECUTIVE")
        manager_emp = self._make_employee(
            "auto_manager_case", "SALES_MANAGER"
        )

        config = self._make_config(" sales_executive , Sales_Manager ")
        eligible = get_eligible_employees(self.db, config)

        self.assertEqual(
            {employee.id for employee in eligible},
            {exec_emp.id, manager_emp.id},
        )

    def test_legacy_config_is_upgraded_and_empty_roles_use_default(self):
        self._make_config("EMPLOYEE,MANAGER")

        loaded = get_or_create_auto_assign_config(self.db)
        self.assertEqual(
            loaded.eligible_roles, "SALES_EXECUTIVE,SALES_MANAGER"
        )

        loaded.eligible_roles = ""
        self.db.commit()
        loaded = get_or_create_auto_assign_config(self.db)
        self.assertEqual(
            loaded.eligible_roles, "SALES_EXECUTIVE,SALES_MANAGER"
        )

    def test_update_endpoint_saves_canonical_roles(self):
        admin = User(
            username="auto_admin",
            hashed_password="not-used-in-tests",
            role="ADMIN",
            is_active=True,
        )
        self.db.add(admin)
        self.db.commit()
        self.db.refresh(admin)

        payload = AutoAssignConfigUpdate(
            enabled=True,
            waiting_time_minutes=45,
            assignment_method="ROUND_ROBIN",
            eligible_roles="EMPLOYEE,MANAGER",
            working_hours_enabled=False,
            working_hours_start="09:00",
            working_hours_end="18:00",
        )
        updated = update_auto_assign_config(
            config_in=payload, db=self.db, current_user=admin
        )

        self.assertEqual(
            updated.eligible_roles, "SALES_EXECUTIVE,SALES_MANAGER"
        )
        self.assertEqual(updated.waiting_time_minutes, 45)
        self.assertEqual(updated.assignment_method, "ROUND_ROBIN")

    # ------------------------------------------------------------------
    # Scheduler behaviour
    # ------------------------------------------------------------------
    def test_scheduler_assigns_new_lead_alias_and_marks_it_assigned(self):
        exec_emp = self._make_employee("auto_scheduler_exec", "SALES_EXECUTIVE")
        self._make_config("EMPLOYEE", waiting_time_minutes=0)
        lead = self._make_lead(status="NEW LEAD", age_minutes=120)

        assigned_count = auto_assign_pending_leads(self.db)

        self.assertEqual(assigned_count, 1)
        self.db.refresh(lead)
        self.assertEqual(lead.assigned_to, exec_emp.id)
        self.assertEqual(lead.status, "ASSIGNED")

        assignment = (
            self.db.query(LeadAssignment)
            .filter(LeadAssignment.lead_id == lead.id)
            .one()
        )
        self.assertEqual(assignment.assignment_method, "AUTOMATIC")
        self.assertEqual(assignment.assigned_to, exec_emp.id)

        activity = (
            self.db.query(LeadActivity)
            .filter(
                LeadActivity.lead_id == lead.id,
                LeadActivity.activity_type == "AUTO_ASSIGNED",
            )
            .one()
        )
        self.assertIn(exec_emp.name, activity.description)

    def test_waiting_time_uses_ist_created_at_clock(self):
        exec_emp = self._make_employee("auto_ist_exec", "SALES_EXECUTIVE")
        self._make_config("SALES_EXECUTIVE", waiting_time_minutes=60)
        # 90 minutes old in IST is only 90 minutes old for the configured
        # timeout. A UTC cutoff would leave this lead unassigned for hours.
        lead = self._make_lead(status="NEW", age_minutes=90)

        assigned_count = auto_assign_pending_leads(self.db)

        self.assertEqual(assigned_count, 1)
        self.db.refresh(lead)
        self.assertEqual(lead.assigned_to, exec_emp.id)

    def test_scheduler_does_not_touch_leads_inside_waiting_window(self):
        self._make_employee("auto_wait_exec", "SALES_EXECUTIVE")
        self._make_config("SALES_EXECUTIVE", waiting_time_minutes=60)
        lead = self._make_lead(status="NEW", age_minutes=30)

        assigned_count = auto_assign_pending_leads(self.db)

        self.assertEqual(assigned_count, 0)
        self.db.refresh(lead)
        self.assertIsNone(lead.assigned_to)
        self.assertEqual(lead.status, "NEW")

    def test_scheduler_skips_terminal_and_already_assigned_leads(self):
        exec_emp = self._make_employee("auto_terminal_exec", "SALES_EXECUTIVE")
        self._make_config("SALES_EXECUTIVE", waiting_time_minutes=0)

        terminal_statuses = [
            "WON",
            "CLOSED_WON",
            "CLOSED_LOST",
            "CONVERTED",
            "CONVERTED TO SUPPORT",
            "LOST",
            "NOT_INTERESTED",
            "REJECTED",
            "RNR",
            "JUNK",
            "PENDING_ONBOARDING",
        ]
        terminal_leads = [
            self._make_lead(status=status, age_minutes=120)
            for status in terminal_statuses
        ]
        already_assigned = self._make_lead(
            status="NEW LEAD", age_minutes=120, assigned_to=exec_emp.id
        )

        assigned_count = auto_assign_pending_leads(self.db)

        self.assertEqual(assigned_count, 0)
        for lead in terminal_leads:
            self.db.refresh(lead)
            self.assertIsNone(lead.assigned_to)
        self.db.refresh(already_assigned)
        self.assertEqual(already_assigned.assigned_to, exec_emp.id)

    def test_scheduler_does_nothing_when_disabled(self):
        self._make_employee("auto_disabled_exec", "SALES_EXECUTIVE")
        self._make_config(
            "SALES_EXECUTIVE", enabled=False, waiting_time_minutes=0
        )
        lead = self._make_lead(status="NEW LEAD", age_minutes=120)

        assigned_count = auto_assign_pending_leads(self.db)

        self.assertEqual(assigned_count, 0)
        self.db.refresh(lead)
        self.assertIsNone(lead.assigned_to)

    def test_least_assigned_prefers_lower_workload(self):
        busy = self._make_employee("auto_busy_exec", "SALES_EXECUTIVE")
        idle = self._make_employee("auto_idle_exec", "SALES_EXECUTIVE")
        for _ in range(2):
            self._make_lead(status="CONTACTED", assigned_to=busy.id)

        self._make_config(
            "SALES_EXECUTIVE",
            waiting_time_minutes=0,
            assignment_method="LEAST_ASSIGNED",
        )
        lead = self._make_lead(status="NEW LEAD", age_minutes=120)

        auto_assign_pending_leads(self.db)

        self.db.refresh(lead)
        self.assertEqual(lead.assigned_to, idle.id)

    def test_round_robin_prefers_least_recently_assigned(self):
        first = self._make_employee("auto_rr_first", "SALES_EXECUTIVE")
        second = self._make_employee("auto_rr_second", "SALES_EXECUTIVE")
        now = get_ist_now()
        self.db.add_all([
            LeadAssignment(
                lead_id=self._make_lead(
                    status="CONTACTED", assigned_to=first.id
                ).id,
                assigned_to=first.id,
                assigned_at=now - timedelta(hours=2),
                assignment_method="MANUAL",
            ),
            LeadAssignment(
                lead_id=self._make_lead(
                    status="CONTACTED", assigned_to=second.id
                ).id,
                assigned_to=second.id,
                assigned_at=now - timedelta(hours=1),
                assignment_method="MANUAL",
            ),
        ])
        self.db.commit()

        self._make_config(
            "SALES_EXECUTIVE",
            waiting_time_minutes=0,
            assignment_method="ROUND_ROBIN",
        )
        lead = self._make_lead(status="NEW LEAD", age_minutes=120)

        auto_assign_pending_leads(self.db)

        self.db.refresh(lead)
        self.assertEqual(lead.assigned_to, first.id)

    # ------------------------------------------------------------------
    # Immediate capture path
    # ------------------------------------------------------------------
    def test_immediate_assignment_honours_legacy_roles(self):
        exec_emp = self._make_employee("auto_immediate_exec", "SALES_EXECUTIVE")
        self._make_config("EMPLOYEE", waiting_time_minutes=60)
        lead = self._make_lead(status="NEW LEAD", age_minutes=0)

        assignee = assign_lead_immediately(self.db, lead)
        self.db.commit()
        self.db.refresh(lead)

        self.assertIsNotNone(assignee)
        self.assertEqual(assignee.id, exec_emp.id)
        self.assertEqual(lead.assigned_to, exec_emp.id)
        self.assertEqual(lead.status, "ASSIGNED")
        self.assertEqual(
            self.db.query(LeadAssignment)
            .filter(LeadAssignment.lead_id == lead.id)
            .count(),
            1,
        )


if __name__ == "__main__":
    unittest.main()
