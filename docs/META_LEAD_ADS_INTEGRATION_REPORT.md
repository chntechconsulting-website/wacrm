# Facebook & Instagram Lead Ads — Implementation Report

**Project:** CHN CRM / WaCRM  
**Scope:** Native Facebook & Instagram Instant Form (Lead Ads) integration built on the existing Meta OAuth, Graph API and webhook infrastructure.  
**Status:** Implemented, automated tests passing. Live Meta end-to-end validation is pending production permissions/App Review.

---

## 1. Completed Features

### Connection and OAuth
- Official Meta OAuth connect flow from **Settings → Integrations → Facebook & Instagram**.
- Stateless, HMAC-SHA256-signed OAuth `state` with a 10-minute expiry and nonce.
- Callback re-validates that the connected user still exists and is an **ADMIN**.
- Long-lived user token exchange, encrypted at rest with Fernet (`crypto.py`), derived from `SECRET_KEY`.
- Reconnect (re-run OAuth), disconnect (optionally revoke Meta permissions), connection status, token expiry and days remaining.
- Connection-level and per-Page **Auto Sync** toggles.
- Required Meta permissions are displayed in the UI.

### Page and Lead Form discovery
- Authorized Pages are discovered automatically after OAuth — name, image, Page ID, category, status, linked Instagram business account, form counts and selection state. No manual Page ID entry.
- All Instant Forms are discovered per Page — name, Form ID, status, locale, lead count, selection state, last sync/lead time.
- Page selection, per-Page Auto Sync, manual **Sync Now**, Page refresh and Page webhook re-subscription.
- Lead Form multi-select plus **Select All / Deselect All** per Page.
- Pages no longer returned by Meta are marked `ACCESS_REMOVED` instead of being deleted.

### Webhook ingestion
- Reuses the existing endpoint: `POST /api/integrations/meta/webhook`.
- `GET` verification challenge uses `META_VERIFY_TOKEN`; `POST` requires a valid `X-Hub-Signature-256` and **fails closed** (`503`) if `META_APP_SECRET` is missing.
- Rejects invalid signatures (`403`) and non-JSON payloads (`400`).
- Validates Page existence, Page selection, Page status, Page Auto Sync, connection Auto Sync and Form selection before fetching a lead.
- Durable event queue (`meta_lead_events`) with event keys for idempotency and duplicate suppression.
- Graph lead fetch is offloaded to the threadpool so slow Meta responses do not block the event loop.
- Background retry worker runs every 60 seconds with exponential backoff (max 8 attempts), plus manual retry per event and **Retry Failed Leads**.
- Page `leadgen` subscription via `subscribed_apps`; subscription failures are recorded without breaking asset sync.

### Lead mapping and CRM integration
- Maps:
  - Name, Mobile, Email, City and all custom form answers.
  - Page name/ID, Form name/ID, Meta Lead ID.
  - Campaign/Ad Set/Ad IDs and names (when Meta returns them).
  - Meta `created_time`, preserved in IST on the Lead, LeadEnquiry and lead activity.
  - `Lead Source` = `META` (Facebook) or `INSTAGRAM`, based on the actual lead platform.
- Attribution stored both on `Lead` (latest) and `LeadEnquiry` (per enquiry), so re-inquiries do not lose the ad attribution.
- Reuses `ReInquiryService.register_enquiry()` and `assign_lead_immediately()` — existing dedupe, auto-assignment, notifications and follow-up workflows are unchanged.
- No separate assignment engine was introduced.

### Historical import
- Presets: **24 hours, 7 days, 30 days, 90 days, Custom** date range.
- Import runs in a background daemon thread; the API returns immediately.
- Persisted progress: status, processed/total forms, fetched/imported/duplicates/failed counts, current item, timestamps and error.
- Cancel endpoint; completed/partial status reporting.
- Dedupe by Meta Lead ID (`Lead.meta_lead_id` + `meta_lead_events.event_key`).
- Respects Page/Form selection and Meta-side permissions/retention.

### Dashboard and activity
- Account, Page and Form counts; selected forms.
- Total Meta/Instagram leads and today's leads.
- Failed and pending sync/event counts.
- Last successful sync and last webhook time.
- Token state (`VALID`, `EXPIRING_SOON`, `EXPIRED`, `DISCONNECTED`) and webhook state.
- Recent import jobs, failed lead events and a unified activity log (connection, sync, Page/Form, webhook, import, retries).

