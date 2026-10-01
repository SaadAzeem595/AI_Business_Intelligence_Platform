import time
from app.features.rag.vector_store.repository import DuckDBVectorRepository
from app.features.rag.embeddings.providers import MockEmbeddingProvider
from app.features.rag.retrieval.service import RetrievalService

repo = DuckDBVectorRepository(db_path="rag_vector.db")
embeddings = MockEmbeddingProvider()
svc = RetrievalService(vector_repo=repo, embedding_provider=embeddings)

query = "What does total_order_value mean according to the Olist business dictionary?"
filters = {"workspace": "proj-2d1a2d1d"}

print("Starting test...")
t0 = time.time()
try:
    res = svc.retrieve(query=query, limit=5, filters=filters, hybrid_alpha=0.5)
    print(f"Retrieved {len(res)} results in {time.time() - t0:.2f}s:")
    for r in res:
        print(" -", r.chunk_id, r.score, r.citation.filename, r.citation.heading)
except Exception as e:
    import traceback
    traceback.print_exc()
