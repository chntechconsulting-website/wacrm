import logging
import re
import uuid
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, and_

from config import settings
from database import get_db
from models.user import User
from models.employee import Employee
from models.lead import Lead
from models.customer import Customer
from models.followup import Followup
from models.activity import LeadActivity
from models.monitoring import FieldVisit, EmployeeActivityLog
from services.auth import get_current_user
from services.hierarchy_service import get_authorized_performance_employee_ids
from services.reinquiry_service import ReInquiryService
from routers.employee_monitoring import authorize_employee_access

logger = logging.getLogger("field_visits_router")

router = APIRouter(prefix="/field-visits", tags=["Field Visits"])

# Field-visit images are stored under the existing uploads root and served by
# the already-mounted /uploads route. Temporary device paths are never persisted.
_FIELD_VISIT_UPLOAD_DIR = "field_visits"
_FIELD_VISIT_URL_PREFIX = f"/uploads/{_FIELD_VISIT_UPLOAD_DIR}/"
_MAX_IMAGE_BYTES = 10 * 1024 * 1024
_ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heif",
}


def _looks_like_image(header: bytes, extension: str) -> bool:
    """Rejects files whose bytes do not match the claimed image type."""
    if extension in (".jpg", ".jpeg"):
        return header.startswith(b"\xff\xd8\xff")
    if extension == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if extension == ".webp":
        return (
            len(header) >= 12
            and header[:4] == b"RIFF"
            and header[8:12] == b"WEBP"
        )
    if extension in (".heic", ".heif"):
        # ISO-BMFF container: size (4 bytes) + 'ftyp' + HEIF brand.
        return len(header) >= 12 and header[4:8] == b"ftyp"
    return False


def _clean_url(value: Any, field_label: str) -> Optional[str]:
    """
    Accepts only empty values or URLs produced by the upload endpoint.

    A device temp path (`/data/user/...`, `file://`, `content://`) must never be
    stored as a permanent image URL. External https URLs stay accepted for
    backwards compatibility with records created before uploads existed.
    """
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.startswith(("file://", "content://")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"{field_label} must be uploaded first. Local device paths "
                "cannot be stored as permanent image URLs."
            ),
        )
    lower = raw.lower()
    if lower.startswith(("http://", "https://")):
        return raw
    if raw.startswith(_FIELD_VISIT_URL_PREFIX):
        return raw
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"{field_label} must be a valid uploaded image URL.",
    )


def get_employee_for_user(db: Session, user: User) -> Optional[Employee]:
    return db.query(Employee).filter(Employee.user_id == user.id).first()


