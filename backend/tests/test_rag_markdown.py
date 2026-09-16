import os
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.features.rag.ingestion.parsers import DocumentParserService, MarkdownParser
from app.features.rag.ingestion.cleaner import TextCleaner
from app.features.rag.ingestion.chunker import ChunkerService
from app.features.rag.embeddings.providers import MockEmbeddingProvider
from app.features.rag.vector_store.repository import InMemoryVectorRepository, DuckDBVectorRepository
from app.features.rag.retrieval.service import RetrievalService
from app.features.rag.retrieval.context_builder import ContextBuilder
from app.features.rag.schemas import Chunk, DocumentMetadata

PROJECT_ID = "proj-43d2ca3d"
OLIST_MD_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "olist_business_dictionary.md")


def read_olist_md_bytes() -> bytes:
    with open(OLIST_MD_PATH, "rb") as f:
        return f.read()


# Test A & Test B: API Upload Validation (.md accepted, .exe rejected)
def test_markdown_upload_validation_reject_exe():
    client = TestClient(app)

    # 1. Reject .exe file with HTTP 400
    exe_payload = b"MZ\x90\x00\x03\x00\x00\x00This is a binary executable"
    files = {"file": ("malicious_payload.exe", exe_payload, "application/x-msdownload")}
    data = {"workspace": PROJECT_ID, "author": "Tester"}

    resp_exe = client.post("/api/v1/rag/ingest", files=files, data=data)
    assert resp_exe.status_code == 400
    detail = resp_exe.json().get("detail", {})
    assert detail.get("error") == "UNSUPPORTED_FILE_TYPE"
    assert "exe" in detail.get("message", "").lower()


def test_markdown_upload_success_api():
    client = TestClient(app)
    md_bytes = read_olist_md_bytes()

    # Upload olist_business_dictionary.md
    files = {"file": ("olist_business_dictionary.md", md_bytes, "text/markdown")}
    data = {"workspace": PROJECT_ID, "author": "Business Analyst", "tags": "olist,ecommerce,dictionary"}

    resp = client.post("/api/v1/rag/ingest", files=files, data=data)
    assert resp.status_code == 201
    resp_data = resp.json()
    assert resp_data["status"] == "success"
    assert resp_data["workspace"] == PROJECT_ID
    assert resp_data["chunks_count"] > 0
    assert resp_data["filename"] == "olist_business_dictionary.md"

    # Verify listing document in project
    docs_resp = client.get(f"/api/v1/rag/documents?workspace={PROJECT_ID}")
    assert docs_resp.status_code == 200
    docs = docs_resp.json()
    olist_doc = next((d for d in docs if d["filename"] == "olist_business_dictionary.md"), None)
    assert olist_doc is not None
    assert olist_doc["document_type"] in ("MD", "MARKDOWN")
    assert olist_doc["status"] == "Indexed"
    assert olist_doc["chunks_count"] > 0


# Test C: Parsing Markdown Headings, Section Labels, and UTF-8 encodings
def test_markdown_parser_headings_and_encodings():
    parser = MarkdownParser()
    sample_md = """# Dataset: Olist Brazilian E-Commerce

orders:
- order_id
- customer_id

order_items:
- order_id
- price
- freight_value

Title Header
===

Subtitle
---

| Table Col 1 | Table Col 2 |
| --- | --- |
| Val 1 | Val 2 |

```python
def example():
    return "code block preserved"
```
"""
    # Test UTF-8 and UTF-8 BOM
    parsed_utf8 = parser.parse(sample_md.encode("utf-8"), "test.md")
    assert "# Dataset: Olist Brazilian E-Commerce" in parsed_utf8
    assert "orders:" in parsed_utf8
    assert "freight_value" in parsed_utf8
    assert "| Table Col 1 | Table Col 2 |" in parsed_utf8
    assert "code block preserved" in parsed_utf8

    # UTF-8 BOM test
    bom_bytes = b"\xef\xbb\xbf" + sample_md.encode("utf-8")
    parsed_bom = parser.parse(bom_bytes, "test.md")
    assert "freight_value" in parsed_bom


# Test D & Test E: Chunker Service on Markdown
def test_markdown_chunker_intelligent_grouping():
    chunker = ChunkerService(chunk_size=500, chunk_overlap=50)
    raw_md = read_olist_md_bytes().decode("utf-8")

    chunks = chunker.chunk_markdown(raw_md)
    assert len(chunks) >= 3  # Multiple logical sections

    headings = [c["heading"] for c in chunks]
    assert any("orders" in h.lower() for h in headings)
    assert any("order_items" in h.lower() for h in headings)
    assert any("customers" in h.lower() for h in headings)
    assert any("products" in h.lower() for h in headings)
    assert any("Business definitions" in h or "definitions" in h.lower() for h in headings)

    # Verify no tiny meaningless fragments (e.g. single bullet point as separate chunk)
    for c in chunks:
        assert len(c["text"].strip()) > 20
        assert c["chunk_type"] == "markdown_section"


