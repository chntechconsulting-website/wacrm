"""Customer POC (Point of Contact) management and call-mapping tests.

Isolated in-memory SQLite only. No live CRM record is read or written.

Scenarios covered:
A.  One Support customer can have multiple POCs; the first is primary.
B.  Primary POC can be changed and exactly one primary remains.
C.  Editing one POC never changes another POC or the customer main contact.
D.  Duplicate POC mobile/WhatsApp/email is rejected within the customer.
E.  Sales users cannot read or create POCs.
F.  An unrelated Support Executive is blocked; the Support Manager is allowed.
G.  Incoming-call context resolves a POC number to its parent customer.
H.  A Support interaction can be linked to the selected POC.
I.  DooCTI call ingestion links the POC and never creates a duplicate Lead.
J.  DooCTI lead lookup returns the parent Lead for a POC number.
"""

import asyncio
import os
import sys
import unittest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

import models  # noqa: F401 - registers every model on Base.metadata
from database import Base
from models.call_log import CallLog
from models.customer import Customer
from models.employee import Employee
from models.lead import Lead
from models.support import CustomerPOC, SupportInteraction
from models.user import User
from models.workflow import SupportHandoff
from routers.doocti import get_lead_by_number, push_doocti_call_log
from routers.support import (
    create_customer_poc,
    create_support_interaction,
    get_customer_pocs,
    get_customer_support_history,
    incoming_call_context,
    set_customer_poc_primary,
    update_customer_poc,
)
from schemas.support import CustomerPOCCreate, CustomerPOCUpdate, SupportInteractionCreate
from utils.timezone import get_ist_now


def _poc_payload(**overrides):
    data = {
        "name": "Ravi POC",
        "mobile": "9876500001",
        "alternate_mobile": "9876500002",
        "whatsapp_number": "9876500003",
        "email": "ravi.poc@example.com",
        "designation": "Plant Manager",
        "department": "Operations",
        "preferred_contact_method": "CALL",
        "notes": "Reachable after 10 AM.",
        "is_primary": False,
    }
    data.update(overrides)
    return CustomerPOCCreate(**data)


class CustomerPOCTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db = Session()

        self.manager_user, self.manager_emp = self._make_person(
            "poc_mgr", "SUPPORT_MANAGER", "SUPPORT"
        )
        self.owner_user, self.owner_emp = self._make_person(
            "poc_owner", "SUPPORT_EXECUTIVE", "SUPPORT", manager_id=self.manager_emp.id
        )
        self.other_user, self.other_emp = self._make_person(
            "poc_other", "SUPPORT_EXECUTIVE", "SUPPORT", manager_id=self.manager_emp.id
        )
        self.sales_user, self.sales_emp = self._make_person(
            "poc_sales", "SALES_EXECUTIVE", "SALES"
        )

        self.lead = Lead(
            name="POC Customer",
            phone="9899000222",
            email="poc.customer@example.com",
            company="POC Industries",
            source="MANUAL",
            status="CONVERTED",
            assigned_to=self.owner_emp.id,
        )
        self.db.add(self.lead)
        self.db.commit()
        self.db.refresh(self.lead)

        self.customer = Customer(
            company_name="POC Industries",
            contact_name="POC Customer",
            phone="9899000222",
            email="poc.customer@example.com",
            location="Coimbatore",
            converted_from_lead=self.lead.id,
        )
        self.db.add(self.customer)
        self.db.commit()
        self.db.refresh(self.customer)

        self.handoff = SupportHandoff(
            lead_id=self.lead.id,
            customer_id=self.customer.id,
            customer_name="POC Customer",
            company_name="POC Industries",
            phone="9899000222",
            email="poc.customer@example.com",
            product_service="CRM Cloud Pro",
            customer_users_count=10,
            support_manager_id=self.manager_emp.id,
            support_manager_name=self.manager_emp.name,
            assigned_agent_id=self.owner_emp.id,
            assigned_agent_name=self.owner_emp.name,
            onboarding_status="ACTIVE",
        )
        self.db.add(self.handoff)
        self.db.commit()
        self.db.refresh(self.handoff)

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _make_person(self, username, role, department, manager_id=None):
        user = User(
            username=username,
            hashed_password="test-only",
            role=role,
            department=department,
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        employee = Employee(
            user_id=user.id,
            manager_id=manager_id,
            department=department,
            name=f"{username.title()} Employee",
            email=f"{username}@example.com",
            phone=f"97{abs(hash(username)) % 100000000:08d}",
            username=username,
            role=role,
            status="ACTIVE",
        )
        self.db.add(employee)
        self.db.commit()
        self.db.refresh(employee)
        return user, employee

    def _create_poc(self, payload=None, user=None):
        return create_customer_poc(
            lead_id=self.lead.id,
            payload=payload or _poc_payload(),
            customer_id=None,
            db=self.db,
            current_user=user or self.owner_user,
        )

    # ------------------------------------------------------------------
    # A. Add one / multiple POCs
    # ------------------------------------------------------------------
    def test_add_and_list_multiple_pocs(self):
        first = self._create_poc()
        self.assertEqual(first["poc_count"], 1)
        self.assertTrue(first["poc"]["is_primary"])
        first_id = first["poc"]["id"]

        second = self._create_poc(
            _poc_payload(
                name="Suresh POC",
                mobile="9876500010",
                alternate_mobile=None,
                whatsapp_number=None,
                email="suresh.poc@example.com",
                designation="Accounts Head",
                department="Finance",
            )
        )
        self.assertEqual(second["poc_count"], 2)
        self.assertFalse(second["poc"]["is_primary"])

        listing = get_customer_pocs(
            lead_id=self.lead.id,
            customer_id=None,
            db=self.db,
            current_user=self.owner_user,
        )
        self.assertEqual(listing["poc_count"], 2)
        self.assertEqual([row["id"] for row in listing["items"]], [first_id, second["poc"]["id"]])
        self.assertEqual(listing["primary_poc"]["id"], first_id)

    # ------------------------------------------------------------------
    # B. Change primary POC
    # ------------------------------------------------------------------
    def test_set_and_change_primary_poc(self):
        first = self._create_poc()
        second = self._create_poc(
            _poc_payload(
                name="Suresh POC",
                mobile="9876500010",
                alternate_mobile=None,
                whatsapp_number=None,
                email="suresh.poc@example.com",
            )
        )

        response = set_customer_poc_primary(
            poc_id=second["poc"]["id"],
            db=self.db,
            current_user=self.owner_user,
        )
        self.assertTrue(response["poc"]["is_primary"])
        primary_rows = (
            self.db.query(CustomerPOC)
            .filter(CustomerPOC.lead_id == self.lead.id, CustomerPOC.is_primary.is_(True))
            .all()
        )
        self.assertEqual(len(primary_rows), 1)
        self.assertEqual(primary_rows[0].id, second["poc"]["id"])

        self.db.refresh(self.db.query(CustomerPOC).filter(CustomerPOC.id == first["poc"]["id"]).one())
        self.assertFalse(
            self.db.query(CustomerPOC).filter(CustomerPOC.id == first["poc"]["id"]).one().is_primary
        )

    # ------------------------------------------------------------------
    # C. Edit isolation, main customer number untouched
    # ------------------------------------------------------------------
    def test_edit_one_poc_does_not_affect_others_or_customer(self):
        first = self._create_poc()
        second = self._create_poc(
            _poc_payload(
                name="Suresh POC",
                mobile="9876500010",
                alternate_mobile="9876500011",
                whatsapp_number="9876500012",
                email="suresh.poc@example.com",
                designation="Accounts Head",
                department="Finance",
                notes="Finance contact.",
            )
        )

        updated = update_customer_poc(
            poc_id=first["poc"]["id"],
            payload=CustomerPOCUpdate(
                name="Ravi Kumar",
                designation="Senior Plant Manager",
                preferred_contact_method="WHATSAPP",
            ),
            db=self.db,
            current_user=self.owner_user,
        )
        self.assertEqual(updated["poc"]["name"], "Ravi Kumar")
        self.assertEqual(updated["poc"]["designation"], "Senior Plant Manager")
        self.assertEqual(updated["poc"]["preferred_contact_method"], "WHATSAPP")
        self.assertEqual(updated["poc"]["mobile"], first["poc"]["mobile"])

        second_row = (
            self.db.query(CustomerPOC).filter(CustomerPOC.id == second["poc"]["id"]).one()
        )
        self.assertEqual(second_row.name, "Suresh POC")
        self.assertEqual(second_row.mobile, "9876500010")
        self.assertEqual(second_row.designation, "Accounts Head")
        self.assertEqual(second_row.department, "Finance")

        self.db.refresh(self.lead)
        self.db.refresh(self.customer)
        self.assertEqual(self.lead.phone, "9899000222")
        self.assertEqual(self.customer.phone, "9899000222")

    # ------------------------------------------------------------------
    # D. Duplicate prevention
    # ------------------------------------------------------------------
    def test_duplicate_poc_mobile_and_email_rejected(self):
        self._create_poc()

        with self.assertRaises(HTTPException) as mobile_ctx:
            self._create_poc(
                _poc_payload(name="Duplicate", mobile="+91 98765 00001", email=None)
            )
        self.assertEqual(mobile_ctx.exception.status_code, 409)

        with self.assertRaises(HTTPException) as alt_ctx:
            self._create_poc(
                _poc_payload(name="Duplicate Alt", mobile="9876500099", alternate_mobile="9876500002", email=None)
            )
        self.assertEqual(alt_ctx.exception.status_code, 409)

        with self.assertRaises(HTTPException) as email_ctx:
            self._create_poc(
                _poc_payload(name="Duplicate Email", mobile="9876500098", email="RAVI.POC@EXAMPLE.COM")
            )
        self.assertEqual(email_ctx.exception.status_code, 409)

    # ------------------------------------------------------------------
    # E/F. Permissions
    # ------------------------------------------------------------------
    def test_sales_is_blocked_from_poc_access(self):
        with self.assertRaises(HTTPException) as read_ctx:
            get_customer_pocs(
                lead_id=self.lead.id,
                customer_id=None,
                db=self.db,
                current_user=self.sales_user,
            )
        self.assertEqual(read_ctx.exception.status_code, 403)

        with self.assertRaises(HTTPException) as create_ctx:
            self._create_poc(user=self.sales_user)
        self.assertEqual(create_ctx.exception.status_code, 403)

    def test_unrelated_support_executive_blocked_and_manager_allowed(self):
        with self.assertRaises(HTTPException) as other_ctx:
            self._create_poc(user=self.other_user)
        self.assertEqual(other_ctx.exception.status_code, 403)

        manager_response = self._create_poc(user=self.manager_user)
        self.assertTrue(manager_response["poc"]["is_primary"])


    # ------------------------------------------------------------------
    # G. Incoming-call POC resolution
    # ------------------------------------------------------------------
    def test_incoming_call_resolves_poc_to_parent_customer(self):
        create_response = self._create_poc(
            _poc_payload(mobile="9876500021", alternate_mobile=None, whatsapp_number="9876500022")
        )
        poc_id = create_response["poc"]["id"]
        call_logs_before = self.db.query(CallLog).count()

        context = incoming_call_context(
            phone="+91 98765 00022",
            number=None,
            db=self.db,
            current_user=self.owner_user,
        )

        self.assertTrue(context["found"])
        self.assertTrue(context["authorized"])
        self.assertEqual(context["customer"]["lead_id"], self.lead.id)
        self.assertEqual(context["customer"]["customer_id"], self.customer.id)
        self.assertEqual(context["matched_poc"]["id"], poc_id)
        self.assertEqual(len(context["pocs"]), 1)
        self.assertEqual(self.db.query(CallLog).count(), call_logs_before)
        self.assertEqual(self.db.query(Lead).count(), 1)

    # ------------------------------------------------------------------
    # H. Interaction POC link and history projection
    # ------------------------------------------------------------------
    def test_interaction_links_selected_poc_and_history_shows_it(self):
        create_response = self._create_poc()
        poc_id = create_response["poc"]["id"]

        interaction_response = create_support_interaction(
            lead_id=self.lead.id,
            payload=SupportInteractionCreate(
                customer_poc_id=poc_id,
                interaction_type="OUTBOUND",
                discussion="Called the plant manager about the reported issue.",
                next_action="Send the replacement part.",
                client_reference="poc-test-interaction-1",
            ),
            db=self.db,
            current_user=self.owner_user,
        )
        interaction = interaction_response["interaction"]
        self.assertEqual(interaction["customer_poc_id"], poc_id)
        self.assertEqual(interaction["poc_name"], "Ravi POC")
        self.assertEqual(interaction["poc_phone"], "9876500001")

        history = get_customer_support_history(
            lead_id=self.lead.id,
            customer_id=None,
            db=self.db,
            current_user=self.owner_user,
        )
        self.assertEqual(history["poc_count"], 1)
        self.assertEqual(history["primary_poc"]["id"], poc_id)
        self.assertEqual(history["interactions"][0]["customer_poc_id"], poc_id)
        self.assertEqual(history["interactions"][0]["poc_name"], "Ravi POC")

        stored = self.db.query(SupportInteraction).one()
        self.assertEqual(stored.customer_poc_id, poc_id)

    # ------------------------------------------------------------------
    # I. DooCTI CDR ingestion maps the call to POC + parent Lead
    # ------------------------------------------------------------------
    def test_doocti_call_links_poc_without_duplicate_lead(self):
        create_response = self._create_poc(
            _poc_payload(mobile="9876500031", alternate_mobile=None, whatsapp_number=None)
        )
        poc_id = create_response["poc"]["id"]
        leads_before = self.db.query(Lead).count()

        payload = {
            "uniqueid": "poc-call-test-1",
            "phone_number": "9876500031",
            "status": "COMPLETED",
            "duration": 45,
            "call_direction": "OUTBOUND",
            "employee_id": self.owner_emp.id,
            "entity_id": self.lead.id,
            "customer_poc_id": poc_id,
            "agent": self.owner_emp.name,
            "agent_email": self.owner_emp.email,
            "start_time": "2026-11-14 10:00:00",
        }
        request = self._make_request("/doocti/push-call-log", payload)
        response = asyncio.run(push_doocti_call_log(request, db=self.db))

        self.assertNotEqual(response.get("status"), "ignored")
        call_log = self.db.query(CallLog).filter(CallLog.provider_call_id == "poc-call-test-1").one()
        self.assertEqual(call_log.customer_poc_id, poc_id)
        self.assertEqual(call_log.lead_id, self.lead.id)
        self.assertEqual(call_log.call_direction, "OUTBOUND")
        self.assertEqual(call_log.duration_seconds, 45)
        self.assertEqual(self.db.query(Lead).count(), leads_before)

    def test_doocti_call_resolves_poc_by_phone_without_explicit_id(self):
        create_response = self._create_poc(
            _poc_payload(mobile="9876500041", alternate_mobile=None, whatsapp_number=None)
        )
        poc_id = create_response["poc"]["id"]
        leads_before = self.db.query(Lead).count()

        payload = {
            "uniqueid": "poc-call-test-2",
            "from_number": "9876500041",
            "to_number": "1001",
            "status": "COMPLETED",
            "duration": 12,
            "call_direction": "INBOUND",
            "employee_id": self.owner_emp.id,
            "agent": self.owner_emp.name,
            "agent_email": self.owner_emp.email,
            "start_time": "2026-11-14 11:00:00",
        }
        request = self._make_request("/doocti/push-call-log", payload)
        asyncio.run(push_doocti_call_log(request, db=self.db))

        call_log = self.db.query(CallLog).filter(CallLog.provider_call_id == "poc-call-test-2").one()
        self.assertEqual(call_log.customer_poc_id, poc_id)
        self.assertEqual(call_log.lead_id, self.lead.id)
        self.assertEqual(call_log.call_direction, "INBOUND")
        self.assertEqual(self.db.query(Lead).count(), leads_before)

    # ------------------------------------------------------------------
    # J. DooCTI lead lookup by POC number
    # ------------------------------------------------------------------
    def test_doocti_lead_lookup_returns_parent_customer_for_poc_number(self):
        create_response = self._create_poc(
            _poc_payload(mobile="9876500051", alternate_mobile=None, whatsapp_number=None)
        )
        poc_id = create_response["poc"]["id"]
        leads_before = self.db.query(Lead).count()

        result = get_lead_by_number(
            number="+91 98765 00051",
            phone=None,
            auto_create=False,
            uniqueid=None,
            call_id=None,
            station=None,
            db=self.db,
        )

        self.assertTrue(result["exists"])
        self.assertEqual(result["lead"]["id"], self.lead.id)
        self.assertEqual(result["lead"]["customer_poc_id"], poc_id)
        self.assertEqual(result["lead"]["poc_name"], "Ravi POC")
        self.assertEqual(result["lead"]["phone"], "9876500051")
        self.assertEqual(result["lead"]["primary_poc"]["id"], poc_id)
        self.assertEqual(self.db.query(Lead).count(), leads_before)

    def _make_request(self, path, payload):
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }
        request = Request(scope)
        request.state.cdr_payload = payload
        return request


if __name__ == "__main__":
    unittest.main()
