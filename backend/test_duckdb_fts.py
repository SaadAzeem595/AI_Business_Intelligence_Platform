import duckdb

conn = duckdb.connect("rag_vector.db")
print("Connected to rag_vector.db")

# Check if fts is available
try:
    conn.execute("INSTALL fts")
    conn.execute("LOAD fts")
    print("FTS extension installed and loaded successfully!")
except Exception as e:
    print("FTS install/load:", e)

# Test creating FTS index on rag_chunks table
try:
    # Drops existing index if any
    try:
        conn.execute("PRAGMA drop_fts_index('rag_chunks')")
        print("Dropped old FTS index")
    except Exception as e:
        print("Drop FTS index notice:", e)

    # In DuckDB FTS: PRAGMA create_fts_index(table_name, id_col, col1, col2, ...)
    conn.execute("PRAGMA create_fts_index('rag_chunks', 'id', 'text', 'heading', 'filename', 'columns', overwrite=1)")
    print("Created FTS index on rag_chunks ('id', 'text', 'heading', 'filename', 'columns')!")

    # Test FTS query using match_bm25
    query = "total_order_value"
    sql = """
        SELECT id, doc_id, filename, heading, score
        FROM (
            SELECT *, fts_main_rag_chunks.match_bm25(id, ?) AS score
            FROM rag_chunks
        )
        WHERE score IS NOT NULL
        ORDER BY score DESC
        LIMIT 5
    """
    res = conn.execute(sql, (query,)).fetchall()
    print(f"\nFTS BM25 search for '{query}': {len(res)} hits:")
    for r in res:
        print(f"  Hit: id={r[0]}, file={r[2]}, heading={r[3]}, score={r[4]}")

except Exception as e:
    import traceback
    traceback.print_exc()
