import asyncio
import logging
from datetime import datetime, timedelta, date, time
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import SessionLocal
from models.followup import Followup
from models.lead import Lead
from models.employee import Employee
from models.user import User
from models.notification import Notification

logger = logging.getLogger("followup_reminder_service")

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

def check_and_trigger_followup_reminders(db: Session) -> int:
    """
    Evaluates pending follow-ups and dispatches reminder notifications 1 hour before scheduled time.
    Guarantees no duplicate notifications even when called repeatedly or across app restarts.
    """
    now = datetime.now()
    pending_followups = db.query(Followup).filter(
        Followup.status == "Pending",
        Followup.reminder_dismissed == False,
        Followup.reminder_sent == False
    ).all()

    triggered_count = 0

    for f in pending_followups:
        scheduled_dt = parse_followup_datetime(f.followup_date, f.followup_time)
        if not scheduled_dt:
            continue

        # Check if snoozed
        if f.snoozed_until and now < f.snoozed_until:
            continue

        # 1-hour window: scheduled_dt - 1 hour <= now <= scheduled_dt + 24 hours
        reminder_window_start = scheduled_dt - timedelta(hours=1)
        if reminder_window_start <= now <= (scheduled_dt + timedelta(hours=24)):
            lead = db.query(Lead).filter(Lead.id == f.lead_id).first() if f.lead_id else None
            lead_name = lead.name if lead else f"Lead #{f.lead_id}"
            lead_phone = lead.phone if lead else "-"
            disp_time = format_display_time(f.followup_date, f.followup_time)

            title = f"Follow-up Reminder: {lead_name}"
            msg = f"Upcoming follow-up with {lead_name} ({lead_phone}) scheduled for {disp_time}. Priority: {f.priority}. Notes: {f.notes or 'None'}"

            # Target recipient users:
            target_user_ids = set()
            if f.assigned_to:
                emp = db.query(Employee).filter(Employee.id == f.assigned_to).first()
                if emp and emp.user_id:
                    target_user_ids.add(emp.user_id)
                if emp and emp.manager_id:
                    mgr_emp = db.query(Employee).filter(Employee.id == emp.manager_id).first()
                    if mgr_emp and mgr_emp.user_id:
                        target_user_ids.add(mgr_emp.user_id)

            # Fallback if no employee user mapped: notify admins
            if not target_user_ids:
                admins = db.query(User).filter(User.role == "ADMIN", User.is_active == True).all()
                for a in admins:
                    target_user_ids.add(a.id)

            for u_id in target_user_ids:
                # Prevent duplicate notification
                existing_notif = db.query(Notification).filter(
                    Notification.user_id == u_id,
                    Notification.title == title,
                    Notification.link_url == f"/leads?openLeadId={f.lead_id}"
                ).first()

                if not existing_notif:
                    notif = Notification(
                        user_id=u_id,
                        title=title,
                        message=msg,
                        notification_type="FOLLOWUP",
                        link_url=f"/leads?openLeadId={f.lead_id}",
                        is_read=False,
                        created_at=now
                    )
                    db.add(notif)

            f.reminder_sent = True
            f.reminder_sent_at = now
            triggered_count += 1

    if triggered_count > 0:
        db.commit()

    return triggered_count

async def start_followup_reminder_scheduler(interval_seconds: int = 60):
    """
    Background scheduler loop checking and arming 1-hour follow-up reminders.
    """
    logger.info("Follow-up 1-Hour Reminder background scheduler started.")
    while True:
        try:
            db = SessionLocal()
            try:
                check_and_trigger_followup_reminders(db)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error in followup reminder scheduler loop: {e}")
        await asyncio.sleep(interval_seconds)
