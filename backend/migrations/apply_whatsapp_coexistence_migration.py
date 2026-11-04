"""
Idempotent migration for WhatsApp Business App coexistence onboarding.

Creates only the three additive coexistence tables. It never alters the
existing conversations, messages, leads, lead_enquiries or any other CRM table.

Run from the backend directory:
    venv\\Scripts\\python.exe migrations\\apply_whatsapp_coexistence_migration.py
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import models  # noqa: F401 - register every model on Base.metadata
from database import Base, engine
from models.whatsapp_coexistence import (
    WhatsAppCoexistenceConnection,
    WhatsAppCoexistenceEvent,
    WhatsAppSmbContact,
)


def run_migration():
    print("=== WhatsApp coexistence migration (additive) ===")

    # Connection first (parents), then event/contact children with their FKs.
    tables = [
        WhatsAppCoexistenceConnection.__table__,
        WhatsAppCoexistenceEvent.__table__,
        WhatsAppSmbContact.__table__,
    ]
    Base.metadata.create_all(bind=engine, tables=tables, checkfirst=True)

    from sqlalchemy import inspect

    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    expected = (
        "whatsapp_coexistence_connections",
        "whatsapp_coexistence_events",
        "whatsapp_smb_contacts",
    )
    for table in expected:
        if table in existing:
            print(f"OK: table '{table}' exists.")
        else:
            raise RuntimeError(f"Expected table '{table}' was not created.")

    print("=== Migration finished. Existing CRM data was not modified. ===")


if __name__ == "__main__":
    run_migration()
