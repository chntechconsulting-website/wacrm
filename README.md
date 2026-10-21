# WaCRM - Production-Structured Internal CRM MVP

WaCRM is a corporate CRM web application designed for internal company lead tracking, employee management, follow-up scheduling, customer conversions, Excel lead imports, and automated integrations (Meta Lead Ads, WhatsApp, IVR).

---

## 🛠️ Technology Stack

### Frontend
- **Framework**: React.js with Vite
- **Styling**: Plain Vanilla CSS (Custom Design System with Light Mode aesthetic)
- **HTTP Client**: Axios (with request/response interceptors for JWT auth & 401 handling)
- **Routing**: React Router DOM (v6) with Role-Based Protected Routes (`ADMIN`, `MANAGER`, `EMPLOYEE`)
- **Icons**: Lucide React

### Backend
- **Framework**: Python FastAPI
- **Database ORM**: SQLAlchemy 2.0
- **Validation**: Pydantic v2
- **Authentication**: JWT Tokens (`pyjwt`) with bcrypt password hashing
- **Excel Processing**: `openpyxl`
- **HTTP Engine**: `uvicorn`

### Database
- **Engine**: MySQL 8.0 (`wa_crm` database)

---

## 📦 Main Modules & Features

1. **Authentication**:
   - Login, Logout, JWT Token authorization, `GET /api/auth/me`.
   - Role-based access control (`ADMIN`, `MANAGER`, `EMPLOYEE`).

2. **Lead Management (CRUD & Timeline)**:
   - Full CRUD: Create lead, Edit lead, Delete lead, Search, Filter by Status/Source, Pagination.
   - Statuses: `NEW`, `ASSIGNED`, `CONTACTED`, `INTERESTED`, `FOLLOW_UP`, `QUALIFIED`, `CONVERTED`, `NOT_INTERESTED`, `LOST`.
   - Interactive Activity History Timeline drawer.
   - Lead assignment to sales representatives.

3. **Follow-up Management**:
   - Schedule follow-up date, time, priority (`LOW`, `MEDIUM`, `HIGH`), notes, and status (`Pending`, `Completed`, `Cancelled`).
   - Upcoming follow-ups widget on Dashboard.

4. **Excel Lead Import & Duplicate Detection**:
   - Download Excel `.xlsx` template.
   - Upload Excel leads with automatic column validation.
   - Detect duplicate phone numbers and duplicate emails (against DB & within file).
   - Show import summary (Total Rows, Imported, Duplicates, Invalid).
   - Download invalid/duplicate error rows as an `.xlsx` file.
   - Imported leads automatically tagged with `source = "Excel"`.

5. **Customer Conversion**:
   - One-click lead conversion (`CONVERTED`).
   - Customer directory (`customers` table) linked to lead origin history.

6. **Dashboard & Analytics**:
   - Total Leads, New Leads, Follow-up Leads, Total Customers.
   - Source distribution (Meta Ads vs Excel vs Manual).
   - Employee productivity & lead assignment metrics.

7. **Meta Lead Ads Integration (`backend/integrations/meta/`)**:
   - Dedicated webhook route `POST /api/integrations/meta/webhook` and verification `GET /api/integrations/meta/webhook`.
   - Graph API details fetching & automatic MySQL lead creation with `source = "Meta Ads"`.

8. **WhatsApp & IVR Service Architecture**:
   - Provider-independent service layers in `backend/integrations/whatsapp/` and `backend/integrations/ivr/`.

9. **Native Quotations, Proformas & Invoicing Studio**:
   - 100% natively built into Wa CRM — no external or secondary server required!
   - 1-click Quotation / Proforma generation directly from Leads and Customer profiles with automatic contact and address prefilling.
   - Dynamic line items grid with presets, custom unit rates, discounts, and HSN codes.
   - Dual-mode Indian GST Engine: Intra-State (Tamil Nadu: CGST 50% + SGST 50%) vs Inter-State (IGST 100%) with round-off and amount in words (Lakhs & Crores).
   - Instant client-side PDF generation & download powered by `pdfmake`.
   - Native MySQL storage with automatic lead timeline activity logging.

---

## 🚀 How to Run the Project Locally

### Unified One-Click Dev Runner:
Run `run_dev_all.bat` from the root of `Wa CRM` to start:
- FastAPI Backend on `http://127.0.0.1:8000`
- React (Vite) Frontend on `http://localhost:5173`

### 1. Database Setup
Make sure MySQL server is running on `localhost:3306` with database `wa_crm`:
```sql
CREATE DATABASE IF NOT EXISTS wa_crm CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2. Backend Setup & Startup
```bash
cd backend

# Create & activate Python virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1   # On Windows

# Install Python requirements
pip install -r requirements.txt

# Start FastAPI Uvicorn Server
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
* **API Documentation (Swagger UI)**: `http://localhost:8000/docs`

### 3. Frontend Setup & Startup
```bash
cd frontend

# Install Node dependencies
npm install

# Start Vite Development Server
npm run dev
```
* **Web Application**: `http://localhost:5173`

---


