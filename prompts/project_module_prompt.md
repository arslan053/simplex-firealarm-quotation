```text
Claude Code: Implement Project Module (Phase 0 – Step 2)

Read these files first (source of truth):
- ./project-scope-techstack.md
- ./backend_architect.md
- ./frontend_structure_prompt.md
- ./multitenant_prompt.md

You have already implemented multi-tenancy + auth foundation.

Now implement the PROJECT MODULE only.

Do NOT implement BoQ parsing, spec parsing, pricing logic, or file-processing logic yet. Only structure + UI + endpoints.

====================================
PROJECT MODULE – FUNCTIONAL REQUIREMENTS
====================================

ROLES & PERMISSIONS

1) Only:
   - Employee
   - Admin
   can create projects.

2) Super Admin:
   - Cannot create projects.

3) Employee:
   - Can see only their own projects.
   - Can open their own project.
   - Can update their own project.

4) Admin:
   - Can see all projects inside the tenant.
   - Must only see limited fields in list view:
        - project_name
        - client_name
        - status
   - Admin can also see created by name of employee.
   - If project status = COMPLETED (future feature), Admin can download final quotation document (placeholder only for now).

====================================
PROJECT DATA MODEL
====================================

Each Project must contain:

- id (UUID)
- tenant_id (required)
- owner_user_id (required)
- project_name (string, required)
- client_name (string, required)
- country (string, required)
- city (string, required)
- due_date (DATE only, required)
- panel_family (string, nullable, default NULL)
- status (ENUM)
    Allowed values:
      - IN_PROGRESS
      - IN_REVIEW
      - COMPLETED
    Default:
      - IN_PROGRESS
- created_at
- updated_at

Multi-tenancy enforcement:
- All queries must filter by tenant_id.
- Employee queries must also filter by owner_user_id.

====================================
BACKEND REQUIREMENTS
====================================

Implement:

1) Create Project endpoint
   - Only Admin or Employee allowed.
   - Super Admin forbidden.
   - Assign:
       tenant_id from resolved tenant
       owner_user_id from current user
       status = IN_PROGRESS
       panel_family = NULL
   - By default country is KSA but country must be selected from a countries list (not free text).
   - City remains input text, but when saved normalize it to standard format: First letter capital, remaining small.

2) Update Project endpoint
   - Only project owner (Employee) can update.
   - Admin cannot update.
   - Cannot manually change panel_family (system controlled).
   - Status must remain uneditable by user; system will update it.

3) List Projects endpoint (Paginated)
   - Must support pagination:
       page
       limit
       total count
   - Employee:
       return only their own projects (full fields)
   - Admin:
       return all tenant projects
       but restrict response fields to:
         id
         project_name
         client_name
         status
         created_at
         created_by_name
   - If suitable, support filtering in listing:
       - by project_name
       - by organisation name
       - or both

4) Get Project Details endpoint
   - Employee:
       full project details (if owner)
   - Admin:
       restricted view (same limited fields unless specified otherwise)

Pagination:
- Must be implemented cleanly.
- Response format:
    {
      data: [...],
      pagination: {
          page,
          limit,
          total,
          total_pages
      }
    }

====================================
FRONTEND REQUIREMENTS
====================================

Follow ./frontend_structure_prompt.md structure.

Implement:

1) Project List Screen
   - Paginated table
   - Sorting by created_at (default desc)
   - Employee:
       shows their projects
   - Admin:
       shows restricted project table (limited columns)

2) Create Project Screen
   - Fields:
       project_name
       client_name
       country
       city
       due_date (date picker)
   - Status must NOT be editable on creation.
   - Use proper form validation.
   - After success → redirect to project detail page.

3) Update Project Screen
   - Only accessible by owner.
   - Editable fields:
       project_name
       client_name
       country
       city
       due_date
   - panel_family not editable.
   - status editable only if allowed by backend rule.

4) Project Detail Page (New Route)
   Route example:
     /projects/:projectId

   Must contain:
   - Basic project information section.
   - Two upload placeholders:
       - Upload BoQ file
       - Upload Specification file

   IMPORTANT:
   Do NOT implement file processing logic yet.
   Just create UI + endpoint placeholders.
   Actual upload handling will be implemented in the next phase.

====================================
AUDIT REQUIREMENT
====================================

Log at minimum:
- PROJECT_CREATED
- PROJECT_UPDATED

Use existing audit service from Step 1.

====================================
SECURITY RULES
====================================

- Enforce tenant isolation strictly.
- Enforce role-based restrictions strictly.
- Never allow cross-tenant access.
- Validate UUIDs and ownership checks on backend.
- Apply RLS policies where necessary (including this projects table and other tenant-owned tables where required).

====================================
IMPLEMENTATION STYLE
====================================

- Use consistent pagination strategy.
- Use React Query if already chosen in foundation.
- Keep UI clean with Tailwind best practices.
- Do not over-abstract.
- Keep logic feature-scoped.

====================================
DELIVERABLE
====================================

1) Implement backend schema/migration for projects.
2) Implement backend endpoints.
3) Implement frontend pages + routing.
4) Ensure project creation → listing → open → update works end-to-end locally.
5) Update docker-compose if needed.
6) Provide short "How to test Project Module locally" section.

Do NOT implement BoQ/spec parsing yet.

Start now.
```

====================================
GENERAL INSTRUCTIONS (APPLIES TO ALREADY BUILD AND ALL FUTURE MODULES)
====================================

- If any required RLS policies for multi-tenancy are missing (in projects or any tenant-owned tables), implement them using best-practice Postgres RLS patterns.
- Review the codebase structure and confirm responsibilities are correctly separated (routes/controllers/services/repos, frontend feature-first boundaries, no mixed concerns). Refactor lightly if needed to keep it clean.
- Ensure the full frontend setup is production-quality: consistent theme tokens (colors/typography/spacing), sensible primary color usage, and shared UI primitives applied consistently.
- Make ALL screens (existing + new) fully responsive (mobile/tablet/desktop) and follow best UI/UX practices.
