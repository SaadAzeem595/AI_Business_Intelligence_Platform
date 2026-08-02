import pytest
import os
import shutil
import tempfile
import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.features.rag.ingestion.cleaner import TextCleaner
from app.features.rag.ingestion.chunker import ChunkerService
from app.features.rag.ingestion.ocr import MockOCRProvider
from app.features.rag.ingestion.parsers import DocumentParserService
from app.features.rag.embeddings.providers import MockEmbeddingProvider
from app.features.rag.vector_store.repository import InMemoryVectorRepository, DuckDBVectorRepository
from app.features.rag.retrieval.service import RetrievalService, MockReranker
from app.features.rag.retrieval.context_builder import ContextBuilder
from app.features.rag.evaluation.service import RAGEvaluationService
from app.features.rag.schemas import Chunk, DocumentMetadata, GroundTruthItem

# 1. Text Cleaner Unit Tests
def test_text_cleaner():
    dirty_text = "Hello    World!  \n\n\n  Stylized “quotes” and — dashes. \r\nNew lines here.  "
    clean = TextCleaner.normalize_text(dirty_text)
    assert "Hello World!" in clean
    assert 'Stylized "quotes" and - dashes.' in clean
    assert "New lines here." in clean
    assert "\r" not in clean

# 2. Chunker Unit Tests
def test_chunker():
    chunker = ChunkerService(chunk_size=100, chunk_overlap=20)
    
    # Test fixed size chunking
    text = "The quick brown fox jumps over the lazy dog. A quick brown fox jumps over the lazy dog. A quick brown fox jumps over the lazy dog."
    chunks = chunker.chunk_fixed_size(text)
    assert len(chunks) > 0
    assert chunks[0].startswith("The quick")
    
    # Test heading-aware chunking
    heading_text = """
# Introduction
Here is the first section.
## Details
Here is some detail text.
--- Slide 2 ---
Slide text goes here.
"""
    heading_chunks = chunker.chunk_by_heading(heading_text)
    assert len(heading_chunks) >= 3
    assert heading_chunks[0]["heading"] == "Introduction"
    assert heading_chunks[1]["heading"] == "Details"
    assert heading_chunks[2]["heading"] == "Slide 2"

# 3. Embedding Provider Unit Tests
def test_mock_embeddings():
    provider = MockEmbeddingProvider(dimension=128)
    vec1 = provider.get_embedding("Hello RAG")
    vec2 = provider.get_embedding("Hello RAG")
    vec3 = provider.get_embedding("Different text")
    
    assert len(vec1) == 128
    # Parity check
    assert vec1 == vec2
    assert vec1 != vec3
    
    # Unit normalization check (norm = 1.0)
    norm = np.linalg.norm(vec1)
    assert pytest.approx(norm, 0.001) == 1.0

# 4. Parsers Unit Tests
def test_parsers():
    parser_service = DocumentParserService(ocr_provider=MockOCRProvider())
    
    # HTML Parsing
    html_bytes = b"<html><body><h1>Title</h1><p>Paragraph content</p></body></html>"
    html_text = parser_service.parse_file(html_bytes, "test.html")
    assert "Title" in html_text
    assert "Paragraph content" in html_text
    
    # JSON Parsing
    json_bytes = b'{"key": "value"}'
    json_text = parser_service.parse_file(json_bytes, "test.json")
    assert "key" in json_text
    assert "value" in json_text

# 5. Vector Store Unit Tests (InMemory & DuckDB)
def test_vector_repositories():
    meta = DocumentMetadata(
        filename="business.txt",
        document_type="TXT",
        workspace="marketing"
    )
    
    chunks = [
        Chunk(id="c1", doc_id="d1", text="Company revenue in 2026 reached $5M.", embedding=[0.1, 0.9], metadata=meta),
        Chunk(id="c2", doc_id="d1", text="Operating expenses were $2M.", embedding=[0.8, 0.2], metadata=meta)
    ]
    
    # Test In-Memory Repository
    in_mem_repo = InMemoryVectorRepository()
    in_mem_repo.insert_chunks(chunks)
    
    # Vector Search
    vector_results = in_mem_repo.query_similarity(query_vector=[0.12, 0.88], limit=1, filters={"workspace": "marketing"})
    assert len(vector_results) == 1
    assert vector_results[0][0].id == "c1"
    
    # Keyword Search
    keyword_results = in_mem_repo.keyword_search("operating expenses", limit=1)
    assert len(keyword_results) == 1
    assert keyword_results[0][0].id == "c2"
    
    # Test persistent DuckDB Repository
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_rag.db")
    
    duck_repo = DuckDBVectorRepository(db_path=db_path)
    duck_repo.insert_chunks(chunks)
    
    # List documents
    docs = duck_repo.list_documents(workspace="marketing")
    assert len(docs) == 1
    assert docs[0]["filename"] == "business.txt"
    
    # Vector search in DuckDB
    duck_vector_res = duck_repo.query_similarity(query_vector=[0.78, 0.22], limit=1, filters={"workspace": "marketing"})
    assert len(duck_vector_res) == 1
    assert duck_vector_res[0][0].id == "c2"
    
    # Delete doc
    duck_repo.delete_by_document("d1")
    assert len(duck_repo.list_documents("marketing")) == 0
    
    shutil.rmtree(temp_dir)

