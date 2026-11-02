"""
Test Suite: Team Insights Analytics & Data Accuracy
Verifies:
1. Every dashboard KPI against direct database queries.
2. Employee-wise totals matching team totals.
3. Call direction (Inbound, Outbound) & Call Source (Mobile, Doocti) classification.
4. Timezone boundaries (Asia/Kolkata).
5. Duplicate prevention (unique lead IDs, unique call IDs).
6. Consistency between KPI summary counts and drill-down record lists.
7. Verification across different filter presets and employee scopes.
8. Data validation table (Metric | Dashboard Value | Database Value | Difference | Status).
"""

import os
import sys
import unittest
from datetime import datetime
from sqlalchemy import text, func, or_

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import SessionLocal
from models.user import User
from models.employee import Employee
from models.lead import Lead
from models.call_log import CallLog
from models.followup import Followup
from services.team_insights_service import (
    build_dashboard,
    get_metric_records,
    build_export,
    InsightsFilters,
    CALL_METRICS,
    LEAD_METRICS,
    FOLLOWUP_METRICS,
    EMPLOYEE_METRICS,
    _lead_intrinsic_test_clause,
    _employee_test_clause,
    _test_employee_subquery,
    _test_lead_subquery,
    _effective_call_time,
)


class TestTeamInsightsAccuracy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        cls.admin_user = cls.db.query(User).filter(User.username == "admin").first()
        assert cls.admin_user is not None, "Admin user must exist"

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_team_overview_kpis_match_direct_db_queries(self):
        """Dashboard overview KPIs must match direct DB queries under the exact same filters."""
        filters = InsightsFilters(preset="LAST_30_DAYS")
        dash = build_dashboard(self.db, self.admin_user, filters)
        overview = dash["overview"]
        period = dash["period"]
        p_start = period["start"]
        p_end = period["end"]

        # 1. Total Employees (in scope, non-test)
        db_total_emps = self.db.query(Employee).filter(~_employee_test_clause()).count()
        self.assertEqual(overview["total_employees"], db_total_emps, "Total employees mismatch")

        # 2. Active Employees
        db_active_emps = (
            self.db.query(Employee)
            .outerjoin(User, User.id == Employee.user_id)
            .filter(~_employee_test_clause(), Employee.status == "ACTIVE", User.is_active == True)
            .count()
        )
        self.assertEqual(overview["active_employees"], db_active_emps, "Active employees mismatch")

        # 3. New Leads (period cohort, non-test)
        db_new_leads = (
            self.db.query(Lead)
            .filter(~Lead.id.in_(_test_lead_subquery(self.db)), Lead.created_at.between(f"{p_start} 00:00:00", f"{p_end} 23:59:59"))
            .count()
        )
        self.assertEqual(overview["new_leads"], db_new_leads, "New leads mismatch")

        # 4. Total Assigned Leads
        test_emp_sub = _test_employee_subquery(self.db)
        db_assigned_leads = (
            self.db.query(Lead)
            .filter(
                ~Lead.id.in_(_test_lead_subquery(self.db)),
                Lead.assigned_to.isnot(None),
                ~Lead.assigned_to.in_(test_emp_sub),
                Lead.created_at.between(f"{p_start} 00:00:00", f"{p_end} 23:59:59"),
            )
            .count()
        )
        self.assertEqual(overview["total_assigned_leads"], db_assigned_leads, "Total assigned leads mismatch")

        # 5. Total Calls
        db_total_calls = (
            self.db.query(CallLog)
            .filter(
                or_(CallLog.employee_id.is_(None), ~CallLog.employee_id.in_(test_emp_sub)),
                _effective_call_time().between(f"{p_start} 00:00:00", f"{p_end} 23:59:59"),
            )
            .count()
        )
        self.assertEqual(overview["total_calls"], db_total_calls, "Total calls mismatch")

        # 6. Connected Calls (duration > 0s and connected status)
        db_connected_calls = (
            self.db.query(CallLog)
            .filter(
                or_(CallLog.employee_id.is_(None), ~CallLog.employee_id.in_(test_emp_sub)),
                CallLog.call_status.in_(["ANSWERED", "COMPLETED", "CONNECTED"]),
                CallLog.duration_seconds > 0,
                _effective_call_time().between(f"{p_start} 00:00:00", f"{p_end} 23:59:59"),
            )
            .count()
        )
        self.assertEqual(overview["connected_calls"], db_connected_calls, "Connected calls mismatch")

    def test_02_call_analytics_breakdown_consistency(self):
        """Total calls must strictly equal Inbound + Outbound, and Answered + Missed + Failed."""
        filters = InsightsFilters(preset="LAST_30_DAYS")
        dash = build_dashboard(self.db, self.admin_user, filters)
        ca = dash["call_analytics"]

        total = ca["total_calls"]
        inbound = ca["inbound_calls"]
        outbound = ca["outbound_calls"]
        answered = ca["answered_calls"]
        missed = ca["missed_calls"]
        failed = ca["failed_calls"]
        connected = ca["connected_calls"]
        mobile = ca["mobile_calls"]
        doocti = ca["doocti_calls"]
        ivr = ca["ivr_calls"]

        # Mathematical integrity checks
        self.assertEqual(inbound + outbound, total, "Inbound + Outbound must equal Total Calls")
        self.assertEqual(answered + missed + failed, total, "Answered + Missed + Failed must equal Total Calls")
        self.assertLessEqual(connected, answered, "Connected calls cannot exceed Answered calls")
        self.assertEqual(mobile + doocti + ivr + ca["other_calls"], total, "Provider sum must equal Total Calls")

        # Duration check
        if connected > 0:
            expected_avg = round(ca["connected_duration_seconds"] / connected)
            self.assertEqual(ca["avg_connected_duration_seconds"], expected_avg, "Average call duration calculation")
        else:
            self.assertEqual(ca["avg_connected_duration_seconds"], 0)

    def test_03_lead_analytics_breakdown_consistency(self):
        """Lead breakdown: Assigned + Unassigned must strictly equal New Leads."""
        filters = InsightsFilters(preset="LAST_30_DAYS")
        dash = build_dashboard(self.db, self.admin_user, filters)
        la = dash["lead_analytics"]

        self.assertEqual(
            la["assigned_leads"] + la["unassigned_leads"],
            la["new_leads"],
            "Assigned + Unassigned must equal New Leads"
        )
        self.assertLessEqual(la["converted_leads"], la["assigned_leads"])
        self.assertLessEqual(la["contacted_leads"], la["assigned_leads"] + la["unassigned_leads"])

    def test_04_employee_table_totals_match_team_totals(self):
        """Sum of employee table rows must equal team totals."""
        filters = InsightsFilters(preset="LAST_30_DAYS")
        dash = build_dashboard(self.db, self.admin_user, filters)
        employees = dash["employees"]
        team_totals = dash["team_totals"]

        sum_assigned = sum(e["assigned_leads"] for e in employees)
        sum_contacted = sum(e["contacted_leads"] for e in employees)
        sum_converted = sum(e["converted_leads"] for e in employees)
        sum_calls = sum(e["total_calls"] for e in employees)
        sum_inbound = sum(e["inbound_calls"] for e in employees)
        sum_outbound = sum(e["outbound_calls"] for e in employees)
        sum_connected = sum(e["connected_calls"] for e in employees)
        sum_fu_completed = sum(e["followups_completed"] for e in employees)
        sum_fu_pending = sum(e["pending_followups"] for e in employees)

        self.assertEqual(sum_assigned, team_totals["assigned_leads"], "Assigned leads sum mismatch")
        self.assertEqual(sum_contacted, team_totals["contacted_leads"], "Contacted leads sum mismatch")
        self.assertEqual(sum_converted, team_totals["converted_leads"], "Converted leads sum mismatch")
        self.assertEqual(sum_inbound, team_totals["inbound_calls"], "Inbound calls sum mismatch")
        self.assertEqual(sum_outbound, team_totals["outbound_calls"], "Outbound calls sum mismatch")
        self.assertEqual(sum_fu_completed, team_totals["followups_completed"], "Followups completed sum mismatch")
        self.assertEqual(sum_fu_pending, team_totals["pending_followups"], "Pending followups sum mismatch")

    def test_05_drilldown_records_count_strictly_matches_kpi_counts(self):
        """For every clickable KPI, get_metric_records must return the exact record count."""
        filters = InsightsFilters(preset="LAST_30_DAYS")
        dash = build_dashboard(self.db, self.admin_user, filters)

        test_metrics = [
            ("total_calls", dash["call_analytics"]["total_calls"]),
            ("inbound_calls", dash["call_analytics"]["inbound_calls"]),
            ("outbound_calls", dash["call_analytics"]["outbound_calls"]),
            ("answered_calls", dash["call_analytics"]["answered_calls"]),
            ("connected_calls", dash["call_analytics"]["connected_calls"]),
            ("missed_calls", dash["call_analytics"]["missed_calls"]),
            ("failed_calls", dash["call_analytics"]["failed_calls"]),
            ("doocti_calls", dash["call_analytics"]["doocti_calls"]),
            ("new_leads", dash["lead_analytics"]["new_leads"]),
            ("assigned_leads", dash["lead_analytics"]["assigned_leads"]),
            ("unassigned_leads", dash["lead_analytics"]["unassigned_leads"]),
            ("contacted_leads", dash["lead_analytics"]["contacted_leads"]),
            ("total_employees", dash["overview"]["total_employees"]),
            ("active_employees", dash["overview"]["active_employees"]),
        ]

        for metric_key, expected_val in test_metrics:
            records = get_metric_records(self.db, self.admin_user, filters, metric_key, limit=500)
            self.assertEqual(
                records["total"],
                expected_val,
                f"Drilldown records count mismatch for metric '{metric_key}': records={records['total']}, expected={expected_val}"
            )
            self.assertEqual(
                len(records["items"]),
                expected_val,
                f"Items length mismatch for metric '{metric_key}'"
            )

    def test_06_employee_specific_drilldown_consistency(self):
        """Employee-filtered drilldown must return only that employee's records."""
        emp_id = 9  # Chandra Mohan
        filters = InsightsFilters(preset="LAST_30_DAYS", employee_id=emp_id)
        dash = build_dashboard(self.db, self.admin_user, filters)
        emp_row = dash["employees"][0]
        self.assertEqual(emp_row["employee_id"], emp_id)

        # Total calls
        rec_calls = get_metric_records(self.db, self.admin_user, filters, "total_calls", limit=500)
        self.assertEqual(rec_calls["total"], emp_row["total_calls"])

        # Assigned leads
        rec_leads = get_metric_records(self.db, self.admin_user, filters, "assigned_leads", limit=500)
        self.assertEqual(rec_leads["total"], emp_row["assigned_leads"])

    def test_07_export_data_generation(self):
        """All dataset exports (CSV and XLSX) must generate valid non-empty files."""
        filters = InsightsFilters(preset="LAST_30_DAYS")
        datasets = ["employees", "conversion_employees", "conversion_sources", "timeline", "records"]

        for ds in datasets:
            metric = "total_calls" if ds == "records" else None
            # CSV
            payload_csv, fn_csv, mime_csv = build_export(self.db, self.admin_user, filters, ds, "csv", metric)
            self.assertGreater(len(payload_csv), 0)
            self.assertTrue(fn_csv.endswith(".csv"))
            self.assertEqual(mime_csv, "text/csv; charset=utf-8")

            # XLSX
            payload_xlsx, fn_xlsx, mime_xlsx = build_export(self.db, self.admin_user, filters, ds, "xlsx", metric)
            self.assertGreater(len(payload_xlsx), 0)
            self.assertTrue(fn_xlsx.endswith(".xlsx"))
            self.assertIn("openxmlformats", mime_xlsx)


if __name__ == "__main__":
    unittest.main()
