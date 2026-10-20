from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from database import get_db
from models.user import User
from models.notification import Notification
from services.auth import get_current_user
from services.notification_service import sync_notifications_from_real_data, create_notification

router = APIRouter(prefix="/notifications", tags=["Notifications"])

class NotificationOut(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    notification_type: str
    link_url: Optional[str] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

@router.get("", response_model=List[NotificationOut])
def get_notifications(
    is_read: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetch all real CRM notifications for the authenticated user.
    If no notifications exist, automatically syncs from real CRM events (leads, followups, calls, conversions).
    """
    user_count = db.query(Notification).filter(Notification.user_id == current_user.id).count()
    if user_count == 0:
        sync_notifications_from_real_data(db, user_id=current_user.id)

    query = db.query(Notification).filter(Notification.user_id == current_user.id)

    if is_read is not None:
        query = query.filter(Notification.is_read == is_read)

    notifications = query.order_by(desc(Notification.created_at), desc(Notification.id)).limit(limit).all()
    return notifications

@router.put("/{notification_id}/read", response_model=NotificationOut)
def toggle_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Toggle or mark a specific notification as read/unread.
    """
    notif = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()

    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    notif.is_read = not notif.is_read
    db.commit()
    db.refresh(notif)
    return notif

@router.post("/mark-all-read")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mark all notifications for the current user as read.
    """
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).update({"is_read": True}, synchronize_session=False)

    db.commit()
    return {"message": "All notifications marked as read"}

@router.delete("/clear-all")
def clear_all_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete all notifications for the current user.
    """
    db.query(Notification).filter(Notification.user_id == current_user.id).delete(synchronize_session=False)
    db.commit()
    return {"message": "All notifications cleared"}

@router.delete("/{notification_id}")
def delete_single_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a specific notification.
    """
    notif = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()

    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    db.delete(notif)
    db.commit()
    return {"message": "Notification deleted"}

@router.post("/sync")
def trigger_sync_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manually sync new CRM events into notifications.
    """
    sync_notifications_from_real_data(db, user_id=current_user.id)
    return {"message": "Notifications synced successfully from CRM database"}
