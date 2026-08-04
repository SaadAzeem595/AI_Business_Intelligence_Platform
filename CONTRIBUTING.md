# Contributing to AI Business Intelligence Platform

Thank you for your interest in contributing to the AI Business Intelligence Platform! As an open-source project, we welcome contributions from developers, architects, and technical writers of all backgrounds.

---

## Code of Conduct
Please read and adhere to our [Code of Conduct](CODE_OF_CONDUCT.md) in all community interactions.

---

## Local Environment Setup

We recommend developing on Unix-like environments or WSL for Windows.

### Prerequisites
* Python 3.12+
* Node.js 18+ (LTS)
* Docker & Docker Compose
* PostgreSQL & Redis (optional, fallback in-memory cache is active by default)

### Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies using pip:
   ```bash
   pip install -r pyproject.toml
   ```
4. Copy the environment variables template:
   ```bash
   cp .env.example .env
   ```
5. Run migrations and start the backend development server:
   ```bash
   python run.py
   ```

### Frontend Setup
1. Navigate to the root directory:
   ```bash
   npm install
   ```
2. Copy the environment variables:
   ```bash
   cp .env.example .env.local
   ```
3. Start the Next.js development server:
   ```bash
   npm run dev
   ```

---

## Coding Standards

### Python (Backend)
* We use **Ruff** for linting and formatting. Run ruff checks before submitting PRs:
  ```bash
  ruff check app/
  ruff format app/
  ```
* Ensure all functions and parameters are fully typed with **type hints**.
* Write descriptive docstrings adhering to Google Style.

### TypeScript / React (Frontend)
* Use functional React components with appropriate TypeScript typing.
* Run ESLint checks:
  ```bash
  npm run lint
  ```

---

## Pull Request Guidelines

1. **Fork the Repository**: Create a personal fork and branch off `main`.
2. **Write Automated Tests**: Add test cases under `backend/tests/` or frontend test configs validating your implementation.
3. **Verify All Tests Pass**:
   ```bash
   pytest
   ```
4. **Keep Commits Clean**: Use descriptive commit messages following the Conventional Commits style (`feat:`, `fix:`, `docs:`, `refactor:`).
5. **Open a PR**: Submit your PR targeting the `main` branch. Provide a detailed description of changes, screenshots for UI changes, and test results.
