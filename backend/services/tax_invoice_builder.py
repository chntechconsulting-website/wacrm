import io
import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Register standard Arial fonts if available on Windows, else fallback to Helvetica
FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_ITALIC = "Helvetica-Oblique"
FONT_BOLD_ITALIC = "Helvetica-BoldOblique"

try:
    if os.path.exists(r"C:\Windows\Fonts\arial.ttf"):
        pdfmetrics.registerFont(TTFont("CustomArial", r"C:\Windows\Fonts\arial.ttf"))
        FONT_REGULAR = "CustomArial"
    if os.path.exists(r"C:\Windows\Fonts\arialbd.ttf"):
        pdfmetrics.registerFont(TTFont("CustomArial-Bold", r"C:\Windows\Fonts\arialbd.ttf"))
        FONT_BOLD = "CustomArial-Bold"
    if os.path.exists(r"C:\Windows\Fonts\ariali.ttf"):
        pdfmetrics.registerFont(TTFont("CustomArial-Italic", r"C:\Windows\Fonts\ariali.ttf"))
        FONT_ITALIC = "CustomArial-Italic"
    if os.path.exists(r"C:\Windows\Fonts\arialbi.ttf"):
        pdfmetrics.registerFont(TTFont("CustomArial-BoldItalic", r"C:\Windows\Fonts\arialbi.ttf"))
        FONT_BOLD_ITALIC = "CustomArial-BoldItalic"
except Exception:
    pass

CHN_COMPANY_INFO = {
    "legal_name": "CHN TECHNOLOGIES PVT LTD",
    "address_ho": "NO: 28, 4th Main Road,CIT Nagar,\nChennai - 600035",
    "address_branch": "Door No.1650, 2nd Floor\nAAA Towers,Avinashi Rd, Near\nHope College, Coimbatore - 641004",
    "gstin": "33AAJCC3705A1ZC",
    "state_name": "Tamil Nadu",
    "state_code": "33",
    "contact": "9884450030 / 7010203031",
    "email": "info@chnindia.com",
    "bank_name": "Axis Bank - 921020014696411",
    "account_holder": "CHN TECHNOLOGIES PVT LTD",
    "account_number": "921020014696411",
    "ifsc": "UTIB0003702"
}

