# Architecture Blueprint

This document details the software architecture, design patterns, data pipelines, and operational flowcharts of the AI Business Intelligence Platform. 

---

## 1. Overall System Architecture

The platform follows a decoupled, service-oriented architecture designed to handle heavy analytics queries and background machine learning pipelines without blocking the web request lifecycle.

```mermaid
graph TD
    Client[Next.js Web Dashboard] <--> |HTTPS / JSON| API[FastAPI Web Server]
    API <--> |Session Cache / Rate Limits| Redis[(Redis distributed cache)]
    API <--> |OLAP Analytical Queries| DuckDB[(DuckDB Filesystem)]
    API --> |Write Metadata| Postgres[(PostgreSQL Metadata Store)]
    API --> |Queue Tasks| RedisBroker[(Redis Message Broker)]
    RedisBroker --> Celery[Celery Background Workers]
    Celery <--> |Embeddings Retrieval| Chroma[(Chroma Vector DB)]
    Celery <--> |Model Versioning| MLflow[(MLflow Model Registry)]
    Celery --> |PDF / PPTX Exports| Storage[(Local reports/ storage)]
    Celery <--> |Read Datasets| DuckDB
```

---

## 2. Frontend Architecture

The frontend is built using Next.js 15 App Router. It is modularly grouped by **features** rather than arbitrary folder directories.

```mermaid
graph TD
    RootLayout[src/app/layout.tsx] --> AppRoute[src/app/page.tsx - Dashboard Root]
    RootLayout --> DashboardLayout[src/app/dashboard/layout.tsx]
    
    DashboardLayout --> Route1[datasets/page.tsx]
    DashboardLayout --> Route2[sql/page.tsx]
    DashboardLayout --> Route3[forecasting/page.tsx]
    DashboardLayout --> Route4[segmentation/page.tsx]
    DashboardLayout --> Route5[anomalies/page.tsx]
    DashboardLayout --> Route6[chat/page.tsx]
    DashboardLayout --> Route7[reports/page.tsx]
    
    Route1 --> Features[src/features/]
    Route2 --> Features
    Route3 --> Features
    
    Features --> FeatureHooks[hooks/ - custom fetch wrappers]
    Features --> FeatureComp[components/ - UI charts/cards]
    Features --> FeatureAPI[api/ - fetch fetchers]
    
    Features --> Shared[src/shared/ - components, utils, icons]
```

---

## 3. Backend Architecture

The backend FastAPI structure is structured under a clean, layered design that separates HTTP routing, dependency checkouts, business logic, and database access.

```mermaid
graph TD
    Request[HTTP Request] --> Router[FastAPI Routers app/features/*/router.py]
    Router --> Deps[Dependencies Injection app/core/dependencies.py]
    
    Deps --> Auth[JWT Signature & RBAC Verification]
    Deps --> APIKey[API Key Header Verification]
    
    Router --> Service[Service layer app/features/*/service.py]
    Service --> Engine[Analytics Engines app/features/analytics/engine/]
    Service --> Repos[DB Repositories app/features/*/repository.py]
    
    Repos --> Models[SQLAlchemy Models app/features/*/models.py]
    Models --> DB[(PostgreSQL Database)]
```

---

## 4. Database Schema (ERD)

PostgreSQL stores metadata related to system execution, reports, and scheduled cron configurations. Analytical datasets are stored as separate CSV/Parquet files and queried via DuckDB.

```mermaid
erDiagram
    users {
        uuid id PK
        string email UK
        string password_hash
        string role "Admin | Executive | Analyst | Viewer"
        timestamp created_at
    }
    datasets {
        uuid id PK
        string filename
        string file_path
        string status "Active | Processing | Error"
        integer row_count
        timestamp uploaded_at
        uuid uploaded_by FK
    }
    reports {
        uuid id PK
        string title
        string type "PDF | PPTX"
        string file_path
        string status "Pending | Completed | Failed"
        string frequency "Daily | Weekly | Monthly | Ad-hoc"
        uuid author_id FK
        timestamp created_at
    }
    schedules {
        uuid id PK
        string title
        string workspace
        string report_type
        string frequency
        boolean is_active
        timestamp created_at
    }
    
    users ||--o{ datasets : "uploads"
    users ||--o{ reports : "generates"
```

---

## 5. Data Ingestion Pipeline

When a user uploads a new dataset, it is validated, saved to disk, and automatically registered for analytical queries via DuckDB.

```mermaid
sequenceDiagram
    autonumber
    actor User as Analyst / Client
    participant API as FastAPI Server
    participant Storage as File Storage
    participant DuckDB as DuckDB Engine

    User->>API: POST /api/v1/datasets/upload (Multipart File)
    API->>API: Validate file extension (CSV, XLSX, Parquet)
    API->>Storage: Save file to disk (storage/datasets/{id}.csv)
    API->>DuckDB: Register file path view (CREATE VIEW ON CSV)
    API->>DuckDB: Profile schema (Column types, row counts, missing values)
    DuckDB-->>API: Data profile metrics
    API-->>User: HTTP 200 OK (DatasetResponse with metadata)
```

---

## 6. Machine Learning Pipeline

Models are trained in background Celery workers, logged, registered, and immediately cached for subsequent predictions.

