from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from typing import List, Optional
from datetime import datetime

from database import get_db
from models.user import User
from models.employee import Employee
from models.audit_log import AuditLog
from schemas.user import (
    UserCreateRequest,
    UserUpdateRequest,
    PasswordResetRequest,
    UserDetailOut,
    AuditLogOut,
    ReassignReportsRequest
)
from services.auth import get_current_user, require_roles, require_admin, hash_password
from services.audit import log_audit
from services.hierarchy_service import (
    validate_reporting_manager,
    get_eligible_managers,
    reassign_manager_reports,
    get_department_for_role,
    normalize_role,
    normalize_department,
    validate_department_and_role,
    ROLE_ADMIN,
    DEPT_ADMINISTRATION
)

router = APIRouter(prefix="/users", tags=["User Management"])

def build_user_detail(user: User, db: Session) -> UserDetailOut:
    emp = db.query(Employee).filter(Employee.user_id == user.id).first()
    
    # Resolve reporting manager details
    reporting_mgr_id = user.reporting_manager_id or (emp.reporting_manager_id if emp else None)
    reporting_mgr_name = None
    reporting_mgr_role = None
    
    if reporting_mgr_id:
        mgr_user = db.query(User).filter(User.id == reporting_mgr_id).first()
        if mgr_user:
            reporting_mgr_role = mgr_user.role
            mgr_emp = db.query(Employee).filter(Employee.user_id == mgr_user.id).first()
            reporting_mgr_name = mgr_emp.name if mgr_emp and mgr_emp.name else mgr_user.username

    # Legacy manager resolution
    manager_name = reporting_mgr_name
    manager_id = reporting_mgr_id
    if emp and emp.manager_id and not manager_name:
        mgr = db.query(Employee).filter(Employee.id == emp.manager_id).first()
        if mgr:
            manager_name = mgr.name
            manager_id = mgr.id

    direct_reports_count = db.query(User).filter(
        User.reporting_manager_id == user.id,
        User.is_active == True
    ).count()

    dept = user.department or (emp.department if emp else None) or get_department_for_role(user.role)

    return UserDetailOut(
        id=user.id,
        employee_id=emp.id if emp else None,
        name=emp.name if emp and emp.name else user.username,
        email=emp.email if emp and emp.email else f"{user.username}@company.com",
        username=user.username,
        role=user.role,
        department=dept,
        reporting_manager_id=reporting_mgr_id,
        reporting_manager_name=reporting_mgr_name,
        reporting_manager_role=reporting_mgr_role,
        manager_id=manager_id,
        manager_name=manager_name,
        direct_reports_count=direct_reports_count,
        status="ACTIVE" if user.is_active else "INACTIVE",
        is_active=user.is_active,
        phone=emp.phone if emp else None,
        created_at=user.created_at,
        last_login=user.last_login
    )

@router.get("/eligible-managers")
def list_eligible_managers(
    role: str = Query(..., description="Role to find eligible managers for"),
    department: Optional[str] = Query(None),
    exclude_user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "SALES_MANAGER", "SUPPORT_MANAGER", "MANAGER"]))
):
    """
    Returns active managers eligible for the given role, preventing circular loops and self-assignment.
    """
    return get_eligible_managers(role=role, department=department, exclude_user_id=exclude_user_id, db=db)

@router.get("", response_model=List[UserDetailOut])
@router.get("/", response_model=List[UserDetailOut])
def list_users(
    department: Optional[str] = Query(None, description="Filter users by department"),
    role: Optional[str] = Query(None, description="Filter users by role"),
    status: Optional[str] = Query(None, description="Filter users by status"),
    search: Optional[str] = Query(None, description="Search by name, email, or username"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "SALES_MANAGER", "SUPPORT_MANAGER", "MANAGER"]))
):
    """
    Lists all CRM users with linked Employee profile, role, department, status, and last login.
    """
    query = db.query(User)
    if department and department.upper() != "ALL":
        norm_dept = normalize_department(department)
        if norm_dept == DEPT_ADMINISTRATION:
            query = query.filter(User.department.in_([DEPT_ADMINISTRATION, "ADMIN"]))
        else:
            query = query.filter(User.department == norm_dept)
    if role and role.upper() != "ALL":
        query = query.filter(User.role == normalize_role(role))
    if status and status.upper() != "ALL":
        is_active = (status.upper() == "ACTIVE")
        query = query.filter(User.is_active == is_active)
    if search:
        s = f"%{search.strip()}%"
        query = query.outerjoin(Employee, Employee.user_id == User.id).filter(
            or_(
                User.username.ilike(s),
                Employee.name.ilike(s),
                Employee.email.ilike(s)
            )
        )
    users = query.order_by(desc(User.created_at)).all()
    return [build_user_detail(u, db) for u in users]

