from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base


class Team(Base):
    """
    Admin-registered department team.

    Team membership is NOT duplicated here. Members continue to be derived from
    the existing Employee.manager_id reporting hierarchy, which keeps employee
    records, IDs and ownership unchanged. This table only registers/naming a
    team under a department and pins it to an existing manager.
    """

    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("department", "name", name="uq_team_department_name"),
        UniqueConstraint("manager_id", name="uq_team_manager"),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    department = Column(String(50), nullable=False, index=True)
    manager_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    description = Column(Text, nullable=True)
    status = Column(String(20), default="ACTIVE", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    manager = relationship("Employee", foreign_keys=[manager_id])
