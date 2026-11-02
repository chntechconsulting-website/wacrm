from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base
from utils.timezone import get_ist_now


class OfficeSimMapping(Base):
    """
    The employee's registered Office SIM.

    SIM slot is stored for display only. Identity is verified from Android's
    subscription/phone-account data plus a fingerprint, so replacing a SIM or a
    subscription-id reconfiguration forces explicit re-verification.
    """

    __tablename__ = "employee_office_sim"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(
        Integer,
        ForeignKey("employees.id"),
        unique=True,
        nullable=False,
        index=True,
    )

    subscription_id = Column(Integer, nullable=True, index=True)
    sim_slot = Column(Integer, nullable=True)
    carrier_name = Column(String(100), nullable=True)
    display_name = Column(String(100), nullable=True)
    phone_number = Column(String(30), nullable=True)
    phone_account_id = Column(String(150), nullable=True)
    phone_account_component = Column(String(200), nullable=True)
    sim_fingerprint = Column(String(128), nullable=False)

    # VERIFIED | REQUIRES_VERIFICATION
    status = Column(String(30), nullable=False, default="VERIFIED", index=True)
    verification_reason = Column(String(255), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=get_ist_now, nullable=False)
    updated_at = Column(
        DateTime,
        default=get_ist_now,
        onupdate=get_ist_now,
        nullable=False,
    )

    employee = relationship("Employee", backref="office_sim_mapping")
