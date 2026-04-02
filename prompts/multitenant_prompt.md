# Prompt: FastAPI Multi-Tenant Foundation (Domain-Based) — Single DB, Shared Tables

You are Claude Code acting as a senior SaaS architect and backend engineer.

## Objective
Implement a **domain/subdomain-based multi-tenant foundation** in **FastAPI** using:
- **Single PostgreSQL database**
- **Shared tables** across all tenants (no separate schemas/DBs)
- **Tenant isolation via `tenant_id` scoping** in every query (**RLS optional**, not required for MVP)
- **Exactly 3 roles** (no full RBAC):
  - `super_admin` (platform-level)
  - `admin` (company/tenant-level)
  - `employee` (company/tenant-level)

Tenants are differentiated by **subdomain**:
- **Super Admin app**: `admin.app.com`
- **Tenant apps**: `{tenant_slug}.app.com`

Local development must also use domain-based tenancy (not path-based). Provide dev setup instructions.

---

## Non-negotiable Security Rules
1. **Never rely on the frontend for security.** Enforce authorization in backend.
2. For every **tenant-domain** request:
   - Resolve tenant from `Host` header (subdomain).
   - Validate tenant exists and is `active`.
   - Verify JWT.
   - Ensure JWT `tenant_id` **matches** resolved tenant_id.
3. For every **admin-domain** request (`admin.app.com`):
   - Verify JWT.
   - Ensure role is `super_admin`.
4. For all writes/updates/deletes on tenant-owned tables, SQL must include:
   - `... WHERE id = :id AND tenant_id = :tenant_id`
5. Use **soft delete** for users:
   - `is_active = false`, `deleted_at = now()`
6. Prevent lockout:
   - `admin` cannot deactivate themselves
   - cannot deactivate the last active `admin` within a tenant
7. Passwords:
   - store `password_hash` only (bcrypt/argon2)
   - do not log passwords or tokens
8. Access tokens should be short-lived (e.g., 10–20 min). Refresh tokens optional for MVP.

---

## Tech Stack Assumptions
- FastAPI + Pydantic
- SQLAlchemy 2.0 (or SQLModel) + Alembic migrations
- PostgreSQL
- JWT (HS256/RS256 acceptable)
- Password hashing: bcrypt/argon2
- Email sending via a provider abstraction (SMTP or API), mocked in dev/tests

---

## Tenancy: Host/Subdomain Resolution
### Rules
- If `Host` is exactly `admin.app.com` (or `admin.local` in dev), treat as **platform context** (no tenant).
- Else parse subdomain from host: `{tenant_slug}.app.com`
  - Example: `acme.app.com` → tenant_slug = `acme`
- Look up tenant by slug in DB.
- If tenant not found → 404
- If tenant suspended → 403 (or 423 Locked)

### Deliverable
Implement `TenantResolverMiddleware` (or dependency) that:
- reads `request.headers["host"]`
- extracts subdomain (robustly handles ports like `acme.local:8000`)
- sets `request.state.tenant = { id, slug, status }` when in tenant context
- sets `request.state.is_admin_domain = True/False`

---

## Data Model (Shared Tables)
Create the minimal schema and migrations:

### tenants (companies)
- `id` UUID PK
- `name` text
- `slug` text UNIQUE (used for subdomain)
- `status` enum/text: `active` | `suspended`
- `settings_json` jsonb nullable
- `created_at` timestamptz
- `updated_at` timestamptz

### users
- `id` UUID PK
- `tenant_id` UUID nullable
  - `NULL` for `super_admin` (platform user)
  - non-null for `admin` and `employee`
- `email` text UNIQUE globally for MVP (simple)
- `password_hash` text
- `role` enum/text: `super_admin` | `admin` | `employee`
- `must_change_password` bool default false
- `is_active` bool default true
- `deleted_at` timestamptz nullable
- `created_at` timestamptz
- `updated_at` timestamptz

### audit_logs
- `id` UUID PK
- `tenant_id` UUID nullable (null for platform events)
- `actor_user_id` UUID nullable
- `action` text
- `entity_type` text
- `entity_id` text/uuid
- `metadata_json` jsonb
- `created_at` timestamptz

### Indexes
- `tenants.slug` UNIQUE
- `users.email` UNIQUE
- `users(tenant_id, id)`
- `audit_logs(tenant_id, created_at)`

---

## Authentication (JWT)
### JWT claims
Include:
- `sub` = user_id
- `role` = one of (`super_admin`, `admin`, `employee`)
- `tenant_id` = UUID or null
- `exp` standard expiry

### Auth endpoints
- `POST /auth/login`
  - input: email, password
  - output: access_token (JWT), token_type
  - reject if `is_active=false`
- `POST /auth/change-password`
  - allowed when authenticated
  - if `must_change_password=true`, this endpoint is required before using anything else
- `GET /auth/me`
  - returns user info + resolved tenant context

