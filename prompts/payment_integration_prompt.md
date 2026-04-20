# Module: Payment Integration (Moyasar + Subscription & Per-Project Billing)

First read and follow `./prompts/workflow_orchestration.md` as mandatory operating rules.

---

## Overview

Build a complete **Payment & Billing** module that gates project creation behind paid access. The system supports two billing modes:

1. **Monthly Subscription** — 250 USD for 25 projects per month (time-limited)
2. **Per-Project Purchase** — 25 USD per project (no expiry)

Payments are processed through **Moyasar**, a Saudi payment gateway. Follow Moyasar's official documentation strictly: https://docs.moyasar.com/

---

## Business Rules

### Billing Modes

| Mode | Price | Projects | Expiry |
|---|---|---|---|
| Monthly Subscription | 250 USD | 25 | 30 days from purchase |
| Per-Project | 25 USD | 1 | Never expires |

### Access Control

- **Only admins can purchase** — employees cannot access the billing page or make payments.
- **All tenant users are affected** — when the tenant has no quota, no user in that tenant can create projects.

### Quota Consumption Priority

**Always consume subscription quota first, then per-project credits.**

Reason: subscription has a time limit — if not used before expiry, those projects are lost. Per-project credits never expire, so they should be preserved.

```
User creates project:
  1. Active subscription with projects_used < projects_limit?
     → YES: projects_used += 1, create project
  2. project_credits.balance > 0?
     → YES: balance -= 1, create project
  3. Neither?
     → HTTP 402, return specific message (see Messages section below)
```

### Subscription Rules

- A tenant can have **only one active subscription at a time**.
- A new subscription **cannot be purchased until the previous one's expiry date has passed** — even if all 25 projects are used up with days remaining. During that time, the admin can only buy per-project credits.
- When a subscription expires (expires_at < now), its status changes to `expired`. Projects already created are NOT affected — only new project creation is blocked.
- **No cancellation flow** — skip cancellation for now. Will be added later.

### Auto-Renewal

- When a subscription expires, the system attempts to charge the tenant's saved card automatically.
- This requires a background cron job that runs periodically (e.g., every hour or daily).
- **If auto-renewal succeeds**: a new subscription row is created, status `active`, for another 30 days.
- **If auto-renewal fails** (card declined, expired, no saved card): subscription expires immediately. New project creation is blocked. A **warning banner** is displayed at the top of the screen **to admin only** — something like: "Your subscription has expired and auto-renewal failed. Please update your payment method to continue creating projects."
- **No emails** for now — all notifications are in-app only. Email notifications will be added later.
- Auto-renewal is **opt-in** — the admin can toggle it on/off from the billing page.

### Project Creation Gate Messages (Shared Utility)

When a user tries to create a project and has no quota, show a specific message depending on the situation. **Put this logic in a shared service/utility** (e.g., `backend/app/shared/quota.py` or similar) because it will be reused in other places.

| Scenario | Message |
|---|---|
| Active subscription, limit reached, subscription not expired | "You've used all 25 projects in your current subscription. You can purchase additional projects individually until your subscription renews." |
| Subscription expired, no per-project credits | "Your monthly subscription has expired. Please renew your subscription or purchase individual projects to continue." |
| No subscription ever, no per-project credits | "You need an active subscription or purchased project credits to create projects. Visit Billing to get started." |
| Per-project credits used up, no active subscription | "Your purchased project credits have been used. Purchase more projects or subscribe to a monthly plan for better value." |

These messages should be returned from a shared function like `get_quota_status(tenant_id, db)` that returns both whether the user can create a project AND the appropriate message. The frontend can then display this message in a modal or inline alert.

---

## Moyasar Integration — Follow Official Docs

**Documentation**: https://docs.moyasar.com/

### Payment Methods

- **Credit/Debit Cards** — Visa, Mastercard, Mada (via Moyasar embedded form)
- **STC Pay** — Mobile wallet (via Moyasar embedded form)
- **No Apple Pay** for now.

### API Keys

- **Publishable key** (`pk_test_` / `pk_live_`): used on the frontend in the Moyasar form. Safe for browser.
- **Secret key** (`sk_test_` / `sk_live_`): used on the backend only. Never expose to frontend.
- Store keys in environment variables (see Environment Variables section below). Set **placeholders only** — actual keys will be added manually.

### Moyasar Amounts

Moyasar uses the **smallest currency unit** (cents for USD):
- 250 USD = `25000`
- 25 USD = `2500`

### Payment Flow (Step by Step)

This is the exact flow to implement, based on Moyasar's official documentation:

