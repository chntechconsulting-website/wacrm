"""Provision the least-privilege Meta App Review account.

This script is intended to be run on the production host from the ``backend``
directory after the reviewer-access code has been deployed:

    ./venv/bin/python migrations/provision_meta_reviewer.py \\
        --username meta.reviewer \\
        --email approot@example.com \\
        --password 'use-a-strong-unique-password' \\
        --name "Meta App Reviewer" \\
        --seed-conversation \\
        --test-phone 9198XXXXXXXX \\
        --test-name "Review test contact"

It creates (or repairs) a dedicated ``META_REVIEWER`` user + linked Employee,
reports it to the active Admin, and optionally seeds an assigned test lead and
WhatsApp conversation. It never sends a WhatsApp message and never touches the
live WhatsApp Business App number 7547900900.

The password is only read from the command line or ``--password-stdin``. It is
never written to the repository, printed, or stored outside the normal bcrypt
hash in the users table.
"""

import argparse
import getpass
import os
import re
import sys
from datetime import datetime
from typing import Optional, Tuple

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import SessionLocal  # noqa: E402
from models.employee import Employee  # noqa: E402
from models.lead import Lead  # noqa: E402
from models.user import User  # noqa: E402
from models.whatsapp import Conversation, WhatsAppMessage  # noqa: E402
from services.auth import hash_password  # noqa: E402
from services.permission_service import seed_default_roles_if_needed  # noqa: E402

REVIEWER_ROLE = "META_REVIEWER"
ADMIN_DEPARTMENT = "ADMINISTRATION"
PROTECTED_NUMBER = "7547900900"
TEST_LEAD_NOTE = "Meta App Review test lead. Not a real customer."
TEST_MESSAGE_BODY = (
    "Hello, I am testing the WhatsApp inbox for Meta App Review. "
    "This is a test conversation."
)


class ProvisioningError(RuntimeError):
    pass


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _assert_not_protected(phone: str, label: str) -> str:
    digits = _digits(phone)
    if not digits:
        raise ProvisioningError(f"{label} is required and must contain digits.")
    if digits.endswith(PROTECTED_NUMBER):
        raise ProvisioningError(
            f"{label} must not be the live WhatsApp Business App number "
            f"{PROTECTED_NUMBER}. Use a separate review test phone."
        )
    return digits


def _find_active_admin(db) -> Tuple[User, Optional[Employee]]:
    admin = (
        db.query(User)
        .filter(User.role == "ADMIN", User.is_active.is_(True))
        .order_by(User.id.asc())
        .first()
    )
    if not admin:
        raise ProvisioningError(
            "No active ADMIN user exists. Sign in as an administrator once "
            "before provisioning the reviewer account."
        )
    admin_emp = db.query(Employee).filter(Employee.user_id == admin.id).first()
    return admin, admin_emp


def provision_reviewer(
    db,
    username: str,
    email: str,
    password: str,
    name: str,
    phone: Optional[str] = None,
) -> Tuple[User, Employee]:
    """Create or repair the reviewer User + Employee. Idempotent."""
    username = (username or "").strip().lower()
    email = (email or "").strip().lower()
    name = (name or "").strip()

    if not username:
        raise ProvisioningError("--username is required.")
    if not email or "@" not in email:
        raise ProvisioningError("A valid --email is required.")
    if not name:
        raise ProvisioningError("--name is required.")
    if not password or len(password) < 10:
        raise ProvisioningError("Password must be at least 10 characters.")
    if phone:
        _assert_not_protected(phone, "--phone")

    seed_default_roles_if_needed(db)
    admin, admin_emp = _find_active_admin(db)

    existing_user = db.query(User).filter(User.username == username).first()
    email_owner = db.query(Employee).filter(Employee.email == email).first()

    if existing_user and (existing_user.role or "").upper() != REVIEWER_ROLE:
        raise ProvisioningError(
            f"Username '{username}' already belongs to role "
            f"'{existing_user.role}'. Use a dedicated new username for the "
            "reviewer; this script refuses to convert an existing account."
        )
    if email_owner and existing_user and email_owner.user_id != existing_user.id:
        raise ProvisioningError(
            f"Email '{email}' is already linked to another employee."
        )

    if existing_user:
        user = existing_user
        user.hashed_password = hash_password(password)
        user.role = REVIEWER_ROLE
        user.department = ADMIN_DEPARTMENT
        user.reporting_manager_id = admin.id
        user.is_active = True
    else:
        user = User(
            username=username,
            hashed_password=hash_password(password),
            role=REVIEWER_ROLE,
            department=ADMIN_DEPARTMENT,
            reporting_manager_id=admin.id,
            is_active=True,
        )
        db.add(user)
    db.commit()
    db.refresh(user)

    employee = (
        db.query(Employee)
        .filter((Employee.user_id == user.id) | (Employee.username == username))
        .first()
    )
    manager_employee_id = admin_emp.id if admin_emp else None

    if employee:
        employee.user_id = user.id
        employee.name = name
        employee.email = email
        employee.phone = phone or employee.phone
        employee.username = username
        employee.role = REVIEWER_ROLE
        employee.department = ADMIN_DEPARTMENT
        employee.manager_id = manager_employee_id
        employee.reporting_manager_id = admin.id
        employee.status = "ACTIVE"
    else:
        employee = Employee(
            user_id=user.id,
            manager_id=manager_employee_id,
            reporting_manager_id=admin.id,
            department=ADMIN_DEPARTMENT,
            name=name,
            email=email,
            phone=phone,
            username=username,
            role=REVIEWER_ROLE,
            status="ACTIVE",
        )
        db.add(employee)

    db.commit()
    db.refresh(employee)
    return user, employee


