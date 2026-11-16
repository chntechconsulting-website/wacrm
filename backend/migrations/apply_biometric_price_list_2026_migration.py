"""Sync the 2026 biometric device price list into the live bundle master.

Repeatable and non-destructive:

1. Updates only rows whose ``bundle_code`` is a per-device ``bio_dev_*``
   catalogue code. Name, pricing, features and display order are taken from
   ``services.billing_catalog.DEFAULT_BIOMETRIC_BUNDLES``.
2. Inserts any missing device (for example the new UFACE302 4G).
3. Never touches the three biometric package bundles (``bio_standard``,
   ``bio_atm``, ``bio_enterprise``), any WAHRMS bundle, or any saved
   quotation/proforma/invoice document.

Running it more than once is safe: unchanged rows are reported, not rewritten.
"""

import os
import sys
from datetime import datetime

from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import SessionLocal
from models.quotation import WAHRMSBundle
from services.billing_catalog import (
    BIOMETRIC_DEVICE_BUNDLE_CODES,
    DEFAULT_BIOMETRIC_BUNDLES,
)

SYNC_FIELDS = (
    "category",
    "name",
    "tagline",
    "description",
    "badge",
    "features",
    "items",
    "sort_order",
)

MIGRATION_KEY = "2026_biometric_price_list_v1"


def _ensure_migration_tracking(db):
    db.execute(
        text(
            "CREATE TABLE IF NOT EXISTS wacrm_schema_migrations ("
            "migration_key VARCHAR(191) NOT NULL PRIMARY KEY, "
            "applied_at DATETIME NOT NULL)"
        )
    )


def _is_applied(db) -> bool:
    _ensure_migration_tracking(db)
    row = db.execute(
        text("SELECT 1 FROM wacrm_schema_migrations WHERE migration_key = :key"),
        {"key": MIGRATION_KEY},
    ).first()
    return row is not None


def apply_migration():
    print("Applying 2026 biometric device price list migration...")

    device_codes = set(BIOMETRIC_DEVICE_BUNDLE_CODES)
    device_bundles = [
        bundle
        for bundle in DEFAULT_BIOMETRIC_BUNDLES
        if bundle["bundle_code"] in device_codes
    ]

    db = SessionLocal()
    inserted = 0
    updated = 0
    unchanged = 0

    try:
        if _is_applied(db):
            print(f"Migration {MIGRATION_KEY} already applied. Nothing to do.")
            return

        for bundle in device_bundles:
            row = (
                db.query(WAHRMSBundle)
                .filter(WAHRMSBundle.bundle_code == bundle["bundle_code"])
                .first()
            )

            if row is None:
                db.add(WAHRMSBundle(**bundle))
                inserted += 1
                print(f"  + inserted {bundle['bundle_code']} ({bundle['name']})")
                continue

            changes = {}
            for field in SYNC_FIELDS:
                new_value = bundle[field]
                if getattr(row, field) != new_value:
                    changes[field] = new_value

            if changes:
                for field, value in changes.items():
                    setattr(row, field, value)
                updated += 1
                price = bundle["items"][0]["rate"] if bundle.get("items") else "-"
                print(
                    f"  ~ updated {bundle['bundle_code']} "
                    f"({bundle['name']}) rate={price}"
                )
            else:
                unchanged += 1

        total_devices = (
            db.query(WAHRMSBundle)
            .filter(WAHRMSBundle.bundle_code.in_(device_codes))
            .count()
        )
        if total_devices != len(device_codes):
            raise RuntimeError(
                "Biometric device bundle count mismatch after migration: "
                f"{total_devices} != {len(device_codes)}"
            )

        db.execute(
            text(
                "INSERT INTO wacrm_schema_migrations (migration_key, applied_at) "
                "VALUES (:key, :applied_at)"
            ),
            {"key": MIGRATION_KEY, "applied_at": datetime.utcnow()},
        )
        db.commit()
        print(
            "Done. "
            f"inserted={inserted}, updated={updated}, "
            f"unchanged={unchanged}, device_rows={total_devices}/{len(device_codes)}"
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    apply_migration()
