# DataPilot AI

> **AI-Powered Business Intelligence, Analytics & Executive Intelligence Platform**
>
> Turn business datasets and organizational knowledge into verified analytics, natural-language answers, forecasts, customer segments, anomaly detection, and executive-ready reports.

[![Frontend](https://img.shields.io/badge/Frontend-Next.js%20%2B%20React-blue)](https://nextjs.org/)
[![Backend](https://img.shields.io/badge/Backend-FastAPI-009688)](https://fastapi.tiangolo.com/)
[![Language](https://img.shields.io/badge/Language-Python%20%2B%20TypeScript-yellow)](https://www.python.org/)
[![Analytics](https://img.shields.io/badge/Analytics-DuckDB-yellow)](https://duckdb.org/)
[![AI](https://img.shields.io/badge/AI-LangGraph%20%2B%20LLMs-orange)](https://www.langchain.com/langgraph)
[![Cloud](https://img.shields.io/badge/Cloud-Azure%20Container%20Apps-0078D4)](https://azure.microsoft.com/products/container-apps)
[![Registry](https://img.shields.io/badge/Registry-Azure%20Container%20Registry-0078D4)](https://azure.microsoft.com/products/container-registry)
[![Billing](https://img.shields.io/badge/Billing-Stripe-635BFF)](https://stripe.com/)

---

## 1. What is DataPilot AI?

**DataPilot AI** is a full-stack AI Business Intelligence SaaS application built to help organizations move from raw business data to evidence-backed business intelligence.

Instead of requiring an analyst to manually move between CSV/Excel files, SQL tools, Python notebooks, dashboards, forecasting scripts, segmentation workflows, anomaly detection tools, document repositories, and presentation software, DataPilot AI brings these workflows into a single project-oriented platform.

The platform is designed around one central principle:

> **Deterministic systems calculate facts; retrieval systems provide evidence; AI orchestrates and explains verified context.**

This architecture is particularly important for business analytics because an LLM should not invent a revenue number, silently calculate an order count incorrectly, or turn an order count into a different business metric.

### Typical workflow

```text
                 BUSINESS DATA
                      |
          +-----------+-----------+
          |                       |
          v                       v
     Structured Data        Business Documents
          |                       |
          v                       v
       Profiling              RAG Ingestion
          |                       |
          v                       v
        DuckDB             BM25 + Dense Search
          |                       |
          +-----------+-----------+
                      |
                      v
              AI / Analytics Layer
                      |
        +-------------+-------------+
        |       |       |       |    |
        v       v       v       v    v
       SQL  Forecast Segment Anomaly RAG
        |       |       |       |    |
        +-------+-------+-------+----+
                      |
                      v
             Executive Intelligence
                      |
                      v
              PDF / PPTX / HTML
```

---

# 2. Live Application

### Production frontend

**DataPilot AI:**

https://datapilot-web.ashyriver-d1eb08b9.uaenorth.azurecontainerapps.io/

### Production backend

**DataPilot API:**

https://datapilot-api.ashyriver-d1eb08b9.uaenorth.azurecontainerapps.io/

API prefix:

```text
/api/v1
```

> These are the current deployment URLs. Azure Container Apps URLs can change when infrastructure is recreated or domains are replaced.

---

# 3. Main Product Modules

DataPilot AI currently organizes the platform around the following major workflows:

```text
Dashboard
Projects
Datasets
AI Chat
Forecasting
Segmentation
Anomaly Detection
SQL Playground
Knowledge Base
Executive Reports
Settings / Billing
```

Each module is intended to consume the same project-scoped data and authorization context rather than operating as isolated demo features.

---

## 3.1 Dashboard

The Dashboard provides the executive starting point for a project.

Typical metrics include:

- Total Revenue
- Total Orders
- Average Order Value
- Freight / Delivery Value
- Period-over-period changes
- Business trends
- Connected analytical modules
- Project-level performance indicators

The Dashboard is not intended to be a collection of hardcoded values. KPIs should be derived from the active project's actual datasets and analytical services.

---

## 3.2 Projects

Projects provide the primary analytical isolation boundary.

A project can contain:

- Datasets
- Relational dataset views
- Knowledge Base documents
- AI conversations
- SQL analyses
- Forecasting results
- Segmentation results
- Anomaly results
- Executive reports

The project context is propagated through the backend so that a user working on one project does not accidentally retrieve or analyze data belonging to another project.

---

## 3.3 Dataset Management

DataPilot AI is designed to work with real business datasets rather than demo records.

Supported data sources can include:

- CSV
- XLSX / Excel
- Structured relational views
- Project-level analytical datasets

The ingestion pipeline is conceptually:

```text
Upload
  |
  v
Validation
  |
  v
Parsing
  |
  v
Schema Detection
  |
  v
Data Profiling
  |
  v
Type / Feature Detection
  |
  v
Project Registration
  |
  v
DuckDB / Analytical View
  |
  +-------------------------------+
  |               |               |
  v               v               v
SQL           Forecasting     Segmentation
```

The profiler can identify useful properties such as:

- Numeric columns
- Categorical columns
- Identifiers
- Dates / timestamps
- Boolean columns
- Text columns
- Missing values
- Cardinality
- Potential analytical features

---

# 4. AI Chat

AI Chat provides a natural-language interface over project data and project knowledge.

Example questions:

```text
What were total orders last month?

Which product categories generated the most revenue?

What is the average order value?

Which customer groups are the most valuable?

What does total_order_value mean according to our business dictionary?

Why was there an unusual sales spike?
```

The application should route questions to the appropriate source.

### Exact numerical question

```text
User
 |
 v
Query understanding
 |
 v
SQL / DuckDB
 |
 v
Verified result
 |
 v
LLM explanation
```

### Knowledge / definition question

```text
User
 |
 v
Query understanding
 |
 v
Hybrid RAG
 |
 v
Retrieved evidence
 |
 v
Grounded answer
```

### Mixed question

```text
User
 |
 v
Planner / Router
 |
 +--------------------+
 |                    |
 v                    v
DuckDB               RAG
 |                    |
 +----------+---------+
            |
            v
      Verified context
            |
            v
      AI synthesis
```

The purpose of this separation is to prevent the language model from being treated as the authoritative calculator.

---

# 5. Semantic Search & RAG

The Knowledge Base provides project-scoped semantic search and source-grounded answers.

The system can ingest supported documents such as:

- PDF
- DOCX
- TXT
- CSV
- XLSX
- PPTX
- HTML
- JSON
- Markdown

### RAG pipeline

```text
Document
   |
   v
Parser / Extractor
   |
   v
Text + Table Extraction
   |
   v
Chunking
   |
   v
Metadata Enrichment
   |
   +---------------------+
   |                     |
   v                     v
BM25 Index          Embedding Index
   |                     |
   +----------+----------+
              |
              v
        Hybrid Retrieval
              |
              v
       Reciprocal Rank Fusion
              |
              v
             Top-K
              |
              v
      Retrieved Evidence
              |
              v
       Grounded Generation
```

### Hybrid retrieval

The retrieval engine combines:

- BM25 / keyword retrieval
- Dense vector retrieval
- Reciprocal Rank Fusion (RRF)
- Project/document metadata
- Top-K limits

This allows the system to handle both exact terms and semantically similar language.

### Grounded-answer behavior

If the indexed documents do not contain enough evidence, the application should return an insufficient-evidence response rather than hallucinating.

For example:

```text
Question:
Who founded Olist according to olist_orders_dataset.csv?

Expected behavior:
The indexed document does not contain enough information to answer that reliably.
```

---

# 6. SQL Playground

The SQL Playground provides direct analytical querying over project data.

The main analytical engine is **DuckDB**, which is designed for analytical SQL workloads and is well suited to local and embedded data analysis.

Example:

```sql
SELECT
    order_status,
    COUNT(*) AS order_count
FROM orders
GROUP BY order_status
ORDER BY order_count DESC;
```

SQL is particularly important for questions requiring exact values:

```text
How many orders were delivered?
What is total revenue?
What is average order value?
How many customers purchased in 2018?
```

The system should prefer deterministic SQL/DuckDB execution for these questions rather than asking an LLM to estimate the answer.

---

# 7. Forecasting Engine

The Forecasting module converts historical time-based data into future projections.

The system is designed to dynamically detect and normalize timestamp/date columns instead of assuming one hardcoded timestamp format.

Potential input formats include:

- ISO timestamps
- Date-only values
- `DD/MM/YYYY`
- `DD/MM/YYYY HH:MM`
- timezone-aware values
- numeric epoch timestamps where supported
- mixed values when safely parseable

### Forecasting pipeline

```text
Dataset
   |
   v
Timestamp Candidate Detection
   |
   v
Format Detection / Parsing
   |
   v
Canonical TIMESTAMP
   |
   v
Time-Series Aggregation
   |
   v
Data Sufficiency Validation
   |
   v
Model Selection
   |
   v
Cross-Validation / Evaluation
   |
   v
Forecast + Confidence Interval
   |
   v
Visualization
   |
   v
Executive Report
```

Possible statistical forecasting methods include ARIMA and Prophet depending on the actual implementation and suitability of the dataset.

A forecast result should contain structured metadata such as:

```text
target metric
source dataset
time column
normalized frequency
historical observations
forecast horizon
forecast values
confidence interval
model
model evaluation information
```

This structured result can then be reused by the Executive Reports module.

---

# 8. Customer & Tabular Segmentation

Segmentation discovers groups in structured business data.

The system can dynamically identify:

- Identifier fields
- Numeric features
- Categorical features
- Boolean fields
- Date/time fields
- Text fields

Identifiers should not automatically become clustering features because a unique ID normally carries no meaningful similarity information.

### RFM customer segmentation

For customer datasets, the platform can derive:

```text
Recency
Frequency
Monetary Value
```

### Segmentation pipeline

```text
Dataset
   |
   v
Entity Detection
   |
   v
Feature Detection
   |
   v
Feature Cleaning
   |
   v
Encoding / Scaling
   |
   v
Candidate Cluster Evaluation
   |
   v
K-Means / Configured Algorithm
   |
   v
Cluster Statistics
   |
   v
Business Interpretation
```

Persona labels should be based on actual cluster statistics rather than invented descriptions.

---

# 9. Anomaly Detection

Anomaly Detection identifies unusual patterns in business data.

Potential use cases:

- Revenue spikes
- Revenue drops
- Order-volume anomalies
- Product anomalies
- Customer behavior anomalies
- Time-series outliers
- Unexpected category behavior

Conceptually:

```text
Historical Data
      |
      v
Feature / Metric Construction
      |
      v
Anomaly Algorithm
      |
      v
Outlier Detection
      |
      v
Deviation / Severity
      |
      v
Business Interpretation
```

An anomaly statement included in an executive report should point back to the analytical result that produced it.

---

# 10. Executive Intelligence & Reports

Executive Reports are the final synthesis layer of the platform.

A report can combine:

- Dashboard KPIs
- SQL / DuckDB facts
- Forecasting
- Segmentation
- Anomaly Detection
- Knowledge Base / RAG evidence
- AI-generated narrative
- Business impact
- Recommendations
- Source citations

### Report pipeline

```text
Dashboard KPIs
      |
SQL / DuckDB
      |
Forecasting
      |
Segmentation
      |
Anomaly Detection
      |
RAG / Business Dictionary
      |
      v
Report Context Builder
      |
      v
Fact / Semantic Validation
      |
      v
AI Narrative Generation
      |
      v
Evidence Binding
      |
      v
Executive Report
      |
      +-----------+-----------+
      |           |           |
      v           v           v
     PDF         PPTX        HTML
```

### Anti-hallucination rule

The report engine must preserve the semantic meaning of every metric.

For example, if SQL produces:

```text
Total Orders = 98,666
```

the report must never reinterpret that value as:

```text
Operating Margin = 98,666
```

A typed metric model should carry information such as:

```text
metric_name
metric_value
unit
business_definition
source_type
source_id
period
query/model metadata
```

---

# 11. Evidence & Source Citations

Reports and RAG answers can use source identifiers such as:

```text
[SRC-SQL-1]
[SRC-KPI-1]
[SRC-FC-1]
[SRC-SEG-1]
[SRC-ANOM-1]
[SRC-RAG-DICT]
```

The purpose is to allow a user to trace an important statement back to the analytical or knowledge source.

Example:

```text
Total Orders: 98,666

Source: [SRC-SQL-1]
DuckDB analytical query
```

---

# 12. AI Agent Architecture

The application uses an agent-oriented design for complex analytical requests.

The architecture can include the following specialized roles:

```text
Planner
Router
SQL Agent
Analytics Agent
ML Agent
Forecast Agent
RAG Agent
Visualization Agent
Recommendation Agent
Executive Report Agent
Response Synthesizer
```

A complex request can follow:

```text
User Query
    |
    v
  Planner
    |
    v
  Router
    |
    +----------+----------+----------+
    |          |          |          |
    v          v          v          v
   SQL      Analytics    RAG     Forecast
    |          |          |          |
    +----------+----------+----------+
               |
               v
          Verification
               |
               v
       Response Synthesizer
               |
               v
          User Answer
```

### Architectural rule

> **Agents orchestrate tools. Tools produce authoritative facts.**

This makes it possible to use AI without making the LLM the source of truth for deterministic business calculations.

---

# 13. Technology Stack

## Frontend

| Technology | Purpose |
|---|---|
| Next.js | Full-stack React web framework / application shell |
| React | Component-based UI |
| TypeScript | Static typing |
| Tailwind CSS | Utility-first styling |
| shadcn/ui | Reusable UI components |
| Axios | HTTP/API communication |
| TanStack React Query | Server-state management where used |
| Zustand | Client-side state where used |
| Recharts | Charts and business visualizations |
| Framer Motion | UI animation where used |
| Zod | Runtime validation where used |

## Backend

| Technology | Purpose |
|---|---|
| Python | AI, analytics and backend implementation |
| FastAPI | REST API |
| Pydantic | Request/response validation |
| PostgreSQL | Application and relational persistence where configured |
| asyncpg | Async PostgreSQL connectivity |
| DuckDB | Analytical SQL engine |
| Celery | Background processing where configured |
| Redis | Cache/task infrastructure where configured |
| OpenTelemetry | Observability/tracing |
| Sentry | Error monitoring |

## AI / ML / RAG

| Technology | Purpose |
|---|---|
| LangGraph | Agent/workflow orchestration |
| OpenRouter | Unified LLM API/model routing |
| BM25 | Lexical retrieval |
| Dense embeddings | Semantic retrieval |
| RRF | Hybrid retrieval fusion |
| ARIMA | Statistical forecasting where selected |
| Prophet | Forecasting where selected/configured |
| K-Means | Customer/tabular clustering where selected |
| OCR / document parsers | Document ingestion |

## DevOps / Cloud

| Technology | Purpose |
|---|---|
| Git | Version control |
| GitHub | Source repository and collaboration |
| Docker | Containerization |
| Azure Container Registry | Private container image registry |
| Azure Container Apps | Production container runtime |
| Azure | Cloud infrastructure |
| GitHub Actions | CI/CD where configured |

## SaaS / Payments

| Technology | Purpose |
|---|---|
| Stripe Checkout | Subscription checkout |
| Stripe Billing | Recurring subscription billing |
| Stripe Customer Portal | Customer billing management |
| Stripe Webhooks | Server-side subscription synchronization |

---

# 14. External APIs & Services

## 14.1 OpenRouter API

DataPilot AI can use OpenRouter as its LLM gateway. OpenRouter provides an OpenAI-compatible API endpoint and a unified interface to many models/providers. The documented chat endpoint is:

```text
POST https://openrouter.ai/api/v1/chat/completions
```

The API uses bearer authentication with an OpenRouter API key.

Official documentation:

https://openrouter.ai/docs/quickstart

https://openrouter.ai/docs/api/api-reference/chat/send-chat-completion-request

### Typical DataPilot flow

```text
DataPilot Backend
      |
      v
OpenRouter API
      |
      v
Selected LLM / Provider
      |
      v
AI response
      |
      v
Validation / synthesis
      |
      v
DataPilot user
```

The OpenRouter key must remain server-side and must never be exposed in `NEXT_PUBLIC_*` variables.

---

## 14.2 Stripe API

Stripe provides the billing infrastructure for paid DataPilot plans.

Typical flow:

```text
User
 |
 v
Pricing Page
 |
 v
Backend Checkout Endpoint
 |
 v
Stripe Checkout
 |
 v
Payment
 |
 v
Stripe Webhook
 |
 v
Backend Subscription Record
 |
 v
Entitlement Service
 |
 v
Feature Access
```

Stripe documentation:

https://docs.stripe.com/

https://docs.stripe.com/api/subscriptions/create

### Important security rule

A successful browser redirect must not be the authoritative source for granting a paid plan.

The backend should grant paid entitlements after validating Stripe webhook events and updating the application's subscription state.

---

# 15. Internal API Architecture

The backend exposes versioned REST endpoints under:

```text
/api/v1
```

Representative endpoint groups include:

```text
/api/v1/projects
/api/v1/datasets
/api/v1/analytics
/api/v1/forecasting
/api/v1/segmentation
/api/v1/anomaly
/api/v1/rag
/api/v1/reports
/api/v1/billing
```

The exact route names and request schemas should be treated as repository implementation details and verified from the current OpenAPI schema rather than copied blindly into integrations.

### Billing endpoints designed for the platform

```text
POST /api/v1/billing/checkout
POST /api/v1/billing/portal
POST /api/v1/billing/webhook
GET  /api/v1/billing/subscription
GET  /api/v1/billing/usage
```

---

# 16. Authentication & Authorization

Protected API resources should require authentication.

Authorization should be evaluated at the server for:

```text
User
  |
  v
Workspace
  |
  v
Project
  |
  v
Dataset / Document
  |
  v
Report / Export
```

The browser should never be trusted to supply an arbitrary user, workspace, project, or subscription identifier.

### Protected report exports

A report download endpoint must preserve the same authentication context used by the rest of the application. Opening a private API URL directly in a new browser tab can result in an HTTP 401 if the authentication mechanism is not automatically attached to that navigation request.

A production frontend should therefore use its authenticated HTTP client/fetch mechanism to request protected files and then create a client-side download from the authenticated response.

---

# 17. SaaS Pricing Plans

The current product concept uses three plans.

## Starter — $0/month

Designed for:

- Individual analysts
- Students
- Evaluation
- Small-scale experimentation

Example included capabilities:

- 1 active dataset file
- Basic SQL Playground
- Standard AI Chat queries
- Core analytics

### Starter positioning

The Starter plan lowers the barrier to trying the platform and gives an individual user enough functionality to understand the product's value.

---

## Growth — $79/month

Designed for:

- Growing businesses
- Professional analysts
- Managers
- Small teams
- Organizations that need predictive analytics

Included capabilities:

- Unlimited dataset uploading
- Advanced Forecasting
- Outlier / Anomaly analysis
- Scheduled Executive PDF reports
- Shared team collaboration spaces
- Expanded AI/analytics capabilities

### Growth positioning

The Growth plan is intended to convert organizations that have moved from experimentation to recurring business use.

---

## Enterprise — Custom

Designed for larger organizations requiring additional controls and integrations.

Potential capabilities include:

- Custom integrations
- SSO
- SAML
- Audit capabilities
- Dedicated analytics scaling
- Enterprise support arrangements
- Custom security/networking requirements
- Larger workloads

Enterprise capabilities and SLA terms should be defined by the actual commercial contract rather than assumed by the application.

---

# 18. Subscription & Entitlement Architecture

The backend should maintain a subscription state similar to:

```text
subscription_id
workspace_id
stripe_customer_id
stripe_subscription_id
stripe_price_id
plan
status
current_period_start
current_period_end
cancel_at_period_end
created_at
updated_at
```

A centralized entitlement service can expose concepts such as:

```text
getWorkspacePlan()
hasFeature()
checkDatasetLimit()
getPlanEntitlements()
```

Example denial response:

```json
{
  "code": "FEATURE_NOT_AVAILABLE",
  "feature": "scheduled_reports",
  "current_plan": "starter",
  "required_plan": "growth"
}
```

Example dataset limit response:

```json
{
  "code": "PLAN_LIMIT_REACHED",
  "feature": "active_datasets",
  "current": 1,
  "limit": 1,
  "required_plan": "growth"
}
```

Server-side enforcement is required. UI buttons are only presentation; they are not security controls.

---

# 19. Complete System Architecture

```text
                                 +----------------------+
                                 |       END USER       |
                                 +----------+-----------+
                                            |
                                          HTTPS
                                            |
                                            v
                         +-------------------------------------+
                         |         NEXT.JS FRONTEND            |
                         | React / TypeScript / Tailwind       |
                         | shadcn/ui / Recharts / Axios        |
                         +----------------+--------------------+
                                          |
                                          v
                         +-------------------------------------+
                         |            FASTAPI API              |
                         | Auth / RBAC / Projects / Datasets   |
                         | Analytics / Reports / Billing       |
                         +----------------+--------------------+
                                          |
              +---------------------------+---------------------------+
              |                           |                           |
              v                           v                           v
     +------------------+       +------------------+        +------------------+
     |   PostgreSQL     |       |     DuckDB       |        | Redis / Workers  |
     | App Persistence  |       | Analytics Engine |        | Cache / Jobs     |
     +------------------+       +---------+--------+        +------------------+
                                         |
                        +----------------+----------------+
                        |                |                |
                        v                v                v
                  +-----------+   +-----------+   +-----------+
                  | Forecast  |   | Segment   |   | Anomaly   |
                  +-----------+   +-----------+   +-----------+
                        |                |                |
                        +----------------+----------------+
                                         |
                                         v
                               +-------------------+
                               |   LangGraph AI    |
                               | Planner / Router   |
                               | Specialized Agents|
                               +---------+---------+
                                         |
                       +-----------------+-----------------+
                       |                 |                 |
                       v                 v                 v
                 +-----------+     +-----------+     +-----------+
                 | OpenRouter|     | RAG Engine |     | SQL Tools |
                 | LLM API   |     | BM25+Dense |     | DuckDB    |
                 +-----------+     +-----------+     +-----------+
                       |                 |
                       v                 v
                 LLM generation     Evidence retrieval
                       |                 |
                       +--------+--------+
                                |
                                v
                       +--------------------+
                       | Validation /       |
                       | Response Synthesis |
                       +----------+---------+
                                  |
                                  v
                       +--------------------+
                       | Executive Reports  |
                       | PDF / PPTX / HTML  |
                       +--------------------+

                 BILLING PATH

User -> DataPilot Pricing -> Stripe Checkout
                         -> Stripe Webhook
                         -> Backend Subscription State
                         -> Entitlement Service
                         -> Feature Access

                 CLOUD PATH

GitHub -> Docker Build -> Azure Container Registry
                              |
                              v
                    Azure Container Apps
                              |
                              +--> Frontend Container
                              |
                              +--> Backend Container
```

---

# 20. Data Flow: From CSV to Executive Report

This is one of the most important end-to-end flows in the application.

```text
1. User uploads CSV
        |
        v
2. Backend validates file
        |
        v
3. Schema + profiling
        |
        v
4. Dataset registered to project
        |
        v
5. DuckDB analytical representation
        |
        +--------------------+
        |                    |
        v                    v
6. Dashboard            7. AI Chat
        |                    |
        |              +-----+------+
        |              |            |
        |              v            v
        |            SQL           RAG
        |              |            |
        +--------------+------------+
                       |
                       v
8. Forecast / Segmentation / Anomaly
                       |
                       v
9. Report Context Builder
                       |
                       v
10. Source & Semantic Validation
                       |
                       v
11. AI Executive Narrative
                       |
                       v
12. PDF / PPTX / HTML
```

---

# 21. Example: Olist Brazilian E-Commerce

A primary demonstration dataset for DataPilot AI is the **Brazilian E-Commerce Public Dataset by Olist**.

Dataset:

https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

The dataset contains multiple related tables, including:

- Orders
- Order items
- Customers
- Products
- Payments
- Reviews
- Sellers
- Geolocation

This makes it useful for demonstrating relational business intelligence rather than only single-table analytics.

### Example Olist project

```text
Olist E-Commerce Executive Intelligence
│
├── orders
├── order_items
├── customers
├── products
├── payments
├── reviews
├── sellers
├── geolocation
│
├── Knowledge Base
│   └── olist_business_dictionary.md
│
├── Dashboard
├── AI Chat
├── SQL Playground
├── Forecasting
├── Segmentation
├── Anomaly Detection
└── Executive Reports
```

---

# 22. Knowledge Base Example

A project can contain a business dictionary such as:

```text
olist_business_dictionary.md
```

The dictionary can define concepts such as:

```text
total_order_value
average_order_value
order
customer
freight_value
revenue
```

A question such as:

> What does total_order_value mean?

should be answered from the project's indexed business documentation when available.

This prevents a generic language model interpretation from replacing the organization's own definition.

---

# 23. Environment Variables

Do not commit real secrets to GitHub.

A typical backend configuration may include:

```env
DATABASE_URL=
REDIS_URL=

OPENROUTER_API_KEY=

STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_GROWTH_PRICE_ID=
STRIPE_PUBLISHABLE_KEY=

SENTRY_DSN=

CORS_ORIGINS=

EMBEDDING_PROVIDER=
EMBEDDING_MODEL=

AZURE_STORAGE_CONNECTION_STRING=
```

Only define variables actually required by the implementation.

Frontend variables should contain only browser-safe values, for example:

```env
NEXT_PUBLIC_API_URL=
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=
```

Never put secrets such as these into `NEXT_PUBLIC_*`:

```text
OPENROUTER_API_KEY
STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET
DATABASE_PASSWORD
JWT_SECRET
```

---

# 24. Local Development

## Prerequisites

Install:

- Git
- Node.js
- Python
- Docker
- PostgreSQL or the configured database
- Redis if required by the configured worker architecture
- Azure CLI for cloud deployment

## Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd <PROJECT_DIRECTORY>
```

## Frontend

```bash
npm install
npm run dev
```

Typical local frontend URL:

```text
http://localhost:3000
```

## Backend

Create and activate a Python environment using the project's selected environment manager.

Example on Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Install dependencies using the repository's actual lock/requirements configuration.

Example FastAPI startup:

```bash
uvicorn app.main:app --reload
```

The exact module path should match the repository implementation.

---

# 25. Docker Architecture

Production deployment uses containers.

```text
Source Code
    |
    v
Dockerfile
    |
    v
Docker Image
    |
    v
Azure Container Registry
    |
    v
Azure Container Apps
```

Example local build:

```bash
docker build -t datapilot-api:local .
```

Example local run:

```bash
docker run --env-file .env -p 8000:8000 datapilot-api:local
```

Adjust paths, ports, and Dockerfiles to match the repository.

---

# 26. Production Deployment on Azure

The current production architecture uses **Azure Container Apps** for the containerized frontend/backend runtime and **Azure Container Registry (ACR)** for container images.

Azure Container Apps is designed to run containerized applications while managing much of the underlying orchestration infrastructure. It supports container images, ingress, revisions, scaling, secrets/configuration, and related application operations. 

Official documentation:

https://learn.microsoft.com/azure/container-apps/

Azure Container Apps documentation confirms that applications can use Linux `linux/amd64` images and private/public registries, and that template changes create new revisions. citeturn0search3turn0search4

---

# 27. Azure Container Registry (ACR)

ACR is the private registry used to store container images before deployment.

Microsoft's documented flow is:

```text
Docker image
   |
   v
Tag with ACR login server
   |
   v
Docker push
   |
   v
ACR repository
   |
   v
Azure Container Apps
```

Official documentation:

https://learn.microsoft.com/azure/container-registry/

Microsoft documents tagging an image with the registry login server and pushing it with `docker push`. citeturn0search0turn0search1

### Example

```bash
az login
az acr login --name <ACR_NAME>

docker build -t <ACR_NAME>.azurecr.io/datapilot-api:<TAG> .
docker push <ACR_NAME>.azurecr.io/datapilot-api:<TAG>
```

Prefer immutable tags such as:

```text
Git commit SHA
```

or:

```text
2026-10-01-<commit-sha>
```

rather than relying only on `latest`.

---

# 28. Deploying to Azure Container Apps

A production deployment follows:

```text
GitHub
  |
  v
Tests
  |
  v
Docker Build
  |
  v
ACR Push
  |
  v
Container App Revision
  |
  v
Smoke Tests
  |
  v
Production
```

Azure's official deployment documentation covers deployment from an existing container image and source/repository workflows. citeturn0search5turn0search8

Example update command:

```bash
az containerapp update \
  --name <CONTAINER_APP_NAME> \
  --resource-group <RESOURCE_GROUP> \
  --image <ACR_NAME>.azurecr.io/datapilot-api:<TAG>
```

Do not guess production values for:

- Resource group
- Container App name
- Environment name
- Registry name
- Image name
- Port
- Secrets
- Environment variables

Read them from the actual Azure resource configuration.

---

# 29. Azure Deployment with GitHub Actions

A mature CI/CD flow can be:

```text
Developer
   |
   v
Git Push
   |
   v
GitHub Actions
   |
   +--> Test
   |
   +--> Build
   |
   +--> Docker Image
   |
   +--> Push to ACR
   |
   +--> Deploy Container App
   |
   +--> Smoke Test
   |
   v
Production
```

Azure documents repository-based Container Apps deployment workflows in which pushes can trigger image builds, ACR pushes, and Container Apps deployments. citeturn0search6

---

# 30. Production Storage Consideration

Azure Container Apps instances should not be treated as permanent storage for critical uploaded files, vector indexes, generated reports, or other state that must survive restarts/revisions.

For production, persistent application state should be stored in appropriate managed services such as:

```text
PostgreSQL       -> application metadata
Object Storage   -> uploaded documents / generated files
Vector Store     -> embeddings where required
Redis            -> cache / transient jobs
```

The exact services should be selected according to workload, scale, cost, security, and compliance requirements.

---

# 31. Observability

Production observability can include:

- Sentry
- OpenTelemetry
- structured logs
- Azure Container Apps logs
- application health endpoints
- performance metrics

Important signals include:

```text
API latency
API error rate
SQL execution errors
RAG retrieval failures
RAG insufficient-evidence rate
LLM failures
LLM latency
Forecast failures
Report generation duration
Worker failures
Database latency
Container restart rate
```

---

# 32. Testing Strategy

A production SaaS platform should be tested at multiple levels.

## Unit tests

Test:

- KPI calculations
- data transformations
- timestamp parsing
- feature selection
- clustering utilities
- anomaly calculations
- report semantic validation
- RRF ranking
- billing entitlement logic

## Integration tests

Test combinations of:

```text
FastAPI
+
PostgreSQL
+
DuckDB
+
RAG
+
ML
+
LLM
+
Stripe webhook handling
```

## End-to-end tests

The complete happy path should be:

```text
Login
 -> Create Project
 -> Upload Dataset
 -> Verify Dataset
 -> Ask AI Chat
 -> Run SQL
 -> Forecast
 -> Segment
 -> Detect Anomaly
 -> Generate Executive Report
 -> Export PDF
 -> Export PPTX
 -> Export HTML
```

## Security tests

Test:

- Unauthenticated API requests
- Unauthorized project access
- Cross-workspace access
- Cross-project RAG retrieval
- Unauthorized report download
- Stripe webhook signature validation
- Subscription spoofing
- Dataset ownership
- File access control

---

# 33. RAG Evaluation

RAG quality should be measured separately from the final generated answer.

Important dimensions:

### Retrieval relevance

Did the system retrieve the correct document chunks?

### Groundedness

Are claims supported by the retrieved evidence?

### Answer relevance

Does the response actually answer the user's question?

### Completeness

Does the retrieved context contain enough information to answer the question?

A system that retrieves irrelevant chunks and produces a fluent answer is not a reliable enterprise RAG system.

---

# 34. Security Principles

### Never commit secrets

Never commit:

```text
.env
.env.local
.env.production
API keys
Stripe secret keys
OpenRouter keys
Database passwords
JWT secrets
Azure credentials
Private certificates
```

### Backend-only secrets

Secrets should remain on the server.

### Authorization

Every protected operation should validate the authenticated user's access to the relevant workspace/project/resource.

### Billing

The frontend must never be the authoritative source of subscription entitlements.

### Webhooks

Stripe webhook signatures should be verified and webhook processing should be idempotent.

### Report exports

Private report exports must use authenticated server-side access controls.

---

# 35. SaaS Business Model

DataPilot AI can monetize the platform through a tiered SaaS model:

```text
                 +----------------+
                 |    STARTER     |
                 |     $0/mo      |
                 +-------+--------+
                         |
                         v
                 +----------------+
                 |     GROWTH     |
                 |    $79/mo      |
                 +-------+--------+
                         |
                         v
                 +----------------+
                 |   ENTERPRISE   |
                 |    Custom      |
                 +----------------+
```

The model allows a user/company to begin with a low-friction plan and expand when the platform becomes part of regular business operations.

---

# 36. How DataPilot AI Can Help a Company Grow

DataPilot AI should not be presented as guaranteeing revenue growth or profitability. Its potential business value comes from reducing analysis friction and helping teams use business information more consistently.

A typical value chain is:

```text
Raw Business Data
       |
       v
Faster Data Preparation
       |
       v
Faster Analysis
       |
       v
Better Visibility
       |
       v
Earlier Detection of Problems
       |
       v
Forecast / Segment / Investigate
       |
       v
Evidence-backed Decisions
       |
       v
Business Actions
```

### Potential operational improvements

#### 1. Faster reporting

Instead of manually preparing the same KPI report repeatedly, a standardized report pipeline can generate it from verified sources.

#### 2. Faster investigation

Natural-language questions can reduce the time required to locate data and formulate SQL manually.

#### 3. Better anomaly awareness

Automated anomaly detection can highlight unusual movements that deserve human investigation.

#### 4. Customer understanding

Segmentation can help teams identify different behavioral groups and investigate their characteristics.

#### 5. Forecasting support

Forecasting can help teams examine possible future trends based on historical data.

#### 6. Centralized business knowledge

A business dictionary and internal documentation can make organizational definitions searchable.

#### 7. Executive communication

PDF/PPTX/HTML reports can turn analytical outputs into a consistent executive communication format.

---

# 37. Growth Strategy for the Product

A possible product-growth path is:

```text
PHASE 1 — Core BI
|
+-- Dataset Upload
+-- Dashboard
+-- SQL Playground
+-- AI Chat
|
v
PHASE 2 — AI Analytics
|
+-- RAG
+-- Forecasting
+-- Segmentation
+-- Anomaly Detection
|
v
PHASE 3 — Executive Intelligence
|
+-- Automated Reports
+-- Evidence / Citations
+-- PDF / PPTX / HTML
+-- Scheduled Reports
|
v
PHASE 4 — Team SaaS
|
+-- Collaboration
+-- Roles
+-- Billing
+-- Usage Management
|
v
PHASE 5 — Enterprise
|
+-- SSO / SAML
+-- Audit
+-- Private Networking
+-- Dedicated Scaling
+-- Enterprise Integrations
```

Potential future integrations include:

- PostgreSQL direct connectors
- MySQL
- Snowflake
- BigQuery
- Salesforce
- HubSpot
- Shopify
- Slack
- Microsoft Teams
- automated email briefings
- scheduled anomaly alerts
- data quality monitoring
- semantic metrics catalog
- scenario / what-if analysis
- natural-language dashboard generation

These are roadmap opportunities, not guaranteed current features.

---

# 38. Example Business Use Cases

## E-commerce

- Revenue analysis
- Order analysis
- AOV
- Product performance
- Category performance
- Customer segmentation
- Delivery analysis
- Review analysis
- Anomaly detection
- Forecasting

## Retail

- Sales trends
- Inventory analysis
- Product performance
- Store performance
- Customer cohorts
- Seasonal patterns

## SaaS

- MRR / ARR datasets
- Churn analysis
- Retention
- Cohorts
- Customer segmentation
- Product usage analytics

## Operations

- Delivery performance
- Service-level monitoring
- Throughput
- Operational anomalies
- Trend analysis

## Customer Analytics

- RFM
- Lifetime-value-oriented analysis
- Cohorts
- Purchase frequency
- Churn indicators
- Customer personas derived from observed data

---

# 39. Recommended End-User Workflow

```text
1. Create Workspace
        |
2. Create Project
        |
3. Upload Business Data
        |
4. Inspect Dataset
        |
5. Ask AI Chat Questions
        |
6. Run SQL Analysis
        |
7. Run Forecasting
        |
8. Run Segmentation
        |
9. Run Anomaly Detection
        |
10. Upload Business Documentation
        |
11. Search Knowledge Base
        |
12. Generate Executive Report
        |
13. Review Sources & Evidence
        |
14. Export PDF / PPTX / HTML
        |
15. Share with Executives / Teams
```

---

# 40. Example Executive Request

A manager could ask:

> **Give me a summary of business performance, identify unusual activity, explain the major customer groups, and prepare an executive report with supporting evidence.**

The platform can orchestrate:

```text
Dashboard KPIs
      |
      v
SQL Analysis
      |
      v
Anomaly Detection
      |
      v
Forecasting
      |
      v
Segmentation
      |
      v
Business Dictionary / RAG
      |
      v
Executive Synthesis
      |
      v
Source Validation
      |
      v
PDF / PPTX / HTML
```

---

# 41. Design Principles

### 1. Data first

Business data and verified source documents are the foundation.

### 2. AI-assisted, not AI-fabricated

AI should interpret and orchestrate evidence rather than invent it.

### 3. Deterministic calculations

Exact numerical questions should use SQL/analytical engines.

### 4. Grounded knowledge

Document questions should use retrieved evidence.

### 5. Project isolation

Project data must not leak across project boundaries.

### 6. Server-side authorization

Access decisions must be enforced by the backend.

### 7. Observable production behavior

Errors should be logged and diagnosable.

### 8. Scalable architecture

The system should be able to evolve from individual usage to team and enterprise deployments.

### 9. Reproducibility

Important analytical outputs should be traceable to source data, query/model configuration, and period.

### 10. Human decision-making

DataPilot AI provides analysis and evidence. Business leaders remain responsible for decisions.

---

# 42. Repository Structure

A representative structure is:

```text
datapilot-ai/
|
+-- frontend/
|   +-- app/
|   +-- components/
|   +-- features/
|   +-- hooks/
|   +-- lib/
|   +-- services/
|   +-- ...
|
+-- backend/
|   +-- app/
|       +-- api/
|       +-- auth/
|       +-- datasets/
|       +-- analytics/
|       +-- forecasting/
|       +-- segmentation/
|       +-- anomaly/
|       +-- rag/
|       +-- agents/
|       +-- reports/
|       +-- billing/
|       +-- ...
|
+-- tests/
+-- docs/
+-- scripts/
+-- .github/
|   +-- workflows/
|
+-- Dockerfile / Dockerfiles
+-- docker-compose.yml
+-- README.md
+-- .gitignore
```

The exact tree should be kept synchronized with the repository as the codebase evolves.

---

# 43. CI/CD Checklist

Before a production deployment:

```text
[ ] Frontend tests pass
[ ] Backend tests pass
[ ] Production build passes
[ ] Type checking passes
[ ] Linting passes
[ ] No secrets committed
[ ] Environment variables configured
[ ] Database migrations applied
[ ] CORS configured for production
[ ] Authentication verified
[ ] Authorization verified
[ ] RAG indexing verified
[ ] Dataset upload verified
[ ] AI Chat verified
[ ] SQL verified
[ ] Forecasting verified
[ ] Segmentation verified
[ ] Anomaly Detection verified
[ ] Executive report verified
[ ] PDF export verified
[ ] PPTX export verified
[ ] HTML export verified
[ ] Stripe checkout verified in test mode
[ ] Stripe webhook verified
[ ] Protected report download verified
[ ] Docker image built
[ ] ACR push successful
[ ] Container App revision healthy
[ ] Production smoke test passed
```

---

# 44. Production Report Validation

Because Executive Reports are a high-value output, report generation should be tested end-to-end.

The test should verify:

```text
Project selected
   |
   v
Correct datasets loaded
   |
   v
Dashboard KPIs loaded
   |
   v
SQL evidence generated
   |
   v
Forecast result loaded or correctly marked unavailable
   |
   v
Segmentation result loaded or correctly marked unavailable
   |
   v
Anomaly result loaded or correctly marked unavailable
   |
   v
RAG evidence loaded where selected
   |
   v
Report context validated
   |
   v
AI narrative generated
   |
   v
Metric semantics validated
   |
   v
Sources attached
   |
   v
PDF/PPTX/HTML rendered
   |
   v
Protected export endpoint authenticated
   |
   v
Downloaded file opens successfully
```

A report must never display a fake zero simply because an upstream module failed. It should distinguish between:

```text
Actual zero
```

and:

```text
Unavailable / insufficient data / module failure
```

---

# 45. Known Production Reliability Rules

DataPilot AI should not depend on:

- fake datasets
- fake KPIs
- hardcoded project IDs
- hardcoded dataset IDs
- hardcoded user IDs
- hardcoded production URLs inside business logic
- fabricated AI responses
- fabricated source citations
- unauthenticated private exports
- frontend-only billing state
- ephemeral local filesystem as the only copy of critical production state

---

# 46. Documentation & Official References

### Application

- [DataPilot AI — Production Frontend](https://datapilot-web.ashyriver-d1eb08b9.uaenorth.azurecontainerapps.io/)
- [DataPilot AI — Production API](https://datapilot-api.ashyriver-d1eb08b9.uaenorth.azurecontainerapps.io/)

### Data

- [Olist Brazilian E-Commerce Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)

### Core technology

- [Next.js](https://nextjs.org/)
- [React](https://react.dev/)
- [TypeScript](https://www.typescriptlang.org/)
- [Python](https://www.python.org/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [DuckDB](https://duckdb.org/)
- [PostgreSQL](https://www.postgresql.org/)
- [Redis](https://redis.io/)
- [LangGraph / LangChain](https://docs.langchain.com/)
- [OpenRouter](https://openrouter.ai/)
- [Stripe](https://stripe.com/)
- [Docker](https://www.docker.com/)
- [GitHub](https://github.com/)

### Azure

- [Azure Container Apps](https://learn.microsoft.com/azure/container-apps/)
- [Azure Container Registry](https://learn.microsoft.com/azure/container-registry/)
- [Azure Container Apps — existing image deployment](https://learn.microsoft.com/azure/container-apps/get-started-existing-container-image)
- [Azure Container Apps — repository deployment](https://learn.microsoft.com/azure/container-apps/quickstart-repo-to-cloud)
- [Azure Container Registry — Docker push/pull](https://learn.microsoft.com/azure/container-registry/container-registry-get-started-docker-cli)

### AI APIs

- [OpenRouter Quickstart](https://openrouter.ai/docs/quickstart)
- [OpenRouter Chat Completions API](https://openrouter.ai/docs/api/api-reference/chat/send-chat-completion-request)

### Billing

- [Stripe Documentation](https://docs.stripe.com/)
- [Stripe Subscriptions API](https://docs.stripe.com/api/subscriptions/create)

---

# 47. Future Scaling Architecture

## Stage 1 — Individual / Small Team

```text
Next.js
FastAPI
PostgreSQL
DuckDB
Redis
Azure Container Apps
OpenRouter
Stripe
```

Focus:

- Product validation
- Small/medium datasets
- Low operational complexity

## Stage 2 — Growing Teams

Add:

- Background workers
- Scheduled reports
- Persistent object storage
- Dedicated vector infrastructure where needed
- Better caching
- Queue-based processing
- More detailed observability
- Autoscaling

## Stage 3 — Enterprise

Add according to requirements:

- SSO/SAML
- Private networking
- Dedicated environments
- Advanced audit controls
- Larger persistent storage
- Dedicated compute
- Advanced governance
- Custom integrations
- Enterprise data connectors

Azure Container Apps supports revisions and scaling capabilities that can support progressive deployment and changing workloads. citeturn0search3turn0search4

---

# 48. Product Vision

The long-term vision is to evolve DataPilot AI from an analytics application into a **Business Intelligence Operating System**.

```text
                    BUSINESS DATA
                         |
          +--------------+--------------+
          |              |              |
          v              v              v
     Structured       Documents      External APIs
          |              |              |
          +--------------+--------------+
                         |
                         v
                   DATAPILOT AI
                         |
          +--------------+--------------+
          |              |              |
          v              v              v
      Analytics        AI / RAG       ML / Forecast
          |              |              |
          +--------------+--------------+
                         |
                         v
                 BUSINESS INTELLIGENCE
                         |
          +--------------+--------------+
          |              |              |
          v              v              v
       Analysts       Managers      Executives
          |              |              |
          +--------------+--------------+
                         |
                         v
                 INFORMED BUSINESS ACTION
```

The goal is not merely another dashboard.

The goal is a unified system where an organization can:

```text
Understand its data
        +
Ask questions naturally
        +
Calculate exact metrics
        +
Search internal knowledge
        +
Discover patterns
        +
Detect anomalies
        +
Forecast trends
        +
Understand customer groups
        +
Generate evidence-backed reports
        =
Unified decision-support platform
```

---

# 49. Author

**Saad Azeem**  
BS Computer Science  
AI / Machine Learning / Software Engineering

Areas of focus:

- Artificial Intelligence
- Machine Learning
- Generative AI
- RAG
- Agentic AI
- Data Analytics
- MLOps
- Full-Stack AI Applications
- Cloud Deployment
- Production AI Systems

GitHub:

https://github.com/SaadAzeem595

LinkedIn:

https://www.linkedin.com/in/saad-azeem-8941bb317/

---

# 50. License

Add the project's actual license here before publishing.

For example:

```text
MIT License
```

Only use the MIT License statement if the repository has actually been licensed under MIT.

---

# 51. Final Summary

DataPilot AI brings together:

```text
Next.js
+
React
+
TypeScript
+
FastAPI
+
Python
+
PostgreSQL
+
DuckDB
+
Redis
+
LangGraph
+
OpenRouter / LLMs
+
BM25
+
Dense Retrieval
+
RRF
+
Forecasting
+
Segmentation
+
Anomaly Detection
+
Stripe
+
Docker
+
GitHub
+
Azure Container Registry
+
Azure Container Apps
```

into a unified AI Business Intelligence and Executive Intelligence platform.

Its core philosophy is:

> **Calculate with deterministic systems. Retrieve from real sources. Use AI to reason over verified context. Validate the result. Deliver business intelligence in a form people can act on.**

---

## Project Status

**DataPilot AI — AI Business Intelligence & Executive Intelligence Platform**

**Production target:** Azure Container Apps + Azure Container Registry  
**Billing:** Stripe  
**LLM gateway:** OpenRouter  
**Analytics:** DuckDB + Python analytics  
**AI orchestration:** LangGraph / agent workflows  
**RAG:** BM25 + dense retrieval + RRF  

