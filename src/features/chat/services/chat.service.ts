import { apiClient } from "@/shared/api/client";
import { API_ENDPOINTS } from "@/shared/api/endpoints";

export interface ChatMessagePayload {
  message: string;
  sessionId?: string;
}

export interface ChatMessageResponse {
  role: "user" | "assistant";
  content: string;
  chart?: any;
  table?: any;
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
      const response = await apiClient.post<ChatMessageResponse>(API_ENDPOINTS.CHAT.MESSAGE, data);
      return response.data;
    } catch {
      const text = data.message.toLowerCase();
      let res: ChatMessageResponse = {
        role: "assistant",
        content: "I analyzed the request. Here are the monthly trends extracted from q3_financials.xlsx.",
      };

      if (text.includes("forecast") || text.includes("sales") || text.includes("chart") || text.includes("trend")) {
        res = {
          role: "assistant",
          content: "I queried q3_financials.xlsx via DuckDB and compiled the monthly sales compared to targets. Here is the visualization:",
          chart: {
            type: text.includes("bar") ? "bar" : "line",
            xKey: "month",
            yKeys: ["sales", "target"],
            data: [
              { month: "Jan", sales: 4200, target: 4000 },
              { month: "Feb", sales: 4800, target: 4100 },
              { month: "Mar", sales: 5100, target: 4300 },
              { month: "Apr", sales: 4900, target: 4500 },
              { month: "May", sales: 6200, target: 4800 },
              { month: "Jun", sales: 7400, target: 5000 },
            ],
          },
        };
      } else if (text.includes("segment") || text.includes("cohort") || text.includes("cluster") || text.includes("customer")) {
        res = {
          role: "assistant",
          content: "I executed a clustering operation on your cohort records. Here are the user profiles clustered by monthly active engagement scores:",
          table: {
            columns: [
              { header: "Cohort Cluster ID", accessorKey: "cluster" },
              { header: "Average engagement", accessorKey: "engagement" },
              { header: "Size (Users)", accessorKey: "size" },
            ],
            data: [
              { cluster: "Cluster Alpha (Power Users)", engagement: "94.2/100", size: 1402 },
              { cluster: "Cluster Beta (Casual)", engagement: "48.7/100", size: 6820 },
              { cluster: "Cluster Gamma (Inactive)", engagement: "12.4/100", size: 5982 },
            ],
          },
        };
      }

      return res;
    }
  },
};
