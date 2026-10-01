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

  async download(
    id: string,
    title: string,
    format?: string,
    mode: "download" | "preview" = "download"
  ): Promise<void> {
    const targetFormat = (format || "pdf").toLowerCase();
    const endpoint = API_ENDPOINTS.REPORTS.DOWNLOAD(id, targetFormat);

    // Authenticated request via apiClient attaching Bearer token automatically
    const response = await apiClient.get(endpoint, {
      responseType: "blob",
    });

    const mimeType =
      targetFormat === "pptx"
        ? "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        : targetFormat === "html"
        ? "text/html"
        : "application/pdf";

    const contentTypeHeader = response.headers ? response.headers["content-type"] : undefined;
    const blob = new Blob([response.data], {
      type: typeof contentTypeHeader === "string" ? contentTypeHeader : mimeType,
    });
    const blobUrl = URL.createObjectURL(blob);

    if (mode === "preview" && (targetFormat === "pdf" || targetFormat === "html")) {
      const newTab = window.open(blobUrl, "_blank");
      if (!newTab) {
        // Pop-up blocker fallback: download directly
        const link = document.createElement("a");
        link.href = blobUrl;
        link.download = `${title.replace(/\s+/g, "_")}.${targetFormat}`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      }
      setTimeout(() => URL.revokeObjectURL(blobUrl), 120000);
    } else {
      const link = document.createElement("a");
      link.href = blobUrl;
      link.download = `${title.replace(/\s+/g, "_")}.${targetFormat}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      setTimeout(() => URL.revokeObjectURL(blobUrl), 30000);
    }
  },

  async preview(id: string, title: string, format: string = "pdf"): Promise<void> {
    return this.download(id, title, format, "preview");
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