def seed_review_conversation(
    db,
    reviewer: Employee,
    test_phone: str,
    test_name: str,
    force: bool = False,
) -> Conversation:
    """Create or repair one assigned test lead + conversation.

    Existing real leads are never hijacked. The only reusable lead is one that
    is unassigned or already assigned to the reviewer.
    """
    digits = _assert_not_protected(test_phone, "--test-phone")
    test_name = (test_name or "Meta Review Test").strip() or "Meta Review Test"
    suffix = digits[-10:]
    admin, admin_emp = _find_active_admin(db)

    lead = (
        db.query(Lead)
        .filter(Lead.phone.like(f"%{suffix}"))
        .order_by(Lead.id.asc())
        .first()
    )
    if lead:
        if (lead.source or "").upper() == "WHATSAPP_ADS":
            raise ProvisioningError(
                "The test phone matches a real WhatsApp Ads lead. Choose a "
                "separate review test phone so attribution data is not touched."
            )
        is_marked_test = (lead.requirement_notes or "") == TEST_LEAD_NOTE
        if not is_marked_test and lead.assigned_to != reviewer.id and not force:
            raise ProvisioningError(
                f"Lead {lead.id} for this phone is not marked as a review test. "
                "Choose a different test phone, or re-run with --force only "
                "after confirming it is safe to reuse."
            )
        if lead.assigned_to not in (None, reviewer.id) and not force:
            raise ProvisioningError(
                f"Lead {lead.id} for this phone is assigned to employee "
                f"{lead.assigned_to}. Re-run with --force only after confirming "
                "it is a test lead."
            )
        lead.name = test_name
        lead.first_name = test_name.split(" ")[0]
        lead.last_name = " ".join(test_name.split(" ")[1:]) or None
        lead.phone = digits
        lead.whatsapp_number = digits
        lead.assigned_to = reviewer.id
        lead.assigned_by = admin_emp.id if admin_emp else lead.assigned_by
        lead.assigned_at = lead.assigned_at or datetime.utcnow()
        lead.status = "ASSIGNED"
        if not lead.requirement_notes:
            lead.requirement_notes = TEST_LEAD_NOTE
    else:
        lead = Lead(
            name=test_name,
            first_name=test_name.split(" ")[0],
            last_name=" ".join(test_name.split(" ")[1:]) or None,
            phone=digits,
            whatsapp_number=digits,
            source="Manual",
            status="ASSIGNED",
            rating="Warm",
            priority="MEDIUM",
            product_category="UNCLASSIFIED",
            requirement_notes=TEST_LEAD_NOTE,
            assigned_to=reviewer.id,
            assigned_by=admin_emp.id if admin_emp else None,
            assigned_at=datetime.utcnow(),
        )
        db.add(lead)
    db.commit()
    db.refresh(lead)

    conversation = (
        db.query(Conversation)
        .filter(Conversation.phone.like(f"%{suffix}"))
        .order_by(Conversation.id.asc())
        .first()
    )
    if conversation:
        if conversation.lead_id not in (None, lead.id):
            raise ProvisioningError(
                f"Conversation {conversation.id} is linked to a different lead "
                f"({conversation.lead_id}). Choose a different test phone."
            )
        real_messages = (
            db.query(WhatsAppMessage)
            .filter(
                WhatsAppMessage.conversation_id == conversation.id,
                ~WhatsAppMessage.provider_message_id.like("review-seed-%"),
            )
            .count()
        )
        if real_messages and not force:
            raise ProvisioningError(
                f"Conversation {conversation.id} already contains "
                f"{real_messages} message(s). Choose a different test phone, or "
                "re-run with --force only after confirming it is a test thread."
            )
        if conversation.assigned_to not in (None, reviewer.id) and not force:
            raise ProvisioningError(
                f"Conversation {conversation.id} for this phone is assigned to "
                f"employee {conversation.assigned_to}. Re-run with --force only "
                "after confirming it is a test conversation."
            )
        conversation.lead_id = conversation.lead_id or lead.id
        conversation.contact_name = test_name
        conversation.assigned_to = reviewer.id
    else:
        conversation = Conversation(
            lead_id=lead.id,
            phone=digits,
            contact_name=test_name,
            assigned_to=reviewer.id,
            unread_count=1,
            last_message_text=TEST_MESSAGE_BODY,
            last_message_at=datetime.utcnow(),
        )
        db.add(conversation)
    db.commit()
    db.refresh(conversation)

    provider_id = f"review-seed-{conversation.id}"
    message = (
        db.query(WhatsAppMessage)
        .filter(WhatsAppMessage.provider_message_id == provider_id)
        .first()
    )
    if not message:
        message = WhatsAppMessage(
            conversation_id=conversation.id,
            lead_id=lead.id,
            direction="INBOUND",
            message_type="TEXT",
            body=TEST_MESSAGE_BODY,
            provider_message_id=provider_id,
            status="DELIVERED",
            sent_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
        db.add(message)

    conversation.unread_count = max(conversation.unread_count or 0, 1)
    conversation.last_message_text = TEST_MESSAGE_BODY
    conversation.last_message_at = datetime.utcnow()
    db.commit()
    db.refresh(conversation)
    return conversation


def _read_password(args) -> str:
    if args.password_stdin:
        password = sys.stdin.readline().strip()
    elif args.password:
        password = args.password
    else:
        password = getpass.getpass("Reviewer password: ")
        confirmation = getpass.getpass("Confirm reviewer password: ")
        if password != confirmation:
            raise ProvisioningError("Passwords do not match.")
    return password


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Provision the least-privilege META_REVIEWER account."
    )
    parser.add_argument("--username", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", default=None)
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read the password from the first line of stdin instead of argv.",
    )
    parser.add_argument("--name", required=True)
    parser.add_argument("--phone", default=None, help="Optional reviewer phone.")
    parser.add_argument(
        "--seed-conversation",
        action="store_true",
        help="Seed one assigned test lead and WhatsApp conversation.",
    )
    parser.add_argument("--test-phone", default=None)
    parser.add_argument("--test-name", default="Meta Review Test")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow reusing a test lead/conversation already assigned to "
        "another employee. Never used for real WhatsApp Ads leads.",
    )
    return parser


