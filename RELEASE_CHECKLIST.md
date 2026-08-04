# Release Checklist (v1.0.0)

This checklist outlines the quality gates, validation checks, and operational steps required before publishing the repository to GitHub as a public portfolio project.

---

## 1. Quality & Standards Gate

### Code Hygiene
* [ ] **Lint and Format**:
  * Run ESLint for frontend code formatting checks.
  * Run Ruff for Python backend imports organization and style alignments:
    ```bash
    make lint
    make format
    ```
* [ ] **Type Check validation**:
  * Verify all TypeScript files compile cleanly.
  * Ensure python type hints have 100% coverage on core service utilities.
* [ ] **Security Vulnerability Sweep**:
  * Run Bandit check to verify no hardcoded secrets or unsafe imports are in python modules:
    ```bash
    bandit -r backend/app -x backend/app/tests
    ```
  * Run dependency safety vulnerability checks.

---

## 2. Test Execution & Verification

* [ ] **Database Schema Refresh**:
  * Reset local Postgres and run migrations from scratch to confirm Alembic scripts are error-free:
    ```bash
    cd backend
    alembic upgrade head
    ```
* [ ] **Run Full Test Suite**:
  * Run all backend automated tests and verify that 40/40 tests pass:
    ```bash
    make test
    ```
* [ ] **Manual Endpoint Verification**:
  * Verify that `/live` returns 200 OK.
  * Verify that `/ready` returns 200 OK when postgres, redis, and duckdb are healthy.
  * Verify that `/metrics` returns Prometheus text metrics formats.

---

## 3. Documentation Audit

* [ ] **Mermaid Diagram validation**:
  * Verify all 11 Mermaid diagrams in `docs/ARCHITECTURE.md` compile and render correctly on GitHub markdown previews.
* [ ] **Developer Guides review**:
  * Validate that setup steps in `docs/DEVELOPER_GUIDE.md` work exactly as written.
* [ ] **Sample Data review**:
  * Confirm that sample datasets in `sample_data/` can be successfully uploaded and processed.

---

## 4. Release & Publishing Steps

* [ ] **Git Cleanup**:
  * Prune all temporary developer branches.
  * Ensure `.gitignore` ignores Python cache files, reports outputs, vector storage databases, and virtual environments.
* [ ] **Tag Version Release**:
  * Commit all changes and tag the git history with the release version:
    ```bash
    git tag -a v1.0.0 -m "Hardened production enterprise release"
    git push origin v1.0.0
    ```
* [ ] **Open Source Publishing**:
  * Set repository visibility to **Public**.
  * Add descriptive repository topics: `fastapi`, `nextjs`, `langgraph`, `duckdb`, `opentelemetry`, `prometheus`, `redis-caching`, `rag`.