```
STEP 1: Admin chooses plan on Billing page
──────────────────────────────────────────
Admin clicks "Subscribe Monthly (250 USD)" or "Buy 1 Project (25 USD)".

STEP 2: Frontend calls backend — POST /api/billing/payments/initiate
────────────────────────────────────────────────────────────────────
Backend:
  - Validates user is admin
  - For monthly: checks no active subscription exists (or current one is expired)
  - Generates a UUID v4 as given_id (for Moyasar idempotency)
  - Creates a payment_history record:
      { plan, amount, currency: "USD", status: "pending", given_id }
  - Returns: { internal_id, amount, currency, given_id, description }

STEP 3: Frontend renders Moyasar embedded form
───────────────────────────────────────────────
Moyasar.init({
  element: '.mysr-form',
  amount: 25000,   // from backend response (cents)
  currency: 'USD',
  description: 'Monthly Subscription - 25 Projects',
  publishable_api_key: VITE_MOYASAR_PUBLISHABLE_KEY,
  callback_url: 'https://{tenant}.{domain}/billing/verify',
  metadata: {
    internal_id: '47',          // from backend Step 2
    tenant_id: '...',
    plan: 'monthly'
  },
  methods: ['creditcard', 'stcpay'],
  creditcard: {
    save_card: true             // save card for auto-renewal
  },
  on_completed: function(payment) {
    // payment.status is "initiated" at this point (NOT "paid")
    // 3DS redirect happens automatically after this callback
    // No action needed here — Moyasar handles the redirect
  },
  on_failure: function(error) {
    // Show error to user
  }
});

STEP 4: 3DS / OTP verification (handled by Moyasar)
─────────────────────────────────────────────────────
- Mada cards: 3DS always required
- Visa/MC: 3DS usually required
- STC Pay: OTP via STC Pay app
- If no 3DS needed: payment goes straight to "paid"

STEP 5: User redirected to callback_url
────────────────────────────────────────
Browser goes to:
  https://{tenant}.{domain}/billing/verify?id=pay_abc123&status=paid&message=APPROVED

Frontend /billing/verify page:
  - Extracts moyasar payment ID from URL params
  - Calls backend: POST /api/billing/payments/verify
    Body: { moyasar_payment_id: "pay_abc123" }
  - Shows success or failure based on backend response
  - DOES NOT trust URL params — always verifies via backend

STEP 6: Backend verifies with Moyasar (CRITICAL SECURITY STEP)
───────────────────────────────────────────────────────────────
POST /api/billing/payments/verify endpoint:

  1. Call Moyasar API:
     GET https://api.moyasar.com/v1/payments/{moyasar_payment_id}
     Authorization: Basic base64(MOYASAR_SECRET_KEY:)

  2. Moyasar returns payment object with:
     - status, amount, currency, metadata, source (including token if save_card)

  3. Backend verifies ALL of:
     - status === "paid"
     - amount matches expected amount from payment_history record
     - currency === "USD"
     - metadata.internal_id exists in payment_history table

  4. If verification passes:
     - Update payment_history: status → "paid", moyasar_payment_id, paid_at
     - If plan === "monthly":
         Create subscription: { projects_limit: 25, projects_used: 0,
                                starts_at: now, expires_at: now + 30 days,
                                status: "active" }
     - If plan === "per_project":
         Upsert project_credits: balance += 1
     - If source.token exists (save_card was true):
         Save token to payment_tokens table

  5. If verification fails:
     - Update payment_history: status → "failed"
     - Return error to frontend

  6. Return result to frontend with subscription/credits status

STEP 7: Webhook (backup — server-to-server)
────────────────────────────────────────────
Moyasar POSTs to: POST /api/billing/webhooks/moyasar

Configured in Moyasar Dashboard (not in code).

Webhook handler:
  1. Verify secret_token matches configured value
  2. Return 200 IMMEDIATELY (before any processing)
  3. Process asynchronously:
     - Extract metadata.internal_id from payment data
     - Check if payment_history already processed (idempotent)
     - If not yet processed, perform same activation as Step 6
  4. Must be idempotent — same webhook arriving twice must not
     create duplicate subscriptions or double-increment credits

Subscribe to these webhook events in Moyasar Dashboard:
  - payment_paid
  - payment_failed
```

### Auto-Renewal Flow (Server-Side Token Charge)

