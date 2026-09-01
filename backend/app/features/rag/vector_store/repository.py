import os
import json
import logging
import threading

logger = logging.getLogger(__name__)
import numpy as np
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
import duckdb
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.features.rag.schemas import Chunk, DocumentMetadata

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
        """Lists metadata of all ingested documents in a workspace."""
        pass

    @abstractmethod
    def get_document_chunks_raw(self, doc_id: str) -> List[Dict[str, Any]]:
        """Retrieves raw chunk fields for document re-indexing."""
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

        embeddings = np.array([c.embedding for c in filtered_chunks])
        query_arr = np.array([query_vector])
        
        # Calculate cosine similarity
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
            
        # Implement keyword search using standard TF-IDF similarity
        texts = [c.text for c in filtered_chunks]
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
            # Fallback to simple substring match score if TF-IDF fails (e.g. vocabulary size too small)
            results = []
            for c in filtered_chunks:
                matches = sum(1 for w in query_text.lower().split() if w in c.text.lower())
                if matches > 0:
                    results.append((c, float(matches / len(query_text.split()))))
            results = sorted(results, key=lambda x: x[1], reverse=True)
            return results[:limit]

    def delete_by_document(self, doc_id: str) -> None:
        self.chunks = [c for c in self.chunks if c.doc_id != doc_id]

    def list_documents(self, workspace: str = "default") -> List[Dict[str, Any]]:
        docs = {}
        for c in self.chunks:
            if c.metadata.workspace == workspace:
                docs[c.doc_id] = {
                    "doc_id": c.doc_id,
                    "filename": c.metadata.filename,
                    "document_type": c.metadata.document_type,
                    "upload_date": c.metadata.upload_date
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
                table_name VARCHAR
            )
        """)
        for col_def in [
            "file_size INTEGER DEFAULT 0",
            "chunk_type VARCHAR DEFAULT 'text'",
            "row_start INTEGER",
            "row_end INTEGER",
            "columns VARCHAR",
            "table_name VARCHAR"
        ]:
            try:
                conn.execute(f"ALTER TABLE rag_chunks ADD COLUMN {col_def}")
            except Exception:
                pass

    def _get_connection(self):
        with self._lock:
            if self._conn is not None:
                return self._conn

            if self.db_path == ":memory:":
                self._conn = duckdb.connect(":memory:")
                self._create_chunks_table(self._conn)
                return self._conn

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

    def _close_conn(self, conn=None):
        # Do not close persistent connection on every operation to avoid WAL checkpoint lock contention
        pass

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
                    tags_str = ",".join(chunk.metadata.tags)
                    cols_str = json.dumps(chunk.metadata.columns) if getattr(chunk.metadata, "columns", None) else None
                    conn.execute("""
                        INSERT OR REPLACE INTO rag_chunks (
                            id, doc_id, text, embedding, filename, author, upload_date, workspace, page, heading, tags, document_type, file_size, chunk_type, row_start, row_end, columns, table_name
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        chunk.id,
                        chunk.doc_id,
                        chunk.text,
                        emb_str,
                        chunk.metadata.filename,
                        chunk.metadata.author,
                        chunk.metadata.upload_date,
                        chunk.metadata.workspace,
                        chunk.metadata.page,
                        chunk.metadata.heading,
                        tags_str,
                        chunk.metadata.document_type,
                        getattr(chunk.metadata, "file_size", 0) or 0,
                        getattr(chunk.metadata, "chunk_type", "text") or "text",
                        getattr(chunk.metadata, "row_start", None),
                        getattr(chunk.metadata, "row_end", None),
                        cols_str,
                        getattr(chunk.metadata, "table_name", None)
                    ))
                conn.execute("COMMIT")
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
            if k == "tags" and isinstance(v, list):
                # Search comma-separated tags
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
            table_name=t_name
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
                
            embeddings = np.array([c.embedding for c in chunks])
            query_arr = np.array([query_vector])
            similarities = cosine_similarity(query_arr, embeddings)[0]
            
            results = []
            for idx, score in enumerate(similarities):
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
            res = conn.execute(f"SELECT * FROM rag_chunks {filter_clause}", args).fetchall()
            if not res or not query_text.strip():
                return []
                
            chunks = [self._row_to_chunk(row) for row in res]
            
            texts = [c.text for c in chunks]
            try:
                vectorizer = TfidfVectorizer(stop_words='english')
                tfidf_matrix = vectorizer.fit_transform(texts)
                query_vec = vectorizer.transform([query_text])
                similarities = cosine_similarity(query_vec, tfidf_matrix)[0]
                
                results = []
                for idx, score in enumerate(similarities):
                    if score > 0:
                        results.append((chunks[idx], float(score)))
                results = sorted(results, key=lambda x: x[1], reverse=True)
                return results[:limit]
            except Exception:
                results = []
                for c in chunks:
                    matches = sum(1 for w in query_text.lower().split() if w in c.text.lower())
                    if matches > 0:
                        results.append((c, float(matches / len(query_text.split()))))
                results = sorted(results, key=lambda x: x[1], reverse=True)
                return results[:limit]

        return self._execute_with_retry(_do_search)

    def delete_by_document(self, doc_id: str) -> None:
        def _do_delete(conn):
            conn.execute("DELETE FROM rag_chunks WHERE doc_id = ?", (doc_id,))

        self._execute_with_retry(_do_delete)

    def list_documents(self, workspace: str = "default") -> List[Dict[str, Any]]:
        def _do_list(conn):
            res = conn.execute("""
                SELECT 
                    doc_id, 
                    filename, 
                    document_type, 
                    upload_date, 
                    workspace, 
                    COUNT(id) as chunks_count, 
                    MAX(page) as pages_count, 
                    MAX(file_size) as file_size, 
                    MAX(author) as author
                FROM rag_chunks 
                WHERE workspace = ?
                GROUP BY doc_id, filename, document_type, upload_date, workspace
                ORDER BY upload_date DESC, doc_id DESC
            """, (workspace,)).fetchall()
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


