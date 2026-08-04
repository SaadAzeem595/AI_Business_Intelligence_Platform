# Changelog

All notable changes to the AI Business Intelligence Platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-08-04

This release transitions the prototype application into a hardened, production-ready enterprise intelligence platform.

### Added
* **Observability Infrastructure**:
  * OpenTelemetry FastAPI request tracing instrumentation.
  * Custom Prometheus metric collectors for API, SQL, ML, RAG, Celery, and agent execution latency.
  * Sentry error exception reporting.
  * Structured JSON logging format setup.
* **Security & Hardening**:
  * Cryptography-backed HS256 JWT authorization signatures and refresh token mechanics.
  * API Key authentication (`X-API-Key`) for automated Analyst pipelines.
  * Role-Based Access Control (RBAC) supporting `Admin`, `Executive`, `Analyst`, and `Viewer` clearance tiers.
  * Redis-backed sliding window API request rate limiter.
  * Security browser headers (Clickjacking, Sniffing, and CORS protection policies).
* **Caching & Performance**:
  * High-performance thread-safe Redis client wrapper with fallback in-memory cache connections.
  * Cache layers mapping: DuckDB query outputs, Random Forest ML inferences (with custom JSON serializers), RAG search retrievals, and Executive report outputs.
  * Automated invalidation logic triggered on sheet uploads, deletes, model retraining, and report creation.
* **Probes & Hardening**:
  * `/live` and `/ready` health endpoints checking PostgreSQL, Redis, and DuckDB connection status.
  * GZip response compression.
  * Secure, non-root execution context in Docker builds.
  * Celery Beat cron task scheduler container service.
  * GitHub Actions workflows validating linting, testing, Docker builds, and Bandit security scans.

---

## [0.1.0] - 2026-07-15

Initial prototype release.

### Added
* Multi-agent conversational system using LangGraph.
* RAG system using Chroma vector database.
* Tabular data profiling and querying using DuckDB.
* Classical statistical forecasting and random forest classifiers.
* Report compiler mapping output to PDF and PowerPoint files.
* Basic Next.js frontend UI dashboard views.
