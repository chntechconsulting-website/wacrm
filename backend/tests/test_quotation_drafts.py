import os
import sys
import unittest

sys.path.insert(0, os.path.abspath('backend'))

from database import SessionLocal
from models.activity import LeadActivity
from models.audit_log import AuditLog
from models.lead import Lead
from models.quotation import Quotation
from models.user import User
from integrations.waquote.router import (
    CreateDocumentRequest,
    create_document,
    get_waquote_document,
    list_waquote_documents,
    update_waquote_document,
)

MARKER = "[TEST-DRAFT-FLOW]"


class TestQuotationDraftFlow(unittest.TestCase):
    """Proves that Save Draft persists, lists, reopens and updates without duplicates."""

    def setUp(self):
        self.db = SessionLocal()
        self.admin_user = self.db.query(User).filter(User.username == "admin").first()
        self.assertIsNotNone(self.admin_user)
        self._cleanup()

    def tearDown(self):
        self._cleanup()
        self.db.close()

    def _cleanup(self):
        draft_ids = [
            str(row.id) for row in self.db.query(Quotation.id).filter(
                Quotation.notes.like(f"%{MARKER}%")
            ).all()
        ]
        if draft_ids:
            self.db.query(AuditLog).filter(
                AuditLog.entity_type == "QUOTATION",
                AuditLog.entity_id.in_(draft_ids),
            ).delete(synchronize_session=False)
        self.db.query(Quotation).filter(
            Quotation.notes.like(f"%{MARKER}%")
        ).delete(synchronize_session=False)
        lead_ids = [
            row.id for row in self.db.query(Lead.id).filter(
                Lead.name.like(f"%{MARKER}%")
            ).all()
        ]
        if lead_ids:
            self.db.query(LeadActivity).filter(
                LeadActivity.lead_id.in_(lead_ids)
            ).delete(synchronize_session=False)
            self.db.query(Lead).filter(
                Lead.id.in_(lead_ids)
            ).delete(synchronize_session=False)
        self.db.commit()

    def _draft_request(self, **overrides):
        payload = {
            "doc_type": "quotation",
            "status": "draft",
            "selected_bundle": "hr_atm",
            "product_category": "wahrms",
            "customer_name": "Draft Flow Customer",
            "company_name": "Draft Flow Industries",
            "phone": "9000012345",
            "email": "draft.flow@example.com",
            "address": "12 Test Street, Chennai",
            "state": "Tamil Nadu",
            "state_code": "33",
            "gstin": "33ABCDE1234F1Z5",
            "tax_mode": "intra",
            "subtotal": 10000.0,
            "cgst": 900.0,
            "sgst": 900.0,
            "igst": 0.0,
            "tax_total": 1800.0,
            "round_off": 0.0,
            "grand_total": 11800.0,
            "line_items": [
                {
                    "description": "WAHRMS Employee Count Subscription",
                    "hsn": "998314",
                    "qty": 25,
                    "rate": 400.0,
                    "gstRate": 0.18,
                    "discount": 0.0,
                    "amount": 11800.0,
                }
            ],
            "terms_and_conditions": "Draft terms",
            "notes": f"{MARKER} draft",
            "prepared_by": "Draft Test Runner",
        }
        payload.update(overrides)
        return CreateDocumentRequest(**payload)

    def test_01_draft_persists_lists_updates_and_issues_without_duplicates(self):
        created = create_document(self._draft_request(), db=self.db, current_user=self.admin_user)
        self.assertTrue(created["ok"])
        draft_id = created["document"]["rawId"]

        row = self.db.query(Quotation).filter(Quotation.id == draft_id).first()
        self.assertIsNotNone(row)
        self.assertEqual(row.status, "draft")
        self.assertEqual(row.selected_bundle, "hr_atm")
        self.assertEqual(row.product_category, "wahrms")
        self.assertEqual(row.customer_name, "Draft Flow Customer")
        self.assertEqual(row.company_name, "Draft Flow Industries")
        self.assertEqual(row.phone, "9000012345")
        self.assertEqual(row.email, "draft.flow@example.com")
        self.assertEqual(row.address, "12 Test Street, Chennai")
        self.assertEqual(row.state, "Tamil Nadu")
        self.assertEqual(row.state_code, "33")
        self.assertEqual(row.gstin, "33ABCDE1234F1Z5")
        self.assertEqual(row.tax_mode, "intra")
        self.assertAlmostEqual(row.subtotal, 10000.0)
        self.assertAlmostEqual(row.cgst, 900.0)
        self.assertAlmostEqual(row.sgst, 900.0)
        self.assertAlmostEqual(row.tax_total, 1800.0)
        self.assertAlmostEqual(row.grand_total, 11800.0)
        self.assertEqual(row.line_items[0]["qty"], 25)
        self.assertEqual(row.line_items[0]["rate"], 400.0)

        draft_docs = list_waquote_documents(
            doc_type="quotation",
            status_filter="draft",
            search="Draft Flow Customer",
            db=self.db,
            current_user=self.admin_user,
        )["documents"]
        self.assertEqual([d["rawId"] for d in draft_docs], [draft_id])
        self.assertEqual(draft_docs[0]["status"], "draft")
        self.assertEqual(draft_docs[0]["number"], row.doc_number)
        self.assertAlmostEqual(draft_docs[0]["financials"]["grandTotal"], 11800.0)

        issued_docs = list_waquote_documents(
            doc_type="quotation",
            status_filter="issued",
            search="Draft Flow Customer",
            db=self.db,
            current_user=self.admin_user,
        )["documents"]
        self.assertEqual(issued_docs, [])

        reopened = get_waquote_document(str(draft_id), db=self.db, current_user=self.admin_user)
        self.assertTrue(reopened["ok"])
        self.assertEqual(reopened["document"]["status"], "draft")
        self.assertEqual(reopened["document"]["customer"]["name"], "Draft Flow Customer")
        self.assertEqual(reopened["document"]["lineItems"][0]["qty"], 25)

        updated_req = self._draft_request(
            subtotal=11000.0,
            cgst=990.0,
            sgst=990.0,
            tax_total=1980.0,
            grand_total=12980.0,
            notes=f"{MARKER} draft edited",
        )
        updated = update_waquote_document(str(draft_id), updated_req, db=self.db, current_user=self.admin_user)
        self.assertTrue(updated["ok"])

        self.db.expire_all()
        row = self.db.query(Quotation).filter(Quotation.id == draft_id).first()
        self.assertEqual(row.status, "draft")
        self.assertAlmostEqual(row.grand_total, 12980.0)
        self.assertEqual(
            self.db.query(Quotation).filter(Quotation.notes.like(f"%{MARKER}%")).count(),
            1,
            "Re-saving the same draft must update it, not insert a duplicate.",
        )

        issued_req = self._draft_request(
            status="issued",
            subtotal=11000.0,
            cgst=990.0,
            sgst=990.0,
            tax_total=1980.0,
            grand_total=12980.0,
            notes=f"{MARKER} draft edited",
        )
        issued = update_waquote_document(str(draft_id), issued_req, db=self.db, current_user=self.admin_user)
        self.assertTrue(issued["ok"])

        self.db.expire_all()
        row = self.db.query(Quotation).filter(Quotation.id == draft_id).first()
        self.assertEqual(row.status, "issued")
        self.assertEqual(self.db.query(Quotation).filter(Quotation.notes.like(f"%{MARKER}%")).count(), 1)

        draft_docs = list_waquote_documents(
            doc_type="quotation",
            status_filter="draft",
            search="Draft Flow Customer",
            db=self.db,
            current_user=self.admin_user,
        )["documents"]
        issued_docs = list_waquote_documents(
            doc_type="quotation",
            status_filter="issued",
            search="Draft Flow Customer",
            db=self.db,
            current_user=self.admin_user,
        )["documents"]
        self.assertEqual(draft_docs, [])
        self.assertEqual([d["rawId"] for d in issued_docs], [draft_id])

    def test_02_draft_does_not_overwrite_lead_issued_quotation_reference(self):
        lead = Lead(name=f"Draft Lead {MARKER}", phone="9000098765", status="NEW")
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)

        issued_req = self._draft_request(
            status="issued",
            lead_id=lead.id,
            notes=f"{MARKER} issued source",
        )
        issued = create_document(issued_req, db=self.db, current_user=self.admin_user)
        issued_id = issued["document"]["rawId"]

        self.db.refresh(lead)
        self.assertEqual(lead.quotetask_quotation_id, str(issued_id))
        self.assertEqual(lead.quotetask_quotation_status, "issued")
        issued_number = lead.quotetask_quotation_number

        draft_req = self._draft_request(
            status="draft",
            lead_id=lead.id,
            allow_duplicate=True,
            customer_name="Draft Flow Customer",
            notes=f"{MARKER} draft sibling",
        )
        draft = create_document(draft_req, db=self.db, current_user=self.admin_user)
        draft_id = draft["document"]["rawId"]

        self.db.refresh(lead)
        self.assertEqual(lead.quotetask_quotation_id, str(issued_id))
        self.assertEqual(lead.quotetask_quotation_status, "issued")
        self.assertEqual(lead.quotetask_quotation_number, issued_number)

        issued_draft_req = self._draft_request(
            status="issued",
            lead_id=lead.id,
            allow_duplicate=True,
            customer_name="Draft Flow Customer",
            notes=f"{MARKER} draft sibling",
        )
        update_waquote_document(str(draft_id), issued_draft_req, db=self.db, current_user=self.admin_user)

        self.db.refresh(lead)
        self.assertEqual(lead.quotetask_quotation_id, str(draft_id))
        self.assertEqual(lead.quotetask_quotation_status, "issued")

        self.db.expire_all()
        self.assertEqual(
            self.db.query(Quotation).filter(Quotation.notes.like(f"%{MARKER}%")).count(),
            2,
        )


if __name__ == "__main__":
    unittest.main()
