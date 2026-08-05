import { apiClient } from "@/shared/api/client";
import { API_ENDPOINTS } from "@/shared/api/endpoints";

export interface ChatMessagePayload {
  message: string;
  sessionId?: string;
  workspace?: string;
  dataset?: string;
  activeProject?: string;
  history?: { role: "user" | "assistant"; content: string }[];
}

export interface ChatMessageResponse {
  role: "user" | "assistant";
  content: string;
  chart?: any;
  table?: any;
  sessionId?: string;
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
      const payload = {
        message: data.message,
        thread_id: data.sessionId,
        workspace: data.workspace,
        dataset: data.dataset,
        active_project: data.activeProject,
        history: data.history,
      };
      
      if (process.env.NODE_ENV === "development") {
        console.log("[AI Chat API Request]", payload);
      }
      
      const response = await apiClient.post<any>(API_ENDPOINTS.CHAT.MESSAGE, payload);
      
      if (process.env.NODE_ENV === "development") {
        console.log("[AI Chat API Response]", response.data);
      }
      
      return {
        role: "assistant",
        content: response.data.response || "I processed your request, but no response content was returned.",
        chart: response.data.chart || null,
        table: response.data.table || null,
        sessionId: response.data.thread_id,
      };
    } catch (err: any) {
      if (process.env.NODE_ENV === "development") {
        console.error("[AI Chat API Error]", err);
      }
      
      // If the error response contains details from backend validation/resolution
      const errDetail = err?.response?.data?.detail;
      if (errDetail && errDetail.startsWith("I couldn't analyze the requested dataset")) {
        return {
          role: "assistant",
          content: errDetail,
        };
      }
      
      // Fallback
      throw err;
    }
  },
};
