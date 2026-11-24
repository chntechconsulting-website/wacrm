"""Collapse the legacy NEW / NEW_LEAD Sales statuses into NEW LEAD.

Only ``leads.status`` is rewritten. Support statuses (which also use the value
``NEW``) and historical ``lead_status_history`` audit rows are intentionally
left untouched.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import func

from database import SessionLocal
from models.lead import Lead
from utils.lead_status import STATUS_NEW

LEGACY_STATUSES = ("NEW", "NEW_LEAD")


def run_migration():
    db = SessionLocal()
    try:
        updated = (
            db.query(Lead)
            .filter(func.upper(func.trim(Lead.status)).in_(LEGACY_STATUSES))
            .update({Lead.status: STATUS_NEW}, synchronize_session=False)
        )
        db.commit()
        print(
            f"Normalized {updated} lead(s) from NEW/NEW_LEAD to '{STATUS_NEW}'."
        )
        return updated
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_migration()
