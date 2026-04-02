# Quotation Platform

Multi-tenant pricing platform that processes BOQ files and specification documents.

## Architecture

- **Backend:** FastAPI (Python) — modular monolith
- **Frontend:** React + TypeScript + Vite + Tailwind CSS
- **Database:** PostgreSQL (single DB, shared tables, tenant_id scoping)
- **Cache/Queue:** Redis
- **Auth:** JWT (HS256), 3 roles: super_admin, admin, employee

### Multi-Tenancy

Tenants are resolved by **domain/subdomain**:
- `admin.local` → Super admin platform
- `acme.local` → Tenant "acme"
- `beta.local` → Tenant "beta"

Request flow:
```
Browser → X-Tenant-Host header → Tenant Resolve Middleware → JWT Auth → Role Guard → Tenant-Scoped SQL
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- A text editor to modify `/etc/hosts`

### 1. Configure Local Domains

Add these entries to your hosts file:

**Linux/Mac:** `/etc/hosts`
**Windows:** `C:\Windows\System32\drivers\etc\hosts`

```
127.0.0.1 admin.local
127.0.0.1 acme.local
127.0.0.1 beta.local
```

### 2. Set Up Environment Files

```bash
# Backend
cp backend/.env.example backend/.env

# Frontend
cp frontend/.env.example frontend/.env
```

### 3. Start with Docker Compose

```bash
docker-compose up --build
```

This starts:
- **PostgreSQL** on port 5432
- **Redis** on port 6379
- **Backend API** on port 8000 (with auto-reload)
- **Frontend** on port 5173 (with HMR)

On first start, it automatically runs database migrations and seeds.

### 4. Access the Application

| URL | Purpose |
|-----|---------|
| `http://acme.local:5173` | Acme tenant frontend |
| `http://beta.local:5173` | Beta tenant frontend |
| `http://admin.local:5173` | Super admin frontend |
| `http://localhost:8000/docs` | API documentation (Swagger) |
| `http://localhost:8000/redoc` | API documentation (ReDoc) |

### 5. Seed Users (auto-created on first start)

| Email | Password | Role | Tenant |
|-------|----------|------|--------|
| `superadmin@app.com` | `admin123` | super_admin | — (platform) |
| `admin@acme.com` | `admin123` | admin | Acme Corp |
| `employee1@acme.com` | `admin123` | employee | Acme Corp |
| `employee2@acme.com` | `admin123` | employee | Acme Corp |
| `admin@beta.com` | `admin123` | admin | Beta Inc |
| `employee1@beta.com` | `admin123` | employee | Beta Inc |
| `employee2@beta.com` | `admin123` | employee | Beta Inc |

## Local Development (Without Docker)

### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Set up .env
cp .env.example .env
# Edit .env with your local PostgreSQL connection string

# Run migrations
alembic upgrade head

# Seed data
python seeds.py

# Start dev server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Set up .env
cp .env.example .env

# Start dev server
npm run dev
```

## Project Structure

```
quotation/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── main.py          # App entry point
│   │   ├── config.py        # Settings (pydantic-settings)
│   │   ├── database.py      # Async SQLAlchemy setup
│   │   ├── shared/          # Shared utilities (security, email, enums)
│   │   ├── middleware/       # Tenant resolution middleware
│   │   ├── dependencies/    # Auth & role guard dependencies
│   │   └── modules/         # Feature modules
│   │       ├── auth/        # Login, password, JWT
│   │       ├── tenants/     # Tenant CRUD (super admin)
│   │       ├── users/       # User management (tenant admin)
│   │       └── audit/       # Audit logging
│   ├── alembic/             # Database migrations
│   ├── tests/               # Backend tests
│   └── seeds.py             # Seed data script
├── frontend/                # React SPA
│   └── src/
│       ├── app/             # App bootstrap, config, router, providers
│       ├── features/        # Feature modules (auth, tenants, dashboard)
│       └── shared/          # Shared UI, API client, utilities
├── docs/                    # Architecture decisions & guides
├── docker-compose.yml       # Local dev orchestration
└── README.md
```

## Email in Development

In development, emails are printed to the backend console (stdout). Look for
`--- EMAIL ---` blocks in the backend logs to see reset password links and
invitation emails.

To use real SMTP in development, set these in `backend/.env`:
```
EMAIL_BACKEND=smtp
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=your-user
SMTP_PASSWORD=your-password
SMTP_FROM=noreply@yourdomain.com
```

## Running Tests

### Backend
```bash
cd backend
pytest tests/ -v
```

### Frontend
```bash
cd frontend
npm test
```