```
Cron job runs periodically:
  1. Find subscriptions where:
     - status = "active"
     - expires_at <= now
     - tenant has auto_renew enabled

  2. For each, find tenant's active payment token

  3. Call Moyasar API from backend:
     POST https://api.moyasar.com/v1/payments
     Authorization: Basic base64(MOYASAR_SECRET_KEY:)
     {
       "amount": 25000,
       "currency": "USD",
       "description": "Monthly subscription auto-renewal",
       "callback_url": "https://{domain}/billing/verify",
       "source": {
         "type": "token",
         "token": "token_xyz789",
         "3ds": false           // active tokens skip 3DS
       },
       "metadata": {
         "internal_id": "new-payment-history-id",
         "tenant_id": "...",
         "plan": "monthly",
         "type": "auto_renewal"
       }
     }

  4. If response status === "paid":
     - Create new payment_history record (status: "paid")
     - Mark old subscription as "expired"
     - Create new subscription (active, 30 days, auto_renew = true
       — carry forward the flag from the old subscription)

  5. If response status === "failed":
     - Create payment_history record (status: "failed")
     - Mark subscription as "expired"
     - Set a flag on tenant/subscription so the banner is shown

  6. If no saved token exists:
     - Mark subscription as "expired"
     - Set the banner flag
```

### Server-Side Payment Verification

**NEVER trust client-side data.** Always verify with Moyasar using the secret key:

```
GET https://api.moyasar.com/v1/payments/{id}
Authorization: Basic base64(MOYASAR_SECRET_KEY:)
```

Verify: `status`, `amount`, `currency` all match your internal record.

### Webhook Security

- Moyasar sends a `secret_token` in the webhook payload.
- This token is configured in the Moyasar Dashboard.
- Store it in your backend environment variable: `MOYASAR_WEBHOOK_SECRET`.
- Compare the incoming `secret_token` against your stored value. Reject mismatches.
- Return HTTP 200 immediately before processing. Moyasar retries up to 6 times if you don't.

---

## Database Design

### Table: `subscriptions`

Tracks monthly subscription plans per tenant.

```sql
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    amount_paid INTEGER NOT NULL,           -- in cents (25000 = 250 USD)
    projects_limit INTEGER NOT NULL,        -- 25
    projects_used INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
                                            -- active | expired
    auto_renew BOOLEAN NOT NULL DEFAULT false,
    starts_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    moyasar_payment_id VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_subscriptions_tenant ON subscriptions (tenant_id);
CREATE INDEX ix_subscriptions_tenant_status ON subscriptions (tenant_id, status);

-- RLS
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_policy ON subscriptions
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
CREATE POLICY app_bypass_policy ON subscriptions
    USING (current_setting('app.tenant_id', true) IS NULL);
```

### Table: `project_credits`

One row per tenant. Tracks the balance of purchased per-project credits.

```sql
CREATE TABLE project_credits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) UNIQUE,
    balance INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- RLS
ALTER TABLE project_credits ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_policy ON project_credits
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
CREATE POLICY app_bypass_policy ON project_credits
    USING (current_setting('app.tenant_id', true) IS NULL);
```

### Table: `payment_history`

Audit trail for every payment attempt (successful or failed).

```sql
CREATE TABLE payment_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    user_id UUID NOT NULL REFERENCES users(id),
    plan VARCHAR(20) NOT NULL,              -- monthly | per_project
    amount INTEGER NOT NULL,                -- in cents
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                                            -- pending | paid | failed
    moyasar_payment_id VARCHAR(100),
    given_id UUID NOT NULL,                 -- Moyasar idempotency key
    payment_type VARCHAR(20) NOT NULL DEFAULT 'manual',
                                            -- manual | auto_renewal
    metadata_json JSONB,
    paid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_payment_history_tenant ON payment_history (tenant_id);
CREATE INDEX ix_payment_history_given_id ON payment_history (given_id);
CREATE INDEX ix_payment_history_moyasar ON payment_history (moyasar_payment_id);

-- RLS
ALTER TABLE payment_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_policy ON payment_history
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
CREATE POLICY app_bypass_policy ON payment_history
    USING (current_setting('app.tenant_id', true) IS NULL);
```

### Table: `payment_tokens`

Saved cards for auto-renewal.

```sql
CREATE TABLE payment_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    user_id UUID NOT NULL REFERENCES users(id),
    moyasar_token VARCHAR(100) NOT NULL,
    card_brand VARCHAR(20),                 -- visa, mada, mastercard
    last_four VARCHAR(4),
    expires_month INTEGER,
    expires_year INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
                                            -- active | expired | revoked
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_payment_tokens_tenant ON payment_tokens (tenant_id);

-- RLS
ALTER TABLE payment_tokens ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_policy ON payment_tokens
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
CREATE POLICY app_bypass_policy ON payment_tokens
    USING (current_setting('app.tenant_id', true) IS NULL);
```

---

## Backend Architecture

### Module Structure

