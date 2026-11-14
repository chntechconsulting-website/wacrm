"""Trial expiry reminder coverage.

Isolated in-memory SQLite only. No live CRM record is read or written.

Scenarios:
1.  T-3 notifies the assigned Sales Manager and the assigned Support employee.
2.  T-1, expiry day, and the three days after expiry are scheduled.
3.  Expiry-day wording matches the required customer follow-up sentence.
4.  Non-milestone days (T-2, 4+ days after expiry) send nothing.
5.  Re-running the scheduler never duplicates a delivery.
6.  Leaving TRIAL stops all later reminders immediately.
7.  Only the assigned recipients are notified (role scoping).
8.  Inactive recipients are skipped safely.
9.  A new trial cycle (new end date) can notify again.
10. The unread-count endpoint counts the current user's trial reminders.
"""

import os
import sys
import unittest
from datetime import date, timedelta

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401 - registers every model on Base.metadata
from database import Base
from models.customer import Customer
from models.employee import Employee
from models.lead import Lead, LeadAssignment
from models.notification import Notification
from models.trial_reminder import TrialReminderDelivery
from models.user import User
from models.workflow import SupportHandoff
from routers.notifications import (
    get_unread_notification_count,
    trigger_trial_reminders_run,
)
from routers.reports import build_support_dashboard_payload
from services.trial_reminder_service import (
    MILESTONE_EXPIRY_DAY,
    MILESTONE_EXPIRED_1,
    MILESTONE_EXPIRED_2,
    MILESTONE_EXPIRED_3,
    MILESTONE_T1,
    MILESTONE_T3,
    NOTIFICATION_TYPE,
    SALES_TITLE,
    SUPPORT_TITLE,
    build_trial_reminder_message,
    check_and_send_trial_reminders,
    trial_milestone_for,
)


class TrialReminderTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db = Session()
        self._phone_counter = 9700000000

        self.admin_user, self.admin_emp = self._make_person(
            "trial_admin", "ADMIN", "ADMINISTRATION"
        )
        self.sales_manager_user, self.sales_manager_emp = self._make_person(
            "trial_sales_mgr", "SALES_MANAGER", "SALES"
        )
        self.sales_exec_user, self.sales_exec_emp = self._make_person(
            "trial_sales_exec",
            "SALES_EXECUTIVE",
            "SALES",
            manager_emp=self.sales_manager_emp,
        )
        self.other_sales_manager_user, self.other_sales_manager_emp = self._make_person(
            "trial_other_sales_mgr", "SALES_MANAGER", "SALES"
        )
        self.other_sales_exec_user, self.other_sales_exec_emp = self._make_person(
            "trial_other_sales_exec",
            "SALES_EXECUTIVE",
            "SALES",
            manager_emp=self.other_sales_manager_emp,
        )
        self.support_manager_user, self.support_manager_emp = self._make_person(
            "trial_support_mgr", "SUPPORT_MANAGER", "SUPPORT"
        )
        self.support_exec_user, self.support_exec_emp = self._make_person(
            "trial_support_exec",
            "SUPPORT_EXECUTIVE",
            "SUPPORT",
            manager_emp=self.support_manager_emp,
        )
        self.other_support_exec_user, self.other_support_exec_emp = self._make_person(
            "trial_other_support_exec",
            "SUPPORT_EXECUTIVE",
            "SUPPORT",
            manager_emp=self.support_manager_emp,
        )

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    # ------------------------------------------------------------------
    # Fixtures
    # ------------------------------------------------------------------
    def _make_person(self, username, role, department, status="ACTIVE", manager_emp=None):
        user = User(
            username=username,
            hashed_password="not-used-in-tests",
            role=role,
            department=department,
            is_active=status == "ACTIVE",
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        employee = Employee(
            user_id=user.id,
            manager_id=manager_emp.id if manager_emp else None,
            department=department,
            name=username.replace("_", " ").title(),
            email=f"{username}@example.test",
            phone="9800000000",
            username=username,
            role=role,
            status=status,
        )
        self.db.add(employee)
        self.db.commit()
        self.db.refresh(employee)
        return user, employee

    def _make_trial_lead(self, trial_end_date, status="TRIAL", assigned_to=None):
        self._phone_counter += 1
        lead = Lead(
            name=f"Trial Customer {self._phone_counter}",
            phone=str(self._phone_counter),
            email=f"trial{self._phone_counter}@example.com",
            company=f"Trial Company {self._phone_counter}",
            source="MANUAL",
            status=status,
            assigned_to=assigned_to if assigned_to is not None else self.sales_exec_emp.id,
            trial_start_date=trial_end_date - timedelta(days=14),
            trial_end_date=trial_end_date,
        )
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        return lead

    def _assign_support(self, lead, agent_emp=None):
        agent_emp = agent_emp or self.support_exec_emp
        customer = Customer(
            company_name=lead.company or "Trial Company",
            contact_name=lead.name,
            phone=lead.phone,
        )
        self.db.add(customer)
        self.db.commit()
        self.db.refresh(customer)

        handoff = SupportHandoff(
            lead_id=lead.id,
            customer_id=customer.id,
            customer_name=lead.name,
            company_name=lead.company,
            phone=lead.phone,
            sales_employee_id=self.sales_exec_emp.id,
            sales_employee_name=self.sales_exec_emp.name,
            assigned_agent_id=agent_emp.id,
            assigned_agent_name=agent_emp.name,
        )
        self.db.add(handoff)
        self.db.commit()
        self.db.refresh(handoff)
        return handoff

    def _notifications_for(self, user):
        return (
            self.db.query(Notification)
            .filter(
                Notification.user_id == user.id,
                Notification.notification_type == NOTIFICATION_TYPE,
            )
            .order_by(Notification.id.asc())
            .all()
        )

    # ------------------------------------------------------------------
    # 1. Milestone calculation
    # ------------------------------------------------------------------
    def test_01_milestones_are_exact(self):
        end = date(2026, 11, 20)
        expected = {
            3: MILESTONE_T3,
            2: None,
            1: MILESTONE_T1,
            0: MILESTONE_EXPIRY_DAY,
            -1: MILESTONE_EXPIRED_1,
            -2: MILESTONE_EXPIRED_2,
            -3: MILESTONE_EXPIRED_3,
            -4: None,
        }
        for offset, milestone in expected.items():
            today = end - timedelta(days=offset)
            self.assertEqual(
                trial_milestone_for(end, today),
                milestone,
                f"offset {offset}",
            )

    # ------------------------------------------------------------------
    # 2. T-3 reaches both role-appropriate recipients
    # ------------------------------------------------------------------
    def test_02_t3_notifies_sales_manager_and_support_employee(self):
        today = date(2026, 11, 13)
        end = today + timedelta(days=3)
        lead = self._make_trial_lead(end)
        self._assign_support(lead)

        result = check_and_send_trial_reminders(self.db, today=today)
        self.assertEqual(result["notifications_created"], 2)
        self.assertEqual(result["errors"], 0)

        sales_notifications = self._notifications_for(self.sales_manager_user)
        support_notifications = self._notifications_for(self.support_exec_user)
        self.assertEqual(len(sales_notifications), 1)
        self.assertEqual(len(support_notifications), 1)

        sales_note = sales_notifications[0]
        self.assertEqual(sales_note.title, SALES_TITLE)
        self.assertEqual(sales_note.link_url, f"/leads?openLeadId={lead.id}")
        self.assertFalse(sales_note.is_read)
        self.assertIn(lead.name, sales_note.message)
        self.assertIn(lead.company, sales_note.message)
        self.assertIn("16 Nov 2026", sales_note.message)
        self.assertIn("Remaining Trial Days: 3", sales_note.message)
        self.assertIn("Assigned Support Employee:", sales_note.message)
        self.assertIn(self.support_exec_emp.name, sales_note.message)

        support_note = support_notifications[0]
        self.assertEqual(support_note.title, SUPPORT_TITLE)
        self.assertEqual(
            support_note.link_url,
            f"/support/assigned-leads?openLeadId={lead.id}",
        )
        self.assertIn("Assigned Sales Manager:", support_note.message)
        self.assertIn(self.sales_manager_emp.name, support_note.message)

        # No other user receives the reminder.
        self.assertEqual(self._notifications_for(self.other_sales_manager_user), [])
        self.assertEqual(self._notifications_for(self.other_sales_exec_user), [])
        self.assertEqual(self._notifications_for(self.other_support_exec_user), [])
        self.assertEqual(self._notifications_for(self.admin_user), [])

    # ------------------------------------------------------------------
    # 3. T-1
    # ------------------------------------------------------------------
    def test_03_t1_notifies_both_recipients(self):
        today = date(2026, 11, 13)
        end = today + timedelta(days=1)
        lead = self._make_trial_lead(end)
        self._assign_support(lead)

        result = check_and_send_trial_reminders(self.db, today=today)
        self.assertEqual(result["notifications_created"], 2)

        for user in (self.sales_manager_user, self.support_exec_user):
            notes = self._notifications_for(user)
            self.assertEqual(len(notes), 1)
            self.assertIn("Remaining Trial Days: 1", notes[0].message)
            self.assertIn("14 Nov 2026", notes[0].message)

    # ------------------------------------------------------------------
    # 4. Expiry day exact wording
    # ------------------------------------------------------------------
    def test_04_expiry_day_uses_required_sentence(self):
        today = date(2026, 11, 13)
        lead = self._make_trial_lead(today)
        self._assign_support(lead)

        result = check_and_send_trial_reminders(self.db, today=today)
        self.assertEqual(result["notifications_created"], 2)

        expected_sentence = (
            f"Today's the last day of the trial for {lead.company}. "
            "Please complete the customer follow-up and update the lead status."
        )
        for user in (self.sales_manager_user, self.support_exec_user):
            notes = self._notifications_for(user)
            self.assertEqual(len(notes), 1)
            self.assertTrue(notes[0].message.startswith(expected_sentence))
            self.assertIn("Remaining Trial Days: 0", notes[0].message)

    # ------------------------------------------------------------------
    # 5. Days 1-3 after expiry
    # ------------------------------------------------------------------
    def test_05_first_three_days_after_expiry(self):
        today = date(2026, 11, 13)
        leads = {}
        for offset in (1, 2, 3):
            lead = self._make_trial_lead(today - timedelta(days=offset))
            self._assign_support(lead)
            leads[offset] = lead

        result = check_and_send_trial_reminders(self.db, today=today)
        self.assertEqual(result["notifications_created"], 6)

        notes = self._notifications_for(self.sales_manager_user)
        self.assertEqual(len(notes), 3)
        by_lead = {}
        for note in notes:
            for offset, lead in leads.items():
                if lead.name in note.message:
                    by_lead[offset] = note
        self.assertEqual(set(by_lead), {1, 2, 3})
        for offset in (1, 2, 3):
            self.assertIn(
                f"Trial Expired: {offset} {'day' if offset == 1 else 'days'} ago",
                by_lead[offset].message,
            )

    # ------------------------------------------------------------------
    # 6. Non-milestone days are silent
    # ------------------------------------------------------------------
    def test_06_non_milestone_days_do_not_notify(self):
        end = date(2026, 11, 15)
        lead = self._make_trial_lead(end)
        self._assign_support(lead)

        for today in (
            end - timedelta(days=2),
            end - timedelta(days=4),
            end + timedelta(days=4),
            end + timedelta(days=10),
        ):
            result = check_and_send_trial_reminders(self.db, today=today)
            self.assertEqual(result["notifications_created"], 0)

        self.assertEqual(self._notifications_for(self.sales_manager_user), [])
        self.assertEqual(self._notifications_for(self.support_exec_user), [])

    # ------------------------------------------------------------------
    # 7. Idempotency
    # ------------------------------------------------------------------
    def test_07_repeated_runs_do_not_duplicate(self):
        today = date(2026, 11, 13)
        lead = self._make_trial_lead(today + timedelta(days=3))
        self._assign_support(lead)

        first = check_and_send_trial_reminders(self.db, today=today)
        second = check_and_send_trial_reminders(self.db, today=today)
        third = check_and_send_trial_reminders(self.db, today=today)

        self.assertEqual(first["notifications_created"], 2)
        self.assertEqual(second["notifications_created"], 0)
        self.assertEqual(third["notifications_created"], 0)
        self.assertEqual(second["duplicates_skipped"], 2)

        self.assertEqual(len(self._notifications_for(self.sales_manager_user)), 1)
        self.assertEqual(len(self._notifications_for(self.support_exec_user)), 1)
        self.assertEqual(self.db.query(TrialReminderDelivery).count(), 2)

    # ------------------------------------------------------------------
    # 8. Leaving TRIAL stops reminders
    # ------------------------------------------------------------------
    def test_08_status_change_stops_later_reminders(self):
        end = date(2026, 11, 16)
        lead = self._make_trial_lead(end)
        self._assign_support(lead)

        t3 = check_and_send_trial_reminders(self.db, today=end - timedelta(days=3))
        self.assertEqual(t3["notifications_created"], 2)

        lead.status = "WON"
        self.db.commit()

        for today in (end - timedelta(days=1), end, end + timedelta(days=1)):
            result = check_and_send_trial_reminders(self.db, today=today)
            self.assertEqual(result["notifications_created"], 0)

        self.assertEqual(len(self._notifications_for(self.sales_manager_user)), 1)
        self.assertEqual(len(self._notifications_for(self.support_exec_user)), 1)

    # ------------------------------------------------------------------
    # 9. Recipient fallbacks and inactive accounts
    # ------------------------------------------------------------------
    def test_09_inactive_support_user_is_skipped(self):
        today = date(2026, 11, 13)
        lead = self._make_trial_lead(today + timedelta(days=3))
        self._assign_support(lead)

        self.support_exec_user.is_active = False
        self.db.commit()

        result = check_and_send_trial_reminders(self.db, today=today)
        self.assertEqual(result["notifications_created"], 1)
        self.assertEqual(result["missing_recipient"], 0)
        self.assertEqual(len(self._notifications_for(self.sales_manager_user)), 1)
        self.assertEqual(self._notifications_for(self.support_exec_user), [])

    def test_10_legacy_manual_support_assignment_is_used(self):
        today = date(2026, 11, 13)
        lead = self._make_trial_lead(today + timedelta(days=3))
        # No handoff: simulate the legacy MANUAL_SUPPORT assignment shape.
        self.db.add(
            LeadAssignment(
                lead_id=lead.id,
                assigned_to=self.support_exec_emp.id,
                assigned_by=self.support_manager_emp.id,
                assignment_method="MANUAL_SUPPORT",
            )
        )
        self.db.commit()

        result = check_and_send_trial_reminders(self.db, today=today)
        self.assertEqual(result["notifications_created"], 2)
        self.assertEqual(len(self._notifications_for(self.support_exec_user)), 1)

    # ------------------------------------------------------------------
    # 10. New trial cycle
    # ------------------------------------------------------------------
    def test_11_new_trial_cycle_notifies_again(self):
        end = date(2026, 11, 16)
        lead = self._make_trial_lead(end)
        self._assign_support(lead)

        first = check_and_send_trial_reminders(self.db, today=end - timedelta(days=3))
        self.assertEqual(first["notifications_created"], 2)

        # A new trial cycle has a genuinely different end date.
        new_end = date(2026, 12, 15)
        lead.trial_end_date = new_end
        self.db.commit()

        second = check_and_send_trial_reminders(self.db, today=new_end - timedelta(days=3))
        self.assertEqual(second["notifications_created"], 2)
        self.assertEqual(len(self._notifications_for(self.sales_manager_user)), 2)
        self.assertEqual(len(self._notifications_for(self.support_exec_user)), 2)

    # ------------------------------------------------------------------
    # 11. Message includes the opposite assignee for both roles
    # ------------------------------------------------------------------
    def test_12_message_contains_both_opposite_assignees(self):
        end = date(2026, 11, 20)
        lead = self._make_trial_lead(end)
        self._assign_support(lead)

        sales_msg = build_trial_reminder_message(
            lead=lead,
            recipient_role="SALES_MANAGER",
            trial_end_date=end,
            today=date(2026, 11, 17),
            sales_manager_name=self.sales_manager_emp.name,
            support_employee_name=self.support_exec_emp.name,
        )
        support_msg = build_trial_reminder_message(
            lead=lead,
            recipient_role="SUPPORT_EMPLOYEE",
            trial_end_date=end,
            today=date(2026, 11, 17),
            sales_manager_name=self.sales_manager_emp.name,
            support_employee_name=self.support_exec_emp.name,
        )

        self.assertIn(f"Lead Name: {lead.name}", sales_msg)
        self.assertIn(f"Company Name: {lead.company}", sales_msg)
        self.assertIn("Trial End Date: 20 Nov 2026", sales_msg)
        self.assertIn(f"Assigned Support Employee: {self.support_exec_emp.name}", sales_msg)
        self.assertIn(f"Assigned Sales Manager: {self.sales_manager_emp.name}", support_msg)

    # ------------------------------------------------------------------
    # 12. Unread count used by the notification bell
    # ------------------------------------------------------------------
    def test_13_unread_count_scopes_to_current_user(self):
        today = date(2026, 11, 13)
        lead = self._make_trial_lead(today + timedelta(days=3))
        self._assign_support(lead)
        check_and_send_trial_reminders(self.db, today=today)

        sales_payload = get_unread_notification_count(self.db, self.sales_manager_user)
        support_payload = get_unread_notification_count(self.db, self.support_exec_user)
        other_payload = get_unread_notification_count(self.db, self.other_sales_exec_user)

        self.assertEqual(sales_payload["unread_count"], 1)
        self.assertEqual(support_payload["unread_count"], 1)
        self.assertEqual(other_payload["unread_count"], 0)

        note = self._notifications_for(self.sales_manager_user)[0]
        note.is_read = True
        self.db.commit()
        self.assertEqual(
            get_unread_notification_count(self.db, self.sales_manager_user)["unread_count"],
            0,
        )

    # ------------------------------------------------------------------
    # 13. Direct assigned employee fallback in Support department
    # ------------------------------------------------------------------
    def test_14_direct_assigned_employee_in_support_is_used(self):
        today = date(2026, 11, 13)
        lead = self._make_trial_lead(
            today + timedelta(days=3),
            assigned_to=self.support_exec_emp.id,
        )
        result = check_and_send_trial_reminders(self.db, today=today)
        notes = self._notifications_for(self.support_exec_user)
        self.assertEqual(len(notes), 1)
        self.assertIn(lead.name, notes[0].message)

    # ------------------------------------------------------------------
    # 14. POST /notifications/trial-reminders/run endpoint
    # ------------------------------------------------------------------
    def test_15_trigger_endpoint_runs_and_is_idempotent(self):
        from utils.timezone import get_ist_now
        today = get_ist_now().date()
        lead = self._make_trial_lead(today + timedelta(days=3))
        self._assign_support(lead)

        res1 = trigger_trial_reminders_run(db=self.db, current_user=self.admin_user)
        self.assertEqual(res1["message"], "Trial reminders processed successfully")
        self.assertGreaterEqual(res1["result"]["notifications_created"], 2)

        # Run again - must be idempotent (0 created, duplicates skipped)
        res2 = trigger_trial_reminders_run(db=self.db, current_user=self.admin_user)
        self.assertEqual(res2["result"]["notifications_created"], 0)
        self.assertGreaterEqual(res2["result"]["duplicates_skipped"], 2)

    # ------------------------------------------------------------------
    # 15. Support Dashboard recent tickets expired flag
    # ------------------------------------------------------------------
    def test_16_support_dashboard_payload_includes_expired_flag(self):
        from utils.timezone import get_ist_now
        today = get_ist_now().date()
        expired_lead = self._make_trial_lead(today - timedelta(days=1))
        self._assign_support(expired_lead)

        payload = build_support_dashboard_payload(
            user=self.support_exec_user,
            employee=self.support_exec_emp,
            db=self.db,
        )
        recent = payload.get("recent_tickets", [])
        self.assertTrue(len(recent) > 0)
        ticket = next((t for t in recent if t["lead_id"] == expired_lead.id), None)
        self.assertIsNotNone(ticket)
        self.assertTrue(ticket["is_trial_expired"])
        self.assertEqual(ticket["trial_days_remaining"], -1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
