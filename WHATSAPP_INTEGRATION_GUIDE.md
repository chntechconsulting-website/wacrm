# WhatsApp Business Platform Setup & Integration Guide

This guide explains how to connect Meta's official **WhatsApp Business Cloud API** to **WaCRM** so you can send and receive real WhatsApp messages, templates, and media attachments directly inside your CRM.

---

## 📋 Prerequisites

Before starting, make sure you have:
1. A **Meta Developer Account**: Register at [developers.facebook.com](https://developers.facebook.com).
2. A **Meta Business Account** (Facebook Business Manager).
3. A **Phone Number** to use for WhatsApp Business (or use Meta's free Test Number for development).

---

## ⚙️ Step-by-Step Meta Developer Setup

### Step 1: Create a Meta App
1. Go to [developers.facebook.com/apps](https://developers.facebook.com/apps) and click **Create App**.
2. Select **Business** or **Other** as the app type.
3. Name your app (e.g. `WaCRM WhatsApp App`) and select your Meta Business Account.
4. Click **Create App**.

---

### Step 2: Add WhatsApp Product
1. On your App Dashboard, scroll down to **WhatsApp** and click **Set up**.
2. Choose your Meta Business Account or select **Continue**.
3. You will be taken to the **WhatsApp > API Setup** page.

---

### Step 3: Collect your API Credentials

On the **API Setup** page, copy the following values:

1. **Temporary / Permanent Access Token**:
   - Copy the access token shown under *Step 1: Select phone number and text message*.
   - *(For production, generate a permanent System User Token under Business Manager > System Users).*
2. **Phone Number ID**:
   - Copy the string of digits under **Phone number ID** (e.g. `100609346387084`).
3. **WhatsApp Business Account ID**:
   - Copy the string under **WhatsApp Business Account ID** (e.g. `104928374829102`).

---

## 🛠️ Step 4: Update Backend Environment (.env)

Open the `.env` file in your `backend/` folder (or create one if it doesn't exist) and add your Meta WhatsApp credentials:

```env
# Meta WhatsApp Business Cloud API Configuration
WHATSAPP_API_TOKEN=EAAG...YOUR_ACCESS_TOKEN_HERE...
WHATSAPP_PHONE_NUMBER_ID=100609346387084
WHATSAPP_BUSINESS_ACCOUNT_ID=104928374829102
WHATSAPP_VERIFY_TOKEN=wa_crm_verify_token_2026
WHATSAPP_API_VERSION=v20.0
```

> 💡 **Note**: Once saved, restart your FastAPI backend server. The CRM status badge will automatically turn green and show **WhatsApp API Connected**.

---

## 🔔 Step 5: Configure Webhook for Incoming Messages

To receive incoming WhatsApp messages from customers automatically inside the CRM:

1. Go to Meta Developer Dashboard $\rightarrow$ **WhatsApp** $\rightarrow$ **Configuration**.
2. Under **Webhook**, click **Edit**.
3. Fill in:
   - **Callback URL**: `https://your-crm-domain.com/api/whatsapp/webhook`
   - **Verify Token**: `wa_crm_verify_token_2026` *(or whatever value you set in `.env`)*
4. Click **Verify and Save**.
5. Under **Webhook Fields**, click **Manage** and subscribe to **`messages`**.

---

## 📱 How to Use WhatsApp in WaCRM

### 1. Main WhatsApp Inbox
- Navigate to **COMMUNICATION** $\rightarrow$ **WhatsApp** (`/communication/whatsapp`).
- View conversations organized by tabs:
  - **All**: All active conversations.
  - **Unread**: Conversations with pending customer messages.
  - **My Chats**: Conversations assigned to you.
  - **Archived**: Archived conversations.
- Search contacts by name, phone number, or message content.

### 2. WhatsApp Chat Panel in Lead Details
- Go to **LEADS** $\rightarrow$ **All Leads**.
- Click on any Lead to open the **Lead Details Drawer**.
- Click the **WhatsApp Chat** tab.
- Send text messages, choose quick pre-approved templates (`hello_world`, `catalog_inquiry`), or attach Image/Document URLs.

### 3. Automated Lead Timeline Audit Trail
- Every outgoing and incoming WhatsApp message is automatically linked to the Lead's record.
- Message history is logged in the Lead's **Activity Timeline** (`WHATSAPP_SENT`, `WHATSAPP_RECEIVED`).

---

## 🧪 Testing

### Test Outbound Message via cURL

```bash
curl -X POST "http://127.0.0.1:8000/api/whatsapp/send-message" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer YOUR_CRM_JWT_TOKEN" \
     -d '{
           "phone": "+919876543210",
           "message_type": "TEXT",
           "body": "Hello from WaCRM!"
         }'
```
