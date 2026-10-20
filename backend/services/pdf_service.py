"""
Dedicated PDF Generation Service for CRM Quotations and Proforma Invoices.
Builds separate, pixel-perfect PDF documents using ReportLab.
- Quotation PDF: Signature Red theme (#dc2626), Quotation layout, white text on red table header.
- Proforma Invoice PDF: Signature Red theme (#dc2626), Proforma layout, payment bank details, dedicated Scan & Pay page.
"""

import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

# Colors
BRAND_RED_600 = colors.HexColor("#dc2626")
BRAND_RED_700 = colors.HexColor("#b91c1c")
BRAND_RED_50 = colors.HexColor("#fef2f2")
BRAND_TEAL_600 = colors.HexColor("#0f766e")
BRAND_TEAL_50 = colors.HexColor("#f0fdfa")
INK_900 = colors.HexColor("#0f172a")
INK_700 = colors.HexColor("#1e293b")
INK_500 = colors.HexColor("#475569")
INK_200 = colors.HexColor("#cbd5e1")
INK_100 = colors.HexColor("#e2e8f0")
INK_50 = colors.HexColor("#f8fafc")
WHITE = colors.white

COMPANY_INFO = {
    "legal_name": "CHN TECHNOLOGIES PVT LTD",
    "short_name": "WAHRMS",
    "gstin": "33AAJCC3705A1ZC",
    "pan": "AAJCC3705A",
    "address_line1": "No, 28 Fourth Main Road, CIT Nagar",
    "address_line2": "Chennai, Tamil Nadu 600035",
    "phone": "+91 84366 00600",
    "email": "info@chnindia.com",
    "bank_name": "AXIS BANK",
    "account_name": "CHN TECHNOLOGIES PRIVATE LIMITED",
    "account_number": "921020014696411",
    "ifsc": "UTIB0003702",
    "account_type": "Current"
}


def number_to_indian_words(num):
    """Convert number to Indian currency words format."""
    num = int(round(num or 0))
    if num == 0:
        return "Rupees Zero Only"
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
            res += (" and " if res else "") + two_digits(rem)
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
    return "Rupees " + " ".join(parts) + " Only"


