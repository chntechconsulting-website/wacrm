# Meta App Review Submission Pack

Paste-ready answers for the three sections still marked incomplete:

- **Allowed usage**
- **Data handling**
- **Reviewer instructions**

App: **WA!CRM** (`https://www.wapluscrm.in`)
Last updated: 2026-11-04

> Replace every `<...>` placeholder before submitting. Do not submit with
> placeholder credentials.

---

## 0. What is actually being reviewed

| Item | Status |
|---|---|
| Business verification | Approved |
| App settings (icon, category, privacy URL) | Complete |
| Allowed usage | To fill |
| Data handling | To fill |
| Reviewer instructions | To fill |
| Screen recording: `whatsapp_business_messaging` | To record |
| Screen recording: `whatsapp_business_management` | To record via `/settings/whatsapp-connection` |

The permissions power different parts of the CRM:

- `whatsapp_business_messaging` — the shared WhatsApp inbox where agents read and
  reply to customer messages.
- `whatsapp_business_management` — connecting and managing the business's own
  WhatsApp Business Account (WABA), phone numbers, and message templates.
- `business_management` — reading the business portfolio and WABA assets the
  owner selects during Embedded Signup. Request it only if the Meta form lists
  it for this app.

---

## 1. Allowed usage

Paste the matching text into the description box for each permission. If Meta
shows a use-case selector, choose **Manage your WhatsApp Business Account** for
management and **Send and receive messages** for messaging.

### 1.1 `whatsapp_business_messaging`

```
WA!CRM is a multi-tenant CRM used by businesses to manage their own customer
conversations. We use whatsapp_business_messaging only on behalf of the business
that owns the connected WhatsApp Business Account.

Specifically, we:
- receive inbound customer messages, media metadata, contact profile names,
  timestamps, and delivery/read statuses through the Meta webhook;
- store each message against the matching lead and conversation so authorized
  agents can see the full history in one inbox;
- send agent replies (text, image, document, or approved template) from the CRM;
- send approved message templates for follow-ups to customers who have messaged
  the business or opted in;
- capture Click-to-WhatsApp referral data (ctwa_clid, ad/source IDs, headline)
  to attribute an inbound conversation to the ad that generated it.

We do not send unsolicited or bulk messages, do not scrape WhatsApp, do not use
WhatsApp Web automation, and do not message people who have not contacted the
business or opted in.
```

### 1.2 `whatsapp_business_management`

```
WA!CRM lets a business connect its own WhatsApp Business Account (WABA) and manage
it from the CRM. We use whatsapp_business_management only after the account owner
authorizes the connection through Meta Embedded Signup.

Specifically, we:
- read the WABA ID and phone number details for the account the business connected;
- onboard an existing WhatsApp Business App number through official Meta
  Embedded Signup coexistence, without disconnecting the Business App;
- subscribe our app to that WABA so message and account webhooks are delivered;
- request the business's one-time contacts and chat-history synchronization and
  mirror messages sent from the Business App into the CRM inbox;
- list, create, and manage the message templates the business uses for replies
  and follow-ups;
- check the connection, verification, and quality status of the business's number;
- store the returned business token server-side so the connection keeps working.

We only act on accounts that the business has explicitly connected. We do not
manage, modify, or message from accounts we do not own or have authorization for.
```

### 1.3 `business_management`

```
WA!CRM uses business_management only after a business owner authorizes the
connection through Meta Embedded Signup. We use it to:
- read the business portfolio and WhatsApp Business Account assets the owner
  selected during Embedded Signup;
- verify that the selected phone number belongs to that WABA;
- subscribe our app to the WABA so message and account webhooks are delivered;
- read phone number, verification, quality, and message-template status;
- create and manage the message templates the business uses for replies and
  follow-ups.

We do not access, modify, or manage any business or asset that has not been
explicitly connected. We do not use business_management for advertising,
audience building, or resale.
```

