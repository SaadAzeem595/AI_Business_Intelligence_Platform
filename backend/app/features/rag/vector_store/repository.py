import os
import json
import logging
import threading
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import duckdb
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.features.rag.schemas import Chunk, DocumentMetadata

logger = logging.getLogger(__name__)


class BaseVectorRepository(ABC):
    @abstractmethod
    def insert_chunks(self, chunks: List[Chunk]) -> None:
        """Inserts a batch of chunks into the store."""
        pass

    @abstractmethod
    def query_similarity(
        self, 
        query_vector: List[float], 
        limit: int = 5, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[Chunk, float]]:
        """Queries the vector store for similar vectors and returns Tuple[Chunk, score]."""
        pass

    @abstractmethod
    def keyword_search(
        self, 
        query_text: str, 
        limit: int = 5, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[Chunk, float]]:
        """Performs keyword search on chunk texts."""
        pass

    @abstractmethod
    def delete_by_document(self, doc_id: str) -> None:
        """Deletes all chunks belonging to a document."""
        pass

    @abstractmethod
    def list_documents(self, workspace: str = "default") -> List[Dict[str, Any]]:
        """Lists metadata of all ingested documents in a workspace/project."""
        pass

    @abstractmethod
    def get_document_chunks_raw(self, doc_id: str) -> List[Dict[str, Any]]:
        """Retrieves raw chunk fields for document re-indexing."""
        pass

    @abstractmethod
    def get_document_diagnostics(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves retrieval and index health diagnostics for a specific document."""
        pass

    @abstractmethod
    def get_project_diagnostics(self, project_id: str) -> Dict[str, Any]:
        """Retrieves scope counts (documents and chunks) for a project."""
        pass


class InMemoryVectorRepository(BaseVectorRepository):
    def __init__(self):
        self.chunks: List[Chunk] = []

    def insert_chunks(self, chunks: List[Chunk]) -> None:
        self.chunks.extend(chunks)

    def _matches_filters(self, metadata: DocumentMetadata, filters: Optional[Dict[str, Any]]) -> bool:
        if not filters:
            return True
        for k, v in filters.items():
            if k in ("workspace", "project_id"):
                chunk_ws = getattr(metadata, "workspace", None)
                chunk_pid = getattr(metadata, "project_id", None)
                if chunk_ws != v and chunk_pid != v:
                    return False
            else:
                val = getattr(metadata, k, None)
                if val != v:
                    return False
        return True

    def query_similarity(
        self, 
        query_vector: List[float], 
        limit: int = 5, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[Chunk, float]]:
        filtered_chunks = [c for c in self.chunks if self._matches_filters(c.metadata, filters) and c.embedding is not None]
        if not filtered_chunks:
            return []

        stored_dim = len(filtered_chunks[0].embedding)
        query_dim = len(query_vector)
        if stored_dim != query_dim:
            raise ValueError(f"Embedding dimension mismatch: query dimension ({query_dim}) != stored ({stored_dim})")

        embeddings = np.array([c.embedding for c in filtered_chunks])
        query_arr = np.array([query_vector])
        similarities = cosine_similarity(query_arr, embeddings)[0]
        
        results = []
        for idx, score in enumerate(similarities):
            results.append((filtered_chunks[idx], float(score)))
            
        results = sorted(results, key=lambda x: x[1], reverse=True)
        return results[:limit]

    def keyword_search(
        self, 
        query_text: str, 
        limit: int = 5, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[Chunk, float]]:
        filtered_chunks = [c for c in self.chunks if self._matches_filters(c.metadata, filters)]
        if not filtered_chunks or not query_text.strip():
            return []
            
        texts = [f"{c.metadata.filename} {c.metadata.heading or ''} {getattr(c.metadata, 'heading_path', '') or ''} {' '.join(c.metadata.columns or [])} {c.text}" for c in filtered_chunks]
        try:
            vectorizer = TfidfVectorizer(stop_words='english')
            tfidf_matrix = vectorizer.fit_transform(texts)
            query_vec = vectorizer.transform([query_text])
            similarities = cosine_similarity(query_vec, tfidf_matrix)[0]
            
            results = []
            for idx, score in enumerate(similarities):
                if score > 0:
                    results.append((filtered_chunks[idx], float(score)))
            results = sorted(results, key=lambda x: x[1], reverse=True)
            return results[:limit]
        except Exception:
            results = []
            q_words = [w.lower().strip("?,.!\"'") for w in query_text.split() if len(w.strip("?,.!\"'")) > 1]
            for c in filtered_chunks:
                searchable = f"{c.metadata.filename} {c.metadata.heading or ''} {' '.join(c.metadata.columns or [])} {c.text}".lower()
                matches = sum(1 for w in q_words if w in searchable)
                if matches > 0:
                    results.append((c, float(matches / max(1, len(q_words)))))
            results = sorted(results, key=lambda x: x[1], reverse=True)
            return results[:limit]

    def delete_by_document(self, doc_id: str) -> None:
        self.chunks = [c for c in self.chunks if c.doc_id != doc_id]

    def list_documents(self, workspace: str = "default") -> List[Dict[str, Any]]:
        docs = {}
        for c in self.chunks:
            if c.metadata.workspace == workspace or getattr(c.metadata, "project_id", None) == workspace:
                docs[c.doc_id] = {
                    "doc_id": c.doc_id,
                    "filename": c.metadata.filename,
                    "document_type": c.metadata.document_type,
                    "upload_date": c.metadata.upload_date,
                    "workspace": workspace,
                    "chunks_count": sum(1 for x in self.chunks if x.doc_id == c.doc_id),
                    "pages_count": max((x.metadata.page or 1 for x in self.chunks if x.doc_id == c.doc_id), default=1),
                    "file_size": getattr(c.metadata, "file_size", 0) or 0,
                    "author": c.metadata.author or "Unknown",
                    "status": "Indexed"
                }
        return list(docs.values())

    def get_document_chunks_raw(self, doc_id: str) -> List[Dict[str, Any]]:
        res = [c for c in self.chunks if c.doc_id == doc_id]
        return [
            {
                "text": c.text,
                "filename": c.metadata.filename,
                "author": c.metadata.author,
                "document_type": c.metadata.document_type,
                "tags": ",".join(c.metadata.tags) if c.metadata.tags else "",
                "file_size": getattr(c.metadata, "file_size", 0) or 0
            }
            for c in res
        ]

    def get_document_diagnostics(self, doc_id: str) -> Optional[Dict[str, Any]]:
        doc_chunks = [c for c in self.chunks if c.doc_id == doc_id]
        if not doc_chunks:
            return None
        emb_count = sum(1 for c in doc_chunks if c.embedding is not None)
        emb_dim = len(doc_chunks[0].embedding) if emb_count > 0 and doc_chunks[0].embedding else 1536
        return {
            "document_id": doc_id,
            "filename": doc_chunks[0].metadata.filename,
            "status": "Indexed" if len(doc_chunks) > 0 else "Failed",
            "chunk_count": len(doc_chunks),
            "embedded_chunk_count": emb_count,
            "bm25_indexed": True,
            "vector_indexed": emb_count > 0,
            "embedding_model": "openai/text-embedding-3-small",
            "embedding_dimension": emb_dim,
            "project_id": getattr(doc_chunks[0].metadata, "project_id", doc_chunks[0].metadata.workspace) or "default",
            "workspace_id": doc_chunks[0].metadata.workspace or "default",
            "searchable": len(doc_chunks) > 0 and emb_count > 0
        }

    def get_project_diagnostics(self, project_id: str) -> Dict[str, Any]:
        p_chunks = [c for c in self.chunks if self._matches_filters(c.metadata, {"workspace": project_id})]
        doc_ids = set(c.doc_id for c in p_chunks)
        return {
            "documents_in_scope": len(doc_ids),
            "chunks_in_scope": len(p_chunks)
        }


class DuckDBVectorRepository(BaseVectorRepository):
    def __init__(self, db_path: str = "rag_vector.db"):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._conn = None
        self._init_db()

    def _cleanup_stale_locks(self):
        """Attempts safe cleanup of orphan WAL files if no active DuckDB process holds them."""
        if self.db_path == ":memory:":
            return
        wal_path = f"{self.db_path}.wal"
        if os.path.exists(wal_path):
            try:
                if os.path.getsize(wal_path) == 0:
                    os.remove(wal_path)
                    logger.info(f"Cleaned up empty orphan WAL file: {wal_path}")
            except Exception as e:
                logger.debug(f"WAL file {wal_path} is currently locked or in use: {e}")

    def _configure_pragmas(self, conn):
        """Configures performance & WAL parameters for DuckDB."""
        try:
            conn.execute("PRAGMA threads=4")
            conn.execute("PRAGMA checkpoint_threshold='64MB'")
        except Exception as e:
            logger.debug(f"Failed to set DuckDB PRAGMAs: {e}")

    def _ensure_fts_index(self, conn):
        """Ensures DuckDB Full Text Search (FTS) extension is loaded and BM25 index is active."""
        try:
            conn.execute("INSTALL fts")
            conn.execute("LOAD fts")
        except Exception:
            pass

        try:
            # Check row count first; FTS index requires at least schema definition
            conn.execute("""
                PRAGMA create_fts_index(
                    'rag_chunks', 'id', 'text', 'heading', 'filename', 'columns',
                    overwrite=1
                )
            """)
            logger.debug("DuckDB FTS BM25 index refreshed on rag_chunks.")
        except Exception as e:
            logger.debug(f"DuckDB FTS index update notice: {e}")

    def _create_chunks_table(self, conn):
        self._configure_pragmas(conn)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rag_chunks (
                id VARCHAR PRIMARY KEY,
                doc_id VARCHAR,
                text VARCHAR,
                embedding VARCHAR,  -- Store embedding as JSON string
                filename VARCHAR,
                author VARCHAR,
                upload_date VARCHAR,
                workspace VARCHAR,
                page INTEGER,
                heading VARCHAR,
                tags VARCHAR,       -- Comma-separated list
                document_type VARCHAR,
                file_size INTEGER DEFAULT 0,
                chunk_type VARCHAR DEFAULT 'text',
                row_start INTEGER,
                row_end INTEGER,
                columns VARCHAR,
                table_name VARCHAR,
                file_type VARCHAR,
                mime_type VARCHAR,
                project_id VARCHAR,
                chunk_index INTEGER,
                heading_path VARCHAR,
                content_type VARCHAR
            )
        """)
        for col_def in [
            "file_size INTEGER DEFAULT 0",
            "chunk_type VARCHAR DEFAULT 'text'",
            "row_start INTEGER",
            "row_end INTEGER",
            "columns VARCHAR",
            "table_name VARCHAR",
            "file_type VARCHAR",
            "mime_type VARCHAR",
            "project_id VARCHAR",
            "chunk_index INTEGER",
            "heading_path VARCHAR",
            "content_type VARCHAR"
        ]:
            try:
                conn.execute(f"ALTER TABLE rag_chunks ADD COLUMN {col_def}")
            except Exception:
                pass

        self._ensure_fts_index(conn)

    def _get_connection(self):
        with self._lock:
            if self._conn is not None:
                return self._conn

            if self.db_path == ":memory:":
                self._conn = duckdb.connect(":memory:")
                self._create_chunks_table(self._conn)
                return self._conn

            # Ensure parent directory exists for file-backed storage
            db_dir = os.path.dirname(os.path.abspath(self.db_path))
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)

            self._cleanup_stale_locks()
            try:
                self._conn = duckdb.connect(self.db_path)
                self._create_chunks_table(self._conn)
                return self._conn
            except (duckdb.IOException, duckdb.ConnectionException, Exception) as e:
                logger.warning(f"DuckDB lock contention or error on '{self.db_path}'. Falling back to ':memory:': {e}")
                self.db_path = ":memory:"
                self._conn = duckdb.connect(self.db_path)
                self._create_chunks_table(self._conn)
                return self._conn

    def _recover_connection(self, error_msg: str):
        """Recovers invalidated DB connection or falls back to :memory:."""
        with self._lock:
            logger.warning(f"DuckDB connection invalidated or fatal error detected: {error_msg}. Initiating recovery...")
            if self._conn:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None

            if self.db_path != ":memory:":
                try:
                    self._cleanup_stale_locks()
                    self._conn = duckdb.connect(self.db_path)
                    self._create_chunks_table(self._conn)
                    logger.info("Successfully re-established DuckDB connection handle.")
                    return self._conn
                except Exception as rec_err:
                    logger.warning(f"Failed to reconnect to '{self.db_path}': {rec_err}. Falling back to ':memory:'.")
                    self.db_path = ":memory:"
            
            self._conn = duckdb.connect(":memory:")
            self._create_chunks_table(self._conn)
            return self._conn

    def _execute_with_retry(self, operation_fn):
        """Executes a database operation with automatic invalidation recovery."""
        with self._lock:
            conn = self._get_connection()
            try:
                return operation_fn(conn)
            except Exception as e:
                err_str = str(e).lower()
                is_invalidated = isinstance(e, (duckdb.ConnectionException, duckdb.IOException, duckdb.FatalException, Exception)) and any(k in err_str for k in [
                    "invalidated", "fatal error", "being used by another process", "checkpoint", "restarted prior to being used", "connection already closed", "connection error", "closed"
                ])
                if is_invalidated or isinstance(e, (duckdb.ConnectionException, duckdb.IOException, duckdb.FatalException)):
                    new_conn = self._recover_connection(str(e))
                    return operation_fn(new_conn)
                raise

    def _init_db(self):
        with self._lock:
            self._get_connection()

    def close(self):
        with self._lock:
            if self._conn and self.db_path != ":memory:":
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None

    def insert_chunks(self, chunks: List[Chunk]) -> None:
        def _do_insert(conn):
            conn.execute("BEGIN TRANSACTION")
            try:
                for chunk in chunks:
                    emb_str = json.dumps(chunk.embedding) if chunk.embedding else None
                    tags_str = ",".join(chunk.metadata.tags) if chunk.metadata.tags else ""
                    cols_str = json.dumps(chunk.metadata.columns) if getattr(chunk.metadata, "columns", None) else None
                    target_pid = getattr(chunk.metadata, "project_id", None) or chunk.metadata.workspace or "default"
                    conn.execute("""
                        INSERT OR REPLACE INTO rag_chunks (
                            id, doc_id, text, embedding, filename, author, upload_date, workspace, page, heading, tags, document_type, file_size, chunk_type, row_start, row_end, columns, table_name, file_type, mime_type, project_id, chunk_index, heading_path, content_type
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        chunk.id,
                        chunk.doc_id,
                        chunk.text,
                        emb_str,
                        chunk.metadata.filename,
                        chunk.metadata.author or "Unknown",
                        chunk.metadata.upload_date,
                        chunk.metadata.workspace or target_pid,
                        chunk.metadata.page,
                        chunk.metadata.heading,
                        tags_str,
                        chunk.metadata.document_type,
                        getattr(chunk.metadata, "file_size", 0) or 0,
                        getattr(chunk.metadata, "chunk_type", "text") or "text",
                        getattr(chunk.metadata, "row_start", None),
                        getattr(chunk.metadata, "row_end", None),
                        cols_str,
                        getattr(chunk.metadata, "table_name", None),
                        getattr(chunk.metadata, "file_type", None),
                        getattr(chunk.metadata, "mime_type", None),
                        target_pid,
                        getattr(chunk.metadata, "chunk_index", None),
                        getattr(chunk.metadata, "heading_path", None),
                        getattr(chunk.metadata, "content_type", None)
                    ))
                conn.execute("COMMIT")
                # Immediately update FTS BM25 index on new chunks
                self._ensure_fts_index(conn)
            except Exception:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
                raise

        self._execute_with_retry(_do_insert)

    def _build_filter_clause(self, filters: Optional[Dict[str, Any]]) -> Tuple[str, List[Any]]:
        if not filters:
            return "", []
        clauses = []
        args = []
        for k, v in filters.items():
            if k in ("workspace", "project_id"):
                # Unified project scoping: check both columns to ensure project isolation and prevent scoping mismatches
                clauses.append("(workspace = ? OR project_id = ?)")
                args.extend([v, v])
            elif k == "tags" and isinstance(v, list):
                for tag in v:
                    clauses.append("tags LIKE ?")
                    args.append(f"%{tag}%")
            else:
                clauses.append(f"{k} = ?")
                args.append(v)
        return "WHERE " + " AND ".join(clauses), args

    def _row_to_chunk(self, row: tuple) -> Chunk:
        tags = row[10].split(",") if row[10] else []
        file_sz = row[12] if len(row) > 12 and row[12] is not None else 0
        chunk_tp = row[13] if len(row) > 13 and row[13] is not None else "text"
        r_start = row[14] if len(row) > 14 else None
        r_end = row[15] if len(row) > 15 else None
        cols_val = row[16] if len(row) > 16 and row[16] else None
        cols_list = []
        if cols_val:
            try:
                cols_list = json.loads(cols_val)
            except Exception:
                cols_list = [c.strip() for c in cols_val.split(",") if c.strip()]
        t_name = row[17] if len(row) > 17 else None
        f_type = row[18] if len(row) > 18 else None
        m_type = row[19] if len(row) > 19 else None
        p_id = row[20] if len(row) > 20 else None
        c_idx = row[21] if len(row) > 21 else None
        h_path = row[22] if len(row) > 22 else None
        c_type = row[23] if len(row) > 23 else None

        meta = DocumentMetadata(
            filename=row[4],
            author=row[5],
            upload_date=row[6],
            workspace=row[7],
            page=row[8],
            heading=row[9],
            tags=tags,
            document_type=row[11],
            file_size=file_sz,
            chunk_type=chunk_tp,
            row_start=r_start,
            row_end=r_end,
            columns=cols_list,
            table_name=t_name,
            file_type=f_type,
            mime_type=m_type,
            project_id=p_id or row[7],
            chunk_index=c_idx,
            heading_path=h_path,
            content_type=c_type
        )
        emb = json.loads(row[3]) if row[3] else None
        return Chunk(
            id=row[0],
            doc_id=row[1],
            text=row[2],
            embedding=emb,
            metadata=meta
        )

    def query_similarity(
        self, 
        query_vector: List[float], 
        limit: int = 5, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[Chunk, float]]:
        filter_clause, args = self._build_filter_clause(filters)

        def _do_query(conn):
            res = conn.execute(f"SELECT * FROM rag_chunks {filter_clause}", args).fetchall()
            if not res:
                return []
                
            chunks = [self._row_to_chunk(row) for row in res if row[3] is not None]
            if not chunks:
                return []

            # Compare query dimension vs stored chunk embedding dimension
            stored_dim = len(chunks[0].embedding)
            query_dim = len(query_vector)
            if stored_dim != query_dim:
                logger.error(
                    f"RAG_EMBEDDING_DIM_MISMATCH: Query dimension ({query_dim}) does not match "
                    f"stored chunk dimension ({stored_dim}) for '{chunks[0].metadata.filename}'."
                )
                raise ValueError(
                    f"Configuration error: Query embedding dimension ({query_dim}) does not match "
                    f"stored chunk dimension ({stored_dim}). Re-indexing required."
                )
                
            embeddings = np.array([c.embedding for c in chunks])
            query_arr = np.array([query_vector])
            similarities = cosine_similarity(query_arr, embeddings)[0]
            
            results = []
            for idx, score in enumerate(similarities):
                # Filter out candidates below dense similarity threshold
                if float(score) >= 0.20:
                    results.append((chunks[idx], float(score)))
                
            results = sorted(results, key=lambda x: x[1], reverse=True)
            return results[:limit]

        return self._execute_with_retry(_do_query)

    def keyword_search(
        self, 
        query_text: str, 
        limit: int = 5, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[Chunk, float]]:
        filter_clause, args = self._build_filter_clause(filters)

        def _do_search(conn):
            clean_q = re.sub(r"[^\w\s-]", " ", query_text).strip()
            terms = [t.strip() for t in clean_q.split() if len(t.strip()) > 1]
            fts_query = " ".join(terms) if terms else clean_q

            results = []
            if fts_query:
                try:
                    # Execute DuckDB FTS BM25 ranking
                    sql = f"""
                        SELECT *, fts_main_rag_chunks.match_bm25(id, ?) AS bm25_score
                        FROM rag_chunks
                        {filter_clause}
                        WHERE bm25_score IS NOT NULL
                        ORDER BY bm25_score DESC
                        LIMIT ?
                    """
                    query_args = [fts_query] + args + [limit * 3]
                    rows = conn.execute(sql, query_args).fetchall()
                    for r in rows:
                        chunk = self._row_to_chunk(r[:-1])
                        score = float(r[-1])
                        results.append((chunk, score))
                except Exception as fts_err:
                    logger.debug(f"DuckDB FTS match_bm25 query failed ({fts_err}), using term matching.")

            if not results:
                # Fallback to exact/fuzzy token matching over the project chunk corpus
                res = conn.execute(f"SELECT * FROM rag_chunks {filter_clause}", args).fetchall()
                if not res or not query_text.strip():
                    return []
                chunks = [self._row_to_chunk(row) for row in res]
                q_words = [w.lower().strip("?,.!\"'") for w in query_text.split() if len(w.strip("?,.!\"'")) > 1]
                scored = []
                for c in chunks:
                    cols_str = " ".join(c.metadata.columns) if c.metadata.columns else ""
                    searchable = f"{c.metadata.filename} {c.metadata.heading or ''} {cols_str} {c.text}".lower()
                    matches = sum(1 for w in q_words if w in searchable)
                    if matches > 0:
                        scored.append((c, float(matches / max(1, len(q_words)))))
                scored = sorted(scored, key=lambda x: x[1], reverse=True)
                results = scored[:limit * 3]

            return results[:limit]

        return self._execute_with_retry(_do_search)

    def delete_by_document(self, doc_id: str) -> None:
        def _do_delete(conn):
            conn.execute("DELETE FROM rag_chunks WHERE doc_id = ?", (doc_id,))
            self._ensure_fts_index(conn)

        self._execute_with_retry(_do_delete)

    def list_documents(self, workspace: str = "default") -> List[Dict[str, Any]]:
        def _do_list(conn):
            res = conn.execute("""
                SELECT 
                    doc_id, 
                    filename, 
                    document_type, 
                    upload_date, 
                    COALESCE(project_id, workspace) as workspace, 
                    COUNT(id) as chunks_count, 
                    MAX(page) as pages_count, 
                    MAX(file_size) as file_size, 
                    MAX(author) as author
                FROM rag_chunks 
                WHERE workspace = ? OR project_id = ?
                GROUP BY doc_id, filename, document_type, upload_date, COALESCE(project_id, workspace)
                ORDER BY upload_date DESC, doc_id DESC
            """, (workspace, workspace)).fetchall()
            return [
                {
                    "doc_id": row[0],
                    "filename": row[1],
                    "document_type": row[2],
                    "upload_date": row[3],
                    "workspace": row[4],
                    "chunks_count": row[5],
                    "pages_count": row[6] or 1,
                    "file_size": row[7] or 0,
                    "author": row[8] or "Unknown",
                    "status": "Indexed"
                }
                for row in res
            ]

        return self._execute_with_retry(_do_list)

    def get_document_chunks_raw(self, doc_id: str) -> List[Dict[str, Any]]:
        def _do_get(conn):
            res = conn.execute(
                "SELECT text, filename, author, document_type, tags, file_size FROM rag_chunks WHERE doc_id = ?", 
                (doc_id,)
            ).fetchall()
            return [
                {
                    "text": row[0],
                    "filename": row[1],
                    "author": row[2],
                    "document_type": row[3],
                    "tags": row[4],
                    "file_size": row[5] or 0
                }
                for row in res
            ]

        return self._execute_with_retry(_do_get)

    def get_document_diagnostics(self, doc_id: str) -> Optional[Dict[str, Any]]:
        def _do_diag(conn):
            res = conn.execute("""
                SELECT 
                    doc_id, 
                    filename, 
                    document_type, 
                    COALESCE(project_id, workspace) as project_id, 
                    workspace, 
                    COUNT(id) as chunk_count, 
                    COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as embedded_chunk_count
                FROM rag_chunks 
                WHERE doc_id = ?
                GROUP BY doc_id, filename, document_type, project_id, workspace
            """, (doc_id,)).fetchone()
            if not res:
                return None
            sample_emb = conn.execute(
                "SELECT embedding FROM rag_chunks WHERE doc_id = ? AND embedding IS NOT NULL LIMIT 1", 
                (doc_id,)
            ).fetchone()
            emb_dim = 0
            if sample_emb and sample_emb[0]:
                try:
                    emb_dim = len(json.loads(sample_emb[0]))
                except Exception:
                    pass
            return {
                "document_id": res[0],
                "filename": res[1],
                "status": "Indexed" if res[5] > 0 else "Failed",
                "chunk_count": res[5],
                "embedded_chunk_count": res[6],
                "bm25_indexed": True,
                "vector_indexed": res[6] > 0,
                "embedding_model": "openai/text-embedding-3-small",
                "embedding_dimension": emb_dim or 1536,
                "project_id": res[3] or res[4],
                "workspace_id": res[4] or res[3],
                "searchable": res[5] > 0 and res[6] > 0
            }
        return self._execute_with_retry(_do_diag)

    def get_project_diagnostics(self, project_id: str) -> Dict[str, Any]:
        def _do_pdiag(conn):
            docs = conn.execute(
                "SELECT COUNT(DISTINCT doc_id), COUNT(id) FROM rag_chunks WHERE workspace = ? OR project_id = ?",
                (project_id, project_id)
            ).fetchone()
            return {
                "documents_in_scope": docs[0] if docs else 0,
                "chunks_in_scope": docs[1] if docs else 0,
            }
        return self._execute_with_retry(_do_pdiag)
