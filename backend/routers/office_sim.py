from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models.employee import Employee
from models.office_sim import OfficeSimMapping
from models.user import User
from services.auth import get_current_user
from utils.timezone import get_ist_now

router = APIRouter(prefix="/office-sim", tags=["Office SIM Configuration"])

STATUS_VERIFIED = "VERIFIED"
STATUS_REQUIRES_VERIFICATION = "REQUIRES_VERIFICATION"
VALID_STATUSES = {STATUS_VERIFIED, STATUS_REQUIRES_VERIFICATION}


class OfficeSimMappingRequest(BaseModel):
    subscription_id: Optional[int] = None
    sim_slot: Optional[int] = None
    carrier_name: Optional[str] = ""
    display_name: Optional[str] = ""
    phone_number: Optional[str] = None
    phone_account_id: Optional[str] = None
    phone_account_component: Optional[str] = None
    sim_fingerprint: str = Field(min_length=8, max_length=128)


class OfficeSimStatusRequest(BaseModel):
    status: str
    reason: Optional[str] = None


class OfficeSimMappingResponse(BaseModel):
    configured: bool
    id: Optional[int] = None
    employee_id: Optional[int] = None
    subscription_id: Optional[int] = None
    sim_slot: Optional[int] = None
    carrier_name: Optional[str] = None
    display_name: Optional[str] = None
    phone_number: Optional[str] = None
    phone_account_id: Optional[str] = None
    phone_account_component: Optional[str] = None
    sim_fingerprint: Optional[str] = None
    status: str = "NOT_CONFIGURED"
    verification_reason: Optional[str] = None
    verified_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


def get_employee_for_user(user: User, db: Session) -> Optional[Employee]:
    return db.query(Employee).filter(Employee.user_id == user.id).first()


def get_office_sim_mapping(
    db: Session, employee_id: Optional[int]
) -> Optional[OfficeSimMapping]:
    if employee_id is None:
        return None
    return (
        db.query(OfficeSimMapping)
        .filter(OfficeSimMapping.employee_id == employee_id)
        .first()
    )


def canonical_identity_tokens(mapping: OfficeSimMapping) -> set:
    """
    The set of exact identity tokens that may represent this Office SIM.

    No fuzzy matching: the phone number and slot are never used on their own
    because both can change or collide.
    """
    tokens = set()
    if mapping.subscription_id is not None:
        tokens.add(f"subId:{mapping.subscription_id}")
    account_id = (mapping.phone_account_id or "").strip()
    component = (mapping.phone_account_component or "").strip()
    if account_id:
        tokens.add(account_id)
        tokens.add(f"phoneAccount:{account_id}")
        if component:
            tokens.add(f"phoneAccount:{component}#{account_id}")
            tokens.add(f"phoneAccount:{component}|{account_id}")
    return tokens


def sim_identity_matches(
    mapping: OfficeSimMapping,
    sim_account_id: Optional[str],
    sim_subscription_id: Optional[int] = None,
) -> bool:
    # A native subscription id is exact evidence and cannot collide with a
    # personal SIM on the same device.
    if sim_subscription_id is not None and mapping.subscription_id is not None:
        if int(sim_subscription_id) == int(mapping.subscription_id):
            return True
    token = (sim_account_id or "").strip()
    if not token:
        return False
    return token in canonical_identity_tokens(mapping)


def serialize_mapping(mapping: Optional[OfficeSimMapping]) -> OfficeSimMappingResponse:
    if mapping is None:
        return OfficeSimMappingResponse(configured=False)
    return OfficeSimMappingResponse(
        configured=True,
        id=mapping.id,
        employee_id=mapping.employee_id,
        subscription_id=mapping.subscription_id,
        sim_slot=mapping.sim_slot,
        carrier_name=mapping.carrier_name,
        display_name=mapping.display_name,
        phone_number=mapping.phone_number,
        phone_account_id=mapping.phone_account_id,
        phone_account_component=mapping.phone_account_component,
        sim_fingerprint=mapping.sim_fingerprint,
        status=mapping.status or STATUS_REQUIRES_VERIFICATION,
        verification_reason=mapping.verification_reason,
        verified_at=mapping.verified_at,
        updated_at=mapping.updated_at,
    )


def _require_employee(user: User, db: Session) -> Employee:
    employee = get_employee_for_user(user, db)
    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No employee profile is linked to this account.",
        )
    return employee


@router.get("", response_model=OfficeSimMappingResponse)
def read_office_sim(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee = _require_employee(current_user, db)
    return serialize_mapping(get_office_sim_mapping(db, employee.id))


@router.put("", response_model=OfficeSimMappingResponse)
def save_office_sim(
    body: OfficeSimMappingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Registers or re-verifies the employee's Office SIM.

    A subscription id OR a phone-account identity is required. Slot, carrier and
    phone number are descriptive only and can never identify a SIM by
    themselves.
    """
    employee = _require_employee(current_user, db)

    account_id = (body.phone_account_id or "").strip()
    component = (body.phone_account_component or "").strip()
    if body.subscription_id is None and not account_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "An Office SIM must be identified by an Android subscription id "
                "or a phone-account id. Slot, carrier and phone number alone are "
                "not sufficient."
            ),
        )

    fingerprint = (body.sim_fingerprint or "").strip()
    if not fingerprint:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A SIM identity fingerprint is required.",
        )

    mapping = get_office_sim_mapping(db, employee.id)
    now = get_ist_now()
    if mapping is None:
        mapping = OfficeSimMapping(employee_id=employee.id)
        db.add(mapping)

    mapping.subscription_id = body.subscription_id
    mapping.sim_slot = body.sim_slot
    mapping.carrier_name = (body.carrier_name or "").strip() or None
    mapping.display_name = (body.display_name or "").strip() or None
    mapping.phone_number = (body.phone_number or "").strip() or None
    mapping.phone_account_id = account_id or None
    mapping.phone_account_component = component or None
    mapping.sim_fingerprint = fingerprint
    mapping.status = STATUS_VERIFIED
    mapping.verification_reason = None
    mapping.verified_at = now
    mapping.updated_at = now

    db.commit()
    db.refresh(mapping)
    return serialize_mapping(mapping)


@router.post("/status", response_model=OfficeSimMappingResponse)
def update_office_sim_status(
    body: OfficeSimStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lets the device report that the configured SIM is missing or has changed.

    Automatic synchronization stops while the mapping is REQUIRES_VERIFICATION.
    """
    employee = _require_employee(current_user, db)
    mapping = get_office_sim_mapping(db, employee.id)
    if mapping is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Office SIM is configured.",
        )

    new_status = (body.status or "").strip().upper()
    if new_status not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Status must be VERIFIED or REQUIRES_VERIFICATION.",
        )

    mapping.status = new_status
    if new_status == STATUS_VERIFIED:
        mapping.verification_reason = None
        mapping.verified_at = get_ist_now()
    else:
        mapping.verification_reason = (body.reason or "").strip()[:255] or (
            "The configured Office SIM identity changed on this device."
        )
    mapping.updated_at = get_ist_now()
    db.commit()
    db.refresh(mapping)
    return serialize_mapping(mapping)


@router.delete("", response_model=OfficeSimMappingResponse)
def delete_office_sim(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee = _require_employee(current_user, db)
    mapping = get_office_sim_mapping(db, employee.id)
    if mapping is not None:
        db.delete(mapping)
        db.commit()
    return serialize_mapping(None)
