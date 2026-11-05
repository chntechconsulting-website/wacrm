"""Sales WON -> Support purchase handover verification.

Isolated in-memory SQLite only. No live CRM record is read or written.

Scenarios covered:
1.  Sales marks WON and Support handover is triggered.
2.  Package and plan are preserved for Support.
3.  Employee quantity, duration and purchased add-ons are preserved.
4.  Handover reuses the existing customer/handoff (no duplicates).
5.  Support can see the purchase details; Sales cannot.
6.  Purchase fields (dates, plan, amount, documents) are complete.
7.  Only actually purchased add-ons are shown with quantity/unit price/type.
8.  Sales activities are hidden from Support.
9.  Support activities are hidden from Sales.
10. Support status updates never overwrite Sales status or Sales history.
"""

import calendar
import os
import sys
import unittest
from datetime import date, datetime

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401 - registers every model on Base.metadata
import services.activity_visibility_service  # noqa: F401 - registers insert listener
from database import Base
from models.activity import LeadActivity
from models.call_log import CallLog
from models.customer import Customer
from models.employee import Employee
from models.followup import Followup
from models.lead import Lead, LeadStatusHistory
from models.quotation import Quotation
from models.user import User
from models.workflow import FinanceHandoff, SupportHandoff
from routers.activities import get_activities
from routers.customers import get_customer, get_customer_purchase_details
from routers.followups import list_followups
from routers.ivr import list_call_logs
from routers.leads import (
    build_lead_out,
    get_lead_purchase_details,
    get_support_assigned_leads,
    update_support_lead_status,
)
from routers.reports import dashboard_stats
from routers.workflow import get_support_handoff_detail, list_support_handoffs
from schemas.workflow import SupportStatusUpdateRequest
from services.purchase_details_service import build_support_purchase_details
from services.workflow_service import WorkflowService
from starlette.responses import Response


def add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


class SalesSupportPurchaseHandoverTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db = Session()

        self.admin_user, self.admin_emp = self._make_person(
            "handover_admin", "ADMIN", "ADMINISTRATION"
        )
        self.sales_user, self.sales_emp = self._make_person(
            "handover_sales", "SALES_EXECUTIVE", "SALES"
        )
        self.support_manager_user, self.support_manager_emp = self._make_person(
            "handover_support_mgr", "SUPPORT_MANAGER", "SUPPORT"
        )
        self.support_exec_user, self.support_exec_emp = self._make_person(
            "handover_support_exec",
            "SUPPORT_EXECUTIVE",
            "SUPPORT",
            manager_user=self.support_manager_user,
            manager_emp=self.support_manager_emp,
        )

        self.lead = Lead(
            name="Purchase Handover Customer",
            phone="9888000222",
            email="purchase.handover@example.com",
            company="Handover Industries",
            source="MANUAL",
            status="NEW",
            assigned_to=self.sales_emp.id,
        )
        self.db.add(self.lead)
        self.db.commit()
        self.db.refresh(self.lead)

        self.quotation = Quotation(
            doc_type="quotation",
            doc_number="QT-HANDOVER-0001",
            status="issued",
            payment_status="unpaid",
            lead_id=self.lead.id,
            customer_name=self.lead.name,
            company_name=self.lead.company,
            issue_date=datetime(2026, 1, 5, 10, 0, 0),
            grand_total=215000,
            line_items=[],
        )
        self.db.add(self.quotation)
        self.db.commit()
        self.db.refresh(self.quotation)

        self.proforma = Quotation(
            doc_type="proforma",
            doc_number="PI-HANDOVER-0001",
            status="issued",
            payment_status="PAYMENT_PENDING",
            lead_id=self.lead.id,
            source_quotation_id=self.quotation.id,
            source_quotation_number=self.quotation.doc_number,
            customer_name=self.lead.name,
            company_name=self.lead.company,
            phone=self.lead.phone,
            email=self.lead.email,
            issue_date=datetime(2026, 1, 6, 10, 0, 0),
            selected_bundle="hr_atm",
            product_category="WAHRMS",
            grand_total=215000,
            amount_paid=0,
            pdf_url="/api/v1/integrations/waquote/proformas/1/download",
            line_items=self._purchased_line_items(),
        )
        self.db.add(self.proforma)
        self.db.commit()
        self.db.refresh(self.proforma)

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _purchased_line_items(self):
        return [
            {
                "id": 1,
                "isBundleItem": True,
                "isBundleDetail": True,
                "bundleId": "hr_atm",
                "itemCode": "HR_ATM_SUB",
                "name": "WA! HRMS Subscription",
                "description": (
                    "WA! HRMS Subscription\n"
                    "Plan : Business\n"
                    "Duration : 12\n"
                    "No. Of Onboardings : 25\n"
                    "Unit Price : 55"
                ),
                "planCode": "business",
                "planName": "Business",
                "durationMonths": 12,
                "onboardingCount": 25,
                "qty": 300,
                "rate": 55,
                "gstRate": 0.18,
                "discount": 0,
            },
            {
                "id": 2,
                "isAddon": True,
                "is_addon": True,
                "addonCode": "live_location_tracking",
                "itemCode": "LIVE_LOCATION_TRACKING",
                "name": "Live Location Tracking",
                "description": "Live Location Tracking",
                "pricingType": "per_employee",
                "billingUnit": "employee",
                "qty": 25,
                "rate": 60,
                "gstRate": 0.18,
            },
            {
                "id": 3,
                "isAddon": True,
                "is_addon": True,
                "addonCode": "biometric_device_setup",
                "itemCode": "BIOMETRIC_DEVICE_SETUP",
                "name": "Biometric Device Setup",
                "description": "Biometric Device Setup",
                "pricingType": "one_time",
                "billingUnit": "device",
                "qty": 2,
                "rate": 4999,
                "gstRate": 0.18,
            },
            {
                # Deliberately not flagged as an add-on. It must never appear
                # in the Support "Purchased Add-ons" list.
                "id": 4,
                "itemCode": "MISC",
                "name": "Priority Support",
                "description": "Priority Support",
                "qty": 1,
                "rate": 5000,
                "gstRate": 0.18,
            },
        ]

    def _make_person(
        self,
        username,
        role,
        department,
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
            name=username.replace("_", " ").title(),
            email=f"{username}@example.test",
            phone="9800000001",
            username=username,
            role=role,
            status="ACTIVE",
        )
        self.db.add(employee)
        self.db.commit()
        self.db.refresh(employee)
        return user, employee

    def _run_won(self, **overrides):
        won_data = {
            "support_manager_id": self.support_manager_emp.id,
            "total_deal_amount": 215000,
            "product_service": "WA! HRMS Subscription",
            "payment_status": "PAYMENT_PENDING",
        }
        won_data.update(overrides)
        result = WorkflowService.complete_deal_won_workflow(
            db=self.db,
            lead_id=self.lead.id,
            won_data=won_data,
            current_user=self.sales_user,
        )
        self.db.refresh(self.lead)
        return result

    def _handoff(self):
        return (
            self.db.query(SupportHandoff)
            .filter(SupportHandoff.lead_id == self.lead.id)
            .one()
        )

    # ------------------------------------------------------------------
    # Scenarios 1-4, 6-7
    # ------------------------------------------------------------------
    def test_01_won_triggers_support_handover_and_preserves_purchase(self):
        result = self._run_won()
        self.assertTrue(result["success"])

        # Scenario 1: Sales status is WON and Support handover exists.
        self.assertEqual(self.lead.status, "WON")
        handoff = self._handoff()
        self.assertEqual(handoff.customer_id, result["customer_id"])
        self.assertEqual(handoff.support_manager_id, self.support_manager_emp.id)
        self.assertIsNotNone(handoff.purchase_snapshot)

        # Scenario 4: Reuses the linked customer and never duplicates it.
        self.assertEqual(self.db.query(Customer).count(), 1)
        self.assertEqual(
            self.db.query(SupportHandoff).filter(SupportHandoff.lead_id == self.lead.id).count(),
            1,
        )

        details = build_support_purchase_details(self.db, handoff)
        self.assertEqual(details["source"], "saved_purchase_snapshot")
        self.assertEqual(details["snapshot_version"], 1)

        # Scenario 2: Package and plan.
        self.assertEqual(details["package"]["code"], "hr_atm")
        self.assertEqual(details["package"]["name"], "HR + ATM")
        self.assertEqual(details["plan"]["code"], "business")
        self.assertEqual(details["plan"]["name"], "Business")

        # Scenario 3/6: Employee quantity, duration and subscription dates.
        self.assertEqual(details["employee_quantity"], 25)
        self.assertEqual(details["subscription"]["duration_months"], 12)
        self.assertEqual(details["subscription"]["start_basis"], "deal_won_date")
        self.assertEqual(
            details["subscription"]["start_date"],
            handoff.won_at.date().isoformat(),
        )
        self.assertEqual(
            details["subscription"]["end_date"],
            add_months(handoff.won_at.date(), 12).isoformat(),
        )
        self.assertEqual(details["purchase_amount"], 215000)

        # Scenario 6: Customer and purchase documents are present.
        self.assertEqual(details["customer"]["customer_id"], handoff.customer_id)
        self.assertEqual(details["customer"]["company_name"], self.lead.company)
        doc_types = {doc["type"] for doc in details["documents"]}
        self.assertIn("quotation", doc_types)
        self.assertIn("proforma", doc_types)
        proforma_doc = next(d for d in details["documents"] if d["type"] == "proforma")
        self.assertTrue(proforma_doc["url"].startswith("/api/integrations/waquote/"))
        self.assertNotIn("/api/v1/", proforma_doc["url"])

        # Scenario 7: Only the two actually purchased add-ons appear.
        addons = {addon["name"]: addon for addon in details["addons"]}
        self.assertEqual(
            set(addons),
            {"Live Location Tracking", "Biometric Device Setup"},
        )
        self.assertNotIn("Priority Support", addons)
        self.assertEqual(addons["Live Location Tracking"]["quantity"], 25)
        self.assertEqual(addons["Live Location Tracking"]["unit_price"], 60)
        self.assertEqual(addons["Live Location Tracking"]["pricing_type"], "per_employee")
        self.assertEqual(addons["Biometric Device Setup"]["quantity"], 2)
        self.assertEqual(addons["Biometric Device Setup"]["unit_price"], 4999)
        self.assertEqual(addons["Biometric Device Setup"]["pricing_type"], "one_time")

    # ------------------------------------------------------------------
    # Immutability of the snapshotted purchase
    # ------------------------------------------------------------------
    def test_02_purchase_snapshot_not_rewritten_by_later_document_changes(self):
        self._run_won()
        handoff = self._handoff()
        original = build_support_purchase_details(self.db, handoff)

        # Simulate a later catalogue/quotation revision and a re-saved deal.
        revised_lines = self._purchased_line_items()
        revised_lines[0].update({"rate": 999, "onboardingCount": 999, "qty": 999})
        revised_lines[1].update({"rate": 1, "qty": 999})
        self.proforma.line_items = revised_lines[:2]
        self.proforma.grand_total = 1
        self.db.commit()

        self._run_won(total_deal_amount=1, customer_users_count=999)

        refreshed = self._handoff()
        details = build_support_purchase_details(self.db, refreshed)
        self.assertEqual(details["source"], "saved_purchase_snapshot")
        self.assertEqual(details["employee_quantity"], original["employee_quantity"])
        self.assertEqual(details["plan"]["code"], original["plan"]["code"])
        self.assertEqual(
            details["subscription"]["duration_months"],
            original["subscription"]["duration_months"],
        )
        self.assertEqual(
            [(a["name"], a["quantity"], a["unit_price"]) for a in details["addons"]],
            [(a["name"], a["quantity"], a["unit_price"]) for a in original["addons"]],
        )
        self.assertEqual(self.db.query(Customer).count(), 1)
        self.assertEqual(self.db.query(SupportHandoff).count(), 1)

    # ------------------------------------------------------------------
    # Scenario 5: Support visibility and Sales denial
    # ------------------------------------------------------------------
    def test_03_support_can_read_purchase_details_sales_cannot(self):
        self._run_won()

        support_details = get_lead_purchase_details(
            lead_id=self.lead.id,
            db=self.db,
            current_user=self.support_manager_user,
        )
        self.assertEqual(support_details["package"]["name"], "HR + ATM")
        self.assertEqual(support_details["employee_quantity"], 25)

        # Support Assigned Leads queue embeds the same projection.
        queue = get_support_assigned_leads(
            search=None,
            status=None,
            priority=None,
            source=None,
            assigned_agent_id=None,
            skip=0,
            limit=50,
            db=self.db,
            current_user=self.support_manager_user,
        )
        self.assertEqual(queue["total"], 1)
        row = queue["items"][0]
        self.assertEqual(row["sales_status"], "WON")
        self.assertEqual(row["support_status"], "NEW")
        self.assertEqual(row["purchase_details"]["plan"]["code"], "business")

        # Workflow Support handoff list/detail also expose purchase details.
        handoffs = list_support_handoffs(
            status_filter="all",
            search=None,
            limit=50,
            page=1,
            db=self.db,
            current_user=self.support_manager_user,
        )
        self.assertEqual(len(handoffs), 1)
        self.assertEqual(handoffs[0].purchase_details["employee_quantity"], 25)

        detail = get_support_handoff_detail(
            support_id=handoffs[0].id,
            db=self.db,
            current_user=self.support_manager_user,
        )
        self.assertEqual(detail.purchase_details["package"]["code"], "hr_atm")

        # Sales users are denied at the API layer, even for their own lead.
        with self.assertRaises(HTTPException) as ctx:
            get_lead_purchase_details(
                lead_id=self.lead.id,
                db=self.db,
                current_user=self.sales_user,
            )
        self.assertEqual(ctx.exception.status_code, 403)

        with self.assertRaises(HTTPException) as ctx:
            get_support_assigned_leads(
                search=None,
                status=None,
                priority=None,
                source=None,
                assigned_agent_id=None,
                skip=0,
                limit=50,
                db=self.db,
                current_user=self.sales_user,
            )
        self.assertEqual(ctx.exception.status_code, 403)

        # A Support Executive who is not assigned to this customer is denied.
        with self.assertRaises(HTTPException) as ctx:
            get_lead_purchase_details(
                lead_id=self.lead.id,
                db=self.db,
                current_user=self.support_exec_user,
            )
        self.assertEqual(ctx.exception.status_code, 403)

        # Dedicated /customers/{id}/purchase-details endpoint
        handoff = handoffs[0]
        cust_details = get_customer_purchase_details(
            customer_id=handoff.customer_id,
            db=self.db,
            current_user=self.support_manager_user,
        )
        self.assertEqual(cust_details["package"]["name"], "HR + ATM")
        self.assertEqual(cust_details["employee_quantity"], 25)

        # Sales is denied at /customers/{id}/purchase-details
        with self.assertRaises(HTTPException) as ctx:
            get_customer_purchase_details(
                customer_id=handoff.customer_id,
                db=self.db,
                current_user=self.sales_user,
            )
        self.assertEqual(ctx.exception.status_code, 403)

        # Unassigned Support Executive is denied at /customers/{id}/purchase-details
        with self.assertRaises(HTTPException) as ctx:
            get_customer_purchase_details(
                customer_id=handoff.customer_id,
                db=self.db,
                current_user=self.support_exec_user,
            )
        self.assertEqual(ctx.exception.status_code, 403)

        # Customer Profile /customers/{id} includes purchase_details for Support and None for Sales
        support_cust = get_customer(
            customer_id=handoff.customer_id,
            db=self.db,
            current_user=self.support_manager_user,
        )
        self.assertIsNotNone(support_cust.get("purchase_details"))
        self.assertEqual(support_cust["purchase_details"]["package"]["code"], "hr_atm")

        sales_cust = get_customer(
            customer_id=handoff.customer_id,
            db=self.db,
            current_user=self.sales_user,
        )
        self.assertIsNone(sales_cust.get("purchase_details"))

        # Support Dashboard stats include purchase_details in recent_tickets
        dash = dashboard_stats(db=self.db, current_user=self.support_manager_user)
        recent = dash.get("recent_tickets") or dash.get("support", {}).get("recent_tickets", [])
        self.assertGreaterEqual(len(recent), 1)
        rt = next(t for t in recent if t["id"] == handoff.id)
        self.assertIsNotNone(rt["purchase_details"])
        self.assertEqual(rt["purchase_details"]["employee_quantity"], 25)

    # ------------------------------------------------------------------
    # Scenarios 8-9: activity isolation
    # ------------------------------------------------------------------
    def test_04_sales_and_support_activities_are_department_isolated(self):
        self._run_won()
        handoff = self._handoff()

        sales_activity = LeadActivity(
            lead_id=self.lead.id,
            customer_id=handoff.customer_id,
            performed_by=self.sales_emp.id,
            employee_id=self.sales_emp.id,
            activity_type="NOTE_ADDED",
            description="SALES-ONLY negotiation note",
        )
        self.db.add(sales_activity)
        self.db.commit()
        self.db.refresh(sales_activity)
        self.assertEqual(sales_activity.department, "SALES")

        # A Support status update creates a Support-owned activity.
        update_support_lead_status(
            lead_id=self.lead.id,
            payload=SupportStatusUpdateRequest(support_status="ONBOARDING"),
            db=self.db,
            current_user=self.support_manager_user,
        )
        support_activity = (
            self.db.query(LeadActivity)
            .filter(
                LeadActivity.lead_id == self.lead.id,
                LeadActivity.activity_type == "SUPPORT_STATUS_CHANGED",
            )
            .one()
        )
        self.assertEqual(support_activity.department, "SUPPORT")

        def activities_for(user):
            return get_activities(
                lead_id=self.lead.id,
                customer_id=None,
                employee_id=None,
                type=None,
                activity_type=None,
                source=None,
                scope=None,
                department=None,
                limit=100,
                offset=0,
                db=self.db,
                current_user=user,
            )

        # Scenario 8: Support never receives the Sales note.
        support_rows = activities_for(self.support_manager_user)
        support_descriptions = {row["description"] for row in support_rows}
        self.assertFalse(
            any("SALES-ONLY" in description for description in support_descriptions)
        )
        self.assertTrue(
            any("Support status changed" in description for description in support_descriptions)
        )

        # Scenario 9: Sales never receives the Support activity.
        sales_rows = activities_for(self.sales_user)
        sales_descriptions = {row["description"] for row in sales_rows}
        self.assertIn("SALES-ONLY negotiation note", sales_descriptions)
        self.assertFalse(
            any("Support status changed" in description for description in sales_descriptions)
        )

        # Admin sees both departments for audit.
        admin_rows = activities_for(self.admin_user)
        admin_descriptions = {row["description"] for row in admin_rows}
        self.assertTrue(any("SALES-ONLY" in d for d in admin_descriptions))
        self.assertTrue(any("Support status changed" in d for d in admin_descriptions))

        # The embedded /leads/{id} activity list is filtered identically.
        sales_lead = build_lead_out(self.lead, self.sales_user, self.db)
        self.assertFalse(
            any("Support status changed" in (a.description or "") for a in sales_lead.activities)
        )
        self.assertTrue(
            any("SALES-ONLY" in (a.description or "") for a in sales_lead.activities)
        )

        support_lead = build_lead_out(self.lead, self.support_manager_user, self.db)
        self.assertFalse(
            any("SALES-ONLY" in (a.description or "") for a in support_lead.activities)
        )
        self.assertTrue(
            any("Support status changed" in (a.description or "") for a in support_lead.activities)
        )

        # Sales cannot bypass the isolation with the Admin-only department filter.
        with self.assertRaises(HTTPException) as ctx:
            get_activities(
                lead_id=self.lead.id,
                customer_id=None,
                employee_id=None,
                type=None,
                activity_type=None,
                source=None,
                scope="ALL",
                department="SUPPORT",
                limit=100,
                offset=0,
                db=self.db,
                current_user=self.sales_user,
            )
        self.assertEqual(ctx.exception.status_code, 403)

    # ------------------------------------------------------------------
    # Scenario 10: Support status never overwrites Sales status/history
    # ------------------------------------------------------------------
    def test_05_support_status_updates_preserve_won_and_sales_history(self):
        self._run_won()
        history_before = (
            self.db.query(LeadStatusHistory)
            .filter(LeadStatusHistory.lead_id == self.lead.id)
            .count()
        )

        first = update_support_lead_status(
            lead_id=self.lead.id,
            payload=SupportStatusUpdateRequest(support_status="ONBOARDING"),
            db=self.db,
            current_user=self.support_manager_user,
        )
        self.assertEqual(first.support_status, "ONBOARDING")
        self.db.refresh(self.lead)
        self.assertEqual(self.lead.status, "WON")

        second = update_support_lead_status(
            lead_id=self.lead.id,
            payload=SupportStatusUpdateRequest(support_status="ACTIVE"),
            db=self.db,
            current_user=self.support_manager_user,
        )
        self.assertEqual(second.support_status, "ACTIVE")
        self.db.refresh(self.lead)
        self.assertEqual(self.lead.status, "WON")
        self.assertEqual(
            self.db.query(LeadStatusHistory)
            .filter(LeadStatusHistory.lead_id == self.lead.id)
            .count(),
            history_before,
            "Support updates must never append Sales status history",
        )

        # The handoff carries both independent statuses.
        handoff = self._handoff()
        self.assertEqual(handoff.support_status, "ACTIVE")
        self.assertEqual(handoff.sales_status, "WON")

        # Finance/Support handover counts remain stable.
        self.assertEqual(self.db.query(FinanceHandoff).count(), 1)
        self.assertEqual(self.db.query(SupportHandoff).count(), 1)

    # ------------------------------------------------------------------
    # Packages: HR + Payroll, HR + ATM + Payroll, Biometric + Payroll
    # ------------------------------------------------------------------
    def test_06_package_options_and_add_ons(self):
        packages_to_test = [
            ("hr_payroll", "HR + Payroll", "pro", "Pro"),
            ("hr_atm_payroll", "HR + ATM + Payroll", "business", "Business"),
            ("bio_payroll", "Biometric + Payroll", "custom", "Custom"),
        ]

        for pkg_code, pkg_name, plan_code, plan_name in packages_to_test:
            lead = Lead(
                name=f"Customer {pkg_name}",
                phone=f"9811000{pkg_code[:3]}",
                email=f"{pkg_code}@example.com",
                company=f"{pkg_name} Corp",
                source="MANUAL",
                status="NEW",
                assigned_to=self.sales_emp.id,
            )
            self.db.add(lead)
            self.db.commit()
            self.db.refresh(lead)

            proforma = Quotation(
                doc_type="proforma",
                doc_number=f"PI-{pkg_code.upper()}-001",
                status="issued",
                payment_status="PAID",
                lead_id=lead.id,
                customer_name=lead.name,
                company_name=lead.company,
                phone=lead.phone,
                email=lead.email,
                issue_date=datetime(2026, 2, 1, 10, 0, 0),
                selected_bundle=pkg_code,
                product_category="WAHRMS",
                grand_total=150000,
                amount_paid=150000,
                line_items=[
                    {
                        "id": 1,
                        "isBundleItem": True,
                        "bundleId": pkg_code,
                        "name": f"WA! {pkg_name}",
                        "description": f"WA! {pkg_name}\nPlan: {plan_name}\nDuration: 12\nNo. Of Onboardings: 50",
                        "planCode": plan_code,
                        "planName": plan_name,
                        "durationMonths": 12,
                        "onboardingCount": 50,
                        "qty": 600,
                        "rate": 75,
                        "gstRate": 0.18,
                    },
                    {
                        "id": 2,
                        "is_addon": True,
                        "addonCode": "whatsapp_integration",
                        "name": "WhatsApp Automation Add-on",
                        "pricingType": "per_employee",
                        "billingUnit": "employee",
                        "qty": 50,
                        "rate": 30,
                    },
                    {
                        "id": 3,
                        "is_addon": True,
                        "addonCode": "onboarding_training",
                        "name": "Dedicated Onboarding Training",
                        "pricingType": "one_time",
                        "qty": 1,
                        "rate": 9999,
                    },
                ],
            )
            self.db.add(proforma)
            self.db.commit()
            self.db.refresh(proforma)

            result = WorkflowService.complete_deal_won_workflow(
                db=self.db,
                lead_id=lead.id,
                won_data={
                    "support_manager_id": self.support_manager_emp.id,
                    "total_deal_amount": 150000,
                    "proforma_id": proforma.id,
                    "selected_bundle": pkg_name,
                    "customer_users_count": 50,
                },
                current_user=self.sales_user,
            )
            self.assertTrue(result["success"])

            handoff = (
                self.db.query(SupportHandoff)
                .filter(SupportHandoff.lead_id == lead.id)
                .one()
            )
            details = build_support_purchase_details(self.db, handoff)

            self.assertEqual(details["package"]["name"], pkg_name)
            self.assertEqual(details["plan"]["name"], plan_name)
            self.assertEqual(details["employee_quantity"], 50)
            self.assertEqual(details["subscription"]["duration_months"], 12)
            self.assertEqual(len(details["addons"]), 2)

            addon_by_name = {a["name"]: a for a in details["addons"]}
            self.assertIn("WhatsApp Automation Add-on", addon_by_name)
            self.assertIn("Dedicated Onboarding Training", addon_by_name)
            self.assertEqual(addon_by_name["WhatsApp Automation Add-on"]["quantity"], 50)
            self.assertEqual(addon_by_name["WhatsApp Automation Add-on"]["unit_price"], 30)
            self.assertEqual(addon_by_name["Dedicated Onboarding Training"]["quantity"], 1)
            self.assertEqual(addon_by_name["Dedicated Onboarding Training"]["unit_price"], 9999)
            self.assertEqual(addon_by_name["Dedicated Onboarding Training"]["classification"], "One-time setup")

    # ------------------------------------------------------------------
    # Calls & Follow-ups isolation
    # ------------------------------------------------------------------
    def test_07_call_and_followup_isolation(self):
        self._run_won()

        # Sales creates a call log
        sales_call = CallLog(
            lead_id=self.lead.id,
            employee_id=self.sales_emp.id,
            provider_call_id="call_sales_test_001",
            from_number="09513886363",
            to_number=self.lead.phone,
            call_direction="OUTBOUND",
            call_status="COMPLETED",
            duration_seconds=180,
            notes="Sales commercial discussion - discount offered",
            provider="DOOCTI",
        )
        self.db.add(sales_call)
        self.db.commit()

        # Sales creates a follow-up
        sales_followup = Followup(
            lead_id=self.lead.id,
            assigned_to=self.sales_emp.id,
            created_by=self.sales_emp.id,
            followup_date=date(2026, 1, 10),
            followup_time="11:00 AM",
            status="Pending",
            notes="Sales contract follow-up call",
            creator_department="SALES",
            assigned_department="SALES",
            owner_department="SALES",
        )
        self.db.add(sales_followup)
        self.db.commit()

        # Support Manager queries calls for this lead: Sales calls are hidden
        support_calls = list_call_logs(
            response=Response(),
            lead_id=self.lead.id,
            db=self.db,
            current_user=self.support_manager_user,
        )
        self.assertEqual(support_calls.total, 0)
        self.assertEqual(len(support_calls.items), 0)

        # Sales employee queries calls for their lead: sees their call
        sales_calls = list_call_logs(
            response=Response(),
            lead_id=self.lead.id,
            db=self.db,
            current_user=self.sales_user,
        )
        self.assertEqual(sales_calls.total, 1)

        # Support Manager queries follow-ups: Sales follow-ups are hidden
        support_followups = list_followups(
            status_filter="Pending",
            db=self.db,
            current_user=self.support_manager_user,
        )
        self.assertEqual(len(support_followups), 0)

        # Sales rep queries follow-ups: sees their follow-up
        sales_followups = list_followups(
            status_filter="Pending",
            db=self.db,
            current_user=self.sales_user,
        )
        self.assertEqual(len(sales_followups), 1)
        self.assertEqual(sales_followups[0].notes, "Sales contract follow-up call")

        # Support creates an onboarding follow-up
        support_followup = Followup(
            lead_id=self.lead.id,
            assigned_to=self.support_manager_emp.id,
            created_by=self.support_manager_emp.id,
            followup_date=date(2026, 1, 15),
            followup_time="02:00 PM",
            status="Pending",
            notes="Support onboarding welcome call",
            creator_department="SUPPORT",
            assigned_department="SUPPORT",
            owner_department="SUPPORT",
        )
        self.db.add(support_followup)
        self.db.commit()

        # Sales user must NOT see the Support onboarding follow-up
        sales_followups_after = list_followups(
            status_filter="Pending",
            db=self.db,
            current_user=self.sales_user,
        )
        self.assertEqual(len(sales_followups_after), 1)
        self.assertEqual(sales_followups_after[0].notes, "Sales contract follow-up call")

        # Support manager sees the Support onboarding follow-up
        support_followups_after = list_followups(
            status_filter="Pending",
            db=self.db,
            current_user=self.support_manager_user,
        )
        self.assertEqual(len(support_followups_after), 1)
        self.assertEqual(support_followups_after[0].notes, "Support onboarding welcome call")

    def test_08_support_can_download_handed_over_purchase_documents(self):
        """Support can view/download Proforma, Quotation and Invoice for handed-over deal,
        via both singular and plural endpoint routes."""
        from services.permission_service import is_user_authorized_for_billing_doc

        # Before handover: Support cannot view Sales billing docs
        self.assertFalse(
            is_user_authorized_for_billing_doc(
                self.support_manager_user, self.proforma, self.db, "view"
            )
        )

        # Sales marks deal WON and hands over to Support
        self._run_won(assigned_agent_id=self.support_exec_emp.id)

        # After handover: Support Manager and assigned Support Executive CAN view
        can_manager_view = is_user_authorized_for_billing_doc(
            self.support_manager_user, self.proforma, self.db, "view"
        )
        self.assertTrue(can_manager_view)

        can_exec_view = is_user_authorized_for_billing_doc(
            self.support_exec_user, self.proforma, self.db, "view"
        )
        self.assertTrue(can_exec_view)

        # Support CANNOT edit or delete billing documents
        can_exec_edit = is_user_authorized_for_billing_doc(
            self.support_exec_user, self.proforma, self.db, "edit"
        )
        self.assertFalse(can_exec_edit)

        # Download via waquote endpoints
        from integrations.waquote.router import download_proforma_pdf, download_quotation_pdf

        proforma_resp = download_proforma_pdf(
            doc_id=str(self.proforma.id),
            db=self.db,
            current_user=self.support_exec_user,
        )
        self.assertEqual(proforma_resp.media_type, "application/pdf")
        self.assertTrue(len(proforma_resp.body) > 0)

        quotation_resp = download_quotation_pdf(
            doc_id=str(self.quotation.id),
            db=self.db,
            current_user=self.support_exec_user,
        )
        self.assertEqual(quotation_resp.media_type, "application/pdf")
        self.assertTrue(len(quotation_resp.body) > 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
