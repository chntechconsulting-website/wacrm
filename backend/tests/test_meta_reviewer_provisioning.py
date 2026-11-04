"""Tests for the Meta reviewer provisioning script.

These tests use an isolated in-memory SQLite database. They never touch the
live CRM database or WhatsApp number 7547900900.
"""

import os
import sys
import unittest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MIGRATIONS_DIR = os.path.join(BACKEND_DIR, "migrations")
for path in (BACKEND_DIR, MIGRATIONS_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401 - registers every model on Base.metadata
from database import Base
from models.employee import Employee
from models.lead import Lead
from models.user import User
from models.whatsapp import Conversation, WhatsAppMessage
from provision_meta_reviewer import (
    PROTECTED_NUMBER,
    ProvisioningError,
    TEST_LEAD_NOTE,
    _assert_not_protected,
    provision_reviewer,
    seed_review_conversation,
)
from services.auth import hash_password
from services.permission_service import seed_default_roles_if_needed


class MetaReviewerProvisioningTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(
            bind=self.engine, autoflush=False, autocommit=False
        )
        self.db = self.Session()

        admin = User(
            username="admin",
            hashed_password=hash_password("admin-test-password"),
            role="ADMIN",
            department="ADMINISTRATION",
            is_active=True,
        )
        self.db.add(admin)
        self.db.commit()
        self.db.refresh(admin)
        self.db.add(
            Employee(
                user_id=admin.id,
                name="System Administrator",
                email="admin@example.test",
                username="admin",
                role="ADMIN",
                department="ADMINISTRATION",
                status="ACTIVE",
            )
        )
        self.db.commit()
        seed_default_roles_if_needed(self.db)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_provisions_reviewer_under_admin(self):
        user, employee = provision_reviewer(
            self.db,
            username="reviewer",
            email="reviewer@example.test",
            password="strong-review-password",
            name="Meta App Reviewer",
            phone="919800000001",
        )

        self.assertEqual(user.role, "META_REVIEWER")
        self.assertEqual(user.department, "ADMINISTRATION")
        self.assertTrue(user.is_active)
        self.assertEqual(employee.user_id, user.id)
        self.assertEqual(employee.role, "META_REVIEWER")
        self.assertEqual(employee.department, "ADMINISTRATION")
        self.assertEqual(employee.status, "ACTIVE")
        self.assertIsNotNone(employee.reporting_manager_id)
        self.assertIsNotNone(employee.manager_id)

    def test_provisioning_is_idempotent(self):
        provision_reviewer(
            self.db,
            username="reviewer",
            email="reviewer@example.test",
            password="strong-review-password",
            name="Meta App Reviewer",
        )
        provision_reviewer(
            self.db,
            username="reviewer",
            email="reviewer@example.test",
            password="new-strong-review-password",
            name="Meta App Reviewer Updated",
        )

        self.assertEqual(self.db.query(User).filter(User.role == "META_REVIEWER").count(), 1)
        self.assertEqual(
            self.db.query(Employee).filter(Employee.role == "META_REVIEWER").count(), 1
        )

    def test_refuses_to_convert_existing_non_reviewer_account(self):
        self.db.add(
            User(
                username="sales.user",
                hashed_password=hash_password("sales-password"),
                role="SALES_EXECUTIVE",
                department="SALES",
                is_active=True,
            )
        )
        self.db.commit()

        with self.assertRaises(ProvisioningError):
            provision_reviewer(
                self.db,
                username="sales.user",
                email="sales@example.test",
                password="strong-review-password",
                name="Someone Else",
            )

    def test_seeds_assigned_test_conversation_once(self):
        _, reviewer = provision_reviewer(
            self.db,
            username="reviewer",
            email="reviewer@example.test",
            password="strong-review-password",
            name="Meta App Reviewer",
        )

        conversation = seed_review_conversation(
            self.db,
            reviewer=reviewer,
            test_phone="+91 98000 00002",
            test_name="Review Test Contact",
        )

        self.assertEqual(conversation.assigned_to, reviewer.id)
        lead = self.db.query(Lead).filter(Lead.id == conversation.lead_id).first()
        self.assertIsNotNone(lead)
        self.assertEqual(lead.assigned_to, reviewer.id)
        self.assertEqual(lead.requirement_notes, TEST_LEAD_NOTE)
        self.assertEqual(conversation.contact_name, "Review Test Contact")
        self.assertEqual(
            self.db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.conversation_id == conversation.id)
            .count(),
            1,
        )

        again = seed_review_conversation(
            self.db,
            reviewer=reviewer,
            test_phone="919800000002",
            test_name="Review Test Contact",
        )
        self.assertEqual(again.id, conversation.id)
        self.assertEqual(
            self.db.query(Conversation).filter(Conversation.lead_id == lead.id).count(),
            1,
        )
        self.assertEqual(
            self.db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.conversation_id == conversation.id)
            .count(),
            1,
        )

    def test_refuses_protected_live_number(self):
        with self.assertRaises(ProvisioningError):
            _assert_not_protected(PROTECTED_NUMBER, "--test-phone")
        with self.assertRaises(ProvisioningError):
            _assert_not_protected("+91 75479 00900", "--test-phone")

    def test_refuses_real_whatsapp_ads_lead(self):
        _, reviewer = provision_reviewer(
            self.db,
            username="reviewer",
            email="reviewer@example.test",
            password="strong-review-password",
            name="Meta App Reviewer",
        )
        self.db.add(
            Lead(
                name="Real Ad Lead",
                phone="919800000003",
                source="WHATSAPP_ADS",
                status="NEW",
            )
        )
        self.db.commit()

        with self.assertRaises(ProvisioningError):
            seed_review_conversation(
                self.db,
                reviewer=reviewer,
                test_phone="919800000003",
                test_name="Should Not Touch",
                force=True,
            )


if __name__ == "__main__":
    unittest.main()
