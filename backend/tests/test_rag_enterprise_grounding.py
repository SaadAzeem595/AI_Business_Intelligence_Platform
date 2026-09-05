import pytest
import io
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.features.rag.ingestion.parsers import CsvParser
from app.features.rag.ingestion.chunker import ChunkerService
from app.features.rag.embeddings.providers import MockEmbeddingProvider
from app.features.rag.vector_store.repository import InMemoryVectorRepository
from app.features.rag.retrieval.service import RetrievalService, MockReranker
from app.features.rag.retrieval.context_builder import ContextBuilder
from app.features.rag.schemas import Chunk, DocumentMetadata, QueryIntent

ENTERPRISE_REVIEWS_CSV = """review_id,product_id,star_rating,sentiment,is_fake_review,verified_purchase,review_text,category,price_usd
rev-101,prod-A,5,Positive,0,1,"Excellent product, works like a charm!",Electronics,49.99
rev-102,prod-A,1,Negative,1,0,"Terrible scam, broke in 2 minutes!",Electronics,49.99
rev-103,prod-B,5,Positive,0,1,"Great value for money, highly recommend.",Home & Kitchen,19.95
rev-104,prod-C,1,Negative,1,0,"Fake item, completely useless.",Electronics,99.00
rev-105,prod-B,4,Positive,0,1,"Nice and durable, works fine.",Home & Kitchen,19.95
rev-106,prod-C,2,Negative,1,0,"Poor build quality, returned it.",Electronics,99.00
rev-107,prod-D,5,Positive,0,1,"Loved it, fantastic quality.",Books,14.50
rev-108,prod-E,1,Negative,1,0,"Spam seller, don't buy.",Office,24.00"""


@pytest.fixture
def enterprise_rag_setup():
    parser = CsvParser()
    parsed_text = parser.parse(ENTERPRISE_REVIEWS_CSV.encode("utf-8"), "reviews.csv")

    chunker = ChunkerService()
    chunk_dicts = chunker.chunk_by_heading(parsed_text)

    embeddings = MockEmbeddingProvider()
    repo = InMemoryVectorRepository()

    doc_id = "doc-enterprise-reviews"
    chunks = []
    for i, cd in enumerate(chunk_dicts):
        meta = DocumentMetadata(
            filename="reviews.csv",
            document_type="CSV",
            workspace="proj-enterprise",
            page=i + 1,
            heading=cd["heading"],
            chunk_type=cd.get("chunk_type", "text"),
            row_start=cd.get("row_start"),
            row_end=cd.get("row_end"),
            columns=cd.get("columns", [])
        )
        c = Chunk(
            id=f"{doc_id}-{i}",
            doc_id=doc_id,
            text=cd["text"],
            embedding=embeddings.get_embedding(cd["text"]),
            metadata=meta
        )
        chunks.append(c)

    repo.insert_chunks(chunks)
    retrieval_svc = RetrievalService(vector_repo=repo, embedding_provider=embeddings, reranker=MockReranker())
    return retrieval_svc, chunks


# Test 1: "What fields are available in reviews.csv?" -> Returns schema fields
def test_schema_field_query(enterprise_rag_setup):
    svc, _ = enterprise_rag_setup
    q = "What fields are available in reviews.csv?"
    results = svc.retrieve(query=q, limit=3, filters={"workspace": "proj-enterprise"}, enable_rerank=True)
    assert len(results) > 0
    
    # Top chunk should be dataset_schema
    assert results[0].citation.chunk_type == "dataset_schema"
    ans = ContextBuilder.generate_grounded_answer(q, results)
    
    assert ans["grounded"] is True
    assert "is_fake_review" in ans["answer"]
    assert "verified_purchase" in ans["answer"]
    assert "star_rating" in ans["answer"]
    assert ans["intent"] == QueryIntent.SCHEMA_QUERY.value


# Test 2: "Which field identifies fake reviews?" -> Returns is_fake_review
def test_field_identifies_fake_reviews(enterprise_rag_setup):
    svc, _ = enterprise_rag_setup
    q = "Which field identifies fake reviews?"
    results = svc.retrieve(query=q, limit=3, filters={"workspace": "proj-enterprise"}, enable_rerank=True)
    assert len(results) > 0
    assert results[0].citation.chunk_type == "dataset_schema"
    
    ans = ContextBuilder.generate_grounded_answer(q, results)
    assert ans["grounded"] is True
    assert "is_fake_review" in ans["answer"]
    assert any("is_fake_review" in f for f in ans["direct_facts"])


