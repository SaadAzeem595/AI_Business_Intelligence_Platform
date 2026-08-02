import time
from typing import List
from app.features.rag.schemas import EvaluationMetrics, GroundTruthItem
from app.features.rag.retrieval.service import RetrievalService

class RAGEvaluationService:
    @staticmethod
    def evaluate_retrieval(
        retrieval_service: RetrievalService,
        ground_truth: List[GroundTruthItem],
        limit: int = 5,
        hybrid_alpha: float = 0.5
    ) -> EvaluationMetrics:
        """
        Benchmarks retrieval performance by calculating Hit Rate, Mean Reciprocal Rank (MRR),
        Precision@K, and average retrieval latency across a ground-truth dataset.
        """
        total_queries = len(ground_truth)
        if total_queries == 0:
            return EvaluationMetrics(
                hit_rate=0.0,
                mrr=0.0,
                precision_at_k=0.0,
                avg_latency_ms=0.0,
                total_queries=0
            )
            
        hits = 0
        sum_reciprocal_rank = 0.0
        total_precision = 0.0
        total_time_ms = 0.0
        
        for item in ground_truth:
            start_time = time.perf_counter()
            results = retrieval_service.retrieve(
                query=item.query, 
                limit=limit, 
                hybrid_alpha=hybrid_alpha,
                enable_rerank=False
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            total_time_ms += elapsed_ms
            
            retrieved_doc_ids = [res.doc_id for res in results]
            
            # 1. Hit Rate: Was at least one expected document retrieved?
            hit = any(doc_id in item.expected_doc_ids for doc_id in retrieved_doc_ids)
            if hit:
                hits += 1
                
            # 2. Mean Reciprocal Rank (MRR): 1 / rank of the first relevant document
            first_match_rank = None
            for rank, doc_id in enumerate(retrieved_doc_ids):
                if doc_id in item.expected_doc_ids:
                    first_match_rank = rank + 1
                    break
            if first_match_rank is not None:
                sum_reciprocal_rank += 1.0 / first_match_rank
                
            # 3. Precision@K: Proportion of retrieved documents that are relevant
            if retrieved_doc_ids:
                matching_count = sum(1 for doc_id in retrieved_doc_ids if doc_id in item.expected_doc_ids)
                total_precision += matching_count / len(retrieved_doc_ids)
                
        return EvaluationMetrics(
            hit_rate=float(hits / total_queries),
            mrr=float(sum_reciprocal_rank / total_queries),
            precision_at_k=float(total_precision / total_queries),
            avg_latency_ms=float(total_time_ms / total_queries),
            total_queries=total_queries
        )
