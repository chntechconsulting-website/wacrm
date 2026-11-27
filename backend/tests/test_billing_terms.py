import unittest

from services.billing_terms import (
    BIOMETRIC_TERMS_AND_CONDITIONS,
    WAHRMS_TERMS_AND_CONDITIONS,
    default_terms_for_category,
    resolve_billing_terms,
)


class BillingTermsTests(unittest.TestCase):
    def test_quotations_default_to_category_terms(self):
        self.assertEqual(
            resolve_billing_terms(None, "quotation"),
            WAHRMS_TERMS_AND_CONDITIONS,
        )
        self.assertEqual(
            resolve_billing_terms("   ", "quotation"),
            WAHRMS_TERMS_AND_CONDITIONS,
        )
        self.assertEqual(
            resolve_billing_terms(None, "quotation", "biometric"),
            BIOMETRIC_TERMS_AND_CONDITIONS,
        )

    def test_proforma_invoices_never_have_terms(self):
        for doc_type in ("proforma", "PROFORMA"):
            with self.subTest(doc_type=doc_type):
                self.assertEqual(resolve_billing_terms(None, doc_type), "")
                self.assertEqual(resolve_billing_terms("   ", doc_type), "")
                self.assertEqual(
                    resolve_billing_terms("Custom commercial terms.", doc_type),
                    "",
                )
                self.assertEqual(
                    resolve_billing_terms(None, doc_type, "biometric"),
                    "",
                )
                self.assertEqual(
                    resolve_billing_terms(
                        BIOMETRIC_TERMS_AND_CONDITIONS, doc_type, "biometric"
                    ),
                    "",
                )
                self.assertEqual(
                    resolve_billing_terms(
                        WAHRMS_TERMS_AND_CONDITIONS, doc_type, "wahrms"
                    ),
                    "",
                )

    def test_legacy_proforma_terms_are_replaced_on_quotations(self):
        legacy_terms = (
            "1. Payment terms: 100% advance payment against this Proforma Invoice.\n"
            "2. Bank transfers to be credited to the Axis Bank account mentioned above.\n"
            "3. Materials will be dispatched upon payment credit receipt.\n"
            "4. Goods once sold will not be taken back."
        )
        self.assertEqual(
            resolve_billing_terms(legacy_terms, "quotation"),
            WAHRMS_TERMS_AND_CONDITIONS,
        )
        legacy_terms = (
            "1. 100% advance payment against Proforma Invoice.\n"
            "2. Service will be activated upon payment confirmation.\n"
            "3. Taxes applicable as per GST guidelines."
        )
        self.assertEqual(
            resolve_billing_terms(legacy_terms, "quotation"),
            WAHRMS_TERMS_AND_CONDITIONS,
        )
        self.assertEqual(
            resolve_billing_terms(
                "1. Software access activates upon payment.\n"
                "2. Prices subject to applicable GST.",
                "quotation",
            ),
            WAHRMS_TERMS_AND_CONDITIONS,
        )

    def test_custom_terms_are_preserved_on_quotations(self):
        self.assertEqual(
            resolve_billing_terms("Custom commercial terms.", "quotation"),
            "Custom commercial terms.",
        )

    def test_biometric_category_uses_biometric_terms(self):
        self.assertEqual(
            default_terms_for_category("biometric"),
            BIOMETRIC_TERMS_AND_CONDITIONS,
        )
        self.assertEqual(
            default_terms_for_category("BIOMETRIC"),
            BIOMETRIC_TERMS_AND_CONDITIONS,
        )
        self.assertEqual(
            default_terms_for_category("wahrms"),
            WAHRMS_TERMS_AND_CONDITIONS,
        )
        self.assertIn("All civil works must be done by the client.", BIOMETRIC_TERMS_AND_CONDITIONS)
        self.assertIn("75% advance payment", BIOMETRIC_TERMS_AND_CONDITIONS)
        self.assertIn(
            "remaining 25% balance payment",
            BIOMETRIC_TERMS_AND_CONDITIONS,
        )

    def test_biometric_quotations_resolve_to_biometric_terms(self):
        legacy_terms = (
            "1. Payment terms: 100% advance payment against this Proforma Invoice.\n"
            "2. Bank transfers to be credited to the Axis Bank account mentioned above.\n"
            "3. Materials will be dispatched upon payment credit receipt.\n"
            "4. Goods once sold will not be taken back."
        )
        self.assertEqual(
            resolve_billing_terms(None, "quotation", "biometric"),
            BIOMETRIC_TERMS_AND_CONDITIONS,
        )
        self.assertEqual(
            resolve_billing_terms("   ", "quotation", "BIOMETRIC"),
            BIOMETRIC_TERMS_AND_CONDITIONS,
        )
        self.assertEqual(
            resolve_billing_terms(legacy_terms, "quotation", "biometric"),
            BIOMETRIC_TERMS_AND_CONDITIONS,
        )
        self.assertEqual(
            resolve_billing_terms("Biometric Terms", "quotation", "biometric"),
            BIOMETRIC_TERMS_AND_CONDITIONS,
        )
        self.assertEqual(
            resolve_billing_terms(
                BIOMETRIC_TERMS_AND_CONDITIONS, "quotation", "biometric"
            ),
            BIOMETRIC_TERMS_AND_CONDITIONS,
        )
        self.assertEqual(
            resolve_billing_terms(
                "Custom biometric terms.", "quotation", "biometric"
            ),
            "Custom biometric terms.",
        )
        self.assertEqual(
            resolve_billing_terms(None, "quotation", "wahrms"),
            WAHRMS_TERMS_AND_CONDITIONS,
        )

    def test_invoice_terms_are_not_replaced(self):
        self.assertEqual(
            resolve_billing_terms("Finance-specific terms.", "invoice"),
            "Finance-specific terms.",
        )
        self.assertEqual(resolve_billing_terms(None, "invoice"), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
