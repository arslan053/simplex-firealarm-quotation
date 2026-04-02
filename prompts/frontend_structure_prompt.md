# Frontend Architecture Prompt (React + TypeScript + Tailwind, Multi-tenant by Domain)

You are a coding AI working inside an existing product repository.  
Your job in **this step** is to **define and scaffold the frontend architecture and structure only** — do **not** build business modules yet (BoQ, Specs, Pricing, Rules, etc.).  
Treat this as the **foundation prompt** that future module-prompts will build upon.

## Non-goals for this step
- Do **not** implement domain features (BoQ/spec parsing/pricing logic/UI workflows).
- Do **not** create mock business screens beyond minimal placeholders needed for routing verification.
- Do **not** hardcode vendor or product-specific rules.  
- Do **not** ask questions about “monorepo vs separate repos” or “folder separation strategy” — decide a sensible approach and proceed.

---

## Tech choices (must follow)
- **React** (no Next.js) + **TypeScript**
- **Tailwind CSS** for styling (use community best-practice patterns)
- Routing: **react-router-dom**
- HTTP: **axios** *or* native `fetch` with a proper wrapper. Choose one and justify briefly.
- State management:
  - Default to **useState / useReducer** and feature-local state.
  - Use **Redux** only where truly needed (global cross-feature client state).
- Server-state/data fetching:
  - Prefer **@tanstack/react-query** if it fits well (caching, retries, polling, invalidation).
  - If you decide not to use it, propose an alternative pattern using custom hooks **and** explain tradeoffs.

---

## Multi-tenancy requirement (critical)
Multi-tenancy is resolved by **domain separation** (subdomain or custom domain), **not** by tenant in URL.

### Must implement the following foundation pattern
1. On app bootstrap, read `window.location.hostname`.
2. 
3. Backend returns tenant metadata (example fields):
   - `tenantId`, `tenantSlug`, `branding`, `enabledModules`, `authMode`, etc.
4. Store tenant context in a **TenantProvider** (React context).
5. All subsequent API calls must include tenant context as needed (header, cookie, or request field — follow backend contract).
6. Routing should **not** include tenantId in the path.

Implement a clean tenant bootstrapping flow with:
- Loading state (splash/loader)
- Failure state (unknown tenant / maintenance)
- Caching (avoid resolving tenant repeatedly unless host changes)

---

## API contracts & type consistency (must address)
**Goal:** frontend and backend must never drift in request/response shapes.

You must propose and implement **one** of these:
1. **OpenAPI-first**: backend exposes OpenAPI schema; frontend generates TS types/client from it.
2. **Shared contracts**: schemas (Zod/JSON Schema) stored in a shared package/folder and imported by frontend.

### Requirements
- Ask clarifying questions specifically about:
  - Whether backend already exposes OpenAPI
  - Where the schema should live
  - Preferred generation tool (e.g. `openapi-typescript`) if using OpenAPI
- Do **not** block progress: if unsure, implement a safe default that can be swapped later.

---

## Folder structure (feature-first, scalable)
Use a **feature-first** approach with a small **shared** layer.

### Target structure (adapt if needed, but keep the spirit)
- `src/app/`  
  - What are necessary systems
- `src/features/<feature>/`  
  - feature-local `api/`, `components/`, `hooks/`, `pages/`, `store/` (only if needed), `types/`, `utils/`
- `src/shared/`  
  - reusable UI primitives, shared components, shared hooks, API client base, utilities, styles

### Frontend foundation features to scaffold now (no business logic)
- `features/auth` (minimal shell: login route placeholder; no full auth flows unless trivial)
- `features/tenants` (tenant resolve + TenantProvider)
- `features/projects` (placeholder list/detail routes only)

---

## Styling & UI system (Tailwind best practices)
Implement a community-recommended Tailwind setup:
- Tailwind configured properly with TypeScript + Vite
- Utility helper for class merging:
  - `clsx` + `tailwind-merge` (or equivalent)
- Create a small `shared/ui/` layer for primitives (Button, Input, Badge, Modal/Dialog):
  - Use accessible patterns (Radix optional but recommended)
- Icons: `lucide-react` (recommended)

Avoid building a full design system; just enough primitives to scale.

---

## Forms & validation (foundation)
Even if future modules will be “model-assisted”, the product still needs forms (login, project creation, admin, overrides).

Select and set up a standard approach:
- `react-hook-form` + `zod` + resolver 
- Create a pattern for feature-local forms and validations.

---

## Data-heavy UI foundation
This product will show large BoQ tables and spec clause lists.

Prepare the base tooling (without implementing BoQ UI):
- Recommend a table/grid strategy:
  - `@tanstack/react-table` for headless tables
  - Add virtualization if needed (`@tanstack/react-virtual`)
- Create reusable table shell components in `shared/components/` (minimal).

---

## Error handling, UX, and observability
Implement the following:
- Global `ErrorBoundary` + friendly fallback screen //if needed
- Consistent API error normalization (axios/fetch)
- Toast notifications (choose a simple library; e.g. `sonner` or `react-hot-toast`)
- Standard loading skeleton/spinner component
- Optional but recommended: Sentry integration placeholder (no keys committed)

---

## Quality & tooling (must include)
- ESLint + Prettier
- TypeScript strict mode (reasonable strictness)
- Tests baseline:
  - `vitest` + `@testing-library/react`
- Git hooks optional (husky/lint-staged) — if you include, explain briefly.

---

## Environment & configuration
- Use `.env` pattern suitable for Vite (`VITE_` prefix)
- Centralize config reading in `src/app/config/`
- No secrets in repo.

---

## Docker & local dev (must address)
Provide:
1. `Dockerfile` for frontend (development and/or production)
2. `docker-compose.yml` (or compose snippet) to run frontend locally alongside backend services

### Requirements
- Don’t assume backend compose exists; write compose in a way that can be merged or extended.
- Provide clear ports and environment variables.
- Include health checks or a simple readiness strategy if feasible.

---

## Versioning guidance (no hardcoded versions)
Do **not** pin exact versions in the prompt output.

Instead:
- Recommend using stable/current major versions compatible with React + Vite + TS.
- If a dependency is sensitive (e.g., React Router major changes), mention “choose the latest stable major version” and any compatibility notes.

---

## Deliverables for this step (what you must output/do)
### 1) First response: architecture proposal + minimal questions
Before generating files, respond with:
- A short architecture overview (1–2 pages max)
- Key decisions (HTTP choice, query library choice, contracts strategy)
- **Only necessary clarifying questions** (focus on OpenAPI/contracts + auth style; do not ask repo-structure questions)

### 2) Then scaffold the frontend
Create the actual folders and baseline files:
- Vite + React + TS setup
- Tailwind setup
- Router skeleton with layouts
- Tenant resolve bootstrap + TenantProvider
- API client base (axios/fetch wrapper)
- Query client provider if using React Query
- Placeholder routes/pages to validate navigation
- Tooling configs (eslint/prettier/tsconfig/vitest)

### 3) Document how future module-prompts should extend this
Add a short `docs/FRONTEND_MODULE_PROMPT_TEMPLATE.md` describing:
- Where new feature modules go
- How to add routes
- How to add API calls + query hooks
- Where to put UI components
- Where Redux is allowed (rare)

---

## Constraints & conventions
- Keep code clean, typed, and consistent.
- Prefer composition over inheritance.
- Keep shared code minimal; don’t over-abstract early.
- Ensure tenant context is available everywhere safely.
- Ensure API errors never crash the app; show a friendly message.

---

## Start now
Proceed with the deliverables.  
Remember: **Do not build business modules yet** — this is only the foundation architecture and scaffolding.
