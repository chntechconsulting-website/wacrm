import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from models.user import User
from models.employee import Employee
from models.lead import Lead
from models.workflow import SupportHandoff
from models.quotation import Quotation
from services.auth import hash_password, create_access_token
from services.hierarchy_service import (
    validate_reporting_manager,
    detect_circular_hierarchy,
    get_eligible_managers,
    reassign_manager_reports,
    get_team_user_ids,
    get_team_employee_ids_from_user,
    normalize_role,
    ROLE_ADMIN,
    ROLE_SALES_MANAGER,
    ROLE_SALES_EXECUTIVE,
    ROLE_SUPPORT_MANAGER,
    ROLE_SUPPORT_EXECUTIVE
)
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_rbac_suite():
    db = SessionLocal()
    print("==================================================================")
    print("   STARTING RBAC & REPORTING MANAGER COMPREHENSIVE TEST SUITE    ")
    print("==================================================================")

    # 1. Verify Seeded Accounts
    admin_user = db.query(User).filter(User.username == "admin").first()
    sales_mgr = db.query(User).filter(User.username == "chnm030").first()
    sales_exec = db.query(User).filter(User.username == "chnm040").first()
    support_mgr = db.query(User).filter(User.username == "kumar").first()
    support_exec = db.query(User).filter(User.username == "chnm023").first()

    assert admin_user is not None, "Admin user must exist"
    assert sales_mgr is not None, "Sales Manager chnm030 must exist"
    assert sales_exec is not None, "Sales Exec chnm040 must exist"
    assert support_mgr is not None, "Support Manager kumar must exist"
    assert support_exec is not None, "Support Exec chnm023 must exist"

    print("[PASS] Seeded accounts verified:")
    print(f"  - Admin: #{admin_user.id} ({admin_user.username}, Role: {admin_user.role})")
    print(f"  - Sales Mgr: #{sales_mgr.id} ({sales_mgr.username}, Role: {sales_mgr.role}, Mgr: #{sales_mgr.reporting_manager_id})")
    print(f"  - Sales Exec: #{sales_exec.id} ({sales_exec.username}, Role: {sales_exec.role}, Mgr: #{sales_exec.reporting_manager_id})")
    print(f"  - Support Mgr: #{support_mgr.id} ({support_mgr.username}, Role: {support_mgr.role}, Mgr: #{support_mgr.reporting_manager_id})")
    print(f"  - Support Exec: #{support_exec.id} ({support_exec.username}, Role: {support_exec.role}, Mgr: #{support_exec.reporting_manager_id})")

    # Generate Auth Tokens for each role
    admin_token = create_access_token({"sub": admin_user.username, "role": admin_user.role, "user_id": admin_user.id})
    sales_mgr_token = create_access_token({"sub": sales_mgr.username, "role": sales_mgr.role, "user_id": sales_mgr.id})
    sales_exec_token = create_access_token({"sub": sales_exec.username, "role": sales_exec.role, "user_id": sales_exec.id})
    support_mgr_token = create_access_token({"sub": support_mgr.username, "role": support_mgr.role, "user_id": support_mgr.id})
    support_exec_token = create_access_token({"sub": support_exec.username, "role": support_exec.role, "user_id": support_exec.id})

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    sales_mgr_headers = {"Authorization": f"Bearer {sales_mgr_token}"}
    sales_exec_headers = {"Authorization": f"Bearer {sales_exec_token}"}
    support_mgr_headers = {"Authorization": f"Bearer {support_mgr_token}"}
    support_exec_headers = {"Authorization": f"Bearer {support_exec_token}"}

    # ============================================================================
    # TEST 1: REPORTING MANAGER VALIDATION RULES
    # ============================================================================
    print("\n--- TEST 1: Reporting Manager Assignment Validation Rules ---")

    # 1.1 Sales Executive without manager -> must fail
    ok, err = validate_reporting_manager(None, ROLE_SALES_EXECUTIVE, "SALES", None, db)
    assert not ok and "Sales Executive requires" in err, f"Expected fail: {err}"
    print("[PASS] Rule 1.1: Sales Executive without manager rejected.")

    # 1.2 Sales Executive reporting to Admin -> must fail (must report to Sales Manager)
    ok, err = validate_reporting_manager(None, ROLE_SALES_EXECUTIVE, "SALES", admin_user.id, db)
    assert not ok and "Sales Manager" in err, f"Expected fail: {err}"
    print("[PASS] Rule 1.2: Sales Executive reporting to Admin rejected (must report to Sales Manager).")

    # 1.3 Sales Executive reporting to Sales Manager -> must succeed
    ok, err = validate_reporting_manager(None, ROLE_SALES_EXECUTIVE, "SALES", sales_mgr.id, db)
    assert ok and err is None, f"Expected pass: {err}"
    print("[PASS] Rule 1.3: Sales Executive reporting to Sales Manager accepted.")

    # 1.4 Support Executive reporting to Sales Manager -> must fail
    ok, err = validate_reporting_manager(None, ROLE_SUPPORT_EXECUTIVE, "SUPPORT", sales_mgr.id, db)
    assert not ok and "Support Manager" in err, f"Expected fail: {err}"
    print("[PASS] Rule 1.4: Support Executive reporting to Sales Manager rejected (must report to Support Manager).")

    # 1.5 Support Executive reporting to Support Manager -> must succeed
    ok, err = validate_reporting_manager(None, ROLE_SUPPORT_EXECUTIVE, "SUPPORT", support_mgr.id, db)
    assert ok and err is None, f"Expected pass: {err}"
    print("[PASS] Rule 1.5: Support Executive reporting to Support Manager accepted.")

    # 1.6 Sales Manager reporting to Sales Executive -> must fail (must report to Admin)
    ok, err = validate_reporting_manager(None, ROLE_SALES_MANAGER, "SALES", sales_exec.id, db)
    assert not ok and "Admin" in err, f"Expected fail: {err}"
    print("[PASS] Rule 1.6: Sales Manager reporting to Sales Executive rejected (must report to Admin).")

    # 1.7 Sales Manager reporting to Admin -> must succeed
    ok, err = validate_reporting_manager(None, ROLE_SALES_MANAGER, "SALES", admin_user.id, db)
    assert ok and err is None, f"Expected pass: {err}"
    print("[PASS] Rule 1.7: Sales Manager reporting to Admin accepted.")

    # 1.8 Support Manager reporting to Admin -> must succeed
    ok, err = validate_reporting_manager(None, ROLE_SUPPORT_MANAGER, "SUPPORT", admin_user.id, db)
    assert ok and err is None, f"Expected pass: {err}"
    print("[PASS] Rule 1.8: Support Manager reporting to Admin accepted.")

    # 1.9 Admin user without manager -> must succeed
    ok, err = validate_reporting_manager(None, ROLE_ADMIN, "ADMIN", None, db)
    assert ok and err is None, f"Expected pass: {err}"
    print("[PASS] Rule 1.9: Admin user without manager accepted.")

    # 1.10 Self-assignment -> must fail
    ok, err = validate_reporting_manager(sales_mgr.id, ROLE_SALES_MANAGER, "SALES", sales_mgr.id, db)
    assert not ok and "own reporting manager" in err, f"Expected fail: {err}"
    print("[PASS] Rule 1.10: Self-reporting manager assignment rejected.")

    # 1.11 Circular hierarchy detection:
    is_circ, path = detect_circular_hierarchy(admin_user.id, sales_exec.id, db)
    assert is_circ, f"Expected circular hierarchy detection for admin -> sales_exec -> sales_mgr -> admin"
    print(f"[PASS] Rule 1.11: Circular hierarchy detected and blocked: {' -> '.join(path)}")

    # ============================================================================
    # TEST 2: ELIGIBLE MANAGERS API
    # ============================================================================
    print("\n--- TEST 2: Eligible Managers API Filtering ---")

    # For Sales Executive -> eligible managers must all be SALES_MANAGER
    res = client.get("/api/users/eligible-managers?role=SALES_EXECUTIVE", headers=admin_headers)
    assert res.status_code == 200, res.text
    mgrs = res.json()
    assert len(mgrs) > 0, "Must return at least one active sales manager"
    for m in mgrs:
        assert m["role"] in ["SALES_MANAGER", "MANAGER"], f"Invalid manager role: {m}"
    print(f"[PASS] Eligible managers for Sales Executive: {[m['username'] for m in mgrs]}")

    # For Support Executive -> eligible managers must all be SUPPORT_MANAGER
    res = client.get("/api/users/eligible-managers?role=SUPPORT_EXECUTIVE", headers=admin_headers)
    assert res.status_code == 200, res.text
    mgrs = res.json()
    assert len(mgrs) > 0, "Must return at least one active support manager"
    for m in mgrs:
        assert m["role"] == "SUPPORT_MANAGER", f"Invalid manager role: {m}"
    print(f"[PASS] Eligible managers for Support Executive: {[m['username'] for m in mgrs]}")

    # For Sales Manager -> eligible managers must all be ADMIN
    res = client.get("/api/users/eligible-managers?role=SALES_MANAGER", headers=admin_headers)
    assert res.status_code == 200, res.text
    mgrs = res.json()
    assert len(mgrs) > 0, "Must return at least one active admin"
    for m in mgrs:
        assert m["role"] == "ADMIN", f"Invalid manager role: {m}"
    print(f"[PASS] Eligible managers for Sales Manager: {[m['username'] for m in mgrs]}")

    # Exclude user and their subordinates
    res = client.get(f"/api/users/eligible-managers?role=SALES_MANAGER&exclude_user_id={admin_user.id}", headers=admin_headers)
    assert res.status_code == 200
    mgr_ids = [m["id"] for m in res.json()]
    assert admin_user.id not in mgr_ids, "Excluded user must not appear"
    print("[PASS] Exclude user_id filtering works properly.")

    # ============================================================================
    # TEST 3: USER CREATION & REASSIGNMENT APIS
    # ============================================================================
    print("\n--- TEST 3: User Creation & Reassignment Workflows ---")

    test_exec_username = "test_exec_unit"
    temp_mgr_username = "temp_sales_mgr"

    def cleanup_test_users():
        cleanup_db = SessionLocal()
        try:
            # 1. Restore sales_exec (chnm040) reporting to sales_mgr (chnm030) FIRST
            se = cleanup_db.query(User).filter(User.username == "chnm040").first()
            sm = cleanup_db.query(User).filter(User.username == "chnm030").first()
            if se and sm:
                se.reporting_manager_id = sm.id
                se_emp = cleanup_db.query(Employee).filter(Employee.user_id == se.id).first()
                sm_emp = cleanup_db.query(Employee).filter(Employee.user_id == sm.id).first()
                if se_emp:
                    se_emp.reporting_manager_id = sm.id
                    if sm_emp: se_emp.manager_id = sm_emp.id
            cleanup_db.commit()

            # 2. Reassign any reports of temp_mgr back to sales_mgr
            temp_u = cleanup_db.query(User).filter(User.username == temp_mgr_username).first()
            if temp_u and sm:
                reports = cleanup_db.query(User).filter(User.reporting_manager_id == temp_u.id).all()
                for r in reports:
                    r.reporting_manager_id = sm.id
                cleanup_db.commit()

            # 3. Delete test users
            for uname in [test_exec_username, temp_mgr_username]:
                u = cleanup_db.query(User).filter(User.username == uname).first()
                if u:
                    e = cleanup_db.query(Employee).filter(Employee.user_id == u.id).first()
                    if e: cleanup_db.delete(e)
                    cleanup_db.delete(u)
            cleanup_db.commit()
        finally:
            cleanup_db.close()

    cleanup_test_users()
    db.expire_all()

    try:
        # 3.1 Try creating Sales Executive with invalid manager (Admin) -> should return 400
        res = client.post("/api/users", json={
            "name": "Test Exec",
            "email": "test_exec@example.com",
            "username": test_exec_username,
            "password": "Password123!",
            "role": "SALES_EXECUTIVE",
            "department": "SALES",
            "reporting_manager_id": admin_user.id
        }, headers=admin_headers)
        assert res.status_code == 400, f"Expected 400 Bad Request, got {res.status_code}"
        print("[PASS] API blocked creation of Sales Executive with non-Sales-Manager manager.")

        # 3.2 Create Sales Executive with valid Sales Manager -> should return 201
        res = client.post("/api/users", json={
            "name": "Test Exec",
            "email": "test_exec@example.com",
            "username": test_exec_username,
            "password": "Password123!",
            "role": "SALES_EXECUTIVE",
            "department": "SALES",
            "reporting_manager_id": sales_mgr.id
        }, headers=admin_headers)
        assert res.status_code == 201, f"Expected 201 Created, got {res.status_code}: {res.text}"
        created_user_id = res.json()["id"]
        print(f"[PASS] Successfully created user #{created_user_id} with Sales Manager #{sales_mgr.id}.")

        # 3.3 Check deactivating manager with active reports is blocked
        res = client.post(f"/api/users/{sales_mgr.id}/toggle-status", headers=admin_headers)
        assert res.status_code == 400 and "active direct report" in res.json()["detail"], f"Expected deactivation block, got {res.status_code}: {res.text}"
        print("[PASS] API blocked deactivating manager who has active reports.")

        # 3.4 Create a second Sales Manager to reassign reports to
        res = client.post("/api/users", json={
            "name": "Temp Sales Manager",
            "email": "temp_sales_mgr@example.com",
            "username": temp_mgr_username,
            "password": "Password123!",
            "role": "SALES_MANAGER",
            "department": "SALES",
            "reporting_manager_id": admin_user.id
        }, headers=admin_headers)
        assert res.status_code == 201, f"Failed creating temp sales manager: {res.text}"
        temp_mgr_id = res.json()["id"]

        # 3.5 Reassign reports to temp_sales_mgr
        res = client.post(f"/api/users/{sales_mgr.id}/reassign-reports", json={
            "new_manager_id": temp_mgr_id
        }, headers=admin_headers)
        assert res.status_code == 200, f"Failed reassigning reports: {res.text}"
        print(f"[PASS] Reassigned reports from #{sales_mgr.id} to #{temp_mgr_id}: {res.json()['message']}")

    finally:
        cleanup_test_users()
        db.expire_all()

    # ============================================================================
    # TEST 4: STRICT RBAC DATA SEGREGATION - LEADS
    # ============================================================================
    print("\n--- TEST 4: Strict RBAC Data Segregation - Leads ---")

    # 4.1 Support Manager trying to list leads -> must return 403 Forbidden
    res = client.get("/api/leads", headers=support_mgr_headers)
    assert res.status_code == 403, f"Expected 403 Forbidden for Support Manager, got {res.status_code}"
    print("[PASS] Support Manager forbidden from listing Sales leads (HTTP 403).")

    # 4.2 Support Executive trying to list leads -> must return 403 Forbidden
    res = client.get("/api/leads", headers=support_exec_headers)
    assert res.status_code == 403, f"Expected 403 Forbidden for Support Executive, got {res.status_code}"
    print("[PASS] Support Executive forbidden from listing Sales leads (HTTP 403).")

    # 4.3 Sales Executive listing leads -> only assigned to them
    sales_exec_emp = db.query(Employee).filter(Employee.user_id == sales_exec.id).first()
    res = client.get("/api/leads", headers=sales_exec_headers)
    assert res.status_code == 200, f"Expected 200 for Sales Executive, got {res.status_code}"
    leads_data = res.json()
    for l in leads_data.get("items", []):
        assert l["assigned_to"] == sales_exec_emp.id, f"Sales Exec saw lead assigned to {l['assigned_to']}"
    print(f"[PASS] Sales Executive sees only their own assigned leads ({len(leads_data.get('items', []))} items).")

    # 4.4 Sales Executive trying to delete a lead -> must return 403 Forbidden
    any_lead = db.query(Lead).first()
    if any_lead:
        res = client.delete(f"/api/leads/{any_lead.id}", headers=sales_exec_headers)
        assert res.status_code == 403, f"Expected 403 Forbidden for Sales Exec deletion, got {res.status_code}"
        print("[PASS] Sales Executive forbidden from deleting leads (HTTP 403).")

    # 4.5 Sales Manager listing leads -> sees their team leads
    res = client.get("/api/leads", headers=sales_mgr_headers)
    assert res.status_code == 200, f"Expected 200 for Sales Manager, got {res.status_code}"
    print(f"[PASS] Sales Manager can view team leads ({res.json().get('total', 0)} total).")

    # 4.6 Admin listing leads -> sees all leads
    res = client.get("/api/leads", headers=admin_headers)
    assert res.status_code == 200, f"Expected 200 for Admin, got {res.status_code}"
    print(f"[PASS] Admin has company-wide visibility ({res.json().get('total', 0)} total).")

    # ============================================================================
    # TEST 5: STRICT RBAC DATA SEGREGATION - QUOTATIONS
    # ============================================================================
    print("\n--- TEST 5: Strict RBAC Data Segregation - Quotations ---")

    # 5.1 Support Manager trying to list quotations -> 403 Forbidden
    res = client.get("/api/integrations/waquote/documents", headers=support_mgr_headers)
    assert res.status_code == 403, f"Expected 403 for Support Manager on quotations, got {res.status_code}"
    print("[PASS] Support Manager forbidden from listing Sales quotations (HTTP 403).")

    # 5.2 Support Executive trying to list quotations -> 403 Forbidden
    res = client.get("/api/integrations/waquote/documents", headers=support_exec_headers)
    assert res.status_code == 403, f"Expected 403 for Support Executive on quotations, got {res.status_code}"
    print("[PASS] Support Executive forbidden from listing Sales quotations (HTTP 403).")

    # 5.3 Support Manager trying to access client quotation context -> 403 Forbidden
    if any_lead:
        res = client.get(f"/api/integrations/waquote/lead-context/{any_lead.id}", headers=support_mgr_headers)
        assert res.status_code == 403, f"Expected 403 for Support Manager on quote context, got {res.status_code}"
        print("[PASS] Support Manager forbidden from accessing client quotation context (HTTP 403).")

    # 5.4 Sales Manager listing quotations -> 200 OK
    res = client.get("/api/integrations/waquote/documents", headers=sales_mgr_headers)
    assert res.status_code == 200, f"Expected 200 for Sales Manager, got {res.status_code}"
    print(f"[PASS] Sales Manager can view sales quotations ({len(res.json().get('documents', []))} documents).")

    # 5.5 Admin listing quotations -> 200 OK
    res = client.get("/api/integrations/waquote/documents", headers=admin_headers)
    assert res.status_code == 200, f"Expected 200 for Admin, got {res.status_code}"
    print(f"[PASS] Admin can view all quotations ({len(res.json().get('documents', []))} documents).")

    # ============================================================================
    # TEST 6: STRICT RBAC DATA SEGREGATION - SUPPORT ONBOARDING & TICKETS
    # ============================================================================
    print("\n--- TEST 6: Strict RBAC Data Segregation - Support Onboarding ---")

    # 6.1 Sales Executive trying to list support handoffs -> 403 Forbidden
    res = client.get("/api/workflow/support/handoffs", headers=sales_exec_headers)
    assert res.status_code == 403, f"Expected 403 for Sales Exec on support handoffs, got {res.status_code}"
    print("[PASS] Sales Executive forbidden from accessing internal Support tickets (HTTP 403).")

    # 6.2 Sales Manager trying to list support handoffs -> 403 Forbidden
    res = client.get("/api/workflow/support/handoffs", headers=sales_mgr_headers)
    assert res.status_code == 403, f"Expected 403 for Sales Manager on support handoffs, got {res.status_code}"
    print("[PASS] Sales Manager forbidden from accessing internal Support tickets (HTTP 403).")

    # 6.3 Support Manager listing support handoffs -> 200 OK
    res = client.get("/api/workflow/support/handoffs", headers=support_mgr_headers)
    assert res.status_code == 200, f"Expected 200 for Support Manager, got {res.status_code}"
    print(f"[PASS] Support Manager can access support onboarding queue ({len(res.json())} items).")

    # 6.4 Support Executive listing support handoffs -> 200 OK (scoped to own assignments)
    res = client.get("/api/workflow/support/handoffs", headers=support_exec_headers)
    assert res.status_code == 200, f"Expected 200 for Support Executive, got {res.status_code}"
    print(f"[PASS] Support Executive can access assigned support onboarding queue ({len(res.json())} items).")

    # 6.5 Admin listing support handoffs -> 200 OK
    res = client.get("/api/workflow/support/handoffs", headers=admin_headers)
    assert res.status_code == 200, f"Expected 200 for Admin, got {res.status_code}"
    print(f"[PASS] Admin can access all support onboarding records ({len(res.json())} items).")

    print("\n==================================================================")
    print("   ALL RBAC & REPORTING MANAGER TESTS COMPLETED SUCCESSFULLY!    ")
    print("==================================================================")

if __name__ == "__main__":
    test_rbac_suite()
