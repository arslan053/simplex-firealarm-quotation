# Backend Architecture Prompt (FastAPI + Modular Monolith + Orchestration)

You are a coding model working on an AI-assisted multi-tenant pricing system that calculates pricing from:
- **BOQ** (structured Excel, categorized)
- **Specifications** (PDFs; may contain images; text extracted via PyMuPDF when possible, OCR when needed)
- **Questions/Answers** (system-defined questions answered via deterministic logic and/or an RLM)
- **Rules/Knowledge Base** (hundreds of rule combinations and constraints)

Your goal is to implement a **clean, maintainable backend** using **FastAPI** with a **modular monolith** design, **thin API layer**, **background workers**, and a **central orchestration layer** that coordinates the workflow.


> **Build Approach Note (Important):** Treat this document as the **base architectural foundation** and guidance for a **step-by-step, modular implementation**. The system will be built incrementally (module-by-module and pipeline-by-pipeline). Do **not** assume the full end-to-end platform must be delivered in one pass; each increment should remain compatible with this architecture so future modules can be added cleanly.


---

## 1) Core Architectural Goals

### Separation of Concerns
- **API layer**: request handling only (auth, validation, enqueue jobs, return IDs/status). No heavy parsing, OCR, RLM calls, or rule evaluation for batch pipelines.
- **Business modules/services**: domain logic (parsing, rule evaluation, question resolution, pricing calculations, RLM calls).
- **Workers**: execute long-running tasks (file parsing/OCR, batch pipelines, model-heavy steps).
- **Orchestration**: one place that coordinates services in the correct order; services should not call each other arbitrarily.

### Multi-Tenancy
- System is **multi-tenant**. All stored entities must be scoped to **tenant_id** (and typically **project_id**).
- Ensure tenant isolation through:
  - tenant-aware queries
  - tenant context in request lifecycle
  - consistent tenant_id presence across records

### Reliability & Observability
- Jobs must be trackable with status and progress.
- RLM calls must be centralized, structured, logged, and validated.

---

## 2) High-Level System Flow

### A) Ingestion Phase (Parsing & Storage)
1. User uploads **BOQ Excel** and **Spec PDFs/folders**.
2. API stores files to object storage (S3/MinIO/local) and creates DB file records.
3. API creates a **Job** record and enqueues worker tasks.
4. Worker parses:
   - BOQ → structured rows stored in DB (no vector required for BOQ).
   - Specs → extracted text/sections/images stored in DB (chunked/sectioned for retrieval; OCR used only when necessary).
5. Job status/progress updated in DB; frontend polls for status.

### B) Decision & Pricing Phase (Orchestrated Pipeline)
After BOQ and Specs are stored:
1. Run a pipeline per project or per BOQ item.
2. For each BOQ item, build a **Project Context** object.
3. Use deterministic **rule engine** + question resolution.
4. Call **RLM** only where needed to decide/normalize exact items or to answer complex questions.
5. Compute pricing using pricing engine.
6. Store outputs and audit logs.

---

## 3) Orchestration Pattern (Key Requirement)

### Central Orchestrator
Implement a **Decision Orchestrator** that coordinates all steps. Services are “specialists”; the orchestrator is the “manager”.

**Rule:** services should not call each other directly for workflow sequencing.  
They should expose clean functions and accept inputs; orchestration decides order.

### Project Context Object
Use a single context object passed through steps (e.g., dict/class). It accumulates:
- tenant_id, project_id
- boq_item (structured)
- relevant spec sections/chunks
- question answers
- applicable rules/rule outputs
- RLM decision output (strict JSON)
- pricing result
- logs/trace ids

**Example conceptual flow (no code required):**
- Load BOQ item → retrieve relevant spec chunks → resolve questions → match rules → call RLM → calculate pricing → persist result.

---

## 4) Modules and Responsibilities (Conceptual)

Implement domain modules with clear responsibilities. A suggested set:

**Module file convention (keep it simple and consistent):** each module may contain:
- `router.py` (API endpoints for that domain; thin)
- `models.py` (DB models)
- `schemas.py` (request/response DTOs)
- `repository.py` (DB queries/data access)
- `service.py` (domain/business logic)


- **tenants/projects**: tenant/project management, configs
- **files**: file records (type, storage_url), upload handling (thin)
- **boq**: parse Excel, validate, store structured items, query BOQ items
- **specs**: parse PDFs (PyMuPDF), OCR path (when images/scan), store sections/chunks/images; provide “find relevant” retrieval
- **rules**: deterministic rule evaluation and rule matching (no RLM inside)
- **questions**: define required questions for item types; resolve answers via deterministic logic and/or RLM
- **rlm**: centralized model interface (prompt build, call, retries, strict output validation, logging)
- **pricing**: compute pricing from context (BOQ + decisions + answers + rules)
- **results/audit**: store decision outputs, pricing outputs, prompt logs, traceability

---

## 5) Workers and Job Tracking

### Background Workers
Use workers for:
- BOQ parsing (Excel)
- Specs parsing (PDF extraction and OCR)
- Full project pipeline (process many BOQ items)
- Optional per-item pipeline for retries

### Job/Progress Model
- Maintain a DB **jobs** table:
  - status: queued/running/succeeded/failed
  - progress: 0–100
  - message: human-readable progress
  - error: failure details
- API exposes:
  - `GET /jobs/{job_id}` for frontend polling

**Important:** do not keep requests open for parsing/pipeline execution. Return job_id immediately.

---

## 6) RLM Usage Rules (Production-Friendly)

- All RLM calls must go through the **rlm module**.
- Use **structured JSON outputs** with schema validation.
- Log:
  - prompt inputs (or references to stored inputs)
  - model config/version
  - raw response
  - parsed JSON
  - validation failures and retries
- Prefer deterministic rules first; use RLM for ambiguous mapping/interpretation.

---

## 7) Data Storage (High Level)

- **PostgreSQL** for structured data: tenants, projects, file records, BOQ items, spec sections, rules, questions/answers, decisions, pricing outputs, jobs.
- **Object storage** for raw files and extracted images (S3/MinIO/local).
- **Redis** (recommended) for queue backend and caching.
- **Neo4j** for storing BOQ-derived results/relationships (e.g., item → decision → rule → spec-reference links) alongside PostgreSQL.

(BOQ is not stored as vectors. Specs may be stored as structured sections/chunks; if embeddings are added later, keep it optional and isolated.)

### Local Development (Docker Compose)
- Provide a `docker-compose.yml` for local development that includes at minimum: **api**, **worker**, **postgres**, **redis**, and **neo4j** (optionally **minio** for S3-compatible file storage in dev).
- The compose setup should support running the API and workers together, with environment variables provided via `.env`.

---

## 8) Implementation Guidance (Do/Don’t)

### Do
- Keep API routers thin.
- Use **enums** where constrained values exist (e.g., job status, file types, document types, rule operators, pipeline states) to keep the codebase consistent and reduce bugs.

- Use orchestration to coordinate multi-step workflows.
- Keep deterministic rules separate from RLM.
- Pass identifiers to workers (job_id/file_id), not large file bytes.
- Make everything tenant-aware.

### Don’t
- Don’t scatter RLM calls across modules.
- Don’t let services call each other in chains that cause circular dependencies.
- Don’t block HTTP requests waiting for parsing/pipelines to finish.

---

## 9) Deliverables Expected From the Coding Model

- A clean FastAPI backend project structured as a modular monolith.
- Worker setup with background tasks and job progress tracking.
- Orchestration layer with context-driven pipeline execution.
- Clear module boundaries that match the responsibilities above.
- Multi-tenant-safe database access patterns and consistent scoping.

