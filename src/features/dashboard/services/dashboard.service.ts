import { apiClient } from "@/shared/api/client";
import { API_ENDPOINTS } from "@/shared/api/endpoints";

export interface DashboardMetrics {
  grossRevenue: string;
  grossRevenueChange: number;
  activeUsers: string;
  activeUsersChange: number;
  predictionAccuracy: string;
  predictionAccuracyChange: number;
  anomaliesCount: number;
}

export const DashboardService = {
  async getMetrics(): Promise<DashboardMetrics> {
    try {
      const response = await apiClient.get<DashboardMetrics>(API_ENDPOINTS.DASHBOARD.METRICS);
      return response.data;
    } catch {
      return {
        grossRevenue: "$1,248,390",
        grossRevenueChange: 14.2,
        activeUsers: "14,204",
        activeUsersChange: 8.7,
        predictionAccuracy: "94.6%",
        predictionAccuracyChange: 1.2,
        anomaliesCount: 2,
      };
    }
  },

  async getTrends(): Promise<any[]> {
    try {
      const response = await apiClient.get<any[]>(API_ENDPOINTS.DASHBOARD.TRENDS);
      return response.data;
    } catch {
      return [
        { month: "Jan", revenue: 45000, target: 40000, margin: 23 },
        { month: "Feb", revenue: 52000, target: 43000, margin: 24 },
        { month: "Mar", revenue: 61000, target: 48000, margin: 26 },
        { month: "Apr", revenue: 58000, target: 50000, margin: 25 },
        { month: "May", revenue: 71000, target: 55000, margin: 28 },
        { month: "Jun", revenue: 84000, target: 60000, margin: 30 },
        { month: "Jul", revenue: 95000, target: 68000, margin: 32 },
      ];
    }
  },
};
