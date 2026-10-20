from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from models.role import Role, RolePermission
from models.user import User
from models.employee import Employee
from services.permission_catalog import SYSTEM_MODULES, MODULE_KEYS

def get_role_permissions_map(role_name: str, db: Session) -> Dict[str, Dict[str, Any]]:
    """
    Returns a dictionary of module -> permissions dict for a given role.
    If role is ADMIN, all permissions are true and view_scope is 'company'.
    """
    norm_role = (role_name or "").strip().upper()
    
    # 1. ADMIN has super-access across every module
    if norm_role == "ADMIN":
        return {
            mod["key"]: {
                "has_access": True,
                "can_view": True,
                "can_create": True,
                "can_edit": True,
                "can_delete": True,
                "can_export": True,
                "can_approve": True,
                "can_assign": True,
                "can_call": True,
                "can_whatsapp": True,
                "view_scope": "company"
            }
            for mod in SYSTEM_MODULES
        }

    # 2. Lookup role in database
    from services.hierarchy_service import normalize_role
    role_record = db.query(Role).filter(Role.name == norm_role).first()
    if not role_record:
        canonical = normalize_role(norm_role)
        role_record = db.query(Role).filter(Role.name == canonical).first()
    if not role_record or not role_record.is_active:
        # Fallback empty permission set
        return {
            mod["key"]: {
                "has_access": False,
                "can_view": False,
                "can_create": False,
                "can_edit": False,
                "can_delete": False,
                "can_export": False,
                "can_approve": False,
                "can_assign": False,
                "can_call": False,
                "can_whatsapp": False,
                "view_scope": "none"
            }
            for mod in SYSTEM_MODULES
        }

    # 3. Populate from DB permissions
    perm_dict = {}
    db_perms = {p.module.lower(): p for p in role_record.permissions}

    for mod in SYSTEM_MODULES:
        k = mod["key"]
        p = db_perms.get(k)
        if p and p.has_access:
            perm_dict[k] = {
                "has_access": True,
                "can_view": p.can_view,
                "can_create": p.can_create,
                "can_edit": p.can_edit,
                "can_delete": p.can_delete,
                "can_export": p.can_export,
                "can_approve": p.can_approve,
                "can_assign": p.can_assign,
                "can_call": p.can_call,
                "can_whatsapp": p.can_whatsapp,
                "view_scope": p.view_scope or "own"
            }
        else:
            perm_dict[k] = {
                "has_access": False,
                "can_view": False,
                "can_create": False,
                "can_edit": False,
                "can_delete": False,
                "can_export": False,
                "can_approve": False,
                "can_assign": False,
                "can_call": False,
                "can_whatsapp": False,
                "view_scope": "none"
            }

    return perm_dict


def get_user_permissions(user: User, db: Session) -> Dict[str, Dict[str, Any]]:
    """Helper to fetch full permission set for a user based on their assigned role."""
    return get_role_permissions_map(user.role, db)


def user_has_permission(
    user: User,
    module: str,
    action: str, # "view", "create", "edit", "delete", "export", "approve", "assign", "call", "whatsapp"
    db: Session
) -> bool:
    """Check if the user's role has permission for a specific module and action."""
    if user.role.upper() == "ADMIN":
        return True

    perms = get_user_permissions(user, db)
    mod_perm = perms.get(module.lower())
    if not mod_perm or not mod_perm.get("has_access"):
        return False

    action_key = f"can_{action.lower()}"
    return bool(mod_perm.get(action_key, False))


def is_finance_team(user: User, db: Optional[Session] = None) -> bool:
    """
    Checks if the user belongs strictly to the Finance team (role FINANCE).
    Official Tax Invoices are restricted strictly to Finance team members.
    """
    if not user:
        return False
    norm_role = (user.role or "").strip().upper()
    return norm_role == "FINANCE"


def is_finance_or_admin(user: User, db: Optional[Session] = None) -> bool:
    """
    Checks if the user has Finance or Admin authority to create, verify, or issue Tax Invoices.
    Users with role ADMIN, FINANCE, or users having explicit 'invoices' approve/create access qualify.
    """
    if not user:
        return False
    norm_role = (user.role or "").strip().upper()
    if norm_role in ["ADMIN", "FINANCE"]:
        return True
    if db is not None:
        return user_has_permission(user, "invoices", "create", db) or user_has_permission(user, "invoices", "approve", db)
    return False



def get_user_view_scope(user: User, module: str, db: Session) -> str:
    """Returns 'none', 'own', 'team', 'department', or 'company'."""
    if user.role.upper() == "ADMIN":
        return "company"

    perms = get_user_permissions(user, db)
    mod_perm = perms.get(module.lower())
    if not mod_perm or not mod_perm.get("has_access"):
        return "none"
    return mod_perm.get("view_scope", "own")