### Error handling
- Expired/revoked token → connection/Page marked `TOKEN_EXPIRED`, event queued for retry, UI prompts reconnect.
- Missing permissions (`code 10` / permission errors) → Page marked `ERROR` with `PERMISSION_MISSING`, event queued.
- Page access removed → event `IGNORED`, Page marked `ACCESS_REMOVED`.
- Invalid/missing webhook signature → `403`; missing app secret → `503`; no lead is created.
- Meta rate limits / HTTP 429 / transient 5xx → Graph request retries with backoff.
- Network failures, failed lead fetches and post-fetch crashes → event stays `RETRYING` with `next_retry_at`.
- Duplicates → no second lead; event and lead counts report duplicates.
- Unselected Page/Form or disabled Auto Sync → event `IGNORED` with a clear reason.

### Security
- Access tokens are encrypted server-side and never returned by any API; only masked tokens are exposed.
- Tokens and customer data are not written to logs.
- OAuth state is signed and expiring; callback re-checks ADMIN role.
- Webhook signature verification is mandatory.
- Write/settings endpoints are **ADMIN-only**; dashboard/read endpoints are **ADMIN/MANAGER**; the legacy `/status` endpoint now requires authentication.
- All DB access is parameterized via SQLAlchemy.

### Compatibility
- Meta Ads, WhatsApp (Cloud API and Click-to-WhatsApp ads), website leads, Excel import, CRM assignment rules, sales dashboards and reports remain intact.
- `META`/`INSTAGRAM` source filters were added to leads, activities and reports so Facebook and Instagram leads appear in existing CRM views.
- Legacy manual Page-ID/token endpoints remain available for backward compatibility.

---

## 2. API Surface

### OAuth / connection (ADMIN unless noted)
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/integrations/meta/oauth/start` | Build Meta OAuth URL |
| GET | `/api/integrations/meta/oauth/callback` | OAuth callback (public, signed state) |
| GET | `/api/integrations/meta/connection` | Connection + token + stats (ADMIN/MANAGER) |
| POST | `/api/integrations/meta/connection/disconnect` | Disconnect / optionally revoke |
| POST | `/api/integrations/meta/connection/auto-sync` | Connection Auto Sync toggle |
| POST | `/api/integrations/meta/sync-now` | Refresh assets/forms/subscriptions + process due events |

### Pages / forms
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/integrations/meta/assets/pages` | Discovered Pages (ADMIN/MANAGER) |
| POST | `/api/integrations/meta/pages/{page_id}/select` | Select/deselect Page |
| POST | `/api/integrations/meta/pages/{page_id}/auto-sync` | Page Auto Sync toggle |
| POST | `/api/integrations/meta/pages/{page_id}/subscribe` | Re-subscribe Page webhook |
| POST | `/api/integrations/meta/pages/{page_id}/forms/sync` | Refresh Page forms |
| GET | `/api/integrations/meta/forms` | Forms, optional `page_id` (ADMIN/MANAGER) |
| POST | `/api/integrations/meta/forms/selection` | Multi-select / Select All |

