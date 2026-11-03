import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_db
from main import app
from models import (  # noqa: F401 - imported so create_all sees every table
    Base as _Base,
    Customer,
    Employee,
    FieldVisit,
    Lead,
    LeadActivity,
    LeadAssignment,
    LeadEnquiry,
    LeadStatusHistory,
)
from services.auth import get_current_user

PAGE_SIZE = 150
TOTAL_LEADS = 350  # 3 pages -> 150 + 150 + 50
WEBSITE_LEADS = 200  # first 200 records use the WEBSITE source
ACME_LEADS = 180  # first 180 records match the "Acme" search


class LeadsPaginationTest(unittest.TestCase):
    """Server-side pagination for the Leads list (page / page_size)."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        db_path = os.path.join(cls.temp_dir.name, "leads_pagination_test.db")
        cls.engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

        def override_db():
            db = cls.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id=1, role="ADMIN", username="admin", employee_id=1
        )
        cls.client = TestClient(app)

        # Seed a dataset bigger than one page so paging can be asserted.
        db = cls.Session()
        db.add(
            Employee(
                id=1,
                user_id=1,
                name="Admin Employee",
                email="admin@example.com",
                username="admin",
                phone="+919876500000",
            )
        )
        base_time = datetime(2026, 1, 1, 9, 0, 0)
        for i in range(TOTAL_LEADS):
            # created_at ascends with i, so newest-first (default) returns high ids first
            db.add(
                Lead(
                    name=f"Acme Lead {i:03d}" if i < ACME_LEADS else f"Plain Lead {i:03d}",
                    phone=f"+9190000{i:06d}",
                    source="WEBSITE" if i < WEBSITE_LEADS else "META",
                    status="NEW",
                    assigned_to=1,
                    created_at=base_time + timedelta(minutes=i),
                )
            )
        db.commit()
        db.close()

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        cls.engine.dispose()
        cls.temp_dir.cleanup()

    # ------------------------------------------------------------- helpers
    def _get(self, path="/api/leads", **params):
        response = self.client.get(path, params=params)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _db_count(self):
        db = self.Session()
        try:
            return db.query(Lead).count()
        finally:
            db.close()

    def _ids(self, body):
        return [item["id"] for item in body["items"]]

    # --------------------------------------------------------------- tests
    def test_response_contains_pagination_fields(self):
        body = self._get(page=1, page_size=PAGE_SIZE)
        for key in ("items", "total", "page", "page_size", "total_pages"):
            self.assertIn(key, body)
        self.assertEqual(body["page"], 1)
        self.assertEqual(body["page_size"], PAGE_SIZE)
        self.assertEqual(body["total"], TOTAL_LEADS)
        self.assertEqual(body["total"], self._db_count())
        self.assertEqual(body["total_pages"], 3)

    def test_page_one_returns_first_150_records(self):
        body = self._get(page=1, page_size=PAGE_SIZE)
        self.assertEqual(len(body["items"]), 150)
        # Default sort is newest received first
        self.assertEqual(body["items"][0]["name"], f"Plain Lead {TOTAL_LEADS - 1:03d}")

    def test_page_two_returns_the_next_150_records(self):
        page1 = self._get(page=1, page_size=PAGE_SIZE)
        page2 = self._get(page=2, page_size=PAGE_SIZE)
        self.assertEqual(len(page2["items"]), 150)
        self.assertEqual(page2["page"], 2)
        self.assertEqual(set(self._ids(page1)).intersection(self._ids(page2)), set())

    def test_last_page_returns_remaining_records(self):
        page3 = self._get(page=3, page_size=PAGE_SIZE)
        self.assertEqual(page3["page"], 3)
        self.assertEqual(len(page3["items"]), 50)
        self.assertEqual(page3["total_pages"], 3)

        all_ids = []
        for page in (1, 2, 3):
            all_ids.extend(self._ids(self._get(page=page, page_size=PAGE_SIZE)))
        self.assertEqual(len(all_ids), TOTAL_LEADS)
        self.assertEqual(len(set(all_ids)), TOTAL_LEADS)

    def test_default_page_size_is_150(self):
        body = self._get(page=1)
        self.assertEqual(body["page_size"], PAGE_SIZE)
        self.assertEqual(len(body["items"]), 150)

    def test_source_filter_applies_to_every_page(self):
        page1 = self._get(page=1, page_size=PAGE_SIZE, source_filter="WEBSITE")
        page2 = self._get(page=2, page_size=PAGE_SIZE, source_filter="WEBSITE")
        self.assertEqual(page1["total"], WEBSITE_LEADS)
        self.assertEqual(page1["total_pages"], 2)
        self.assertEqual(len(page1["items"]), 150)
        self.assertEqual(len(page2["items"]), 50)
        for item in page1["items"] + page2["items"]:
            self.assertEqual(item["source"], "WEBSITE")

    def test_search_applies_to_every_page(self):
        page1 = self._get(page=1, page_size=PAGE_SIZE, search="Acme")
        page2 = self._get(page=2, page_size=PAGE_SIZE, search="Acme")
        self.assertEqual(page1["total"], ACME_LEADS)
        self.assertEqual(page1["total_pages"], 2)
        self.assertEqual(len(page1["items"]), 150)
        self.assertEqual(len(page2["items"]), 30)
        for item in page1["items"] + page2["items"]:
            self.assertIn("Acme", item["name"])

    def test_sorting_is_preserved_across_pages(self):
        page1 = self._get(page=1, page_size=PAGE_SIZE, sort_order="asc")
        page2 = self._get(page=2, page_size=PAGE_SIZE, sort_order="asc")
        page1_ids = self._ids(page1)
        page2_ids = self._ids(page2)
        self.assertEqual(len(page1_ids), 150)
        self.assertEqual(len(page2_ids), 150)
        self.assertEqual(page1_ids[0], min(page1_ids))
        self.assertTrue(max(page1_ids) < min(page2_ids))

    def test_legacy_skip_and_limit_still_work(self):
        body = self._get(skip=25, limit=25)
        self.assertEqual(len(body["items"]), 25)
        self.assertEqual(body["total"], TOTAL_LEADS)
        self.assertEqual(body["page"], 2)
        self.assertEqual(body["page_size"], 25)
        self.assertEqual(body["total_pages"], 14)

    def test_mobile_style_page_and_limit_request_keeps_page_size(self):
        # The mobile app sends page together with skip/limit - its page size
        # must not be overridden by the 150 default.
        body = self._get(page=2, skip=20, limit=20)
        legacy = self._get(skip=20, limit=20)
        self.assertEqual(body["page_size"], 20)
        self.assertEqual(body["page"], 2)
        self.assertEqual(len(body["items"]), 20)
        self.assertEqual(self._ids(body), self._ids(legacy))

    def test_my_leads_endpoint_supports_pagination(self):
        page1 = self._get("/api/leads/my", page=1, page_size=PAGE_SIZE)
        page2 = self._get("/api/leads/my", page=2, page_size=PAGE_SIZE)
        self.assertEqual(page1["total"], TOTAL_LEADS)
        self.assertEqual(page1["total_pages"], 3)
        self.assertEqual(len(page1["items"]), 150)
        self.assertEqual(len(page2["items"]), 150)
        self.assertEqual(set(self._ids(page1)).intersection(self._ids(page2)), set())

    def test_out_of_range_page_returns_empty_items(self):
        body = self._get(page=99, page_size=PAGE_SIZE)
        self.assertEqual(body["items"], [])
        self.assertEqual(body["page"], 99)
        self.assertEqual(body["total"], TOTAL_LEADS)


if __name__ == "__main__":
    unittest.main()
