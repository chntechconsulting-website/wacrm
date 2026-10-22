import os
import sys

# Ensure backend root is on Python sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import inspect, text
from database import engine, SessionLocal
from models.user import User
from models.employee import Employee

def run_department_migration():
    """
    Safe, repeatable, backward-compatible migration for WACRM Department field:
    1. Ensures 'department' column exists in 'users' and 'employees' tables.
    2. Backfills any existing users and employees that have NULL or empty department.
    3. Preserves all user IDs, passwords, sessions, leads, and relationships.
    """
    print("=== Starting Department Database Migration ===")
    insp = inspect(engine)

    with engine.begin() as conn:
        user_cols = [c['name'] for c in insp.get_columns('users')]
        emp_cols = [c['name'] for c in insp.get_columns('employees')]

        # 1. Update users table if department is missing
        if 'department' not in user_cols:
            print("Adding 'department' column to 'users' table...")
            conn.execute(text("ALTER TABLE users ADD COLUMN department VARCHAR(50) NULL AFTER role"))
            try:
                conn.execute(text("CREATE INDEX ix_users_department ON users (department)"))
            except Exception as e:
                print(f"Index creation note: {e}")
        else:
            print("Column 'department' already present in 'users' table.")

        # 2. Update employees table if department is missing
        if 'department' not in emp_cols:
            print("Adding 'department' column to 'employees' table...")
            conn.execute(text("ALTER TABLE employees ADD COLUMN department VARCHAR(50) NULL AFTER role"))
            try:
                conn.execute(text("CREATE INDEX ix_employees_department ON employees (department)"))
            except Exception as e:
                print(f"Index creation note: {e}")
        else:
            print("Column 'department' already present in 'employees' table.")

    # 3. Backfill data safely
    db = SessionLocal()
    try:
        users = db.query(User).all()
        updated_users = 0
        updated_employees = 0

        for u in users:
            emp = db.query(Employee).filter(Employee.user_id == u.id).first()
            r = (u.role or "").strip().upper()

            # Determine department based on organizational role
            if r in ["ADMIN"]:
                dept = "ADMINISTRATION"
            elif r in ["SALES_MANAGER", "SALES_EXECUTIVE", "MANAGER", "SALES", "EMPLOYEE"]:
                dept = "SALES"
            elif r in ["SUPPORT_MANAGER", "SUPPORT_EXECUTIVE", "SUPPORT"]:
                dept = "SUPPORT"
            elif r in ["FINANCE", "ACCOUNTS"]:
                dept = "FINANCE"
            else:
                dept = "SALES"

            # Normalize existing ADMIN to ADMINISTRATION or keep clean
            if u.department in [None, "", "ADMIN"]:
                u.department = dept
                updated_users += 1

            if emp:
                if emp.department in [None, "", "ADMIN"]:
                    emp.department = u.department
                    updated_employees += 1
                if not emp.role:
                    emp.role = u.role

        db.commit()
        print(f"Migration completed successfully. Backfilled {updated_users} user(s) and {updated_employees} employee(s).")

        # Verify
        print("\n=== Current Users State in Database ===")
        for u in db.query(User).all():
            print(f"User #{u.id} ({u.username}): Role={u.role}, Department={u.department}, Manager={u.reporting_manager_id}")

    except Exception as e:
        db.rollback()
        print(f"Error during migration: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    run_department_migration()
