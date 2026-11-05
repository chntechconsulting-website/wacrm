"""Additive production migration for the Sales -> Support purchase handover.

Repeatable and non-destructive:

1. Adds ``support_handoffs.purchase_snapshot`` (JSON NULL) if missing.
2. Adds ``lead_activities.department`` (VARCHAR(30) NULL) and its index.
3. Backfills the immutable activity department snapshot from the existing
   creator employee. Rows with no attributable employee stay NULL (Admin-only).
4. Captures the immutable purchase snapshot for existing Support handovers.

No customer, quotation, package, add-on, employee or workflow row is created,
deleted, re-assigned or re-priced by this script.
"""

import os
import sys

# Ensure backend root is on Python sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import inspect, text

from database import SessionLocal, engine


def _table_exists(inspector, table_name):
    return table_name in inspector.get_table_names()


def _column_names(inspector, table_name):
    return {column["name"] for column in inspector.get_columns(table_name)}


def run_sales_support_handover_migration():
    print("=== Starting Sales -> Support Purchase Handover Migration ===")

    inspector = inspect(engine)

    if not _table_exists(inspector, "support_handoffs"):
        print("Table 'support_handoffs' does not exist yet. Start the app once, then re-run this migration.")
        return

    support_cols = _column_names(inspector, "support_handoffs")
    activity_cols = (
        _column_names(inspector, "lead_activities")
        if _table_exists(inspector, "lead_activities")
        else set()
    )

    with engine.begin() as conn:
        if "purchase_snapshot" not in support_cols:
            print("Adding 'purchase_snapshot' JSON column to 'support_handoffs'...")
            conn.execute(text(
                "ALTER TABLE support_handoffs ADD COLUMN purchase_snapshot JSON NULL"
            ))
        else:
            print("Column 'support_handoffs.purchase_snapshot' already present.")

        if activity_cols and "department" not in activity_cols:
            print("Adding 'department' VARCHAR(30) column to 'lead_activities'...")
            conn.execute(text(
                "ALTER TABLE lead_activities ADD COLUMN department VARCHAR(30) NULL"
            ))
        elif activity_cols:
            print("Column 'lead_activities.department' already present.")

        if activity_cols:
            indexes = {}
            try:
                indexes = {
                    index["name"] for index in inspect(engine).get_indexes("lead_activities")
                }
            except Exception as exc:
                print(f"Index inspection note: {exc}")
            if "ix_lead_activities_department" not in indexes:
                print("Creating index 'ix_lead_activities_department'...")
                try:
                    conn.execute(text(
                        "CREATE INDEX ix_lead_activities_department "
                        "ON lead_activities (department)"
                    ))
                except Exception as exc:
                    print(f"Index creation note: {exc}")
            else:
                print("Index 'ix_lead_activities_department' already present.")

    # Backfills use the ORM so JSON serialization stays consistent with the
    # application models. Both helpers are additive and idempotent.
    db = SessionLocal()
    try:
        if activity_cols:
            from services.activity_visibility_service import backfill_activity_departments

            updated_activities = backfill_activity_departments(db)
            print(
                "Backfilled department ownership for "
                f"{updated_activities} lead activity row(s)."
            )

        from services.purchase_details_service import backfill_support_purchase_snapshots

        updated_handovers = backfill_support_purchase_snapshots(db)
        print(
            "Captured purchase snapshots for "
            f"{updated_handovers} Support handover(s)."
        )
    except Exception as exc:
        db.rollback()
        print(f"Migration backfill error: {exc}")
        raise
    finally:
        db.close()

    print("=== Sales -> Support Purchase Handover Migration Complete ===")


if __name__ == "__main__":
    run_sales_support_handover_migration()
