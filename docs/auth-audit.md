# Authentication Audit & Clerk Migration Strategy

This document details the audit of the existing authentication system in the **AI Business Intelligence Platform (DataPilot AI)** and outlines the strategy for migrating to **Clerk** as the production authentication provider.

---

## Part 1: Current Authentication Audit

### A. Existing Authentication System
The application currently uses a **simulated/mock JWT & RBAC authentication system**:
- **Frontend**: The `useAuth` hook (`src/features/auth/hooks/useAuth.ts`) uses `AuthService` (`src/features/auth/services/auth.service.ts`) to communicate with the mock auth endpoints. Session metadata and tokens (`accessToken` and `refreshToken`) are manually stored in the browser's `localStorage`.
- **API Client**: The Axios client (`src/shared/api/client.ts`) intercepts outgoing requests, extracts the JWT `accessToken` from `localStorage`, and appends it to the `Authorization` header as a Bearer token. It also intercepts `401 Unauthorized` responses to attempt a refresh cycle using the stored `refreshToken`.
- **Backend**: The backend is built using FastAPI. A mock authentication router (`backend/app/features/auth/router.py`) handles request parameters for `/login`, `/register`, `/refresh`, `/me`, and `/logout`.
- **Security Check**: The backend dependency `get_current_user` in `backend/app/core/dependencies.py` authenticates requests via:
  1. Dev Auth Bypass (`settings.DEV_AUTH_BYPASS`).
  2. API Key verification (`X-API-Key` header).
  3. Custom JWT token decoding (HS256).
  It then returns a `MockUser` Pydantic model representation of the user context.

### B. Where JWT Tokens are Created
- JWT tokens are created in `backend/app/features/auth/service.py` using `AuthService.create_access_token` and `AuthService.create_refresh_token`.
- The tokens are signed using a symmetric **HS256** algorithm against a single server secret key (`settings.SECRET_KEY`).

### C. Where JWT Tokens are Verified
- JWT tokens are verified in the FastAPI backend inside the `get_current_user` dependency (`backend/app/core/dependencies.py`).
- The validation is performed via `jose.jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])`.

### D. How the Frontend Sends Credentials
- During authentication requests (login/signup), credentials are submitted as form-urlencoded parameters (`username`, `password`, `email`, `name`).
- For all other resource endpoints, the Axios request interceptor (`src/shared/api/client.ts`) automatically sets the header:
  `Authorization: Bearer <accessToken>`

### E. Which Endpoints Require Authentication
Nearly all feature routes are protected under the `Depends(get_current_user)` dependency:
- **Datasets**: `/api/v1/datasets/*`
- **Analytics**: `/api/v1/analytics/*`
- **AI Chat**: `/api/v1/chat/*`
- **RAG**: `/api/v1/rag/*`
- **ML Platform**: `/api/v1/ml/*`
- **Executive Reports**: `/api/v1/reports/*`
- **Settings**: `/api/v1/settings/*`
- **Agents**: `/api/v1/agents/*`

### F. Which Endpoints Use Roles
Currently, Role-Based Access Control (RBAC) checks (`require_role`) are defined as a helper dependency in `backend/app/core/dependencies.py`, but they are **only utilized in test suites** (`backend/tests/test_production.py` and `backend/tests/test_dev_auth_bypass.py`). They are not active in the production routers.

### G. Mock/Developer Authentication
Yes, developer authentication bypass exists:
- Enabled via setting `settings.DEV_AUTH_BYPASS = True` (only validated in non-production environments).
- When active, `get_current_user` automatically returns a default mock user (`developer@datapilot.com`, role `Admin`, name `Saad A.`) without requiring any headers.

### H. Potential Conflicts with Clerk Integration
1. **Token Lifetime and Refresh**: Clerk handles token refreshing client-side automatically. The custom Axios refresh interceptor will conflict with Clerk's built-in session management.
2. **Token Format/Signature**: Clerk tokens are signed using **RS256** against a private key. The backend must retrieve Clerk's public JSON Web Key Set (JWKS) to verify signatures instead of decoding symmetric HS256 tokens.
3. **User Record Synchronization**: Currently, the backend does not store session details or associate operations with a persistent database user. We must map the Clerk user ID (`clerk_user_id`) to a local database user and establish default roles.
4. **UI Duplication**: The existing `/login` and `/register` routes will conflict with Clerk's `/sign-in` and `/sign-up` UI paths.

---

## Part 2: Proposed Clerk Migration Strategy

We will integrate Clerk as the production authentication provider while preserving the existing FastAPI backend, database models, RAG pipeline, and ML engines.

### 1. Environment Configuration
Add Clerk variables to environment configurations:
- **Frontend (`.env`)**:
  - `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`: Clerk Publishable Key.
  - `NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in`
  - `NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up`
  - `NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/dashboard`
  - `NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/dashboard`
- **Backend (`backend/.env`)**:
  - `CLERK_SECRET_KEY`: Clerk API secret key.
  - `CLERK_JWKS_URL`: URL to Clerk's public JSON Web Key Set (JWKS) to fetch keys.

### 2. Frontend Integration (Next.js)
1. **Package Installation**: Install `@clerk/nextjs` (version compatible with React 19 and Next.js 16.2.12).
2. **Root Layout**: Wrap the Next.js app in `<ClerkProvider>` inside `src/app/layout.tsx`.
3. **Middleware**: Implement `src/middleware.ts` using Clerk's `clerkMiddleware` to protect app routes (e.g., `/dashboard`, `/datasets`, `/chat`, `/sql`, etc.) and leave `/`, `/sign-in`, `/sign-up` public.
4. **Auth Pages**: Replace `/login` and `/register` with `/sign-in` and `/sign-up` using Clerk's `<SignIn />` and `<SignUp />` components.
5. **User Menu**: Update the custom `UserMenu.tsx` component to leverage the `useUser` and `useClerk` hooks from Clerk to display the authenticated user's name, email, avatar, and invoke `signOut()`.
6. **Axios Client**: Refactor `apiClient` interceptors in `src/shared/api/client.ts` to fetch Clerk's short-lived session token dynamically using the Clerk JavaScript SDK on each request. Remove local storage JWT tokens and the manual refresh interceptor.

### 3. Backend Verification (FastAPI)
1. **Update User Table**: Update `backend/app/features/auth/models.py` to add `clerk_user_id` (String, unique, indexed) and `role` (String, default `"Viewer"`).
2. **Clerk JWT Verification**: Implement public key validation (RS256) inside `backend/app/core/dependencies.py`:
   - Fetch the JWKS from Clerk (with caching and key rotation verification).
   - Validate token expiration (`exp`), issuer (`iss`), and signatures.
3. **Local User Sync**:
   - Extract the user's email, name, and Clerk ID from the verified token payload.
   - Look up the user in the local database. If not found, create a new local user record with a default role of `"Viewer"`.
   - Map this to the current user context.
4. **Preserve API Key Auth**: Maintain API Key authentication (`X-API-Key`) for programmatic/M2M clients.

### 5. Verification Plan
- **Backend Unit Tests**: Update test suite to mock Clerk token verification and test RBAC role restrictions (Admin, Analyst, Viewer).
- **Frontend Integration**: Test sign-in/sign-up flows, Axios header injection, route protection, and dataset queries.
