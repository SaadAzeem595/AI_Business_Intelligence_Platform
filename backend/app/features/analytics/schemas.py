from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ForecastPayload(BaseModel):
    model: str = Field(..., description="Name of the forecast model/column to predict", examples=["revenue", "sales"])
    confidence: float = Field(0.95, description="Confidence interval target threshold", examples=[0.95, 0.80])
    periods: int = Field(12, description="Number of future intervals to forecast", examples=[12, 24])


class ForecastPoint(BaseModel):
    date: str
    actual: Optional[float] = None
    forecast: Optional[float] = None


class ForecastMetric(BaseModel):
    metric: str
    arimaValue: str
    prophetValue: str


class ForecastResponse(BaseModel):
    data: List[ForecastPoint]
    metrics: List[ForecastMetric]


class SegmentPayload(BaseModel):
    clusters: Optional[int] = Field(3, description="Number of clusters (k)")
    features: Optional[str] = Field(None, description="Comma-separated feature list or None for auto-selection")
    dataset_id: Optional[str] = Field(None, description="ID of dataset to segment")
    project_id: Optional[str] = Field(None, description="Scope segmentation to project")
    mode: Optional[str] = Field("auto", description="Segmentation mode: 'auto', 'rfm', or 'numerical'")
    entity_key: Optional[str] = Field(None, description="Explicit entity/customer key column")


class CohortSegment(BaseModel):
    name: str
    count: int
    avgSpent: str
    freqScore: str
    riskRating: str


class ScatterPoint(BaseModel):
    name: str
    x: float
    y: float
    cluster: str
    details: Optional[Dict[str, Any]] = None


class ClusterEvaluation(BaseModel):
    optimal_k: int
    selected_k: int
    silhouette_score: float
    davies_bouldin_index: float
    calinski_harabasz_index: float
    metrics_by_k: Dict[int, Dict[str, float]] = {}


class SegmentProfile(BaseModel):
    cluster_id: int
    name: str
    size: int
    percentage: float
    characteristics: str
    recommendation: str
    risk_rating: str
    feature_means: Dict[str, float] = {}


class SegmentResponse(BaseModel):
    scatter: List[ScatterPoint]
    cohorts: List[CohortSegment]
    evaluation: Optional[ClusterEvaluation] = None
    profiles: List[SegmentProfile] = []
    features_used: List[str] = []
    dataset_type: str = "tabular"
    entity_key: Optional[str] = None
    message: Optional[str] = None


class SegmentationCandidate(BaseModel):
    dataset_id: str
    dataset_name: str
    filename: Optional[str] = None
    eligible: bool = True
    row_count: int = 0
    column_count: int = 0
    entity_key: Optional[str] = None
    available_entity_keys: List[str] = []
    numerical_features: List[str] = []
    categorical_features: List[str] = []
    usable_features: List[str] = []
    excluded_features: List[str] = []
    suggested_features: List[str] = []
    suggested_mode: str = "auto"
    is_rfm_capable: bool = False
    is_derived: bool = False
    dataset_type: str = "tabular"
    reason: Optional[str] = None


class ProjectSegmentSchemaResponse(BaseModel):
    project_id: str
    dataset_count: int
    eligible_count: int
    candidates: List[SegmentationCandidate] = []
    message: Optional[str] = None


class AnomalyPayload(BaseModel):
    sensitivity: float


class TimelinePoint(BaseModel):
    date: str
    value: float
    limit: float


class AnomalyLog(BaseModel):
    id: str
    metric: str
    value: str
    deviation: str
    date: str
    status: str


class AnomalyResponse(BaseModel):
    timeline: List[TimelinePoint]
    logs: List[AnomalyLog]


# Production Anomaly Detection Schemas
class ProjectAnomalyRequest(BaseModel):
    dataset_id: Optional[str] = Field(None, description="ID of specific dataset to inspect, or auto-detect")
    timestamp_column: Optional[str] = Field(None, description="Timestamp/date column name")
    metric_column: Optional[str] = Field(None, description="Numeric metric column name")
    detection_method: str = Field("zscore", description="Anomaly detection algorithm: 'zscore', 'iqr', 'iforest'")
    sensitivity: float = Field(0.05, description="Sensitivity threshold or contamination factor (0.01 - 0.20)")


