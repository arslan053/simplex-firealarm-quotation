# Project Scope & Tech Stack

## Project Scope
A multi-tenant platform that:
- Accepts **BOQ Excel** files (well-categorized/structured).
- Accepts **Specification documents** (PDFs; may include images).
- Extracts and stores BOQ data and spec content.
- Uses **rules + questions + model assistance** to map BOQ lines to the correct catalog items and compute pricing.
- Supports rule combinations and knowledge-based decision logic.
- Runs heavy tasks asynchronously with job tracking and progress reporting.
- Produces structured pricing outputs and decision logs per project/BOQ item.

## Tech Stack
- **Backend API:** FastAPI (Python)
- **Background Jobs / Workers:** Celery (or RQ) + Redis
- **Database:** PostgreSQL
- **Cache / Queue Broker:** Redis
- **File Storage:** S3-compatible storage (MinIO/S3) or local storage (initial)
- **Spec Parsing:** PyMuPDF for text PDFs; OCR pipeline for image-heavy PDFs (e.g., DeepSeek OCR2)
- **Frontend:** React
- **Auth:** JWT-based auth with tenant scoping
- **Migrations:** Alembic (recommended for production schema evolution)
