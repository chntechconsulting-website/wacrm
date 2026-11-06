import unittest

from services.billing_terms import (
    WAHRMS_TERMS_AND_CONDITIONS,
    resolve_billing_terms,
)


class BillingTermsTests(unittest.TestCase):
    def test_quotation_and_proforma_default_to_wahrms_terms(self):
        for doc_type in ("quotation", "proforma"):
            with self.subTest(doc_type=doc_type):
                self.assertEqual(
                    resolve_billing_terms(None, doc_type),
                    WAHRMS_TERMS_AND_CONDITIONS,
                )
                self.assertEqual(
                    resolve_billing_terms("   ", doc_type),
                    WAHRMS_TERMS_AND_CONDITIONS,
                )

    def test_legacy_proforma_terms_are_replaced(self):
        legacy_terms = (
            "1. 100% advance payment against Proforma Invoice.\n"
            "2. Service will be activated upon payment confirmation.\n"
            "3. Taxes applicable as per GST guidelines."
        )
        self.assertEqual(
            resolve_billing_terms(legacy_terms, "proforma"),
            WAHRMS_TERMS_AND_CONDITIONS,
        )
        self.assertEqual(
            resolve_billing_terms(
                "1. Software access activates upon payment.\n"
                "2. Prices subject to applicable GST.",
                "proforma",
            ),
            WAHRMS_TERMS_AND_CONDITIONS,
        )

    def test_custom_terms_are_preserved(self):
        self.assertEqual(
            resolve_billing_terms("Custom commercial terms.", "proforma"),
            "Custom commercial terms.",
        )
        self.assertEqual(
            resolve_billing_terms("Custom commercial terms.", "quotation"),
            "Custom commercial terms.",
        )

    def test_invoice_terms_are_not_replaced(self):
        self.assertEqual(
            resolve_billing_terms("Finance-specific terms.", "invoice"),
            "Finance-specific terms.",
        )
        self.assertEqual(resolve_billing_terms(None, "invoice"), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
