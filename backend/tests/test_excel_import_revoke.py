"""
Regression tests for Excel import batch tracking and the admin revoke action.

The revoke must delete only the leads created by one upload. Re-inquiries,
other imports and every other lead source must remain untouched.

Run from the repository root:
    backend\\venv\\Scripts\\python.exe -m unittest backend.tests.test_excel_import_revoke -v
"""
import io
import os
import sys
import unittest
import uuid
from datetime import date

sys.path.insert(0, os.path.abspath("backend"))

import openpyxl
from fastapi.testclient import TestClient

import main
import models  # noqa: F401  (registers every model on Base.metadata)
from database import Base, SessionLocal, engine
from models.activity import LeadActivity
from models.audit_log import AuditLog
from models.customer import Customer
from models.employee import Employee
from models.excel_import import ExcelImportBatch
from models.followup import Followup
from models.lead import Lead, LeadAssignment, LeadEnquiry
from services.auth import create_access_token
from utils.phone import normalize_phone

# Every lead created by these tests starts with this prefix so cleanup can
# never touch real CRM data. Test batches use a distinct filename prefix.
TEST_PHONE_PREFIX = "77700002"
TEST_FILENAME_PREFIX = "revoke_test_"

client = TestClient(main.app)
AUTH = {"Authorization": f"Bearer {create_access_token({'sub': 'admin'})}"}

# The production database already has these tables, but a fresh test database
# needs the new batch table before the first request.
Base.metadata.create_all(bind=engine)


