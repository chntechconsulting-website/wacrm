from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from models.role import Role, RolePermission
from models.user import User
from models.employee import Employee
from services.permission_catalog import SYSTEM_MODULES, MODULE_KEYS

def get_default_role_permissions(role_name: str) -> Dict[str, Dict[str, Any]]:
    """
    Returns canonical default system permissions for standard roles.
    Guarantees that Sales Managers, Sales Executives, Support, Finance, and Admins
    always have access to their required business modules, even if DB role records
    or migrations have not yet been applied to the live database.
    """
    norm = (role_name or "").strip().upper()
    
    # 1. ADMIN - Superuser
    if norm == "ADMIN":
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

    # 2. SALES_MANAGER / MANAGER
    if norm in ["SALES_MANAGER", "MANAGER"]:
        sales_mgr_mods = {
            "dashboard", "leads", "customers", "contacts", "quotations",
            "invoices", "calls", "whatsapp", "followups", "activities",
            "reports", "analytics", "employees"
        }
        res = {}
        for mod in SYSTEM_MODULES:
            k = mod["key"]
            has_acc = k in sales_mgr_mods
            res[k] = {
                "has_access": has_acc,
                "can_view": has_acc,
                "can_create": k in ["leads", "customers", "contacts", "quotations", "calls", "whatsapp", "followups", "activities"],
                "can_edit": k in ["leads", "customers", "contacts", "quotations", "followups", "activities"],
                "can_delete": k in ["leads", "quotations"],
                "can_export": k in ["leads", "quotations", "invoices", "reports"],
                "can_approve": k in ["quotations"],
                "can_assign": k in ["leads"],
                "can_call": k in ["calls", "leads", "customers"],
                "can_whatsapp": k in ["whatsapp", "leads", "customers"],
                "view_scope": "team" if has_acc else "none"
            }
        return res

    # 3. SALES_EXECUTIVE / SALES / EMPLOYEE
    if norm in ["SALES_EXECUTIVE", "SALES", "EMPLOYEE"]:
        sales_exec_mods = {
            "dashboard", "leads", "customers", "contacts", "quotations",
            "calls", "whatsapp", "followups", "activities"
        }
        res = {}
        for mod in SYSTEM_MODULES:
            k = mod["key"]
            has_acc = k in sales_exec_mods
            res[k] = {
                "has_access": has_acc,
                "can_view": has_acc,
                "can_create": k in ["leads", "customers", "contacts", "quotations", "calls", "whatsapp", "followups", "activities"],
                "can_edit": k in ["leads", "customers", "contacts", "quotations", "followups", "activities"],
                "can_delete": False,
                "can_export": k in ["leads", "quotations"],
                "can_approve": False,
                "can_assign": False,
                "can_call": k in ["calls", "leads", "customers"],
                "can_whatsapp": k in ["whatsapp", "leads", "customers"],
                "view_scope": "own" if has_acc else "none"
            }
        return res

    # 4. SUPPORT_MANAGER
    if norm == "SUPPORT_MANAGER":
        sup_mgr_mods = {
            "dashboard", "customers", "contacts", "support_tickets",
            "calls", "whatsapp", "activities", "reports", "leads"
        }
        res = {}
        for mod in SYSTEM_MODULES:
            k = mod["key"]
            has_acc = k in sup_mgr_mods
            res[k] = {
                "has_access": has_acc,
                "can_view": has_acc,
                "can_create": k in ["support_tickets", "calls", "whatsapp", "activities"],
                "can_edit": k in ["support_tickets", "activities", "customers"],
                "can_delete": False,
                "can_export": k in ["support_tickets", "reports"],
                "can_approve": False,
                "can_assign": k in ["support_tickets"],
                "can_call": k in ["calls", "customers"],
                "can_whatsapp": k in ["whatsapp", "customers"],
                "view_scope": "team" if has_acc else "none"
            }
        return res

    # 5. SUPPORT_EXECUTIVE / SUPPORT
    if norm in ["SUPPORT_EXECUTIVE", "SUPPORT"]:
        sup_exec_mods = {
            "dashboard", "customers", "contacts", "support_tickets",
            "calls", "whatsapp", "activities"
        }
        res = {}
        for mod in SYSTEM_MODULES:
            k = mod["key"]
            has_acc = k in sup_exec_mods
            res[k] = {
                "has_access": has_acc,
                "can_view": has_acc,
                "can_create": k in ["support_tickets", "calls", "whatsapp", "activities"],
                "can_edit": k in ["support_tickets", "activities"],
                "can_delete": False,
                "can_export": False,
                "can_approve": False,
                "can_assign": False,
                "can_call": k in ["calls", "customers"],
                "can_whatsapp": k in ["whatsapp", "customers"],
                "view_scope": "own" if has_acc else "none"
            }
        return res

    # 6. FINANCE
    if norm == "FINANCE":
        fin_mods = {"dashboard", "payments", "invoices", "customers", "reports"}
        res = {}
        for mod in SYSTEM_MODULES:
            k = mod["key"]
            has_acc = k in fin_mods
            res[k] = {
                "has_access": has_acc,
                "can_view": has_acc,
                "can_create": k in ["payments"],
                "can_edit": k in ["payments"],
                "can_delete": False,
                "can_export": has_acc,
                "can_approve": k in ["payments"],
                "can_assign": False,
                "can_call": False,
                "can_whatsapp": False,
                "view_scope": "company" if has_acc else "none"
            }
        return res

    # Fallback for unrecognized role
    return {
        mod["key"]: {
            "has_access": mod["key"] == "dashboard",
            "can_view": mod["key"] == "dashboard",
            "can_create": False,
            "can_edit": False,
            "can_delete": False,
            "can_export": False,
            "can_approve": False,
            "can_assign": False,
            "can_call": False,
            "can_whatsapp": False,
            "view_scope": "own" if mod["key"] == "dashboard" else "none"
        }
        for mod in SYSTEM_MODULES
    }


