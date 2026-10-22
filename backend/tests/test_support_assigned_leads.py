import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.abspath('backend'))

from database import SessionLocal
from models.user import User
from models.employee import Employee
from models.lead import Lead, LeadAssignment
from models.workflow import SupportHandoff
from routers.leads import (
    get_support_assigned_leads,
    get_support_team_members,
    assign_support_lead,
    get_lead,
    update_lead,
    change_lead_status
)
from schemas.lead import LeadUpdate, LeadStatusRequest
from fastapi import HTTPException

class TestSupportAssignedLeads(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()

        self.admin_user = self.db.query(User).filter(User.username == "admin").first()
        self.sales_mgr = self.db.query(User).filter(User.username == "chnm030").first() # Gowtham (Sales Manager)
        self.sales_exec = self.db.query(User).filter(User.username == "chnm040").first() # Chandra Mohan (Sales Exec)
        self.sup_mgr_user = self.db.query(User).filter(User.username == "kumar").first() # Kumar (Support Manager)
        self.sup_exec_a_user = self.db.query(User).filter(User.username == "chnm023").first() # ram (Support Exec A)

        self.assertIsNotNone(self.admin_user, "Admin user must exist")
        self.assertIsNotNone(self.sales_mgr, "Sales manager user must exist")
        self.assertIsNotNone(self.sales_exec, "Sales exec user must exist")
        self.assertIsNotNone(self.sup_mgr_user, "Support manager user must exist")
        self.assertIsNotNone(self.sup_exec_a_user, "Support exec A user must exist")

        self.emp_sup_mgr = self.db.query(Employee).filter(Employee.user_id == self.sup_mgr_user.id).first()
        self.emp_sup_a = self.db.query(Employee).filter(Employee.user_id == self.sup_exec_a_user.id).first()
        self.emp_sales = self.db.query(Employee).filter(Employee.user_id == self.sales_exec.id).first()

        # Create or ensure Support Exec B (outside Exec A's ownership)
        self.sup_exec_b_user = self.db.query(User).filter(User.username == "test_sup_b").first()
        if not self.sup_exec_b_user:
            from services.auth import hash_password
            self.sup_exec_b_user = User(
                username="test_sup_b",
                hashed_password=hash_password("Support@123"),
                role="SUPPORT_EXECUTIVE",
                department="SUPPORT",
                is_active=True
            )
            self.db.add(self.sup_exec_b_user)
            self.db.commit()
            self.db.refresh(self.sup_exec_b_user)

        self.emp_sup_b = self.db.query(Employee).filter(Employee.user_id == self.sup_exec_b_user.id).first()
        if not self.emp_sup_b:
            self.emp_sup_b = Employee(
                user_id=self.sup_exec_b_user.id,
                name="Support Exec B",
                username="test_sup_b",
                email="test_sup_b@example.com",
                phone="9876543210",
                role="SUPPORT_EXECUTIVE",
                department="SUPPORT",
                manager_id=self.emp_sup_mgr.id if self.emp_sup_mgr else None
            )
            self.db.add(self.emp_sup_b)
            self.db.commit()
            self.db.refresh(self.emp_sup_b)

        # Create a dedicated support lead for Exec A
        self.lead_a = self.db.query(Lead).filter(Lead.name == "[TEST] Support Lead A").first()
        if not self.lead_a:
            self.lead_a = Lead(
                name="[TEST] Support Lead A",
                phone="9876543201",
                email="leada@testsupport.com",
                company="Test Corp Alpha",
                source="MANUAL",
                status="PENDING_ONBOARDING",
                priority="HIGH",
                assigned_to=self.emp_sup_a.id
            )
            self.db.add(self.lead_a)
            self.db.commit()
            self.db.refresh(self.lead_a)

        self.handoff_a = self.db.query(SupportHandoff).filter(SupportHandoff.lead_id == self.lead_a.id).first()
        if not self.handoff_a:
            self.handoff_a = SupportHandoff(
                lead_id=self.lead_a.id,
                customer_id=1,
                customer_name="Test Customer Alpha",
                company_name="Test Corp Alpha",
                product_service="CRM Cloud Pro",
                customer_requirements="Requires SSO & WhatsApp Integration setup.",
                support_manager_id=self.emp_sup_mgr.id,
                support_manager_name=self.emp_sup_mgr.name,
                assigned_agent_id=self.emp_sup_a.id,
                assigned_agent_name=self.emp_sup_a.name,
                onboarding_status="PENDING_ONBOARDING"
            )
            self.db.add(self.handoff_a)
            self.db.commit()

        # Always ensure proper baseline assignment
        self.lead_a.assigned_to = self.emp_sup_a.id
        self.handoff_a.assigned_agent_id = self.emp_sup_a.id
        self.handoff_a.assigned_agent_name = self.emp_sup_a.name
        self.db.commit()

        # Create a dedicated support lead for Exec B
        self.lead_b = self.db.query(Lead).filter(Lead.name == "[TEST] Support Lead B").first()
        if not self.lead_b:
            self.lead_b = Lead(
                name="[TEST] Support Lead B",
                phone="9876543202",
                email="leadb@testsupport.com",
                company="Test Corp Beta",
                source="MANUAL",
                status="CONTACTED",
                priority="MEDIUM",
                assigned_to=self.emp_sup_b.id
            )
            self.db.add(self.lead_b)
            self.db.commit()
            self.db.refresh(self.lead_b)

        self.handoff_b = self.db.query(SupportHandoff).filter(SupportHandoff.lead_id == self.lead_b.id).first()
        if not self.handoff_b:
            self.handoff_b = SupportHandoff(
                lead_id=self.lead_b.id,
                customer_id=2,
                customer_name="Test Customer Beta",
                company_name="Test Corp Beta",
                product_service="Payroll Integration",
                customer_requirements="Configure biometric attendance.",
                support_manager_id=self.emp_sup_mgr.id,
                support_manager_name=self.emp_sup_mgr.name,
                assigned_agent_id=self.emp_sup_b.id,
                assigned_agent_name=self.emp_sup_b.name,
                onboarding_status="CONTACTED"
            )
            self.db.add(self.handoff_b)
            self.db.commit()

        # Pure Sales lead (not in support)
        self.sales_only_lead = self.db.query(Lead).filter(Lead.name == "[TEST] Pure Sales Lead").first()
        if not self.sales_only_lead:
            self.sales_only_lead = Lead(
                name="[TEST] Pure Sales Lead",
                phone="9876543299",
                email="salesonly@example.com",
                company="Sales Prospect Ltd",
                source="META",
                status="NEW",
                assigned_to=self.emp_sales.id
            )
            self.db.add(self.sales_only_lead)
            self.db.commit()
            self.db.refresh(self.sales_only_lead)

    def tearDown(self):
        self.db.close()

    def test_01_support_exec_a_sees_only_own_assigned_leads(self):
        """Support Executive A must see Lead A, but NOT Lead B."""
        res = get_support_assigned_leads(
            search=None, status=None, priority=None, source=None,
            assigned_agent_id=None, skip=0, limit=50,
            db=self.db, current_user=self.sup_exec_a_user
        )
        item_ids = [item["id"] for item in res["items"]]
        self.assertIn(self.lead_a.id, item_ids, "Exec A must see their own assigned lead A")
        self.assertNotIn(self.lead_b.id, item_ids, "Exec A must NOT see Exec B's assigned lead B")
        self.assertNotIn(self.sales_only_lead.id, item_ids, "Exec A must NOT see pure sales leads")

    def test_02_support_exec_b_sees_only_own_assigned_leads(self):
        """Support Executive B must see Lead B, but NOT Lead A."""
        res = get_support_assigned_leads(
            search=None, status=None, priority=None, source=None,
            assigned_agent_id=None, skip=0, limit=50,
            db=self.db, current_user=self.sup_exec_b_user
        )
        item_ids = [item["id"] for item in res["items"]]
        self.assertIn(self.lead_b.id, item_ids, "Exec B must see their own assigned lead B")
        self.assertNotIn(self.lead_a.id, item_ids, "Exec B must NOT see Exec A's assigned lead A")

    def test_03_support_manager_sees_team_assigned_leads(self):
        """Support Manager must see leads for their authorized support team (Lead A and Lead B)."""
        res = get_support_assigned_leads(
            search=None, status=None, priority=None, source=None,
            assigned_agent_id=None, skip=0, limit=50,
            db=self.db, current_user=self.sup_mgr_user
        )
        item_ids = [item["id"] for item in res["items"]]
        self.assertIn(self.lead_a.id, item_ids, "Manager must see team lead A")
        self.assertIn(self.lead_b.id, item_ids, "Manager must see team lead B")
        self.assertNotIn(self.sales_only_lead.id, item_ids, "Manager must NOT see pure sales leads")

    def test_04_sales_executive_forbidden_from_support_assigned(self):
        """Sales Executive attempting to access Support Assigned Leads receives 403 Forbidden."""
        with self.assertRaises(HTTPException) as ctx:
            get_support_assigned_leads(
                search=None, status=None, priority=None, source=None,
                assigned_agent_id=None, skip=0, limit=50,
                db=self.db, current_user=self.sales_exec
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("Sales users cannot access Support Assigned Leads", ctx.exception.detail)

    def test_05_sales_manager_forbidden_from_support_assigned(self):
        """Sales Manager attempting to access Support Assigned Leads receives 403 Forbidden."""
        with self.assertRaises(HTTPException) as ctx:
            get_support_assigned_leads(
                search=None, status=None, priority=None, source=None,
                assigned_agent_id=None, skip=0, limit=50,
                db=self.db, current_user=self.sales_mgr
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("Sales users cannot access Support Assigned Leads", ctx.exception.detail)

    def test_06_admin_has_company_wide_visibility(self):
        """Admin sees all company-wide support leads."""
        res = get_support_assigned_leads(
            search=None, status=None, priority=None, source=None,
            assigned_agent_id=None, skip=0, limit=50,
            db=self.db, current_user=self.admin_user
        )
        item_ids = [item["id"] for item in res["items"]]
        self.assertIn(self.lead_a.id, item_ids, "Admin must see lead A")
        self.assertIn(self.lead_b.id, item_ids, "Admin must see lead B")

    def test_07_support_exec_can_view_own_lead_detail(self):
        """Support Executive can view GET /leads/{id} for authorized support lead, but receives 403 for unauthorized lead."""
        # Own lead: should succeed
        out = get_lead(lead_id=self.lead_a.id, db=self.db, current_user=self.sup_exec_a_user)
        self.assertEqual(out.id, self.lead_a.id)

        # Other exec's lead: should be forbidden
        with self.assertRaises(HTTPException) as ctx:
            get_lead(lead_id=self.lead_b.id, db=self.db, current_user=self.sup_exec_a_user)
        self.assertEqual(ctx.exception.status_code, 403)

        # Sales-only lead: should be forbidden
        with self.assertRaises(HTTPException) as ctx:
            get_lead(lead_id=self.sales_only_lead.id, db=self.db, current_user=self.sup_exec_a_user)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_08_support_exec_can_update_own_lead_status(self):
        """Support Executive can change status on authorized lead."""
        req = LeadStatusRequest(status="ONBOARDING_IN_PROGRESS")
        out = change_lead_status(
            lead_id=self.lead_a.id,
            status_req=req,
            db=self.db,
            current_user=self.sup_exec_a_user
        )
        self.assertEqual(out.status, "ONBOARDING_IN_PROGRESS")

        # Attempting to update another exec's lead status returns 403
        with self.assertRaises(HTTPException) as ctx:
            change_lead_status(
                lead_id=self.lead_b.id,
                status_req=req,
                db=self.db,
                current_user=self.sup_exec_a_user
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_09_support_manager_can_reassign_agent(self):
        """Support Manager can assign/reassign a Support Executive to a lead."""
        res = assign_support_lead(
            lead_id=self.lead_a.id,
            payload={"assigned_agent_id": self.emp_sup_b.id},
            db=self.db,
            current_user=self.sup_mgr_user
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["assigned_to"], self.emp_sup_b.id)

        # Reassign back to Exec A
        res2 = assign_support_lead(
            lead_id=self.lead_a.id,
            payload={"assigned_agent_id": self.emp_sup_a.id},
            db=self.db,
            current_user=self.sup_mgr_user
        )
        self.assertTrue(res2["success"])
        self.assertEqual(res2["assigned_to"], self.emp_sup_a.id)

    def test_10_support_team_members_list(self):
        """Support team members endpoint returns support employees only."""
        members = get_support_team_members(db=self.db, current_user=self.sup_mgr_user)
        self.assertIsInstance(members, list)
        member_ids = [m["id"] for m in members]
        self.assertIn(self.emp_sup_a.id, member_ids)
        self.assertIn(self.emp_sup_b.id, member_ids)

        # Sales users are forbidden from viewing Support team members
        with self.assertRaises(HTTPException) as ctx:
            get_support_team_members(db=self.db, current_user=self.sales_exec)
        self.assertEqual(ctx.exception.status_code, 403)

if __name__ == "__main__":
    unittest.main()
