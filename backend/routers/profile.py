import logging
import uuid
from pathlib import Path
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.employee import Employee
from models.team import Team
from models.user import User
from schemas.profile import ProfileOut, ProfileUpdateRequest
from services.audit import log_audit
from services.auth import get_current_user
from services.hierarchy_service import (
    get_department_for_role,
    normalize_department,
    normalize_role,
)

logger = logging.getLogger("profile_router")

router = APIRouter(prefix="/profile", tags=["My Profile"])

ROLE_LABELS = {
    "ADMIN": "Administrator",
    "SALES_MANAGER": "Sales Manager",
    "SALES_EXECUTIVE": "Sales Executive",
    "SUPPORT_MANAGER": "Support Manager",
    "SUPPORT_EXECUTIVE": "Support Executive",
    "FINANCE": "Finance",
    "MANAGER": "Manager",
}

DEPARTMENT_LABELS = {
    "ADMINISTRATION": "Administration",
    "ADMIN": "Administration",
    "SALES": "Sales",
    "SUPPORT": "Support",
    "FINANCE": "Finance",
}

_PROFILE_UPLOAD_DIR = "profiles"
_PROFILE_URL_PREFIX = f"/uploads/{_PROFILE_UPLOAD_DIR}/"
_MAX_PROFILE_PHOTO_BYTES = 2 * 1024 * 1024
_ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _role_label(role: Optional[str]) -> str:
    normalized = normalize_role(role)
    if normalized in ROLE_LABELS:
        return ROLE_LABELS[normalized]
    return (role or "Employee").replace("_", " ").title()


def _department_label(department: Optional[str]) -> Optional[str]:
    normalized = normalize_department(department)
    if not normalized:
        return None
    return DEPARTMENT_LABELS.get(normalized, normalized.replace("_", " ").title())


def _get_employee_or_404(db: Session, user: User) -> Employee:
    employee = db.query(Employee).filter(Employee.user_id == user.id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No employee profile is linked to this account.",
        )
    return employee


def _resolve_reporting_manager(
    db: Session, user: User, employee: Employee
) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """
    Returns (reporting_manager_user_id, manager_employee_id, manager_name).

    ``User.reporting_manager_id`` stores a user id while the legacy
    ``Employee.manager_id`` stores an employee id. Both are supported exactly as
    the existing Users/Roles and reporting APIs do.
    """
    manager_user = None
    manager_employee = None

    manager_user_id = user.reporting_manager_id or employee.reporting_manager_id
    if manager_user_id:
        manager_user = db.query(User).filter(User.id == manager_user_id).first()
        if manager_user:
            manager_employee = (
                db.query(Employee)
                .filter(Employee.user_id == manager_user.id)
                .first()
            )

    if manager_user is None and manager_employee is None and employee.manager_id:
        manager_employee = (
            db.query(Employee).filter(Employee.id == employee.manager_id).first()
        )
        if manager_employee and manager_employee.user_id:
            manager_user = (
                db.query(User)
                .filter(User.id == manager_employee.user_id)
                .first()
            )

    manager_name = None
    if manager_employee and manager_employee.name:
        manager_name = manager_employee.name
    elif manager_user:
        manager_name = manager_user.username

    resolved_user_id = manager_user.id if manager_user else None
    resolved_employee_id = manager_employee.id if manager_employee else None
    return resolved_user_id, resolved_employee_id, manager_name


def _resolve_team(
    db: Session,
    employee: Employee,
    manager_employee_id: Optional[int],
    manager_name: Optional[str],
) -> Optional[str]:
    """
    Team names come from the existing ``teams`` registry, with the same implicit
    manager-team naming used by the Admin department service.
    """
    if manager_employee_id:
        registered = (
            db.query(Team)
            .filter(
                Team.manager_id == manager_employee_id,
                Team.status == "ACTIVE",
            )
            .first()
        )
        if registered:
            return registered.name
        return f"{manager_name}'s Team" if manager_name else None

    registered = (
        db.query(Team)
        .filter(Team.manager_id == employee.id, Team.status == "ACTIVE")
        .first()
    )
    if registered:
        return registered.name

    has_reports = (
        db.query(Employee.id)
        .filter(
            Employee.manager_id == employee.id,
            Employee.status == "ACTIVE",
        )
        .first()
    )
    if has_reports:
        return f"{employee.name}'s Team"
    return None


def _build_profile(db: Session, user: User) -> ProfileOut:
    employee = _get_employee_or_404(db, user)
    manager_user_id, manager_employee_id, manager_name = _resolve_reporting_manager(
        db, user, employee
    )
    department = (
        user.department
        or employee.department
        or get_department_for_role(user.role)
    )
    role_label = _role_label(user.role or employee.role)
    joining_date = employee.date_of_joining
    if joining_date is None and employee.created_at:
        joining_date = employee.created_at.date()

    return ProfileOut(
        id=user.id,
        employee_id=employee.id,
        name=employee.name or user.username,
        email=employee.email,
        phone=employee.phone,
        username=user.username,
        role=normalize_role(user.role or employee.role),
        role_label=role_label,
        department=department,
        department_label=_department_label(department),
        designation=role_label,
        team=_resolve_team(
            db, employee, manager_employee_id, manager_name
        ),
        reporting_manager_id=manager_user_id or manager_employee_id,
        reporting_manager_name=manager_name,
        date_of_joining=joining_date,
        employment_status=(employee.status or ("ACTIVE" if user.is_active else "INACTIVE")).upper(),
        account_status="ACTIVE" if user.is_active else "INACTIVE",
        is_active=bool(user.is_active),
        last_login=user.last_login,
        created_at=user.created_at,
        photo_url=employee.photo_url,
        date_of_birth=employee.date_of_birth,
        gender=employee.gender,
        address=employee.address,
    )


