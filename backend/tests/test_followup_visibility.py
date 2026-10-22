import os
import sys
import unittest
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.abspath('backend'))

from database import SessionLocal
from models.user import User
from models.employee import Employee
from models.lead import Lead
from models.followup import Followup
from routers.followups import (
    list_followups,
    get_followup,
    create_followup,
    update_followup,
    delete_followup
)
from routers.reports import dashboard_stats
from schemas.followup import FollowupCreate, FollowupUpdate
from fastapi import HTTPException

class TestFollowupVisibilityAndSecurity(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        
        # Load test actors
        self.admin_user = self.db.query(User).filter(User.username == "admin").first()
        self.mgr_user = self.db.query(User).filter(User.username == "chnm030").first() # Gowtham (Sales Manager)
        self.exec_a_user = self.db.query(User).filter(User.username == "chnm040").first() # Chandra Mohan (Sales Exec in Gowtham's team)
        self.exec_b_user = self.db.query(User).filter(User.username == "test_other").first() # Carol (Sales Exec in different team)
        self.support_user = self.db.query(User).filter(User.username == "chnm023").first() # ram (Support Exec)

        self.assertIsNotNone(self.admin_user, "Admin user must exist")
        self.assertIsNotNone(self.mgr_user, "Sales Manager user must exist")
        self.assertIsNotNone(self.exec_a_user, "Sales Exec A user must exist")
        self.assertIsNotNone(self.exec_b_user, "Sales Exec B user must exist")
        self.assertIsNotNone(self.support_user, "Support Exec user must exist")

        self.emp_mgr = self.db.query(Employee).filter(Employee.user_id == self.mgr_user.id).first()
        self.emp_a = self.db.query(Employee).filter(Employee.user_id == self.exec_a_user.id).first()
        self.emp_b = self.db.query(Employee).filter(Employee.user_id == self.exec_b_user.id).first()
        self.emp_support = self.db.query(Employee).filter(Employee.user_id == self.support_user.id).first()

        # Clean up any test followups from previous runs
        self.db.query(Followup).filter(Followup.notes.like("%[TEST-VISIBILITY]%")).delete()
        self.db.commit()

        # Ensure test leads exist
        self.lead_a = self.db.query(Lead).filter(Lead.assigned_to == self.emp_a.id).first()
        if not self.lead_a:
            self.lead_a = Lead(name="Test Lead A", phone="9000000001", assigned_to=self.emp_a.id, status="NEW")
            self.db.add(self.lead_a)
            self.db.commit()
            self.db.refresh(self.lead_a)

        self.lead_b = self.db.query(Lead).filter(Lead.assigned_to == self.emp_b.id).first()
        if not self.lead_b:
            self.lead_b = Lead(name="Test Lead B", phone="9000000002", assigned_to=self.emp_b.id, status="NEW")
            self.db.add(self.lead_b)
            self.db.commit()
            self.db.refresh(self.lead_b)

        self.lead_support = self.db.query(Lead).filter(Lead.assigned_to == self.emp_support.id).first()
        if not self.lead_support:
            self.lead_support = Lead(name="Test Lead Support", phone="9000000003", assigned_to=self.emp_support.id, status="NEW")
            self.db.add(self.lead_support)
            self.db.commit()
            self.db.refresh(self.lead_support)

        # Create distinct test follow-ups
        today = date.today()
        self.fu_a = Followup(
            lead_id=self.lead_a.id,
            assigned_to=self.emp_a.id,
            created_by=self.emp_a.id,
            followup_date=today,
            followup_time="11:00 AM",
            notes="[TEST-VISIBILITY] Follow-up for Exec A",
            priority="HIGH",
            status="Pending"
        )
        self.fu_b = Followup(
            lead_id=self.lead_b.id,
            assigned_to=self.emp_b.id,
            created_by=self.emp_b.id,
            followup_date=today + timedelta(days=1),
            followup_time="02:00 PM",
            notes="[TEST-VISIBILITY] Follow-up for Exec B",
            priority="LOW",
            status="Pending"
        )
        self.fu_support = Followup(
            lead_id=self.lead_support.id,
            assigned_to=self.emp_support.id,
            created_by=self.emp_support.id,
            followup_date=today + timedelta(days=2),
            followup_time="03:00 PM",
            notes="[TEST-VISIBILITY] Follow-up for Support",
            priority="MEDIUM",
            status="Pending"
        )
        self.db.add_all([self.fu_a, self.fu_b, self.fu_support])
        self.db.commit()
        self.db.refresh(self.fu_a)
        self.db.refresh(self.fu_b)
        self.db.refresh(self.fu_support)

    def tearDown(self):
        self.db.query(Followup).filter(Followup.notes.like("%[TEST-VISIBILITY]%")).delete()
        self.db.commit()
        self.db.close()

    def test_01_sales_executive_a_sees_only_own_followups(self):
        """1. Sales Executive A sees only their follow-ups, and NOT Exec B's or Support's."""
        results = list_followups(db=self.db, current_user=self.exec_a_user)
        result_ids = [f.id for f in results]

        self.assertIn(self.fu_a.id, result_ids, "Exec A must see their own follow-up")
        self.assertNotIn(self.fu_b.id, result_ids, "Exec A must NEVER see Exec B's follow-up")
        self.assertNotIn(self.fu_support.id, result_ids, "Exec A must NEVER see Support follow-up")

    def test_02_sales_executive_b_sees_only_own_followups(self):
        """2. Sales Executive B must NOT see Exec A's follow-up."""
        results = list_followups(db=self.db, current_user=self.exec_b_user)
        result_ids = [f.id for f in results]

        self.assertIn(self.fu_b.id, result_ids, "Exec B must see their own follow-up")
        self.assertNotIn(self.fu_a.id, result_ids, "Exec B must NEVER see Exec A's follow-up")
        self.assertNotIn(self.fu_support.id, result_ids, "Exec B must NEVER see Support follow-up")

    def test_03_sales_manager_sees_only_authorized_sales_team(self):
        """3. Sales Manager sees Exec A (their team member) but NOT Exec B (other team) or Support."""
        results = list_followups(db=self.db, current_user=self.mgr_user)
        result_ids = [f.id for f in results]

        self.assertIn(self.fu_a.id, result_ids, "Sales Manager must see their team member Exec A's follow-up")
        self.assertNotIn(self.fu_b.id, result_ids, "Sales Manager must NOT see unrelated Exec B's follow-up")
        self.assertNotIn(self.fu_support.id, result_ids, "Sales Manager must NOT see Support team's follow-up")

    def test_04_support_executive_sees_only_support_followups(self):
        """4. Support Executive sees only their support follow-ups and NO sales follow-ups."""
        results = list_followups(db=self.db, current_user=self.support_user)
        result_ids = [f.id for f in results]

        self.assertIn(self.fu_support.id, result_ids, "Support Exec must see their own support follow-up")
        self.assertNotIn(self.fu_a.id, result_ids, "Support Exec must NEVER see Sales Exec A follow-up")
        self.assertNotIn(self.fu_b.id, result_ids, "Support Exec must NEVER see Sales Exec B follow-up")

    def test_05_admin_has_global_visibility(self):
        """5. Admin can view all follow-ups across teams."""
        results = list_followups(db=self.db, current_user=self.admin_user)
        result_ids = [f.id for f in results]

        self.assertIn(self.fu_a.id, result_ids, "Admin sees Exec A follow-up")
        self.assertIn(self.fu_b.id, result_ids, "Admin sees Exec B follow-up")
        self.assertIn(self.fu_support.id, result_ids, "Admin sees Support follow-up")

    def test_06_direct_api_get_by_id_enforces_security(self):
        """6. Exec B cannot fetch Exec A's follow-up via GET /followups/{id} (throws 403)."""
        # Exec A can fetch their own follow-up
        res_a = get_followup(followup_id=self.fu_a.id, db=self.db, current_user=self.exec_a_user)
        self.assertEqual(res_a.id, self.fu_a.id)

        # Exec B tries to fetch Exec A's follow-up -> 403 Forbidden
        with self.assertRaises(HTTPException) as ctx:
            get_followup(followup_id=self.fu_a.id, db=self.db, current_user=self.exec_b_user)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_07_direct_api_update_enforces_security(self):
        """7. Exec B cannot update Exec A's follow-up via PUT /followups/{id} (throws 403)."""
        update_data = FollowupUpdate(notes="Malicious update by Exec B", status="Completed")
        with self.assertRaises(HTTPException) as ctx:
            update_followup(
                followup_id=self.fu_a.id,
                f_in=update_data,
                db=self.db,
                current_user=self.exec_b_user
            )
        self.assertEqual(ctx.exception.status_code, 403)

        # Exec A can legally update their own follow-up
        legal_update = FollowupUpdate(notes="Legitimate update by Exec A", priority="HIGH")
        updated = update_followup(
            followup_id=self.fu_a.id,
            f_in=legal_update,
            db=self.db,
            current_user=self.exec_a_user
        )
        self.assertEqual(updated.notes, "Legitimate update by Exec A")

    def test_08_dashboard_counts_and_followup_table_agree(self):
        """8. Dashboard follow-up count strictly matches Follow-up Management table for each role."""
        for user, title in [(self.exec_a_user, "Exec A"), (self.exec_b_user, "Exec B"), (self.support_user, "Support Exec")]:
            table_list = list_followups(db=self.db, current_user=user)
            dash = dashboard_stats(db=self.db, current_user=user)
            
            # Pending followups in table
            pending_in_table = len([f for f in table_list if f.status == "Pending"])
            # Upcoming followups list in dashboard should only contain user's authorized leads
            for uf in dash.get("upcoming_followups", []):
                fu_record = self.db.query(Followup).filter(Followup.id == uf["id"]).first()
                if fu_record:
                    emp_user_id = self.db.query(Employee.user_id).filter(Employee.id == fu_record.assigned_to).scalar()
                    self.assertEqual(emp_user_id, user.id, f"Dashboard upcoming follow-up for {title} must belong to them")

if __name__ == "__main__":
    unittest.main()
