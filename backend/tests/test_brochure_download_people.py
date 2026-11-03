"""Isolated tests for the dedicated Brochure Download People module.

These tests use an in-memory SQLite database and never touch the live CRM data.
They exercise the real public website form endpoint, brochure-only isolation,
deduplication, search/filters/pagination, follow-up updates, summary KPIs and
the Excel export.
"""

import io
import os
import sys
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import openpyxl
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401 - registers every model on Base.metadata
from database import Base, get_db
from integrations.website.router import router as website_router
from integrations.website.schemas import WebsiteLeadRequest
from models.brochure_enquiry import BrochureEnquiry
from models.employee import Employee
from models.lead import Lead
from routers.brochure_enquiries import router as brochure_router
from services.auth import get_current_user
from services.brochure_enquiry_service import is_brochure_submission


class BrochureDownloadPeopleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=cls.engine)
        cls.Session = sessionmaker(bind=cls.engine, autoflush=False, autocommit=False)

        def override_db():
            db = cls.Session()
            try:
                yield db
            finally:
                db.close()

        cls.admin = SimpleNamespace(
            id=1,
            role="ADMIN",
            username="admin",
            is_active=True,
        )

        cls.app = FastAPI()
        cls.app.include_router(website_router, prefix="/api")
        cls.app.include_router(brochure_router, prefix="/api")
        cls.app.dependency_overrides[get_db] = override_db
        cls.app.dependency_overrides[get_current_user] = lambda: cls.admin
        cls.client = TestClient(cls.app)

    def setUp(self):
        db = self.Session()
        try:
            db.query(BrochureEnquiry).delete()
            db.query(Lead).delete()
            db.query(Employee).delete()
            db.commit()
        finally:
            db.close()

    @staticmethod
    def brochure_payload(**overrides):
        payload = {
            "name": "Arun Kumar",
            "phone": "9876543210",
            "countryCode": "91",
            "email": "arun@example.com",
            "product_name": "HRMS",
            "brochure_name": "HRMS Product Brochure",
            "product_id": "prod-hrms",
            "brochure_id": "brochure-hrms-2026",
            "website_id": "wapluscrm",
            "website_name": "WA Plus CRM",
            "landing_page": "https://www.wapluscrm.in/hrms",
            "campaign": "HRMS Brochure Download",
            "form_type": "brochure_download",
        }
        payload.update(overrides)
        return payload

    def test_normal_contact_payload_is_not_classified_as_brochure(self):
        normal = WebsiteLeadRequest(name="Normal Lead", phone="9876543210", message="Please contact me")
        self.assertFalse(is_brochure_submission(normal))

        explicit_type = WebsiteLeadRequest(name="Brochure Lead", phone="9876543210", form_type="brochure_download")
        self.assertTrue(is_brochure_submission(explicit_type))

        explicit_name = WebsiteLeadRequest(name="Brochure Lead", phone="9876543210", brochure_name="HRMS Brochure")
        self.assertTrue(is_brochure_submission(explicit_name))

    def test_public_brochure_form_creates_dedicated_record_with_details(self):
        response = self.client.post("/api/integrations/website/brochures", json=self.brochure_payload())
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["record_type"], "BROCHURE_ENQUIRY")
        self.assertFalse(body["is_duplicate"])
        self.assertIsNotNone(body["enquiry_id"])

        db = self.Session()
        try:
            record = db.query(BrochureEnquiry).one()
            self.assertEqual(record.name, "Arun Kumar")
            self.assertEqual(record.phone, "+91 9876543210")
            self.assertEqual(record.whatsapp_number, "+91 9876543210")
            self.assertEqual(record.country_code, "+91")
            self.assertEqual(record.email, "arun@example.com")
            self.assertEqual(record.product_name, "HRMS")
            self.assertEqual(record.brochure_name, "HRMS Product Brochure")
            self.assertEqual(record.brochure_id, "brochure-hrms-2026")
            self.assertEqual(record.website_name, "WA Plus CRM")
            self.assertEqual(record.campaign, "HRMS Brochure Download")
            self.assertEqual(record.source, "WEBSITE_BROCHURE")
            self.assertEqual(record.followup_status, "PENDING")
            self.assertIsNotNone(record.download_at)
            self.assertEqual(db.query(Lead).count(), 0)
        finally:
            db.close()

    def test_repeated_submission_updates_instead_of_duplicating(self):
        first = self.client.post("/api/integrations/website/brochures", json=self.brochure_payload())
        self.assertEqual(first.status_code, 201)
        enquiry_id = first.json()["enquiry_id"]

        db = self.Session()
        try:
            record = db.query(BrochureEnquiry).filter(BrochureEnquiry.id == enquiry_id).one()
            record.followup_status = "CONTACTED"
            record.notes = "Customer asked for a callback."
            db.commit()
        finally:
            db.close()

        repeated = self.client.post(
            "/api/integrations/website/brochures",
            json=self.brochure_payload(
                phone="98765 43210",
                countryCode="+91",
                email="arun.kumar@example.com",
            ),
        )
        self.assertEqual(repeated.status_code, 201, repeated.text)
        body = repeated.json()
        self.assertTrue(body["is_duplicate"])
        self.assertEqual(body["enquiry_id"], enquiry_id)
        self.assertEqual(body["submission_count"], 2)

        db = self.Session()
        try:
            self.assertEqual(db.query(BrochureEnquiry).count(), 1)
            record = db.query(BrochureEnquiry).one()
            self.assertEqual(record.submission_count, 2)
            self.assertEqual(record.followup_status, "CONTACTED")
            self.assertEqual(record.notes, "Customer asked for a callback.")
            self.assertEqual(record.email, "arun.kumar@example.com")
        finally:
            db.close()

    def test_brochure_marker_on_leads_endpoint_does_not_create_lead(self):
        response = self.client.post(
            "/api/integrations/website/leads",
            json=self.brochure_payload(enquiry_type="brochure_download"),
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["record_type"], "BROCHURE_ENQUIRY")

        db = self.Session()
        try:
            self.assertEqual(db.query(BrochureEnquiry).count(), 1)
            self.assertEqual(db.query(Lead).count(), 0)
        finally:
            db.close()

    def _seed_records(self):
        db = self.Session()
        try:
            manager = Employee(
                name="Sales Manager",
                email="sales.manager@example.com",
                username="sales.manager",
                role="SALES_MANAGER",
                department="SALES",
                status="ACTIVE",
            )
            executive = Employee(
                name="Sales Executive",
                email="sales.executive@example.com",
                username="sales.executive",
                role="SALES_EXECUTIVE",
                department="SALES",
                status="ACTIVE",
            )
            db.add_all([manager, executive])
            db.commit()
            db.refresh(manager)
            db.refresh(executive)

            now = datetime(2026, 11, 3, 10, 30, 0)
            records = [
                BrochureEnquiry(
                    name="Arun Kumar",
                    phone="+91 9876543210",
                    whatsapp_number="+91 9876543210",
                    country_code="+91",
                    email="arun@example.com",
                    product_name="HRMS",
                    brochure_name="HRMS Product Brochure",
                    download_at=now,
                    last_submitted_at=now,
                    submission_count=1,
                    dedupe_key="a" * 64,
                    followup_status="PENDING",
                    source="WEBSITE_BROCHURE",
                ),
                BrochureEnquiry(
                    name="Bala Sundar",
                    phone="+91 9123456780",
                    whatsapp_number="+91 9123456780",
                    country_code="+91",
                    email="bala@example.com",
                    product_name="Payroll",
                    brochure_name="Payroll Brochure",
                    download_at=now - timedelta(days=1),
                    last_submitted_at=now - timedelta(days=1),
                    submission_count=1,
                    dedupe_key="b" * 64,
                    followup_status="CONTACTED",
                    assigned_to=manager.id,
                    source="WEBSITE_BROCHURE",
                ),
                BrochureEnquiry(
                    name="Chitra Devi",
                    phone="+91 9000011122",
                    whatsapp_number="+91 9000011122",
                    country_code="+91",
                    email="chitra@example.com",
                    product_name="CRM",
                    brochure_name="CRM Brochure",
                    download_at=now - timedelta(days=2),
                    last_submitted_at=now - timedelta(days=2),
                    submission_count=1,
                    dedupe_key="c" * 64,
                    followup_status="CONVERTED",
                    assigned_to=executive.id,
                    source="WEBSITE_BROCHURE",
                ),
            ]
            db.add_all(records)
            db.commit()
            return [record.id for record in records]
        finally:
            db.close()

    def test_search_filters_pagination_and_summary(self):
        self._seed_records()

        page_one = self.client.get("/api/brochure-enquiries?page=1&page_size=2")
        self.assertEqual(page_one.status_code, 200, page_one.text)
        body = page_one.json()
        self.assertEqual(body["total"], 3)
        self.assertEqual(body["page"], 1)
        self.assertEqual(body["page_size"], 2)
        self.assertEqual(body["total_pages"], 2)
        self.assertEqual(len(body["items"]), 2)

        page_two = self.client.get("/api/brochure-enquiries?page=2&page_size=2")
        self.assertEqual(page_two.status_code, 200)
        self.assertEqual(len(page_two.json()["items"]), 1)

        by_name = self.client.get("/api/brochure-enquiries?search=Bala")
        self.assertEqual(by_name.status_code, 200)
        self.assertEqual(by_name.json()["total"], 1)
        self.assertEqual(by_name.json()["items"][0]["name"], "Bala Sundar")

        by_phone = self.client.get("/api/brochure-enquiries?search=9876543210")
        self.assertEqual(by_phone.status_code, 200)
        self.assertEqual(by_phone.json()["total"], 1)

        by_phone = self.client.get("/api/brochure-enquiries?search=98765 43210")
        self.assertEqual(by_phone.status_code, 200)
        self.assertEqual(by_phone.json()["total"], 1)

        by_brochure = self.client.get("/api/brochure-enquiries?brochure=Payroll%20Brochure")
        self.assertEqual(by_brochure.status_code, 200)
        self.assertEqual(by_brochure.json()["total"], 1)

        by_status = self.client.get("/api/brochure-enquiries?followup_status=CONVERTED")
        self.assertEqual(by_status.status_code, 200)
        self.assertEqual(by_status.json()["total"], 1)

        by_date = self.client.get("/api/brochure-enquiries?date_from=2026-11-03&date_to=2026-11-03")
        self.assertEqual(by_date.status_code, 200)
        self.assertEqual(by_date.json()["total"], 1)

        db = self.Session()
        try:
            manager_id = db.query(Employee).filter(Employee.name == "Sales Manager").one().id
        finally:
            db.close()
        by_employee = self.client.get(f"/api/brochure-enquiries?employee_id={manager_id}")
        self.assertEqual(by_employee.status_code, 200)
        self.assertEqual(by_employee.json()["total"], 1)

        summary = self.client.get("/api/brochure-enquiries/summary")
        self.assertEqual(summary.status_code, 200, summary.text)
        self.assertEqual(summary.json()["total_downloads"], 3)
        self.assertEqual(summary.json()["pending_followups"], 1)
        self.assertEqual(summary.json()["contacted_customers"], 1)
        self.assertEqual(summary.json()["converted_customers"], 1)

        options = self.client.get("/api/brochure-enquiries/filter-options")
        self.assertEqual(options.status_code, 200)
        option_body = options.json()
        self.assertIn("HRMS Product Brochure", option_body["brochures"])
        self.assertIn("Payroll Brochure", option_body["brochures"])
        self.assertTrue(any(employee["name"] == "Sales Manager" for employee in option_body["employees"]))

    def test_sales_executive_scope_includes_own_and_unassigned(self):
        self._seed_records()

        executive_user = SimpleNamespace(
            id=2,
            role="SALES_EXECUTIVE",
            username="sales.executive",
            is_active=True,
        )
        db = self.Session()
        try:
            executive = db.query(Employee).filter(Employee.name == "Sales Executive").one()
            executive.user_id = executive_user.id
            db.commit()
        finally:
            db.close()

        original_override = self.app.dependency_overrides.get(get_current_user)
        self.app.dependency_overrides[get_current_user] = lambda: executive_user
        try:
            listing = self.client.get("/api/brochure-enquiries?page=1&page_size=50")
            self.assertEqual(listing.status_code, 200, listing.text)
            names = {item["name"] for item in listing.json()["items"]}
            # Own assignment plus the shared unassigned intake queue; the
            # manager's record stays out of an executive's scope.
            self.assertEqual(names, {"Arun Kumar", "Chitra Devi"})

            summary = self.client.get("/api/brochure-enquiries/summary")
            self.assertEqual(summary.status_code, 200, summary.text)
            self.assertEqual(summary.json()["total_downloads"], 2)
        finally:
            self.app.dependency_overrides[get_current_user] = original_override

    def test_followup_update_and_note_append(self):
        enquiry_id = self._seed_records()[0]

        response = self.client.patch(
            f"/api/brochure-enquiries/{enquiry_id}",
            json={
                "followup_status": "FOLLOW_UP",
                "next_followup_date": "2026-11-05",
                "next_followup_time": "11:30",
                "note": "Called customer; requested a demo next week.",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["followup_status"], "FOLLOW_UP")
        self.assertEqual(body["next_followup_date"], "2026-11-05")
        self.assertEqual(body["next_followup_time"], "11:30")
        self.assertIn("Called customer; requested a demo next week.", body["notes"])
        self.assertIsNotNone(body["last_contacted_at"])

        second = self.client.patch(
            f"/api/brochure-enquiries/{enquiry_id}",
            json={"followup_status": "CONVERTED", "note": "Customer converted."},
        )
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json()["followup_status"], "CONVERTED")
        self.assertIsNotNone(second.json()["converted_at"])
        self.assertIn("Customer converted.", second.json()["notes"])
        self.assertIn("Called customer; requested a demo next week.", second.json()["notes"])

    def test_excel_export_contains_filtered_records(self):
        self._seed_records()

        response = self.client.get("/api/brochure-enquiries/export?followup_status=CONTACTED")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            response.headers.get("content-type", ""),
        )
        self.assertIn("Brochure_Download_People_", response.headers.get("content-disposition", ""))

        workbook = openpyxl.load_workbook(io.BytesIO(response.content))
        sheet = workbook.active
        self.assertEqual(sheet.title, "Brochure Downloads")
        headers = [cell.value for cell in sheet[1]]
        self.assertIn("Customer Name", headers)
        self.assertIn("WhatsApp Number", headers)
        self.assertIn("Product Name", headers)
        self.assertIn("Brochure Name", headers)
        self.assertEqual(sheet.max_row, 2)
        row_values = [cell.value for cell in sheet[2]]
        self.assertEqual(row_values[headers.index("Customer Name")], "Bala Sundar")
        self.assertEqual(row_values[headers.index("Follow-up Status")], "CONTACTED")


if __name__ == "__main__":
    unittest.main()
