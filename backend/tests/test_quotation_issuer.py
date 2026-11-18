import io
import os
import sys
import unittest
from uuid import uuid4

from pypdf import PdfReader

sys.path.insert(0, os.path.abspath('backend'))

from database import SessionLocal
from models.activity import LeadActivity
from models.audit_log import AuditLog
from models.quotation import Quotation
from models.user import User
from integrations.waquote.router import (
    CreateDocumentRequest,
    create_document,
    generate_proforma_from_quotation,
    get_waquote_document,
    list_waquote_documents,
    update_waquote_document,
)
from services.pdf_service import (
    build_common_data,
    generate_quotation_pdf,
    resolve_issuer_profile,
)

MARKER = "[TEST-ISSUER-ROUNDTRIP]"


class QuotationIssuerPersistenceTests(unittest.TestCase):
    """Issuer/company and logo identity must survive create, list, open and edit."""

    def setUp(self):
        self.db = SessionLocal()
        self.admin_user = self.db.query(User).filter(User.username == "admin").first()
        self.assertIsNotNone(self.admin_user)
        self._cleanup()

    def tearDown(self):
        self._cleanup()
        self.db.close()

    def _cleanup(self):
        self.db.rollback()
        doc_ids = [
            str(row.id) for row in self.db.query(Quotation.id).filter(
                Quotation.notes.like(f"%{MARKER}%")
            ).all()
        ]
        if doc_ids:
            self.db.query(AuditLog).filter(
                AuditLog.entity_type.in_(("QUOTATION", "PROFORMA")),
                AuditLog.entity_id.in_(doc_ids),
            ).delete(synchronize_session=False)
        self.db.query(Quotation).filter(
            Quotation.notes.like(f"%{MARKER}%")
        ).delete(synchronize_session=False)
        self.db.commit()

    def _payload(self, **overrides):
        payload = {
            "doc_type": "quotation",
            "status": "draft",
            "doc_number": f"TEST-ISS-{uuid4().hex[:10].upper()}",
            "selected_bundle": "bio_standard",
            "product_category": "biometric",
            "customer_name": "Issuer Roundtrip Customer",
            "company_name": "Issuer Roundtrip Industries",
            "phone": "9000011223",
            "email": "issuer.roundtrip@example.com",
            "address": "14 Test Street, Chennai",
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
                    "description": "Biometric Device Installation",
                    "hsn": "998315",
                    "qty": 1,
                    "rate": 10000.0,
                    "gstRate": 0.18,
                    "discount": 0.0,
                    "amount": 11800.0,
                }
            ],
            "terms_and_conditions": "Issuer test terms",
            "notes": f"{MARKER} issuer roundtrip",
            "prepared_by": "Issuer Test Runner",
            "company_id": "chn-tech",
            "company": {
                "id": "chn-tech",
                "legalName": "CHN TECHNOLOGIES PVT LTD",
                "shortName": "CHN TECH",
                "logoType": "chn-tech",
                "logoRef": "chn-tech",
                "gstin": "33AAJCC3705A1ZC",
                "pan": "AAJCC3705A",
            },
            "logo_ref": "chn-tech",
            "issuer_gstin": "33AAJCC3705A1ZC",
            "issuer_pan": "AAJCC3705A",
            "document_prefix": "CHN/QT",
        }
        payload.update(overrides)
        return CreateDocumentRequest(**payload)

    def _create(self, **overrides):
        result = create_document(
            self._payload(**overrides),
            db=self.db,
            current_user=self.admin_user,
        )
        self.assertTrue(result["ok"])
        return result["document"]["rawId"]

    def test_biometric_issuer_roundtrip_and_issuer_change(self):
        doc_id = self._create()

        row = self.db.query(Quotation).filter(Quotation.id == doc_id).first()
        self.assertIsNotNone(row)
        self.assertEqual(row.product_category, "biometric")
        self.assertEqual(row.company_id, "chn-tech")
        self.assertEqual(row.logo_ref, "chn-tech")
        self.assertEqual(row.issuer_gstin, "33AAJCC3705A1ZC")
        self.assertEqual(row.issuer_pan, "AAJCC3705A")
        self.assertEqual(row.document_prefix, "CHN/QT")

        detail = get_waquote_document(
            str(doc_id), db=self.db, current_user=self.admin_user
        )["document"]
        self.assertEqual(detail["productCategory"], "biometric")
        self.assertEqual(detail["companyId"], "chn-tech")
        self.assertEqual(detail["logoRef"], "chn-tech")
        self.assertEqual(detail["issuerGstin"], "33AAJCC3705A1ZC")
        self.assertEqual(detail["issuerPan"], "AAJCC3705A")
        self.assertEqual(detail["documentPrefix"], "CHN/QT")
        self.assertEqual(detail["issuer"]["companyId"], "chn-tech")

        listed = list_waquote_documents(
            doc_type="quotation",
            search="Issuer Roundtrip Customer",
            db=self.db,
            current_user=self.admin_user,
        )["documents"]
        listed_row = next(doc for doc in listed if doc["rawId"] == doc_id)
        self.assertEqual(listed_row["companyId"], "chn-tech")
        self.assertEqual(listed_row["logoRef"], "chn-tech")

        # Change issuer in Edit mode and persist it back as WAHRMS.
        updated = update_waquote_document(
            str(doc_id),
            self._payload(
                product_category="wahrms",
                selected_bundle="hr_atm",
                company_id="wahrms",
                company={
                    "id": "wahrms",
                    "legalName": "CHN TECHNOLOGIES PVT LTD",
                    "shortName": "WAHRMS",
                    "logoType": "wahrms",
                    "logoRef": "wahrms",
                    "gstin": "33AAJCC3705A1ZC",
                    "pan": "AAJCC3705A",
                },
                logo_ref="wahrms",
            ),
            db=self.db,
            current_user=self.admin_user,
        )
        self.assertTrue(updated["ok"])
        self.assertEqual(updated["document"]["companyId"], "wahrms")

        self.db.expire_all()
        row = self.db.query(Quotation).filter(Quotation.id == doc_id).first()
        self.assertEqual(row.product_category, "wahrms")
        self.assertEqual(row.company_id, "wahrms")
        self.assertEqual(row.logo_ref, "wahrms")

        reopened = get_waquote_document(
            str(doc_id), db=self.db, current_user=self.admin_user
        )["document"]
        self.assertEqual(reopened["companyId"], "wahrms")
        self.assertEqual(reopened["logoRef"], "wahrms")

    def test_wahrms_default_issuer_is_persisted(self):
        doc_id = self._create(
            product_category="wahrms",
            selected_bundle="hr_atm",
            company_id=None,
            company=None,
            logo_ref=None,
            issuer_gstin=None,
            issuer_pan=None,
            document_prefix=None,
        )

        row = self.db.query(Quotation).filter(Quotation.id == doc_id).first()
        self.assertEqual(row.company_id, "wahrms")
        self.assertEqual(row.logo_ref, "wahrms")
        self.assertEqual(row.document_prefix, "CHN/QT")

        detail = get_waquote_document(
            str(doc_id), db=self.db, current_user=self.admin_user
        )["document"]
        self.assertEqual(detail["companyId"], "wahrms")
        self.assertEqual(detail["logoRef"], "wahrms")
        self.assertEqual(detail["productCategory"], "wahrms")

    def test_edit_without_company_fields_preserves_saved_issuer(self):
        doc_id = self._create()

        update_waquote_document(
            str(doc_id),
            self._payload(
                company_id=None,
                company=None,
                logo_ref=None,
                issuer_gstin=None,
                issuer_pan=None,
                document_prefix=None,
            ),
            db=self.db,
            current_user=self.admin_user,
        )

        self.db.expire_all()
        row = self.db.query(Quotation).filter(Quotation.id == doc_id).first()
        self.assertEqual(row.company_id, "chn-tech")
        self.assertEqual(row.logo_ref, "chn-tech")
        self.assertEqual(row.issuer_gstin, "33AAJCC3705A1ZC")
        self.assertEqual(row.issuer_pan, "AAJCC3705A")
        self.assertEqual(row.document_prefix, "CHN/QT")

    def test_proforma_generated_from_quotation_copies_issuer(self):
        doc_id = self._create()

        result = generate_proforma_from_quotation(
            str(doc_id), db=self.db, current_user=self.admin_user
        )
        self.assertTrue(result["ok"])
        proforma = result["document"]

        self.db.expire_all()
        row = self.db.query(Quotation).filter(
            Quotation.id == proforma["rawId"]
        ).first()
        self.assertIsNotNone(row)
        self.assertEqual(row.doc_type, "proforma")
        self.assertEqual(row.source_quotation_id, doc_id)
        self.assertEqual(row.product_category, "biometric")
        self.assertEqual(row.company_id, "chn-tech")
        self.assertEqual(row.logo_ref, "chn-tech")
        self.assertEqual(row.issuer_gstin, "33AAJCC3705A1ZC")
        self.assertEqual(row.issuer_pan, "AAJCC3705A")
        self.assertEqual(row.document_prefix, "CHN/PI")

        self.assertEqual(proforma["companyId"], "chn-tech")
        self.assertEqual(proforma["logoRef"], "chn-tech")

    def test_historical_biometric_row_resolves_without_rewrite(self):
        legacy = Quotation(
            doc_type="quotation",
            product_category="biometric",
            company_id=None,
            logo_ref=None,
            doc_number=f"TEST-LEGACY-{uuid4().hex[:10]}",
            status="draft",
            payment_status="unpaid",
            customer_name="Legacy Biometric Customer",
            company_name="Legacy Biometric Industries",
            phone="9000044556",
            email="legacy.biometric@example.com",
            address="8 Legacy Street, Chennai",
            state="Tamil Nadu",
            state_code="33",
            gstin="33ABCDE1234F1Z5",
            tax_mode="intra",
            subtotal=1000.0,
            cgst=90.0,
            sgst=90.0,
            igst=0.0,
            tax_total=180.0,
            round_off=0.0,
            grand_total=1180.0,
            amount_paid=0.0,
            line_items=[],
            terms_and_conditions="Legacy terms",
            notes=f"{MARKER} legacy biometric",
            prepared_by="Legacy Importer",
        )
        self.db.add(legacy)
        self.db.commit()
        self.db.refresh(legacy)

        detail = get_waquote_document(
            str(legacy.id), db=self.db, current_user=self.admin_user
        )["document"]
        self.assertEqual(detail["companyId"], "chn-tech")
        self.assertEqual(detail["logoRef"], "chn-tech")

        # Read-time fallback must not rewrite the historical record.
        self.db.expire_all()
        legacy = self.db.query(Quotation).filter(Quotation.id == legacy.id).first()
        self.assertIsNone(legacy.company_id)
        self.assertIsNone(legacy.logo_ref)


