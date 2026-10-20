from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from models.employee import Employee
from schemas.auth import LoginRequest, TokenResponse, UserOut
from services.auth import verify_password, create_access_token, get_current_user, build_user_out
from services.audit import log_audit

router = APIRouter(prefix="/auth", tags=["Authentication"])

def find_user_by_login(login_input: str, db: Session) -> User:
    # 1. Try username
    user = db.query(User).filter(User.username == login_input).first()
    if user:
        return user
    # 2. Try employee email
    emp = db.query(Employee).filter(Employee.email == login_input).first()
    if emp and emp.user_id:
        return db.query(User).filter(User.id == emp.user_id).first()
    return None

@router.post("/login", response_model=TokenResponse)
def login(request_data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    login_str = request_data.username.strip()
    password = request_data.password

    user = find_user_by_login(login_str, db)
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled. Please contact system administrator."
        )

    # Update last_login
    user.last_login = datetime.utcnow()
    db.commit()

    emp = db.query(Employee).filter(Employee.user_id == user.id).first()
    emp_id = emp.id if emp else None

    # Update Employee Presence and Activity Log on login
    if emp:
        try:
            from models.monitoring import EmployeeActivityLog, EmployeePresence
            act = EmployeeActivityLog(
                employee_id=emp.id,
                activity_type="LOGIN",
                description=f"Employee {emp.name} logged in to CRM",
                timestamp=datetime.utcnow()
            )
            db.add(act)

            presence = db.query(EmployeePresence).filter(EmployeePresence.employee_id == emp.id).first()
            if not presence:
                presence = EmployeePresence(employee_id=emp.id)
                db.add(presence)
            presence.last_seen = datetime.utcnow()
            presence.ip_address = request.client.host if request.client else None
            db.commit()
        except Exception:
            db.rollback()

    # Include user_id, employee_id, role in JWT token
    access_token = create_access_token(data={
        "sub": user.username,
        "user_id": user.id,
        "employee_id": emp_id,
        "role": user.role
    })

    log_audit(
        db=db,
        user_id=user.id,
        username=user.username,
        action="LOGIN",
        entity_type="USER",
        entity_id=user.id,
        details=f"User {user.username} logged in successfully.",
        ip_address=request.client.host if request.client else None
    )

    user_out = build_user_out(user, db)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_out
    )

@router.post("/token", response_model=TokenResponse)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), request: Request = None, db: Session = Depends(get_db)):
    login_str = form_data.username.strip()
    user = find_user_by_login(login_str, db)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled. Please contact system administrator."
        )

    user.last_login = datetime.utcnow()
    db.commit()

    emp = db.query(Employee).filter(Employee.user_id == user.id).first()
    emp_id = emp.id if emp else None

    access_token = create_access_token(data={
        "sub": user.username,
        "user_id": user.id,
        "employee_id": emp_id,
        "role": user.role
    })

    log_audit(
        db=db,
        user_id=user.id,
        username=user.username,
        action="LOGIN",
        entity_type="USER",
        entity_id=user.id,
        details=f"User {user.username} logged in via OAuth2 token endpoint.",
        ip_address=request.client.host if (request and request.client) else None
    )

    user_out = build_user_out(user, db)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_out
    )

@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return build_user_out(current_user, db)

@router.post("/logout")
def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    log_audit(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action="LOGOUT",
        entity_type="USER",
        entity_id=current_user.id,
        details=f"User {current_user.username} logged out."
    )
    return {"message": "Logged out successfully"}
