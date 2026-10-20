import logging
from typing import List, Optional, Tuple, Set, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException, status

from models.user import User
from models.employee import Employee

logger = logging.getLogger("hierarchy_service")

ROLE_ADMIN = "ADMIN"
ROLE_SALES_MANAGER = "SALES_MANAGER"
ROLE_SALES_EXECUTIVE = "SALES_EXECUTIVE"
ROLE_SUPPORT_MANAGER = "SUPPORT_MANAGER"
ROLE_SUPPORT_EXECUTIVE = "SUPPORT_EXECUTIVE"

ADMIN_ROLES = {"ADMIN"}
SALES_MANAGER_ROLES = {"SALES_MANAGER", "MANAGER"}
SALES_EXECUTIVE_ROLES = {"SALES_EXECUTIVE", "SALES", "EMPLOYEE"}
SUPPORT_MANAGER_ROLES = {"SUPPORT_MANAGER"}
SUPPORT_EXECUTIVE_ROLES = {"SUPPORT_EXECUTIVE", "SUPPORT"}

def normalize_role(role_name: Optional[str]) -> str:
    r = (role_name or "").strip().upper()
    if r in ADMIN_ROLES:
        return ROLE_ADMIN
    if r in SALES_MANAGER_ROLES:
        return ROLE_SALES_MANAGER
    if r in SALES_EXECUTIVE_ROLES:
        return ROLE_SALES_EXECUTIVE
    if r in SUPPORT_MANAGER_ROLES:
        return ROLE_SUPPORT_MANAGER
    if r in SUPPORT_EXECUTIVE_ROLES:
        return ROLE_SUPPORT_EXECUTIVE
    return r

def get_department_for_role(role_name: Optional[str]) -> str:
    norm = normalize_role(role_name)
    if norm == ROLE_ADMIN:
        return "ADMIN"
    if norm in [ROLE_SALES_MANAGER, ROLE_SALES_EXECUTIVE]:
        return "SALES"
    if norm in [ROLE_SUPPORT_MANAGER, ROLE_SUPPORT_EXECUTIVE]:
        return "SUPPORT"
    if norm == "FINANCE":
        return "FINANCE"
    return "GENERAL"

def detect_circular_hierarchy(user_id: int, proposed_manager_id: int, db: Session) -> Tuple[bool, List[str]]:
    """
    Checks if setting user_id's manager to proposed_manager_id would create a circular reporting loop.
    Traverses upward from proposed_manager_id. If user_id is encountered, a cycle exists.
    """
    if user_id == proposed_manager_id:
        u = db.query(User).filter(User.id == user_id).first()
        name = u.username if u else f"User#{user_id}"
        return True, [name, name]

    curr_id = proposed_manager_id
    visited: Set[int] = {user_id}
    path_ids = [user_id, proposed_manager_id]

    for _ in range(50):
        if not curr_id:
            break
        curr_user = db.query(User).filter(User.id == curr_id).first()
        if not curr_user or not curr_user.reporting_manager_id:
            break

        parent_id = curr_user.reporting_manager_id
        path_ids.append(parent_id)

        if parent_id == user_id:
            id_to_user = {u.id: u.username for u in db.query(User).filter(User.id.in_(path_ids)).all()}
            path_names = [id_to_user.get(i, f"User#{i}") for i in path_ids]
            return True, path_names

        if parent_id in visited:
            break
        visited.add(parent_id)
        curr_id = parent_id

    return False, []