def get_role_permissions_map(role_name: str, db: Session) -> Dict[str, Dict[str, Any]]:
    """
    Returns a dictionary of module -> permissions dict for a given role.
    If role is ADMIN, all permissions are true and view_scope is 'company'.
    Falls back to canonical defaults if database records are missing or incomplete.
    """
    norm_role = (role_name or "").strip().upper()
    
    # 1. ADMIN has super-access across every module
    if norm_role == "ADMIN":
        return get_default_role_permissions("ADMIN")

    # 2. Get baseline defaults for this role
    defaults = get_default_role_permissions(norm_role)

    # 3. Lookup role in database
    from services.hierarchy_service import normalize_role
    role_record = db.query(Role).filter(Role.name == norm_role).first()
    if not role_record:
        canonical = normalize_role(norm_role)
        role_record = db.query(Role).filter(Role.name == canonical).first()
        
    # If role not found in DB or inactive or has no permissions seeded, return canonical defaults
    if not role_record or not role_record.is_active or not role_record.permissions:
        return defaults

    # 4. Populate from DB permissions, overlaying onto defaults
    perm_dict = dict(defaults)
    db_perms = {p.module.lower(): p for p in role_record.permissions}

    for mod in SYSTEM_MODULES:
        k = mod["key"]
        p = db_perms.get(k)
        if p is not None:
            perm_dict[k] = {
                "has_access": bool(p.has_access),
                "can_view": bool(p.can_view),
                "can_create": bool(p.can_create),
                "can_edit": bool(p.can_edit),
                "can_delete": bool(p.can_delete),
                "can_export": bool(p.can_export),
                "can_approve": bool(p.can_approve),
                "can_assign": bool(p.can_assign),
                "can_call": bool(p.can_call),
                "can_whatsapp": bool(p.can_whatsapp),
                "view_scope": p.view_scope or ("team" if norm_role in ["SALES_MANAGER", "MANAGER", "SUPPORT_MANAGER"] else "own")
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
    Initializes and synchronizes default system roles and permission sets in the database:
    ADMIN, SALES_MANAGER, SALES_EXECUTIVE, MANAGER, SALES, EMPLOYEE, FINANCE, SUPPORT, SUPPORT_MANAGER, SUPPORT_EXECUTIVE.
    Also repairs/seeds any missing module permissions for existing roles so that every role
    has all 19 module rows populated with valid permission flags.
    """
    standard_roles_specs = [
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
            "name": "MANAGER",
            "display_name": "Operations / Sales Manager",
            "description": "Manages teams, leads, approvals, and team records.",
            "is_system": False
        },
        {
            "name": "SALES",
            "display_name": "Sales Representative",
            "description": "Handles assigned leads, follow-ups, calls, WhatsApp, and quotations.",
            "is_system": False
        },
        {
            "name": "EMPLOYEE",
            "display_name": "Standard Employee",
            "description": "Default employee role for sales agents and executives.",
            "is_system": False
        },
        {
            "name": "FINANCE",
            "display_name": "Finance & Accounts",
            "description": "Manages finance queue, payments, and payment approvals.",
            "is_system": False
        },
        {
            "name": "SUPPORT",
            "display_name": "Customer Support & Onboarding",
            "description": "Handles customer tickets, onboarding fulfillment, and technical support.",
            "is_system": False
        },
        {
            "name": "SUPPORT_MANAGER",
            "display_name": "Support Manager",
            "description": "Manages customer onboarding, support tickets, agent assignments, and client fulfillment.",
            "is_system": False
        },
        {
            "name": "SUPPORT_EXECUTIVE",
            "display_name": "Support Executive",
            "description": "Handles assigned customer support tickets and onboarding tasks.",
            "is_system": False
        }
    ]

    all_roles = db.query(Role).all()
    existing_roles_map = {r.name.upper(): r for r in all_roles}

    # 1. Create any missing roles
    for r_spec in standard_roles_specs:
        r_name = r_spec["name"].upper()
        if r_name not in existing_roles_map:
            new_role = Role(
                name=r_spec["name"],
                display_name=r_spec["display_name"],
                description=r_spec["description"],
                is_system=r_spec.get("is_system", False),
                is_active=True
            )
            db.add(new_role)
            db.commit()
            db.refresh(new_role)
            existing_roles_map[r_name] = new_role

    # 2. Synchronize / repair permissions for all roles
    for role_name_key, role_obj in existing_roles_map.items():
        existing_perms = {p.module.lower(): p for p in role_obj.permissions}
        role_defaults = get_default_role_permissions(role_obj.name)

        for mod in SYSTEM_MODULES:
            mod_key = mod["key"].lower()
            p = existing_perms.get(mod_key)
            d = role_defaults.get(mod_key, {})

            if not p:
                new_rp = RolePermission(
                    role_id=role_obj.id,
                    module=mod_key,
                    has_access=d.get("has_access", False),
                    can_view=d.get("can_view", False),
                    can_create=d.get("can_create", False),
                    can_edit=d.get("can_edit", False),
                    can_delete=d.get("can_delete", False),
                    can_export=d.get("can_export", False),
                    can_approve=d.get("can_approve", False),
                    can_assign=d.get("can_assign", False),
                    can_call=d.get("can_call", False),
                    can_whatsapp=d.get("can_whatsapp", False),
                    view_scope=d.get("view_scope", "none")
                )
                db.add(new_rp)
    db.commit()

    # 3. Seed Support Manager user 'Kumar' if not existing
    try:
        import bcrypt
        def _quick_hash(pwd: str) -> str:
            return bcrypt.hashpw(pwd.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        kumar_user = db.query(User).filter(User.username == "kumar").first()
        if not kumar_user:
            kumar_user = User(
                username="kumar",
                hashed_password=_quick_hash("kumar123"),
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

