from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
from models.user import User
from models.employee import Employee
from schemas.employee import EmployeeCreate, EmployeeUpdate, EmployeeOut
from services.auth import get_current_user, require_roles, hash_password

router = APIRouter(prefix="/employees", tags=["Employees"])

@router.get("")
@router.get("/", response_model=List[EmployeeOut])
def list_employees(
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Employee)
    if status_filter:
        query = query.filter(Employee.status == status_filter)
    return query.order_by(Employee.created_at.desc()).all()

@router.post("")
@router.post("/", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
def create_employee(
    emp_in: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "MANAGER"]))
):
    # Check if username or email already exists
    existing_user = db.query(User).filter(User.username == emp_in.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username is already taken.")

    existing_email = db.query(Employee).filter(Employee.email == emp_in.email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email is already registered.")

    # Create User
    new_user = User(
        username=emp_in.username,
        hashed_password=hash_password(emp_in.password),
        role=emp_in.role,
        is_active=(emp_in.status == "ACTIVE")
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Create Employee
    new_emp = Employee(
        user_id=new_user.id,
        name=emp_in.name,
        email=emp_in.email,
        phone=emp_in.phone,
        username=emp_in.username,
        role=emp_in.role,
        status=emp_in.status
    )
    db.add(new_emp)
    db.commit()
    db.refresh(new_emp)

    return new_emp

@router.put("/{employee_id}", response_model=EmployeeOut)
def update_employee(
    employee_id: int,
    emp_in: EmployeeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "MANAGER"]))
):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found.")

    user = db.query(User).filter(User.id == emp.user_id).first()

    if emp_in.name is not None:
        emp.name = emp_in.name
    if emp_in.phone is not None:
        emp.phone = emp_in.phone

    if emp_in.email is not None and emp_in.email != emp.email:
        existing = db.query(Employee).filter(Employee.email == emp_in.email, Employee.id != employee_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already taken.")
        emp.email = emp_in.email

    if emp_in.role is not None:
        emp.role = emp_in.role
        if user:
            user.role = emp_in.role

    if emp_in.status is not None:
        emp.status = emp_in.status
        if user:
            user.is_active = (emp_in.status == "ACTIVE")

    if emp_in.password and user:
        user.hashed_password = hash_password(emp_in.password)

    db.commit()
    db.refresh(emp)
    return emp

@router.delete("/{employee_id}")
def delete_or_deactivate_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from services.delete_request_service import handle_entity_deletion
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found.")

    def do_delete():
        emp.status = "INACTIVE"
        if emp.user:
            emp.user.is_active = False
        db.commit()

    return handle_entity_deletion(
        db=db,
        current_user=current_user,
        entity_type="EMPLOYEE",
        entity_id=emp.id,
        entity_name=emp.name or f"Employee #{emp.id}",
        delete_fn=do_delete
    )
