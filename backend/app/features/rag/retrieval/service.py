from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple, Union
import logging
import hashlib
import json
import time
import re

from app.features.rag.schemas import Chunk, RetrievalResult, Citation, QueryIntent, RetrievalDiagnostics
from app.features.rag.embeddings.providers import BaseEmbeddingProvider
from app.features.rag.vector_store.repository import BaseVectorRepository

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
    STOP_WORDS = {
        "what", "was", "the", "in", "which", "had", "do", "show", "over", "time", 
        "a", "an", "is", "are", "of", "to", "for", "with", "me", "tell", "from",
        "how", "does", "mean", "dataset", "datasets", "table", "tables", "contains",
        "contain", "between", "difference", "related"
    }

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
            heading_str = f"{chunk.metadata.heading or ''} {getattr(chunk.metadata, 'heading_path', '') or ''}".lower()
            c_text_lower = f"{heading_str} {chunk.text.lower()}".strip()
            c_words_set = set(c_text_lower.split())
            c_type = getattr(chunk.metadata, "chunk_type", "text") or "text"
            chunk_cols = [c.lower() for c in (getattr(chunk.metadata, "columns", []) or [])]
            fn_clean = (chunk.metadata.filename or "").lower()
            
            if not target_words:
                score = 0.1
            else:
                matches = 0
                col_matches = 0
                for w in target_words:
                    alias = self.MONTH_ALIASES.get(w, w)
                    stem = w[:-3] if len(w) > 6 and w.endswith("ies") else (w[:-1] if len(w) > 4 and w.endswith("s") else w)
                    matched_in_text = (
                        w in c_words_set or alias in c_words_set or w in c_text_lower or alias in c_text_lower
                        or stem in c_text_lower or w in fn_clean
                    )
                    matched_in_cols = any(w in col or stem in col for col in chunk_cols)
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
                
                # Filename match boost
                if fn_clean and (fn_clean in q_clean or any(p in q_clean for p in fn_clean.split(".") if len(p) > 3)):
                    raw_score += 0.20

                # Boost schema chunk when query intent is SCHEMA_QUERY or questions ask for fields/columns
                if intent == QueryIntent.SCHEMA_QUERY or any(k in q_clean for k in ["column", "columns", "field", "fields", "schema"]):
                    if c_type == "dataset_schema":
                        raw_score += 0.40 + (0.15 * (col_matches / max(1, len(target_words))))
                    elif c_type == "dataset_summary":
                        raw_score += 0.20
                    elif c_type == "table_rows":
                        raw_score -= 0.10
                elif intent == QueryIntent.AGGREGATION_QUERY:
                    if c_type in ("dataset_summary", "dataset_schema"):
                        raw_score += 0.15
                else:
                    if query_coverage >= 0.75:
                        raw_score += 0.15
                    elif query_coverage >= 0.50:
                        raw_score += 0.10

                # Dimension / weight query boosting
                if any(w in q_clean for w in ["dimension", "dimensions", "weight", "height", "width", "length", "lenght"]):
                    if any(dw in col for col in chunk_cols for dw in ["weight", "length", "lenght", "height", "width"]):
                        raw_score += 0.25

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
            
        import numpy as np
        pairs = [[query, chunk.text] for chunk in chunks]
        scores = self._model.predict(pairs)
        
        results = []
        for idx, score in enumerate(scores):
            norm_score = 1.0 / (1.0 + float(np.exp(-score))) if isinstance(score, (int, float, np.number)) else float(score)
            results.append((chunks[idx], float(norm_score)))
            
        return sorted(results, key=lambda x: x[1], reverse=True)


