import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text, inspect
from database import engine, SessionLocal
from models.quotation import Quotation
from models.employee import Employee
from models.lead import Lead
from models.user import User

def run_migration():
    print("Starting migration: Add creator and assignment columns to quotations table...")
    with engine.connect() as conn:
        insp = inspect(engine)
        existing_cols = [c["name"] for c in insp.get_columns("quotations")]
        print("Existing columns in quotations:", existing_cols)

        new_cols = {
            "created_by": "INT NULL",
            "created_by_user_id": "INT NULL",
            "assigned_to": "INT NULL"
        }

        for col_name, col_type in new_cols.items():
            if col_name not in existing_cols:
                print(f"Adding column '{col_name}' ({col_type}) to quotations table...")
                conn.execute(text(f"ALTER TABLE quotations ADD COLUMN {col_name} {col_type}"))
                conn.commit()
                print(f"Added column '{col_name}'.")
            else:
                print(f"Column '{col_name}' already exists.")

    # Safe backfill
    db = SessionLocal()
    try:
        employees = db.query(Employee).all()
        emp_name_map = {}
        for emp in employees:
            if emp.name:
                emp_name_map[emp.name.strip().lower()] = emp

        users = db.query(User).all()
        user_name_map = {}
        for u in users:
            if u.username:
                user_name_map[u.username.strip().lower()] = u

        quotations = db.query(Quotation).all()
        updated_count = 0

        for q in quotations:
            dirty = False
            # 1. Match from Lead if available
            if q.lead_id:
                ld = db.query(Lead).filter(Lead.id == q.lead_id).first()
                if ld:
                    if q.assigned_to is None and ld.assigned_to:
                        q.assigned_to = ld.assigned_to
                        dirty = True
                    if q.created_by is None and ld.assigned_to:
                        q.created_by = ld.assigned_to
                        dirty = True
                    if q.created_by_user_id is None and ld.assigned_to:
                        emp_obj = db.query(Employee).filter(Employee.id == ld.assigned_to).first()
                        if emp_obj and emp_obj.user_id:
                            q.created_by_user_id = emp_obj.user_id
                            dirty = True

            # 2. Match from prepared_by if still None
            if q.prepared_by and (q.created_by is None or q.created_by_user_id is None):
                prep = q.prepared_by.strip().lower()
                matched_emp = emp_name_map.get(prep)
                if not matched_emp:
                    # Partial match
                    for name_key, emp_obj in emp_name_map.items():
                        if name_key in prep or prep in name_key:
                            matched_emp = emp_obj
                            break

                if matched_emp:
                    if q.created_by is None:
                        q.created_by = matched_emp.id
                        dirty = True
                    if q.created_by_user_id is None and matched_emp.user_id:
                        q.created_by_user_id = matched_emp.user_id
                        dirty = True
                    if q.assigned_to is None:
                        q.assigned_to = matched_emp.id
                        dirty = True

            if dirty:
                updated_count += 1

        db.commit()
        print(f"Migration completed. Backfilled {updated_count} historical quotations with confident creator/assignment details.")
    except Exception as e:
        db.rollback()
        print(f"Error during backfill: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    run_migration()
