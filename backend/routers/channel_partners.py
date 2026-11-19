"""CRM-facing, read-only Channel Partner endpoints.

Every response is served from the local mirror created by
``services.channel_partner_sync``. Secrets, full PAN, bank account numbers and
document links are never returned by these routes. Application document links
are proxied through a separately authorised, audited endpoint.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from database import get_db
from integrations.wahrms_channel_partner.client import (
    ChannelPartnerAPIError,
    ChannelPartnerClient,
    ChannelPartnerNotConfigured,
)
from integrations.wahrms_channel_partner.config import (
    WEBHOOK_PATH,
    effective_webhook_secret,
    get_integration_row,
    get_webhook_url,
    load_effective_config,
    mask_secret,
    save_configuration,
)
from integrations.wahrms_channel_partner.normalizers import (
    as_json,
    extract_object,
    first_present,
    ist_iso,
)
from models.channel_partner import (
    ChannelPartner,
    ChannelPartnerApplication,
    ChannelPartnerClientAttribution,
    ChannelPartnerCommission,
    ChannelPartnerCoupon,
    ChannelPartnerLead,
    ChannelPartnerLogin,
    ChannelPartnerPayout,
    ChannelPartnerSyncCheckpoint,
    ChannelPartnerSyncRun,
    ChannelPartnerWebhookEvent,
)
from models.lead import Lead, LeadStatusHistory
from models.activity import LeadActivity
from models.user import User
from services.audit import log_audit
from services.auth import get_current_user, require_admin
from services.channel_partner_sync import (
    APPLICATION_STATUSES,
    CHANNEL_PARTNER_STATUSES,
    CHANNEL_PARTNER_TO_CRM_STATUS,
    COMMISSION_STATUSES,
    LEAD_STATUSES,
    PARTNER_STATUSES,
    PAYOUT_STATUSES,
    ChannelPartnerStatusSyncError,
    checkpoint_snapshot,
    create_sync_run,
    execute_sync_run,
    map_crm_status_to_channel_partner,
    normalize_crm_status,
    process_webhook_event,
    retry_channel_partner_status_sync,
    run_event_poll,
    sync_channel_partner_status_for_lead,
    validate_channel_partner_status_change,
    validate_channel_partner_transition,
)
from services.permission_service import user_has_permission
from utils.timezone import get_ist_now

router = APIRouter(prefix="/channel-partners", tags=["Channel Partners"])

SYNC_SCOPES = {"full", "summary", "partners", "applications", "leads", "payouts", "events"}


def require_channel_partner_view(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    if (current_user.role or "").upper() == "ADMIN":
        return current_user
    if user_has_permission(current_user, "channel_partners", "view", db):
        return current_user
    raise HTTPException(
        status_code=403,
        detail="Forbidden: You do not have permission to view Channel Partners.",
    )


def require_channel_partner_edit(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    if (current_user.role or "").upper() == "ADMIN":
        return current_user
    if user_has_permission(current_user, "channel_partners", "edit", db):
        return current_user
    raise HTTPException(
        status_code=403,
        detail="Forbidden: You do not have permission to update Channel Partner leads.",
    )


def require_channel_partner_document_access(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    if (current_user.role or "").upper() == "ADMIN":
        return current_user
    if user_has_permission(current_user, "channel_partners", "edit", db) or user_has_permission(
        current_user, "channel_partners", "approve", db
    ):
        return current_user
    raise HTTPException(
        status_code=403,
        detail=(
            "Forbidden: Viewing PAN/Aadhaar identity documents requires "
            "Channel Partner edit or approval permission."
        ),
    )


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------
def _page(query, page: int, limit: int):
    page = max(1, int(page or 1))
    limit = max(1, min(int(limit or 25), 200))
    total = query.count()
    rows = query.offset((page - 1) * limit).limit(limit).all()
    return rows, total, page, limit


def _page_meta(total: int, page: int, limit: int) -> Dict[str, Any]:
    pages = (total + limit - 1) // limit if limit else 0
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
        "hasNext": page < pages,
        "hasPrev": page > 1,
    }


def _partner_summary(row: ChannelPartner) -> Dict[str, Any]:
    return {
        "id": row.external_id,
        "name": row.name,
        "code": row.code,
        "entityType": row.entity_type,
        "legalName": row.legal_name,
        "email": row.email,
        "phone": row.phone,
        "city": row.city,
        "state": row.state,
        "status": row.status,
        "commissionRateBps": row.commission_rate_bps,
        "payoutFrequency": row.payout_frequency,
        "panMasked": row.pan_masked,
        "gstRegistered": row.gst_registered,
        "gstin": row.gstin,
        "syncedAt": ist_iso(row.synced_at),
        "sourceUpdatedAt": ist_iso(row.source_updated_at),
    }


def _partner_detail(row: ChannelPartner, logins: List[ChannelPartnerLogin]) -> Dict[str, Any]:
    payload = _partner_summary(row)
    payload.update(
        {
            "address": {
                "line1": row.address_line1,
                "line2": row.address_line2,
                "city": row.city,
                "state": row.state,
                "stateCode": row.state_code,
                "pincode": row.pincode,
            },
            "panMasked": row.pan_masked,
            "panLast4": row.pan_last4,
            "panPresent": row.pan_present,
            "gstRateBps": row.gst_rate_bps,
            "holdDays": row.hold_days,
            "minPayoutPaise": row.min_payout_paise,
            "firstClientDiscountBps": row.first_client_discount_bps,
            "tdsCertificate": {
                "rateBps": row.tds_certificate_rate_bps,
                "number": row.tds_certificate_number,
                "validUntil": row.tds_certificate_valid_until.isoformat()
                if row.tds_certificate_valid_until
                else None,
            },
            "notes": row.notes,
            "balances": row.balances_json,
            "monthlyCommissionSeries": row.monthly_commission_series_json,
            "tdsStatus": row.tds_status_json,
            "inactivityStatus": row.inactivity_status_json,
            "firstClientOffer": row.first_client_offer_json,
            "applicationDocuments": row.application_documents_json,
            "logins": [
                {
                    "id": login.external_id,
                    "name": login.name,
                    "email": login.email,
                    "phone": login.phone,
                    "role": login.role,
                    "isActive": login.is_active,
                    "inviteStatus": login.invite_status,
                    "invitedAt": ist_iso(login.invited_at),
                    "lastLoginAt": ist_iso(login.last_login_at),
                }
                for login in logins
            ],
            "sourceCreatedAt": ist_iso(row.source_created_at),
            "syncedAt": ist_iso(row.synced_at),
            "raw": row.detail_raw or row.list_raw,
        }
    )
    return payload


def _application_summary(row: ChannelPartnerApplication) -> Dict[str, Any]:
    return {
        "id": row.external_id,
        "entityType": row.entity_type,
        "businessName": row.business_name,
        "businessType": row.business_type,
        "teamSize": row.team_size,
        "yearsInBusiness": row.years_in_business,
        "website": row.website,
        "contactName": row.contact_name,
        "designation": row.designation,
        "email": row.email,
        "phone": row.phone,
        "city": row.city,
        "state": row.state,
        "status": row.status,
        "panMasked": row.pan_masked,
        "gstin": row.gstin,
        "createdAt": ist_iso(row.source_created_at),
        "syncedAt": ist_iso(row.synced_at),
    }


def _application_detail(row: ChannelPartnerApplication) -> Dict[str, Any]:
    payload = _application_summary(row)
    payload.update(
        {
            "address": {
                "line1": row.address_line1,
                "line2": row.address_line2,
                "city": row.city,
                "state": row.state,
                "stateCode": row.state_code,
                "pincode": row.pincode,
            },
            "regions": row.regions,
            "industries": row.industries_json,
            "currentClients": row.current_clients,
            "expectedClients": row.expected_clients,
            "heardFrom": row.heard_from,
            "message": row.message,
            "consent": row.consent,
            "reviewNote": row.review_note,
            "reviewedAt": ist_iso(row.reviewed_at),
            "partnerExternalId": row.partner_external_id,
            "documents": row.document_metadata_json,
            "sourceUpdatedAt": ist_iso(row.source_updated_at),
            "raw": row.raw_data,
        }
    )
    return payload


def _lead_payload(
    row: ChannelPartnerLead,
    *,
    include_raw: bool = False,
    crm_lead: Optional[Lead] = None,
) -> Dict[str, Any]:
    payload = {
        "id": row.external_id,
        "partnerId": row.partner_external_id,
        "partnerName": row.partner_name,
        "status": row.status,
        "companyName": row.company_name,
        "contactName": row.contact_name,
        "email": row.email,
        "phone": row.phone,
        "city": row.city,
        "state": row.state,
        "source": row.source,
        "message": row.message,
        "reviewNote": row.review_note,
        "reviewedAt": ist_iso(row.reviewed_at),
        "organizationId": row.organization_id,
        "subscriptionOrderId": row.subscription_order_id,
        "convertedAt": ist_iso(row.converted_at),
        "protectionUntil": ist_iso(row.protection_until),
        "createdAt": ist_iso(row.source_created_at),
        "updatedAt": ist_iso(row.source_updated_at),
        "syncedAt": ist_iso(row.synced_at),
    }
    if crm_lead is not None:
        payload.update(
            {
                "crmLeadId": crm_lead.id,
                "crmStatus": crm_lead.status,
                "syncStatus": crm_lead.channel_partner_sync_status,
                "lastSyncedAt": ist_iso(crm_lead.channel_partner_last_synced_at),
                "lastSyncError": crm_lead.channel_partner_last_sync_error,
                "pendingStatus": crm_lead.channel_partner_pending_status,
            }
        )
    else:
        payload.update(
            {
                "crmLeadId": None,
                "crmStatus": None,
                "syncStatus": None,
                "lastSyncedAt": None,
                "lastSyncError": None,
                "pendingStatus": None,
            }
        )
    if include_raw:
        payload["raw"] = row.raw_data
    return payload


def _client_payload(row: ChannelPartnerClientAttribution, *, include_raw: bool = False) -> Dict[str, Any]:
    payload = {
        "id": row.external_id or row.record_key,
        "attributionId": row.external_id,
        "partnerId": row.partner_external_id,
        "organizationId": row.organization_id,
        "organizationName": row.organization_name,
        "subscriptionOrderId": row.subscription_order_id,
        "orderNumber": row.order_number,
        "status": row.status,
        "effectiveFrom": ist_iso(row.effective_from),
        "endedAt": ist_iso(row.ended_at),
        "endReason": row.end_reason,
        "createdAt": ist_iso(row.source_created_at),
        "updatedAt": ist_iso(row.source_updated_at),
        "attribution": row.attribution_data,
    }
    if include_raw:
        payload["raw"] = row.raw_data
    return payload


def _coupon_payload(row: ChannelPartnerCoupon, *, include_raw: bool = False) -> Dict[str, Any]:
    payload = {
        "id": row.external_id or row.record_key,
        "couponId": row.external_id,
        "partnerId": row.partner_external_id,
        "code": row.code,
        "status": row.status,
        "description": row.description,
        "discountBps": row.discount_bps,
        "assignedAt": ist_iso(row.assigned_at),
        "expiresAt": ist_iso(row.expires_at),
        "details": row.details_json,
        "updatedAt": ist_iso(row.source_updated_at),
    }
    if include_raw:
        payload["raw"] = row.raw_data
    return payload


def _commission_payload(row: ChannelPartnerCommission, *, include_raw: bool = False) -> Dict[str, Any]:
    payload = {
        "id": row.external_id,
        "partnerId": row.partner_external_id,
        "description": row.description,
        "amountPaise": row.amount_paise,
        "basePaise": row.base_paise,
        "rateBps": row.rate_bps,
        "status": row.status,
        "holdUntil": ist_iso(row.hold_until),
        "invoiceNumber": row.invoice_number,
        "clientName": row.client_name,
        "type": row.entry_type,
        "reason": row.reason,
        "earnedAt": ist_iso(row.earned_at),
        "updatedAt": ist_iso(row.source_updated_at),
        "syncedAt": ist_iso(row.synced_at),
    }
    if include_raw:
        payload["raw"] = row.raw_data
    return payload


def _payout_payload(row: ChannelPartnerPayout, *, include_raw: bool = False) -> Dict[str, Any]:
    payload = {
        "id": row.external_id,
        "partnerId": row.partner_external_id,
        "partnerName": row.partner_name,
        "status": row.status,
        "grossPaise": row.gross_paise,
        "netPaise": row.net_paise,
        "tdsPaise": row.tds_paise,
        "gstPaise": row.gst_paise,
        "adjustmentPaise": row.adjustment_paise,
        "paymentMethod": row.payment_method,
        "paymentReference": row.payment_reference,
        "paymentDate": ist_iso(row.payment_date),
        "partnerInvoiceNumber": row.partner_invoice_number,
        "notes": row.notes,
        "cancellationReason": row.cancellation_reason,
        "createdAt": ist_iso(row.source_created_at),
        "updatedAt": ist_iso(row.source_updated_at),
        "syncedAt": ist_iso(row.synced_at),
    }
    if include_raw:
        payload["commissionEntries"] = row.commission_entries_json
        payload["raw"] = row.raw_data
    return payload


def _event_payload(row: ChannelPartnerWebhookEvent, *, include_payload: bool = False) -> Dict[str, Any]:
    payload = {
        "id": row.event_id,
        "databaseId": row.id,
        "type": row.event_type,
        "eventCreatedAt": ist_iso(row.event_created_at),
        "receivedAt": ist_iso(row.received_at),
        "processedAt": ist_iso(row.processed_at),
        "status": row.status,
        "error": row.error,
        "source": row.source,
        "deliveryId": row.delivery_id,
        "sequence": row.sequence,
        "partnerId": row.related_partner_external_id,
        "leadId": row.related_lead_external_id,
        "clientId": row.related_client_external_id,
    }
    if include_payload:
        try:
            import json

            payload["data"] = json.loads(row.payload or "{}")
        except Exception:
            payload["data"] = row.payload
        payload["headers"] = row.headers_json
    return payload


def _integration_public(db: Session) -> Dict[str, Any]:
    config = load_effective_config(db)
    integration = get_integration_row(db)
    webhook_secret, _ = effective_webhook_secret(db)
    checkpoint = (
        db.query(ChannelPartnerSyncCheckpoint)
        .filter(ChannelPartnerSyncCheckpoint.checkpoint_key == "events")
        .first()
    )
    return {
        "configured": config.configured,
        "lastSyncAt": ist_iso(integration.last_sync_at) if integration else None,
        "lastSyncStatus": integration.last_sync_status if integration else None,
        "lastEventPollAt": ist_iso(integration.last_event_poll_at) if integration else None,
        "webhookConfigured": bool(webhook_secret),
        "lastProcessedCheckpoint": int(checkpoint.last_after or 0) if checkpoint else 0,
        "readOnly": True,
        "scopes": ["read"],
    }


def _counts(db: Session) -> Dict[str, Any]:
    def grouped(model, column):
        return {
            (status or "unknown"): count
            for status, count in db.query(column, func.count(model.id)).group_by(column).all()
        }

    partner_counts = grouped(ChannelPartner, ChannelPartner.status)
    application_counts = grouped(ChannelPartnerApplication, ChannelPartnerApplication.status)
    lead_counts = grouped(ChannelPartnerLead, ChannelPartnerLead.status)
    payout_counts = grouped(ChannelPartnerPayout, ChannelPartnerPayout.status)

    commission_rows = (
        db.query(
            ChannelPartnerCommission.status,
            func.count(ChannelPartnerCommission.id),
            func.coalesce(func.sum(ChannelPartnerCommission.amount_paise), 0),
        )
        .group_by(ChannelPartnerCommission.status)
        .all()
    )
    commission_counts = {
        (status or "unknown"): {"count": count, "amountPaise": int(amount or 0)}
        for status, count, amount in commission_rows
    }

    return {
        "partners": {
            "total": db.query(func.count(ChannelPartner.id)).scalar() or 0,
            "byStatus": partner_counts,
        },
        "applications": {
            "total": db.query(func.count(ChannelPartnerApplication.id)).scalar() or 0,
            "byStatus": application_counts,
        },
        "leads": {
            "total": db.query(func.count(ChannelPartnerLead.id)).scalar() or 0,
            "byStatus": lead_counts,
        },
        "clients": {
            "total": db.query(func.count(ChannelPartnerClientAttribution.id)).scalar() or 0,
        },
        "coupons": {
            "total": db.query(func.count(ChannelPartnerCoupon.id)).scalar() or 0,
        },
        "commissions": {
            "total": db.query(func.count(ChannelPartnerCommission.id)).scalar() or 0,
            "byStatus": commission_counts,
        },
        "payouts": {
            "total": db.query(func.count(ChannelPartnerPayout.id)).scalar() or 0,
            "byStatus": payout_counts,
        },
        "events": {
            "total": db.query(func.count(ChannelPartnerWebhookEvent.id)).scalar() or 0,
            "failed": db.query(func.count(ChannelPartnerWebhookEvent.id))
            .filter(ChannelPartnerWebhookEvent.status == "failed")
            .scalar()
            or 0,
        },
    }


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------
@router.get("/overview")
def get_overview(
    db: Session = Depends(get_db),
    _: User = Depends(require_channel_partner_view),
):
    integration = get_integration_row(db)
    latest_run = (
        db.query(ChannelPartnerSyncRun)
        .order_by(ChannelPartnerSyncRun.id.desc())
        .first()
    )
    recent_events = (
        db.query(ChannelPartnerWebhookEvent)
        .order_by(ChannelPartnerWebhookEvent.received_at.desc())
        .limit(8)
        .all()
    )
    return {
        "summary": integration.summary_json if integration else None,
        "summarySyncedAt": ist_iso(integration.summary_synced_at) if integration else None,
        "counts": _counts(db),
        "integration": _integration_public(db),
        "latestSyncRun": {
            "id": latest_run.id,
            "scope": latest_run.scope,
            "trigger": latest_run.trigger,
            "status": latest_run.status,
            "startedAt": ist_iso(latest_run.started_at),
            "finishedAt": ist_iso(latest_run.finished_at),
            "stats": latest_run.stats_json,
            "error": latest_run.error,
        }
        if latest_run
        else None,
        "recentEvents": [_event_payload(event) for event in recent_events],
        "readOnly": True,
    }


# ---------------------------------------------------------------------------
# Partners
# ---------------------------------------------------------------------------
@router.get("/partners")
def list_partners(
    search: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_channel_partner_view),
):
    query = db.query(ChannelPartner)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                ChannelPartner.name.ilike(pattern),
                ChannelPartner.code.ilike(pattern),
                ChannelPartner.legal_name.ilike(pattern),
                ChannelPartner.email.ilike(pattern),
                ChannelPartner.city.ilike(pattern),
                ChannelPartner.gstin.ilike(pattern),
            )
        )
    if status:
        query = query.filter(ChannelPartner.status == status.lower())
    query = query.order_by(ChannelPartner.name.asc(), ChannelPartner.id.asc())
    rows, total, page, limit = _page(query, page, limit)
    return {
        "items": [_partner_summary(row) for row in rows],
        "pagination": _page_meta(total, page, limit),
    }


@router.get("/partners/{partner_id}")
def get_partner(
    partner_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_channel_partner_view),
):
    row = (
        db.query(ChannelPartner)
        .filter(ChannelPartner.external_id == partner_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Channel partner not found.")
    logins = (
        db.query(ChannelPartnerLogin)
        .filter(ChannelPartnerLogin.partner_external_id == partner_id)
        .order_by(ChannelPartnerLogin.id.asc())
        .all()
    )
    payload = _partner_detail(row, logins)
    is_admin = (current_user.role or "").upper() == "ADMIN"
    payload["permissions"] = {
        "canViewDocuments": is_admin
        or user_has_permission(current_user, "channel_partners", "edit", db)
        or user_has_permission(current_user, "channel_partners", "approve", db),
        "canSync": is_admin,
    }
    payload["relatedCounts"] = {
        "clients": db.query(func.count(ChannelPartnerClientAttribution.id))
        .filter(ChannelPartnerClientAttribution.partner_external_id == partner_id)
        .scalar()
        or 0,
        "coupons": db.query(func.count(ChannelPartnerCoupon.id))
        .filter(ChannelPartnerCoupon.partner_external_id == partner_id)
        .scalar()
        or 0,
        "commissions": db.query(func.count(ChannelPartnerCommission.id))
        .filter(ChannelPartnerCommission.partner_external_id == partner_id)
        .scalar()
        or 0,
        "leads": db.query(func.count(ChannelPartnerLead.id))
        .filter(ChannelPartnerLead.partner_external_id == partner_id)
        .scalar()
        or 0,
        "payouts": db.query(func.count(ChannelPartnerPayout.id))
        .filter(ChannelPartnerPayout.partner_external_id == partner_id)
        .scalar()
        or 0,
    }
    return payload


@router.get("/partners/{partner_id}/clients")
def list_partner_clients(
    partner_id: str,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_channel_partner_view),
):
    query = db.query(ChannelPartnerClientAttribution).filter(
        ChannelPartnerClientAttribution.partner_external_id == partner_id
    )
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                ChannelPartnerClientAttribution.organization_name.ilike(pattern),
                ChannelPartnerClientAttribution.organization_id.ilike(pattern),
                ChannelPartnerClientAttribution.subscription_order_id.ilike(pattern),
            )
        )
    rows, total, page, limit = _page(
        query.order_by(ChannelPartnerClientAttribution.id.desc()), page, limit
    )
    return {
        "items": [_client_payload(row) for row in rows],
        "pagination": _page_meta(total, page, limit),
    }


@router.get("/partners/{partner_id}/coupons")
def list_partner_coupons(
    partner_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_channel_partner_view),
):
    query = db.query(ChannelPartnerCoupon).filter(
        ChannelPartnerCoupon.partner_external_id == partner_id
    )
    rows, total, page, limit = _page(query.order_by(ChannelPartnerCoupon.id.desc()), page, limit)
    return {
        "items": [_coupon_payload(row) for row in rows],
        "pagination": _page_meta(total, page, limit),
    }


@router.get("/partners/{partner_id}/commissions")
def list_partner_commissions(
    partner_id: str,
    status: Optional[str] = None,
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_channel_partner_view),
):
    return _commission_list(
        db,
        partner_id=partner_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
@router.get("/applications")
def list_applications(
    status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_channel_partner_view),
):
    query = db.query(ChannelPartnerApplication)
    if status:
        query = query.filter(ChannelPartnerApplication.status == status.lower())
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                ChannelPartnerApplication.business_name.ilike(pattern),
                ChannelPartnerApplication.contact_name.ilike(pattern),
                ChannelPartnerApplication.email.ilike(pattern),
                ChannelPartnerApplication.phone.ilike(pattern),
                ChannelPartnerApplication.external_id.ilike(pattern),
            )
        )
    query = query.order_by(
        ChannelPartnerApplication.source_created_at.desc(),
        ChannelPartnerApplication.id.desc(),
    )
    rows, total, page, limit = _page(query, page, limit)
    return {
        "items": [_application_summary(row) for row in rows],
        "pagination": _page_meta(total, page, limit),
    }


@router.get("/applications/{application_id}")
def get_application(
    application_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_channel_partner_view),
):
    row = (
        db.query(ChannelPartnerApplication)
        .filter(ChannelPartnerApplication.external_id == application_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Application not found.")
    return _application_detail(row)


@router.get("/applications/{application_id}/documents/{document_type}")
def get_application_document(
    application_id: str,
    document_type: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_channel_partner_document_access),
):
    if document_type not in ("pan", "aadhaar"):
        raise HTTPException(status_code=404, detail="Unknown document type.")
    row = (
        db.query(ChannelPartnerApplication)
        .filter(ChannelPartnerApplication.external_id == application_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Application not found.")

    config = load_effective_config(db)
    if not config.configured:
        raise HTTPException(
            status_code=503,
            detail="WA HRMS Channel Partner API is not configured.",
        )
    try:
        with ChannelPartnerClient(config) as client:
            payload = client.get_application_document(application_id, document_type)
    except ChannelPartnerNotConfigured:
        raise HTTPException(status_code=503, detail="Integration not configured.")
    except ChannelPartnerAPIError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": exc.message,
                "upstreamStatus": exc.status_code,
            },
        )

    log_audit(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action="VIEW_CHANNEL_PARTNER_DOCUMENT",
        entity_type="CHANNEL_PARTNER_APPLICATION",
        entity_id=application_id,
        details=f"Viewed {document_type} document for application {application_id}.",
        ip_address=request.client.host if request.client else None,
    )

    document = payload
    object_payload = extract_object(payload, ["document"])
    url = first_present(
        object_payload,
        ["url", "link", "downloadUrl", "signedUrl"],
        default=None,
    )
    expires_at = first_present(
        object_payload,
        ["expiresAt", "expiry", "validUntil"],
        default=None,
    )
    return JSONResponse(
        content=as_json(
            {
                "applicationId": application_id,
                "documentType": document_type,
                "url": url,
                "expiresAt": expires_at,
                "expiresInSeconds": 300,
                "document": document,
                "fetchedAt": get_ist_now().isoformat(),
            }
        ),
        headers={"Cache-Control": "no-store, private, max-age=0"},
    )


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------
@router.get("/leads")
def list_leads(
    partner_id: Optional[str] = Query(None, alias="partnerId"),
    status: Optional[str] = None,
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_channel_partner_view),
):
    query = db.query(ChannelPartnerLead)
    if partner_id:
        query = query.filter(ChannelPartnerLead.partner_external_id == partner_id)
    if status:
        query = query.filter(ChannelPartnerLead.status == status.lower())
    if date_from:
        query = query.filter(func.date(ChannelPartnerLead.source_created_at) >= date_from)
    if date_to:
        query = query.filter(func.date(ChannelPartnerLead.source_created_at) <= date_to)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                ChannelPartnerLead.company_name.ilike(pattern),
                ChannelPartnerLead.contact_name.ilike(pattern),
                ChannelPartnerLead.email.ilike(pattern),
                ChannelPartnerLead.phone.ilike(pattern),
                ChannelPartnerLead.external_id.ilike(pattern),
            )
        )
    query = query.order_by(
        ChannelPartnerLead.source_created_at.desc(), ChannelPartnerLead.id.desc()
    )
    rows, total, page, limit = _page(query, page, limit)
    external_ids = [row.external_id for row in rows if row.external_id]
    crm_leads: Dict[str, Lead] = {}
    if external_ids:
        for crm_lead in (
            db.query(Lead)
            .filter(Lead.channel_partner_lead_id.in_(external_ids))
            .all()
        ):
            crm_leads[crm_lead.channel_partner_lead_id] = crm_lead
    return {
        "items": [
            _lead_payload(row, crm_lead=crm_leads.get(row.external_id))
            for row in rows
        ],
        "pagination": _page_meta(total, page, limit),
    }


@router.get("/leads/{lead_id}")
def get_lead(
    lead_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_channel_partner_view),
):
    row = (
        db.query(ChannelPartnerLead)
        .filter(ChannelPartnerLead.external_id == lead_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Partner lead not found.")
    crm_lead = (
        db.query(Lead)
        .filter(Lead.channel_partner_lead_id == lead_id)
        .first()
    )
    return _lead_payload(row, include_raw=True, crm_lead=crm_lead)


class ChannelPartnerLeadStatusRequest(BaseModel):
    status: str
    review_note: Optional[str] = None


def _partner_crm_lead(
    db: Session, lead_id: str
) -> tuple[ChannelPartnerLead, Lead]:
    mirror = (
        db.query(ChannelPartnerLead)
        .filter(ChannelPartnerLead.external_id == lead_id)
        .first()
    )
    if not mirror:
        raise HTTPException(status_code=404, detail="Partner lead not found.")
    crm_lead = (
        db.query(Lead)
        .filter(Lead.channel_partner_lead_id == lead_id)
        .first()
    )
    if not crm_lead:
        raise HTTPException(
            status_code=404,
            detail="This partner lead is not linked to a CRM lead yet.",
        )
    return mirror, crm_lead


@router.put("/leads/{lead_id}/status")
def update_partner_lead_status(
    lead_id: str,
    payload: ChannelPartnerLeadStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_channel_partner_edit),
):
    """Change the CRM status of a partner lead and push it to WA HRMS.

    Only statuses with a documented external equivalent are accepted here.
    ``converted`` must go through the Sales WON workflow so the CRM finance and
    Support handoffs stay consistent; every other supported status is sent
    through the same common synchronization path as All Leads.
    """
    mirror, crm_lead = _partner_crm_lead(db, lead_id)

    raw_status = (payload.status or "").strip()
    if not raw_status:
        raise HTTPException(status_code=400, detail="A CRM status is required.")

    # Accept either the external status name (submitted/qualified/rejected/lost)
    # or a CRM status value (NEW, NEW LEAD, QUALIFIED, REJECTED, LOST). Both are
    # normalised through the same mapping used by the All Leads endpoints.
    if raw_status.lower() in CHANNEL_PARTNER_STATUSES:
        external_status = raw_status.lower()
        crm_status = CHANNEL_PARTNER_TO_CRM_STATUS[external_status]
    else:
        crm_status = normalize_crm_status(raw_status)
        external_status = map_crm_status_to_channel_partner(crm_status)

    if external_status is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"CRM status '{payload.status}' cannot be sent to WA HRMS from "
                "Partner Leads. Use NEW, NEW LEAD, QUALIFIED, REJECTED or LOST."
            ),
        )
    if external_status == "converted":
        raise HTTPException(
            status_code=400,
            detail=(
                "Converted must be completed through the All Leads WON workflow "
                "so the CRM finance and Support handoffs stay consistent."
            ),
        )

    # Store the canonical CRM status for the confirmed external status (for
    # example NEW LEAD -> submitted -> NEW).
    crm_status = CHANNEL_PARTNER_TO_CRM_STATUS[external_status]

    # Validate the partner-facing note and the documented WA HRMS transition
    # before committing the CRM status.
    try:
        validate_channel_partner_status_change(crm_status, payload.review_note)
        validate_channel_partner_transition(crm_lead, crm_status)
    except ChannelPartnerStatusSyncError as exc:
        raise HTTPException(status_code=400, detail=exc.message)

    # Repeated clicks on an unchanged, already-synced status must not send a
    # duplicate PATCH. A new note still counts as an update.
    clean_note = (payload.review_note or "").strip() or None
    already_synced = (
        normalize_crm_status(crm_lead.status) == crm_status
        and (crm_lead.channel_partner_sync_status or "").upper() == "SYNCED"
        and clean_note in (None, (mirror.review_note or "").strip() or None)
    )
    if already_synced:
        response = _lead_payload(mirror, include_raw=True, crm_lead=crm_lead)
        response["syncMessage"] = (
            "CRM and WA HRMS are already synchronized for this status."
        )
        return response

    # Commit the CRM workflow status first. The external push then records
    # PENDING/SYNCED/FAILED without ever rolling back the user's CRM change.
    if normalize_crm_status(crm_lead.status) != crm_status:
        old_status = crm_lead.status
        crm_lead.status = crm_status
        db.add(
            LeadStatusHistory(
                lead_id=crm_lead.id,
                old_status=old_status,
                new_status=crm_status,
                changed_by=None,
                changed_at=get_ist_now(),
            )
        )
        db.add(
            LeadActivity(
                lead_id=crm_lead.id,
                activity_type="STATUS_CHANGED",
                related_entity_type="LEAD",
                related_entity_id=crm_lead.id,
                department="SALES",
                description=(
                    f"{current_user.username} changed the Channel Partner CRM status "
                    f"{old_status} -> {crm_status} from Partner Leads."
                ),
                created_at=get_ist_now(),
            )
        )
        db.commit()
        db.refresh(crm_lead)

    result = sync_channel_partner_status_for_lead(
        db,
        crm_lead,
        crm_status=crm_status,
        review_note=payload.review_note,
    )

    db.refresh(crm_lead)
    db.refresh(mirror)
    response = _lead_payload(mirror, include_raw=True, crm_lead=crm_lead)
    response["syncMessage"] = result.get("message")
    return response


@router.post("/leads/{lead_id}/retry-sync")
def retry_partner_lead_status_sync(
    lead_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_channel_partner_edit),
):
    """Retry a failed/pending WA HRMS status push from Partner Leads."""
    mirror, crm_lead = _partner_crm_lead(db, lead_id)
    try:
        result = retry_channel_partner_status_sync(db, crm_lead)
    except ChannelPartnerStatusSyncError as exc:
        raise HTTPException(status_code=400, detail=exc.message)
    db.refresh(crm_lead)
    db.refresh(mirror)
    response = _lead_payload(mirror, include_raw=True, crm_lead=crm_lead)
    response["syncMessage"] = result.get("message")
    return response


# ---------------------------------------------------------------------------
# Clients / coupons (global)
# ---------------------------------------------------------------------------
@router.get("/clients")
def list_clients(
    partner_id: Optional[str] = Query(None, alias="partnerId"),
    status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_channel_partner_view),
):
    query = db.query(ChannelPartnerClientAttribution)
    if partner_id:
        query = query.filter(
            ChannelPartnerClientAttribution.partner_external_id == partner_id
        )
    if status:
        query = query.filter(ChannelPartnerClientAttribution.status == status.lower())
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                ChannelPartnerClientAttribution.organization_name.ilike(pattern),
                ChannelPartnerClientAttribution.organization_id.ilike(pattern),
                ChannelPartnerClientAttribution.subscription_order_id.ilike(pattern),
                ChannelPartnerClientAttribution.order_number.ilike(pattern),
            )
        )
    rows, total, page, limit = _page(
        query.order_by(ChannelPartnerClientAttribution.id.desc()), page, limit
    )
    return {
        "items": [_client_payload(row) for row in rows],
        "pagination": _page_meta(total, page, limit),
    }


@router.get("/coupons")
def list_coupons(
    partner_id: Optional[str] = Query(None, alias="partnerId"),
    status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_channel_partner_view),
):
    query = db.query(ChannelPartnerCoupon)
    if partner_id:
        query = query.filter(ChannelPartnerCoupon.partner_external_id == partner_id)
    if status:
        query = query.filter(ChannelPartnerCoupon.status == status.lower())
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                ChannelPartnerCoupon.code.ilike(pattern),
                ChannelPartnerCoupon.description.ilike(pattern),
            )
        )
    rows, total, page, limit = _page(
        query.order_by(ChannelPartnerCoupon.id.desc()), page, limit
    )
    return {
        "items": [_coupon_payload(row) for row in rows],
        "pagination": _page_meta(total, page, limit),
    }


# ---------------------------------------------------------------------------
# Commissions
# ---------------------------------------------------------------------------
def _commission_list(
    db: Session,
    *,
    partner_id: Optional[str],
    status: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    page: int,
    limit: int,
):
    query = db.query(ChannelPartnerCommission)
    if partner_id:
        query = query.filter(ChannelPartnerCommission.partner_external_id == partner_id)
    if status:
        query = query.filter(ChannelPartnerCommission.status == status.lower())
    if date_from:
        query = query.filter(func.date(ChannelPartnerCommission.earned_at) >= date_from)
    if date_to:
        query = query.filter(func.date(ChannelPartnerCommission.earned_at) <= date_to)
    rows, total, page, limit = _page(
        query.order_by(ChannelPartnerCommission.earned_at.desc(), ChannelPartnerCommission.id.desc()),
        page,
        limit,
    )
    return {
        "items": [_commission_payload(row) for row in rows],
        "pagination": _page_meta(total, page, limit),
    }


@router.get("/commissions")
def list_commissions(
    partner_id: Optional[str] = Query(None, alias="partnerId"),
    status: Optional[str] = None,
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_channel_partner_view),
):
    return _commission_list(
        db,
        partner_id=partner_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# Payouts
# ---------------------------------------------------------------------------
@router.get("/payouts")
def list_payouts(
    partner_id: Optional[str] = Query(None, alias="partnerId"),
    status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_channel_partner_view),
):
    query = db.query(ChannelPartnerPayout)
    if partner_id:
        query = query.filter(ChannelPartnerPayout.partner_external_id == partner_id)
    if status:
        query = query.filter(ChannelPartnerPayout.status == status.lower())
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                ChannelPartnerPayout.partner_name.ilike(pattern),
                ChannelPartnerPayout.payment_reference.ilike(pattern),
                ChannelPartnerPayout.partner_invoice_number.ilike(pattern),
                ChannelPartnerPayout.external_id.ilike(pattern),
            )
        )
    rows, total, page, limit = _page(
        query.order_by(ChannelPartnerPayout.source_created_at.desc(), ChannelPartnerPayout.id.desc()),
        page,
        limit,
    )
    return {
        "items": [_payout_payload(row) for row in rows],
        "pagination": _page_meta(total, page, limit),
    }


@router.get("/payouts/{payout_id}")
def get_payout(
    payout_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_channel_partner_view),
):
    row = (
        db.query(ChannelPartnerPayout)
        .filter(ChannelPartnerPayout.external_id == payout_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Payout not found.")
    return _payout_payload(row, include_raw=True)


# ---------------------------------------------------------------------------
# Activity / events
# ---------------------------------------------------------------------------
@router.get("/events")
def list_events(
    event_type: Optional[str] = Query(None, alias="type"),
    status: Optional[str] = None,
    partner_id: Optional[str] = Query(None, alias="partnerId"),
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_channel_partner_view),
):
    query = db.query(ChannelPartnerWebhookEvent)
    if event_type:
        if "," in event_type:
            types = [value.strip() for value in event_type.split(",") if value.strip()]
            query = query.filter(ChannelPartnerWebhookEvent.event_type.in_(types))
        else:
            query = query.filter(ChannelPartnerWebhookEvent.event_type == event_type)
    if status:
        query = query.filter(ChannelPartnerWebhookEvent.status == status.lower())
    if partner_id:
        query = query.filter(
            ChannelPartnerWebhookEvent.related_partner_external_id == partner_id
        )
    if date_from:
        query = query.filter(
            func.date(ChannelPartnerWebhookEvent.event_created_at) >= date_from
        )
    if date_to:
        query = query.filter(
            func.date(ChannelPartnerWebhookEvent.event_created_at) <= date_to
        )
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                ChannelPartnerWebhookEvent.event_id.ilike(pattern),
                ChannelPartnerWebhookEvent.event_type.ilike(pattern),
                ChannelPartnerWebhookEvent.related_partner_external_id.ilike(pattern),
                ChannelPartnerWebhookEvent.related_lead_external_id.ilike(pattern),
                ChannelPartnerWebhookEvent.related_client_external_id.ilike(pattern),
            )
        )
    rows, total, page, limit = _page(
        query.order_by(
            ChannelPartnerWebhookEvent.event_created_at.desc(),
            ChannelPartnerWebhookEvent.id.desc(),
        ),
        page,
        limit,
    )
    return {
        "items": [_event_payload(row) for row in rows],
        "pagination": _page_meta(total, page, limit),
    }


@router.get("/events/{event_id}")
def get_event(
    event_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_channel_partner_view),
):
    row = (
        db.query(ChannelPartnerWebhookEvent)
        .filter(ChannelPartnerWebhookEvent.event_id == event_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Event not found.")
    return _event_payload(row, include_payload=True)


@router.post("/events/{event_id}/reprocess")
def reprocess_event(
    event_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    row = (
        db.query(ChannelPartnerWebhookEvent)
        .filter(ChannelPartnerWebhookEvent.event_id == event_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Event not found.")
    row.status = "pending"
    row.error = None
    row.processed_at = None
    db.commit()
    background_tasks.add_task(process_webhook_event, row.id)
    log_audit(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action="REPROCESS_CHANNEL_PARTNER_EVENT",
        entity_type="CHANNEL_PARTNER_EVENT",
        entity_id=event_id,
    )
    return {"status": "queued", "eventId": event_id}


# ---------------------------------------------------------------------------
# Integration settings + manual sync (Admin only)
# ---------------------------------------------------------------------------
class SettingsUpdate(BaseModel):
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    clear_api_key: bool = False
    webhook_secret: Optional[str] = None
    clear_webhook_secret: bool = False


class SyncRequest(BaseModel):
    scope: str = "full"


def _settings_payload(db: Session) -> Dict[str, Any]:
    config = load_effective_config(db)
    integration = get_integration_row(db)
    checkpoint = checkpoint_snapshot(db)
    webhook_secret, webhook_secret_source = effective_webhook_secret(db)
    latest_run = (
        db.query(ChannelPartnerSyncRun)
        .order_by(ChannelPartnerSyncRun.id.desc())
        .first()
    )
    return {
        "configured": config.configured,
        "baseUrl": config.base_url,
        "baseUrlSource": config.base_url_source,
        "apiKeyConfigured": bool(config.api_key),
        "apiKeyMasked": mask_secret(config.api_key),
        "apiKeySource": config.api_key_source,
        "webhookUrl": get_webhook_url(),
        "webhookPath": WEBHOOK_PATH,
        "webhookSecretConfigured": bool(webhook_secret),
        "webhookSecretMasked": mask_secret(webhook_secret),
        "webhookSecretSource": webhook_secret_source,
        "webhookConfigured": bool(webhook_secret),
        "webhookLastReceivedAt": ist_iso(integration.webhook_last_received_at)
        if integration
        else None,
        "webhookLastEventType": integration.webhook_last_event_type if integration else None,
        "lastSyncAt": ist_iso(integration.last_sync_at) if integration else None,
        "lastSyncStatus": integration.last_sync_status if integration else None,
        "lastSyncError": integration.last_sync_error if integration else None,
        "lastEventPollAt": ist_iso(integration.last_event_poll_at) if integration else None,
        "lastEventPollError": integration.last_event_poll_error if integration else None,
        **checkpoint,
        "latestSyncRun": {
            "id": latest_run.id,
            "scope": latest_run.scope,
            "trigger": latest_run.trigger,
            "status": latest_run.status,
            "startedAt": ist_iso(latest_run.started_at),
            "finishedAt": ist_iso(latest_run.finished_at),
            "stats": latest_run.stats_json,
            "error": latest_run.error,
        }
        if latest_run
        else None,
        "readOnly": True,
        "scopes": ["read"],
        "payoutsScopeEnabled": False,
        "secretHandling": "API key and webhook secret stay on the server.",
    }


@router.get("/settings")
def get_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return _settings_payload(db)


@router.put("/settings")
def update_settings(
    body: SettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    changed: List[str] = []
    try:
        if body.base_url is not None:
            save_configuration(
                db,
                base_url=body.base_url,
                set_base_url=True,
            )
            changed.append("base_url")
        if body.clear_api_key:
            save_configuration(db, clear_api_key=True)
            changed.append("api_key_cleared")
        elif body.api_key is not None and body.api_key.strip():
            save_configuration(db, api_key=body.api_key)
            changed.append("api_key_updated")
        if body.clear_webhook_secret:
            save_configuration(db, clear_webhook_secret=True)
            changed.append("webhook_secret_cleared")
        elif body.webhook_secret is not None and body.webhook_secret.strip():
            save_configuration(db, webhook_secret=body.webhook_secret)
            changed.append("webhook_secret_updated")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if changed:
        log_audit(
            db=db,
            user_id=current_user.id,
            username=current_user.username,
            action="UPDATE_CHANNEL_PARTNER_SETTINGS",
            entity_type="INTEGRATION",
            details="Updated Channel Partner integration settings: "
            + ", ".join(changed),
        )
    return _settings_payload(db)


@router.post("/settings/test-connection")
def test_connection(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    config = load_effective_config(db)
    if not config.configured:
        return {
            "ok": False,
            "status_code": None,
            "message": (
                "API credentials are not configured. Set "
                "WAHRMS_CHANNEL_PARTNER_API_KEY or save a key here."
            ),
            "tested_at": get_ist_now().isoformat(),
        }
    try:
        with ChannelPartnerClient(config) as client:
            result = client.test_connection()
    except ChannelPartnerNotConfigured:
        return {
            "ok": False,
            "status_code": None,
            "message": "Integration is not configured.",
            "tested_at": get_ist_now().isoformat(),
        }
    log_audit(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action="TEST_CHANNEL_PARTNER_CONNECTION",
        entity_type="INTEGRATION",
        details=f"Channel Partner connection test: {'success' if result.get('ok') else 'failure'}",
    )
    return result


@router.post("/sync")
def start_sync(
    body: SyncRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    scope = (body.scope or "full").lower()
    if scope not in SYNC_SCOPES:
        raise HTTPException(status_code=400, detail="Unsupported sync scope.")
    config = load_effective_config(db)
    if not config.configured:
        raise HTTPException(
            status_code=503,
            detail="WA HRMS Channel Partner API is not configured.",
        )
    running = (
        db.query(ChannelPartnerSyncRun)
        .filter(ChannelPartnerSyncRun.status == "running")
        .order_by(ChannelPartnerSyncRun.id.desc())
        .first()
    )
    if running:
        return {
            "status": "already_running",
            "runId": running.id,
            "scope": running.scope,
            "startedAt": ist_iso(running.started_at),
        }
    run = create_sync_run(
        db, scope=scope, trigger="manual", user_id=current_user.id
    )
    background_tasks.add_task(execute_sync_run, run.id)
    log_audit(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action="START_CHANNEL_PARTNER_SYNC",
        entity_type="INTEGRATION",
        entity_id=str(run.id),
        details=f"Started read-only Channel Partner sync ({scope}).",
    )
    return {
        "status": "queued",
        "runId": run.id,
        "scope": scope,
        "startedAt": ist_iso(run.started_at),
    }


@router.get("/sync/status")
def sync_status(
    db: Session = Depends(get_db),
    _: User = Depends(require_channel_partner_view),
):
    runs = (
        db.query(ChannelPartnerSyncRun)
        .order_by(ChannelPartnerSyncRun.id.desc())
        .limit(10)
        .all()
    )
    return {
        "latest": {
            "id": runs[0].id,
            "scope": runs[0].scope,
            "trigger": runs[0].trigger,
            "status": runs[0].status,
            "startedAt": ist_iso(runs[0].started_at),
            "finishedAt": ist_iso(runs[0].finished_at),
            "stats": runs[0].stats_json,
            "error": runs[0].error,
        }
        if runs
        else None,
        "runs": [
            {
                "id": run.id,
                "scope": run.scope,
                "trigger": run.trigger,
                "status": run.status,
                "startedAt": ist_iso(run.started_at),
                "finishedAt": ist_iso(run.finished_at),
                "stats": run.stats_json,
                "error": run.error,
            }
            for run in runs
        ],
        "integration": _integration_public(db),
        "checkpoint": checkpoint_snapshot(db),
    }


@router.post("/sync/events")
def sync_events_now(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    config = load_effective_config(db)
    if not config.configured:
        raise HTTPException(
            status_code=503,
            detail="WA HRMS Channel Partner API is not configured.",
        )
    run = create_sync_run(
        db, scope="events", trigger="manual", user_id=current_user.id
    )
    background_tasks.add_task(execute_sync_run, run.id)
    return {"status": "queued", "runId": run.id, "scope": "events"}


@router.post("/sync/reprocess-failed")
def reprocess_failed_events(
    background_tasks: BackgroundTasks,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    rows = (
        db.query(ChannelPartnerWebhookEvent)
        .filter(ChannelPartnerWebhookEvent.status == "failed")
        .order_by(ChannelPartnerWebhookEvent.id.asc())
        .limit(limit)
        .all()
    )
    for row in rows:
        row.status = "pending"
        row.error = None
        row.processed_at = None
    db.commit()
    for row in rows:
        background_tasks.add_task(process_webhook_event, row.id)
    log_audit(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action="REPROCESS_CHANNEL_PARTNER_EVENTS",
        entity_type="INTEGRATION",
        details=f"Queued {len(rows)} failed Channel Partner event(s) for reprocessing.",
    )
    return {"status": "queued", "count": len(rows)}
