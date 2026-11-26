from sqlalchemy import Column, Integer, String, DateTime, Index
from database import Base

from utils.timezone import get_ist_now


class ExcelImportBatch(Base):
    """One successfully committed Excel/CSV bulk import.

    The row is created only when at least one new lead was created by the
    upload, so every ACTIVE batch has leads that can be revoked. Re-inquiries
    are counted for the history but are never tagged with the batch id: those
    leads already existed before the upload and must never be deleted by a
    revoke.
    """

    __tablename__ = "excel_import_batches"
    __table_args__ = (
        Index("ix_excel_import_batches_status_created", "status", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    uploaded_by_id = Column(Integer, nullable=True, index=True)
    uploaded_by_username = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=get_ist_now, nullable=False, index=True)

    total_rows = Column(Integer, default=0, nullable=False)
    imported_count = Column(Integer, default=0, nullable=False)
    reinquiry_count = Column(Integer, default=0, nullable=False)
    duplicate_count = Column(Integer, default=0, nullable=False)
    invalid_count = Column(Integer, default=0, nullable=False)

    # ACTIVE or REVOKED. Revoked batches stay in the table as an audit trail.
    status = Column(String(20), default="ACTIVE", nullable=False, index=True)

    revoked_at = Column(DateTime, nullable=True)
    revoked_by_id = Column(Integer, nullable=True)
    revoked_by_username = Column(String(100), nullable=True)
    revoked_lead_count = Column(Integer, default=0, nullable=False)
    revoked_activity_count = Column(Integer, default=0, nullable=False)
    revoked_enquiry_count = Column(Integer, default=0, nullable=False)
    revoked_assignment_count = Column(Integer, default=0, nullable=False)
