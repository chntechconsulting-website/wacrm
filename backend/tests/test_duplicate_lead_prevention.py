import sys
import unittest
import datetime
sys.path.append('backend')

from database import SessionLocal
from models import Lead, CallLog, Employee, Customer, LeadActivity
from models.lead import LeadAssignment
from sqlalchemy import or_
from routers.doocti import push_doocti_call_log, get_lead_by_number
from integrations.ivr.webhook import handle_incoming_ivr_webhook
from utils.phone import normalize_phone, find_existing_lead_by_phone, find_existing_customer_by_phone
from starlette.requests import Request

class MockRequest:
    def __init__(self, data=None, method="POST", client_host="127.0.0.1", headers=None):
        self._data = data or {}
        self.method = method
        self.client = type("Client", (), {"host": client_host})
        self.headers = headers or {"content-type": "application/json"}
        self.query_params = {}

    async def json(self):
        return self._data

    async def form(self):
        return self._data

class TestDuplicateLeadPrevention(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        # Clean any preexisting test records
        self.cleanup()

    def tearDown(self):
        self.cleanup()
        self.db.close()

    def cleanup(self):
        lead_ids = [
            l.id for l in self.db.query(Lead).filter(
                Lead.phone.in_([
                    "9500589185", "+91 9500589185", "+91 95005 89185", "+919500589185", "09500589185",
                    "9876500001", "+919876500001",
                    "9876500002", "+919876500002",
                    "9876500003", "+919876500003"
                ])
            ).all()
        ]
        self.db.query(CallLog).filter(
            or_(
                CallLog.provider_call_id.like("test_%"),
                CallLog.lead_id.in_(lead_ids) if lead_ids else False
            )
        ).delete(synchronize_session=False)

        if lead_ids:
            self.db.query(LeadAssignment).filter(LeadAssignment.lead_id.in_(lead_ids)).delete(synchronize_session=False)
            self.db.query(LeadActivity).filter(LeadActivity.lead_id.in_(lead_ids)).delete(synchronize_session=False)
            self.db.query(Lead).filter(Lead.id.in_(lead_ids)).delete(synchronize_session=False)
        self.db.commit()

    def test_outbound_call_to_existing_lead_never_duplicates(self):
        """
        Scenario from user report:
        Existing Lead #35 (Salem Ranjini, 9500589185).
        Agent calls lead and disconnects (or finishes call).
        Verify that NO new lead (#36 Call Lead) is created, and the call is linked to the existing lead.
        """
        # Create existing lead with spaced phone number
        lead = Lead(
            name="Salem Ranjini",
            phone="+91 95005 89185",
            source="MANUAL",
            status="NEW"
        )
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        original_lead_id = lead.id

        # Webhook event for outbound call disconnect from DooCTI
        call_id = f"test_outbound_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        req = MockRequest({
            "uniqueid": call_id,
            "direction": "OUTBOUND",
            "caller": "1282",
            "destination": "9500589185",
            "status": "COMPLETED",
            "duration": 45,
            "agent": "System Administrator",
            "station": "1282"
        })

        import asyncio
        res = asyncio.run(push_doocti_call_log(req, self.db))
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["lead_id"], original_lead_id)

        # Check total leads matching this phone
        matching_leads = [
            l for l in self.db.query(Lead).all()
            if normalize_phone(l.phone) == "9500589185"
        ]
        self.assertEqual(len(matching_leads), 1, "Expected exactly 1 lead, no duplicate lead created!")
        self.assertEqual(matching_leads[0].id, original_lead_id)

        # Verify call log is linked to original lead
        call_log = self.db.query(CallLog).filter(CallLog.provider_call_id == call_id).first()
        self.assertIsNotNone(call_log)
        self.assertEqual(call_log.lead_id, original_lead_id)
        self.assertEqual(call_log.call_status, "COMPLETED")
        self.assertEqual(call_log.duration_seconds, 45)

    def test_outbound_call_to_new_number_creates_lead_assigned_to_agent(self):
        """
        When an agent calls a new phone number that does not exist in CRM:
        1. Automatically create a new lead.
        2. Assign lead to calling agent (assigned_to = agent employee ID, not Admin).
        3. Set source to 'DOOCTI' and status to 'NEW LEAD'.
        4. When the call ends, update existing call record without creating another lead.
        """
        # Station 1282 maps to Chandra Mohan (emp_id 9)
        call_id = f"test_outbound_new_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        req1 = MockRequest({
            "uniqueid": call_id,
            "direction": "OUTBOUND",
            "caller": "1282",
            "destination": "9876500002",
            "status": "ANSWERED",
            "duration": 20,
            "station": "1282",
            "agent": "Chandra Mohan",
            "employee_id": 9
        })

        import asyncio
        res1 = asyncio.run(push_doocti_call_log(req1, self.db))
        self.assertEqual(res1["status"], "success")
        new_lead_id = res1["lead_id"]
        self.assertIsNotNone(new_lead_id)
        self.assertEqual(res1["employee_id"], 9)

        # Verify created lead in database
        lead = self.db.query(Lead).filter(Lead.id == new_lead_id).first()
        self.assertIsNotNone(lead)
        self.assertEqual(lead.assigned_to, 9)
        self.assertEqual(lead.source, "DOOCTI")
        self.assertEqual(lead.status, "NEW LEAD")

        # Verify assignment record exists
        asgn = self.db.query(LeadAssignment).filter(LeadAssignment.lead_id == new_lead_id).first()
        self.assertIsNotNone(asgn)
        self.assertEqual(asgn.assigned_to, 9)
        self.assertEqual(asgn.assignment_method, "OUTBOUND_CALL")

        # Now simulate call hangup / disconnect webhook
        req2 = MockRequest({
            "uniqueid": call_id,
            "direction": "OUTBOUND",
            "caller": "1282",
            "destination": "9876500002",
            "status": "COMPLETED",
            "duration": 55,
            "station": "1282",
            "agent": "Chandra Mohan",
            "employee_id": 9
        })
        res2 = asyncio.run(push_doocti_call_log(req2, self.db))
        self.assertEqual(res2["status"], "success")
        self.assertEqual(res2["lead_id"], new_lead_id)
        self.assertEqual(res2["call_log_id"], res1["call_log_id"])

        # Verify NO duplicate lead was created
        matching_leads = [
            l for l in self.db.query(Lead).all()
            if normalize_phone(l.phone) == "9876500002"
        ]
        self.assertEqual(len(matching_leads), 1)

    def test_outbound_call_agent_b_assigned_to_agent_b(self):
        """
        Verify that Agent B (Gowtham, emp_id 8, station 1283) calling a different new number
        gets assigned to Agent B (8), not Admin (1).
        """
        call_id = f"test_outbound_agent_b_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        req = MockRequest({
            "uniqueid": call_id,
            "direction": "OUTBOUND",
            "caller": "1283",
            "destination": "9876500003",
            "status": "ANSWERED",
            "duration": 15,
            "station": "1283",
            "agent": "Gowtham",
            "employee_id": 8
        })

        import asyncio
        res = asyncio.run(push_doocti_call_log(req, self.db))
        self.assertEqual(res["status"], "success")
        new_lead_id = res["lead_id"]
        self.assertIsNotNone(new_lead_id)
        self.assertEqual(res["employee_id"], 8)

        lead = self.db.query(Lead).filter(Lead.id == new_lead_id).first()
        self.assertIsNotNone(lead)
        self.assertEqual(lead.assigned_to, 8)
        self.assertNotEqual(lead.assigned_to, 1, "Must NOT be assigned to Admin (1)!")
        self.assertEqual(lead.source, "DOOCTI")
        self.assertEqual(lead.status, "NEW LEAD")

    def test_unresolved_agent_identity_does_not_assign_to_admin(self):
        """
        If agent identity cannot be determined, do not assign to Admin (1).
        """
        call_id = f"test_outbound_unresolved_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        req = MockRequest({
            "uniqueid": call_id,
            "direction": "OUTBOUND",
            "caller": "unknown_station_9999",
            "destination": "9876500001",
            "status": "COMPLETED",
            "duration": 10,
            "station": "9999",
            "employee_id": None
        })

        import asyncio
        res = asyncio.run(push_doocti_call_log(req, self.db))
        self.assertEqual(res["status"], "success")
        self.assertIsNone(res["employee_id"])

        new_lead_id = res["lead_id"]
        if new_lead_id:
            lead = self.db.query(Lead).filter(Lead.id == new_lead_id).first()
            self.assertIsNone(lead.assigned_to, "Must remain unassigned, NOT assigned to Admin (1)!")

    def test_call_lifecycle_webhook_updates_single_record(self):
        """
        Test call lifecycle: RINGING -> ANSWERED -> COMPLETED updates single call log
        without creating duplicate calls or duplicate leads.
        """
        call_id = f"test_lifecycle_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        import asyncio

        # 1. Ringing event
        req1 = MockRequest({
            "uniqueid": call_id,
            "direction": "INBOUND",
            "caller": "9500589185",
            "destination": "1282",
            "status": "RINGING",
            "duration": 0,
            "station": "1282"
        })
        res1 = asyncio.run(push_doocti_call_log(req1, self.db))
        self.assertEqual(res1["status"], "success")
        lead_id = res1["lead_id"]
        self.assertIsNotNone(lead_id)

        # 2. Answered event
        req2 = MockRequest({
            "uniqueid": call_id,
            "direction": "INBOUND",
            "caller": "9500589185",
            "destination": "1282",
            "status": "ANSWERED",
            "duration": 5,
            "station": "1282"
        })
        res2 = asyncio.run(push_doocti_call_log(req2, self.db))
        self.assertEqual(res2["status"], "success")
        self.assertEqual(res2["lead_id"], lead_id)
        self.assertEqual(res2["call_log_id"], res1["call_log_id"])

        # 3. Completed event
        req3 = MockRequest({
            "uniqueid": call_id,
            "direction": "INBOUND",
            "caller": "9500589185",
            "destination": "1282",
            "status": "COMPLETED",
            "duration": 30,
            "recording_path": "https://example.com/rec.mp3",
            "station": "1282"
        })
        res3 = asyncio.run(push_doocti_call_log(req3, self.db))
        self.assertEqual(res3["status"], "success")
        self.assertEqual(res3["lead_id"], lead_id)
        self.assertEqual(res3["call_log_id"], res1["call_log_id"])

        # Verify exactly 1 call log exists for this call_id
        logs = self.db.query(CallLog).filter(CallLog.provider_call_id == call_id).all()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].call_status, "COMPLETED")
        self.assertEqual(logs[0].duration_seconds, 30)
        self.assertEqual(logs[0].recording_url, "https://example.com/rec.mp3")

        # Verify exactly 1 lead exists
        matching_leads = [
            l for l in self.db.query(Lead).all()
            if normalize_phone(l.phone) == "9500589185"
        ]
        self.assertEqual(len(matching_leads), 1)

    def test_ivr_webhook_lifecycle_and_deduplication(self):
        """
        Test general IVR webhook (handle_incoming_ivr_webhook) handles lifecycle and
        matches existing leads via normalized phone without duplicating.
        """
        # Create lead
        lead = Lead(
            name="Salem Ranjini",
            phone="+91 95005 89185",
            source="MANUAL",
            status="NEW"
        )
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)

        call_id = f"test_ivr_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        payload = {
            "uuid": call_id,
            "direction": "INBOUND",
            "from": "9500589185",
            "to": "09513886363",
            "call_status": "ANSWERED",
            "duration": 20
        }
        res = handle_incoming_ivr_webhook(self.db, payload, {})
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["lead_id"], lead.id)

        # Retry webhook with completed status
        payload["call_status"] = "COMPLETED"
        payload["duration"] = 25
        res2 = handle_incoming_ivr_webhook(self.db, payload, {})
        self.assertEqual(res2["status"], "success")
        self.assertEqual(res2["action"], "UPDATED")
        self.assertEqual(res2["lead_id"], lead.id)

        # Verify only 1 lead exists
        matching_leads = [
            l for l in self.db.query(Lead).all()
            if normalize_phone(l.phone) == "9500589185"
        ]
        self.assertEqual(len(matching_leads), 1)

if __name__ == "__main__":
    unittest.main()
