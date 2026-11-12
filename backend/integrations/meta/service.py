"""Meta (Facebook & Instagram) Lead Ads service.

This module extends the original Meta Lead Ads implementation with:

* official OAuth token exchange and long-lived token handling,
* automatic Page / Instagram asset and Lead Form discovery,
* Page ``leadgen`` webhook subscription,
* full lead attribution (Page, Form, Campaign, Ad Set, Ad, custom answers),
* a durable DB-backed event queue with retries,
* historical lead imports with persisted job progress,
* dashboard/activity helpers.

Existing method names (``connect_or_add_page``, ``sync_page`` …) are kept so
the original manual Page endpoints and the Integration Hub keep working.
Access tokens are only ever handled server side.
"""

import asyncio
import datetime
import hashlib
import hmac
import json
import logging
import re
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx
from sqlalchemy import desc, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.integration import IntegrationLog
from models.lead import Lead
from models.meta_connection import (
    MetaConnection,
    MetaImportJob,
    MetaLeadEvent,
    MetaLeadForm,
)
from models.meta_page import MetaPage
from models.notification import Notification
from services.lead_assignment_service import assign_lead_immediately
from services.reinquiry_service import ReInquiryService
from utils.timezone import IST_TIMEZONE, get_ist_now

from .config import MetaConfig
from .crypto import decrypt_token, encrypt_token, mask_token

logger = logging.getLogger("meta_integration")

# Existing reporting code grouped these values as Meta. Instagram Instant Form
# leads are kept as a distinct source so reports can show them separately,
# while every Meta filter also includes INSTAGRAM.
META_SOURCE_VALUES = ["META", "Meta Ads", "Meta", "INSTAGRAM", "Instagram"]

# In-memory tracking retained for backwards compatibility with /status.
_last_webhook_received: Optional[datetime.datetime] = None
_last_sync: Optional[datetime.datetime] = None

_IMPORT_TASKS: set = set()

LEAD_FETCH_FIELDS = (
    "id,created_time,field_data,ad_id,ad_name,adset_id,adset_name,"
    "campaign_id,campaign_name,form_id,platform,is_organic"
)

PAGE_ASSET_FIELDS = (
    "id,name,category,access_token,picture{url},tasks,"
    "instagram_business_account{id,username}"
)

FORM_FIELDS = "id,name,status,locale,questions,created_time,leads_count"