### Imports / events / dashboard
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/integrations/meta/import` | Start historical import |
| GET | `/api/integrations/meta/import/jobs` | List import jobs (ADMIN/MANAGER) |
| GET | `/api/integrations/meta/import/jobs/{job_id}` | Job progress (ADMIN/MANAGER) |
| POST | `/api/integrations/meta/import/jobs/{job_id}/cancel` | Cancel import |
| GET | `/api/integrations/meta/events?status=FAILED` | List events (ADMIN/MANAGER) |
| POST | `/api/integrations/meta/events/{event_id}/retry` | Retry one event |
| POST | `/api/integrations/meta/events/retry-failed` | Retry all failed leads |
| GET | `/api/integrations/meta/dashboard` | Dashboard (ADMIN/MANAGER) |
| GET | `/api/integrations/meta/activity` | Activity log (ADMIN/MANAGER) |

Legacy manual endpoints (`/pages` CRUD, `/pages/{id}/sync|connect|disconnect|refresh`, `/status`) remain mounted.

---

## 3. Required Meta Permissions

Default OAuth scope set (`META_OAUTH_SCOPES` can override):

| Permission | Purpose |
|---|---|
| `pages_show_list` | List Pages the user manages |
| `pages_read_engagement` | Read Page metadata |
| `pages_manage_metadata` | Manage Page webhook subscriptions (`subscribed_apps`) |
| `leads_retrieval` | Read leadgen data / Instant Form leads |
| `ads_read` | Campaign/Ad Set/Ad attribution |
| `instagram_basic` | Read linked Instagram business account metadata |
| `business_management` | Required in many Business Manager setups for asset access (grant via App Review/business verification) |

Production notes:
- Standard Access only works for users with a role on the Meta App. Production requires **Advanced Access** for `leads_retrieval`, `pages_manage_metadata`, `pages_read_engagement` and `pages_show_list`, and usually `ads_read`.
- Instagram Lead Ads require an Instagram business/creator account linked to an authorized Facebook Page, and Meta permissions/asset access for that account.
- `instagram_basic` alone does not guarantee Instagram Instant Form availability; eligibility depends on the account, region and Meta product support.

---

## 4. Database Changes

All changes are additive.

### New tables
| Table | Purpose |
|---|---|
| `meta_connections` | One official OAuth connection; encrypted long-lived user token, scopes, expiry, Auto Sync, sync/webhook timestamps |
| `meta_lead_forms` | Discovered Instant Forms, Page mapping, selection, lead counts, sync timestamps |
| `meta_lead_events` | Durable webhook/queue with event key, status, attempts, backoff, payload, lead link |
| `meta_import_jobs` | Historical import progress and counters |

### Extended columns — `leads`
`meta_page_id`, `meta_page_name`, `meta_form_name`, `meta_campaign_id`, `meta_adset_id`, `meta_adset_name`, `meta_ad_id`, `meta_ad_name`, `meta_platform`, `meta_created_at`, `meta_custom_answers`

(`meta_lead_id`, `meta_form_id` already existed.)

### Extended columns — `meta_pages`
`connection_id`, `page_picture_url`, `instagram_account_id`, `instagram_username`, `is_selected`, `auto_sync_enabled`, `webhook_subscribed`, `token_expires_at`, `forms_last_synced_at`, `last_lead_at`, `last_error_code`

### Extended columns — `lead_enquiries`
`meta_lead_id`, `meta_form_id`, `meta_page_id`, `meta_platform`, `meta_campaign_id`, `meta_adset_id`, `meta_ad_id`

Startup migrations in `backend/main.py` create the tables and add missing columns automatically, so an existing MySQL installation upgrades in place.

---

## 5. Test Results

### Automated
- **Backend full suite:** `470 tests`, `OK`, ~56 s (`python -W ignore -m unittest discover -s tests -q`).
- **Meta Lead Ads suite:** `30 tests`, `OK` (`python -W ignore -m unittest tests.test_meta_lead_ads -v`).
- **Frontend build:** Vite production build succeeds (2,085 modules; only the existing bundle-size warning).
- Local MySQL schema verified: all four new tables plus the Meta columns on `leads`, `meta_pages` and `lead_enquiries`.

### Runtime smoke test (real FastAPI app + local MySQL)
| Check | Result |
|---|---|
| Webhook verification with the configured verify token | `200`, challenge returned |
| Webhook verification with a wrong token | `403` |
| Webhook POST with an invalid signature | `403` |
| Dashboard without authentication | `401` |
| Legacy `/status` without authentication | `401` |
| OAuth start without authentication | `401` |

New Meta tests cover:
- OAuth start/callback, state round-trip, expiry and tamper rejection.
- Connect, disconnect, Auto Sync, token encryption/non-exposure.
- Page/Instagram/Form discovery, Sync Now, Select All.
- Webhook signature validation and fail-closed behavior.
- Facebook and Instagram source selection.
- Lead mapping (name/phone/email/city/custom answers/campaign/adset/ad).
- Meta-created time preservation in IST.
- Assignment and notification creation.
- Duplicate webhook suppression.
- Failed fetch + retry; expired token; permission errors; access removed; rate-limit retry.
- Historical import, progress, background thread and dedupe.
- Dashboard/activity; ADMIN vs MANAGER access; legacy `/status` auth.
- Unselected form and disabled Auto Sync.

### 12 production scenarios — status
| # | Scenario | Automated result |
|---|---|---|
| 1 | New Facebook lead arrives by webhook | Pass |
| 2 | New Instagram lead arrives with correct source | Pass |
| 3 | Duplicate webhook delivery | Pass — one lead only |
| 4 | Historical import (preset/custom) with progress | Pass — dedupe on re-run |
| 5 | Expired/revoked token | Pass — queued for retry, reconnect prompt state |
| 6 | Missing permissions | Pass — Page error code + queued event |
| 7 | Page access removed | Pass — event ignored, Page marked `ACCESS_REMOVED` |
| 8 | Invalid/missing webhook signature or app secret | Pass — `403`/`503`, no lead |
| 9 | Meta rate limit / transient Graph error | Pass — retried |
| 10 | Failed lead fetch / network error | Pass — queued, manual and background retry |
| 11 | Duplicate lead / re-inquiry attribution | Pass — dedupe and per-enquiry attribution |
| 12 | Admin settings, roles, dashboard and activity log | Pass |

### Not yet validated live
- Real Meta webhook deliveries and real Instant Form leads require approved production permissions.
- Instagram Lead Ads require an authorized Instagram business asset.
- Historical import against live Meta data is limited by Meta retention/permissions.

### Live credential diagnostic (2026-11-12)
- `META_APP_ID` / `META_APP_SECRET`: accepted by Meta.
- The existing `META_ACCESS_TOKEN` in `backend/.env`: **rejected by Meta** with `OAuthException 190 — Invalid OAuth access token signature`. It cannot be used for live lead retrieval.
- Consequence: live testing must start with the **OAuth connect flow** once the required permissions/App Review are in place. The legacy env-token mode remains as a compatibility fallback only.

---

## 6. Configuration

Required in `backend/.env` (see `.env.example`):

```env
META_APP_ID="..."
META_APP_SECRET="..."
META_VERIFY_TOKEN="..."
META_API_VERSION="v26.0"
PUBLIC_BASE_URL="https://www.wapluscrm.in"

