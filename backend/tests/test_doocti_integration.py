import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
from models import CallLog, Lead, Employee

class TestDooctiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db = SessionLocal()

        # Seed dynamic extension mapping into database table
        from models.integration import IntegrationConfig
        import json
        cfg = cls.db.query(IntegrationConfig).filter(IntegrationConfig.integration_type == "IVR").first()
        if not cfg:
            cfg = IntegrationConfig(
                integration_type="IVR",
                provider="DOOCTI",
                name="Doocti Telephony",
                is_active=True,
                status="ACTIVE",
                webhook_url="https://www.wapluscrm.in/api/doocti/call-log"
            )
            cls.db.add(cfg)
        test_mapping = {
            "1281": {"employee_id": 1, "username": "admin", "name": "System Administrator", "role": "ADMIN", "type": "ADMIN"},
            "1282": {"employee_id": 9, "username": "chnm040", "name": "Chandra Mohan", "role": "SALES_EXECUTIVE", "type": "AGENT"},
            "1283": {"employee_id": 8, "username": "chnm030", "name": "Gowtham", "role": "SALES_MANAGER", "type": "AGENT"},
            "1286": {"employee_id": 10, "username": "chnm023", "name": "ram", "role": "SUPPORT_EXECUTIVE", "type": "AGENT"}
        }
        cfg.config_data = json.dumps({
            "provider": "DOOCTI",
            "webhook_url": "https://www.wapluscrm.in/api/doocti/call-log",
            "did_numbers": ["07969671855", "07969671856", "07969671857"],
            "admin_extension": "1281",
            "agent_extensions": ["1282", "1283", "1286"],
            "extension_mapping": test_mapping
        })
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def tearDown(self):
        # Cleanup any test call logs created during tests
        test_logs = self.db.query(CallLog).filter(CallLog.provider_call_id.like("test_doocti_%")).all()
        for log in test_logs:
            self.db.delete(log)
        self.db.commit()

    def test_call_statuses_endpoint(self):
        response = self.client.get("/api/doocti/call-statuses")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        status_codes = [s["code"] for s in data["statuses"]]
        self.assertIn("ANSWERED", status_codes)
        self.assertIn("MISSED", status_codes)
        self.assertIn("BUSY", status_codes)

    def test_lead_statuses_endpoint(self):
        response = self.client.get("/api/doocti/lead-statuses")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        codes = [s["code"] for s in data["statuses"]]
        self.assertIn("NEW", codes)
        self.assertIn("CONTACTED", codes)

    def test_call_log_json_post(self):
        call_id = "test_doocti_json_001"
        payload = {
            "uniqueid": call_id,
            "phone_number": "919876543299",
            "start_time": "2026-10-22 10:00:00",
            "station": "1282",
            "agent": "chntechnolog_agent01",
            "status": "ANSWERED",
            "end_time": "2026-10-22 10:02:00",
            "duration": 120,
            "recording_path": "https://storage.oracle.com/doocti/rec_001.mp3"
        }
        response = self.client.post("/api/doocti/call-log", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["uniqueid"], call_id)
        self.assertEqual(data["call_status"], "ANSWERED")
        self.assertEqual(data["duration"], 120)

        # Verify DB
        log = self.db.query(CallLog).filter(CallLog.provider_call_id == call_id).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.duration_seconds, 120)
        self.assertEqual(log.call_status, "ANSWERED")

    def test_call_log_form_post(self):
        call_id = "test_doocti_form_002"
        form_data = {
            "uniqueid": call_id,
            "phone_number": "9876543298",
            "duration": "75",
            "status": "COMPLETED",
            "station": "1282"
        }
        response = self.client.post("/api/doocti/call-log", data=form_data)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["uniqueid"], call_id)

    def test_call_log_get_query(self):
        call_id = "test_doocti_query_003"
        url = f"/api/doocti/call-log?uniqueid={call_id}&phone_number=9876543297&duration=40&status=ANSWERED&station=1282"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["uniqueid"], call_id)

    def test_delayed_recording_update_idempotency(self):
        call_id = "test_doocti_rec_004"
        # 1. First event: Call completed without recording
        init_res = self.client.post("/api/doocti/call-log", json={
            "uniqueid": call_id,
            "phone_number": "9876543296",
            "station": "1282",
            "status": "ANSWERED",
            "duration": 95
        })
        self.assertEqual(init_res.status_code, 200)

        # 2. Second event: Recording ready pushed subsequently
        rec_url = "https://storage.oracle.com/doocti/rec_004.mp3"
        rec_res = self.client.post("/api/doocti/call-log", json={
            "uniqueid": call_id,
            "recording_path": rec_url
        })
        self.assertEqual(rec_res.status_code, 200)
        data = rec_res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["recording_path"], rec_url)

        # Verify DB preserved duration and status while updating recording URL
        log = self.db.query(CallLog).filter(CallLog.provider_call_id == call_id).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.call_status, "ANSWERED")
        self.assertEqual(log.duration_seconds, 95)
        self.assertEqual(log.recording_url, rec_url)

    def test_ghost_call_rejection(self):
        # Self-extension dialing should be rejected
        for ext in ["1281", "1282", "1283", "1286"]:
            response = self.client.post("/api/doocti/call-log", json={
                "uniqueid": f"test_doocti_ghost_{ext}",
                "phone_number": ext,
                "station": ext,
                "status": "ANSWERED"
            })
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "ignored")
            self.assertIn("Ghost call rejected", data["message"])

    def test_get_config_endpoint(self):
        response = self.client.get("/api/doocti/config")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["admin_extension"], "1281")
        self.assertIn("07969671855", data["did_numbers"])
        self.assertIn("07969671856", data["did_numbers"])
        self.assertIn("07969671857", data["did_numbers"])
        self.assertIn("1282", data["agent_extensions"])
        self.assertIn("1283", data["agent_extensions"])
        self.assertIn("1286", data["agent_extensions"])
        # Extension mapping checks
        mapping = data.get("extension_mapping", {})
        self.assertEqual(mapping.get("1281", {}).get("employee_id"), 1)
        self.assertEqual(mapping.get("1282", {}).get("employee_id"), 9)
        self.assertEqual(mapping.get("1283", {}).get("employee_id"), 8)
        self.assertEqual(mapping.get("1286", {}).get("employee_id"), 10)

    def test_extension_1281_admin_mapping(self):
        call_id = "test_doocti_admin_1281"
        payload = {
            "uniqueid": call_id,
            "phone_number": "9876543210",
            "station": "1281",
            "status": "ANSWERED",
            "duration": 60,
            "call_direction": "OUTBOUND"
        }
        res = self.client.post("/api/doocti/call-log", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["employee_id"], 1)

        log = self.db.query(CallLog).filter(CallLog.provider_call_id == call_id).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.employee_id, 1)

    def test_extension_1282_sales_exec_mapping(self):
        call_id = "test_doocti_agent_1282"
        payload = {
            "uniqueid": call_id,
            "phone_number": "9876543211",
            "station": "1282",
            "status": "ANSWERED",
            "duration": 45,
            "call_direction": "OUTBOUND"
        }
        res = self.client.post("/api/doocti/call-log", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["employee_id"], 9)

        log = self.db.query(CallLog).filter(CallLog.provider_call_id == call_id).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.employee_id, 9)

    def test_extension_1283_sales_manager_mapping(self):
        call_id = "test_doocti_agent_1283"
        payload = {
            "uniqueid": call_id,
            "phone_number": "9876543212",
            "station": "1283",
            "status": "ANSWERED",
            "duration": 80,
            "call_direction": "OUTBOUND"
        }
        res = self.client.post("/api/doocti/call-log", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["employee_id"], 8)

        log = self.db.query(CallLog).filter(CallLog.provider_call_id == call_id).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.employee_id, 8)

    def test_extension_1286_support_exec_mapping(self):
        call_id = "test_doocti_agent_1286"
        payload = {
            "uniqueid": call_id,
            "phone_number": "9876543213",
            "station": "1286",
            "status": "ANSWERED",
            "duration": 110,
            "call_direction": "OUTBOUND"
        }
        res = self.client.post("/api/doocti/call-log", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["employee_id"], 10)

        log = self.db.query(CallLog).filter(CallLog.provider_call_id == call_id).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.employee_id, 10)

    def test_inbound_call_did_routing(self):
        call_id = "test_doocti_inbound_did_001"
        payload = {
            "uniqueid": call_id,
            "phone_number": "9876543214",
            "destination": "07969671855",
            "station": "1282",
            "status": "ANSWERED",
            "duration": 50
        }
        res = self.client.post("/api/doocti/call-log", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")

        log = self.db.query(CallLog).filter(CallLog.provider_call_id == call_id).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.call_direction, "INBOUND")
        self.assertEqual(log.to_number, "07969671855")
        self.assertEqual(log.employee_id, 9)

    def test_dynamic_update_from_admin_page(self):
        # Verify Admin can change extension mappings dynamically via PUT /api/doocti/config
        new_map = {
            "1299": {
                "employee_id": 8,
                "username": "chnm030",
                "name": "Gowtham",
                "role": "SALES_MANAGER",
                "type": "AGENT"
            }
        }
        put_res = self.client.put("/api/doocti/config", json={"extension_mapping": new_map})
        self.assertEqual(put_res.status_code, 200)

        # Call with newly mapped extension 1299
        call_id = "test_doocti_dynamic_1299"
        res = self.client.post("/api/doocti/call-log", json={
            "uniqueid": call_id,
            "phone_number": "9876543290",
            "station": "1299",
            "status": "ANSWERED",
            "duration": 30
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["employee_id"], 8)

        # Restore test setup mapping
        test_mapping = {
            "1281": {"employee_id": 1, "username": "admin", "name": "System Administrator", "role": "ADMIN", "type": "ADMIN"},
            "1282": {"employee_id": 9, "username": "chnm040", "name": "Chandra Mohan", "role": "SALES_EXECUTIVE", "type": "AGENT"},
            "1283": {"employee_id": 8, "username": "chnm030", "name": "Gowtham", "role": "SALES_MANAGER", "type": "AGENT"},
            "1286": {"employee_id": 10, "username": "chnm023", "name": "ram", "role": "SUPPORT_EXECUTIVE", "type": "AGENT"}
        }
        self.client.put("/api/doocti/config", json={"extension_mapping": test_mapping})

    def test_answered_call_not_overwritten_by_late_no_answer(self):
        # Verify that an answered outbound call with duration > 0 is NOT overwritten by a late NO ANSWER webhook
        call_id = "test_doocti_answered_protect_001"
        res1 = self.client.post("/api/doocti/call-log", json={
            "uniqueid": call_id,
            "phone_number": "9876543211",
            "station": "1282",
            "status": "ANSWERED",
            "duration": 54,
            "recording_path": "https://storage.oracle.com/doocti/rec_54s.mp3"
        })
        self.assertEqual(res1.status_code, 200)

        # Subsequent delayed/duplicate Asterisk event arrives with NO ANSWER
        res2 = self.client.post("/api/doocti/call-log", json={
            "uniqueid": call_id,
            "phone_number": "9876543211",
            "station": "1282",
            "status": "NO ANSWER",
            "duration": 0
        })
        self.assertEqual(res2.status_code, 200)

        # Database record must preserve COMPLETED/ANSWERED and duration 54s
        log = self.db.query(CallLog).filter(CallLog.provider_call_id == call_id).first()
        self.assertIsNotNone(log)
        self.assertIn(log.call_status, ["ANSWERED", "COMPLETED"])
        self.assertNotEqual(log.call_status, "NO_ANSWER")
        self.assertNotEqual(log.call_status, "NO ANSWER")
        self.assertEqual(log.duration_seconds, 54)
        self.assertIsNotNone(log.recording_url)

    def test_call_with_recording_is_never_classified_as_no_answer(self):
        # A call payload having recording_url or duration > 0 must not be classified as NO_ANSWER even if status string says NO ANSWER
        call_id = "test_doocti_rec_protect_002"
        res = self.client.post("/api/doocti/call-log", json={
            "uniqueid": call_id,
            "phone_number": "9876543212",
            "station": "1282",
            "status": "NO ANSWER",
            "duration": 22,
            "recording_path": "https://storage.oracle.com/doocti/rec_22s.mp3"
        })
        self.assertEqual(res.status_code, 200)

        log = self.db.query(CallLog).filter(CallLog.provider_call_id == call_id).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.call_status, "COMPLETED")
        self.assertEqual(log.duration_seconds, 22)

    def test_doocti_status_complete_maps_to_completed(self):
        # DooCTI CDR portal sends status as "COMPLETE" (without trailing D)
        call_id = "test_doocti_complete_status_003"
        res = self.client.post("/api/doocti/call-log", json={
            "uniqueid": call_id,
            "phone_number": "9876543213",
            "station": "1283",
            "status": "COMPLETE",
            "agent_email": "itsales@chnindia.com",
            "did": "7969671856"
        })
        self.assertEqual(res.status_code, 200)

        log = self.db.query(CallLog).filter(CallLog.provider_call_id == call_id).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.call_status, "COMPLETED")

if __name__ == "__main__":
    unittest.main()
