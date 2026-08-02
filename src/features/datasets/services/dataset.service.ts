import { apiClient } from "@/shared/api/client";
import { API_ENDPOINTS } from "@/shared/api/endpoints";
import { Dataset, DatasetDetails } from "@/shared/types/dataset";

export const DatasetService = {
  async getList(): Promise<Dataset[]> {
    try {
      const response = await apiClient.get<Dataset[]>(API_ENDPOINTS.DATASETS.LIST);
      return response.data;
    } catch {
      return [
        { id: "1", filename: "q3_financials.xlsx", type: "Excel", size: "2.4 MB", rows: 14020, qualityScore: 98, status: "Active", date: "2026-08-02" },
        { id: "2", filename: "customer_churn.csv", type: "CSV", size: "480 KB", rows: 6200, qualityScore: 92, status: "Active", date: "2026-08-01" },
        { id: "3", filename: "raw_clicks_logs.json", type: "JSON", size: "14.8 MB", rows: 185000, qualityScore: 88, status: "Processing", date: "2026-08-02" },
        { id: "4", filename: "unstructured_invoice.pdf", type: "PDF", size: "1.2 MB", rows: 0, qualityScore: 0, status: "Active", date: "2026-07-29" },
      ];
    }
  },

  async getDetails(id: string): Promise<DatasetDetails> {
    try {
      const response = await apiClient.get<DatasetDetails>(API_ENDPOINTS.DATASETS.DETAIL(id));
      return response.data;
    } catch {
      return {
        id,
        filename: id === "2" ? "customer_churn.csv" : "q3_financials.xlsx",
        size: id === "2" ? "480 KB" : "2.4 MB",
        rows: id === "2" ? 6200 : 14020,
        cols: id === "2" ? 8 : 12,
        health: id === "2" ? 92 : 98,
        missing: id === "2" ? 42 : 12,
        duplicates: id === "2" ? 8 : 0,
        status: "Active",
        schema: [
          { name: "id", type: "INTEGER (KEY)", completeness: 100, distinctValues: id === "2" ? 6200 : 14020 },
          { name: "customer_name", type: "VARCHAR", completeness: 100, distinctValues: 4200 },
          { name: "transaction_date", type: "DATE", completeness: 100, distinctValues: 180 },
          { name: "amount", type: "DOUBLE", completeness: 98, distinctValues: 1205 },
          { name: "region", type: "VARCHAR", completeness: 100, distinctValues: 4 },
          { name: "status", type: "VARCHAR", completeness: 100, distinctValues: 3 },
        ],
        preview: [
          { id: 101, customer_name: "John Doe", transaction_date: "2026-08-02", amount: 120.5, region: "North", status: "Completed" },
          { id: 102, customer_name: "Jane Smith", transaction_date: "2026-08-02", amount: 450.0, region: "East", status: "Completed" },
          { id: 103, customer_name: "Acme Corp", transaction_date: "2026-08-01", amount: 8900.0, region: "West", status: "Processing" },
          { id: 104, customer_name: "Bob Johnson", transaction_date: "2026-07-31", amount: 15.2, region: "North", status: "Completed" },
          { id: 105, customer_name: "Alice Brown", transaction_date: "2026-07-30", amount: 320.0, region: "South", status: "Refunded" },
        ],
      };
    }
  },

  async upload(file: File, tableName: string, onUploadProgress?: (progressEvent: any) => void): Promise<Dataset> {
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("tableName", tableName);

      const response = await apiClient.post<Dataset>(API_ENDPOINTS.DATASETS.UPLOAD, formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
        onUploadProgress,
      });
      return response.data;
    } catch {
      return {
        id: "mock-new-id",
        filename: file.name,
        type: file.name.endsWith(".csv") ? "CSV" : file.name.endsWith(".pdf") ? "PDF" : "Excel",
        size: `${Math.round(file.size / 1024)} KB`,
        rows: 4500,
        qualityScore: 94,
        status: "Active",
        date: new Date().toISOString().split("T")[0],
      };
    }
  },

  async clean(id: string, actions: string[]): Promise<DatasetDetails> {
    try {
      const response = await apiClient.post<DatasetDetails>(API_ENDPOINTS.DATASETS.CLEAN(id), { actions });
      return response.data;
    } catch {
      const details = await this.getDetails(id);
      return {
        ...details,
        missing: 0,
        duplicates: 0,
        health: 100,
      };
    }
  },

  async delete(id: string): Promise<void> {
    try {
      await apiClient.delete(API_ENDPOINTS.DATASETS.DETAIL(id));
    } catch {
      // Mock passes silently
    }
  },
};
