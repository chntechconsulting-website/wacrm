# WhatsApp Business App Coexistence (Meta Embedded Signup)

Status: **implemented and disabled by default**. No live WhatsApp number, Meta
asset, webhook, token, or production database has been changed. The existing
WhatsApp Business App number **7547900900 (+91 75479 00900)** must stay untouched
until App Review/Tech Provider approval is complete and the business owner gives
explicit approval for live onboarding.

This module adds official Meta **coexistence** onboarding for an existing
WhatsApp Business App number. It does **not** use WhatsApp Web automation, QR
hacks, scraping, or unofficial providers.

---

## 1. Safety invariants

1. `WHATSAPP_COEXISTENCE_ENABLED` defaults to `false`. The exchange endpoint and
   the Embedded Signup launcher are locked unless it is exactly `true`.
2. A connection row is only created after a business completes Meta Embedded
   Signup and the backend exchanges the one-time code.
3. The backend verifies that the selected phone number belongs to the returned
   WABA before saving the connection.
4. The business token is encrypted at rest with the existing Meta Fernet helper
   and is never returned by an API response or rendered in the frontend.
5. Business App contact sync is stored in `whatsapp_smb_contacts`. It never
   creates, overwrites, or reassigns CRM leads.
6. Business App echoes are mirrored into the existing inbox as outbound
   messages. The CRM never sends anything back for an echo.
7. The coexistence webhook shares `https://www.wapluscrm.in/api/webhook/whatsapp`
   with Click-to-WhatsApp lead capture. Coexistence fields are processed first;
   a coexistence failure must not stop CTWA lead capture.
8. Do not use the Meta-hosted Embedded Signup link with the production number.
   The custom Facebook JS SDK flow is required so the exchangeable code and
   session-log events are available to the backend.

---

## 2. What is implemented

### Backend

| File | Purpose |
|---|---|
| `backend/models/whatsapp_coexistence.py` | Connection, event/idempotency log, and Business App contact tables |
| `backend/integrations/whatsapp_coexistence/config.py` | Safety gate, app/config IDs, callback URL, required webhook fields |
| `backend/integrations/whatsapp_coexistence/service.py` | Code exchange, WABA ownership check, encryption, subscription, sync requests, webhook handlers, templates |
| `backend/integrations/whatsapp_coexistence/router.py` | Admin-only status, session-log, exchange, refresh, sync, templates, events APIs |
| `backend/integrations/whatsapp_coexistence/schemas.py` | Request/response models; the connection response never contains a token |
| `backend/migrations/apply_whatsapp_coexistence_migration.py` | Idempotent additive migration |
| `backend/integrations/whatsapp/config.py` | Prefers the active coexistence token, phone number ID, WABA ID, and API version |
| `backend/integrations/whatsapp_ads/service.py` | Shared signed webhook entry; processes coexistence fields and allows the coexistence WABA |
| `backend/tests/test_whatsapp_coexistence.py` | Isolated tests for the safety gate, webhook fields, dedupe, media-placeholder upgrade, contacts, echoes, account updates, phone-ID resolution, token non-exposure, config preference, and template validation |

### Frontend

| File | Purpose |
|---|---|
| `frontend/src/pages/Settings/WhatsAppConnectionPage.jsx` | Embedded Signup launcher, `WA_EMBEDDED_SIGNUP` listener, session logging, automatic code exchange, connection/sync status, templates, events |
| `frontend/src/pages/Settings/WhatsAppConnectionPage.css` | Page styling |
| `frontend/src/App.jsx` | Admin-only `/settings/whatsapp-connection` route |
| `frontend/src/components/Sidebar/Sidebar.jsx` | Admin sidebar link |
| `frontend/src/pages/Settings/IntegrationsPage.jsx` | WhatsApp card link to the connection page |

### API endpoints

