"""Regression tests for the single canonical Sales "NEW LEAD" status.

The CRM historically stored a fresh Sales lead as either ``NEW`` or
``NEW LEAD``. Both spellings now normalise to ``NEW LEAD`` while the separate
Support status ``NEW`` must stay unchanged.
"""

import os
import sys
import unittest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from services.channel_partner_sync import (
    CHANNEL_PARTNER_INITIAL_CRM_STATUS,
    CHANNEL_PARTNER_TO_CRM_STATUS,
    CRM_TO_CHANNEL_PARTNER_STATUS,
)
from services.excel_service import normalize_status
from utils.lead_status import (
    STATUS_NEW,
    canonical_new_status,
    normalize_lead_status,
)
from utils.support_status import SUPPORT_STATUS_NEW, normalize_support_status


class LeadStatusCanonicalTests(unittest.TestCase):
    def test_new_lead_is_the_single_sales_status(self):
        self.assertEqual(STATUS_NEW, "NEW LEAD")

    def test_legacy_new_spellings_normalise_to_new_lead(self):
        for value in ("NEW", "new", " New ", "NEW LEAD", "new lead", "NEW_LEAD"):
            with self.subTest(value=value):
                self.assertEqual(normalize_lead_status(value), "NEW LEAD")
                self.assertEqual(canonical_new_status(value), "NEW LEAD")

    def test_canonical_helper_preserves_other_statuses(self):
        self.assertIsNone(canonical_new_status(None))
        for value in (
            "ASSIGNED",
            "CONTACTED",
            "INTERESTED",
            "QUALIFIED",
            "TRIAL",
            "WON",
            "CONVERTED_TO_SUPPORT",
            "LOST",
            "FOLLOW-UP",
        ):
            with self.subTest(value=value):
                self.assertEqual(canonical_new_status(value), value)

    def test_support_new_status_is_not_renamed(self):
        self.assertEqual(SUPPORT_STATUS_NEW, "NEW")
        self.assertEqual(normalize_support_status("NEW"), "NEW")

    def test_excel_import_maps_legacy_new_to_new_lead(self):
        self.assertEqual(normalize_status("NEW"), "NEW LEAD")
        self.assertEqual(normalize_status("new lead"), "NEW LEAD")
        self.assertEqual(normalize_status("NEW_LEAD"), "NEW LEAD")
        self.assertEqual(normalize_status(""), "NEW LEAD")

    def test_channel_partner_submitted_status_uses_new_lead(self):
        self.assertEqual(CHANNEL_PARTNER_INITIAL_CRM_STATUS["submitted"], "NEW LEAD")
        self.assertEqual(CHANNEL_PARTNER_TO_CRM_STATUS["submitted"], "NEW LEAD")
        # Both legacy and canonical CRM spellings still push "submitted".
        self.assertEqual(CRM_TO_CHANNEL_PARTNER_STATUS["NEW"], "submitted")
        self.assertEqual(CRM_TO_CHANNEL_PARTNER_STATUS["NEW_LEAD"], "submitted")


if __name__ == "__main__":
    unittest.main()
