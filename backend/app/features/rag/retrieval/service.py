from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
import logging
import hashlib
import json
import time
import re

from app.features.rag.schemas import Chunk, RetrievalResult, Citation, QueryIntent
from app.features.rag.embeddings.providers import BaseEmbeddingProvider
from app.features.rag.vector_store.repository import BaseVectorRepository
from app.core.cache import cache_client, run_async_as_sync
from app.core.telemetry import RAG_RETRIEVAL_LATENCY

logger = logging.getLogger(__name__)

class BaseReranker(ABC):
    @abstractmethod
    def rerank(self, query: str, chunks: List[Chunk], intent: Optional[str] = None) -> List[Tuple[Chunk, float]]:
        """Reranks the retrieved chunks against the query and returns Tuple[Chunk, score]."""
        pass


class MockReranker(BaseReranker):
    MONTH_ALIASES = {
        "january": "jan", "february": "feb", "march": "mar", "april": "apr",
        "june": "jun", "july": "jul", "august": "aug", "september": "sep",
        "october": "oct", "november": "nov", "december": "dec"
    }
    STOP_WORDS = {"what", "was", "the", "in", "which", "had", "do", "show", "over", "time", "a", "an", "is", "are", "of", "to", "for", "with", "me", "tell"}

    def rerank(self, query: str, chunks: List[Chunk], intent: Optional[str] = None) -> List[Tuple[Chunk, float]]:
        """Computes query coverage, column matching, and semantic density relevance score (0.0 to 1.0)."""
        logger.info(f"Executing MockReranker (query coverage + semantic density, intent={intent})...")
        q_clean = query.lower()
        all_words = [w.strip("?,.!\"'") for w in q_clean.split() if len(w.strip("?,.!\"'")) > 1]
        
        # Filter content words
        content_words = [w for w in all_words if w not in self.STOP_WORDS]
        target_words = content_words if content_words else all_words
        
        results = []
        for chunk in chunks:
            c_text_lower = chunk.text.lower()
            c_words_set = set(c_text_lower.split())
            c_type = getattr(chunk.metadata, "chunk_type", "text") or "text"
            chunk_cols = [c.lower() for c in (getattr(chunk.metadata, "columns", []) or [])]
            
            if not target_words:
                score = 0.1
            else:
                matches = 0
                col_matches = 0
                for w in target_words:
                    alias = self.MONTH_ALIASES.get(w, w)
                    matched_in_text = (w in c_words_set or alias in c_words_set or w in c_text_lower or alias in c_text_lower)
                    matched_in_cols = any(w in col for col in chunk_cols)
                    if matched_in_text or matched_in_cols:
                        matches += 1
                    if matched_in_cols:
                        col_matches += 1
                        
                query_coverage = matches / len(target_words)
                
                # Jaccard overlap
                q_set = set(target_words)
                union_len = len(q_set.union(c_words_set))
                jaccard = len(q_set.intersection(c_words_set)) / union_len if union_len > 0 else 0.0
                
                # Combined base score
                raw_score = 0.70 * query_coverage + 0.30 * jaccard
                
                # Boost schema chunk when query intent is SCHEMA_QUERY or questions ask for fields
                if intent == QueryIntent.SCHEMA_QUERY:
                    if c_type == "dataset_schema":
                        raw_score += 0.35 + (0.10 * (col_matches / max(1, len(target_words))))
                    elif c_type == "dataset_summary":
                        raw_score += 0.15
                    elif c_type == "table_rows":
                        raw_score -= 0.15
                elif intent == QueryIntent.AGGREGATION_QUERY:
                    if c_type in ("dataset_summary", "dataset_schema"):
                        raw_score += 0.15
                else:
                    if query_coverage >= 0.75:
                        raw_score += 0.15
                    elif query_coverage >= 0.50:
                        raw_score += 0.10

                if query_coverage == 0 and col_matches == 0:
                    raw_score = 0.05
                    
                score = min(1.0, max(0.05, float(raw_score)))
                
            results.append((chunk, score))
            
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

    def rerank(self, query: str, chunks: List[Chunk], intent: Optional[str] = None) -> List[Tuple[Chunk, float]]:
        if not self._model:
            return MockReranker().rerank(query, chunks, intent=intent)
            
        pairs = [[query, chunk.text] for chunk in chunks]
        scores = self._model.predict(pairs)
        
        results = []
        for idx, score in enumerate(scores):
            norm_score = 1.0 / (1.0 + float(np.exp(-score))) if isinstance(score, (int, float, np.number)) else float(score)
            results.append((chunks[idx], float(norm_score)))
            
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

    @staticmethod
    def classify_intent(query: str) -> QueryIntent:
        """Classifies user query into structured retrieval intent."""
        q = query.lower().strip()
        
        # 1. Row lookup intent (specific filters, single records)
        row_lookup_keywords = [
            "show me rows", "show rows", "show records", "find records", 
            "lookup row", "find reviews for", "show reviews for", "records where", 
            "rows where", "where is_fake_review", "product p0", "is_fake_review = 1"
        ]
        if any(k in q for k in row_lookup_keywords):
            return QueryIntent.ROW_LOOKUP
            
        # 2. Aggregation intent (numerical questions needing exact calculation)
        analytical_keywords = [
            "average", "mean", "percentage", "percent", "pct", "total count", 
            "sum", "how many", "which category has the most", "highest count", 
            "lowest count", "max rating", "min rating", "average rating"
        ]
        if any(k in q for k in analytical_keywords):
            return QueryIntent.AGGREGATION_QUERY

        # 3. Schema intent (fields, columns, schema structure)
        schema_keywords = [
            "field", "fields", "column", "columns", "schema", "which field", 
            "what field", "which column", "what column", "what are the columns", 
            "available fields", "attribute", "attributes", "data type", "data types"
        ]
        if any(k in q for k in schema_keywords):
            return QueryIntent.SCHEMA_QUERY
            
        # 4. Summary intent
        if any(k in q for k in ["summarize", "summary", "overview of dataset", "what is this dataset about"]):
            return QueryIntent.SUMMARY_QUERY
            
        # 5. Relationship intent
        if any(k in q for k in ["relationship", "correlat", "relate to customer"]):
            return QueryIntent.RELATIONSHIP_QUERY
            
        return QueryIntent.DOCUMENT_FACT_QUERY

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
                        workspace=cit.get("workspace", "default"),
                        chunk_type=cit.get("chunk_type", "text"),
                        row_start=cit.get("row_start"),
                        row_end=cit.get("row_end"),
                        columns=cit.get("columns", [])
                    )
                    results.append(
                        RetrievalResult(
                            chunk_id=item.get("chunk_id"),
                            doc_id=item.get("doc_id"),
                            text=item.get("text"),
                            score=item.get("score"),
                            relevance_label=item.get("relevance_label", "Relevant"),
                            explanation=item.get("explanation"),
                            chunk_type=item.get("chunk_type"),
                            row_range=item.get("row_range"),
                            matched_columns=item.get("matched_columns", []),
                            citation=citation
                        )
                    )
                return results
        except Exception:
            pass

        intent = self.classify_intent(query)
        logger.info(f"Retrieving for query: '{query}' (intent={intent}, alpha={hybrid_alpha}, rerank={enable_rerank})")
        
        # 1. Fetch vector results if alpha > 0
        vector_res = []
        if hybrid_alpha > 0.0:
            query_vec = self.embeddings.get_embedding(query)
            # Fetch a larger candidate pool to allow RRF merge and rerank
            vector_res = self.repo.query_similarity(query_vec, limit=limit * 3, filters=filters)
            
        # 2. Fetch keyword results if alpha < 1
        keyword_res = []
        if hybrid_alpha < 1.0:
            keyword_res = self.repo.keyword_search(query, limit=limit * 3, filters=filters)
            
        # 3. Merge results
        if hybrid_alpha == 1.0:
            candidate_tuples = vector_res
        elif hybrid_alpha == 0.0:
            candidate_tuples = keyword_res
        else:
            candidate_tuples = self.reciprocal_rank_fusion(vector_res, keyword_res)
            
        # Deduplicate candidates by chunk ID and content
        seen_ids = set()
        dedup_candidates = []
        for chunk, score in candidate_tuples:
            if chunk.id not in seen_ids:
                seen_ids.add(chunk.id)
                dedup_candidates.append((chunk, score))
                
        chunks = [item[0] for item in dedup_candidates]

        # 4. Reranking or default score calculation with intent prioritization
        if (enable_rerank or intent == QueryIntent.SCHEMA_QUERY) and chunks:
            ranked_tuples = self.reranker.rerank(query, chunks, intent=intent)
            scoring_mode = "rerank"
        else:
            ranked_tuples = dedup_candidates
            if hybrid_alpha == 1.0:
                scoring_mode = "dense"
            elif hybrid_alpha == 0.0:
                scoring_mode = "keyword"
            else:
                scoring_mode = "rrf"

        # If SCHEMA_QUERY, ensure schema chunks matching query appear first
        if intent == QueryIntent.SCHEMA_QUERY and ranked_tuples:
            schema_tuples = [t for t in ranked_tuples if getattr(t[0].metadata, "chunk_type", "") == "dataset_schema"]
            other_tuples = [t for t in ranked_tuples if getattr(t[0].metadata, "chunk_type", "") != "dataset_schema"]
            ranked_tuples = schema_tuples + other_tuples
            
        # Slice to limit
        top_tuples = ranked_tuples[:limit]
        max_raw = max([t[1] for t in top_tuples], default=1.0)
        
        # 5. Format into RetrievalResult schemas
        formatted_results = []
        q_clean = query.lower()
        all_q_words = [w.strip("?,.!\"'") for w in q_clean.split() if len(w.strip("?,.!\"'")) > 1]
        stop_words = {"what", "is", "the", "in", "a", "an", "for", "of", "to", "with", "show", "find", "list", "are", "me", "tell", "from", "which"}
        q_words = [w for w in all_q_words if w not in stop_words]
        if not q_words:
            q_words = all_q_words

        for chunk, raw_score in top_tuples:
            c_type = getattr(chunk.metadata, "chunk_type", "text") or "text"
            c_text_lower = chunk.text.lower()
            chunk_cols = getattr(chunk.metadata, "columns", []) or []
            matched_terms = [w for w in q_words if w in c_text_lower]
            matched_cols = [c for c in chunk_cols if any(qw in c.lower() for qw in q_words)]
            
            # Check if query had any genuine match with this chunk
            has_term_match = len(matched_terms) > 0 or len(matched_cols) > 0

            # Score normalization and calibration
            if scoring_mode == "rerank":
                norm_score = float(raw_score)
            elif scoring_mode == "rrf":
                max_rrf = 2.0 / 61.0
                norm_score = float(raw_score / max_rrf)
            elif scoring_mode in ("dense", "keyword") and max_raw > 0 and max_raw < 0.4:
                norm_score = float(raw_score / max_raw)
            else:
                norm_score = float(raw_score)

            if not has_term_match:
                # No content words matched: calibrate strictly low
                norm_score = min(0.20, norm_score * 0.25)
            else:
                # Direct schema match boost for schema queries
                if intent == QueryIntent.SCHEMA_QUERY and c_type == "dataset_schema" and matched_cols:
                    norm_score = max(0.85, norm_score)
                    
            norm_score = round(min(1.0, max(0.05, norm_score)), 2)
            
            # Relevance label assignment
            if norm_score >= 0.75:
                rel_label = "Highly Relevant"
            elif norm_score >= 0.50:
                rel_label = "Relevant"
            elif norm_score >= 0.30:
                rel_label = "Moderately Relevant"
            else:
                rel_label = "Low Relevance"
                
            # Match explanation generation
            c_type = getattr(chunk.metadata, "chunk_type", "text") or "text"
            c_text_lower = chunk.text.lower()
            matched_terms = [w for w in q_words if w in c_text_lower]
            chunk_cols = getattr(chunk.metadata, "columns", []) or []
            matched_cols = [c for c in chunk_cols if any(qw in c.lower() for qw in q_words)]
            fn = chunk.metadata.filename
            
            if c_type == "dataset_schema":
                expl = f"Matched dataset schema context for '{fn}'. Fields: {', '.join(matched_cols[:4]) if matched_cols else 'table schema'}."
            elif c_type == "dataset_summary":
                expl = f"Matched statistical summary for dataset '{fn}'."
            elif c_type == "table_rows":
                r_range = f"Rows {chunk.metadata.row_start}–{chunk.metadata.row_end}" if getattr(chunk.metadata, "row_start", None) else "row records"
                if matched_terms:
                    expl = f"Matched query terms ({', '.join(matched_terms[:3])}) in {r_range} of '{fn}'."
                else:
                    expl = f"Relevant row record match ({r_range}) in '{fn}'."
            else:
                if matched_terms:
                    expl = f"Semantic match on key terms: {', '.join(matched_terms[:3])}."
                else:
                    expl = f"Semantic text passage match in '{fn}'."

            row_rng = f"{chunk.metadata.row_start}–{chunk.metadata.row_end}" if getattr(chunk.metadata, "row_start", None) else None

            citation = Citation(
                filename=chunk.metadata.filename,
                document_type=chunk.metadata.document_type,
                page=chunk.metadata.page,
                heading=chunk.metadata.heading,
                workspace=chunk.metadata.workspace or "default",
                chunk_type=c_type,
                row_start=getattr(chunk.metadata, "row_start", None),
                row_end=getattr(chunk.metadata, "row_end", None),
                columns=chunk_cols
            )
            
            formatted_results.append(
                RetrievalResult(
                    chunk_id=chunk.id,
                    doc_id=chunk.doc_id,
                    text=chunk.text,
                    score=norm_score,
                    relevance_label=rel_label,
                    explanation=expl,
                    chunk_type=c_type,
                    row_range=row_rng,
                    matched_columns=matched_cols,
                    citation=citation
                )
            )
            
        # Observe latency
        duration = time.perf_counter() - start_time
        workspace_lbl = filters.get("workspace", "default") if filters else "default"
        RAG_RETRIEVAL_LATENCY.labels(workspace=workspace_lbl).observe(duration)
        
        # Save to cache
        try:
            cache_payload = [item.model_dump() for item in formatted_results]
            run_async_as_sync(cache_client.set(cache_key, cache_payload, ttl=300))
        except Exception:
            pass
            
        return formatted_results