def run(args) -> int:
    if args.seed_conversation and not args.test_phone:
        raise ProvisioningError("--test-phone is required with --seed-conversation.")

    password = _read_password(args)
    db = SessionLocal()
    try:
        user, employee = provision_reviewer(
            db,
            username=args.username,
            email=args.email,
            password=password,
            name=args.name,
            phone=args.phone,
        )
        print("Reviewer account ready.")
        print(f"  user_id:     {user.id}")
        print(f"  username:    {user.username}")
        print(f"  role:        {user.role}")
        print(f"  department:  {user.department}")
        print(f"  employee_id: {employee.id}")

        if args.seed_conversation:
            conversation = seed_review_conversation(
                db,
                reviewer=employee,
                test_phone=args.test_phone,
                test_name=args.test_name,
                force=args.force,
            )
            print("Test conversation ready.")
            print(f"  conversation_id: {conversation.id}")
            print(f"  lead_id:         {conversation.lead_id}")
            print(f"  assigned_to:     {conversation.assigned_to}")

        print(
            "\nNo WhatsApp message was sent. Sign in as the reviewer and confirm "
            "only Communication > WhatsApp and Settings > WhatsApp Connection "
            "are visible."
        )
        return 0
    finally:
        db.close()


def main() -> int:
    parser = _build_parser()
    try:
        return run(parser.parse_args())
    except ProvisioningError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
