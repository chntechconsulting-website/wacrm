"""
Idempotent migration for Meta Click-to-WhatsApp ad lead capture.

Creates only the two additive attribution/event tables. It never alters the
existing leads, lead_enquiries, lead_assignments or any other CRM table.

Run from the backend directory:
    venv\\Scripts\\python.exe migrations\\apply_whatsapp_ad_leads_migration.py
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import models  # noqa: F401 - register every model on Base.metadata
from database import Base, engine
from models.whatsapp_ad_lead import WhatsAppAdAttribution, WhatsAppWebhookEvent


def run_migration():
    print("=== WhatsApp Ad Leads migration (additive) ===")

    # Attribution must exist before the event table's foreign key is created.
    tables = [WhatsAppAdAttribution.__table__, WhatsAppWebhookEvent.__table__]
    Base.metadata.create_all(bind=engine, tables=tables, checkfirst=True)

    from sqlalchemy import inspect, text

    inspector = inspect(engine)

    # If an earlier build of this new table already exists, add the metadata
    # columns without touching any existing row.
    if "whatsapp_ad_attributions" in inspector.get_table_names():
        columns = {
            col["name"]
            for col in inspector.get_columns("whatsapp_ad_attributions")
        }
        missing = {
            "channel": "VARCHAR(30) NOT NULL DEFAULT 'WHATSAPP'",
            "business_account_id": "VARCHAR(100) NULL",
            "phone_number_id": "VARCHAR(100) NULL",
        }
        with engine.begin() as conn:
            for column, ddl in missing.items():
                if column not in columns:
                    conn.execute(
                        text(
                            f"ALTER TABLE whatsapp_ad_attributions "
                            f"ADD COLUMN {column} {ddl}"
                        )
                    )
                    print(f"Added missing column '{column}'.")
            for column in missing:
                index_name = f"ix_whatsapp_ad_attributions_{column}"
                try:
                    conn.execute(
                        text(
                            f"CREATE INDEX {index_name} "
                            f"ON whatsapp_ad_attributions ({column})"
                        )
                    )
                except Exception:
                    # Index already exists (or the dialect auto-created it).
                    pass

    existing = set(inspector.get_table_names())
    for table in ("whatsapp_ad_attributions", "whatsapp_webhook_events"):
        if table in existing:
            print(f"OK: table '{table}' exists.")
        else:
            raise RuntimeError(f"Expected table '{table}' was not created.")

    print("=== Migration finished. Existing CRM data was not modified. ===")


if __name__ == "__main__":
    run_migration()
