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
    chunk_type: Optional[str] = "text"  # text, dataset_schema, dataset_summary, table_rows
    row_start: Optional[int] = None
    row_end: Optional[int] = None
    columns: List[str] = Field(default_factory=list)
    table_name: Optional[str] = None

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
    chunk_type: Optional[str] = "text"
    row_start: Optional[int] = None
    row_end: Optional[int] = None
    columns: List[str] = Field(default_factory=list)

class RetrievalResult(BaseModel):
    chunk_id: str
    doc_id: str
    text: str
    score: float
    relevance_label: str = "Relevant"  # Highly Relevant, Relevant, Moderately Relevant, Low Relevance
    explanation: Optional[str] = None
    chunk_type: Optional[str] = "text"
    row_range: Optional[str] = None
    matched_columns: List[str] = Field(default_factory=list)
    citation: Citation

class AnalyticalAnswer(BaseModel):
    is_analytical: bool = True
    question: str
    calculated_value: str
    explanation: str
    sql_query: Optional[str] = None
    dataset_name: Optional[str] = None

class ContextResponse(BaseModel):
    context_text: str
    results: List[RetrievalResult]
    token_count: int
    analytical_answer: Optional[AnalyticalAnswer] = None

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
