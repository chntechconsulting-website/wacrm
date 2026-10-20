import unittest
import os
import sys
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

# Ensure backend directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.product_validation_service import ProductValidationService, ProductCategoryValidationResult
from services.destination_sync_service import DestinationSyncService
from models.quotation import Quotation, WAHRMSBundle
from database import SessionLocal


class TestProductCategoryValidation(unittest.TestCase):
    """Tests authoritative multi-factor category classification."""

    def test_pure_wahrms_software_document(self):
        doc = MagicMock()
        doc.selected_bundle = "hr_payroll"
        doc.product_category = "wahrms"
        doc.line_items = [
            {
                "item_code": "HR_PAYROLL_SUB",
                "hsn": "998314",
                "name": "WAHRMS HR + Payroll Cloud Subscription",
                "description": "WAHRMS HR + Payroll Cloud Subscription\nDuration: 12 Months | Onboardings: 25 Users",
                "qty": 300,
                "rate": 50.0,
                "gstRate": 0.18
            },
            {
                "item_code": "PAYROLL_SETUP",
                "hsn": "998315",
                "name": "WA Payroll Cloud Setup & Deployment",
                "description": "Cloud Setup & Deployment",
                "qty": 1,
                "rate": 5000.0,
                "gstRate": 0.18
            }
        ]

        result = ProductValidationService.validate_document_products(doc)
        self.assertTrue(result.is_wahrms_only)
        self.assertFalse(result.has_biometric)
        self.assertTrue(result.has_wahrms)
        self.assertFalse(result.is_mixed)
        self.assertEqual(result.resolved_category, "WAHRMS")
        self.assertEqual(result.licence_count, 25)
        self.assertEqual(result.biometric_device_count, 0)

    def test_pure_biometric_hardware_document(self):
        doc = MagicMock()
        doc.selected_bundle = "bio_standard"
        doc.product_category = "biometric"
        doc.line_items = [
            {
                "item_code": "MB160",
                "hsn": "85437099",
                "name": "MB160 Biometric Device",
                "description": "MB160 Face + Fingerprint + RFID Terminal\nIncludes 4G IoT Data SIM Card",
                "qty": 2,
                "rate": 22400.0,
                "gstRate": 0.18
            },
            {
                "item_code": "BIO_INSTALL",
                "hsn": "998315",
                "name": "Installation & Calibration",
                "description": "Onsite Device Mounting & Terminal Configuration",
                "qty": 1,
                "rate": 1000.0,
                "gstRate": 0.18
            }
        ]

        result = ProductValidationService.validate_document_products(doc)
        self.assertFalse(result.is_wahrms_only)
        self.assertTrue(result.has_biometric)
        self.assertFalse(result.is_mixed)
        self.assertEqual(result.resolved_category, "BIOMETRIC")
        self.assertEqual(result.biometric_device_count, 2)

    def test_mixed_document_blocks_synchronization(self):
        """Mixed WAHRMS software + Biometric hardware must be strictly blocked."""
        doc = MagicMock()
        doc.selected_bundle = "hr_atm_payroll"
        doc.product_category = "wahrms"  # Even if declared as wahrms on top level!
        doc.line_items = [
            {
                "item_code": "HR_ATM_PAYROLL_SUB",
                "hsn": "998314",
                "name": "WAHRMS Complete Suite Subscription",
                "description": "WAHRMS Subscription - 10 Users",
                "qty": 120,
                "rate": 65.0,
                "gstRate": 0.18
            },
            {
                "item_code": "BIO_PAYROLL_PACKAGE",
                "hsn": "85437099",
                "name": "MB160 Biometric Hardware Device",
                "description": "Attendance Terminal Hardware with Power Supply",
                "qty": 1,
                "rate": 24500.0,
                "gstRate": 0.18
            }
        ]

        result = ProductValidationService.validate_document_products(doc)
        self.assertFalse(result.is_wahrms_only)
        self.assertTrue(result.has_biometric)
        self.assertTrue(result.has_wahrms)
        self.assertTrue(result.is_mixed)
        self.assertEqual(result.resolved_category, "MIXED")
        self.assertIn("mixed WAHRMS software and Biometric products", result.primary_reason)


