import os
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4

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
    download_quotation_pdf,
)
from routers.leads import download_lead_quotation
from services.pdf_service import (
    apply_issuer_filename_prefix,
    quotation_filename,
    resolve_issuer_filename_prefix,
)

MARKER = "[TEST-QUOTE-FILENAME]"
PHONE_MARKER = "99999"


def filename_from_response(response):
    disposition = response.headers.get("content-disposition", "")
    return disposition.split('filename="', 1)[1].rstrip('"')


class QuotationFilenameHelperTests(unittest.TestCase):
    """The filename prefix must follow the same issuer the PDF renders."""

    def test_explicit_company_id_wins(self):
        self.assertEqual(resolve_issuer_filename_prefix("wahrms"), "WAHRMS")
        self.assertEqual(resolve_issuer_filename_prefix("chn-tech"), "CHN")

    def test_logo_ref_is_used_when_company_id_is_missing(self):
        self.assertEqual(resolve_issuer_filename_prefix(None, None, "wahrms"), "WAHRMS")
        self.assertEqual(resolve_issuer_filename_prefix(None, None, "chn-tech"), "CHN")

    def test_product_category_is_the_historical_fallback(self):
        self.assertEqual(resolve_issuer_filename_prefix(None, "biometric"), "CHN")
        self.assertEqual(resolve_issuer_filename_prefix(None, "wahrms"), "WAHRMS")
        self.assertEqual(resolve_issuer_filename_prefix(), "WAHRMS")

    def test_leading_token_is_replaced_and_remainder_preserved(self):
        base = "CHN-PI-26-1476-SRI-VENKATESHWARA-COLLEGE.pdf"
        prefixed = apply_issuer_filename_prefix(base, "WAHRMS")
        self.assertEqual(prefixed, "WAHRMS-PI-26-1476-SRI-VENKATESHWARA-COLLEGE.pdf")
        self.assertEqual(prefixed[len("WAHRMS"):], base[len("CHN"):])

    def test_chn_quotation_keeps_chn_prefix(self):
        self.assertEqual(
            apply_issuer_filename_prefix("CHN-QT-2627-0020-CHANDRA-MOHAN.pdf", "CHN"),
            "CHN-QT-2627-0020-CHANDRA-MOHAN.pdf",
        )

    def test_prefix_is_added_when_filename_has_none(self):
        self.assertEqual(
            apply_issuer_filename_prefix("Quotation_CHN-QT-2627-0020.pdf", "WAHRMS"),
            "WAHRMS-Quotation_CHN-QT-2627-0020.pdf",
        )

    def test_quotation_filename_uses_resolved_issuer(self):
        self.assertEqual(
            quotation_filename("wahrms", "wahrms", None, "Quotation_CHN-QT-1.pdf"),
            "WAHRMS-Quotation_CHN-QT-1.pdf",
        )
        self.assertEqual(
            quotation_filename(None, "biometric", None, "Quotation_CHN-QT-1.pdf"),
            "CHN-Quotation_CHN-QT-1.pdf",
        )


