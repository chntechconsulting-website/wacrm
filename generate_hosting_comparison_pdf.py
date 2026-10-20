import os
import shutil
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
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
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        
        # Header (pages after cover/page 1)
        if self._pageNumber > 1:
            self.drawString(40, letter[1] - 32, "WaCRM — Production Hosting Architecture & Cost Comparison")
            self.drawRightString(letter[0] - 40, letter[1] - 32, "TECHNICAL & FINANCIAL REPORT")
            self.setStrokeColor(colors.HexColor("#e2e8f0"))
            self.setLineWidth(0.75)
            self.line(40, letter[1] - 38, letter[0] - 40, letter[1] - 38)

        # Footer
        text = f"Page {self._pageNumber} of {page_count}"
        self.setFont("Helvetica", 8)
        self.drawRightString(letter[0] - 40, 26, text)
        self.drawString(40, 26, "WaCRM Infrastructure Evaluation © 2026 • Confidential & Proprietary")
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.75)
        self.line(40, 36, letter[0] - 40, 36)
        self.restoreState()


def build_pdf(output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=46,
        bottomMargin=46
    )

    styles = getSampleStyleSheet()
    
    # Custom Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0f172a')
    )
    
    subtitle_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#475569')
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=colors.HexColor('#1e293b'),
        spaceAfter=6
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#0369a1'),
        spaceAfter=4
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#334155')
    )

    body_bold = ParagraphStyle(
        'Body_Bold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#1e293b')
    )

    badge_recommended = ParagraphStyle(
        'BadgeRec',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#065f46')
    )

    table_header = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#ffffff')
    )

    table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#1e293b')
    )

    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#0f172a')
    )

    callout_style = ParagraphStyle(
        'Callout',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor('#0f766e')
    )

    elements = []

    # 1. HEADER BANNER
    header_table_data = [
        [
            Paragraph("<b>WaCRM Production Hosting & Price Comparison</b>", title_style),
            Paragraph("<b>DOCUMENT ID:</b> WACRM-HOST-2026<br/><b>DATE:</b> October 2026<br/><b>TARGET:</b> Production Deployment", ParagraphStyle('MetaRight', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=11, textColor=colors.HexColor('#64748b'), alignment=2))
        ]
    ]
    t_header = Table(header_table_data, colWidths=[380, 152])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(t_header)
    elements.append(Spacer(1, 6))

    elements.append(Paragraph(
        "Comprehensive technical evaluation, architecture feasibility, and Total Cost of Ownership (TCO) analysis for hosting the WaCRM stack (FastAPI Backend, React Vite Frontend, MySQL 8.0, WhatsApp Cloud API & Meta Lead Ads Webhooks).",
        subtitle_style
    ))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0284c7"), spaceAfter=12))

    # 2. APPLICATION REQUIREMENTS SUMMARY
    elements.append(Paragraph("1. System Architecture & Workload Requirements", h1_style))
    
    req_data = [
        [
            Paragraph("<b>Component</b>", table_header),
            Paragraph("<b>Technology</b>", table_header),
            Paragraph("<b>Production Hosting Requirement</b>", table_header),
            Paragraph("<b>Critical Constraints</b>", table_header)
        ],
        [
            Paragraph("Frontend", table_cell_bold),
            Paragraph("React.js (Vite Build)", table_cell),
            Paragraph("Static Web Hosting / Nginx Reverse Proxy", table_cell),
            Paragraph("Fast CDN delivery; client-side routing", table_cell)
        ],
        [
            Paragraph("Backend API", table_cell_bold),
            Paragraph("Python FastAPI + Uvicorn", table_cell),
            Paragraph("24/7 Persistent Linux Process (systemd/PM2)", table_cell),
            Paragraph("Zero sleep mode; webhook latency < 500ms", table_cell)
        ],
        [
            Paragraph("Database", table_cell_bold),
            Paragraph("MySQL 8.0 (InnoDB)", table_cell),
            Paragraph("High IOPS persistent disk + Daily Automated Dumps", table_cell),
            Paragraph("UTF8mb4 collation; relational integrity", table_cell)
        ],
        [
            Paragraph("Integrations", table_cell_bold),
            Paragraph("Meta Lead Ads & WhatsApp", table_cell),
            Paragraph("Valid HTTPS Domain (Port 443, SSL/TLS)", table_cell),
            Paragraph("Meta requires 200 OK within 5s on webhooks", table_cell)
        ],
        [
            Paragraph("Storage", table_cell_bold),
            Paragraph("Local /uploads directory", table_cell),
            Paragraph("Persistent file volume (Quotations, Excel imports)", table_cell),
            Paragraph("Cannot use ephemeral serverless disks", table_cell)
        ]
    ]
    t_req = Table(req_data, colWidths=[80, 110, 192, 150])
    t_req.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#ffffff'), colors.HexColor('#f8fafc')])
    ]))
    elements.append(t_req)
    elements.append(Spacer(1, 14))

    # 3. COMPREHENSIVE COST COMPARISON MATRIX
    elements.append(Paragraph("2. Hosting Platform Price & Technical Comparison", h1_style))
    elements.append(Paragraph(
        "Evaluation of leading infrastructure platforms across monthly expenditure, India regional availability, webhook compatibility, and setup complexity:",
        body_style
    ))
    elements.append(Spacer(1, 6))

    matrix_data = [
        [
            Paragraph("<b>Hosting Model</b>", table_header),
            Paragraph("<b>Target Providers</b>", table_header),
            Paragraph("<b>Specs Included</b>", table_header),
            Paragraph("<b>Monthly Cost (USD / INR)</b>", table_header),
            Paragraph("<b>Webhook Reliability</b>", table_header),
            Paragraph("<b>Overall Rating</b>", table_header)
        ],
        [
            Paragraph("<b>Option 1: Cloud VPS</b><br/><font color='#047857'><b>[RECOMMENDED]</b></font>", table_cell),
            Paragraph("Hostinger KVM 2 / Hetzner / DigitalOcean", table_cell),
            Paragraph("2 vCPU, 4GB RAM, 50GB NVMe, Nginx + MySQL + FastAPI on 1 box", table_cell),
            Paragraph("<b>$5 – $8 / mo</b><br/>(₹450 – ₹699 / mo)", table_cell_bold),
            Paragraph("<font color='#059669'><b>100% Reliable</b></font><br/>Always-on daemon", table_cell),
            Paragraph("<b>9.5 / 10</b><br/>Lowest TCO, top speed", table_cell_bold)
        ],
        [
            Paragraph("<b>Option 2: AWS Lightsail</b><br/><font color='#0284c7'><b>[ENTERPRISE VPS]</b></font>", table_cell),
            Paragraph("Amazon Web Services (Mumbai Region)", table_cell),
            Paragraph("1–2 vCPU, 2GB–4GB RAM, 60GB SSD, AWS Global Backbone", table_cell),
            Paragraph("<b>$10 – $20 / mo</b><br/>(₹840 – ₹1,680 / mo)", table_cell_bold),
            Paragraph("<font color='#059669'><b>100% Reliable</b></font><br/>AWS 99.99% SLA", table_cell),
            Paragraph("<b>9.0 / 10</b><br/>Brand trust & low ping", table_cell_bold)
        ],
        [
            Paragraph("<b>Option 3: PaaS Cloud</b><br/><font color='#b45309'><b>[DEVELOPER EASY]</b></font>", table_cell),
            Paragraph("Render.com / Railway.app + Vercel", table_cell),
            Paragraph("FastAPI Web Service + Managed MySQL addon + Vercel edge", table_cell),
            Paragraph("<b>$16 – $28 / mo</b><br/>(₹1,350 – ₹2,350 / mo)", table_cell_bold),
            Paragraph("<font color='#d97706'><b>Paid Plan Only</b></font><br/>Free tier sleeps & drops leads", table_cell),
            Paragraph("<b>7.5 / 10</b><br/>Zero setup, higher cost", table_cell_bold)
        ],
        [
            Paragraph("<b>Option 4: Enterprise AWS</b><br/><font color='#64748b'><b>[HIGH SCALE]</b></font>", table_cell),
            Paragraph("AWS EC2 (t4g.small) + AWS RDS MySQL", table_cell),
            Paragraph("Separated App instance + Multi-AZ managed database + S3", table_cell),
            Paragraph("<b>$45 – $85 / mo</b><br/>(₹3,800 – ₹7,100 / mo)", table_cell_bold),
            Paragraph("<font color='#059669'><b>100% Reliable</b></font><br/>Enterprise tier", table_cell),
            Paragraph("<b>6.5 / 10</b><br/>Overkill for MVP CRM", table_cell_bold)
        ]
    ]

    t_matrix = Table(matrix_data, colWidths=[90, 95, 125, 95, 75, 52])
    t_matrix.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#ffffff'), colors.HexColor('#f8fafc')]),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#f0fdf4')), # highlight recommended
    ]))
    elements.append(t_matrix)
    elements.append(Spacer(1, 14))

    # 4. ANNUAL TOTAL COST OF OWNERSHIP (TCO) COMPARISON
    elements.append(Paragraph("3. Annual Total Cost of Ownership (TCO) Projection (1 Year)", h1_style))
    
    tco_data = [
        [
            Paragraph("<b>Cost Line Item</b>", table_header),
            Paragraph("<b>Option 1: Hostinger VPS</b>", table_header),
            Paragraph("<b>Option 2: AWS Lightsail</b>", table_header),
            Paragraph("<b>Option 3: Railway / Render</b>", table_header),
            Paragraph("<b>Option 4: AWS EC2 + RDS</b>", table_header)
        ],
        [
            Paragraph("Backend Compute (FastAPI)", table_cell_bold),
            Paragraph("Included in VPS", table_cell),
            Paragraph("Included in Instance", table_cell),
            Paragraph("₹590 / mo ($7/mo)", table_cell),
            Paragraph("₹1,600 / mo ($19/mo)", table_cell)
        ],
        [
            Paragraph("Database (MySQL 8.0)", table_cell_bold),
            Paragraph("Included on localhost", table_cell),
            Paragraph("Included on localhost", table_cell),
            Paragraph("₹670 / mo ($8/mo)", table_cell),
            Paragraph("₹2,350 / mo ($28/mo)", table_cell)
        ],
        [
            Paragraph("Frontend Hosting (React Vite)", table_cell_bold),
            Paragraph("Included (Nginx static)", table_cell),
            Paragraph("Included (Nginx static)", table_cell),
            Paragraph("₹0 (Vercel Free Tier)", table_cell),
            Paragraph("₹350 / mo (S3 + CloudFront)", table_cell)
        ],
        [
            Paragraph("SSL / TLS Certificate", table_cell_bold),
            Paragraph("₹0 (Let's Encrypt)", table_cell),
            Paragraph("₹0 (Let's Encrypt)", table_cell),
            Paragraph("₹0 (Included)", table_cell),
            Paragraph("₹0 (AWS ACM)", table_cell)
        ],
        [
            Paragraph("Storage & Uploads (50GB)", table_cell_bold),
            Paragraph("Included in disk", table_cell),
            Paragraph("Included in disk", table_cell),
            Paragraph("₹350 / mo (Vol/S3)", table_cell),
            Paragraph("₹400 / mo (EBS & S3)", table_cell)
        ],
        [
            Paragraph("<b>Total Monthly Cost</b>", table_cell_bold),
            Paragraph("<b>₹499 / mo (~$6)</b>", ParagraphStyle('P1', parent=table_cell_bold, textColor=colors.HexColor('#047857'))),
            Paragraph("<b>₹840 / mo (~$10)</b>", ParagraphStyle('P2', parent=table_cell_bold, textColor=colors.HexColor('#0284c7'))),
            Paragraph("<b>₹1,610 / mo (~$19)</b>", table_cell_bold),
            Paragraph("<b>₹4,700 / mo (~$56)</b>", table_cell_bold)
        ],
        [
            Paragraph("<b>Annual Cost (1 Year)</b>", table_cell_bold),
            Paragraph("<b>₹5,988 / year</b>", ParagraphStyle('A1', parent=table_cell_bold, textColor=colors.HexColor('#047857'))),
            Paragraph("<b>₹10,080 / year</b>", ParagraphStyle('A2', parent=table_cell_bold, textColor=colors.HexColor('#0284c7'))),
            Paragraph("<b>₹19,320 / year</b>", table_cell_bold),
            Paragraph("<b>₹56,400 / year</b>", table_cell_bold)
        ]
    ]

    t_tco = Table(tco_data, colWidths=[132, 100, 100, 100, 100])
    t_tco.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -3), [colors.HexColor('#ffffff'), colors.HexColor('#f8fafc')]),
        ('BACKGROUND', (0, -2), (-1, -1), colors.HexColor('#e2e8f0')),
    ]))
    elements.append(t_tco)
    elements.append(Spacer(1, 14))

    # 5. RECOMMENDED ARCHITECTURE BLUEPRINT (Callout Box)
    elements.append(Paragraph("4. Recommended Architecture: Single-Host Linux VPS", h1_style))
    
    arch_box_content = [
        [
            Paragraph(
                "<b>💡 Why the Cloud VPS Architecture is the Optimal Choice for WaCRM:</b><br/>"
                "• <b>Zero Cold Starts for Meta & WhatsApp Webhooks:</b> Meta Developer Platform mandates a 200 OK response within 5,000ms. Serverless sleeping containers fail this and lead to disabled webhooks. A persistent VPS processes requests in <30ms.<br/>"
                "• <b>Co-located MySQL:</b> FastAPI connects to MySQL over Unix socket/localhost with 0.1ms query latency, drastically speeding up dashboard analytics and Excel bulk imports.<br/>"
                "• <b>Persistent File Storage:</b> Uploaded Excel lead rosters and generated quotation PDFs stay on persistent NVMe/SSD storage without needing third-party S3 integration or extra billable services.<br/>"
                "• <b>Data Sovereignty:</b> Choosing a Mumbai data center (AWS Lightsail or Hostinger India) guarantees strict compliance with Indian data regulations and ensures minimal round-trip latency.",
                callout_style
            )
        ]
    ]
    t_arch_box = Table(arch_box_content, colWidths=[532])
    t_arch_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0fdfa')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#14b8a6')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(t_arch_box)
    elements.append(Spacer(1, 14))

    # 6. STEP-BY-STEP DEPLOYMENT ROADMAP
    elements.append(Paragraph("5. Production Deployment Implementation Roadmap", h1_style))
    
    steps_data = [
        [
            Paragraph("<b>Phase</b>", table_header),
            Paragraph("<b>Action Items</b>", table_header),
            Paragraph("<b>Tools / Commands</b>", table_header)
        ],
        [
            Paragraph("<b>Step 1: Domain & DNS</b>", table_cell_bold),
            Paragraph("Point an `A` record (e.g. `crm.yourcompany.com`) to the VPS Public IP Address.", table_cell),
            Paragraph("Cloudflare / Namecheap / GoDaddy DNS", table_cell)
        ],
        [
            Paragraph("<b>Step 2: Server Provisioning</b>", table_cell_bold),
            Paragraph("Install Python 3.11+, MySQL Server 8.0, Nginx, and Git on Ubuntu 24.04 LTS.", table_cell),
            Paragraph("`apt update && apt install nginx mysql-server python3-venv`", table_cell)
        ],
        [
            Paragraph("<b>Step 3: Database & Backend</b>", table_cell_bold),
            Paragraph("Create `wa_crm` database, set up Python virtual environment, configure `.env`, start via systemd service.", table_cell),
            Paragraph("`systemctl enable --now wacrm-backend` (Uvicorn 4 workers)", table_cell)
        ],
        [
            Paragraph("<b>Step 4: Frontend Build & Nginx</b>", table_cell_bold),
            Paragraph("Build React frontend (`npm run build`), configure Nginx reverse proxy routing `/api` to FastAPI and `/` to HTML static files.", table_cell),
            Paragraph("`npm run build` -> `/var/www/wacrm/frontend/dist`", table_cell)
        ],
        [
            Paragraph("<b>Step 5: SSL & Webhooks</b>", table_cell_bold),
            Paragraph("Issue free TLS 1.3 certificate. Verify Meta Webhook with verify token and start live lead ingestion.", table_cell),
            Paragraph("`certbot --nginx -d crm.yourcompany.com`", table_cell)
        ]
    ]

    t_steps = Table(steps_data, colWidths=[120, 242, 170])
    t_steps.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#ffffff'), colors.HexColor('#f8fafc')])
    ]))
    elements.append(t_steps)

    # Build the PDF
    doc.build(elements, canvasmaker=NumberedCanvas)
    print(f"PDF successfully generated at: {output_path}")

if __name__ == '__main__':
    target = os.path.abspath("WaCRM_Hosting_Price_Comparison.pdf")
    build_pdf(target)
