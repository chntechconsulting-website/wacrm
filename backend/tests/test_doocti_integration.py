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
        response = self.client.post("/api/doocti/call-log", json={
            "uniqueid": "test_doocti_ghost_005",
            "phone_number": "1282",
            "station": "1282",
            "status": "ANSWERED"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ignored")
        self.assertIn("Ghost call rejected", data["message"])

if __name__ == "__main__":
    unittest.main()
