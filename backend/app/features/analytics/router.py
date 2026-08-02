from typing import List, Dict, Any
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import get_current_user, MockUser
from app.features.analytics.schemas import (
    ForecastPayload,
    ForecastResponse,
    ForecastPoint,
    ForecastMetric,
    SegmentPayload,
    SegmentResponse,
    ScatterPoint,
    CohortSegment,
    AnomalyPayload,
    AnomalyResponse,
    TimelinePoint,
    AnomalyLog,
    SQLPayload,
    SQLResponse,
)
from app.features.analytics.service import AnalyticsService

router = APIRouter(tags=["Analytics & ML Model Operations"])


@router.post("/analytics/forecast", response_model=ForecastResponse)
async def forecast_trend(
    payload: ForecastPayload,
    current_user: MockUser = Depends(get_current_user),
) -> ForecastResponse:
    """Mock forecasting endpoint returning mathematical ARIMA/Prophet predictions timelines."""
    # Scaffold baseline projection points
    data = [
        ForecastPoint(date="Feb 26", actual=12000),
        ForecastPoint(date="Mar 26", actual=13500),
        ForecastPoint(date="Apr 26", actual=14200),
        ForecastPoint(date="May 26", actual=13900),
        ForecastPoint(date="Jun 26", actual=15400),
        ForecastPoint(date="Jul 26", actual=16800),
        ForecastPoint(date="Aug 26 (P)", forecast=17200 if payload.model == "Prophet" else 16900),
        ForecastPoint(date="Sep 26 (P)", forecast=17900 if payload.model == "Prophet" else 17300),
        ForecastPoint(date="Oct 26 (P)", forecast=18500 if payload.model == "Prophet" else 17800),
        ForecastPoint(date="Nov 26 (P)", forecast=19100 if payload.model == "Prophet" else 18200),
        ForecastPoint(date="Dec 26 (P)", forecast=19800 if payload.model == "Prophet" else 18700),
    ]
    metrics = [
        ForecastMetric(metric="R-Squared (Precision)", arimaValue="0.89", prophetValue="0.94"),
        ForecastMetric(metric="Mean Absolute Error (MAE)", arimaValue="$1,420", prophetValue="$890"),
        ForecastMetric(metric="Root Mean Square Error (RMSE)", arimaValue="$1,980", prophetValue="$1,120"),
    ]
    return ForecastResponse(data=data, metrics=metrics)


@router.post("/analytics/segment", response_model=SegmentResponse)
async def segment_cohorts(
    payload: SegmentPayload,
    current_user: MockUser = Depends(get_current_user),
) -> SegmentResponse:
    """Mock segmentation endpoint returning scatter points coordinates and cohorts details."""
    scatter = [
        ScatterPoint(name="John", x=85, y=92, cluster="Champions"),
        ScatterPoint(name="Sarah", x=78, y=88, cluster="Champions"),
        ScatterPoint(name="Acme LLC", x=92, y=95, cluster="Champions"),
        ScatterPoint(name="David", x=42, y=55, cluster="Loyal"),
        ScatterPoint(name="Emily", x=38, y=62, cluster="Loyal"),
        ScatterPoint(name="Mike", x=12, y=22, cluster="At-Risk"),
        ScatterPoint(name="Jessica", x=15, y=18, cluster="At-Risk"),
    ]
    cohorts = [
        CohortSegment(name="Champions (High Spend, High Recency)", count=420, avgSpent="$4,850", freqScore="94/100", riskRating="Low"),
        CohortSegment(name="Loyal Customers (Average Spend)", count=1850, avgSpent="$1,280", freqScore="62/100", riskRating="Low"),
        CohortSegment(name="At-Risk Core (High Spend, Idle)", count=280, avgSpent="$3,120", freqScore="18/100", riskRating="High"),
        CohortSegment(name="Snoozing (Low engagement)", count=3200, avgSpent="$140", freqScore="8/100", riskRating="Medium"),
    ]
    return SegmentResponse(scatter=scatter, cohorts=cohorts)


@router.post("/analytics/anomalies", response_model=AnomalyResponse)
async def detect_anomalies(
    payload: AnomalyPayload,
    current_user: MockUser = Depends(get_current_user),
) -> AnomalyResponse:
    """Mock anomaly scanner returning spikes/dips limits violations timelines."""
    timeline = [
        TimelinePoint(date="Jul 20", value=1400, limit=1800),
        TimelinePoint(date="Jul 21", value=1450, limit=1800),
        TimelinePoint(date="Jul 22", value=1390, limit=1800),
        TimelinePoint(date="Jul 23", value=1560, limit=1800),
        TimelinePoint(date="Jul 24", value=1200, limit=1800),
        TimelinePoint(date="Jul 25", value=1480, limit=1800),
        TimelinePoint(date="Jul 26", value=1520, limit=1800),
        TimelinePoint(date="Jul 27", value=1610, limit=1800),
        TimelinePoint(date="Jul 28", value=1580, limit=1800),
        TimelinePoint(date="Jul 29", value=2450, limit=1800),
        TimelinePoint(date="Jul 30", value=1600, limit=1800),
    ]
    logs = [
        AnomalyLog(id="A-9204", metric="Daily API Calls Spike", value="85,420 calls", deviation="+3.2 Std Dev", date="2026-08-02", status="Unresolved"),
        AnomalyLog(id="A-8902", metric="Unusual refund volume", value="$4,850 value", deviation="+4.1 Std Dev", date="2026-07-29", status="Unresolved"),
        AnomalyLog(id="A-7201", metric="Logins count dip", value="1,200 count", deviation="-2.8 Std Dev", date="2026-07-24", status="Resolved"),
    ]
    return AnomalyResponse(timeline=timeline, logs=logs)


@router.post("/sql/run", response_model=SQLResponse)
async def run_sql_query(
    payload: SQLPayload,
    current_user: MockUser = Depends(get_current_user),
) -> SQLResponse:
    """Executes SQL queries against temporary CSV view mappings via the DuckDB engine."""
    try:
        return AnalyticsService.execute_duckdb_query(payload.query)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/sql/schema", response_model=List[Dict[str, Any]])
async def get_sql_schema(
    current_user: MockUser = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Returns currently available view mappings registered in the DuckDB context."""
    from app.features.datasets.router import UPLOADED_PATHS_CACHE

    schema_list = []
    # Fetch active views from cache
    for dataset_id, item in UPLOADED_PATHS_CACHE.items():
        view_name = item["filename"].split(".")[0]
        schema_list.append({"name": view_name, "rowsCount": 100})
        
    # Standard baseline maps fallback
    if not schema_list:
        schema_list = [
            {"name": "q3_financials", "rowsCount": 14020},
            {"name": "customer_churn", "rowsCount": 6200},
            {"name": "raw_clicks_logs", "rowsCount": 185000},
        ]
    return schema_list
