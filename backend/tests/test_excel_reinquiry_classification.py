"""
Regression tests for Excel bulk-import duplicate detection and re-inquiry
classification.

Covers the reported bug where leads uploaded through Excel were shown as
RE-INQUIRY even though their mobile/email did not belong to an existing lead.

Run from the repository root:
    backend\\venv\\Scripts\\python.exe -m unittest backend.tests.test_excel_reinquiry_classification -v
"""
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath("backend"))

import openpyxl
from fastapi.testclient import TestClient

import main
from database import SessionLocal
from models.customer import Customer
from models.lead import Lead, LeadEnquiry
from services.auth import create_access_token
from services.reinquiry_service import ReInquiryService
from utils.phone import normalize_email, normalize_phone

# Every lead/email created by these tests starts with this prefix so cleanup
# can never touch real CRM data.
TEST_PHONE_PREFIX = "77700001"
TEST_EMAIL_DOMAIN = "excel-reinquiry-test.invalid"

client = TestClient(main.app)
AUTH = {"Authorization": f"Bearer {create_access_token({'sub': 'admin'})}"}


def build_excel(rows, headers=None):
    wb = openpyxl.Workbook()
    ws = wb.active
    headers = headers or [
        "First Name", "Last Name", "Phone", "WhatsApp Number", "Email", "Company",
    ]
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def upload(rows, headers=None):
    res = client.post(
        "/api/leads/import/excel",
        files={
            "file": (
                "lead_import_test.xlsx",
                build_excel(rows, headers),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=AUTH,
    )
    return res


class TestExcelReInquiryClassification(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        self._cleanup()

    def tearDown(self):
        self._cleanup()
        self.db.close()

    def _cleanup(self):
        """Remove only rows created by this test module."""
        self.db.rollback()
        for lead in self.db.query(Lead).all():
            if normalize_phone(lead.phone).startswith(TEST_PHONE_PREFIX):
                self.db.delete(lead)
        for customer in self.db.query(Customer).all():
            if (customer.phone and normalize_phone(customer.phone).startswith(TEST_PHONE_PREFIX)) or (
                customer.email and customer.email.lower().endswith(TEST_EMAIL_DOMAIN)
            ):
                self.db.delete(customer)
        self.db.commit()

    def _make_existing_lead(self, phone, **kwargs):
        lead = Lead(
            name=kwargs.pop("name", "Existing Test Lead"),
            phone=phone,
            source=kwargs.pop("source", "MANUAL"),
            status=kwargs.pop("status", "CONTACTED"),
            **kwargs,
        )
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        return lead

    def _populate(self):
        # End the current read transaction so data committed by the API's own
        # session is visible here (MySQL REPEATABLE READ keeps a snapshot).
        self.db.rollback()
        self.db.expire_all()

    def test_new_phones_are_created_as_new_leads(self):
        res = upload([
            ["New", "One", "7770000101", "", f"new1@{TEST_EMAIL_DOMAIN}", "Co One"],
            ["New", "Two", "+91 77700 00102", "", f"new2@{TEST_EMAIL_DOMAIN}", "Co Two"],
            ["New", "Three", "7770000103", "", "", "Co Three"],
        ])
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["total_rows"], 3)
        self.assertEqual(body["imported"], 3)
        self.assertEqual(body["reinquiries"], 0)
        self.assertEqual(body["duplicates"], 0)
        self.assertEqual(body["invalid"], 0)

        self._populate()
        leads = self.db.query(Lead).filter(Lead.phone.in_(
            ["7770000101", "+91 77700 00102", "7770000103"]
        )).all()
        self.assertEqual(len(leads), 3)
        for lead in leads:
            self.assertFalse(lead.is_reinquiry, f"lead {lead.id} must be NEW")
            self.assertEqual(lead.reinquiry_count, 0)
            self.assertEqual(lead.total_enquiries, 1)
            enquiries = self.db.query(LeadEnquiry).filter(LeadEnquiry.lead_id == lead.id).all()
            self.assertEqual(len(enquiries), 1)
            self.assertEqual(enquiries[0].enquiry_type, "INITIAL")

    def test_duplicate_rows_in_file_are_duplicates_not_reinquiries(self):
        """The exact production bug: same lead twice with different formatting."""
        res = upload([
            ["Dup", "One", "+91 77700 00111", "+91 77700 00111", "", "Co Dup"],
            ["Dup", "One again", "7770000111", "7770000111", "", "Co Dup"],
            ["Unique", "Three", "7770000112", "", "", "Co Unique"],
        ])
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["total_rows"], 3)
        self.assertEqual(body["imported"], 2)
        self.assertEqual(body["reinquiries"], 0)
        self.assertEqual(body["duplicates"], 1)
        self.assertEqual(body["invalid_rows"][0]["reason"], "Duplicate Phone in File")

        self._populate()
        first = self.db.query(Lead).filter(Lead.phone == "+91 77700 00111").first()
        self.assertIsNotNone(first)
        self.assertFalse(first.is_reinquiry)
        self.assertEqual(first.reinquiry_count, 0)
        self.assertEqual(first.total_enquiries, 1)

    def test_existing_mobile_number_is_reinquiry_and_history_is_preserved(self):
        existing = self._make_existing_lead(
            "7770000121",
            name="Existing Person",
            email=f"existing@{TEST_EMAIL_DOMAIN}",
            company="Original Company",
            assigned_to=9,
            assigned_by=1,
        )
        original = {
            "id": existing.id,
            "name": existing.name,
            "email": existing.email,
            "company": existing.company,
            "status": existing.status,
            "assigned_to": existing.assigned_to,
        }

        res = upload([
            ["Existing", "Person", "+91 77700 00121", "", "", "Attempted Overwrite Co"],
        ])
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["imported"], 0)
        self.assertEqual(body["reinquiries"], 1)
        self.assertEqual(body["duplicates"], 0)

        self._populate()
        self.db.refresh(existing)
        self.assertEqual(existing.id, original["id"])
        self.assertEqual(existing.name, original["name"])
        self.assertEqual(existing.email, original["email"])
        self.assertEqual(existing.company, original["company"], "existing data must not be overwritten")
        self.assertEqual(existing.status, original["status"])
        self.assertEqual(existing.assigned_to, original["assigned_to"])
        self.assertTrue(existing.is_reinquiry)
        self.assertEqual(existing.reinquiry_count, 1)
        self.assertEqual(existing.total_enquiries, 2)

        enquiries = self.db.query(LeadEnquiry).filter(LeadEnquiry.lead_id == existing.id).all()
        self.assertEqual(len(enquiries), 1)
        self.assertEqual(enquiries[0].enquiry_type, "RE-INQUIRY")

        # No duplicate lead was created.
        duplicates = self.db.query(Lead).filter(Lead.id != existing.id).all()
        self.assertFalse(any(normalize_phone(l.phone) == "7770000121" for l in duplicates))

    def test_existing_email_only_is_reinquiry(self):
        existing = self._make_existing_lead(
            "7770000131",
            email=f"matchemail@{TEST_EMAIL_DOMAIN}",
        )
        res = upload([
            ["Email", "Match", "7770000132", "", f"MatchEmail@{TEST_EMAIL_DOMAIN.upper()}", "Co"],
        ])
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["imported"], 0)
        self.assertEqual(body["reinquiries"], 1)

        self._populate()
        self.assertIsNone(
            self.db.query(Lead).filter(Lead.phone == "7770000132").first(),
            "email match must not create a new lead",
        )
        self.db.refresh(existing)
        self.assertTrue(existing.is_reinquiry)

    def test_empty_or_invalid_values_never_match(self):
        self._make_existing_lead("7770000141", email=f"some@{TEST_EMAIL_DOMAIN}")

        for phone, email in [
            (None, None),
            ("", ""),
            ("   ", "   "),
            (None, "not-an-email"),
            (None, "@"),
            ("abc", None),
            ("12", None),
            (None, f"missing-at-sign.{TEST_EMAIL_DOMAIN}"),
        ]:
            with self.subTest(phone=phone, email=email):
                self.assertIsNone(
                    ReInquiryService.find_existing_lead(self.db, phone=phone, email=email),
                    f"{phone!r}/{email!r} must never match an existing lead",
                )

        self.assertEqual(normalize_email("-"), "")
        self.assertEqual(normalize_email("N/A"), "")
        self.assertEqual(normalize_email(""), "")

    def test_placeholder_email_does_not_collapse_rows(self):
        res = upload([
            ["Placeholder", "One", "7770000151", "", "-", "Co"],
            ["Placeholder", "Two", "7770000152", "", "-", "Co"],
            ["Placeholder", "Three", "7770000153", "", "N/A", "Co"],
        ])
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["imported"], 3)
        self.assertEqual(body["duplicates"], 0)
        self.assertEqual(body["reinquiries"], 0)

    def test_invalid_phone_rows_are_rejected_not_reinquiries(self):
        res = upload([
            ["Bad", "Phone", "N/A", "", "", "Co"],
            ["Short", "Phone", "12345", "", "", "Co"],
            ["Good", "Phone", "7770000161", "", "", "Co"],
        ])
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["imported"], 1)
        self.assertEqual(body["invalid"], 2)
        self.assertEqual(body["reinquiries"], 0)

    def test_reuploading_same_file_is_reported_as_reinquiry(self):
        rows = [
            ["Again", "One", "7770000171", "", "", "Co"],
            ["Again", "Two", "7770000172", "", "", "Co"],
        ]
        first = upload(rows).json()
        self.assertEqual((first["imported"], first["reinquiries"]), (2, 0))

        second = upload(rows).json()
        self.assertEqual((second["imported"], second["reinquiries"]), (0, 2))

        self._populate()
        leads = self.db.query(Lead).filter(Lead.phone.in_(["7770000171", "7770000172"])).all()
        self.assertEqual(len(leads), 2, "a re-upload must not duplicate leads")


if __name__ == "__main__":
    unittest.main(verbosity=2)
