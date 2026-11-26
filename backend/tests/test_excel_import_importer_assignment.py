"""Bulk Excel import ownership regression coverage.

Every lead created by a Bulk Excel Import must belong to the authenticated
employee who uploaded the file. The spreadsheet's "Assigned To" column and the
browser payload are never trusted. Automatic, round-robin and background
assignment must not take these leads away from their importer.

Isolated in-memory SQLite only. No live CRM record is read or written.

Run from the repository root:
    backend\\venv\\Scripts\\python.exe -m unittest backend.tests.test_excel_import_importer_assignment -v
"""

import asyncio
import io
import os
import sys
import unittest
import uuid

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import openpyxl
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.datastructures import UploadFile

import models  # noqa: F401 - registers every model on Base.metadata
from database import Base
from models.employee import Employee
from models.excel_import import ExcelImportBatch
from models.lead import AutoAssignConfig, Lead, LeadAssignment, LeadEnquiry
from models.user import User
from routers.leads import (
    assign_lead,
    import_leads_excel,
    list_excel_import_batches,
    list_leads,
)
from schemas.lead import LeadAssignRequest
from services.lead_assignment_service import (
    assign_lead_immediately,
    auto_assign_pending_leads,
)

TEST_PHONE_PREFIX = "77701000"
TEST_FILENAME_PREFIX = "importer_assignment_test_"


def build_excel(phones, assigned_to="", status="NEW LEAD"):
    """Build a small import workbook, including an untrusted Assigned To."""
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append([
        "First Name",
        "Last Name",
        "Phone",
        "Email",
        "Company",
        "Source",
        "Status",
        "Assigned To",
    ])
    for index, phone in enumerate(phones, start=1):
        sheet.append([
            "Bulk",
            f"Lead {index}",
            phone,
            f"bulk-{phone}@example.com",
            "Importer Test Co",
            "EXCEL",
            status,
            assigned_to,
        ])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


class ExcelImportImporterAssignmentTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(
            bind=self.engine, autoflush=False, autocommit=False
        )
        self.db = Session()

        self.admin_user, self.admin_emp = self._make_person(
            "importer_admin", "ADMIN", "ADMINISTRATION"
        )
        self.manager_user, self.manager_emp = self._make_person(
            "importer_sales_manager", "SALES_MANAGER", "SALES"
        )
        self.target_manager_user, self.target_manager_emp = self._make_person(
            "importer_target_manager", "SALES_MANAGER", "SALES"
        )
        self.exec_a_user, self.exec_a_emp = self._make_person(
            "importer_exec_a",
            "SALES_EXECUTIVE",
            "SALES",
            manager_emp=self.manager_emp,
        )
        self.exec_b_user, self.exec_b_emp = self._make_person(
            "importer_exec_b",
            "SALES_EXECUTIVE",
            "SALES",
            manager_emp=self.manager_emp,
        )
        self._phone_counter = 0

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    # ------------------------------------------------------------------
    # Fixtures
    # ------------------------------------------------------------------
    def _make_person(
        self, username, role, department, status="ACTIVE", manager_emp=None
    ):
        user = User(
            username=username,
            hashed_password="not-used-in-tests",
            role=role,
            department=department,
            is_active=status == "ACTIVE",
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        employee = Employee(
            user_id=user.id,
            manager_id=manager_emp.id if manager_emp else None,
            department=department,
            name=username.replace("_", " ").title(),
            email=f"{username}@example.test",
            phone="9800000000",
            username=username,
            role=role,
            status=status,
        )
        self.db.add(employee)
        self.db.commit()
        self.db.refresh(employee)
        return user, employee

    def _next_phones(self, count):
        phones = []
        for _ in range(count):
            self._phone_counter += 1
            phones.append(f"{TEST_PHONE_PREFIX}{self._phone_counter:02d}")
        return phones

    def _filename(self, label):
        return f"{TEST_FILENAME_PREFIX}{label}_{uuid.uuid4().hex[:8]}.xlsx"

    def _import(self, user, phones, assigned_to="", status="NEW LEAD", label="a"):
        upload = UploadFile(
            filename=self._filename(label),
            file=io.BytesIO(build_excel(phones, assigned_to, status)),
        )
        return asyncio.run(
            import_leads_excel(
                file=upload,
                db=self.db,
                current_user=user,
            )
        )

    def _batch_leads(self, batch_id):
        return (
            self.db.query(Lead)
            .filter(Lead.import_batch_id == batch_id)
            .order_by(Lead.id.asc())
            .all()
        )

    def _list(self, user, search=None):
        return list_leads(
            search=search,
            status_filter="ALL",
            source_filter="EXCEL",
            page=1,
            page_size=50,
            skip=0,
            limit=None,
            db=self.db,
            current_user=user,
        )

    def _make_auto_assign_config(self):
        self.db.query(AutoAssignConfig).delete()
        self.db.add(AutoAssignConfig(
            id=1,
            enabled=True,
            waiting_time_minutes=0,
            assignment_method="ROUND_ROBIN",
            eligible_roles="SALES_EXECUTIVE,SALES_MANAGER",
            working_hours_enabled=False,
            working_hours_start="00:00",
            working_hours_end="23:59",
        ))
        self.db.commit()

    # ------------------------------------------------------------------
    # Importer ownership
    # ------------------------------------------------------------------
    def test_importer_owns_all_new_leads_and_excel_assigned_to_is_ignored(self):
        """Employee A imports 10 leads. All 10 belong to A, none to B."""
        phones = self._next_phones(10)

        result = self._import(
            self.exec_a_user,
            phones,
            assigned_to=self.exec_b_emp.name,  # untrusted spreadsheet value
            label="a",
        )

        self.assertEqual(result["imported"], 10)
        self.assertEqual(result["reinquiries"], 0)
        self.assertEqual(result["imported_by"], self.exec_a_emp.id)
        self.assertEqual(result["imported_by_name"], self.exec_a_emp.name)
        batch_id = result["batch_id"]
        self.assertIsNotNone(batch_id)

        leads = self._batch_leads(batch_id)
        self.assertEqual(len(leads), 10)
        for lead in leads:
            self.assertEqual(lead.assigned_to, self.exec_a_emp.id)
            self.assertEqual(lead.assigned_by, self.exec_a_emp.id)
            self.assertIsNotNone(lead.assigned_at)
            self.assertNotEqual(lead.assigned_to, self.exec_b_emp.id)
            self.assertEqual(lead.status, "ASSIGNED")

            assignments = (
                self.db.query(LeadAssignment)
                .filter(LeadAssignment.lead_id == lead.id)
                .all()
            )
            self.assertEqual(len(assignments), 1)
            self.assertEqual(assignments[0].assigned_to, self.exec_a_emp.id)
            self.assertEqual(assignments[0].assigned_by, self.exec_a_emp.id)
            self.assertEqual(
                assignments[0].assignment_method, "EXCEL_IMPORT"
            )

        batch = (
            self.db.query(ExcelImportBatch)
            .filter(ExcelImportBatch.id == batch_id)
            .one()
        )
        self.assertEqual(batch.imported_by, self.exec_a_emp.id)
        self.assertEqual(batch.imported_by_name, self.exec_a_emp.name)
        self.assertEqual(batch.total_rows, 10)
        self.assertEqual(batch.imported_count, 10)
        self.assertEqual(batch.successful_rows, 10)
        self.assertEqual(batch.failed_rows, 0)

        # The untrusted spreadsheet value produced no assignment for B.
        self.assertEqual(
            self.db.query(LeadAssignment)
            .filter(
                LeadAssignment.lead_id.in_([lead.id for lead in leads]),
                LeadAssignment.assigned_to == self.exec_b_emp.id,
            )
            .count(),
            0,
        )

    def test_two_importers_keep_their_batches_and_visibility_separate(self):
        phones_a = self._next_phones(10)
        phones_b = self._next_phones(10)

        batch_a = self._import(self.exec_a_user, phones_a, label="a")
        batch_b = self._import(
            self.exec_b_user,
            phones_b,
            assigned_to=self.exec_a_emp.name,
            label="b",
        )

        self.assertEqual(batch_a["imported"], 10)
        self.assertEqual(batch_b["imported"], 10)
        self.assertNotEqual(batch_a["batch_id"], batch_b["batch_id"])

        leads_a = self._batch_leads(batch_a["batch_id"])
        leads_b = self._batch_leads(batch_b["batch_id"])
        self.assertEqual({lead.assigned_to for lead in leads_a}, {self.exec_a_emp.id})
        self.assertEqual({lead.assigned_to for lead in leads_b}, {self.exec_b_emp.id})
        self.assertTrue(
            {lead.id for lead in leads_a}.isdisjoint(
                {lead.id for lead in leads_b}
            )
        )

        # Existing role-based visibility is unchanged: each executive sees
        # only their own imported leads.
        page_a = self._list(self.exec_a_user)
        page_b = self._list(self.exec_b_user)
        self.assertEqual(page_a["total"], 10)
        self.assertEqual(page_b["total"], 10)
        self.assertEqual(
            {item.id for item in page_a["items"]},
            {lead.id for lead in leads_a},
        )
        self.assertEqual(
            {item.id for item in page_b["items"]},
            {lead.id for lead in leads_b},
        )

        # B cannot find A's lead by searching its exact phone number.
        hidden = self._list(self.exec_b_user, search=leads_a[0].phone)
        self.assertEqual(hidden["total"], 0)

        # Admin retains company-wide visibility.
        admin_page = self._list(self.admin_user)
        self.assertEqual(admin_page["total"], 20)

        # Import history records the importer employee for every batch.
        history = list_excel_import_batches(
            limit=50, db=self.db, current_user=self.admin_user
        )
        by_id = {batch["id"]: batch for batch in history["batches"]}
        self.assertEqual(
            by_id[batch_a["batch_id"]]["imported_by"], self.exec_a_emp.id
        )
        self.assertEqual(
            by_id[batch_a["batch_id"]]["imported_by_name"],
            self.exec_a_emp.name,
        )
        self.assertEqual(
            by_id[batch_b["batch_id"]]["imported_by"], self.exec_b_emp.id
        )
        self.assertEqual(
            by_id[batch_b["batch_id"]]["imported_by_name"],
            self.exec_b_emp.name,
        )
        self.assertEqual(
            by_id[batch_a["batch_id"]]["successful_rows"], 10
        )
        self.assertEqual(by_id[batch_a["batch_id"]]["failed_rows"], 0)

    def test_reupload_preserves_the_existing_importer_owner(self):
        """A later upload of the same phone is a re-inquiry, not a takeover."""
        phone = self._next_phones(1)
        first = self._import(self.exec_a_user, phone, label="owner")
        lead_id = self._batch_leads(first["batch_id"])[0].id

        second = self._import(
            self.exec_b_user,
            phone,
            assigned_to=self.exec_b_emp.name,
            label="reinquiry",
        )

        self.assertEqual(second["imported"], 0)
        self.assertEqual(second["reinquiries"], 1)
        self.assertIsNone(second["batch_id"])

        self.db.expire_all()
        lead = self.db.query(Lead).filter(Lead.id == lead_id).one()
        self.assertEqual(lead.assigned_to, self.exec_a_emp.id)
        self.assertEqual(lead.reinquiry_count, 1)
        self.assertEqual(
            self.db.query(LeadAssignment)
            .filter(LeadAssignment.lead_id == lead.id)
            .count(),
            1,
        )
        self.assertEqual(
            self.db.query(LeadEnquiry)
            .filter(LeadEnquiry.lead_id == lead.id)
            .count(),
            2,
        )

    def test_auto_assignment_and_round_robin_never_take_imported_leads(self):
        phones = self._next_phones(10)
        result = self._import(self.exec_a_user, phones, label="auto")

        self._make_auto_assign_config()
        self.assertEqual(auto_assign_pending_leads(self.db), 0)
        self.db.expire_all()
        leads = self._batch_leads(result["batch_id"])
        self.assertEqual(
            {lead.assigned_to for lead in leads}, {self.exec_a_emp.id}
        )

        # Defence in depth: even if a legacy row lost its owner, the batch
        # reference makes it ineligible for automatic assignment.
        orphan = leads[0]
        orphan.assigned_to = None
        self.db.commit()
        self.assertIsNone(assign_lead_immediately(self.db, orphan))
        self.assertEqual(auto_assign_pending_leads(self.db), 0)
        self.db.refresh(orphan)
        self.assertIsNone(orphan.assigned_to)
        self.assertEqual(
            self.db.query(LeadAssignment)
            .filter(
                LeadAssignment.lead_id == orphan.id,
                LeadAssignment.assignment_method == "AUTOMATIC",
            )
            .count(),
            0,
        )

    def test_admin_and_manager_reassignment_still_works(self):
        phones = self._next_phones(2)
        result = self._import(self.exec_a_user, phones, label="reassign")
        leads = self._batch_leads(result["batch_id"])

        admin_result = assign_lead(
            lead_id=leads[0].id,
            assign_req=LeadAssignRequest(assigned_to=self.target_manager_emp.id),
            db=self.db,
            current_user=self.admin_user,
        )
        self.assertEqual(admin_result.assigned_to, self.target_manager_emp.id)

        manager_result = assign_lead(
            lead_id=leads[1].id,
            assign_req=LeadAssignRequest(assigned_to=self.target_manager_emp.id),
            db=self.db,
            current_user=self.manager_user,
        )
        self.assertEqual(
            manager_result.assigned_to, self.target_manager_emp.id
        )

        self.db.expire_all()
        reassigned = self.db.query(Lead).filter(
            Lead.id.in_([leads[0].id, leads[1].id])
        ).all()
        self.assertEqual(
            {lead.assigned_to for lead in reassigned},
            {self.target_manager_emp.id},
        )
        manual_count = (
            self.db.query(LeadAssignment)
            .filter(
                LeadAssignment.lead_id.in_([leads[0].id, leads[1].id]),
                LeadAssignment.assignment_method == "MANUAL",
                LeadAssignment.assigned_to == self.target_manager_emp.id,
            )
            .count()
        )
        self.assertEqual(manual_count, 2)

    def test_login_without_employee_cannot_create_unowned_imports(self):
        user = User(
            username="importer_without_employee",
            hashed_password="not-used-in-tests",
            role="SALES_EXECUTIVE",
            department="SALES",
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        upload = UploadFile(
            filename=self._filename("no_employee"),
            file=io.BytesIO(build_excel(self._next_phones(1))),
        )
        with self.assertRaises(HTTPException) as context:
            asyncio.run(
                import_leads_excel(
                    file=upload, db=self.db, current_user=user
                )
            )
        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("not linked to an employee", context.exception.detail)
        self.assertEqual(self.db.query(Lead).count(), 0)
        self.assertEqual(self.db.query(ExcelImportBatch).count(), 0)


if __name__ == "__main__":
    unittest.main()
