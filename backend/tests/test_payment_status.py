import unittest

from utils.payment_status import (
    FINANCE_STATUS_CANCELLED,
    FINANCE_STATUS_PAID,
    FINANCE_STATUS_PENDING,
    FINANCE_STATUS_REJECTED,
    PAYMENT_STATUS_PAID,
    PAYMENT_STATUS_PARTIALLY_PAID,
    PAYMENT_STATUS_PENDING,
    finance_status_filter_values,
    normalize_finance_status,
    normalize_payment_status,
)


class PaymentStatusTests(unittest.TestCase):
    def test_lowercase_proforma_values_are_normalized(self):
        self.assertEqual(normalize_payment_status("unpaid"), PAYMENT_STATUS_PENDING)
        self.assertEqual(normalize_payment_status("paid"), PAYMENT_STATUS_PAID)
        self.assertEqual(
            normalize_payment_status("partially paid"),
            PAYMENT_STATUS_PARTIALLY_PAID,
        )

    def test_finance_status_is_always_canonical(self):
        self.assertEqual(normalize_finance_status("unpaid"), FINANCE_STATUS_PENDING)
        self.assertEqual(
            normalize_finance_status("PAYMENT PENDING"), FINANCE_STATUS_PENDING
        )
        self.assertEqual(normalize_finance_status("paid"), FINANCE_STATUS_PAID)
        self.assertEqual(normalize_finance_status("REJECTED"), FINANCE_STATUS_REJECTED)
        self.assertEqual(
            normalize_finance_status("cancelled"), FINANCE_STATUS_CANCELLED
        )

    def test_pending_filter_includes_legacy_values(self):
        values = finance_status_filter_values("PAYMENT_PENDING")
        self.assertIn("PAYMENT_PENDING", values)
        self.assertIn("UNPAID", values)
        self.assertIn("PENDING", values)
        self.assertIn("PARTIALLY_PAID", values)

    def test_paid_filter_includes_lowercase_value(self):
        values = finance_status_filter_values("PAID")
        self.assertIn("PAID", values)
        self.assertIn("SUCCESS", values)
        self.assertIn("CONFIRMED", values)


if __name__ == "__main__":
    unittest.main(verbosity=2)
