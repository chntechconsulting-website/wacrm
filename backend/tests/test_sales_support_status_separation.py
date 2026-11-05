"""End-to-end verification of independent Sales and Support statuses.

Uses an isolated in-memory SQLite database. It never connects to the live MySQL
database and never mutates real CRM records.

Workflow verified:
1. Sales marks the lead WON.
2. Deal/customer is handed over to Support.
3. Sales status remains WON.
4. Support sets Onboarding.
5. Sales status remains WON.
6. Support sets Active.
7. Sales status remains WON.
8. Admin sees both statuses independently.
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
from models.employee import Employee
from models.lead import Lead, LeadStatusHistory
from models.quotation import Quotation
from models.user import User
from models.workflow import SupportHandoff
from routers.admin import admin_handovers
from routers.leads import change_lead_status, update_support_lead_status
from routers.workflow import update_support_onboarding_status
from schemas.lead import LeadStatusRequest
from schemas.workflow import SupportHandoffOut, SupportStatusUpdateRequest
from services.workflow_service import WorkflowService


class SalesSupportStatusSeparationTests(unittest.TestCase):
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
            "status_admin", "ADMIN", "ADMINISTRATION"
        )
        self.sales_user, self.sales_emp = self._make_person(
            "status_sales", "SALES_EXECUTIVE", "SALES"
        )
        self.support_manager_user, self.support_manager_emp = self._make_person(
            "status_support_mgr", "SUPPORT_MANAGER", "SUPPORT"
        )
        self.support_exec_user, self.support_exec_emp = self._make_person(
            "status_support_exec",
            "SUPPORT_EXECUTIVE",
            "SUPPORT",
            manager_user=self.support_manager_user,
            manager_emp=self.support_manager_emp,
        )

        self.lead = Lead(
            name="Status Separation Customer",
            phone="9888000111",
            email="status.separation@example.test",
            company="Separation Industries",
            source="MANUAL",
            status="NEW",
            assigned_to=self.sales_emp.id,
        )
        self.db.add(self.lead)
        self.db.commit()
        self.db.refresh(self.lead)

        # A normal Sales WON always links an existing proforma invoice.
        self.proforma = Quotation(
            doc_type="proforma",
            doc_number="PI-STATUS-TEST-0001",
            status="issued",
            payment_status="PAYMENT_PENDING",
            lead_id=self.lead.id,
            customer_name=self.lead.name,
            company_name=self.lead.company,
            phone=self.lead.phone,
            email=self.lead.email,
            grand_total=125000,
            amount_paid=0,
            product_category="WAHRMS",
            line_items=[
                {
                    "description": "WaCRM Business Suite",
                    "qty": 10,
                    "rate": 12500,
                    "amount": 125000,
                }
            ],
        )
        self.db.add(self.proforma)
        self.db.commit()
        self.db.refresh(self.proforma)

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

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
            phone="9800000000",
            username=username,
            role=role,
            status="ACTIVE",
        )
        self.db.add(employee)
        self.db.commit()
        self.db.refresh(employee)
        return user, employee

    def test_sales_and_support_statuses_remain_independent(self):
        # 1. Sales closes the deal as WON.
        result = WorkflowService.complete_deal_won_workflow(
            db=self.db,
            lead_id=self.lead.id,
            won_data={
                "support_manager_id": self.support_manager_emp.id,
                "total_deal_amount": 125000,
                "product_service": "WaCRM Business Suite",
                "payment_status": "PAYMENT_PENDING",
            },
            current_user=self.sales_user,
        )
        self.assertTrue(result["success"])
        self.db.refresh(self.lead)
        self.assertEqual(self.lead.status, "WON", "Step 1: Sales status must be WON")

        # 2. Handover uses the existing lead/customer relationship (no duplicates).
        handoff = (
            self.db.query(SupportHandoff)
            .filter(SupportHandoff.lead_id == self.lead.id)
            .one()
        )
        self.assertEqual(handoff.customer_id, result["customer_id"])
        self.assertEqual(handoff.support_manager_id, self.support_manager_emp.id)
        self.assertEqual(
            self.db.query(SupportHandoff)
            .filter(SupportHandoff.lead_id == self.lead.id)
            .count(),
            1,
            "Step 2: Handover must not duplicate the lead/customer record",
        )

        # 3. Sales still displays WON after the handover.
        self.db.refresh(self.lead)
        self.assertEqual(self.lead.status, "WON", "Step 3: Sales status must stay WON")

        history_before = (
            self.db.query(LeadStatusHistory)
            .filter(LeadStatusHistory.lead_id == self.lead.id)
            .count()
        )

        # 4. Support sets the independent status to Onboarding.
        updated = update_support_lead_status(
            lead_id=self.lead.id,
            payload=SupportStatusUpdateRequest(support_status="ONBOARDING"),
            db=self.db,
            current_user=self.support_manager_user,
        )
        self.assertEqual(updated.support_status, "ONBOARDING")
        self.assertEqual(updated.onboarding_status, "ONBOARDING")

        # 5. Sales still displays WON.
        self.db.refresh(self.lead)
        self.assertEqual(self.lead.status, "WON", "Step 5: Sales status must stay WON")

        # 6. Support employee changes Support status to Active.
        handoff.assigned_agent_id = self.support_exec_emp.id
        handoff.assigned_agent_name = self.support_exec_emp.name
        self.db.commit()
        updated = update_support_onboarding_status(
            support_id=handoff.id,
            payload=SupportStatusUpdateRequest(support_status="ACTIVE"),
            db=self.db,
            current_user=self.support_exec_user,
        )
        self.assertEqual(updated.support_status, "ACTIVE")

        # 7. Sales still displays WON.
        self.db.refresh(self.lead)
        self.assertEqual(self.lead.status, "WON", "Step 7: Sales status must stay WON")
        self.assertEqual(
            self.db.query(LeadStatusHistory)
            .filter(LeadStatusHistory.lead_id == self.lead.id)
            .count(),
            history_before,
            "Support updates must not append Sales status history",
        )

        # The Support queue API payload exposes both statuses explicitly.
        serialized = SupportHandoffOut.model_validate(handoff)
        self.assertEqual(serialized.sales_status, "WON")
        self.assertEqual(serialized.support_status, "ACTIVE")
        self.assertEqual(serialized.onboarding_status, "ACTIVE")

        # 8. Admin sees both statuses independently on the same customer.
        admin_view = admin_handovers(
            status_filter=None,
            search=None,
            page=1,
            limit=50,
            db=self.db,
            current_user=self.admin_user,
        )
        self.assertEqual(admin_view["total"], 1)
        row = admin_view["items"][0]
        self.assertEqual(row["lead_id"], self.lead.id)
        self.assertEqual(row["sales_status"], "WON")
        self.assertEqual(row["support_status"], "ACTIVE")
        self.assertEqual(admin_view["status_counts"].get("ACTIVE"), 1)

        filtered = admin_handovers(
            status_filter="ACTIVE",
            search=None,
            page=1,
            limit=50,
            db=self.db,
            current_user=self.admin_user,
        )
        self.assertEqual(filtered["total"], 1)
        self.assertEqual(filtered["items"][0]["support_status"], "ACTIVE")

        # Support roles are blocked from the Sales status endpoint.
        with self.assertRaises(HTTPException) as ctx:
            change_lead_status(
                lead_id=self.lead.id,
                status_req=LeadStatusRequest(status="LOST"),
                db=self.db,
                current_user=self.support_manager_user,
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.db.refresh(self.lead)
        self.assertEqual(self.lead.status, "WON")


if __name__ == "__main__":
    unittest.main(verbosity=2)