> If Embedded Signup is not built yet, do **not** submit the management
> description above until the flow exists. See section 5.

---

## 2. Data handling

Answer the questionnaire with the text below. Wording is deliberately factual;
adjust only if your hosting or retention actually differs.

### 2.1 What platform data does the app access?

```
- WhatsApp messages, media metadata, timestamps, delivery/read statuses, and
  the customer's WhatsApp ID and profile name.
- WhatsApp Business App contacts and chat history that the business authorizes
  us to synchronize during coexistence onboarding.
- WhatsApp Business Account ID, phone number ID, display phone number, template
  definitions, and connection/quality status.
- Click-to-WhatsApp referral data: ctwa_clid, source type, source ID, source URL,
  headline, and ad/campaign identifiers when Meta returns them.
- Facebook Page lead form data (name, phone, email, and form answers) for the
  existing Meta Instant Form integration.
```

### 2.2 Why is the data used?

```
To provide the CRM features the business has asked for: a shared WhatsApp inbox,
lead and enquiry management, assignment and follow-up workflows, and reporting on
the business's own leads and ad campaigns. Data is used only for the business that
owns the connected account.
```

### 2.3 Is the data used for advertising or audience building?

```
No. We do not use Meta platform data to target ads, build advertising audiences,
or resell data. Click-to-WhatsApp identifiers are stored only to attribute an
inbound conversation to the ad that generated it, for the business's own
reporting.
```

### 2.4 Is the data shared with third parties?

```
We do not sell, rent, or trade Meta platform data. Data is processed only by
infrastructure providers needed to run the service (application hosting, managed
database, and telephony where the business enables calling), under contract. Each
business's data is isolated from other tenants. Data may be disclosed only when
required by law.
```

### 2.5 How is the data stored and protected?

```
Data is transmitted over TLS. Access is controlled by role-based permissions, so
employees only see the leads and conversations assigned to them or their team.
WhatsApp and Meta access tokens are stored server-side and are never returned to
the browser or exposed in API responses. Access to production systems is limited
to authorized administrators and audit-logged.
```

### 2.6 How long is data retained?

```
Customer records, messages, and audit logs are retained while the business's
subscription is active, and afterwards only as long as required by applicable tax,
accounting, or legal obligations. The business can request export or deletion at
any time.
```

### 2.7 How can people request deletion?

```
Through the public data deletion page at
https://www.wapluscrm.in/data-deletion, or by emailing
privacy@chntechnologies.com with the subject "Data Deletion Request". We identify
the record from the phone number or email submitted, permanently delete the
contact record and associated messages/call logs within 48 hours, and confirm by
email.
```

### 2.8 Who can access platform data inside the app?

```
Only authorized employees of the business that owns the connected account, scoped
by role-based access control. Sales staff see their own assigned leads; managers
see their team; administrators see the business's records. Every access is tied to
an authenticated CRM user.
```

---

## 3. Reviewer instructions

Paste the text below into **Reviewer instructions**. Replace the placeholders.