class TestDestinationSyncServiceProductExclusion(unittest.TestCase):
    """Verifies that Biometric and mixed documents never trigger external HTTP calls."""

    @patch("httpx.Client")
    def test_biometric_document_makes_zero_external_requests(self, mock_client_cls):
        """CRITICAL: Biometric documents must NEVER make any HTTP request to external website."""
        mock_http = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_http

        db = SessionLocal()
        proforma = None
        try:
            # Create a mock or temporary proforma
            proforma = Quotation(
                doc_type="proforma",
                product_category="biometric",
                selected_bundle="bio_standard",
                doc_number="TEST-BIO-PF-001",
                customer_name="Biometric Client Pvt Ltd",
                company_name="Biometric Client Pvt Ltd",
                phone="9876543210",
                email="client@biometric.com",
                subtotal=22400.0,
                grand_total=26432.0,
                line_items=[
                    {
                        "item_code": "MB160",
                        "hsn": "85437099",
                        "name": "MB160 Face Terminal",
                        "description": "Biometric Machine",
                        "qty": 1,
                        "rate": 22400.0
                    }
                ],
                destination_sync_status="PENDING"
            )
            db.add(proforma)
            db.commit()
            db.refresh(proforma)

            # Trigger destination sync
            result = DestinationSyncService.sync_proforma_to_destination(db, proforma.id)

            # 1. Assert result
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "NOT_APPLICABLE")
            self.assertEqual(result["sync_status"], "NOT_APPLICABLE")
            self.assertFalse(result["eligible"])

            # 2. Assert DB updated to NOT_APPLICABLE
            db.refresh(proforma)
            self.assertEqual(proforma.destination_sync_status, "NOT_APPLICABLE")
            self.assertIsNone(proforma.destination_sync_error)

            # 3. CRITICAL: Verify ZERO HTTP calls were made!
            mock_http.post.assert_not_called()
            mock_http.get.assert_not_called()

        finally:
            # Cleanup
            if proforma and proforma.id:
                db.delete(proforma)
                db.commit()
            db.close()

    @patch("httpx.Client")
    def test_mixed_document_makes_zero_external_requests(self, mock_client_cls):
        """Mixed documents must be excluded and make zero external network requests."""
        mock_http = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_http

        db = SessionLocal()
        proforma = None
        try:
            proforma = Quotation(
                doc_type="proforma",
                product_category="wahrms",  # User or dropdown labeled as wahrms
                selected_bundle="hr_payroll",
                doc_number="TEST-MIXED-PF-002",
                customer_name="Mixed Client Pvt Ltd",
                line_items=[
                    {"item_code": "HR_PAYROLL_SUB", "hsn": "998314", "description": "WAHRMS Payroll", "qty": 10, "rate": 500},
                    {"item_code": "BIO_DEVICE", "hsn": "85437099", "description": "Biometric Machine MB160", "qty": 1, "rate": 15000}
                ],
                destination_sync_status="PENDING"
            )
            db.add(proforma)
            db.commit()
            db.refresh(proforma)

            result = DestinationSyncService.sync_proforma_to_destination(db, proforma.id)

            self.assertEqual(result["status"], "NOT_APPLICABLE")
            self.assertFalse(result["eligible"])
            db.refresh(proforma)
            self.assertEqual(proforma.destination_sync_status, "NOT_APPLICABLE")

            # ZERO HTTP calls made
            mock_http.post.assert_not_called()
            mock_http.get.assert_not_called()

        finally:
            if proforma and proforma.id:
                db.delete(proforma)
                db.commit()
            db.close()

    @patch("httpx.Client")
    def test_wahrms_only_document_triggers_sync_with_idempotency(self, mock_client_cls):
        """Pure WAHRMS documents must be synchronized with idempotency key and licence count."""
        mock_http = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_http

        # Mock successful client lookup / creation
        mock_cust_resp = MagicMock()
        mock_cust_resp.status_code = 200
        mock_cust_resp.json.return_value = {"customers": [{"id": "EXT-CUST-999"}]}

        # Mock successful proforma document creation
        mock_doc_resp = MagicMock()
        mock_doc_resp.status_code = 201
        mock_doc_resp.json.return_value = {"id": "EXT-PROFORMA-888"}

        mock_http.get.return_value = mock_cust_resp
        mock_http.post.return_value = mock_doc_resp

        db = SessionLocal()
        proforma = None
        try:
            proforma = Quotation(
                doc_type="proforma",
                product_category="wahrms",
                selected_bundle="hr_payroll",
                doc_number="TEST-WAHRMS-PF-003",
                customer_name="Pure WAHRMS Client",
                company_name="Pure WAHRMS Client",
                phone="9123456789",
                email="admin@wahrms-client.com",
                subtotal=6000.0,
                grand_total=7080.0,
                line_items=[
                    {
                        "item_code": "HR_PAYROLL_SUB",
                        "hsn": "998314",
                        "name": "WAHRMS HR + Payroll Cloud Subscription",
                        "description": "WAHRMS HR + Payroll Subscription - 50 Users",
                        "qty": 120,
                        "rate": 50.0
                    }
                ],
                destination_sync_status="PENDING"
            )
            db.add(proforma)
            db.commit()
            db.refresh(proforma)

            result = DestinationSyncService.sync_proforma_to_destination(db, proforma.id)

            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "SYNCED")
            self.assertEqual(result["external_proforma_id"], "EXT-PROFORMA-888")

            db.refresh(proforma)
            self.assertEqual(proforma.destination_sync_status, "SYNCED")
            self.assertEqual(proforma.external_proforma_id, "EXT-PROFORMA-888")

            # Check that post was called with Idempotency-Key
            post_calls = mock_http.post.call_args_list
            self.assertGreaterEqual(len(post_calls), 1)
            doc_call_kwargs = post_calls[-1][1]
            sent_headers = doc_call_kwargs.get("headers", {})
            self.assertIn("Idempotency-Key", sent_headers)
            expected_idempotency = f"CRM-PROFORMA-{proforma.id}-{proforma.doc_number.replace('/', '-')}"
            self.assertEqual(sent_headers["Idempotency-Key"], expected_idempotency)

            # Check sent payload contains licence count
            sent_payload = doc_call_kwargs.get("json", {})
            self.assertEqual(sent_payload.get("licenceCount"), 50)
            self.assertEqual(sent_payload.get("metadata", {}).get("licenceCount"), 50)

            # Test Idempotency: subsequent call must return SYNCED without calling API again
            mock_http.post.reset_mock()
            repeat_res = DestinationSyncService.sync_proforma_to_destination(db, proforma.id)
            self.assertTrue(repeat_res["already_synced"])
            mock_http.post.assert_not_called()

        finally:
            if proforma and proforma.id:
                db.delete(proforma)
                db.commit()
            db.close()


