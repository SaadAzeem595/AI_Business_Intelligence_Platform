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
    clusters: int
    features: str


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


class SegmentResponse(BaseModel):
    scatter: List[ScatterPoint]
    cohorts: List[CohortSegment]


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

class ProjectForecastRequest(BaseModel):
    dataset_id: Optional[str] = Field(None, description="ID of specific dataset to forecast, or auto-detect if None")
    date_column: Optional[str] = Field(None, description="Date/timestamp column name")
    target_column: Optional[str] = Field(None, description="Numeric metric column name to forecast")
    aggregation: str = Field("monthly", description="Time series bucket: 'daily', 'weekly', 'monthly'")
    horizon: int = Field(6, description="Forecast horizon steps ahead")
    group_by: Optional[str] = Field(None, description="Optional column to group/breakdown forecast by (e.g. category)")
    model: str = Field("auto", description="Forecasting model choice: 'auto', 'arima', 'prophet', 'naive'")
    confidence: float = Field(0.95, description="Confidence level (0.80 - 0.99)")


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


class TimeSeriesCandidate(BaseModel):
    dataset_id: str
    dataset_name: str
    date_columns: List[str]
    metric_columns: List[str]
    categorical_columns: List[str]
    is_derived_olist: bool = False
    suggested_date: Optional[str] = None
    suggested_metric: Optional[str] = None


class ProjectSchemaInfoResponse(BaseModel):
    has_time_series: bool
    candidates: List[TimeSeriesCandidate] = []
    message: Optional[str] = None