@router.post("/uploads", status_code=status.HTTP_201_CREATED)
async def upload_field_visit_image(
    kind: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Stores a company-board or visiting-card photo with the existing upload
    infrastructure and returns the permanent URL to save against the visit.

    Files are validated by content type and size before anything is written, and
    are stored outside any static-name directory so two visits can never
    overwrite each other.
    """
    emp = get_employee_for_user(db, current_user)
    if not emp:
        emp = db.query(Employee).filter(
            Employee.id == getattr(current_user, "employee_id", None)
        ).first()
    if not emp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only registered employees can attach field-visit photos.",
        )

    kind_value = (kind or "").strip().lower()
    if kind_value not in {"company_board", "visiting_card"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Photo kind must be 'company_board' or 'visiting_card'.",
        )

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    extension = _ALLOWED_IMAGE_TYPES.get(content_type)
    if not extension:
        filename_ext = Path(file.filename or "").suffix.lower()
        if filename_ext in {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}:
            extension = ".jpg" if filename_ext == ".jpeg" else filename_ext
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Only JPG, PNG, WEBP or HEIC images can be uploaded.",
            )

    target_dir = (
        Path(settings.UPLOAD_DIR) / _FIELD_VISIT_UPLOAD_DIR / str(emp.id)
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    target_name = f"{kind_value}_{uuid.uuid4().hex}{extension}"
    target_path = target_dir / target_name

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
            if total > _MAX_IMAGE_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Each field-visit photo must be 10 MB or smaller.",
                )
            out.write(first_chunk)
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_IMAGE_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Each field-visit photo must be 10 MB or smaller.",
                    )
                out.write(chunk)
    except HTTPException:
        target_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        target_path.unlink(missing_ok=True)
        logger.exception("Field-visit image upload failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not store the image: {exc}",
        )

    return {
        "url": f"{_FIELD_VISIT_URL_PREFIX}{emp.id}/{target_name}",
        "kind": kind_value,
        "size_bytes": total,
        "content_type": content_type,
    }


def handle_field_visit_submission(
    data: Dict[str, Any],
    db: Session,
    current_user: User
) -> Dict[str, Any]:
    emp = get_employee_for_user(db, current_user)
    if not emp:
        # Fallback to employee mapped via User ID or first employee for admin
        emp = db.query(Employee).filter(Employee.id == getattr(current_user, "employee_id", None)).first()
        if not emp and current_user.role == "ADMIN":
            emp = db.query(Employee).first()

    if not emp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only registered employees with an active profile can record field visits."
        )

    # 1. Idempotency & Duplicate Prevention
    client_token = data.get("client_token")
    if client_token:
        existing = db.query(FieldVisit).filter(
            FieldVisit.client_token == client_token,
            FieldVisit.employee_id == emp.id
        ).first()
        if existing:
            return existing.to_dict()

    # 2. Extract and validate payload before writing anything
    checkin_lat = str(data.get("checkin_lat") or "").strip()
    checkin_lng = str(data.get("checkin_lng") or "").strip()
    checkin_address = data.get("checkin_address") or data.get("location_name")
    photo_url = _clean_url(
        data.get("company_board_photo") or data.get("photo_url"),
        "Company board photo",
    )
    visiting_card_url = _clean_url(
        data.get("visiting_card_photo") or data.get("visiting_card_url"),
        "Visiting card photo",
    )
    customer_requirements = data.get("customer_requirements") or data.get("requirements")
    visit_outcome = data.get("visit_outcome") or "Completed"
    notes = data.get("notes") or ""

    gps_accuracy_m: Optional[float] = None
    raw_accuracy = data.get("checkin_accuracy_m")
    if raw_accuracy not in (None, ""):
        try:
            gps_accuracy_m = round(float(raw_accuracy), 2)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="GPS accuracy must be a number of meters.",
            )

    gps_captured_at: Optional[datetime] = None
    raw_captured_at = data.get("gps_captured_at")
    if raw_captured_at:
        try:
            if isinstance(raw_captured_at, datetime):
                gps_captured_at = raw_captured_at
            else:
                gps_captured_at = datetime.fromisoformat(
                    str(raw_captured_at).replace("Z", "+00:00")
                )
        except (TypeError, ValueError):
            gps_captured_at = None

    visit_time = datetime.utcnow()
    raw_visit_time = data.get("visit_time") or data.get("checkin_time")
    if raw_visit_time:
        try:
            if isinstance(raw_visit_time, str):
                visit_time = datetime.fromisoformat(raw_visit_time.replace("Z", "+00:00"))
            elif isinstance(raw_visit_time, datetime):
                visit_time = raw_visit_time
        except Exception:
            visit_time = datetime.utcnow()
    now = datetime.utcnow()

    # 3. Resolve the linked lead. A new lead is created through the existing
    # ReInquiryService so the same phone number can never produce a duplicate:
    # a matching phone links the visit to that lead and registers a re-inquiry.
    lead_id = data.get("lead_id")
    customer_id = data.get("customer_id")
    customer_name = (data.get("customer_name") or "").strip()
    create_new_lead = bool(data.get("create_new_lead"))
    new_lead_payload = data.get("new_lead") or {}
    if not isinstance(new_lead_payload, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="new_lead must be an object with name and phone.",
        )

    lead = None
    if create_new_lead and lead_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Choose either an existing lead or a new lead, not both.",
        )

    new_lead_created = False
    new_lead_matched_existing = False
    if create_new_lead:
        new_name = str(new_lead_payload.get("name") or "").strip()
        new_phone = str(new_lead_payload.get("phone") or "").strip()
        new_company = str(new_lead_payload.get("company") or "").strip()
        new_email = str(new_lead_payload.get("email") or "").strip()
        if not new_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Customer name is required to create a new lead.",
            )
        if len(re.sub(r"\D", "", new_phone)) < 7:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A valid phone number is required to create a new lead.",
            )

        lead_data = {
            "name": new_name,
            "phone": new_phone,
            "company": new_company or None,
            "email": new_email or None,
            "location": checkin_address,
            "source": "FIELD_VISIT",
            "status": "ASSIGNED",
            "assigned_to": emp.id,
            "requirement_notes": customer_requirements,
            "notes": notes,
        }
        lead, is_reinquiry, _enquiry = ReInquiryService.register_enquiry(
            db=db,
            enquiry_data=lead_data,
            creator_emp_id=emp.id,
            creator_name=emp.name,
            commit=False,
        )
        lead_id = lead.id
        new_lead_created = not is_reinquiry
        new_lead_matched_existing = is_reinquiry
        if not customer_name:
            customer_name = (
                lead.name or lead.company or new_name
            )
        if customer_requirements:
            # Keep the visit requirements on the lead as well.
            existing_req = (lead.requirement_notes or "").strip()
            if not existing_req:
                lead.requirement_notes = customer_requirements
    else:
        if lead_id:
            lead = db.query(Lead).filter(Lead.id == lead_id).first()
            if lead and not customer_name:
                customer_name = lead.name or lead.company or f"Lead #{lead.id}"

    customer = None
    if customer_id:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if customer and not customer_name:
            customer_name = customer.company_name or customer.contact_name

    # Prevent rapid double-clicks (same employee, same customer/lead within 30 seconds)
    recent_dup = db.query(FieldVisit).filter(
        FieldVisit.employee_id == emp.id,
        FieldVisit.customer_name == customer_name,
        FieldVisit.checkin_time >= (now - timedelta(seconds=30))
    ).first()
    if recent_dup and not client_token:
        return recent_dup.to_dict()

    # 4. Create Field Visit Record (linked to the resolved or new lead)
    visit = FieldVisit(
        employee_id=emp.id,
        lead_id=lead_id,
        customer_id=customer_id,
        customer_name=customer_name or "Client",
        checkin_lat=checkin_lat,
        checkin_lng=checkin_lng,
        checkin_address=checkin_address,
        checkin_accuracy_m=gps_accuracy_m,
        gps_captured_at=gps_captured_at,
        checkin_time=visit_time,
        checkout_time=now,
        photo_url=photo_url,
        visiting_card_url=visiting_card_url,
        customer_requirements=customer_requirements,
        visit_outcome=visit_outcome,
        notes=notes,
        client_token=client_token,
        status="COMPLETED"
    )
    db.add(visit)
    db.flush()

    # 4. Automatic CRM Activity Creation
    desc_parts = [f"Field Visit completed for {visit.customer_name} by {emp.name}."]
    desc_parts.append(f"Outcome: {visit.visit_outcome}")
    if visit.checkin_address or (visit.checkin_lat and visit.checkin_lng):
        loc_str = visit.checkin_address or f"GPS: {visit.checkin_lat}, {visit.checkin_lng}"
        if visit.checkin_lat and visit.checkin_lng and visit.checkin_address:
            loc_str = (
                f"{loc_str} (GPS: {visit.checkin_lat}, {visit.checkin_lng})"
            )
        if visit.checkin_accuracy_m is not None:
            loc_str = f"{loc_str} [accuracy {visit.checkin_accuracy_m} m]"
        desc_parts.append(f"Location: {loc_str}")
    if visit.customer_requirements:
        desc_parts.append(f"Requirements: {visit.customer_requirements}")
    if visit.notes:
        desc_parts.append(f"Notes: {visit.notes}")
    if visit.photo_url:
        desc_parts.append(f"Company Board Photo: {visit.photo_url}")
    if visit.visiting_card_url:
        desc_parts.append(f"Visiting Card: {visit.visiting_card_url}")

    activity_description = "\n".join(desc_parts)

    activity = LeadActivity(
        lead_id=lead_id,
        customer_id=customer_id,
        employee_id=emp.id,
        performed_by=emp.id,
        activity_type="FIELD_VISIT",
        related_entity_type="FIELD_VISIT",
        related_entity_id=visit.id,
        description=activity_description,
        created_at=now
    )
    db.add(activity)

    emp_log = EmployeeActivityLog(
        employee_id=emp.id,
        activity_type="FIELD_VISIT",
        entity_type="FIELD_VISIT",
        entity_id=visit.id,
        description=f"Field visit at {visit.customer_name} ({visit.visit_outcome})"
    )
    db.add(emp_log)

    # 5. Follow-up Scheduling (Optional)
    schedule_followup = data.get("schedule_followup", False)
    followup_date_str = data.get("followup_date")

    if schedule_followup and followup_date_str and lead_id:
        try:
            fu_date = datetime.strptime(str(followup_date_str).strip(), "%Y-%m-%d").date()
        except ValueError:
            fu_date = date.today() + timedelta(days=2)

        fu_time = data.get("followup_time") or "10:00 AM"
        fu_priority = (data.get("followup_priority") or "MEDIUM").upper()
        fu_notes = data.get("followup_notes") or f"Follow-up after field visit ({visit.visit_outcome})"

        # Check existing pending followup for this lead to avoid duplicates
        existing_fu = db.query(Followup).filter(
            Followup.lead_id == lead_id,
            Followup.status == "Pending"
        ).first()

        if existing_fu:
            existing_fu.followup_date = fu_date
            existing_fu.followup_time = fu_time
            existing_fu.priority = fu_priority
            existing_fu.notes = fu_notes
            existing_fu.assigned_to = emp.id
            existing_fu.reminder_sent = False
            existing_fu.reminder_sent_at = None
            existing_fu.snoozed_until = None
            existing_fu.reminder_dismissed = False
            visit.followup_id = existing_fu.id
            target_fu = existing_fu
        else:
            new_fu = Followup(
                lead_id=lead_id,
                assigned_to=emp.id,
                followup_date=fu_date,
                followup_time=fu_time,
                priority=fu_priority,
                notes=fu_notes,
                status="Pending",
                created_by=emp.id,
                reminder_sent=False,
                reminder_dismissed=False
            )
            db.add(new_fu)
            db.flush()
            visit.followup_id = new_fu.id
            target_fu = new_fu

        # Sync Lead status
        if lead:
            lead.status = "FOLLOW-UP"
            lead.followup_date = fu_date
            lead.followup_time = fu_time

        # Create Follow-up Activity
        fu_activity = LeadActivity(
            lead_id=lead_id,
            customer_id=customer_id,
            employee_id=emp.id,
            performed_by=emp.id,
            activity_type="FOLLOW_UP_SCHEDULED",
            related_entity_type="FOLLOWUP",
            related_entity_id=target_fu.id,
            description=f"Follow-up scheduled for {fu_date} at {fu_time} ({fu_priority} Priority) following field visit. Notes: {fu_notes}",
            created_at=now
        )
        db.add(fu_activity)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(visit)
    payload = visit.to_dict()
    payload["lead_created"] = new_lead_created
    payload["lead_matched_existing"] = new_lead_matched_existing
    return payload


@router.post("", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
def create_field_visit(
    data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submits a new Field Visit record with:
    - Automatic CRM Activity creation linked to lead/customer and employee
    - Optional follow-up scheduling with 1-hour automated reminder tracking
    - Idempotent duplicate prevention via client_token
    - Full synchronization across mobile app and web CRM
    """
    return handle_field_visit_submission(data, db, current_user)


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_field_visits(
    employee_id: Optional[int] = Query(None, description="Filter by Employee ID"),
    lead_id: Optional[int] = Query(None, description="Filter by Lead ID"),
    customer_id: Optional[int] = Query(None, description="Filter by Customer ID"),
    status: Optional[str] = Query(None, description="Filter by status (COMPLETED, CHECKED_IN)"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves Field Visits respecting backend hierarchy and role permissions:
    - Admin: View all company-wide field visits
    - Sales Manager: View team field visits
    - Sales Executive: Strictly view their own field visits
    """
    authorized_emp_ids = get_authorized_performance_employee_ids(current_user, db)
    if authorized_emp_ids is not None and len(authorized_emp_ids) == 0:
        return []

    query = db.query(FieldVisit)

    if employee_id is not None and isinstance(employee_id, int):
        authorize_employee_access(current_user, employee_id, db)
        query = query.filter(FieldVisit.employee_id == employee_id)
    elif authorized_emp_ids is not None:
        query = query.filter(FieldVisit.employee_id.in_(authorized_emp_ids))

    if lead_id is not None and isinstance(lead_id, int):
        query = query.filter(FieldVisit.lead_id == lead_id)

    if customer_id is not None and isinstance(customer_id, int):
        query = query.filter(FieldVisit.customer_id == customer_id)

    if status is not None and isinstance(status, str):
        query = query.filter(FieldVisit.status == status.upper())

    limit_val = limit if isinstance(limit, int) else 100
    offset_val = offset if isinstance(offset, int) else 0
    visits = query.order_by(desc(FieldVisit.checkin_time)).offset(offset_val).limit(limit_val).all()
    return [v.to_dict() for v in visits]


@router.get("/{visit_id}", response_model=Dict[str, Any])
def get_field_visit_by_id(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    visit = db.query(FieldVisit).filter(FieldVisit.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Field visit not found")

    authorize_employee_access(current_user, visit.employee_id, db)
    return visit.to_dict()