def number_to_indian_words_tax(num):
    num = int(round(num or 0))
    if num == 0:
        return "INR Zero Only"
    units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
             "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def two_digits(n):
        if n < 20:
            return units[n]
        return tens[n // 10] + ((" " + units[n % 10]) if n % 10 != 0 else "")

    def three_digits(n):
        h = n // 100
        rem = n % 100
        res = ""
        if h > 0:
            res += units[h] + " Hundred"
        if rem > 0:
            res += (" " if res else "") + two_digits(rem)
        return res

    parts = []
    crore = num // 10000000
    num %= 10000000
    lakh = num // 100000
    num %= 100000
    thousand = num // 1000
    rem = num % 1000
    if crore > 0:
        parts.append(two_digits(crore) + " Crore")
    if lakh > 0:
        parts.append(two_digits(lakh) + " Lakh")
    if thousand > 0:
        parts.append(two_digits(thousand) + " Thousand")
    if rem > 0:
        parts.append(three_digits(rem))
    return "INR " + " ".join(parts).strip() + " Only"

def _fmt_money(val):
    v = float(val or 0.0)
    return f"{v:,.2f}"

def build_tax_invoice_model_pdf(data: dict) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    page_w, page_h = A4 # 595.27 x 841.89

    # Boundary coordinates matching model exactly:
    left = 32.0
    right = 550.0
    top = 802.0
    bottom = 31.0
    width = right - left
    mid_x = 280.0
    mid_sub_x = 415.0

    # Draw Top Document Title (Above the outer box)
    c.setFont(FONT_BOLD, 10.5)
    c.drawCentredString(page_w / 2.0, top + 14, "Tax Invoice")

    # Draw Outer Border Box
    c.setLineWidth(0.6)
    c.setStrokeColor(colors.black)
    c.rect(left, bottom, width, top - bottom)

    # -------------------------------------------------------------
    # 1. TOP HEADER SECTION (y: 585 to 802)
    # -------------------------------------------------------------
    c.line(mid_x, 585.0, mid_x, top)

    # Left: Company Logo (WAHRMS logo by default as requested)
    comp_id = (data.get("companyId") or data.get("company_id") or "").lower()
    if comp_id == "chn-tech" or "chn" in (data.get("company_name_select") or "").lower():
        logo_path = os.path.join(os.path.dirname(__file__), "chn_logo_actual.png")
    else:
        logo_path = os.path.join(os.path.dirname(__file__), "wahrms-logo.png")
        if not os.path.exists(logo_path):
            logo_path = os.path.join(os.path.dirname(__file__), "chn_logo_actual.png")

    if os.path.exists(logo_path):
        if "wahrms" in logo_path.lower():
            # WAHRMS logo has 950x607 aspect ratio (1.56:1)
            c.drawImage(logo_path, left + 4, top - 62, width=56, height=36, preserveAspectRatio=True, mask='auto')
        else:
            c.drawImage(logo_path, left + 4, top - 68, width=54, height=54, preserveAspectRatio=True, mask='auto')

    # Company Text beside logo
    comp_x = left + 64
    c.setFont(FONT_BOLD, 8.5)
    c.drawString(comp_x, top - 12, CHN_COMPANY_INFO["legal_name"])
    c.setFont(FONT_REGULAR, 5.5)
    c.drawString(comp_x, top - 20, "NO: 28, 4th Main Road,CIT Nagar,")
    c.drawString(comp_x, top - 27, "Chennai - 600035")
    c.drawString(comp_x, top - 34, "Branch Addres :Door No.1650, 2nd Floor")
    c.drawString(comp_x, top - 41, "AAA Towers,Avinashi Rd, Near")
    c.drawString(comp_x, top - 48, "Hope College, Coimbatore - 641004")
    c.drawString(comp_x, top - 55, f"GSTIN/UIN: {CHN_COMPANY_INFO['gstin']}")
    c.drawString(comp_x, top - 62, f"State Name :  {CHN_COMPANY_INFO['state_name']}, Code : {CHN_COMPANY_INFO['state_code']}")
    c.drawString(comp_x, top - 69, f"Contact : {CHN_COMPANY_INFO['contact']}")
    c.drawString(comp_x, top - 76, f"E-Mail : {CHN_COMPANY_INFO['email']}")

    # Horizontal dividing lines for Consignee / Buyer
    c.line(left, 722.0, mid_x, 722.0) # Line above Consignee
    c.line(left, 650.0, mid_x, 650.0) # Line above Buyer
    c.line(left, 585.0, right, 585.0) # Line below Header/Parties block

    # Consignee Details (Ship to)
    c.setFont(FONT_REGULAR, 7.5)
    c.drawString(left + 3, 714.0, "Consignee (Ship to)")
    c.setFont(FONT_BOLD, 8.2)
    cust_name = data.get("company_name") or data.get("customer_name") or "Valued Client"
    c.drawString(left + 3, 703.0, cust_name[:45])
    c.setFont(FONT_REGULAR, 7.5)
    addr = data.get("address") or "Chennai - 600041"
    addr_lines = [l.strip() for l in addr.split(",") if l.strip()]
    addr_line1 = ", ".join(addr_lines[:3]) if addr_lines else addr
    addr_line2 = ", ".join(addr_lines[3:]) if len(addr_lines) > 3 else ""
    c.drawString(left + 3, 693.0, addr_line1[:50])
    if addr_line2:
        c.drawString(left + 3, 684.0, addr_line2[:50])
    c.drawString(left + 3, 672.0, f"GSTIN/UIN : {data.get('gstin') or '33AAFCP5736J1Z9'}")
    c.drawString(left + 3, 661.0, f"State Name : {data.get('state') or 'Tamil Nadu'}, Code : {data.get('state_code') or '33'}")

    # Buyer Details (Bill to)
    c.setFont(FONT_REGULAR, 7.5)
    c.drawString(left + 3, 642.0, "Buyer (Bill to)")
    c.setFont(FONT_BOLD, 8.2)
    c.drawString(left + 3, 631.0, cust_name[:45])
    c.setFont(FONT_REGULAR, 7.5)
    c.drawString(left + 3, 621.0, addr_line1[:50])
    if addr_line2:
        c.drawString(left + 3, 612.0, addr_line2[:50])
    c.drawString(left + 3, 600.0, f"GSTIN/UIN : {data.get('gstin') or '33AAFCP5736J1Z9'}")
    c.drawString(left + 3, 589.0, f"State Name : {data.get('state') or 'Tamil Nadu'}, Code : {data.get('state_code') or '33'}")

    # Right: Metadata Grid (y: 585 to 802)
    meta_y_lines = [779.5, 757.0, 734.4, 712.0, 689.5, 667.0]
    for my in meta_y_lines:
        c.line(mid_x, my, right, my)

    # Vertical line dividing the 2 columns of metadata down to y=667.0
    c.line(mid_sub_x, 667.0, mid_sub_x, top)

    # Format Date
    issue_date = data.get("issue_date")
    if isinstance(issue_date, datetime):
        date_str = issue_date.strftime("%d-%b-%y")
    else:
        date_str = str(issue_date)[:10] if issue_date else datetime.utcnow().strftime("%d-%b-%y")

    doc_num = data.get("doc_number") or data.get("number") or "CHN/26-27/151"

    # Row 1: Invoice No. | Dated
    c.setFont(FONT_REGULAR, 7.0)
    c.drawString(mid_x + 3, 794.6, "Invoice No.")
    c.drawString(mid_sub_x + 3, 794.6, "Dated")
    c.setFont(FONT_BOLD, 8.2)
    c.drawString(mid_x + 3, 783.0, str(doc_num))
    c.drawString(mid_sub_x + 3, 783.0, date_str)

    # Row 2: Delivery Note | Mode/Terms of Payment
    c.setFont(FONT_REGULAR, 7.0)
    c.drawString(mid_x + 3, 772.0, "Delivery Note")
    c.drawString(mid_sub_x + 3, 772.0, "Mode/Terms of Payment")

    # Row 3: Reference No. & Date. | Other References
    c.setFont(FONT_REGULAR, 7.0)
    c.drawString(mid_x + 3, 749.5, "Reference No. & Date.")
    c.drawString(mid_sub_x + 3, 749.5, "Other References")
    c.setFont(FONT_BOLD, 8.2)
    c.drawString(mid_x + 3, 737.0, f"{doc_num} dt. {date_str}"[:30])

    # Row 4: Buyer's Order No. | Dated
    c.setFont(FONT_REGULAR, 7.0)
    c.drawString(mid_x + 3, 727.0, "Buyer's Order No.")
    c.drawString(mid_sub_x + 3, 727.0, "Dated")

    # Row 5: Dispatch Doc No. | Delivery Note Date
    c.setFont(FONT_REGULAR, 7.0)
    c.drawString(mid_x + 3, 704.4, "Dispatch Doc No.")
    c.drawString(mid_sub_x + 3, 704.4, "Delivery Note Date")

    # Row 6: Dispatched through | Destination
    c.setFont(FONT_REGULAR, 7.0)
    c.drawString(mid_x + 3, 681.8, "Dispatched through")
    c.drawString(mid_sub_x + 3, 681.8, "Destination")

    # Row 7: Terms of Delivery
    c.setFont(FONT_REGULAR, 7.0)
    c.drawString(mid_x + 3, 657.6, "Terms of Delivery")

    # -------------------------------------------------------------
    # 2. LINE ITEMS TABLE (y: 228 to 585)
    # -------------------------------------------------------------
    table_top = 585.0
    header_bottom = 560.0
    table_bottom = 228.0

    c.line(left, header_bottom, right, header_bottom)
    c.line(left, table_bottom, right, table_bottom)

    # Column x-coordinates:
    col_sl = 46.0
    col_desc = 315.0
    col_hsn = 363.0
    col_qty = 411.0
    col_rate = 459.0
    col_per = 480.0

    # Draw vertical grid lines
    for cx in [col_sl, col_desc, col_hsn, col_qty, col_rate, col_per]:
        c.line(cx, table_bottom, cx, table_top)

    # Header Titles
    c.setFont(FONT_BOLD, 7.5)
    c.drawString(left + 2, 575.0, "Sl")
    c.drawString(left + 1, 566.0, "No.")
    c.drawCentredString((col_sl + col_desc) / 2.0, 574.0, "Description of Goods and Services")
    c.drawCentredString((col_desc + col_hsn) / 2.0, 569.0, "HSN/SAC")
    c.drawCentredString((col_hsn + col_qty) / 2.0, 569.0, "Quantity")
    c.drawCentredString((col_qty + col_rate) / 2.0, 569.0, "Rate")
    c.drawCentredString((col_rate + col_per) / 2.0, 569.0, "per")
    c.drawCentredString((col_per + right) / 2.0, 569.0, "Amount")

    # Render Line Items
    items = data.get("line_items") or []
    cur_y = 550.0
    total_qty_num = 0

    for idx, item in enumerate(items, start=1):
        name = item.get("description") or item.get("name") or "Product/Service"
        hsn = item.get("hsn") or item.get("hsn_sac") or "85437099"
        qty = float(item.get("quantity") or item.get("qty") or 1)
        rate = float(item.get("unit_price") or item.get("rate") or 0.0)
        amt = float(item.get("amount") or (qty * rate))
        total_qty_num += int(qty)

        c.setFont(FONT_REGULAR, 7.8)
        c.drawString(left + 3, cur_y, str(idx))
        c.setFont(FONT_BOLD, 7.8)
        c.drawString(col_sl + 3, cur_y, name[:48])
        c.setFont(FONT_REGULAR, 7.8)
        c.drawCentredString((col_desc + col_hsn) / 2.0, cur_y, str(hsn))
        c.setFont(FONT_BOLD, 7.8)
        c.drawRightString(col_qty - 4, cur_y, f"{int(qty)} NOS" if qty == int(qty) else f"{qty} NOS")
        c.setFont(FONT_REGULAR, 7.8)
        c.drawRightString(col_rate - 4, cur_y, _fmt_money(rate))
        c.drawCentredString((col_rate + col_per) / 2.0, cur_y, "NOS")
        c.setFont(FONT_BOLD, 7.8)
        c.drawRightString(right - 4, cur_y, _fmt_money(amt))

        # Check secondary description / sub-details
        sub_desc = item.get("sub_description") or item.get("details")
        if sub_desc:
            cur_y -= 10.0
            c.setFont(FONT_ITALIC, 7.0)
            c.drawString(col_sl + 6, cur_y, str(sub_desc)[:55])

        cur_y -= 18.0

    subtotal_val = float(data.get("subtotal") or 0.0)
    cgst_val = float(data.get("cgst") or 0.0)
    sgst_val = float(data.get("sgst") or 0.0)
    igst_val = float(data.get("igst") or 0.0)
    grand_total_val = float(data.get("grand_total") or (subtotal_val + cgst_val + sgst_val + igst_val))

    # Output taxes inside line item section
    cur_y = max(cur_y, 495.0)
    c.line(col_per, cur_y + 12, right, cur_y + 12)
    c.setFont(FONT_BOLD, 8.2)
    c.drawRightString(right - 4, cur_y + 1, _fmt_money(subtotal_val))

    cur_y -= 14.0
    if igst_val > 0:
        c.setFont(FONT_BOLD, 7.8)
        c.drawRightString(col_desc - 6, cur_y, "Output IGST@ 18%")
        c.drawCentredString((col_rate + col_per) / 2.0, cur_y, "18 %")
        c.drawRightString(right - 4, cur_y, _fmt_money(igst_val))
    else:
        c.setFont(FONT_BOLD, 7.8)
        c.drawRightString(col_desc - 6, cur_y, "Output CGST@ 9%")
        c.drawCentredString((col_rate + col_per) / 2.0, cur_y, "9 %")
        c.drawRightString(right - 4, cur_y, _fmt_money(cgst_val))
        cur_y -= 11.0
        c.drawRightString(col_desc - 6, cur_y, "Output SGST@ 9%")
        c.drawCentredString((col_rate + col_per) / 2.0, cur_y, "9 %")
        c.drawRightString(right - 4, cur_y, _fmt_money(sgst_val))

    # Total Row at table_bottom (y: 228 to 242)
    c.setFont(FONT_BOLD, 7.8)
    c.drawString(col_desc - 24, 233.0, "Total")
    c.drawRightString(col_qty - 4, 233.0, f"{total_qty_num} NOS")
    c.setFont(FONT_BOLD, 9.0)
    c.drawRightString(right - 4, 233.0, f"\u20B9 {_fmt_money(grand_total_val)}")

    # -------------------------------------------------------------
    # 3. AMOUNT IN WORDS & E. & O.E. (y: 204 to 228)
    # -------------------------------------------------------------
    c.line(left, 204.0, right, 204.0)
    c.setFont(FONT_REGULAR, 7.2)
    c.drawString(left + 3, 220.0, "Amount Chargeable (in words)")
    c.setFont(FONT_ITALIC, 7.2)
    c.drawRightString(right - 4, 220.0, "E. & O.E")

    c.setFont(FONT_BOLD, 8.2)
    words_str = number_to_indian_words_tax(grand_total_val)
    c.drawString(left + 3, 209.0, words_str)

    # -------------------------------------------------------------
    # 4. STATUTORY HSN/SAC TAX SUMMARY TABLE (y: 156 to 204)
    # -------------------------------------------------------------
    hsn_box_top = 204.0
    hsn_hdr_sub = 194.0
    hsn_hdr_bot = 184.0
    hsn_box_bot = 156.0

    c.line(left, hsn_hdr_bot, right, hsn_hdr_bot)
    c.line(left, hsn_box_bot, right, hsn_box_bot)

    hsn_c1 = 272.0
    hsn_c2 = 326.0
    hsn_c3_rate = 358.0
    hsn_c3_amt = 414.0
    hsn_c4_rate = 446.0
    hsn_c4_amt = 498.0

    # Vertical lines in HSN table
    for hx in [hsn_c1, hsn_c2, hsn_c3_amt, hsn_c4_amt]:
        c.line(hx, hsn_box_bot, hx, hsn_box_top)
    for hx in [hsn_c3_rate, hsn_c4_rate]:
        c.line(hx, hsn_box_bot, hx, hsn_hdr_sub)

    c.line(hsn_c2, hsn_hdr_sub, hsn_c4_amt, hsn_hdr_sub)

    # HSN Table Headers
    c.setFont(FONT_BOLD, 7.2)
    c.drawCentredString((left + hsn_c1) / 2.0, 191.0, "HSN/SAC")
    c.drawCentredString((hsn_c1 + hsn_c2) / 2.0, 195.0, "Taxable")
    c.drawCentredString((hsn_c1 + hsn_c2) / 2.0, 187.0, "Value")

    c.drawCentredString((hsn_c2 + hsn_c3_amt) / 2.0, 196.0, "CGST")
    c.drawString(hsn_c2 + 6, 187.0, "Rate")
    c.drawCentredString((hsn_c3_rate + hsn_c3_amt) / 2.0, 187.0, "Amount")

    c.drawCentredString((hsn_c3_amt + hsn_c4_amt) / 2.0, 196.0, "SGST/UTGST")
    c.drawString(hsn_c3_amt + 6, 187.0, "Rate")
    c.drawCentredString((hsn_c4_rate + hsn_c4_amt) / 2.0, 187.0, "Amount")

    c.drawCentredString((hsn_c4_amt + right) / 2.0, 195.0, "Total")
    c.drawCentredString((hsn_c4_amt + right) / 2.0, 187.0, "Tax Amount")

    # Render HSN Summary Lines
    hsn_map = {}
    for item in items:
        h = str(item.get("hsn") or item.get("hsn_sac") or "85437099")
        q = float(item.get("quantity") or item.get("qty") or 1)
        r = float(item.get("unit_price") or item.get("rate") or 0.0)
        a = float(item.get("amount") or (q * r))
        hsn_map[h] = hsn_map.get(h, 0.0) + a

    hsn_y = 175.0
    for h_code, h_val in hsn_map.items():
        c_tax = h_val * 0.09
        s_tax = h_val * 0.09
        tot_tax = c_tax + s_tax
        c.setFont(FONT_REGULAR, 7.2)
        c.drawString(left + 4, hsn_y, h_code)
        c.drawRightString(hsn_c2 - 4, hsn_y, _fmt_money(h_val))
        c.drawCentredString((hsn_c2 + hsn_c3_rate) / 2.0, hsn_y, "9%")
        c.drawRightString(hsn_c3_amt - 4, hsn_y, _fmt_money(c_tax))
        c.drawCentredString((hsn_c3_amt + hsn_c4_rate) / 2.0, hsn_y, "9%")
        c.drawRightString(hsn_c4_amt - 4, hsn_y, _fmt_money(s_tax))
        c.drawRightString(right - 4, hsn_y, _fmt_money(tot_tax))
        hsn_y -= 9.0

    # Total row of HSN Table
    c.line(left, 164.0, right, 164.0)
    c.setFont(FONT_BOLD, 7.2)
    c.drawString(hsn_c1 - 25, 157.0, "Total")
    c.drawRightString(hsn_c2 - 4, 157.0, _fmt_money(subtotal_val))
    c.drawRightString(hsn_c3_amt - 4, 157.0, _fmt_money(cgst_val))
    c.drawRightString(hsn_c4_amt - 4, 157.0, _fmt_money(sgst_val))
    c.drawRightString(right - 4, 157.0, _fmt_money(cgst_val + sgst_val + igst_val))

    # -------------------------------------------------------------
    # 5. TAX AMOUNT IN WORDS (y: 140 to 156)
    # -------------------------------------------------------------
    c.line(left, 140.0, right, 140.0)
    c.setFont(FONT_REGULAR, 7.2)
    c.drawString(left + 3, 146.0, "Tax Amount (in words)  :")
    c.setFont(FONT_BOLD, 7.8)
    c.drawString(left + 95, 146.0, number_to_indian_words_tax(cgst_val + sgst_val + igst_val))

    # -------------------------------------------------------------
    # 6. BOTTOM SECTION: REMARKS, DECLARATION, BANK & SIGNATURES
    # -------------------------------------------------------------
    bot_mid_x = 292.0
    c.line(bot_mid_x, bottom, bot_mid_x, 140.0)

    # Left: Remarks
    c.setFont(FONT_ITALIC, 7.2)
    c.drawString(left + 3, 93.0, "Remarks:")
    c.setFont(FONT_REGULAR, 7.2)
    rem_text = data.get("notes") or f"Being towards Sale of {items[0].get('name', 'Goods and Services') if items else 'Hardware and Networking'}"
    c.drawString(left + 3, 84.0, rem_text[:60])
    if len(rem_text) > 60:
        c.drawString(left + 3, 75.0, rem_text[60:120])

    # Left: Declaration
    c.setFont(FONT_BOLD, 7.2)
    c.drawString(left + 3, 62.0, "Declaration")
    c.setFont(FONT_REGULAR, 6.8)
    c.drawString(left + 3, 52.0, "We declare that this invoice shows the actual price of the goods")
    c.drawString(left + 3, 44.0, "described and that all particulars are true and correct.")

    # Right: Company Bank Details (y: 69 to 140)
    c.setFont(FONT_BOLD, 7.2)
    c.drawString(bot_mid_x + 4, 110.0, "Company's Bank Details")

    c.setFont(FONT_REGULAR, 7.0)
    c.drawString(bot_mid_x + 4, 100.0, "A/c Holder's Name :")
    c.setFont(FONT_BOLD, 7.0)
    c.drawString(bot_mid_x + 85, 100.0, CHN_COMPANY_INFO['account_holder'])

    c.setFont(FONT_REGULAR, 7.0)
    c.drawString(bot_mid_x + 4, 91.0, "Bank Name          :")
    c.setFont(FONT_BOLD, 7.0)
    c.drawString(bot_mid_x + 85, 91.0, CHN_COMPANY_INFO['bank_name'])

    c.setFont(FONT_REGULAR, 7.0)
    c.drawString(bot_mid_x + 4, 82.0, "A/c No.               :")
    c.setFont(FONT_BOLD, 7.0)
    c.drawString(bot_mid_x + 85, 82.0, CHN_COMPANY_INFO['account_number'])

    c.setFont(FONT_REGULAR, 7.0)
    c.drawString(bot_mid_x + 4, 73.0, "Branch & IFS Code:")
    c.setFont(FONT_BOLD, 7.0)
    c.drawString(bot_mid_x + 85, 73.0, CHN_COMPANY_INFO['ifsc'])

    # Right: Signature Block (y: bottom to 69)
    c.line(bot_mid_x, 69.0, right, 69.0)
    c.setFont(FONT_BOLD, 7.5)
    c.drawRightString(right - 6, 60.0, f"for {CHN_COMPANY_INFO['legal_name']}")

    c.setFont(FONT_REGULAR, 7.2)
    c.drawString(bot_mid_x + 4, 35.0, "Prepared by")
    c.drawCentredString((bot_mid_x + right) / 2.0, 35.0, "Verified by")
    c.drawRightString(right - 6, 35.0, "Authorised Signatory")

    # Bottom Footer outside box
    c.setFont(FONT_REGULAR, 7.0)
    c.drawCentredString(page_w / 2.0, bottom - 13, "This is a Computer Generated Invoice")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()