```
backend/app/modules/billing/
├── __init__.py
├── models.py              -- SQLAlchemy models: Subscription, ProjectCredit,
│                             PaymentHistory, PaymentToken
├── schemas.py             -- Pydantic request/response schemas
├── repository.py          -- Database queries for all billing tables
├── service.py             -- Payment initiation, verification, subscription
│                             management, credit management
├── router.py              -- API endpoints (admin-only)
├── webhook_router.py      -- Webhook endpoint (no auth — Moyasar calls this)
├── moyasar_client.py      -- Moyasar API client (verify payment, charge token,
│                             fetch payment details)
└── renewal_service.py     -- Auto-renewal logic (called by cron/background task)
```

**Important:** Keep files focused. If `service.py` grows beyond ~300 lines, split into `payment_service.py`, `subscription_service.py`, `credit_service.py`.

### Shared Quota Utility

```
backend/app/shared/quota.py
```

This file provides:

```python
@dataclass
class QuotaStatus:
    can_create: bool
    source: str | None           # "subscription" | "credits" | None
    message: str                 # User-facing message
    subscription_projects_used: int | None
    subscription_projects_limit: int | None
    subscription_expires_at: datetime | None
    credits_balance: int

async def get_quota_status(tenant_id: UUID, db: AsyncSession) -> QuotaStatus:
    """
    Check if the tenant can create a project.
    Returns quota status with specific message for each scenario.
    Used by project creation endpoint AND by frontend to show status.
    """
```

This function is called from:
1. `ProjectService.create_project()` — to gate project creation
2. `GET /api/billing/quota` — so frontend can display remaining projects and appropriate messages
3. Any future place that needs to check project quota

### API Endpoints

All billing endpoints are under `/api/billing/` with `require_role("admin")` except where noted.

#### Quota (accessible to all authenticated users)

```
GET /api/billing/quota
  - Returns QuotaStatus for the current tenant
  - Accessible to admin AND employee (they need to see remaining projects)
  - Response: {
      can_create: bool,
      source: "subscription" | "credits" | null,
      message: str,
      subscription: {
        status: "active" | "expired" | null,
        projects_used: int,
        projects_limit: int,
        expires_at: datetime,
        auto_renew: bool
      } | null,
      credits_balance: int
    }
```

#### Payment Initiation (admin only)

```
POST /api/billing/payments/initiate
  - Body: { plan: "monthly" | "per_project" }
  - Validates:
    - User is admin
    - For monthly: no active subscription (not expired)
    - Amount is determined server-side (not from frontend)
  - Creates payment_history record with status "pending"
  - Returns: { internal_id, amount, currency, given_id, description }
```

#### Payment Verification (admin only)

```
POST /api/billing/payments/verify
  - Body: { moyasar_payment_id: str }
  - Calls Moyasar API to verify payment
  - Verifies status, amount, currency against internal record
  - Activates subscription or increments credits
  - Saves card token if present
  - Returns: { success: bool, message: str, quota: QuotaStatus }
```

#### Payment History (admin only)

```
GET /api/billing/payments
  - Paginated list of all payment attempts for the tenant
  - Filterable by: status, plan, date range
  - Response: paginated list of PaymentHistoryResponse
```

#### Subscription Management (admin only)

```
GET /api/billing/subscription
  - Returns current/latest subscription details (or null)

PATCH /api/billing/subscription/auto-renew
  - Body: { enabled: bool }
  - Toggles auto-renewal on the active subscription
```

#### Saved Cards (admin only)

```
GET /api/billing/cards
  - Returns list of saved payment tokens (masked card info)

DELETE /api/billing/cards/{token_id}
  - Revokes a saved card token
  - Also calls Moyasar DELETE /v1/tokens/{token} to delete remotely
```

#### Webhook (NO AUTH — Moyasar calls this)

```
POST /api/billing/webhooks/moyasar
  - No JWT auth (Moyasar can't authenticate as a user)
  - Verify secret_token from payload against MOYASAR_WEBHOOK_SECRET env var
  - Return 200 immediately
  - Process payment asynchronously (same logic as verify endpoint)
  - Must be idempotent
  - Register this router WITHOUT tenant/auth dependencies
  - IMPORTANT: This endpoint has no tenant context from middleware.
    Use get_worker_db(tenant_id) after extracting tenant_id from
    the payment metadata, or use the plain get_db() session which
    bypasses RLS via the app_bypass_policy (current_setting is NULL).
```

### Moyasar API Client

```
backend/app/modules/billing/moyasar_client.py
```

Encapsulates all Moyasar API calls:

