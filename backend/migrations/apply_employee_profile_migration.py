"""Additive migration for self-service employee profile fields.

Adds nullable columns only. No existing employee, user, role, department,
assignment or reporting-hierarchy data is modified.

Usage:
    python backend/migrations/apply_employee_profile_migration.py
"""

import os
import sys

sys.path.insert(0, os.path.abspath("backend"))

from sqlalchemy import inspect, text

from database import engine


PROFILE_COLUMNS = {
    "photo_url": "VARCHAR(500) NULL",
    "date_of_birth": "DATE NULL",
    "gender": "VARCHAR(30) NULL",
    "address": "TEXT NULL",
    "date_of_joining": "DATE NULL",
}


def run_migration():
    print("=== Starting Employee Profile DB Migration ===")
    inspector = inspect(engine)
    if "employees" not in inspector.get_table_names():
        print("Employees table does not exist yet; create_all will create it.")
        return

    existing = {column["name"] for column in inspector.get_columns("employees")}
    added = []

    with engine.begin() as conn:
        for column_name, column_type in PROFILE_COLUMNS.items():
            if column_name in existing:
                continue
            print(f"Adding '{column_name}' column to employees table...")
            conn.execute(
                text(
                    f"ALTER TABLE employees "
                    f"ADD COLUMN {column_name} {column_type}"
                )
            )
            added.append(column_name)

    if added:
        print(f"Migration complete. Added: {', '.join(added)}")
    else:
        print("Migration complete. All profile columns already exist.")


if __name__ == "__main__":
    run_migration()