def validate_reporting_manager(
    user_id: Optional[int],
    role: str,
    department: Optional[str],
    reporting_manager_id: Optional[int],
    db: Session
) -> Tuple[bool, Optional[str]]:
    """
    Strictly validates reporting manager rules:
    - Sales Executive: requires selecting an active Sales Manager.
    - Support Executive: requires selecting an active Support Manager.
    - Sales Manager or Support Manager: requires selecting an active Admin.
    - Admin: does not require a reporting manager (should be None).
    - Prevents self-assignment.
    - Prevents inactive manager assignment.
    - Prevents circular reporting hierarchies.
    """
    norm_role = normalize_role(role)

    # Rule 4: Admin users do not require a reporting manager
    if norm_role == ROLE_ADMIN:
        return True, None

    # All non-admin roles MUST have a reporting manager
    if not reporting_manager_id:
        if norm_role == ROLE_SALES_EXECUTIVE:
            return False, "Sales Executive requires selecting an active Sales Manager as reporting manager."
        elif norm_role == ROLE_SUPPORT_EXECUTIVE:
            return False, "Support Executive requires selecting an active Support Manager as reporting manager."
        elif norm_role in [ROLE_SALES_MANAGER, ROLE_SUPPORT_MANAGER]:
            display_title = "Sales Manager" if norm_role == ROLE_SALES_MANAGER else "Support Manager"
            return False, f"{display_title} requires selecting an active Admin as reporting manager."
        else:
            return False, "Reporting manager is required for this role."

    # Prevent self-assignment
    if user_id and reporting_manager_id == user_id:
        return False, "A user cannot be their own reporting manager."

    # Check manager exists
    manager = db.query(User).filter(User.id == reporting_manager_id).first()
    if not manager:
        return False, f"Reporting manager user #{reporting_manager_id} not found."

    # Rule: Manager must be active
    if not manager.is_active:
        return False, f"Selected manager '{manager.username}' is inactive. Inactive managers cannot be assigned."

    mgr_norm_role = normalize_role(manager.role)

    # Rule 1: Sales Executive requires selecting an active Sales Manager
    if norm_role == ROLE_SALES_EXECUTIVE:
        if mgr_norm_role != ROLE_SALES_MANAGER:
            return False, f"Sales Executive must report to an active Sales Manager. User '{manager.username}' has role '{manager.role}'."

    # Rule 2: Support Executive requires selecting an active Support Manager
    elif norm_role == ROLE_SUPPORT_EXECUTIVE:
        if mgr_norm_role != ROLE_SUPPORT_MANAGER:
            return False, f"Support Executive must report to an active Support Manager. User '{manager.username}' has role '{manager.role}'."

    # Rule 3: Sales Manager or Support Manager requires selecting an Admin
    elif norm_role in [ROLE_SALES_MANAGER, ROLE_SUPPORT_MANAGER]:
        if mgr_norm_role != ROLE_ADMIN:
            display_title = "Sales Manager" if norm_role == ROLE_SALES_MANAGER else "Support Manager"
            return False, f"{display_title} must report to an active Admin. User '{manager.username}' has role '{manager.role}'."

    # Rule 7: Prevent circular reporting hierarchy
    if user_id:
        is_circular, cycle_path = detect_circular_hierarchy(user_id, reporting_manager_id, db)
        if is_circular:
            return False, f"Circular reporting hierarchy detected: {' -> '.join(cycle_path)}."

    return True, None

def get_all_subordinate_user_ids(manager_user_id: int, db: Session) -> List[int]:
    """
    Recursively returns all user IDs reporting directly or indirectly to manager_user_id.
    """
    subordinates = []
    queue = [manager_user_id]
    visited = {manager_user_id}

    while queue:
        curr_id = queue.pop(0)
        direct_reports = db.query(User.id).filter(User.reporting_manager_id == curr_id).all()
        for (r_id,) in direct_reports:
            if r_id not in visited:
                visited.add(r_id)
                subordinates.append(r_id)
                queue.append(r_id)

    return subordinates

def get_team_user_ids(user: User, db: Session) -> List[int]:
    """
    Returns user.id + all subordinate user IDs.
    For an Admin, returns all user IDs.
    """
    norm_role = normalize_role(user.role)
    if norm_role == ROLE_ADMIN:
        return [u.id for u in db.query(User.id).all()]
    return [user.id] + get_all_subordinate_user_ids(user.id, db)

def get_team_employee_ids_from_user(user: User, db: Session) -> List[int]:
    """
    Returns employee IDs belonging to the user and all their subordinates.
    For Admin, returns all employee IDs.
    """
    norm_role = normalize_role(user.role)
    if norm_role == ROLE_ADMIN:
        return [e.id for e in db.query(Employee.id).all()]

    user_ids = get_team_user_ids(user, db)
    emps = db.query(Employee.id).filter(Employee.user_id.in_(user_ids)).all()
    emp_ids = [e[0] for e in emps]

    # Also include employees who have manager_id pointing to user's employee id
    emp = db.query(Employee).filter(Employee.user_id == user.id).first()
    if emp:
        if emp.id not in emp_ids:
            emp_ids.append(emp.id)
        sub_emps = db.query(Employee.id).filter(Employee.manager_id == emp.id).all()
        for (se_id,) in sub_emps:
            if se_id not in emp_ids:
                emp_ids.append(se_id)

    return emp_ids

def get_eligible_managers(
    role: str,
    department: Optional[str] = None,
    exclude_user_id: Optional[int] = None,
    db: Session = None
) -> List[Dict[str, Any]]:
    """
    Returns active users eligible to be reporting managers for a specified role:
    - Sales Executive -> active Sales Managers
    - Support Executive -> active Support Managers
    - Sales Manager or Support Manager -> active Admins
    - Admin -> []
    Filters out exclude_user_id and all its subordinates to prevent circular hierarchies.
    """
    norm_role = normalize_role(role)
    if norm_role == ROLE_ADMIN:
        return []

    target_roles = []
    if norm_role == ROLE_SALES_EXECUTIVE:
        target_roles = list(SALES_MANAGER_ROLES)
    elif norm_role == ROLE_SUPPORT_EXECUTIVE:
        target_roles = list(SUPPORT_MANAGER_ROLES)
    elif norm_role in [ROLE_SALES_MANAGER, ROLE_SUPPORT_MANAGER]:
        target_roles = list(ADMIN_ROLES)
    else:
        target_roles = list(ADMIN_ROLES | SALES_MANAGER_ROLES | SUPPORT_MANAGER_ROLES)

    # Exclude user and all subordinates
    excluded_ids = set()
    if exclude_user_id:
        excluded_ids.add(exclude_user_id)
        subordinates = get_all_subordinate_user_ids(exclude_user_id, db)
        excluded_ids.update(subordinates)

    q = db.query(User).filter(
        User.role.in_(target_roles),
        User.is_active == True
    )
    if excluded_ids:
        q = q.filter(~User.id.in_(list(excluded_ids)))

    managers = q.order_by(User.username).all()
    results = []
    for m in managers:
        emp = db.query(Employee).filter(Employee.user_id == m.id).first()
        results.append({
            "id": m.id,
            "username": m.username,
            "name": emp.name if emp else m.username,
            "role": m.role,
            "department": m.department or get_department_for_role(m.role),
            "email": emp.email if emp else f"{m.username}@company.com"
        })
    return results

