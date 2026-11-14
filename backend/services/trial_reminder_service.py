"""Trial expiry reminders for Sales Managers and the assigned Support Manager.

The scheduler is deliberately independent from page activity. It re-checks the
database periodically, while :class:`TrialReminderDelivery` guarantees that a
given lead/user/milestone/trial-end-date combination is delivered at most once
even across restarts or multiple application workers.

Recipients come from the existing assignment chain (Support handoff, legacy
MANUAL_SUPPORT row, then the Support Manager selected in the Set Trial Period
modal), so changing a trial's duration or expiry re-targets the reminders
without touching the post-conversion Support workflow.

All date calculations use Asia/Kolkata through ``get_ist_now``. Trial columns
are additive and nullable, so existing production rows are never changed.
"""

import asyncio
import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import SessionLocal
from models.employee import Employee
from models.lead import Lead, LeadAssignment
from models.notification import Notification
from models.trial_reminder import TrialReminderDelivery
from models.user import User
from models.workflow import SupportHandoff
from services.hierarchy_service import (
    ROLE_SALES_MANAGER,
    ROLE_SUPPORT_MANAGER,
    normalize_role,
)
from utils.lead_status import is_trial_status
from utils.timezone import format_ist_date, get_ist_now

logger = logging.getLogger("trial_reminder_service")

NOTIFICATION_TYPE = "TRIAL_EXPIRY"
SALES_TITLE = "Trial Expiry Reminder"
SUPPORT_TITLE = "Trial Expiry – Customer Follow-up Required"

ROLE_SALES = "SALES_MANAGER"
ROLE_SUPPORT = "SUPPORT_EMPLOYEE"

# Milestone keys are stable because they are part of the delivery uniqueness
# key. Do not rename them once production records exist.
MILESTONE_T3 = "T-3"
MILESTONE_T1 = "T-1"
MILESTONE_EXPIRY_DAY = "EXPIRY_DAY"
MILESTONE_EXPIRED_1 = "EXPIRED_1"
MILESTONE_EXPIRED_2 = "EXPIRED_2"
MILESTONE_EXPIRED_3 = "EXPIRED_3"

MILESTONE_BY_DAYS = {
    3: MILESTONE_T3,
    1: MILESTONE_T1,
    0: MILESTONE_EXPIRY_DAY,
    -1: MILESTONE_EXPIRED_1,
    -2: MILESTONE_EXPIRED_2,
    -3: MILESTONE_EXPIRED_3,
}


def trial_milestone_for(trial_end_date: Optional[date], today: Optional[date] = None) -> Optional[str]:
    """Return the reminder milestone due on ``today``, or ``None``.

    Exactly T-3, T-1, expiry day and the first three days after expiry are
    scheduled. The scheduler does not "catch up" missed milestones because that
    would send several reminders at once after downtime.
    """
    if not trial_end_date:
        return None
    today = today or get_ist_now().date()
    return MILESTONE_BY_DAYS.get((trial_end_date - today).days)


def _active_user_for_employee(db: Session, employee: Optional[Employee]) -> Optional[User]:
    """Resolve the login account for an employee, respecting active state."""
    if not employee:
        return None
    if (employee.status or "").strip().upper() != "ACTIVE":
        return None
    if not employee.user_id:
        return None
    user = db.query(User).filter(User.id == employee.user_id).first()
    if not user or not user.is_active:
        return None
    return user


def _manager_user_for_employee(db: Session, employee: Optional[Employee]) -> Optional[User]:
    """Resolve an employee's Sales Manager login account.

    Mirrors the read-only reporting-manager resolution used by the Leads API,
    including the legacy shape where ``reporting_manager_id`` points at a User
    instead of an Employee.
    """
    if not employee:
        return None

    if employee.manager_id:
        manager = db.query(Employee).filter(Employee.id == employee.manager_id).first()
        user = _active_user_for_employee(db, manager)
        if user:
            return user

    if employee.reporting_manager_id:
        manager = (
            db.query(Employee)
            .filter(Employee.id == employee.reporting_manager_id)
            .first()
        )
        user = _active_user_for_employee(db, manager)
        if user:
            return user

        # Legacy rows may store a User id in reporting_manager_id.
        legacy_user = (
            db.query(User)
            .filter(User.id == employee.reporting_manager_id)
            .first()
        )
        if legacy_user and legacy_user.is_active:
            return legacy_user

    return None


