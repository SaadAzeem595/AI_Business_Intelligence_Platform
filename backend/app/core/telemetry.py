import time
import logging
from functools import wraps
from typing import Callable, Any, Optional
from prometheus_client import Histogram, Counter
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from app.core.config import settings

logger = logging.getLogger(__name__)

# Prometheus Metrics definition
API_LATENCY = Histogram(
    "api_latency_seconds",
    "API endpoint response latency",
    ["method", "endpoint"]
)
SQL_LATENCY = Histogram(
    "sql_latency_seconds",
    "DuckDB SQL query execution latency",
    ["query_hash"]
)
LANGGRAPH_LATENCY = Histogram(
    "langgraph_latency_seconds",
    "LangGraph multi-agent execution latency",
    ["thread_id"]
)
AGENT_LATENCY = Histogram(
    "agent_latency_seconds",
    "LangGraph individual agent node execution latency",
    ["agent_name"]
)
ML_INFERENCE_LATENCY = Histogram(
    "ml_inference_latency_seconds",
    "ML model inference latency",
    ["model_name"]
)
RAG_RETRIEVAL_LATENCY = Histogram(
    "rag_retrieval_latency_seconds",
    "RAG vector/hybrid retrieval execution latency",
    ["workspace"]
)
BACKGROUND_TASK_LATENCY = Histogram(
    "background_task_latency_seconds",
    "Celery background worker task execution latency",
    ["task_name"]
)
AUDIT_LOG_COUNTER = Counter(
    "audit_events_total",
    "Total count of security audit events",
    ["event_type", "status"]
)

# OpenTelemetry Setup
def setup_telemetry(app_name: str = "ai-bi-platform-backend") -> trace.Tracer:
    """Configures OpenTelemetry tracer with standard span processors."""
    try:
        resource = Resource.create(attributes={"service.name": app_name})
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)
        
        # Console Span Exporter for stdout debugging
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(console_exporter))
        
        # OTLP Collector Exporter if endpoint configured
        otlp_endpoint = getattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", None)
        if otlp_endpoint:
            logger.info(f"Registering OTLP trace exporter to endpoint {otlp_endpoint}")
            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            
        logger.info("OpenTelemetry trace instrumentation configured successfully.")
    except Exception as e:
        logger.error(f"Failed to setup OpenTelemetry provider: {str(e)}")
        
    return trace.get_tracer(app_name)

tracer = trace.get_tracer("ai-bi-platform-backend")

def track_latency(metric: Histogram, *label_args: str) -> Callable:
    """Decorator to automatically log execution latency metrics and trace spans."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.perf_counter()
            with tracer.start_as_current_span(func.__name__) as span:
                try:
                    result = func(*args, **kwargs)
                    duration = time.perf_counter() - start_time
                    metric.labels(*label_args).observe(duration)
                    return result
                except Exception as e:
                    span.record_exception(e)
                    raise
        
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.perf_counter()
            with tracer.start_as_current_span(func.__name__) as span:
                try:
                    result = await func(*args, **kwargs)
                    duration = time.perf_counter() - start_time
                    metric.labels(*label_args).observe(duration)
                    return result
                except Exception as e:
                    span.record_exception(e)
                    raise
                    
        return async_wrapper if re_is_coroutine(func) else sync_wrapper
    return decorator

def re_is_coroutine(func: Callable) -> bool:
    import inspect
    return inspect.iscoroutinefunction(func)
