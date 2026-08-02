import { apiClient } from "@/shared/api/client";
import { API_ENDPOINTS } from "@/shared/api/endpoints";
import { Report } from "@/shared/types/reports";

export interface GenerateReportPayload {
  title: string;
  type: Report["type"];
  frequency: Report["frequency"];
  recipient: string;
}

export const ReportService = {
  async getList(): Promise<Report[]> {
    try {
      const response = await apiClient.get<Report[]>(API_ENDPOINTS.REPORTS.LIST);
      return response.data;
    } catch {
      return [
        { id: "1", title: "Q3 Sales Projections & Outliers Report", type: "PDF", frequency: "Weekly", created: "2026-08-02", size: "1.4 MB", recipient: "board@acme.com" },
        { id: "2", title: "Customer Clustering & Cohort Profile Review", type: "PowerPoint", frequency: "Ad-hoc", created: "2026-07-28", size: "4.2 MB", recipient: "saad@example.com" },
        { id: "3", title: "System Anomalies Log Summary", type: "PDF", frequency: "Daily", created: "2026-08-01", size: "320 KB", recipient: "ops@acme.com" },
      ];
    }
  },

  async generate(data: GenerateReportPayload): Promise<Report> {
    try {
      const response = await apiClient.post<Report>(API_ENDPOINTS.REPORTS.GENERATE, data);
      return response.data;
    } catch {
      return {
        id: "mock-new-report-id",
        title: data.title,
        type: data.type,
        frequency: data.frequency,
        created: new Date().toISOString().split("T")[0],
        size: "950 KB",
        recipient: data.recipient,
      };
    }
  },

  async delete(id: string): Promise<void> {
    try {
      await apiClient.delete(API_ENDPOINTS.REPORTS.DELETE(id));
    } catch {
      // Mock passes silently
    }
  },
};