```python
class MoyasarClient:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.base_url = "https://api.moyasar.com/v1"

    async def fetch_payment(self, payment_id: str) -> dict:
        """GET /v1/payments/{id} — verify payment status"""

    async def charge_token(self, token: str, amount: int, currency: str,
                           callback_url: str, metadata: dict) -> dict:
        """POST /v1/payments — charge saved card for auto-renewal"""

    async def fetch_token(self, token_id: str) -> dict:
        """GET /v1/tokens/{id} — get card info"""

    async def delete_token(self, token_id: str) -> None:
        """DELETE /v1/tokens/{id} — revoke saved card"""
```

Use `httpx.AsyncClient` with Basic Auth (secret key as username, empty password).

### Auto-Renewal Background Task

```
backend/app/modules/billing/renewal_service.py
```

This service:
1. Queries subscriptions where `status = "active"` and `expires_at <= now()`
2. For each, checks if `auto_renew = true`
3. Finds the tenant's active payment token
4. Charges via `MoyasarClient.charge_token()`
5. On success: creates new subscription, marks old as expired
6. On failure: marks subscription as expired, logs failure

**How to trigger:** Use **system cron inside the Docker container**. Add cron to the backend Dockerfile. The cron daemon runs alongside the FastAPI process and calls a standalone management script every hour:

```
0 * * * *  cd /app && python -m app.modules.billing.cron_renewal 2>&1 | logger -t renewal
```

This is the professional, production-proven approach. Do NOT use `asyncio.sleep()` loops — they die with the process, miss schedules during restarts, and are unreliable for payment-critical tasks.

Also add a `POST /api/billing/admin/run-renewal` endpoint (super_admin only) as a manual trigger for testing/debugging.

### Modifying Project Creation

**File:** `backend/app/modules/projects/service.py`

Add a quota check at the beginning of `create_project()`:

```python
from app.shared.quota import get_quota_status, consume_quota

async def create_project(self, tenant_id, owner_user_id, data):
    # --- Payment gate ---
    quota = await get_quota_status(tenant_id, self.db)
    if not quota.can_create:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=quota.message,
        )

    # --- Existing project creation logic ---
    ...
    project = await self.repo.create(...)

    # --- Consume quota AFTER successful creation ---
    await consume_quota(tenant_id, quota.source, self.db)

    return project
```

The `consume_quota` function either increments `subscription.projects_used` or decrements `project_credits.balance` based on `quota.source`.

### Admin Banner for Expired Subscription / Failed Renewal

Add a lightweight endpoint or include in the existing `/auth/me` response:

```
GET /api/billing/alerts
  - Returns any active billing alerts for the current tenant
  - Response: { alerts: [{ type: "subscription_expired", message: "..." }] }
  - Accessible to admin only
  - Frontend calls this on app load and shows a top banner if alerts exist
```

Alternatively, include a `billing_alert` field in the `/auth/me` response for admins so no extra API call is needed.

---

## Environment Variables

### Backend — add to `.env.example`, `.env.development`, `.env.production`

```
# Moyasar Payment Gateway
MOYASAR_SECRET_KEY=sk_test_PLACEHOLDER
MOYASAR_WEBHOOK_SECRET=PLACEHOLDER
```

**Set placeholder values only.** Actual keys will be added manually.

Add to `backend/app/config.py` Settings class:

```python
MOYASAR_SECRET_KEY: str = ""
MOYASAR_WEBHOOK_SECRET: str = ""
```

### Frontend — add to `.env.example`, `.env.development`, `.env.production`

```
VITE_MOYASAR_PUBLISHABLE_KEY=pk_test_PLACEHOLDER
```

**Set placeholder value only.** Actual key will be added manually.

Add to frontend config/env if it exists, or access via `import.meta.env.VITE_MOYASAR_PUBLISHABLE_KEY`.

---

## Frontend Architecture

### Files

```
frontend/src/features/billing/
├── api/
│   └── billing.api.ts          -- API calls to backend billing endpoints
├── types/
│   └── index.ts                -- TypeScript interfaces
├── pages/
│   ├── BillingPage.tsx         -- Main billing dashboard
│   └── PaymentVerifyPage.tsx   -- Callback page after Moyasar redirect
├── components/
│   ├── SubscriptionCard.tsx    -- Current subscription status display
│   ├── CreditBalanceCard.tsx   -- Per-project credits display
│   ├── PlanSelector.tsx        -- Choose monthly vs per-project
│   ├── MoyasarPaymentForm.tsx  -- Wrapper for Moyasar.init embedded form
│   ├── PaymentHistoryTable.tsx -- Paginated payment history
│   ├── SavedCardsSection.tsx   -- Manage saved payment cards
│   └── BillingAlert.tsx        -- Top banner for expired sub / failed renewal
└── hooks/
    └── useQuota.ts             -- Hook to fetch and cache quota status
```

