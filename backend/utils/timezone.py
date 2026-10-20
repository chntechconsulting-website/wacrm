import datetime as dt
from typing import Optional

# Indian Standard Time (IST) is strictly UTC+05:30 with no Daylight Saving Time
IST_TIMEZONE = dt.timezone(dt.timedelta(hours=5, minutes=30), name="IST")

def get_ist_now() -> dt.datetime:
    """
    Returns current date and time in Asia/Kolkata (IST) without timezone offset (naive).
    This ensures MySQL DATETIME columns accurately store the exact Indian Standard Time.
    """
    return dt.datetime.now(IST_TIMEZONE).replace(tzinfo=None)

def format_ist_datetime(dt_val: Optional[dt.datetime]) -> str:
    """
    Formats a datetime object to: '08 Oct 2026, 12:35 PM'
    """
    if not dt_val:
        return ""
    # Ensure dt_val is treated as IST
    return dt_val.strftime("%d %b %Y, %I:%M %p")

def format_ist_date(dt_val: Optional[dt.datetime]) -> str:
    """
    Formats a datetime object to: '08 Oct 2026'
    """
    if not dt_val:
        return ""
    return dt_val.strftime("%d %b %Y")

def format_ist_time(dt_val: Optional[dt.datetime]) -> str:
    """
    Formats a datetime object to: '12:35 PM'
    """
    if not dt_val:
        return ""
    return dt_val.strftime("%I:%M %p")
