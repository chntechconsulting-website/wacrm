from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=True)
    manager_id = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)
    reporting_manager_id = Column(Integer, nullable=True, index=True)
    department = Column(String(50), nullable=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    phone = Column(String(30), nullable=True)
    username = Column(String(100), nullable=False)
    role = Column(String(50), default="SALES_EXECUTIVE", nullable=False)
    status = Column(String(20), default="ACTIVE", nullable=False)  # ACTIVE, INACTIVE
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="employee")
    manager = relationship("Employee", remote_side=[id], backref="team_members")