def seed_default_roles_if_needed(db: Session):
    """
    Initializes default roles (ADMIN, MANAGER, EMPLOYEE, SALES, FINANCE, SUPPORT)
    in the database if they do not exist.
    Admin can edit any of these permissions or create new custom roles.
    """
    existing_roles = {r.name.upper(): r for r in db.query(Role).all()}

    # 1. ADMIN Role
    if "ADMIN" not in existing_roles:
        admin_role = Role(
            name="ADMIN",
            display_name="System Administrator",
            description="Full access to all modules, records, and security controls.",
            is_system=True,
            is_active=True
        )
        db.add(admin_role)
        db.commit()
        db.refresh(admin_role)

        for mod in SYSTEM_MODULES:
            rp = RolePermission(
                role_id=admin_role.id,
                module=mod["key"],
                has_access=True,
                can_view=True,
                can_create=True,
                can_edit=True,
                can_delete=True,
                can_export=True,
                can_approve=True,
                can_assign=True,
                can_call=True,
                can_whatsapp=True,
                view_scope="company"
            )
            db.add(rp)
        db.commit()

    # 2. MANAGER Role
    if "MANAGER" not in existing_roles:
        mgr_role = Role(
            name="MANAGER",
            display_name="Operations / Sales Manager",
            description="Manages teams, leads, approvals, and team records.",
            is_system=False,
            is_active=True
        )
        db.add(mgr_role)
        db.commit()
        db.refresh(mgr_role)

        for mod in SYSTEM_MODULES:
            k = mod["key"]
            is_admin_only = k in ["settings", "roles", "integrations"]
            rp = RolePermission(
                role_id=mgr_role.id,
                module=k,
                has_access=not is_admin_only,
                can_view=not is_admin_only,
                can_create=not is_admin_only,
                can_edit=not is_admin_only,
                can_delete=k in ["leads", "quotations"],
                can_export=not is_admin_only,
                can_approve=True,
                can_assign=True,
                can_call=True,
                can_whatsapp=True,
                view_scope="team" if not is_admin_only else "none"
            )
            db.add(rp)
        db.commit()

    # 3. SALES Role
    if "SALES" not in existing_roles:
        sales_role = Role(
            name="SALES",
            display_name="Sales Executive",
            description="Handles assigned leads, follow-ups, calls, WhatsApp, and quotations.",
            is_system=False,
            is_active=True
        )
        db.add(sales_role)
        db.commit()
        db.refresh(sales_role)

        for mod in SYSTEM_MODULES:
            k = mod["key"]
            can_access = k in ["dashboard", "leads", "customers", "contacts", "quotations", "calls", "whatsapp", "followups", "activities"]
            rp = RolePermission(
                role_id=sales_role.id,
                module=k,
                has_access=can_access,
                can_view=can_access,
                can_create=k in ["leads", "customers", "contacts", "quotations", "calls", "whatsapp", "followups", "activities"],
                can_edit=k in ["leads", "customers", "contacts", "quotations", "followups"],
                can_delete=False,
                can_export=k in ["leads", "quotations"],
                can_approve=False,
                can_assign=False,
                can_call=can_access,
                can_whatsapp=can_access,
                view_scope="own" if can_access else "none"
            )
            db.add(rp)
        db.commit()

    # 4. EMPLOYEE Role (Default sales employee fallback)
    if "EMPLOYEE" not in existing_roles:
        emp_role = Role(
            name="EMPLOYEE",
            display_name="Standard Employee",
            description="Default employee role for sales agents and executives.",
            is_system=False,
            is_active=True
        )
        db.add(emp_role)
        db.commit()
        db.refresh(emp_role)

        for mod in SYSTEM_MODULES:
            k = mod["key"]
            can_access = k in ["dashboard", "leads", "customers", "contacts", "quotations", "calls", "whatsapp", "followups", "activities"]
            rp = RolePermission(
                role_id=emp_role.id,
                module=k,
                has_access=can_access,
                can_view=can_access,
                can_create=k in ["leads", "customers", "contacts", "quotations", "calls", "whatsapp", "followups", "activities"],
                can_edit=k in ["leads", "customers", "contacts", "quotations", "followups"],
                can_delete=False,
                can_export=False,
                can_approve=False,
                can_assign=False,
                can_call=can_access,
                can_whatsapp=can_access,
                view_scope="own" if can_access else "none"
            )
            db.add(rp)
        db.commit()

    # 5. FINANCE Role
    if "FINANCE" not in existing_roles:
        fin_role = Role(
            name="FINANCE",
            display_name="Finance & Accounts",
            description="Manages finance queue, payments, and payment approvals.",
            is_system=False,
            is_active=True
        )
        db.add(fin_role)
        db.commit()
        db.refresh(fin_role)

        for mod in SYSTEM_MODULES:
            k = mod["key"]
            can_access = k in ["dashboard", "payments", "customers", "reports"]
            rp = RolePermission(
                role_id=fin_role.id,
                module=k,
                has_access=can_access,
                can_view=can_access,
                can_create=k in ["payments"],
                can_edit=k in ["payments"],
                can_delete=False,
                can_export=can_access,
                can_approve=k in ["payments"],
                can_assign=False,
                can_call=False,
                can_whatsapp=False,
                view_scope="company" if can_access else "none"
            )
            db.add(rp)
        db.commit()

    # 6. SUPPORT Role
    if "SUPPORT" not in existing_roles:
        sup_role = Role(
            name="SUPPORT",
            display_name="Customer Support & Onboarding",
            description="Handles customer tickets, onboarding fulfillment, and technical support.",
            is_system=False,
            is_active=True
        )
        db.add(sup_role)
        db.commit()
        db.refresh(sup_role)

        for mod in SYSTEM_MODULES:
            k = mod["key"]
            can_access = k in ["dashboard", "customers", "contacts", "support_tickets", "calls", "whatsapp", "activities"]
            rp = RolePermission(
                role_id=sup_role.id,
                module=k,
                has_access=can_access,
                can_view=can_access,
                can_create=k in ["support_tickets", "calls", "whatsapp", "activities"],
                can_edit=k in ["support_tickets", "activities"],
                can_delete=False,
                can_export=k in ["support_tickets"],
                can_approve=False,
                can_assign=k in ["support_tickets"],
                can_call=can_access,
                can_whatsapp=can_access,
                view_scope="team" if can_access else "none"
            )
            db.add(rp)
        db.commit()

    # 7. SUPPORT_MANAGER Role
    if "SUPPORT_MANAGER" not in existing_roles:
        sm_role = Role(
            name="SUPPORT_MANAGER",
            display_name="Support Manager",
            description="Manages customer onboarding, support tickets, agent assignments, and client fulfillment.",
            is_system=False,
            is_active=True
        )
        db.add(sm_role)
        db.commit()
        db.refresh(sm_role)

        for mod in SYSTEM_MODULES:
            k = mod["key"]
            can_access = k in ["dashboard", "customers", "contacts", "support_tickets", "calls", "whatsapp", "activities", "reports", "leads"]
            rp = RolePermission(
                role_id=sm_role.id,
                module=k,
                has_access=can_access,
                can_view=can_access,
                can_create=k in ["support_tickets", "calls", "whatsapp", "activities"],
                can_edit=k in ["support_tickets", "activities", "customers"],
                can_delete=False,
                can_export=k in ["support_tickets", "reports"],
                can_approve=False,
                can_assign=k in ["support_tickets"],
                can_call=can_access,
                can_whatsapp=can_access,
                view_scope="team" if can_access else "none"
            )
            db.add(rp)
        db.commit()

    # 8. Seed Support Manager user 'Kumar' if not existing
    try:
        from services.auth import hash_password
        kumar_user = db.query(User).filter(User.username == "kumar").first()
        if not kumar_user:
            kumar_user = User(
                username="kumar",
                hashed_password=hash_password("kumar123"),
                role="SUPPORT_MANAGER",
                is_active=True
            )
            db.add(kumar_user)
            db.commit()
            db.refresh(kumar_user)
        else:
            if kumar_user.role != "SUPPORT_MANAGER":
                kumar_user.role = "SUPPORT_MANAGER"
                db.commit()

        kumar_emp = db.query(Employee).filter(Employee.user_id == kumar_user.id).first()
        if not kumar_emp:
            kumar_emp = Employee(
                user_id=kumar_user.id,
                name="Kumar",
                email="kumar@company.com",
                phone="9876543210",
                username="kumar",
                role="SUPPORT_MANAGER",
                status="ACTIVE"
            )
            db.add(kumar_emp)
            db.commit()
        else:
            if kumar_emp.role != "SUPPORT_MANAGER":
                kumar_emp.role = "SUPPORT_MANAGER"
                db.commit()
    except Exception as e:
        print(f"Error seeding Kumar Support Manager: {e}")
        db.rollback()


