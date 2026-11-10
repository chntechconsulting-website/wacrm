"""Additive production migration for Support history and leave coverage.

Repeatable and non-destructive:

1. Creates ``support_interactions`` (append-only interaction timeline).
2. Creates ``employee_leaves`` (Support leave/approval audit trail).
3. Creates ``support_coverage_assignments`` (temporary, auditable backup
   coverage for one customer during an approved leave).
4. Adds any missing indexes required by the ORM models.

No existing table, customer, handover, employee, call or Sales record is
modified, deleted or reassigned. The permanent Support owner remains
``support_handoffs.assigned_agent_id``.
"""

import os
import sys

# Ensure backend root is on Python sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import inspect, text

import models  # noqa: F401 - registers every mapped table
from database import Base, engine


TABLES = ("support_interactions", "employee_leaves", "support_coverage_assignments")

INDEXES = {
    "support_interactions": {
        "ix_support_interactions_customer_time": "(customer_id, interaction_at)",
        "ix_support_interactions_lead_time": "(lead_id, interaction_at)",
    },
    "employee_leaves": {
        "ix_employee_leaves_employee_dates": "(employee_id, start_date, end_date)",
        "ix_employee_leaves_status_dates": "(status, start_date, end_date)",
    },
    "support_coverage_assignments": {
        "ix_support_coverage_backup_status_dates": (
            "(backup_employee_id, status, start_date, end_date)"
        ),
        "ix_support_coverage_lead_status_dates": (
            "(lead_id, status, start_date, end_date)"
        ),
        "ix_support_coverage_original_status": (
            "(original_employee_id, status)"
        ),
    },
}


def _table_exists(inspector, table_name):
    return table_name in inspector.get_table_names()


def run_support_history_coverage_migration():
    print("=== Starting Support History & Coverage Migration ===")

    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    missing = [name for name in TABLES if name not in existing]

    if missing:
        print("Creating missing tables: " + ", ".join(missing))
        Base.metadata.create_all(
            bind=engine,
            tables=[Base.metadata.tables[name] for name in missing],
            checkfirst=True,
        )
    else:
        print("All Support history/coverage tables already exist.")

    # ``create_all`` adds the ORM indexes for new tables. This pass also covers
    # partially-created tables from an interrupted deployment.
    for table_name, indexes in INDEXES.items():
        if not _table_exists(inspect(engine), table_name):
            print(f"Table '{table_name}' is still missing; index check skipped.")
            continue
        try:
            present = {
                index["name"] for index in inspect(engine).get_indexes(table_name)
            }
        except Exception as exc:
            print(f"Index inspection note for '{table_name}': {exc}")
            present = set()
        with engine.begin() as conn:
            for index_name, columns in indexes.items():
                if index_name in present:
                    print(f"Index '{index_name}' already present.")
                    continue
                print(f"Creating index '{index_name}' on '{table_name}'...")
                try:
                    conn.execute(
                        text(
                            f"CREATE INDEX {index_name} "
                            f"ON {table_name} {columns}"
                        )
                    )
                except Exception as exc:
                    print(f"Index creation note for '{index_name}': {exc}")

    # Foreign keys are created with the tables. Report any missing ones instead
    # of mutating populated tables during a deployment.
    for table_name in TABLES:
        if not _table_exists(inspect(engine), table_name):
            continue
        try:
            foreign_keys = inspect(engine).get_foreign_keys(table_name)
        except Exception as exc:
            print(f"Foreign-key inspection note for '{table_name}': {exc}")
            continue
        print(
            f"Table '{table_name}': {len(foreign_keys)} foreign key(s) verified."
        )

    print("=== Support History & Coverage Migration Complete ===")


if __name__ == "__main__":
    run_support_history_coverage_migration()
