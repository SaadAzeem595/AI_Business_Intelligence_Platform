export interface ForecastPoint {
  date: string;
  actual: number | null;
  forecast: number | null;
}

export interface ForecastResult {
  data: ForecastPoint[];
  metrics: {
    metric: string;
    arimaValue: string;
    prophetValue: string;
  }[];
}

export interface CohortSegment {
  name: string;
  count: number;
  avgSpent: string;
  freqScore: string;
  riskRating: "Low" | "Medium" | "High";
}

export interface SegmentationResult {
  scatter: { x: number; y: number; cluster: string; name: string }[];
  cohorts: CohortSegment[];
}

export interface AnomalyLog {
  id: string;
  metric: string;
  value: string;
  deviation: string;
  date: string;
  status: "Unresolved" | "Resolved";
}

export interface AnomaliesResult {
  timeline: { date: string; value: number; limit: number }[];
  logs: AnomalyLog[];
}

export interface SQLResult {
  columns: string[];
  rows: Record<string, string | number | boolean>[];
  elapsedMs: number;
}
