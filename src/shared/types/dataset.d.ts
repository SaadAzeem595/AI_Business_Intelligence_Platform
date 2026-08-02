export interface Dataset {
  id: string;
  filename: string;
  type: "CSV" | "Excel" | "JSON" | "PDF";
  size: string;
  rows: number;
  qualityScore: number;
  status: "Active" | "Processing" | "Failed";
  date: string;
}

export interface SchemaColumn {
  name: string;
  type: string;
  completeness: number;
  distinctValues: number;
}

export interface DatasetDetails {
  id: string;
  filename: string;
  size: string;
  rows: number;
  cols: number;
  health: number;
  missing: number;
  duplicates: number;
  status: Dataset["status"];
  schema: SchemaColumn[];
  preview: Record<string, string | number | boolean>[];
}
