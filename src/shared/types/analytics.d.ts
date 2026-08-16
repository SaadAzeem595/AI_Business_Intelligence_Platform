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

export interface TimeSeriesCandidate {
  dataset_id: string;
  dataset_name: string;
  date_columns: string[];
  metric_columns: string[];
  categorical_columns: string[];
  is_derived_olist: boolean;
  suggested_date?: string;
  suggested_metric?: string;
}

export interface ProjectSchemaInfoResponse {
  has_time_series: boolean;
  candidates: TimeSeriesCandidate[];
  message?: string;
}

export interface TimelinePointDetailed {
  date: string;
  actual: number | null;
  forecast: number | null;
  lower: number | null;
  upper: number | null;
}

export interface ForecastModelMetrics {
  model_name: string;
  mae: number;
  rmse: number;
  mape: number;
  r_squared?: number;
  is_best: boolean;
}

export interface ForecastBusinessSummary {
  current_trend: string; // "Upward" | "Downward" | "Stable"
  forecasted_total: number;
  historical_total: number;
  growth_percentage: number;
  horizon_label: string;
  best_period: string;
  worst_period: string;
  confidence_level: number;
  headline: string;
}

export interface CategoryForecast {
  category: string;
  historical_sum: number;
  forecast_sum: number;
  growth_percentage: number;
  trend: string;
}

export interface ProjectForecastResponse {
  status: "success" | "warning" | "error";
  project_id?: string;
  dataset_id?: string;
  dataset_name?: string;
  date_column?: string;
  target_column?: string;
  aggregation: string;
  horizon: number;
  selected_model: string;
  timeline: TimelinePointDetailed[];
  metrics: ForecastModelMetrics[];
  business_summary?: ForecastBusinessSummary;
  insights: string[];
  recommendations: string[];
  category_forecasts: CategoryForecast[];
  diagnostics: Record<string, any>;
  message?: string;
}

export interface ProjectForecastRequest {
  dataset_id?: string;
  date_column?: string;
  target_column?: string;
  aggregation?: string;
  horizon?: number;
  group_by?: string;
  model?: string;
  confidence?: number;
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
