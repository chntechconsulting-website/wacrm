import os
import sys

sys.path.insert(0, os.path.abspath('backend'))

from sqlalchemy import inspect, text
from database import engine, SessionLocal
from models.user import User
from models.employee import Employee
from models.role import Role, RolePermission
from services.permission_catalog import SYSTEM_MODULES

def run_migration():
    print("=== Starting Reporting Manager & Roles DB Migration ===")
    insp = inspect(engine)
    
    with engine.begin() as conn:
        user_cols = [c['name'] for c in insp.get_columns('users')]
        emp_cols = [c['name'] for c in insp.get_columns('employees')]
        
        # 1. Update users table
        if 'department' not in user_cols:
            print("Adding 'department' column to users table...")
            conn.execute(text("ALTER TABLE users ADD COLUMN department VARCHAR(50) NULL AFTER role"))
            
        if 'reporting_manager_id' not in user_cols:
            print("Adding 'reporting_manager_id' column to users table...")
            conn.execute(text("ALTER TABLE users ADD COLUMN reporting_manager_id INT NULL AFTER department"))
            try:
                conn.execute(text("ALTER TABLE users ADD CONSTRAINT fk_users_reporting_manager FOREIGN KEY (reporting_manager_id) REFERENCES users(id) ON DELETE SET NULL"))
            except Exception as e:
                print(f"Note on foreign key creation: {e}")

        # 2. Update employees table
        if 'department' not in emp_cols:
            print("Adding 'department' column to employees table...")
            conn.execute(text("ALTER TABLE employees ADD COLUMN department VARCHAR(50) NULL AFTER role"))

        if 'reporting_manager_id' not in emp_cols:
            print("Adding 'reporting_manager_id' column to employees table...")
            conn.execute(text("ALTER TABLE employees ADD COLUMN reporting_manager_id INT NULL AFTER manager_id"))

    db = SessionLocal()
    try:
        # 3. Seed / Update Roles
        standard_roles = [
            {
                "name": "ADMIN",
                "display_name": "System Administrator",
                "description": "Full access to all modules, records, and security controls.",
                "is_system": True
            },
            {
                "name": "SALES_MANAGER",
                "display_name": "Sales Manager",
                "description": "Manages sales executives, assigned leads, quotations, and team sales performance.",
                "is_system": False
            },
            {
                "name": "SALES_EXECUTIVE",
                "display_name": "Sales Executive",
                "description": "Handles assigned sales leads, follow-ups, calls, WhatsApp, and quotations.",
                "is_system": False
            },
            {
                "name": "SUPPORT_MANAGER",
                "display_name": "Support Manager",
                "description": "Manages customer onboarding, support tickets, support agents, and client fulfillment.",
                "is_system": False
            },
            {
                "name": "SUPPORT_EXECUTIVE",
                "display_name": "Support Executive",
                "description": "Handles assigned customer support tickets and onboarding tasks.",
                "is_system": False
            }
        ]

        for r_spec in standard_roles:
            role_obj = db.query(Role).filter(Role.name == r_spec["name"]).first()
            if not role_obj:
                print(f"Creating role: {r_spec['name']}")
                role_obj = Role(
                    name=r_spec["name"],
                    display_name=r_spec["display_name"],
                    description=r_spec["description"],
                    is_system=r_spec["is_system"],
                    is_active=True
                )
                db.add(role_obj)
                db.commit()
                db.refresh(role_obj)
            else:
                role_obj.display_name = r_spec["display_name"]
                role_obj.description = r_spec["description"]
                db.commit()

            # Set up permissions for each role
            existing_perms = {p.module.lower(): p for p in role_obj.permissions}
            r_name = r_spec["name"]

            for mod in SYSTEM_MODULES:
                k = mod["key"]
                p = existing_perms.get(k)
                
                # Determine permissions based on role
                has_access = False
                can_view = False
                can_create = False
                can_edit = False
                can_delete = False
                can_export = False
                can_approve = False
                can_assign = False
                can_call = False
                can_whatsapp = False
                view_scope = "none"

                if r_name == "ADMIN":
                    has_access = True
                    can_view = can_create = can_edit = can_delete = can_export = can_approve = can_assign = can_call = can_whatsapp = True
                    view_scope = "company"

                elif r_name == "SALES_MANAGER":
                    can_access_mod = k in [
                        "dashboard", "leads", "customers", "contacts", "quotations", 
                        "invoices", "calls", "whatsapp", "followups", "activities", 
                        "reports", "analytics", "employees"
                    ]
                    has_access = can_access_mod
                    can_view = can_access_mod
                    can_create = k in ["leads", "customers", "contacts", "quotations", "calls", "whatsapp", "followups", "activities"]
                    can_edit = k in ["leads", "customers", "contacts", "quotations", "followups"]
                    can_delete = k in ["leads", "quotations"]
                    can_export = k in ["leads", "quotations", "invoices", "reports"]
                    can_approve = k in ["quotations"]
                    can_assign = k in ["leads"]
                    can_call = k in ["calls", "leads", "customers"]
                    can_whatsapp = k in ["whatsapp", "leads", "customers"]
                    view_scope = "team" if can_access_mod else "none"

                elif r_name == "SALES_EXECUTIVE":
                    can_access_mod = k in [
                        "dashboard", "leads", "customers", "contacts", "quotations", 
                        "calls", "whatsapp", "followups", "activities"
                    ]
                    has_access = can_access_mod
                    can_view = can_access_mod
                    can_create = k in ["leads", "customers", "contacts", "quotations", "calls", "whatsapp", "followups", "activities"]
                    can_edit = k in ["leads", "customers", "contacts", "quotations", "followups"]
                    can_delete = False  # Sales Executives cannot delete records
                    can_export = k in ["leads", "quotations"]
                    can_approve = False
                    can_assign = False
                    can_call = k in ["calls", "leads", "customers"]
                    can_whatsapp = k in ["whatsapp", "leads", "customers"]
                    view_scope = "own" if can_access_mod else "none"

                elif r_name == "SUPPORT_MANAGER":
                    can_access_mod = k in [
                        "dashboard", "customers", "contacts", "support_tickets", 
                        "calls", "whatsapp", "activities", "reports"
                    ]
                    has_access = can_access_mod
                    can_view = can_access_mod
                    can_create = k in ["support_tickets", "calls", "whatsapp", "activities"]
                    can_edit = k in ["support_tickets", "activities", "customers"]
                    can_delete = False
                    can_export = k in ["support_tickets", "reports"]
                    can_approve = False
                    can_assign = k in ["support_tickets"]
                    can_call = k in ["calls", "customers"]
                    can_whatsapp = k in ["whatsapp", "customers"]
                    view_scope = "team" if can_access_mod else "none"

                elif r_name == "SUPPORT_EXECUTIVE":
                    can_access_mod = k in [
                        "dashboard", "customers", "contacts", "support_tickets", 
                        "calls", "whatsapp", "activities"
                    ]
                    has_access = can_access_mod
                    can_view = can_access_mod
                    can_create = k in ["support_tickets", "calls", "whatsapp", "activities"]
                    can_edit = k in ["support_tickets", "activities"]
                    can_delete = False
                    can_export = False
                    can_approve = False
                    can_assign = False
                    can_call = k in ["calls", "customers"]
                    can_whatsapp = k in ["whatsapp", "customers"]
                    view_scope = "own" if can_access_mod else "none"

                if not p:
                    new_p = RolePermission(
                        role_id=role_obj.id,
                        module=k,
                        has_access=has_access,
                        can_view=can_view,
                        can_create=can_create,
                        can_edit=can_edit,
                        can_delete=can_delete,
                        can_export=can_export,
                        can_approve=can_approve,
                        can_assign=can_assign,
                        can_call=can_call,
                        can_whatsapp=can_whatsapp,
                        view_scope=view_scope
                    )
                    db.add(new_p)
                else:
                    p.has_access = has_access
                    p.can_view = can_view
                    p.can_create = can_create
                    p.can_edit = can_edit
                    p.can_delete = can_delete
                    p.can_export = can_export
                    p.can_approve = can_approve
                    p.can_assign = can_assign
                    p.can_call = can_call
                    p.can_whatsapp = can_whatsapp
                    p.view_scope = view_scope

            db.commit()

        # 4. Backfill existing users and employees
        users = db.query(User).all()
        admin_user = db.query(User).filter(User.username == "admin").first()
        admin_id = admin_user.id if admin_user else 1

        for u in users:
            emp = db.query(Employee).filter(Employee.user_id == u.id).first()
            uname = u.username.lower()
            
            if uname == "admin":
                u.role = "ADMIN"
                u.department = "ADMIN"
                u.reporting_manager_id = None
            elif uname == "chnm030":
                u.role = "SALES_MANAGER"
                u.department = "SALES"
                u.reporting_manager_id = admin_id
            elif uname == "chnm040":
                u.role = "SALES_EXECUTIVE"
                u.department = "SALES"
                # Gowtham chnm030 is manager
                mgr = db.query(User).filter(User.username == "chnm030").first()
                u.reporting_manager_id = mgr.id if mgr else admin_id
            elif uname == "kumar":
                u.role = "SUPPORT_MANAGER"
                u.department = "SUPPORT"
                u.reporting_manager_id = admin_id
            elif uname == "chnm023":
                u.role = "SUPPORT_EXECUTIVE"
                u.department = "SUPPORT"
                # Kumar is manager
                mgr = db.query(User).filter(User.username == "kumar").first()
                u.reporting_manager_id = mgr.id if mgr else admin_id
            elif uname == "chnm020":
                u.role = "FINANCE"
                u.department = "FINANCE"
                u.reporting_manager_id = admin_id
            else:
                # Default non-admin to sales executive if unassigned
                if not u.department:
                    if "support" in (u.role or "").lower():
                        u.department = "SUPPORT"
                        u.role = "SUPPORT_EXECUTIVE"
                    elif "manager" in (u.role or "").lower():
                        u.department = "SALES"
                        u.role = "SALES_MANAGER"
                        u.reporting_manager_id = admin_id
                    else:
                        u.department = "SALES"
                        u.role = "SALES_EXECUTIVE"

            if emp:
                emp.role = u.role
                emp.department = u.department
                emp.reporting_manager_id = u.reporting_manager_id
                # Map manager_id to employee id of the manager user
                if u.reporting_manager_id:
                    mgr_emp = db.query(Employee).filter(Employee.user_id == u.reporting_manager_id).first()
                    emp.manager_id = mgr_emp.id if mgr_emp else None
                else:
                    emp.manager_id = None

        db.commit()
        print("Successfully backfilled users and employees.")
        
        # Verify
        users_after = db.query(User).all()
        for u in users_after:
            print(f"User #{u.id} ({u.username}): Role={u.role}, Dept={u.department}, ManagerID={u.reporting_manager_id}")

        print("=== Migration Completed Successfully ===")
    finally:
        db.close()

if __name__ == "__main__":
    run_migration()
