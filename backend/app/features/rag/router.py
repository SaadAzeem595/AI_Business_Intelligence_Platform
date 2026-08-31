import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status

from app.core.dependencies import get_current_user, MockUser, require_role
from app.features.rag.schemas import (
    QueryPayload, 
    ContextResponse, 
    EvaluationPayload, 
    EvaluationMetrics,
    DocumentMetadata,
    AnalyticalAnswer,
    RetrievalResult
)
from app.features.rag.ingestion.ocr import MockOCRProvider
from app.features.rag.ingestion.parsers import DocumentParserService
from app.features.rag.ingestion.cleaner import TextCleaner
from app.features.rag.ingestion.chunker import ChunkerService
from app.features.rag.embeddings.providers import MockEmbeddingProvider
from app.features.rag.vector_store.repository import DuckDBVectorRepository
from app.features.rag.retrieval.service import RetrievalService
from app.features.rag.retrieval.context_builder import ContextBuilder
from app.features.rag.evaluation.service import RAGEvaluationService
from app.features.rag.schemas import Chunk
from app.core.cache import cache_client

router = APIRouter(prefix="/rag", tags=["RAG Knowledge Layer Operations"])

# Initialize RAG components (default to DuckDB persistence and Mock embeddings for CPU environments)
db_repo = DuckDBVectorRepository(db_path="rag_vector.db")
embeddings = MockEmbeddingProvider()
retrieval_svc = RetrievalService(vector_repo=db_repo, embedding_provider=embeddings)
parser_svc = DocumentParserService(ocr_provider=MockOCRProvider())
chunker_svc = ChunkerService()


def check_and_execute_analytical_routing(query: str, project_id: str, results: List[RetrievalResult]) -> Optional[AnalyticalAnswer]:
    """
    Detects if query requires exact numerical calculation (percentages, averages, counts).
    If structured tabular datasets exist, routes calculation to DuckDB SQL analytics engine.
    """
    q_lower = query.lower()
    analytical_keywords = ["average", "mean", "percentage", "percent", "pct", "total", "sum", "count", "fake", "rating", "how many"]
    if not any(k in q_lower for k in analytical_keywords):
        return None

    # Find tabular chunks in search results to identify dataset filename
    tabular_results = [r for r in results if r.chunk_type in ("dataset_schema", "dataset_summary", "table_rows") or r.citation.document_type in ("CSV", "XLSX", "XLS")]
    if not tabular_results:
        return None

    target_filename = tabular_results[0].citation.filename
    table_name = target_filename.split(".")[0].lower().replace(" ", "_").replace("-", "_")

    try:
        from app.features.agents.tools import execute_duckdb_query
        
        # Scenario A: Fake review percentage question
        if "fake" in q_lower and ("percent" in q_lower or "percentage" in q_lower or "%" in q_lower or "rate" in q_lower or "how many" in q_lower):
            sql = f'SELECT COUNT(*) as total, COUNT(CASE WHEN LOWER(CAST(is_fake_review AS VARCHAR)) IN (\'1\', \'true\', \'yes\') THEN 1 END) as fake_count FROM "{table_name}"'
            res = execute_duckdb_query(sql, project_id=project_id)
            if res and res.get("rows") and len(res["rows"]) > 0:
                row = res["rows"][0]
                total = row.get("total", 0) or 0
                fake_count = row.get("fake_count", 0) or 0
                if total > 0:
                    pct = round((fake_count / total) * 100.0, 1)
                    return AnalyticalAnswer(
                        is_analytical=True,
                        question=query,
                        calculated_value=f"{pct}% ({fake_count:,} fake out of {total:,} total reviews)",
                        explanation=f"Calculated exact fake review percentage via DuckDB SQL query on dataset '{target_filename}' (field: 'is_fake_review').",
                        sql_query=sql,
                        dataset_name=target_filename
                    )

        # Scenario B: Average rating question
        if "average" in q_lower or "mean" in q_lower or "rating" in q_lower:
            sql = f'SELECT AVG(CAST(star_rating AS DOUBLE)) as avg_rating, COUNT(*) as total FROM "{table_name}" WHERE star_rating IS NOT NULL'
            res = execute_duckdb_query(sql, project_id=project_id)
            if res and res.get("rows") and len(res["rows"]) > 0:
                row = res["rows"][0]
                avg_val = row.get("avg_rating")
                total = row.get("total", 0)
                if avg_val is not None:
                    return AnalyticalAnswer(
                        is_analytical=True,
                        question=query,
                        calculated_value=f"{round(float(avg_val), 2)} / 5.0 (across {total:,} rated entries)",
                        explanation=f"Calculated exact average star rating via DuckDB SQL query on dataset '{target_filename}' (field: 'star_rating').",
                        sql_query=sql,
                        dataset_name=target_filename
                    )

        # Scenario C: General count / total question
        if "count" in q_lower or "total" in q_lower or "how many" in q_lower:
            sql = f'SELECT COUNT(*) as total FROM "{table_name}"'
            res = execute_duckdb_query(sql, project_id=project_id)
            if res and res.get("rows") and len(res["rows"]) > 0:
                total = res["rows"][0].get("total", 0)
                return AnalyticalAnswer(
                    is_analytical=True,
                    question=query,
                    calculated_value=f"{total:,} total records",
                    explanation=f"Calculated total record count via DuckDB SQL query on dataset '{target_filename}'.",
                    sql_query=sql,
                    dataset_name=target_filename
                )

    except Exception as err:
        pass

    return None


