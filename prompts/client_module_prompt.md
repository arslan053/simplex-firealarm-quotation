```text
Claude Code: Implement Client Module

Read and follow `./prompts/workflow_orchestration.md` first; treat it as mandatory operating rules for this session.

Read these files first (source of truth):
- ./project-scope-techstack.md
- ./backend_architect.md
- ./frontend_structure_prompt.md
- ./multitenant_prompt.md
- ./project_module_prompt.md   ← Follow the same module creation pattern

You have already implemented multi-tenancy + auth + projects.

Now implement the CLIENT MODULE.

This is a standalone CRUD module. Clients are a separate entity that projects
belong to. Every project must have a client (one-to-many: one client → many
projects, one project → exactly one client).

====================================
CLIENT MODULE – FUNCTIONAL REQUIREMENTS
====================================

ROLES & PERMISSIONS

1) Admin:
   - Can create clients.
   - Can see ALL clients in the tenant.
   - Can update any client.
   - Can click on a client and see ALL projects belonging to that client.
   - Can open any project from the client's project list (same as normal project detail page).

2) Employee:
   - Can create clients.
   - Can see ALL clients in the tenant (client list is shared, not ownership-scoped).
   - Can update any client (clients are a shared company resource, not per-user).
   - Can click on a client and see ONLY the projects they (the employee) created
     for that client.
   - Cannot access projects they did not create — not even by manually entering
     a URL. Backend must enforce ownership check for employees.



IMPORTANT SECURITY NOTES:
- The client list itself is visible to all roles within the tenant (admin + employee).
- The per-client project list is role-filtered:
    - Admin: sees all projects for that client.
    - Employee: sees only their own projects for that client.
- An employee who manually enters a project URL they do not own must get 403/404.
  This is already enforced by the existing project detail endpoint — do NOT break
  that. Just make sure the client → projects listing also respects this.

====================================
CLIENT DATA MODEL
====================================

Each Client must contain:

- id (UUID, PK, server_default gen_random_uuid())
- tenant_id (UUID, FK → tenants.id, NOT NULL)
- name (TEXT, NOT NULL) — The contact person's name
- company_name (TEXT, NOT NULL) — The company/organization name
- email (TEXT, nullable) — Must be validated as email format if provided
- phone (TEXT, nullable) — Free text, optional
- address (TEXT, nullable) — Free text, optional
- created_at (timestamptz, NOT NULL, default now())
- updated_at (timestamptz, NOT NULL, default now(), auto-update)

Constraints:
- UNIQUE(tenant_id, company_name) — No duplicate company names within a tenant.
- INDEX on tenant_id for fast filtering.

Relationship to Projects:
- Add a new column to the projects table:
    client_id (UUID, FK → clients.id, nullable)
  Nullable for backward compatibility — existing projects will have client_id = NULL.
  New projects MUST have a client_id (enforced at API level, not DB level, to avoid
  breaking existing data).

Row Level Security (RLS):
- Enable RLS on the clients table.
- Policy: tenant_isolation_policy — USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
- Policy: app_bypass_policy — USING (current_setting('app.tenant_id', true) IS NULL)
- Same pattern as quotations table (see migration 028 for reference).

====================================
BACKEND REQUIREMENTS
====================================

Create a new module: backend/app/modules/clients/

Files to create (follow project module pattern exactly):
- __init__.py
- models.py (SQLAlchemy ORM model inheriting Base, UUIDPrimaryKey, TimestampMixin)
- schemas.py (Pydantic request/response schemas)
- repository.py (data access layer with tenant_id in all queries)
- service.py (business logic, validation)
- router.py (FastAPI endpoints with auth guards)

Endpoints:

1) POST /api/clients
   - Create a new client.
   - Allowed: admin, employee (NOT super_admin).
   - Dependencies: require_tenant_domain, require_tenant_match, require_role("admin", "employee").
   - Validate:
     - name: required, non-empty
     - company_name: required, non-empty
     - email: if provided, must be valid email format
   - Check uniqueness of (tenant_id, company_name) — return 409 Conflict if duplicate.
   - Audit log: action="client.created"

2) GET /api/clients
   - List all clients in the tenant.
   - Allowed: admin, employee.
   - Paginated: page, limit, search (search on name, company_name, email).
   - Response:
     {
       data: [ClientResponse, ...],
       pagination: { page, limit, total, total_pages }
     }
   - Both admin and employee see the same list (clients are a shared resource).

3) GET /api/clients/{client_id}
   - Get a single client's details.
   - Allowed: admin, employee.
   - Must filter by tenant_id.
   - Return 404 if not found.

4) PATCH /api/clients/{client_id}
   - Update a client.
   - Allowed: admin, employee.
   - Updatable fields: name, company_name, email, phone, address.
   - If company_name is changing, re-check uniqueness.
   - Audit log: action="client.updated"

5) GET /api/clients/{client_id}/projects
   - List projects belonging to this client.
   - Allowed: admin, employee.
   - Paginated: page, limit, search.
   - Admin: returns ALL projects for this client (within tenant).
   - Employee: returns ONLY projects where owner_user_id = current user.
   - Use the same ProjectResponse / ProjectAdminResponse schemas as the project module.
   - Filter: WHERE tenant_id = :tid AND client_id = :cid (+ owner filter for employee).

6) GET /api/clients/search?q=...
   - Quick search endpoint for the client selector dropdown in the project creation form.
   - Returns: list of { id, name, company_name } matching the query.
   - Max 20 results, sorted by company_name.
   - Used by frontend autocomplete/select component.

Register the router in the main app (same way projects router is registered).

====================================
PROJECT MODULE CHANGES
====================================

Modify the existing project module to support client_id:

1) Migration:
   - Add client_id UUID column to projects table (nullable, FK → clients.id).
   - Add INDEX on (tenant_id, client_id) for fast lookups.

2) CreateProjectRequest schema:
   - Add client_id: UUID (required for new projects).
   - Validate that the client exists and belongs to the same tenant.

3) UpdateProjectRequest schema:
   - Add client_id: UUID | None (optional, can change client assignment).

4) ProjectResponse schema:
   - Add client_id: UUID | None.
   - Add client_name_display: str | None — populated from the related client's company_name
     (so the project list can show the client name without a separate API call).

5) Project model:
   - Add client_id column.
   - Add relationship: client = relationship("Client", lazy="selectin")

6) Repository / Service:
   - On create: validate client_id exists within tenant. Return 400 if invalid.
   - On update: if client_id changing, validate new client exists within tenant.

7) Project list / detail endpoints:
   - Include client info in response (client_name_display from the relationship).

====================================
FRONTEND REQUIREMENTS
====================================

Follow ./frontend_structure_prompt.md structure.

Create a new feature: frontend/src/features/clients/

Files to create:
- api/clients.api.ts
- types/index.ts
- pages/ClientListPage.tsx
- pages/ClientDetailPage.tsx (shows client info + their projects)
- components/CreateClientModal.tsx (modal form for quick client creation)
- components/ClientSelector.tsx (reusable select/autocomplete for project forms)

1) Client List Page (/clients)
   - Paginated table showing all clients.
   - Columns: Company Name, Contact Name, Email, Phone, Created At.
   - Search bar (searches company_name, name, email).
   - "New Client" button → opens CreateClientModal.
   - Each row clickable → navigates to /clients/:clientId.
   - Responsive: hide phone/email columns on mobile, show company + name only.

2) Client Detail Page (/clients/:clientId)
   - Top section: client info card (name, company_name, email, phone, address).
   - Edit button → inline edit or modal to update client info.
   - Bottom section: "Projects" table — paginated list of projects for this client.
     - Admin: sees all projects for this client.
     - Employee: sees only their own projects for this client.
   - Each project row clickable → navigates to /projects/:projectId (existing detail page).
   - "New Project" button → navigates to /projects/new?clientId=:clientId (pre-selects client).

3) CreateClientModal
   - Modal form with fields:
     - Name (required)
     - Company Name (required)
     - Email (optional, email format validation)
     - Phone (optional)
     - Address (optional)
   - On success: closes modal, refreshes client list, returns the new client.
   - Shows server errors (e.g., duplicate company name).

4) ClientSelector (reusable component)
   - Used in CreateProjectPage and UpdateProjectPage.
   - Searchable dropdown that queries GET /api/clients/search?q=...
   - Shows company_name + contact name in dropdown options.
   - Has a "+ Create New Client" option at the bottom of the dropdown.
     - Clicking it opens CreateClientModal inline.
     - After creating, auto-selects the new client.
   - Required field (new projects must have a client).

5) Modify CreateProjectPage:
   - Replace the free-text "Client Name" input with the ClientSelector component.
   - The form now sends client_id instead of client_name (or both — client_name
     can be auto-populated from the selected client's company_name for backward
     compatibility, but client_id is the source of truth).

6) Modify ProjectDetailPage:
   - Show client info (company name as a clickable link → /clients/:clientId).

7) Routing (add to frontend/src/app/router/index.tsx):
   - { path: 'clients', element: <ClientListPage /> }
   - { path: 'clients/:clientId', element: <ClientDetailPage /> }

8) Navigation (add to AppLayout.tsx → getNavItems):
   - Add "Clients" nav item with a suitable icon (e.g., Users or ContactRound from lucide).
   - Visible to: admin AND employee (same condition as projects).
   - Position: between Dashboard and Projects in the nav.

====================================
AUDIT REQUIREMENT
====================================

Log at minimum:
- client.created
- client.updated

Use existing AuditService from the audit module.
Same pattern as project.created / project.updated.

====================================
SECURITY RULES
====================================

- Enforce tenant isolation strictly — ALL queries must filter by tenant_id.
- Clients are tenant-scoped: a client belongs to one tenant only.
- Both admin and employee can see all clients (shared resource within tenant).
- Project visibility within a client is role-filtered:
    Admin → all projects for client.
    Employee → only their own projects for client.
- Never allow cross-tenant access.
- Validate UUIDs and ownership on backend.
- RLS policies on clients table (same pattern as quotations).
- An employee cannot access a project they don't own by URL manipulation.
  The existing project detail endpoint already enforces this — do not regress.

====================================
MIGRATION
====================================

Create a single Alembic migration that:

1) Creates the clients table with all columns, constraints, and indexes.
2) Enables RLS + creates tenant_isolation_policy and app_bypass_policy.
3) Adds client_id column to projects table (nullable UUID, FK → clients.id).
4) Adds index ix_projects_tenant_client on (tenant_id, client_id).

Use raw SQL for RLS (same pattern as migration 028 for quotations).
For the Postgres enum patterns, follow the notes in MEMORY.md.

Number the migration as the next sequential number after the latest existing one.

====================================
IMPLEMENTATION STYLE
====================================

- Follow the exact same module structure as the project module:
    models.py → schemas.py → repository.py → service.py → router.py
- Use consistent pagination (same PaginationMeta, build_pagination helper — import
  from projects.schemas or move to a shared location if not already shared).
- Use react-hook-form + Zod for frontend forms.
- Keep UI clean with Tailwind best practices.
- Do not over-abstract.
- Keep logic feature-scoped.
- Use existing shared UI components: Card, Button, Input, Badge.

====================================
DELIVERABLE
====================================

1) Alembic migration for clients table + client_id on projects.
2) Backend module: models, schemas, repository, service, router.
3) Project module updates: schema changes, model changes, validation.
4) Frontend: client feature (pages, components, API, types).
5) Frontend: project creation form updated with ClientSelector.
6) Routing + nav item registered.
7) End-to-end: create client → create project with client → view client's
   projects → verify employee can only see own projects.

====================================
GENERAL INSTRUCTIONS (APPLIES TO ALL MODULES)
====================================

- If any required RLS policies for multi-tenancy are missing, implement them using
  best-practice Postgres RLS patterns.
- Review the codebase structure and confirm responsibilities are correctly separated
  (routes/controllers/services/repos, frontend feature-first boundaries, no mixed
  concerns). Refactor lightly if needed to keep it clean.
- Ensure the full frontend setup is production-quality: consistent theme tokens
  (colors/typography/spacing), sensible primary color usage, and shared UI
  primitives applied consistently.
- Make ALL screens (existing + new) fully responsive (mobile/tablet/desktop) and
  follow best UI/UX practices.
```
