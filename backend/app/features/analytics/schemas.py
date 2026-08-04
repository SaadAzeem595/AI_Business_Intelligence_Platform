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


class SQLResponse(BaseModel):
    columns: List[str] = Field(..., description="List of columns returned by the query", examples=[["region", "SUM(revenue)"]])
    rows: List[Dict[str, Any]] = Field(..., description="List of rows represented as key-value dictionaries", examples=[[{"region": "North", "SUM(revenue)": 450000.0}]])
    elapsedMs: int = Field(..., description="Query execution duration in milliseconds", examples=[12])
