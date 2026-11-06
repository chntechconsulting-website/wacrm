import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.billing_catalog import (
    BIOMETRIC_BUNDLE_CODES,
    BIOMETRIC_DEVICE_BUNDLE_CODES,
    DEFAULT_BIOMETRIC_BUNDLES,
    DEFAULT_BIOMETRIC_DEVICES,
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


EXPECTED_BIOMETRIC_PRICES = {
    "bio_dev_ai_mercury": 10722,
    "bio_dev_ai_urans": 10722,
    "bio_dev_ai_neptune": 13809,
    "bio_dev_ai_neptune_bat": 14732,
    "bio_dev_ai_pluto": 19130,
    "bio_dev_ai_mars": 23038,
    "bio_dev_ai_mars_wifi": 23571,
    "bio_dev_ai_mars_palm": 25539,
    "bio_dev_ai_jupiter": 33420,
    "bio_dev_ai_orcus": 13949,
    "bio_dev_ai_magnum_lite": 15151,
    "bio_dev_ai_magnum": 18307,
    "bio_dev_ai_magnum_wifi": 20718,
    "bio_dev_mb160": 12800,
    "bio_dev_mb160_bat": 13785,
    "bio_dev_mb160_bat_wifi_lan_bat": 16151,
    "bio_dev_mb20": 10722,
    "bio_dev_uface302": 25804,
    "bio_dev_silkbio_101tc_id_bat": 18181,
    "bio_dev_ai_eris": 26724,
    "bio_dev_ai_arion": 34315,
    "bio_dev_k30_bat": 6841,
    "bio_dev_k30_wifi_bat": 8633,
    "bio_dev_k90": 6553,
    "bio_dev_f22_wifi": 12322,
    "bio_dev_x990": 15012,
    "bio_dev_iclock_990": 23149,
    "bio_dev_fr1200": 6194,
    "bio_dev_kr500_e": 1651,
    "bio_dev_x7": 4009,
    "bio_dev_f_18": 16927,
    "bio_dev_sf_100": 10253,
    "bio_dev_sc_405": 11684,
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

    def test_all_33_biometric_devices_are_in_the_catalogue(self):
        self.assertEqual(len(DEFAULT_BIOMETRIC_DEVICES), 33)
        self.assertEqual(
            {device["code"] for device in DEFAULT_BIOMETRIC_DEVICES},
            set(EXPECTED_BIOMETRIC_PRICES),
        )
        self.assertEqual(len(BIOMETRIC_DEVICE_BUNDLE_CODES), 33)
        self.assertEqual(set(BIOMETRIC_DEVICE_BUNDLE_CODES), set(EXPECTED_BIOMETRIC_PRICES))

    def test_biometric_device_groups_match_the_price_list(self):
        counts = {}
        for device in DEFAULT_BIOMETRIC_DEVICES:
            counts[device["group"]] = counts.get(device["group"], 0) + 1
        self.assertEqual(counts, {"face_finger": 21, "finger": 6, "reader": 6})

    def test_every_biometric_device_bundle_uses_the_exact_dealer_price_and_gst(self):
        bundles_by_code = {
            bundle["bundle_code"]: bundle for bundle in DEFAULT_BIOMETRIC_BUNDLES
        }
        for code, expected_price in EXPECTED_BIOMETRIC_PRICES.items():
            bundle = bundles_by_code[code]
            self.assertEqual(bundle["category"], "BIOMETRIC")
            self.assertEqual(bundle["items"][0]["hsn"], "85437099")
            self.assertEqual(bundle["items"][0]["rate"], float(expected_price))
            self.assertEqual(bundle["items"][0]["gstRate"], 0.18)
            self.assertEqual(bundle["items"][0]["qty"], 1)
            self.assertIn("GST 18% Extra", bundle["features"])
            self.assertEqual(get_bundle_plans(code), [])

    def test_existing_biometric_packages_are_preserved(self):
        bundles_by_code = {
            bundle["bundle_code"]: bundle for bundle in DEFAULT_BIOMETRIC_BUNDLES
        }
        self.assertEqual(
            bundles_by_code["bio_standard"]["items"][0]["rate"], 22400.0
        )
        self.assertEqual(bundles_by_code["bio_atm"]["items"][0]["rate"], 18500.0)
        self.assertEqual(
            bundles_by_code["bio_enterprise"]["items"][0]["rate"], 44800.0
        )
        self.assertIn("bio_standard", BIOMETRIC_BUNDLE_CODES)
        self.assertIn("bio_atm", BIOMETRIC_BUNDLE_CODES)
        self.assertIn("bio_enterprise", BIOMETRIC_BUNDLE_CODES)

    def test_get_default_bundle_resolves_a_biometric_device(self):
        bundle = get_default_bundle("bio_dev_ai_mars_wifi")
        self.assertIsNotNone(bundle)
        self.assertEqual(bundle["name"], "AI MARS-WIFI")
        self.assertEqual(bundle["items"][0]["rate"], 23571.0)
        self.assertEqual(get_default_bundle("bio_dev_missing"), None)


if __name__ == "__main__":
    unittest.main()
