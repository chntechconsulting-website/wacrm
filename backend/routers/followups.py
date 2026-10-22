from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from typing import List, Optional
from datetime import datetime, date, time, timedelta

from database import get_db
from models.user import User
from models.employee import Employee
from models.lead import Lead
from models.followup import Followup
from models.activity import LeadActivity

from schemas.followup import (
    FollowupCreate, 
    FollowupUpdate, 
    FollowupOut, 
    FollowupSnoozeRequest, 
    FollowupReminderOut
)
from services.auth import get_current_user
from services.notification_service import create_notification

router = APIRouter(prefix="/followups", tags=["Followups"])

def get_employee_for_user(user: User, db: Session) -> Optional[Employee]:
    return db.query(Employee).filter(Employee.user_id == user.id).first()

def build_followup_out(f: Followup) -> FollowupOut:
    return FollowupOut(
        id=f.id,
        lead_id=f.lead_id,
        lead_name=f.lead.name if f.lead else f"Lead #{f.lead_id}",
        lead_phone=f.lead.phone if f.lead else "-",
        assigned_to=f.assigned_to,
        assigned_employee_name=f.assigned_employee.name if f.assigned_employee else "-",
        followup_date=f.followup_date,
        followup_time=f.followup_time,
        notes=f.notes,
        priority=f.priority,
        status=f.status,
        created_by=f.created_by,
        created_at=f.created_at,
        reminder_sent=getattr(f, 'reminder_sent', False),
        reminder_dismissed=getattr(f, 'reminder_dismissed', False)
    )

def get_team_employee_ids(manager_emp_id: int, db: Session) -> List[int]:
    team = db.query(Employee).filter(Employee.manager_id == manager_emp_id).all()
    return [e.id for e in team] + [manager_emp_id]

def parse_followup_datetime(f_date, f_time_str) -> Optional[datetime]:
    if not f_date:
        return None
    if isinstance(f_date, str):
        try:
            f_date = datetime.strptime(f_date, "%Y-%m-%d").date()
        except Exception:
            return None
    time_str = (f_time_str or "").strip()
    if not time_str:
        return datetime.combine(f_date, time(10, 0))
    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M", "%H:%M:%S", "%I:%M:%S %p"):
        try:
            t = datetime.strptime(time_str.upper(), fmt).time()
            return datetime.combine(f_date, t)
        except ValueError:
            pass
    return datetime.combine(f_date, time(10, 0))

def format_display_time(f_date, f_time_str) -> str:
    dt = parse_followup_datetime(f_date, f_time_str)
    if not dt:
        return str(f_date)
    today = date.today()
    tomorrow = today + timedelta(days=1)
    time_part = dt.strftime("%I:%M %p").lstrip("0")
    if dt.date() == today:
        return f"Today, {time_part}"
    elif dt.date() == tomorrow:
        return f"Tomorrow, {time_part}"
    else:
        return f"{dt.strftime('%b %d')}, {time_part}"


# ==============================================================================
# REMINDER ENDPOINTS (1-Hour Automatic Reminder with Snooze and Dismiss)
# ==============================================================================

