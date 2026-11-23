"""Add indexes used by the WAQuote document list.

The list endpoint orders by ``created_at DESC`` and can narrow by document type
or payment status. Without these indexes MySQL reports ``Using filesort`` for
every page request.

Safe to run more than once: existing indexes are skipped.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import inspect, text

from database import engine


INDEXES = {
    "ix_quotations_created_at": "(`created_at`)",
    "ix_quotations_type_created_at": "(`doc_type`, `created_at`)",
    "ix_quotations_payment_created_at": "(`payment_status`, `created_at`)",
}


def run_migration():
    print("Starting migration: add WAQuote list indexes...")
    inspector = inspect(engine)
    existing = {index["name"] for index in inspector.get_indexes("quotations")}

    with engine.connect() as conn:
        for name, columns in INDEXES.items():
            if name in existing:
                print(f"Index '{name}' already exists.")
                continue
            print(f"Creating index '{name}' on {columns}...")
            conn.execute(text(f"CREATE INDEX {name} ON quotations {columns}"))
            conn.commit()
            print(f"Created index '{name}'.")

    print("Migration completed.")


if __name__ == "__main__":
    run_migration()