@router.get("", response_model=ProfileOut)
@router.get("/", response_model=ProfileOut)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns the authenticated employee's own profile."""
    return _build_profile(db, current_user)


@router.put("", response_model=ProfileOut)
@router.put("/", response_model=ProfileOut)
def update_my_profile(
    body: ProfileUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Updates personal information only.

    Employment identity fields are deliberately absent from the request schema
    and rejected as unknown fields, so an employee can never change employee_id,
    department, role, permissions, manager or status through this endpoint.
    """
    employee = _get_employee_or_404(db, current_user)
    provided = body.model_fields_set
    changed = []

    if "name" in provided and body.name is not None:
        if body.name != employee.name:
            employee.name = body.name
            changed.append("name")

    if "email" in provided:
        if body.email is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Email address is required.",
            )
        new_email = str(body.email).strip().lower()
        existing = (
            db.query(Employee)
            .filter(
                func.lower(Employee.email) == new_email,
                Employee.id != employee.id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This email address is already registered to another employee.",
            )
        if new_email != (employee.email or "").lower():
            employee.email = new_email
            changed.append("email")

    if "phone" in provided:
        new_phone = body.phone
        if new_phone != employee.phone:
            employee.phone = new_phone
            changed.append("phone")

    if "date_of_birth" in provided:
        if body.date_of_birth != employee.date_of_birth:
            employee.date_of_birth = body.date_of_birth
            changed.append("date_of_birth")

    if "gender" in provided:
        if body.gender != employee.gender:
            employee.gender = body.gender
            changed.append("gender")

    if "address" in provided:
        if body.address != employee.address:
            employee.address = body.address
            changed.append("address")

    if changed:
        try:
            db.commit()
            db.refresh(employee)
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The updated profile conflicts with an existing employee record.",
            )

        log_audit(
            db=db,
            user_id=current_user.id,
            username=current_user.username,
            action="PROFILE_UPDATE",
            entity_type="EMPLOYEE",
            entity_id=employee.id,
            details=(
                f"User {current_user.username} updated personal profile fields: "
                f"{', '.join(changed)}."
            ),
            ip_address=request.client.host if request.client else None,
        )

    return _build_profile(db, current_user)


def _looks_like_image(header: bytes, extension: str) -> bool:
    if extension == ".jpg":
        return header.startswith(b"\xff\xd8\xff")
    if extension == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if extension == ".webp":
        return (
            len(header) >= 12
            and header[:4] == b"RIFF"
            and header[8:12] == b"WEBP"
        )
    return False


def _delete_previous_photo(employee_id: int, photo_url: Optional[str]) -> None:
    if not photo_url or not photo_url.startswith(_PROFILE_URL_PREFIX):
        return
    try:
        relative = photo_url[len("/uploads/"):]
        candidate = (Path(settings.UPLOAD_DIR) / relative).resolve()
        allowed_root = (
            Path(settings.UPLOAD_DIR) / _PROFILE_UPLOAD_DIR / str(employee_id)
        ).resolve()
        candidate.relative_to(allowed_root)
        if candidate.is_file():
            candidate.unlink()
    except (ValueError, OSError):
        # Cleanup must never fail the profile update.
        logger.warning("Could not remove previous profile photo", exc_info=True)


@router.post("/photo", status_code=status.HTTP_201_CREATED)
async def upload_profile_photo(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Stores a profile photo under the existing uploads root and returns its
    permanent public URL. Only JPG, PNG and WEBP images up to 2 MB are accepted.
    """
    employee = _get_employee_or_404(db, current_user)

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    extension = _ALLOWED_IMAGE_TYPES.get(content_type)
    if not extension:
        filename_ext = Path(file.filename or "").suffix.lower()
        if filename_ext in {".jpg", ".jpeg", ".png", ".webp"}:
            extension = ".jpg" if filename_ext == ".jpeg" else filename_ext
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Profile photo must be a JPG, PNG or WEBP image.",
            )

    target_dir = Path(settings.UPLOAD_DIR) / _PROFILE_UPLOAD_DIR / str(employee.id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"avatar_{uuid.uuid4().hex}{extension}"

    total = 0
    try:
        with target_path.open("wb") as out:
            first_chunk = await file.read(1024 * 1024)
            if not first_chunk:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="The uploaded image is empty.",
                )
            if not _looks_like_image(first_chunk, extension):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="The uploaded file is not a valid image of the declared type.",
                )
            total += len(first_chunk)
            if total > _MAX_PROFILE_PHOTO_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Profile photo must be 2 MB or smaller.",
                )
            out.write(first_chunk)
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_PROFILE_PHOTO_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Profile photo must be 2 MB or smaller.",
                    )
                out.write(chunk)
    except HTTPException:
        target_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        target_path.unlink(missing_ok=True)
        logger.exception("Profile photo upload failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not store the profile photo: {exc}",
        )

    previous_photo = employee.photo_url
    employee.photo_url = f"{_PROFILE_URL_PREFIX}{employee.id}/{target_path.name}"
    try:
        db.commit()
        db.refresh(employee)
    except IntegrityError:
        db.rollback()
        target_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not attach the profile photo to the employee record.",
        )

    _delete_previous_photo(employee.id, previous_photo)

    log_audit(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action="PROFILE_PHOTO_UPDATE",
        entity_type="EMPLOYEE",
        entity_id=employee.id,
        details=f"User {current_user.username} updated their profile photo.",
        ip_address=request.client.host if request.client else None,
    )

    return {
        "message": "Profile photo updated successfully.",
        "photo_url": employee.photo_url,
    }
