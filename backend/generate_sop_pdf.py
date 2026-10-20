import os
import shutil
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        
        # Header (pages after cover/page 1)
        if self._pageNumber > 1:
            self.drawString(54, letter[1] - 36, "Wa CRM — External Proforma & Client Integration API (SOP-INT-001)")
            self.drawRightString(letter[0] - 54, letter[1] - 36, "CONFIDENTIAL & TECHNICAL")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(54, letter[1] - 42, letter[0] - 54, letter[1] - 42)

        # Footer
        text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 54, 30, text)
        self.drawString(54, 30, "Wa CRM Integration System © 2026. All rights reserved.")
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(54, 42, letter[0] - 54, 42)
        self.restoreState()


def generate_pdf(output_paths):
    doc_path = output_paths[0]
    doc = SimpleDocTemplate(
        doc_path,
        pagesize=letter,
        leftMargin=50,
        rightMargin=50,
        topMargin=50,
        bottomMargin=50
    )

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0f172a')
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#0f766e')
    )
    h1_style = ParagraphStyle(
        'DocH1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#0f172a'),
        spaceBefore=10,
        spaceAfter=4
    )
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#334155'),
        spaceAfter=4
    )
    body_bold = ParagraphStyle(
        'DocBodyBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#0f172a')
    )
    code_box = ParagraphStyle(
        'DocCodeBox',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7,
        leading=9.5,
        textColor=colors.HexColor('#0f172a')
    )
    code_white = ParagraphStyle(
        'DocCodeWhite',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7,
        leading=9.5,
        textColor=colors.HexColor('#38bdf8')
    )
    table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#1e293b')
    )
    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#0f172a')
    )
    table_cell_code = ParagraphStyle(
        'TableCellCode',
        parent=styles['Normal'],
        fontName='Courier-Bold',
        fontSize=7,
        leading=9.5,
        textColor=colors.HexColor('#0f766e')
    )

    story = []

    # Title & Metadata
    story.append(Paragraph("STANDARD OPERATING PROCEDURE (SOP) & DEVELOPER MANUAL", subtitle_style))
    story.append(Spacer(1, 3))
    story.append(Paragraph("Wa CRM — External Proforma & Client Integration API", title_style))
    story.append(Spacer(1, 6))

    meta_data = [
        [Paragraph("Document ID:", table_cell_bold), Paragraph("SOP-INT-WACRM-001", table_cell), Paragraph("Effective Date:", table_cell_bold), Paragraph("October 2026", table_cell)],
        [Paragraph("Production Base URL:", table_cell_bold), Paragraph("<b>https://wacrm.dinuping.com</b>", table_cell_code), Paragraph("Version:", table_cell_bold), Paragraph("1.0.0 (Production)", table_cell)],
        [Paragraph("Target Endpoint:", table_cell_bold), Paragraph("<b>POST /api/integrations/proforma</b>", table_cell_code), Paragraph("Security:", table_cell_bold), Paragraph("API Key (Header)", table_cell)]
    ]
    t_meta = Table(meta_data, colWidths=[105, 185, 95, 127])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 8))

    # Section 1: Credentials
    story.append(Paragraph("1. Connection Prerequisites & Authentication Credentials", h1_style))
    story.append(Paragraph(
        "All requests from your external website or backend must supply the authorized integration key via standard HTTP headers:",
        body_style
    ))
    
    cred_table_data = [
        [Paragraph("Parameter", table_cell_bold), Paragraph("Value", table_cell_bold), Paragraph("Notes", table_cell_bold)],
        [Paragraph("Base URL", table_cell), Paragraph("<b>https://wacrm.dinuping.com</b>", table_cell_code), Paragraph("Production endpoint (HTTPS enforced)", table_cell)],
        [Paragraph("Header Option A", table_cell), Paragraph("<b>X-API-Key: wacrm_ext_live_8849204128f73a0e691823c91</b>", table_cell_code), Paragraph("Recommended header", table_cell)],
        [Paragraph("Header Option B", table_cell), Paragraph("<b>Authorization: Bearer wacrm_ext_live_8849204128f73a0e691823c91</b>", table_cell_code), Paragraph("Standard OAuth Bearer format", table_cell)],
        [Paragraph("Rate Limit", table_cell), Paragraph("<b>120 req / minute</b>", table_cell), Paragraph("Sliding window per IP/key (HTTP 429 on breach)", table_cell)],
        [Paragraph("Interactive Docs", table_cell), Paragraph("<b>https://wacrm.dinuping.com/docs</b>", table_cell_code), Paragraph("Live Swagger sandbox to test endpoints", table_cell)]
    ]
    t_cred = Table(cred_table_data, colWidths=[95, 275, 142])
    t_cred.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f766e')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t_cred)
    story.append(Spacer(1, 8))

    # Section 2: Endpoints
    story.append(Paragraph("2. API Routes Specification", h1_style))
    routes_data = [
        [Paragraph("Method", table_cell_bold), Paragraph("Path", table_cell_bold), Paragraph("Purpose", table_cell_bold)],
        [Paragraph("POST", table_cell_code), Paragraph("<b>/api/integrations/proforma</b>", table_cell_code), Paragraph("<b>Main Endpoint</b>: Ingests client & proforma, recalculates GST, enforces idempotency, returns authoritative totals.", table_cell)],
        [Paragraph("GET", table_cell_code), Paragraph("<b>/api/integrations/proforma/{id_or_number}</b>", table_cell_code), Paragraph("Retrieves single authoritative proforma by numeric ID or Document Number (e.g. <code>PI-2026-0042</code>).", table_cell)],
        [Paragraph("GET", table_cell_code), Paragraph("<b>/api/integrations/proforma</b>", table_cell_code), Paragraph("Lists and paginates authoritative proformas with search, customer ID, and limit filters.", table_cell)],
        [Paragraph("OPTIONS", table_cell_code), Paragraph("<b>/api/integrations/proforma</b>", table_cell_code), Paragraph("CORS preflight handler for cross-origin web browser and client applications.", table_cell)]
    ]
    t_routes = Table(routes_data, colWidths=[55, 210, 247])
    t_routes.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t_routes)
    story.append(Spacer(1, 8))

    # Section 3: Duplicate Prevention & Tax Rules
    story.append(Paragraph("3. Duplicate Prevention & Authoritative Tax Calculation", h1_style))
    story.append(Paragraph(
        "<b>Duplicate Prevention (Idempotency):</b> Send a unique transaction UUID in header <code>X-Idempotency-Key</code> or body field <code>idempotencyKey</code>. If an identical request is repeated within 24 hours, the CRM re-returns the previously issued document (<code>processingStatus: AUTHORITATIVE_VERIFIED</code>) without creating duplicate records.<br/>"
        "<b>Authoritative Tax Rules:</b> The CRM calculates <code>Taxable Subtotal = (Rate * Qty) - Discount</code>.<br/>"
        "• <b>Intra-state (Tamil Nadu, State Code '33')</b>: 9% CGST + 9% SGST.<br/>"
        "• <b>Inter-state (Other States / Union Territories)</b>: 18% IGST.<br/>"
        "Arbitrary caller-supplied totals are verified; authoritative CRM math is enforced on the generated invoice.",
        body_style
    ))
    story.append(Spacer(1, 4))

    # Section 4: Data Schema
    story.append(PageBreak())

    story.append(Paragraph("4. JSON Request Field Dictionary (`POST /api/integrations/proforma`)", h1_style))
    schema_data = [
        [Paragraph("Field", table_cell_bold), Paragraph("Type", table_cell_bold), Paragraph("Req?", table_cell_bold), Paragraph("Description & Rules", table_cell_bold)],
        [Paragraph("idempotencyKey", table_cell_code), Paragraph("string", table_cell), Paragraph("Yes*", table_cell), Paragraph("Unique transaction UUID (prevents duplicate documents).", table_cell)],
        [Paragraph("companyName", table_cell_code), Paragraph("string", table_cell), Paragraph("Yes**", table_cell), Paragraph("Legal company or customer trade name.", table_cell)],
        [Paragraph("contactPerson", table_cell_code), Paragraph("string", table_cell), Paragraph("Yes**", table_cell), Paragraph("Primary contact name (**Either companyName or contactPerson required).", table_cell)],
        [Paragraph("phone", table_cell_code), Paragraph("string", table_cell), Paragraph("Yes", table_cell), Paragraph("10-digit phone number with optional country code.", table_cell)],
        [Paragraph("email", table_cell_code), Paragraph("string", table_cell), Paragraph("Opt", table_cell), Paragraph("Email address for billing and invoice dispatch.", table_cell)],
        [Paragraph("gstin", table_cell_code), Paragraph("string", table_cell), Paragraph("Opt", table_cell), Paragraph("15-character GSTIN (e.g. <code>33AAAAA1234A1Z5</code>).", table_cell)],
        [Paragraph("billingAddress", table_cell_code), Paragraph("object", table_cell), Paragraph("Opt", table_cell), Paragraph("Object with <code>line1</code>, <code>city</code>, <code>state</code>, <code>stateCode</code>, <code>pincode</code>.", table_cell)],
        [Paragraph("proformaNumber", table_cell_code), Paragraph("string", table_cell), Paragraph("Opt", table_cell), Paragraph("Document number. If omitted, CRM auto-generates <code>PI-YYYY-XXXX</code>.", table_cell)],
        [Paragraph("productCategory", table_cell_code), Paragraph("string", table_cell), Paragraph("Opt", table_cell), Paragraph("<code>wahrms</code> (Software) or <code>biometric</code> (Hardware).", table_cell)],
        [Paragraph("lineItems", table_cell_code), Paragraph("array", table_cell), Paragraph("Yes", table_cell), Paragraph("List of purchased items (minimum 1 item required).", table_cell)],
        [Paragraph("  item.name", table_cell_code), Paragraph("string", table_cell), Paragraph("Yes", table_cell), Paragraph("Product / Service bundle title.", table_cell)],
        [Paragraph("  item.hsn", table_cell_code), Paragraph("string", table_cell), Paragraph("Opt", table_cell), Paragraph("HSN/SAC code (<code>998314</code> for software, <code>85437099</code> for biometric).", table_cell)],
        [Paragraph("  item.qty", table_cell_code), Paragraph("number", table_cell), Paragraph("Yes", table_cell), Paragraph("Quantity (must be &gt; 0).", table_cell)],
        [Paragraph("  item.rate", table_cell_code), Paragraph("number", table_cell), Paragraph("Yes", table_cell), Paragraph("Unit rate excluding tax (must be &ge; 0).", table_cell)],
        [Paragraph("  item.discount", table_cell_code), Paragraph("number", table_cell), Paragraph("Opt", table_cell), Paragraph("Flat line discount (default: 0.0).", table_cell)],
        [Paragraph("  item.gstRate", table_cell_code), Paragraph("number", table_cell), Paragraph("Opt", table_cell), Paragraph("Tax decimal (<code>0.18</code>) or percentage (<code>18</code>).", table_cell)]
    ]
    t_schema = Table(schema_data, colWidths=[90, 40, 32, 350])
    t_schema.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f766e')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
    ]))
    story.append(t_schema)
    story.append(Spacer(1, 8))

    # Section 5: Live Request Example
    story.append(Paragraph("5. Live HTTP Request Example", h1_style))
    req_lines = [
        "POST /api/integrations/proforma HTTP/1.1",
        "Host: wacrm.dinuping.com",
        "X-API-Key: wacrm_ext_live_8849204128f73a0e691823c91",
        "X-Idempotency-Key: idem_req_20261017_001",
        "Content-Type: application/json",
        "",
        "{",
        '  "idempotencyKey": "idem_req_20261017_001",',
        '  "companyName": "Acme Global Solutions Pvt Ltd",',
        '  "contactPerson": "Rajesh Kumar",',
        '  "phone": "+91 9876543210",',
        '  "email": "billing@acmeglobal.com",',
        '  "gstin": "33AAAAA1234A1Z5",',
        '  "billingAddress": {',
        '    "line1": "Level 4, Tidel Park, Rajiv Gandhi Salai",',
        '    "city": "Chennai", "state": "Tamil Nadu", "stateCode": "33", "pincode": "600113"',
        '  },',
        '  "productCategory": "wahrms",',
        '  "lineItems": [',
        '    {',
        '      "name": "WAHRMS Core HR + Payroll Cloud Suite",',
        '      "hsn": "998314", "qty": 1, "rate": 75000.00, "gstRate": 0.18',
        '    }',
        '  ],',
        '  "termsAndConditions": "1. Software onboarding commences upon payment receipt."',
        "}"
    ]
    t_req = Table([[Paragraph("<br/>".join(req_lines), code_white)]], colWidths=[512])
    t_req.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#0f172a')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#334155')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_req)
    story.append(Spacer(1, 8))

    story.append(PageBreak())

    # Section 6: Live Response Example
    story.append(Paragraph("6. Authoritative Success Response (HTTP 201 Created)", h1_style))
    res_lines = [
        "HTTP/1.1 201 Created",
        "Content-Type: application/json",
        "",
        "{",
        '  "success": true,',
        '  "requestId": "req_88a91b2c4d",',
        '  "processingStatus": "CREATED",',
        '  "customerId": 101,',
        '  "customerName": "Rajesh Kumar",',
        '  "companyName": "Acme Global Solutions Pvt Ltd",',
        '  "proformaId": 204,',
        '  "proformaNumber": "PI-2026-0042",',
        '  "authoritativeSummary": {',
        '    "taxableSubtotal": 75000.0,',
        '    "taxMode": "intra",',
        '    "cgst": 6750.0,',
        '    "sgst": 6750.0,',
        '    "igst": 0.0,',
        '    "totalTax": 13500.0,',
        '    "roundOff": 0.0,',
        '    "grandTotal": 88500.0,',
        '    "lineItemsCount": 1',
        '  },',
        '  "pdfDownloadUrl": "/api/integrations/waquote/proformas/204/download",',
        '  "syncedAt": "2026-10-17T11:10:00+00:00",',
        '  "message": "Proforma Invoice #PI-2026-0042 successfully registered in CRM."',
        "}"
    ]
    t_res = Table([[Paragraph("<br/>".join(res_lines), ParagraphStyle('CGreen', parent=code_box, textColor=colors.HexColor('#047857')))]], colWidths=[512])
    t_res.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#ecfdf5')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#a7f3d0')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_res)
    story.append(Spacer(1, 10))

    # Section 7: Code Snippets
    story.append(Paragraph("7. Ready-to-Copy Developer Integration Code", h1_style))
    story.append(Paragraph("<b>Node.js (Axios):</b>", body_bold))
    node_lines = [
        "const axios = require('axios');",
        "const response = await axios.post('https://wacrm.dinuping.com/api/integrations/proforma', {",
        "  idempotencyKey: `idem_${Date.now()}`,",
        "  companyName: 'Acme Corp', contactPerson: 'Ravi', phone: '+91 9876543210',",
        "  lineItems: [{ name: 'WAHRMS Software', qty: 1, rate: 50000, gstRate: 0.18 }]",
        "}, {",
        "  headers: { 'X-API-Key': 'wacrm_ext_live_8849204128f73a0e691823c91', 'Content-Type': 'application/json' }",
        "});",
        "console.log('Invoice #:', response.data.proformaNumber, 'Grand Total:', response.data.authoritativeSummary.grandTotal);"
    ]
    t_node = Table([[Paragraph("<br/>".join(node_lines), code_box)]], colWidths=[512])
    t_node.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_node)
    story.append(Spacer(1, 6))

    story.append(Paragraph("<b>cURL (Terminal One-Liner):</b>", body_bold))
    curl_lines = [
        'curl -X POST "https://wacrm.dinuping.com/api/integrations/proforma" \\',
        '  -H "X-API-Key: wacrm_ext_live_8849204128f73a0e691823c91" \\',
        '  -H "Content-Type: application/json" \\',
        '  -d \'{"companyName":"Test Client","contactPerson":"Ravi","phone":"9876543210","lineItems":[{"name":"WAHRMS","rate":50000,"qty":1,"gstRate":0.18}]}\''
    ]
    t_curl = Table([[Paragraph("<br/>".join(curl_lines), code_box)]], colWidths=[512])
    t_curl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_curl)
    story.append(Spacer(1, 10))

    # Section 8: Troubleshooting
    story.append(Paragraph("8. HTTP Status Codes & Troubleshooting", h1_style))
    err_data = [
        [Paragraph("HTTP Code", table_cell_bold), Paragraph("Error / Cause", table_cell_bold), Paragraph("Action Required", table_cell_bold)],
        [Paragraph("401", table_cell_code), Paragraph("Missing server-to-server authentication...", table_cell), Paragraph("Add header <code>X-API-Key: wacrm_ext_live_8849204128f73a0e691823c91</code>", table_cell)],
        [Paragraph("403", table_cell_code), Paragraph("Invalid API key or unauthorized credential", table_cell), Paragraph("Verify API key characters. Check for trailing whitespace or typos.", table_cell)],
        [Paragraph("422", table_cell_code), Paragraph("Validation error (missing company/items)", table_cell), Paragraph("Ensure <code>companyName</code> or <code>contactPerson</code> and <code>lineItems</code> are non-empty.", table_cell)],
        [Paragraph("429", table_cell_code), Paragraph("Rate limit exceeded (120 req/min)", table_cell), Paragraph("Reduce call frequency or implement exponential backoff.", table_cell)]
    ]
    t_err = Table(err_data, colWidths=[60, 210, 242])
    t_err.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t_err)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Generated PDF at: {doc_path}")

    # Copy to all destinations
    for extra_path in output_paths[1:]:
        os.makedirs(os.path.dirname(extra_path), exist_ok=True)
        shutil.copy2(doc_path, extra_path)
        print(f"Copied PDF to: {extra_path}")

if __name__ == "__main__":
    targets = [
        os.path.abspath("docs/DEVELOPER_SOP_PROFORMA_API_INTEGRATION.pdf"),
        os.path.abspath("../docs/DEVELOPER_SOP_PROFORMA_API_INTEGRATION.pdf"),
        os.path.abspath("../frontend/public/DEVELOPER_SOP_PROFORMA_API_INTEGRATION.pdf"),
        os.path.abspath("../frontend/dist/DEVELOPER_SOP_PROFORMA_API_INTEGRATION.pdf"),
        os.path.abspath("uploads/DEVELOPER_SOP_PROFORMA_API_INTEGRATION.pdf")
    ]
    os.makedirs(os.path.dirname(targets[0]), exist_ok=True)
    generate_pdf(targets)
