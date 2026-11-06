import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from integrations.waquote.router import get_wahrms_bundles
from services.billing_catalog import (
    BIOMETRIC_BUNDLE_CODES,
    WAHRMS_PACKAGE_CODES,
)


class TestBiometricBundleSeeding(unittest.TestCase):
    def test_all_biometric_bundles_are_seeded_when_missing(self):
        db = MagicMock()
        db.query.return_value.all.return_value = []
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        result = get_wahrms_bundles(category="all", db=db, current_user=None)

        self.assertTrue(result["ok"])
        self.assertEqual(
            db.add.call_count,
            len(WAHRMS_PACKAGE_CODES) + len(BIOMETRIC_BUNDLE_CODES),
        )
        added_codes = {call.args[0].bundle_code for call in db.add.call_args_list}
        for code in BIOMETRIC_BUNDLE_CODES:
            self.assertIn(code, added_codes)
        self.assertGreaterEqual(db.commit.call_count, 2)

    def test_existing_biometric_bundles_are_not_overwritten(self):
        existing_codes = set(BIOMETRIC_BUNDLE_CODES)
        db = MagicMock()
        db.query.return_value.all.return_value = [
            MagicMock(bundle_code=code) for code in existing_codes
        ]
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        result = get_wahrms_bundles(category="BIOMETRIC", db=db, current_user=None)

        self.assertTrue(result["ok"])
        added_codes = {call.args[0].bundle_code for call in db.add.call_args_list}
        self.assertFalse(added_codes & existing_codes)


if __name__ == "__main__":
    unittest.main()
