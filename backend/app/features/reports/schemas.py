from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, ConfigDict, Field


class ReportKPICard(BaseModel):
    title: str
    current_value: str
    previous_value: Optional[str] = None
    change_pct: Optional[str] = None
    change_abs: Optional[str] = None
    direction: str = "flat"  # up, down, flat
    status: str = "neutral"  # positive, negative, neutral
    source: str = "Dashboard / SQL"
    source_id: str = "SRC-KPI"


class ReportKeyInsight(BaseModel):
    id: str
    title: str
    description: str
    severity: str = "Medium"  # High, Medium, Low
    business_relevance: str
    supporting_metric: str
    source: str
    source_id: str


class ReportAnomalyItem(BaseModel):
    id: str
    metric: str
    affected_date: str
    severity: str = "Medium"
    deviation: str
    baseline: str
    business_impact: str
    source: str = "Anomaly Detection"
    source_id: str = "SRC-ANOM"


class ReportForecastPoint(BaseModel):
    date: str
    actual: Optional[float] = None
    forecast: Optional[float] = None
    lower: Optional[float] = None
    upper: Optional[float] = None


class ReportForecastSection(BaseModel):
    horizon: str = "30 Days"
    model_used: str = "ARIMA"
    historical_performance: str = ""
    trend_direction: str = "Stable"
    points: List[ReportForecastPoint] = []
    metrics: Dict[str, Any] = {}
    source: str = "Forecasting"
    source_id: str = "SRC-FC"


class ReportSegmentItem(BaseModel):
    name: str
    size: int = 0
    size_pct: str = "0%"
    avg_spent: str = "$0"
    risk_rating: str = "Low"
    status: str = "Stable"
    meaningful_changes: str = "No critical variation observed."
    source: str = "Segmentation"
    source_id: str = "SRC-SEG"


class ReportBusinessImpact(BaseModel):
    id: str
    issue: str
    affected_area: str
    magnitude: str
    severity: str = "Medium"
    supporting_evidence: str
    source_id: str = "SRC-IMP"


class ReportRecommendation(BaseModel):
    id: str
    recommendation: str
    reason: str
    priority: str = "Medium"  # High, Medium, Low
    expected_impact: str
    suggested_owner: str
    supporting_evidence: str
    source_id: str = "SRC-REC"


class ModuleExecutionStatus(BaseModel):
    module: str
    status: str  # SUCCESS, UNAVAILABLE, FAILED, SKIPPED
    duration_ms: int = 0
    dataset_ids: List[str] = []
    result_summary: str = ""
    error: Optional[str] = None


class StructuredMetric(BaseModel):
    key: str
    label: str
    value: Any
    unit: Optional[str] = None
    period: Optional[str] = None
    source_module: str
    query_id: Optional[str] = None
    run_id: Optional[str] = None
    dataset_ids: List[str] = []
    source_rows: Optional[int] = None
    confidence: float = 1.0
    generated_at: str = ""


class ReportEvidenceItem(BaseModel):
    source_id: str
    category: str  # Dashboard KPI, SQL Analytics, Forecasting, Segmentation, Anomaly Detection, Knowledge Base
    claim: str
    source_name: str
    details: str


class ReportMetadata(BaseModel):
    report_id: str
    title: str
    project_name: str = "Global Workspace"
    project_id: Optional[str] = None
    reporting_period: str = "Full Dataset Period"
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    dataset_min_date: Optional[str] = None
    dataset_max_date: Optional[str] = None
    generated_at: str
    author: str = "system"
    recipient: str
    confidence_score: float = 0.95
    verification_rate: float = 1.0
    sources_included: List[str] = []
    module_statuses: List[ModuleExecutionStatus] = []