class QuotationFilenameDownloadTests(unittest.TestCase):
    """Both quotation download endpoints must emit the issuer-prefixed name."""

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
            str(row.id)
            for row in self.db.query(Quotation.id).filter(
                Quotation.notes.like(f"%{MARKER}%")
            ).all()
        ]
        lead_ids = [
            row.id
            for row in self.db.query(Lead.id).filter(
                Lead.name.like(f"%{MARKER}%")
            ).all()
        ]
        if doc_ids:
            self.db.query(AuditLog).filter(
                AuditLog.entity_type.in_(("QUOTATION", "PROFORMA")),
                AuditLog.entity_id.in_(doc_ids),
            ).delete(synchronize_session=False)
        if lead_ids:
            self.db.query(LeadActivity).filter(
                LeadActivity.lead_id.in_(lead_ids)
            ).delete(synchronize_session=False)
        self.db.query(Quotation).filter(
            Quotation.notes.like(f"%{MARKER}%")
        ).delete(synchronize_session=False)
        if lead_ids:
            self.db.query(Quotation).filter(
                Quotation.lead_id.in_(lead_ids)
            ).delete(synchronize_session=False)
            self.db.query(Lead).filter(
                Lead.id.in_(lead_ids)
            ).delete(synchronize_session=False)
        self.db.commit()

    def _payload(self, company_id, product_category, lead_id=None):
        token = uuid4().hex[:10].upper()
        short_name = "WA!HRMS" if company_id == "wahrms" else "CHN TECH"
        return CreateDocumentRequest(
            doc_type="quotation",
            status="draft",
            doc_number=f"TEST/QF/{token}",
            product_category=product_category,
            allow_duplicate=True,
            lead_id=lead_id,
            customer_name=f"{MARKER} Customer",
            company_name="Filename Test Co",
            phone="9000012345",
            email="filename.test@example.com",
            grand_total=11800.0,
            line_items=[],
            notes=f"{MARKER} {token}",
            prepared_by="Filename Test Runner",
            company_id=company_id,
            logo_ref=company_id,
            document_prefix="CHN/QT" if company_id == "chn-tech" else "WAHRMS/QT",
            company={
                "id": company_id,
                "legalName": "CHN TECHNOLOGIES PVT LTD",
                "shortName": short_name,
                "logoRef": company_id,
            },
        )

    def _create(self, company_id, product_category, lead_id=None):
        result = create_document(
            self._payload(company_id, product_category, lead_id=lead_id),
            db=self.db,
            current_user=self.admin_user,
        )
        self.assertTrue(result["ok"])
        return result["document"]["rawId"]

    def _create_lead(self):
        lead = Lead(
            name=f"{MARKER} Lead {uuid4().hex[:6]}",
            phone=f"{PHONE_MARKER}{uuid4().int % 100000:05d}",
            source="MANUAL",
            status="NEW LEAD",
            product_category="WAHRMS",
        )
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        return lead

    def test_wahrms_quotation_download_filename_matches_pdf_issuer(self):
        doc_id = self._create("wahrms", "wahrms")
        row = self.db.query(Quotation).filter(Quotation.id == doc_id).first()
        sentinel = b"%PDF-sentinel-wahrms"

        with patch(
            "services.pdf_service.generate_quotation_pdf", return_value=sentinel
        ) as generate:
            response = download_quotation_pdf(
                str(doc_id), db=self.db, current_user=self.admin_user
            )

        filename = filename_from_response(response)
        expected_remainder = f"Quotation_{row.doc_number.replace('/', '-')}.pdf"

        self.assertTrue(filename.startswith("WAHRMS-"))
        self.assertEqual(filename, f"WAHRMS-{expected_remainder}")
        self.assertEqual(filename[len("WAHRMS-"):], expected_remainder)
        # The endpoint must still return the unchanged PDF bytes.
        self.assertEqual(response.body, sentinel)
        self.assertEqual(generate.call_args.args[0].id, doc_id)

    def test_chn_quotation_download_filename_matches_pdf_issuer(self):
        doc_id = self._create("chn-tech", "biometric")
        row = self.db.query(Quotation).filter(Quotation.id == doc_id).first()
        sentinel = b"%PDF-sentinel-chn"

        with patch(
            "services.pdf_service.generate_quotation_pdf", return_value=sentinel
        ) as generate:
            response = download_quotation_pdf(
                str(doc_id), db=self.db, current_user=self.admin_user
            )

        filename = filename_from_response(response)
        expected_remainder = f"Quotation_{row.doc_number.replace('/', '-')}.pdf"

        self.assertTrue(filename.startswith("CHN-"))
        self.assertEqual(filename, f"CHN-{expected_remainder}")
        self.assertEqual(filename[len("CHN-"):], expected_remainder)
        self.assertEqual(response.body, sentinel)
        self.assertEqual(generate.call_args.args[0].id, doc_id)

    def test_lead_quotation_download_uses_saved_issuer(self):
        lead = self._create_lead()
        doc_id = self._create("chn-tech", "biometric", lead_id=lead.id)
        row = self.db.query(Quotation).filter(Quotation.id == doc_id).first()
        sentinel = b"%PDF-sentinel-lead"

        with patch(
            "services.pdf_service.generate_quotation_pdf", return_value=sentinel
        ) as generate:
            response = download_lead_quotation(
                lead.id, db=self.db, current_user=self.admin_user
            )

        filename = filename_from_response(response)
        expected_remainder = f"Quotation_{row.doc_number.replace('/', '-')}.pdf"

        self.assertEqual(filename, f"CHN-{expected_remainder}")
        self.assertEqual(response.body, sentinel)
        self.assertEqual(generate.call_args.args[0].id, doc_id)

    def test_lead_quotation_fallback_matches_generated_pdf_issuer(self):
        lead = self._create_lead()
        sentinel = b"%PDF-sentinel-fallback"

        with patch(
            "services.pdf_service.generate_quotation_pdf", return_value=sentinel
        ) as generate:
            response = download_lead_quotation(
                lead.id, db=self.db, current_user=self.admin_user
            )

        filename = filename_from_response(response)
        snapshot = generate.call_args.args[0]

        # The fallback snapshot is rendered with the default WAHRMS issuer, so
        # the filename must say WAHRMS even though the number contains CHN.
        self.assertEqual(
            filename,
            f"WAHRMS-Quotation_CHN-QT-2627-{lead.id:04d}.pdf",
        )
        self.assertEqual(response.body, sentinel)
        self.assertIsNone(snapshot.get("company_id"))
        self.assertIsNone(snapshot.get("product_category"))


if __name__ == "__main__":
    unittest.main()