# 6. Retrieval & Context Builder Unit Tests
def test_retrieval_and_context_builder():
    repo = InMemoryVectorRepository()
    embeddings = MockEmbeddingProvider()
    
    meta = DocumentMetadata(filename="doc1.txt", document_type="TXT", workspace="sales")
    chunks = [
        Chunk(id="ch1", doc_id="dc1", text="Q4 sales forecasts show upward trends.", embedding=embeddings.get_embedding("Q4 sales forecasts show upward trends."), metadata=meta),
        Chunk(id="ch2", doc_id="dc1", text="Marketing leads are rising by 15 percent.", embedding=embeddings.get_embedding("Marketing leads are rising by 15 percent."), metadata=meta)
    ]
    repo.insert_chunks(chunks)
    
    retrieval_svc = RetrievalService(vector_repo=repo, embedding_provider=embeddings)
    
    # Test hybrid RRF retrieval
    results = retrieval_svc.retrieve(query="Q4 sales", limit=1, hybrid_alpha=0.5)
    assert len(results) == 1
    assert results[0].doc_id == "dc1"
    assert results[0].citation.filename == "doc1.txt"
    
    # Test Context Builder
    context_text, token_count = ContextBuilder.build_context(results, max_tokens=100)
    assert "[Source Reference #1" in context_text
    assert "Q4 sales forecasts" in context_text
    assert token_count > 0

# 7. Evaluation Service Unit Tests
def test_evaluation_service():
    repo = InMemoryVectorRepository()
    embeddings = MockEmbeddingProvider()
    
    meta = DocumentMetadata(filename="doc1.txt", document_type="TXT", workspace="default")
    chunks = [
        Chunk(id="ch1", doc_id="dc1", text="Annual report summary details.", embedding=embeddings.get_embedding("Annual report summary details."), metadata=meta)
    ]
    repo.insert_chunks(chunks)
    
    retrieval_svc = RetrievalService(vector_repo=repo, embedding_provider=embeddings)
    
    ground_truth = [
        GroundTruthItem(query="Annual report", expected_doc_ids=["dc1"])
    ]
    
    metrics = RAGEvaluationService.evaluate_retrieval(retrieval_svc, ground_truth, limit=1)
    assert metrics.hit_rate == 1.0
    assert metrics.mrr == 1.0
    assert metrics.precision_at_k == 1.0
    assert metrics.total_queries == 1

# 8. API Integration Tests (using TestClient)
def test_rag_api_endpoints():
    client = TestClient(app)
    
    # Test 1: Ingest document via API
    # Create simple text file payload
    file_content = b"Financial statements for 2026. Sales grew by 20% year over year."
    files = {"file": ("financials.txt", file_content, "text/plain")}
    data = {
        "author": "Chief Financial Officer",
        "workspace": "finance",
        "tags": "finance,sales,2026"
    }
    
    response = client.post("/api/v1/rag/ingest", files=files, data=data)
    assert response.status_code == 201
    resp_json = response.json()
    assert resp_json["status"] == "success"
    assert "doc_id" in resp_json
    assert resp_json["chunks_count"] > 0
    
    doc_id = resp_json["doc_id"]
    
    # Test 2: Retrieve context via API
    retrieve_payload = {
        "query": "financial statements 2026 sales growth",
        "limit": 3,
        "filters": {"workspace": "finance"},
        "hybrid_alpha": 0.5,
        "enable_rerank": True
    }
    retrieve_resp = client.post("/api/v1/rag/retrieve", json=retrieve_payload)
    assert retrieve_resp.status_code == 200
    retrieve_json = retrieve_resp.json()
    assert "context_text" in retrieve_json
    assert len(retrieve_json["results"]) > 0
    assert retrieve_json["results"][0]["doc_id"] == doc_id
    
    # Test 3: List documents via API
    docs_resp = client.get("/api/v1/rag/documents?workspace=finance")
    assert docs_resp.status_code == 200
    docs_json = docs_resp.json()
    assert len(docs_json) > 0
    assert docs_json[0]["filename"] == "financials.txt"
    
    # Test 4: Evaluate RAG via API
    eval_payload = {
        "benchmark_dataset": [
            {
                "query": "financial statements sales growth",
                "expected_doc_ids": [doc_id]
            }
        ],
        "limit": 2
    }
    eval_resp = client.post("/api/v1/rag/evaluate", json=eval_payload)
    assert eval_resp.status_code == 200
    eval_json = eval_resp.json()
    assert eval_json["hit_rate"] == 1.0
    assert eval_json["total_queries"] == 1
    
    # Test 5: Delete document via API
    delete_resp = client.delete(f"/api/v1/rag/documents/{doc_id}")
    assert delete_resp.status_code == 200
    delete_json = delete_resp.json()
    assert delete_json["status"] == "success"
    
    # List documents again (should be empty for finance workspace)
    docs_resp_after = client.get("/api/v1/rag/documents?workspace=finance")
    assert len(docs_resp_after.json()) == 0