def get_team_employee_ids(manager_emp_id: int, db: Session) -> List[int]:
    """
    Returns manager_emp_id + all direct and indirect reportees.
    """
    team_ids = {manager_emp_id}
    queue = [manager_emp_id]
    while queue:
        curr_id = queue.pop(0)
        reportees = db.query(Employee.id).filter(Employee.manager_id == curr_id).all()
        for (r_id,) in reportees:
            if r_id not in team_ids:
                team_ids.add(r_id)
                queue.append(r_id)
    return list(team_ids)


def get_authorized_call_employee_ids(user: User, db: Session) -> Optional[List[int]]:
    """
    Returns:
      None: if user has company-wide access (ADMIN or view_scope == 'company')
      List[int]: authorized employee IDs (for manager: team + manager; for employee: [emp.id])
      []: if unauthorized or no employee profile
    """
    norm_role = (user.role or "").strip().upper()
    if norm_role == "ADMIN":
        return None

    # Determine view_scope from database-driven role permission matrix
    scope = get_user_view_scope(user, "calls", db)
    if scope == "company":
        return None
    if scope == "none":
        return []

    emp = db.query(Employee).filter(Employee.user_id == user.id).first()
    if not emp:
        return []

    if scope == "team" or norm_role in ["MANAGER", "SUPPORT_MANAGER"]:
        return get_team_employee_ids(emp.id, db)
    elif scope == "department" and getattr(emp, "department", None):
        dept_emps = db.query(Employee.id).filter(Employee.department == emp.department).all()
        return [e[0] for e in dept_emps]
    else:  # "own"
        return [emp.id]

