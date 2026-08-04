from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
import logging
import hashlib
import json
import time

from app.features.rag.schemas import Chunk, RetrievalResult, Citation
from app.features.rag.embeddings.providers import BaseEmbeddingProvider
from app.features.rag.vector_store.repository import BaseVectorRepository
from app.core.cache import cache_client, run_async_as_sync
from app.core.telemetry import RAG_RETRIEVAL_LATENCY

logger = logging.getLogger(__name__)

class BaseReranker(ABC):
    @abstractmethod
    def rerank(self, query: str, chunks: List[Chunk]) -> List[Tuple[Chunk, float]]:
        """Reranks the retrieved chunks against the query and returns Tuple[Chunk, score]."""
        pass


class MockReranker(BaseReranker):
    def rerank(self, query: str, chunks: List[Chunk]) -> List[Tuple[Chunk, float]]:
        """Computes Jaccard word-overlap coefficient as a semantic-proxy score."""
        logger.info("Executing MockReranker (Jaccard overlap coefficient)...")
        q_words = set(query.lower().split())
        results = []
        for chunk in chunks:
            c_words = set(chunk.text.lower().split())
            union_len = len(q_words.union(c_words))
            score = len(q_words.intersection(c_words)) / union_len if union_len > 0 else 0.0
            results.append((chunk, float(score)))
            
        return sorted(results, key=lambda x: x[1], reverse=True)


class CrossEncoderReranker(BaseReranker):
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self._model = None
        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name)
            logger.info(f"CrossEncoder '{self.model_name}' loaded successfully locally.")
        except ImportError:
            logger.warning("sentence-transformers not installed. CrossEncoderReranker falling back to MockReranker.")

    def rerank(self, query: str, chunks: List[Chunk]) -> List[Tuple[Chunk, float]]:
        if not self._model:
            return MockReranker().rerank(query, chunks)
            
        pairs = [[query, chunk.text] for chunk in chunks]
        scores = self._model.predict(pairs)
        
        results = []
        for idx, score in enumerate(scores):
            results.append((chunks[idx], float(score)))
            
        return sorted(results, key=lambda x: x[1], reverse=True)


class RetrievalService:
    """Coordinates vector, keyword, hybrid retrieval and reranking pipelines."""
    
    def __init__(
        self, 
        vector_repo: BaseVectorRepository, 
        embedding_provider: BaseEmbeddingProvider,
        reranker: Optional[BaseReranker] = None
    ):
        self.repo = vector_repo
        self.embeddings = embedding_provider
        self.reranker = reranker or MockReranker()

    def reciprocal_rank_fusion(
        self, 
        vector_results: List[Tuple[Chunk, float]], 
        keyword_results: List[Tuple[Chunk, float]], 
        k: int = 60
    ) -> List[Tuple[Chunk, float]]:
        """Combines rankings from vector and keyword results using Reciprocal Rank Fusion (RRF)."""
        rrf_scores = {}
        chunk_map = {}
        
        # Add vector ranks
        for rank, (chunk, _) in enumerate(vector_results):
            chunk_map[chunk.id] = chunk
            rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + (1.0 / (k + rank + 1))
            
        # Add keyword ranks
        for rank, (chunk, _) in enumerate(keyword_results):
            chunk_map[chunk.id] = chunk
            rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + (1.0 / (k + rank + 1))
            
        # Sort desc
        sorted_rrf = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        return [(chunk_map[chunk_id], float(score)) for chunk_id, score in sorted_rrf]

    def retrieve(
        self,
        query: str,
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        hybrid_alpha: float = 0.5,
        enable_rerank: bool = False
    ) -> List[RetrievalResult]:
        """Runs vector/keyword/hybrid retrieval and outputs ranked results with citations."""
        start_time = time.perf_counter()
        
        # Cache check
        filter_str = json.dumps(filters, sort_keys=True) if filters else ""
        cache_str = f"{query}:{limit}:{filter_str}:{hybrid_alpha}:{enable_rerank}"
        cache_hash = hashlib.md5(cache_str.encode("utf-8")).hexdigest()
        cache_key = f"rag_retrieve:{cache_hash}"
        
        try:
            cached_data = run_async_as_sync(cache_client.get(cache_key))
            if cached_data:
                results = []
                for item in cached_data:
                    cit = item.get("citation", {})
                    citation = Citation(
                        filename=cit.get("filename"),
                        document_type=cit.get("document_type"),
                        page=cit.get("page"),
                        heading=cit.get("heading"),
                        workspace=cit.get("workspace", "default")
                    )
                    results.append(
                        RetrievalResult(
                            chunk_id=item.get("chunk_id"),
                            doc_id=item.get("doc_id"),
                            text=item.get("text"),
                            score=item.get("score"),
                            citation=citation
                        )
                    )
                return results
        except Exception:
            pass

        logger.info(f"Retrieving for query: '{query}' (alpha={hybrid_alpha}, rerank={enable_rerank})")
        
        # 1. Fetch vector results if alpha > 0
        vector_res = []
        if hybrid_alpha > 0.0:
            query_vec = self.embeddings.get_embedding(query)
            # Fetch a larger candidate pool to allow RRF merge and rerank
            vector_res = self.repo.query_similarity(query_vec, limit=limit * 2, filters=filters)
            
        # 2. Fetch keyword results if alpha < 1
        keyword_res = []
        if hybrid_alpha < 1.0:
            keyword_res = self.repo.keyword_search(query, limit=limit * 2, filters=filters)
            
        # 3. Merge results
        if hybrid_alpha == 1.0:
            candidate_tuples = vector_res
        elif hybrid_alpha == 0.0:
            candidate_tuples = keyword_res
        else:
            candidate_tuples = self.reciprocal_rank_fusion(vector_res, keyword_res)
            
        # Extract candidate chunks
        chunks = [item[0] for item in candidate_tuples]
        
        # 4. Optional Reranking
        if enable_rerank and chunks:
            ranked_tuples = self.reranker.rerank(query, chunks)
        else:
            # Map score mappings from candidates
            ranked_tuples = candidate_tuples
            
        # Slice to limit
        top_tuples = ranked_tuples[:limit]
        
        # 5. Format into RetrievalResult schemas
        formatted_results = []
        for chunk, score in top_tuples:
            citation = Citation(
                filename=chunk.metadata.filename,
                document_type=chunk.metadata.document_type,
                page=chunk.metadata.page,
                heading=chunk.metadata.heading,
                workspace=chunk.metadata.workspace or "default"
            )
            formatted_results.append(
                RetrievalResult(
                    chunk_id=chunk.id,
                    doc_id=chunk.doc_id,
                    text=chunk.text,
                    score=score,
                    citation=citation
                )
            )
            
        # Observe latency
        duration = time.perf_counter() - start_time
        workspace_lbl = filters.get("workspace", "default") if filters else "default"
        RAG_RETRIEVAL_LATENCY.labels(workspace=workspace_lbl).observe(duration)
        
        # Save to cache
        try:
            cache_payload = []
            for item in formatted_results:
                cache_payload.append({
                    "chunk_id": item.chunk_id,
                    "doc_id": item.doc_id,
                    "text": item.text,
                    "score": item.score,
                    "citation": {
                        "filename": item.citation.filename,
                        "document_type": item.citation.document_type,
                        "page": item.citation.page,
                        "heading": item.citation.heading,
                        "workspace": item.citation.workspace
                    }
                })
            run_async_as_sync(cache_client.set(cache_key, cache_payload, ttl=300))
        except Exception:
            pass
            
        return formatted_results
