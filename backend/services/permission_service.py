from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
import logging

from sqlalchemy.orm import Session
from models.role import Role, RolePermission
from models.user import User
from models.employee import Employee
from services.permission_catalog import SYSTEM_MODULES, MODULE_KEYS

logger = logging.getLogger(__name__)

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
            "dashboard", "leads", "brochure_downloads", "customers", "contacts",
            "quotations", "invoices", "calls", "whatsapp", "followups", "activities",
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
                "can_edit": k in ["leads", "brochure_downloads", "customers", "contacts", "quotations", "followups", "activities"],
                "can_delete": k in ["leads", "quotations"],
                "can_export": k in ["leads", "brochure_downloads", "quotations", "invoices", "reports"],
                "can_approve": k in ["quotations"],
                "can_assign": k in ["leads", "brochure_downloads"],
                "can_call": k in ["calls", "leads", "customers"],
                "can_whatsapp": k in ["whatsapp", "leads", "brochure_downloads", "customers"],
                "view_scope": "team" if has_acc else "none"
            }
        return res

    # 3. SALES_EXECUTIVE / SALES / EMPLOYEE
    if norm in ["SALES_EXECUTIVE", "SALES", "EMPLOYEE"]:
        sales_exec_mods = {
            "dashboard", "leads", "brochure_downloads", "customers", "contacts",
            "quotations", "calls", "whatsapp", "followups", "activities"
        }
        res = {}
        for mod in SYSTEM_MODULES:
            k = mod["key"]
            has_acc = k in sales_exec_mods
            res[k] = {
                "has_access": has_acc,
                "can_view": has_acc,
                "can_create": k in ["leads", "customers", "contacts", "quotations", "calls", "whatsapp", "followups", "activities"],
                "can_edit": k in ["leads", "brochure_downloads", "customers", "contacts", "quotations", "followups", "activities"],
                "can_delete": False,
                "can_export": k in ["leads", "brochure_downloads", "quotations"],
                "can_approve": False,
                "can_assign": False,
                "can_call": k in ["calls", "leads", "customers"],
                "can_whatsapp": k in ["whatsapp", "leads", "brochure_downloads", "customers"],
                "view_scope": "own" if has_acc else "none"
            }
        return res

    # 4. SUPPORT_MANAGER
    if norm == "SUPPORT_MANAGER":
        sup_mgr_mods = {
            "dashboard", "customers", "contacts", "support_tickets",
            "calls", "whatsapp", "activities", "reports", "leads", "followups"
        }
        res = {}
        for mod in SYSTEM_MODULES:
            k = mod["key"]
            has_acc = k in sup_mgr_mods
            res[k] = {
                "has_access": has_acc,
                "can_view": has_acc,
                "can_create": k in ["support_tickets", "calls", "whatsapp", "activities", "followups"],
                "can_edit": k in ["support_tickets", "activities", "customers", "followups", "leads"],
                "can_delete": False,
                "can_export": k in ["support_tickets", "reports"],
                "can_approve": False,
                "can_assign": k in ["support_tickets", "leads"],
                "can_call": k in ["calls", "customers", "leads"],
                "can_whatsapp": k in ["whatsapp", "customers", "leads"],
                "view_scope": "team" if has_acc else "none"
            }
        return res

    # 5. SUPPORT_EXECUTIVE / SUPPORT
    if norm in ["SUPPORT_EXECUTIVE", "SUPPORT"]:
        sup_exec_mods = {
            "dashboard", "customers", "contacts", "support_tickets",
            "calls", "whatsapp", "activities", "followups", "leads"
        }
        res = {}
        for mod in SYSTEM_MODULES:
            k = mod["key"]
            has_acc = k in sup_exec_mods
            res[k] = {
                "has_access": has_acc,
                "can_view": has_acc,
                "can_create": k in ["support_tickets", "calls", "whatsapp", "activities", "followups"],
                "can_edit": k in ["support_tickets", "activities", "followups", "leads"],
                "can_delete": False,
                "can_export": False,
                "can_approve": False,
                "can_assign": False,
                "can_call": k in ["calls", "customers", "leads"],
                "can_whatsapp": k in ["whatsapp", "customers", "leads"],
                "view_scope": "own" if has_acc else "none"
            }
        return res

    # 6. FINANCE
    if norm == "FINANCE":
        fin_mods = {"dashboard", "payments", "invoices", "customers", "subscriptions", "refunds", "reports"}
        res = {}
        for mod in SYSTEM_MODULES:
            k = mod["key"]
            has_acc = k in fin_mods
            res[k] = {
                "has_access": has_acc,
                "can_view": has_acc,
                "can_create": k in ["payments", "invoices", "subscriptions", "refunds"],
                "can_edit": k in ["payments", "invoices", "subscriptions", "refunds"],
                "can_delete": False,
                "can_export": has_acc,
                "can_approve": k in ["payments", "refunds", "invoices"],
                "can_assign": False,
                "can_call": False,
                "can_whatsapp": False,
                "view_scope": "company" if has_acc else "none"
            }
        return res

    # 7. META_REVIEWER - least-privilege account for Meta App Review.
    # Only the WhatsApp inbox (own/test conversations) and read-only connection
    # status are granted. The backend reviewer allowlist in
    # services/reviewer_access.py is the hard boundary even if an admin edits
    # these permissions later.
    if norm == "META_REVIEWER":
        reviewer_modules = {"whatsapp", "whatsapp_connection"}
        res = {}
        for mod in SYSTEM_MODULES:
            k = mod["key"]
            has_acc = k in reviewer_modules
            res[k] = {
                "has_access": has_acc,
                "can_view": has_acc,
                "can_create": k in ("whatsapp", "whatsapp_connection"),
                "can_edit": False,
                "can_delete": False,
                "can_export": False,
                "can_approve": False,
                "can_assign": False,
                "can_call": False,
                "can_whatsapp": k == "whatsapp",
                "view_scope": (
                    "own" if k == "whatsapp"
                    else "company" if k == "whatsapp_connection"
                    else "none"
                ),
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
    ADMIN, SALES_MANAGER, SALES_EXECUTIVE, MANAGER, SALES, EMPLOYEE, FINANCE, SUPPORT,
    SUPPORT_MANAGER, SUPPORT_EXECUTIVE, META_REVIEWER.
    Also repairs/seeds any missing module permissions for existing roles so that every role
    has every catalog module row populated with valid permission flags.
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
        },
        {
            "name": "META_REVIEWER",
            "display_name": "Meta App Reviewer (limited)",
            "description": "Least-privilege review account. Only the WhatsApp inbox and read-only WhatsApp Connection status are reachable.",
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
            elif role_obj.name.upper() in ["SUPPORT_EXECUTIVE", "SUPPORT", "SUPPORT_MANAGER"] and mod_key == "followups" and not p.has_access:
                p.has_access = True
                p.can_view = True
                p.can_create = True
                p.can_edit = True
                p.view_scope = "team" if "MANAGER" in role_obj.name.upper() else "own"
    db.commit()

    # 2b. Grant bulk lead import to Sales Executives.
    # Bulk import uses the same `leads:create` permission as single lead creation.
    # Older or partially configured permission matrices can have that flag off,
    # which made the Import Leads tab fail with
    # "Forbidden: Operation not permitted for role: SALES_EXECUTIVE".
    se_role = existing_roles_map.get("SALES_EXECUTIVE")
    if se_role:
        se_leads = next(
            (p for p in se_role.permissions if (p.module or "").strip().lower() == "leads"),
            None,
        )
        if se_leads:
            repaired_fields = []
            for field in ("has_access", "can_view", "can_create"):
                if not getattr(se_leads, field):
                    setattr(se_leads, field, True)
                    repaired_fields.append(field)
            if repaired_fields:
                db.commit()
                logger.info(
                    "[Permissions] Enabled leads import for SALES_EXECUTIVE (%s).",
                    ", ".join(repaired_fields),
                )

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


SUPPORT_TEAM_ROLES = {"SUPPORT_MANAGER", "SUPPORT_EXECUTIVE", "SUPPORT"}


def _is_support_team_employee(emp: Optional[Employee]) -> bool:
    """Return True when the employee belongs to the Support team."""
    if not emp:
        return False
    role = (emp.role or "").strip().upper()
    department = (emp.department or "").strip().upper()
    # Support roles are authoritative. A generic MANAGER in the Support
    # department is also accepted; a Sales role placed in that department is
    # not treated as a support team member.
    return role in SUPPORT_TEAM_ROLES or (department == "SUPPORT" and role == "MANAGER")


def _utc_naive_to_ist_naive(value: Optional[datetime]) -> Optional[datetime]:
    """
    Convert a naive UTC database timestamp (Employee/User.created_at) into the
    naive IST representation used by CallLog.created_at.

    Employee/User timestamps are written with datetime.utcnow(), while call-log
    timestamps are written with get_ist_now(). Comparing them directly would
    shift the cutoff by 5h30m and expose calls made before the team existed.
    """
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value + timedelta(hours=5, minutes=30)


def get_support_team_call_scope(
    user: User,
    db: Session,
    authorized_employee_ids: Optional[List[int]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Resolve the strict Support Team call-log scope for a user.

    There is no separate teams table in this database. The Support Team's
    database identity is the Support Manager's Employee row; its members are
    resolved through the existing Employee.manager_id team relationship.

    Returns None for Admin, non-support users, or users without a support
    employee profile. Otherwise returns:
      team_id: Support Manager Employee.id (the team's DB identity)
      team_manager_employee_id: same value, kept explicit for reporting
      team_created_at_utc: Support Manager Employee.created_at (naive UTC)
      team_created_at_ist: creation cutoff in CallLog.created_at's naive IST
      employee_ids: current support team employee IDs used for filtering
      employee_cutoffs: {employee_id: earliest eligible call timestamp (IST)}

    A member's cutoff is max(team creation, member Employee.created_at), so a
    newly added member's older calls are not retroactively assigned to the team.
    """
    if not user:
        return None

    # Admin always keeps company-wide call visibility.
    if (user.role or "").strip().upper() == "ADMIN":
        return None

    current_emp = db.query(Employee).filter(Employee.user_id == user.id).first()
    if not current_emp or not _is_support_team_employee(current_emp):
        return None

    scope = get_user_view_scope(user, "calls", db)
    if scope == "none":
        return None

    role = (user.role or current_emp.role or "").strip().upper()

    # A Support Manager's own Employee row is the team root. For other support
    # members (e.g. a support executive with own-scope calls), use their
    # Support Manager as the root so the team creation cutoff still applies.
    root = None
    if role == "SUPPORT_MANAGER":
        root = current_emp
    elif current_emp.manager_id:
        candidate = db.query(Employee).filter(Employee.id == current_emp.manager_id).first()
        if candidate and _is_support_team_employee(candidate):
            root = candidate
    if root is None:
        root = current_emp

    team_ids = set(get_team_employee_ids(root.id, db))
    team_ids.add(current_emp.id)
    if authorized_employee_ids is not None:
        team_ids &= set(authorized_employee_ids)
    if not team_ids:
        return None

    members = db.query(Employee).filter(Employee.id.in_(team_ids)).all()
    support_members = [member for member in members if _is_support_team_employee(member)]
    if not support_members:
        return None

    team_created_at_utc = root.created_at or current_emp.created_at
    if team_created_at_utc is None:
        known_creation_times = [
            member.created_at for member in support_members if member.created_at is not None
        ]
        team_created_at_utc = min(known_creation_times) if known_creation_times else None

    if team_created_at_utc is None:
        # Without an authoritative creation time we must not expose any call as
        # belonging to the team.
        return {
            "team_id": root.id,
            "team_manager_employee_id": root.id,
            "team_created_at_utc": None,
            "team_created_at_ist": None,
            "employee_ids": [],
            "employee_cutoffs": {},
        }

    team_cutoff_ist = _utc_naive_to_ist_naive(team_created_at_utc)
    employee_cutoffs: Dict[int, datetime] = {}
    for member in support_members:
        member_created_at_utc = member.created_at or team_created_at_utc
        member_cutoff_ist = _utc_naive_to_ist_naive(member_created_at_utc)
        employee_cutoffs[member.id] = max(team_cutoff_ist, member_cutoff_ist)

    return {
        "team_id": root.id,
        "team_manager_employee_id": root.id,
        "team_created_at_utc": team_created_at_utc,
        "team_created_at_ist": team_cutoff_ist,
        "employee_ids": sorted(employee_cutoffs.keys()),
        "employee_cutoffs": employee_cutoffs,
    }


def get_authorized_followup_employee_ids(user: User, db: Session) -> Optional[List[int]]:
    """
    Returns authorized employee IDs for follow-up viewing, creation, and modification:
      - None: Admin with full company-wide visibility.
      - List[int]: Manager (same-department team employee IDs + self) or
        Executive ([self.id]).
      - []: Unauthorized user or user without an employee profile.

    Follow-ups are only ever scoped to Sales or Support. A non-Admin can never
    receive company-wide visibility, and manager hierarchies are intersected
    with the manager's own department so cross-department reportees cannot leak
    their follow-ups into another department.
    """
    if not user:
        return []

    from services.department_service import (
        DEPT_SALES,
        DEPT_SUPPORT,
        employee_department,
        get_department_employee_ids,
    )
    from services.hierarchy_service import (
        get_team_employee_ids_from_user,
        normalize_role,
        ROLE_ADMIN,
        ROLE_SALES_MANAGER,
        ROLE_SUPPORT_MANAGER,
    )

    norm_role = normalize_role((user.role or "").strip().upper())
    if norm_role == ROLE_ADMIN:
        return None

    emp = db.query(Employee).filter(Employee.user_id == user.id).first()
    if not emp:
        return []

    department = employee_department(emp)
    if department not in (DEPT_SALES, DEPT_SUPPORT):
        return []

    canonical_role = normalize_role(emp.role or norm_role)

    # Check permission scope for 'followups'
    scope = get_user_view_scope(user, "followups", db)
    if scope == "none":
        return []

    department_employee_ids = get_department_employee_ids(db, department)
    allowed_ids = set(department_employee_ids)

    if canonical_role in [ROLE_SALES_MANAGER, ROLE_SUPPORT_MANAGER] or scope == "team":
        team_ids = get_team_employee_ids_from_user(user, db)
        if emp.id not in team_ids:
            team_ids.append(emp.id)
        return [emp_id for emp_id in team_ids if emp_id in allowed_ids]

    if scope in ("department", "company"):
        return department_employee_ids

    # "own", SALES_EXECUTIVE, SUPPORT_EXECUTIVE, EMPLOYEE
    return [emp.id]


def apply_billing_scope_filter(query, user: User, db: Session):
    """
    Applies strict role, department, team, and ownership filters to a Quotation/billing query.
    - ADMIN: Unrestricted company-wide.
    - FINANCE: Company-wide billing scope for accounting & reconciliation.
    - SALES_MANAGER: Scoped to their authorized Sales team (created by team, assigned to team, lead in team, prepared by team).
    - SALES_EXECUTIVE: Scoped to their own documents (created by self, assigned to self, lead assigned to self, prepared by self).
    - SUPPORT_MANAGER / SUPPORT_EXECUTIVE: Excluded from Sales billing documents unless explicitly authorized.
    """
    from models.quotation import Quotation
    from models.lead import Lead
    from sqlalchemy import or_

    if not user:
        return query.filter(Quotation.id == -1)

    norm_role = (user.role or "").strip().upper()
    if norm_role == "ADMIN":
        return query

    # Finance Department / Role check
    if is_finance_team(user, db) or norm_role in ["FINANCE", "FINANCE_EXECUTIVE", "FINANCE_MANAGER", "ACCOUNTS"]:
        return query

    from services.hierarchy_service import (
        normalize_role,
        get_team_employee_ids_from_user,
        get_team_user_ids,
        ROLE_ADMIN,
        ROLE_SALES_MANAGER,
        ROLE_SALES_EXECUTIVE,
        ROLE_SUPPORT_MANAGER,
        ROLE_SUPPORT_EXECUTIVE
    )

    canonical_role = normalize_role(norm_role)
    if canonical_role == ROLE_ADMIN:
        return query

    # Check explicit permission matrix for quotations
    scope = get_user_view_scope(user, "quotations", db)
    if scope == "company":
        return query

    # Support roles cannot access Sales quotations/invoices unless explicitly granted
    if canonical_role in [ROLE_SUPPORT_MANAGER, ROLE_SUPPORT_EXECUTIVE]:
        if not user_has_permission(user, "quotations", "view", db) and not user_has_permission(user, "invoices", "view", db):
            return query.filter(Quotation.id == -1)

    emp = db.query(Employee).filter(Employee.user_id == user.id).first()
    if not emp:
        return query.filter(Quotation.id == -1)

    if canonical_role in [ROLE_SALES_MANAGER, "MANAGER"] or scope == "team":
        team_emp_ids = get_team_employee_ids_from_user(user, db)
        if emp.id not in team_emp_ids:
            team_emp_ids.append(emp.id)
        team_user_ids = get_team_user_ids(user, db)
        if user.id not in team_user_ids:
            team_user_ids.append(user.id)
        team_lead_ids = [lid for (lid,) in db.query(Lead.id).filter(Lead.assigned_to.in_(team_emp_ids)).all()]
        team_emps = db.query(Employee).filter(Employee.id.in_(team_emp_ids)).all()
        team_names = [e.name for e in team_emps if e.name] + [user.username]
        name_filters = [Quotation.prepared_by.ilike(f"%{name}%") for name in team_names if name]

        conditions = [
            Quotation.created_by.in_(team_emp_ids),
            Quotation.created_by_user_id.in_(team_user_ids),
            Quotation.assigned_to.in_(team_emp_ids),
            Quotation.lead_id.in_(team_lead_ids)
        ] + name_filters
        return query.filter(or_(*conditions))

    elif scope == "department" and getattr(emp, "department", None):
        dept_emps = db.query(Employee.id).filter(Employee.department == emp.department).all()
        dept_emp_ids = [e[0] for e in dept_emps]
        dept_lead_ids = [lid for (lid,) in db.query(Lead.id).filter(Lead.assigned_to.in_(dept_emp_ids)).all()]
        return query.filter(
            or_(
                Quotation.created_by.in_(dept_emp_ids),
                Quotation.assigned_to.in_(dept_emp_ids),
                Quotation.lead_id.in_(dept_lead_ids)
            )
        )
    else:
        # Sales Executive / own scope
        emp_id = emp.id
        emp_name = emp.name if emp.name else user.username
        my_lead_ids = [lid for (lid,) in db.query(Lead.id).filter(Lead.assigned_to == emp_id).all()]
        conditions = [
            Quotation.created_by == emp_id,
            Quotation.created_by_user_id == user.id,
            Quotation.assigned_to == emp_id,
            Quotation.lead_id.in_(my_lead_ids)
        ]
        if emp_name:
            conditions.append(Quotation.prepared_by.ilike(f"%{emp_name}%"))
        if user.username:
            conditions.append(Quotation.prepared_by.ilike(f"%{user.username}%"))
        return query.filter(or_(*conditions))


def _support_handoffs_for_billing_doc(doc: Any, db: Session) -> List[Any]:
    """Return every Support handover that owns/contains a billing document.

    A billing document is not always linked back to a lead or customer. A
    quotation converted into a proforma, for example, can keep ``lead_id`` and
    ``customer_id`` NULL while the Support handover only stores the proforma
    id/number. Looking solely at ``doc.lead_id``/``doc.customer_id`` therefore
    denied Support access to a document surfaced in its own purchase view.

    The lookup below walks every explicit link we keep between a document and
    a handover: direct lead/customer, proforma id/number, quotation number,
    source quotation of the handover's proforma, and invoice number.
    """
    from sqlalchemy import or_

    from models.quotation import Quotation
    from models.workflow import FinanceHandoff, SupportHandoff

    handoffs: List[Any] = []
    seen = set()

    def add(candidate):
        if candidate and candidate.id not in seen:
            seen.add(candidate.id)
            handoffs.append(candidate)

    lead_id = getattr(doc, "lead_id", None)
    customer_id = getattr(doc, "customer_id", None)
    doc_id = getattr(doc, "id", None)
    doc_number = getattr(doc, "doc_number", None)
    doc_type = (getattr(doc, "doc_type", "") or "").lower()

    if lead_id:
        for handoff in db.query(SupportHandoff).filter(SupportHandoff.lead_id == lead_id).all():
            add(handoff)

    if customer_id:
        for handoff in db.query(SupportHandoff).filter(SupportHandoff.customer_id == customer_id).all():
            add(handoff)

    direct_conditions = []
    if doc_id:
        direct_conditions.append(SupportHandoff.proforma_id == doc_id)
    if doc_number:
        direct_conditions.extend(
            [
                SupportHandoff.proforma_number == doc_number,
                SupportHandoff.quotation_number == doc_number,
                SupportHandoff.invoice_number == doc_number,
            ]
        )
    if direct_conditions:
        for handoff in db.query(SupportHandoff).filter(or_(*direct_conditions)).all():
            add(handoff)

    # A quotation is normally converted into a proforma before the Sales ->
    # Support handover. The quotation itself may carry no lead/customer, so
    # resolve it through the proforma it was converted into.
    if doc_type == "quotation" and (doc_id or doc_number):
        proforma_conditions = []
        if doc_id:
            proforma_conditions.append(Quotation.source_quotation_id == doc_id)
        if doc_number:
            proforma_conditions.append(Quotation.source_quotation_number == doc_number)
        converted_proformas = (
            db.query(Quotation)
            .filter(Quotation.doc_type == "proforma", or_(*proforma_conditions))
            .all()
        )
        for proforma in converted_proformas:
            conditions = []
            if proforma.id:
                conditions.append(SupportHandoff.proforma_id == proforma.id)
            if proforma.doc_number:
                conditions.append(SupportHandoff.proforma_number == proforma.doc_number)
            if conditions:
                for handoff in db.query(SupportHandoff).filter(or_(*conditions)).all():
                    add(handoff)

    # Finance can record an invoice number on its own handoff before/without a
    # matching Quotation row, so also resolve the Support handover through it.
    if doc_number:
        finance_handoffs = (
            db.query(FinanceHandoff)
            .filter(FinanceHandoff.invoice_number == doc_number)
            .all()
        )
        for finance in finance_handoffs:
            conditions = [SupportHandoff.finance_handoff_id == finance.id]
            if finance.lead_id:
                conditions.append(SupportHandoff.lead_id == finance.lead_id)
            for handoff in db.query(SupportHandoff).filter(or_(*conditions)).all():
                add(handoff)

    return handoffs


def is_user_authorized_for_billing_doc(user: User, doc, db: Session, action: str = "view") -> bool:
    """
    Verifies if the authenticated user has permission to access (view, edit, download) a specific Quotation.
    """
    if not user or not doc:
        return False

    norm_role = (user.role or "").strip().upper()
    if norm_role == "ADMIN":
        return True

    # If action is edit or create on Tax Invoice, only Finance or Admin can do so
    if getattr(doc, "doc_type", "") == "invoice" and action in ["edit", "create", "delete"]:
        return is_finance_team(user, db) or norm_role in ["ADMIN", "FINANCE"]

    # Finance can view all billing documents for accounts reconciliation
    if is_finance_team(user, db) or norm_role in ["FINANCE", "FINANCE_EXECUTIVE", "FINANCE_MANAGER", "ACCOUNTS"]:
        return True

    from services.hierarchy_service import (
        normalize_role,
        get_team_employee_ids_from_user,
        get_team_user_ids,
        ROLE_ADMIN,
        ROLE_SALES_MANAGER,
        ROLE_SALES_EXECUTIVE,
        ROLE_SUPPORT_MANAGER,
        ROLE_SUPPORT_EXECUTIVE
    )
    from models.lead import Lead

    canonical_role = normalize_role(norm_role)
    if canonical_role == ROLE_ADMIN:
        return True

    # Support roles can view handed-over purchase documentation for onboarding/support
    if canonical_role in [ROLE_SUPPORT_MANAGER, ROLE_SUPPORT_EXECUTIVE]:
        if action != "view":
            return False

        emp = db.query(Employee).filter(Employee.user_id == user.id).first()
        emp_id = emp.id if emp else None

        handoffs = _support_handoffs_for_billing_doc(doc, db)
        if handoffs:
            if canonical_role == ROLE_SUPPORT_MANAGER:
                return True
            # Support Executive: can view if assigned, unassigned queue, or in team
            if any(not handoff.assigned_agent_id for handoff in handoffs):
                return True
            if emp_id and any(handoff.assigned_agent_id == emp_id for handoff in handoffs):
                return True
            team_emp_ids = get_team_employee_ids_from_user(user, db)
            if any(handoff.assigned_agent_id in team_emp_ids for handoff in handoffs):
                return True

        # Support users with explicit quotation/invoice view permission
        if user_has_permission(user, "quotations", "view", db) or user_has_permission(user, "invoices", "view", db):
            return True

        return False

    emp = db.query(Employee).filter(Employee.user_id == user.id).first()
    if not emp:
        return False

    scope = get_user_view_scope(user, "quotations", db)
    if scope == "company":
        return True

    if canonical_role in [ROLE_SALES_MANAGER, "MANAGER"] or scope == "team":
        team_emp_ids = get_team_employee_ids_from_user(user, db)
        if emp.id not in team_emp_ids:
            team_emp_ids.append(emp.id)
        team_user_ids = get_team_user_ids(user, db)
        if user.id not in team_user_ids:
            team_user_ids.append(user.id)

        if doc.created_by and doc.created_by in team_emp_ids:
            return True
        if doc.created_by_user_id and doc.created_by_user_id in team_user_ids:
            return True
        if doc.assigned_to and doc.assigned_to in team_emp_ids:
            return True
        if doc.lead_id:
            lead = db.query(Lead).filter(Lead.id == doc.lead_id).first()
            if lead and lead.assigned_to and lead.assigned_to in team_emp_ids:
                return True

        if doc.prepared_by:
            team_emps = db.query(Employee).filter(Employee.id.in_(team_emp_ids)).all()
            for e in team_emps:
                if e.name and e.name.lower() in doc.prepared_by.lower():
                    return True
            if user.username and user.username.lower() in doc.prepared_by.lower():
                return True
        return False
    else:
        # Sales Executive
        if doc.created_by and doc.created_by == emp.id:
            return True
        if doc.created_by_user_id and doc.created_by_user_id == user.id:
            return True
        if doc.assigned_to and doc.assigned_to == emp.id:
            return True
        if doc.lead_id:
            lead = db.query(Lead).filter(Lead.id == doc.lead_id).first()
            if lead and lead.assigned_to == emp.id:
                return True
        if doc.prepared_by:
            if emp.name and emp.name.lower() in doc.prepared_by.lower():
                return True
            if user.username and user.username.lower() in doc.prepared_by.lower():
                return True
        return False


def is_support_lead_authorized(lead: Any, user: User, db: Session) -> bool:
    """
    Checks if a given lead is authorized for a Support team member or Admin.
    - ADMIN: Unrestricted access to all leads.
    - SALES users: Unauthorized for Support Assigned view (return False).
    - SUPPORT_MANAGER: Authorized if:
        1. SupportHandoff exists and support_manager_id == current_emp.id, OR
        2. SupportHandoff exists and assigned_agent_id in team_emp_ids, OR
        3. lead.assigned_to in team_emp_ids, OR
        4. LeadAssignment has assigned_to in team_emp_ids.
    - SUPPORT_EXECUTIVE: Authorized if:
        1. SupportHandoff exists and assigned_agent_id == current_emp.id, OR
        2. lead.assigned_to == current_emp.id, OR
        3. LeadAssignment has assigned_to == current_emp.id.
    """
    if not user or not lead:
        return False

    norm_role = (user.role or "").strip().upper()
    if norm_role == "ADMIN":
        return True

    from services.hierarchy_service import (
        normalize_role,
        get_team_employee_ids_from_user,
        ROLE_ADMIN,
        ROLE_SALES_MANAGER,
        ROLE_SALES_EXECUTIVE,
        ROLE_SUPPORT_MANAGER,
        ROLE_SUPPORT_EXECUTIVE
    )

    canonical_role = normalize_role(norm_role)
    if canonical_role == ROLE_ADMIN:
        return True

    # Sales roles cannot access Support-only lead records
    if canonical_role in [ROLE_SALES_MANAGER, ROLE_SALES_EXECUTIVE]:
        return False

    emp = db.query(Employee).filter(Employee.user_id == user.id).first()
    if not emp:
        return False

    from models.workflow import SupportHandoff
    from models.lead import LeadAssignment
    from models.support import SupportCoverageAssignment
    from utils.timezone import get_ist_now

    handoff = (
        db.query(SupportHandoff)
        .filter(SupportHandoff.lead_id == lead.id)
        .order_by(SupportHandoff.id.desc())
        .first()
    )

    # A leave backup receives temporary access through an explicit, active
    # coverage row. The permanent handoff owner is never rewritten.
    active_coverage = (
        db.query(SupportCoverageAssignment)
        .filter(
            SupportCoverageAssignment.lead_id == lead.id,
            SupportCoverageAssignment.status == "ACTIVE",
            SupportCoverageAssignment.start_date <= get_ist_now().date(),
            SupportCoverageAssignment.end_date >= get_ist_now().date(),
            SupportCoverageAssignment.backup_employee_id == emp.id,
        )
        .first()
    )
    if active_coverage:
        return True

    if canonical_role == ROLE_SUPPORT_MANAGER:
        team_emp_ids = get_team_employee_ids_from_user(user, db)
        if emp.id not in team_emp_ids:
            team_emp_ids.append(emp.id)

        if handoff:
            if handoff.support_manager_id == emp.id or (handoff.support_manager_id and handoff.support_manager_id in team_emp_ids):
                return True
            if handoff.assigned_agent_id and handoff.assigned_agent_id in team_emp_ids:
                return True
            # Converted deals wait unassigned for a Support Manager to pick an
            # executive. Any Support Manager may see and assign them, while
            # still not seeing ordinary Sales-owned leads before conversion.
            from utils.lead_status import is_converted_to_support_status
            if not handoff.assigned_agent_id and is_converted_to_support_status(lead.status):
                return True

        if lead.assigned_to and lead.assigned_to in team_emp_ids:
            return True

        # Trial customers handed to a Support employee of this team before the
        # deal is converted are visible to that employee's Support Manager.
        if getattr(lead, "trial_support_employee_id", None) and lead.trial_support_employee_id in team_emp_ids:
            return True

        team_coverage = (
            db.query(SupportCoverageAssignment.id)
            .filter(
                SupportCoverageAssignment.lead_id == lead.id,
                SupportCoverageAssignment.status == "ACTIVE",
                SupportCoverageAssignment.start_date <= get_ist_now().date(),
                SupportCoverageAssignment.end_date >= get_ist_now().date(),
                SupportCoverageAssignment.backup_employee_id.in_(team_emp_ids),
            )
            .first()
        )
        if team_coverage:
            return True

        return False

    elif canonical_role == ROLE_SUPPORT_EXECUTIVE:
        if handoff and handoff.assigned_agent_id == emp.id:
            return True

        if lead.assigned_to == emp.id:
            return True

        # The Support employee selected in the Set Trial Period modal owns the
        # trial customer from that moment, before any Won -> Support handoff.
        if getattr(lead, "trial_support_employee_id", None) == emp.id:
            return True

        return False

    return False


def get_support_authorized_lead_ids(user: User, db: Session) -> Optional[List[int]]:
    """
    Returns list of Lead IDs authorized for the Support user, or None if ADMIN (unrestricted).
    Returns [] if user has no authorized support leads or is unauthorized.
    """
    if not user:
        return []

    norm_role = (user.role or "").strip().upper()
    if norm_role == "ADMIN":
        return None

    from services.hierarchy_service import (
        normalize_role,
        get_team_employee_ids_from_user,
        ROLE_ADMIN,
        ROLE_SALES_MANAGER,
        ROLE_SALES_EXECUTIVE,
        ROLE_SUPPORT_MANAGER,
        ROLE_SUPPORT_EXECUTIVE
    )

    canonical_role = normalize_role(norm_role)
    if canonical_role == ROLE_ADMIN:
        return None

    if canonical_role in [ROLE_SALES_MANAGER, ROLE_SALES_EXECUTIVE]:
        return []

    emp = db.query(Employee).filter(Employee.user_id == user.id).first()
    if not emp:
        return []

    from models.workflow import SupportHandoff
    from models.lead import Lead
    from models.support import SupportCoverageAssignment
    from utils.timezone import get_ist_now
    from sqlalchemy import or_

    lead_ids = set()
    today = get_ist_now().date()

    if canonical_role == ROLE_SUPPORT_MANAGER:
        team_emp_ids = get_team_employee_ids_from_user(user, db)
        if emp.id not in team_emp_ids:
            team_emp_ids.append(emp.id)

        # 1. Handoffs where support_manager_id is in team or assigned_agent_id is in team
        h_leads = db.query(SupportHandoff.lead_id).filter(
            or_(
                SupportHandoff.support_manager_id.in_(team_emp_ids),
                SupportHandoff.assigned_agent_id.in_(team_emp_ids)
            )
        ).all()
        for h in h_leads:
            if h[0]:
                lead_ids.add(h[0])

        # 1b. Converted deals that are still waiting for a Support Executive.
        # They are intentionally visible to Support Managers so the explicit
        # conversion step can be completed without assigning ownership early.
        from utils.lead_status import is_converted_to_support_status
        unassigned_converted = (
            db.query(SupportHandoff.lead_id, Lead.status)
            .join(Lead, Lead.id == SupportHandoff.lead_id)
            .filter(SupportHandoff.assigned_agent_id.is_(None))
            .all()
        )
        for lead_id, lead_status in unassigned_converted:
            if lead_id and is_converted_to_support_status(lead_status):
                lead_ids.add(lead_id)

        # 2. Leads directly assigned to team members
        direct_leads = db.query(Lead.id).filter(Lead.assigned_to.in_(team_emp_ids)).all()
        for d in direct_leads:
            lead_ids.add(d[0])

        # 2b. Trial customers whose Support owner is a team member
        trial_support_leads = (
            db.query(Lead.id)
            .filter(Lead.trial_support_employee_id.in_(team_emp_ids))
            .all()
        )
        for t in trial_support_leads:
            if t[0]:
                lead_ids.add(t[0])

        # 3. Temporary coverage handled by any team member
        coverage_leads = (
            db.query(SupportCoverageAssignment.lead_id)
            .filter(
                SupportCoverageAssignment.status == "ACTIVE",
                SupportCoverageAssignment.start_date <= today,
                SupportCoverageAssignment.end_date >= today,
                SupportCoverageAssignment.backup_employee_id.in_(team_emp_ids),
            )
            .all()
        )
        for row in coverage_leads:
            if row[0]:
                lead_ids.add(row[0])

    elif canonical_role == ROLE_SUPPORT_EXECUTIVE:
        # 1. Handoffs where assigned_agent_id == emp.id
        h_leads = db.query(SupportHandoff.lead_id).filter(SupportHandoff.assigned_agent_id == emp.id).all()
        for h in h_leads:
            if h[0]:
                lead_ids.add(h[0])

        # 2. Leads directly assigned to emp
        direct_leads = db.query(Lead.id).filter(Lead.assigned_to == emp.id).all()
        for d in direct_leads:
            lead_ids.add(d[0])

        # 2b. Trial customers where this employee is the selected Support owner
        trial_support_leads = (
            db.query(Lead.id)
            .filter(Lead.trial_support_employee_id == emp.id)
            .all()
        )
        for t in trial_support_leads:
            if t[0]:
                lead_ids.add(t[0])

        # 3. Customers temporarily covered during the permanent owner's leave
        coverage_leads = (
            db.query(SupportCoverageAssignment.lead_id)
            .filter(
                SupportCoverageAssignment.status == "ACTIVE",
                SupportCoverageAssignment.start_date <= today,
                SupportCoverageAssignment.end_date >= today,
                SupportCoverageAssignment.backup_employee_id == emp.id,
            )
            .all()
        )
        for row in coverage_leads:
            if row[0]:
                lead_ids.add(row[0])

    return list(lead_ids)




