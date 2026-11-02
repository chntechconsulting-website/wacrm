import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import settings
from database import Base, get_db
from main import app
from models import (  # noqa: F401 - imported so create_all sees every table
    Base as _Base,
    Customer,
    Employee,
    FieldVisit,
    Lead,
    LeadActivity,
    LeadAssignment,
    LeadEnquiry,
    LeadStatusHistory,
)
from models.monitoring import EmployeeActivityLog
from services.auth import get_current_user


class FieldVisitUploadAndLeadTest(unittest.TestCase):
    """Covers photo uploads and automatic lead creation/linking for field visits."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.old_upload_dir = settings.UPLOAD_DIR
        settings.UPLOAD_DIR = cls.temp_dir.name

        db_path = os.path.join(cls.temp_dir.name, "field_visit_test.db")
        cls.engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

        def override_db():
            db = cls.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id=1, role="SALES_EXECUTIVE", username="agent", employee_id=1
        )
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        settings.UPLOAD_DIR = cls.old_upload_dir
        cls.engine.dispose()
        cls.temp_dir.cleanup()

    def setUp(self):
        db = self.Session()
        for model in (
            FieldVisit,
            LeadActivity,
            LeadEnquiry,
            LeadAssignment,
            LeadStatusHistory,
            Lead,
            EmployeeActivityLog,
            Customer,
            Employee,
        ):
            db.query(model).delete()
        db.add(
            Employee(
                id=1,
                user_id=1,
                name="Field Agent",
                email="agent@example.com",
                username="agent",
                phone="+919876500000",
            )
        )
        db.commit()
        db.close()

    # ---------------------------------------------------------------- helpers
    def _submit(self, **overrides):
        payload = {
            "client_token": "visit-test-token",
            "customer_name": "Acme Industries",
            "checkin_lat": "12.971599",
            "checkin_lng": "77.594566",
            "checkin_address": "MG Road, Bengaluru",
            "checkin_accuracy_m": 8.5,
            "gps_captured_at": "2026-05-01T10:15:00",
            "visit_outcome": "Interested",
            "customer_requirements": "Needs 20 units",
            "notes": "Met the purchase manager",
        }
        payload.update(overrides)
        return self.client.post("/api/field-visits", json=payload)

    def _lead_count(self):
        db = self.Session()
        try:
            return db.query(Lead).count()
        finally:
            db.close()

    # ------------------------------------------------------------------ tests
    def test_upload_rejects_non_image(self):
        response = self.client.post(
            "/api/field-visits/uploads",
            data={"kind": "company_board"},
            files={"file": ("note.txt", b"not an image", "text/plain")},
        )
        self.assertEqual(response.status_code, 422, response.text)

    def test_upload_rejects_invalid_kind(self):
        response = self.client.post(
            "/api/field-visits/uploads",
            data={"kind": "selfie"},
            files={"file": ("board.jpg", b"\xff\xd8\xff\xe0fake", "image/jpeg")},
        )
        self.assertEqual(response.status_code, 422, response.text)

    def test_upload_rejects_oversized_image(self):
        with patch("routers.field_visits._MAX_IMAGE_BYTES", 1024):
            response = self.client.post(
                "/api/field-visits/uploads",
                data={"kind": "visiting_card"},
                files={
                    "file": (
                        "card.png",
                        b"\x89PNG\r\n\x1a\n" + b"x" * 2048,
                        "image/png",
                    ),
                },
            )
        self.assertEqual(response.status_code, 413, response.text)

    def test_upload_rejects_spoofed_image_content(self):
        response = self.client.post(
            "/api/field-visits/uploads",
            data={"kind": "company_board"},
            files={"file": ("fake.jpg", b"not really a jpeg", "image/jpeg")},
        )
        self.assertEqual(response.status_code, 422, response.text)

    def test_upload_stores_file_without_exposing_device_path(self):
        response = self.client.post(
            "/api/field-visits/uploads",
            data={"kind": "company_board"},
            files={"file": ("board.jpg", b"\xff\xd8\xff\xe0fake-image", "image/jpeg")},
        )
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertTrue(body["url"].startswith("/uploads/field_visits/1/"), body["url"])
        self.assertTrue(body["url"].endswith(".jpg"))
        self.assertEqual(body["kind"], "company_board")
        stored = body["url"].replace("/uploads/", "")
        target = os.path.join(settings.UPLOAD_DIR, *stored.split("/"))
        self.assertTrue(os.path.exists(target), target)

    def test_submission_rejects_device_local_image_path(self):
        response = self._submit(company_board_photo="file:///data/user/0/cache/board.jpg")
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self._lead_count(), 0)

    def test_new_lead_is_created_and_linked_to_visit(self):
        response = self._submit(
            create_new_lead=True,
            new_lead={
                "name": "Ramesh Kumar",
                "phone": "+91 98765 43210",
                "company": "Ramesh Traders",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertTrue(body["lead_created"])
        self.assertFalse(body["lead_matched_existing"])
        lead_id = body["lead_id"]
        self.assertIsNotNone(lead_id)
        self.assertEqual(body["checkin_accuracy_m"], 8.5)

        db = self.Session()
        try:
            lead = db.query(Lead).filter(Lead.id == lead_id).first()
            self.assertIsNotNone(lead)
            self.assertEqual(lead.name, "Ramesh Kumar")
            self.assertEqual(lead.source, "FIELD_VISIT")
            self.assertEqual(lead.assigned_to, 1)
            self.assertEqual(lead.requirement_notes, "Needs 20 units")
            visit = db.query(FieldVisit).filter(FieldVisit.id == body["id"]).first()
            self.assertEqual(visit.lead_id, lead_id)
            self.assertEqual(visit.checkin_accuracy_m, 8.5)
        finally:
            db.close()

        # The new lead must appear on the CRM Leads page immediately.
        leads_response = self.client.get(
            "/api/leads", params={"search": "Ramesh", "limit": 10}
        )
        self.assertEqual(leads_response.status_code, 200, leads_response.text)
        lead_ids = [item["id"] for item in leads_response.json()["items"]]
        self.assertIn(lead_id, lead_ids)

        # Web CRM reads the same visit row, so the GPS/photo metadata matches.
        web_response = self.client.get("/api/employee-monitoring/field-visits")
        self.assertEqual(web_response.status_code, 200, web_response.text)
        web_visit = next(
            v for v in web_response.json() if v["id"] == body["id"]
        )
        self.assertEqual(web_visit["checkin_accuracy_m"], 8.5)
        self.assertEqual(web_visit["checkin_address"], "MG Road, Bengaluru")
        self.assertEqual(web_visit["visit_outcome"], "Interested")

    def test_duplicate_phone_links_existing_lead_instead_of_creating_one(self):
        db = self.Session()
        existing = Lead(
            name="Ramesh Kumar",
            phone="+91 98765 43210",
            source="MANUAL",
            status="NEW",
        )
        db.add(existing)
        db.commit()
        db.refresh(existing)
        existing_id = existing.id
        db.close()

        response = self._submit(
            client_token="visit-duplicate-phone",
            create_new_lead=True,
            new_lead={
                "name": "Ramesh Kumar",
                "phone": "9876543210",
                "company": "Ramesh Traders",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertFalse(body["lead_created"])
        self.assertTrue(body["lead_matched_existing"])
        self.assertEqual(body["lead_id"], existing_id)
        self.assertEqual(self._lead_count(), 1)

    def test_existing_lead_visit_does_not_create_a_lead(self):
        db = self.Session()
        existing = Lead(name="Existing Co", phone="+919876543211", source="MANUAL")
        db.add(existing)
        db.commit()
        db.refresh(existing)
        existing_id = existing.id
        db.close()

        response = self._submit(
            client_token="visit-existing-lead",
            lead_id=existing_id,
            customer_name="Existing Co",
            create_new_lead=False,
        )
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertFalse(body["lead_created"])
        self.assertEqual(body["lead_id"], existing_id)
        self.assertEqual(self._lead_count(), 1)

    def test_client_token_is_idempotent(self):
        first = self._submit(
            client_token="visit-idempotent",
            create_new_lead=True,
            new_lead={
                "name": "Idempotent Customer",
                "phone": "+919876543212",
                "company": "Idem Ltd",
            },
        )
        second = self._submit(
            client_token="visit-idempotent",
            create_new_lead=True,
            new_lead={
                "name": "Idempotent Customer",
                "phone": "+919876543212",
                "company": "Idem Ltd",
            },
        )
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(second.status_code, 201, second.text)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(self._lead_count(), 1)

        db = self.Session()
        try:
            self.assertEqual(db.query(FieldVisit).count(), 1)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