```mermaid
graph TD
    Payload[Trigger payload: model_type, dataset_id] --> Celery[Celery Task app/features/ml/tasks.py]
    Celery --> Load[Load CSV dataset via DuckDB]
    Load --> Preprocess[Scikit-learn preprocessing pipeline]
    Preprocess --> Train[Fit model Classifier / Forecast]
    Train --> Eval[Calculate performance metrics MSE/Accuracy]
    Eval --> Log[Log artifacts & metrics to MLflow]
    Log --> Register[Register model version in MLflow registry]
    Register --> Invalidate[Evict predictions cache for this model]
    Invalidate --> Finish[Update model task record status = Completed]
```

---

## 7. RAG Ingestion & Retrieval Architecture

The RAG pipeline enables users to query their unstructured PDF reports, utilizing a hybrid search strategy that blends keyword matching with vector embeddings.

### Document Ingestion Flow
```mermaid
graph LR
    PDF[Raw Report PDF] --> Parse[PyPDF chunking]
    Parse --> Embedding[Generate OpenAI/HuggingFace embeddings]
    Embedding --> Chroma[(Chroma Vector Database)]
```

### Retrieval & Synthesis Flow
```mermaid
graph TD
    Query[User Query] --> EmbedQuery[Vector Embed query]
    EmbedQuery --> VectorSearch[Chroma vector query]
    Query --> KeywordSearch[DuckDB SQL text lookup]
    VectorSearch --> Combine[Merge & rank results]
    KeywordSearch --> Combine
    Combine --> Synthesis[Construct LLM context payload]
    Synthesis --> LLM[Generate response]
    LLM --> Response[Final Answer + Citations]
```

---

## 8. LangGraph Multi-Agent Workflow

The agentic chat workspace runs on a state-based multi-agent system built using LangGraph, routing queries dynamically to specialized analytics nodes.

```mermaid
stateDiagram-v2
    [*] --> Start
    Start --> Planner : Initialize state
    Planner --> Router : Formulate execution plan
    
    state Router <<choice>>
    Router --> SQL_Agent : If query requires database querying
    Router --> ML_Agent : If query requires training or forecasting
    Router --> RAG_Agent : If query requires document retrieval
    Router --> Summarizer : If plan steps are fully complete
    
    SQL_Agent --> Router : Append SQL result to state
    ML_Agent --> Router : Append ML predictions to state
    RAG_Agent --> Router : Append context to state
    
    Summarizer --> [*] : Return final response
```

---

## 9. Executive Reporting Pipeline

Executive reports are scheduled or triggered on-demand, running in the background to compile data visualizations and tabular KPIs into PDF/PowerPoint documents.

```mermaid
graph TD
    Trigger[Trigger Report Event] --> Celery[Celery Worker]
    Celery --> Fetch[Query DuckDB for KPI analytics snapshots]
    Fetch --> Viz[Generate charts using Matplotlib]
    Viz --> PDF[Compile PDF file using ReportLab]
    Viz --> PPTX[Compile slides using python-pptx]
    PDF --> Save[Save file deliverables to storage/reports/]
    PPTX --> Save
    Save --> DB[Insert Report entry in PostgreSQL Metadata DB]
    DB --> Notify[Emit socket notification: Generation Success]
```

---

## 10. Deployment Architecture

For high availability and performance scaling, the platform is deployed in isolated network subnets, splitting stateless API queries from computation-heavy workers.

```mermaid
graph TD
    subnet[Isolated Application VPC]
    Internet[Client Traffic] --> |HTTPS / Port 443| LB[Load Balancer]
    
    subnet --> LB
    LB --> Web[Next.js Frontend Container]
    LB --> API[FastAPI backend Containers]
    
    API <--> Cache[(Redis Cache & Session Store)]
    API <--> DB[(PostgreSQL Database RDS)]
    
    RedisBroker[(Redis Queue Broker)] --> Workers[Celery computation Containers]
    API --> RedisBroker
    Workers <--> DB
    
    Storage[(EFS / Mounted Storage volume)] <--> API
    Storage <--> Workers
```

---

## 11. Request Lifecycle

The chronological sequence of middleware processing for every HTTP request hitting the FastAPI server:

```mermaid
sequenceDiagram
    autonumber
    Client->>FastAPI: HTTP GET /api/v1/analytics/query
    FastAPI->>RateLimit: Check Redis sliding-window limit
    RateLimit-->>FastAPI: Request allowed (under throttle cap)
    FastAPI->>Headers: Inject secure browser headers (XSS, CORS)
    FastAPI->>Auth: Validate JWT / API Key validation
    Auth-->>FastAPI: Identity verified (MockUser: Analyst)
    FastAPI->>Cache: Lookup query cache key (Redis)
    alt Cache Hit
        Cache-->>FastAPI: Return cached JSON payload
    else Cache Miss
        FastAPI->>DuckDB: Execute SQL analytics query
        DuckDB-->>FastAPI: Pandas DataFrame output
        FastAPI->>Cache: Set cache key (Redis) with 300s TTL
    end
    FastAPI->>GZip: Compress JSON response payload
    FastAPI-->>Client: HTTP 200 OK (GZip compressed stream)
```
