import os
import sys
import uuid
from datetime import datetime

# Set up python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.features.rag.schemas import DocumentMetadata, Chunk
from app.features.rag.embeddings.providers import OpenRouterEmbeddingProvider, SemanticProjectionEmbeddingProvider
from app.features.rag.vector_store.repository import DuckDBVectorRepository
from app.features.rag.retrieval.service import RetrievalService
from app.features.rag.retrieval.context_builder import ContextBuilder
from app.features.rag.ingestion.parsers import DocumentParserService
from app.features.rag.ingestion.ocr import MockOCRProvider
from app.features.rag.ingestion.cleaner import TextCleaner
from app.features.rag.ingestion.chunker import ChunkerService

def run_tests():
    print("=" * 60)
    print("STARTING END-TO-END RAG PIPELINE VERIFICATION SUITE")
    print("=" * 60)
    
    # 1. Initialize repository and embedding provider
    print(f"\n[1] Initializing Vector Repository at: {settings.resolved_rag_db_path}")
    repo = DuckDBVectorRepository(db_path=settings.resolved_rag_db_path)
    
    print(f"[2] Initializing Embedding Provider: {settings.EMBEDDING_PROVIDER} ({settings.EMBEDDING_MODEL})")
    embeddings = OpenRouterEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION, model=settings.EMBEDDING_MODEL)
    
    parser = DocumentParserService(ocr_provider=MockOCRProvider())
    chunker = ChunkerService()
    retrieval_svc = RetrievalService(vector_repo=repo, embedding_provider=embeddings)
    
    test_project = "proj-olist-test"
    isolated_project = "proj-isolated-other"

    # Clean previous test entries if any
    try:
        for doc in repo.list_documents(workspace=test_project):
            repo.delete_by_document(doc["doc_id"])
        for doc in repo.list_documents(workspace=isolated_project):
            repo.delete_by_document(doc["doc_id"])
    except Exception as e:
        print(f"Cleanup note: {e}")

    # Helper function to ingest a file
    def ingest_file(filepath: str, filename: str, proj: str, doc_id: str):
        with open(filepath, "rb") as f:
            content = f.read()
        raw_text = parser.parse_file(content, filename)
        clean_text = TextCleaner.normalize_text(raw_text)
        chunk_dicts = chunker.chunk_by_heading(clean_text)
        chunk_texts = [cd["text"] for cd in chunk_dicts]
        chunk_embs = embeddings.get_embeddings(chunk_texts)
        
        chunks = []
        ext = filename.split(".")[-1].lower() if "." in filename else "txt"
        doc_type = "MD" if ext in ("md", "markdown") else ext.upper()
        
        for i, cd in enumerate(chunk_dicts):
            meta = DocumentMetadata(
                filename=filename,
                author="Analyst",
                upload_date=datetime.now().strftime("%Y-%m-%d"),
                workspace=proj,
                project_id=proj,
                page=i + 1,
                chunk_index=i,
                heading=cd["heading"],
                tags=["olist", "production"],
                document_type=doc_type,
                file_type=ext,
                file_size=len(content),
                chunk_type=cd.get("chunk_type", "text"),
                row_start=cd.get("row_start"),
                row_end=cd.get("row_end"),
                columns=cd.get("columns", []),
                table_name=cd.get("table_name")
            )
            c = Chunk(
                id=f"{doc_id}-{i}",
                doc_id=doc_id,
                text=cd["text"],
                embedding=chunk_embs[i],
                metadata=meta
            )
            chunks.append(c)
            
        repo.delete_by_document(doc_id)
        repo.insert_chunks(chunks)
        print(f"Indexed '{filename}': {len(chunks)} chunks into '{proj}' (doc_id={doc_id})")
        return chunks

    # 2. Ingest test documents
    print("\n--- INGESTION ---")
    csv_path = "app/uploads/320431a1-9b2b-4653-90b9-dc9d1e0cf56b_olist_products_dataset.csv"
    md_path = "../olist_business_dictionary.md"
    
    doc1_id = "doc-olist-products"
    doc2_id = "doc-olist-dictionary"
    doc_iso_id = "doc-secret-project-b"
    
    ingest_file(csv_path, "olist_products_dataset.csv", test_project, doc1_id)
    ingest_file(md_path, "olist_business_dictionary.md", test_project, doc2_id)
    
    # Ingest isolated doc into Project B
    with open("temp_proj_b.txt", "w", encoding="utf-8") as tf:
        tf.write("Confidential Project B Data: Quantum Supercomputer internal architecture.")
    ingest_file("temp_proj_b.txt", "project_b_secrets.txt", isolated_project, doc_iso_id)
    if os.path.exists("temp_proj_b.txt"):
        os.remove("temp_proj_b.txt")

    # 3. Document Diagnostics Check
    print("\n--- DOCUMENT DIAGNOSTICS ---")
    d1_diag = repo.get_document_diagnostics(doc1_id)
    print(f"Doc 1 Diagnostics: status={d1_diag['status']}, chunks={d1_diag['chunk_count']}, embedded={d1_diag['embedded_chunk_count']}, searchable={d1_diag['searchable']}, dim={d1_diag['embedding_dimension']}")
    assert d1_diag["searchable"] is True
    assert d1_diag["chunk_count"] > 0
    assert d1_diag["embedded_chunk_count"] == d1_diag["chunk_count"]

    d2_diag = repo.get_document_diagnostics(doc2_id)
    print(f"Doc 2 Diagnostics: status={d2_diag['status']}, chunks={d2_diag['chunk_count']}, embedded={d2_diag['embedded_chunk_count']}, searchable={d2_diag['searchable']}, dim={d2_diag['embedding_dimension']}")
    assert d2_diag["searchable"] is True

    # 4. Execute Real Test Queries
    print("\n--- REAL QUERIES TESTING ---")
    filters = {"workspace": test_project}
    
    # Test 1: What columns are available in olist_products_dataset.csv?
    print("\n[Test 1] Query: 'What columns are available in olist_products_dataset.csv?'")
    res1, diag1 = retrieval_svc.retrieve("What columns are available in olist_products_dataset.csv?", limit=5, filters=filters, hybrid_alpha=0.5, return_diagnostics=True)
    ans1 = ContextBuilder.generate_grounded_answer("What columns are available in olist_products_dataset.csv?", res1)
    print(f"Hits: {len(res1)} | BM25: {diag1.bm25_candidates} | Dense: {diag1.dense_candidates} | RRF: {diag1.rrf_candidates}")
    print(f"Answer: {ans1['answer'][:180]}...")
    assert len(res1) > 0, "Test 1 failed: Expected > 0 chunks"
    assert any("olist_products_dataset.csv" in r.citation.filename for r in res1)
    assert ans1["grounded"] is True

    # Test 2: Which columns contain information about product dimensions and weight?
    print("\n[Test 2] Query: 'Which columns contain information about product dimensions and weight?'")
    res2, diag2 = retrieval_svc.retrieve("Which columns contain information about product dimensions and weight?", limit=5, filters=filters, hybrid_alpha=0.5, return_diagnostics=True)
    ans2 = ContextBuilder.generate_grounded_answer("Which columns contain information about product dimensions and weight?", res2)
    print(f"Hits: {len(res2)} | Answer: {ans2['answer']}")
    assert len(res2) > 0, "Test 2 failed: Expected > 0 chunks"
    assert any(col in ans2['answer'] for col in ["product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"])

    # Test 3: What product categories are represented in this document?
    print("\n[Test 3] Query: 'What product categories are represented in this document?'")
    res3, diag3 = retrieval_svc.retrieve("What product categories are represented in this document?", limit=5, filters=filters, hybrid_alpha=0.5, return_diagnostics=True)
    ans3 = ContextBuilder.generate_grounded_answer("What product categories are represented in this document?", res3)
    print(f"Hits: {len(res3)} | Answer: {ans3['answer'][:180]}...")
    assert len(res3) > 0, "Test 3 failed: Expected > 0 chunks"
    assert ans3["grounded"] is True

    # Test 4: According to olist_products_dataset.csv, who founded Olist?
    print("\n[Test 4] Query: 'According to olist_products_dataset.csv, who founded Olist?'")
    res4, diag4 = retrieval_svc.retrieve("According to olist_products_dataset.csv, who founded Olist?", limit=5, filters=filters, hybrid_alpha=0.5, return_diagnostics=True)
    ans4 = ContextBuilder.generate_grounded_answer("According to olist_products_dataset.csv, who founded Olist?", res4)
    print(f"Hits: {len(res4)} | Evidence status: {ans4['evidence_status']} | Confidence: {ans4['confidence_score']}")
    print(f"Answer: {ans4['answer']}")
    assert ans4["evidence_status"] == "INSUFFICIENT_EVIDENCE", "Test 4 failed: Must refuse unsupported claims"
    assert ans4["confidence_score"] == 0.0
    assert "Insufficient evidence" in ans4["answer"]

    # Test 5: What does total_order_value mean according to the Olist business dictionary?
    print("\n[Test 5] Query: 'What does total_order_value mean according to the Olist business dictionary?'")
    res5, diag5 = retrieval_svc.retrieve("What does total_order_value mean according to the Olist business dictionary?", limit=5, filters=filters, hybrid_alpha=0.5, return_diagnostics=True)
    ans5 = ContextBuilder.generate_grounded_answer("What does total_order_value mean according to the Olist business dictionary?", res5)
    print(f"Hits: {len(res5)} | Top Hit File: {res5[0].citation.filename} | Top Heading: {res5[0].citation.heading}")
    print(f"Answer: {ans5['answer'][:180]}...")
    assert len(res5) > 0, "Test 5 failed: Expected business dictionary chunk"
    assert any("olist_business_dictionary.md" in r.citation.filename for r in res5)

    # Test 6: Using the Olist business dictionary and product dataset, explain what product information is available and how it should be interpreted.
    print("\n[Test 6] Query: Cross-document explanation")
    q6 = "Using the Olist business dictionary and product dataset, explain what product information is available and how it should be interpreted."
    res6, diag6 = retrieval_svc.retrieve(q6, limit=5, filters=filters, hybrid_alpha=0.5, return_diagnostics=True)
    ans6 = ContextBuilder.generate_grounded_answer(q6, res6)
    retrieved_files = {r.citation.filename for r in res6}
    print(f"Hits: {len(res6)} | Retrieved files: {retrieved_files}")
    print(f"Answer: {ans6['answer'][:200]}...")
    assert len(res6) > 0, "Test 6 failed: Expected chunks"
    assert ans6["grounded"] is True

    # 5. Test Retrieval Modes
    print("\n--- RETRIEVAL MODES COMPARISON ---")
    query_mode = "product weight and dimensions in olist products"
    
    # BM25 only (alpha = 0.0)
    res_bm25, diag_bm25 = retrieval_svc.retrieve(query_mode, limit=5, filters=filters, hybrid_alpha=0.0, return_diagnostics=True)
    print(f"BM25 Only (alpha=0.0): {len(res_bm25)} hits | BM25 candidates: {diag_bm25.bm25_candidates} | Dense candidates: {diag_bm25.dense_candidates}")
    assert len(res_bm25) > 0, "BM25 only search failed"
    assert diag_bm25.dense_candidates == 0

    # Dense only (alpha = 1.0)
    res_dense, diag_dense = retrieval_svc.retrieve(query_mode, limit=5, filters=filters, hybrid_alpha=1.0, return_diagnostics=True)
    print(f"Dense Only (alpha=1.0): {len(res_dense)} hits | BM25 candidates: {diag_dense.bm25_candidates} | Dense candidates: {diag_dense.dense_candidates}")
    assert len(res_dense) > 0, "Dense only search failed"
    assert diag_dense.bm25_candidates == 0

    # Hybrid (alpha = 0.5)
    res_hybrid, diag_hybrid = retrieval_svc.retrieve(query_mode, limit=5, filters=filters, hybrid_alpha=0.5, return_diagnostics=True)
    print(f"Hybrid RRF (alpha=0.5): {len(res_hybrid)} hits | BM25 candidates: {diag_hybrid.bm25_candidates} | Dense candidates: {diag_hybrid.dense_candidates} | RRF: {diag_hybrid.rrf_candidates}")
    assert len(res_hybrid) > 0, "Hybrid search failed"

    # 6. Test Project Isolation
    print("\n--- PROJECT ISOLATION TEST ---")
    # Search Project A for Project B's secret
    res_iso, diag_iso = retrieval_svc.retrieve("Quantum Supercomputer", limit=5, filters={"workspace": test_project}, return_diagnostics=True)
    project_b_leaked = [r for r in res_iso if r.citation.filename == "project_b_secrets.txt" or r.citation.workspace == isolated_project]
    assert len(project_b_leaked) == 0, f"CROSS-PROJECT LEAK DETECTED: {len(project_b_leaked)} chunks from Project B found in Project A!"
    print(f"Verified 0 chunks from Project B leaked into Project A search (total Project A hits: {len(res_iso)}, Project B leaked: 0)")

    # Search Project B for Project B's secret
    res_b, diag_b = retrieval_svc.retrieve("Quantum Supercomputer", limit=5, filters={"workspace": isolated_project}, return_diagnostics=True)
    print(f"Searching Project B for Project B data: {len(res_b)} hits")
    assert len(res_b) > 0, "Project B could not retrieve its own data"
    assert res_b[0].citation.filename == "project_b_secrets.txt"
    print("Project isolation successfully verified!")

    # 7. Test Idempotent Reindex
    print("\n--- IDEMPOTENT REINDEX TEST ---")
    initial_chunks = repo.get_document_chunks_raw(doc1_id)
    initial_count = len(initial_chunks)
    print(f"Before reindex: {initial_count} chunks")
    
    # Reindex doc 1
    ingest_file(csv_path, "olist_products_dataset.csv", test_project, doc1_id)
    after_chunks = repo.get_document_chunks_raw(doc1_id)
    after_count = len(after_chunks)
    print(f"After reindex: {after_count} chunks")
    assert initial_count == after_count, f"Reindex was not idempotent: {initial_count} vs {after_count}"
    print("Reindex idempotency verified!")

    # 8. Test Delete Lifecycle
    print("\n--- DELETE LIFECYCLE TEST ---")
    repo.delete_by_document(doc1_id)
    retrieval_svc.clear_cache()
    deleted_diag = repo.get_document_diagnostics(doc1_id)
    print(f"Deleted doc diagnostics: {deleted_diag}")
    assert deleted_diag is None or deleted_diag.get("status") == "not_found"
    
    res_after_del = retrieval_svc.retrieve("What columns are available in olist_products_dataset.csv?", limit=5, filters=filters)
    assert not any(r.citation.filename == "olist_products_dataset.csv" for r in res_after_del)
    print("Delete lifecycle verified: document chunks completely removed from retrieval.")

    # Re-ingest to leave system in indexed state
    ingest_file(csv_path, "olist_products_dataset.csv", test_project, doc1_id)

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED SUCCESSFULLY! RAG RETRIEVAL PIPELINE VERIFIED.")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
