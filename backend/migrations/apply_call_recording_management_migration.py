"""Adds call-recording lifecycle columns to the existing call_logs table.

Run from the backend directory:
    python migrations/apply_call_recording_management_migration.py

These columns power the mobile/web recording status machine:
AVAILABLE, PENDING_SYNC, RECORDING_UNAVAILABLE, UPLOAD_FAILED and
VERIFICATION_FAILED. The FastAPI startup hook also adds them automatically.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text

from database import engine


ADDITIONS = {
    "recording_status": "VARCHAR(40) NULL",
    "recording_status_detail": "VARCHAR(255) NULL",
    "recording_checksum": "VARCHAR(64) NULL",
    "recording_verified_at": "DATETIME NULL",
    "recording_consent_at": "DATETIME NULL",
}


def run_migration():
    print("=== Starting Call Recording Management DB Migration ===")
    inspector = inspect(engine)
    columns = [column["name"] for column in inspector.get_columns("call_logs")]

    with engine.begin() as connection:
        for name, definition in ADDITIONS.items():
            if name in columns:
                print(f"Column '{name}' already exists; skipping.")
                continue
            print(f"Adding '{name}' to call_logs...")
            connection.execute(
                text(f"ALTER TABLE call_logs ADD COLUMN {name} {definition}")
            )
        try:
            connection.execute(
                text(
                    "ALTER TABLE call_logs ADD INDEX "
                    "ix_call_logs_recording_checksum (recording_checksum)"
                )
            )
            print("Added recording_checksum index.")
        except Exception:
            print("recording_checksum index already exists or is unsupported.")

    print("=== Call Recording Management DB Migration Completed ===")


if __name__ == "__main__":
    run_migration()