```
App: WA!CRM
Public URL: https://www.wapluscrm.in
Login URL: https://www.wapluscrm.in/login

Reviewer account
  Username/email: metareview@chntechnologies.com
  Password: <paste the current reviewer password from the secure handoff>
  Role: META_REVIEWER (least privilege)

The account is a dedicated reviewer account on our production CRM. It can only
open Communication > WhatsApp and Settings > WhatsApp Connection. It cannot
open leads, customers, reports, billing, users, roles, the admin panel, or any
other settings. It only sees the test WhatsApp conversation assigned to it.
No real customer data is exposed.

Test setup
  - Connected WhatsApp Business Account: <WABA display name> (<WABA ID>)
  - Test WhatsApp number: <number with country code>
  - A test conversation with this number is already visible under
    Communication > WhatsApp.

Test whatsapp_business_messaging
  1. Open https://www.wapluscrm.in/login and sign in with the reviewer account.
  2. In the left sidebar open Communication > WhatsApp.
  3. Select the test conversation.
  4. Type a message in the composer and click Send.
     Expected: the message appears in the thread with a timestamp and is
     delivered through the WhatsApp Cloud API.
  5. Change the composer type to Template, select "hello_world", and send.
     Expected: the approved template is delivered, demonstrating messaging
     outside the 24-hour customer service window.
  6. Optional: reply from the test phone. The inbound message appears in the CRM
     within a few seconds.

Test whatsapp_business_management
  1. Sign in with the same reviewer account.
  2. Open Settings > WhatsApp Connection.
     Expected: the connected WABA, phone number ID, and webhook status are shown.
     The reviewer account is intentionally blocked from onboarding, re-reading,
     and sync actions.
  3. Create a message template named "review_test_<timestamp>" with category
     UTILITY and one body parameter.
     Expected: the template is created through the WhatsApp Business Management
     API and appears in the template list.
  4. Open the template list and confirm the new template is present with status
     PENDING or APPROVED.

Notes
  - Tokens are stored server-side and are never displayed in the UI.
  - The app does not use WhatsApp Web automation or unofficial providers.
  - Contact for review questions: privacy@chntechnologies.com
```

The template-management screen exists at **Settings → WhatsApp Connection**
and is restricted to the `whatsapp_connection` permission. The reviewer role
has view + template-create only; onboarding, re-read, and sync require the
`edit` action, which the reviewer does not have. Use the coexistence Embedded
Signup flow with an internal test operator account for the management
recording. After onboarding, the test business must add a payment method in
WhatsApp Manager before Cloud API messaging is fully enabled.

### 3.1 Reviewer account setup

1. Deploy the code that adds the `META_REVIEWER` role.
2. Confirm the role **Meta App Reviewer (limited)** exists under Users & Roles.
3. Create a login in the **Administration** department with that role.
4. Link the login to an Employee record; the WhatsApp inbox scopes the reviewer
   to conversations and leads assigned to that Employee.
5. Assign the seeded test lead and test WhatsApp conversation to the reviewer's
   Employee record.
6. Sign in as the reviewer and confirm the sidebar shows only **WhatsApp** and
   **WhatsApp Connection**. Direct URLs to leads, customers, reports, billing,
   users, admin, or settings must be denied.

The backend reviewer allowlist is enforced independently of the permission
matrix in `backend/services/reviewer_access.py`. Even if the role is edited by
mistake, the reviewer can only call the login, WhatsApp inbox, and connection
status/template endpoints.

---

## 4. Screen recordings

Meta rejects a permission when its recording is missing. Record two separate
videos, each narrated or with on-screen captions.

General rules:

- Show the browser address bar (`https://www.wapluscrm.in/...`).
- Start logged out, then log in, so the reviewer sees the entry point.
- Keep it continuous; do not cut out failed steps.
- 2–4 minutes each, 1080p, MP4 or MOV.
- Show the actual result, not just the button click.

### Video A — `whatsapp_business_messaging`

1. Open `https://www.wapluscrm.in/login`, sign in.
2. Show **Communication → WhatsApp** and the conversation list.
3. Open the test conversation and show the existing inbound message.
4. Send a text reply. Show it appear in the thread with a timestamp.
5. Send the `hello_world` template. Show the template bubble.
6. Show the same message arriving on the test phone.
7. Optionally show the delivery/read status updating in the CRM.

### Video B — `whatsapp_business_management`

Option A (fast, no new UI):

1. Open Graph API Explorer with the app and a token that has
   `whatsapp_business_management`.
2. `GET /v26.0/<WABA_ID>/phone_numbers` — show the number returned.
3. `POST /v26.0/<WABA_ID>/message_templates` with a simple UTILITY template —
   show the created template ID.
4. `GET /v26.0/<WABA_ID>/message_templates` — show the new template in the list.
5. `GET /v26.0/<WABA_ID>/subscribed_apps` — show the app subscription.