def _sales_recipient(db: Session, lead: Lead) -> Optional[Dict[str, Any]]:
    assigned = lead.assigned_employee
    manager_employee: Optional[Employee] = None
    manager_user: Optional[User] = None

    if assigned:
        if normalize_role(assigned.role) == ROLE_SALES_MANAGER:
            manager_employee = assigned
            manager_user = _active_user_for_employee(db, assigned)
        else:
            manager_user = _manager_user_for_employee(db, assigned)
            if manager_user:
                manager_employee = (
                    db.query(Employee)
                    .filter(Employee.user_id == manager_user.id)
                    .first()
                )

    # Preserve attribution when the lead was assigned by a Sales Manager but
    # the current owner no longer has a reporting manager configured.
    if not manager_user and lead.assigned_by_employee:
        assigner = lead.assigned_by_employee
        if normalize_role(assigner.role) == ROLE_SALES_MANAGER:
            manager_employee = assigner
            manager_user = _active_user_for_employee(db, assigner)

    # If the lead was handed off to Support, check the sales representative on the handoff.
    if not manager_user:
        handoff = (
            db.query(SupportHandoff)
            .filter(SupportHandoff.lead_id == lead.id)
            .order_by(SupportHandoff.id.desc())
            .first()
        )
        if handoff and handoff.sales_employee_id:
            sales_emp = (
                db.query(Employee)
                .filter(Employee.id == handoff.sales_employee_id)
                .first()
            )
            if sales_emp:
                if normalize_role(sales_emp.role) == ROLE_SALES_MANAGER:
                    manager_employee = sales_emp
                    manager_user = _active_user_for_employee(db, sales_emp)
                else:
                    manager_user = _manager_user_for_employee(db, sales_emp)
                    if manager_user:
                        manager_employee = (
                            db.query(Employee)
                            .filter(Employee.user_id == manager_user.id)
                            .first()
                        )

    if not manager_user:
        return None

    return {
        "user": manager_user,
        "role": ROLE_SALES,
        "name": (
            (manager_employee.name if manager_employee else None)
            or manager_user.username
        ),
    }


def _support_recipient(db: Session, lead: Lead) -> Optional[Dict[str, Any]]:
    """Resolve the assigned Support contact for the reminder.

    Order: Support handoff agent, legacy ``MANUAL_SUPPORT`` assignment row
    (read-only fallback), then the Support Manager selected in the Set Trial
    Period modal. A Support Manager is never substituted for an *unassigned*
    contact - only an explicitly selected manager is notified - because the
    requirement is to notify whoever actually owns the follow-up.
    """
    handoff = (
        db.query(SupportHandoff)
        .filter(SupportHandoff.lead_id == lead.id)
        .order_by(SupportHandoff.id.desc())
        .first()
    )

    support_employee: Optional[Employee] = None
    if handoff and handoff.assigned_agent_id:
        support_employee = (
            db.query(Employee)
            .filter(Employee.id == handoff.assigned_agent_id)
            .first()
        )

    if not support_employee:
        assignment = (
            db.query(LeadAssignment)
            .filter(
                LeadAssignment.lead_id == lead.id,
                LeadAssignment.assignment_method == "MANUAL_SUPPORT",
            )
            .order_by(LeadAssignment.id.desc())
            .first()
        )
        if assignment and assignment.assigned_to:
            support_employee = (
                db.query(Employee)
                .filter(Employee.id == assignment.assigned_to)
                .first()
            )

    if not support_employee and getattr(lead, "trial_support_employee_id", None):
        # Support Manager selected in the Set Trial Period modal (before any
        # post-conversion handoff exists).
        support_employee = (
            db.query(Employee)
            .filter(Employee.id == lead.trial_support_employee_id)
            .first()
        )

    if not support_employee and lead.assigned_employee:
        assigned = lead.assigned_employee
        dept = (assigned.department or "").strip().upper()
        role = (assigned.role or "").strip().upper()
        if dept == "SUPPORT" or "SUPPORT" in role:
            support_employee = assigned

    if not support_employee:
        return None

    support_user = _active_user_for_employee(db, support_employee)
    if not support_user:
        return None

    return {
        "user": support_user,
        "role": ROLE_SUPPORT,
        "name": support_employee.name or support_user.username,
        # Canonical role of the assigned employee, used to address the Sales
        # message as "Support Manager" or "Support Employee" correctly.
        "employee_role": support_employee.role,
    }


def _lead_display_name(lead: Lead) -> str:
    full_name = (lead.name or "").strip()
    if not full_name:
        full_name = f"{lead.first_name or ''} {lead.last_name or ''}".strip()
    return full_name or f"Lead #{lead.id}"


def _company_display_name(lead: Lead) -> str:
    return (lead.company or "").strip() or _lead_display_name(lead)


