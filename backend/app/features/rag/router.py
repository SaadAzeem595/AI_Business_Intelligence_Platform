import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status

from app.core.dependencies import get_current_user, MockUser
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
    workspace: Optional[str] = Form("default"),
    tags: Optional[str] = Form(""),  # comma-separated
    current_user: MockUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """Uploads, parses, cleans, chunks, embeds, and indexes a business document."""
    try:
        content_bytes = await file.read()
        filename = file.filename
        
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
        
        # 4. Generate embeddings and create Chunk objects
        for i, cd in enumerate(chunk_dicts):
            chunk_text = cd["text"]
            heading = cd["heading"]
            
            chunk_embedding = embeddings.get_embedding(chunk_text)
            
            meta = DocumentMetadata(
                filename=filename,
                author=author,
                upload_date=datetime.now().strftime("%Y-%m-%d"),
                workspace=workspace,
                page=i + 1,  # Page maps to chunk sequence number for non-paged formats
                heading=heading,
                tags=tag_list,
                document_type=filename.split(".")[-1].upper() if "." in filename else "TXT"
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
        
        return {
            "status": "success",
            "doc_id": doc_id,
            "filename": filename,
            "chunks_count": len(chunks_to_insert),
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
        results = retrieval_svc.retrieve(
            query=payload.query,
            limit=payload.limit,
            filters=payload.filters,
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
    workspace: Optional[str] = "default",
    current_user: MockUser = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """Returns metadata listings of all indexed documents in a workspace."""
    try:
        return db_repo.list_documents(workspace=workspace)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to list documents: {str(e)}"
        )

@router.delete("/documents/{doc_id}")
async def delete_rag_document(
    doc_id: str,
    current_user: MockUser = Depends(get_current_user)
) -> Dict[str, str]:
    """Deletes all indexed chunks and reference markers associated with a document ID."""
    try:
        db_repo.delete_by_document(doc_id)
        return {"status": "success", "message": f"Successfully deleted document '{doc_id}' from index."}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to delete document: {str(e)}"
        )
