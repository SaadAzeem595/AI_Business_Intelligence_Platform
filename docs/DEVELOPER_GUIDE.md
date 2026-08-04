# Local Developer Onboarding Guide

Welcome to the developer onboarding handbook for the AI Business Intelligence Platform. This document provides step-by-step instructions for installing, configuring, testing, and debugging the application in a local workspace environment.

---

## 📁 Repository Directory Structure

```
├── backend/                 # FastAPI Backend Codebase
│   ├── alembic/             # PostgreSQL database migrations files
│   ├── app/                 # Backend source folders
│   │   ├── core/            # Database engine, caching, middleware configurations
│   │   ├── db/              # Models Base and DB Session factory
│   │   ├── features/        # Business logic modules (Auth, SQL, ML, RAG, Agents)
│   │   └── main.py          # FastAPI application initialization
│   ├── tests/               # Pytest tests (Unit, Integration, Security audits)
│   ├── pyproject.toml       # Backend package specifications and configurations
│   └── run.py               # Local server runner script
├── src/                     # Next.js Frontend Codebase
│   ├── app/                 # Next.js routing and web pages
│   ├── features/            # Feature hooks and API fetch wrappers
│   └── shared/              # Reusable layout controls and hooks
├── sample_data/             # Mock datasets for Sales, Finance, and Marketing
└── Makefile                 # Root-level unified command-line target manager
```

---

## 🛠️ Step-by-Step Workspace Setup

### 1. Prerequisite Installations
* Install **Python 3.12+** (ensure python is on PATH).
* Install **Node.js 18+** (LTS version recommended).
* Install **Docker & Docker Compose** for database/caching services.

### 2. Dependency Installation
Run the root Makefile install target to download package assets:
```bash
make install
```

### 3. Database Schema Migrations
If database schema definitions are updated:
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Generate a new revision:
   ```bash
   alembic revision --autogenerate -m "description of changes"
   ```
3. Apply migration changes to local Postgres instance:
   ```bash
   alembic upgrade head
   ```

---

## 🔌 Caching Operations

To maintain high development velocity, the Redis cache module uses a transparent in-memory dictionary fallback when Redis is offline.

* **Redis Active**: Set environment variables `REDIS_HOST=localhost` and `REDIS_PORT=6379`.
* **Redis Offline (Fallback)**: If Redis connection fails, the cache module automatically prints a console notice:
  ```
  Redis client offline: fallback in-memory storage active.
  ```
  This is useful for writing frontend logic or testing queries offline without database setups.

---

## 🔬 Observability & Debugging

### Verifying Metrics
With the development server running, query `/metrics` using curl:
```bash
curl http://localhost:8000/metrics
```
Expected output:
```
# HELP http_request_duration_seconds FastAPI HTTP request duration in seconds
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{le="0.005",method="GET",path="/live"} 1.0
```

### Accessing Traces (OpenTelemetry)
By default, trace spans are printed directly to log stdout outputs using the OpenTelemetry Console SpanExporter. You will see JSON blocks formatted like:
```json
{
    "name": "GET /api/v1/analytics/query",
    "context": {
        "trace_id": "0x97f83787bb1d23c4e6ab8b553c54d161",
        "span_id": "0xc3b3ed19142f8f98"
    },
    "status": {
        "status_code": "UNSET"
    }
}
```
Use these trace and span IDs to trace issues across services.