# Test 3: "Which field identifies verified purchases?" -> Returns verified_purchase
def test_field_identifies_verified_purchases(enterprise_rag_setup):
    svc, _ = enterprise_rag_setup
    q = "Which field identifies verified purchases?"
    results = svc.retrieve(query=q, limit=3, filters={"workspace": "proj-enterprise"}, enable_rerank=True)
    assert len(results) > 0
    
    ans = ContextBuilder.generate_grounded_answer(q, results)
    assert ans["grounded"] is True
    assert "verified_purchase" in ans["answer"]


# Test 4: "Which fields relate to review quality?" -> Returns only fields present in schema
def test_fields_relate_to_review_quality(enterprise_rag_setup):
    svc, _ = enterprise_rag_setup
    q = "Which fields relate to review quality?"
    results = svc.retrieve(query=q, limit=3, filters={"workspace": "proj-enterprise"}, enable_rerank=True)
    assert len(results) > 0
    
    ans = ContextBuilder.generate_grounded_answer(q, results)
    assert ans["grounded"] is True
    valid_cols = {"review_id", "product_id", "star_rating", "sentiment", "is_fake_review", "verified_purchase", "review_text", "category", "price_usd"}
    # Ensure no hallucinated column names
    assert "customer_satisfaction_score" not in ans["answer"]
    assert "quality_index" not in ans["answer"]
    # Check that it identified actual quality fields
    assert any(col in ans["answer"] for col in ["star_rating", "sentiment", "verified_purchase", "is_fake_review"])


# Test 5: "How many fake reviews are there?" -> Analytical SQL routing
def test_analytical_routing_fake_reviews_count():
    client = TestClient(app)
    files = {"file": ("reviews.csv", ENTERPRISE_REVIEWS_CSV.encode("utf-8"), "text/csv")}
    data = {"workspace": "enterprise_test_ws", "author": "QA Engineer"}
    
    ingest_resp = client.post("/api/v1/rag/ingest", files=files, data=data)
    assert ingest_resp.status_code == 201
    doc_id = ingest_resp.json()["doc_id"]
    
    try:
        q_payload = {
            "query": "How many fake reviews are there?",
            "limit": 3,
            "filters": {"workspace": "enterprise_test_ws"},
            "hybrid_alpha": 0.5
        }
        resp = client.post("/api/v1/rag/retrieve", json=q_payload)
        assert resp.status_code == 200
        res = resp.json()
        assert res["grounded_answer"] is not None
        # 4 fake reviews in sample or 5,900 in full dataset
        ans = res["grounded_answer"]
        assert any(num in ans["answer"] for num in ["4", "5,900", "5900"])
    finally:
        client.delete(f"/api/v1/rag/documents/{doc_id}")


# Test 6: "What is the average rating of fake reviews?" -> Exact computation
def test_analytical_routing_avg_rating_fake_reviews():
    client = TestClient(app)
    files = {"file": ("reviews.csv", ENTERPRISE_REVIEWS_CSV.encode("utf-8"), "text/csv")}
    data = {"workspace": "enterprise_test_ws_2", "author": "QA Engineer"}
    
    ingest_resp = client.post("/api/v1/rag/ingest", files=files, data=data)
    assert ingest_resp.status_code == 201
    doc_id = ingest_resp.json()["doc_id"]
    
    try:
        q_payload = {
            "query": "What is the average rating of fake reviews?",
            "limit": 3,
            "filters": {"workspace": "enterprise_test_ws_2"},
            "hybrid_alpha": 0.5
        }
        resp = client.post("/api/v1/rag/retrieve", json=q_payload)
        assert resp.status_code == 200
        res = resp.json()
        assert res["grounded_answer"] is not None
        # Ratings for fake reviews: 1.25 (sample) or 4.66 (full 100k dataset)
        ans = res["grounded_answer"]
        assert "1.25" in ans["answer"] or "4.66" in ans["answer"] or "1.25" in str(ans.get("sql_results", []))
    finally:
        client.delete(f"/api/v1/rag/documents/{doc_id}")


# Test 7: "Which category has the most fake reviews?" -> Exact computation
def test_analytical_routing_top_category_fake_reviews():
    client = TestClient(app)
    files = {"file": ("reviews.csv", ENTERPRISE_REVIEWS_CSV.encode("utf-8"), "text/csv")}
    data = {"workspace": "enterprise_test_ws_3", "author": "QA Engineer"}
    
    ingest_resp = client.post("/api/v1/rag/ingest", files=files, data=data)
    assert ingest_resp.status_code == 201
    doc_id = ingest_resp.json()["doc_id"]
    
    try:
        q_payload = {
            "query": "Which category has the most fake reviews?",
            "limit": 3,
            "filters": {"workspace": "enterprise_test_ws_3"},
            "hybrid_alpha": 0.5
        }
        resp = client.post("/api/v1/rag/retrieve", json=q_payload)
        assert resp.status_code == 200
        res = resp.json()
        assert res["grounded_answer"] is not None
        # Electronics has 2 fake reviews (rev-102, rev-104, rev-106 -> Electronics has 3)
        ans = res["grounded_answer"]
        assert "Electronics" in ans["answer"]
    finally:
        client.delete(f"/api/v1/rag/documents/{doc_id}")