class RetrievalService:
    """Coordinates vector, keyword, hybrid retrieval and reranking pipelines with diagnostics."""
    
    def __init__(
        self, 
        vector_repo: BaseVectorRepository, 
        embedding_provider: BaseEmbeddingProvider,
        reranker: Optional[BaseReranker] = None
    ):
        self.repo = vector_repo
        self.embeddings = embedding_provider
        self.reranker = reranker or MockReranker()
        self._memory_cache: Dict[str, Tuple[List[Dict[str, Any]], float]] = {}
        self.last_diagnostics: Optional[RetrievalDiagnostics] = None

    def clear_cache(self) -> None:
        """Clears the in-memory retrieval cache."""
        self._memory_cache.clear()

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

        # 3. Schema intent (fields, columns, schema structure, dimensions, weight)
        schema_keywords = [
            "field", "fields", "column", "columns", "schema", "which field", 
            "what field", "which column", "what column", "what are the columns", 
            "available fields", "attribute", "attributes", "data type", "data types",
            "dimensions and weight", "product dimensions", "which columns contain"
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
        alpha: float = 0.5,
        k: int = 60
    ) -> List[Tuple[Chunk, float]]:
        """
        Combines rankings from vector and keyword results using weighted Reciprocal Rank Fusion (RRF).
        RRF(chunk) = alpha * (1 / (k + dense_rank + 1)) + (1 - alpha) * (1 / (k + bm25_rank + 1))
        Gracefully degrades when one search arm is empty.
        Eligible chunks do NOT require appearance in both arms.
        """
        # Case A: BM25 results exist, Dense is empty
        if not vector_results and keyword_results:
            return keyword_results
            
        # Case B: Dense results exist, BM25 is empty
        if not keyword_results and vector_results:
            return vector_results
            
        # Case D: Both empty
        if not vector_results and not keyword_results:
            return []

        # Case C: Both exist -> Weighted RRF
        rrf_scores = {}
        chunk_map = {}
        
        # Add vector ranks weighted by alpha
        dense_weight = float(alpha)
        for rank, (chunk, _) in enumerate(vector_results):
            chunk_map[chunk.id] = chunk
            rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + (dense_weight / (k + rank + 1))
            
        # Add keyword ranks weighted by (1 - alpha)
        bm25_weight = float(1.0 - alpha)
        for rank, (chunk, _) in enumerate(keyword_results):
            chunk_map[chunk.id] = chunk
            rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + (bm25_weight / (k + rank + 1))
            
        sorted_rrf = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        return [(chunk_map[chunk_id], float(score)) for chunk_id, score in sorted_rrf]

    def retrieve(
        self,
        query: str,
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        hybrid_alpha: float = 0.5,
        enable_rerank: bool = False,
        return_diagnostics: bool = False
    ) -> Union[List[RetrievalResult], Tuple[List[RetrievalResult], RetrievalDiagnostics]]:
        """Runs vector/keyword/hybrid retrieval and outputs ranked results with citations and diagnostics."""
        start_time = time.perf_counter()
        project_scope = (filters.get("workspace") or filters.get("project_id") or "default") if filters else "default"
        
        # In-memory fast cache check
        filter_str = json.dumps(filters, sort_keys=True) if filters else ""
        cache_str = f"{query}:{limit}:{filter_str}:{hybrid_alpha}:{enable_rerank}"
        cache_hash = hashlib.md5(cache_str.encode("utf-8")).hexdigest()
        now = time.time()
        
        if cache_hash in self._memory_cache:
            cached_data, expire_at = self._memory_cache[cache_hash]
            if now < expire_at:
                results = []
                for item in cached_data:
                    cit = item.get("citation", {})
                    citation = Citation(
                        filename=cit.get("filename"),
                        document_type=cit.get("document_type"),
                        page=cit.get("page"),
                        heading=cit.get("heading"),
                        workspace=cit.get("workspace", project_scope),
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
                if return_diagnostics and self.last_diagnostics:
                    return results, self.last_diagnostics
                return results

        # 0. Measure project scope
        proj_stats = self.repo.get_project_diagnostics(project_scope)
        docs_in_scope = proj_stats.get("documents_in_scope", 0)
        chunks_in_scope = proj_stats.get("chunks_in_scope", 0)

        intent = self.classify_intent(query)
        logger.info(
            f"RAG_RETRIEVE_START: query='{query}' project='{project_scope}' "
            f"docs_in_scope={docs_in_scope} chunks_in_scope={chunks_in_scope} alpha={hybrid_alpha}"
        )
        
        # 1. Fetch vector results if alpha > 0
        vector_res: List[Tuple[Chunk, float]] = []
        query_vec_generated = False
        query_vec_dim = getattr(self.embeddings, "dimension", 1536)
        dense_model_name = getattr(self.embeddings, "model_name", "openai/text-embedding-3-small")

        if hybrid_alpha > 0.0 and chunks_in_scope > 0:
            try:
                query_vec = self.embeddings.get_embedding(query)
                query_vec_generated = True
                query_vec_dim = len(query_vec)
                logger.info(
                    f"RAG_QUERY_EMBEDDING: query_embedding_generated=True "
                    f"query_embedding_dimension={query_vec_dim} configured_embedding_model='{dense_model_name}'"
                )
                vector_res = self.repo.query_similarity(query_vec, limit=limit * 4, filters=filters)
            except Exception as emb_err:
                logger.warning(f"RAG_DENSE_RETRIEVAL_WARN: Vector search failed ({emb_err}). Continuing with BM25 degradation.")
                query_vec_generated = False
            
        # 2. Fetch keyword / BM25 results if alpha < 1
        keyword_res: List[Tuple[Chunk, float]] = []
        if hybrid_alpha < 1.0 and chunks_in_scope > 0:
            try:
                keyword_res = self.repo.keyword_search(query, limit=limit * 4, filters=filters)
            except Exception as bm_err:
                logger.warning(f"RAG_BM25_RETRIEVAL_WARN: BM25 search failed ({bm_err}). Continuing with Dense degradation.")

        # 3. Merge results with weighted RRF
        if hybrid_alpha == 1.0:
            candidate_tuples = vector_res
            scoring_mode = "dense"
        elif hybrid_alpha == 0.0:
            candidate_tuples = keyword_res
            scoring_mode = "keyword"
        else:
            candidate_tuples = self.reciprocal_rank_fusion(vector_res, keyword_res, alpha=hybrid_alpha)
            scoring_mode = "rrf"
            
        # Deduplicate candidates by chunk ID and text content
        seen_ids = set()
        seen_texts = set()
        dedup_candidates = []
        for chunk, score in candidate_tuples:
            text_key = (getattr(chunk.metadata, "filename", "") or "", chunk.text.strip())
            if chunk.id not in seen_ids and text_key not in seen_texts:
                seen_ids.add(chunk.id)
                seen_texts.add(text_key)
                dedup_candidates.append((chunk, score))

        # 4. Metadata, Filename & Schema Boosting
        q_lower = query.lower()
        is_schema_q = (
            intent == QueryIntent.SCHEMA_QUERY
            or any(w in q_lower for w in ["column", "columns", "schema", "field", "fields", "attribute", "attributes"])
        )
        is_dimension_q = any(w in q_lower for w in ["dimension", "dimensions", "weight", "height", "width", "length", "lenght", "size"])

        boosted_tuples = []
        for chunk, score in dedup_candidates:
            c_type = getattr(chunk.metadata, "chunk_type", "") or "text"
            c_cols = [c.lower() for c in (getattr(chunk.metadata, "columns", []) or [])]
            fn_clean = (chunk.metadata.filename or "").lower()

            boost = 0.0
            # Document filename boosting
            if fn_clean and (fn_clean in q_lower or any(p in q_lower for p in fn_clean.split(".") if len(p) > 3)):
                boost += 0.20

            # Schema chunk boosting
            if is_schema_q:
                if c_type == "dataset_schema":
                    boost += 0.40
                elif c_type == "dataset_summary":
                    boost += 0.20

            # Dimension / weight boosting
            if is_dimension_q:
                if any(dw in col for col in c_cols for dw in ["weight", "length", "lenght", "height", "width"]):
                    boost += 0.30

            boosted_tuples.append((chunk, score + boost))

        boosted_tuples = sorted(boosted_tuples, key=lambda x: x[1], reverse=True)
        chunks = [item[0] for item in boosted_tuples]

        # 5. Reranking or scoring
        if (enable_rerank or is_schema_q) and chunks:
            ranked_tuples = self.reranker.rerank(query, chunks, intent=intent)
            scoring_mode = "rerank"
        else:
            ranked_tuples = boosted_tuples

        # Slice to requested Top-K limit
        top_tuples = ranked_tuples[:limit]
        max_raw = max([t[1] for t in top_tuples], default=1.0)
        
        # 6. Format into RetrievalResult schemas
        formatted_results = []
        all_q_words = [w.strip("?,.!\"'") for w in q_lower.split() if len(w.strip("?,.!\"'")) > 1]
        stop_words = {"what", "is", "the", "in", "a", "an", "for", "of", "to", "with", "show", "find", "list", "are", "me", "tell", "from", "which", "how", "who"}
        q_words = [w for w in all_q_words if w not in stop_words]
        if not q_words:
            q_words = all_q_words

        for chunk, raw_score in top_tuples:
            c_type = getattr(chunk.metadata, "chunk_type", "text") or "text"
            c_text_lower = chunk.text.lower()
            chunk_cols = getattr(chunk.metadata, "columns", []) or []
            matched_terms = [w for w in q_words if w in c_text_lower]
            matched_cols = [c for c in chunk_cols if any(qw in c.lower() for qw in q_words)]
            
            has_term_match = len(matched_terms) > 0 or len(matched_cols) > 0

            # Score calibration
            if scoring_mode == "rerank":
                norm_score = float(raw_score)
            elif scoring_mode == "rrf":
                max_rrf = 2.0 / 61.0
                norm_score = float(raw_score / max_rrf)
            elif scoring_mode in ("dense", "keyword") and max_raw > 0 and max_raw < 0.4:
                norm_score = float(raw_score / max_raw)
            else:
                norm_score = float(raw_score)

            if not has_term_match and scoring_mode != "rerank":
                norm_score = min(0.35, norm_score * 0.5)
            else:
                if (is_schema_q or is_dimension_q) and c_type == "dataset_schema":
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
                workspace=chunk.metadata.workspace or project_scope,
                chunk_type=c_type,
                row_start=getattr(chunk.metadata, "row_start", None),
                row_end=getattr(chunk.metadata, "row_end", None),
                columns=chunk_cols,
                project_id=getattr(chunk.metadata, "project_id", project_scope)
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

        # 7. Determine Search Diagnostics State
        if docs_in_scope == 0:
            search_state = "NO_DOCUMENTS"
        elif chunks_in_scope == 0:
            search_state = "NO_CHUNKS"
        elif hybrid_alpha == 1.0 and not query_vec_generated:
            search_state = "DENSE_FAILED"
        elif len(formatted_results) == 0:
            search_state = "NO_RELEVANT_MATCHES"
        else:
            search_state = "SUCCESS"

        diagnostics = RetrievalDiagnostics(
            query=query,
            project_id=project_scope,
            workspace_id=project_scope,
            documents_in_scope=docs_in_scope,
            chunks_in_scope=chunks_in_scope,
            bm25_candidates=len(keyword_res),
            dense_candidates=len(vector_res),
            rrf_candidates=len(candidate_tuples),
            after_threshold=len(ranked_tuples),
            final_top_k=len(formatted_results),
            search_state=search_state,
            embedding_model=dense_model_name,
            embedding_dimension=query_vec_dim,
            query_embedding_generated=query_vec_generated
        )
        self.last_diagnostics = diagnostics

        # Structured diagnostic logging
        logger.info(
            f"RAG_RETRIEVAL_DIAGNOSTIC: {json.dumps(diagnostics.model_dump())}"
        )

        # Cache results in memory
        try:
            cache_payload = [item.model_dump() for item in formatted_results]
            self._memory_cache[cache_hash] = (cache_payload, now + 300.0)
        except Exception:
            pass

        if return_diagnostics:
            return formatted_results, diagnostics
        return formatted_results
