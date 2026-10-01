import duckdb
import json

conn = duckdb.connect("rag_vector.db")
print("=== SCHEMAS ===")
for row in conn.execute("DESCRIBE rag_chunks").fetchall():
    print(row)

print("\n=== DOCUMENTS IN RAG_CHUNKS ===")
docs = conn.execute("""
    SELECT doc_id, filename, workspace, project_id, document_type, count(*), min(chunk_index), max(chunk_index)
    FROM rag_chunks
    GROUP BY doc_id, filename, workspace, project_id, document_type
""").fetchall()
for d in docs:
    print(d)

print("\n=== SAMPLE CHUNKS ===")
chunks = conn.execute("""
    SELECT id, doc_id, filename, workspace, project_id, heading, chunk_type, columns, text, embedding IS NOT NULL, length(embedding)
    FROM rag_chunks
    WHERE filename LIKE '%olist%' OR filename LIKE '%csv%' OR filename LIKE '%md%'
    LIMIT 5
""").fetchall()
for c in chunks:
    text_preview = (c[8] or "")[:150].replace("\n", " ")
    print(f"ID: {c[0]} | File: {c[2]} | WS: {c[3]} | Proj: {c[4]} | Heading: {c[5]} | Type: {c[6]} | Cols: {c[7]} | HasEmb: {c[9]} (len {c[10]})")
    print(f"  Text: {text_preview}")