class NumberedCanvas(canvas.Canvas):
    """Canvas that computes total page count dynamically and prints footer."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_footer(num_pages)
            super().showPage()
        super().save()

    def draw_footer(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 7.5)
        self.setFillColor(INK_500)
        footer_text = f"For any enquiry, reach out via email at {COMPANY_INFO['email']}, call on {COMPANY_INFO['phone']}"
        self.drawString(28 * mm, 12 * mm, footer_text)
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(A4[0] - 28 * mm, 12 * mm, page_str)
        self.restoreState()


def _format_inr(val):
    v = float(val or 0.0)
    return f"{v:,.2f}"


def build_common_data(doc):
    """Extract standard attributes from a Quotation SQLAlchemy model or dictionary."""
    if isinstance(doc, dict):
        d = doc
        return {
            "id": d.get("id"),
            "doc_number": d.get("doc_number") or d.get("number") or "DOC",
            "doc_type": (d.get("doc_type") or d.get("docType") or "quotation").lower(),
            "customer_name": d.get("customer_name") or d.get("customerName") or "Valued Client",
            "company_name": d.get("company_name") or d.get("companyName") or "",
            "phone": d.get("phone") or "",
            "email": d.get("email") or "",
            "address": d.get("address") or "",
            "state": d.get("state") or "Tamil Nadu",
            "state_code": d.get("state_code") or d.get("stateCode") or "33",
            "gstin": d.get("gstin") or "",
            "pan": d.get("pan") or (d.get("gstin", "")[2:12] if len(d.get("gstin", "")) == 15 else ""),
            "tax_mode": d.get("tax_mode") or d.get("taxMode") or "intra",
            "subtotal": float(d.get("subtotal") or 0.0),
            "cgst": float(d.get("cgst") or 0.0),
            "sgst": float(d.get("sgst") or 0.0),
            "igst": float(d.get("igst") or 0.0),
            "tax_total": float(d.get("tax_total") or d.get("taxTotal") or 0.0),
            "round_off": float(d.get("round_off") or d.get("roundOff") or 0.0),
            "grand_total": float(d.get("grand_total") or d.get("grandTotal") or 0.0),
            "line_items": d.get("line_items") or d.get("lineItems") or [],
            "terms": d.get("terms_and_conditions") or d.get("terms") or "",
            "notes": d.get("notes") or "",
            "prepared_by": d.get("prepared_by") or d.get("preparedBy") or "Authorized Signatory",
            "issue_date": d.get("issue_date") or datetime.utcnow()
        }
    else:
        cgst_val = float(doc.cgst or 0.0)
        sgst_val = float(doc.sgst or 0.0)
        igst_val = float(doc.igst or 0.0)
        tax_mode_val = doc.tax_mode or ("intra" if str(doc.state_code or "").strip() == "33" else "inter")
        gstin_val = (doc.gstin or "").upper().strip()
        pan_val = gstin_val[2:12] if len(gstin_val) == 15 else ""

        return {
            "id": doc.id,
            "doc_number": doc.doc_number or "DOC",
            "doc_type": (doc.doc_type or "quotation").lower(),
            "customer_name": doc.customer_name or "Valued Client",
            "company_name": doc.company_name or "",
            "phone": doc.phone or "",
            "email": doc.email or "",
            "address": doc.address or "",
            "state": doc.state or "Tamil Nadu",
            "state_code": doc.state_code or "33",
            "gstin": gstin_val,
            "pan": pan_val,
            "tax_mode": tax_mode_val,
            "subtotal": float(doc.subtotal or 0.0),
            "cgst": cgst_val,
            "sgst": sgst_val,
            "igst": igst_val,
            "tax_total": float(doc.tax_total or (cgst_val + sgst_val + igst_val)),
            "round_off": float(doc.round_off or 0.0),
            "grand_total": float(doc.grand_total or 0.0),
            "line_items": doc.line_items or [],
            "terms": doc.terms_and_conditions or "",
            "notes": doc.notes or "",
            "prepared_by": doc.prepared_by or "Authorized Signatory",
            "issue_date": doc.issue_date or datetime.utcnow()
        }


def generate_quotation_pdf(doc_or_model) -> bytes:
    """Generates the official Quotation PDF with signature Red branding."""
    data = build_common_data(doc_or_model)
    data["doc_type"] = "quotation"
    return _build_pdf_stream(data, is_proforma=False)


def generate_proforma_pdf(doc_or_model) -> bytes:
    """Generates the official Proforma Invoice PDF with signature Red branding and Scan & Pay."""
    data = build_common_data(doc_or_model)
    data["doc_type"] = "proforma"
    return _build_pdf_stream(data, doc_type="proforma")


def generate_tax_invoice_pdf(doc_or_model) -> bytes:
    """
    Generates the official statutory Tax Invoice PDF issued exclusively by Finance.
    Matches the exact CHN TECHNOLOGIES PVT LTD boxed layout model:
    - Boxed full-page grid layout
    - CHN logo and registered + branch addresses
    - 2-column metadata table (Invoice No, Dated, Reference, Delivery Note, etc.)
    - Consignee (Ship to) and Buyer (Bill to) blocks
    - Line items with HSN/SAC, NOS, Embedded Output CGST/SGST taxes, and Total
    - Amount Chargeable in words & E. & O.E
    - Statutory HSN/SAC tax breakdown grid
    - Bank Details (Axis Bank), Declaration & Signatures
    - 'This is a Computer Generated Invoice' footer
    """
    from services.tax_invoice_builder import build_tax_invoice_model_pdf
    data = build_common_data(doc_or_model)
    data["doc_type"] = "invoice"
    return build_tax_invoice_model_pdf(data)


def _build_pdf_stream(data: dict, is_proforma: bool = False, doc_type: str = "quotation") -> bytes:
    if doc_type == "quotation" and is_proforma:
        doc_type = "proforma"
    elif not doc_type:
        doc_type = data.get("doc_type", "quotation").lower()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=18 * mm
    )

    styles = getSampleStyleSheet()

    # Custom styles
    is_invoice = (doc_type == "invoice")
    is_proforma = (doc_type == "proforma")

    # Invoices use statutory deep navy/slate (#1e3a8a), while Quotes & Proformas use signature red (#dc2626)
    primary_color = colors.HexColor("#1e3a8a") if is_invoice else BRAND_RED_600
    card_bg_right = colors.HexColor("#eff6ff") if is_invoice else BRAND_RED_50
    grand_bg = colors.HexColor("#eff6ff") if is_invoice else BRAND_RED_50

    if is_invoice:
        doc_title_text = "TAX INVOICE"
    elif is_proforma:
        doc_title_text = "PROFORMA INVOICE"
    else:
        doc_title_text = "QUOTATION"

    style_title = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=primary_color,
        alignment=2 # Right
    )
    style_subtitle = ParagraphStyle(
        "DocSubTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=INK_500,
        alignment=2
    )
    style_doc_num = ParagraphStyle(
        "DocNum",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        textColor=INK_900,
        alignment=2
    )
    style_meta_label = ParagraphStyle(
        "MetaLabel",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=INK_500,
        alignment=2
    )
    style_meta_val = ParagraphStyle(
        "MetaVal",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        textColor=INK_900,
        alignment=2
    )
    style_company_head = ParagraphStyle(
        "CompanyHead",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=primary_color
    )
    style_panel_title = ParagraphStyle(
        "PanelTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        textColor=primary_color
    )
    style_panel_name = ParagraphStyle(
        "PanelName",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=13,
        textColor=INK_900
    )
    style_panel_body = ParagraphStyle(
        "PanelBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=INK_700
    )
    style_th = ParagraphStyle(
        "TH",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=WHITE,
        alignment=1
    )
    style_td = ParagraphStyle(
        "TD",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=INK_700
    )
    style_td_desc = ParagraphStyle(
        "TDDesc",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.8,
        leading=9,
        textColor=INK_500
    )
    style_td_num = ParagraphStyle(
        "TDNum",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=INK_900,
        alignment=2
    )
    style_tot_label = ParagraphStyle(
        "TotLabel",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=INK_700
    )
    style_tot_val = ParagraphStyle(
        "TotVal",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        textColor=INK_900,
        alignment=2
    )
    style_grand_label = ParagraphStyle(
        "GrandLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=13,
        textColor=primary_color
    )
    style_grand_val = ParagraphStyle(
        "GrandVal",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        textColor=primary_color,
        alignment=2
    )
    style_notes = ParagraphStyle(
        "Notes",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=11,
        textColor=INK_700
    )

    story = []

    # 1. Header Section (2 Columns: Company on left, Doc Info on right)
    company_left = [
        Spacer(1, 2 * mm),
        Paragraph("WA!HRMS", style_company_head),
        Paragraph("<font size=7 color='#64748b'>PEOPLE AT THE HEART</font>", style_panel_body)
    ]

    issue_date_str = data["issue_date"].strftime("%b %d, %Y") if isinstance(data["issue_date"], datetime) else str(data["issue_date"])
    valid_date_str = (datetime.utcnow().strftime("%b %d, %Y"))

    meta_table_data = [
        [Paragraph("Invoice Date" if is_invoice else "Issue Date", style_meta_label), Paragraph(issue_date_str, style_meta_val)],
        [Paragraph("Due Date" if (is_proforma or is_invoice) else "Valid Till", style_meta_label), Paragraph(valid_date_str, style_meta_val)],
        [Paragraph("Place of Supply", style_meta_label), Paragraph(f"{data['state']} ({data['state_code']})", style_meta_val)],
        [Paragraph("Tax Mode", style_meta_label), Paragraph("Intra-state (CGST + SGST)" if data["tax_mode"] == "intra" else "Inter-state (IGST)", style_meta_val)],
        [Paragraph("Reverse Charge", style_meta_label), Paragraph("No", style_meta_val)] if is_invoice else [Paragraph("Prepared By", style_meta_label), Paragraph(data["prepared_by"], style_meta_val)]
    ]
    meta_table = Table(meta_table_data, colWidths=[28 * mm, 38 * mm])
    meta_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))

    header_right = [
        Paragraph(doc_title_text, style_title),
        Paragraph("ORIGINAL FOR RECIPIENT", style_subtitle) if is_invoice else Paragraph(data["doc_number"], style_doc_num),
        Paragraph(data["doc_number"], style_doc_num) if is_invoice else Spacer(1, 1 * mm),
        Spacer(1, 1 * mm),
        meta_table
    ]

    header_table = Table([[company_left, header_right]], colWidths=[90 * mm, 92 * mm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 2 * mm))

    # Divider Rule
    story.append(HRFlowable(width="100%", thickness=1.5, color=primary_color, spaceBefore=1, spaceAfter=3))

    # 2. Parties Block: ISSUED BY vs QUOTATION FOR / BILLED TO
    issued_by_content = [
        Paragraph("ISSUED BY", style_panel_title),
        Paragraph(COMPANY_INFO["legal_name"], style_panel_name),
        Paragraph(COMPANY_INFO["address_line1"] + "<br/>" + COMPANY_INFO["address_line2"], style_panel_body),
        Spacer(1, 1 * mm),
        Paragraph(f"GSTIN: {COMPANY_INFO['gstin']}", style_panel_body),
        Paragraph(f"PAN: {COMPANY_INFO['pan']}", style_panel_body),
        Paragraph(f"Email: {COMPANY_INFO['email']}", style_panel_body),
        Paragraph(f"Phone: {COMPANY_INFO['phone']}", style_panel_body),
    ]

    billed_to_label = "BILLED TO (RECIPIENT)" if is_invoice else ("BILLED TO" if is_proforma else "QUOTATION FOR")
    cust_co = data["company_name"]
    cust_nm = data["customer_name"]
    cust_display = cust_co if cust_co else cust_nm
    contact_line = f"Contact: {cust_nm}<br/>" if (cust_co and cust_nm) else ""
    addr_line = f"{data['address']}<br/>{data['state']} {data['state_code']}" if data["address"] else f"{data['state']}"

    billed_to_content = [
        Paragraph(billed_to_label, style_panel_title),
        Paragraph(cust_display, style_panel_name),
        Paragraph(contact_line + addr_line, style_panel_body),
        Spacer(1, 1 * mm),
    ]
    if data["gstin"]:
        billed_to_content.append(Paragraph(f"GSTIN: {data['gstin']}", style_panel_body))
    if data["pan"]:
        billed_to_content.append(Paragraph(f"PAN: {data['pan']}", style_panel_body))
    if data["email"]:
        billed_to_content.append(Paragraph(f"Email: {data['email']}", style_panel_body))
    if data["phone"]:
        billed_to_content.append(Paragraph(f"Phone: {data['phone']}", style_panel_body))

    parties_table = Table([[issued_by_content, billed_to_content]], colWidths=[89 * mm, 89 * mm])
    parties_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), INK_50),
        ('BACKGROUND', (1, 0), (1, 0), card_bg_right),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(parties_table)
    story.append(Spacer(1, 3 * mm))


    # 3. Items Table
    is_intra = (data["tax_mode"] == "intra")
    if is_intra:
        headers = ['#', 'Item / Description', 'HSN', 'Qty', 'Rate', 'Amount', 'Tax %', 'CGST', 'SGST', 'Total']
        col_widths = [8 * mm, 56 * mm, 14 * mm, 10 * mm, 16 * mm, 17 * mm, 12 * mm, 15 * mm, 15 * mm, 19 * mm]
    else:
        headers = ['#', 'Item / Description', 'HSN', 'Qty', 'Rate', 'Amount', 'Tax %', 'IGST', 'Total']
        col_widths = [8 * mm, 62 * mm, 15 * mm, 10 * mm, 18 * mm, 18 * mm, 13 * mm, 18 * mm, 20 * mm]

    table_data = [[Paragraph(f"<b>{h}</b>", style_th) for h in headers]]

    line_items = data["line_items"] or []
    if not line_items:
        line_items = [{
            "description": "WAHRMS Subscription Business Plan",
            "hsn": "998314",
            "qty": 1,
            "rate": data["subtotal"] or data["grand_total"],
            "discount": 0,
            "gstRate": 0.18
        }]

    for idx, item in enumerate(line_items, 1):
        desc = item.get("description", "Item")
        # Split multiline descriptions nicely
        desc_parts = [p.strip() for p in str(desc).split("\n") if p.strip()]
        desc_flowable = [Paragraph(f"<b>{desc_parts[0]}</b>", style_td)]
        for sub in desc_parts[1:]:
            desc_flowable.append(Paragraph(sub, style_td_desc))

        qty = float(item.get("qty") or 1)
        rate = float(item.get("rate") or 0)
        discount = float(item.get("discount") or 0)
        amt = max(0.0, qty * rate - discount)
        gst_r = float(item.get("gstRate", 0.18))
        tax_pct = f"{int(round(gst_r * 100))}%"
        tax_amt = amt * gst_r

        if is_intra:
            c_val = tax_amt / 2.0
            s_val = tax_amt / 2.0
            row = [
                Paragraph(str(idx), style_td),
                desc_flowable,
                Paragraph(str(item.get("hsn", "998314")), style_td),
                Paragraph(str(int(qty) if qty.is_integer() else qty), style_td_num),
                Paragraph(_format_inr(rate), style_td_num),
                Paragraph(_format_inr(amt), style_td_num),
                Paragraph(tax_pct, style_td),
                Paragraph(_format_inr(c_val), style_td_num),
                Paragraph(_format_inr(s_val), style_td_num),
                Paragraph(_format_inr(amt + tax_amt), style_td_num),
            ]
        else:
            row = [
                Paragraph(str(idx), style_td),
                desc_flowable,
                Paragraph(str(item.get("hsn", "998314")), style_td),
                Paragraph(str(int(qty) if qty.is_integer() else qty), style_td_num),
                Paragraph(_format_inr(rate), style_td_num),
                Paragraph(_format_inr(amt), style_td_num),
                Paragraph(tax_pct, style_td),
                Paragraph(_format_inr(tax_amt), style_td_num),
                Paragraph(_format_inr(amt + tax_amt), style_td_num),
            ]
        table_data.append(row)

    items_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, 0), 4),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
        ('TOPPADDING', (0, 1), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('LINEBELOW', (0, 1), (-1, -1), 0.5, INK_100),
        ('LINEBELOW', (0, 0), (-1, 0), 1, primary_color),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 2 * mm))

    # 4. Totals Block & Amount in Words
    totals_rows = [
        [Paragraph("Taxable Amount", style_tot_label), Paragraph(_format_inr(data["subtotal"]), style_tot_val)],
    ]
    if is_intra:
        totals_rows.append([Paragraph("CGST", style_tot_label), Paragraph(_format_inr(data["cgst"]), style_tot_val)])
        totals_rows.append([Paragraph("SGST", style_tot_label), Paragraph(_format_inr(data["sgst"]), style_tot_val)])
    else:
        totals_rows.append([Paragraph("IGST", style_tot_label), Paragraph(_format_inr(data["igst"]), style_tot_val)])

    if data["round_off"]:
        totals_rows.append([Paragraph("Round Off", style_tot_label), Paragraph(_format_inr(data["round_off"]), style_tot_val)])

    totals_rows.append([Paragraph("Total (INR)", style_grand_label), Paragraph(_format_inr(data["grand_total"]), style_grand_val)])

    tot_table = Table(totals_rows, colWidths=[42 * mm, 34 * mm])
    grand_bg = BRAND_RED_50
    tot_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, INK_100),
        ('BACKGROUND', (0, -1), (-1, -1), grand_bg),
    ]))

    words_text = number_to_indian_words(data["grand_total"])
    amount_words_p = Paragraph(f"<b>Amount in Words:</b> <i>{words_text}</i>", style_panel_body)

    summary_split_table = Table([[amount_words_p, tot_table]], colWidths=[102 * mm, 80 * mm])
    summary_split_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(summary_split_table)
    story.append(Spacer(1, 3 * mm))

    # 5. Terms & Payment / Bank Block
    if is_invoice:
        default_terms = (
            "1. Payment acknowledged/settled as per agreed commercial terms.\n"
            "2. Goods/Services supplied as per Purchase Order / Quotation specifications.\n"
            "3. Subject to Chennai jurisdiction. E. & O.E."
        )
    elif is_proforma:
        default_terms = (
            "1. 100% advance payment against Proforma Invoice.\n"
            "2. Service will be activated upon payment confirmation.\n"
            "3. Taxes applicable as per GST guidelines."
        )
    else:
        default_terms = (
            "1. Prices are subject to applicable GST as specified.\n"
            "2. Software activation and onboarding will begin upon PO confirmation and receipt of payment.\n"
            "3. Setup, training, and technical support will be provided as agreed.\n"
            "4. The client is responsible for providing accurate employee and payroll data and verifying payroll calculations.\n"
            "5. Timely subscription renewal is required to ensure uninterrupted software access.\n"
            "6. Customization and third-party integrations may incur additional charges.\n"
            "7. Confirmation of the purchase order constitutes acceptance of the quotation and these terms."
        )
    terms_txt = data["terms"] or default_terms
    terms_flowable = [
        Paragraph("<b>TERMS & CONDITIONS</b>", style_panel_title),
        Paragraph(terms_txt.replace("\n", "<br/>"), style_notes)
    ]

    if is_proforma:
        bank_flowable = [
            Paragraph("<b>PAYMENT DETAILS (AXIS BANK)</b>", style_panel_title),
            Paragraph(f"<b>A/c Name:</b> {COMPANY_INFO['account_name']}", style_panel_body),
            Paragraph(f"<b>Bank:</b> {COMPANY_INFO['bank_name']} &nbsp;&nbsp;|&nbsp;&nbsp; <b>A/c No:</b> {COMPANY_INFO['account_number']}", style_panel_body),
            Paragraph(f"<b>IFSC:</b> {COMPANY_INFO['ifsc']} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Type:</b> {COMPANY_INFO['account_type']}", style_panel_body),
            Spacer(1, 1 * mm),
            Paragraph("<font color='#dc2626'><b>* For UPI / QR Code payment, please refer to Page 2.</b></font>", style_notes)
        ]
    elif is_invoice:
        bank_flowable = [
            Paragraph("<b>COMPANY BANK DETAILS</b>", style_panel_title),
            Paragraph(f"<b>A/c Name:</b> {COMPANY_INFO['account_name']}", style_panel_body),
            Paragraph(f"<b>Bank:</b> {COMPANY_INFO['bank_name']}<br/><b>A/c No:</b> {COMPANY_INFO['account_number']}<br/><b>IFSC:</b> {COMPANY_INFO['ifsc']}", style_panel_body),
            Spacer(1, 1 * mm),
            Paragraph("<font color='#1e3a8a'><b>Official Statutory Tax Invoice</b></font>", style_notes)
        ]
    else:
        bank_flowable = [
            Paragraph("<b>BANK DETAILS</b>", style_panel_title),
            Paragraph(f"<b>Bank:</b> {COMPANY_INFO['bank_name']}<br/><b>A/c No:</b> {COMPANY_INFO['account_number']}<br/><b>IFSC:</b> {COMPANY_INFO['ifsc']}", style_panel_body)
        ]

    sign_flowable = [
        Paragraph(f"For <b>{COMPANY_INFO['legal_name']}</b>", style_panel_title),
        Spacer(1, 12 * mm),
        Paragraph("<b>Authorized Signatory</b>", style_panel_body)
    ]

    bottom_table = Table([[terms_flowable, bank_flowable, sign_flowable]], colWidths=[70 * mm, 64 * mm, 48 * mm])
    bottom_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(KeepTogether(bottom_table))

    # 6. Proforma Invoice Page 2: Dedicated Scan & Pay Page
    if is_proforma:
        story.append(PageBreak())
        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph("PAYMENT — SCAN TO PAY", style_title))
        story.append(Paragraph(f"Proforma Invoice No: {data['doc_number']}", style_doc_num))
        story.append(Paragraph(f"Amount: ₹ {_format_inr(data['grand_total'])}", style_grand_val))
        story.append(Spacer(1, 6 * mm))

        qr_box = [
            Paragraph("<b>Scan with any UPI App to Pay Instantly</b>", style_panel_title),
            Paragraph("GPay, PhonePe, Paytm, BHIM or any Banking UPI App", style_panel_body),
            Spacer(1, 4 * mm),
            Paragraph(f"<b>UPI Payee:</b> {COMPANY_INFO['account_name']}", style_panel_body),
            Paragraph(f"<b>A/c No:</b> {COMPANY_INFO['account_number']}", style_panel_body),
            Paragraph(f"<b>IFSC:</b> {COMPANY_INFO['ifsc']}", style_panel_body),
            Spacer(1, 4 * mm),
            Paragraph("<i>Please share transaction UTR / Reference with your account manager after payment.</i>", style_notes)
        ]
        qr_table = Table([[qr_box]], colWidths=[150 * mm])
        qr_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), BRAND_RED_50),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 16),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 16),
            ('LEFTPADDING', (0, 0), (-1, -1), 16),
            ('RIGHTPADDING', (0, 0), (-1, -1), 16),
            ('BOX', (0, 0), (-1, -1), 1, BRAND_RED_600),
        ]))
        story.append(qr_table)

    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer.getvalue()
