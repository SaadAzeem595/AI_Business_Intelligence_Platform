import duckdb
from app.features.rag.vector_store.repository import DuckDBVectorRepository
from app.features.rag.embeddings.providers import MockEmbeddingProvider
from app.features.rag.retrieval.service import RetrievalService

repo = DuckDBVectorRepository(db_path="rag_vector.db")
embeddings = MockEmbeddingProvider()
svc = RetrievalService(vector_repo=repo, embedding_provider=embeddings)

query = "What does total_order_value mean according to the Olist business dictionary?"
filters = {"workspace": "proj-2d1a2d1d"}

print(f"=== TESTING RETRIEVAL for query: '{query}' with filters={filters} ===")
query_vec = embeddings.get_embedding(query)
vec_res = repo.query_similarity(query_vec, limit=15, filters=filters)
print(f"vector_res count: {len(vec_res)}")
for chunk, score in vec_res[:3]:
    print(f"  Vec hit: {chunk.metadata.filename} | {chunk.metadata.heading} | score={score}")

kw_res = repo.keyword_search(query, limit=15, filters=filters)
print(f"\nkeyword_res count: {len(kw_res)}")
for chunk, score in kw_res[:3]:
    print(f"  KW hit: {chunk.metadata.filename} | {chunk.metadata.heading} | score={score}")

results = svc.retrieve(query=query, limit=5, filters=filters, hybrid_alpha=0.5)
print(f"\nsvc.retrieve results count: {len(results)}")
for r in results:
    print(f"  Result: {r.citation.filename} | {r.citation.heading} | score={r.score} | label={r.relevance_label}")
    print(f"    Text preview: {r.text[:100]}...")
