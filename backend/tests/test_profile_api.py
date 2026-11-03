"""Isolated tests for the self-service My Profile API.

These tests use an in-memory SQLite database, synthetic employees and a
temporary upload directory. They never connect to the live MySQL CRM database.
"""

import os
import sys
import tempfile
import unittest
from datetime import date, datetime
from unittest.mock import patch

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401 - registers every model on Base.metadata
from config import settings
from database import Base, get_db
from models.audit_log import AuditLog
from models.employee import Employee
from models.team import Team
from models.user import User
from routers.auth import ChangePasswordRequest, change_password, router as auth_router
from routers.profile import router as profile_router
from services.auth import (
    build_user_out,
    create_access_token,
    hash_password,
    verify_password,
)


class ProfileApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.old_upload_dir = settings.UPLOAD_DIR
        settings.UPLOAD_DIR = cls.temp_dir.name

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

        cls.app = FastAPI()
        cls.app.include_router(profile_router, prefix="/api")
        cls.app.include_router(auth_router, prefix="/api")
        cls.app.dependency_overrides[get_db] = override_db
        cls.client = TestClient(cls.app)
        token = create_access_token(
            data={"sub": "jane.doe", "user_id": 1, "employee_id": 20}
        )
        cls.client.headers.update({"Authorization": f"Bearer {token}"})

    @classmethod
    def tearDownClass(cls):
        cls.app.dependency_overrides.clear()
        cls.engine.dispose()
        settings.UPLOAD_DIR = cls.old_upload_dir
        cls.temp_dir.cleanup()

    def setUp(self):
        db = self.Session()
        for model in (AuditLog, Team, Employee, User):
            db.query(model).delete()
        db.commit()

        manager_user = User(
            id=2,
            username="sales.manager",
            hashed_password=hash_password("ManagerPass123"),
            role="SALES_MANAGER",
            department="SALES",
            is_active=True,
            created_at=datetime(2023, 1, 10),
        )
        manager_employee = Employee(
            id=10,
            user_id=2,
            name="Morgan Lee",
            email="morgan.lee@example.com",
            phone="9876500001",
            username="sales.manager",
            role="SALES_MANAGER",
            department="SALES",
            status="ACTIVE",
            created_at=datetime(2023, 1, 10),
        )
        employee = Employee(
            id=20,
            user_id=1,
            manager_id=10,
            reporting_manager_id=2,
            name="Jane Doe",
            email="jane.doe@example.com",
            phone="9876543210",
            username="jane.doe",
            role="SALES_EXECUTIVE",
            department="SALES",
            status="ACTIVE",
            created_at=datetime(2024, 4, 1, 9, 30),
        )
        user = User(
            id=1,
            username="jane.doe",
            hashed_password=hash_password("OldPass123"),
            role="SALES_EXECUTIVE",
            department="SALES",
            reporting_manager_id=2,
            is_active=True,
            created_at=datetime(2024, 4, 1, 9, 30),
            last_login=datetime(2026, 10, 30, 18, 15),
        )
        team = Team(
            id=5,
            name="Enterprise Sales",
            department="SALES",
            manager_id=10,
            status="ACTIVE",
        )

        db.add_all([manager_user, manager_employee, user, employee, team])
        db.commit()
        db.close()

    # ------------------------------------------------------------------ read
    def test_get_profile_returns_dynamic_employee_data(self):
        response = self.client.get("/api/profile")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()

        self.assertEqual(body["employee_id"], 20)
        self.assertEqual(body["name"], "Jane Doe")
        self.assertEqual(body["email"], "jane.doe@example.com")
        self.assertEqual(body["username"], "jane.doe")
        self.assertEqual(body["role_label"], "Sales Executive")
        self.assertEqual(body["designation"], "Sales Executive")
        self.assertEqual(body["department"], "SALES")
        self.assertEqual(body["department_label"], "Sales")
        self.assertEqual(body["team"], "Enterprise Sales")
        self.assertEqual(body["reporting_manager_name"], "Morgan Lee")
        self.assertEqual(body["date_of_joining"], "2024-04-01")
        self.assertEqual(body["employment_status"], "ACTIVE")
        self.assertEqual(body["account_status"], "ACTIVE")
        self.assertEqual(body["last_login"], "2026-10-30T18:15:00")
        self.assertIsNone(body["photo_url"])
        self.assertNotIn("hashed_password", body)
        self.assertNotIn("password", body)

    # ---------------------------------------------------------------- update
    def test_personal_update_persists_only_authorised_fields(self):
        response = self.client.put(
            "/api/profile",
            json={
                "name": "Jane A. Doe",
                "email": "JANE.NEW@EXAMPLE.COM",
                "phone": "+91 98765 12345",
                "date_of_birth": "1996-08-14",
                "gender": "female",
                "address": "12 Mount Road, Chennai",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["name"], "Jane A. Doe")
        self.assertEqual(body["email"], "jane.new@example.com")
        self.assertEqual(body["phone"], "9876512345")
        self.assertEqual(body["date_of_birth"], "1996-08-14")
        self.assertEqual(body["gender"], "Female")
        self.assertEqual(body["address"], "12 Mount Road, Chennai")

        db = self.Session()
        try:
            employee = db.query(Employee).filter(Employee.id == 20).one()
            user = db.query(User).filter(User.id == 1).one()
            self.assertEqual(employee.name, "Jane A. Doe")
            self.assertEqual(employee.email, "jane.new@example.com")
            self.assertEqual(employee.phone, "9876512345")
            self.assertEqual(employee.date_of_birth, date(1996, 8, 14))
            self.assertEqual(employee.gender, "Female")
            self.assertEqual(employee.department, "SALES")
            self.assertEqual(employee.role, "SALES_EXECUTIVE")
            self.assertEqual(employee.status, "ACTIVE")
            self.assertEqual(user.department, "SALES")
            self.assertEqual(user.role, "SALES_EXECUTIVE")
        finally:
            db.close()

    def test_profile_update_rejects_employment_and_permission_fields(self):
        forbidden_values = {
            "employee_id": 999,
            "department": "ADMINISTRATION",
            "role": "ADMIN",
            "status": "INACTIVE",
            "permissions": {"*": True},
            "reporting_manager_id": 1,
        }

        for field, value in forbidden_values.items():
            with self.subTest(field=field):
                response = self.client.put("/api/profile", json={field: value})
                self.assertEqual(response.status_code, 422, response.text)

        db = self.Session()
        try:
            employee = db.query(Employee).filter(Employee.id == 20).one()
            user = db.query(User).filter(User.id == 1).one()
            self.assertEqual(employee.department, "SALES")
            self.assertEqual(employee.role, "SALES_EXECUTIVE")
            self.assertEqual(employee.status, "ACTIVE")
            self.assertEqual(user.role, "SALES_EXECUTIVE")
            self.assertTrue(user.is_active)
        finally:
            db.close()

    def test_profile_update_rejects_duplicate_email(self):
        db = self.Session()
        db.add(
            Employee(
                id=21,
                name="Existing Person",
                email="taken@example.com",
                username="existing.person",
                role="SALES_EXECUTIVE",
                department="SALES",
                status="ACTIVE",
            )
        )
        db.commit()
        db.close()

        response = self.client.put(
            "/api/profile", json={"email": "TAKEN@example.com"}
        )
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("already registered", response.json()["detail"].lower())

    def test_profile_update_validates_personal_fields(self):
        future_dob = self.client.put(
            "/api/profile", json={"date_of_birth": "2999-01-01"}
        )
        self.assertEqual(future_dob.status_code, 422, future_dob.text)

        invalid_gender = self.client.put(
            "/api/profile", json={"gender": "Unknown"}
        )
        self.assertEqual(invalid_gender.status_code, 422, invalid_gender.text)

        blank_name = self.client.put("/api/profile", json={"name": "   "})
        self.assertEqual(blank_name.status_code, 422, blank_name.text)

        invalid_phone = self.client.put("/api/profile", json={"phone": "12"})
        self.assertEqual(invalid_phone.status_code, 422, invalid_phone.text)

    # ----------------------------------------------------------------- photo
    def test_photo_upload_updates_profile_and_auth_avatar(self):
        response = self.client.post(
            "/api/profile/photo",
            files={
                "file": (
                    "avatar.png",
                    b"\x89PNG\r\n\x1a\n" + b"x" * 128,
                    "image/png",
                )
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        photo_url = response.json()["photo_url"]
        self.assertTrue(photo_url.startswith("/uploads/profiles/20/"), photo_url)

        stored_path = os.path.join(
            settings.UPLOAD_DIR, *photo_url.replace("/uploads/", "").split("/")
        )
        self.assertTrue(os.path.exists(stored_path), stored_path)

        db = self.Session()
        try:
            employee = db.query(Employee).filter(Employee.id == 20).one()
            user = db.query(User).filter(User.id == 1).one()
            self.assertEqual(employee.photo_url, photo_url)
            auth_payload = build_user_out(user, db)
            self.assertEqual(auth_payload.photo_url, photo_url)
            self.assertEqual(auth_payload.employee_name, "Jane Doe")
        finally:
            db.close()

    def test_replacing_photo_removes_previous_upload(self):
        first = self.client.post(
            "/api/profile/photo",
            files={
                "file": (
                    "first.jpg",
                    b"\xff\xd8\xff\xe0" + b"a" * 64,
                    "image/jpeg",
                )
            },
        )
        self.assertEqual(first.status_code, 201, first.text)
        first_url = first.json()["photo_url"]
        first_path = os.path.join(
            settings.UPLOAD_DIR, *first_url.replace("/uploads/", "").split("/")
        )
        self.assertTrue(os.path.exists(first_path))

        second = self.client.post(
            "/api/profile/photo",
            files={
                "file": (
                    "second.jpg",
                    b"\xff\xd8\xff\xe0" + b"b" * 64,
                    "image/jpeg",
                )
            },
        )
        self.assertEqual(second.status_code, 201, second.text)
        self.assertNotEqual(first_url, second.json()["photo_url"])
        self.assertFalse(os.path.exists(first_path))

    def test_photo_url_propagates_to_other_employee_avatar_surfaces(self):
        from services.department_service import _employee_payload
        from services.team_insights_service import _employee_row_base

        photo_url = "/uploads/profiles/20/avatar_test.png"
        db = self.Session()
        try:
            employee = db.query(Employee).filter(Employee.id == 20).one()
            employee.photo_url = photo_url
            db.commit()

            admin_payload = _employee_payload(db, employee)
            insights_row = _employee_row_base(employee)

            self.assertEqual(admin_payload["photo_url"], photo_url)
            self.assertEqual(insights_row["photo_url"], photo_url)
        finally:
            db.close()

    def test_photo_upload_rejects_invalid_and_oversized_files(self):
        invalid_type = self.client.post(
            "/api/profile/photo",
            files={"file": ("avatar.txt", b"not an image", "text/plain")},
        )
        self.assertEqual(invalid_type.status_code, 422, invalid_type.text)

        spoofed = self.client.post(
            "/api/profile/photo",
            files={"file": ("avatar.jpg", b"not really a jpeg", "image/jpeg")},
        )
        self.assertEqual(spoofed.status_code, 422, spoofed.text)

        with patch("routers.profile._MAX_PROFILE_PHOTO_BYTES", 1024):
            oversized = self.client.post(
                "/api/profile/photo",
                files={
                    "file": (
                        "avatar.png",
                        b"\x89PNG\r\n\x1a\n" + b"x" * 2048,
                        "image/png",
                    )
                },
            )
        self.assertEqual(oversized.status_code, 413, oversized.text)

    # -------------------------------------------------------------- password
    def test_password_change_uses_existing_bcrypt_flow(self):
        db = self.Session()
        try:
            user = db.query(User).filter(User.id == 1).one()

            with self.assertRaises(HTTPException) as wrong:
                change_password(
                    ChangePasswordRequest(
                        current_password="WrongPass123",
                        new_password="NewPass456",
                    ),
                    current_user=user,
                    db=db,
                )
            self.assertEqual(wrong.exception.status_code, 400)

            with self.assertRaises(HTTPException) as short:
                change_password(
                    ChangePasswordRequest(
                        current_password="OldPass123",
                        new_password="12345",
                    ),
                    current_user=user,
                    db=db,
                )
            self.assertEqual(short.exception.status_code, 400)

            result = change_password(
                ChangePasswordRequest(
                    current_password="OldPass123",
                    new_password="NewPass456",
                ),
                current_user=user,
                db=db,
            )
            self.assertIn("successfully", result["message"].lower())

            db.refresh(user)
            self.assertTrue(verify_password("NewPass456", user.hashed_password))
            self.assertFalse(verify_password("OldPass123", user.hashed_password))
            self.assertNotIn("NewPass456", user.hashed_password)
        finally:
            db.close()

    def test_password_change_endpoint_contract_used_by_profile_page(self):
        wrong = self.client.post(
            "/api/auth/change-password",
            json={
                "current_password": "WrongPass123",
                "new_password": "NewPass456",
            },
        )
        self.assertEqual(wrong.status_code, 400, wrong.text)
        self.assertIn("incorrect", wrong.json()["detail"].lower())

        success = self.client.post(
            "/api/auth/change-password",
            json={
                "current_password": "OldPass123",
                "new_password": "NewPass456",
            },
        )
        self.assertEqual(success.status_code, 200, success.text)
        self.assertIn("successfully", success.json()["message"].lower())

        db = self.Session()
        try:
            user = db.query(User).filter(User.id == 1).one()
            self.assertTrue(verify_password("NewPass456", user.hashed_password))
            self.assertFalse(verify_password("OldPass123", user.hashed_password))
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
