# WhatsApp Ad Leads (Meta Click-to-WhatsApp)

Automatically captures **Meta Click-to-WhatsApp (CTWA)** ad enquiries into the
existing CRM lead pipeline. This is an additive attribution layer on top of the
current leads/re-inquiry/assignment system — it does **not** replace the normal
WhatsApp inbox and it does **not** create a second lead system.

> **Status:** code and automated tests are complete. End-to-end verification with
> a real Meta ad click is still pending because no production Meta/WhatsApp
> account, number, webhook, or token has been changed.

---

## 1. What is captured

When a customer taps a Click-to-WhatsApp ad and sends the first message, Meta
includes a `referral` object on the message. The webhook stores:

| CRM data | Source |
|---|---|
| Phone number | `messages[].from` |
| Customer/profile name | `contacts[].profile.name` |
| First enquiry message | message `text.body` (or a readable placeholder for media) |
| Message timestamp | message `timestamp` |
| Ad ID | `referral.source_id` |
| Referral source type | `referral.source_type` (normally `ad`) |
| Referral source URL | `referral.source_url` |
| Headline | `referral.headline` |
| Ad body | `referral.body` |
| CTWA click ID | `referral.ctwa_clid` |
| Campaign/ad names | Marketing API later, when authorized |
| Raw referral metadata | `raw_referral` JSON |
| Channel | always `WHATSAPP` |
| WABA ID / phone number ID | webhook metadata |

The lead itself is created through the existing
`ReInquiryService.register_enquiry` flow, so duplicate detection, re-inquiry
history, assignment, permissions, reports, and the normal Leads screen all keep
working. The lead source is stored canonically as `WHATSAPP_ADS` and shown in
the UI as **WhatsApp Ads**. This is intentionally separate from the existing
Meta Instant Form source (`META`).

---

## 2. Architecture

```
Meta WhatsApp Cloud API
        │  signed POST (X-Hub-Signature-256)
        ▼
/integrations/whatsapp_ads/webhook.py
        │  verify signature → parse → idempotency
        ▼
WhatsAppAdLeadService.process_payload()
        │
        ├── whatsapp_webhook_events      (unique event key / wamid)
        ├── ReInquiryService.register_enquiry()  → existing leads + lead_enquiries
        ├── LeadAssignmentService.assign_lead_immediately()
        ├── whatsapp_ad_attributions     (ad attribution + raw referral)
        ├── optional mirror to existing WhatsApp inbox
        └── Marketing API resolver → campaign/ad names (background)
```

### New tables

`whatsapp_ad_attributions`

- `lead_id` → existing `leads.id`
- `lead_enquiry_id` → existing `lead_enquiries.id`
- message identity: `wamid` (unique), `phone`, `contact_name`,
  `message_text`, `message_type`, `message_timestamp`
- channel metadata: `channel` (`WHATSAPP`), `business_account_id`,
  `phone_number_id`
- attribution: `source_type`, `source_id`, `source_url`, `headline`,
  `ad_body`, `ctwa_clid` (unique when present)
- campaign/ad: `campaign_id`, `campaign_name`, `ad_name`, `resolution_status`,
  `resolution_error`, `resolved_at`
- `raw_referral` JSON
- `created_at` / `updated_at`

`whatsapp_webhook_events`

- unique `event_key` (derived from `wamid` or a deterministic payload hash)
- optional `wamid`
- event type, processing status/error, timestamps, raw payload
- prevents duplicate leads when Meta retries a delivery

The migration is additive and idempotent. It never alters or deletes existing
CRM rows.

---

## 3. Setup

### 3.1 Environment variables

Add these to `backend/.env` (all are optional if the existing WhatsApp/Meta
configuration already supplies safe fallbacks):

```dotenv
# Dedicated CTWA webhook
WHATSAPP_AD_VERIFY_TOKEN=""
WHATSAPP_AD_APP_SECRET=""
WHATSAPP_AD_ACCESS_TOKEN=""
WHATSAPP_AD_BUSINESS_ACCOUNT_ID=""
WHATSAPP_AD_API_VERSION="v26.0"

# Token with ads_read permission, used only to resolve campaign/ad names
META_MARKETING_ACCESS_TOKEN=""

# Keep CTWA chats visible in Communication > WhatsApp (default true)
WHATSAPP_AD_MIRROR_INBOX="true"
```

Fallbacks:

- `WHATSAPP_AD_VERIFY_TOKEN` → `WHATSAPP_VERIFY_TOKEN` → existing WhatsApp config
- `WHATSAPP_AD_APP_SECRET` → `META_APP_SECRET` → existing Meta config
- `WHATSAPP_AD_ACCESS_TOKEN` → `WHATSAPP_API_TOKEN` / `META_ACCESS_TOKEN`
- `WHATSAPP_AD_BUSINESS_ACCOUNT_ID` → `WHATSAPP_BUSINESS_ACCOUNT_ID`
- `WHATSAPP_AD_API_VERSION` defaults to the current `v26.0`; set it explicitly
  only when Meta releases a newer version

