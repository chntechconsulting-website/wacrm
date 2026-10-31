"""Adds optional mobile-SIM metadata columns to the existing call_logs table.

Run from the backend directory:
    python migrations/apply_mobile_sim_call_migration.py

The FastAPI startup hook also adds these columns automatically. This script is
provided for deployments where startup schema sync is disabled or the service
account cannot run ALTER statements during boot.
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

    additions = {
        "sim_account_id": "VARCHAR(100) NULL",
        "sim_label": "VARCHAR(100) NULL",
        "sim_slot": "INT NULL",
    }

    with engine.begin() as connection:
        for name, definition in additions.items():
            if name in columns:
                print(f"Column '{name}' already exists; skipping.")
                continue
            print(f"Adding '{name}' to call_logs...")
            connection.execute(text(f"ALTER TABLE call_logs ADD COLUMN {name} {definition}"))

    print("=== Mobile SIM Call DB Migration Completed ===")


if __name__ == "__main__":
    run_migration()
