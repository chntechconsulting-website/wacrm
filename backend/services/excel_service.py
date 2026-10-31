import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from sqlalchemy.orm import Session
from datetime import datetime

from models.lead import Lead
from models.employee import Employee
from utils.phone import normalize_email, normalize_phone

def generate_excel_template() -> io.BytesIO:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Lead Import Template"

    headers = [
        "First Name",
        "Last Name",
        "Phone",
        "WhatsApp Number",
        "Email",
        "Company",
        "Designation",
        "Industry",
        "Website",
        "Company Size",
        "Country",
        "State",
        "City",
        "Source",
        "Status",
        "Priority",
        "Campaign Name",
        "Requirement Notes",
        "Assigned To"
    ]
    ws.append(headers)

    # Style header row
    header_fill = PatternFill(start_color="059669", end_color="059669", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        col_letter = openpyxl.utils.get_column_letter(col_num)
        ws.column_dimensions[col_letter].width = max(len(header) + 4, 18)

    # Add realistic sample row
    sample_row = [
        "John",
        "Doe",
        "+91 9876543210",
        "+91 9876543210",
        "john@example.com",
        "Acme Inc",
        "Operations Manager",
        "Manufacturing",
        "https://acme.example.com",
        "50-200",
        "India",
        "Delhi",
        "Delhi",
        "EXCEL",
        "NEW",
        "HIGH",
        "Summer Campaign",
        "Interested in 50 user licenses demo",
        "System Administrator"
    ]
    ws.append(sample_row)

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream

def normalize_status(raw_s: str, assigned_to_id: int = None) -> str:
    s = (raw_s or "").upper().strip()
    if not s:
        return "ASSIGNED" if assigned_to_id else "NEW"
    if ("NOT" in s or "NO " in s or "ISNT" in s or "ISN'T" in s) and any(w in s for w in ["INTREST", "INTEREST", "INTERST", "SUITABLE", "WANT", "NEED"]):
        return "NOT_INTERESTED"
    if any(w in s for w in ["PURCHASE", "BUY", "BOUGHT", "CONVERT", "WON", "PAID", "DONE", "CLOSED"]):
        return "CONVERTED"
    if any(w in s for w in ["QUOTE", "QUOTATION", "PROPOSAL", "ESTIMATE"]):
        return "QUALIFIED"
    if any(w in s for w in ["FUTURE", "UPDATE", "FOLLOW", "LATER", "INITIATE", "CALL", "DAYS", "MONTH", "DECEMBER", "WEEK", "NEXT"]):
        return "FOLLOW_UP"
    if any(w in s for w in ["INTREST", "INTEREST", "INTERST", "POSSIBLE", "CONSIDER"]):
        return "INTERESTED"
    if any(w in s for w in ["CONTACT", "REACH", "SPOKE", "TALK"]):
        return "CONTACTED"
    if any(w in s for w in ["LOST", "DROP", "REJECT", "CANCEL"]):
        return "LOST"
    if s in ["NEW", "ASSIGNED", "CONTACTED", "INTERESTED", "FOLLOW_UP", "QUALIFIED", "CONVERTED", "NOT_INTERESTED", "LOST"]:
        return s
    return "ASSIGNED" if assigned_to_id else "NEW"

def parse_and_validate_excel_leads(file_contents: bytes, db: Session):
    wb = openpyxl.load_workbook(filename=io.BytesIO(file_contents), data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return {"total_rows": 0, "imported": 0, "duplicates": 0, "invalid": 0, "valid_leads": [], "invalid_rows": []}

    # Extract headers
    raw_headers = [str(cell).strip() if cell is not None else "" for cell in rows[0]]
    
    # Map header indices flexibly. Most-specific headers are matched first so
    # "Company Size" is not captured by "Company" and "First Name"/"Last Name"
    # are not captured by the generic "Name" column.
    col_indices = {
        "first_name": -1,
        "last_name": -1,
        "name": -1,
        "phone": -1,
        "whatsapp_number": -1,
        "email": -1,
        "company": -1,
        "company_size": -1,
        "designation": -1,
        "industry": -1,
        "website": -1,
        "city": -1,
        "state": -1,
        "country": -1,
        "location": -1,
        "campaign_name": -1,
        "source": -1,
        "status": -1,
        "priority": -1,
        "requirement_notes": -1,
        "assigned_to": -1
    }

    for idx, raw_h in enumerate(raw_headers):
        h = raw_h.lower().replace("*", "").replace("_", " ").strip()
        h = " ".join(h.split())
        if not h:
            continue
        if "whatsapp" in h or h in ("wa", "wa number", "wa no", "wa.no"):
            col_indices["whatsapp_number"] = idx
        elif "email" in h or "e-mail" in h:
            col_indices["email"] = idx
        elif ("company size" in h or "companysize" in h or "employee count" in h
              or "no of employees" in h or "number of employees" in h):
            col_indices["company_size"] = idx
        elif "first" in h and "name" in h:
            col_indices["first_name"] = idx
        elif "last" in h and "name" in h:
            col_indices["last_name"] = idx
        elif "phone" in h or "mobile" in h or "contact" in h:
            if col_indices["phone"] == -1:
                col_indices["phone"] = idx
        elif "company" in h or "organization" in h or "org" in h:
            if col_indices["company"] == -1:
                col_indices["company"] = idx
        elif "designation" in h or "job" in h or "title" in h or "role" in h:
            col_indices["designation"] = idx
        elif "industry" in h or "sector" in h:
            col_indices["industry"] = idx
        elif "website" in h or "web site" in h or "url" in h:
            col_indices["website"] = idx
        elif "country" in h:
            col_indices["country"] = idx
        elif "city" in h:
            col_indices["city"] = idx
        elif "state" in h or "province" in h:
            col_indices["state"] = idx
        elif "location" in h or "address" in h:
            col_indices["location"] = idx
        elif "campaign" in h:
            col_indices["campaign_name"] = idx
        elif "source" in h or "channel" in h:
            col_indices["source"] = idx
        elif "status" in h or "stage" in h:
            col_indices["status"] = idx
        elif "priority" in h or "rating" in h:
            col_indices["priority"] = idx
        elif "note" in h or "remark" in h or "requirement" in h or "comment" in h:
            col_indices["requirement_notes"] = idx
        elif "assign" in h or "agent" in h or "owner" in h or "rep" in h:
            col_indices["assigned_to"] = idx
        elif "name" in h and col_indices["name"] == -1:
            col_indices["name"] = idx

    if col_indices["phone"] == -1:
        raise ValueError("Excel file must contain a 'Phone' or 'Mobile' column.")

    # Get active employees map for resolving 'Assigned To'
    active_employees = db.query(Employee).filter(Employee.status == "ACTIVE").all()
    emp_map = {}
    for emp in active_employees:
        if emp.name:
            emp_map[emp.name.strip().lower()] = emp.id
        if emp.email:
            emp_map[emp.email.strip().lower()] = emp.id
        emp_map[str(emp.id)] = emp.id

    # Keys used to detect duplicate rows *inside the uploaded file*.  Phone
    # numbers are compared after normalization so "+91 98765 43210" and
    # "9876543210" are recognized as the same lead.  Emails are only used when
    # they are valid addresses, so placeholders like "-" or "N/A" do not mark
    # every row after the first as a duplicate.
    seen_file_phones = set()
    seen_file_emails = set()

    imported_leads = []
    invalid_rows = []

    total_count = 0
    duplicate_count = 0
    invalid_count = 0

    def _to_text(value):
        if value is None:
            return ""
        if isinstance(value, float):
            # Excel stores whole numbers (phone numbers, ids) as floats.
            return str(int(value)) if value.is_integer() else str(value).strip()
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        return str(value).strip()

    def get_val(row, key):
        idx = col_indices.get(key, -1)
        if idx != -1 and idx < len(row):
            v = _to_text(row[idx])
            return v if v.lower() != "none" else ""
        return ""

    for row_idx, row in enumerate(rows[1:], start=2):
        if not any(row):  # Skip completely empty rows
            continue

        total_count += 1

        first_name = get_val(row, "first_name")
        last_name = get_val(row, "last_name")
        name = get_val(row, "name")
        phone = get_val(row, "phone")
        whatsapp_number = get_val(row, "whatsapp_number") or phone
        email = get_val(row, "email").lower()
        company = get_val(row, "company")
        company_size = get_val(row, "company_size")
        designation = get_val(row, "designation")
        industry = get_val(row, "industry")
        website = get_val(row, "website")
        city = get_val(row, "city")
        state = get_val(row, "state")
        country = get_val(row, "country")
        location = get_val(row, "location")
        campaign_name = get_val(row, "campaign_name")
        source_raw = get_val(row, "source")
        status_raw = get_val(row, "status")
        priority_raw = get_val(row, "priority").upper()
        requirement_notes = get_val(row, "requirement_notes")
        assigned_to_raw = get_val(row, "assigned_to")

        # Validate mandatory phone field
        if not phone:
            invalid_count += 1
            invalid_rows.append({
                "row_index": row_idx,
                "name": name or company or "(Empty)",
                "phone": "(Missing)",
                "email": email,
                "reason": "Missing required Phone number"
            })
            continue

        # A lead must have a usable mobile number.  This also guarantees that
        # empty/garbage values can never participate in duplicate matching.
        if len(normalize_phone(phone)) < 7:
            invalid_count += 1
            invalid_rows.append({
                "row_index": row_idx,
                "name": name or company or "(Empty)",
                "phone": phone,
                "email": email,
                "reason": "Invalid Phone number (minimum 7 digits required)"
            })
            continue

        # Automatic fallback for Name: use First/Last Name, then Company, then Phone
        raw_name = name
        if not name:
            name = f"{first_name} {last_name}".strip()
        if not name:
            if company:
                name = company
            else:
                clean_p = phone.replace(" ", "").replace("+91", "")
                name = f"Lead {clean_p[-5:] if len(clean_p) >= 5 else clean_p}"
        # Older files only had a single Name column; derive the parts for the form.
        if raw_name and not first_name and not last_name:
            parts = raw_name.split(None, 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""

        # Fallback location from city/state
        if not location and (city or state):
            location = f"{city}, {state}".strip(", ")

        # Check duplicate inside the same uploaded file (normalized keys).
        # `phone_key` falls back to the raw text for unusual identifiers so a
        # repeated non-numeric value is still caught.
        phone_key = normalize_phone(phone) or phone.strip().lower()
        email_key = normalize_email(email)

        is_file_dup_phone = bool(phone_key) and phone_key in seen_file_phones
        is_file_dup_email = bool(email_key) and email_key in seen_file_emails

        if is_file_dup_phone or is_file_dup_email:
            duplicate_count += 1
            dup_reason = []
            if is_file_dup_phone: dup_reason.append("Duplicate Phone in File")
            if is_file_dup_email: dup_reason.append("Duplicate Email in File")

            invalid_rows.append({
                "row_index": row_idx,
                "name": name,
                "phone": phone,
                "email": email,
                "reason": ", ".join(dup_reason)
            })
            continue

        # Resolve assigned employee
        assigned_to_id = None
        if assigned_to_raw:
            assigned_to_id = emp_map.get(assigned_to_raw.lower())

        # Normalize status with smart mapping
        status = normalize_status(status_raw, assigned_to_id)

        # If status column had rich text remarks, ensure it's captured in requirement_notes
        if status_raw and len(status_raw) > 8 and status_raw not in (requirement_notes or ""):
            requirement_notes = f"{status_raw} | {requirement_notes}" if requirement_notes else status_raw

        # Normalize priority & rating
        priority = "MEDIUM"
        rating = "Warm"
        if "HIGH" in priority_raw or "HOT" in priority_raw:
            priority = "HIGH"
            rating = "Hot"
        elif "LOW" in priority_raw or "COLD" in priority_raw:
            priority = "LOW"
            rating = "Cold"

        # Add to valid list
        if phone_key:
            seen_file_phones.add(phone_key)
        if email_key:
            seen_file_emails.add(email_key)

        # Lead source: keep an explicit value from the sheet, else mark as EXCEL.
        source_value = (source_raw or "EXCEL").strip().upper() or "EXCEL"
        if source_value in ["META ADS", "META_ADS"]:
            source_value = "META"
        source_value = source_value[:50]

        imported_leads.append({
            "first_name": first_name if first_name else None,
            "last_name": last_name if last_name else None,
            "name": name,
            "phone": phone,
            "whatsapp_number": whatsapp_number if whatsapp_number else None,
            "email": email if email else None,
            "company": company if company else None,
            "company_size": company_size if company_size else None,
            "designation": designation if designation else None,
            "industry": industry if industry else None,
            "website": website if website else None,
            "city": city if city else None,
            "state": state if state else None,
            "country": country if country else "India",
            "location": location if location else None,
            "campaign_name": campaign_name if campaign_name else None,
            "status": status,
            "priority": priority,
            "rating": rating,
            "requirement_notes": requirement_notes if requirement_notes else None,
            "assigned_to": assigned_to_id,
            "source": source_value
        })

    return {
        "total_rows": total_count,
        "imported": len(imported_leads),
        "duplicates": duplicate_count,
        "invalid": invalid_count,
        "valid_leads": imported_leads,
        "invalid_rows": invalid_rows
    }

def generate_error_rows_excel(invalid_rows: list) -> io.BytesIO:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Import Errors"

    headers = ["Row Index", "Name", "Phone", "Email", "Error Reason"]
    ws.append(headers)

    header_fill = PatternFill(start_color="DC2626", end_color="DC2626", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")

    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_num)].width = 22

    for r in invalid_rows:
        ws.append([r.get("row_index"), r.get("name"), r.get("phone"), r.get("email"), r.get("reason")])

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream
