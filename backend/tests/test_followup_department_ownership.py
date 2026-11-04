"""Isolated department ownership and visibility tests for follow-ups.

These tests use an in-memory SQLite database and synthetic records. They never
touch the live MySQL CRM database.
"""

import os
import sys
import unittest
from datetime import date, timedelta

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401 - registers every model on Base.metadata
from database import Base
from models.employee import Employee
from models.followup import Followup
from models.lead import Lead
from models.user import User
from routers.followups import (
    create_followup,
    delete_followup,
    dismiss_followup_reminder,
    get_followup,
    list_followups,
    snooze_followup_reminder,
    update_followup,
)
from routers.reports import build_support_dashboard_payload, dashboard_stats
from schemas.followup import (
    FollowupCreate,
    FollowupSnoozeRequest,
    FollowupUpdate,
)
from services.followup_visibility_service import backfill_followup_departments
from services.permission_service import seed_default_roles_if_needed


class FollowupDepartmentOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db = self.Session()

        # Real role/permission data, matching production defaults.
        seed_default_roles_if_needed(self.db)

        self.admin_user, self.admin_emp = self._make_person(
            "test_admin_owner", "ADMIN", "ADMINISTRATION"
        )
        self.sales_manager_user, self.sales_manager = self._make_person(
            "test_sales_manager_owner",
            "SALES_MANAGER",
            "SALES",
            manager_user=self.admin_user,
            manager_emp=self.admin_emp,
        )
        self.sales_exec_user, self.sales_exec = self._make_person(
            "test_sales_exec_owner",
            "SALES_EXECUTIVE",
            "SALES",
            manager_user=self.sales_manager_user,
            manager_emp=self.sales_manager,
        )
        self.sales_exec_other_user, self.sales_exec_other = self._make_person(
            "test_sales_other_owner", "SALES_EXECUTIVE", "SALES"
        )
        self.support_manager_user, self.support_manager = self._make_person(
            "test_support_manager_owner",
            "SUPPORT_MANAGER",
            "SUPPORT",
            manager_user=self.admin_user,
            manager_emp=self.admin_emp,
        )
        self.support_exec_user, self.support_exec = self._make_person(
            "test_support_exec_owner",
            "SUPPORT_EXECUTIVE",
            "SUPPORT",
            manager_user=self.support_manager_user,
            manager_emp=self.support_manager,
        )
        self.support_exec_other_user, self.support_exec_other = self._make_person(
            "test_support_other_owner", "SUPPORT_EXECUTIVE", "SUPPORT"
        )
        # Cross-department reporting link: the Sales manager must not gain
        # visibility of this Support employee's follow-ups through hierarchy.
        self.support_cross_user, self.support_cross = self._make_person(
            "test_support_cross_owner",
            "SUPPORT_EXECUTIVE",
            "SUPPORT",
            manager_user=self.sales_manager_user,
            manager_emp=self.sales_manager,
        )

        self.sales_lead = Lead(
            name="Ownership Sales Lead",
            phone="9100000001",
            status="NEW",
            assigned_to=self.sales_exec.id,
        )
        self.sales_lead_other = Lead(
            name="Ownership Other Sales Lead",
            phone="9100000002",
            status="NEW",
            assigned_to=self.sales_exec_other.id,
        )
        self.support_lead = Lead(
            name="Ownership Support Lead",
            phone="9100000003",
            status="NEW",
            assigned_to=self.support_exec.id,
        )
        self.support_lead_other = Lead(
            name="Ownership Other Support Lead",
            phone="9100000006",
            status="NEW",
            assigned_to=self.support_exec_other.id,
        )
        self.support_cross_lead = Lead(
            name="Ownership Cross Support Lead",
            phone="9100000004",
            status="NEW",
            assigned_to=self.support_cross.id,
        )
        self.handover_lead = Lead(
            name="Ownership Handover Lead",
            phone="9100000005",
            status="NEW",
            assigned_to=self.sales_exec.id,
        )
        self.db.add_all(
            [
                self.sales_lead,
                self.sales_lead_other,
                self.support_lead,
                self.support_lead_other,
                self.support_cross_lead,
                self.handover_lead,
            ]
        )
        self.db.commit()
        for lead in (
            self.sales_lead,
            self.sales_lead_other,
            self.support_lead,
            self.support_lead_other,
            self.support_cross_lead,
            self.handover_lead,
        ):
            self.db.refresh(lead)

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _make_person(
        self,
        username,
        role,
        department,
        manager_user=None,
        manager_emp=None,
    ):
        user = User(
            username=username,
            hashed_password="not-used-in-tests",
            role=role,
            department=department,
            reporting_manager_id=manager_user.id if manager_user else None,
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        employee = Employee(
            user_id=user.id,
            manager_id=manager_emp.id if manager_emp else None,
            reporting_manager_id=manager_user.id if manager_user else None,
            department=department,
            name=username.replace("_", " ").title(),
            email=f"{username}@example.test",
            phone=f"97{user.id:08d}"[:10],
            username=username,
            role=role,
            status="ACTIVE",
        )
        self.db.add(employee)
        self.db.commit()
        self.db.refresh(employee)
        return user, employee

    def _create(self, user, lead, assigned_to=None, notes="ownership test"):
        return create_followup(
            f_in=FollowupCreate(
                lead_id=lead.id,
                assigned_to=assigned_to,
                followup_date=date.today() + timedelta(days=1),
                followup_time="10:00 AM",
                notes=notes,
                priority="MEDIUM",
                status="Pending",
            ),
            db=self.db,
            current_user=user,
        )

    def _list_ids(self, user, department=None, assigned_to=None):
        records = list_followups(
            status_filter=None,
            status=None,
            priority_filter=None,
            priority=None,
            date_filter=None,
            search=None,
            assigned_to_filter=assigned_to,
            assigned_to=None,
            department=department,
            upcoming_only=False,
            db=self.db,
            current_user=user,
        )
        return {record.id for record in records}

    def _stored(self, followup_id):
        self.db.expire_all()
        return (
            self.db.query(Followup)
            .filter(Followup.id == followup_id)
            .first()
        )

    # ------------------------------------------------------------------
    # 1 + 2: creation persists authenticated department ownership
    # ------------------------------------------------------------------
    def test_01_sales_and_support_creation_persist_department_ownership(self):
        sales_out = self._create(self.sales_exec_user, self.sales_lead)
        support_out = self._create(self.support_exec_user, self.support_lead)

        sales = self._stored(sales_out.id)
        support = self._stored(support_out.id)

        self.assertEqual(sales.created_by, self.sales_exec.id)
        self.assertEqual(sales.creator_department, "SALES")
        self.assertEqual(sales.assigned_to, self.sales_exec.id)
        self.assertEqual(sales.assigned_department, "SALES")
        self.assertEqual(sales.owner_department, "SALES")

        self.assertEqual(support.created_by, self.support_exec.id)
        self.assertEqual(support.creator_department, "SUPPORT")
        self.assertEqual(support.assigned_to, self.support_exec.id)
        self.assertEqual(support.assigned_department, "SUPPORT")
        self.assertEqual(support.owner_department, "SUPPORT")

    # ------------------------------------------------------------------
    # 3 + 4: employee visibility is department-isolated
    # ------------------------------------------------------------------
    def test_02_sales_and_support_employees_only_see_their_department(self):
        sales_out = self._create(self.sales_exec_user, self.sales_lead)
        support_out = self._create(self.support_exec_user, self.support_lead)

        self.assertIn(sales_out.id, self._list_ids(self.sales_exec_user))
        self.assertNotIn(support_out.id, self._list_ids(self.sales_exec_user))

        self.assertIn(support_out.id, self._list_ids(self.support_exec_user))
        self.assertNotIn(sales_out.id, self._list_ids(self.support_exec_user))

    # ------------------------------------------------------------------
    # 5 + 6: managers see their own department team only
    # ------------------------------------------------------------------
    def test_03_sales_manager_sees_sales_team_only(self):
        team_out = self._create(self.sales_exec_user, self.sales_lead)
        other_out = self._create(
            self.sales_exec_other_user, self.sales_lead_other
        )
        support_out = self._create(self.support_exec_user, self.support_lead)
        cross_out = self._create(self.support_cross_user, self.support_cross_lead)

        ids = self._list_ids(self.sales_manager_user)
        self.assertIn(team_out.id, ids)
        self.assertNotIn(other_out.id, ids)
        self.assertNotIn(support_out.id, ids)
        self.assertNotIn(cross_out.id, ids)

    def test_04_support_manager_sees_support_team_only(self):
        team_out = self._create(self.support_exec_user, self.support_lead)
        other_out = self._create(
            self.support_exec_other_user, self.support_lead_other
        )
        sales_out = self._create(self.sales_exec_user, self.sales_lead)

        ids = self._list_ids(self.support_manager_user)
        self.assertIn(team_out.id, ids)
        self.assertNotIn(other_out.id, ids)
        self.assertNotIn(sales_out.id, ids)

    # ------------------------------------------------------------------
    # 7: Admin sees both departments and can filter
    # ------------------------------------------------------------------
    def test_05_admin_sees_both_departments_and_filters(self):
        sales_out = self._create(self.sales_exec_user, self.sales_lead)
        support_out = self._create(self.support_exec_user, self.support_lead)

        all_ids = self._list_ids(self.admin_user)
        self.assertIn(sales_out.id, all_ids)
        self.assertIn(support_out.id, all_ids)

        sales_ids = self._list_ids(self.admin_user, department="SALES")
        support_ids = self._list_ids(self.admin_user, department="SUPPORT")
        self.assertIn(sales_out.id, sales_ids)
        self.assertNotIn(support_out.id, sales_ids)
        self.assertIn(support_out.id, support_ids)
        self.assertNotIn(sales_out.id, support_ids)

        with self.assertRaises(HTTPException) as non_admin:
            self._list_ids(self.sales_exec_user, department="SALES")
        self.assertEqual(non_admin.exception.status_code, 403)

        with self.assertRaises(HTTPException) as invalid:
            self._list_ids(self.admin_user, department="FINANCE")
        self.assertEqual(invalid.exception.status_code, 400)

    # ------------------------------------------------------------------
    # 8: direct API tampering is blocked for every endpoint
    # ------------------------------------------------------------------
    def test_06_cross_department_api_access_is_blocked(self):
        sales_out = self._create(self.sales_exec_user, self.sales_lead)
        support_out = self._create(self.support_exec_user, self.support_lead)

        zeroth = date.today() + timedelta(days=2)
        with self.assertRaises(HTTPException) as sales_get:
            get_followup(support_out.id, db=self.db, current_user=self.sales_exec_user)
        self.assertEqual(sales_get.exception.status_code, 403)

        with self.assertRaises(HTTPException) as support_get:
            get_followup(sales_out.id, db=self.db, current_user=self.support_exec_user)
        self.assertEqual(support_get.exception.status_code, 403)

        with self.assertRaises(HTTPException) as sales_update:
            update_followup(
                support_out.id,
                FollowupUpdate(status="Completed"),
                db=self.db,
                current_user=self.sales_exec_user,
            )
        self.assertEqual(sales_update.exception.status_code, 403)

        with self.assertRaises(HTTPException) as support_update:
            update_followup(
                sales_out.id,
                FollowupUpdate(status="Completed"),
                db=self.db,
                current_user=self.support_exec_user,
            )
        self.assertEqual(support_update.exception.status_code, 403)

        with self.assertRaises(HTTPException) as sales_delete:
            delete_followup(
                support_out.id,
                db=self.db,
                current_user=self.sales_exec_user,
            )
        self.assertEqual(sales_delete.exception.status_code, 403)

        with self.assertRaises(HTTPException) as sales_snooze:
            snooze_followup_reminder(
                support_out.id,
                FollowupSnoozeRequest(minutes=15),
                db=self.db,
                current_user=self.sales_exec_user,
            )
        self.assertEqual(sales_snooze.exception.status_code, 403)

        with self.assertRaises(HTTPException) as sales_dismiss:
            dismiss_followup_reminder(
                support_out.id,
                db=self.db,
                current_user=self.sales_exec_user,
            )
        self.assertEqual(sales_dismiss.exception.status_code, 403)

        # A tampered assigned_to filter must not reveal another department.
        self.assertEqual(
            self._list_ids(
                self.sales_exec_user, assigned_to=self.support_exec.id
            ),
            set(),
        )

        self.assertEqual(len(self._list_ids(self.admin_user)), 2)

    def test_07_cross_department_assignment_is_rejected(self):
        with self.assertRaises(HTTPException) as create_cross:
            self._create(
                self.sales_manager_user,
                self.sales_lead,
                assigned_to=self.support_exec.id,
            )
        self.assertEqual(create_cross.exception.status_code, 403)

        sales_out = self._create(self.sales_exec_user, self.sales_lead)
        with self.assertRaises(HTTPException) as update_cross:
            update_followup(
                sales_out.id,
                FollowupUpdate(assigned_to=self.support_exec.id),
                db=self.db,
                current_user=self.sales_manager_user,
            )
        self.assertEqual(update_cross.exception.status_code, 403)

    # ------------------------------------------------------------------
    # 9 + 10: handover preserves history and creates a new Support record
    # ------------------------------------------------------------------
    def test_08_handover_preserves_old_sales_and_creates_new_support(self):
        sales_out = self._create(self.sales_exec_user, self.handover_lead)
        sales_record = self._stored(sales_out.id)
        self.assertEqual(sales_record.owner_department, "SALES")

        # Simulate Support receiving the customer: the lead owner changes, but
        # the existing Sales follow-up must keep its original ownership.
        self.handover_lead.assigned_to = self.support_exec.id
        self.db.commit()

        support_out = self._create(self.support_exec_user, self.handover_lead)

        sales_record = self._stored(sales_out.id)
        support_record = self._stored(support_out.id)
        self.assertIsNotNone(sales_record, "Existing Sales follow-up must not be deleted")
        self.assertEqual(sales_record.owner_department, "SALES")
        self.assertEqual(sales_record.assigned_to, self.sales_exec.id)
        self.assertEqual(support_record.owner_department, "SUPPORT")
        self.assertEqual(support_record.assigned_to, self.support_exec.id)
        self.assertNotEqual(sales_record.id, support_record.id)

        sales_ids = self._list_ids(self.sales_exec_user)
        support_ids = self._list_ids(self.support_exec_user)
        self.assertIn(sales_out.id, sales_ids)
        self.assertNotIn(support_out.id, sales_ids)
        self.assertIn(support_out.id, support_ids)
        self.assertNotIn(sales_out.id, support_ids)

        admin_sales = self._list_ids(self.admin_user, department="SALES")
        admin_support = self._list_ids(self.admin_user, department="SUPPORT")
        self.assertIn(sales_out.id, admin_sales)
        self.assertNotIn(support_out.id, admin_sales)
        self.assertIn(support_out.id, admin_support)
        self.assertNotIn(sales_out.id, admin_support)

    def test_09_backfill_preserves_existing_rows_and_snapshots_creator_ownership(self):
        legacy_sales = Followup(
            lead_id=self.sales_lead.id,
            assigned_to=self.sales_exec.id,
            created_by=self.sales_exec.id,
            followup_date=date.today(),
            followup_time="10:00 AM",
            notes="legacy sales row",
            status="Pending",
        )
        legacy_cross = Followup(
            lead_id=self.sales_lead.id,
            assigned_to=self.sales_exec.id,
            created_by=self.support_exec.id,
            followup_date=date.today(),
            followup_time="11:00 AM",
            notes="legacy support-created row",
            status="Pending",
        )
        self.db.add_all([legacy_sales, legacy_cross])
        self.db.commit()
        self.db.refresh(legacy_sales)
        self.db.refresh(legacy_cross)

        updated = backfill_followup_departments(self.db)
        self.assertGreaterEqual(updated, 2)
        self.assertEqual(self.db.query(Followup).count(), 2)

        legacy_sales = self._stored(legacy_sales.id)
        legacy_cross = self._stored(legacy_cross.id)
        self.assertEqual(legacy_sales.creator_department, "SALES")
        self.assertEqual(legacy_sales.assigned_department, "SALES")
        self.assertEqual(legacy_sales.owner_department, "SALES")
        self.assertEqual(legacy_cross.creator_department, "SUPPORT")
        self.assertEqual(legacy_cross.assigned_department, "SALES")
        self.assertEqual(legacy_cross.owner_department, "SUPPORT")

        # Historical ownership follows the creator, not the lead's owner.
        self.assertIn(legacy_sales.id, self._list_ids(self.sales_exec_user))
        self.assertNotIn(legacy_cross.id, self._list_ids(self.sales_exec_user))
        self.assertIn(legacy_cross.id, self._list_ids(self.support_exec_user))

    def test_10_admin_created_ownership_uses_assignee_department(self):
        out = self._create(
            self.admin_user,
            self.support_lead,
            assigned_to=self.support_exec.id,
        )
        stored = self._stored(out.id)
        self.assertEqual(stored.assigned_department, "SUPPORT")
        self.assertEqual(stored.owner_department, "SUPPORT")

        self.assertIn(out.id, self._list_ids(self.admin_user, department="SUPPORT"))
        self.assertNotIn(out.id, self._list_ids(self.admin_user, department="SALES"))

    def test_11_dashboards_never_leak_other_department_followups(self):
        sales_out = self._create(self.sales_exec_user, self.sales_lead)
        support_out = self._create(self.support_exec_user, self.support_lead)

        sales_dash = dashboard_stats(db=self.db, current_user=self.sales_exec_user)
        sales_upcoming_ids = {item["id"] for item in sales_dash["upcoming_followups"]}
        self.assertIn(sales_out.id, sales_upcoming_ids)
        self.assertNotIn(support_out.id, sales_upcoming_ids)

        support_dash = dashboard_stats(db=self.db, current_user=self.support_exec_user)
        support_upcoming_ids = {item["id"] for item in support_dash["upcoming_followups"]}
        self.assertIn(support_out.id, support_upcoming_ids)
        self.assertNotIn(sales_out.id, support_upcoming_ids)

        support_payload = build_support_dashboard_payload(
            self.support_exec_user,
            self.support_exec,
            self.db,
            "SUPPORT_EXECUTIVE",
        )
        payload_ids = {item["id"] for item in support_payload["upcoming_followups"]}
        self.assertIn(support_out.id, payload_ids)
        self.assertNotIn(sales_out.id, payload_ids)
        self.assertEqual(support_payload["customer_followups"], 1)

    def test_12_admin_reassignment_cannot_transfer_ownership(self):
        support_out = self._create(self.support_exec_user, self.support_lead)

        with self.assertRaises(HTTPException) as cross:
            update_followup(
                support_out.id,
                FollowupUpdate(assigned_to=self.sales_exec.id),
                db=self.db,
                current_user=self.admin_user,
            )
        self.assertEqual(cross.exception.status_code, 403)

        stored = self._stored(support_out.id)
        self.assertEqual(stored.owner_department, "SUPPORT")
        self.assertEqual(stored.assigned_to, self.support_exec.id)

        updated = update_followup(
            support_out.id,
            FollowupUpdate(assigned_to=self.support_exec_other.id),
            db=self.db,
            current_user=self.admin_user,
        )
        self.assertEqual(updated.assigned_to, self.support_exec_other.id)
        stored = self._stored(support_out.id)
        self.assertEqual(stored.assigned_department, "SUPPORT")
        self.assertEqual(stored.owner_department, "SUPPORT")

    def test_13_admin_can_assign_unowned_record_to_a_department(self):
        out = self._create(
            self.admin_user,
            self.sales_lead,
            assigned_to=self.admin_emp.id,
        )
        stored = self._stored(out.id)
        self.assertEqual(stored.owner_department, "ADMINISTRATION")
        self.assertNotIn(out.id, self._list_ids(self.admin_user, department="SALES"))
        self.assertNotIn(out.id, self._list_ids(self.admin_user, department="SUPPORT"))

        update_followup(
            out.id,
            FollowupUpdate(assigned_to=self.sales_exec.id),
            db=self.db,
            current_user=self.admin_user,
        )
        stored = self._stored(out.id)
        self.assertEqual(stored.owner_department, "SALES")
        self.assertEqual(stored.assigned_department, "SALES")
        self.assertIn(out.id, self._list_ids(self.sales_exec_user))


if __name__ == "__main__":
    unittest.main(verbosity=2)
