"""Adds incremental call-log sync columns to employee_office_sim.

Run from the backend directory:
    python migrations/apply_office_sim_sync_migration.py

The FastAPI startup hook also adds these columns automatically. This script is
provided for deployments where startup schema sync is disabled or the service
account cannot run ALTER statements during boot.

Existing Office SIM mappings start in NOT_CONFIGURED, so upgrading never
imports historical call-log rows. The employee must explicitly enable sync,
which captures a fresh activation baseline.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text

from database import engine


def run_migration():
    print("=== Starting Office SIM Sync DB Migration ===")
    inspector = inspect(engine)
    if "employee_office_sim" not in inspector.get_table_names():
        print("Table 'employee_office_sim' does not exist yet; nothing to do.")
        return

    columns = [
        column["name"] for column in inspector.get_columns("employee_office_sim")
    ]

    additions = {
        "sync_status": "VARCHAR(30) NOT NULL DEFAULT 'NOT_CONFIGURED'",
        "sync_activated_at": "DATETIME NULL",
        "sync_baseline_date_ms": "BIGINT NULL",
        "sync_baseline_id": "BIGINT NULL",
        "sync_watermark_date_ms": "BIGINT NULL",
        "sync_watermark_id": "BIGINT NULL",
        "last_successful_sync_at": "DATETIME NULL",
    }

    with engine.begin() as connection:
        for name, definition in additions.items():
            if name in columns:
                print(f"Column '{name}' already exists; skipping.")
                continue
            print(f"Adding '{name}' to employee_office_sim...")
            connection.execute(
                text(
                    f"ALTER TABLE employee_office_sim "
                    f"ADD COLUMN {name} {definition}"
                )
            )

    print("=== Office SIM Sync DB Migration Completed ===")


if __name__ == "__main__":
    run_migration()