@router.post("/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_document(
    file: UploadFile = File(...),
    author: Optional[str] = Form("Unknown"),
    workspace: Optional[str] = Form(None),
    tags: Optional[str] = Form(""),  # comma-separated
    current_user: MockUser = Depends(require_role(["Analyst", "Admin"]))
) -> Dict[str, Any]:
    """Uploads, parses, cleans, chunks, embeds, and indexes a business document."""
    try:
        content_bytes = await file.read()
        filename = file.filename or "document.txt"
        file_size = len(content_bytes)
        target_ws = workspace.strip() if (workspace and workspace.strip()) else current_user.workspace_id
        
        # 1. Parse document
        raw_text = parser_svc.parse_file(content_bytes, filename)
        
        # 2. Clean text
        clean_text = TextCleaner.normalize_text(raw_text)
        if not clean_text:
            raise ValueError("Document did not contain any extractable text.")
            
        # 3. Chunk text (heading & tabular aware)
        chunk_dicts = chunker_svc.chunk_by_heading(clean_text)
        
        # Parse tags
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        
        doc_id = str(uuid.uuid4())
        chunks_to_insert = []
        
        # 4. Batch generate embeddings and create Chunk objects
        chunk_texts = [cd["text"] for cd in chunk_dicts]
        chunk_embeddings = embeddings.get_embeddings(chunk_texts)
        
        doc_ext = filename.split(".")[-1].upper() if "." in filename else "TXT"
        for i, cd in enumerate(chunk_dicts):
            chunk_text = cd["text"]
            heading = cd["heading"]
            chunk_embedding = chunk_embeddings[i]
            
            meta = DocumentMetadata(
                filename=filename,
                author=author,
                upload_date=datetime.now().strftime("%Y-%m-%d"),
                workspace=target_ws,
                page=i + 1,  # Page maps to chunk sequence number for non-paged formats
                heading=heading,
                tags=tag_list,
                document_type=doc_ext,
                file_size=file_size,
                chunk_type=cd.get("chunk_type", "text"),
                row_start=cd.get("row_start"),
                row_end=cd.get("row_end"),
                columns=cd.get("columns", []),
                table_name=cd.get("table_name")
            )
            
            chunk_obj = Chunk(
                id=f"{doc_id}-{i}",
                doc_id=doc_id,
                text=chunk_text,
                embedding=chunk_embedding,
                metadata=meta
            )
            chunks_to_insert.append(chunk_obj)
            
        # 5. Index chunks
        db_repo.insert_chunks(chunks_to_insert)
        
        # Invalidate RAG retrieve cache
        await cache_client.invalidate_pattern("rag_retrieve:*")
        
        return {
            "status": "success",
            "doc_id": doc_id,
            "filename": filename,
            "chunks_count": len(chunks_to_insert),
            "file_size": file_size,
            "workspace": target_ws,
            "message": f"Successfully parsed and indexed {len(chunks_to_insert)} chunks into project '{target_ws}'."
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "DOCUMENT_INDEXING_FAILED",
                "message": f"Document ingestion failed: {str(e)}",
                "filename": file.filename if file else "unknown",
                "workspace": workspace or "default"
            }
        )

@router.post("/retrieve", response_model=ContextResponse)
async def retrieve_context(
    payload: QueryPayload,
    current_user: MockUser = Depends(get_current_user)
) -> ContextResponse:
    """Executes vector/keyword/hybrid retrieval and context compilation."""
    try:
        filters = payload.filters or {}
        if "workspace" not in filters or not filters["workspace"]:
            filters["workspace"] = current_user.workspace_id
        
        results = retrieval_svc.retrieve(
            query=payload.query,
            limit=payload.limit,
            filters=filters,
            hybrid_alpha=payload.hybrid_alpha,
            enable_rerank=payload.enable_rerank
        )
        
        # Build prompt context
        context_text, token_count = ContextBuilder.build_context(results)
        
        # Check for analytical calculation routing
        analytical_ans = check_and_execute_analytical_routing(
            query=payload.query,
            project_id=filters.get("workspace", current_user.workspace_id),
            results=results
        )
        
        return ContextResponse(
            context_text=context_text,
            results=results,
            token_count=token_count,
            analytical_answer=analytical_ans
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Context retrieval failed: {str(e)}"
        )

