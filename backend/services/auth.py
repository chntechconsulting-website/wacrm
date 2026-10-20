import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
from config import settings
from models.user import User
from models.employee import Employee
from schemas.auth import UserOut

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def hash_password(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def get_user_from_token(token_str: str, db: Session) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token_str, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled. Please contact system administrator."
        )

    return user

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    return get_user_from_token(token, db)

def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin permission required."
        )
    return current_user

def require_manager_or_admin(current_user: User = Depends(get_current_user)):
    if current_user.role not in ["ADMIN", "MANAGER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Manager or Admin permission required."
        )
    return current_user

def require_roles(allowed_roles: List[str]):
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Operation not permitted for role: {current_user.role}"
            )
        return current_user
    return role_checker

def build_user_out(user: User, db: Session) -> UserOut:
    from services.permission_service import get_user_permissions
    employee = db.query(Employee).filter(Employee.user_id == user.id).first()
    emp_id = employee.id if employee else None
    name = employee.name if employee else user.username
    email = employee.email if employee else None
    user_status = "ACTIVE" if user.is_active else "INACTIVE"
    user_perms = get_user_permissions(user, db)

    return UserOut(
        id=user.id,
        employee_id=emp_id,
        name=name,
        email=email,
        username=user.username,
        role=user.role,
        status=user_status,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login=user.last_login,
        employee_name=name,
        employee_email=email,
        permissions=user_perms
    )

def require_permission(module: str, action: str):
    """
    FastAPI Security Dependency:
    Enforces dynamic database-driven permissions on every protected endpoint.
    Returns HTTP 403 Forbidden if current user's role lacks the requested permission.
    """
    def permission_checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        from services.permission_service import user_has_permission
        if not user_has_permission(current_user, module, action, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: You do not have permission to {action} in module '{module}'."
            )
        return current_user
    return permission_checker

