import sys
import duckdb
from app.features.rag.vector_store.repository import DuckDBVectorRepository
from app.features.rag.embeddings.providers import MockEmbeddingProvider

print("1. Initializing DuckDBVectorRepository...", flush=True)
repo = DuckDBVectorRepository(db_path="rag_vector.db")
print("2. Initializing MockEmbeddingProvider...", flush=True)
embeddings = MockEmbeddingProvider()

query = "What does total_order_value mean according to the Olist business dictionary?"
filters = {"workspace": "proj-2d1a2d1d"}

print("3. Generating query embedding...", flush=True)
query_vec = embeddings.get_embedding(query)
print(f"4. Query vector length: {len(query_vec)}", flush=True)

print("5. Calling repo.query_similarity...", flush=True)
vec_res = repo.query_similarity(query_vec, limit=5, filters=filters)
print(f"6. Vector results count: {len(vec_res)}", flush=True)
for chunk, score in vec_res:
    print(f"   Hit: {chunk.metadata.filename} | score={score}")

print("7. Calling repo.keyword_search...", flush=True)
kw_res = repo.keyword_search(query, limit=5, filters=filters)
print(f"8. Keyword results count: {len(kw_res)}", flush=True)
for chunk, score in kw_res:
    print(f"   Hit: {chunk.metadata.filename} | score={score}")

print("9. Done!", flush=True)
