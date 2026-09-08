export interface ReportKPICard {
  title: string;
  current_value: string;
  previous_value?: string;
  change_pct?: string;
  change_abs?: string;
  direction: "up" | "down" | "flat";
  status: "positive" | "negative" | "neutral";
  source: string;
  source_id: string;
}

export interface ReportKeyInsight {
  id: string;
  title: string;
  description: string;
  severity: "High" | "Medium" | "Low";
  business_relevance: string;
  supporting_metric: string;
  source: string;
  source_id: string;
}

export interface ReportAnomaly {
  id: string;
  metric: string;
  affected_date: string;
  severity: "High" | "Medium" | "Low";
  deviation: string;
  baseline: string;
  business_impact: string;
  source: string;
  source_id: string;
}

export interface ReportForecastPoint {
  date: string;
  actual?: number;
  forecast?: number;
  lower?: number;
  upper?: number;
}

export interface ReportForecastSection {
  horizon: string;
  model_used: string;
  historical_performance: string;
  trend_direction: string;
  points: ReportForecastPoint[];
  metrics: Record<string, any>;
  source: string;
  source_id: string;
}

export interface ReportSegmentItem {
  name: string;
  size: number;
  size_pct: string;
  avg_spent: string;
  risk_rating: string;
  status: string;
  meaningful_changes: string;
  source: string;
  source_id: string;
}

export interface ReportBusinessImpact {
  id: string;
  issue: string;
  affected_area: string;
  magnitude: string;
  severity: "High" | "Medium" | "Low";
  supporting_evidence: string;
  source_id: string;
}

export interface ReportRecommendation {
  id: string;
  recommendation: string;
  reason: string;
  priority: "High" | "Medium" | "Low";
  expected_impact: string;
  suggested_owner: string;
  supporting_evidence: string;
  source_id: string;
}

export interface ReportEvidenceItem {
  source_id: string;
  category: string;
  claim: string;
  source_name: string;
  details: string;
}

export interface ReportMetadata {
  report_id: string;
  title: string;
  project_name: string;
  project_id?: string;
  reporting_period: string;
  generated_at: string;
  author: string;
  recipient: string;
  confidence_score: number;
  sources_included: string[];
}

export interface ExecutiveReportData {
  metadata: ReportMetadata;
  executive_summary: string[];
  kpi_overview: ReportKPICard[];
  key_insights: ReportKeyInsight[];
  trends_chart: {
    title: string;
    labels: string[];
    values: number[];
    type: string;
    color: string;
  };
  anomalies: ReportAnomaly[];
  forecast?: ReportForecastSection;
  segmentation: ReportSegmentItem[];
  business_impact: ReportBusinessImpact[];
  recommendations: ReportRecommendation[];
  evidence: ReportEvidenceItem[];
}

export interface Report {
  id: string;
  title: string;
  type: "PDF" | "PowerPoint" | "HTML" | "CSV";
  frequency: "Daily" | "Weekly" | "Monthly" | "Ad-hoc";
  created: string;
  size: string;
  recipient: string;
  workspace?: string;
  project_id?: string;
  template?: string;
  reporting_period?: string;
  data_sources?: string;
  options?: string;
  delivery_status: "Delivered" | "Pending" | "Failed" | "Delivery Pending";
  delivery_error?: string;
  file_path?: string;
  report_data?: ExecutiveReportData;
}

export interface GenerateReportPayload {
  title: string;
  type: "PDF" | "PowerPoint" | "HTML";
  frequency: "Daily" | "Weekly" | "Monthly" | "Ad-hoc";
  workspace?: string;
  project_id?: string;
  template?: string;
  reporting_period: string;
  custom_date_range?: { startDate: string; endDate: string };
  data_sources: string[];
  options: string[];
  recipient: string;
  preview_only?: boolean;
}

export interface ReportFilterParams {
  project_id?: string;
  report_type?: string;
  format?: string;
  status?: string;
  search?: string;
  page?: number;
  page_size?: number;
}

export interface Invoice {
  invoiceId: string;
  amount: string;
  date: string;
  status: "Paid" | "Pending";
}

export interface NotificationLog {
  id: string;
  title: string;
  description: string;
  date: string;
  read: boolean;
}
