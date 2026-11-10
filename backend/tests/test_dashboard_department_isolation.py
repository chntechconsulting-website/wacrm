"""
Department isolation tests for the Sales and Support dashboards.

These tests use an in-memory SQLite database and synthetic records only. They
never connect to the live MySQL CRM database and never mutate production data.

Covered guarantees:
  * Admin Sales dashboard/API payloads contain Sales employees only.
  * Admin Support dashboard/API payloads contain Support employees only.
  * Sales managers see their Sales team, sales executives only themselves.
  * Support managers/executives never receive Sales metrics.
  * Cross-department hierarchy links cannot widen a dashboard.
  * Sales targets default to Sales; Support requires an explicit Admin view.
"""

import os
import sys
import unittest
from datetime import date, datetime, timedelta

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
from models.sales_target import SalesTarget
from models.user import User
from models.workflow import SupportHandoff
from routers.reports import (
    dashboard_stats,
    sales_overview_report,
    sales_revenue_report,
)
from routers.sales_targets import (
    create_or_update_target,
    get_companies_revenue,
    get_employee_achievements,
    get_targets,
    update_target,
)
from schemas.sales_target import (
    SalesTargetCreate,
    SalesTargetUpdate,
)
from services.permission_service import seed_default_roles_if_needed


class DashboardDepartmentIsolationTests(unittest.TestCase):
    TARGET_YEAR = 2026
    TARGET_MONTH = 6

    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db = self.Session()

        # Real role/permission rows, matching production defaults.
        seed_default_roles_if_needed(self.db)

        # ------------------------------------------------------------------
        # Sales team
        # ------------------------------------------------------------------
        self.admin_user, self.admin_emp = self._make_person(
            "isolation_admin", "ADMIN", "ADMINISTRATION", name="Isolation Admin"
        )
        self.sales_manager_user, self.sales_manager = self._make_person(
            "isolation_sales_manager",
            "SALES_MANAGER",
            "SALES",
            name="Sales Manager",
            manager_user=self.admin_user,
            manager_emp=self.admin_emp,
        )
        self.sales_a_user, self.sales_a = self._make_person(
            "isolation_sales_a",
            "SALES_EXECUTIVE",
            "SALES",
            name="Sales Executive A",
            manager_user=self.sales_manager_user,
            manager_emp=self.sales_manager,
        )
        self.sales_b_user, self.sales_b = self._make_person(
            "isolation_sales_b",
            "SALES_EXECUTIVE",
            "SALES",
            name="Sales Executive B",
            manager_user=self.sales_manager_user,
            manager_emp=self.sales_manager,
        )
        # Legacy row with no department: role fallback must place it in Sales.
        self.sales_legacy_user, self.sales_legacy = self._make_person(
            "isolation_sales_legacy",
            "SALES_EXECUTIVE",
            None,
            name="Sales Legacy",
            manager_user=self.sales_manager_user,
            manager_emp=self.sales_manager,
        )

        # ------------------------------------------------------------------
        # Support team
        # ------------------------------------------------------------------
        self.support_manager_user, self.support_manager = self._make_person(
            "isolation_support_manager",
            "SUPPORT_MANAGER",
            "SUPPORT",
            name="Support Manager",
            manager_user=self.admin_user,
            manager_emp=self.admin_emp,
        )
        self.support_a_user, self.support_a = self._make_person(
            "isolation_support_a",
            "SUPPORT_EXECUTIVE",
            "SUPPORT",
            name="Support Executive A",
            manager_user=self.support_manager_user,
            manager_emp=self.support_manager,
        )
        self.support_b_user, self.support_b = self._make_person(
            "isolation_support_b",
            "SUPPORT_EXECUTIVE",
            "SUPPORT",
            name="Support Executive B",
            manager_user=self.support_manager_user,
            manager_emp=self.support_manager,
        )
        # Cross-department reporting link: a Support employee reports to the
        # Sales Manager. Department membership must still win.
        self.support_cross_user, self.support_cross = self._make_person(
            "isolation_support_cross",
            "SUPPORT_EXECUTIVE",
            "SUPPORT",
            name="Support Cross Team",
            manager_user=self.sales_manager_user,
            manager_emp=self.sales_manager,
        )

        # ------------------------------------------------------------------
        # Leads / calls / follow-ups
        # ------------------------------------------------------------------
        self.sales_a_lead = Lead(
            name="Sales A Lead",
            phone="9200000001",
            status="NEW",
            source="Meta Ads",
            city="Chennai",
            assigned_to=self.sales_a.id,
        )
        self.sales_b_lead = Lead(
            name="Sales B Won Lead",
            phone="9200000002",
            status="CONVERTED",
            source="Referral",
            city="Coimbatore",
            assigned_to=self.sales_b.id,
        )
        self.support_a_lead = Lead(
            name="Support A Lead",
            phone="9200000003",
            status="NEW",
            source="Meta Ads",
            city="Madurai",
            assigned_to=self.support_a.id,
        )
        self.support_cross_lead = Lead(
            name="Support Cross Lead",
            phone="9200000004",
            status="NEW",
            source="Referral",
            city="Salem",
            assigned_to=self.support_cross.id,
        )
        # A won Support deal must never be treated as Sales revenue.
        self.support_won_lead = Lead(
            name="Support Won Lead",
            phone="9200000005",
            status="CONVERTED",
            source="Referral",
            city="Tiruchirappalli",
            assigned_to=self.support_a.id,
        )
        self.db.add_all([
            self.sales_a_lead,
            self.sales_b_lead,
            self.support_a_lead,
            self.support_cross_lead,
            self.support_won_lead,
        ])
        self.db.commit()
        for lead in (
            self.sales_a_lead,
            self.sales_b_lead,
            self.support_a_lead,
            self.support_cross_lead,
            self.support_won_lead,
        ):
            self.db.refresh(lead)

        self.db.add_all([
            CallLog(
                lead_id=self.sales_a_lead.id,
                employee_id=self.sales_a.id,
                provider="DOOCTI",
                provider_call_id="isolation-call-sales-a",
                from_number="9200000001",
                to_number="1001",
                call_status="COMPLETED",
                call_direction="OUTBOUND",
                duration_seconds=60,
            ),
            CallLog(
                lead_id=self.sales_b_lead.id,
                employee_id=self.sales_b.id,
                provider="DOOCTI",
                provider_call_id="isolation-call-sales-b",
                from_number="9200000002",
                to_number="1002",
                call_status="ANSWERED",
                call_direction="INBOUND",
                duration_seconds=30,
            ),
            CallLog(
                lead_id=self.support_a_lead.id,
                employee_id=self.support_a.id,
                provider="DOOCTI",
                provider_call_id="isolation-call-support-a",
                from_number="9200000003",
                to_number="1003",
                call_status="MISSED",
                call_direction="INBOUND",
                duration_seconds=0,
            ),
        ])

        self.sales_a_followup = Followup(
            lead_id=self.sales_a_lead.id,
            assigned_to=self.sales_a.id,
            created_by=self.sales_a.id,
            followup_date=date.today() + timedelta(days=1),
            followup_time="10:00 AM",
            notes="[ISOLATION] Sales A follow-up",
            priority="HIGH",
            status="Pending",
            creator_department="SALES",
            assigned_department="SALES",
            owner_department="SALES",
        )
        self.sales_b_followup = Followup(
            lead_id=self.sales_b_lead.id,
            assigned_to=self.sales_b.id,
            created_by=self.sales_b.id,
            followup_date=date.today() + timedelta(days=2),
            followup_time="11:00 AM",
            notes="[ISOLATION] Sales B follow-up",
            priority="MEDIUM",
            status="Pending",
            creator_department="SALES",
            assigned_department="SALES",
            owner_department="SALES",
        )
        self.support_a_followup = Followup(
            lead_id=self.support_a_lead.id,
            assigned_to=self.support_a.id,
            created_by=self.support_a.id,
            followup_date=date.today() + timedelta(days=1),
            followup_time="12:00 PM",
            notes="[ISOLATION] Support A follow-up",
            priority="LOW",
            status="Pending",
            creator_department="SUPPORT",
            assigned_department="SUPPORT",
            owner_department="SUPPORT",
        )
        self.support_cross_followup = Followup(
            lead_id=self.support_cross_lead.id,
            assigned_to=self.support_cross.id,
            created_by=self.support_cross.id,
            followup_date=date.today() + timedelta(days=3),
            followup_time="01:00 PM",
            notes="[ISOLATION] Support cross follow-up",
            priority="LOW",
            status="Pending",
            creator_department="SUPPORT",
            assigned_department="SUPPORT",
            owner_department="SUPPORT",
        )
        self.db.add_all([
            self.sales_a_followup,
            self.sales_b_followup,
            self.support_a_followup,
            self.support_cross_followup,
        ])

        # ------------------------------------------------------------------
        # Support handovers (one legacy row names a Sales agent incorrectly)
        # ------------------------------------------------------------------
        self.customer = Customer(
            company_name="Isolation Industries",
            contact_name="Isolation Contact",
            phone="9200000001",
        )
        self.db.add(self.customer)
        self.db.commit()
        self.db.refresh(self.customer)

        self.db.add_all([
            SupportHandoff(
                lead_id=self.support_a_lead.id,
                customer_id=self.customer.id,
                customer_name="Support A Customer",
                company_name="Isolation Industries",
                product_service="CRM Subscription",
                sales_employee_id=self.sales_a.id,
                sales_employee_name=self.sales_a.name,
                support_manager_id=self.support_manager.id,
                support_manager_name=self.support_manager.name,
                assigned_agent_id=self.support_a.id,
                assigned_agent_name=self.support_a.name,
                onboarding_status="PENDING_ONBOARDING",
                created_at=datetime.utcnow() - timedelta(days=3),
            ),
            SupportHandoff(
                lead_id=self.support_cross_lead.id,
                customer_id=self.customer.id,
                customer_name="Support B Customer",
                company_name="Isolation Industries",
                product_service="WhatsApp Suite",
                sales_employee_id=self.sales_b.id,
                sales_employee_name=self.sales_b.name,
                support_manager_id=self.support_manager.id,
                support_manager_name=self.support_manager.name,
                assigned_agent_id=self.support_b.id,
                # Stale free-text label: the Support ID is authoritative and
                # the dashboard must display the canonical Support name.
                assigned_agent_name=self.sales_a.name,
                onboarding_status="CONTACTED",
                created_at=datetime.utcnow() - timedelta(days=2),
            ),
            # Legacy data anomaly: a Support handover still names a Sales
            # employee as its assigned agent. It must never enter Support ranks.
            SupportHandoff(
                lead_id=self.sales_a_lead.id,
                customer_id=self.customer.id,
                customer_name="Legacy Misassigned Customer",
                company_name="Isolation Industries",
                product_service="CRM Subscription",
                sales_employee_id=self.sales_a.id,
                sales_employee_name=self.sales_a.name,
                support_manager_id=self.support_manager.id,
                support_manager_name=self.support_manager.name,
                assigned_agent_id=self.sales_a.id,
                assigned_agent_name=self.sales_a.name,
                onboarding_status="ONBOARDING_IN_PROGRESS",
                created_at=datetime.utcnow() - timedelta(days=1),
            ),
        ])

        # ------------------------------------------------------------------
        # Targets: one Support target must never appear in a Sales view
        # ------------------------------------------------------------------
        self.sales_a_target = SalesTarget(
            employee_id=self.sales_a.id,
            target_amount=500000.0,
            period_type="monthly",
            period_month=self.TARGET_MONTH,
            period_year=self.TARGET_YEAR,
            created_by=self.admin_user.id,
        )
        self.sales_b_target = SalesTarget(
            employee_id=self.sales_b.id,
            target_amount=250000.0,
            period_type="monthly",
            period_month=self.TARGET_MONTH,
            period_year=self.TARGET_YEAR,
            created_by=self.admin_user.id,
        )
        self.support_a_target = SalesTarget(
            employee_id=self.support_a.id,
            target_amount=100000.0,
            period_type="monthly",
            period_month=self.TARGET_MONTH,
            period_year=self.TARGET_YEAR,
            created_by=self.admin_user.id,
        )
        self.db.add_all([
            self.sales_a_target,
            self.sales_b_target,
            self.support_a_target,
        ])
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
        name=None,
        manager_user=None,
        manager_emp=None,
    ):
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
            name=name or username.replace("_", " ").title(),
            email=f"{username}@example.test",
            phone=f"96{user.id:08d}"[:10],
            username=username,
            role=role,
            status="ACTIVE",
        )
        self.db.add(employee)
        self.db.commit()
        self.db.refresh(employee)
        return user, employee

    def _names(self, records, key="name"):
        return {record[key] if isinstance(record, dict) else getattr(record, key) for record in records}

    def _dashboard(self, user):
        return dashboard_stats(db=self.db, current_user=user)

    def _overview(self, user, **kwargs):
        return sales_overview_report(db=self.db, current_user=user, **kwargs)

    def _revenue(self, user, **kwargs):
        return sales_revenue_report(db=self.db, current_user=user, **kwargs)

    def _achievements(self, user, department=None, employee_id=None):
        return get_employee_achievements(
            period_year=self.TARGET_YEAR,
            period_month=self.TARGET_MONTH,
            period_type="monthly",
            department=department,
            employee_id=employee_id,
            db=self.db,
            current_user=user,
        )

    def _targets(self, user, employee_id=None):
        return get_targets(
            period_year=self.TARGET_YEAR,
            period_month=self.TARGET_MONTH,
            period_type="monthly",
            employee_id=employee_id,
            db=self.db,
            current_user=user,
        )

    # ------------------------------------------------------------------
    # 1. Admin: Sales and Support payloads stay separate
    # ------------------------------------------------------------------
    def test_01_admin_dashboard_separates_sales_and_support_payloads(self):
        payload = self._dashboard(self.admin_user)

        self.assertEqual(payload["dashboard_type"], "both")
        self.assertEqual(
            payload["available_dashboards"], ["sales", "support", "finance"]
        )

        sales_names = {
            self.sales_manager.name,
            self.sales_a.name,
            self.sales_b.name,
            self.sales_legacy.name,
        }
        support_names = {
            self.support_manager.name,
            self.support_a.name,
            self.support_b.name,
            self.support_cross.name,
        }

        # Top-level Sales block: Sales employees only.
        self.assertEqual(self._names(payload["team_performance"]), sales_names)
        self.assertEqual(self._names(payload["employee_lead_counts"], "employee_name"), sales_names)
        self.assertEqual(
            {item["department"] for item in payload["employee_lead_counts"]},
            {"SALES"},
        )
        self.assertEqual(payload["total_leads"], 2)
        self.assertEqual(payload["converted_leads"], 1)
        self.assertEqual(
            {item["id"] for item in payload["recent_meta_leads"]},
            {self.sales_a_lead.id},
        )
        self.assertEqual(
            {item["id"] for item in payload["upcoming_followups"]},
            {self.sales_a_followup.id, self.sales_b_followup.id},
        )

        # Support block: Support employees only, no Sales agent rankings.
        support = payload["support"]
        self.assertEqual(
            self._names(support["agent_workload"]),
            {self.support_a.name, self.support_b.name},
        )
        self.assertNotIn(self.sales_a.name, self._names(support["agent_workload"]))
        self.assertEqual(
            {item["id"] for item in support["upcoming_followups"]},
            {self.support_a_followup.id, self.support_cross_followup.id},
        )
        self.assertEqual(support["customer_followups"], 2)
        self.assertEqual(support["total_tickets"], 3)
        self.assertEqual(
            self._names(support["agent_workload"]) & support_names,
            {self.support_a.name, self.support_b.name},
        )

        tickets_by_customer = {
            ticket["customer_name"]: ticket for ticket in support["recent_tickets"]
        }
        self.assertEqual(
            tickets_by_customer["Support B Customer"]["assigned_agent_name"],
            self.support_b.name,
        )
        self.assertEqual(
            tickets_by_customer["Legacy Misassigned Customer"]["assigned_agent_name"],
            "Unassigned",
        )
        self.assertFalse(
            {
                ticket["assigned_agent_name"]
                for ticket in support["recent_tickets"]
                if ticket["assigned_agent_name"]
            }
            & {
                self.sales_manager.name,
                self.sales_a.name,
                self.sales_b.name,
                self.sales_legacy.name,
            }
        )
        self.assertFalse(
            {
                ticket["support_manager_name"]
                for ticket in support["recent_tickets"]
                if ticket["support_manager_name"]
            }
            & {
                self.sales_manager.name,
                self.sales_a.name,
                self.sales_b.name,
                self.sales_legacy.name,
            }
        )

    # ------------------------------------------------------------------
    # 2. Sales manager: only their Sales team
    # ------------------------------------------------------------------
    def test_02_sales_manager_dashboard_is_team_and_department_scoped(self):
        payload = self._dashboard(self.sales_manager_user)

        self.assertEqual(payload["dashboard_type"], "sales")
        expected_team = {
            self.sales_manager.name,
            self.sales_a.name,
            self.sales_b.name,
            self.sales_legacy.name,
        }
        self.assertEqual(self._names(payload["team_performance"]), expected_team)
        self.assertEqual(self._names(payload["employee_lead_counts"], "employee_name"), expected_team)
        # Cross-department reportee is a Support employee, not a Sales metric.
        self.assertNotIn(self.support_cross.name, self._names(payload["team_performance"]))
        self.assertNotIn(self.support_a.name, self._names(payload["team_performance"]))
        # Only the Sales team's leads are counted.
        self.assertEqual(payload["total_leads"], 2)
        self.assertEqual(
            {item["id"] for item in payload["upcoming_followups"]},
            {self.sales_a_followup.id, self.sales_b_followup.id},
        )

    # ------------------------------------------------------------------
    # 3. Sales executive: only themselves
    # ------------------------------------------------------------------
    def test_03_sales_executive_dashboard_contains_only_self(self):
        payload = self._dashboard(self.sales_a_user)

        self.assertEqual(payload["dashboard_type"], "sales")
        self.assertEqual(self._names(payload["team_performance"]), {self.sales_a.name})
        self.assertEqual(
            self._names(payload["employee_lead_counts"], "employee_name"),
            {self.sales_a.name},
        )
        self.assertEqual(payload["total_leads"], 1)
        self.assertEqual(
            {item["id"] for item in payload["upcoming_followups"]},
            {self.sales_a_followup.id},
        )

    # ------------------------------------------------------------------
    # 4. Support-only payloads never expose Sales performance
    # ------------------------------------------------------------------
    def test_04_support_users_receive_support_only_data(self):
        manager_payload = self._dashboard(self.support_manager_user)
        self.assertEqual(manager_payload["dashboard_type"], "support")
        for sales_key in (
            "total_leads",
            "team_performance",
            "employee_lead_counts",
            "source_lead_counts",
            "status_lead_counts",
        ):
            self.assertNotIn(sales_key, manager_payload)

        manager_support = manager_payload["support"]
        self.assertEqual(
            self._names(manager_support["agent_workload"]),
            {self.support_a.name, self.support_b.name},
        )
        self.assertEqual(
            {item["id"] for item in manager_support["upcoming_followups"]},
            {self.support_a_followup.id},
        )

        exec_payload = self._dashboard(self.support_a_user)
        self.assertEqual(exec_payload["dashboard_type"], "support")
        self.assertNotIn("team_performance", exec_payload)
        self.assertEqual(
            self._names(exec_payload["support"]["agent_workload"]),
            {self.support_a.name},
        )

    # ------------------------------------------------------------------
    # 5. Sales executive report APIs contain Sales employees only
    # ------------------------------------------------------------------
    def test_05_sales_reports_are_scoped_by_department_and_team(self):
        admin_overview = self._overview(self.admin_user)
        self.assertEqual(
            self._names(admin_overview["top_salespersons"]),
            {
                self.sales_manager.name,
                self.sales_a.name,
                self.sales_b.name,
                self.sales_legacy.name,
            },
        )
        self.assertEqual(
            {item["name"] for item in admin_overview["filter_options"]["salespersons"]},
            {
                "All Salespersons",
                self.sales_manager.name,
                self.sales_a.name,
                self.sales_b.name,
                self.sales_legacy.name,
            },
        )
        self.assertEqual(
            {item["customer"] for item in admin_overview["upcoming_followups"]},
            {self.sales_a_lead.name, self.sales_b_lead.name},
        )

        manager_overview = self._overview(self.sales_manager_user)
        self.assertEqual(
            self._names(manager_overview["top_salespersons"]),
            {
                self.sales_manager.name,
                self.sales_a.name,
                self.sales_b.name,
                self.sales_legacy.name,
            },
        )

        exec_overview = self._overview(self.sales_a_user)
        self.assertEqual(
            self._names(exec_overview["top_salespersons"]),
            {self.sales_a.name},
        )
        self.assertEqual(
            {item["name"] for item in exec_overview["filter_options"]["salespersons"]},
            {"All Salespersons", self.sales_a.name},
        )

        admin_revenue = self._revenue(self.admin_user)
        self.assertEqual(
            self._names(admin_revenue["revenue_by_salesperson"]),
            {
                self.sales_manager.name,
                self.sales_a.name,
                self.sales_b.name,
                self.sales_legacy.name,
            },
        )
        exec_revenue = self._revenue(self.sales_a_user)
        self.assertEqual(
            self._names(exec_revenue["revenue_by_salesperson"]),
            {self.sales_a.name},
        )

        for user in (self.support_a_user, self.support_manager_user):
            with self.assertRaises(HTTPException) as overview_denied:
                self._overview(user)
            self.assertEqual(overview_denied.exception.status_code, 403)
            with self.assertRaises(HTTPException) as revenue_denied:
                self._revenue(user)
            self.assertEqual(revenue_denied.exception.status_code, 403)

    def test_06_salesperson_filters_reject_support_employees(self):
        for user in (self.admin_user, self.sales_manager_user, self.sales_a_user):
            with self.assertRaises(HTTPException) as overview_denied:
                self._overview(user, salesperson_id=self.support_a.id)
            self.assertEqual(overview_denied.exception.status_code, 403)

            with self.assertRaises(HTTPException) as revenue_denied:
                self._revenue(user, salesperson_id=self.support_a.id)
            self.assertEqual(revenue_denied.exception.status_code, 403)

        # A Salesperson inside the manager's team is accepted and the response
        # still contains Sales employees only.
        manager_overview = self._overview(
            self.sales_manager_user, salesperson_id=self.sales_a.id
        )
        self.assertIn(
            self.sales_a.name,
            self._names(manager_overview["top_salespersons"]),
        )
        self.assertNotIn(
            self.support_a.name,
            self._names(manager_overview["top_salespersons"]),
        )

    # ------------------------------------------------------------------
    # 6. Sales targets default to Sales and isolate Support
    # ------------------------------------------------------------------
    def test_07_sales_targets_default_to_sales_for_admins(self):
        targets = self._targets(self.admin_user)
        self.assertEqual(
            {target.employee_id for target in targets},
            {self.sales_a.id, self.sales_b.id},
        )

        achievements = self._achievements(self.admin_user)
        self.assertEqual(
            {row.employee_id for row in achievements},
            {
                self.sales_manager.id,
                self.sales_a.id,
                self.sales_b.id,
                self.sales_legacy.id,
            },
        )
        self.assertEqual({row.department for row in achievements}, {"SALES"})

        sales_only = self._achievements(self.admin_user, department="SALES")
        self.assertEqual(
            {row.employee_id for row in sales_only},
            {row.employee_id for row in achievements},
        )

        support_only = self._achievements(self.admin_user, department="SUPPORT")
        support_ids = {row.employee_id for row in support_only}
        self.assertTrue(
            {
                self.support_manager.id,
                self.support_a.id,
                self.support_b.id,
                self.support_cross.id,
            }.issubset(support_ids)
        )
        self.assertFalse(
            support_ids
            & {
                self.sales_manager.id,
                self.sales_a.id,
                self.sales_b.id,
                self.sales_legacy.id,
            }
        )
        self.assertEqual({row.department for row in support_only}, {"SUPPORT"})

        combined = self._achievements(self.admin_user, department="ALL")
        self.assertEqual(
            {row.employee_id for row in combined},
            {row.employee_id for row in achievements} | support_ids,
        )

        # An explicit employee outside the Sales roster is not readable through
        # the Sales-target APIs.
        with self.assertRaises(HTTPException) as target_denied:
            self._targets(self.admin_user, employee_id=self.support_a.id)
        self.assertEqual(target_denied.exception.status_code, 403)

        with self.assertRaises(HTTPException) as achievement_denied:
            self._achievements(self.admin_user, employee_id=self.support_a.id)
        self.assertEqual(achievement_denied.exception.status_code, 403)

    def test_08_non_admin_target_views_are_scoped_and_support_is_rejected(self):
        manager_achievements = self._achievements(self.sales_manager_user)
        self.assertEqual(
            {row.employee_id for row in manager_achievements},
            {
                self.sales_manager.id,
                self.sales_a.id,
                self.sales_b.id,
                self.sales_legacy.id,
            },
        )

        exec_achievements = self._achievements(self.sales_a_user)
        self.assertEqual(
            {row.employee_id for row in exec_achievements},
            {self.sales_a.id},
        )
        self.assertEqual(
            {target.employee_id for target in self._targets(self.sales_a_user)},
            {self.sales_a.id},
        )

        for user in (self.sales_manager_user, self.sales_a_user):
            with self.assertRaises(HTTPException) as denied:
                self._achievements(user, department="SUPPORT")
            self.assertEqual(denied.exception.status_code, 403)

            # Non-admins cannot widen "ALL" into Support either.
            all_rows = self._achievements(user, department="ALL")
            self.assertEqual({row.department for row in all_rows}, {"SALES"})

        for user in (self.support_a_user, self.support_manager_user):
            with self.assertRaises(HTTPException) as denied:
                self._achievements(user)
            self.assertEqual(denied.exception.status_code, 403)
            with self.assertRaises(HTTPException) as revenue_denied:
                get_companies_revenue(
                    search=None,
                    customer_id=None,
                    db=self.db,
                    current_user=user,
                )
            self.assertEqual(revenue_denied.exception.status_code, 403)

        admin_companies = get_companies_revenue(
            search=None,
            customer_id=None,
            db=self.db,
            current_user=self.admin_user,
        )
        company_names = {row.company_name for row in admin_companies}
        self.assertIn("Sales B Won Lead", company_names)
        self.assertNotIn("Support Won Lead", company_names)
        self.assertTrue(
            {
                invoice.salesperson_name
                for row in admin_companies
                for invoice in row.invoices
            }.issubset(
                {
                    self.sales_manager.name,
                    self.sales_a.name,
                    self.sales_b.name,
                    self.sales_legacy.name,
                }
            )
        )

    def test_09_target_writes_reject_support_employees(self):
        with self.assertRaises(HTTPException) as create_denied:
            create_or_update_target(
                payload=SalesTargetCreate(
                    employee_id=self.support_a.id,
                    target_amount=75000.0,
                    period_type="monthly",
                    period_month=self.TARGET_MONTH,
                    period_year=self.TARGET_YEAR,
                ),
                db=self.db,
                current_user=self.admin_user,
            )
        self.assertEqual(create_denied.exception.status_code, 400)

        with self.assertRaises(HTTPException) as update_denied:
            update_target(
                target_id=self.support_a_target.id,
                payload=SalesTargetUpdate(target_amount=80000.0),
                db=self.db,
                current_user=self.admin_user,
            )
        self.assertEqual(update_denied.exception.status_code, 400)

        # The rejected writes did not change the stored Support target.
        self.db.refresh(self.support_a_target)
        self.assertEqual(self.support_a_target.target_amount, 100000.0)


if __name__ == "__main__":
    unittest.main()