class TestProformaInboundAndManualEndpoints(unittest.TestCase):
    """Tests inbound API and manual retry endpoints enforcing strict WAHRMS-only policy."""

    def test_inbound_post_rejects_biometric_payload(self):
        """External website attempting to ingest biometric proforma must receive 422."""
        from integrations.proforma.service import ProformaIntegrationService
        from integrations.proforma.schemas import ProformaIntegrationPayload
        from fastapi import HTTPException

        db = SessionLocal()
        try:
            payload = ProformaIntegrationPayload(
                companyName="Biometric Inbound Co",
                contactPerson="John Inbound",
                email="inbound@bio.com",
                phone="9876543210",
                productCategory="biometric",
                selectedBundle="bio_standard",
                lineItems=[
                    {"itemCode": "MB160", "hsn": "85437099", "name": "MB160 Terminal", "rate": 20000.0, "qty": 1}
                ]
            )

            with self.assertRaises(HTTPException) as ctx:
                ProformaIntegrationService.process_proforma_payload(db, payload)

            self.assertEqual(ctx.exception.status_code, 422)
            self.assertIn("strictly to WAHRMS documents", ctx.exception.detail)
        finally:
            db.close()

    def test_inbound_get_returns_404_for_biometric_proforma(self):
        """External website querying a biometric proforma by number must get 404."""
        from integrations.proforma.service import ProformaIntegrationService
        from fastapi import HTTPException

        db = SessionLocal()
        proforma = None
        try:
            proforma = Quotation(
                doc_type="proforma",
                product_category="biometric",
                selected_bundle="bio_standard",
                doc_number="TEST-INBOUND-BIO-001",
                customer_name="Secret Biometric Client",
                subtotal=20000.0,
                grand_total=23600.0,
                line_items=[
                    {"item_code": "MB160", "hsn": "85437099", "description": "MB160 Device", "qty": 1, "rate": 20000.0}
                ],
                destination_sync_status="NOT_APPLICABLE"
            )
            db.add(proforma)
            db.commit()
            db.refresh(proforma)

            with self.assertRaises(HTTPException) as ctx:
                ProformaIntegrationService.get_proforma_by_id_or_number(db, proforma.doc_number)

            self.assertEqual(ctx.exception.status_code, 404)
        finally:
            if proforma and proforma.id:
                db.delete(proforma)
                db.commit()
            db.close()

    @patch("httpx.Client")
    def test_manual_retry_blocks_biometric_document(self, mock_client_cls):
        """Manual sync trigger for biometric document must return blocked status with zero HTTP calls."""
        from integrations.waquote.router import sync_proforma_destination_manual
        from models.user import User

        mock_http = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_http

        db = SessionLocal()
        proforma = None
        try:
            admin_user = db.query(User).filter(User.role == "ADMIN").first()
            if not admin_user:
                admin_user = MagicMock()
                admin_user.role = "ADMIN"

            proforma = Quotation(
                doc_type="proforma",
                product_category="biometric",
                selected_bundle="bio_standard",
                doc_number="TEST-MANUAL-BIO-002",
                customer_name="Manual Retry Client",
                subtotal=15000.0,
                grand_total=17700.0,
                line_items=[
                    {"item_code": "MB160", "hsn": "85437099", "description": "MB160 Device", "qty": 1, "rate": 15000.0}
                ],
                destination_sync_status="PENDING"
            )
            db.add(proforma)
            db.commit()
            db.refresh(proforma)

            res = sync_proforma_destination_manual(doc_id=proforma.doc_number, db=db, current_user=admin_user)

            self.assertFalse(res["ok"])
            self.assertEqual(res["status"], "NOT_APPLICABLE")
            self.assertIn("Not Applicable", res["message"])

            # Verify ZERO HTTP requests made
            mock_http.post.assert_not_called()
            mock_http.get.assert_not_called()
        finally:
            if proforma and proforma.id:
                db.delete(proforma)
                db.commit()
            db.close()


if __name__ == "__main__":
    unittest.main()
