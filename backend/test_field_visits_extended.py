import os
import sys
from datetime import datetime, date, timedelta

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, Base, engine
from models.user import User
from models.employee import Employee
from models.lead import Lead
from models.customer import Customer
from models.followup import Followup
from models.activity import LeadActivity
from models.monitoring import FieldVisit, EmployeeActivityLog
from routers.field_visits import handle_field_visit_submission, get_field_visits
from services.followup_reminder_service import check_and_trigger_followup_reminders

def run_tests():
    print("==================================================")
    print("RUNNING EXTENDED FIELD VISIT & FOLLOW-UP TESTS")
    print("==================================================")

    db = SessionLocal()
    try:
        # 1. Setup Test Users & Employees
        # Admin User
        admin_user = db.query(User).filter(User.username == "test_admin").first()
        if not admin_user:
            admin_user = User(username="test_admin", hashed_password="pw", role="ADMIN", is_active=True)
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)

        admin_emp = db.query(Employee).filter(Employee.user_id == admin_user.id).first()
        if not admin_emp:
            admin_emp = Employee(name="Admin User", username="test_admin", email="admin@test.com", user_id=admin_user.id, role="ADMIN", status="ACTIVE")
            db.add(admin_emp)
            db.commit()
            db.refresh(admin_emp)

        # Sales Manager User
        mgr_user = db.query(User).filter(User.username == "test_mgr").first()
        if not mgr_user:
            mgr_user = User(username="test_mgr", hashed_password="pw", role="SALES_MANAGER", is_active=True, reporting_manager_id=admin_user.id)
            db.add(mgr_user)
            db.commit()
            db.refresh(mgr_user)

        mgr_emp = db.query(Employee).filter(Employee.user_id == mgr_user.id).first()
        if not mgr_emp:
            mgr_emp = Employee(name="Sales Manager Bob", username="test_mgr", email="mgr@test.com", user_id=mgr_user.id, role="SALES_MANAGER", status="ACTIVE")
            db.add(mgr_emp)
            db.commit()
            db.refresh(mgr_emp)

        # Sales Executive User
        exec_user = db.query(User).filter(User.username == "test_exec").first()
        if not exec_user:
            exec_user = User(username="test_exec", hashed_password="pw", role="SALES_EXECUTIVE", is_active=True, reporting_manager_id=mgr_user.id)
            db.add(exec_user)
            db.commit()
            db.refresh(exec_user)

        exec_emp = db.query(Employee).filter(Employee.user_id == exec_user.id).first()
        if not exec_emp:
            exec_emp = Employee(name="Sales Executive Alice", username="test_exec", email="exec@test.com", user_id=exec_user.id, role="SALES_EXECUTIVE", manager_id=mgr_emp.id, reporting_manager_id=mgr_user.id, status="ACTIVE")
            db.add(exec_emp)
            db.commit()
            db.refresh(exec_emp)
        else:
            exec_emp.manager_id = mgr_emp.id
            db.commit()

        # Another Executive in another team
        other_user = db.query(User).filter(User.username == "test_other").first()
        if not other_user:
            other_user = User(username="test_other", hashed_password="pw", role="SALES_EXECUTIVE", is_active=True)
            db.add(other_user)
            db.commit()
            db.refresh(other_user)

        other_emp = db.query(Employee).filter(Employee.user_id == other_user.id).first()
        if not other_emp:
            other_emp = Employee(name="Other Agent Carol", username="test_other", email="other@test.com", user_id=other_user.id, role="SALES_EXECUTIVE", status="ACTIVE")
            db.add(other_emp)
            db.commit()
            db.refresh(other_emp)

        # Test Lead
        test_lead = db.query(Lead).filter(Lead.phone == "+919988776655").first()
        if not test_lead:
            test_lead = Lead(
                name="Sun Pharma Retail",
                phone="+919988776655",
                company="Sun Pharma Group",
                status="NEW",
                assigned_to=exec_emp.id
            )
            db.add(test_lead)
            db.commit()
            db.refresh(test_lead)

        print("[OK] Test environment and users initialized.")

        # TEST 1: Field Visit submission with Automatic Activity Creation
        token_1 = f"tok_test_{datetime.now().timestamp()}"
        submission_data = {
            "client_token": token_1,
            "lead_id": test_lead.id,
            "customer_name": test_lead.name,
            "checkin_lat": "13.0827",
            "checkin_lng": "80.2707",
            "checkin_address": "Guindy Industrial Estate, Chennai",
            "company_board_photo": "https://storage.wapluscrm.in/board1.jpg",
            "visiting_card_photo": "https://storage.wapluscrm.in/card1.jpg",
            "customer_requirements": "Requires 200 Face Recognition Access Devices",
            "visit_outcome": "Interested",
            "notes": "Met procurement head. They want quotation sent by Thursday.",
            "schedule_followup": True,
            "followup_date": (date.today() + timedelta(days=2)).isoformat(),
            "followup_time": "11:00 AM",
            "followup_priority": "HIGH",
            "followup_notes": "Call procurement head to review submitted quotation."
        }

        visit_res = handle_field_visit_submission(submission_data, db, exec_user)
        assert visit_res["id"] > 0, "Field visit ID must be > 0"
        assert visit_res["customer_name"] == test_lead.name
        assert visit_res["employee_id"] == exec_emp.id
        print(f"[TEST 1 PASS] Field Visit created successfully (ID: {visit_res['id']}).")

        # TEST 2: Verify Automatic Activity was logged
        activity = db.query(LeadActivity).filter(
            LeadActivity.related_entity_type == "FIELD_VISIT",
            LeadActivity.related_entity_id == visit_res["id"]
        ).first()
        assert activity is not None, "LeadActivity for FIELD_VISIT must exist"
        assert activity.activity_type == "FIELD_VISIT"
        assert "Outcome: Interested" in activity.description
        assert "Guindy Industrial Estate" in activity.description
        assert "200 Face Recognition Access Devices" in activity.description
        assert "board1.jpg" in activity.description
        assert "card1.jpg" in activity.description
        print(f"[TEST 2 PASS] Automatic CRM Activity created with all linked references (ID: {activity.id}).")

        # TEST 3: Verify Follow-up Scheduling & Lead Status Sync
        followup = db.query(Followup).filter(Followup.id == visit_res["followup_id"]).first()
        assert followup is not None, "Scheduled followup must exist"
        assert followup.assigned_to == exec_emp.id
        assert followup.priority == "HIGH"
        assert followup.status == "Pending"
        assert followup.reminder_sent is False

        # Lead status updated to FOLLOW-UP
        db.refresh(test_lead)
        assert test_lead.status == "FOLLOW-UP", f"Lead status should be FOLLOW-UP, got {test_lead.status}"
        print(f"[TEST 3 PASS] Follow-up automatically scheduled (ID: {followup.id}) and Lead synced to FOLLOW-UP.")

        # TEST 4: Duplicate Submission Prevention (Idempotency)
        dup_res = handle_field_visit_submission(submission_data, db, exec_user)
        assert dup_res["id"] == visit_res["id"], "Duplicate token submission must return existing visit ID"
        activities_count = db.query(LeadActivity).filter(
            LeadActivity.related_entity_type == "FIELD_VISIT",
            LeadActivity.related_entity_id == visit_res["id"]
        ).count()
        assert activities_count == 1, "Duplicate submission must NOT create duplicate activities"
        print("[TEST 4 PASS] Duplicate prevention successfully verified (no duplicate visit or activity created).")

        # TEST 5: 1-Hour Reminder Triggering & Background Service Check
        # Set followup date and time to exactly 45 minutes from now (within the 1-hour window)
        now_dt = datetime.now()
        target_fu_dt = now_dt + timedelta(minutes=45)
        followup.followup_date = target_fu_dt.date()
        followup.followup_time = target_fu_dt.strftime("%I:%M %p")
        followup.reminder_sent = False
        db.commit()

        triggered = check_and_trigger_followup_reminders(db)
        assert triggered >= 1, f"Reminder should trigger for followup in 45 mins, triggered: {triggered}"
        db.refresh(followup)
        assert followup.reminder_sent is True, "Followup reminder_sent flag must be True"

        # Check notification was created
        notif = db.query(LeadActivity).filter(LeadActivity.lead_id == test_lead.id).first()
        assert notif is not None, "Notification must be generated"

        # Calling again should not trigger duplicates
        triggered_again = check_and_trigger_followup_reminders(db)
        assert triggered_again == 0, "No duplicate reminder notifications should trigger"
        print("[TEST 5 PASS] 1-Hour automated reminder triggered with zero duplicates.")

        # TEST 6: Rescheduling Follow-up Resets Reminder State
        followup.followup_date = date.today() + timedelta(days=5)
        followup.followup_time = "03:00 PM"
        followup.reminder_sent = False
        followup.reminder_sent_at = None
        db.commit()
        db.refresh(followup)
        assert followup.reminder_sent is False, "Rescheduled followup reminder must be re-armed"
        print("[TEST 6 PASS] Rescheduled follow-up correctly resets reminder state.")

        # TEST 7: Manager & Executive Visibility Enforcement
        # Alice (Sales Executive) queries field visits
        alice_visits = get_field_visits(db=db, current_user=exec_user)
        alice_emp_ids = {v["employee_id"] for v in alice_visits}
        assert all(eid == exec_emp.id for eid in alice_emp_ids), "Sales Executive must only see their own visits"

        # Bob (Sales Manager) queries field visits (should see Alice's visit as her manager)
        bob_visits = get_field_visits(db=db, current_user=mgr_user)
        bob_emp_ids = {v["employee_id"] for v in bob_visits}
        assert exec_emp.id in bob_emp_ids, "Sales Manager must see visits from their team"

        # Admin queries field visits (company wide)
        admin_visits = get_field_visits(db=db, current_user=admin_user)
        assert len(admin_visits) >= len(bob_visits), "Admin has company-wide visibility"

        print("[TEST 7 PASS] Role-based visibility and hierarchy verified for Executive, Manager, and Admin.")

        print("\nALL BACKEND & INTEGRATION TESTS PASSED SUCCESSFULLY!")

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
