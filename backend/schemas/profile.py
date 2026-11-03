import re
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

ALLOWED_GENDERS = {"Male", "Female", "Other", "Prefer not to say"}


class ProfileOut(BaseModel):
    """Read-only projection of the authenticated employee's profile."""

    id: int
    employee_id: int
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    username: str
    role: str
    role_label: str
    department: Optional[str] = None
    department_label: Optional[str] = None
    designation: str
    team: Optional[str] = None
    reporting_manager_id: Optional[int] = None
    reporting_manager_name: Optional[str] = None
    date_of_joining: Optional[date] = None
    employment_status: str = "ACTIVE"
    account_status: str = "ACTIVE"
    is_active: bool = True
    last_login: Optional[datetime] = None
    created_at: Optional[datetime] = None
    photo_url: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    address: Optional[str] = None


class ProfileUpdateRequest(BaseModel):
    """
    Personal fields only.

    ``extra="forbid"`` is intentional: attempts to edit employee_id,
    department, role, status, permissions or reporting hierarchy through the
    profile endpoint are rejected with HTTP 422 instead of being silently
    applied.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=30)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(default=None, max_length=30)
    address: Optional[str] = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Full name is required.")
        if len(cleaned) > 100:
            raise ValueError("Full name cannot exceed 100 characters.")
        return cleaned

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        raw = value.strip()
        if not raw:
            return None
        digits = re.sub(r"\D", "", raw)
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        elif len(digits) == 11 and digits.startswith("0"):
            digits = digits[1:]
        if not 7 <= len(digits) <= 15:
            raise ValueError("Enter a valid mobile number with 7 to 15 digits.")
        return digits

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value: Optional[date]) -> Optional[date]:
        if value is None:
            return None
        today = date.today()
        if value > today:
            raise ValueError("Date of birth cannot be in the future.")
        if value.year < 1900:
            raise ValueError("Date of birth must be after 1900.")
        return value

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        raw = value.strip()
        if not raw:
            return None
        canonical = {item.lower(): item for item in ALLOWED_GENDERS}.get(raw.lower())
        if not canonical:
            raise ValueError(
                "Gender must be one of: Male, Female, Other, Prefer not to say."
            )
        return canonical

    @field_validator("address")
    @classmethod
    def validate_address(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if len(cleaned) > 500:
            raise ValueError("Address cannot exceed 500 characters.")
        return cleaned