All endpoints require an administrator token.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/whatsapp/coexistence/status` | Safe config, connection, webhook status |
| `POST` | `/api/whatsapp/coexistence/session-log` | Store `WA_EMBEDDED_SIGNUP` events; codes/tokens are redacted |
| `POST` | `/api/whatsapp/coexistence/exchange` | Exchange the one-time code and start onboarding (hard-locked) |
| `POST` | `/api/whatsapp/coexistence/refresh` | Re-read phone number and app subscription from Meta |
| `POST` | `/api/whatsapp/coexistence/sync` | Retry the one-time `contacts` or `history` sync |
| `GET` | `/api/whatsapp/coexistence/templates` | List message templates on the connected WABA |
| `POST` | `/api/whatsapp/coexistence/templates` | Create a template on the connected WABA |
| `GET` | `/api/whatsapp/coexistence/events` | Recent session/webhook events (no raw payloads) |

`POST /exchange` accepts `waba_id` plus an optional `phone_number_id`. When
Meta's session event returns only `waba_id`, the backend resolves the number
with the newly issued token and refuses to continue if the WABA has multiple
ambiguous Business App numbers.

---

## 3. Prerequisites

1. Meta **Business Verification** approved.
2. App Review approval for:
   - `whatsapp_business_messaging`
   - `whatsapp_business_management`
3. Meta **Tech Provider** status (or Solution Partner status).
4. A Meta app with **Facebook Login for Business** and a configuration ID that
   includes WhatsApp Embedded Signup.
5. `https://www.wapluscrm.in/api/webhook/whatsapp` registered as the app callback
   with the fields listed in section 5.
6. The business's WhatsApp Business App version must be **2.24.17 or newer**.
7. Explicit business approval to onboard the live number. Approval must be
   recorded outside this repository before setting the enable flag.

Do not use a Meta test number to claim production readiness. Test numbers cannot
receive real Click-to-WhatsApp ads.

---

## 4. Environment configuration

Add these to `backend/.env` only when the code and approval are ready. Keep
`WHATSAPP_COEXISTENCE_ENABLED=false` until the live onboarding window.

```dotenv
# Hard safety gate. Leave false until explicitly approved.
WHATSAPP_COEXISTENCE_ENABLED="false"

# Facebook Login for Business configuration ID (WhatsApp Embedded Signup).
# Production default: Wacrmwap configuration (app 2041712130118952).
WHATSAPP_COEXISTENCE_CONFIG_ID="2372647743564644"

# Dedicated production WhatsApp app. Set both values together; the backend
# refuses to reuse the legacy META_APP_SECRET for a different app.
WHATSAPP_COEXISTENCE_APP_ID="2041712130118952"
WHATSAPP_COEXISTENCE_APP_SECRET="<Wacrmwap App Secret from Settings -> Basic -> Show>"
WHATSAPP_COEXISTENCE_API_VERSION="v26.0"

# Defaults to <PUBLIC_BASE_URL>/api/webhook/whatsapp.
WHATSAPP_COEXISTENCE_CALLBACK_URL=""

# Meta requires contacts/history to sync within 24 hours.
WHATSAPP_COEXISTENCE_SYNC_DEADLINE_HOURS="24"
```

The app secret and business token never appear in the frontend. The frontend
receives only `enabled`, `configured`, `ready`, the public app ID, the public
configuration ID, API version, callback URL, and warnings.

The Facebook Login for Business configuration ID belongs to exactly one Meta
app. If coexistence uses a dedicated app that differs from the legacy
`META_APP_ID`, set `WHATSAPP_COEXISTENCE_APP_ID` **and**
`WHATSAPP_COEXISTENCE_APP_SECRET` together. The backend intentionally refuses to
pair a coexistence app ID with the legacy app's secret, because Meta rejects that
combination with an OAuth signature error and the failure is otherwise hard to
diagnose.

Known configuration ownership:

| Configuration ID | Owning Meta app |
|---|---|
| `2372647743564644` | `2041712130118952` (**Wacrmwap**, production WhatsApp) |
| `1698501728618095` | `1158185796552320` (**Wacrmleadpage**, test/staging) |

Production must use the Wacrmwap app and configuration together. The status
endpoint reports `configured:false` with an ownership warning when they do not
match, instead of allowing Embedded Signup to fail at Meta's OAuth step. The
configuration ID is public; the app secret is not and must only be set in the
backend environment.

The shared webhook validates `X-Hub-Signature-256` against every configured app
secret, so a delivery signed by the legacy lead-ads app and one signed by a
separate coexistence app are both accepted. A signature that matches neither is
still rejected.

Important: the encrypted token is derived from `SECRET_KEY`. Changing
`SECRET_KEY` makes existing encrypted tokens unreadable. Reconnect the number
through Embedded Signup after a secret rotation.

---

## 5. Meta App Dashboard setup

### 5.1 Facebook Login for Business

1. Open the Meta app.
2. Add the **Facebook Login for Business** product.
3. In its settings, add the production domain and callback URLs used by the CRM
   (`https://www.wapluscrm.in`).
4. Create a configuration for **WhatsApp Embedded Signup** with the permissions
   needed for coexistence:
   - `whatsapp_business_messaging`
   - `whatsapp_business_management`
   - `business_management`