@router.post("/evaluate", response_model=EvaluationMetrics)
async def evaluate_rag_retrieval(
    payload: EvaluationPayload,
    workspace: Optional[str] = None,
    current_user: MockUser = Depends(get_current_user)
) -> EvaluationMetrics:
    """Evaluates retrieval quality (Hit Rate, MRR, Precision@K) and average latency."""
    try:
        target_ws = workspace.strip() if (workspace and workspace.strip()) else current_user.workspace_id
        filters = {"workspace": target_ws} if target_ws else None
        metrics = RAGEvaluationService.evaluate_retrieval(
            retrieval_service=retrieval_svc,
            ground_truth=payload.benchmark_dataset,
            limit=payload.limit,
            hybrid_alpha=payload.hybrid_alpha,
            filters=filters
        )
        return metrics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Retrieval evaluation failed: {str(e)}"
        )

@router.get("/documents", response_model=List[Dict[str, Any]])
async def list_rag_documents(
    workspace: Optional[str] = None,
    current_user: MockUser = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """Returns metadata listings of all indexed documents in a workspace."""
    try:
        target_ws = workspace.strip() if (workspace and workspace.strip()) else current_user.workspace_id
        return db_repo.list_documents(workspace=target_ws)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to list documents: {str(e)}"
        )

@router.delete("/documents/{doc_id}")
async def delete_rag_document(
    doc_id: str,
    workspace: Optional[str] = None,
    current_user: MockUser = Depends(require_role(["Analyst", "Admin"]))
) -> Dict[str, str]:
    """Deletes all indexed chunks and reference markers associated with a document ID."""
    try:
        db_repo.delete_by_document(doc_id)
        await cache_client.invalidate_pattern("rag_retrieve:*")
        return {"status": "success", "message": f"Successfully deleted document '{doc_id}' from index."}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to delete document: {str(e)}"
        )

@router.post("/reindex/{doc_id}")
async def reindex_rag_document(
    doc_id: str,
    workspace: Optional[str] = Form(None),
    current_user: MockUser = Depends(require_role(["Analyst", "Admin"]))
) -> Dict[str, Any]:
    """Re-chunks and re-embeds an existing indexed document."""
    try:
        target_ws = workspace.strip() if (workspace and workspace.strip()) else current_user.workspace_id
        conn = db_repo._get_connection()
        try:
            res = conn.execute(
                "SELECT text, filename, author, document_type, tags, file_size FROM rag_chunks WHERE doc_id = ?", 
                (doc_id,)
            ).fetchall()
            if not res:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
            full_text = "\n\n".join([row[0] for row in res if row[0]])
            filename = res[0][1]
            author = res[0][2]
            document_type = res[0][3]
            tags_str = res[0][4]
            file_size = res[0][5] or 0
            tag_list = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
        finally:
            conn.close()

        clean_text = TextCleaner.normalize_text(full_text)
        chunk_dicts = chunker_svc.chunk_by_heading(clean_text)

        chunk_texts = [cd["text"] for cd in chunk_dicts]
        chunk_embeddings = embeddings.get_embeddings(chunk_texts)

        chunks_to_insert = []
        for i, cd in enumerate(chunk_dicts):
            chunk_text = cd["text"]
            heading = cd["heading"]
            chunk_embedding = chunk_embeddings[i]

            meta = DocumentMetadata(
                filename=filename,
                author=author,
                upload_date=datetime.now().strftime("%Y-%m-%d"),
                workspace=target_ws,
                page=i + 1,
                heading=heading,
                tags=tag_list,
                document_type=document_type,
                file_size=file_size,
                chunk_type=cd.get("chunk_type", "text"),
                row_start=cd.get("row_start"),
                row_end=cd.get("row_end"),
                columns=cd.get("columns", []),
                table_name=cd.get("table_name")
            )

            chunk_obj = Chunk(
                id=f"{doc_id}-{i}",
                doc_id=doc_id,
                text=chunk_text,
                embedding=chunk_embedding,
                metadata=meta
            )
            chunks_to_insert.append(chunk_obj)

        db_repo.delete_by_document(doc_id)
        db_repo.insert_chunks(chunks_to_insert)
        await cache_client.invalidate_pattern("rag_retrieve:*")

        return {
            "status": "success",
            "doc_id": doc_id,
            "filename": filename,
            "chunks_count": len(chunks_to_insert),
            "message": f"Successfully re-indexed {len(chunks_to_insert)} chunks for {filename}."
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Re-indexing failed: {str(e)}"
        )

