import { apiClient } from "@/shared/api/client";
import { API_ENDPOINTS } from "@/shared/api/endpoints";
import { 
  ForecastResult, 
  SegmentationResult, 
  AnomaliesResult, 
  SQLResult,
  ProjectForecastRequest,
  ProjectForecastResponse,
  ProjectSchemaInfoResponse
} from "@/shared/types/analytics";

export const AnalyticsService = {
  async getProjectForecastSchemaInfo(projectId: string): Promise<ProjectSchemaInfoResponse> {
    const response = await apiClient.get<ProjectSchemaInfoResponse>(`/projects/${projectId}/forecast/schema-info`);
    return response.data;
  },

  async runProjectForecast(projectId: string, payload: ProjectForecastRequest): Promise<ProjectForecastResponse> {
    const response = await apiClient.post<ProjectForecastResponse>(`/projects/${projectId}/forecast`, payload);
    return response.data;
  },

  async getForecast(model: string, confidence: number, periods: number): Promise<ForecastResult> {
    const response = await apiClient.post<ForecastResult>(API_ENDPOINTS.ANALYTICS.FORECAST, {
      model,
      confidence,
      periods,
    });
    return response.data;
  },

  async getSegmentation(clusters: number, features: string): Promise<SegmentationResult> {
    try {
      const response = await apiClient.post<SegmentationResult>(API_ENDPOINTS.ANALYTICS.SEGMENT, {
        clusters,
        features,
      });
      return response.data;
    } catch {
      return {
        scatter: [
          { name: "John", x: 85, y: 92, cluster: "Champions" },
          { name: "Sarah", x: 78, y: 88, cluster: "Champions" },
          { name: "Acme LLC", x: 92, y: 95, cluster: "Champions" },
          { name: "David", x: 42, y: 55, cluster: "Loyal" },
          { name: "Emily", x: 38, y: 62, cluster: "Loyal" },
          { name: "Mike", x: 12, y: 22, cluster: "At-Risk" },
          { name: "Jessica", x: 15, y: 18, cluster: "At-Risk" },
        ],
        cohorts: [
          { name: "Champions (High Spend, High Recency)", count: 420, avgSpent: "$4,850", freqScore: "94/100", riskRating: "Low" },
          { name: "Loyal Customers (Average Spend)", count: 1850, avgSpent: "$1,280", freqScore: "62/100", riskRating: "Low" },
          { name: "At-Risk Core (High Spend, Idle)", count: 280, avgSpent: "$3,120", freqScore: "18/100", riskRating: "High" },
          { name: "Snoozing (Low engagement)", count: 3200, avgSpent: "$140", freqScore: "8/100", riskRating: "Medium" },
        ],
      };
    }
  },

  async getAnomalies(sensitivity: number): Promise<AnomaliesResult> {
    try {
      const response = await apiClient.post<AnomaliesResult>(API_ENDPOINTS.ANALYTICS.ANOMALIES, {
        sensitivity,
      });
      return response.data;
    } catch {
      return {
        timeline: [
          { date: "Jul 20", value: 1400, limit: 1800 },
          { date: "Jul 21", value: 1450, limit: 1800 },
          { date: "Jul 22", value: 1390, limit: 1800 },
          { date: "Jul 23", value: 1560, limit: 1800 },
          { date: "Jul 24", value: 1200, limit: 1800 },
          { date: "Jul 25", value: 1480, limit: 1800 },
          { date: "Jul 26", value: 1520, limit: 1800 },
          { date: "Jul 27", value: 1610, limit: 1800 },
          { date: "Jul 28", value: 1580, limit: 1800 },
          { date: "Jul 29", value: 2450, limit: 1800 },
          { date: "Jul 30", value: 1600, limit: 1800 },
        ],
        logs: [
          { id: "A-9204", metric: "Daily API Calls Spike", value: "85,420 calls", deviation: "+3.2 Std Dev", date: "2026-08-02", status: "Unresolved" },
          { id: "A-8902", metric: "Unusual refund volume", value: "$4,850 value", deviation: "+4.1 Std Dev", date: "2026-07-29", status: "Unresolved" },
          { id: "A-7201", metric: "Logins count dip", value: "1,200 count", deviation: "-2.8 Std Dev", date: "2026-07-24", status: "Resolved" },
        ],
      };
    }
  },

  async executeSQL(query: string, projectId?: string): Promise<SQLResult> {
    try {
      const response = await apiClient.post<SQLResult>(API_ENDPOINTS.SQL.RUN, { 
        query, 
        project_id: projectId 
      });
      return response.data;
    } catch (error) {
      console.error("SQL query execution failed:", error);
      throw error;
    }
  },

  async getSQLSchema(projectId?: string): Promise<any[]> {
    try {
      const url = projectId ? `${API_ENDPOINTS.SQL.SCHEMA}?project_id=${projectId}` : API_ENDPOINTS.SQL.SCHEMA;
      const response = await apiClient.get<any[]>(url);
      return response.data;
    } catch {
      return [
        { name: "q3_financials", rowsCount: 14020 },
        { name: "customer_churn", rowsCount: 6200 },
        { name: "raw_clicks_logs", rowsCount: 185000 },
      ];
    }
  },
};