5. Copy the configuration ID into `WHATSAPP_COEXISTENCE_CONFIG_ID`. The
   production app is **Wacrmwap** (`2041712130118952`); confirm the configuration
   shown in **Facebook Login for Business → Configurations** matches
   `2372647743564644` before saving. A configuration ID belongs to exactly one
   app and cannot be moved between apps.

The frontend launches `FB.login` with `config_id`, `response_type=code`,
`override_default_response_type=true`, and:

```js
extras: {
  setup: {},
  featureType: 'whatsapp_business_app_onboarding',
  sessionInfoVersion: '3',
}
```

### 5.2 Webhook

Use one callback URL:

```text
https://www.wapluscrm.in/api/webhook/whatsapp
```

Subscribe to:

- `messages`
- `account_update`
- `history`
- `smb_app_state_sync`
- `smb_message_echoes`

The last four are required for coexistence. Do not point the same WABA at two
different callbacks; Meta delivers to only one.

### 5.3 WABA subscription

The backend subscribes the app to the customer WABA automatically during the
code exchange with `POST /<WABA_ID>/subscribed_apps`. The connection page shows
whether the subscription is confirmed.

---

## 6. Onboarding flow

1. Deploy the backend and frontend with
   `WHATSAPP_COEXISTENCE_ENABLED=false`.
2. Run the additive migration:

   ```powershell
   cd backend
   .\venv\Scripts\python.exe migrations\apply_whatsapp_coexistence_migration.py
   ```

3. Sign in with a user whose role has the `whatsapp_connection` **edit**
   permission (ADMIN by default). The `META_REVIEWER` role is view +
   template-create only and cannot launch onboarding, refresh, or sync.
4. Open **Settings → WhatsApp Connection**.
5. Confirm the page shows all configuration checks as ready.
6. Set `WHATSAPP_COEXISTENCE_ENABLED=true` in `backend/.env` and restart the
   backend. This is the live-onboarding action; only do it after approval.
7. Click **Launch Embedded Signup**.
8. The business logs in with the Facebook account that manages the WhatsApp
   Business App and selects the existing number.
9. Meta posts `WA_EMBEDDED_SIGNUP` session events to the page. The page logs them
   and receives the one-time code from `FB.login`.
10. The backend:
    - exchanges the code for a business token;
    - resolves the phone number ID from the WABA if the session event returned
      only `waba_id`, preferring the number flagged `is_on_biz_app=true` and
      refusing to guess between multiple ambiguous numbers;
    - verifies the phone number belongs to the WABA;
    - encrypts and stores the token;
    - subscribes the app to the WABA;
    - requests the one-time contacts sync;
    - requests the one-time history sync.
    - skips phone registration because the number is already registered with the
      WhatsApp Business App.
11. Watch the **One-time synchronization** panel. Do not close the Business App
    or change the number until the window completes.
12. Once `history_progress` reaches `100`, the status becomes `SYNC_COMPLETE`.
13. Instruct the business owner to open **WhatsApp Manager → Overview →
    Add payment method** and complete Meta billing. Cloud API messaging is not
    fully enabled until this step is done. Meta's help link:
    <https://www.facebook.com/business/help/488291839463771>.

If the 24-hour window closes before sync completes, Meta requires the number to
be offboarded and re-onboarded. Do not delete CRM conversations or messages.

The sequence mirrors Meta's Tech Provider flow. Step 3 of that flow (register
the customer's phone number) does not apply to coexistence; Meta requires you to
skip it because the Business App number is already registered.

---

## 7. Webhook processing

| Field | Handling |
|---|---|
| `history` | Imports history threads and messages into existing conversations; deduplicates by WAMID and chunk fingerprint; upgrades `media_placeholder` rows when Meta sends the follow-up media webhook; updates progress/phase; marks `SYNC_COMPLETE` at 100% |
| `smb_app_state_sync` | Upserts Business App contacts into `whatsapp_smb_contacts`; updates conversation display names; never creates leads |
| `smb_message_echoes` | Mirrors Business App outbound messages as `OUTBOUND` inbox messages; handles revoke/edit; never sends anything back |
| `account_update` | `PARTNER_REMOVED` / `ACCOUNT_OFFBOARDED` mark the connection disconnected; `ACCOUNT_RECONNECTED` restores connected status; resolves the real WABA from `value.waba_info.waba_id` when `entry.id` is the partner business ID |
| `messages` | Continues through the existing WhatsApp inbox and Click-to-WhatsApp lead pipeline |

