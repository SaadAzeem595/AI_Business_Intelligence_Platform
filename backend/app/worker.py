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
