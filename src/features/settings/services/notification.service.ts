import { apiClient } from "@/shared/api/client";
import { NotificationLog } from "@/shared/types/reports";

export const NotificationService = {
  async getNotifications(): Promise<NotificationLog[]> {
    try {
      const response = await apiClient.get<NotificationLog[]>("/settings/notifications");
      return response.data;
    } catch {
      return [
        { id: "1", title: "Dataset uploaded successfully", description: "Your file `q3_financials.xlsx` was processed.", date: "5m ago", read: false },
        { id: "2", title: "AI Analysis Complete", description: "Anomaly checks flagged 2 outliers.", date: "1h ago", read: false },
      ];
    }
  },

  async markAllRead(): Promise<void> {
    try {
      await apiClient.post("/settings/notifications/mark-read");
    } catch {
      // Mock passes silently
    }
  },
};