### Must-change-password enforcement
If `must_change_password=true`, block other endpoints with 403 until password changed (allow only `/auth/me` and `/auth/change-password`).

---

## Authorization (No RBAC, Just Role Guards)
Implement reusable FastAPI dependencies:

- `require_auth()`:
  - verify JWT
  - load minimal user context (id, role, tenant_id)
  - put in `request.state.user`
- `require_admin_domain()`:
  - ensure admin host
- `require_tenant_domain()`:
  - ensure tenant host and tenant resolved
- `require_tenant_match()`:
  - ensure `request.state.user.tenant_id == request.state.tenant.id`
- `require_role(*roles)`:
  - ensure user.role in allowed list

**Examples**
- Super admin routes:
  - `require_auth + require_admin_domain + require_role("super_admin")`
- Tenant admin user-management routes:
  - `require_auth + require_tenant_domain + require_tenant_match + require_role("admin")`
- Normal tenant routes:
  - `require_auth + require_tenant_domain + require_tenant_match + require_role("admin","employee")`

Also enforce tenant scoping inside queries (WHERE tenant_id = ...).

---

## Super Admin Dashboard API (admin domain only)
Prefix: `/admin`

- `GET /admin/tenants` — list companies
- `POST /admin/tenants` — create company + create initial tenant `admin`
  - input: company name, slug, admin_email
  - create tenant (active)
  - create user (role=admin, tenant_id=tenant.id, must_change_password=true, is_active=true)
  - generate either:
    - **one-time setup link** (preferred), OR
    - a temporary password
  - send email to `admin_email` with:
    - login URL `https://{slug}.app.com`
    - setup instructions
- `GET /admin/tenants/{tenant_id}` — details
- `PATCH /admin/tenants/{tenant_id}` — update status/settings
- `GET /admin/audit-logs` — platform logs (optional filters)
- `POST /admin/me/change-password` — super admin changes own password (can reuse /auth/change-password)

**Email rule**
Prefer one-time setup link rather than emailing plaintext password.
If using temp password, force change on first login.

---

## Tenant Admin User Management API (tenant domain only)
Prefix: `/tenant`

- `GET /tenant/users` (admin only)
- `POST /tenant/users/invite` (admin only)
  - input: email, role (default employee; allow admin if you want, but enforce lockout rules)
  - create user with `must_change_password=true`
  - send setup link
- `PATCH /tenant/users/{user_id}` (admin only)
  - update role between `admin` and `employee` within tenant
  - NEVER allow setting `super_admin`
- `POST /tenant/users/{user_id}/deactivate` (admin only)
  - soft delete
  - enforce:
    - cannot deactivate self
    - cannot deactivate last active admin
  - SQL must include tenant filter:
    - `UPDATE users SET is_active=false, deleted_at=now() WHERE id=:user_id AND tenant_id=:tenant_id`

---

## Email Provider Abstraction
Create interface:
- `EmailSender.send(to, subject, body)`

Implement:
- `ConsoleEmailSender` for dev (prints to console)
- stub/placeholder for production provider

Emails must include:
- Tenant URL: `https://{slug}.app.com`
- Setup instructions
- One-time link (preferred)

---

## Local Development — Domain-Based Tenancy
Write a README section and implement host parsing accordingly.

### Approach (recommended): hosts file
Add to hosts file:
- `127.0.0.1 admin.local`
- `127.0.0.1 acme.local`
- `127.0.0.1 beta.local`

Run FastAPI on `:8000`, then use:
- `http://admin.local:8000` (super admin area)
- `http://acme.local:8000` (tenant acme)
- `http://beta.local:8000` (tenant beta)

Tenant slug is `acme` from `acme.local`.

Host parsing must handle stripping ports.

---

## Seeds / Bootstrap
Provide seed script/command that creates:
- super admin:
  - email: `superadmin@app.com`
  - role: `super_admin`
  - tenant_id: null
- tenants:
  - `acme`, `beta`
- tenant admins for each:
  - role: `admin`
  - must_change_password: true
- 2 employees for each tenant

---

## Automated Tests (minimum)
Write tests to prove isolation:
1. Token for tenant `acme` cannot access `beta` domain endpoints (403)
2. Non-super_admin cannot access `admin` domain endpoints (403)
3. Tenant admin can deactivate employee only within same tenant
4. Cannot deactivate the last active admin
5. Suspended tenant blocks access/login (403)

---

## Output / Deliverables
1) Short architecture explanation: request flow
   `Host -> tenant resolve -> JWT auth -> tenant match -> role guard -> tenant-scoped SQL`
2) FastAPI code:
   - middleware/dependencies for tenancy + authorization
   - routers for auth/admin/tenant
3) DB migrations (Alembic) + models
4) seed script
5) README local domain setup
6) tests

Now implement this foundation cleanly with good structure and comments.
