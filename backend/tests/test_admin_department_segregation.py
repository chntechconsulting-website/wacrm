"""
Isolated Admin department segregation tests.

These tests use an in-memory SQLite database and synthetic records only. They
never connect to the live MySQL CRM database and never mutate production data.
"""

import os
import sys
import unittest
from datetime import date, datetime, timedelta

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi import HTTPException, Response
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
from models.team import Team
from models.user import User
from models.workflow import SupportHandoff
from routers.admin import (
    TeamCreateRequest,
    admin_create_team,
    admin_department_overview,
    admin_employees,
    admin_handovers,
    admin_managers,
    admin_reports,
    admin_teams,
)
from routers.followups import list_followups
from routers.ivr import list_call_logs
from services.department_service import (
    get_department_employee_ids,
    list_department_teams,
)


class AdminDepartmentSegregationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db = self.Session()

        # ------------------------------------------------------------------
        # Users / Employees
        # ------------------------------------------------------------------
        self.admin_user, self.admin_emp = self._make_person(
            "admin_test", "ADMIN", "ADMINISTRATION", role_label="Admin"
        )
        self.sales_manager_user, self.sales_manager = self._make_person(
            "sales_mgr_test",
            "SALES_MANAGER",
            "SALES",
            manager_user=self.admin_user,
            manager_emp=self.admin_emp,
        )
        self.sales_exec_a_user, self.sales_exec_a = self._make_person(
            "sales_exec_a_test",
            "SALES_EXECUTIVE",
            "SALES",
            manager_user=self.sales_manager_user,
            manager_emp=self.sales_manager,
        )
        self.sales_exec_b_user, self.sales_exec_b = self._make_person(
            "sales_exec_b_test",
            "SALES_EXECUTIVE",
            "SALES",
            manager_user=self.sales_manager_user,
            manager_emp=self.sales_manager,
        )
        # Legacy row with no department: must fall back to its role department.
        self.sales_legacy_user, self.sales_legacy = self._make_person(
            "sales_legacy_test",
            "SALES_EXECUTIVE",
            None,
            manager_user=self.sales_manager_user,
            manager_emp=self.sales_manager,
        )
        self.support_manager_user, self.support_manager = self._make_person(
            "support_mgr_test",
            "SUPPORT_MANAGER",
            "SUPPORT",
            manager_user=self.admin_user,
            manager_emp=self.admin_emp,
        )
        self.support_exec_user, self.support_exec = self._make_person(
            "support_exec_test",
            "SUPPORT_EXECUTIVE",
            "SUPPORT",
            manager_user=self.support_manager_user,
            manager_emp=self.support_manager,
        )

        # ------------------------------------------------------------------
        # Leads / customers / follow-ups
        # ------------------------------------------------------------------
        self.lead_sales = Lead(
            name="Alpha Sales Lead",
            phone="9000000001",
            status="NEW",
            assigned_to=self.sales_exec_a.id,
        )
        self.lead_sales_won = Lead(
            name="Beta Won Lead",
            phone="9000000002",
            status="CONVERTED",
            assigned_to=self.sales_exec_b.id,
        )
        self.lead_support = Lead(
            name="Gamma Support Lead",
            phone="9000000003",
            status="NEW",
            assigned_to=self.support_exec.id,
        )
        self.db.add_all([self.lead_sales, self.lead_sales_won, self.lead_support])
        self.db.commit()
        for lead in (self.lead_sales, self.lead_sales_won, self.lead_support):
            self.db.refresh(lead)

        self.followup_sales_a = Followup(
            lead_id=self.lead_sales.id,
            assigned_to=self.sales_exec_a.id,
            created_by=self.sales_exec_a.id,
            followup_date=date.today() - timedelta(days=1),
            followup_time="10:00 AM",
            notes="[ADMIN-SEGREGATION-TEST] overdue sales followup",
            priority="HIGH",
            status="Pending",
        )
        self.followup_sales_b = Followup(
            lead_id=self.lead_sales_won.id,
            assigned_to=self.sales_exec_b.id,
            created_by=self.sales_exec_b.id,
            followup_date=date.today(),
            followup_time="11:00 AM",
            notes="[ADMIN-SEGREGATION-TEST] sales followup",
            priority="MEDIUM",
            status="Pending",
        )
        self.followup_support = Followup(
            lead_id=self.lead_support.id,
            assigned_to=self.support_exec.id,
            created_by=self.support_exec.id,
            followup_date=date.today(),
            followup_time="12:00 PM",
            notes="[ADMIN-SEGREGATION-TEST] support followup",
            priority="LOW",
            status="Completed",
        )
        self.db.add_all(
            [self.followup_sales_a, self.followup_sales_b, self.followup_support]
        )

        # ------------------------------------------------------------------
        # Calls (including one unassigned call)
        # ------------------------------------------------------------------
        self.db.add_all(
            [
                CallLog(
                    lead_id=self.lead_sales.id,
                    employee_id=self.sales_exec_a.id,
                    provider="DOOCTI",
                    provider_call_id="admin-seg-call-sales-1",
                    from_number="9000000001",
                    to_number="1001",
                    call_status="COMPLETED",
                    call_direction="OUTBOUND",
                    duration_seconds=60,
                ),
                CallLog(
                    lead_id=self.lead_sales_won.id,
                    employee_id=self.sales_exec_b.id,
                    provider="DOOCTI",
                    provider_call_id="admin-seg-call-sales-2",
                    from_number="9000000002",
                    to_number="1002",
                    call_status="MISSED",
                    call_direction="INBOUND",
                    duration_seconds=0,
                ),
                CallLog(
                    lead_id=self.lead_support.id,
                    employee_id=self.support_exec.id,
                    provider="DOOCTI",
                    provider_call_id="admin-seg-call-support-1",
                    from_number="9000000003",
                    to_number="1003",
                    call_status="ANSWERED",
                    call_direction="INBOUND",
                    duration_seconds=30,
                ),
                CallLog(
                    employee_id=None,
                    provider="DOOCTI",
                    provider_call_id="admin-seg-call-unassigned",
                    from_number="9999999999",
                    to_number="1000",
                    call_status="COMPLETED",
                    call_direction="INBOUND",
                    duration_seconds=10,
                ),
            ]
        )

        # ------------------------------------------------------------------
        # Customers / handovers
        # ------------------------------------------------------------------
        self.customer_alpha = Customer(
            company_name="Alpha Industries",
            contact_name="Alpha Contact",
            phone="9000000001",
        )
        self.customer_beta = Customer(
            company_name="Beta Industries",
            contact_name="Beta Contact",
            phone="9000000002",
        )
        self.db.add_all([self.customer_alpha, self.customer_beta])
        self.db.commit()
        self.db.refresh(self.customer_alpha)
        self.db.refresh(self.customer_beta)

        self.handover_explicit = SupportHandoff(
            lead_id=self.lead_sales.id,
            customer_id=self.customer_alpha.id,
            customer_name="Alpha Contact",
            company_name="Alpha Industries",
            phone="9000000001",
            email="alpha@example.com",
            product_service="CRM Cloud Pro",
            total_deal_amount=125000,
            paid_amount=125000,
            payment_status="PAID",
            sales_employee_id=self.sales_exec_a.id,
            sales_employee_name="Sales Exec A",
            support_manager_id=self.support_manager.id,
            support_manager_name="Support Manager",
            assigned_agent_id=self.support_exec.id,
            assigned_agent_name="Support Exec",
            onboarding_status="PENDING_ONBOARDING",
            created_at=datetime.utcnow() - timedelta(days=2),
        )
        # No explicit Sales attribution: Admin view must fall back to the lead
        # owner for display only, without modifying the handoff row.
        self.handover_lead_owner = SupportHandoff(
            lead_id=self.lead_sales_won.id,
            customer_id=self.customer_beta.id,
            customer_name="Beta Contact",
            company_name="Beta Industries",
            phone="9000000002",
            product_service="WhatsApp Suite",
            total_deal_amount=75000,
            paid_amount=75000,
            payment_status="PAID",
            sales_employee_id=None,
            support_manager_id=self.support_manager.id,
            support_manager_name="Support Manager",
            assigned_agent_id=None,
            onboarding_status="COMPLETED",
            created_at=datetime.utcnow() - timedelta(days=1),
        )
        self.db.add_all([self.handover_explicit, self.handover_lead_owner])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _make_person(
        self,
        username,
        role,
        department,
        manager_user=None,
        manager_emp=None,
        role_label=None,
    ):
        display = role_label or username.replace("_", " ").title()
        user = User(
            username=username,
            hashed_password="not-used-in-tests",
            role=role,
            department=department,
            reporting_manager_id=manager_user.id if manager_user else None,
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        employee = Employee(
            user_id=user.id,
            manager_id=manager_emp.id if manager_emp else None,
            reporting_manager_id=manager_user.id if manager_user else None,
            department=department,
            name=display,
            email=f"{username}@example.test",
            phone=f"98{user.id:08d}"[:10],
            username=username,
            role=role,
            status="ACTIVE",
        )
        self.db.add(employee)
        self.db.commit()
        self.db.refresh(employee)
        return user, employee

    def _call_logs(self, user, department=None):
        return list_call_logs(
            response=Response(),
            lead_id=None,
            employee_id=None,
            call_status=None,
            direction=None,
            call_direction=None,
            provider=None,
            department=department,
            search=None,
            page=1,
            limit=50,
            db=self.db,
            current_user=user,
        )

    def _followups(self, user, department=None):
        return list_followups(
            status_filter=None,
            status=None,
            priority_filter=None,
            priority=None,
            date_filter=None,
            search=None,
            assigned_to_filter=None,
            assigned_to=None,
            department=department,
            upcoming_only=False,
            db=self.db,
            current_user=user,
        )

    # ------------------------------------------------------------------
    # 1. Department overview
    # ------------------------------------------------------------------
    def test_01_overview_separates_sales_support_and_company(self):
        overview = admin_department_overview(
            date_from=None,
            date_to=None,
            db=self.db,
            current_user=self.admin_user,
        )

        self.assertEqual(len(overview["departments"]), 2)
        sales, support = overview["departments"]
        self.assertEqual(sales["key"], "SALES")
        self.assertEqual(support["key"], "SUPPORT")

        # Manager + 2 executives + legacy employee (role fallback).
        self.assertEqual(sales["employees"]["total"], 4)
        self.assertEqual(sales["employees"]["managers"], 1)
        self.assertEqual(sales["employees"]["executives"], 3)
        # Support manager + 1 executive.
        self.assertEqual(support["employees"]["total"], 2)

        # One manager-led team each; registered table is still empty here.
        self.assertEqual(sales["teams"]["total"], 1)
        self.assertEqual(sales["teams"]["registered"], 0)
        self.assertEqual(sales["teams"]["implicit"], 1)
        self.assertEqual(sales["teams"]["people"], 4)
        self.assertEqual(support["teams"]["total"], 1)
        self.assertEqual(support["teams"]["people"], 2)

        # Department-scoped records.
        self.assertEqual(sales["calls"]["total"], 2)
        self.assertEqual(sales["calls"]["inbound"], 1)
        self.assertEqual(sales["calls"]["outbound"], 1)
        self.assertEqual(sales["calls"]["connected"], 1)
        self.assertEqual(sales["calls"]["missed"], 1)
        self.assertEqual(support["calls"]["total"], 1)
        self.assertEqual(sales["followups"]["total"], 2)
        self.assertEqual(sales["followups"]["overdue"], 1)
        self.assertEqual(support["followups"]["total"], 1)
        self.assertEqual(sales["leads"]["total"], 2)
        self.assertEqual(sales["leads"]["converted"], 1)

        # Handover attribution: explicit Sales employee + lead-owner fallback.
        self.assertEqual(sales["handovers"]["total"], 2)
        self.assertEqual(support["handovers"]["total"], 2)
        self.assertEqual(sales["handovers"]["completed"], 1)
        self.assertEqual(sales["handovers"]["unassigned"], 1)

        # Company-wide includes Administration and the unassigned call.
        self.assertEqual(overview["company"]["employees"]["total"], 7)
        self.assertEqual(overview["company"]["calls"]["total"], 4)
        self.assertEqual(overview["company"]["followups"]["total"], 3)
        self.assertEqual(overview["company"]["handovers"]["total"], 2)

        # Combined Sales + Support excludes Administration and unassigned calls.
        self.assertEqual(overview["combined"]["employees"]["total"], 6)
        self.assertEqual(overview["combined"]["calls"]["total"], 3)
        self.assertEqual(overview["combined"]["followups"]["total"], 3)
        self.assertEqual(overview["combined"]["handovers"]["total"], 2)

    # ------------------------------------------------------------------
    # 2. Employee filtering / department assignment
    # ------------------------------------------------------------------
    def test_02_employee_filter_uses_employee_department_and_role_fallback(self):
        sales = admin_employees(
            department="SALES",
            status_filter="ACTIVE",
            search=None,
            db=self.db,
            current_user=self.admin_user,
        )
        support = admin_employees(
            department="SUPPORT",
            status_filter="ACTIVE",
            search=None,
            db=self.db,
            current_user=self.admin_user,
        )
        all_departments = admin_employees(
            department=None,
            status_filter="ALL",
            search=None,
            db=self.db,
            current_user=self.admin_user,
        )
        legacy_search = admin_employees(
            department="SALES",
            status_filter=None,
            search="legacy",
            db=self.db,
            current_user=self.admin_user,
        )

        self.assertEqual(sales["total"], 4)
        self.assertEqual(support["total"], 2)
        self.assertEqual(all_departments["total"], 6)  # Admin Department excluded

        sales_ids = {item["id"] for item in sales["items"]}
        support_ids = {item["id"] for item in support["items"]}
        self.assertIn(self.sales_legacy.id, sales_ids)
        self.assertIn(self.support_exec.id, support_ids)
        self.assertNotIn(self.admin_emp.id, sales_ids | support_ids)

        legacy = next(item for item in sales["items"] if item["id"] == self.sales_legacy.id)
        self.assertEqual(legacy["department"], "SALES")
        self.assertEqual(legacy["manager_id"], self.sales_manager.id)
        self.assertEqual(
            legacy["reporting_manager_id"], self.sales_manager_user.id
        )

        self.assertEqual(legacy_search["total"], 1)
        self.assertEqual(legacy_search["items"][0]["id"], self.sales_legacy.id)

    # ------------------------------------------------------------------
    # 3. Teams are derived from existing manager hierarchies
    # ------------------------------------------------------------------
    def test_03_teams_use_manager_hierarchy_and_registered_team_replaces_implicit(self):
        before = admin_teams(
            department="SALES",
            db=self.db,
            current_user=self.admin_user,
        )
        self.assertEqual(before["total"], 1)
        self.assertFalse(before["items"][0]["registered"])
        self.assertEqual(before["items"][0]["manager_id"], self.sales_manager.id)
        self.assertEqual(before["items"][0]["member_count"], 3)

        support_before = admin_teams(
            department="SUPPORT",
            db=self.db,
            current_user=self.admin_user,
        )
        self.assertEqual(support_before["total"], 1)
        self.assertEqual(support_before["items"][0]["member_count"], 1)

        created = admin_create_team(
            payload=TeamCreateRequest(
                name="Enterprise Sales",
                department="SALES",
                manager_id=self.sales_manager.id,
                description="Registered test team",
            ),
            db=self.db,
            current_user=self.admin_user,
        )
        self.assertTrue(created["registered"])
        self.assertEqual(created["name"], "Enterprise Sales")
        self.assertEqual(created["member_count"], 3)

        after = admin_teams(
            department="SALES",
            db=self.db,
            current_user=self.admin_user,
        )
        self.assertEqual(after["total"], 1, "Registered team must replace implicit team")
        self.assertTrue(after["items"][0]["registered"])
        self.assertEqual(after["items"][0]["id"], created["id"])

        # Employee records/IDs are unchanged.
        self.assertEqual(
            self.db.query(Employee).filter(Employee.id == self.sales_manager.id).count(),
            1,
        )
        self.assertEqual(self.db.query(Team).count(), 1)

    # ------------------------------------------------------------------
    # 4. Team creation validation
    # ------------------------------------------------------------------
    def test_04_team_creation_rejects_cross_department_and_duplicates(self):
        with self.assertRaises(HTTPException) as cross_department:
            admin_create_team(
                payload=TeamCreateRequest(
                    name="Invalid Support Team",
                    department="SALES",
                    manager_id=self.support_manager.id,
                ),
                db=self.db,
                current_user=self.admin_user,
            )
        self.assertEqual(cross_department.exception.status_code, 400)

        with self.assertRaises(HTTPException) as invalid_department:
            admin_create_team(
                payload=TeamCreateRequest(
                    name="Finance Team",
                    department="FINANCE",
                    manager_id=self.sales_manager.id,
                ),
                db=self.db,
                current_user=self.admin_user,
            )
        self.assertEqual(invalid_department.exception.status_code, 400)

        admin_create_team(
            payload=TeamCreateRequest(
                name="Enterprise Sales",
                department="SALES",
                manager_id=self.sales_manager.id,
            ),
            db=self.db,
            current_user=self.admin_user,
        )
        with self.assertRaises(HTTPException) as duplicate_manager:
            admin_create_team(
                payload=TeamCreateRequest(
                    name="Second Sales Team",
                    department="SALES",
                    manager_id=self.sales_manager.id,
                ),
                db=self.db,
                current_user=self.admin_user,
            )
        self.assertEqual(duplicate_manager.exception.status_code, 400)

        # No duplicate employee/team row was created by failed attempts.
        self.assertEqual(self.db.query(Team).count(), 1)

    def test_05_manager_endpoint_is_department_scoped(self):
        sales_managers = admin_managers(
            department="SALES", db=self.db, current_user=self.admin_user
        )
        support_managers = admin_managers(
            department="SUPPORT", db=self.db, current_user=self.admin_user
        )

        self.assertEqual(sales_managers["total"], 1)
        self.assertEqual(sales_managers["items"][0]["id"], self.sales_manager.id)
        self.assertEqual(
            sales_managers["items"][0]["user_id"], self.sales_manager_user.id
        )
        self.assertTrue(sales_managers["items"][0]["can_create_team"])

        self.assertEqual(support_managers["total"], 1)
        self.assertEqual(support_managers["items"][0]["id"], self.support_manager.id)
        self.assertNotIn(
            self.sales_manager.id,
            {item["id"] for item in support_managers["items"]},
        )

        with self.assertRaises(HTTPException) as missing_department:
            admin_managers(
                department="ALL", db=self.db, current_user=self.admin_user
            )
        self.assertEqual(missing_department.exception.status_code, 400)

    # ------------------------------------------------------------------
    # 6. Call log department filter
    # ------------------------------------------------------------------
    def test_06_call_log_department_filter_is_backend_scoped_and_admin_only(self):
        all_calls = self._call_logs(self.admin_user)
        sales_calls = self._call_logs(self.admin_user, "SALES")
        support_calls = self._call_logs(self.admin_user, "SUPPORT")

        self.assertEqual(all_calls.total, 4)
        self.assertEqual(sales_calls.total, 2)
        self.assertEqual(support_calls.total, 1)
        self.assertEqual(sales_calls.metrics.total_calls, 2)
        self.assertEqual(support_calls.metrics.total_calls, 1)

        sales_employee_ids = set(get_department_employee_ids(self.db, "SALES"))
        for item in sales_calls.items:
            self.assertIn(item.employee_id, sales_employee_ids)

        with self.assertRaises(HTTPException) as non_admin:
            self._call_logs(self.sales_exec_a_user, "SALES")
        self.assertEqual(non_admin.exception.status_code, 403)

        with self.assertRaises(HTTPException) as invalid_filter:
            self._call_logs(self.admin_user, "FINANCE")
        self.assertEqual(invalid_filter.exception.status_code, 400)

    # ------------------------------------------------------------------
    # 7. Follow-up department filter
    # ------------------------------------------------------------------
    def test_07_followup_department_filter_is_backend_scoped_and_admin_only(self):
        all_followups = self._followups(self.admin_user)
        sales_followups = self._followups(self.admin_user, "SALES")
        support_followups = self._followups(self.admin_user, "SUPPORT")

        self.assertEqual(len(all_followups), 3)
        self.assertEqual(len(sales_followups), 2)
        self.assertEqual(len(support_followups), 1)
        self.assertTrue(
            all(item.assigned_to in get_department_employee_ids(self.db, "SALES") for item in sales_followups)
        )
        self.assertEqual(
            support_followups[0].assigned_to,
            self.support_exec.id,
        )

        with self.assertRaises(HTTPException) as non_admin:
            self._followups(self.sales_exec_a_user, "SALES")
        self.assertEqual(non_admin.exception.status_code, 403)

    # ------------------------------------------------------------------
    # 8. Reports agree with the same department scoping
    # ------------------------------------------------------------------
    def test_08_reports_match_department_record_filters(self):
        sales_report = admin_reports(
            department="SALES",
            date_from=None,
            date_to=None,
            db=self.db,
            current_user=self.admin_user,
        )
        all_report = admin_reports(
            department="ALL",
            date_from=None,
            date_to=None,
            db=self.db,
            current_user=self.admin_user,
        )

        self.assertEqual(len(sales_report["departments"]), 1)
        sales_stats = sales_report["departments"][0]
        self.assertEqual(sales_stats["calls"]["total"], 2)
        self.assertEqual(sales_stats["followups"]["total"], 2)
        self.assertEqual(sales_stats["employees"]["total"], 4)
        self.assertEqual(sales_stats["handovers"]["total"], 2)
        self.assertEqual(sales_report["combined"]["calls"]["total"], 3)
        self.assertEqual(sales_report["company"]["calls"]["total"], 4)

        self.assertEqual(len(all_report["departments"]), 2)
        report_by_key = {item["key"]: item for item in all_report["departments"]}
        self.assertEqual(report_by_key["SALES"]["calls"]["total"], 2)
        self.assertEqual(report_by_key["SUPPORT"]["calls"]["total"], 1)
        self.assertEqual(report_by_key["SALES"]["followups"]["total"], 2)
        self.assertEqual(report_by_key["SUPPORT"]["followups"]["total"], 1)

        future = admin_reports(
            department="ALL",
            date_from="2099-01-01",
            date_to="2099-12-31",
            db=self.db,
            current_user=self.admin_user,
        )
        self.assertEqual(future["company"]["calls"]["total"], 0)
        self.assertEqual(future["company"]["followups"]["total"], 0)
        self.assertEqual(future["company"]["handovers"]["total"], 0)

        with self.assertRaises(HTTPException) as invalid_department:
            admin_reports(
                department="FINANCE",
                date_from=None,
                date_to=None,
                db=self.db,
                current_user=self.admin_user,
            )
        self.assertEqual(invalid_department.exception.status_code, 400)

        with self.assertRaises(HTTPException) as invalid_date:
            admin_reports(
                department="ALL",
                date_from="not-a-date",
                date_to=None,
                db=self.db,
                current_user=self.admin_user,
            )
        self.assertEqual(invalid_date.exception.status_code, 400)

    # ------------------------------------------------------------------
    # 9. Handover monitoring
    # ------------------------------------------------------------------
    def test_09_handover_monitoring_preserves_attribution_and_history(self):
        result = admin_handovers(
            status_filter=None,
            search=None,
            page=1,
            limit=50,
            db=self.db,
            current_user=self.admin_user,
        )
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["status_counts"].get("PENDING_ONBOARDING"), 1)
        self.assertEqual(result["status_counts"].get("COMPLETED"), 1)

        by_id = {item["id"]: item for item in result["items"]}
        explicit = by_id[self.handover_explicit.id]
        self.assertEqual(explicit["sales_employee_id"], self.sales_exec_a.id)
        self.assertEqual(explicit["sales_employee_name"], "Sales Exec A Test")
        self.assertEqual(explicit["sales_employee_source"], "HANDOFF")
        self.assertEqual(explicit["support_employee_id"], self.support_exec.id)
        self.assertEqual(explicit["product_service"], "CRM Cloud Pro")
        self.assertEqual(explicit["lead_owner_id"], self.sales_exec_a.id)

        fallback = by_id[self.handover_lead_owner.id]
        self.assertIsNone(fallback["sales_employee_id"])
        self.assertEqual(fallback["sales_employee_name"], "Sales Exec B Test")
        self.assertEqual(fallback["sales_employee_source"], "LEAD_OWNER")
        self.assertEqual(fallback["lead_owner_id"], self.sales_exec_b.id)
        self.assertEqual(fallback["support_employee_name"], "Support Mgr Test")
        self.assertEqual(fallback["assigned_agent_id"], None)

        # Fetching does not mutate the stored handoff attribution.
        stored = (
            self.db.query(SupportHandoff)
            .filter(SupportHandoff.id == self.handover_lead_owner.id)
            .first()
        )
        self.assertIsNone(stored.sales_employee_id)

        filtered = admin_handovers(
            status_filter="COMPLETED",
            search=None,
            page=1,
            limit=50,
            db=self.db,
            current_user=self.admin_user,
        )
        self.assertEqual(filtered["total"], 1)
        self.assertEqual(filtered["items"][0]["id"], self.handover_lead_owner.id)

        searched = admin_handovers(
            status_filter=None,
            search="Alpha",
            page=1,
            limit=50,
            db=self.db,
            current_user=self.admin_user,
        )
        self.assertEqual(searched["total"], 1)
        self.assertEqual(searched["items"][0]["id"], self.handover_explicit.id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