Option B (safer for Tech Provider, requires the coexistence module):

1. Sign in with the internal test operator account used for onboarding
   (not the read-only reviewer account).
2. Open **Settings → WhatsApp Connection**.
3. Launch Embedded Signup and complete it with a test business account.
4. Show the returned WABA ID and phone number ID stored on the page.
5. Show the app subscription and webhook fields.
6. Create a template from the CRM and show it in the list.

Use Option A only if you accept the rejection risk. Tech Provider review expects
the onboarding flow, so Option B is the stronger submission.

---

## 5. Blockers to settle before submitting

### 5.1 `whatsapp_business_management` review path

The CRM now has a permission-restricted WABA connection page at
`/settings/whatsapp-connection`. It provides:

- Facebook Login for Business Embedded Signup (v4/v5);
- `WA_EMBEDDED_SIGNUP` session logging;
- one-time code exchange and WABA ownership verification;
- encrypted business token storage;
- WABA subscription and webhook-field visibility;
- contacts/history sync requests and progress;
- template list/create;
- recent coexistence event diagnostics.

Record the management video with **Option B** in section 4. Do not use the
Meta-hosted Embedded Signup link for the production number; the custom JS SDK
flow is required for the exchangeable code and session logs.

The module is hard-locked behind `WHATSAPP_COEXISTENCE_ENABLED=true`. For the
recording, use a test business/number, not **7547900900**.

The app ID shown on **Settings → WhatsApp Connection** must be the Meta app that
owns the Facebook Login for Business configuration ID. If the coexistence app is
different from the legacy `META_APP_ID`, set **both**
`WHATSAPP_COEXISTENCE_APP_ID` and `WHATSAPP_COEXISTENCE_APP_SECRET` to that app.
The backend deliberately does not reuse `META_APP_SECRET` across different app
IDs, because Meta rejects the exchange with an OAuth signature error.

Configuration ownership:

- Production WhatsApp app: **Wacrmwap** (`2041712130118952`), using Facebook
  Login for Business config **2372647743564644**. Confirm the configuration
  appears under this app in **Facebook Login for Business → Configurations**;
  the ID is public but cannot be moved between apps.
- Test/staging app: **Wacrmleadpage** (`1158185796552320`) owns config
  **1698501728618095**.
- The legacy lead-form app **1797499357941817** ("wa crm lead integration")
  remains the `META_APP_ID` for Facebook Instant Form capture. Set
  `WHATSAPP_COEXISTENCE_APP_ID=2041712130118952` and
  `WHATSAPP_COEXISTENCE_APP_SECRET` to the Wacrmwap app secret; do not reuse the
  legacy secret.
- The shared webhook accepts signatures from both configured secrets, so
  Instant Form and coexistence deliveries continue to work during the
  transition.

### 5.2 Reviewer account setup

Create a dedicated CRM user before submitting. The `META_REVIEWER` role is
already seeded at backend startup; it can only open **Communication → WhatsApp**
and **Settings → WhatsApp Connection** and is hard-blocked by the backend
allowlist in `backend/services/reviewer_access.py`.

Recommended: create the account and the seeded test conversation with the
provisioning script on the production host:

```bash
cd /path/to/wacrm/backend
printf '%s\n' 'USE-A-UNIQUE-STRONG-PASSWORD' | \
  ./venv/bin/python migrations/provision_meta_reviewer.py \
    --username meta.reviewer \
    --email approot@wapluscrm.in \
    --password-stdin \
    --name "Meta App Reviewer" \
    --seed-conversation \
    --test-phone 9198XXXXXXXX \
    --test-name "Review test contact"
```

The script never sends a WhatsApp message, refuses the live number
**7547900900**, never overwrites a real WhatsApp Ads lead, and is safe to run
twice. It prints the reviewer `user_id`, `employee_id`, `conversation_id`, and
`lead_id`; record those in the internal review checklist, not in this file.

Manual alternative:

