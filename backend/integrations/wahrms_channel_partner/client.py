"""HTTP client for the WA HRMS Channel Partner API.

The integration is read-mostly: partner, application, payout and lead data are
mirrored read-only. The single write operation is the documented
``PATCH /leads/{id}`` used for two-way lead status synchronisation. No endpoint
can create partners, approve applications or move money.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import httpx

from integrations.wahrms_channel_partner.config import EffectiveConfig

logger = logging.getLogger("wacrm.channel_partner")

# The API key must have the ``write`` scope (and its creator must hold the WA
# HRMS Channel Partner edit permission) for PATCH /leads/{id} to succeed. The
# key itself never leaves the backend; the frontend only calls CRM endpoints.
WRITE_SCOPE_REQUIRED = True


class ChannelPartnerNotConfigured(Exception):
    pass


class ChannelPartnerAPIError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        errors: Optional[Dict[str, Any]] = None,
        payload: Any = None,
        retry_after: Optional[float] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.errors = errors
        self.payload = payload
        self.retry_after = retry_after


class ChannelPartnerClient:
    def __init__(
        self,
        config: EffectiveConfig,
        *,
        transport: Optional[httpx.BaseTransport] = None,
        timeout: float = 25.0,
        max_retries: int = 2,
        sleep_func=time.sleep,
    ):
        if not config.configured:
            raise ChannelPartnerNotConfigured(
                "WA HRMS Channel Partner API credentials are not configured."
            )
        self.config = config
        self.timeout = timeout
        self.max_retries = max_retries
        self._sleep = sleep_func
        self._client = httpx.Client(
            timeout=timeout,
            transport=transport,
            follow_redirects=False,
        )

    # -- lifecycle ---------------------------------------------------------
    def close(self):
        try:
            self._client.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    # -- request helpers ---------------------------------------------------
    def _url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        base = self.config.base_url.rstrip("/")
        # WA HRMS routes GET / as the partner list. Sending a trailing slash
        # makes the API treat the empty segment as a partner UUID and return
        # HTTP 400 "Validation failed (uuid is expected)".
        if not path or path == "/":
            return base
        return f"{base}/{path.lstrip('/')}"

    @staticmethod
    def _error_from_response(response: httpx.Response) -> ChannelPartnerAPIError:
        payload: Any = None
        message = f"WA HRMS returned HTTP {response.status_code}."
        errors = None
        try:
            payload = response.json()
            if isinstance(payload, dict):
                message = (
                    payload.get("message")
                    or payload.get("error")
                    or payload.get("detail")
                    or message
                )
                if isinstance(payload.get("errors"), dict):
                    errors = payload["errors"]
        except Exception:
            text = (response.text or "").strip()
            if text:
                message = text[:400]
        retry_after = None
        header = response.headers.get("Retry-After")
        if header:
            try:
                retry_after = float(header)
            except ValueError:
                retry_after = None
        return ChannelPartnerAPIError(
            str(message),
            status_code=response.status_code,
            errors=errors,
            payload=payload,
            retry_after=retry_after,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        max_retries: Optional[int] = None,
        retry_transient: bool = True,
    ) -> Any:
        url = self._url(path)
        retries = self.max_retries if max_retries is None else max_retries
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Accept": "application/json",
            "User-Agent": "WaCRM-ChannelPartner/1.0",
        }
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        clean_params = {
            key: value for key, value in (params or {}).items() if value not in (None, "")
        }

        last_error: Optional[ChannelPartnerAPIError] = None
        for attempt in range(retries + 1):
            try:
                response = self._client.request(
                    method,
                    url,
                    headers=headers,
                    params=clean_params or None,
                    json=json_body,
                )
            except httpx.HTTPError as exc:
                last_error = ChannelPartnerAPIError(
                    f"Could not reach WA HRMS: {exc.__class__.__name__}."
                )
                if attempt >= retries:
                    break
                self._sleep(min(2 ** attempt, 4))
                continue

            if 200 <= response.status_code < 300:
                if response.status_code == 204 or not response.content:
                    return {}
                try:
                    return response.json()
                except ValueError:
                    raise ChannelPartnerAPIError(
                        "WA HRMS returned a non-JSON response.",
                        status_code=response.status_code,
                        payload=(response.text or "")[:1000],
                    )

            error = self._error_from_response(response)
            last_error = error
            retryable = retry_transient and (
                response.status_code == 429 or response.status_code >= 500
            )
            if not retryable or attempt >= retries:
                break
            delay = error.retry_after if error.retry_after is not None else 2 ** attempt
            self._sleep(min(max(delay, 0.25), 5.0))

        raise last_error or ChannelPartnerAPIError("WA HRMS request failed.")

    def get(
        self,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        max_retries: Optional[int] = None,
    ) -> Any:
        return self._request("GET", path, params=params, max_retries=max_retries)

    def patch(
        self,
        path: str,
        *,
        json_body: Optional[Dict[str, Any]] = None,
        max_retries: int = 0,
    ) -> Any:
        """Send one PATCH request.

        PATCH retries default to zero on purpose: a timed-out request may have
        been applied by WA HRMS, so the CRM asks the operator to retry
        explicitly instead of silently sending the same status twice.
        """
        return self._request(
            "PATCH",
            path,
            json_body=json_body,
            max_retries=max_retries,
            retry_transient=False,
        )

    def update_lead(
        self,
        lead_id: str,
        *,
        status: Optional[str] = None,
        review_note: Optional[str] = None,
    ) -> Any:
        """Apply the documented ``PATCH /leads/{id}`` status update.

        Only the fields that actually change are sent. ``reviewNote`` is shown
        to the partner by WA HRMS, so callers must pass a partner-safe reason.
        """
        body: Dict[str, Any] = {}
        if status:
            body["status"] = status
        if review_note is not None:
            body["reviewNote"] = review_note
        if not body:
            raise ValueError("At least one lead field must be supplied.")
        return self.patch(f"/leads/{lead_id}", json_body=body)

    # -- documented read journeys -----------------------------------------
    def get_summary(self) -> Any:
        return self.get("/summary", max_retries=1)

    def list_partners(self, **params) -> Any:
        return self.get("/", params=params)

    def get_partner(self, partner_id: str) -> Any:
        return self.get(f"/{partner_id}")

    def get_inactivity_settings(self) -> Any:
        return self.get("/settings/inactivity")

    def list_applications(self, status: Optional[str] = None) -> Any:
        params = {"status": status} if status else None
        return self.get("/applications", params=params)

    def get_application(self, application_id: str) -> Any:
        return self.get(f"/applications/{application_id}")

    def get_application_document(self, application_id: str, kind: str) -> Any:
        return self.get(f"/applications/{application_id}/documents/{kind}")

    def list_leads(self, status: Optional[str] = None, partner_id: Optional[str] = None) -> Any:
        return self.get(
            "/leads",
            params={"status": status, "partnerId": partner_id},
        )

    def list_partner_clients(self, partner_id: str) -> Any:
        return self.get(f"/{partner_id}/clients")

    def list_partner_coupons(self, partner_id: str) -> Any:
        return self.get(f"/{partner_id}/coupons")

    def list_partner_commissions(
        self,
        partner_id: str,
        *,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Any:
        return self.get(
            f"/{partner_id}/commissions",
            params={
                "status": status,
                "from": date_from,
                "to": date_to,
                "limit": limit,
                "offset": offset,
            },
        )

    def list_payouts(
        self, status: Optional[str] = None, partner_id: Optional[str] = None
    ) -> Any:
        return self.get("/payouts", params={"status": status, "partnerId": partner_id})

    def get_payout(self, payout_id: str) -> Any:
        return self.get(f"/payouts/{payout_id}")

    def list_events(
        self, after: int = 0, limit: int = 500, event_type: Optional[str] = None
    ) -> Any:
        capped = max(1, min(int(limit or 500), 500))
        return self.get(
            "/events",
            params={"after": int(after or 0), "limit": capped, "type": event_type},
            max_retries=1,
        )

    def test_connection(self) -> Dict[str, Any]:
        started = time.time()
        try:
            payload = self.get("/summary", max_retries=0)
            elapsed = int((time.time() - started) * 1000)
            return {
                "ok": True,
                "status_code": 200,
                "message": "Connected to WA HRMS Channel Partner API.",
                "latency_ms": elapsed,
                "endpoint": "/summary",
                "response": payload,
                "tested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        except ChannelPartnerAPIError as exc:
            elapsed = int((time.time() - started) * 1000)
            return {
                "ok": False,
                "status_code": exc.status_code,
                "message": exc.message,
                "errors": exc.errors,
                "latency_ms": elapsed,
                "endpoint": "/summary",
                "tested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