class AnomalyTimelinePointDetailed(BaseModel):
    timestamp: str
    value: float
    upper_limit: Optional[float] = None
    lower_limit: Optional[float] = None
    is_anomaly: bool = False
    anomaly_score: float = 0.0
    severity: str = "None"


class AnomalyLogDetailed(BaseModel):
    id: str
    timestamp: str
    metric: str
    value: float
    value_formatted: str
    score: float
    deviation: str
    severity: str
    status: str = "Unresolved"
    explanation: str
    threshold: Optional[float] = None
    threshold_formatted: Optional[str] = None
    expected_value: Optional[float] = None
    expected_value_formatted: Optional[str] = None
    deviation_pct: Optional[float] = None


class ProjectAnomalyResponse(BaseModel):
    status: str = Field("success", description="'success' or 'error'")
    project_id: Optional[str] = None
    dataset_id: Optional[str] = None
    dataset_name: Optional[str] = None
    timestamp_column: Optional[str] = None
    metric_column: Optional[str] = None
    detection_method: str = "zscore"
    sensitivity: float = 0.05
    total_observations: int = 0
    anomalies_detected: int = 0
    anomaly_rate: float = 0.0
    highest_severity: str = "None"
    upper_threshold: Optional[float] = None
    lower_threshold: Optional[float] = None
    min_observed: Optional[float] = None
    max_observed: Optional[float] = None
    mean_observed: Optional[float] = None
    std_observed: Optional[float] = None
    sensitivity_explanation: Optional[str] = None
    timeline: List[AnomalyTimelinePointDetailed] = []
    logs: List[AnomalyLogDetailed] = []
    business_impact: List[str] = []
    recommended_actions: List[str] = []
    message: Optional[str] = None




class SQLPayload(BaseModel):
    query: str = Field(..., description="The read-only SQL query statement to execute against DuckDB", examples=["SELECT region, SUM(revenue) FROM active_dataset GROUP BY region"])
    project_id: Optional[str] = Field(None, description="Scope the query context to a specific project workspace")


class SQLResponse(BaseModel):
    columns: List[str] = Field(..., description="List of columns returned by the query", examples=[["region", "SUM(revenue)"]])
    rows: List[Dict[str, Any]] = Field(..., description="List of rows represented as key-value dictionaries", examples=[[{"region": "North", "SUM(revenue)": 450000.0}]])
    elapsedMs: int = Field(..., description="Query execution duration in milliseconds", examples=[12])


# ==========================================
# Production-Grade Time Series Forecasting Schemas
# ==========================================

class DateDetectionMetadata(BaseModel):
    model_config = {"extra": "ignore"}
    column: Optional[str] = None
    source_column: Optional[str] = None
    type: str = "datetime"
    detected_type: Optional[str] = "datetime"
    format: Optional[str] = None
    detected_format: Optional[str] = None
    confidence: float = 1.0
    valid_count: int = 0
    invalid_count: int = 0
    parse_success_rate: float = 1.0
    min: Optional[str] = None
    max: Optional[str] = None
    min_timestamp: Optional[str] = None
    max_timestamp: Optional[str] = None
    is_ambiguous: bool = False
    ambiguous: bool = False
    candidate_formats: List[str] = []
    warnings: List[str] = []

    def __init__(self, **data: Any):
        if "column" not in data and "source_column" in data:
            data["column"] = data["source_column"]
        elif "source_column" not in data and "column" in data:
            data["source_column"] = data["column"]

        if "format" not in data and "detected_format" in data:
            data["format"] = data["detected_format"]
        elif "detected_format" not in data and "format" in data:
            data["detected_format"] = data["format"]

        if "type" not in data and "detected_type" in data:
            data["type"] = data["detected_type"]
        elif "detected_type" not in data and "type" in data:
            data["detected_type"] = data["type"]

        if "min" not in data and "min_timestamp" in data:
            data["min"] = data["min_timestamp"]
        elif "min_timestamp" not in data and "min" in data:
            data["min_timestamp"] = data["min"]

        if "max" not in data and "max_timestamp" in data:
            data["max"] = data["max_timestamp"]
        elif "max_timestamp" not in data and "max" in data:
            data["max_timestamp"] = data["max"]

        if "ambiguous" not in data and "is_ambiguous" in data:
            data["ambiguous"] = data["is_ambiguous"]
        elif "is_ambiguous" not in data and "ambiguous" in data:
            data["is_ambiguous"] = data["ambiguous"]

        super().__init__(**data)


