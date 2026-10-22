import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base
from models.user import User
from models.employee import Employee
from models.role import Role
from services.auth import hash_password, build_user_out
from services.hierarchy_service import (
    normalize_role,
    normalize_department,
    get_department_for_role,
    validate_department_and_role,
    validate_reporting_manager,
    get_eligible_managers,
    ROLE_ADMIN,
    ROLE_SALES_MANAGER,
    ROLE_SALES_EXECUTIVE,
    ROLE_SUPPORT_MANAGER,
    ROLE_SUPPORT_EXECUTIVE,
    DEPT_ADMINISTRATION,
    DEPT_SALES,
    DEPT_SUPPORT,
    DEPT_FINANCE
)

test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

class TestDepartmentHierarchy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=test_engine)
        cls.db = TestingSessionLocal()

        # Seed Admin
        cls.admin_user = User(
            username="admin_test",
            hashed_password=hash_password("admin123"),
            role=ROLE_ADMIN,
            department=DEPT_ADMINISTRATION,
            reporting_manager_id=None,
            is_active=True
        )
        cls.db.add(cls.admin_user)
        cls.db.commit()
        cls.db.refresh(cls.admin_user)

        admin_emp = Employee(
            user_id=cls.admin_user.id,
            name="Admin Test",
            email="admin@test.com",
            username="admin_test",
            role=ROLE_ADMIN,
            department=DEPT_ADMINISTRATION,
            status="ACTIVE"
        )
        cls.db.add(admin_emp)

        # Seed Sales Manager
        cls.sales_mgr = User(
            username="sales_mgr_test",
            hashed_password=hash_password("mgr123"),
            role=ROLE_SALES_MANAGER,
            department=DEPT_SALES,
            reporting_manager_id=cls.admin_user.id,
            is_active=True
        )
        cls.db.add(cls.sales_mgr)
        cls.db.commit()
        cls.db.refresh(cls.sales_mgr)

        sm_emp = Employee(
            user_id=cls.sales_mgr.id,
            name="Sales Mgr Test",
            email="sm@test.com",
            username="sales_mgr_test",
            role=ROLE_SALES_MANAGER,
            department=DEPT_SALES,
            status="ACTIVE",
            reporting_manager_id=cls.admin_user.id
        )
        cls.db.add(sm_emp)

        # Seed Support Manager
        cls.supp_mgr = User(
            username="supp_mgr_test",
            hashed_password=hash_password("supp123"),
            role=ROLE_SUPPORT_MANAGER,
            department=DEPT_SUPPORT,
            reporting_manager_id=cls.admin_user.id,
            is_active=True
        )
        cls.db.add(cls.supp_mgr)
        cls.db.commit()
        cls.db.refresh(cls.supp_mgr)

        sp_emp = Employee(
            user_id=cls.supp_mgr.id,
            name="Support Mgr Test",
            email="sp@test.com",
            username="supp_mgr_test",
            role=ROLE_SUPPORT_MANAGER,
            department=DEPT_SUPPORT,
            status="ACTIVE",
            reporting_manager_id=cls.admin_user.id
        )
        cls.db.add(sp_emp)
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        Base.metadata.drop_all(bind=test_engine)

    def test_department_normalization(self):
        self.assertEqual(normalize_department("admin"), DEPT_ADMINISTRATION)
        self.assertEqual(normalize_department("Administration"), DEPT_ADMINISTRATION)
        self.assertEqual(normalize_department("sales"), DEPT_SALES)
        self.assertEqual(normalize_department("SUPPORT"), DEPT_SUPPORT)
        self.assertEqual(normalize_department("Finance"), DEPT_FINANCE)

    def test_department_role_mapping(self):
        self.assertEqual(get_department_for_role("ADMIN"), DEPT_ADMINISTRATION)
        self.assertEqual(get_department_for_role("SALES_EXECUTIVE"), DEPT_SALES)
        self.assertEqual(get_department_for_role("SALES_MANAGER"), DEPT_SALES)
        self.assertEqual(get_department_for_role("SUPPORT_EXECUTIVE"), DEPT_SUPPORT)
        self.assertEqual(get_department_for_role("SUPPORT_MANAGER"), DEPT_SUPPORT)
        self.assertEqual(get_department_for_role("FINANCE"), DEPT_FINANCE)

    def test_department_and_role_validation(self):
        # Valid pairings
        ok, err = validate_department_and_role("Sales", "SALES_EXECUTIVE")
        self.assertTrue(ok)
        self.assertIsNone(err)

        ok, err = validate_department_and_role("Sales", "SALES_MANAGER")
        self.assertTrue(ok)

        ok, err = validate_department_and_role("Support", "SUPPORT_EXECUTIVE")
        self.assertTrue(ok)

        ok, err = validate_department_and_role("Finance", "FINANCE")
        self.assertTrue(ok)

        # Invalid pairing: Support Executive in Sales department
        ok, err = validate_department_and_role("Sales", "SUPPORT_EXECUTIVE")
        self.assertFalse(ok)
        self.assertIn("not valid for department", err)

        # Invalid pairing: Sales Executive in Support department
        ok, err = validate_department_and_role("Support", "SALES_EXECUTIVE")
        self.assertFalse(ok)
        self.assertIn("not valid for department", err)

        # Missing department
        ok, err = validate_department_and_role("", "SALES_EXECUTIVE")
        self.assertFalse(ok)
        self.assertIn("required", err.lower())

    def test_reporting_manager_logic(self):
        # Sales Executive must report to an active Sales Manager in Sales
        ok, err = validate_reporting_manager(None, ROLE_SALES_EXECUTIVE, DEPT_SALES, self.sales_mgr.id, self.db)
        self.assertTrue(ok)

        # Sales Executive cannot report to Support Manager
        ok, err = validate_reporting_manager(None, ROLE_SALES_EXECUTIVE, DEPT_SALES, self.supp_mgr.id, self.db)
        self.assertFalse(ok)
        self.assertIn("Sales Manager", err)

        # Support Executive must report to Support Manager
        ok, err = validate_reporting_manager(None, ROLE_SUPPORT_EXECUTIVE, DEPT_SUPPORT, self.supp_mgr.id, self.db)
        self.assertTrue(ok)

        # Support Executive cannot report to Sales Manager
        ok, err = validate_reporting_manager(None, ROLE_SUPPORT_EXECUTIVE, DEPT_SUPPORT, self.sales_mgr.id, self.db)
        self.assertFalse(ok)

        # Sales Manager must report to Admin
        ok, err = validate_reporting_manager(None, ROLE_SALES_MANAGER, DEPT_SALES, self.admin_user.id, self.db)
        self.assertTrue(ok)

        # Admin does not require reporting manager
        ok, err = validate_reporting_manager(None, ROLE_ADMIN, DEPT_ADMINISTRATION, None, self.db)
        self.assertTrue(ok)

    def test_get_eligible_managers(self):
        # Sales Executive eligible managers should ONLY include active Sales Manager(s)
        se_managers = get_eligible_managers(ROLE_SALES_EXECUTIVE, DEPT_SALES, db=self.db)
        se_roles = [m["role"] for m in se_managers]
        self.assertTrue(all(r == ROLE_SALES_MANAGER for r in se_roles))
        self.assertGreaterEqual(len(se_managers), 1)

        # Support Executive eligible managers should ONLY include active Support Manager(s)
        sp_managers = get_eligible_managers(ROLE_SUPPORT_EXECUTIVE, DEPT_SUPPORT, db=self.db)
        sp_roles = [m["role"] for m in sp_managers]
        self.assertTrue(all(r == ROLE_SUPPORT_MANAGER for r in sp_roles))
        self.assertGreaterEqual(len(sp_managers), 1)

        # Admin has no eligible managers (top of hierarchy)
        admin_managers = get_eligible_managers(ROLE_ADMIN, DEPT_ADMINISTRATION, db=self.db)
        self.assertEqual(len(admin_managers), 0)

    def test_build_user_out_includes_department(self):
        user_out = build_user_out(self.admin_user, self.db)
        self.assertEqual(user_out.department, DEPT_ADMINISTRATION)
        self.assertEqual(user_out.role, ROLE_ADMIN)

if __name__ == "__main__":
    unittest.main()
