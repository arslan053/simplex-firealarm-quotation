# Architecture Decisions

## Decision Log

### D1: Tenant Resolution via X-Tenant-Host Header

**Context:** The spec requires domain-based multi-tenancy where `acme.app.com` resolves
to tenant `acme`. In a SPA architecture, the frontend runs on one port (5173) and the
backend API on another (8000). The browser `Host` header for API requests will be the
API server's host (`localhost:8000`), not the tenant domain.

**Decision:** The frontend sends `X-Tenant-Host: <window.location.hostname>` header
with every API request. The backend middleware reads this header (falling back to `Host`)
to resolve the tenant subdomain.

**Rationale:**
- Works identically in dev (different ports) and production (same domain via proxy)
- No reverse proxy required for local development
- Simple, explicit, and testable
- In production, a reverse proxy can optionally set this header from the real `Host`

**Alternatives considered:**
- Reverse proxy (nginx) in dev to unify domains → added complexity for dev setup
- Reading `Origin`/`Referer` headers → unreliable, not sent on all requests

---

### D2: API Contract Strategy — OpenAPI Auto-Generated

**Context:** The frontend and backend need consistent request/response types.
The spec asks to choose between OpenAPI-first or shared contracts.

**Decision:** Use FastAPI's auto-generated OpenAPI schema (`/docs`, `/openapi.json`).
For now, frontend types are manually kept in sync. In a future step, we can add
`openapi-typescript` to auto-generate frontend types from the schema.

**Rationale:**
- FastAPI generates OpenAPI automatically from Pydantic models — zero extra work
- Manual sync is acceptable for the small auth/tenant surface area
- Adding type generation later is straightforward and non-breaking

---

### D3: Monorepo with Two Top-Level Directories

**Context:** The spec says not to ask about monorepo vs separate repos.

**Decision:** Single repository with `backend/` and `frontend/` as top-level directories.
Shared configuration (docker-compose, docs) lives at the root.

**Rationale:**
- Simplest approach for a single team
- Single docker-compose orchestrates everything
- Shared docs and decisions in one place

---

### D4: JWT Stored in localStorage

**Context:** JWT token needs to be stored client-side. Options: localStorage, sessionStorage,
httpOnly cookies.

**Decision:** Store JWT in localStorage under key `access_token`.

**Rationale:**
- Simple to implement and debug
- Works with the `Authorization: Bearer` header pattern
- httpOnly cookies add CORS/CSRF complexity not justified for MVP
- Can migrate to httpOnly cookies later if security audit requires it

**Trade-off:** localStorage is vulnerable to XSS. Mitigated by:
- Short-lived tokens (15 min)
- No sensitive data in the token payload beyond user ID and role
- CSP headers can be added later

---

### D5: Password Reset via Stateless JWT Tokens

**Context:** Forgot/reset password flow needs secure, single-use tokens.

**Decision:** Reset tokens are JWTs containing `user_id`, `purpose: "reset"`, and a
prefix of the current `password_hash`. Token expires in 1 hour.

**Rationale:**
- Stateless — no extra DB columns or tables needed
- Self-invalidating — changing the password changes the hash, invalidating old tokens
- Uses the same JWT infrastructure already in the project

---

### D6: HTTP Client — axios

**Context:** The frontend spec allows axios or a fetch wrapper.

**Decision:** Use axios with a pre-configured instance.

**Rationale:**
- Built-in interceptors for auth headers and error handling
- Automatic JSON serialization/deserialization
- Widespread adoption and TypeScript support
- Request/response interceptors cleanly handle the X-Tenant-Host header injection

---

### D7: Three Simple Roles (No RBAC)

**Context:** The spec explicitly states "no full RBAC" — just 3 roles.

**Decision:** Implement simple role checking via `require_role(*roles)` dependency.
Roles are: `super_admin`, `admin`, `employee`.

**Rationale:**
- RBAC is over-engineering for 3 roles
- Role guard dependencies are composable and explicit
- Can upgrade to full RBAC later if needed

---

### D8: Email Backend Abstraction

**Context:** Need email for password reset and user invitations.

**Decision:** Abstract `EmailSender` interface with two implementations:
- `ConsoleEmailSender` for development (prints to stdout)
- `SmtpEmailSender` for production (via aiosmtplib)

Selected via `EMAIL_BACKEND` env var (`console` or `smtp`).

**Rationale:**
- No external email service dependency for development
- Easy to swap providers
- Console output makes dev/testing straightforward

---

### D9: Local Dev Domain Setup via /etc/hosts

**Context:** Multi-tenancy requires different hostnames in the browser.

**Decision:** Developers add entries to `/etc/hosts`:
```
127.0.0.1 admin.local
127.0.0.1 acme.local
127.0.0.1 beta.local
```

Then access:
- Frontend: `http://acme.local:5173`, `http://admin.local:5173`
- Backend direct: `http://acme.local:8000`

**Rationale:**
- Standard approach for local domain-based development
- No DNS server or proxy needed
- Works on all operating systems

---

### D10: Soft Delete for Users Only

**Context:** The spec requires soft delete for users.

**Decision:** Users have `is_active` (boolean) and `deleted_at` (timestamp) columns.
Deactivation sets `is_active=false` and `deleted_at=now()`. No hard deletes.

Tenants use `status` field (`active`/`suspended`) rather than soft delete.

**Rationale:**
- Matches the spec exactly
- Preserves audit trail
- Suspended tenants can be reactivated
