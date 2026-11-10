"""Adds optional mobile-SIM metadata columns to the existing call_logs table.

Run from the backend directory:
    python migrations/apply_mobile_sim_call_migration.py

The FastAPI startup hook also adds these columns automatically. This script is
provided for deployments where startup schema sync is disabled or the service
account cannot run ALTER statements during boot.

The `native_call_reference` column is the stable identity of one Android
CallLog row. It is backfilled only from legacy history rows whose
`provider_call_id` is provably that same reference, then protected by a unique
index so a concurrent live sync and history sync cannot insert two rows for one
physical call.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text

from database import engine


def run_migration():
    print("=== Starting Mobile SIM Call DB Migration ===")
    inspector = inspect(engine)
    columns = [column["name"] for column in inspector.get_columns("call_logs")]
    is_mysql = engine.dialect.name == "mysql"

    additions = {
        "sim_account_id": "VARCHAR(100) NULL",
        "sim_label": "VARCHAR(100) NULL",
        "sim_slot": "INT NULL",
        "native_call_reference": "VARCHAR(100) NULL",
    }

    with engine.begin() as connection:
        for name, definition in additions.items():
            if name in columns:
                print(f"Column '{name}' already exists; skipping.")
                continue
            print(f"Adding '{name}' to call_logs...")
            connection.execute(text(f"ALTER TABLE call_logs ADD COLUMN {name} {definition}"))

        # Backfill only rows that were created by the device-history sync and
        # therefore already stored the native reference as provider_call_id.
        result = connection.execute(text(
            "UPDATE call_logs SET native_call_reference = provider_call_id "
            "WHERE native_call_reference IS NULL "
            "AND provider IN ('MOBILE_SIM', 'DIRECT_DIAL') "
            "AND provider_call_id LIKE 'MOBILE\\_%'"
        ))
        print(f"Backfilled native_call_reference for {result.rowcount or 0} row(s).")

        indexes = {index["name"] for index in inspector.get_indexes("call_logs")}
        if "ix_call_logs_native_call_reference" in indexes:
            print("Unique native-reference index already exists; skipping.")
        elif is_mysql:
            # Existing duplicates would make this fail loudly instead of
            # silently dropping the guard.
            connection.execute(text(
                "ALTER TABLE call_logs ADD UNIQUE INDEX "
                "ix_call_logs_native_call_reference (native_call_reference)"
            ))
            print("Added unique native-reference index.")
        else:
            connection.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ix_call_logs_native_call_reference "
                "ON call_logs (native_call_reference)"
            ))
            print("Added unique native-reference index.")

    print("=== Mobile SIM Call DB Migration Completed ===")


if __name__ == "__main__":
    run_migration()
