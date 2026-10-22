import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("wacrm")

from config import settings
from database import engine, Base, SessionLocal
from models import User, Employee
from services.auth import hash_password

from routers import (
    auth,
    users,
    employees,
    leads,
    customers,
    followups,
    reports,
    integrations,
    ivr,
    whatsapp,
    employee_monitoring,
    delete_requests,
    activities,
    notifications,
    workflow,
    roles,
    doocti,
    field_visits
)

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

app = FastAPI(
    title="WaCRM API",
    description="Production-structured WaCRM API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

origins = [
    "http://www.wapluscrm.in",
    "https://www.wapluscrm.in",
    "http://wapluscrm.in",
    "https://wapluscrm.in",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost",
    "http://127.0.0.1",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=r".*",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount upload directory for file attachments / exports
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

from integrations.meta.webhook import router as meta_webhook_router
from integrations.website.router import router as website_lead_router
from integrations.whatsapp.webhook import webhook_router as whatsapp_webhook_router
from integrations.quotetask.router import router as quotetask_router
from integrations.waquote.router import router as waquote_router
from integrations.proforma.router import router as proforma_integration_router

# Register Routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(users.router, prefix=settings.API_V1_STR)
app.include_router(employees.router, prefix=settings.API_V1_STR)
app.include_router(leads.router, prefix=settings.API_V1_STR)
app.include_router(customers.router, prefix=settings.API_V1_STR)
app.include_router(followups.router, prefix=settings.API_V1_STR)
app.include_router(reports.router, prefix=settings.API_V1_STR)
app.include_router(integrations.router, prefix=settings.API_V1_STR)
app.include_router(ivr.router, prefix=settings.API_V1_STR)
app.include_router(whatsapp.router, prefix=settings.API_V1_STR)
app.include_router(employee_monitoring.router, prefix=settings.API_V1_STR)
app.include_router(field_visits.router, prefix=settings.API_V1_STR)
app.include_router(field_visits.router)  # Allow direct /api/field-visits endpoint
app.include_router(delete_requests.router, prefix=settings.API_V1_STR)
app.include_router(activities.router, prefix=settings.API_V1_STR)
app.include_router(activities.router)  # Allow direct /api/activities endpoint
app.include_router(notifications.router, prefix=settings.API_V1_STR)
app.include_router(meta_webhook_router, prefix=settings.API_V1_STR)
app.include_router(website_lead_router, prefix=settings.API_V1_STR)
app.include_router(whatsapp_webhook_router, prefix=settings.API_V1_STR)
app.include_router(quotetask_router, prefix=settings.API_V1_STR)
app.include_router(waquote_router, prefix=settings.API_V1_STR)
app.include_router(proforma_integration_router, prefix=settings.API_V1_STR)
app.include_router(workflow.router, prefix=settings.API_V1_STR)
app.include_router(roles.router, prefix=settings.API_V1_STR)
app.include_router(doocti.router, prefix=settings.API_V1_STR)
app.include_router(doocti.router, prefix="/api") # Allow /api/doocti/... paths
app.include_router(doocti.router, prefix="/api/v1") # Allow /api/v1/doocti/... paths
app.include_router(doocti.router)  # Also allow direct /doocti/... paths

@app.on_event("startup")
def startup_db_client():
    # Initialize Database Tables
    try:
        Base.metadata.create_all(bind=engine)
        print("Database tables created/verified successfully.")
        
        # Ensure column schema synchronization for leads and call_logs tables
        from sqlalchemy import text
        with engine.connect() as conn:
            try:
                result = conn.execute(text("SHOW COLUMNS FROM leads"))
                columns = [row[0] for row in result.fetchall()]
                missing_cols = {
                    "website_id": "VARCHAR(50) NULL",
                    "website_name": "VARCHAR(100) NULL",
                    "landing_page": "VARCHAR(255) NULL",
                    "quotetask_quotation_id": "VARCHAR(100) NULL",
                    "quotetask_quotation_number": "VARCHAR(100) NULL",
                    "quotetask_quotation_status": "VARCHAR(50) NULL",
                    "quotetask_quotation_amount": "FLOAT NULL",
                    "quotetask_quotation_url": "VARCHAR(255) NULL",
                    "quotetask_po_id": "VARCHAR(100) NULL",
                    "quotetask_po_number": "VARCHAR(100) NULL",
                    "quotetask_po_status": "VARCHAR(50) NULL",
                    "quotetask_synced_at": "DATETIME NULL",
                    "is_reinquiry": "BOOLEAN DEFAULT FALSE",
                    "reinquiry_count": "INT DEFAULT 0",
                    "total_enquiries": "INT DEFAULT 1",
                    "first_enquiry_date": "DATETIME NULL",
                    "latest_enquiry_date": "DATETIME NULL",
                    "previous_sources": "VARCHAR(255) NULL",
                    "latest_source": "VARCHAR(50) NULL"
                }
                for col_name, col_type in missing_cols.items():
                    if col_name not in columns:
                        conn.execute(text(f"ALTER TABLE leads ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
                        print(f"Auto-added missing column '{col_name}' to 'leads' table.")
            except Exception as ex:
                print(f"Leads column sync check: {ex}")

            # Call logs table schema sync
            try:
                for col_sql in [
                    "ALTER TABLE call_logs ADD COLUMN transcript TEXT NULL",
                    "ALTER TABLE call_logs ADD COLUMN ai_summary TEXT NULL",
                    "ALTER TABLE call_logs ADD COLUMN sentiment VARCHAR(50) NULL"
                ]:
                    try:
                        conn.execute(text(col_sql))
                        conn.commit()
                    except Exception:
                        pass
            except Exception as ex:
                print(f"Call logs column sync check: {ex}")

            # lead_assignments table schema sync
            try:
                result = conn.execute(text("SHOW COLUMNS FROM lead_assignments"))
                la_cols = [row[0] for row in result.fetchall()]
                if "assignment_method" not in la_cols:
                    conn.execute(text("ALTER TABLE lead_assignments ADD COLUMN assignment_method VARCHAR(50) DEFAULT 'MANUAL'"))
                    conn.commit()
                if "notes" not in la_cols:
                    conn.execute(text("ALTER TABLE lead_assignments ADD COLUMN notes TEXT NULL"))
                    conn.commit()
                conn.execute(text("ALTER TABLE lead_assignments MODIFY COLUMN assigned_by INT NULL"))
                conn.commit()
                print("Lead assignments table schema synchronized successfully.")
            except Exception as ex:
                print(f"Lead assignments column sync check: {ex}")

            # lead_activities table schema sync
            try:
                result = conn.execute(text("SHOW COLUMNS FROM lead_activities"))
                act_cols = [row[0] for row in result.fetchall()]
                missing_act_cols = {
                    "customer_id": "INT NULL",
                    "employee_id": "INT NULL",
                    "related_entity_type": "VARCHAR(50) NULL",
                    "related_entity_id": "INT NULL"
                }
                for col_name, col_type in missing_act_cols.items():
                    if col_name not in act_cols:
                        conn.execute(text(f"ALTER TABLE lead_activities ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
                conn.execute(text("ALTER TABLE lead_activities MODIFY COLUMN lead_id INT NULL"))
                conn.commit()
                print("Lead activities table schema synchronized successfully.")
            except Exception as ex:
                print(f"Lead activities column sync check: {ex}")

            # followups table schema sync for automatic reminders
            try:
                result = conn.execute(text("SHOW COLUMNS FROM followups"))
                fu_cols = [row[0] for row in result.fetchall()]
                missing_fu_cols = {
                    "reminder_sent": "BOOLEAN DEFAULT FALSE NOT NULL",
                    "reminder_sent_at": "DATETIME NULL",
                    "snoozed_until": "DATETIME NULL",
                    "reminder_dismissed": "BOOLEAN DEFAULT FALSE NOT NULL"
                }
                for col_name, col_type in missing_fu_cols.items():
                    if col_name not in fu_cols:
                        conn.execute(text(f"ALTER TABLE followups ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
                        print(f"Auto-added missing column '{col_name}' to 'followups' table.")
            except Exception as ex:
                print(f"Followups column sync check: {ex}")

            # field_visits table schema sync
            try:
                result = conn.execute(text("SHOW COLUMNS FROM field_visits"))
                fv_cols = [row[0] for row in result.fetchall()]
                missing_fv_cols = {
                    "customer_id": "INT NULL",
                    "checkin_address": "VARCHAR(255) NULL",
                    "visiting_card_url": "TEXT NULL",
                    "customer_requirements": "TEXT NULL",
                    "visit_outcome": "VARCHAR(100) NULL",
                    "followup_id": "INT NULL",
                    "client_token": "VARCHAR(100) NULL"
                }
                for col_name, col_type in missing_fv_cols.items():
                    if col_name not in fv_cols:
                        conn.execute(text(f"ALTER TABLE field_visits ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
                        print(f"Auto-added missing column '{col_name}' to 'field_visits' table.")
            except Exception as ex:
                print(f"Field visits column sync check: {ex}")
            # quotations table schema sync
            try:
                result = conn.execute(text("SHOW COLUMNS FROM quotations"))
                q_cols = [row[0] for row in result.fetchall()]
                missing_q_cols = {
                    "created_by": "INT NULL",
                    "created_by_user_id": "INT NULL",
                    "assigned_to": "INT NULL"
                }
                for col_name, col_type in missing_q_cols.items():
                    if col_name not in q_cols:
                        conn.execute(text(f"ALTER TABLE quotations ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
                        print(f"Auto-added missing column '{col_name}' to 'quotations' table.")
            except Exception as ex:
                print(f"Quotations column sync check: {ex}")
    except Exception as e:
        print(f"Error creating/synchronizing database tables: {e}")

    # Launch Dynamic Lead Auto-Assignment Background Scheduler
    try:
        import asyncio
        from services.lead_assignment_service import start_auto_assignment_scheduler, get_or_create_auto_assign_config
        
        # Ensure default configuration row exists
        db_init = SessionLocal()
        try:
            get_or_create_auto_assign_config(db_init)
        finally:
            db_init.close()

        asyncio.create_task(start_auto_assignment_scheduler(interval_seconds=60))
        print("Dynamic Lead Auto-Assignment background scheduler launched.")
    except Exception as ex:
        print(f"Failed to start lead auto-assignment scheduler: {ex}")

    # Launch Follow-up 1-Hour Reminder Background Scheduler
    try:
        import asyncio
        from services.followup_reminder_service import start_followup_reminder_scheduler
        asyncio.create_task(start_followup_reminder_scheduler(interval_seconds=60))
        print("Follow-up 1-Hour Reminder background scheduler launched.")
    except Exception as ex:
        print(f"Failed to start follow-up reminder scheduler: {ex}")

    # Seed initial Admin, Manager, and Employee users if not existing
    db = SessionLocal()
    try:
        # 1. Admin User
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            admin_user = User(
                username="admin",
                hashed_password=hash_password("admin123"),
                role="ADMIN",
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)

            admin_employee = Employee(
                user_id=admin_user.id,
                name="System Administrator",
                email="admin@company.com",
                phone="1234567890",
                username="admin",
                role="ADMIN",
                status="ACTIVE"
            )
            db.add(admin_employee)
            db.commit()

        # Seed default roles & permission matrix if not yet created
        from services.permission_service import seed_default_roles_if_needed
        seed_default_roles_if_needed(db)

        print("Default admin and roles initialized.")
    except Exception as e:
        print(f"Error initializing admin user: {e}")
        db.rollback()
    finally:
        db.close()

@app.get("/")
def root():
    return {
        "message": "Welcome to Internal Company CRM API",
        "docs": "/docs",
        "health": "OK"
    }