def build_trial_reminder_message(
    lead: Lead,
    recipient_role: str,
    trial_end_date: date,
    today: date,
    sales_manager_name: Optional[str],
    support_employee_name: Optional[str],
    support_assignee_label: str = "Assigned Support Employee",
) -> str:
    """Build the role-appropriate Trial reminder body.

    The first paragraph matches the wording requested for the 3-day/1-day and
    expiry-day notices. The structured lines underneath include every required
    field: lead, company, trial start date, trial end date, remaining days and
    the opposite assignee. ``support_assignee_label`` lets the caller address
    the Support side as a Support Manager or a Support Employee based on the
    stored role instead of assuming one. The direct lead link is stored
    separately on ``Notification``.
    """
    lead_name = _lead_display_name(lead)
    company_name = _company_display_name(lead)
    days_remaining = (trial_end_date - today).days
    day_word = "day" if abs(days_remaining) == 1 else "days"

    if recipient_role == ROLE_SALES:
        if days_remaining == 0:
            first_line = (
                f"Today's the last day of the trial for {company_name}. "
                "Please complete the customer follow-up and update the lead status."
            )
        elif days_remaining > 0:
            first_line = (
                f"Trial for {company_name} / {lead_name} is ending in "
                f"{days_remaining} {day_word}. Please contact the customer and "
                "follow up for conversion."
            )
        else:
            first_line = (
                f"The trial for {company_name} / {lead_name} expired on "
                f"{format_ist_date(trial_end_date)} ({abs(days_remaining)} "
                f"{day_word} ago). Please contact the customer and follow up "
                "for conversion."
            )
        opposite_line = (
            f"{support_assignee_label}: {support_employee_name or 'Not assigned'}"
        )
    else:
        if days_remaining == 0:
            first_line = (
                f"Today's the last day of the trial for {company_name}. "
                "Please complete the customer follow-up and update the lead status."
            )
        elif days_remaining > 0:
            first_line = (
                f"The trial period for {company_name} / {lead_name} is ending in "
                f"{days_remaining} {day_word}. Please contact the customer, check "
                "their trial usage and update the feedback for the Sales Team."
            )
        else:
            first_line = (
                f"The trial for {company_name} / {lead_name} expired on "
                f"{format_ist_date(trial_end_date)} ({abs(days_remaining)} "
                f"{day_word} ago). Please contact the customer, check their trial "
                "usage and update the feedback for the Sales Team."
            )
        opposite_line = f"Assigned Sales Manager: {sales_manager_name or 'Not assigned'}"

    if days_remaining >= 0:
        remaining_line = f"Remaining Trial Days: {days_remaining}"
    else:
        remaining_line = (
            f"Trial Expired: {abs(days_remaining)} {day_word} ago"
        )

    details_lines = [
        f"Lead Name: {lead_name}",
        f"Company Name: {company_name}",
    ]
    trial_start_date = getattr(lead, "trial_start_date", None)
    if trial_start_date:
        details_lines.append(
            f"Trial Start Date: {format_ist_date(trial_start_date)}"
        )
    details_lines.extend([
        f"Trial End Date: {format_ist_date(trial_end_date)}",
        remaining_line,
        opposite_line,
    ])
    details = "\n".join(details_lines)
    return f"{first_line}\n\n{details}"


def _recipients_for_lead(db: Session, lead: Lead) -> List[Dict[str, Any]]:
    recipients: List[Dict[str, Any]] = []
    seen_user_ids = set()

    sales = _sales_recipient(db, lead)
    if sales:
        recipients.append(sales)
        seen_user_ids.add(sales["user"].id)

    support = _support_recipient(db, lead)
    if support and support["user"].id not in seen_user_ids:
        recipients.append(support)

    return recipients