class ProjectForecastRequest(BaseModel):
    dataset_id: Optional[str] = Field(None, description="ID of specific dataset to forecast, or auto-detect if None")
    date_column: Optional[str] = Field(None, description="Date/timestamp column name")
    target_column: Optional[str] = Field(None, description="Numeric metric column name to forecast")
    aggregation: str = Field("monthly", description="Time series bucket: 'daily', 'weekly', 'monthly'")
    horizon: int = Field(6, description="Forecast horizon steps ahead")
    group_by: Optional[str] = Field(None, description="Optional column to group/breakdown forecast by (e.g. category)")
    model: str = Field("auto", description="Forecasting model choice: 'auto', 'arima', 'prophet', 'naive'")
    confidence: float = Field(0.95, description="Confidence level (0.80 - 0.99)")
    user_date_format: Optional[str] = Field(None, description="Optional user-selected date format override (e.g. 'DD/MM/YYYY')")


class TimelinePointDetailed(BaseModel):
    date: str
    actual: Optional[float] = None
    forecast: Optional[float] = None
    lower: Optional[float] = None
    upper: Optional[float] = None


class ForecastModelMetrics(BaseModel):
    model_name: str
    mae: float
    rmse: float
    mape: float
    r_squared: Optional[float] = None
    is_best: bool = False


class ForecastBusinessSummary(BaseModel):
    current_trend: str  # "Upward" | "Downward" | "Stable"
    forecasted_total: float
    historical_total: float
    growth_percentage: float
    horizon_label: str
    best_period: str
    worst_period: str
    confidence_level: float
    headline: str


class CategoryForecast(BaseModel):
    category: str
    historical_sum: float
    forecast_sum: float
    growth_percentage: float
    trend: str


class ProjectForecastResponse(BaseModel):
    status: str = Field("success", description="'success', 'warning', or 'error'")
    project_id: Optional[str] = None
    dataset_id: Optional[str] = None
    dataset_name: Optional[str] = None
    date_column: Optional[str] = None
    target_column: Optional[str] = None
    aggregation: str = "monthly"
    horizon: int = 6
    selected_model: str = "auto"
    timeline: List[TimelinePointDetailed] = []
    metrics: List[ForecastModelMetrics] = []
    business_summary: Optional[ForecastBusinessSummary] = None
    insights: List[str] = []
    recommendations: List[str] = []
    category_forecasts: List[CategoryForecast] = []
    diagnostics: Dict[str, Any] = {}
    message: Optional[str] = None
    date_detection: Optional[DateDetectionMetadata] = None


class TimeSeriesCandidate(BaseModel):
    dataset_id: str
    dataset_name: str
    date_columns: List[str]
    metric_columns: List[str]
    categorical_columns: List[str]
    is_derived_olist: bool = False
    suggested_date: Optional[str] = None
    suggested_metric: Optional[str] = None
    dataset_type: str = Field("Transactional / Time Series", description="Classification of dataset: 'Transactional / Time Series', 'Dimension / Master Data', 'Reference Data', 'Other'")
    is_time_series_capable: bool = True
    detected_date_metadata: Optional[DateDetectionMetadata] = None


class ProjectSchemaInfoResponse(BaseModel):
    has_time_series: bool
    candidates: List[TimeSeriesCandidate] = []
    message: Optional[str] = None