def reassign_manager_reports(old_manager_id: int, new_manager_id: int, db: Session) -> int:
    """
    Reassigns all direct reports of old_manager_id to new_manager_id.
    """
    new_mgr = db.query(User).filter(User.id == new_manager_id).first()
    if not new_mgr:
        raise HTTPException(status_code=404, detail="New reporting manager not found.")
    if not new_mgr.is_active:
        raise HTTPException(status_code=400, detail="Cannot reassign to an inactive manager.")

    reports = db.query(User).filter(User.reporting_manager_id == old_manager_id).all()
    count = 0
    new_mgr_emp = db.query(Employee).filter(Employee.user_id == new_manager_id).first()

    for r in reports:
        # Validate that new manager is suitable for r's role
        ok, err = validate_reporting_manager(r.id, r.role, r.department, new_manager_id, db)
        if not ok:
            raise HTTPException(status_code=400, detail=f"Cannot reassign user '{r.username}': {err}")

        r.reporting_manager_id = new_manager_id
        emp = db.query(Employee).filter(Employee.user_id == r.id).first()
        if emp:
            emp.reporting_manager_id = new_manager_id
            if new_mgr_emp:
                emp.manager_id = new_mgr_emp.id
        count += 1

    db.commit()
    return count


def get_authorized_performance_employee_ids(user: User, db: Session) -> Optional[List[int]]:
    """
    Returns authorized employee IDs for Employee Performance & Monitoring:
    - Admin: None (company-wide access across all departments).
    - Sales Manager: strictly their assigned Sales team and reporting hierarchy (manager + subordinates).
    - Sales Executive: strictly their own performance metrics ([current_user_emp.id]).
    - Support Manager: strictly their assigned Support team and reporting hierarchy (manager + subordinates).
    - Support Executive: strictly their own performance metrics ([current_user_emp.id]).
    - Finance: follows configured role permissions on employees module; does not grant company-wide unless explicitly configured.
    """
    norm_role = normalize_role(user.role)

    # 1. Admin has company-wide access to all employees across all departments
    if norm_role == ROLE_ADMIN:
        return None

    emp = db.query(Employee).filter(Employee.user_id == user.id).first()
    if not emp:
        return []

    from services.permission_service import get_user_view_scope
    scope = get_user_view_scope(user, "employees", db)
    if scope == "company":
        return None

    # 2. Sales Manager: can view only employees belonging to their assigned Sales team and reporting hierarchy
    if norm_role == ROLE_SALES_MANAGER:
        team_emp_ids = get_team_employee_ids_from_user(user, db)
        if emp.id not in team_emp_ids:
            team_emp_ids.append(emp.id)
        # Strictly ensure employees belong to Sales department/roles
        valid_sales_emps = db.query(Employee.id).filter(
            Employee.id.in_(team_emp_ids),
            Employee.role.in_(list(SALES_MANAGER_ROLES | SALES_EXECUTIVE_ROLES))
        ).all()
        return [e[0] for e in valid_sales_emps]

    # 3. Sales Executive: can view only their own performance metrics unless explicit permission allows additional access
    if norm_role == ROLE_SALES_EXECUTIVE:
        if scope == "team":
            return get_team_employee_ids_from_user(user, db)
        return [emp.id]

    # 4. Support Manager: can view only employees in their assigned Support team and reporting hierarchy
    if norm_role == ROLE_SUPPORT_MANAGER:
        team_emp_ids = get_team_employee_ids_from_user(user, db)
        if emp.id not in team_emp_ids:
            team_emp_ids.append(emp.id)
        # Strictly ensure employees belong to Support department/roles
        valid_support_emps = db.query(Employee.id).filter(
            Employee.id.in_(team_emp_ids),
            Employee.role.in_(list(SUPPORT_MANAGER_ROLES | SUPPORT_EXECUTIVE_ROLES))
        ).all()
        return [e[0] for e in valid_support_emps]

    # 5. Support Executive: can view only their own performance metrics unless explicitly authorized otherwise
    if norm_role == ROLE_SUPPORT_EXECUTIVE:
        if scope == "team":
            return get_team_employee_ids_from_user(user, db)
        return [emp.id]

    # 6. Finance: must follow its configured role permissions. Do not automatically grant company-wide employee performance access
    if norm_role == "FINANCE":
        if scope == "team":
            return get_team_employee_ids_from_user(user, db)
        return [emp.id]

    # Other roles / default fallback
    if scope == "team":
        return get_team_employee_ids_from_user(user, db)
    return [emp.id]