def check_and_send_trial_reminders(
    db: Session,
    today: Optional[date] = None,
    now=None,
) -> Dict[str, int]:
    """Send all Trial reminders due on ``today`` (Asia/Kolkata by default).

    Returns a small summary useful for tests and scheduler logging. The function
    commits once per recipient so a unique-constraint conflict for one recipient
    cannot discard deliveries for the others.
    """
    today = today or get_ist_now().date()
    now = now or get_ist_now()

    # Four due dates at most (T-3, T-1, T-0 and expired days 1-3) are in range.
    # Filtering in SQL keeps the scan bounded; status normalisation stays in
    # Python so legacy spellings such as "TRIAL LEAD" are handled identically.
    candidates = (
        db.query(Lead)
        .filter(
            Lead.trial_end_date.isnot(None),
            Lead.trial_end_date >= today - timedelta(days=3),
            Lead.trial_end_date <= today + timedelta(days=3),
        )
        .all()
    )

    leads_checked = 0
    notifications_created = 0
    duplicates_skipped = 0
    missing_recipient = 0
    errors = 0

    for lead in candidates:
        if not is_trial_status(lead.status):
            continue
        leads_checked += 1

        trial_end_date = lead.trial_end_date
        milestone = trial_milestone_for(trial_end_date, today)
        if not milestone:
            continue

        recipients = _recipients_for_lead(db, lead)
        if not recipients:
            missing_recipient += 1
            continue

        sales_name = next(
            (r["name"] for r in recipients if r["role"] == ROLE_SALES),
            None,
        )
        support_name = next(
            (r["name"] for r in recipients if r["role"] == ROLE_SUPPORT),
            None,
        )
        support_role = next(
            (
                r.get("employee_role")
                for r in recipients
                if r["role"] == ROLE_SUPPORT
            ),
            None,
        )
        # Address the Support side by its real role: the Set Trial Period
        # modal stores a Support Manager, older rows may store an Executive.
        support_assignee_label = (
            "Assigned Support Manager"
            if normalize_role(support_role) == ROLE_SUPPORT_MANAGER
            else "Assigned Support Employee"
        )

        for recipient in recipients:
            user = recipient["user"]
            role = recipient["role"]

            existing = (
                db.query(TrialReminderDelivery)
                .filter(
                    TrialReminderDelivery.lead_id == lead.id,
                    TrialReminderDelivery.user_id == user.id,
                    TrialReminderDelivery.milestone == milestone,
                    TrialReminderDelivery.trial_end_date == trial_end_date,
                )
                .first()
            )
            if existing:
                duplicates_skipped += 1
                continue

            message = build_trial_reminder_message(
                lead=lead,
                recipient_role=role,
                trial_end_date=trial_end_date,
                today=today,
                sales_manager_name=sales_name,
                support_employee_name=support_name,
                support_assignee_label=support_assignee_label,
            )
            title = SALES_TITLE if role == ROLE_SALES else SUPPORT_TITLE
            link_url = (
                f"/leads?openLeadId={lead.id}"
                if role == ROLE_SALES
                else f"/support/assigned-leads?openLeadId={lead.id}"
            )

            delivery = TrialReminderDelivery(
                lead_id=lead.id,
                user_id=user.id,
                recipient_role=role,
                milestone=milestone,
                trial_end_date=trial_end_date,
                created_at=now,
            )
            notification = Notification(
                user_id=user.id,
                title=title,
                message=message,
                notification_type=NOTIFICATION_TYPE,
                link_url=link_url,
                is_read=False,
                created_at=now,
            )

            try:
                db.add(delivery)
                db.add(notification)
                db.flush()
                delivery.notification_id = notification.id
                db.commit()
                notifications_created += 1
            except IntegrityError:
                # Another worker inserted the same delivery key first.
                db.rollback()
                duplicates_skipped += 1
            except Exception as exc:  # pragma: no cover - defensive logging
                db.rollback()
                errors += 1
                logger.error(
                    "Trial reminder failed for lead=%s user=%s milestone=%s: %s",
                    lead.id, user.id, milestone, exc,
                )

    if notifications_created or duplicates_skipped or errors:
        logger.info(
            "Trial reminders: checked=%s created=%s duplicates=%s missing_recipient=%s errors=%s",
            leads_checked, notifications_created, duplicates_skipped,
            missing_recipient, errors,
        )

    return {
        "leads_checked": leads_checked,
        "notifications_created": notifications_created,
        "duplicates_skipped": duplicates_skipped,
        "missing_recipient": missing_recipient,
        "errors": errors,
    }


async def start_trial_reminder_scheduler(interval_seconds: int = 900):
    """Poll the database independently of user activity.

    The check is idempotent, so frequent polling cannot duplicate a reminder.
    The delivery uniqueness key additionally protects against multiple app
    workers. IST is used for every date calculation.
    """
    logger.info("Trial Expiry Reminder background scheduler started.")
    while True:
        try:
            db = SessionLocal()
            try:
                check_and_send_trial_reminders(db)
            finally:
                db.close()
        except Exception as exc:
            logger.error("Error in trial reminder scheduler loop: %s", exc)
        await asyncio.sleep(interval_seconds)


if __name__ == "__main__":
    import os
    import sys

    backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)

    print(f"[{get_ist_now().isoformat()}] Running Trial Expiry Reminders daily sweep (Asia/Kolkata)...")
    db_session = SessionLocal()
    try:
        summary = check_and_send_trial_reminders(db_session)
        print("Trial Expiry Reminders execution result:", summary)
    finally:
        db_session.close()