class ExecutiveReportData(BaseModel):
    metadata: ReportMetadata
    executive_summary: List[str] = []
    kpi_overview: List[ReportKPICard] = []
    key_insights: List[ReportKeyInsight] = []
    trends_chart: Dict[str, Any] = {}
    anomalies: List[ReportAnomalyItem] = []
    forecast: Optional[ReportForecastSection] = None
    segmentation: List[ReportSegmentItem] = []
    business_impact: List[ReportBusinessImpact] = []
    recommendations: List[ReportRecommendation] = []
    evidence: List[ReportEvidenceItem] = []
    module_statuses: List[ModuleExecutionStatus] = []
    structured_metrics: List[StructuredMetric] = []
    verification_rate: float = 1.0
    delivery_confidence: float = 0.95


class GenerateReportPayload(BaseModel):
    title: str = "Executive Intelligence & Performance Report"
    type: str = "PDF"  # PDF, PowerPoint, HTML
    frequency: str = "Ad-hoc"  # Daily, Weekly, Monthly, Ad-hoc
    workspace: str = "default"
    project_id: Optional[str] = None
    template: str = "Executive Summary"  # Executive Summary, Sales Performance, Customer Analytics, Financial Performance, Operations, Risk & Anomaly, Custom
    reporting_period: str = "Full Dataset Period"  # Full Dataset Period, Last 7 Days, Last 30 Days, Last 90 Days, Last 12 Months, Current Quarter, Previous Quarter, Custom Range
    custom_date_range: Optional[Dict[str, str]] = None  # { startDate, endDate }
    data_sources: List[str] = Field(default_factory=lambda: ["dashboard", "sql", "forecasting", "segmentation", "anomaly", "rag"])
    options: List[str] = Field(default_factory=lambda: ["kpis", "charts", "summary", "insights", "impact", "recommendations", "evidence"])
    recipient: EmailStr = "saad@example.com"
    preview_only: bool = False


class RegenerateNarrativePayload(BaseModel):
    report_id: str
    custom_prompt_focus: Optional[str] = None


class EmailReportPayload(BaseModel):
    recipient: Optional[EmailStr] = None


class ReportResponse(BaseModel):
    id: str
    title: str
    type: str
    frequency: str
    template: str
    created: str
    size: str
    recipient: EmailStr
    workspace: str
    project_id: Optional[str] = None
    author: str
    reporting_period: Optional[str] = "Full Dataset Period"
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    data_sources: Optional[str] = None
    options: Optional[str] = None
    datasets_used: Optional[str] = None
    delivery_status: str
    delivery_error: Optional[str] = None
    file_path: Optional[str] = None
    verification_rate: Optional[float] = 1.0
    delivery_confidence: Optional[float] = 0.95
    module_statuses: Optional[List[ModuleExecutionStatus]] = []
    report_data: Optional[ExecutiveReportData] = None

    model_config = ConfigDict(from_attributes=True)


class ReportSchedulePayload(BaseModel):
    title: str
    workspace: str = "default"
    project_id: Optional[str] = None
    report_type: str = "PDF"  # PDF, PowerPoint, HTML
    frequency: str = "Weekly"  # Daily, Weekly, Monthly, Quarterly
    template: str = "Executive Summary"
    reporting_period: str = "Last 30 Days"
    data_sources: Optional[List[str]] = Field(default_factory=lambda: ["dashboard", "sql", "forecasting", "segmentation", "anomaly", "rag"])
    options: Optional[List[str]] = Field(default_factory=lambda: ["kpis", "charts", "summary", "insights", "impact", "recommendations", "evidence"])
    recipient: EmailStr


class ReportScheduleResponse(BaseModel):
    id: str
    title: str
    workspace: str
    project_id: Optional[str] = None
    report_type: str
    frequency: str
    template: str
    reporting_period: Optional[str] = "Last 30 Days"
    data_sources: Optional[str] = None
    options: Optional[str] = None
    recipient: EmailStr
    author: str
    is_active: bool
    created_at: str

    model_config = ConfigDict(from_attributes=True)
