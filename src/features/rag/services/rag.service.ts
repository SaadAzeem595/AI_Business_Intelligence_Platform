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
}

export interface RetrievalResult {
  chunk_id: string;
  doc_id: string;
  text: string;
  score: number;
  citation: Citation;
}

export interface ContextResponse {
  context_text: string;
  results: RetrievalResult[];
  token_count: number;
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
    const response = await apiClient.post(`/rag/reindex/${docId}`, formData);
    return response.data;
  },
};
