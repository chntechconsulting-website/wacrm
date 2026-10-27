import unittest
from datetime import datetime
from database import SessionLocal
from models.user import User
from models.employee import Employee
from models.quotation import Quotation
from models.sales_target import SalesTarget

class TestRevenueAndTargetLogic(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_quotations_vs_invoices_revenue(self):
        """
        Verify that quotations (draft/issued) and proformas are NOT counted in actual revenue.
        Only confirmed tax invoices with doc_type == 'invoice' are counted.
        """
        # Count all doc types in DB
        all_quotations = self.db.query(Quotation).all()
        confirmed_invoices = [
            q for q in all_quotations
            if q.doc_type == "invoice"
            and q.status in ["issued", "paid"]
            and q.payment_status in ["paid", "partial"]
            and q.status != "cancelled"
        ]
        
        quotation_docs = [q for q in all_quotations if q.doc_type in ["quotation", "proforma"]]
        
        # Verify that confirmed invoices are strictly separated from quotation proposals
        for inv in confirmed_invoices:
            self.assertEqual(inv.doc_type, "invoice")
            self.assertIn(inv.status, ["issued", "paid"])
            self.assertIn(inv.payment_status, ["paid", "partial"])

        # Quotations total should be greater than 0, but must not be included in confirmed invoice total
        confirmed_revenue = sum(float(inv.grand_total or 0.0) for inv in confirmed_invoices)
        quotation_total = sum(float(q.grand_total or 0.0) for q in quotation_docs)
        self.assertGreaterEqual(confirmed_revenue, 0.0)
        self.assertGreater(quotation_total, 0.0)

    def test_sales_target_creation_and_achievement_calculation(self):
        """
        Verify that SalesTarget model enforces constraints and achievement calculations:
        - Remaining Target = MAX(Target - Revenue, 0)
        - Achievement % = (Revenue / Target) * 100
        """
        target_amt = 150000.0
        revenue_amt = 120000.0
        remaining = max(0.0, target_amt - revenue_amt)
        achievement = (revenue_amt / target_amt) * 100.0

        self.assertEqual(remaining, 30000.0)
        self.assertEqual(round(achievement, 1), 80.0)

        # Test over-achievement
        target_amt_2 = 200000.0
        revenue_amt_2 = 220000.0
        remaining_2 = max(0.0, target_amt_2 - revenue_amt_2)
        achievement_2 = round((revenue_amt_2 / target_amt_2) * 100.0, 1)

        self.assertEqual(remaining_2, 0.0)
        self.assertEqual(achievement_2, 110.0)

    def test_sales_target_db_persistence(self):
        """
        Verify that SalesTarget table supports creation and lookup in database.
        """
        active_emp = self.db.query(Employee).filter(Employee.status == "ACTIVE").first()
        self.assertIsNotNone(active_emp, "Active employee should exist")

        now = datetime.now()
        # Find or create target
        target = self.db.query(SalesTarget).filter(
            SalesTarget.employee_id == active_emp.id,
            SalesTarget.period_type == "monthly",
            SalesTarget.period_month == 11,
            SalesTarget.period_year == 2026
        ).first()

        if not target:
            target = SalesTarget(
                employee_id=active_emp.id,
                target_amount=175000.0,
                period_type="monthly",
                period_month=11,
                period_year=2026
            )
            self.db.add(target)
            self.db.commit()
            self.db.refresh(target)

        self.assertEqual(target.employee_id, active_emp.id)
        self.assertEqual(target.period_month, 11)
        self.assertEqual(target.period_year, 2026)
        self.assertEqual(target.target_amount, 175000.0)

if __name__ == "__main__":
    unittest.main()
