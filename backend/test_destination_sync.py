import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

# Add backend directory to path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from services.destination_sync_service import DestinationSyncService
from models.quotation import Quotation
from models.customer import Customer
from models.lead import Lead
from models.integration import IntegrationConfig


class TestDestinationSyncService(unittest.TestCase):
    """
    Unit and Integration Test Suite for Destination ERP Server-to-Server Sync
    """

    def setUp(self):
        self.mock_db = MagicMock()
        
        # Setup mock customer
        self.customer = Customer(
            id=101,
            company_name="Test Enterprise Group",
            contact_name="Test Enterprise Contact",
            phone="9876543210",
            email="billing@testenterprise.com",
            location="Chennai",
            external_client_id=None
        )

        # Setup mock proforma invoice
        self.proforma = Quotation(
            id=202,
            doc_number="PI-2026-TEST-001",
            doc_type="proforma",
            customer_id=101,
            customer_name="Test Enterprise Contact",
            company_name="Test Enterprise Group",
            phone="9876543210",
            email="billing@testenterprise.com",
            address="123 Tech Park, Anna Nagar",
            state="Tamil Nadu",
            state_code="33",
            gstin="33AAAAA1234A1Z5",
            product_category="wahrms",
            subtotal=100000.0,
            tax_total=18000.0,
            grand_total=118000.0,
            status="issued",
            source_quotation_number="QT-2026-0001",
            terms_and_conditions="Standard terms apply.",
            line_items=[
                {
                    "name": "WAHRMS HR + Payroll Bundle",
                    "description": "Core HR + Attendance + Payroll cloud subscription",
                    "hsn": "998314",
                    "qty": 1,
                    "rate": 100000.0,
                    "discount": 0,
                    "gstRate": 0.18,
                    "total": 118000.0
                }
            ],
            destination_sync_status="PENDING",
            destination_sync_attempts=0
        )

        # Query dispatcher to accurately return correct entity by model class
        def query_side_effect(model):
            m = MagicMock()
            if model == Quotation:
                m.filter.return_value.first.return_value = self.proforma
            elif model == Customer:
                m.filter.return_value.first.return_value = self.customer
            elif model == IntegrationConfig:
                m.filter.return_value.first.return_value = None
            elif model == Lead:
                m.filter.return_value.first.return_value = None
            else:
                m.filter.return_value.first.return_value = None
            return m

        self.mock_db.query.side_effect = query_side_effect

    def test_credential_sanitization(self):
        """Verifies that API keys, bearer tokens, and secrets are sanitized from logs and error messages."""
        secret_key = "secret_erp_api_key_xyz987"
        raw_msg = f"HTTP 401 Unauthorized for request with Bearer {secret_key} and key={secret_key}"
        sanitized = DestinationSyncService._sanitize_error(raw_msg)
        
        self.assertNotIn(secret_key, sanitized)
        self.assertIn("[REDACTED]", sanitized)

    def test_skip_if_already_synced_without_force(self):
        """Verifies idempotency: Proforma already marked SYNCED is skipped unless force_retry=True."""
        self.proforma.destination_sync_status = "SYNCED"
        self.proforma.external_proforma_id = "doc_remote_888"
        
        result = DestinationSyncService.sync_proforma_to_destination(
            self.mock_db, proforma_id=202, force_retry=False
        )
        
        self.assertTrue(result["ok"])
        self.assertTrue(result.get("skipped", False))
        self.assertEqual(result["status"], "SYNCED")
        self.assertEqual(result["external_proforma_id"], "doc_remote_888")

    @patch("httpx.Client")
    def test_client_reuse_from_local_mapping(self, mock_client_cls):
        """Verifies that if customer already has external_client_id, it is directly reused without remote search."""
        self.customer.external_client_id = "cust_erp_existing_444"
        
        mock_http = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_http
        
        # Destination ERP responds with success on proforma creation
        mock_proforma_resp = MagicMock()
        mock_proforma_resp.status_code = 201
        mock_proforma_resp.json.return_value = {
            "ok": True,
            "id": "pf_remote_999",
            "number": "PI-2026-TEST-001"
        }
        mock_http.post.return_value = mock_proforma_resp
        
        result = DestinationSyncService.sync_proforma_to_destination(
            self.mock_db, proforma_id=202, force_retry=True
        )
        
        self.assertTrue(result["ok"])
        self.assertEqual(result["external_client_id"], "cust_erp_existing_444")
        self.assertEqual(result["external_proforma_id"], "pf_remote_999")
        self.assertEqual(self.proforma.destination_sync_status, "SYNCED")

    @patch("httpx.Client")
    def test_full_sync_with_client_creation(self, mock_client_cls):
        """Verifies complete end-to-end sync when client is not found in ERP: creates client, then creates proforma."""
        self.customer.external_client_id = None
        
        mock_http = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_http
        
        # 1. Search returns empty (customer not found)
        mock_search_resp = MagicMock()
        mock_search_resp.status_code = 200
        mock_search_resp.json.return_value = {"ok": True, "customers": []}
        mock_http.get.return_value = mock_search_resp
        
        # 2. Customer creation returns new external ID
        mock_cust_create_resp = MagicMock()
        mock_cust_create_resp.status_code = 201
        mock_cust_create_resp.json.return_value = {
            "ok": True,
            "id": "cust_new_remote_555",
            "customer": {"id": "cust_new_remote_555", "name": "Test Enterprise Pvt Ltd"}
        }
        
        # 3. Proforma creation returns doc ID
        mock_doc_create_resp = MagicMock()
        mock_doc_create_resp.status_code = 201
        mock_doc_create_resp.json.return_value = {
            "ok": True,
            "id": "doc_remote_777",
            "number": "PI-2026-TEST-001"
        }
        
        mock_http.post.side_effect = [mock_cust_create_resp, mock_doc_create_resp]
        
        result = DestinationSyncService.sync_proforma_to_destination(
            self.mock_db, proforma_id=202, force_retry=True
        )
        
        self.assertTrue(result["ok"])
        self.assertEqual(result["external_client_id"], "cust_new_remote_555")
        self.assertEqual(result["external_proforma_id"], "doc_remote_777")
        self.assertEqual(self.customer.external_client_id, "cust_new_remote_555")
        self.assertEqual(self.proforma.destination_sync_status, "SYNCED")
        self.assertEqual(self.proforma.external_proforma_id, "doc_remote_777")
        self.assertIsNotNone(self.proforma.destination_synced_at)

    @patch("httpx.Client")
    def test_sync_failure_preserves_local_proforma(self, mock_client_cls):
        """
        CRITICAL RESILIENCE RULE:
        When destination ERP is unreachable (HTTP 503 / Network Timeout),
        the local Proforma Invoice MUST NEVER be rolled back, deleted, or invalidated.
        The failure must be safely recorded with status FAILED and sanitized error.
        """
        self.customer.external_client_id = None
        
        mock_http = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_http
        
        # Simulate HTTP 503 Deployment Unavailable error from destination ERP
        err_503 = Exception("HTTP 503: The deployment is currently unavailable")
        mock_http.get.side_effect = err_503
        mock_http.post.side_effect = err_503
        
        result = DestinationSyncService.sync_proforma_to_destination(
            self.mock_db, proforma_id=202, force_retry=True
        )
        
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "FAILED")
        self.assertIn("503", result["error"])
        
        # Verify local proforma invoice was preserved intact
        self.assertEqual(self.proforma.id, 202)
        self.assertEqual(self.proforma.doc_number, "PI-2026-TEST-001")
        self.assertEqual(self.proforma.destination_sync_status, "FAILED")
        self.assertIn("503", self.proforma.destination_sync_error)
        self.assertEqual(self.proforma.destination_sync_attempts, 1)


if __name__ == "__main__":
    unittest.main()