### Moyasar Form Integration

Include the Moyasar library. Add to `index.html` or load dynamically:

```html
<script src="https://cdn.moyasar.com/mpf/1.14.0/moyasar.js"></script>
<link rel="stylesheet" href="https://cdn.moyasar.com/mpf/1.14.0/moyasar.css" />
```

Check the latest version from Moyasar docs. If a newer version exists, use that.

The `MoyasarPaymentForm.tsx` component:
- Accepts `amount`, `currency`, `description`, `metadata`, `callbackUrl` as props
- Calls `Moyasar.init()` in a `useEffect`
- Handles `on_completed` and `on_failure` callbacks
- Cleans up on unmount

### Routing

Add to `frontend/src/app/router/index.tsx`:

```tsx
{ path: 'billing', element: <BillingPage /> },
{ path: 'billing/verify', element: <PaymentVerifyPage /> },
```

Both routes inside the protected `AppLayout` wrapper.

### Navigation

Add to `AppLayout.tsx` navigation items:

```tsx
{
  to: '/billing',
  label: 'Billing',
  icon: CreditCard,       // from lucide-react
  roles: ['admin'],        // admin only
}
```

Position: after Settings in the nav order.

### BillingPage Layout

The billing page has these sections:

**1. Subscription Status Card**
- If active: show plan name, projects used/limit (e.g., "18/25 projects used"), expiry date, auto-renew toggle, progress bar
- If expired: show "Expired on {date}", renew button
- If never subscribed: show "No active subscription", subscribe button

**2. Per-Project Credits Card**
- Show current balance (e.g., "3 project credits remaining")
- "Buy Project" button

**3. Plan Selection (shown when buying)**
- Two cards side by side: Monthly (250 USD) vs Per-Project (25 USD)
- Monthly card: "25 projects, valid 30 days, auto-renewable"
- Per-Project card: "1 project, never expires"
- Clicking a card reveals the Moyasar payment form below

**4. Saved Cards Section**
- List of saved cards (brand icon, last 4 digits, expiry)
- Delete button per card
- If no cards: "No saved cards. A card will be saved on your next payment."

**5. Payment History Table**
- Paginated table: Date, Plan, Amount, Status (badge: green for paid, red for failed, yellow for pending)
- Filterable by status

### PaymentVerifyPage

This page is where Moyasar redirects after payment:

1. Extract `id` and `status` from URL query params
2. Call `POST /api/billing/payments/verify` with the moyasar payment ID
3. Show loading spinner while verifying
4. On success: show success message with updated quota, link to billing page
5. On failure: show error message, link to retry

### BillingAlert Component

- Rendered in `AppLayout.tsx` (above the main content area)
- Calls `GET /api/billing/alerts` on mount (or uses data from `/auth/me`)
- If there's an alert (e.g., subscription expired, renewal failed): show a colored banner at the top
- Only shown to admins
- Dismissible per session (but re-appears on next login if issue persists)

### useQuota Hook

```typescript
function useQuota() {
  // Fetches GET /api/billing/quota
  // Returns: { canCreate, source, message, subscription, creditsBalance, isLoading }
  // Used by project creation page to show warning or block
}
```

### Modify Project Creation Page

In `CreateProjectPage.tsx`:
- Call `useQuota()` on mount
- If `canCreate === false`: show the quota message in an alert/modal instead of the creation form
- The message includes context-specific guidance (from the shared utility messages)

---

## UI Design Guidelines

- Follow the existing design system: Tailwind CSS, `Card`, `Button`, `Input`, `Badge` shared components
- Use consistent colors:
  - Active/paid: green (`bg-green-50`, `text-green-700`)
  - Expired/failed: red (`bg-red-50`, `text-red-700`)
  - Pending: amber (`bg-amber-50`, `text-amber-700`)
- Use `lucide-react` icons consistently
- Responsive layout: works on desktop and tablet
- Clean spacing and typography matching the rest of the app

---

## Security Checklist

1. **Amount tampering**: Backend determines the amount based on plan type. Frontend amount is only for display. Verification checks Moyasar's actual charged amount against your DB record.
2. **Webhook spoofing**: Verify `secret_token` in webhook payload against `MOYASAR_WEBHOOK_SECRET`.
3. **Double activation**: Idempotent processing — check `payment_history.status` before activating. If already `"paid"`, skip.
4. **Role enforcement**: All billing endpoints require `admin` role (except quota and webhook).
5. **Tenant isolation**: All queries filter by `tenant_id`. RLS policies enforce this at DB level.
6. **Secret key protection**: `MOYASAR_SECRET_KEY` never sent to frontend. Only used in backend.
7. **Token security**: Saved card tokens stored in DB, never exposed in full to frontend. Only show masked card info (last 4, brand).
8. **Quota race condition**: Use database-level atomic operations for incrementing `projects_used` and decrementing `balance` to prevent concurrent project creation from over-consuming quota. Use `SELECT ... FOR UPDATE` or equivalent.

