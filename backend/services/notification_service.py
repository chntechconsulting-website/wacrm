from datetime import datetime
from typing import Optional

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from models.call_log import CallLog
from models.followup import Followup
from models.lead import Lead
from models.notification import Notification
from models.user import User


def create_notification(
    db: Session,
    user_id: int,
    title: str,
    message: str,
    notification_type: str = "GENERAL",
    link_url: Optional[str] = None
) -> Notification:
    """
    Creates and persists a real notification for a user.
    """
    notif = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        link_url=link_url,
        is_read=False,
        created_at=datetime.utcnow()
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


def _admin_user_ids(db: Session):
    return {
        user.id
        for user in db.query(User).filter(
            func.upper(User.role) == "ADMIN",
            User.is_active == True,
        ).all()
    }


def _scoped_targets(db: Session, requested_user_id: Optional[int], *user_ids):
    """Return only targets relevant to this request.

    ``user_id`` is supplied by the notification endpoint so one user's page load
    must never create notifications for somebody else. Admin users remain the
    fallback owner for events that have no directly assigned employee.
    """
    targets = set(_admin_user_ids(db))
    for user_id in user_ids:
        if user_id:
            targets.add(int(user_id))
    if requested_user_id is not None:
        targets = {uid for uid in targets if uid == requested_user_id}
    return targets


def _notification_exists(db: Session, user_id: int, title: str, message: str) -> bool:
    return bool(
        db.query(Notification.id).filter(
            Notification.user_id == user_id,
            Notification.title == title,
            Notification.message == message,
        ).first()
    )


def sync_notifications_from_real_data(db: Session, user_id: Optional[int] = None):
    """
    Synchronizes real CRM database events (leads, followups, calls, conversions)
    into the notifications table for all users or a specific user.

    Recipients are scoped to the employee who owns the event (plus Admins as the
    fallback). A Sales user never receives another Sales owner's lead, and a
    Support employee only receives notifications for their own assignments.
    """
    # 1. Sync from Real Leads (Most recent 15 leads)
    recent_leads = db.query(Lead).order_by(desc(Lead.id)).limit(15).all()
    for lead in recent_leads:
        lead_name = lead.name or f"Lead #{lead.id}"
        source = lead.source or "Manual"
        title = f"New {source.capitalize()} Lead: {lead_name}"
        msg = f"{lead_name} was captured via {source}."
        if lead.phone:
            msg += f" Phone: {lead.phone}."
        if lead.company:
            msg += f" Company: {lead.company}."

        assigned_user_id = None
        if lead.assigned_employee and lead.assigned_employee.user_id:
            assigned_user_id = lead.assigned_employee.user_id

        for target_id in _scoped_targets(db, user_id, assigned_user_id):
            if _notification_exists(db, target_id, title, msg):
                continue
            db.add(Notification(
                user_id=target_id,
                title=title,
                message=msg,
                notification_type="LEAD",
                link_url="/leads",
                is_read=False,
                created_at=lead.created_at or datetime.utcnow(),
            ))

    # 2. Sync from Real Scheduled Follow-ups
    recent_followups = db.query(Followup).order_by(desc(Followup.id)).limit(10).all()
    for f in recent_followups:
        lead = db.query(Lead).filter(Lead.id == f.lead_id).first() if f.lead_id else None
        lead_name = lead.name if lead else f"Lead #{f.lead_id}"
        date_str = str(f.followup_date or "")
        time_str = str(f.followup_time or "")

        title = f"Follow-up Scheduled: {lead_name}"
        msg = f"Follow-up call with {lead_name} scheduled for {date_str} at {time_str}."
        if f.notes:
            msg += f" Notes: {f.notes[:80]}"

        assigned_user_id = None
        if f.assigned_employee and f.assigned_employee.user_id:
            assigned_user_id = f.assigned_employee.user_id

        for target_id in _scoped_targets(db, user_id, assigned_user_id):
            if _notification_exists(db, target_id, title, msg):
                continue
            db.add(Notification(
                user_id=target_id,
                title=title,
                message=msg,
                notification_type="FOLLOWUP",
                link_url="/communication/followups",
                is_read=False,
                created_at=f.created_at or datetime.utcnow(),
            ))

    # 3. Sync from Real Calls (Call Logs)
    recent_calls = db.query(CallLog).order_by(desc(CallLog.id)).limit(10).all()
    for call in recent_calls:
        lead = call.lead if hasattr(call, 'lead') else None
        contact_name = (lead.name if lead else None) or call.to_number or call.from_number or f"Call #{call.id}"
        direction = (call.call_direction or "Outbound").capitalize()
        status = (call.call_status or "Initiated").capitalize()

        title = f"{direction} Call: {contact_name} ({status})"
        msg = f"{direction} call with {contact_name} ended with status '{status}'."
        if call.duration_seconds:
            msg += f" Duration: {call.duration_seconds}s."
        if call.notes:
            msg += f" Notes: {call.notes[:80]}"

        employee_user_id = None
        if call.employee and call.employee.user_id:
            employee_user_id = call.employee.user_id

        for target_id in _scoped_targets(db, user_id, employee_user_id):
            if _notification_exists(db, target_id, title, msg):
                continue
            db.add(Notification(
                user_id=target_id,
                title=title,
                message=msg,
                notification_type="CALL",
                link_url="/communication/calls",
                is_read=False,
                created_at=call.created_at or datetime.utcnow(),
            ))

    # 4. Sync from Real Conversions (Leads with CONVERTED / WON)
    converted_leads = db.query(Lead).filter(Lead.status.in_([
        "CONVERTED", "WON", "CONVERTED_TO_SUPPORT", "CONVERTED TO SUPPORT"
    ])).order_by(desc(Lead.id)).limit(5).all()
    for lead in converted_leads:
        lead_name = lead.name or f"Lead #{lead.id}"
        title = f"Lead Converted: {lead_name}"
        msg = f"{lead_name} was successfully converted to customer status ({lead.status})."

        assigned_user_id = None
        if lead.assigned_employee and lead.assigned_employee.user_id:
            assigned_user_id = lead.assigned_employee.user_id

        for target_id in _scoped_targets(db, user_id, assigned_user_id):
            if _notification_exists(db, target_id, title, msg):
                continue
            db.add(Notification(
                user_id=target_id,
                title=title,
                message=msg,
                notification_type="CONVERSION",
                link_url="/customers",
                is_read=False,
                created_at=lead.updated_at or lead.created_at or datetime.utcnow(),
            ))

    db.commit()
