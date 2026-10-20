import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.abspath('backend'))
sys.path.insert(0, os.path.abspath('.'))

from sqlalchemy import inspect, text
from database import engine

def run_migration():
    print("=== Starting Destination ERP Sync DB Migration ===")
    insp = inspect(engine)
    
    with engine.begin() as conn:
        quote_cols = [c['name'] for c in insp.get_columns('quotations')]
        cust_cols = [c['name'] for c in insp.get_columns('customers')]
        
        # 1. Update quotations table
        if 'destination_sync_status' not in quote_cols:
            print("Adding 'destination_sync_status' column to quotations...")
            conn.execute(text("ALTER TABLE quotations ADD COLUMN destination_sync_status VARCHAR(50) NOT NULL DEFAULT 'PENDING' AFTER notes"))
            
        if 'external_client_id' not in quote_cols:
            print("Adding 'external_client_id' column to quotations...")
            conn.execute(text("ALTER TABLE quotations ADD COLUMN external_client_id VARCHAR(100) NULL AFTER destination_sync_status"))

        if 'external_proforma_id' not in quote_cols:
            print("Adding 'external_proforma_id' column to quotations...")
            conn.execute(text("ALTER TABLE quotations ADD COLUMN external_proforma_id VARCHAR(100) NULL AFTER external_client_id"))

        if 'destination_synced_at' not in quote_cols:
            print("Adding 'destination_synced_at' column to quotations...")
            conn.execute(text("ALTER TABLE quotations ADD COLUMN destination_synced_at DATETIME NULL AFTER external_proforma_id"))

        if 'destination_sync_error' not in quote_cols:
            print("Adding 'destination_sync_error' column to quotations...")
            conn.execute(text("ALTER TABLE quotations ADD COLUMN destination_sync_error TEXT NULL AFTER destination_synced_at"))

        if 'destination_sync_attempts' not in quote_cols:
            print("Adding 'destination_sync_attempts' column to quotations...")
            conn.execute(text("ALTER TABLE quotations ADD COLUMN destination_sync_attempts INT NOT NULL DEFAULT 0 AFTER destination_sync_error"))

        if 'destination_sync_response' not in quote_cols:
            print("Adding 'destination_sync_response' column to quotations...")
            conn.execute(text("ALTER TABLE quotations ADD COLUMN destination_sync_response JSON NULL AFTER destination_sync_attempts"))

        # 2. Update customers table
        if 'external_client_id' not in cust_cols:
            print("Adding 'external_client_id' column to customers...")
            conn.execute(text("ALTER TABLE customers ADD COLUMN external_client_id VARCHAR(100) NULL AFTER location"))

        if 'destination_synced_at' not in cust_cols:
            print("Adding 'destination_synced_at' column to customers...")
            conn.execute(text("ALTER TABLE customers ADD COLUMN destination_synced_at DATETIME NULL AFTER external_client_id"))

    print("=== Destination ERP Sync DB Migration Completed Successfully ===")

if __name__ == "__main__":
    run_migration()
