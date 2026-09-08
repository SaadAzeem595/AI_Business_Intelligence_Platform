import { apiClient } from "@/shared/api/client";
import { API_ENDPOINTS } from "@/shared/api/endpoints";
import { Report, GenerateReportPayload, ReportFilterParams } from "@/shared/types/reports";

export const ReportService = {
  async getList(params?: ReportFilterParams): Promise<Report[]> {
    try {
      const response = await apiClient.get<Report[]>(API_ENDPOINTS.REPORTS.LIST, { params });
      return response.data;
    } catch {
      return [
        {
          id: "1",
          title: "Executive Revenue & Variance Quarterly Audit",
          type: "PDF",
          frequency: "Weekly",
          created: new Date().toISOString(),
          size: "1.4 MB",
          recipient: "saad@example.com",
          reporting_period: "Last 30 Days",
          delivery_status: "Delivered",
        },
      ];
    }
  },

  async getById(id: string): Promise<Report> {
    const response = await apiClient.get<Report>(API_ENDPOINTS.REPORTS.DETAIL(id));
    return response.data;
  },

  async generate(data: GenerateReportPayload): Promise<Report> {
    const response = await apiClient.post<Report>(API_ENDPOINTS.REPORTS.GENERATE, data);
    return response.data;
  },

  async regenerateNarrative(id: string, customFocus?: string): Promise<Report> {
    const response = await apiClient.post<Report>(API_ENDPOINTS.REPORTS.REGENERATE(id), {
      report_id: id,
      custom_prompt_focus: customFocus,
    });
    return response.data;
  },

  async sendEmail(id: string, recipient?: string): Promise<void> {
    await apiClient.post(API_ENDPOINTS.REPORTS.EMAIL(id), { recipient });
  },

  async download(id: string, title: string, format?: string): Promise<void> {
    const downloadUrl = `${apiClient.defaults.baseURL || ""}${API_ENDPOINTS.REPORTS.DOWNLOAD(id, format)}`;
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.target = "_blank";
    link.download = `${title.replace(/\s+/g, "_")}.${format?.toLowerCase() || "pdf"}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  },

  async delete(id: string): Promise<void> {
    await apiClient.delete(API_ENDPOINTS.REPORTS.DELETE(id));
  },

  async createSchedule(payload: any): Promise<any> {
    const response = await apiClient.post(API_ENDPOINTS.REPORTS.SCHEDULE, payload);
    return response.data;
  },

  async listSchedules(): Promise<any[]> {
    try {
      const response = await apiClient.get<any[]>(API_ENDPOINTS.REPORTS.SCHEDULES);
      return response.data;
    } catch {
      return [];
    }
  },

  async cancelSchedule(id: string): Promise<void> {
    await apiClient.delete(API_ENDPOINTS.REPORTS.CANCEL_SCHEDULE(id));
  },
};