Tokens and secrets are read server-side only. No API response exposes them.

**Signature verification is mandatory.** If no app secret is configured the
webhook fails closed with HTTP `503`; invalid or missing signatures return
`403`. This prevents unsigned events from creating leads.

### 3.2 Database migration

Run once in the backend environment:

```powershell
backend\venv\Scripts\python.exe backend\migrations\apply_whatsapp_ad_leads_migration.py
```

The application also creates the new tables at startup through the existing
additive `Base.metadata.create_all` path. The migration additionally adds the
new metadata columns if an earlier build of the table already exists.

### 3.3 Meta onboarding path

Choose the onboarding path **before** changing any number or account.

#### Option A — dedicated Cloud API number (works with the current code)

Use this when the existing WhatsApp Business App number must stay untouched.
The CRM captures leads from a separate number used by the ads.

1. Reuse the existing Meta Business app (the one already used for Meta Instant
   Forms) or create a new Business-type app at
   [developers.facebook.com/apps](https://developers.facebook.com/apps).
2. Add the **WhatsApp** product and open **WhatsApp > API Setup**.
3. Create or connect a WhatsApp Business Account (WABA / Messaging account).
   Add a phone number that is **not** currently active on WhatsApp, verify it,
   and note the WABA ID and the business phone number ID.
4. In **Business Settings > Users > System users**, create an admin system
   user and assign:
   - the Meta app (Manage app / Full control)
   - the WhatsApp account
   - the Messaging account
5. Generate a system-user token with:
   - `business_management`
   - `whatsapp_business_management`
   - `whatsapp_business_messaging`
   - `ads_read` (only needed for campaign/ad name resolution)
6. Open **App settings > Basic** and copy the **App secret**. The existing
   `META_APP_SECRET` can be reused for the new webhook.
7. Continue with the webhook configuration in section 3.4.

If the app is only used by your own business, standard access is normally
enough. If you will onboard other businesses, Meta requires App Review and
advanced access for the WhatsApp permissions.

#### Option B — coexistence with the existing WhatsApp Business App number

This keeps the number working in the WhatsApp Business App while Cloud API
receives the same messages. It is **not available through a normal App
Dashboard toggle** and is not implemented in this repository yet.

Official requirements:

- WhatsApp Business App version **2.24.17+**
- You are a Meta **Tech Provider or Solution Partner**
- Embedded Signup **v4 or v5** (v2/v3 are retired)
- Session logging enabled
- Webhook callback able to process:
  `account_update`, `history`, `smb_app_state_sync`,
  `smb_message_echoes`, and `messages`

The flow must:

1. Create a Facebook Login for Business configuration and allowed HTTPS
   domains.
2. Launch Embedded Signup with
   `featureType: "whatsapp_business_app_onboarding"` (v4) or the equivalent
   v5 configuration.
3. Capture `waba_id`, `phone_number_id`, and the exchangeable token code from
   the session event. The code expires after **30 seconds**, so exchange it
   server-side immediately.
4. Onboard the customer, **skip phone-number registration** (the number is
   already registered), and subscribe the app to the customer's webhook.
5. Synchronize contacts and chat history within **24 hours**, then process
   `smb_message_echoes` for messages sent from the Business App.

The current CRM does not contain the Embedded Signup UI, token exchange,
webhook subscription, or history/echo synchronization. Those are additional
development work. If you are not a Tech Provider/Solution Partner, use
Option A; do not attempt coexistence through WhatsApp Web, QR automation, or
unofficial APIs.

**Check Tech Provider status before building anything:**

1. Open **App Dashboard > Use cases > Customize > WhatsApp** and select
   **Tech Provider onboarding**.
2. Open **App Review > Permissions and Features** and confirm **Advanced
   access** for `whatsapp_business_messaging` and
   `whatsapp_business_management`.
3. If the onboarding steps are present, the app is not yet a confirmed Tech
   Provider. Meta requires business verification and App Review before the
   Embedded Signup coexistence flow can onboard a real customer.
4. If self-onboarding your own business portfolio is not offered, use a
   Solution Partner or choose Option A.

Coexistence also changes some WhatsApp Business App behavior: companion
devices are unlinked (supported ones can be relinked), disappearing messages
and view-once are disabled, broadcast lists become read-only, group chats are
not synchronized to Cloud API, and Cloud API throughput is fixed at 20
messages per second. Business App messages remain free; Cloud API messages are
billed separately.

#### Create the Click-to-WhatsApp ad

After the number is connected to Cloud API:

1. Link the Facebook Page and WhatsApp number in Meta Business Suite /
   WhatsApp Manager.
2. In Ads Manager create a campaign with an objective that supports
   conversations (`OUTCOME_ENGAGEMENT`, `OUTCOME_LEADS`, `OUTCOME_SALES`, or
   `OUTCOME_TRAFFIC`).
3. At ad-set level set the conversion/destination to **WhatsApp**, select the
   Page and the connected WhatsApp number, and optimize for **Conversations**.
4. Create an image, video, carousel, or slideshow ad with the
   **Send WhatsApp message** call-to-action, then publish it.
5. Use a phone that is not associated with the business to click the ad and
   send the first message.

Meta attaches the `referral` object (including `ctwa_clid`) to that first
inbound message. WhatsApp Status ad placements may omit `ctwa_clid`; the CRM
still creates the lead without it.

If creating ads through the Marketing API instead of Ads Manager, the app also
needs `ads_management`, `pages_manage_ads`, `pages_read_engagement`, and
`pages_show_list`, plus a Page access token. The CRM's resolver only needs
`ads_read`.

### 3.4 Meta webhook configuration

In the Meta App dashboard, subscribe the WhatsApp Business Account to the
`messages` field and set the callback URL to one of:

- `https://<your-domain>/api/webhook/whatsapp` (production nginx already
  proxies `/api/`), or
- `https://<your-domain>/webhook/whatsapp` (only if that path is exposed
  directly; production nginx currently does **not** proxy it)

Use the same value as `WHATSAPP_AD_VERIFY_TOKEN`.

After the callback URL is verified, make sure the app is actually subscribed to
the WABA (this is separate from subscribing to the webhook field):

```bash
curl -X POST \
  "https://graph.facebook.com/v26.0/<WABA_ID>/subscribed_apps" \
  -H "Authorization: Bearer <SYSTEM_USER_TOKEN>"
```

Verify the subscription:

```bash
curl "https://graph.facebook.com/v26.0/<WABA_ID>/subscribed_apps" \
  -H "Authorization: Bearer <SYSTEM_USER_TOKEN>"
```

Set the Meta app to **Live** mode before testing real ad traffic. Dev-mode apps
may not receive all production webhooks, although the dashboard's test-payload
button can still be used during setup.

The verification endpoint accepts:

```
GET /webhook/whatsapp?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...
```

and echoes `hub.challenge` only when the token matches.

The receiver is:

```
POST /webhook/whatsapp
X-Hub-Signature-256: sha256=...
```

Behavior:

- Valid referral message → create/reuse lead, attribution, event.
- Duplicate delivery (`wamid`/event key already seen) → no new lead.
- Same phone taps another ad → existing lead is reused and a re-inquiry is
  registered; a new attribution records the new click.
- Status-only events → ignored for lead creation (optionally mirrored to the
  inbox).
- Missing `ctwa_clid` → lead is still created; attribution is stored without
  the click ID.
- The webhook returns `500` on unexpected processing errors so Meta retries;
  idempotency makes retries safe.

### 3.5 Marketing API resolution

Campaign and ad names are usually absent from webhook payloads. When
`META_MARKETING_ACCESS_TOKEN` has `ads_read`, a background task retries
`PENDING` attributions every 5 minutes:

```
GET https://graph.facebook.com/{version}/{ad_id}?fields=id,name,campaign{id,name}
```

Failures are stored on the attribution and are **not** retried automatically
after the first failure; an authorized user can retry manually from the detail
view (`POST /api/whatsapp-ad-leads/{id}/resolve-attribution`). An attribution
with no name resolution is still a valid captured lead.

---

## 4. CRM API and UI

New sidebar item: **WhatsApp Ad Leads** → `/leads/whatsapp-ads`.

API endpoints (all under `/api`):

| Method | Path | Purpose |
|---|---|---|
| GET | `/whatsapp-ad-leads` | paginated, scoped listing with search and filters |
| GET | `/whatsapp-ad-leads/summary` | total/assigned/unassigned/campaign counters |
| GET | `/whatsapp-ad-leads/filter-options` | campaigns, employees, statuses in scope |
| GET | `/whatsapp-ad-leads/export` | Excel export of the filtered list |
| GET | `/whatsapp-ad-leads/{id}` | detail with lead + raw referral |
| POST | `/whatsapp-ad-leads/{id}/resolve-attribution` | manual campaign/ad retry |

Filters: date range, campaign, assigned employee, lead status, free-text search
(name, phone, message, campaign, ad, ad ID, CTWA click ID). Listing columns:
customer name, phone, first enquiry message, campaign, ad, created date,
assigned employee, status, and a visible **WhatsApp Ads** badge.

Access reuses the existing `leads` permission module and scope rules (admin,
manager/team, own, support-team exclusion). No new permission module or role
changes are introduced.

---

## 5. Coexistence with the WhatsApp Business App

Meta supports using the WhatsApp Business App and the Cloud API on the **same
number** through Coexistence, but it is not a purely local configuration:

- The WhatsApp Business App must be version **2.24.17 or newer**.
- Onboarding must be done through **Embedded Signup** as a Meta **Tech
  Provider / Solution Partner**, with session logging and coexistence webhook
  payload digestion.
- This repository does not contain that onboarding flow and no account or
  number has been migrated.

No number has been disconnected, migrated, or newly created. Before any
account/number change, confirm eligibility and the onboarding path with Meta.
If coexistence is unavailable, the alternatives are:

1. Keep the existing number on the Business App and use a **separate Cloud API
   number** for ad leads.
2. Migrate the existing number to the Cloud API (disruptive; requires explicit
   approval and a cutover plan).

---

## 6. Tests and verification

Automated tests:

```powershell
backend\venv\Scripts\python.exe -W ignore -m unittest backend.tests.test_whatsapp_ad_leads -v
```

Covered: verification challenge, signature rejection/fail-closed, CTWA lead
creation, duplicate delivery, duplicate click ID, re-inquiry, existing-lead
reuse, status-only/no-referral events, missing `ctwa_clid`, assignment config,
role scoping, Meta Instant Form isolation, detail, summary, filter options, and
Excel export.

Regression suites used alongside it:

```powershell
backend\venv\Scripts\python.exe -W ignore -m unittest `
  backend.tests.test_leads_pagination `
  backend.tests.test_duplicate_lead_prevention `
  backend.tests.test_brochure_download_people `
  backend.tests.test_excel_reinquiry_classification `
  backend.tests.test_followup_visibility `
  backend.tests.test_followup_department_ownership -v
```

Frontend:

```powershell
cd frontend
npm run build
```

### Isolated local verification (completed 2026-11-03)

Ran the real FastAPI app against a temporary SQLite database with WhatsApp
inbox mirroring disabled. Results:

- Webhook verification challenge returned `200` with the expected challenge.
- A correctly signed CTWA POST created one lead with source `WHATSAPP_ADS`.
- Replaying the same signed payload returned one `duplicate` and created no
  additional lead, attribution, or event.
- A second ad click from the same phone reused the lead and registered a
  re-inquiry (`total_enquiries = 2`) with its own attribution.
- Listing, summary, filter options, detail, and Excel export all returned
  `200`; the detail response contained the raw referral data.
- Database counts after the run: 1 lead, 2 lead enquiries, 2 attributions,
  2 processed webhook events.
- The lead remained unassigned because the fresh test database had no active
  employee matching the assignment configuration; this is expected until
  production eligible roles are configured.

No existing local or production CRM rows were touched. The temporary database
was removed afterwards.

> **Local testing note:** the attribution resolver may call the Marketing API
> if `META_MARKETING_ACCESS_TOKEN`, `WHATSAPP_AD_ACCESS_TOKEN`, or
> `META_ACCESS_TOKEN` is present in the environment. Those calls are read-only
> GET requests, but use a dedicated test token or disable the resolver when
> testing with fake ad IDs.

### Live end-to-end checklist (not yet executed)

1. Approve the Meta/WhatsApp account and webhook changes.
2. Configure `WHATSAPP_AD_APP_SECRET`, verify token, and callback URL.
3. Confirm the WABA is subscribed to `messages`.
4. Run the migration and restart the backend.
5. Click a test CTWA ad and send the first message.
6. Confirm the lead appears in **WhatsApp Ad Leads** with a **WhatsApp Ads**
   badge and, where available, ad/campaign attribution.
7. Confirm the same delivery does not create a second lead.
8. Confirm the chat also appears in the existing WhatsApp inbox if mirroring
   is enabled.

The integration must not be described as live-complete until step 6 has
actually been observed with a real enquiry.

---

## 7. Known limitations

- Campaign/ad names require `ads_read`; until then they remain `NULL` and the
  lead is still usable.
- The resolver intentionally retries only `PENDING` rows; `FAILED` rows need a
  manual retry.
- Immediate assignment honors the existing enabled flag, working hours,
  eligible roles, and assignment method, but does not wait for
  `waiting_time_minutes`. Production `eligible_roles` may need to include the
  actual sales roles.
- `/webhook/whatsapp` is only directly reachable on the backend port unless
  nginx is changed; use `/api/webhook/whatsapp` with the current proxy.
- Coexistence onboarding is not implemented in this repository and requires
  Meta approval/Tech Provider access.
