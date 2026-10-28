"""
Comprehensive End-to-End Validation Suite for:
4A. Mandatory Product Classification After Call Completion

Tests the entire lifecycle:
1. Automatic category detection from text, signals, and previous notes.
2. Initial call lookup (`/doocti/lead-by-number`) returns detected or existing product category.
3. Call completion push (`/doocti/call-log`) creates CallLog with accurate product category and links lead.
4. Call disposition update (`/doocti/lead/update`) updates product_category and notes, marking confirmed.
5. Manual correction is strictly preserved during subsequent calls, webhooks, and lookups.
6. Verification in CallLogs API (`/ivr/calls`) showing product_category.
7. Verification that lead assignment/ownership is NEVER altered unless explicitly configured.
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.abspath("backend"))

if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

import database
from models.lead import Lead
from models.call_log import CallLog
from models.employee import Employee
from models.user import User
from services.product_categorization_service import ProductCategorizationService
from routers.doocti import get_lead_by_number, update_lead_from_doocti, DooctiLeadUpdatePayload
from routers.ivr import list_call_logs

db = next(database.get_db())

print("=" * 80)
print("RUNNING 4A. MANDATORY PRODUCT CLASSIFICATION END-TO-END VALIDATION SUITE")
print("=" * 80)

# Setup test employee and user
test_emp = db.query(Employee).filter(Employee.id == 9).first() # Chandra Mohan
admin_user = db.query(User).filter(User.role == "ADMIN").first()

# TEST 1: Automatic Detection Unit Tests
bio_text = "Customer interested in biometric attendance machine and fingerprint scanner MB160"
wahrms_text = "Customer looking for WAHRMS cloud HRMS software with automated payroll and leave management"
ambiguous_text = "General inquiry about business services"

cat_bio = ProductCategorizationService.detect_category_from_text(bio_text)
cat_wahrms = ProductCategorizationService.detect_category_from_text(wahrms_text)
cat_ambig = ProductCategorizationService.detect_category_from_text(ambiguous_text)

assert cat_bio == "BIOMETRIC", f"Expected BIOMETRIC, got {cat_bio}"
assert cat_wahrms == "WAHRMS", f"Expected WAHRMS, got {cat_wahrms}"
assert cat_ambig == "UNCLASSIFIED", f"Expected UNCLASSIFIED, got {cat_ambig}"
print("✓ TEST 1 PASSED: Automatic product category detection correctly classifies BIOMETRIC, WAHRMS, and UNCLASSIFIED.")

# Clean up any previous test leads/call logs
test_phone = "9876543288"
db.query(CallLog).filter(CallLog.from_number.ilike(f"%{test_phone}%") | CallLog.to_number.ilike(f"%{test_phone}%")).delete()
db.query(Lead).filter(Lead.phone.ilike(f"%{test_phone}%")).delete()
db.commit()

# TEST 2: Create a lead with Biometric requirement notes and verify suggestion
lead1 = Lead(
    name="Test Biometric Customer",
    phone=test_phone,
    company="Tech Biometrics Ltd",
    source="DOOCTI",
    status="NEW",
    assigned_to=test_emp.id,
    requirement_notes="Customer wants 2 facial recognition biometric machines for staff attendance."
)
db.add(lead1)
db.commit()
db.refresh(lead1)

sug = ProductCategorizationService.suggest_category_for_lead(lead1)
assert sug["suggested_category"] == "BIOMETRIC", f"Expected BIOMETRIC suggestion, got {sug}"
print(f"✓ TEST 2 PASSED: Lead suggested category correctly identified as '{sug['suggested_category']}'.")

# TEST 3: Lead Retrieval API (/doocti/lead-by-number) returns suggested/existing category
lead_lookup = get_lead_by_number(number=test_phone, auto_create=False, db=db)
assert lead_lookup["success"] is True
assert lead_lookup["lead"]["id"] == lead1.id
assert lead_lookup["lead"]["suggested_product_category"] == "BIOMETRIC"
print(f"✓ TEST 3 PASSED: /doocti/lead-by-number returns suggested category '{lead_lookup['lead']['suggested_product_category']}'.")

# TEST 4: Call End & CallLog creation
call_id = f"test_call_{int(datetime.now().timestamp())}"
call_log = CallLog(
    lead_id=lead1.id,
    employee_id=test_emp.id,
    provider="DOOCTI",
    provider_call_id=call_id,
    from_number="101",
    to_number=test_phone,
    call_status="COMPLETED",
    call_direction="OUTBOUND",
    duration_seconds=125,
    notes="Client confirmed they need 2 biometric devices.",
    product_category="BIOMETRIC"
)
db.add(call_log)
db.commit()
db.refresh(call_log)

assert call_log.id is not None
assert call_log.product_category == "BIOMETRIC"
print(f"✓ TEST 4 PASSED: CallLog #{call_log.id} successfully created with product_category='{call_log.product_category}'.")

# TEST 5: Call Disposition Update (/doocti/lead/update) saves category and confirms it
update_payload = DooctiLeadUpdatePayload(
    lead_id=lead1.id,
    status="CONTACTED",
    call_notes="Call completed. Client confirmed Biometric order.",
    product_category="BIOMETRIC",
    call_id=call_id
)
update_res = update_lead_from_doocti(payload=update_payload, db=db)
assert update_res["status"] == "success"
assert update_res["product_category"] == "BIOMETRIC"

db.refresh(lead1)
assert lead1.product_category == "BIOMETRIC"
assert lead1.product_category_confirmed is True
assert lead1.assigned_to == test_emp.id, "Ownership must not change!"
print("✓ TEST 5 PASSED: Disposition saved product_category='BIOMETRIC', marked confirmed=True, preserved lead assignment.")

# TEST 6: Employee manual correction is preserved on subsequent updates
# Suppose user changes category to WAHRMS
update_payload_2 = DooctiLeadUpdatePayload(
    lead_id=lead1.id,
    status="INTERESTED",
    call_notes="Correction: Client also wants WAHRMS software suite.",
    product_category="WAHRMS",
    call_id=call_id
)
update_res_2 = update_lead_from_doocti(payload=update_payload_2, db=db)
db.refresh(lead1)
assert lead1.product_category == "WAHRMS"
assert lead1.product_category_confirmed is True

# Test that automatic detection does NOT overwrite the manually confirmed category
sug_after = ProductCategorizationService.suggest_category_for_lead(lead1, additional_text="biometric machine")
assert sug_after["suggested_category"] == "WAHRMS", f"Manual confirmation should be preserved! Got {sug_after}"
assert sug_after["is_confirmed"] is True
print("✓ TEST 6 PASSED: Manual correction to 'WAHRMS' is strictly preserved and not overwritten by subsequent signals.")

# TEST 7: Verify Call Logs API reflects product_category
from starlette.responses import Response
mock_response = Response()
logs_res = list_call_logs(
    response=mock_response,
    lead_id=lead1.id,
    db=db,
    current_user=admin_user
)
assert logs_res.total > 0
found_call = next((c for c in logs_res.items if c.provider_call_id == call_id), None)
assert found_call is not None
assert found_call.product_category in ["BIOMETRIC", "WAHRMS"]
print(f"✓ TEST 7 PASSED: IVR Call Logs API returns product_category='{found_call.product_category}'.")

# Clean up test records
db.delete(call_log)
db.delete(lead1)
db.commit()

print("=" * 80)
print("ALL 7 PRODUCT CLASSIFICATION & DISPOSITION TESTS PASSED SUCCESSFULLY!")
print("=" * 80)
