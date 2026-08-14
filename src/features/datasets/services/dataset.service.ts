import { apiClient } from "@/shared/api/client";
import { API_ENDPOINTS } from "@/shared/api/endpoints";
import { Dataset, DatasetDetails } from "@/shared/types/dataset";

// Stateful mock list for fallback when backend API is offline
let mockDatasetsList: Dataset[] = [
  { id: "1", filename: "q3_financials.xlsx", type: "Excel", size: "2.4 MB", rows: 14020, qualityScore: 98, status: "Active", date: "2026-08-02" },
  { id: "2", filename: "customer_churn.csv", type: "CSV", size: "480 KB", rows: 6200, qualityScore: 92, status: "Active", date: "2026-08-01" },
  { id: "3", filename: "raw_clicks_logs.json", type: "JSON", size: "14.8 MB", rows: 185000, qualityScore: 88, status: "Processing", date: "2026-08-02" },
  { id: "4", filename: "unstructured_invoice.pdf", type: "PDF", size: "1.2 MB", rows: 0, qualityScore: 0, status: "Active", date: "2026-07-29" },
];

// Stateful cache for parsed dataset details in mock fallback mode
const mockDatasetsDetailsCache: Record<string, DatasetDetails> = {};

// Helper to split a CSV line while respecting quoted commas
const splitCSVLine = (line: string): string[] => {
  const result: string[] = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (char === '"' || char === "'") {
      inQuotes = !inQuotes;
    } else if (char === ',' && !inQuotes) {
      result.push(current.trim());
      current = "";
    } else {
      current += char;
    }
  }
  result.push(current.trim());
  return result;
};

export const DatasetService = {
  async getList(projectId?: string): Promise<Dataset[]> {
    const url = projectId ? `/projects/${projectId}/datasets` : API_ENDPOINTS.DATASETS.LIST;
    const response = await apiClient.get<Dataset[]>(url);
    return response.data;
  },

  async getDetails(id: string): Promise<DatasetDetails> {
    const response = await apiClient.get<DatasetDetails>(API_ENDPOINTS.DATASETS.DETAIL(id));
    return response.data;
  },

  async upload(
    file: File,
    tableName: string,
    projectId?: string,
    onUploadProgress?: (progressEvent: any) => void
  ): Promise<Dataset> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("tableName", tableName);

    const url = projectId ? `/projects/${projectId}/datasets` : API_ENDPOINTS.DATASETS.UPLOAD;

    const response = await apiClient.post<Dataset>(url, formData, {
      onUploadProgress,
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
    return response.data;
  },

  async clean(id: string, actions: string[]): Promise<DatasetDetails> {
    const response = await apiClient.post<DatasetDetails>(API_ENDPOINTS.DATASETS.CLEAN(id), { actions });
    return response.data;
  },

  async delete(id: string): Promise<void> {
    await apiClient.delete(API_ENDPOINTS.DATASETS.DETAIL(id));
  },
};