Event keys make repeated deliveries idempotent. History messages are also
deduplicated by provider message ID, and a content fingerprint prevents a
retried chunk with the same metadata from being skipped or double-counted.

---

## 8. Business App behavior after coexistence

Meta changes some behavior while coexistence is active:

- Companion/linked devices are unlinked.
- Disappearing messages and view-once media are disabled.
- Broadcast lists become read-only.
- Group chats are not synchronized to Cloud API.
- Throughput is fixed at 20 messages per second.
- The Business App and Cloud API can both send one-to-one messages; Business App
  sends arrive in the CRM as echoes.
- Contacts and chat history are synchronized only during onboarding (and for
  new contacts after that); a failed 24-hour window requires re-onboarding.

These are Meta platform rules, not CRM limitations.

---

## 9. Tests and verification

Run the focused suite:

```powershell
cd backend
.\venv\Scripts\python.exe -m unittest tests.test_whatsapp_coexistence -v
```

Expected: **25 tests pass**.

Run the shared regressions:

```powershell
.\venv\Scripts\python.exe -m unittest `
  tests.test_whatsapp_ad_leads `
  tests.test_duplicate_lead_prevention `
  tests.test_followup_department_ownership `
  tests.test_followup_visibility -v
```

Expected: **42 tests pass**.

Frontend:

```powershell
cd frontend
npm run build
```

Covered by the coexistence suite:

- onboarding locked by default;
- missing configuration rejected;
- a different coexistence app requires its own app secret;
- a known configuration ID refuses to run under the wrong Meta app;
- the shared webhook accepts a signature from either configured app secret;
- public config and status never expose secrets;
- session-log codes redacted;
- history import and duplicate suppression;
- media-placeholder history upgraded by the follow-up media webhook;
- contact sync does not create leads;
- contact remove updates state without deleting history;
- Business App echo mirrored once;
- signed webhook routes coexistence fields;
- account disconnect/reconnect;
- `account_update` resolved from `waba_info` when `entry.id` is the partner ID;
- phone number ID resolved when the session event returns only `waba_id`;
- ambiguous phone number resolution refused instead of guessed;
- WhatsApp config prefers the active coexistence connection;
- template validation happens before network calls;
- template creation requires an active connection.

---

## 10. Live-onboarding checklist (after approval only)

- [ ] App Review approved for both WhatsApp permissions
- [ ] Tech Provider status approved
- [ ] Business owner explicitly approved onboarding of **7547900900**
- [ ] Migration applied on production
- [ ] Backend/frontend deployed with the gate still `false`
- [ ] Configuration page shows all checks ready
- [ ] Reviewer/test onboarding previously succeeded on a non-production number
- [ ] Webhook callback and all five fields confirmed in Meta
- [ ] `WHATSAPP_COEXISTENCE_ENABLED=true` set only for the onboarding window
- [ ] Embedded Signup completed by the business owner
- [ ] WABA subscription confirmed
- [ ] Contacts sync requested
- [ ] History sync requested
- [ ] `history_progress` reaches 100% within 24 hours
- [ ] Business owner adds a payment method in WhatsApp Manager
- [ ] Real inbound CTWA test produces a WhatsApp Ad Lead with attribution
- [ ] Business App still sends and receives normally
- [ ] Business App outbound message appears in the CRM inbox as an echo

Do not claim completion until a real CTWA enquiry appears with attribution.

---

## 11. Rollback and offboarding

- Set `WHATSAPP_COEXISTENCE_ENABLED=false` to stop new onboarding immediately.
- Existing connections remain readable; sending uses the stored connection token.
- To offboard, use the official Meta offboarding/management flow for the WABA.
  Do not delete CRM conversations, messages, or leads as part of offboarding.
- If the 24-hour sync window fails, offboard and re-onboard through Embedded
  Signup. Do not attempt a partial manual sync.
- If `SECRET_KEY` is rotated, existing tokens cannot be decrypted. Reconnect the
  number through Embedded Signup before sending again.

---

## 12. Known limitations

- Campaign/ad-name resolution remains part of the WhatsApp Ad Leads module and
  requires `ads_read`.
- Group chats and broadcast lists are not available through Cloud API.
- Message history imports only what Meta returns during onboarding.
- Templates require Meta approval before use outside the 24-hour service window.
- The module does not support Meta-hosted Embedded Signup links for production
  coexistence because they do not give the CRM the exchangeable code and
  session logs it needs.
