from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime
from models.audit_log import AuditLog

def log_audit(
    db: Session,
    user_id: Optional[int],
    username: str,
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    details: Optional[str] = None,
    ip_address: Optional[str] = None
):
    try:
        log = AuditLog(
            user_id=user_id,
            username=username,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            details=details,
            ip_address=ip_address,
            created_at=datetime.utcnow()
        )
        db.add(log)
        db.commit()
    except Exception as e:
        print(f"Failed to record audit log: {e}")
        db.rollback()