class IssuerPdfBrandingTests(unittest.TestCase):
    def test_saved_company_wins_over_category(self):
        profile = resolve_issuer_profile("chn-tech", "wahrms", None)
        self.assertEqual(profile["company_id"], "chn-tech")
        self.assertEqual(profile["logo_file"].name, "chn_logo_actual.png")

        profile = resolve_issuer_profile("wahrms", "biometric", None)
        self.assertEqual(profile["company_id"], "wahrms")
        self.assertEqual(profile["logo_file"].name, "wahrms-logo.png")

    def test_historical_category_fallback_selects_configured_logo(self):
        profile = resolve_issuer_profile(None, "biometric", None)
        self.assertEqual(profile["company_id"], "chn-tech")
        self.assertEqual(profile["logo_file"].name, "chn_logo_actual.png")

        profile = resolve_issuer_profile(None, "wahrms", None)
        self.assertEqual(profile["company_id"], "wahrms")
        self.assertEqual(profile["logo_file"].name, "wahrms-logo.png")

    def test_pdf_data_and_output_include_issuer(self):
        data = build_common_data({
            "doc_number": "TEST/PDF/001",
            "doc_type": "quotation",
            "product_category": "biometric",
            "companyId": "chn-tech",
            "logoRef": "chn-tech",
            "issuerGstin": "33SNAPSHOT0001Z9",
            "issuerPan": "SNAPSHOT01",
            "documentPrefix": "CHN/QT",
            "customer_name": "PDF Customer",
            "company_name": "PDF Industries",
            "grand_total": 1180.0,
            "line_items": [],
        })
        self.assertEqual(data["company_id"], "chn-tech")
        self.assertEqual(data["logo_ref"], "chn-tech")
        self.assertEqual(data["issuer_gstin"], "33SNAPSHOT0001Z9")
        self.assertEqual(data["issuer_pan"], "SNAPSHOT01")
        self.assertEqual(data["document_prefix"], "CHN/QT")

        pdf_bytes = generate_quotation_pdf({
            "doc_number": "TEST/PDF/001",
            "doc_type": "quotation",
            "product_category": "biometric",
            "company_id": "chn-tech",
            "logo_ref": "chn-tech",
            "issuer_gstin": "33SNAPSHOT0001Z9",
            "issuer_pan": "SNAPSHOT01",
            "customer_name": "PDF Customer",
            "company_name": "PDF Industries",
            "grand_total": 1180.0,
            "line_items": [],
        })
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertGreater(len(pdf_bytes), 1000)

        text = "\n".join(
            page.extract_text() or ""
            for page in PdfReader(io.BytesIO(pdf_bytes)).pages
        )
        self.assertIn("GSTIN: 33SNAPSHOT0001Z9", text)
        self.assertIn("PAN: SNAPSHOT01", text)


if __name__ == "__main__":
    unittest.main()
