import pytest
import io
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.features.rag.ingestion.parsers import CsvParser
from app.features.rag.ingestion.chunker import ChunkerService
from app.features.rag.embeddings.providers import MockEmbeddingProvider
from app.features.rag.vector_store.repository import InMemoryVectorRepository, DuckDBVectorRepository
from app.features.rag.retrieval.service import RetrievalService
from app.features.rag.schemas import Chunk, DocumentMetadata

SAMPLE_REVIEWS_CSV = """review_id,product_id,star_rating,sentiment,is_fake_review,category,price_usd
rev-101,prod-A,5,Positive,0,Electronics,49.99
rev-102,prod-A,1,Negative,1,Electronics,49.99
rev-103,prod-B,5,Positive,0,Home & Kitchen,19.95
rev-104,prod-C,2,Negative,1,Electronics,99.00
rev-105,prod-B,4,Positive,0,Home & Kitchen,19.95"""


def test_csv_schema_and_summary_chunking():
    parser = CsvParser()
    parsed_text = parser.parse(SAMPLE_REVIEWS_CSV.encode("utf-8"), "reviews.csv")

    chunker = ChunkerService()
    chunks = chunker.chunk_by_heading(parsed_text)

    # Check for Schema Chunk
    schema_chunks = [c for c in chunks if c.get("chunk_type") == "dataset_schema"]
    assert len(schema_chunks) == 1
    assert "Dataset Schema: reviews.csv" in schema_chunks[0]["heading"]
    assert "star_rating" in schema_chunks[0]["columns"]
    assert "is_fake_review" in schema_chunks[0]["columns"]

    # Check for Summary Chunk
    summary_chunks = [c for c in chunks if c.get("chunk_type") == "dataset_summary"]
    assert len(summary_chunks) == 1
    assert "Dataset Summary: reviews.csv" in summary_chunks[0]["heading"]
    assert "contains 5 rows and 7 columns" in summary_chunks[0]["text"]

    # Check for Row Chunks
    row_chunks = [c for c in chunks if c.get("chunk_type") == "table_rows"]
    assert len(row_chunks) >= 1
    assert row_chunks[0]["row_start"] == 1
    assert row_chunks[0]["row_end"] == 5


def test_rrf_score_normalization_and_explanations():
    parser = CsvParser()
    parsed_text = parser.parse(SAMPLE_REVIEWS_CSV.encode("utf-8"), "reviews.csv")

    chunker = ChunkerService()
    chunk_dicts = chunker.chunk_by_heading(parsed_text)

    embeddings = MockEmbeddingProvider()
    repo = InMemoryVectorRepository()

    doc_id = "doc-reviews-001"
    chunks = []
    for i, cd in enumerate(chunk_dicts):
        meta = DocumentMetadata(
            filename="reviews.csv",
            document_type="CSV",
            workspace="proj-alpha",
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
    retrieval_svc = RetrievalService(vector_repo=repo, embedding_provider=embeddings)

    # Hybrid search
    results = retrieval_svc.retrieve(
        query="Which fields identify fake reviews?",
        limit=3,
        filters={"workspace": "proj-alpha"},
        hybrid_alpha=0.5
    )

    assert len(results) > 0
    top_hit = results[0]
    
    # Verify normalized score is high (>= 0.50), NOT 2% or 3%
    assert top_hit.score >= 0.50
    assert top_hit.relevance_label in ("Highly Relevant", "Relevant")
    assert top_hit.explanation is not None
    assert len(top_hit.explanation) > 0


def test_api_analytical_routing_and_project_isolation():
    client = TestClient(app)

    # Ingest CSV into Project A
    files_a = {"file": ("reviews.csv", SAMPLE_REVIEWS_CSV.encode("utf-8"), "text/csv")}
    data_a = {"workspace": "project_A", "author": "Analyst"}
    resp_a = client.post("/api/v1/rag/ingest", files=files_a, data=data_a)
    assert resp_a.status_code == 201

    # Search in Project A
    query_payload_a = {
        "query": "What percentage of reviews are fake?",
        "limit": 3,
        "filters": {"workspace": "project_A"},
        "hybrid_alpha": 0.5
    }
    ret_a = client.post("/api/v1/rag/retrieve", json=query_payload_a)
    assert ret_a.status_code == 200
    res_a_json = ret_a.json()
    assert len(res_a_json["results"]) > 0

    # Confirm normalized score is >= 0.50
    assert res_a_json["results"][0]["score"] >= 0.50

    # Search in Project B (should return 0 results due to strict project scoping)
    query_payload_b = {
        "query": "What percentage of reviews are fake?",
        "limit": 3,
        "filters": {"workspace": "project_B"},
        "hybrid_alpha": 0.5
    }
    ret_b = client.post("/api/v1/rag/retrieve", json=query_payload_b)
    assert ret_b.status_code == 200
    res_b_json = ret_b.json()
    assert len(res_b_json["results"]) == 0

    # Delete doc
    doc_id = resp_a.json()["doc_id"]
    del_resp = client.delete(f"/api/v1/rag/documents/{doc_id}")
    assert del_resp.status_code == 200
