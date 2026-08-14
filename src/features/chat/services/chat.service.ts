import { apiClient } from "@/shared/api/client";
import { API_ENDPOINTS } from "@/shared/api/endpoints";

export interface ChatMessagePayload {
  message: string;
  sessionId?: string;
  conversationId?: string;
  workspace?: string;
  workspaceId?: string;
  dataset?: string;
  datasetId?: string;
  selectedDatasetIds?: string[];
  activeProject?: string;
  projectId?: string;
  history?: { role: "user" | "assistant"; content: string }[];
}

export interface ChatMessageResponse {
  role: "user" | "assistant";
  content: string;
  chart?: any;
  table?: any;
  sessionId?: string;
  datasetId?: string;
  datasetName?: string;
  sqlQuery?: string;
  data?: any[];
  columns?: string[];
  rowCount?: number;
}

export const ChatService = {
  async getSessions(): Promise<any[]> {
    try {
      const response = await apiClient.get<any[]>(API_ENDPOINTS.CHAT.SESSION);
      return response.data;
    } catch {
      return [];
    }
  },

  async sendMessage(data: ChatMessagePayload): Promise<ChatMessageResponse> {
    try {
      const activeProj = data.activeProject || data.projectId;
      const payload = {
        message: data.message,
        thread_id: data.sessionId || data.conversationId,
        conversation_id: data.conversationId || data.sessionId,
        workspace: data.workspace,
        workspace_id: data.workspaceId || data.workspace,
        dataset: data.dataset,
        dataset_id: data.datasetId || data.dataset,
        selected_dataset_ids: data.selectedDatasetIds,
        active_project: activeProj,
        project_id: activeProj,
        history: data.history,
      };
      
      if (process.env.NODE_ENV === "development") {
        console.log("[AI Chat API Request]", payload);
      }
      
      const response = await apiClient.post<any>(API_ENDPOINTS.CHAT.MESSAGE, payload);
      
      if (process.env.NODE_ENV === "development") {
        console.log("[AI Chat API Response]", response.data);
      }

      // If backend returns data & columns but no formatted table object, format table for UI
      let tableSpec = response.data.table || null;
      if (!tableSpec && response.data.data && response.data.columns) {
        tableSpec = {
          columns: response.data.columns.map((c: string) => ({ header: c.toUpperCase(), accessorKey: c })),
          data: response.data.data,
        };
      }

      const resContent = response.data.content || response.data.response || "I processed your request, but no response content was returned.";
      
      return {
        role: "assistant",
        content: resContent,
        chart: response.data.chart || null,
        table: tableSpec,
        sessionId: response.data.thread_id,
        datasetId: response.data.dataset_id,
        datasetName: response.data.dataset_name,
        sqlQuery: response.data.sql_query,
        data: response.data.data,
        columns: response.data.columns,
        rowCount: response.data.row_count,
      };
    } catch (err: any) {
      if (process.env.NODE_ENV === "development") {
        console.error("[AI Chat API Error]", err);
      }
      
      // If error detail from backend resolution
      const errDetail = err?.response?.data?.detail;
      if (errDetail && errDetail.startsWith("I couldn't analyze the requested dataset")) {
        return {
          role: "assistant",
          content: errDetail,
        };
      }
      
      throw err;
    }
  },
};
