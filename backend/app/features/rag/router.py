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
    DocumentMetadata
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
            
        # 3. Chunk text (heading-aware)
        chunk_dicts = chunker_svc.chunk_by_heading(clean_text)
        
        # Parse tags
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        
        doc_id = str(uuid.uuid4())
        chunks_to_insert = []
        
        # 4. Batch generate embeddings and create Chunk objects
        chunk_texts = [cd["text"] for cd in chunk_dicts]
        chunk_embeddings = embeddings.get_embeddings(chunk_texts)
        
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
                document_type=filename.split(".")[-1].upper() if "." in filename else "TXT",
                file_size=file_size
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
            "message": f"Successfully parsed and indexed {len(chunks_to_insert)} chunks."
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document ingestion failed: {str(e)}"
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
        
        return ContextResponse(
            context_text=context_text,
            results=results,
            token_count=token_count
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Context retrieval failed: {str(e)}"
        )

@router.post("/evaluate", response_model=EvaluationMetrics)
async def evaluate_rag_retrieval(
    payload: EvaluationPayload,
    current_user: MockUser = Depends(get_current_user)
) -> EvaluationMetrics:
    """Evaluates retrieval quality (Hit Rate, MRR, Precision@K) and average latency."""
    try:
        metrics = RAGEvaluationService.evaluate_retrieval(
            retrieval_service=retrieval_svc,
            ground_truth=payload.benchmark_dataset,
            limit=payload.limit,
            hybrid_alpha=payload.hybrid_alpha
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
                file_size=file_size
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

