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
    try {
      const url = projectId ? `/projects/${projectId}/datasets` : API_ENDPOINTS.DATASETS.LIST;
      const response = await apiClient.get<Dataset[]>(url);
      return response.data;
    } catch {
      if (projectId) {
        return mockDatasetsList.filter((d) => (d as any).project_id === projectId);
      }
      return mockDatasetsList;
    }
  },

  async getDetails(id: string): Promise<DatasetDetails> {
    try {
      const response = await apiClient.get<DatasetDetails>(API_ENDPOINTS.DATASETS.DETAIL(id));
      return response.data;
    } catch {
      // Check if we have parsed details cached for this dataset ID
      if (mockDatasetsDetailsCache[id]) {
        return mockDatasetsDetailsCache[id];
      }

      const matched = mockDatasetsList.find((d) => d.id === id);
      const filename = matched ? matched.filename : "q3_financials.xlsx";
      const size = matched ? matched.size : "2.4 MB";
      const rows = matched ? matched.rows : 14020;
      const qualityScore = matched ? matched.qualityScore : 98;
      const type = matched ? matched.type : "Excel";
      
      const cols = type === "CSV" ? 8 : type === "Excel" ? 12 : type === "JSON" ? 6 : 4;
      
      const schema = [
        { name: "id", type: "INTEGER (KEY)", completeness: 100, distinctValues: rows },
        { name: "name", type: "VARCHAR", completeness: 100, distinctValues: Math.min(rows, 1000) },
        { name: "created_at", type: "DATE", completeness: 100, distinctValues: Math.min(rows, 365) },
        { name: "value", type: "DOUBLE", completeness: qualityScore, distinctValues: Math.min(rows, 800) },
      ];

      return {
        id,
        filename,
        size,
        rows,
        cols,
        health: qualityScore,
        missing: Math.round(rows * (1 - qualityScore / 100)),
        duplicates: Math.max(0, Math.round(rows * 0.02)),
        status: "Active",
        schema: type === "CSV" ? [
          { name: "id", type: "INTEGER (KEY)", completeness: 100, distinctValues: rows },
          { name: "customer_name", type: "VARCHAR", completeness: 100, distinctValues: 4200 },
          { name: "transaction_date", type: "DATE", completeness: 100, distinctValues: 180 },
          { name: "amount", type: "DOUBLE", completeness: qualityScore, distinctValues: 1205 },
          { name: "region", type: "VARCHAR", completeness: 100, distinctValues: 4 },
          { name: "status", type: "VARCHAR", completeness: 100, distinctValues: 3 },
        ] : schema,
        preview: type === "CSV" ? [
          { id: 101, customer_name: "John Doe", transaction_date: "2026-08-02", amount: 120.5, region: "North", status: "Completed" },
          { id: 102, customer_name: "Jane Smith", transaction_date: "2026-08-02", amount: 450.0, region: "East", status: "Completed" },
          { id: 103, customer_name: "Acme Corp", transaction_date: "2026-08-01", amount: 8900.0, region: "West", status: "Processing" },
          { id: 104, customer_name: "Bob Johnson", transaction_date: "2026-07-31", amount: 15.2, region: "North", status: "Completed" },
          { id: 105, customer_name: "Alice Brown", transaction_date: "2026-07-30", amount: 320.0, region: "South", status: "Refunded" },
        ] : [
          { id: 101, name: "Sample record 1", created_at: "2026-08-02", value: 120.5, status: "Active" },
          { id: 102, name: "Sample record 2", created_at: "2026-08-02", value: 450.0, status: "Active" },
          { id: 103, name: "Sample record 3", created_at: "2026-08-01", value: 8900.0, status: "Processing" },
          { id: 104, name: "Sample record 4", created_at: "2026-07-31", value: 15.2, status: "Active" },
          { id: 105, name: "Sample record 5", created_at: "2026-07-30", value: 320.0, status: "Failed" },
        ],
      };
    }
  },

  async upload(
    file: File,
    tableName: string,
    projectId?: string,
    onUploadProgress?: (progressEvent: any) => void
  ): Promise<Dataset> {
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("tableName", tableName);

      const url = projectId ? `/projects/${projectId}/datasets` : API_ENDPOINTS.DATASETS.UPLOAD;

      const response = await apiClient.post<Dataset>(url, formData, {
        onUploadProgress,
      });
      return response.data;
    } catch (error) {
      console.warn("Upload API failed, falling back to client-side parsing:", error);
      
      let parsedHeaders: string[] = ["id", "name", "value"];
      let parsedRows: any[] = [];
      let rowCount = 0;
      let colCount = 3;

      try {
        if (file.name.endsWith(".csv")) {
          const text = await file.text();
          const lines = text.split(/\r?\n/).map((l) => l.trim()).filter((l) => l.length > 0);
          if (lines.length > 0) {
            parsedHeaders = splitCSVLine(lines[0]);
            colCount = parsedHeaders.length;
            rowCount = lines.length - 1;

            const previewLines = lines.slice(1, 6);
            parsedRows = previewLines.map((line, rIdx) => {
              const values = splitCSVLine(line);
              const rowObj: any = {};
              parsedHeaders.forEach((header, cIdx) => {
                const val = values[cIdx] !== undefined ? values[cIdx] : "";
                if (val !== "" && !isNaN(Number(val))) {
                  rowObj[header] = Number(val);
                } else {
                  rowObj[header] = val;
                }
              });
              if (rowObj["id"] === undefined) {
                rowObj["id"] = 101 + rIdx;
              }
              return rowObj;
            });
          }
        } else if (file.name.endsWith(".json")) {
          const text = await file.text();
          const jsonData = JSON.parse(text);
          const dataArray = Array.isArray(jsonData) ? jsonData : [jsonData];
          if (dataArray.length > 0) {
            parsedHeaders = Object.keys(dataArray[0]);
            colCount = parsedHeaders.length;
            rowCount = dataArray.length;
            parsedRows = dataArray.slice(0, 5);
          }
        }
      } catch (err) {
        console.error("Client-side fallback file parse error:", err);
      }

      const mockId = Math.random().toString(36).substring(2, 9);
      const qualityScore = Math.floor(Math.random() * 10) + 90;

      const newMockDetails: DatasetDetails = {
        id: mockId,
        filename: file.name,
        size: file.size < 1024 * 1024 
          ? `${Math.round(file.size / 1024)} KB` 
          : `${(file.size / (1024 * 1024)).toFixed(1)} MB`,
        rows: rowCount || 100,
        cols: colCount,
        health: qualityScore,
        missing: Math.round((rowCount || 100) * (1 - qualityScore / 100)),
        duplicates: 0,
        status: "Active",
        schema: parsedHeaders.map((header) => {
          let guessedType = "VARCHAR";
          if (parsedRows.length > 0) {
            const val = parsedRows[0][header];
            if (typeof val === "number") {
              guessedType = Number.isInteger(val) ? "INTEGER" : "DOUBLE";
            } else if (val && !isNaN(Date.parse(val)) && val.includes("-")) {
              guessedType = "DATE";
            }
          }
          return {
            name: header,
            type: guessedType,
            completeness: 100,
            distinctValues: Math.min(rowCount || 100, 500),
          };
        }),
        preview: parsedRows.length > 0 ? parsedRows : [
          { id: 101, name: "Sample record 1", value: 100 },
          { id: 102, name: "Sample record 2", value: 200 },
        ],
      };

      mockDatasetsDetailsCache[mockId] = newMockDetails;

      const mockNewItem: Dataset = {
        id: mockId,
        filename: file.name,
        type: file.name.endsWith(".csv") ? "CSV" : file.name.endsWith(".pdf") ? "PDF" : file.name.endsWith(".json") ? "JSON" : "Excel",
        size: newMockDetails.size,
        rows: newMockDetails.rows,
        qualityScore: newMockDetails.health,
        status: "Active",
        date: new Date().toISOString().split("T")[0],
      };

      mockDatasetsList = [mockNewItem, ...mockDatasetsList];
      return mockNewItem;
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
      mockDatasetsList = mockDatasetsList.filter((d) => d.id !== id);
    }
  },
};