# Optional overrides
META_OAUTH_REDIRECT_URI=""
META_OAUTH_FRONTEND_REDIRECT=""
META_WEBHOOK_URL=""
META_OAUTH_SCOPES=""
```

Defaults:
- OAuth callback: `<PUBLIC_BASE_URL>/api/integrations/meta/oauth/callback`
- Frontend redirect: `<PUBLIC_BASE_URL>/settings/integrations/meta`
- Webhook: `<PUBLIC_BASE_URL>/api/integrations/meta/webhook`

---

## 7. Remaining Meta Approval / Deployment Requirements

1. **Meta App Review / Advanced Access**
   - `leads_retrieval`
   - `pages_manage_metadata`
   - `pages_read_engagement`
   - `pages_show_list`
   - `ads_read`
   - `business_management` (as required by asset setup)
   - Instagram permissions/asset authorization where Instagram Lead Ads are required.

2. **Meta App Dashboard configuration**
   - Add the exact OAuth redirect URI under **Facebook Login → Settings → Valid OAuth Redirect URIs**.
   - Configure the Webhooks callback URL and verify token.
   - Subscribe the App to the **`page`** object and the **`leadgen`** field.
   - Ensure the App is in **Live** mode for production users.

3. **Business verification and compliance**
   - Business verification, privacy policy URL, terms of service and data-deletion instructions may be required before Advanced Access is granted.

4. **Live validation**
   - Use Meta's Lead Ads Testing Tool (or a real test campaign) to verify:
     - webhook signature + delivery,
     - Facebook and Instagram lead creation,
     - campaign/ad attribution,
     - historical import for each range,
     - token expiry/reconnect behavior.
   - Confirm that the production domain is reachable over HTTPS and that `PUBLIC_BASE_URL` matches the deployed origin.

5. **Operational notes**
   - Historical imports and the retry worker run inside the application process. If the backend is scaled to multiple workers/instances, run imports/workers on a single worker or add a distributed lock.
   - Rate-limit retries and the durable event queue reduce data loss, but monitor `failed` event counts and token expiry from the dashboard.
   - Meta lead-data retention limits how far back historical imports can retrieve; the 90-day preset is the practical maximum.
