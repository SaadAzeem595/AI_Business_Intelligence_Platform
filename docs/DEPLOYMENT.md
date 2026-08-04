# Production Deployment Guide

This guide details the procedures for deploying the AI Business Intelligence Platform to various cloud infrastructure providers: Railway, Render, Microsoft Azure, and Docker Compose.

---

## 📋 Environment Variables Reference

Configure these environmental variables in your target deployment environments.

### Database Settings
* `POSTGRES_SERVER`: Hostname of the PostgreSQL server database (e.g. `db.railway.internal`).
* `POSTGRES_USER`: Database username.
* `POSTGRES_PASSWORD`: Database password.
* `POSTGRES_DB`: Target database name (e.g. `ai_bi_db`).
* `POSTGRES_PORT` (Default: `5432`): Connection port.

### Redis Cache & Broker Settings
* `REDIS_HOST`: Hostname of the Redis instance.
* `REDIS_PORT` (Default: `6379`): Redis connection port.

### Security Configurations
* `SECRET_KEY`: Cryptographically secure random string used to sign JWT tokens. Keep this private.
* `API_KEY`: Enterprise platform credential used to authorize automation clients.
* `RATE_LIMIT_PER_MINUTE` (Default: `100`): Sliding-window limit check count.
* `ALLOWED_ORIGINS`: Commas-separated list of allowed origins (e.g. `https://my-dashboard.com,https://api.my-dashboard.com`).

---

## 🚂 Deploying to Railway

Railway is a modern PaaS ideal for deploying full-stack Docker services.

### Steps
1. **Provision Databases**:
   * Click **New Project** -> **Provision PostgreSQL**.
   * Click **Add Service** -> **Provision Redis**.
2. **Deploy Backend Service**:
   * Click **Add Service** -> **Github Repository** -> select your project fork.
   * Go to **Settings** -> set **Root Directory** = `backend`.
   * Under **Variables**, click **Reference variables** to automatically bind:
     * `POSTGRES_SERVER` to `${{Postgres.DATABASE_URL}}`
     * `REDIS_HOST` to `${{Redis.REDIS_HOST}}`
     * `REDIS_PORT` to `${{Redis.REDIS_PORT}}`
3. **Deploy Celery Worker**:
   * Add a duplicate backend service pointing to the same repository.
   * Go to **Settings** -> set **Start Command** = `celery -A app.worker.celery_app worker --loglevel=info`.
4. **Deploy Next.js Frontend**:
   * Add a service pointing to the repository root directory.
   * Add environment variable: `NEXT_PUBLIC_API_URL` pointing to your deployed backend URL.

---

## ☁️ Deploying to Render

Render provides robust container deployment services.

### Steps
1. **Setup Database Instances**:
   * Create a **New PostgreSQL** instance. Copy the connection credentials.
   * Create a **New Redis** instance. Copy the connection string.
2. **Deploy Backend (FastAPI Web Service)**:
   * Create a **New Web Service** pointing to the repository.
   * Specify **Root Directory** = `backend`.
   * Set **Environment** = `Docker`.
   * Add the required PostgreSQL and Redis environment variables.
3. **Deploy Frontend (Next.js)**:
   * Create a **New Static Site** or **New Web Service** for server-side features.
   * Set **Build Command** = `npm run build`.
   * Set **Start Command** = `npm run start`.
   * Set `NEXT_PUBLIC_API_URL` to the URL of the Backend Web Service.

---

## 🔷 Deploying to Microsoft Azure

Azure Container Apps (ACA) is the recommended path for enterprise scaling.

### Steps
1. **Create Resource Group**:
   ```bash
   az group create --name ai-bi-platform-rg --location eastus
   ```
2. **Provision Database Instances**:
   * Deploy **Azure Database for PostgreSQL flexible server**.
   * Deploy **Azure Cache for Redis** standard tier.
3. **Build and Push Container Images**:
   * Create an **Azure Container Registry (ACR)**.
   * Build the Docker image locally and push:
     ```bash
     az acr build --registry myregistry --image ai-bi-backend:latest ./backend
     ```
4. **Deploy ACA (Container App)**:
   * Deploy the API container container app mapping ingress port `8000`.
   * Bind secrets matching database connection strings.
   * Deploy a separate container app without ingress running the Celery worker command.

---

## 🐳 Deploying via Docker Compose

For quick on-premise setups:

1. Copy backend environment variables template:
   ```bash
   cp backend/.env.example backend/.env
   ```
2. Edit `backend/.env` with your secure custom values.
3. Build and launch services in detached mode:
   ```bash
   make docker-up
   ```
4. Stop all services and clean database volumes:
   ```bash
   make docker-down
   ```
