from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class DocumentMetadata(BaseModel):
    filename: str
    author: Optional[str] = "Unknown"
    upload_date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    workspace: Optional[str] = "default"
    page: Optional[int] = None
    heading: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    document_type: str  # PDF, DOCX, PPTX, TXT, MD, HTML, CSV, XLSX, JSON
    file_size: Optional[int] = 0

class Document(BaseModel):
    id: str
    content: str
    metadata: DocumentMetadata

class Chunk(BaseModel):
    id: str
    doc_id: str
    text: str
    embedding: Optional[List[float]] = None
    metadata: DocumentMetadata

class QueryPayload(BaseModel):
    query: str
    limit: int = 5
    filters: Optional[Dict[str, Any]] = None
    hybrid_alpha: float = 0.5  # 0 = keyword only, 1 = vector only, between = hybrid RRF
    enable_rerank: bool = False

class Citation(BaseModel):
    filename: str
    document_type: str
    page: Optional[int] = None
    heading: Optional[str] = None
    workspace: str = "default"

class RetrievalResult(BaseModel):
    chunk_id: str
    doc_id: str
    text: str
    score: float
    citation: Citation

class ContextResponse(BaseModel):
    context_text: str
    results: List[RetrievalResult]
    token_count: int

class GroundTruthItem(BaseModel):
    query: str
    expected_doc_ids: List[str]

class EvaluationPayload(BaseModel):
    benchmark_dataset: List[GroundTruthItem]
    limit: int = 5
    hybrid_alpha: float = 0.5

class EvaluationMetrics(BaseModel):
    hit_rate: float
    mrr: float  # Mean Reciprocal Rank
    precision_at_k: float
    avg_latency_ms: float
    total_queries: int