def build_excel(rows):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["First Name", "Last Name", "Phone", "Email", "Company"])
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def upload(rows, filename):
    return client.post(
        "/api/leads/import/excel",
        files={
            "file": (
                filename,
                build_excel(rows),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=AUTH,
    )


class TestExcelImportRevoke(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        self._cleanup()

    def tearDown(self):
        self._cleanup()
        self.db.close()

    def _test_lead_ids(self):
        return [
            lead.id
            for lead in self.db.query(Lead).all()
            if normalize_phone(lead.phone).startswith(TEST_PHONE_PREFIX)
        ]

    def _cleanup(self):
        """Remove only rows created by this test module."""
        self.db.rollback()
        lead_ids = self._test_lead_ids()
        if lead_ids:
            self.db.query(Followup).filter(
                Followup.lead_id.in_(lead_ids)
            ).delete(synchronize_session=False)
            self.db.query(LeadActivity).filter(
                LeadActivity.lead_id.in_(lead_ids)
            ).delete(synchronize_session=False)
            self.db.query(LeadEnquiry).filter(
                LeadEnquiry.lead_id.in_(lead_ids)
            ).delete(synchronize_session=False)
            self.db.query(LeadAssignment).filter(
                LeadAssignment.lead_id.in_(lead_ids)
            ).delete(synchronize_session=False)
            self.db.query(Customer).filter(
                Customer.converted_from_lead.in_(lead_ids)
            ).delete(synchronize_session=False)
            self.db.query(Lead).filter(
                Lead.id.in_(lead_ids)
            ).delete(synchronize_session=False)
            self.db.commit()
        self.db.query(ExcelImportBatch).filter(
            ExcelImportBatch.filename.like(f"{TEST_FILENAME_PREFIX}%")
        ).delete(synchronize_session=False)
        self.db.commit()

    def _unique_filename(self, label):
        return f"{TEST_FILENAME_PREFIX}{label}_{uuid.uuid4().hex[:8]}.xlsx"

    def _refresh(self):
        # End the current read transaction so API commits are visible.
        self.db.rollback()
        self.db.expire_all()

    def test_revoke_deletes_only_the_selected_batch(self):
        file_a = self._unique_filename("a")
        file_b = self._unique_filename("b")

        response_a = upload([
            ["Batch", "A One", "7770000201", "a1@revoke-test.invalid", "A Co"],
            ["Batch", "A Two", "7770000202", "a2@revoke-test.invalid", "A Co"],
        ], file_a)
        self.assertEqual(response_a.status_code, 200, response_a.text)
        batch_a_id = response_a.json()["batch_id"]
        self.assertIsNotNone(batch_a_id)

        response_b = upload([
            ["Batch", "B One", "7770000203", "b1@revoke-test.invalid", "B Co"],
            ["Batch", "B Two", "7770000204", "b2@revoke-test.invalid", "B Co"],
        ], file_b)
        self.assertEqual(response_b.status_code, 200, response_b.text)
        batch_b_id = response_b.json()["batch_id"]
        self.assertIsNotNone(batch_b_id)
        self.assertNotEqual(batch_a_id, batch_b_id)

        self._refresh()
        batch_a_lead_ids = {
            lead.id
            for lead in self.db.query(Lead).filter(
                Lead.import_batch_id == batch_a_id
            ).all()
        }
        batch_b_lead_ids = {
            lead.id
            for lead in self.db.query(Lead).filter(
                Lead.import_batch_id == batch_b_id
            ).all()
        }
        self.assertEqual(len(batch_a_lead_ids), 2)
        self.assertEqual(len(batch_b_lead_ids), 2)
        self.assertTrue(batch_a_lead_ids.isdisjoint(batch_b_lead_ids))

        # Give batch A one extra assignment per lead. Import-generated
        # assignments and this record must both be removed by the revoke.
        employee = self.db.query(Employee).first()
        self.assertIsNotNone(employee)
        for lead_id in batch_a_lead_ids:
            self.db.add(LeadAssignment(
                lead_id=lead_id,
                assigned_to=employee.id,
                assigned_by=employee.id,
                assignment_method="MANUAL",
                notes="Test assignment",
            ))
        self.db.commit()

        history = client.get("/api/leads/import/batches", headers=AUTH)
        self.assertEqual(history.status_code, 200, history.text)
        history_body = history.json()
        self.assertTrue(history_body["can_revoke"])
        by_id = {batch["id"]: batch for batch in history_body["batches"]}
        self.assertEqual(by_id[batch_a_id]["remaining_lead_count"], 2)
        self.assertTrue(by_id[batch_a_id]["can_revoke"])
        self.assertEqual(by_id[batch_b_id]["remaining_lead_count"], 2)

        revoke = client.post(
            f"/api/leads/import/batches/{batch_a_id}/revoke",
            headers=AUTH,
        )
        self.assertEqual(revoke.status_code, 200, revoke.text)
        payload = revoke.json()
        self.assertEqual(payload["batch_id"], batch_a_id)
        self.assertEqual(payload["deleted_leads"], 2)
        self.assertEqual(payload["deleted_enquiries"], 2)
        self.assertGreaterEqual(payload["deleted_activities"], 2)
        self.assertGreaterEqual(payload["deleted_assignments"], 2)

        self._refresh()
        self.assertEqual(
            self.db.query(Lead).filter(
                Lead.import_batch_id == batch_a_id
            ).count(),
            0,
        )
        remaining_batch_b = self.db.query(Lead).filter(
            Lead.import_batch_id == batch_b_id
        ).all()
        self.assertEqual(len(remaining_batch_b), 2)
        self.assertEqual(
            {lead.id for lead in remaining_batch_b},
            batch_b_lead_ids,
        )

        revoked_batch = self.db.query(ExcelImportBatch).filter(
            ExcelImportBatch.id == batch_a_id
        ).first()
        self.assertEqual(revoked_batch.status, "REVOKED")
        self.assertEqual(revoked_batch.revoked_lead_count, 2)
        self.assertEqual(revoked_batch.revoked_by_username, "admin")

        active_batch = self.db.query(ExcelImportBatch).filter(
            ExcelImportBatch.id == batch_b_id
        ).first()
        self.assertEqual(active_batch.status, "ACTIVE")

        audit = self.db.query(AuditLog).filter(
            AuditLog.action == "IMPORT_EXCEL_REVOKED",
            AuditLog.entity_id == str(batch_a_id),
        ).order_by(AuditLog.id.desc()).first()
        self.assertIsNotNone(audit)
        self.assertIn(file_a, audit.details)
        self.assertIn("2 leads", audit.details)

    def test_revoke_twice_is_rejected(self):
        filename = self._unique_filename("twice")
        response = upload([
            ["Twice", "Lead", "7770000211", "twice@revoke-test.invalid", "Twice Co"],
        ], filename)
        self.assertEqual(response.status_code, 200, response.text)
        batch_id = response.json()["batch_id"]

        first = client.post(
            f"/api/leads/import/batches/{batch_id}/revoke",
            headers=AUTH,
        )
        self.assertEqual(first.status_code, 200, first.text)

        second = client.post(
            f"/api/leads/import/batches/{batch_id}/revoke",
            headers=AUTH,
        )
        self.assertEqual(second.status_code, 400, second.text)
        self.assertIn("already been revoked", second.json()["detail"])

    def test_revoke_is_blocked_when_a_lead_has_a_followup(self):
        filename = self._unique_filename("followup")
        response = upload([
            ["Worked", "Lead", "7770000221", "worked@revoke-test.invalid", "Worked Co"],
        ], filename)
        self.assertEqual(response.status_code, 200, response.text)
        batch_id = response.json()["batch_id"]

        self._refresh()
        lead = self.db.query(Lead).filter(
            Lead.import_batch_id == batch_id
        ).first()
        self.assertIsNotNone(lead)
        self.db.add(Followup(
            lead_id=lead.id,
            assigned_to=lead.assigned_to or 1,
            followup_date=date.today(),
            notes="Real work added after the import",
        ))
        self.db.commit()

        revoke = client.post(
            f"/api/leads/import/batches/{batch_id}/revoke",
            headers=AUTH,
        )
        self.assertEqual(revoke.status_code, 400, revoke.text)
        self.assertIn("followups.lead_id", revoke.json()["detail"])

        self._refresh()
        self.assertIsNotNone(
            self.db.query(Lead).filter(Lead.id == lead.id).first()
        )
        batch = self.db.query(ExcelImportBatch).filter(
            ExcelImportBatch.id == batch_id
        ).first()
        self.assertEqual(batch.status, "ACTIVE")

    def test_revoke_is_blocked_when_a_lead_has_a_later_reinquiry(self):
        filename = self._unique_filename("reinquiry")
        first = upload([
            ["Re", "Inquiry", "7770000231", "re@revoke-test.invalid", "Re Co"],
        ], filename)
        self.assertEqual(first.status_code, 200, first.text)
        batch_id = first.json()["batch_id"]

        second = upload([
            ["Re", "Inquiry", "7770000231", "re@revoke-test.invalid", "Re Co"],
        ], self._unique_filename("reinquiry2"))
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json()["imported"], 0)
        self.assertEqual(second.json()["reinquiries"], 1)
        self.assertIsNone(second.json()["batch_id"])

        revoke = client.post(
            f"/api/leads/import/batches/{batch_id}/revoke",
            headers=AUTH,
        )
        self.assertEqual(revoke.status_code, 400, revoke.text)
        self.assertIn("worked on", revoke.json()["detail"])

        self._refresh()
        self.assertEqual(
            self.db.query(Lead).filter(
                Lead.import_batch_id == batch_id
            ).count(),
            1,
        )


if __name__ == "__main__":
    unittest.main()
