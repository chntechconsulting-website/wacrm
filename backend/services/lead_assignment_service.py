import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, desc

from database import SessionLocal
from models.employee import Employee
from models.user import User
from models.lead import Lead, LeadAssignment, AutoAssignConfig
from models.activity import LeadActivity

logger = logging.getLogger("lead_assignment")

TERMINAL_STATUSES = ["CONVERTED", "WON", "LOST", "NOT_INTERESTED"]

def get_or_create_auto_assign_config(db: Session) -> AutoAssignConfig:
    """
    Retrieves or initializes the Auto Assignment Configuration from the database.
    """
    cfg = db.query(AutoAssignConfig).filter(AutoAssignConfig.id == 1).first()
    if not cfg:
        cfg = AutoAssignConfig(
            id=1,
            enabled=True,
            waiting_time_minutes=60,
            assignment_method="LEAST_ASSIGNED",
            eligible_roles="EMPLOYEE,MANAGER",
            working_hours_enabled=False,
            working_hours_start="09:00",
            working_hours_end="18:00"
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg

def get_eligible_employees(db: Session, config: AutoAssignConfig) -> List[Employee]:
    """
    Returns list of active, eligible employees who can receive auto-assigned leads.
    Filters by employee active status, linked user active status, and configured roles.
    """
    roles = [r.strip().upper() for r in (config.eligible_roles or "EMPLOYEE,MANAGER").split(",") if r.strip()]
    if not roles:
        roles = ["EMPLOYEE", "MANAGER"]

    query = db.query(Employee).outerjoin(User, Employee.user_id == User.id)\
        .filter(Employee.status == "ACTIVE")\
        .filter(or_(Employee.user_id == None, User.is_active == True))\
        .filter(Employee.role.in_(roles))
    
    return query.all()

def get_employee_workload(db: Session, employee_id: int) -> int:
    return db.query(Lead).filter(
        Lead.assigned_to == employee_id,
        ~Lead.status.in_(TERMINAL_STATUSES)
    ).count()

def get_last_assignment_time(db: Session, employee_id: int) -> datetime:
    last_assignment = db.query(LeadAssignment.assigned_at)\
        .filter(LeadAssignment.assigned_to == employee_id)\
        .order_by(desc(LeadAssignment.assigned_at))\
        .first()
    
    if last_assignment and last_assignment[0]:
        return last_assignment[0]
    return datetime.min

def select_eligible_assignee(db: Session, config: AutoAssignConfig) -> Optional[Employee]:
    """
    Selects the best eligible employee according to the configured assignment method:
    - LEAST_ASSIGNED: Workload balancing (lowest active lead count)
    - ROUND_ROBIN: Sequential order (least recently assigned)
    - HIERARCHICAL: Employee role priority first, then workload balancing
    """
    eligible = get_eligible_employees(db, config)
    if not eligible:
        logger.warning("No eligible active employees found for lead auto-assignment.")
        return None

    method = (config.assignment_method or "LEAST_ASSIGNED").upper()

    if method == "ROUND_ROBIN":
        # Primary: last_assigned_at ascending, Secondary: workload ascending
        eligible.sort(key=lambda emp: (get_last_assignment_time(db, emp.id), get_employee_workload(db, emp.id), emp.id))
    elif method == "HIERARCHICAL":
        # Role rank: EMPLOYEE (1), MANAGER (2), then workload
        role_rank = lambda emp: 1 if emp.role == "EMPLOYEE" else 2
        eligible.sort(key=lambda emp: (role_rank(emp), get_employee_workload(db, emp.id), get_last_assignment_time(db, emp.id), emp.id))
    else:  # LEAST_ASSIGNED
        # Primary: workload ascending, Secondary: last_assigned_at ascending
        eligible.sort(key=lambda emp: (get_employee_workload(db, emp.id), get_last_assignment_time(db, emp.id), emp.id))

    return eligible[0]

def is_within_working_hours(config: AutoAssignConfig) -> bool:
    """
    Checks if current local time is within configured working hours.
    """
    if not config.working_hours_enabled:
        return True

    try:
        now_time = datetime.now().time()
        start_t = datetime.strptime(config.working_hours_start or "09:00", "%H:%M").time()
        end_t = datetime.strptime(config.working_hours_end or "18:00", "%H:%M").time()
        
        if start_t <= end_t:
            return start_t <= now_time <= end_t
        else: # Overnight shift (e.g. 22:00 to 06:00)
            return now_time >= start_t or now_time <= end_t
    except Exception as e:
        logger.error(f"Error evaluating working hours: {e}")
        return True

def auto_assign_pending_leads(db: Session, override_timeout_minutes: Optional[int] = None) -> int:
    """
    Dynamically fetches config from DB, checks if enabled and within working hours,
    and assigns unassigned leads older than the configured waiting time.
    """
    config = get_or_create_auto_assign_config(db)

    if not config.enabled:
        logger.debug("Auto lead assignment is currently disabled in Admin settings.")
        return 0

    if not is_within_working_hours(config):
        logger.debug("Current time is outside configured Working Hours. Skipping auto-assignment.")
        return 0

    waiting_mins = override_timeout_minutes if override_timeout_minutes is not None else config.waiting_time_minutes
    cutoff = datetime.utcnow() - timedelta(minutes=waiting_mins)
    
    unassigned_leads = db.query(Lead).filter(
        Lead.assigned_to == None,
        Lead.created_at <= cutoff
    ).order_by(Lead.created_at.asc()).all()

    if not unassigned_leads:
        return 0

    assigned_count = 0
    now = datetime.utcnow()

    for lead in unassigned_leads:
        # Atomic lock/re-check: ensure lead is still unassigned
        target_lead = db.query(Lead).filter(Lead.id == lead.id, Lead.assigned_to == None).first()
        if not target_lead:
            logger.info(f"Lead #{lead.id} was assigned manually or concurrently. Skipping auto-assignment.")
            continue

        assignee = select_eligible_assignee(db, config)
        if not assignee:
            logger.warning(f"Could not auto-assign Lead #{lead.id}: No eligible employees available.")
            continue

        # Execute Auto-Assignment
        target_lead.assigned_to = assignee.id
        target_lead.assigned_by = None  # System auto-assignment
        target_lead.assigned_at = now

        if target_lead.status == "NEW":
            target_lead.status = "ASSIGNED"

        # Format waiting time label
        wait_label = f"{waiting_mins} mins" if waiting_mins < 60 else f"{waiting_mins // 60} hour(s)"

        # Log Assignment Record with AUTOMATIC method
        assignment_history = LeadAssignment(
            lead_id=target_lead.id,
            assigned_to=assignee.id,
            assigned_by=None,
            assigned_at=now,
            assignment_method="AUTOMATIC",
            notes=f"Auto-assigned after {wait_label} timeout using {config.assignment_method} strategy."
        )
        db.add(assignment_history)

        # Log Activity Timeline
        activity = LeadActivity(
            lead_id=target_lead.id,
            performed_by=None,
            activity_type="AUTO_ASSIGNED",
            description=f"System automatically assigned lead to {assignee.name} after {wait_label} unassigned timeout",
            created_at=now
        )
        db.add(activity)

        db.commit()
        assigned_count += 1
        logger.info(f"Auto-assigned Lead #{target_lead.id} ({target_lead.name}) to Employee #{assignee.id} ({assignee.name}).")

    return assigned_count

async def start_auto_assignment_scheduler(interval_seconds: int = 60):
    """
    Async background task running in backend process.
    Periodically checks DB configuration and executes auto-assignment.
    """
    logger.info(f"Starting Dynamic Lead Auto-Assignment Background Scheduler (Check Interval: {interval_seconds}s).")
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            db = SessionLocal()
            try:
                assigned = auto_assign_pending_leads(db)
                if assigned > 0:
                    logger.info(f"Auto-assignment run complete. Assigned {assigned} leads.")
            finally:
                db.close()
        except asyncio.CancelledError:
            logger.info("Lead Auto-Assignment background task cancelled.")
            break
        except Exception as e:
            logger.error(f"Error in lead auto-assignment background scheduler: {e}", exc_info=True)
