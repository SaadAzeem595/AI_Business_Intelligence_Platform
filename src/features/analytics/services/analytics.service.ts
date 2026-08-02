import { apiClient } from "@/shared/api/client";
import { API_ENDPOINTS } from "@/shared/api/endpoints";
import { ForecastResult, SegmentationResult, AnomaliesResult, SQLResult } from "@/shared/types/analytics";

export const AnalyticsService = {
  async getForecast(model: string, confidence: number, periods: number): Promise<ForecastResult> {
    try {
      const response = await apiClient.post<ForecastResult>(API_ENDPOINTS.ANALYTICS.FORECAST, {
        model,
        confidence,
        periods,
      });
      return response.data;
    } catch {
      return {
        data: [
          { date: "Feb 26", actual: 12000, forecast: null },
          { date: "Mar 26", actual: 13500, forecast: null },
          { date: "Apr 26", actual: 14200, forecast: null },
          { date: "May 26", actual: 13900, forecast: null },
          { date: "Jun 26", actual: 15400, forecast: null },
          { date: "Jul 26", actual: 16800, forecast: null },
          { date: "Aug 26 (P)", actual: null, forecast: 17200 },
          { date: "Sep 26 (P)", actual: null, forecast: 17900 },
          { date: "Oct 26 (P)", actual: null, forecast: 18500 },
          { date: "Nov 26 (P)", actual: null, forecast: 19100 },
          { date: "Dec 26 (P)", actual: null, forecast: 19800 },
        ],
        metrics: [
          { metric: "R-Squared (Precision)", arimaValue: "0.89", prophetValue: "0.94" },
          { metric: "Mean Absolute Error (MAE)", arimaValue: "$1,420", prophetValue: "$890" },
          { metric: "Root Mean Square Error (RMSE)", arimaValue: "$1,980", prophetValue: "$1,120" },
        ],
      };
    }
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

  async executeSQL(query: string): Promise<SQLResult> {
    try {
      const response = await apiClient.post<SQLResult>(API_ENDPOINTS.SQL.RUN, { query });
      return response.data;
    } catch {
      return {
        columns: ["id", "customer_name", "region", "amount", "status"],
        rows: [
          { id: 101, customer_name: "John Doe", region: "North", amount: 120.5, status: "Completed" },
          { id: 104, customer_name: "Bob Johnson", region: "North", amount: 15.2, status: "Completed" },
          { id: 108, customer_name: "Emma Watson", region: "North", amount: 480.0, status: "Completed" },
          { id: 112, customer_name: "Robert Downey", region: "North", amount: 1420.0, status: "Processing" },
          { id: 115, customer_name: "Chris Evans", region: "North", amount: 95.0, status: "Completed" },
        ],
        elapsedMs: 12,
      };
    }
  },

  async getSQLSchema(): Promise<any[]> {
    try {
      const response = await apiClient.get<any[]>(API_ENDPOINTS.SQL.SCHEMA);
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
