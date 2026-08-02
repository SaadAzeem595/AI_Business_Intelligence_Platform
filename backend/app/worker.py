import time
from celery import Celery

from app.core.config import settings

# Initialize Celery Application with Redis Broker & Backend
celery_app = Celery(
    "ai_bi_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Optional configuration updates
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task(name="generate_report_task")
def generate_report_task(report_id: str, payload: dict) -> dict:
    """Simulates background PDF/presentation compile tasks."""
    time.sleep(5)  # Simulate file latency
    return {
        "report_id": report_id,
        "recipient": payload.get("recipient"),
        "status": "completed",
    }


# Import ML platform tasks for Celery registration
try:
    from app.features.ml.tasks import retrain_model_task, scheduled_retrain_task
except ImportError:
    pass

# Setup Celery Beat periodic schedule for ML platform retraining
celery_app.conf.beat_schedule = {
    "scheduled-retrain-forecast": {
        "task": "scheduled_retrain_task",
        "schedule": settings.RETRAIN_INTERVAL_FORECAST,
        "args": ("forecast",),
    },
    "scheduled-retrain-churn": {
        "task": "scheduled_retrain_task",
        "schedule": settings.RETRAIN_INTERVAL_CHURN,
        "args": ("churn",),
    },
    "scheduled-retrain-segmentation": {
        "task": "scheduled_retrain_task",
        "schedule": settings.RETRAIN_INTERVAL_SEGMENTATION,
        "args": ("segmentation",),
    },
    "scheduled-retrain-anomaly": {
        "task": "scheduled_retrain_task",
        "schedule": settings.RETRAIN_INTERVAL_ANOMALY,
        "args": ("anomaly",),
    },
}


