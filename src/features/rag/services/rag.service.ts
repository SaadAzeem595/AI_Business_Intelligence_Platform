import { apiClient } from "@/shared/api/client";

export interface RAGDocument {
  doc_id: string;
  filename: string;
  document_type: string;
  upload_date: string;
  workspace: string;
  chunks_count: number;
  pages_count: number;
  file_size: number;
  author: string;
  status: "Indexed" | "Processing" | "Failed";
}

export interface Citation {
  filename: string;
  document_type: string;
  page?: number;
  heading?: string;
  workspace: string;
  chunk_type?: string;
  row_start?: number;
  row_end?: number;
  columns?: string[];
}

export interface RetrievalResult {
  chunk_id: string;
  doc_id: string;
  text: string;
  score: number;
  relevance_label?: string;
  explanation?: string;
  chunk_type?: string;
  row_range?: string;
  matched_columns?: string[];
  citation: Citation;
}

export interface AnalyticalAnswer {
  is_analytical: boolean;
  question: string;
  calculated_value: string;
  explanation: string;
  sql_query?: string;
  dataset_name?: string;
}

export interface GroundedAnswer {
  answer: string;
  grounded: boolean;
  confidence_score: number;
  evidence_status: "sufficient" | "insufficient" | "analytical" | string;
  sources: Array<{
    reference_num: number;
    filename: string;
    heading?: string;
    page?: number;
    chunk_id: string;
    chunk_type?: string;
    row_range?: string;
    score: number;
    source_label?: string;
  }>;
  direct_facts: string[];
  inferences: string[];
  intent?: string;
}

export interface RetrievalDiagnostics {
  project_id: string;
  query: string;
  documents_in_scope: number;
  chunks_in_scope: number;
  bm25_candidates: number;
  dense_candidates: number;
  rrf_candidates: number;
  after_threshold: number;
  final_top_k: number;
  query_embedding_generated: boolean;
  query_embedding_dimension: number;
  configured_embedding_model: string;
  dense_similarity_threshold: number;
  bm25_minimum_score: number;
  execution_mode: string;
  active_project_id?: string;
  active_workspace_id?: string;
}

export interface DocumentDiagnostics {
  document_id: string;
  status: string;
  chunk_count: number;
  embedded_chunk_count: number;
  bm25_indexed: boolean;
  vector_indexed: boolean;
  embedding_model: string;
  embedding_dimension: number;
  project_id: string;
  workspace_id: string;
  searchable: boolean;
  error?: string;
}

export interface ContextResponse {
  context_text: string;
  results: RetrievalResult[];
  token_count: number;
  analytical_answer?: AnalyticalAnswer;
  grounded_answer?: GroundedAnswer;
  query_intent?: string;
  diagnostics?: RetrievalDiagnostics;
}

export interface IngestResponse {
  status: string;
  doc_id: string;
  filename: string;
  chunks_count: number;
  file_size: number;
  workspace: string;
  message: string;
}

export const RAGService = {
  async listDocuments(projectId: string): Promise<RAGDocument[]> {
    if (!projectId) return [];
    const response = await apiClient.get<RAGDocument[]>("/rag/documents", {
      params: { workspace: projectId }
    });
    return response.data;
  },

  async getDocumentDiagnostics(docId: string, projectId: string): Promise<DocumentDiagnostics> {
    const response = await apiClient.get<DocumentDiagnostics>(`/rag/documents/${docId}/diagnostics`, {
      params: { workspace: projectId }
    });
    return response.data;
  },

  async ingestDocument(
    file: File,
    projectId: string,
    author: string = "Analyst",
    tags: string = ""
  ): Promise<IngestResponse> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("workspace", projectId);
    formData.append("author", author);
    formData.append("tags", tags);

    const response = await apiClient.post<IngestResponse>("/rag/ingest", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      timeout: 300000,
    });
    return response.data;
  },

  async retrieveContext(
    query: string,
    projectId: string,
    limit: number = 5,
    hybridAlpha: number = 0.5
  ): Promise<ContextResponse> {
    const response = await apiClient.post<ContextResponse>("/rag/retrieve", {
      query,
      limit,
      hybrid_alpha: hybridAlpha,
      filters: {
        workspace: projectId,
      },
    });
    return response.data;
  },

  async deleteDocument(docId: string, projectId: string): Promise<void> {
    await apiClient.delete(`/rag/documents/${docId}`, {
      params: { workspace: projectId },
    });
  },

  async reindexDocument(docId: string, projectId: string): Promise<any> {
    const formData = new FormData();
    formData.append("workspace", projectId);
    const response = await apiClient.post(`/rag/reindex/${docId}`, formData, {
      timeout: 300000,
    });
    return response.data;
  },
};