@router.post("", response_model=UserDetailOut, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=UserDetailOut, status_code=status.HTTP_201_CREATED)
def create_user(
    req_data: UserCreateRequest,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Admin Endpoint: Creates a new Employee login credential.
    Performs secure password hashing, strict department/role & manager validation, and links User to Employee record.
    """
    username = req_data.username.strip().lower()
    email = req_data.email.strip().lower()

    # Check duplicates
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail=f"Username '{username}' is already taken.")
    if db.query(Employee).filter(Employee.email == email).first():
        raise HTTPException(status_code=400, detail=f"Email '{email}' is already registered to another employee.")

    role = normalize_role(req_data.role)
    department = normalize_department(req_data.department) or get_department_for_role(role)

    # 1. Validate department and role combination
    dept_ok, dept_err = validate_department_and_role(department, role, current_user)
    if not dept_ok:
        raise HTTPException(status_code=400, detail=dept_err)

    reporting_mgr_id = req_data.reporting_manager_id or req_data.manager_id
    if role == ROLE_ADMIN:
        reporting_mgr_id = None

    # 2. Strict reporting manager validation
    valid, err_msg = validate_reporting_manager(
        user_id=None,
        role=role,
        department=department,
        reporting_manager_id=reporting_mgr_id,
        db=db
    )
    if not valid:
        raise HTTPException(status_code=400, detail=err_msg)

    is_active = (req_data.status.upper() == "ACTIVE")
    hashed_pwd = hash_password(req_data.password)

    # Resolve manager's employee record if any
    mgr_emp = None
    if reporting_mgr_id:
        mgr_emp = db.query(Employee).filter(Employee.user_id == reporting_mgr_id).first()

    # 1. Create User
    new_user = User(
        username=username,
        hashed_password=hashed_pwd,
        role=role,
        department=department,
        reporting_manager_id=reporting_mgr_id,
        is_active=is_active,
        created_at=datetime.utcnow()
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # 2. Create Linked Employee
    new_employee = Employee(
        user_id=new_user.id,
        manager_id=mgr_emp.id if mgr_emp else reporting_mgr_id,
        reporting_manager_id=reporting_mgr_id,
        department=department,
        name=req_data.name.strip(),
        email=email,
        phone=req_data.phone,
        username=username,
        role=role,
        status="ACTIVE" if is_active else "INACTIVE",
        created_at=datetime.utcnow()
    )
    db.add(new_employee)
    db.commit()
    db.refresh(new_employee)

    log_audit(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action="USER_CREATE",
        entity_type="USER",
        entity_id=new_user.id,
        details=f"Admin {current_user.username} created login for {req_data.name} (Role: {new_user.role}, Dept: {department}, Manager ID: {reporting_mgr_id}).",
        ip_address=req.client.host if req.client else None
    )

    return build_user_detail(new_user, db)

@router.put("/{user_id}", response_model=UserDetailOut)
def update_user(
    user_id: int,
    req_data: UserUpdateRequest,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Admin Endpoint: Updates user profile, role, status, or linked manager with strict RBAC rules.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    emp = db.query(Employee).filter(Employee.user_id == user.id).first()

    target_role = normalize_role(req_data.role) if req_data.role else user.role
    target_dept = normalize_department(req_data.department) if req_data.department is not None else (normalize_department(user.department) or get_department_for_role(target_role))

    # Validate department and role combination
    dept_ok, dept_err = validate_department_and_role(target_dept, target_role, current_user)
    if not dept_ok:
        raise HTTPException(status_code=400, detail=dept_err)

    # Manager id resolution
    target_manager_id = user.reporting_manager_id
    if req_data.reporting_manager_id is not None:
        target_manager_id = req_data.reporting_manager_id
    elif req_data.manager_id is not None:
        target_manager_id = req_data.manager_id

    if target_role == ROLE_ADMIN:
        target_manager_id = None

    # Status check
    new_status = req_data.status.upper() if req_data.status else None
    if new_status == "INACTIVE" and user.is_active:
        active_reports = db.query(User).filter(
            User.reporting_manager_id == user.id,
            User.is_active == True
        ).count()
        if active_reports > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot deactivate user '{user.username}' because they have {active_reports} active direct report(s). Please reassign their reports to another active manager first."
            )

    # Validate reporting manager
    valid, err_msg = validate_reporting_manager(
        user_id=user.id,
        role=target_role,
        department=target_dept,
        reporting_manager_id=target_manager_id,
        db=db
    )
    if not valid:
        raise HTTPException(status_code=400, detail=err_msg)

    # Apply updates
    user.role = target_role
    user.department = target_dept
    user.reporting_manager_id = target_manager_id
    if emp:
        emp.role = target_role
        emp.department = target_dept
        emp.reporting_manager_id = target_manager_id
        if target_manager_id:
            mgr_emp = db.query(Employee).filter(Employee.user_id == target_manager_id).first()
            emp.manager_id = mgr_emp.id if mgr_emp else target_manager_id
        else:
            emp.manager_id = None

    if new_status:
        user.is_active = (new_status == "ACTIVE")
        if emp:
            emp.status = "ACTIVE" if user.is_active else "INACTIVE"

    if req_data.password:
        user.hashed_password = hash_password(req_data.password)

    if emp:
        if req_data.name: emp.name = req_data.name.strip()
        if req_data.email: emp.email = req_data.email.strip().lower()
        if req_data.phone is not None: emp.phone = req_data.phone

    db.commit()
    db.refresh(user)

    log_audit(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action="USER_UPDATE",
        entity_type="USER",
        entity_id=user.id,
        details=f"Admin {current_user.username} updated user #{user.id} ({user.username}). Role: {user.role}, Dept: {user.department}, Manager: {user.reporting_manager_id}, Active: {user.is_active}.",
        ip_address=req.client.host if req.client else None
    )

    return build_user_detail(user, db)

@router.post("/{user_id}/reassign-reports")
def reassign_user_reports(
    user_id: int,
    body: ReassignReportsRequest,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Admin Endpoint: Safely reassigns all direct reports of user_id to new_manager_id.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    count = reassign_manager_reports(old_manager_id=user_id, new_manager_id=body.new_manager_id, db=db)

    new_mgr = db.query(User).filter(User.id == body.new_manager_id).first()
    new_mgr_name = new_mgr.username if new_mgr else f"#{body.new_manager_id}"

    log_audit(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action="REASSIGN_REPORTS",
        entity_type="USER",
        entity_id=user.id,
        details=f"Admin {current_user.username} reassigned {count} direct reports of {user.username} to {new_mgr_name}.",
        ip_address=req.client.host if req.client else None
    )

    return {
        "message": f"Successfully reassigned {count} direct report(s) to {new_mgr_name}.",
        "reassigned_count": count
    }

@router.post("/{user_id}/toggle-status", response_model=UserDetailOut)
def toggle_user_status(
    user_id: int,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Admin Endpoint: Activates or Deactivates a user account.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own logged-in admin account.")

    # If deactivating, check if user has active reports
    if user.is_active:
        active_reports = db.query(User).filter(
            User.reporting_manager_id == user.id,
            User.is_active == True
        ).count()
        if active_reports > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot deactivate user '{user.username}' because they have {active_reports} active direct report(s). Please reassign their reports to another active manager first."
            )

    user.is_active = not user.is_active
    emp = db.query(Employee).filter(Employee.user_id == user.id).first()
    if emp:
        emp.status = "ACTIVE" if user.is_active else "INACTIVE"

    db.commit()

    action_label = "ACTIVATED" if user.is_active else "DEACTIVATED"
    log_audit(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action="USER_STATUS_TOGGLE",
        entity_type="USER",
        entity_id=user.id,
        details=f"Admin {current_user.username} {action_label} user account #{user.id} ({user.username}).",
        ip_address=req.client.host if req.client else None
    )

    return build_user_detail(user, db)

@router.post("/{user_id}/reset-password", response_model=UserDetailOut)
def reset_password(
    user_id: int,
    body: PasswordResetRequest,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Admin Endpoint: Resets password for a user.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    user.hashed_password = hash_password(body.new_password)
    db.commit()

    log_audit(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action="PASSWORD_RESET",
        entity_type="USER",
        entity_id=user.id,
        details=f"Admin {current_user.username} reset password for user #{user.id} ({user.username}).",
        ip_address=req.client.host if req.client else None
    )

    return build_user_detail(user, db)

@router.get("/audit-logs", response_model=List[AuditLogOut])
def get_audit_logs(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "MANAGER"]))
):
    """
    Admin/Manager Endpoint: Retrieves system audit logs.
    """
    logs = db.query(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit).all()
    return logs

@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from services.delete_request_service import handle_entity_deletion
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found.")

    if u.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own logged-in user account.")

    def do_delete():
        emp = db.query(Employee).filter(Employee.user_id == u.id).first()
        if emp:
            db.delete(emp)
        db.delete(u)
        db.commit()

    return handle_entity_deletion(
        db=db,
        current_user=current_user,
        entity_type="USER",
        entity_id=u.id,
        entity_name=u.username,
        delete_fn=do_delete
    )