1. Sign in as an administrator.
2. Open **Users & Roles → Add User**.
3. Choose department **Administration** and role **Meta App Reviewer
   (limited)**, reporting to an active Admin.
4. Confirm the account can log in at `https://www.wapluscrm.in/login` and lands
   directly on **Communication → WhatsApp**.
5. Put the credentials only in the App Review form, not in this repository.

The reviewer's linked Employee record controls the inbox scope. If it has no
Employee record, or no conversation is assigned to it, the inbox is empty.
Assign the seeded test lead and conversation to that Employee.

### 5.3 Test conversation must exist in production

The reviewer needs a visible thread. Before recording:

1. Send a WhatsApp message to the connected test number from a phone you control.
2. Confirm the conversation appears under **Communication → WhatsApp**.
3. Confirm the message is stored and visible after a page reload.

Do not use **7547900900** for this. Use the Meta test number or a separate
personal number.

### 5.4 Placeholder contact emails

`PrivacyPolicyPage.jsx` and `DataDeletionPage.jsx` used `admin@company.com`.
They now use `privacy@chntechnologies.com`, matching the mobile app. The code
change is committed but the frontend still needs deployment. Deploy before
submitting so the public pages and the review answers agree.

### 5.5 Webhook callback

Use one callback URL per app:

```
https://www.wapluscrm.in/api/webhook/whatsapp
```

That endpoint validates the Meta signature, captures Click-to-WhatsApp referral
data, and mirrors the payload into the existing inbox. The older
`/api/whatsapp/webhook` path is for the legacy inbox-only integration. Do not
point the same WABA at two callbacks; Meta only delivers to one.

Subscribe the app to the WABA and to the fields:

- `messages`
- `account_update`
- `history`
- `smb_app_state_sync`
- `smb_message_echoes`

The last four are required for coexistence and are implemented by
`WHATSAPP_COEXISTENCE.md`. They remain inactive until an admin completes
Embedded Signup for a WABA.

---

## 6. Built but not live

The coexistence module exists, but do **not** present the production number as
already onboarded. As of this document:

- Embedded Signup / coexistence onboarding is implemented and disabled by
  default.
- `account_update`, `history`, `smb_app_state_sync`, and `smb_message_echoes`
  handlers are implemented and tested.
- Contacts and chat-history sync tracking exists, including the 24-hour deadline.
- Business App echo mirroring is implemented.
- A WABA/template management screen exists at `/settings/whatsapp-connection`.
- The production number **7547900900** has not been touched.
- No real CTWA enquiry with attribution has been observed yet.
- App Review and Tech Provider approval are still pending.

For the reviewer demo, onboard a dedicated test business/number through the same
flow. Do not describe the production number or production CTWA attribution as
already complete.

---

## 7. Final pre-submit checklist

- [ ] Coexistence migration applied on production
- [ ] Production app **2041712130118952** owns config **2372647743564644**
- [ ] Backend deployed with `WHATSAPP_COEXISTENCE_ENABLED=false` and the Wacrmwap app/secret
- [ ] Frontend deployed with `/settings/whatsapp-connection` and the email fix
- [ ] Test business/number successfully onboarded for the recording
- [ ] Reviewer account created and login tested
- [ ] Reviewer credentials entered in the App Review form only
- [ ] Test conversation visible in production
- [ ] `whatsapp_business_messaging` recording uploaded
- [ ] `whatsapp_business_management` recording uploaded (live Embedded Signup)
- [ ] `business_management` answers ready if Meta lists it for the app
- [ ] Allowed usage text pasted for each requested permission
- [ ] Data handling questionnaire answered
- [ ] Reviewer instructions pasted with real URLs and credentials
- [ ] `privacy@chntechnologies.com` deployed on `/privacy` and `/data-deletion`
- [ ] App Review submitted
- [ ] Tech Provider page shows 2 of 2 after approval
- [ ] Production number 7547900900 onboarded only after explicit approval
