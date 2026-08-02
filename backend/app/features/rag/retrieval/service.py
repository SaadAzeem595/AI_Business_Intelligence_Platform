from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
import logging

from app.features.rag.schemas import Chunk, RetrievalResult, Citation
from app.features.rag.embeddings.providers import BaseEmbeddingProvider
from app.features.rag.vector_store.repository import BaseVectorRepository

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
            
        return formatted_results
