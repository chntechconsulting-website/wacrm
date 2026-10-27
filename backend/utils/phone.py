import re
from typing import Optional, Any
from sqlalchemy import or_, desc, func
from sqlalchemy.orm import Session
from models.lead import Lead
from models.customer import Customer
import logging

logger = logging.getLogger("phone_utils")

def normalize_phone(phone: Optional[Any]) -> str:
    """
    Standardize Indian and international phone numbers into a clean 10-digit format
    (or clean numeric digits if length != 10).
    Strips spaces, plus, hyphens, parentheses, country code +91 / 91, and leading zero trunk prefixes.
    """
    if not phone:
        return ""
    # Extract only digits
    cleaned = "".join(filter(str.isdigit, str(phone)))
    if not cleaned:
        return ""
    
    # Handle Indian numbers:
    # 12 digits starting with 91 -> last 10 digits
    if len(cleaned) == 12 and cleaned.startswith("91"):
        cleaned = cleaned[2:]
    # 11 digits starting with 0 -> last 10 digits
    elif len(cleaned) == 11 and cleaned.startswith("0"):
        cleaned = cleaned[1:]
    # More than 10 digits starting with 91
    elif len(cleaned) > 10 and cleaned.startswith("91"):
        cleaned = cleaned[-10:]
    elif len(cleaned) > 10:
        cleaned = cleaned[-10:]
        
    return cleaned

def sql_strip_phone(column):
    """
    Returns a SQL expression that strips common formatting characters:
    spaces, dashes, plus signs, brackets, and periods.
    """
    expr = func.replace(column, " ", "")
    expr = func.replace(expr, "-", "")
    expr = func.replace(expr, "+", "")
    expr = func.replace(expr, "(", "")
    expr = func.replace(expr, ")", "")
    expr = func.replace(expr, ".", "")
    return expr

def find_existing_lead_by_phone(db: Session, raw_phone: Optional[Any]) -> Optional[Lead]:
    """
    Robust database search for an existing Lead using normalized phone numbers.
    Handles any spacing or prefix formatting (+91, 0, spaces, dashes) in both
    the incoming query and the database columns (phone, whatsapp_number).
    """
    clean = normalize_phone(raw_phone)
    if not clean or len(clean) < 7:
        return None

    clean_lead_phone = sql_strip_phone(Lead.phone)
    clean_lead_wa = sql_strip_phone(Lead.whatsapp_number)

    # 1. SQL query using stripped columns to find candidates
    candidates = db.query(Lead).filter(
        or_(
            clean_lead_phone.like(f"%{clean}%"),
            clean_lead_wa.like(f"%{clean}%")
        )
    ).order_by(desc(Lead.id)).all()

    # 2. Strict python verification to guarantee exact 10-digit match
    for lead in candidates:
        if normalize_phone(lead.phone) == clean or normalize_phone(lead.whatsapp_number) == clean:
            return lead

    # 3. Fallback: if lead was entered with extra trunk prefix or suffix, check last 10 digits
    if len(clean) >= 10:
        ten_digit = clean[-10:]
        for lead in candidates:
            lp = normalize_phone(lead.phone)
            lwa = normalize_phone(lead.whatsapp_number)
            if (lp and lp[-10:] == ten_digit) or (lwa and lwa[-10:] == ten_digit):
                return lead

    return None

def find_existing_customer_by_phone(db: Session, raw_phone: Optional[Any]) -> Optional[Customer]:
    """
    Robust database search for an existing Customer using normalized phone numbers.
    """
    clean = normalize_phone(raw_phone)
    if not clean or len(clean) < 7:
        return None

    clean_cust_phone = sql_strip_phone(Customer.phone)
    candidates = db.query(Customer).filter(
        clean_cust_phone.like(f"%{clean}%")
    ).order_by(desc(Customer.id)).all()

    for cust in candidates:
        if normalize_phone(cust.phone) == clean:
            return cust

    if len(clean) >= 10:
        ten_digit = clean[-10:]
        for cust in candidates:
            cp = normalize_phone(cust.phone)
            if cp and cp[-10:] == ten_digit:
                return cust

    return None
