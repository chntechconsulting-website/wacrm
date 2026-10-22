"""
Standalone Live Database Role & Permission Synchronization Script.
Ensures that all standard roles (ADMIN, SALES_MANAGER, SALES_EXECUTIVE, MANAGER, SALES, EMPLOYEE, FINANCE, SUPPORT, SUPPORT_MANAGER, SUPPORT_EXECUTIVE)
exist and have complete 19-module permissions seeded in the database.
"""
import os
import sys

sys.path.insert(0, os.path.abspath('backend'))

from database import engine, SessionLocal
from models.role import Role, RolePermission
from services.permission_service import seed_default_roles_if_needed, get_role_permissions_map
from services.permission_catalog import SYSTEM_MODULES

def run():
    print("=" * 60)
    print("Starting Live DB Role & Permission Synchronization...")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        seed_default_roles_if_needed(db)
        print("\nAll default roles and permissions synchronized successfully.")
        
        print("\nVerification of Role Access:")
        roles = db.query(Role).all()
        for r in roles:
            perms = get_role_permissions_map(r.name, db)
            accessible = [k for k, v in perms.items() if v.get("has_access")]
            print(f" -> Role: {r.name:<18} ({r.display_name or 'No display name'})")
            print(f"    Accessible Modules ({len(accessible)}): {', '.join(accessible)}")
            
    except Exception as e:
        print(f"Error during synchronization: {e}")
        db.rollback()
        raise
    finally:
        db.close()
        
    print("\nRole & Permission Synchronization Complete!")

if __name__ == "__main__":
    run()
