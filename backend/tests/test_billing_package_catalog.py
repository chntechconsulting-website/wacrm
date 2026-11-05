import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.billing_catalog import (
    DEFAULT_WAHRMS_BUNDLES,
    WAHRMS_PACKAGE_CODES,
    enrich_bundle_items_with_plans,
    extract_plan_code,
    get_bundle_plans,
    get_catalog_plans,
    get_default_bundle,
    validate_custom_plan_items
)


EXPECTED_PACKAGES = {
    "hr_atm": {
        "name": "HR + ATM",
        "plans": {"pro": 40, "business": 55, "custom": None},
        "features": [
            "Core HR & Employee Directory",
            "Attendance & Time Tracking",
            "Leave & Holiday Management",
            "Biometric Device Integration",
        ],
    },
    "hr_payroll": {
        "name": "HR + Payroll",
        "plans": {"pro": 45, "business": 60, "custom": None},
        "features": [
            "Core HR & Employee Profiles",
            "Statutory Payroll Engine",
            "PF, ESI, PT & TDS Filings",
            "One-Click Payslips & Direct Bank Advice",
        ],
    },
    "hr_atm_payroll": {
        "name": "HR + ATM + Payroll",
        "plans": {"pro": 50, "business": 70, "custom": None},
        "features": [
            "Core HR & Lifecycle Management",
            "Biometric Attendance Sync",
            "Statutory Payroll & Compliance Engine",
            "One-Click Payslips & Direct Bank Advice",
        ],
    },
    "bio_payroll": {
        "name": "Biometric + Payroll",
        "plans": {"pro": 45, "business": 60, "custom": None},
        "features": [
            "Biometric Device Integration",
            "Attendance Management",
            "Payroll Processing",
            "PF, ESI & Statutory Compliance",
            "Payslip Generation",
        ],
    },
}


class TestBillingPackageCatalog(unittest.TestCase):
    def test_exactly_four_packages_in_display_order(self):
        self.assertEqual(
            WAHRMS_PACKAGE_CODES,
            ["hr_atm", "hr_payroll", "hr_atm_payroll", "bio_payroll"],
        )
        self.assertEqual(len(DEFAULT_WAHRMS_BUNDLES), 4)
        self.assertEqual(len(set(WAHRMS_PACKAGE_CODES)), 4)

    def test_package_names_and_features_are_preserved(self):
        for code, expected in EXPECTED_PACKAGES.items():
            bundle = get_default_bundle(code)
            self.assertIsNotNone(bundle)
            self.assertEqual(bundle["name"], expected["name"])
            self.assertEqual(bundle["features"], expected["features"])

    def test_all_twelve_plan_combinations_have_expected_rates(self):
        for code, expected in EXPECTED_PACKAGES.items():
            plans = get_catalog_plans(code)
            self.assertEqual([plan["code"] for plan in plans], ["pro", "business", "custom"])
            self.assertEqual(
                {plan["code"]: plan["rate"] for plan in plans},
                expected["plans"],
            )

    def test_legacy_bundle_items_are_enriched_without_losing_existing_data(self):
        legacy_items = [
            {
                "item_code": "HR_ATM_SUB",
                "name": "WAHRMS HR + Attendance Subscription",
                "description": "WAHRMS HR + Payroll  + Biometric  Integration",
                "hsn": "998314",
                "qty": 120,
                "rate": 45.0,
                "gstRate": 0.18,
                "discount": 0.0,
            },
            {
                "item_code": "BIO_INTEGRATION",
                "name": "Biometric Integration",
                "description": "Biometric Integration",
                "hsn": "998314",
                "qty": 1,
                "rate": 4999.0,
            },
        ]

        enriched = enrich_bundle_items_with_plans("hr_atm", legacy_items)
        subscription = enriched[0]

        self.assertEqual(subscription["rate"], 45.0)
        self.assertEqual(subscription["billingBasis"], "employee_month")
        self.assertEqual(
            [plan["code"] for plan in subscription["plans"]],
            ["pro", "business", "custom"],
        )
        self.assertEqual(subscription["plans"][0]["rate"], 40.0)
        self.assertIsNone(subscription["plans"][2]["rate"])
        self.assertEqual(enriched[1]["rate"], 4999.0)
        self.assertNotIn("plans", enriched[1])

    def test_existing_plan_metadata_is_not_overwritten(self):
        items = [
            {
                "item_code": "HR_PAYROLL_SUB",
                "name": "WAHRMS HR + Payroll Subscription",
                "plans": [
                    {"code": "pro", "name": "Pro", "rate": 46, "isCustom": False}
                ],
            }
        ]
        enriched = enrich_bundle_items_with_plans("hr_payroll", items)
        self.assertEqual(enriched[0]["plans"][0]["rate"], 46)

    def test_bundle_plans_can_come_from_items_or_catalogue(self):
        items = [
            {
                "item_code": "BIO_PAYROLL_SUB",
                "name": "WAHRMS Biometric + Payroll Subscription",
                "plans": [
                    {"code": "pro", "name": "Pro", "rate": 45, "isCustom": False}
                ],
            }
        ]
        self.assertEqual(get_bundle_plans("bio_payroll", items)[0]["rate"], 45)
        self.assertEqual(get_bundle_plans("bio_payroll")[0]["rate"], 45)
        self.assertEqual(get_bundle_plans("unknown"), [])

    def test_custom_plan_requires_a_positive_negotiated_rate(self):
        self.assertIn(
            "negotiated per-employee rate",
            validate_custom_plan_items(
                [{"isBundleDetail": True, "planCode": "custom", "rate": ""}]
            ),
        )
        self.assertIn(
            "negotiated per-employee rate",
            validate_custom_plan_items(
                [{"isBundleDetail": True, "planCode": "custom", "rate": 0}]
            ),
        )
        self.assertIn(
            "negotiated per-employee rate",
            validate_custom_plan_items(
                [{"isBundleDetail": True, "description": "Plan: Custom", "rate": None}]
            ),
        )
        self.assertIsNone(
            validate_custom_plan_items(
                [{"isBundleDetail": True, "planCode": "custom", "rate": 72.5}]
            )
        )
        self.assertIsNone(
            validate_custom_plan_items(
                [{"isBundleDetail": True, "planCode": "pro", "rate": 0}]
            )
        )

    def test_plan_is_extracted_from_saved_document_lines(self):
        self.assertEqual(extract_plan_code({"planCode": "business"}), "business")
        self.assertEqual(extract_plan_code({"planName": "Custom"}), "custom")
        self.assertEqual(
            extract_plan_code(
                {"description": "WAHRMS HR + ATM Subscription\nPlan: Pro\nDuration: 12 Months"}
            ),
            "pro",
        )
        self.assertEqual(extract_plan_code({"description": "No plan here"}), "")


if __name__ == "__main__":
    unittest.main()
