import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from services.auth import get_current_user, require_roles
from integrations.quotetask.service import QuoteTaskService

logger = logging.getLogger("quotetask_router")

router = APIRouter(prefix="/integrations/quotetask", tags=["QuoteTask Integration"])

@router.post("/test")
def test_quotetask_connection(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "MANAGER"]))
):
    """
    Test REST connection to QuoteTask API server.
    """
    success, message, error_details = QuoteTaskService.test_connection(db)
    return {
        "success": success,
        "message": message,
        "error_details": error_details
    }

@router.post("/webhook")
async def quotetask_webhook_receiver(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Public REST Webhook Receiver for incoming QuoteTask event notifications.
    Updates CRM Lead mapped quotation & PO status automatically and logs timeline activity.
    """
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Invalid JSON payload in QuoteTask webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    headers = dict(request.headers)
    result = QuoteTaskService.handle_incoming_webhook(db, payload, headers)
    return result
