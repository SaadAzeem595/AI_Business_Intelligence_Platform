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
  dataset_type?: string;
  is_time_series_capable?: boolean;
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
  riskRating: "Low" | "Medium" | "High" | "Neutral" | "N/A" | string;
}

export interface ClusterEvaluation {
  optimal_k: number;
  selected_k: number;
  silhouette_score: number;
  davies_bouldin_index: number;
  calinski_harabasz_index: number;
  metrics_by_k?: Record<number, { silhouette_score: number; davies_bouldin_index: number; calinski_harabasz_index: number }>;
}

export interface SegmentProfile {
  cluster_id: number;
  name: string;
  size: number;
  percentage: number;
  characteristics: string;
  recommendation: string;
  risk_rating: "Low" | "Medium" | "High" | "Neutral" | "N/A" | string;
  feature_means?: Record<string, number>;
}

export interface SegmentationResult {
  scatter: { x: number; y: number; cluster: string; name: string; details?: Record<string, number> }[];
  cohorts: CohortSegment[];
  evaluation?: ClusterEvaluation;
  profiles?: SegmentProfile[];
  features_used?: string[];
  dataset_type?: string;
  entity_key?: string | null;
  message?: string | null;
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

export interface ProjectAnomalyRequest {
  dataset_id?: string;
  timestamp_column?: string;
  metric_column?: string;
  detection_method?: "zscore" | "iqr" | "iforest" | string;
  sensitivity?: number;
}

export interface AnomalyTimelinePointDetailed {
  timestamp: string;
  value: number;
  upper_limit?: number | null;
  lower_limit?: number | null;
  is_anomaly: boolean;
  anomaly_score: number;
  severity: "High" | "Medium" | "Low" | "None" | string;
}

export interface AnomalyLogDetailed {
  id: string;
  timestamp: string;
  metric: string;
  value: number;
  value_formatted: string;
  score: number;
  deviation: string;
  severity: "High" | "Medium" | "Low" | string;
  status: "Unresolved" | "Resolved";
  explanation: string;
  threshold?: number | null;
}

export interface ProjectAnomalyResponse {
  status: "success" | "warning" | "error";
  project_id?: string;
  dataset_id?: string;
  dataset_name?: string;
  timestamp_column?: string;
  metric_column?: string;
  detection_method: string;
  sensitivity: number;
  total_observations: number;
  anomalies_detected: number;
  anomaly_rate: number;
  highest_severity: "High" | "Medium" | "Low" | "None" | string;
  upper_threshold?: number | null;
  lower_threshold?: number | null;
  timeline: AnomalyTimelinePointDetailed[];
  logs: AnomalyLogDetailed[];
  business_impact: string[];
  recommended_actions: string[];
  message?: string;
}

export interface SQLResult {
  columns: string[];
  rows: Record<string, string | number | boolean>[];
  elapsedMs: number;
}