---

## Alembic Migration

Create a single migration that creates all four tables:
- `subscriptions`
- `project_credits`
- `payment_history`
- `payment_tokens`

With all indexes, constraints, and RLS policies as defined above.

Number the migration as the next sequential number after the latest existing one.

---

## Common Mistakes to Avoid

1. **DO NOT let the frontend determine the payment amount.** Backend sets it based on plan type. Frontend displays it. Verification checks Moyasar's actual amount against your internal record.

2. **DO NOT trust `callback_url` query params.** Always verify with Moyasar API using the secret key.

3. **DO NOT process webhooks synchronously before returning 200.** Return 200 immediately, then process. Moyasar has a retry schedule and will re-send if you don't respond quickly.

4. **DO NOT create duplicate subscriptions** from webhook + callback both succeeding. Use idempotent checks.

5. **DO NOT allow subscription purchase when an active (non-expired) subscription exists**, even if all projects are used.

6. **DO NOT consume per-project credits when subscription has remaining quota.** Always subscription first.

7. **DO NOT expose Moyasar secret key to frontend code.** It goes in backend env only.

8. **DO NOT skip RLS policies** on new tables. Follow the exact same pattern as existing tables.

9. **DO NOT hardcode Moyasar API keys in code.** Use environment variables with placeholders.

10. **DO NOT forget to handle the case where the webhook arrives before the verify endpoint is called** (especially for no-3DS payments). The `payment_history` record with `internal_id` is created in Step 2 before Moyasar even sees the payment, so the record always exists. Use `metadata.internal_id` to find it.

---

## Deliverables

1. **Alembic migration** — create `subscriptions`, `project_credits`, `payment_history`, `payment_tokens` tables with RLS
2. **Backend billing module** — `backend/app/modules/billing/` with all files listed above
3. **Shared quota utility** — `backend/app/shared/quota.py`
4. **Project creation gate** — modify `ProjectService.create_project()` to check quota
5. **Environment variables** — placeholders in `.env.example`, `.env.development`, `.env.production` (backend + frontend), and in `config.py`
6. **Frontend billing feature** — `frontend/src/features/billing/` with all pages, components, hooks, types, API
7. **Frontend routing** — add billing routes to `router/index.tsx`
8. **Frontend navigation** — add Billing nav item to `AppLayout.tsx` (admin only)
9. **Frontend billing alert** — banner in `AppLayout.tsx` for expired subscription
10. **Frontend project creation gate** — modify `CreateProjectPage.tsx` to check quota
11. **Moyasar library** — include script/CSS in `index.html`
12. **Backend router registration** — register billing routers in `main.py`
13. **Auto-renewal** — background task/cron for charging saved cards on expiry

---

## Constraints

- Do NOT modify any existing module logic unless specifically stated (only project creation gets the quota gate)
- Do NOT modify existing database tables (only add new ones)
- Do NOT implement cancellation — will be added later
- Do NOT implement email notifications — will be added later
- Do NOT hardcode API keys — use environment variables with placeholders
- Follow existing module patterns for structure, auth, tenant isolation
- All queries must filter by `tenant_id`
- Frontend must follow existing patterns and use shared UI components

---

## Renewal, Retries, Card Management & Safety Guards

### Cron Job — System Cron (Not asyncio.sleep)

Use Linux system cron inside the backend Docker container. Runs every **1 hour**. The Dockerfile must install cron and start both the cron daemon and the FastAPI app (use `supervisord` or a startup script).

```dockerfile
# In Dockerfile: install cron, copy crontab, start both processes
```

The cron script (`app/modules/billing/cron_renewal.py`) is a standalone script that:
1. Connects to the database
2. Finds subscriptions needing renewal or retry
3. Processes them
4. Exits cleanly

### Retry Schedule (On Failed Renewal)

When auto-renewal fails, do NOT give up after one try. Use a retry schedule:

| Attempt | When | Action |
|---|---|---|
| 1st | Immediately on expiry | Charge saved card |
| 2nd | +6 hours | Retry charge |
| 3rd | +24 hours (1 day after first fail) | Retry charge |
| 4th | +72 hours (3 days after first fail) | Final retry |
| After 4th | — | Stop retrying, mark as permanently failed |

