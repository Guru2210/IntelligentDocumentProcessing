"""
Celery app configuration.
Deliberately tolerant of Redis being unavailable (local dev without Docker).
"""
from app.config import settings

try:
    from celery import Celery

    celery_app = Celery(
        "idp_worker",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=["app.workers.training_task", "app.workers.extraction_task"],
    )

    celery_app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        result_expires=86400,
        # Don't retry connection on startup — fail fast
        broker_connection_retry_on_startup=False,
        broker_connection_max_retries=1,
    )

except Exception as e:
    print(f"[Celery] Could not configure Celery (Redis may be offline): {e}")
    celery_app = None
