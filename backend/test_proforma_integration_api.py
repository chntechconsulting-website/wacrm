import os
import sys
import unittest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

# Add backend directory to path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from main import app
from database import get_db, SessionLocal
from models.quotation import Quotation
from models.customer import Customer
from models.integration import IntegrationConfig
from integrations.proforma.auth import DEFAULT_INTEGRATION_KEY

client = TestClient(app)


class TestProformaExternalIntegrationAPI(unittest.TestCase):
    """
    Integration test suite for POST /api/integrations/proforma and related endpoints.
    """

    def setUp(self):
        self.db = SessionLocal()
        self.valid_headers = {
            "X-API-Key": DEFAULT_INTEGRATION_KEY,
            "Content-Type": "application/json"
        }
        self.test_suffix = f"test_{int(datetime.now(timezone.utc).timestamp())}"

    def tearDown(self):
        # Cleanup any test created proformas
        try:
            self.db.query(Quotation).filter(Quotation.doc_number.contains(self.test_suffix)).delete()
            self.db.commit()
        except Exception:
            self.db.rollback()
        finally:
            self.db.close()

    def test_missing_auth_returns_401(self):
        """Verifies that requests without API key header are rejected with 401 Unauthorized."""
        payload = {"companyName": "Acme Test Corp", "lineItems": [{"name": "Item 1", "rate": 1000}]}
        response = client.post("/api/integrations/proforma", json=payload)
        self.assertEqual(response.status_code, 401)
        self.assertIn("Missing", response.json().get("detail", ""))

    def test_invalid_auth_returns_403(self):
        """Verifies that requests with an incorrect API key are rejected with 403 Forbidden."""
        payload = {"companyName": "Acme Test Corp", "lineItems": [{"name": "Item 1", "rate": 1000}]}
        headers = {"X-API-Key": "invalid_wrong_secret_key_12345"}
        response = client.post("/api/integrations/proforma", json=payload, headers=headers)
        self.assertEqual(response.status_code, 403)
        self.assertIn("Invalid", response.json().get("detail", ""))

    def test_successful_proforma_ingest_with_authoritative_tax(self):
        """Verifies successful Proforma creation, customer registration, and authoritative GST calculation."""
        proforma_num = f"PI-TEST-{self.test_suffix}"
        payload = {
            "idempotencyKey": f"idem_{self.test_suffix}",
            "companyName": f"Enterprise Test {self.test_suffix} Pvt Ltd",
            "contactPerson": "Ravi Shankar",
            "phone": "9876500001",
            "email": f"ravi_{self.test_suffix}@test.com",
            "proformaNumber": proforma_num,
            "productCategory": "wahrms",
            "billingAddress": {
                "line1": "100 IT Expressway",
                "city": "Chennai",
                "state": "Tamil Nadu",
                "stateCode": "33",
                "pincode": "600096"
            },
            "lineItems": [
                {
                    "name": "WAHRMS HR + Payroll Suite",
                    "description": "Annual software license",
                    "hsn": "998314",
                    "qty": 2,
                    "rate": 50000.0,
                    "discount": 10000.0,
                    "gstRate": 0.18
                }
            ],
            # Pass arbitrary total to verify CRM authoritative re-computation
            "subtotal": 90000.0,
            "grandTotal": 90000.0  # Deliberately missing the 18% GST (16,200)
        }

        response = client.post("/api/integrations/proforma", json=payload, headers=self.valid_headers)
        self.assertEqual(response.status_code, 201)
        data = response.json()

        self.assertTrue(data["success"])
        self.assertEqual(data["processingStatus"], "CREATED")
        self.assertEqual(data["proformaNumber"], proforma_num)
        self.assertIsNotNone(data["customerId"])

        # Check authoritative summary: (2 * 50000) - 10000 = 90000. 18% GST = 16200. Grand = 106200.
        summary = data["authoritativeSummary"]
        self.assertEqual(summary["taxableSubtotal"], 90000.0)
        self.assertEqual(summary["taxMode"], "intra")
        self.assertEqual(summary["cgst"], 8100.0)
        self.assertEqual(summary["sgst"], 8100.0)
        self.assertEqual(summary["igst"], 0.0)
        self.assertEqual(summary["totalTax"], 16200.0)
        self.assertEqual(summary["grandTotal"], 106200.0)

        # Discrepancy between client's 90,000 and CRM's authoritative 106,200 must generate a warning
        self.assertTrue(len(data.get("warnings") or []) > 0)
        self.assertIn("Authoritative", data["warnings"][0])

    def test_idempotency_duplicate_prevention(self):
        """Verifies that repeating an identical request returns the existing record without duplicating."""
        proforma_num = f"PI-IDEM-{self.test_suffix}"
        idem_key = f"idem_key_{self.test_suffix}"
        payload = {
            "idempotencyKey": idem_key,
            "companyName": f"Idempotent Test {self.test_suffix}",
            "contactPerson": "Aravind",
            "phone": "9840099999",
            "proformaNumber": proforma_num,
            "lineItems": [{"name": "Service 1", "rate": 20000.0, "qty": 1, "gstRate": 0.18}]
        }

        # 1st request -> Created
        resp1 = client.post("/api/integrations/proforma", json=payload, headers=self.valid_headers)
        self.assertEqual(resp1.status_code, 201)
        doc_id_1 = resp1.json()["proformaId"]

        # 2nd request (duplicate retry) -> Authoritatively Verified / Reused
        resp2 = client.post("/api/integrations/proforma", json=payload, headers=self.valid_headers)
        self.assertEqual(resp2.status_code, 201)
        data2 = resp2.json()

        self.assertEqual(data2["proformaId"], doc_id_1)
        self.assertEqual(data2["proformaNumber"], proforma_num)
        self.assertEqual(data2["processingStatus"], "AUTHORITATIVE_VERIFIED")

    def test_get_proforma_by_number(self):
        """Verifies GET /api/integrations/proforma/{number} endpoint."""
        proforma_num = f"PI-GET-{self.test_suffix}"
        payload = {
            "companyName": f"Get Test {self.test_suffix}",
            "contactPerson": "Vikram",
            "phone": "9841122334",
            "proformaNumber": proforma_num,
            "lineItems": [{"name": "ATM Biometric Hardware", "rate": 15000.0, "qty": 1, "gstRate": 0.18}]
        }

        create_resp = client.post("/api/integrations/proforma", json=payload, headers=self.valid_headers)
        self.assertEqual(create_resp.status_code, 201)

        # Now fetch by document number
        fetch_resp = client.get(f"/api/integrations/proforma/{proforma_num}", headers=self.valid_headers)
        self.assertEqual(fetch_resp.status_code, 200)
        data = fetch_resp.json()

        self.assertTrue(data["success"])
        self.assertEqual(data["proformaNumber"], proforma_num)
        self.assertEqual(data["authoritativeSummary"]["grandTotal"], 17700.0)


if __name__ == "__main__":
    unittest.main()
