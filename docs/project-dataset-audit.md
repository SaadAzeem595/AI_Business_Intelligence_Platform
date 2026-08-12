# Project/Dataset Flow Audit

This document summarizes the current design, identified issues, and the proposed implementation plan for the project-scoped dataset upload and database integration.

---

## 1. Current Flow Analysis

### Backend
1. **Models**:
   - `Dataset` ([backend/app/features/datasets/models.py](file:///d:/AI%20Business%20Intelligence%20Platform/backend/app/features/datasets/models.py)) represents datasets. It includes columns for metadata, schema, and `workspace_id`, but **does not** have a `project_id` or `owner_id`.
   - There is **no Project model** in the backend database.
2. **Endpoints**:
   - `POST /datasets/upload` ([backend/app/features/datasets/router.py](file:///d:/AI%20Business%20Intelligence%20Platform/backend/app/features/datasets/router.py)): Handles global dataset upload and registers CSVs directly in DuckDB using an in-memory cache fallback (`UPLOADED_PATHS_CACHE`) or commits metadata records to Postgres.
   - `GET /datasets`: Returns a list of datasets in the user's workspace, falling back to mock datasets if empty.
   - `GET /datasets/{id}`: Returns details of a specific dataset.
   - There are **no project-scoped dataset upload/listing endpoints** (such as `POST /projects/{id}/datasets` or `GET /projects/{id}/datasets`).
3. **DuckDB Integration**:
   - Dynamic registration is run globally inside `register_all_datasets_in_duckdb` ([backend/app/features/analytics/service.py](file:///d:/AI%20Business%20Intelligence%20Platform/backend/app/features/analytics/service.py)), loading all datasets from the database and cached paths into memory. There is no partitioning or separation of tables by project.

### Frontend
1. **State Management**:
   - The `/projects` page ([src/app/(dashboard)/projects/page.tsx](file:///d:/AI%20Business%20Intelligence%20Platform/src/app/\(dashboard\)/projects/page.tsx)) displays a hardcoded list of projects in React state and is entirely mock.
   - There is **no project-specific detail/dataset page** or scoped upload view. Clicking "Open Workspace" redirect users to `/dashboard`.
   - `useUIStore` ([src/shared/services/uiStore.ts](file:///d:/AI%20Business%20Intelligence%20Platform/src/shared/services/uiStore.ts)) has an `activeProject` string, but it is initialized to a mock name ("Q3 Sales Analytics") and never updated programmatically.
2. **Ingestion Hook**:
   - `useUpload` ([src/features/datasets/hooks/useUpload.ts](file:///d:/AI%20Business%20Intelligence%20Platform/src/features/datasets/hooks/useUpload.ts)) is designed only for global dataset upload. It triggers `DatasetService.upload` to send files to the global `POST /datasets/upload` endpoint.
   - When users are in a mock project workspace context (if any), uploading a file calls the global upload route and does not bind it to a project.

---

## 2. Discovered Problems

1. **Missing Backend Entities**:
   - The database doesn't define or store a `Project` table.
   - The `Dataset` table lacks fields to associate it with a specific project (`project_id`), the user who uploaded it (`owner_id`), or error details (`error_message`).
2. **Missing Endpoints**:
   - There is no project-specific upload endpoint `POST /projects/{project_id}/datasets`.
   - There is no project-specific list endpoint `GET /projects/{project_id}/datasets`.
3. **No Project Authorization**:
   - Because there is no backend representation of projects, ownership and access control cannot be validated.
4. **Mocked UI Navigation**:
   - Clicking on a project in the frontend redirects to the global dashboard rather than opening a project-specific workspace. There is no project database/datasets view.
5. **No Sandbox Separation**:
   - DuckDB registers all datasets globally, meaning queries from Project A can access datasets uploaded in Project B (violating security criteria).

---

## 3. Root Cause of Original Problem

When the user attempts to upload a CSV from a project database/datasets context:
1. The frontend falls back to standard/global uploads since no project-scoped upload endpoint is called, or fails because there is no workspace route context.
2. The UI remains stuck in the "Uploading & parsing..." state because the frontend React Query hook invalidates global dataset list query keys (`["datasets", "list"]`) instead of project-scoped queries, and the backend returns exceptions that might get swallowed or return status 200 with incorrect format.
3. The newly created project is mock only, meaning `project_id` doesn't correspond to any actual entity, leading to failures to query or display files correctly within that project context.

---

## 4. Proposed Fix

### Step A: Define Backend Models
1. Implement a `Project` SQLAlchemy model in `backend/app/features/projects/models.py`.
2. Add new columns (`project_id`, `owner_id`, `original_filename`, `error_message`) to the `Dataset` model.
3. Update the backend startup event in `backend/app/main.py` to:
   - Synchronize/register the `Project` model on startup.
   - Dynamically check and add the new columns to the `datasets` table using SQL `ALTER TABLE` statements (safeguarding existing databases).

### Step B: Implement Projects API Router
1. Create a `projects` router with the following routes:
   - `POST /projects`: Create a new project.
   - `GET /projects`: List current user's projects.
   - `GET /projects/{project_id}`: Retrieve a single project's details.
   - `GET /projects/{project_id}/datasets`: List datasets belonging to a specific project.
   - `POST /projects/{project_id}/datasets`: Upload a file scoped to the project.
2. Implement strict authorization middleware on all routes to verify that `project.owner_id == current_user.id`. Return `404` if the project doesn't exist, and `403` if access is unauthorized.

### Step C: Scoped Ingestion Pipeline
1. Refactor/reuse `DatasetService` to handle ingestion and parsing.
2. When creating the DuckDB view:
   - Sanitize table names by prefixing them with a project identifier (e.g. `project_<project_id>_<sanitized_filename>`) or register them on-demand based on the selected project context to prevent collisions.
   - Dynamically load only authorized datasets in the SQL Playground and AI Chat tools.

### Step D: Frontend Integration
1. Build `useProjects` query and mutation hooks using TanStack Query.
2. Create a dynamic workspace route page at `src/app/(dashboard)/projects/[id]/page.tsx` containing the project detail workspace and a "Database/Datasets" tab with the file upload zone.
3. Update `useDatasets` and `useUpload` hooks to accept an optional `projectId` param and call the dynamic project endpoints.
4. Support clean UI transitions (`idle` -> `uploading` -> `processing` -> `success` / `error`) and invalidate React Query cache correctly.
