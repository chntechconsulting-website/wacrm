import unittest
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import SessionLocal
from models.user import User
from services.hierarchy_service import get_authorized_performance_employee_ids
from fastapi.testclient import TestClient
from main import app
from services.auth import create_access_token

class TestEmployeePerformanceScoping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        cls.client = TestClient(app)
        
        # Look up test users
        cls.admin = cls.db.query(User).filter(User.username == "admin").first()
        cls.sales_manager = cls.db.query(User).filter(User.username == "chnm030").first()
        cls.sales_exec = cls.db.query(User).filter(User.username == "chnm040").first()
        cls.support_manager = cls.db.query(User).filter(User.username == "kumar").first()
        cls.support_exec = cls.db.query(User).filter(User.username == "chnm023").first()
        cls.finance = cls.db.query(User).filter(User.username == "chnm020").first()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def _headers_for(self, user):
        token = create_access_token(data={"sub": user.username, "role": user.role, "user_id": user.id})
        return {"Authorization": f"Bearer {token}"}

    def test_admin_access(self):
        """Admin can view performance metrics for all employees across all departments."""
        allowed = get_authorized_performance_employee_ids(self.admin, self.db)
        self.assertIsNone(allowed, "Admin should have None (unrestricted/company-wide) access")
        
        res = self.client.get("/api/employee-monitoring/employees", headers=self._headers_for(self.admin))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreaterEqual(len(data), 5, "Admin should see all employees")

    def test_sales_manager_access(self):
        """Sales Manager can view only employees belonging to their assigned Sales team."""
        allowed = get_authorized_performance_employee_ids(self.sales_manager, self.db)
        self.assertIsNotNone(allowed)
        self.assertIn(self.sales_manager.id, allowed)
        self.assertIn(self.sales_exec.id, allowed)
        self.assertNotIn(self.support_manager.id, allowed)
        self.assertNotIn(self.support_exec.id, allowed)
        self.assertNotIn(self.finance.id, allowed)
        
        res = self.client.get("/api/employee-monitoring/employees", headers=self._headers_for(self.sales_manager))
        self.assertEqual(res.status_code, 200)
        returned_ids = [e["employee_id"] for e in res.json()]
        self.assertTrue(all(eid in allowed for eid in returned_ids))
        self.assertNotIn(self.support_exec.id, returned_ids)
        self.assertNotIn(self.finance.id, returned_ids)

        # Sales Manager trying to view Support Executive detail
        detail_res = self.client.get(f"/api/employee-monitoring/{self.support_exec.id}", headers=self._headers_for(self.sales_manager))
        self.assertEqual(detail_res.status_code, 403)

    def test_sales_executive_access(self):
        """Sales Executive can view only their own performance metrics."""
        allowed = get_authorized_performance_employee_ids(self.sales_exec, self.db)
        self.assertEqual(allowed, [self.sales_exec.id])

        res = self.client.get("/api/employee-monitoring/employees", headers=self._headers_for(self.sales_exec))
        self.assertEqual(res.status_code, 200)
        returned_ids = [e["employee_id"] for e in res.json()]
        self.assertEqual(returned_ids, [self.sales_exec.id])

        # Trying to view Manager detail
        detail_res = self.client.get(f"/api/employee-monitoring/{self.sales_manager.id}", headers=self._headers_for(self.sales_exec))
        self.assertEqual(detail_res.status_code, 403)

    def test_support_manager_access(self):
        """Support Manager can view only employees in their assigned Support team."""
        allowed = get_authorized_performance_employee_ids(self.support_manager, self.db)
        self.assertIsNotNone(allowed)
        self.assertIn(self.support_manager.id, allowed)
        self.assertIn(self.support_exec.id, allowed)
        self.assertNotIn(self.sales_manager.id, allowed)
        self.assertNotIn(self.sales_exec.id, allowed)
        self.assertNotIn(self.finance.id, allowed)

        res = self.client.get("/api/employee-monitoring/employees", headers=self._headers_for(self.support_manager))
        self.assertEqual(res.status_code, 200)
        returned_ids = [e["employee_id"] for e in res.json()]
        self.assertTrue(all(eid in allowed for eid in returned_ids))
        self.assertNotIn(self.sales_exec.id, returned_ids)

        # Support Manager trying to view Sales Executive detail
        detail_res = self.client.get(f"/api/employee-monitoring/{self.sales_exec.id}", headers=self._headers_for(self.support_manager))
        self.assertEqual(detail_res.status_code, 403)

    def test_support_executive_access(self):
        """Support Executive can view only their own performance metrics."""
        allowed = get_authorized_performance_employee_ids(self.support_exec, self.db)
        self.assertEqual(allowed, [self.support_exec.id])

        res = self.client.get("/api/employee-monitoring/employees", headers=self._headers_for(self.support_exec))
        self.assertEqual(res.status_code, 200)
        returned_ids = [e["employee_id"] for e in res.json()]
        self.assertEqual(returned_ids, [self.support_exec.id])

        # Trying to view Support Manager detail
        detail_res = self.client.get(f"/api/employee-monitoring/{self.support_manager.id}", headers=self._headers_for(self.support_exec))
        self.assertEqual(detail_res.status_code, 403)

    def test_finance_access(self):
        """Finance must follow configured permissions and not see company-wide records."""
        allowed = get_authorized_performance_employee_ids(self.finance, self.db)
        self.assertEqual(allowed, [self.finance.id])

        res = self.client.get("/api/employee-monitoring/employees", headers=self._headers_for(self.finance))
        self.assertEqual(res.status_code, 200)
        returned_ids = [e["employee_id"] for e in res.json()]
        self.assertEqual(returned_ids, [self.finance.id])

        # Finance trying to view Sales Executive detail
        detail_res = self.client.get(f"/api/employee-monitoring/{self.sales_exec.id}", headers=self._headers_for(self.finance))
        self.assertEqual(detail_res.status_code, 403)

if __name__ == "__main__":
    unittest.main()