@router.get("/reminders/active", response_model=List[FollowupReminderOut])
@router.get("/active-reminders", response_model=List[FollowupReminderOut])
def get_active_reminders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetch all active 1-hour follow-up reminders for the authenticated user/employee.
    Triggers automatically when current time is within 1 hour before scheduled follow-up time.
    Strictly enforces employee role permissions:
      - EMPLOYEE sees only followups assigned to them.
      - MANAGER sees followups for themselves and their team.
      - ADMIN sees authorized pending followups.
    """
    current_emp = get_employee_for_user(current_user, db)

    query = db.query(Followup).join(Lead, Followup.lead_id == Lead.id).filter(
        Followup.status == "Pending",
        Followup.reminder_dismissed == False
    )

    if current_user.role == "EMPLOYEE":
        if not current_emp:
            return []
        query = query.filter(Followup.assigned_to == current_emp.id)
    elif current_user.role == "MANAGER":
        if current_emp:
            team_ids = get_team_employee_ids(current_emp.id, db)
            query = query.filter(Followup.assigned_to.in_(team_ids))
        else:
            return []
    # ADMIN has full visibility over authorized pending followups

    pending_followups = query.all()
    active_reminders: List[FollowupReminderOut] = []
    now = datetime.now()

    for f in pending_followups:
        scheduled_dt = parse_followup_datetime(f.followup_date, f.followup_time)
        if not scheduled_dt:
            continue

        # Check if currently snoozed
        if f.snoozed_until and now < f.snoozed_until:
            continue

        # Trigger exactly 1 hour before scheduled time:
        # reminder_window_start = scheduled_dt - 1 hour
        reminder_window_start = scheduled_dt - timedelta(hours=1)

        # Active if now >= 1 hour before scheduled time, up to 24 hours past scheduled time
        if reminder_window_start <= now <= (scheduled_dt + timedelta(hours=24)):
            # If reminder was not recorded as sent yet, mark it and generate a notification record
            if not f.reminder_sent:
                f.reminder_sent = True
                f.reminder_sent_at = now
                try:
                    lead_name = f.lead.name if f.lead else f"Lead #{f.lead_id}"
                    lead_phone = f.lead.phone if f.lead else "-"
                    disp_time = format_display_time(f.followup_date, f.followup_time)
                    create_notification(
                        db=db,
                        user_id=current_user.id,
                        title=f"Follow-up Reminder: {lead_name}",
                        message=f"Upcoming follow-up with {lead_name} ({lead_phone}) scheduled for {disp_time}. Notes: {f.notes or 'None'}",
                        notification_type="FOLLOWUP",
                        link_url=f"/leads?openLeadId={f.lead_id}"
                    )
                except Exception as ex:
                    print(f"Error creating reminder notification record: {ex}")
                db.commit()

            active_reminders.append(
                FollowupReminderOut(
                    id=f.id,
                    lead_id=f.lead_id,
                    lead_name=f.lead.name if f.lead else f"Lead #{f.lead_id}",
                    lead_phone=f.lead.phone if f.lead else "-",
                    followup_date=str(f.followup_date),
                    followup_time=f.followup_time,
                    scheduled_datetime=scheduled_dt.isoformat(),
                    display_time=format_display_time(f.followup_date, f.followup_time),
                    notes=f.notes,
                    priority=f.priority,
                    status=f.status,
                    assigned_to=f.assigned_to,
                    assigned_employee_name=f.assigned_employee.name if f.assigned_employee else "-",
                    reminder_sent=f.reminder_sent,
                    snoozed_until=f.snoozed_until,
                    reminder_dismissed=f.reminder_dismissed
                )
            )

    return active_reminders


@router.post("/{followup_id}/snooze")
def snooze_followup_reminder(
    followup_id: int,
    snooze_req: FollowupSnoozeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Snooze an active reminder for 10, 15, or 30 minutes without modifying the actual follow-up.
    """
    f = db.query(Followup).filter(Followup.id == followup_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Follow-up not found")

    current_emp = get_employee_for_user(current_user, db)
    if current_user.role == "EMPLOYEE":
        if not current_emp or f.assigned_to != current_emp.id:
            raise HTTPException(status_code=403, detail="Not authorized to snooze this reminder")
    elif current_user.role == "MANAGER":
        if current_emp:
            team_ids = get_team_employee_ids(current_emp.id, db)
            if f.assigned_to not in team_ids:
                raise HTTPException(status_code=403, detail="Not authorized to snooze this reminder")

    mins = snooze_req.minutes if snooze_req.minutes > 0 else 15
    f.snoozed_until = datetime.now() + timedelta(minutes=mins)
    f.reminder_dismissed = False
    db.commit()

    return {
        "success": True,
        "message": f"Reminder snoozed for {mins} minutes",
        "snoozed_until": f.snoozed_until.isoformat()
    }


@router.post("/{followup_id}/dismiss-reminder")
def dismiss_followup_reminder(
    followup_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Dismiss the reminder popup without modifying or deleting the underlying follow-up.
    """
    f = db.query(Followup).filter(Followup.id == followup_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Follow-up not found")

    current_emp = get_employee_for_user(current_user, db)
    if current_user.role == "EMPLOYEE":
        if not current_emp or f.assigned_to != current_emp.id:
            raise HTTPException(status_code=403, detail="Not authorized to dismiss this reminder")
    elif current_user.role == "MANAGER":
        if current_emp:
            team_ids = get_team_employee_ids(current_emp.id, db)
            if f.assigned_to not in team_ids:
                raise HTTPException(status_code=403, detail="Not authorized to dismiss this reminder")

    f.reminder_dismissed = True
    db.commit()

    return {
        "success": True,
        "message": "Follow-up reminder dismissed successfully"
    }


# ==============================================================================
# STANDARD CRUD ENDPOINTS
# ==============================================================================

@router.get("")
@router.get("/", response_model=List[FollowupOut])
def list_followups(
    status_filter: Optional[str] = None,
    status: Optional[str] = None,
    priority_filter: Optional[str] = None,
    priority: Optional[str] = None,
    date_filter: Optional[str] = None,
    search: Optional[str] = None,
    assigned_to_filter: Optional[int] = None,
    assigned_to: Optional[int] = None,
    upcoming_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Followup).join(Lead, Followup.lead_id == Lead.id)
    current_emp = get_employee_for_user(current_user, db)

    # Role permission filter: Sales employees only see followups assigned to them; Managers see their team
    if current_user.role == "EMPLOYEE" and current_emp:
        query = query.filter(Followup.assigned_to == current_emp.id)
    elif current_user.role == "MANAGER" and current_emp:
        team_ids = get_team_employee_ids(current_emp.id, db)
        query = query.filter(Followup.assigned_to.in_(team_ids))

    eff_assigned_to = assigned_to_filter if assigned_to_filter is not None else assigned_to
    if eff_assigned_to:
        query = query.filter(Followup.assigned_to == eff_assigned_to)

    eff_status = status_filter or status
    if eff_status and eff_status.upper() != "ALL":
        query = query.filter(Followup.status == eff_status)

    eff_priority = priority_filter or priority
    if eff_priority and eff_priority.upper() != "ALL":
        query = query.filter(Followup.priority == eff_priority)

    if upcoming_only:
        today = date.today()
        query = query.filter(Followup.followup_date >= today, Followup.status == "Pending")

    if date_filter and date_filter.upper() != "ALL":
        today = date.today()
        df = date_filter.strip().lower()
        if df == "today":
            query = query.filter(Followup.followup_date == today)
        elif df == "upcoming":
            query = query.filter(Followup.followup_date >= today, Followup.status == "Pending")
        elif df == "overdue":
            query = query.filter(Followup.followup_date < today, Followup.status == "Pending")
        elif df == "completed":
            query = query.filter(Followup.status == "Completed")
        else:
            try:
                target_d = datetime.strptime(date_filter.strip(), "%Y-%m-%d").date()
                query = query.filter(Followup.followup_date == target_d)
            except Exception:
                pass

    if search:
        search_fmt = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Lead.name.ilike(search_fmt),
                Lead.phone.ilike(search_fmt),
                Lead.company.ilike(search_fmt),
                Followup.notes.ilike(search_fmt)
            )
        )

    followups = query.order_by(Followup.followup_date.asc()).all()
    return [build_followup_out(f) for f in followups]

@router.post("", response_model=FollowupOut, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=FollowupOut, status_code=status.HTTP_201_CREATED)
def create_followup(
    f_in: FollowupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lead = db.query(Lead).filter(Lead.id == f_in.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    current_emp = get_employee_for_user(current_user, db)
    creator_id = current_emp.id if current_emp else None
    creator_name = current_emp.name if current_emp else current_user.username

    # EMPLOYEE SECURITY ENFORCEMENT
    if current_user.role == "EMPLOYEE":
        if not current_emp or lead.assigned_to != current_emp.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only create followups for leads assigned to you."
            )
        target_assigned_to = current_emp.id
    else:
        target_assigned_to = f_in.assigned_to or lead.assigned_to or creator_id or 1

    # Check for existing pending followups for this lead to avoid duplicate pending entries
    existing_pending = db.query(Followup).filter(
        Followup.lead_id == f_in.lead_id,
        Followup.status == "Pending"
    ).all()

    if existing_pending:
        # Reuse existing pending record and update its schedule details
        target_followup = existing_pending[0]
        target_followup.followup_date = f_in.followup_date
        target_followup.followup_time = f_in.followup_time or "10:00 AM"
        target_followup.priority = f_in.priority or "MEDIUM"
        if f_in.notes:
            target_followup.notes = f_in.notes
        target_followup.assigned_to = target_assigned_to
        # Reset reminder state for new schedule
        target_followup.reminder_sent = False
        target_followup.reminder_sent_at = None
        target_followup.snoozed_until = None
        target_followup.reminder_dismissed = False

        # Remove any extra duplicate pending records for this lead
        for extra in existing_pending[1:]:
            db.delete(extra)

        followup_record = target_followup
    else:
        followup_record = Followup(
            lead_id=f_in.lead_id,
            assigned_to=target_assigned_to,
            followup_date=f_in.followup_date,
            followup_time=f_in.followup_time or "10:00 AM",
            notes=f_in.notes,
            priority=f_in.priority or "MEDIUM",
            status=f_in.status or "Pending",
            created_by=creator_id,
            reminder_sent=False,
            reminder_dismissed=False
        )
        db.add(followup_record)

    # Sync lead status and dates
    lead.status = "FOLLOW-UP"
    lead.followup_date = f_in.followup_date
    lead.followup_time = f_in.followup_time or "10:00 AM"

    db.commit()
    db.refresh(followup_record)

    # Log Activity in lead timeline
    activity = LeadActivity(
        lead_id=lead.id,
        performed_by=creator_id,
        activity_type="FOLLOW_UP_SCHEDULED",
        description=f"Follow-up scheduled for {f_in.followup_date} ({f_in.priority} Priority) by {creator_name}. Notes: {f_in.notes or 'None'}",
        created_at=datetime.utcnow()
    )
    db.add(activity)
    db.commit()

    return build_followup_out(followup_record)

@router.put("/{followup_id}", response_model=FollowupOut)
def update_followup(
    followup_id: int,
    f_in: FollowupUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    f = db.query(Followup).filter(Followup.id == followup_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Follow-up not found")

    current_emp = get_employee_for_user(current_user, db)
    emp_id = current_emp.id if current_emp else None
    emp_name = current_emp.name if current_emp else current_user.username

    # EMPLOYEE SECURITY ENFORCEMENT
    if current_user.role == "EMPLOYEE":
        if not current_emp or (f.assigned_to != current_emp.id and f.lead.assigned_to != current_emp.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only update followups assigned to you."
            )
        f_in.assigned_to = None

    old_status = f.status
    date_changed = (f_in.followup_date is not None and f_in.followup_date != f.followup_date) or \
                   (f_in.followup_time is not None and f_in.followup_time != f.followup_time)

    if f_in.followup_date is not None: f.followup_date = f_in.followup_date
    if f_in.followup_time is not None: f.followup_time = f_in.followup_time
    if f_in.notes is not None: f.notes = f_in.notes
    if f_in.priority is not None: f.priority = f_in.priority
    if f_in.status is not None: f.status = f_in.status
    if f_in.assigned_to is not None and current_user.role != "EMPLOYEE": f.assigned_to = f_in.assigned_to

    # If scheduled date/time changed, reset reminder state for the new schedule
    if date_changed:
        f.reminder_sent = False
        f.reminder_sent_at = None
        f.snoozed_until = None
        f.reminder_dismissed = False

    # If completed or cancelled, dismiss reminder
    if f.status in ["Completed", "Cancelled"]:
        f.reminder_dismissed = True

    if f_in.status and f_in.status != old_status:
        activity = LeadActivity(
            lead_id=f.lead_id,
            performed_by=emp_id,
            activity_type="FOLLOW_UP_UPDATED",
            description=f"Follow-up status changed {old_status} → {f_in.status} by {emp_name}",
            created_at=datetime.utcnow()
        )
        db.add(activity)

    db.commit()
    db.refresh(f)
    return build_followup_out(f)

@router.delete("/{followup_id}")
def delete_followup(
    followup_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from services.delete_request_service import handle_entity_deletion
    f = db.query(Followup).filter(Followup.id == followup_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Follow-up not found")

    lead_title = f.lead.name if f.lead else f"Lead #{f.lead_id}"

    def do_delete():
        db.delete(f)
        db.commit()

    return handle_entity_deletion(
        db=db,
        current_user=current_user,
        entity_type="FOLLOWUP",
        entity_id=f.id,
        entity_name=f"Followup for {lead_title} ({f.followup_date})",
        delete_fn=do_delete
    )