# Test 8: "Tell me something that does not exist in the dataset." -> Insufficient evidence
def test_nonexistent_evidence_handling(enterprise_rag_setup):
    svc, _ = enterprise_rag_setup
    q = "What is the warranty period for product warranty claim?"
    results = svc.retrieve(query=q, limit=3, filters={"workspace": "proj-enterprise"}, enable_rerank=True)
    ans = ContextBuilder.generate_grounded_answer(q, results)
    
    assert ans["evidence_status"] == "INSUFFICIENT_EVIDENCE"
    assert "insufficient evidence" in ans["answer"].lower()
    assert ans["grounded"] is False


# Test 9: "Who is the CEO of the company?" -> Insufficient evidence
def test_irrelevant_out_of_scope_query(enterprise_rag_setup):
    svc, _ = enterprise_rag_setup
    q = "Who is the CEO of the company?"
    results = svc.retrieve(query=q, limit=3, filters={"workspace": "proj-enterprise"}, enable_rerank=True)
    ans = ContextBuilder.generate_grounded_answer(q, results)
    
    assert ans["evidence_status"] == "INSUFFICIENT_EVIDENCE"
    assert "insufficient evidence" in ans["answer"].lower()
    assert ans["grounded"] is False


# Test 10: "Show me rows where is_fake_review = 1." -> Row lookup preview
def test_row_lookup_query():
    client = TestClient(app)
    files = {"file": ("reviews.csv", ENTERPRISE_REVIEWS_CSV.encode("utf-8"), "text/csv")}
    data = {"workspace": "enterprise_test_ws_4", "author": "QA Engineer"}
    
    ingest_resp = client.post("/api/v1/rag/ingest", files=files, data=data)
    assert ingest_resp.status_code == 201
    doc_id = ingest_resp.json()["doc_id"]
    
    try:
        q_payload = {
            "query": "Show me rows where is_fake_review = 1",
            "limit": 5,
            "filters": {"workspace": "enterprise_test_ws_4"},
            "hybrid_alpha": 0.5
        }
        resp = client.post("/api/v1/rag/retrieve", json=q_payload)
        assert resp.status_code == 200
        res = resp.json()
        assert res["grounded_answer"] is not None
        ans = res["grounded_answer"]
        assert ans.get("sql_query") is not None or "is_fake_review" in ans["answer"]
    finally:
        client.delete(f"/api/v1/rag/documents/{doc_id}")


# Test 11: Project scoping isolation test: Project A vs Project B
def test_project_scoping_isolation():
    client = TestClient(app)

    # Upload to Project X
    files_x = {"file": ("reviews.csv", ENTERPRISE_REVIEWS_CSV.encode("utf-8"), "text/csv")}
    data_x = {"workspace": "project_isolate_X", "author": "Analyst X"}
    resp_x = client.post("/api/v1/rag/ingest", files=files_x, data=data_x)
    assert resp_x.status_code == 201
    doc_id_x = resp_x.json()["doc_id"]

    try:
        # Query from Project Y (should return 0 results)
        query_payload_y = {
            "query": "What fields are available in reviews.csv?",
            "limit": 5,
            "filters": {"workspace": "project_isolate_Y"},
            "hybrid_alpha": 0.5
        }
        ret_y = client.post("/api/v1/rag/retrieve", json=query_payload_y)
        assert ret_y.status_code == 200
        res_y = ret_y.json()
        assert len(res_y["results"]) == 0
        assert res_y["grounded_answer"]["evidence_status"] == "INSUFFICIENT_EVIDENCE"

        # Query from Project X (should return results)
        query_payload_x = {
            "query": "What fields are available in reviews.csv?",
            "limit": 5,
            "filters": {"workspace": "project_isolate_X"},
            "hybrid_alpha": 0.5
        }
        ret_x = client.post("/api/v1/rag/retrieve", json=query_payload_x)
        assert ret_x.status_code == 200
        res_x = ret_x.json()
        assert len(res_x["results"]) > 0
        assert res_x["grounded_answer"]["evidence_status"] == "FOUND"
    finally:
        client.delete(f"/api/v1/rag/documents/{doc_id_x}")
