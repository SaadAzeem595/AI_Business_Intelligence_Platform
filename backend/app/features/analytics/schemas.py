from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ForecastPayload(BaseModel):
    model: str
    confidence: float
    periods: int


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
    query: str


class SQLResponse(BaseModel):
    columns: List[str]
    rows: List[Dict[str, Any]]
    elapsedMs: int
