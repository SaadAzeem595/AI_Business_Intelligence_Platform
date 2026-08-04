# Code Quality Audit & Recommendations

This document contains a comprehensive architectural audit of the AI Business Intelligence Platform, highlighting codebase optimization targets, styling inconsistencies, and technical debt items. These recommendations are prioritized to guide future platform iterations without modifying current functional behavior.

---

## 🔍 Codebase Diagnostics

### 1. Duplicate & Redundant Logic
* **Sync-Async Boundaries in Caching**:
  * In `cache.py`, the helper `run_async_as_sync` is used to bridge async Redis calls to sync DuckDB/ML pipelines. This requires managing double connections and can be unified in future refactors by transitioning the analytics execution layer to fully async workflows.
* **Metadata Schema Conversion**:
  * Response models (like `ReportResponse` or `DatasetDetailsResponse`) perform duplicate model dump/validation steps inside routers. Centralizing model serializations within feature base schemas will reduce boilerplate.

### 2. Dead Code Findings
* **Mock Authentication Fallback**:
  * `dependencies.py` has a testing fallback returns `MockUser` configuration when `IS_TESTING` is active. While vital for unit testing, this should be isolated using pytest dependency overrides rather than production middleware conditionals.

### 3. Naming Inconsistencies
* **CamelCase vs snake_case**:
  * Database schemas and metadata records use `snake_case` (e.g., `uploaded_by`), whereas some frontend API contracts expect camelCase keys (e.g., `elapsedMs` in `SQLResponse`). Standardizing all API serialization contracts using Pydantic's `alias_generator` config is recommended.

---

## 📋 Prioritized Recommendations

### 🔴 High Priority (Security & Reliability)
1. **JWT Secret Lifecycle Management**:
   * Migrate the `SECRET_KEY` variable from env files to a secure cloud key vault (e.g., AWS Secrets Manager, Azure Key Vault, HashiCorp Vault) to protect production environments from file leakage risks.
2. **PostgreSQL Connection Pooling Limits**:
   * Configure explicit pool sizes (`pool_size`, `max_overflow`) for `AsyncSessionLocal` in `database.py` to prevent running out of database socket connections when analytics request spikes occur.
3. **DuckDB Write Lock Mitigation**:
   * DuckDB database files (`.db`) only support single-process write access. Since FastAPI web worker processes and Celery background workers run concurrently, configure read-only connection limits on API threads and route all modification operations exclusively through Celery task queues.

### 🟡 Medium Priority (Performance & Maintainability)
4. **Redis Cache TTL Tuning**:
   * Segment cache TTLs by volatility. SQL query caches should have short TTLs (e.g., 5 minutes), whereas ML models and vector indexes should use long TTLs (e.g., 24 hours) or remain stored permanently until an invalidation trigger occurs.
5. **Worker Scalability**:
   * Split Celery worker queues: dedicate high-priority threads for interactive agent queries (`ChatSession`) and low-priority threads for long-running PDF/ML tasks (`retrain_model_task`).
6. **Unified Schema Aliasing**:
   * Add `populate_by_name = True` and use camelCase Pydantic aliases globally to keep backend Python code cleanly in `snake_case` while serving standard JSON formats to the Next.js UI.

### 🟢 Low Priority (DX & Styling)
7. **Type Hint Enforcement**:
   * Run typing verification checks (`mypy`) inside git pre-commit hooks to guarantee 100% type enforcement coverage.
8. **Automated OpenAPI Exports**:
   * Add a build script that automatically exports the raw OpenAPI JSON specification to `docs/openapi.json` during build stages.