# Test F & Test G: Embeddings and Vector/Keyword Store Indexing
def test_markdown_embeddings_and_vector_store():
    embedder = MockEmbeddingProvider(dimension=64)
    raw_md = read_olist_md_bytes().decode("utf-8")
    chunker = ChunkerService()
    chunk_dicts = chunker.chunk_markdown(raw_md)

    texts = [cd["text"] for cd in chunk_dicts]
    embs = embedder.get_embeddings(texts)
    assert len(embs) == len(texts)

    repo = InMemoryVectorRepository()
    chunks = []
    for idx, cd in enumerate(chunk_dicts):
        meta = DocumentMetadata(
            filename="olist_business_dictionary.md",
            document_type="MD",
            workspace=PROJECT_ID,
            heading=cd["heading"],
            heading_path=cd.get("heading_path", cd["heading"]),
            chunk_type=cd.get("chunk_type", "markdown_section")
        )
        chunks.append(Chunk(
            id=f"doc-olist-{idx}",
            doc_id="doc-olist",
            text=cd["text"],
            embedding=embs[idx],
            metadata=meta
        ))

    repo.insert_chunks(chunks)

    # Keyword search test
    kw_results = repo.keyword_search("freight_value", limit=3, filters={"workspace": PROJECT_ID})
    assert len(kw_results) > 0
    top_chunk, score = kw_results[0]
    assert "freight_value" in top_chunk.text or "freight" in top_chunk.text.lower()


# Test H: Grounded Answers & Citations for the 5 Required Queries
@pytest.mark.parametrize("query,expected_keywords,expected_sections", [
    (
        "What does freight_value mean?",
        ["freight_value", "order_items", "freight revenue"],
        ["order_items", "business definitions", "general"]
    ),
    (
        "What is customer_unique_id?",
        ["customer_unique_id", "customers", "customer_id"],
        ["customers", "general"]
    ),
    (
        "What is the difference between customer_id and customer_unique_id?",
        ["customer_id", "customer_unique_id", "customers"],
        ["customers", "orders", "general"]
    ),
    (
        "How are orders related to order items?",
        ["orders", "order_items", "order_id"],
        ["orders", "order_items", "general"]
    ),
    (
        "Which dataset contains product categories?",
        ["products", "product_category_name"],
        ["products", "general"]
    ),
])
def test_markdown_five_required_queries_grounded_answers(query, expected_keywords, expected_sections):
    client = TestClient(app)

    retrieve_payload = {
        "query": query,
        "limit": 5,
        "filters": {"workspace": PROJECT_ID},
        "hybrid_alpha": 0.5,
        "enable_rerank": True
    }

    resp = client.post("/api/v1/rag/retrieve", json=retrieve_payload)
    assert resp.status_code == 200
    res_data = resp.json()

    assert "grounded_answer" in res_data
    grounded = res_data["grounded_answer"]
    assert grounded["grounded"] is True
    answer = grounded["answer"].lower()

    # Verify key conceptual terms appear in dynamic grounded answer
    for kw in expected_keywords:
        assert kw.lower() in answer, f"Expected '{kw}' to appear in answer: {grounded['answer']}"

    # Verify source citation to olist_business_dictionary.md
    assert "olist_business_dictionary.md" in answer or len(grounded.get("sources", [])) > 0
    if grounded.get("sources"):
        top_source = grounded["sources"][0]
        assert "olist_business_dictionary.md" in top_source["filename"]


# Test I: Project Isolation
def test_markdown_project_isolation():
    client = TestClient(app)

    # Search in a completely isolated, non-existent workspace
    other_ws = "isolated-project-workspace-xyz"
    retrieve_payload = {
        "query": "What does freight_value mean?",
        "limit": 5,
        "filters": {"workspace": other_ws},
        "hybrid_alpha": 0.5
    }

    resp = client.post("/api/v1/rag/retrieve", json=retrieve_payload)
    assert resp.status_code == 200
    res_data = resp.json()

    # Must find NO chunks from proj-43d2ca3d in other workspace
    assert len(res_data["results"]) == 0
    assert res_data["grounded_answer"]["grounded"] is False


# Test J: Regression check on existing formats (CSV, TXT, JSON)
def test_regression_existing_formats():
    client = TestClient(app)
    ws = "regression-test-ws"

    # TXT test
    txt_content = b"DataPilot AI Platform provides executive enterprise dashboards."
    client.post(
        "/api/v1/rag/ingest",
        files={"file": ("overview.txt", txt_content, "text/plain")},
        data={"workspace": ws, "author": "Tester"}
    )

    # CSV test
    csv_content = b"metric,value\nrevenue,50000\ngrowth,15\n"
    client.post(
        "/api/v1/rag/ingest",
        files={"file": ("metrics.csv", csv_content, "text/csv")},
        data={"workspace": ws, "author": "Tester"}
    )

    # JSON test
    json_content = b'{"status": "healthy", "service": "rag_knowledge_layer"}'
    client.post(
        "/api/v1/rag/ingest",
        files={"file": ("status.json", json_content, "application/json")},
        data={"workspace": ws, "author": "Tester"}
    )

    # Verify all 3 are listed and indexed
    docs_resp = client.get(f"/api/v1/rag/documents?workspace={ws}")
    assert docs_resp.status_code == 200
    docs = docs_resp.json()
    filenames = [d["filename"] for d in docs]
    assert "overview.txt" in filenames
    assert "metrics.csv" in filenames
    assert "status.json" in filenames
