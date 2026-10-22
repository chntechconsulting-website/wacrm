import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.abspath('backend'))

from database import SessionLocal
from models.user import User
from models.employee import Employee
from models.lead import Lead
from models.quotation import Quotation
from integrations.waquote.router import (
    get_waquote_summary,
    list_waquote_documents,
    get_waquote_document,
    create_document,
    update_waquote_document,
    generate_proforma_from_quotation,
    download_quotation_pdf,
    CreateDocumentRequest
)
from fastapi import HTTPException

class TestBillingVisibilityAndCalculations(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()

        self.admin_user = self.db.query(User).filter(User.username == "admin").first()
        self.mgr_user = self.db.query(User).filter(User.username == "chnm030").first() # Gowtham (Sales Manager)
        self.exec_a_user = self.db.query(User).filter(User.username == "chnm040").first() # Chandra Mohan (Sales Exec in Gowtham's team)
        self.exec_b_user = self.db.query(User).filter(User.username == "test_other").first() # Carol (Sales Exec in outside team)
        self.support_user = self.db.query(User).filter(User.username == "chnm023").first() # ram (Support Exec)
        self.finance_user = self.db.query(User).filter(User.username == "chnm020").first() # april (Finance)

        self.assertIsNotNone(self.admin_user)
        self.assertIsNotNone(self.mgr_user)
        self.assertIsNotNone(self.exec_a_user)
        self.assertIsNotNone(self.exec_b_user)
        self.assertIsNotNone(self.support_user)
        self.assertIsNotNone(self.finance_user)

        self.emp_mgr = self.db.query(Employee).filter(Employee.user_id == self.mgr_user.id).first()
        self.emp_a = self.db.query(Employee).filter(Employee.user_id == self.exec_a_user.id).first()
        self.emp_b = self.db.query(Employee).filter(Employee.user_id == self.exec_b_user.id).first()
        self.emp_support = self.db.query(Employee).filter(Employee.user_id == self.support_user.id).first()
        self.emp_finance = self.db.query(Employee).filter(Employee.user_id == self.finance_user.id).first()

        # Clean up any test quotations from previous runs
        self.db.query(Quotation).filter(Quotation.notes.like("%[TEST-BILLING]%")).delete()
        self.db.commit()

        # Ensure leads for Exec A and Exec B exist
        self.lead_a = self.db.query(Lead).filter(Lead.assigned_to == self.emp_a.id).first()
        if not self.lead_a:
            self.lead_a = Lead(name="Test Client A", phone="9111111111", assigned_to=self.emp_a.id, status="NEW")
            self.db.add(self.lead_a)
            self.db.commit()
            self.db.refresh(self.lead_a)

        self.lead_b = self.db.query(Lead).filter(Lead.assigned_to == self.emp_b.id).first()
        if not self.lead_b:
            self.lead_b = Lead(name="Test Client B", phone="9222222222", assigned_to=self.emp_b.id, status="NEW")
            self.db.add(self.lead_b)
            self.db.commit()
            self.db.refresh(self.lead_b)

    def tearDown(self):
        self.db.query(Quotation).filter(Quotation.notes.like("%[TEST-BILLING]%")).delete()
        self.db.commit()
        self.db.close()

    def test_01_employee_a_and_b_quotation_creation_and_isolation(self):
        """
        Step 1 & 2:
        - Employee A creates a quotation worth ₹10,000.
        - Employee B creates a quotation worth ₹5,000.
        - Employee A must see ONLY their ₹10,000 quotation.
        - Employee B must see ONLY their ₹5,000 quotation.
        """
        # Exec A creates ₹10,000 quotation
        req_a = CreateDocumentRequest(
            doc_type="quotation",
            lead_id=self.lead_a.id,
            customer_name="Client A Enterprise",
            grand_total=10000.0,
            subtotal=8474.58,
            tax_total=1525.42,
            notes="[TEST-BILLING] Quote A 10k"
        )
        res_a = create_document(req_a, db=self.db, current_user=self.exec_a_user)
        quote_a_id = res_a["document"]["rawId"]
        self.assertIsNotNone(quote_a_id)

        # Exec B creates ₹5,000 quotation
        req_b = CreateDocumentRequest(
            doc_type="quotation",
            lead_id=self.lead_b.id,
            customer_name="Client B Solutions",
            grand_total=5000.0,
            subtotal=4237.29,
            tax_total=762.71,
            notes="[TEST-BILLING] Quote B 5k"
        )
        res_b = create_document(req_b, db=self.db, current_user=self.exec_b_user)
        quote_b_id = res_b["document"]["rawId"]
        self.assertIsNotNone(quote_b_id)

        # Verify created_by association
        doc_a_db = self.db.query(Quotation).filter(Quotation.id == quote_a_id).first()
        self.assertEqual(doc_a_db.created_by, self.emp_a.id)
        self.assertEqual(doc_a_db.created_by_user_id, self.exec_a_user.id)

        doc_b_db = self.db.query(Quotation).filter(Quotation.id == quote_b_id).first()
        self.assertEqual(doc_b_db.created_by, self.emp_b.id)
        self.assertEqual(doc_b_db.created_by_user_id, self.exec_b_user.id)

        # Exec A lists documents: must see A, must NOT see B
        docs_a = list_waquote_documents(db=self.db, current_user=self.exec_a_user)["documents"]
        doc_ids_a = [d["rawId"] for d in docs_a]
        self.assertIn(quote_a_id, doc_ids_a)
        self.assertNotIn(quote_b_id, doc_ids_a)

        # Exec B lists documents: must see B, must NOT see A
        docs_b = list_waquote_documents(db=self.db, current_user=self.exec_b_user)["documents"]
        doc_ids_b = [d["rawId"] for d in docs_b]
        self.assertIn(quote_b_id, doc_ids_b)
        self.assertNotIn(quote_a_id, doc_ids_b)

        # Exec A checks summary: must NOT include B's quotation
        summary_a = get_waquote_summary(db=self.db, current_user=self.exec_a_user)["metrics"]
        self.assertEqual(summary_a["financials"]["totalBilled"], 0.0) # Quotations are not billed!
        self.assertGreaterEqual(summary_a["quotations"]["totalCount"], 1)

    def test_02_sales_manager_team_scoping(self):
        """
        Step 3:
        Sales Manager sees team records (Exec A) but NOT outside team records (Exec B).
        """
        req_a = CreateDocumentRequest(
            doc_type="quotation",
            lead_id=self.lead_a.id,
            customer_name="Client A Team Doc",
            grand_total=10000.0,
            notes="[TEST-BILLING] Team Quote"
        )
        res_a = create_document(req_a, db=self.db, current_user=self.exec_a_user)
        quote_a_id = res_a["document"]["rawId"]

        req_b = CreateDocumentRequest(
            doc_type="quotation",
            lead_id=self.lead_b.id,
            customer_name="Client B Outside Team",
            grand_total=5000.0,
            notes="[TEST-BILLING] Outside Team Quote"
        )
        res_b = create_document(req_b, db=self.db, current_user=self.exec_b_user)
        quote_b_id = res_b["document"]["rawId"]

        mgr_docs = list_waquote_documents(db=self.db, current_user=self.mgr_user)["documents"]
        mgr_doc_ids = [d["rawId"] for d in mgr_docs]

        self.assertIn(quote_a_id, mgr_doc_ids, "Sales Manager must see team subordinate's quotation")
        self.assertNotIn(quote_b_id, mgr_doc_ids, "Sales Manager must NOT see quotation from outside team rep")

    def test_03_support_users_blocked_from_sales_billing(self):
        """
        Step 4: Support users must not access Sales billing documents.
        """
        with self.assertRaises(HTTPException) as cm_summary:
            get_waquote_summary(db=self.db, current_user=self.support_user)
        self.assertEqual(cm_summary.exception.status_code, 403)

        with self.assertRaises(HTTPException) as cm_docs:
            list_waquote_documents(db=self.db, current_user=self.support_user)
        self.assertEqual(cm_docs.exception.status_code, 403)

    def test_04_direct_api_access_control_and_tampering(self):
        """
        Direct ID manipulation attempts by unauthorized employee must fail with 403 Forbidden.
        """
        req_a = CreateDocumentRequest(
            doc_type="quotation",
            lead_id=self.lead_a.id,
            customer_name="Client A Private",
            grand_total=10000.0,
            notes="[TEST-BILLING] Private Doc"
        )
        res_a = create_document(req_a, db=self.db, current_user=self.exec_a_user)
        quote_a_id = res_a["document"]["rawId"]

        # 1. Exec B attempts GET /documents/{id}
        with self.assertRaises(HTTPException) as cm_get:
            get_waquote_document(str(quote_a_id), db=self.db, current_user=self.exec_b_user)
        self.assertEqual(cm_get.exception.status_code, 403)

        # 2. Exec B attempts PUT /documents/{id}
        with self.assertRaises(HTTPException) as cm_put:
            update_waquote_document(
                str(quote_a_id),
                payload=CreateDocumentRequest(customer_name="Hacked Name", grand_total=1.0),
                db=self.db,
                current_user=self.exec_b_user
            )
        self.assertEqual(cm_put.exception.status_code, 403)

        # 3. Exec B attempts to download Exec A's quotation PDF
        with self.assertRaises(HTTPException) as cm_dl:
            download_quotation_pdf(str(quote_a_id), db=self.db, current_user=self.exec_b_user)
        self.assertEqual(cm_dl.exception.status_code, 403)

        # 4. Exec B attempts to generate proforma from Exec A's quotation
        with self.assertRaises(HTTPException) as cm_gen:
            generate_proforma_from_quotation(str(quote_a_id), db=self.db, current_user=self.exec_b_user)
        self.assertEqual(cm_gen.exception.status_code, 403)

    def test_05_finance_and_admin_authorized_scopes(self):
        """
        Step 5 & 6:
        Finance & Admin have company-wide visibility.
        Only Finance / Admin can create Tax Invoices.
        """
        # Admin can view all documents
        admin_docs = list_waquote_documents(db=self.db, current_user=self.admin_user)
        self.assertTrue(admin_docs["ok"])

        # Finance can view all documents
        fin_docs = list_waquote_documents(db=self.db, current_user=self.finance_user)
        self.assertTrue(fin_docs["ok"])

        # Sales Exec attempting to create Tax Invoice directly receives 403
        with self.assertRaises(HTTPException) as cm_inv:
            create_document(
                CreateDocumentRequest(
                    doc_type="invoice",
                    customer_name="Forbidden Invoice Client",
                    grand_total=15000.0,
                    notes="[TEST-BILLING] Attempted invoice"
                ),
                db=self.db,
                current_user=self.exec_a_user
            )
        self.assertEqual(cm_inv.exception.status_code, 403)

        # Finance CAN create Tax Invoice
        res_inv = create_document(
            CreateDocumentRequest(
                doc_type="invoice",
                customer_name="Finance Official Client",
                grand_total=15000.0,
                amount_paid=15000.0,
                payment_status="paid",
                status="issued",
                notes="[TEST-BILLING] Finance Invoice"
            ),
            db=self.db,
            current_user=self.finance_user
        )
        self.assertTrue(res_inv["ok"])

    def test_06_summary_cards_calculations_and_double_counting_prevention(self):
        """
        Step 7:
        Verify summary card metrics:
        - Quotations do not count towards Total Billed or Total Paid.
        - When a Proforma has an issued Tax Invoice for the same deal/source,
          it is NOT double-counted.
        - Outstanding Balance reflects unpaid amount correctly.
        """
        # Create an authorized quotation for Exec A
        q_res = create_document(
            CreateDocumentRequest(
                doc_type="quotation",
                lead_id=self.lead_a.id,
                customer_name="Test Metric Client",
                grand_total=20000.0,
                notes="[TEST-BILLING] Quote 20k"
            ),
            db=self.db,
            current_user=self.exec_a_user
        )
        q_id = q_res["document"]["rawId"]

        # Generate Proforma from Quotation (grand_total = 20000)
        pf_res = generate_proforma_from_quotation(str(q_id), db=self.db, current_user=self.exec_a_user)
        pf_id = pf_res["document"]["rawId"]

        summary = get_waquote_summary(db=self.db, current_user=self.exec_a_user)["metrics"]
        # Now proforma is issued (20,000 billed, 0 paid, 20,000 outstanding)
        self.assertIn(summary["financials"]["totalBilled"], [20000.0])
        self.assertEqual(summary["financials"]["totalPaid"], 0.0)
        self.assertEqual(summary["financials"]["totalOutstanding"], 20000.0)

        # Now Finance issues Tax Invoice linked to this source quotation with 20,000 paid
        inv = Quotation(
            doc_type="invoice",
            doc_number="CHN/INV/TEST/0099",
            status="issued",
            payment_status="paid",
            source_quotation_id=pf_id,
            source_quotation_number=pf_res["document"]["number"],
            lead_id=self.lead_a.id,
            customer_name="Test Metric Client",
            grand_total=20000.0,
            amount_paid=20000.0,
            created_by=self.emp_a.id,
            created_by_user_id=self.exec_a_user.id,
            assigned_to=self.emp_a.id,
            notes="[TEST-BILLING] Tax Invoice 20k Paid"
        )
        self.db.add(inv)
        self.db.commit()

        # Check summary again: Total Billed must NOT be 40,000 (no double counting)!
        # It must be 20,000 billed, 20,000 paid, 0 outstanding.
        summary_after_inv = get_waquote_summary(db=self.db, current_user=self.exec_a_user)["metrics"]
        self.assertEqual(summary_after_inv["financials"]["totalBilled"], 20000.0)
        self.assertEqual(summary_after_inv["financials"]["totalPaid"], 20000.0)
        self.assertEqual(summary_after_inv["financials"]["totalOutstanding"], 0.0)

if __name__ == "__main__":
    unittest.main()
