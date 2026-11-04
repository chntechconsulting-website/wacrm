"""Least-privilege tests for the Meta App Review account."""

import os
import sys
import unittest
from types import SimpleNamespace

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401 - registers every model on Base.metadata
from database import Base
from services.permission_service import (
    get_default_role_permissions,
    get_role_permissions_map,
    seed_default_roles_if_needed,
    user_has_permission,
)
from services.reviewer_access import (
    is_meta_reviewer_role,
    reviewer_request_allowed,
)


class MetaReviewerPermissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=cls.engine)
        cls.Session = sessionmaker(bind=cls.engine, autoflush=False, autocommit=False)

        db = cls.Session()
        try:
            seed_default_roles_if_needed(db)
        finally:
            db.close()

    def test_reviewer_defaults_are_whatsapp_only(self):
        perms = get_default_role_permissions("META_REVIEWER")

        for module, values in perms.items():
            if module in ("whatsapp", "whatsapp_connection"):
                self.assertTrue(values["has_access"], module)
                self.assertTrue(values["can_view"], module)
            else:
                self.assertFalse(values["has_access"], module)
                self.assertFalse(values["can_view"], module)

        self.assertEqual(perms["whatsapp"]["view_scope"], "own")
        self.assertEqual(perms["whatsapp_connection"]["view_scope"], "company")
        self.assertFalse(perms["whatsapp_connection"]["can_edit"])
        self.assertTrue(perms["whatsapp_connection"]["can_create"])

    def test_seeded_reviewer_role_denies_crm_modules(self):
        db = self.Session()
        try:
            perms = get_role_permissions_map("META_REVIEWER", db)
            reviewer = SimpleNamespace(role="META_REVIEWER")

            self.assertTrue(perms["whatsapp"]["has_access"])
            self.assertTrue(perms["whatsapp_connection"]["has_access"])
            self.assertFalse(perms["leads"]["has_access"])
            self.assertFalse(perms["customers"]["has_access"])
            self.assertFalse(perms["users"]["has_access"])
            self.assertFalse(perms["settings"]["has_access"])

            self.assertTrue(
                user_has_permission(reviewer, "whatsapp_connection", "view", db)
            )
            self.assertTrue(
                user_has_permission(reviewer, "whatsapp_connection", "create", db)
            )
            self.assertFalse(
                user_has_permission(reviewer, "whatsapp_connection", "edit", db)
            )
            self.assertFalse(user_has_permission(reviewer, "leads", "view", db))
        finally:
            db.close()

    def test_reviewer_role_detection_is_case_insensitive(self):
        self.assertTrue(is_meta_reviewer_role("META_REVIEWER"))
        self.assertTrue(is_meta_reviewer_role(" meta_reviewer "))
        self.assertFalse(is_meta_reviewer_role("ADMIN"))
        self.assertFalse(is_meta_reviewer_role(None))


class MetaReviewerAllowlistTests(unittest.TestCase):
    def test_allowed_whatsapp_surface(self):
        allowed = [
            ("POST", "/api/auth/login"),
            ("GET", "/api/auth/me"),
            ("POST", "/api/auth/logout"),
            ("GET", "/api/whatsapp/config-status"),
            ("GET", "/api/whatsapp/conversations"),
            ("GET", "/api/whatsapp/conversations/12"),
            ("GET", "/api/whatsapp/conversations/by-lead/7"),
            ("PUT", "/api/whatsapp/conversations/12/read"),
            ("POST", "/api/whatsapp/send-message"),
            ("GET", "/api/whatsapp/coexistence/status"),
            ("GET", "/api/whatsapp/coexistence/events?limit=20"),
            ("GET", "/api/whatsapp/coexistence/templates"),
        ]
        for method, path in allowed:
            self.assertTrue(
                reviewer_request_allowed(method, path),
                f"{method} {path} should be allowed",
            )

    def test_everything_else_is_denied(self):
        denied = [
            ("GET", "/api/leads"),
            ("GET", "/api/leads/stats"),
            ("GET", "/api/customers"),
            ("GET", "/api/users"),
            ("GET", "/api/roles"),
            ("GET", "/api/reports"),
            ("GET", "/api/ivr/calls"),
            ("GET", "/api/notifications"),
            ("GET", "/api/settings"),
            ("POST", "/api/whatsapp/coexistence/exchange"),
            ("POST", "/api/whatsapp/coexistence/refresh"),
            ("POST", "/api/whatsapp/coexistence/sync"),
            ("POST", "/api/whatsapp/coexistence/session-log"),
            ("POST", "/api/whatsapp/coexistence/templates"),
            ("DELETE", "/api/whatsapp/conversations/12"),
        ]
        for method, path in denied:
            self.assertFalse(
                reviewer_request_allowed(method, path),
                f"{method} {path} should be denied",
            )

    def test_preflight_is_always_allowed(self):
        self.assertTrue(reviewer_request_allowed("OPTIONS", "/api/leads"))


if __name__ == "__main__":
    unittest.main()
