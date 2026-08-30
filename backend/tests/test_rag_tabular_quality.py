import pytest
import os
import io
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.features.rag.ingestion.parsers import CsvParser, DocumentParserService
from app.features.rag.ingestion.chunker import ChunkerService
from app.features.rag.embeddings.providers import MockEmbeddingProvider
from app.features.rag.vector_store.repository import InMemoryVectorRepository
from app.features.rag.retrieval.service import RetrievalService, MockReranker
from app.features.rag.retrieval.context_builder import ContextBuilder
from app.features.rag.schemas import Chunk, DocumentMetadata

MONTHLY_TRENDS_CSV = """Month,Total Reviews,Positive Reviews,Negative Reviews,Average Rating
Jan 2024,120,95,25,4.2
Feb 2024,150,125,25,4.4
Mar 2024,180,155,25,4.5
Apr 2024,210,190,20,4.7
May 2024,200,180,20,4.6"""


def test_csv_parser_schema_preservation():
    parser = CsvParser()
    parsed_text = parser.parse(MONTHLY_TRENDS_CSV.encode("utf-8"), "monthly_trends.csv")
    
    assert "[TABULAR_DATA: monthly_trends.csv]" in parsed_text
    assert "[SCHEMA: Month | Total Reviews | Positive Reviews | Negative Reviews | Average Rating]" in parsed_text
    assert "Row 1 -> Month: Jan 2024 | Total Reviews: 120" in parsed_text
    assert "Row 4 -> Month: Apr 2024 | Total Reviews: 210" in parsed_text


def test_tabular_chunker_structure_and_headings():
    parser = CsvParser()
    parsed_text = parser.parse(MONTHLY_TRENDS_CSV.encode("utf-8"), "monthly_trends.csv")
    
    chunker = ChunkerService()
    chunks = chunker.chunk_by_heading(parsed_text)
    
    assert len(chunks) > 0
    first_chunk = chunks[0]
    
    # Heading must be descriptive and non-generic (not "Introduction")
    assert first_chunk["heading"] != "Introduction"
    assert "monthly_trends.csv" in first_chunk["heading"]
    assert "Rows 1-" in first_chunk["heading"]
    
    # Text must include Schema, Markdown Table, and Key-Value Row context
    chunk_text = first_chunk["text"]
    assert "### Dataset: monthly_trends.csv" in chunk_text
    assert "| Month | Total Reviews | Positive Reviews | Negative Reviews | Average Rating |" in chunk_text
    assert "| Jan 2024 | 120 | 95 | 25 | 4.2 |" in chunk_text
    assert "Row 1 -> Month: Jan 2024" in chunk_text


def test_rag_retrieval_and_reranking_monthly_trends():
    parser = CsvParser()
    parsed_text = parser.parse(MONTHLY_TRENDS_CSV.encode("utf-8"), "monthly_trends.csv")
    
    chunker = ChunkerService()
    chunk_dicts = chunker.chunk_by_heading(parsed_text)
    
    embeddings = MockEmbeddingProvider()
    repo = InMemoryVectorRepository()
    
    doc_id = "doc-monthly-trends"
    chunks = []
    for i, cd in enumerate(chunk_dicts):
        meta = DocumentMetadata(
            filename="monthly_trends.csv",
            document_type="CSV",
            workspace="analytics",
            page=i + 1,
            heading=cd["heading"]
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
    
    # Query 1: Average rating in January 2024
    q1 = "What was the average rating in January 2024?"
    res1 = retrieval_svc.retrieve(query=q1, limit=3, filters={"workspace": "analytics"}, enable_rerank=True)
    assert len(res1) > 0
    assert res1[0].citation.filename == "monthly_trends.csv"
    assert res1[0].score > 0.50
    
    ans1 = ContextBuilder.generate_grounded_answer(q1, res1)
    assert ans1["grounded"] is True
    assert "4.2" in ans1["answer"]
    assert "monthly_trends.csv" in ans1["answer"]
    
    # Query 2: Month with highest review count
    q2 = "Which month had the highest review count?"
    res2 = retrieval_svc.retrieve(query=q2, limit=3, filters={"workspace": "analytics"}, enable_rerank=True)
    assert len(res2) > 0
    ans2 = ContextBuilder.generate_grounded_answer(q2, res2)
    assert ans2["grounded"] is True
    assert "Apr 2024" in ans2["answer"] or "April" in ans2["answer"]
    assert "210" in ans2["answer"]
    
    # Query 3: Trend of positive reviews over time
    q3 = "What trend do positive reviews show over time?"
    res3 = retrieval_svc.retrieve(query=q3, limit=3, filters={"workspace": "analytics"}, enable_rerank=True)
    assert len(res3) > 0
    ans3 = ContextBuilder.generate_grounded_answer(q3, res3)
    assert ans3["grounded"] is True
    assert "upward trend" in ans3["answer"].lower() or "positive" in ans3["answer"].lower()
    assert "monthly_trends.csv" in ans3["answer"]


def test_api_rag_ingest_and_retrieve_tabular():
    client = TestClient(app)
    
    files = {"file": ("monthly_trends.csv", MONTHLY_TRENDS_CSV.encode("utf-8"), "text/csv")}
    data = {
        "author": "Data Analyst",
        "workspace": "e2e_test_workspace",
        "tags": "monthly,trends,reviews"
    }
    
    # Ingest CSV
    ingest_resp = client.post("/api/v1/rag/ingest", files=files, data=data)
    assert ingest_resp.status_code == 201
    ingest_json = ingest_resp.json()
    assert ingest_json["status"] == "success"
    doc_id = ingest_json["doc_id"]
    
    # Retrieve context
    query_payload = {
        "query": "What was the average rating in January 2024?",
        "limit": 3,
        "filters": {"workspace": "e2e_test_workspace"},
        "hybrid_alpha": 0.5,
        "enable_rerank": True
    }
    ret_resp = client.post("/api/v1/rag/retrieve", json=query_payload)
    assert ret_resp.status_code == 200
    ret_json = ret_resp.json()
    
    assert len(ret_json["results"]) > 0
    assert ret_json["results"][0]["citation"]["filename"] == "monthly_trends.csv"
    assert ret_json["results"][0]["score"] > 0.50
    assert "Jan 2024" in ret_json["context_text"]
    assert "Average Rating" in ret_json["context_text"]
    
    # Delete uploaded test doc
    del_resp = client.delete(f"/api/v1/rag/documents/{doc_id}")
    assert del_resp.status_code == 200
