"""Celery application factory."""

from __future__ import annotations

from celery import Celery

from app.config import settings

celery_app = Celery(
    "carousel",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.research",
        "app.tasks.prompts",
        "app.tasks.images",
        "app.tasks.publish",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    result_expires=3600,
)