Track retry state in the `subscriptions` table (add columns):
- `renewal_attempts INTEGER DEFAULT 0`
- `next_retry_at TIMESTAMPTZ` — when the cron should try again
- `renewal_failed_at TIMESTAMPTZ` — when first failure happened

The cron job checks: `expires_at <= now() AND auto_renew = true AND (next_retry_at IS NULL OR next_retry_at <= now()) AND renewal_attempts < 4`

Between retries, the subscription is **expired** and projects are **blocked**. The banner tells the admin to update their payment method.

### Payment Method Management

**Only ONE payment method per tenant.** No wallet with multiple cards. Simple.

- `POST /api/billing/cards/update` — replaces the current card entirely
  1. Renders Moyasar form with `save_card: true` and a small verification amount ($0.01 or use Moyasar's token-only flow if available)
  2. On success: new token saved, old token deleted (both in DB and via Moyasar DELETE /v1/tokens API)
  3. On failure: old card remains, show error
  4. **After successful card update: if there is a pending retry (subscription expired, renewal_attempts > 0), immediately trigger a retry charge on the new card.** Don't wait for the next cron cycle.

- Frontend: In the billing page, show the saved card with a "Change Payment Method" button. If renewal has failed, show a prominent warning: "Your payment method needs updating. Please add a valid card to continue your subscription."

### Manual Renewal Option

Admin can click "Renew Now" from the billing page at any time after subscription expires. This triggers a fresh payment (same as buying a new subscription — Moyasar form, full payment flow).

**Critical:** When manual renewal succeeds:
- Cancel any pending retry schedule: set `renewal_attempts = 0`, `next_retry_at = NULL` on the old expired subscription
- The cron job must check `is there already an active subscription?` before charging — if yes, skip

### Safety Guards (CRITICAL — Implement All)

Every layer must protect against double-charging and double-activation:

**Guard 1 — Cron job before charging:**
```
Before attempting any charge:
  → Check: does this tenant already have an active subscription (status="active", expires_at > now)?
  → If YES: skip this tenant entirely, reset retry state. Do NOT charge.
```

**Guard 2 — After successful charge (cron or manual):**
```
Before creating a new subscription:
  → Check AGAIN: does an active subscription already exist?
  → If YES: do NOT create another one. Refund the charge via Moyasar refund API.
  → Log this as a safety-catch event.
```

**Guard 3 — Webhook handler:**
```
When webhook says "payment_paid" for a subscription payment:
  → Check: does this tenant already have an active subscription?
  → If YES: do NOT activate again. If this payment was a duplicate charge, refund it.
  → Show notice: "You already have an active subscription."
```

**Guard 4 — Payment initiation endpoint:**
```
POST /api/billing/payments/initiate with plan="monthly":
  → Check: is there an active subscription (not expired)?
  → If YES: reject with 409 "You already have an active subscription."
```

**Guard 5 — Verify endpoint:**
```
POST /api/billing/payments/verify:
  → After confirming payment is "paid" with Moyasar:
  → Before activating: check if subscription was already activated
    (by webhook that arrived first, or by concurrent request)
  → If already active: skip activation, return success with current status
```

These guards are **non-negotiable**. Payment systems must be defensive at every layer. A customer should never be charged twice for the same subscription period. If any guard catches a double-charge, issue an immediate automatic refund via Moyasar's refund API.

### Notification Rules (In-App Only — No Emails)

Show prominent notices on the billing page and/or as a top banner:

| Condition | Notice |
|---|---|
| Renewal failed (retrying) | "We couldn't charge your card. We'll retry automatically. Update your payment method for immediate restoration." |
| All retries exhausted | "Payment failed after multiple attempts. Please update your payment method or renew manually." |
| Insufficient funds (from Moyasar decline reason) | "Your card was declined due to insufficient funds. Please ensure your card has enough balance or use a different card." |
| Card expired (from Moyasar decline reason) | "Your card has expired. Please add a new payment method." |

Store the Moyasar decline reason (from the payment response `source.message` or `source.response_code`) in `payment_history.metadata_json` so you can show the specific reason to the admin.

### Updated Deliverables for This Section

14. **System cron setup** — Dockerfile changes, crontab, supervisord or startup script
15. **Retry logic** — columns on subscriptions table, retry schedule in cron script
16. **Card update flow** — endpoint, Moyasar form for card replacement, immediate retry after update
17. **Manual renewal** — "Renew Now" button on billing page, cancels pending retries on success
18. **Safety guards** — all 5 guards implemented in cron, webhook, verify, and initiation endpoints
19. **Auto-refund** — if any guard catches a double-charge, refund automatically via Moyasar API
20. **Decline reason display** — store and show specific failure reasons from Moyasar
