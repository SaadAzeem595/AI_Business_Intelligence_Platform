# ==============================================================================
# AI Business Intelligence Platform - Unified Commands Interface (Makefile)
# ==============================================================================

ifeq ($(OS),Windows_NT)
    PYTHON = .venv\Scripts\python
    PIP = .venv\Scripts\pip
    PYTEST = .venv\Scripts\pytest
    RUFF = .venv\Scripts\ruff
    RM_DIR = rmdir /s /q
else
    PYTHON = .venv/bin/python
    PIP = .venv/bin/pip
    PYTEST = .venv/bin/pytest
    RUFF = .venv/bin/ruff
    RM_DIR = rm -rf
endif

.PHONY: install dev dev-frontend dev-backend test lint format docker-up docker-down clean help

help:
	@echo "Available commands:"
	@echo "  make install        - Install dependencies for both frontend and backend"
	@echo "  make dev            - Run Next.js frontend and FastAPI backend concurrently"
	@echo "  make dev-frontend   - Run Next.js frontend local development server"
	@echo "  make dev-backend    - Run FastAPI backend local development server"
	@echo "  make test           - Run all backend unit, integration, and security tests"
	@echo "  make lint           - Run lint scans (Frontend ESLint & Backend Ruff)"
	@echo "  make format         - Auto-format Python backend files using Ruff"
	@echo "  make docker-up      - Run Docker Compose multi-container services with build"
	@echo "  make docker-down    - Tear down Docker Compose services and clean volumes"
	@echo "  make clean          - Remove python caches, artifacts, and logs"

install:
	@echo "==> Installing Next.js frontend dependencies..."
	npm install
	@echo "==> Installing FastAPI backend dependencies..."
	cd backend && pip install -r pyproject.toml

dev:
	@echo "==> Starting local development services concurrently..."
	@echo "To run separately, use 'make dev-backend' and 'make dev-frontend'"
	@make -j 2 dev-backend dev-frontend

dev-frontend:
	npm run dev

dev-backend:
	cd backend && $(PYTHON) run.py

test:
	cd backend && $(PYTHON) -m pytest

lint:
	@echo "==> Linting Next.js frontend..."
	npm run lint
	@echo "==> Checking Python backend coding standards..."
	cd backend && $(RUFF) check app/

format:
	@echo "==> Reformatting Python files..."
	cd backend && $(RUFF) format app/

docker-up:
	cd backend && docker compose up --build -d

docker-down:
	cd backend && docker compose down -v

clean:
	@echo "==> Cleaning Python environment cache folders..."
	cd backend && $(RM_DIR) .pytest_cache || true
	cd backend && $(RM_DIR) app\__pycache__ || true
	cd backend && $(RM_DIR) app\core\__pycache__ || true
	cd backend && $(RM_DIR) app\features\auth\__pycache__ || true
	cd backend && $(RM_DIR) app\features\analytics\__pycache__ || true
	cd backend && $(RM_DIR) app\features\analytics\engine\__pycache__ || true
	cd backend && $(RM_DIR) app\features\chat\__pycache__ || true
	cd backend && $(RM_DIR) app\features\datasets\__pycache__ || true
	cd backend && $(RM_DIR) app\features\ml\__pycache__ || true
	cd backend && $(RM_DIR) app\features\rag\__pycache__ || true
	cd backend && $(RM_DIR) app\features\rag\retrieval\__pycache__ || true
	cd backend && $(RM_DIR) app\features\reports\__pycache__ || true
	cd backend && $(RM_DIR) app\features\settings\__pycache__ || true
	cd backend && $(RM_DIR) app\features\agents\__pycache__ || true
