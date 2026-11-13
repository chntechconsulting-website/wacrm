import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath('backend'))

from fastapi import HTTPException
from sqlalchemy import func, or_

from database import SessionLocal
from models.customer import Customer
from models.employee import Employee
from models.lead import Lead
from models.user import User
from models.workflow import SupportHandoff
from routers.reports import (
    dashboard_stats,
    get_dashboard_context,
    sales_overview_report,
    sales_revenue_report,
)
from routers.sales_targets import get_employee_achievements, get_my_target
from services.hierarchy_service import get_team_employee_ids_from_user
from utils.support_status import (
    SUPPORT_OPEN_STATUSES,
    SUPPORT_STATUS_NEW,
    SUPPORT_STATUS_RESOLVED,
    normalize_support_status,
)
from utils.lead_status import CONVERTED_TO_SUPPORT_STATUSES


class TestDashboardRoleAccess(unittest.TestCase):
    PREFIX = "[TEST-DASH]"

    def setUp(self):
        self.db = SessionLocal()

        self.admin_user = self.db.query(User).filter(User.username == "admin").first()
        self.sales_mgr_user = self.db.query(User).filter(User.username == "chnm030").first()
        self.sales_exec_user = self.db.query(User).filter(User.username == "chnm040").first()
        self.support_mgr_user = self.db.query(User).filter(User.username == "kumar").first()
        self.support_exec_user = self.db.query(User).filter(User.username == "chnm023").first()

        self.assertIsNotNone(self.admin_user, "Admin user must exist")
        self.assertIsNotNone(self.sales_mgr_user, "Sales Manager user must exist")
        self.assertIsNotNone(self.sales_exec_user, "Sales Executive user must exist")
        self.assertIsNotNone(self.support_mgr_user, "Support Manager user must exist")
        self.assertIsNotNone(self.support_exec_user, "Support Executive user must exist")

        self.admin_emp = self.db.query(Employee).filter(Employee.user_id == self.admin_user.id).first()
        self.sales_emp = self.db.query(Employee).filter(Employee.user_id == self.sales_exec_user.id).first()
        self.support_mgr_emp = self.db.query(Employee).filter(Employee.user_id == self.support_mgr_user.id).first()
        self.support_exec_emp = self.db.query(Employee).filter(Employee.user_id == self.support_exec_user.id).first()

        self.customer = self.db.query(Customer).first()
        self.lead = self.db.query(Lead).first()
        self.assertIsNotNone(self.customer, "A customer record is required for support handoffs")
        self.assertIsNotNone(self.lead, "A lead record is required for support handoffs")

        self._cleanup_test_records()

        now = datetime.utcnow()
        records = [
            # Support Executive's scoped tickets, one per lifecycle bucket.
            SupportHandoff(
                lead_id=self.lead.id,
                customer_id=self.customer.id,
                customer_name=f"{self.PREFIX} Pending",
                company_name="Dashboard Test Co",
                product_service="CRM Subscription",
                support_manager_id=self.support_mgr_emp.id,
                support_manager_name=self.support_mgr_emp.name,
                assigned_agent_id=self.support_exec_emp.id,
                assigned_agent_name=self.support_exec_emp.name,
                onboarding_status="PENDING_ONBOARDING",
                created_at=now - timedelta(hours=30),
            ),
            SupportHandoff(
                lead_id=self.lead.id,
                customer_id=self.customer.id,
                customer_name=f"{self.PREFIX} Contacted",
                company_name="Dashboard Test Co",
                product_service="CRM Subscription",
                support_manager_id=self.support_mgr_emp.id,
                support_manager_name=self.support_mgr_emp.name,
                assigned_agent_id=self.support_exec_emp.id,
                assigned_agent_name=self.support_exec_emp.name,
                onboarding_status="CONTACTED",
                created_at=now - timedelta(hours=20),
            ),
            SupportHandoff(
                lead_id=self.lead.id,
                customer_id=self.customer.id,
                customer_name=f"{self.PREFIX} In Progress",
                company_name="Dashboard Test Co",
                product_service="CRM Subscription",
                support_manager_id=self.support_mgr_emp.id,
                support_manager_name=self.support_mgr_emp.name,
                assigned_agent_id=self.support_exec_emp.id,
                assigned_agent_name=self.support_exec_emp.name,
                onboarding_status="ONBOARDING_IN_PROGRESS",
                created_at=now - timedelta(hours=14),
            ),
            SupportHandoff(
                lead_id=self.lead.id,
                customer_id=self.customer.id,
                customer_name=f"{self.PREFIX} Completed",
                company_name="Dashboard Test Co",
                product_service="CRM Subscription",
                support_manager_id=self.support_mgr_emp.id,
                support_manager_name=self.support_mgr_emp.name,
                assigned_agent_id=self.support_exec_emp.id,
                assigned_agent_name=self.support_exec_emp.name,
                onboarding_status="COMPLETED",
                created_at=now - timedelta(hours=10),
                completed_at=now - timedelta(hours=4),
            ),
        ]
        self.db.add_all(records)
        self.db.commit()

    def tearDown(self):
        self._cleanup_test_records()
        self.db.close()

    def _cleanup_test_records(self):
        self.db.query(SupportHandoff).filter(
            SupportHandoff.customer_name.like(f"{self.PREFIX}%")
        ).delete(synchronize_session=False)
        self.db.commit()

    def _support_exec_query(self):
        return self.db.query(SupportHandoff).filter(
            SupportHandoff.assigned_agent_id == self.support_exec_emp.id
        )

    def _support_mgr_team_query(self):
        team_ids = get_team_employee_ids_from_user(self.support_mgr_user, self.db)
        if self.support_mgr_emp.id not in team_ids:
            team_ids.append(self.support_mgr_emp.id)
        converted_lead_ids = self.db.query(Lead.id).filter(
            func.upper(func.trim(Lead.status)).in_(sorted(CONVERTED_TO_SUPPORT_STATUSES))
        )
        return self.db.query(SupportHandoff).filter(
            or_(
                SupportHandoff.support_manager_id == self.support_mgr_emp.id,
                SupportHandoff.assigned_agent_id.in_(team_ids),
                (
                    SupportHandoff.assigned_agent_id.is_(None)
                    & SupportHandoff.lead_id.in_(converted_lead_ids)
                ),
            )
        )

    def _status_counts(self, query):
        """Support status counts keyed by canonical status.

        Legacy rows (PENDING_ONBOARDING/CONTACTED/ONBOARDING_IN_PROGRESS/
        COMPLETED) are normalised exactly like the dashboard endpoint does.
        """
        counts = {}
        for status, count in (
            query.with_entities(SupportHandoff.onboarding_status, func.count(SupportHandoff.id))
            .group_by(SupportHandoff.onboarding_status)
            .all()
        ):
            canonical = normalize_support_status(status) or SUPPORT_STATUS_NEW
            counts[canonical] = counts.get(canonical, 0) + int(count or 0)
        return counts

    def test_support_executive_gets_support_dashboard_only(self):
        payload = dashboard_stats(db=self.db, current_user=self.support_exec_user)

        self.assertEqual(payload["dashboard_type"], "support")
        self.assertEqual(payload["department"], "SUPPORT")
        self.assertIn("support", payload)
        self.assertNotIn("total_leads", payload)
        self.assertNotIn("team_performance", payload)
        self.assertNotIn("source_lead_counts", payload)

        counts = self._status_counts(self._support_exec_query())
        support = payload["support"]
        self.assertEqual(support["total_tickets"], sum(counts.values()))
        self.assertEqual(support["pending_tickets"], counts.get(SUPPORT_STATUS_NEW, 0))
        self.assertEqual(
            support["open_tickets"],
            sum(counts.get(status, 0) for status in SUPPORT_OPEN_STATUSES),
        )
        self.assertEqual(
            support["resolved_tickets"],
            counts.get(SUPPORT_STATUS_RESOLVED, 0),
        )

    def test_support_manager_gets_team_scoped_support_dashboard(self):
        payload = dashboard_stats(db=self.db, current_user=self.support_mgr_user)

        self.assertEqual(payload["dashboard_type"], "support")
        counts = self._status_counts(self._support_mgr_team_query())
        self.assertEqual(payload["support"]["total_tickets"], sum(counts.values()))
        self.assertEqual(
            payload["support"]["resolved_tickets"],
            counts.get(SUPPORT_STATUS_RESOLVED, 0),
        )
        self.assertNotIn("total_leads", payload)

    def test_admin_gets_both_dashboards(self):
        payload = dashboard_stats(db=self.db, current_user=self.admin_user)

        self.assertEqual(payload["dashboard_type"], "both")
        self.assertEqual(
            payload["available_dashboards"], ["sales", "support", "finance"]
        )
        self.assertIn("total_leads", payload)
        self.assertIn("support", payload)
        self.assertEqual(
            payload["support"]["total_tickets"],
            self.db.query(SupportHandoff).count(),
        )

    def test_sales_roles_get_sales_dashboard_without_support_data(self):
        for user in (self.sales_exec_user, self.sales_mgr_user):
            payload = dashboard_stats(db=self.db, current_user=user)
            self.assertEqual(payload["dashboard_type"], "sales")
            self.assertIn("total_leads", payload)
            self.assertNotIn("support", payload)

    def test_average_resolution_time_uses_completed_ticket_timestamps(self):
        payload = dashboard_stats(db=self.db, current_user=self.support_exec_user)

        completed = self._support_exec_query().filter(
            SupportHandoff.onboarding_status == "COMPLETED",
            SupportHandoff.completed_at.isnot(None),
            SupportHandoff.created_at.isnot(None),
        ).all()
        durations = [
            (record.completed_at - record.created_at).total_seconds() / 3600.0
            for record in completed
        ]
        expected = round(sum(durations) / len(durations), 1) if durations else None
        self.assertEqual(payload["support"]["average_resolution_hours"], expected)
        self.assertIsNotNone(payload["support"]["average_resolution_display"])
        self.assertNotEqual(payload["support"]["average_resolution_display"], "—")

    def test_support_roles_cannot_read_sales_targets(self):
        for user in (self.support_exec_user, self.support_mgr_user):
            with self.assertRaises(HTTPException) as target_ctx:
                get_my_target(
                    period_year=2026,
                    period_month=11,
                    period_type="monthly",
                    db=self.db,
                    current_user=user,
                )
            self.assertEqual(target_ctx.exception.status_code, 403)

            with self.assertRaises(HTTPException) as achievement_ctx:
                get_employee_achievements(
                    period_year=2026,
                    period_month=11,
                    period_type="monthly",
                    department=None,
                    employee_id=None,
                    db=self.db,
                    current_user=user,
                )
            self.assertEqual(achievement_ctx.exception.status_code, 403)

    def test_legacy_manager_in_support_department_resolves_to_support(self):
        legacy_user = User(username="legacy_support_mgr_test", role="MANAGER", department="SUPPORT")
        legacy_employee = Employee(name="Legacy Support Manager", role="MANAGER", department="SUPPORT")

        context = get_dashboard_context(legacy_user, legacy_employee, self.db)

        self.assertEqual(context["dashboard_type"], "support")
        self.assertEqual(context["role"], "SUPPORT_MANAGER")
        self.assertEqual(context["department"], "SUPPORT")

    def test_support_roles_cannot_read_sales_reports(self):
        for user in (self.support_exec_user, self.support_mgr_user):
            with self.assertRaises(HTTPException) as overview_ctx:
                sales_overview_report(
                    start_date=None,
                    end_date=None,
                    team=None,
                    salesperson_id=None,
                    source=None,
                    db=self.db,
                    current_user=user,
                )
            self.assertEqual(overview_ctx.exception.status_code, 403)

            with self.assertRaises(HTTPException) as revenue_ctx:
                sales_revenue_report(
                    start_date=None,
                    end_date=None,
                    team=None,
                    salesperson_id=None,
                    db=self.db,
                    current_user=user,
                )
            self.assertEqual(revenue_ctx.exception.status_code, 403)

    def test_sales_and_admin_can_read_sales_reports(self):
        for user in (self.sales_exec_user, self.sales_mgr_user, self.admin_user):
            overview = sales_overview_report(
                start_date=None,
                end_date=None,
                team=None,
                salesperson_id=None,
                source=None,
                db=self.db,
                current_user=user,
            )
            self.assertIn("kpis", overview)

            revenue = sales_revenue_report(
                start_date=None,
                end_date=None,
                team=None,
                salesperson_id=None,
                db=self.db,
                current_user=user,
            )
            self.assertIn("kpis", revenue)

    def test_sales_and_admin_can_read_sales_targets(self):
        for user in (self.sales_exec_user, self.sales_mgr_user, self.admin_user):
            summary = get_my_target(
                period_year=2026,
                period_month=11,
                period_type="monthly",
                db=self.db,
                current_user=user,
            )
            self.assertIsNotNone(summary)
            self.assertIn(summary.period_type, ["monthly", "quarterly", "yearly"])

        rows = get_employee_achievements(
            period_year=2026,
            period_month=11,
            period_type="monthly",
            department=None,
            employee_id=None,
            db=self.db,
            current_user=self.admin_user,
        )
        self.assertIsInstance(rows, list)


if __name__ == "__main__":
    unittest.main()
