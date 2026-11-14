from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base
from utils.timezone import get_ist_now


class TrialReminderDelivery(Base):
    """Idempotency record for a single Trial reminder delivery.

    One row exists per lead, recipient user, reminder milestone and trial end
    date. The unique constraint is the database-level guard that stops duplicate
    notifications when the scheduler runs repeatedly, restarts, or runs in more
    than one worker process.

    Keeping ``trial_end_date`` in the key means a genuinely new trial cycle
    (with a new end date) can send its own reminders while a re-run for the same
    cycle can never duplicate a notification.
    """

    __tablename__ = "trial_reminder_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "lead_id",
            "user_id",
            "milestone",
            "trial_end_date",
            name="uq_trial_reminder_delivery",
        ),
        Index(
            "ix_trial_reminder_deliveries_lead_end",
            "lead_id",
            "trial_end_date",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    recipient_role = Column(String(30), nullable=False)
    milestone = Column(String(20), nullable=False)
    trial_end_date = Column(Date, nullable=False)
    notification_id = Column(Integer, ForeignKey("notifications.id"), nullable=True)
    created_at = Column(DateTime, default=get_ist_now, nullable=False)

    lead = relationship("Lead")
    user = relationship("User")
    notification = relationship("Notification")
