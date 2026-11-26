"""Bulk lead assignment regression coverage.

Admin and Manager users can select several leads in the Leads table and assign
them to one active Sales Manager in a single action. The bulk endpoint must
behave like repeated manual assignment: every lead receives a MANUAL assignment
record and an activity entry, initial NEW statuses move to ASSIGNED, and an
invalid target or missing lead rejects the whole batch without partial writes.

Isolated in-memory SQLite only. No live CRM record is read or written.

Run from the repository root:
    backend\\venv\\Scripts\\python.exe -m unittest backend.tests.test_bulk_lead_assignment -v
"""

import os
import sys
import unittest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401 - registers every model on Base.metadata
from database import Base, get_db
from main import app as fastapi_app
from models.activity import LeadActivity
from models.audit_log import AuditLog
from models.employee import Employee
from models.excel_import import ExcelImportBatch
from models.lead import Lead, LeadAssignment
from models.user import User
from routers import leads as leads_router_module
from routers.leads import bulk_assign_leads
from schemas.lead import LeadBulkAssignRequest
from services.auth import get_current_user


class BulkLeadAssignmentTests(unittest.TestCase):
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
        self._phone_counter = 9444400000

        self.admin_user, self.admin_emp = self._make_person(
            "bulk_admin", "ADMIN", "ADMINISTRATION"
        )
        self.manager_user, self.manager_emp = self._make_person(
            "bulk_sales_manager", "SALES_MANAGER", "SALES"
        )
        self.other_manager_user, self.other_manager_emp = self._make_person(
            "bulk_sales_manager_b", "SALES_MANAGER", "SALES"
        )
        self.exec_user, self.exec_emp = self._make_person(
            "bulk_sales_exec",
            "SALES_EXECUTIVE",
            "SALES",
            manager_emp=self.manager_emp,
        )

    def tearDown(self):
        fastapi_app.dependency_overrides.pop(get_db, None)
        fastapi_app.dependency_overrides.pop(get_current_user, None)
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

    def _next_phone(self):
        self._phone_counter += 1
        return str(self._phone_counter)

    def _make_lead(
        self,
        status="NEW LEAD",
        assigned_to=None,
        import_batch_id=None,
    ):
        lead = Lead(
            name="Bulk Assignment Lead",
            phone=self._next_phone(),
            source="MANUAL",
            status=status,
            assigned_to=assigned_to,
            import_batch_id=import_batch_id,
        )
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        return lead

    def _assignments(self, lead_id):
        return (
            self.db.query(LeadAssignment)
            .filter(LeadAssignment.lead_id == lead_id)
            .order_by(LeadAssignment.id.asc())
            .all()
        )

    def _assign(self, user, lead_ids, assigned_to):
        return bulk_assign_leads(
            assign_req=LeadBulkAssignRequest(
                lead_ids=lead_ids,
                assigned_to=assigned_to,
            ),
            db=self.db,
            current_user=user,
        )

    # ------------------------------------------------------------------
    # Bulk assignment
    # ------------------------------------------------------------------
    def test_admin_bulk_assigns_multiple_leads_with_manual_records(self):
        new_lead = self._make_lead(status="NEW LEAD")
        legacy_new = self._make_lead(status="NEW")
        contacted = self._make_lead(status="CONTACTED")
        lead_ids = [new_lead.id, legacy_new.id, contacted.id]

        result = self._assign(
            self.admin_user, lead_ids, self.other_manager_emp.id
        )

        self.assertEqual(result["assigned_count"], 3)
        self.assertEqual(set(result["lead_ids"]), set(lead_ids))
        self.assertEqual(result["assigned_to"], self.other_manager_emp.id)
        self.assertEqual(
            result["assigned_employee_name"], self.other_manager_emp.name
        )

        self.db.expire_all()
        updated = (
            self.db.query(Lead)
            .filter(Lead.id.in_(lead_ids))
            .order_by(Lead.id.asc())
            .all()
        )
        self.assertEqual(
            {lead.assigned_to for lead in updated},
            {self.other_manager_emp.id},
        )
        self.assertEqual(
            {lead.assigned_by for lead in updated}, {self.admin_emp.id}
        )
        self.assertTrue(all(lead.assigned_at for lead in updated))

        by_id = {lead.id: lead for lead in updated}
        self.assertEqual(by_id[new_lead.id].status, "ASSIGNED")
        self.assertEqual(by_id[legacy_new.id].status, "ASSIGNED")
        self.assertEqual(by_id[contacted.id].status, "CONTACTED")

        for lead_id in lead_ids:
            assignments = self._assignments(lead_id)
            self.assertEqual(len(assignments), 1)
            self.assertEqual(
                assignments[0].assigned_to, self.other_manager_emp.id
            )
            self.assertEqual(assignments[0].assigned_by, self.admin_emp.id)
            self.assertEqual(assignments[0].assignment_method, "MANUAL")
            self.assertIn("Bulk assigned by", assignments[0].notes)

            activities = (
                self.db.query(LeadActivity)
                .filter(LeadActivity.lead_id == lead_id)
                .all()
            )
            self.assertEqual(len(activities), 1)
            self.assertEqual(activities[0].activity_type, "ASSIGNED")
            self.assertEqual(activities[0].performed_by, self.admin_emp.id)

        audits = (
            self.db.query(AuditLog)
            .filter(AuditLog.action == "LEAD_BULK_ASSIGNMENT")
            .all()
        )
        self.assertEqual(len(audits), 1)
        self.assertEqual(audits[0].user_id, self.admin_user.id)

    def test_manager_can_bulk_assign_and_duplicate_ids_are_deduplicated(self):
        first = self._make_lead()
        second = self._make_lead()

        result = self._assign(
            self.manager_user,
            [first.id, first.id, second.id],
            self.other_manager_emp.id,
        )

        self.assertEqual(result["assigned_count"], 2)
        self.assertEqual(
            sorted(result["lead_ids"]), sorted([first.id, second.id])
        )
        for lead_id in (first.id, second.id):
            assignments = self._assignments(lead_id)
            self.assertEqual(len(assignments), 1)
            self.assertEqual(
                assignments[0].assigned_to, self.other_manager_emp.id
            )
            self.assertEqual(
                assignments[0].assigned_by, self.manager_emp.id
            )

    def test_imported_lead_can_be_reassigned_by_admin_or_manager(self):
        batch = ExcelImportBatch(
            filename="bulk-assignment-import.xlsx",
            imported_by=self.manager_emp.id,
            imported_by_name=self.manager_emp.name,
            total_rows=1,
            imported_count=1,
        )
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)

        imported = self._make_lead(
            assigned_to=self.manager_emp.id,
            import_batch_id=batch.id,
        )

        result = self._assign(
            self.admin_user, [imported.id], self.other_manager_emp.id
        )

        self.assertEqual(result["assigned_count"], 1)
        self.db.refresh(imported)
        self.assertEqual(imported.assigned_to, self.other_manager_emp.id)
        self.assertEqual(imported.assigned_by, self.admin_emp.id)

        assignments = self._assignments(imported.id)
        self.assertEqual(len(assignments), 1)
        self.assertEqual(assignments[0].assignment_method, "MANUAL")
        self.assertEqual(assignments[0].assigned_to, self.other_manager_emp.id)

        activities = (
            self.db.query(LeadActivity)
            .filter(LeadActivity.lead_id == imported.id)
            .all()
        )
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities[0].activity_type, "ASSIGNMENT_CHANGED")

    # ------------------------------------------------------------------
    # Validation is all-or-nothing
    # ------------------------------------------------------------------
    def test_ineligible_target_rejects_entire_batch(self):
        lead = self._make_lead()

        with self.assertRaises(HTTPException) as context:
            self._assign(self.admin_user, [lead.id], self.exec_emp.id)

        self.assertEqual(context.exception.status_code, 400)
        self.db.refresh(lead)
        self.assertIsNone(lead.assigned_to)
        self.assertEqual(self._assignments(lead.id), [])

    def test_missing_lead_rejects_entire_batch(self):
        lead = self._make_lead()

        with self.assertRaises(HTTPException) as context:
            self._assign(
                self.admin_user,
                [lead.id, 99999999],
                self.other_manager_emp.id,
            )

        self.assertEqual(context.exception.status_code, 404)
        self.assertIn("No leads were assigned", context.exception.detail)
        self.db.refresh(lead)
        self.assertIsNone(lead.assigned_to)
        self.assertEqual(self._assignments(lead.id), [])
        self.assertEqual(
            self.db.query(LeadAssignment)
            .filter(LeadAssignment.assigned_to == self.other_manager_emp.id)
            .count(),
            0,
        )

    def test_bulk_route_is_declared_before_dynamic_assign_route(self):
        paths = [
            getattr(route, "path", None)
            for route in leads_router_module.router.routes
        ]
        self.assertIn("/leads/bulk/assign", paths)
        self.assertIn("/leads/{lead_id}/assign", paths)
        self.assertLess(
            paths.index("/leads/bulk/assign"),
            paths.index("/leads/{lead_id}/assign"),
        )

    def test_http_route_assigns_for_admin_and_forbids_sales_executive(self):
        fastapi_app.dependency_overrides[get_db] = lambda: self.db
        fastapi_app.dependency_overrides[get_current_user] = lambda: self.admin_user
        client = TestClient(fastapi_app)

        lead = self._make_lead()
        response = client.put(
            "/api/leads/bulk/assign",
            json={
                "lead_ids": [lead.id],
                "assigned_to": self.other_manager_emp.id,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["assigned_count"], 1)
        self.assertEqual(response.json()["lead_ids"], [lead.id])

        self.db.refresh(lead)
        self.assertEqual(lead.assigned_to, self.other_manager_emp.id)

        # A Sales Executive has no leads:assign permission, so the same route
        # must be rejected before any lead is touched.
        fastapi_app.dependency_overrides[get_current_user] = lambda: self.exec_user
        untouched = self._make_lead()
        forbidden = client.put(
            "/api/leads/bulk/assign",
            json={
                "lead_ids": [untouched.id],
                "assigned_to": self.other_manager_emp.id,
            },
        )
        self.assertEqual(forbidden.status_code, 403, forbidden.text)
        self.assertIn("do not have permission", forbidden.text)

        self.db.refresh(untouched)
        self.assertIsNone(untouched.assigned_to)


if __name__ == "__main__":
    unittest.main()
