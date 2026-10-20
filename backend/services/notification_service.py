from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from models.notification import Notification
from models.user import User
from models.lead import Lead, LeadAssignment
from models.followup import Followup
from models.call_log import CallLog
from models.activity import LeadActivity

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

def sync_notifications_from_real_data(db: Session, user_id: Optional[int] = None):
    """
    Synchronizes real CRM database events (leads, followups, calls, conversions)
    into the notifications table for all users or a specific user.
    Avoids duplicate entries by checking title/message.
    """
    users = db.query(User).all()
    if user_id:
        users = [u for u in users if u.id == user_id]

    if not users:
        return

    admin_users = [u for u in users if (u.role or "").upper() == "ADMIN"]
    all_target_users = users

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

        notif_type = "LEAD"
        link = f"/leads"

        # Check if already exists
        exists = db.query(Notification).filter(
            Notification.title == title,
            Notification.message == msg
        ).first()

        if not exists:
            # Notify admins and assigned user if any
            targets = admin_users if admin_users else all_target_users
            for target in targets:
                notif = Notification(
                    user_id=target.id,
                    title=title,
                    message=msg,
                    notification_type=notif_type,
                    link_url=link,
                    is_read=False,
                    created_at=lead.created_at or datetime.utcnow()
                )
                db.add(notif)

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

        exists = db.query(Notification).filter(
            Notification.title == title,
            Notification.message == msg
        ).first()

        if not exists:
            # Notify assigned employee or admins
            target_id = f.assigned_to or (admin_users[0].id if admin_users else users[0].id)
            # Find user for employee
            notif = Notification(
                user_id=target_id if any(u.id == target_id for u in users) else users[0].id,
                title=title,
                message=msg,
                notification_type="FOLLOWUP",
                link_url="/communication/followups",
                is_read=False,
                created_at=f.created_at or datetime.utcnow()
            )
            db.add(notif)

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

        exists = db.query(Notification).filter(
            Notification.title == title,
            Notification.message == msg
        ).first()

        if not exists:
            target_user = admin_users[0] if admin_users else users[0]
            notif = Notification(
                user_id=target_user.id,
                title=title,
                message=msg,
                notification_type="CALL",
                link_url="/communication/calls",
                is_read=False,
                created_at=call.created_at or datetime.utcnow()
            )
            db.add(notif)

    # 4. Sync from Real Conversions (Leads with CONVERTED / WON)
    converted_leads = db.query(Lead).filter(Lead.status.in_(["CONVERTED", "WON"])).order_by(desc(Lead.id)).limit(5).all()
    for lead in converted_leads:
        lead_name = lead.name or f"Lead #{lead.id}"
        title = f"Lead Converted: {lead_name}"
        msg = f"{lead_name} was successfully converted to customer status ({lead.status})."

        exists = db.query(Notification).filter(
            Notification.title == title,
            Notification.message == msg
        ).first()

        if not exists:
            for admin in (admin_users if admin_users else users):
                notif = Notification(
                    user_id=admin.id,
                    title=title,
                    message=msg,
                    notification_type="CONVERSION",
                    link_url="/customers",
                    is_read=False,
                    created_at=lead.updated_at or lead.created_at or datetime.utcnow()
                )
                db.add(notif)

    db.commit()
