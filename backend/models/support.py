"""Support customer history, leave and temporary coverage models.

These tables are additive. They never replace or mutate the Sales-owned
``Lead`` / ``SupportHandoff`` ownership fields. The permanent Support owner
stays on ``SupportHandoff.assigned_agent_id``; a leave backup is represented
by a separate, auditable coverage row.
"""

from datetime import datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base
from utils.timezone import get_ist_now


class SupportInteraction(Base):
    """One permanent customer-support interaction record.

    Rows are append-only. The application exposes no update or delete endpoint
    for interaction content, so previous notes can never be overwritten.
    """

    __tablename__ = "support_interactions"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True, index=True)
    support_handoff_id = Column(
        Integer, ForeignKey("support_handoffs.id"), nullable=True, index=True
    )

    # INBOUND, OUTBOUND, MANUAL
    interaction_type = Column(String(20), default="MANUAL", nullable=False, index=True)
    interaction_at = Column(DateTime, default=get_ist_now, nullable=False, index=True)

    discussion = Column(Text, nullable=True)
    problem_reported = Column(Text, nullable=True)
    troubleshooting = Column(Text, nullable=True)
    solution_provided = Column(Text, nullable=True)
    pending_issues = Column(Text, nullable=True)
    customer_commitments = Column(Text, nullable=True)
    next_action = Column(Text, nullable=True)
    follow_up_at = Column(DateTime, nullable=True, index=True)
    notes = Column(Text, nullable=True)
    attachments = Column(JSON, nullable=True)

    # Immutable ownership snapshot at creation time.
    original_employee_id = Column(
        Integer, ForeignKey("employees.id"), nullable=True, index=True
    )
    handling_employee_id = Column(
        Integer, ForeignKey("employees.id"), nullable=False, index=True
    )
    created_by_employee_id = Column(
        Integer, ForeignKey("employees.id"), nullable=False, index=True
    )
    department = Column(String(30), default="SUPPORT", nullable=False, index=True)

    # Optional client-generated idempotency key. A retried HTTP request with the
    # same key cannot create a second interaction for the same customer.
    client_reference = Column(String(100), nullable=True, index=True)

    created_at = Column(DateTime, default=get_ist_now, nullable=False, index=True)
    updated_at = Column(DateTime, default=get_ist_now, onupdate=get_ist_now, nullable=False)

    customer = relationship("Customer", foreign_keys=[customer_id])
    lead = relationship("Lead", foreign_keys=[lead_id])
    support_handoff = relationship("SupportHandoff", foreign_keys=[support_handoff_id])
    original_employee = relationship("Employee", foreign_keys=[original_employee_id])
    handling_employee = relationship("Employee", foreign_keys=[handling_employee_id])
    created_by_employee = relationship("Employee", foreign_keys=[created_by_employee_id])

    __table_args__ = (
        Index("ix_support_interactions_customer_time", "customer_id", "interaction_at"),
        Index("ix_support_interactions_lead_time", "lead_id", "interaction_at"),
        UniqueConstraint(
            "customer_id",
            "client_reference",
            name="uq_support_interactions_customer_client_ref",
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "lead_id": self.lead_id,
            "support_handoff_id": self.support_handoff_id,
            "interaction_type": self.interaction_type,
            "interaction_at": self.interaction_at.isoformat() if self.interaction_at else None,
            "discussion": self.discussion,
            "problem_reported": self.problem_reported,
            "troubleshooting": self.troubleshooting,
            "solution_provided": self.solution_provided,
            "pending_issues": self.pending_issues,
            "customer_commitments": self.customer_commitments,
            "next_action": self.next_action,
            "follow_up_at": self.follow_up_at.isoformat() if self.follow_up_at else None,
            "notes": self.notes,
            "attachments": self.attachments or [],
            "original_employee_id": self.original_employee_id,
            "original_employee_name": (
                self.original_employee.name if self.original_employee else None
            ),
            "handling_employee_id": self.handling_employee_id,
            "handling_employee_name": (
                self.handling_employee.name if self.handling_employee else None
            ),
            "created_by_employee_id": self.created_by_employee_id,
            "created_by_employee_name": (
                self.created_by_employee.name if self.created_by_employee else None
            ),
            "department": self.department,
            "client_reference": self.client_reference,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class EmployeeLeave(Base):
    """Approved leave used to drive temporary Support coverage.

    The CRM had no dedicated leave/attendance table. This additive table is the
    authoritative leave reference for Support coverage and records the approval
    audit trail. Employee presence continues to come from ``employee_presence``.
    """

    __tablename__ = "employee_leaves"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    leave_type = Column(String(30), default="CASUAL", nullable=False)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False, index=True)
    # PENDING, APPROVED, REJECTED, CANCELLED
    status = Column(String(20), default="PENDING", nullable=False, index=True)
    reason = Column(Text, nullable=True)
    manager_notes = Column(Text, nullable=True)

    approved_by_employee_id = Column(
        Integer, ForeignKey("employees.id"), nullable=True, index=True
    )
    approved_at = Column(DateTime, nullable=True)
    created_by_employee_id = Column(
        Integer, ForeignKey("employees.id"), nullable=True, index=True
    )

    created_at = Column(DateTime, default=get_ist_now, nullable=False, index=True)
    updated_at = Column(DateTime, default=get_ist_now, onupdate=get_ist_now, nullable=False)

    employee = relationship("Employee", foreign_keys=[employee_id])
    approved_by = relationship("Employee", foreign_keys=[approved_by_employee_id])
    created_by = relationship("Employee", foreign_keys=[created_by_employee_id])
    coverage_assignments = relationship(
        "SupportCoverageAssignment",
        back_populates="leave",
        cascade="all, save-update, merge",
    )

    __table_args__ = (
        Index("ix_employee_leaves_employee_dates", "employee_id", "start_date", "end_date"),
        Index("ix_employee_leaves_status_dates", "status", "start_date", "end_date"),
    )


class SupportCoverageAssignment(Base):
    """Auditable temporary coverage for one Support customer during leave.

    ``original_employee_id`` is the permanent customer owner at the moment
    coverage starts. ``backup_employee_id`` receives temporary access only.
    Ending coverage never rewrites either employee's historical interactions.
    """

    __tablename__ = "support_coverage_assignments"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    support_handoff_id = Column(
        Integer, ForeignKey("support_handoffs.id"), nullable=True, index=True
    )
    leave_id = Column(Integer, ForeignKey("employee_leaves.id"), nullable=True, index=True)

    original_employee_id = Column(
        Integer, ForeignKey("employees.id"), nullable=False, index=True
    )
    backup_employee_id = Column(
        Integer, ForeignKey("employees.id"), nullable=False, index=True
    )
    assigned_by_employee_id = Column(
        Integer, ForeignKey("employees.id"), nullable=True, index=True
    )

    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False, index=True)
    # ACTIVE, ENDED, CANCELLED
    status = Column(String(20), default="ACTIVE", nullable=False, index=True)

    assigned_at = Column(DateTime, default=get_ist_now, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    ended_by_employee_id = Column(
        Integer, ForeignKey("employees.id"), nullable=True, index=True
    )
    end_reason = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=get_ist_now, nullable=False, index=True)
    updated_at = Column(DateTime, default=get_ist_now, onupdate=get_ist_now, nullable=False)

    customer = relationship("Customer", foreign_keys=[customer_id])
    lead = relationship("Lead", foreign_keys=[lead_id])
    support_handoff = relationship("SupportHandoff", foreign_keys=[support_handoff_id])
    leave = relationship("EmployeeLeave", back_populates="coverage_assignments")
    original_employee = relationship("Employee", foreign_keys=[original_employee_id])
    backup_employee = relationship("Employee", foreign_keys=[backup_employee_id])
    assigned_by_employee = relationship("Employee", foreign_keys=[assigned_by_employee_id])
    ended_by_employee = relationship("Employee", foreign_keys=[ended_by_employee_id])

    __table_args__ = (
        Index(
            "ix_support_coverage_backup_status_dates",
            "backup_employee_id",
            "status",
            "start_date",
            "end_date",
        ),
        Index(
            "ix_support_coverage_lead_status_dates",
            "lead_id",
            "status",
            "start_date",
            "end_date",
        ),
        Index(
            "ix_support_coverage_original_status",
            "original_employee_id",
            "status",
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "lead_id": self.lead_id,
            "support_handoff_id": self.support_handoff_id,
            "leave_id": self.leave_id,
            "original_employee_id": self.original_employee_id,
            "original_employee_name": (
                self.original_employee.name if self.original_employee else None
            ),
            "backup_employee_id": self.backup_employee_id,
            "backup_employee_name": (
                self.backup_employee.name if self.backup_employee else None
            ),
            "assigned_by_employee_id": self.assigned_by_employee_id,
            "assigned_by_employee_name": (
                self.assigned_by_employee.name if self.assigned_by_employee else None
            ),
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "status": self.status,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "ended_by_employee_id": self.ended_by_employee_id,
            "end_reason": self.end_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