class MetaGraphError(Exception):
    """Sanitised Graph API / network failure.

    The message never contains an access token.  ``code`` is either Meta's
    numeric error code, a Meta sub-code, or an internal marker such as
    ``NETWORK`` / ``PAGE_NOT_CONNECTED``.
    """

    def __init__(
        self,
        message: str,
        code: Any = None,
        subcode: Any = None,
        http_status: Optional[int] = None,
        fbtrace_id: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.subcode = subcode
        self.http_status = http_status
        self.fbtrace_id = fbtrace_id

    def _numeric(self, value: Any) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @property
    def is_token_error(self) -> bool:
        return (
            self._numeric(self.code) in {102, 190, 463, 467}
            or self._numeric(self.subcode) in {458, 459, 460, 463, 467}
        )

    @property
    def is_permission_error(self) -> bool:
        return self._numeric(self.code) in {10, 200, 294, 299} or self._numeric(
            self.subcode
        ) in {458, 459, 460}

    @property
    def is_rate_limit(self) -> bool:
        return self.http_status == 429 or self._numeric(self.code) in {
            4,
            17,
            32,
            613,
            80004,
        }


def _safe_error_message(value: Any, limit: int = 2000) -> str:
    """Remove accidental token material before persisting/logging an error."""
    text = str(value or "Unknown Meta error")
    text = re.sub(r"EAA[A-Za-z0-9]+", "[redacted-token]", text)
    text = re.sub(
        r"(access_token=)[^&\s]+", r"\1[redacted]", text, flags=re.IGNORECASE
    )
    return text[:limit]


def _json_dumps(value: Any, limit: Optional[int] = None) -> Optional[str]:
    if value is None:
        return None
    try:
        dumped = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        dumped = str(value)
    return dumped[:limit] if limit else dumped


def _parse_epoch(value: Any) -> Optional[datetime.datetime]:
    if value in (None, "", 0, "0"):
        return None
    try:
        return datetime.datetime.fromtimestamp(
            int(float(value)), tz=IST_TIMEZONE
        ).replace(tzinfo=None)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _parse_meta_datetime(value: Any) -> Optional[datetime.datetime]:
    """Parse either a UNIX epoch or Meta's ISO-8601 created_time."""
    if value in (None, "", 0, "0"):
        return None
    epoch = _parse_epoch(value)
    if epoch:
        return epoch
    try:
        text = str(value).strip().replace("Z", "+00:00")
        parsed = datetime.datetime.fromisoformat(text)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(IST_TIMEZONE).replace(tzinfo=None)
        return parsed
    except (TypeError, ValueError):
        return None


def _appsecret_proof(token: str) -> Optional[str]:
    secret = MetaConfig.get_app_secret()
    if not secret or not token:
        return None
    return hmac.new(
        secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def verify_webhook_signature(raw_body: bytes, signature_header: Optional[str]) -> bool:
    """Constant-time validation of Meta's ``X-Hub-Signature-256`` header."""
    secret = MetaConfig.get_app_secret()
    if not secret or not signature_header:
        return False
    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"), raw_body or b"", hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header.strip())


class MetaLeadService:
    """Service layer for Meta Lead Ads (Facebook + Instagram)."""

    # Tests inject an isolated SQLite session factory here.
    SESSION_FACTORY = None

    # ------------------------------------------------------------------
    # Graph API helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _graph_request(
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        token: Optional[str] = None,
        retries: int = 2,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        url = path if path.startswith("http") else (
            f"{MetaConfig.get_graph_base()}/{str(path).lstrip('/')}"
        )
        query: Dict[str, Any] = {
            k: v for k, v in (params or {}).items() if v is not None
        }
        if token:
            query["access_token"] = token
            proof = _appsecret_proof(token)
            if proof:
                query["appsecret_proof"] = proof

        last_network_error: Optional[Exception] = None
        for attempt in range(retries + 1):
            try:
                with httpx.Client(timeout=timeout) as client:
                    if method.upper() == "GET":
                        resp = client.get(url, params=query)
                    else:
                        resp = client.request(method, url, data=query)
                if resp.status_code < 400:
                    try:
                        return resp.json()
                    except ValueError as exc:
                        raise MetaGraphError(
                            f"Meta returned a non-JSON response ({resp.status_code}).",
                            http_status=resp.status_code,
                        ) from exc

                try:
                    payload = resp.json()
                except ValueError:
                    payload = {}
                err = (payload or {}).get("error") or {}
                exc = MetaGraphError(
                    err.get("message")
                    or f"Meta Graph API request failed with HTTP {resp.status_code}.",
                    code=err.get("code"),
                    subcode=err.get("error_subcode"),
                    http_status=resp.status_code,
                    fbtrace_id=err.get("fbtrace_id"),
                )
                if exc.is_rate_limit and attempt < retries:
                    time.sleep(2 + attempt * 3)
                    continue
                raise exc
            except MetaGraphError:
                raise
            except (httpx.HTTPError, OSError) as exc:
                last_network_error = exc
                if attempt < retries:
                    time.sleep(1 + attempt)
                    continue
                raise MetaGraphError(
                    "Network error while contacting Meta. Please retry shortly.",
                    code="NETWORK",
                ) from exc

        raise MetaGraphError(
            "Network error while contacting Meta. Please retry shortly.",
            code="NETWORK",
        ) from last_network_error

    @classmethod
    def _graph_paginate(
        cls,
        path: str,
        params: Optional[Dict[str, Any]],
        token: Optional[str],
        max_items: int = 10000,
        max_pages: int = 100,
    ) -> List[Dict[str, Any]]:
        """Fetch a Graph collection, following ``paging.next`` safely."""
        data = cls._graph_request("GET", path, params=params, token=token)
        items: List[Dict[str, Any]] = list(data.get("data") or [])
        next_url = (data.get("paging") or {}).get("next")
        page_count = 1
        while next_url and len(items) < max_items and page_count < max_pages:
            data = cls._graph_request("GET", next_url, params=None, token=None)
            items.extend(data.get("data") or [])
            next_url = (data.get("paging") or {}).get("next")
            page_count += 1
        return items[:max_items]

    # ------------------------------------------------------------------
    # Backwards-compatible timing/status helpers
    # ------------------------------------------------------------------
    @staticmethod
    def get_last_webhook_time() -> Optional[str]:
        return _last_webhook_received.isoformat() if _last_webhook_received else None

    @staticmethod
    def get_last_sync_time() -> Optional[str]:
        return _last_sync.isoformat() if _last_sync else None

    @staticmethod
    def log_activity(
        db: Session,
        event_type: str,
        status_val: str,
        message: str,
        commit: bool = True,
    ) -> IntegrationLog:
        log = IntegrationLog(
            integration_type="META",
            event_type=event_type,
            status=status_val,
            message=_safe_error_message(message, limit=1000),
            created_at=datetime.datetime.utcnow(),
        )
        db.add(log)
        if commit:
            db.commit()
        return log

    # ------------------------------------------------------------------
    # OAuth connection
    # ------------------------------------------------------------------
    @staticmethod
    def get_connection(db: Session, active_only: bool = False) -> Optional[MetaConnection]:
        query = db.query(MetaConnection)
        if active_only:
            query = query.filter(MetaConnection.status == "CONNECTED")
        return query.order_by(MetaConnection.updated_at.desc()).first()

    @classmethod
    def exchange_oauth_code(
        cls, code: str, redirect_uri: str
    ) -> Dict[str, Any]:
        """Exchange an OAuth code for a long-lived user token.

        Returns token metadata only; the caller encrypts and stores it.
        """
        app_id = MetaConfig.get_app_id()
        app_secret = MetaConfig.get_app_secret()
        if not app_id or not app_secret:
            raise MetaGraphError(
                "Meta App ID / App Secret are not configured on the server.",
                code="APP_NOT_CONFIGURED",
            )
        if not code:
            raise MetaGraphError("OAuth authorisation code is missing.", code="OAUTH_CODE")

        base = MetaConfig.get_graph_base()
        try:
            short = cls._graph_request(
                "GET",
                f"{base}/oauth/access_token",
                params={
                    "client_id": app_id,
                    "client_secret": app_secret,
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
                retries=1,
            )
        except MetaGraphError as exc:
            raise MetaGraphError(
                f"Meta rejected the OAuth authorisation: {exc.message}",
                code=exc.code or "OAUTH_EXCHANGE_FAILED",
                subcode=exc.subcode,
            ) from exc

        short_token = short.get("access_token")
        if not short_token:
            raise MetaGraphError(
                "Meta did not return an access token.", code="OAUTH_NO_TOKEN"
            )

        # Exchange the short-lived token for a long-lived (~60 day) token.
        long_token = short_token
        expires_in = short.get("expires_in")
        try:
            long_resp = cls._graph_request(
                "GET",
                f"{base}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": app_id,
                    "client_secret": app_secret,
                    "fb_exchange_token": short_token,
                },
                retries=1,
            )
            long_token = long_resp.get("access_token") or short_token
            expires_in = long_resp.get("expires_in") or expires_in
        except MetaGraphError as exc:
            logger.warning("Long-lived Meta token exchange failed: %s", exc.message)

        expires_at = None
        scopes: List[str] = []
        user_id = None
        try:
            debug = cls._graph_request(
                "GET",
                f"{base}/debug_token",
                params={"input_token": long_token},
                token=f"{app_id}|{app_secret}",
                retries=1,
            )
            debug_data = (debug or {}).get("data") or {}
            user_id = debug_data.get("user_id")
            scopes = list(debug_data.get("scopes") or [])
            if debug_data.get("expires_at"):
                expires_at = datetime.datetime.utcfromtimestamp(
                    int(debug_data["expires_at"])
                )
        except MetaGraphError as exc:
            logger.warning("Meta debug_token failed: %s", exc.message)

        if expires_at is None and expires_in:
            try:
                expires_at = datetime.datetime.utcnow() + datetime.timedelta(
                    seconds=int(expires_in)
                )
            except (TypeError, ValueError):
                expires_at = None

        me: Dict[str, Any] = {}
        try:
            me = cls._graph_request(
                "GET", f"{base}/me", params={"fields": "id,name"}, token=long_token
            )
        except MetaGraphError as exc:
            logger.warning("Meta /me lookup failed: %s", exc.message)

        return {
            "access_token": long_token,
            "token_expires_at": expires_at,
            "token_issued_at": datetime.datetime.utcnow(),
            "scopes": scopes,
            "user_id": str(user_id or me.get("id") or ""),
            "user_name": me.get("name") or "",
        }

    @classmethod
    def save_oauth_connection(
        cls,
        db: Session,
        token_data: Dict[str, Any],
        user_id: Optional[int] = None,
    ) -> MetaConnection:
        fb_user_id = str(token_data.get("user_id") or "").strip()
        if not fb_user_id:
            raise MetaGraphError(
                "Meta did not return the authorised user id.", code="OAUTH_NO_USER"
            )
        connection = (
            db.query(MetaConnection)
            .filter(MetaConnection.fb_user_id == fb_user_id)
            .first()
        )
        if not connection:
            connection = MetaConnection(fb_user_id=fb_user_id)
            db.add(connection)
        connection.fb_user_name = token_data.get("user_name") or connection.fb_user_name
        connection.encrypted_access_token = encrypt_token(token_data["access_token"])
        connection.token_issued_at = token_data.get("token_issued_at") or datetime.datetime.utcnow()
        connection.token_expires_at = token_data.get("token_expires_at")
        connection.scopes = ",".join(token_data.get("scopes") or [])
        connection.status = "CONNECTED"
        connection.last_error = None
        connection.connected_by_user_id = user_id
        connection.updated_at = datetime.datetime.utcnow()
        db.commit()
        db.refresh(connection)
        return connection

    @staticmethod
    def connection_token(connection: Optional[MetaConnection]) -> Optional[str]:
        if not connection:
            return None
        return decrypt_token(connection.encrypted_access_token) or None

    @classmethod
    def disconnect_connection(
        cls, db: Session, connection: MetaConnection, also_revoke: bool = False
    ) -> Tuple[bool, str]:
        token = cls.connection_token(connection)
        if also_revoke and token:
            try:
                cls._graph_request("DELETE", "me/permissions", token=token, retries=0)
            except MetaGraphError as exc:
                logger.warning("Meta permission revoke failed: %s", exc.message)
        connection.status = "DISCONNECTED"
        connection.auto_sync_enabled = False
        connection.last_error = "Disconnected by administrator."
        connection.updated_at = datetime.datetime.utcnow()
        db.query(MetaPage).filter(MetaPage.connection_id == connection.id).update(
            {MetaPage.webhook_subscribed: False}, synchronize_session=False
        )
        db.commit()
        cls.log_activity(
            db, "ACCOUNT_DISCONNECTED", "WARNING",
            f"Facebook account '{connection.fb_user_name or connection.fb_user_id}' disconnected.",
        )
        return True, "Facebook account disconnected. Stored tokens remain encrypted for reconnect."

    # ------------------------------------------------------------------
    # Page / Instagram asset discovery
    # ------------------------------------------------------------------
    @classmethod
    def fetch_authorized_assets(cls, user_token: str) -> List[Dict[str, Any]]:
        """Return every Page the authorised user can manage.

        Each item also carries the linked Instagram business account when Meta
        exposes one through ``instagram_basic``.
        """
        pages = cls._graph_paginate(
            "me/accounts",
            {"fields": PAGE_ASSET_FIELDS, "limit": 100},
            token=user_token,
        )
        seen = set()
        unique: List[Dict[str, Any]] = []
        for page in pages:
            page_id = str(page.get("id") or "").strip()
            if not page_id or page_id in seen:
                continue
            seen.add(page_id)
            unique.append(page)
        return unique

    @classmethod
    def sync_connection_assets(
        cls, db: Session, connection: MetaConnection, fetch_forms: bool = True
    ) -> Dict[str, Any]:
        """Discover/refresh Pages, Instagram assets, subscriptions and forms."""
        global _last_sync
        user_token = cls.connection_token(connection)
        if not user_token:
            connection.status = "ERROR"
            connection.last_error = "Stored Meta token cannot be decrypted."
            db.commit()
            raise MetaGraphError(
                "Stored Meta token is unavailable. Please reconnect the account.",
                code="TOKEN_MISSING",
            )

        try:
            assets = cls.fetch_authorized_assets(user_token)
        except MetaGraphError as exc:
            if exc.is_token_error:
                connection.status = "TOKEN_EXPIRED"
            else:
                connection.status = "ERROR"
            connection.last_error = _safe_error_message(exc.message)
            db.commit()
            raise

        now = datetime.datetime.utcnow()
        seen_ids = set()
        subscribed = 0
        forms_synced = 0
        pages_with_errors = 0

        for asset in assets:
            page_id = str(asset.get("id") or "").strip()
            seen_ids.add(page_id)
            page = (
                db.query(MetaPage).filter(MetaPage.page_id == page_id).first()
            )
            if not page:
                page = MetaPage(page_id=page_id)
                db.add(page)

            page_name = asset.get("name") or f"Facebook Page #{page_id[-4:]}"
            page.page_name = page_name
            page.category = asset.get("category") or page.category
            picture = ((asset.get("picture") or {}).get("data") or {}).get("url")
            if picture:
                page.page_picture_url = picture
            ig = asset.get("instagram_business_account") or {}
            if ig.get("id"):
                page.instagram_account_id = str(ig.get("id"))
                page.instagram_username = ig.get("username")
            else:
                page.instagram_account_id = None
                page.instagram_username = None

            page_token = asset.get("access_token") or user_token
            page.encrypted_access_token = encrypt_token(page_token)
            page.connection_id = connection.id
            page.token_expires_at = connection.token_expires_at
            page.status = "CONNECTED"
            page.error_message = None
            page.last_error_code = None
            page.last_synced_at = now
            if not page.lead_count:
                page.lead_count = 0
            db.flush()

            if page.is_selected:
                ok, _msg = cls.subscribe_page(db, page, commit=False)
                if ok:
                    subscribed += 1

            if fetch_forms and page.is_selected:
                try:
                    forms = cls.sync_page_forms(db, page, commit=False)
                    forms_synced += len(forms)
                except MetaGraphError as exc:
                    pages_with_errors += 1
                    page.error_message = _safe_error_message(exc.message)
                    page.last_error_code = str(exc.code or "FORM_SYNC_FAILED")
                    if exc.is_token_error:
                        page.status = "TOKEN_EXPIRED"
                    logger.warning(
                        "Form discovery failed for Page %s: %s", page_id, exc.message
                    )

        # Pages that were previously authorised but are no longer returned.
        stale_query = db.query(MetaPage).filter(
            MetaPage.connection_id == connection.id
        )
        if seen_ids:
            stale_query = stale_query.filter(
                MetaPage.page_id.notin_(list(seen_ids))
            )
        stale = stale_query.all()
        for page in stale:
            page.status = "ACCESS_REMOVED"
            page.webhook_subscribed = False
            page.error_message = (
                "Page access was removed or the Facebook user no longer manages "
                "this Page. Reconnect the account to restore access."
            )
            page.last_error_code = "ACCESS_REMOVED"

        connection.last_sync_at = now
        connection.status = "CONNECTED" if assets else "ERROR"
        connection.last_error = (
            None
            if assets
            else "No authorized Facebook Pages were returned by Meta."
        )
        _last_sync = now
        db.commit()

        summary = {
            "pages": len(assets),
            "subscribed_pages": subscribed,
            "forms": forms_synced,
            "pages_with_errors": pages_with_errors,
            "instagram_assets": sum(1 for a in assets if a.get("instagram_business_account")),
            "last_sync_at": now.isoformat(),
        }
        cls.log_activity(
            db,
            "ASSETS_SYNCED",
            "SUCCESS" if assets and not pages_with_errors else "WARNING",
            (
                f"Discovered {summary['pages']} Page(s), "
                f"{summary['instagram_assets']} Instagram asset(s), "
                f"{summary['forms']} form(s); subscribed {subscribed} Page(s)."
            ),
        )
        return summary

    @classmethod
    def sync_page_forms(
        cls, db: Session, page: MetaPage, commit: bool = True
    ) -> List[MetaLeadForm]:
        token = decrypt_token(page.encrypted_access_token) or MetaConfig.get_access_token()
        if not token:
            raise MetaGraphError(
                "No Page access token is available for form discovery.",
                code="TOKEN_MISSING",
            )
        try:
            raw_forms = cls._graph_paginate(
                f"{page.page_id}/leadgen_forms",
                {"fields": FORM_FIELDS, "limit": 100},
                token=token,
            )
        except MetaGraphError as exc:
            page.forms_last_synced_at = datetime.datetime.utcnow()
            page.error_message = _safe_error_message(exc.message)
            page.last_error_code = str(exc.code or "FORM_SYNC_FAILED")
            if exc.is_permission_error:
                page.status = "ERROR"
            if commit:
                db.commit()
            raise

        now = datetime.datetime.utcnow()
        seen = set()
        result: List[MetaLeadForm] = []
        for item in raw_forms:
            form_id = str(item.get("id") or "").strip()
            if not form_id:
                continue
            seen.add(form_id)
            form = (
                db.query(MetaLeadForm)
                .filter(MetaLeadForm.form_id == form_id)
                .first()
            )
            if not form:
                form = MetaLeadForm(form_id=form_id, page_id=page.page_id)
                db.add(form)
            form.page_id = page.page_id
            form.page_db_id = page.id
            form.name = item.get("name") or form.name or f"Lead Form #{form_id[-4:]}"
            form.status = item.get("status") or form.status or "ACTIVE"
            form.locale = item.get("locale") or form.locale
            form.questions_json = _json_dumps(item.get("questions"), limit=20000)
            form.leads_count = int(item.get("leads_count") or form.leads_count or 0)
            form.meta_created_at = _parse_meta_datetime(
                item.get("created_time")
            ) or form.meta_created_at
            form.last_synced_at = now
            form.updated_at = now
            db.flush()
            result.append(form)

        # Keep historical forms but mark them archived when Meta no longer
        # returns them. Selection is preserved.
        if seen:
            stale = (
                db.query(MetaLeadForm)
                .filter(
                    MetaLeadForm.page_id == page.page_id,
                    MetaLeadForm.form_id.notin_(seen),
                )
                .all()
            )
            for form in stale:
                if (form.status or "").upper() == "ACTIVE":
                    form.status = "ARCHIVED"
                    form.updated_at = now

        page.forms_last_synced_at = now
        page.error_message = None if page.status == "CONNECTED" else page.error_message
        if page.status == "ERROR" and raw_forms:
            page.status = "CONNECTED"
            page.last_error_code = None
        if commit:
            db.commit()
        return result

    @classmethod
    def subscribe_page(
        cls, db: Session, page: MetaPage, commit: bool = True
    ) -> Tuple[bool, str]:
        token = decrypt_token(page.encrypted_access_token) or MetaConfig.get_access_token()
        if not token:
            page.webhook_subscribed = False
            page.last_error_code = "TOKEN_MISSING"
            page.error_message = "Cannot subscribe Page without an access token."
            if commit:
                db.commit()
            return False, page.error_message
        try:
            cls._graph_request(
                "POST",
                f"{page.page_id}/subscribed_apps",
                params={"subscribed_fields": "leadgen"},
                token=token,
                retries=1,
            )
            page.webhook_subscribed = True
            page.last_error_code = None
            if page.status in {"DISCONNECTED", "ACCESS_REMOVED"}:
                page.status = "CONNECTED"
            if commit:
                db.commit()
            return True, "Page subscribed to leadgen webhook."
        except MetaGraphError as exc:
            page.webhook_subscribed = False
            page.last_error_code = str(exc.code or "SUBSCRIBE_FAILED")
            page.error_message = _safe_error_message(exc.message)
            if exc.is_token_error:
                page.status = "TOKEN_EXPIRED"
            if commit:
                db.commit()
            return False, page.error_message

    @classmethod
    def sync_now(cls, db: Session, connection: Optional[MetaConnection] = None) -> Dict[str, Any]:
        global _last_sync
        connection = connection or cls.get_connection(db)
        if not connection:
            # Legacy manual-Page mode: verify pages and process the queue.
            pages = cls.get_all_pages(db)
            verified = 0
            for page in pages:
                if page.status in {"DISCONNECTED", "ACCESS_REMOVED"}:
                    continue
                ok, _msg, _page, _err = cls.sync_page(db, page.page_id)
                if ok:
                    verified += 1
            queue = cls.process_due_events(db)
            _last_sync_value = datetime.datetime.utcnow()
            _last_sync = _last_sync_value
            cls.log_activity(
                db, "SYNC_NOW", "SUCCESS",
                f"Manual sync verified {verified} Page(s); processed {queue['processed']} event(s).",
            )
            return {
                "mode": "manual_pages",
                "pages_verified": verified,
                "events": queue,
                "last_sync_at": _last_sync_value.isoformat(),
            }

        summary = cls.sync_connection_assets(db, connection, fetch_forms=True)
        queue = cls.process_due_events(db)
        summary["events"] = queue
        summary["mode"] = "oauth"
        return summary

    # ------------------------------------------------------------------
    # Backwards-compatible manual Page management
    # ------------------------------------------------------------------
    @staticmethod
    def get_page_by_id(db: Session, page_id: str) -> Optional[MetaPage]:
        if not page_id:
            return None
        return (
            db.query(MetaPage)
            .filter(MetaPage.page_id == str(page_id).strip())
            .first()
        )

    @staticmethod
    def get_all_pages(db: Session) -> List[MetaPage]:
        return db.query(MetaPage).order_by(MetaPage.created_at.desc()).all()

    @staticmethod
    def verify_page_token(
        page_id: str, access_token: str, version: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        try:
            data = MetaLeadService._graph_request(
                "GET",
                f"{page_id}",
                params={"fields": "id,name,category,picture{url}"},
                token=access_token,
            )
            return True, data, None
        except MetaGraphError as exc:
            return False, {}, exc.message

    @staticmethod
    def connect_or_add_page(
        db: Session,
        page_id: str,
        access_token: str,
        page_name: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[MetaPage], Optional[str]]:
        clean_id = str(page_id).strip()
        clean_token = str(access_token).strip()
        if not clean_id or not clean_token:
            return False, "Page ID and Page Access Token are required.", None, "Missing fields"

        is_valid, page_info, err_msg = MetaLeadService.verify_page_token(
            clean_id, clean_token
        )
        verified_name = page_info.get("name") or (
            page_name.strip() if page_name else f"Facebook Page #{clean_id[-4:]}"
        )
        category = page_info.get("category")
        encrypted_tok = encrypt_token(clean_token)
        now = datetime.datetime.utcnow()

        existing = (
            db.query(MetaPage).filter(MetaPage.page_id == clean_id).first()
        )
        if existing:
            existing.page_name = verified_name
            existing.encrypted_access_token = encrypted_tok
            existing.status = "CONNECTED" if is_valid else "ERROR"
            existing.error_message = None if is_valid else (err_msg or "Token verification failed")
            existing.last_synced_at = now
            existing.is_selected = True
            if category:
                existing.category = category
            picture = ((page_info.get("picture") or {}).get("data") or {}).get("url")
            if picture:
                existing.page_picture_url = picture
            db.commit()
            db.refresh(existing)
            page = existing
            msg = (
                f"Page '{existing.page_name}' updated and connected successfully!"
                if is_valid
                else f"Page updated with warnings: {err_msg}"
            )
        else:
            page = MetaPage(
                page_id=clean_id,
                page_name=verified_name,
                encrypted_access_token=encrypted_tok,
                status="CONNECTED" if is_valid else "ERROR",
                category=category,
                lead_count=0,
                last_synced_at=now,
                error_message=None if is_valid else (err_msg or "Token verification failed"),
                created_at=now,
                updated_at=now,
            )
            db.add(page)
            db.commit()
            db.refresh(page)
            msg = (
                f"Page '{page.page_name}' connected successfully!"
                if is_valid
                else f"Page saved with warnings: {err_msg}"
            )

        if is_valid:
            MetaLeadService.subscribe_page(db, page, commit=True)
        return is_valid, msg, page, err_msg

    @staticmethod
    def sync_page(
        db: Session, page_id: str
    ) -> Tuple[bool, str, Optional[MetaPage], Optional[str]]:
        page = MetaLeadService.get_page_by_id(db, page_id)
        if not page:
            return False, f"Page ID '{page_id}' not found.", None, "Not found"

        token = decrypt_token(page.encrypted_access_token)
        if not token:
            page.status = "ERROR"
            page.error_message = "No access token configured."
            db.commit()
            return False, "Page access token is missing or corrupted.", page, "Empty token"

        is_valid, page_info, err_msg = MetaLeadService.verify_page_token(
            page.page_id, token
        )
        now = datetime.datetime.utcnow()
        page.last_synced_at = now
        if is_valid:
            if page_info.get("name"):
                page.page_name = page_info["name"]
            if page_info.get("category"):
                page.category = page_info["category"]
            picture = ((page_info.get("picture") or {}).get("data") or {}).get("url")
            if picture:
                page.page_picture_url = picture
            page.status = "CONNECTED"
            page.error_message = None
            page.last_error_code = None
            db.commit()
            MetaLeadService.subscribe_page(db, page)
            try:
                MetaLeadService.sync_page_forms(db, page)
            except MetaGraphError:
                pass
            db.refresh(page)
            return True, f"Page '{page.page_name}' synced successfully with Meta Graph API!", page, None

        page.status = "TOKEN_EXPIRED" if "token" in (err_msg or "").lower() else "ERROR"
        page.error_message = err_msg or "Graph API rejected Page Access Token"
        page.last_error_code = "TOKEN_ERROR"
        db.commit()
        db.refresh(page)
        return False, f"Sync failed for '{page.page_name}': {err_msg}", page, err_msg

    @staticmethod
    def disconnect_page(db: Session, page_id: str) -> Tuple[bool, str, Optional[MetaPage]]:
        page = MetaLeadService.get_page_by_id(db, page_id)
        if not page:
            return False, f"Page ID '{page_id}' not found.", None
        page.status = "DISCONNECTED"
        page.is_selected = False
        page.webhook_subscribed = False
        page.updated_at = datetime.datetime.utcnow()
        db.commit()
        db.refresh(page)
        return True, f"Page '{page.page_name}' has been disconnected.", page

    @staticmethod
    def reconnect_page(db: Session, page_id: str) -> Tuple[bool, str, Optional[MetaPage]]:
        page = MetaLeadService.get_page_by_id(db, page_id)
        if not page:
            return False, f"Page ID '{page_id}' not found.", None
        page.status = "CONNECTED"
        page.is_selected = True
        page.auto_sync_enabled = True
        page.updated_at = datetime.datetime.utcnow()
        db.commit()
        MetaLeadService.subscribe_page(db, page)
        db.refresh(page)
        return True, f"Page '{page.page_name}' is now active and connected.", page

    @staticmethod
    def refresh_page(
        db: Session, page_id: str, new_access_token: Optional[str] = None
    ) -> Tuple[bool, str, Optional[MetaPage], Optional[str]]:
        page = MetaLeadService.get_page_by_id(db, page_id)
        if not page:
            return False, f"Page ID '{page_id}' not found.", None, "Not found"

        token_to_use = (
            new_access_token.strip()
            if new_access_token and new_access_token.strip()
            else decrypt_token(page.encrypted_access_token)
        )
        if new_access_token and new_access_token.strip():
            page.encrypted_access_token = encrypt_token(token_to_use)

        is_valid, page_info, err_msg = MetaLeadService.verify_page_token(
            page.page_id, token_to_use
        )
        now = datetime.datetime.utcnow()
        page.last_synced_at = now
        page.updated_at = now
        if is_valid:
            if page_info.get("name"):
                page.page_name = page_info["name"]
            if page_info.get("category"):
                page.category = page_info["category"]
            page.status = "CONNECTED"
            page.error_message = None
            page.last_error_code = None
            db.commit()
            db.refresh(page)
            return True, f"Page '{page.page_name}' token refreshed and verified!", page, None

        page.status = "TOKEN_EXPIRED" if "token" in (err_msg or "").lower() else "ERROR"
        page.error_message = err_msg or "Failed to verify new Page Access Token"
        page.last_error_code = "TOKEN_ERROR"
        db.commit()
        db.refresh(page)
        return False, f"Refresh verification failed: {err_msg}", page, err_msg

    @staticmethod
    def delete_page(db: Session, page_id: str) -> bool:
        page = MetaLeadService.get_page_by_id(db, page_id)
        if not page:
            return False
        db.query(MetaLeadForm).filter(MetaLeadForm.page_id == page.page_id).delete(
            synchronize_session=False
        )
        db.delete(page)
        db.commit()
        return True

    # ------------------------------------------------------------------
    # Lead payload parsing
    # ------------------------------------------------------------------
    @staticmethod
    def fetch_lead_details_from_graph_api(
        leadgen_id: str, access_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Legacy helper: returns {} on failure instead of raising."""
        try:
            return MetaLeadService.fetch_lead_details(leadgen_id, access_token)
        except MetaGraphError as exc:
            logger.error("Failed to fetch Meta lead %s: %s", leadgen_id, exc.message)
            return {}

    @staticmethod
    def fetch_lead_details(
        leadgen_id: str, access_token: Optional[str] = None
    ) -> Dict[str, Any]:
        token = access_token or MetaConfig.get_access_token()
        if not token:
            raise MetaGraphError(
                "No Page/user access token is available to fetch the lead.",
                code="TOKEN_MISSING",
            )
        data = MetaLeadService._graph_request(
            "GET",
            str(leadgen_id),
            params={"fields": LEAD_FETCH_FIELDS},
            token=token,
        )
        if not isinstance(data, dict) or not data:
            raise MetaGraphError(
                "Meta returned an empty lead payload.", code="EMPTY_LEAD"
            )
        return data

    @staticmethod
    def parse_field_data(raw_meta_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Meta ``field_data`` into standard CRM values + custom answers."""
        parsed: Dict[str, Any] = {
            "name": "",
            "first_name": "",
            "last_name": "",
            "phone": "",
            "email": "",
            "company": "",
            "city": "",
            "state": "",
            "country": "",
            "custom_answers": {},
        }
        known_names = {
            "full_name", "full name", "name",
            "first_name", "first name",
            "last_name", "last name",
            "phone_number", "phone number", "phone", "mobile_number", "mobile number",
            "email", "email address", "work email",
            "company_name", "company name", "company",
            "city", "location",
            "state", "province",
            "country",
        }
        first_name = ""
        last_name = ""
        for item in raw_meta_data.get("field_data") or []:
            if not isinstance(item, dict):
                continue
            raw_key = str(item.get("name") or "").strip()
            name_key = raw_key.lower()
            values = item.get("values") or []
            val = str(values[0]).strip() if values else ""
            if not val:
                continue
            if name_key in ["full_name", "full name", "name"]:
                parsed["name"] = val
            elif name_key in ["first_name", "first name"]:
                first_name = val
            elif name_key in ["last_name", "last name"]:
                last_name = val
            elif name_key in [
                "phone_number", "phone number", "phone",
                "mobile_number", "mobile number",
            ]:
                parsed["phone"] = val
            elif name_key in ["email", "email address", "work email"]:
                parsed["email"] = val
            elif name_key in ["company_name", "company name", "company"]:
                parsed["company"] = val
            elif name_key in ["city", "location"]:
                parsed["city"] = val
            elif name_key in ["state", "province"]:
                parsed["state"] = val
            elif name_key == "country":
                parsed["country"] = val
            elif name_key not in known_names:
                parsed["custom_answers"][raw_key or "answer"] = val

        parsed["first_name"] = first_name
        parsed["last_name"] = last_name
        if first_name or last_name:
            parsed["name"] = f"{first_name} {last_name}".strip()
        if not parsed["name"]:
            parsed["name"] = ""
        return parsed

    @staticmethod
    def _synthetic_phone(leadgen_id: str) -> str:
        digits = re.sub(r"\D", "", str(leadgen_id or ""))
        suffix = (digits or "00000000")[-8:].rjust(8, "0")
        return f"+9198{suffix}"

    @classmethod
    def _ensure_form_record(
        cls, db: Session, page: MetaPage, form_id: Optional[str]
    ) -> Optional[MetaLeadForm]:
        if not form_id:
            return None
        form = (
            db.query(MetaLeadForm).filter(MetaLeadForm.form_id == str(form_id)).first()
        )
        if form:
            return form
        token = decrypt_token(page.encrypted_access_token)
        form_name = None
        status = "ACTIVE"
        if token:
            try:
                data = cls._graph_request(
                    "GET",
                    str(form_id),
                    params={"fields": "id,name,status"},
                    token=token,
                    retries=0,
                )
                form_name = data.get("name")
                status = data.get("status") or status
            except MetaGraphError:
                form_name = None
        form = MetaLeadForm(
            form_id=str(form_id),
            page_id=page.page_id,
            page_db_id=page.id,
            name=form_name or f"Lead Form #{str(form_id)[-4:]}",
            status=status,
            is_selected=True,
            last_synced_at=datetime.datetime.utcnow(),
        )
        db.add(form)
        db.flush()
        return form

    # ------------------------------------------------------------------
    # Lead ingestion
    # ------------------------------------------------------------------
    @classmethod
    def ingest_lead(
        cls,
        db: Session,
        leadgen_id: str,
        page_id: Optional[str] = None,
        form_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        graph_data: Optional[Dict[str, Any]] = None,
        source_hint: Optional[str] = None,
        is_import: bool = False,
    ) -> Tuple[Lead, bool, bool]:
        """Create/merge a CRM lead from a Meta leadgen record.

        Returns ``(lead, is_reinquiry, is_duplicate)``.
        Raises ``MetaGraphError`` when the lead cannot be fetched/validated so
        the durable event queue can retry it.
        """
        global _last_webhook_received, _last_sync

        clean_leadgen_id = str(leadgen_id or "").strip()
        if not clean_leadgen_id:
            raise MetaGraphError("leadgen_id is missing.", code="INVALID_EVENT")

        existing = (
            db.query(Lead).filter(Lead.meta_lead_id == clean_leadgen_id).first()
        )
        if existing:
            return existing, False, True

        page_id = str(page_id or (payload or {}).get("page_id") or "").strip()
        page = cls.get_page_by_id(db, page_id) if page_id else None
        if not page and page_id and page_id == MetaConfig.get_page_id():
            token = MetaConfig.get_access_token()
            if token:
                page = MetaPage(
                    page_id=page_id,
                    page_name=f"Facebook Page #{page_id[-4:]}",
                    encrypted_access_token=encrypt_token(token),
                    status="CONNECTED",
                    lead_count=0,
                    is_selected=True,
                    auto_sync_enabled=True,
                )
                db.add(page)
                db.flush()
        if not page:
            raise MetaGraphError(
                f"Page {page_id or '(unknown)'} is not connected to CHN CRM.",
                code="PAGE_NOT_CONNECTED",
            )

        if not is_import and page.status in {"DISCONNECTED", "ACCESS_REMOVED"}:
            raise MetaGraphError(
                f"Page '{page.page_name}' is {page.status.lower()} in CHN CRM.",
                code="PAGE_INACTIVE",
            )
        if not is_import and page.status == "TOKEN_EXPIRED":
            raise MetaGraphError(
                f"Page '{page.page_name}' access token has expired. Reconnect the account.",
                code="TOKEN_EXPIRED",
            )

        token = decrypt_token(page.encrypted_access_token)
        connection = None
        if not token and page.connection_id:
            connection = db.query(MetaConnection).filter(
                MetaConnection.id == page.connection_id
            ).first()
            token = cls.connection_token(connection)
        token = token or MetaConfig.get_access_token()

        webhook_value = (payload or {}).get("value") or {}
        form_id = str(
            form_id
            or (graph_data or {}).get("form_id")
            or webhook_value.get("form_id")
            or ""
        ).strip() or None

        graph = dict(graph_data or {})
        if not graph.get("field_data") or not graph.get("id"):
            fetched = cls.fetch_lead_details(clean_leadgen_id, access_token=token)
            fetched.update({k: v for k, v in graph.items() if v})
            graph = fetched
        if not graph.get("field_data"):
            raise MetaGraphError(
                "Meta lead payload has no field_data. The lead may have been "
                "deleted or the Page token lacks leads_retrieval permission.",
                code="EMPTY_FIELD_DATA",
            )

        form_id = str(graph.get("form_id") or form_id or "").strip() or None
        form = cls._ensure_form_record(db, page, form_id)

        # Validate form selection for real-time ingestion. Historical imports
        # run only for explicitly selected forms, so they bypass this check.
        if not is_import and form and not form.is_selected:
            raise MetaGraphError(
                f"Lead Form '{form.name}' is not selected for sync in CHN CRM.",
                code="FORM_NOT_SELECTED",
            )

        parsed = cls.parse_field_data(graph)
        raw_platform = str(graph.get("platform") or source_hint or "").strip().lower()
        is_instagram = raw_platform in {"ig", "instagram", "instagram_lead_ads"}
        platform = "instagram" if is_instagram else "facebook"
        source = "INSTAGRAM" if is_instagram else "META"
        source_label = "Instagram" if is_instagram else "Facebook"

        page_name = page.page_name or f"Facebook Page {page.page_id}"
        form_name = form.name if form else None
        created_time = (
            _parse_meta_datetime(graph.get("created_time"))
            or _parse_meta_datetime(webhook_value.get("created_time"))
            or get_ist_now()
        )

        phone = parsed["phone"].strip()
        if not phone:
            phone = cls._synthetic_phone(clean_leadgen_id)
        if "<test lead:" in phone.lower() or len(phone) > 25:
            phone = cls._synthetic_phone(clean_leadgen_id)

        email = parsed["email"].strip()
        if email and ("<test lead:" in email.lower() or "@" not in email):
            email = ""

        name = parsed["name"] or f"Meta Lead #{clean_leadgen_id[-6:]}"
        custom_answers = parsed.get("custom_answers") or {}

        campaign_id = str(graph.get("campaign_id") or "").strip() or None
        campaign_name = str(graph.get("campaign_name") or "").strip() or None
        adset_id = str(
            graph.get("adset_id") or webhook_value.get("adgroup_id") or ""
        ).strip() or None
        adset_name = str(graph.get("adset_name") or "").strip() or None
        ad_id = str(graph.get("ad_id") or webhook_value.get("ad_id") or "").strip() or None
        ad_name = str(graph.get("ad_name") or "").strip() or None

        notes_lines = [
            f"Captured via {source_label} Instant Form.",
            f"Page: {page_name} (ID: {page.page_id})",
        ]
        if form:
            notes_lines.append(f"Form: {form_name} (ID: {form.form_id})")
        elif form_id:
            notes_lines.append(f"Form ID: {form_id}")
        if campaign_id or adset_id or ad_id:
            notes_lines.append(
                "Attribution — Campaign: %s | Ad Set: %s | Ad: %s"
                % (campaign_id or "-", adset_id or "-", ad_id or "-")
            )
        if custom_answers:
            notes_lines.append("Custom answers:")
            for key, value in custom_answers.items():
                notes_lines.append(f"  • {key}: {value}")

        campaign_title = campaign_name or (
            f"{source_label} · {form_name}" if form_name else f"{source_label} · {page_name}"
        )

        enquiry_data = {
            "meta_lead_id": clean_leadgen_id,
            "meta_form_id": form_id,
            "meta_page_id": page.page_id,
            "meta_page_name": page_name,
            "meta_form_name": form_name,
            "meta_campaign_id": campaign_id,
            "meta_adset_id": adset_id,
            "meta_adset_name": adset_name,
            "meta_ad_id": ad_id,
            "meta_ad_name": ad_name,
            "meta_platform": platform,
            "meta_created_at": created_time,
            "meta_custom_answers": _json_dumps(custom_answers, limit=10000),
            "name": name,
            "first_name": parsed.get("first_name") or None,
            "last_name": parsed.get("last_name") or None,
            "phone": phone,
            "email": email or None,
            "company": parsed.get("company") or None,
            "city": parsed.get("city") or None,
            "state": parsed.get("state") or None,
            "country": parsed.get("country") or None,
            "source": source,
            "campaign_name": campaign_title,
            "requirement_notes": "\n".join(notes_lines),
            "rating": "Warm",
            "priority": "MEDIUM",
            "created_at": created_time,
        }

        lead, is_reinquiry, _enquiry = ReInquiryService.register_enquiry(
            db=db,
            enquiry_data=enquiry_data,
            creator_emp_id=None,
            creator_name=f"{source_label} Lead Ads",
            commit=False,
        )
        db.flush()

        try:
            assignee = assign_lead_immediately(
                db,
                lead,
                notes=(
                    f"Auto-assigned immediately on {source_label} Lead Ads capture "
                    "using the configured assignment strategy."
                ),
            )
            if assignee and not is_reinquiry:
                cls._notify_assignee(db, lead, assignee, source_label)
        except Exception as exc:  # assignment must never lose the lead
            logger.error("Meta lead auto-assignment failed: %s", exc)

        page.lead_count = (page.lead_count or 0) + (0 if is_reinquiry else 1)
        page.last_lead_at = created_time
        if not is_import:
            page.last_webhook_at = datetime.datetime.utcnow()
        if form:
            form.leads_count = (form.leads_count or 0) + (0 if is_reinquiry else 1)
            form.last_lead_at = created_time
        if page.connection_id:
            conn = connection or db.query(MetaConnection).filter(
                MetaConnection.id == page.connection_id
            ).first()
            if conn and not is_import:
                conn.last_webhook_at = datetime.datetime.utcnow()

        if not is_import:
            _last_webhook_received = datetime.datetime.utcnow()
        _last_sync = datetime.datetime.utcnow()

        logger.info(
            "Processed %s Lead Ads %s: Lead #%s, Page %s, Form %s, ad %s, assigned=%s",
            source_label,
            "re-inquiry" if is_reinquiry else "lead",
            lead.id,
            page.page_id,
            form_id or "-",
            ad_id or "-",
            "yes" if getattr(lead, "assigned_to", None) else "no",
        )
        return lead, is_reinquiry, False

    @staticmethod
    def _notify_assignee(db: Session, lead: Lead, assignee, source_label: str):
        user_id = getattr(assignee, "user_id", None)
        if not user_id:
            return
        db.add(
            Notification(
                user_id=user_id,
                title=f"New {source_label} lead: {lead.name}",
                message=(
                    f"{lead.name} ({lead.phone or 'no phone'}) was captured via "
                    f"{source_label} Lead Ads and assigned to you."
                ),
                notification_type="LEAD",
                link_url="/leads",
                is_read=False,
                created_at=datetime.datetime.utcnow(),
            )
        )

    # ------------------------------------------------------------------
    # Durable event queue / retries
    # ------------------------------------------------------------------
    @staticmethod
    def _backoff_seconds(attempt: int) -> int:
        return min(300 * (2 ** max(attempt - 1, 0)), 21600)

    @classmethod
    def process_lead_event(cls, db: Session, event: MetaLeadEvent) -> str:
        if event.status in {"PROCESSED", "DUPLICATE", "IGNORED"}:
            return event.status

        event.attempt_count = (event.attempt_count or 0) + 1
        event.status = "PROCESSING"
        event.updated_at = datetime.datetime.utcnow()
        db.commit()
        db.refresh(event)

        try:
            payload = json.loads(event.payload_json) if event.payload_json else {}
            lead, is_reinquiry, is_duplicate = cls.ingest_lead(
                db=db,
                leadgen_id=event.leadgen_id,
                page_id=event.page_id,
                form_id=event.form_id,
                payload=payload,
                source_hint=event.platform,
                is_import=False,
            )
            event.status = "DUPLICATE" if is_duplicate else "PROCESSED"
            event.lead_id = lead.id if lead else event.lead_id
            event.is_reinquiry = bool(is_reinquiry)
            event.last_error = (
                "Duplicate Meta Lead ID — existing lead linked."
                if is_duplicate else None
            )
            event.processed_at = datetime.datetime.utcnow()
            event.next_retry_at = None
            event.updated_at = datetime.datetime.utcnow()
            db.commit()
            return event.status
        except IntegrityError:
            db.rollback()
            event = db.query(MetaLeadEvent).filter(MetaLeadEvent.id == event.id).first()
            existing = (
                db.query(Lead)
                .filter(Lead.meta_lead_id == event.leadgen_id)
                .first()
            )
            if existing:
                event.status = "DUPLICATE"
                event.lead_id = existing.id
                event.last_error = "Duplicate Meta Lead ID (database unique constraint)."
                event.processed_at = datetime.datetime.utcnow()
                event.next_retry_at = None
                db.commit()
                return event.status
            raise
        except Exception as exc:
            db.rollback()
            event = db.query(MetaLeadEvent).filter(MetaLeadEvent.id == event.id).first()
            if not event:
                raise
            code = getattr(exc, "code", None)
            safe_message = _safe_error_message(exc)
            event.last_error = safe_message
            event.updated_at = datetime.datetime.utcnow()

            if code == "PAGE_INACTIVE":
                event.status = "IGNORED"
                event.next_retry_at = None
                event.processed_at = datetime.datetime.utcnow()
            elif event.attempt_count >= (event.max_attempts or 8):
                event.status = "FAILED"
                event.next_retry_at = None
            else:
                event.status = "RETRYING"
                event.next_retry_at = (
                    datetime.datetime.utcnow()
                    + datetime.timedelta(seconds=cls._backoff_seconds(event.attempt_count))
                )

            # Mark the Page so the admin sees the actionable token/permission error.
            page = cls.get_page_by_id(db, event.page_id) if event.page_id else None
            if page:
                if code in {"TOKEN_EXPIRED", "TOKEN_MISSING", "NETWORK"} or getattr(
                    exc, "is_token_error", False
                ):
                    if code != "NETWORK":
                        page.status = "TOKEN_EXPIRED"
                        page.error_message = safe_message
                        page.last_error_code = "TOKEN_EXPIRED"
                elif getattr(exc, "is_permission_error", False):
                    page.status = "ERROR"
                    page.error_message = safe_message
                    page.last_error_code = "PERMISSION_MISSING"

            db.commit()
            logger.warning(
                "Meta lead event %s failed (attempt %s/%s): %s",
                event.id,
                event.attempt_count,
                event.max_attempts,
                safe_message,
            )
            return event.status

    @classmethod
    def create_event(
        cls,
        db: Session,
        leadgen_id: Optional[str],
        page_id: Optional[str],
        form_id: Optional[str],
        payload: Optional[Dict[str, Any]],
        platform: Optional[str] = None,
        event_key: Optional[str] = None,
        status: str = "RECEIVED",
        error: Optional[str] = None,
    ) -> Tuple[MetaLeadEvent, bool]:
        key = event_key or f"leadgen:{leadgen_id}"
        existing = (
            db.query(MetaLeadEvent)
            .filter(MetaLeadEvent.event_key == key)
            .first()
        )
        if existing:
            return existing, True
        event = MetaLeadEvent(
            event_key=key,
            leadgen_id=str(leadgen_id or "") or None,
            page_id=str(page_id or "") or None,
            form_id=str(form_id or "") or None,
            platform=platform,
            status=status,
            payload_json=_json_dumps(payload, limit=20000),
            last_error=_safe_error_message(error) if error else None,
            created_at=datetime.datetime.utcnow(),
        )
        db.add(event)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = (
                db.query(MetaLeadEvent)
                .filter(MetaLeadEvent.event_key == key)
                .first()
            )
            if existing:
                return existing, True
            raise
        db.refresh(event)
        return event, False

    @classmethod
    def process_due_events(cls, db: Session, limit: int = 20) -> Dict[str, int]:
        now = datetime.datetime.utcnow()
        events = (
            db.query(MetaLeadEvent)
            .filter(
                MetaLeadEvent.status.in_(["RECEIVED", "RETRYING"]),
                or_(
                    MetaLeadEvent.next_retry_at.is_(None),
                    MetaLeadEvent.next_retry_at <= now,
                ),
            )
            .order_by(MetaLeadEvent.id.asc())
            .limit(limit)
            .all()
        )
        summary = {"processed": 0, "duplicates": 0, "ignored": 0, "failed": 0}
        for event in events:
            try:
                result = cls.process_lead_event(db, event)
            except Exception as exc:
                db.rollback()
                summary["failed"] += 1
                logger.error("Meta event processor crashed: %s", _safe_error_message(exc))
                continue
            if result == "PROCESSED":
                summary["processed"] += 1
            elif result == "DUPLICATE":
                summary["duplicates"] += 1
            elif result == "IGNORED":
                summary["ignored"] += 1
            else:
                summary["failed"] += 1
        return summary

    @classmethod
    def retry_failed_events(cls, db: Session) -> int:
        failed = db.query(MetaLeadEvent).filter(MetaLeadEvent.status == "FAILED").all()
        now = datetime.datetime.utcnow()
        for event in failed:
            event.status = "RECEIVED"
            event.attempt_count = 0
            event.next_retry_at = now
            event.updated_at = now
        db.commit()
        return len(failed)

    @classmethod
    def retry_event(cls, db: Session, event_id: int) -> Tuple[bool, str]:
        event = db.query(MetaLeadEvent).filter(MetaLeadEvent.id == event_id).first()
        if not event:
            return False, "Event not found."
        if event.status not in {"FAILED", "RETRYING", "RECEIVED"}:
            return False, f"Event is already {event.status.lower()}."
        event.status = "RECEIVED"
        event.attempt_count = 0
        event.next_retry_at = datetime.datetime.utcnow()
        event.updated_at = datetime.datetime.utcnow()
        db.commit()
        status = cls.process_lead_event(db, event)
        return True, f"Retry finished with status: {status}."

    @classmethod
    async def start_meta_lead_worker(cls, interval_seconds: int = 60):
        """Background retry worker started from FastAPI startup."""
        while True:
            try:
                await asyncio.to_thread(cls._worker_cycle)
            except Exception as exc:
                logger.error("Meta lead worker cycle failed: %s", _safe_error_message(exc))
            await asyncio.sleep(max(15, interval_seconds))

    @staticmethod
    def _worker_cycle():
        db = MetaLeadService._session_factory()()
        try:
            summary = MetaLeadService.process_due_events(db, limit=25)
            if any(summary.values()):
                logger.info("Meta lead worker cycle: %s", summary)
        finally:
            db.close()

    @classmethod
    def _session_factory(cls):
        """Allow tests to inject an isolated session factory."""
        if cls.SESSION_FACTORY is not None:
            return cls.SESSION_FACTORY
        from database import SessionLocal
        return SessionLocal

    # ------------------------------------------------------------------
    # Historical imports
    # ------------------------------------------------------------------
    @staticmethod
    def _normalise_ist_naive(value: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
        if value is None:
            return None
        if value.tzinfo is not None:
            return value.astimezone(IST_TIMEZONE).replace(tzinfo=None)
        return value

    @staticmethod
    def resolve_import_range(
        preset: Optional[str], since: Optional[datetime.datetime],
        until: Optional[datetime.datetime],
    ) -> Tuple[datetime.datetime, datetime.datetime, str]:
        now = get_ist_now()
        preset_clean = (preset or "").strip().upper()
        mapping = {
            "24H": datetime.timedelta(hours=24),
            "7D": datetime.timedelta(days=7),
            "30D": datetime.timedelta(days=30),
            "90D": datetime.timedelta(days=90),
        }
        # Accept both 7D and LAST_7_DAYS style values.
        aliases = {
            "LAST_24_HOURS": "24H",
            "LAST_7_DAYS": "7D",
            "LAST_30_DAYS": "30D",
            "LAST_90_DAYS": "90D",
        }
        preset_clean = aliases.get(preset_clean, preset_clean)
        if preset_clean == "CUSTOM":
            since = MetaLeadService._normalise_ist_naive(since)
            until = MetaLeadService._normalise_ist_naive(until)
            if not since or not until:
                raise ValueError("Custom range requires both since and until dates.")
            if since > until:
                raise ValueError("The start date must be before the end date.")
            return since, until, "CUSTOM"
        if preset_clean in mapping:
            return now - mapping[preset_clean], now, preset_clean
        raise ValueError("Invalid range. Use 24H, 7D, 30D, 90D or CUSTOM.")

    @classmethod
    def create_import_job(
        cls,
        db: Session,
        user_id: Optional[int],
        preset: Optional[str],
        since: Optional[datetime.datetime] = None,
        until: Optional[datetime.datetime] = None,
        page_ids: Optional[List[str]] = None,
        form_ids: Optional[List[str]] = None,
    ) -> MetaImportJob:
        since, until, preset_clean = cls.resolve_import_range(preset, since, until)

        pages_query = db.query(MetaPage).filter(
            MetaPage.status.in_(["CONNECTED", "DISCONNECTED"])
        )
        if page_ids:
            pages_query = pages_query.filter(MetaPage.page_id.in_(page_ids))
        selected_pages = [
            p for p in pages_query.all() if p.is_selected or page_ids
        ]
        if not selected_pages:
            raise ValueError("No connected Pages are selected for import.")

        allowed_page_ids = [p.page_id for p in selected_pages]
        forms_query = db.query(MetaLeadForm).filter(
            MetaLeadForm.page_id.in_(allowed_page_ids)
        )
        if form_ids:
            forms_query = forms_query.filter(MetaLeadForm.form_id.in_(form_ids))
        else:
            forms_query = forms_query.filter(MetaLeadForm.is_selected.is_(True))
        forms = forms_query.all()
        if not forms:
            raise ValueError(
                "No Lead Forms are selected. Refresh forms and select at least one."
            )

        job = MetaImportJob(
            status="PENDING",
            range_preset=preset_clean,
            since=since,
            until=until,
            page_ids_json=_json_dumps([p.page_id for p in selected_pages]),
            form_ids_json=_json_dumps([f.form_id for f in forms]),
            total_forms=len(forms),
            created_by=user_id,
            created_at=datetime.datetime.utcnow(),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        cls.log_activity(
            db, "IMPORT_QUEUED", "INFO",
            f"Historical import #{job.id} queued for {len(forms)} form(s) ({preset_clean}).",
        )
        return job

    @classmethod
    def start_import_job(cls, job_id: int):
        """Start an import in a background thread without blocking the request.

        FastAPI runs synchronous endpoints in a worker thread, so there is no
        running asyncio loop here.  A daemon thread is the reliable choice and
        the worker creates its own SQLAlchemy session.
        """
        import threading

        worker = threading.Thread(
            target=cls.run_import_job_sync,
            args=(job_id,),
            name=f"meta-import-{job_id}",
            daemon=True,
        )
        worker.start()

    @classmethod
    def run_import_job_sync(cls, job_id: int):
        """Synchronous import worker. Safe to call from a test or a thread."""
        db = cls._session_factory()()
        try:
            job = db.query(MetaImportJob).filter(MetaImportJob.id == job_id).first()
            if not job:
                return
            if job.status not in {"PENDING", "RUNNING"}:
                return
            job.status = "RUNNING"
            job.started_at = datetime.datetime.utcnow()
            job.updated_at = datetime.datetime.utcnow()
            db.commit()

            form_ids = json.loads(job.form_ids_json or "[]")
            forms = (
                db.query(MetaLeadForm)
                .filter(MetaLeadForm.form_id.in_(form_ids))
                .all()
                if form_ids else []
            )
            since_ts = int(
                job.since.replace(tzinfo=IST_TIMEZONE).timestamp()
            ) if job.since else None
            until_ts = int(
                job.until.replace(tzinfo=IST_TIMEZONE).timestamp()
            ) if job.until else None

            for form in forms:
                db.refresh(job)
                if job.status == "CANCELLED":
                    break
                page = (
                    db.query(MetaPage)
                    .filter(MetaPage.page_id == form.page_id)
                    .first()
                )
                job.current_item = (
                    f"{page.page_name if page else form.page_id} / "
                    f"{form.name or form.form_id}"
                )
                job.updated_at = datetime.datetime.utcnow()
                db.commit()
                if not page:
                    job.failed += 1
                    job.processed_forms += 1
                    job.error = f"Page {form.page_id} is not connected."
                    db.commit()
                    continue

                token = decrypt_token(page.encrypted_access_token)
                if not token and page.connection_id:
                    connection = db.query(MetaConnection).filter(
                        MetaConnection.id == page.connection_id
                    ).first()
                    token = cls.connection_token(connection)
                token = token or MetaConfig.get_access_token()
                if not token:
                    job.failed += 1
                    job.processed_forms += 1
                    job.error = f"No access token for Page {page.page_id}."
                    db.commit()
                    continue

                params: Dict[str, Any] = {
                    "fields": LEAD_FETCH_FIELDS,
                    "limit": 100,
                }
                if since_ts:
                    params["since"] = since_ts
                if until_ts:
                    params["until"] = until_ts

                try:
                    leads = cls._graph_paginate(
                        f"{form.form_id}/leads", params, token=token, max_items=10000
                    )
                except MetaGraphError as exc:
                    job.failed += 1
                    job.error = _safe_error_message(
                        f"{form.name or form.form_id}: {exc.message}"
                    )
                    job.processed_forms += 1
                    job.updated_at = datetime.datetime.utcnow()
                    db.commit()
                    if exc.is_token_error and page:
                        page.status = "TOKEN_EXPIRED"
                        page.error_message = _safe_error_message(exc.message)
                        page.last_error_code = "TOKEN_EXPIRED"
                        db.commit()
                    continue

                for item in leads:
                    db.refresh(job)
                    if job.status == "CANCELLED":
                        break
                    job.total_fetched += 1
                    leadgen_id = str(item.get("id") or "").strip()
                    created_at = _parse_meta_datetime(item.get("created_time"))
                    # Defensive client-side range filter (Meta also receives
                    # since/until, but older API versions can ignore it).
                    if created_at:
                        if job.since and created_at < job.since:
                            db.commit()
                            continue
                        if job.until and created_at > job.until:
                            db.commit()
                            continue
                    try:
                        lead, is_reinquiry, is_duplicate = cls.ingest_lead(
                            db=db,
                            leadgen_id=leadgen_id,
                            page_id=form.page_id,
                            form_id=form.form_id,
                            graph_data=item,
                            source_hint=item.get("platform"),
                            is_import=True,
                        )
                        if is_duplicate:
                            job.duplicates += 1
                        else:
                            job.imported += 1
                        job.updated_at = datetime.datetime.utcnow()
                        db.commit()
                    except IntegrityError:
                        db.rollback()
                        job = db.query(MetaImportJob).filter(
                            MetaImportJob.id == job_id
                        ).first()
                        job.duplicates += 1
                        db.commit()
                    except Exception as exc:
                        db.rollback()
                        job = db.query(MetaImportJob).filter(
                            MetaImportJob.id == job_id
                        ).first()
                        job.failed += 1
                        job.error = _safe_error_message(
                            f"Lead {leadgen_id}: {exc}"
                        )
                        job.updated_at = datetime.datetime.utcnow()
                        db.commit()

                    # Be gentle with Graph API rate limits.
                    time.sleep(0.15)

                db.refresh(job)
                job.processed_forms += 1
                job.current_item = None
                job.updated_at = datetime.datetime.utcnow()
                db.commit()

            db.refresh(job)
            if job.status != "CANCELLED":
                job.status = "PARTIAL" if job.failed else "COMPLETED"
            job.current_item = None
            job.completed_at = datetime.datetime.utcnow()
            job.updated_at = datetime.datetime.utcnow()
            db.commit()
            cls.log_activity(
                db,
                "IMPORT_COMPLETED" if job.status == "COMPLETED" else "IMPORT_PARTIAL",
                "SUCCESS" if job.status == "COMPLETED" else "WARNING",
                (
                    f"Historical import #{job.id} {job.status.lower()}: "
                    f"{job.imported} imported, {job.duplicates} duplicate(s), "
                    f"{job.failed} failed."
                ),
            )
        except Exception as exc:
            logger.error("Meta import job %s crashed: %s", job_id, _safe_error_message(exc))
            try:
                db.rollback()
                job = db.query(MetaImportJob).filter(MetaImportJob.id == job_id).first()
                if job:
                    job.status = "FAILED"
                    job.error = _safe_error_message(exc)
                    job.completed_at = datetime.datetime.utcnow()
                    db.commit()
            except Exception:
                pass
        finally:
            db.close()

    @staticmethod
    def cancel_import_job(db: Session, job_id: int) -> Tuple[bool, str]:
        job = db.query(MetaImportJob).filter(MetaImportJob.id == job_id).first()
        if not job:
            return False, "Import job not found."
        if job.status in {"COMPLETED", "FAILED", "CANCELLED"}:
            return False, f"Import job is already {job.status.lower()}."
        job.status = "CANCELLED"
        job.completed_at = datetime.datetime.utcnow()
        job.current_item = None
        db.commit()
        return True, "Import cancellation requested."

    # ------------------------------------------------------------------
    # Forms / dashboard / activity
    # ------------------------------------------------------------------
    @staticmethod
    def get_forms(
        db: Session, page_id: Optional[str] = None, selected_only: bool = False
    ) -> List[MetaLeadForm]:
        query = db.query(MetaLeadForm)
        if page_id:
            query = query.filter(MetaLeadForm.page_id == page_id)
        if selected_only:
            query = query.filter(MetaLeadForm.is_selected.is_(True))
        return query.order_by(MetaLeadForm.page_id.asc(), MetaLeadForm.name.asc()).all()

    @staticmethod
    def set_forms_selection(
        db: Session, form_ids: List[str], selected: bool
    ) -> int:
        if not form_ids:
            return 0
        updated = (
            db.query(MetaLeadForm)
            .filter(MetaLeadForm.form_id.in_(form_ids))
            .update(
                {
                    MetaLeadForm.is_selected: selected,
                    MetaLeadForm.updated_at: datetime.datetime.utcnow(),
                },
                synchronize_session=False,
            )
        )
        db.commit()
        return updated

    @staticmethod
    def _token_status(connection: Optional[MetaConnection]) -> Dict[str, Any]:
        if not connection:
            return {
                "status": "NOT_CONNECTED",
                "expires_at": None,
                "days_remaining": None,
                "label": "Not connected",
            }
        if connection.status == "DISCONNECTED":
            return {
                "status": "DISCONNECTED",
                "expires_at": connection.token_expires_at,
                "days_remaining": None,
                "label": "Disconnected",
            }
        expires = connection.token_expires_at
        if not expires:
            return {
                "status": "VALID",
                "expires_at": None,
                "days_remaining": None,
                "label": "Valid (no expiry reported)",
            }
        now = datetime.datetime.utcnow()
        days = (expires - now).days
        if expires <= now:
            return {
                "status": "EXPIRED",
                "expires_at": expires.isoformat(),
                "days_remaining": 0,
                "label": "Expired — reconnect required",
            }
        if days <= 7:
            return {
                "status": "EXPIRING_SOON",
                "expires_at": expires.isoformat(),
                "days_remaining": days,
                "label": f"Expires in {days} day(s)",
            }
        return {
            "status": "VALID",
            "expires_at": expires.isoformat(),
            "days_remaining": days,
            "label": f"Valid for {days} day(s)",
        }

    @classmethod
    def get_dashboard(cls, db: Session) -> Dict[str, Any]:
        connection = cls.get_connection(db)
        pages = cls.get_all_pages(db)
        forms = cls.get_forms(db)
        selected_forms = [f for f in forms if f.is_selected]
        connected_pages = [p for p in pages if p.status == "CONNECTED"]

        meta_source_filter = or_(
            Lead.meta_lead_id.isnot(None),
            Lead.source.in_(META_SOURCE_VALUES),
        )
        total_meta_leads = db.query(Lead).filter(meta_source_filter).count()
        today_start = get_ist_now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_leads = (
            db.query(Lead)
            .filter(meta_source_filter, Lead.created_at >= today_start)
            .count()
        )
        failed_events = (
            db.query(MetaLeadEvent)
            .filter(MetaLeadEvent.status == "FAILED")
            .count()
        )
        pending_events = (
            db.query(MetaLeadEvent)
            .filter(MetaLeadEvent.status.in_(["RECEIVED", "RETRYING", "PROCESSING"]))
            .count()
        )
        last_event = (
            db.query(MetaLeadEvent)
            .order_by(MetaLeadEvent.created_at.desc())
            .first()
        )
        latest_import = (
            db.query(MetaImportJob)
            .order_by(MetaImportJob.created_at.desc())
            .first()
        )

        last_sync_candidates = [
            value
            for value in [
                connection.last_sync_at if connection else None,
                max((p.last_synced_at for p in pages if p.last_synced_at), default=None),
            ]
            if value
        ]
        last_sync_at = max(last_sync_candidates) if last_sync_candidates else None
        fp_last = (
            db.query(MetaLeadEvent)
            .filter(MetaLeadEvent.status.in_(["PROCESSED", "DUPLICATE"]))
            .order_by(MetaLeadEvent.processed_at.desc())
            .first()
        )
        if fp_last and fp_last.processed_at:
            last_sync_at = max(last_sync_at, fp_last.processed_at) if last_sync_at else fp_last.processed_at

        webhook_configured = bool(
            MetaConfig.get_verify_token() and MetaConfig.signature_verification_configured()
        )
        webhook_status = "NOT_CONFIGURED"
        if webhook_configured:
            if last_event and last_event.created_at:
                age = datetime.datetime.utcnow() - last_event.created_at
                webhook_status = "ACTIVE" if age.total_seconds() < 172800 else "IDLE"
            else:
                webhook_status = "READY"

        pages_out = []
        for p in pages:
            form_count = sum(1 for f in forms if f.page_id == p.page_id)
            selected_count = sum(
                1 for f in forms if f.page_id == p.page_id and f.is_selected
            )
            pages_out.append(
                {
                    "id": p.id,
                    "page_id": p.page_id,
                    "page_name": p.page_name,
                    "page_picture_url": p.page_picture_url,
                    "category": p.category,
                    "status": p.status,
                    "is_selected": bool(p.is_selected),
                    "auto_sync_enabled": bool(p.auto_sync_enabled),
                    "webhook_subscribed": bool(p.webhook_subscribed),
                    "instagram_account_id": p.instagram_account_id,
                    "instagram_username": p.instagram_username,
                    "lead_count": p.lead_count or 0,
                    "form_count": form_count,
                    "selected_form_count": selected_count,
                    "last_lead_at": p.last_lead_at.isoformat() if p.last_lead_at else None,
                    "last_synced_at": p.last_synced_at.isoformat() if p.last_synced_at else None,
                    "forms_last_synced_at": p.forms_last_synced_at.isoformat() if p.forms_last_synced_at else None,
                    "error_message": p.error_message,
                    "last_error_code": p.last_error_code,
                    "token_expires_at": p.token_expires_at.isoformat() if p.token_expires_at else None,
                }
            )

        forms_out = [
            {
                "id": f.id,
                "form_id": f.form_id,
                "page_id": f.page_id,
                "name": f.name,
                "status": f.status,
                "locale": f.locale,
                "is_selected": bool(f.is_selected),
                "leads_count": f.leads_count or 0,
                "last_lead_at": f.last_lead_at.isoformat() if f.last_lead_at else None,
                "last_synced_at": f.last_synced_at.isoformat() if f.last_synced_at else None,
            }
            for f in forms
        ]

        return {
            "configured": MetaConfig.oauth_configured() or bool(pages),
            "app_id": MetaConfig.get_app_id() or None,
            "api_version": MetaConfig.get_api_version(),
            "webhook_url": MetaConfig.get_webhook_url(),
            "webhook_status": webhook_status,
            "webhook_configured": webhook_configured,
            "connection": (
                {
                    "id": connection.id,
                    "fb_user_id": connection.fb_user_id,
                    "fb_user_name": connection.fb_user_name,
                    "status": connection.status,
                    "auto_sync_enabled": bool(connection.auto_sync_enabled),
                    "scopes": [s for s in (connection.scopes or "").split(",") if s],
                    "connected_by_user_id": connection.connected_by_user_id,
                    "last_sync_at": connection.last_sync_at.isoformat() if connection.last_sync_at else None,
                    "last_webhook_at": connection.last_webhook_at.isoformat() if connection.last_webhook_at else None,
                    "last_error": connection.last_error,
                    "created_at": connection.created_at.isoformat() if connection.created_at else None,
                    "token": cls._token_status(connection),
                }
                if connection else None
            ),
            "stats": {
                "connected_accounts": 1 if connection and connection.status == "CONNECTED" else 0,
                "total_pages": len(pages),
                "connected_pages": len(connected_pages),
                "selected_pages": sum(1 for p in pages if p.is_selected),
                "total_forms": len(forms),
                "selected_forms": len(selected_forms),
                "instagram_assets": sum(1 for p in pages if p.instagram_account_id),
                "total_leads": total_meta_leads,
                "today_leads": today_leads,
                "failed_events": failed_events,
                "pending_events": pending_events,
                "last_sync_at": last_sync_at.isoformat() if last_sync_at else None,
                "last_webhook_at": last_event.created_at.isoformat() if last_event else None,
            },
            "token": cls._token_status(connection),
            "pages": pages_out,
            "forms": forms_out,
            "latest_import": cls._import_job_out(latest_import) if latest_import else None,
        }

    @staticmethod
    def _import_job_out(job: MetaImportJob) -> Dict[str, Any]:
        total = max(job.total_fetched or 0, 0)
        return {
            "id": job.id,
            "status": job.status,
            "range_preset": job.range_preset,
            "since": job.since.isoformat() if job.since else None,
            "until": job.until.isoformat() if job.until else None,
            "total_forms": job.total_forms or 0,
            "processed_forms": job.processed_forms or 0,
            "total_fetched": total,
            "imported": job.imported or 0,
            "duplicates": job.duplicates or 0,
            "failed": job.failed or 0,
            "error": job.error,
            "current_item": job.current_item,
            "created_by": job.created_by,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "progress": (
                int(((job.processed_forms or 0) / job.total_forms) * 100)
                if job.total_forms else (100 if job.status in {"COMPLETED", "PARTIAL"} else 0)
            ),
        }

    @classmethod
    def list_import_jobs(cls, db: Session, limit: int = 20) -> List[Dict[str, Any]]:
        jobs = (
            db.query(MetaImportJob)
            .order_by(MetaImportJob.id.desc())
            .limit(limit)
            .all()
        )
        return [cls._import_job_out(job) for job in jobs]

    @staticmethod
    def get_import_job(db: Session, job_id: int) -> Optional[Dict[str, Any]]:
        job = db.query(MetaImportJob).filter(MetaImportJob.id == job_id).first()
        return MetaLeadService._import_job_out(job) if job else None

    @classmethod
    def list_events(
        cls, db: Session, status_filter: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        query = db.query(MetaLeadEvent)
        if status_filter:
            query = query.filter(MetaLeadEvent.status == status_filter.upper())
        events = query.order_by(MetaLeadEvent.id.desc()).limit(limit).all()
        page_names = {
            p.page_id: p.page_name for p in db.query(MetaPage).all()
        }
        form_names = {
            f.form_id: f.name for f in db.query(MetaLeadForm).all()
        }
        return [
            {
                "id": e.id,
                "event_key": e.event_key,
                "leadgen_id": e.leadgen_id,
                "page_id": e.page_id,
                "page_name": page_names.get(e.page_id),
                "form_id": e.form_id,
                "form_name": form_names.get(e.form_id),
                "platform": e.platform,
                "status": e.status,
                "attempt_count": e.attempt_count or 0,
                "max_attempts": e.max_attempts or 8,
                "next_retry_at": e.next_retry_at.isoformat() if e.next_retry_at else None,
                "last_error": e.last_error,
                "lead_id": e.lead_id,
                "is_reinquiry": bool(e.is_reinquiry),
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "processed_at": e.processed_at.isoformat() if e.processed_at else None,
            }
            for e in events
        ]

    @classmethod
    def get_activity_log(cls, db: Session, limit: int = 50) -> List[Dict[str, Any]]:
        limit = max(1, min(limit, 200))
        logs = (
            db.query(IntegrationLog)
            .filter(IntegrationLog.integration_type == "META")
            .order_by(IntegrationLog.created_at.desc())
            .limit(limit)
            .all()
        )
        events = cls.list_events(db, limit=limit)
        combined: List[Dict[str, Any]] = []
        for log in logs:
            combined.append(
                {
                    "source": "integration",
                    "id": log.id,
                    "event_type": log.event_type,
                    "status": log.status,
                    "message": log.message,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
            )
        for event in events:
            label = "Lead captured"
            if event["status"] == "DUPLICATE":
                label = "Duplicate lead ignored"
            elif event["status"] == "FAILED":
                label = "Lead sync failed"
            elif event["status"] == "RETRYING":
                label = f"Lead sync retry {event['attempt_count']}/{event['max_attempts']}"
            elif event["status"] == "IGNORED":
                label = "Lead ignored"
            combined.append(
                {
                    "source": "lead_event",
                    "id": event["id"],
                    "event_type": f"LEAD_{event['status']}",
                    "status": (
                        "SUCCESS"
                        if event["status"] in {"PROCESSED", "DUPLICATE"}
                        else "ERROR"
                        if event["status"] == "FAILED"
                        else "WARNING"
                        if event["status"] in {"RETRYING", "IGNORED"}
                        else "INFO"
                    ),
                    "message": (
                        f"{label}: {event['page_name'] or event['page_id'] or 'Page'}"
                        + (f" / {event['form_name']}" if event.get("form_name") else "")
                        + (f" — {event['last_error']}" if event.get("last_error") else "")
                    ),
                    "page_id": event["page_id"],
                    "form_id": event["form_id"],
                    "lead_id": event["lead_id"],
                    "created_at": event["created_at"],
                }
            )
        combined.sort(key=lambda item: item.get("created_at") or "", reverse=True)
        return combined[:limit]
