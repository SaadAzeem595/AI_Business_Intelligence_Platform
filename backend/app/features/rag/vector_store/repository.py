import os
import json
import logging

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


class DuckDBVectorRepository(BaseVectorRepository):
    def __init__(self, db_path: str = "rag_vector.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        try:
            return duckdb.connect(self.db_path)
        except (duckdb.IOException, duckdb.ConnectionException, Exception) as e:
            if self.db_path != ":memory:":
                logger.warning(f"DuckDB lock contention on '{self.db_path}'. Falling back to ':memory:': {e}")
                self.db_path = ":memory:"
                conn = duckdb.connect(self.db_path)
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
                        document_type VARCHAR
                    )
                """)
                return conn
            raise e

    def _init_db(self):
        # Initialize DuckDB table
        conn = self._get_connection()
        try:
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
                    document_type VARCHAR
                )
            """)
        finally:
            conn.close()

    def insert_chunks(self, chunks: List[Chunk]) -> None:
        conn = self._get_connection()
        try:
            for chunk in chunks:
                emb_str = json.dumps(chunk.embedding) if chunk.embedding else None
                tags_str = ",".join(chunk.metadata.tags)
                conn.execute("""
                    INSERT OR REPLACE INTO rag_chunks (
                        id, doc_id, text, embedding, filename, author, upload_date, workspace, page, heading, tags, document_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    chunk.metadata.document_type
                ))
        finally:
            conn.close()

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
        # Columns mapping:
        # 0: id, 1: doc_id, 2: text, 3: embedding, 4: filename, 5: author, 6: upload_date, 7: workspace, 8: page, 9: heading, 10: tags, 11: document_type
        tags = row[10].split(",") if row[10] else []
        meta = DocumentMetadata(
            filename=row[4],
            author=row[5],
            upload_date=row[6],
            workspace=row[7],
            page=row[8],
            heading=row[9],
            tags=tags,
            document_type=row[11]
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
        conn = self._get_connection()
        try:
            # Query all chunks matching metadata filters first
            res = conn.execute(f"SELECT * FROM rag_chunks {filter_clause}", args).fetchall()
            if not res:
                return []
                
            chunks = [self._row_to_chunk(row) for row in res if row[3] is not None]
            if not chunks:
                return []
                
            # Perform Cosine Similarity calculation in Python
            embeddings = np.array([c.embedding for c in chunks])
            query_arr = np.array([query_vector])
            similarities = cosine_similarity(query_arr, embeddings)[0]
            
            results = []
            for idx, score in enumerate(similarities):
                results.append((chunks[idx], float(score)))
                
            results = sorted(results, key=lambda x: x[1], reverse=True)
            return results[:limit]
        finally:
            conn.close()

    def keyword_search(
        self, 
        query_text: str, 
        limit: int = 5, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[Chunk, float]]:
        filter_clause, args = self._build_filter_clause(filters)
        conn = self._get_connection()
        try:
            res = conn.execute(f"SELECT * FROM rag_chunks {filter_clause}", args).fetchall()
            if not res or not query_text.strip():
                return []
                
            chunks = [self._row_to_chunk(row) for row in res]
            
            # Compute TF-IDF
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
        finally:
            conn.close()

    def delete_by_document(self, doc_id: str) -> None:
        conn = self._get_connection()
        try:
            conn.execute("DELETE FROM rag_chunks WHERE doc_id = ?", (doc_id,))
        finally:
            conn.close()

    def list_documents(self, workspace: str = "default") -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            res = conn.execute("""
                SELECT DISTINCT doc_id, filename, document_type, upload_date 
                FROM rag_chunks 
                WHERE workspace = ?
            """, (workspace,)).fetchall()
            return [
                {
                    "doc_id": row[0],
                    "filename": row[1],
                    "document_type": row[2],
                    "upload_date": row[3]
                }
                for row in res
            ]
        finally:
            conn.close()
