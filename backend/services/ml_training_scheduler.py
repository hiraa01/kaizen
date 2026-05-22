"""
APScheduler-based periodic check for per-student ML training windows.
"""

from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from core.logging_config import api_logger
from services.ml_training_runner import execute_ml_training_with_due_updates

_scheduler: BackgroundScheduler | None = None


def start_ml_training_scheduler() -> None:
    """Start background scheduler if not already running."""
    global _scheduler
    if _scheduler is not None:
        return
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        execute_ml_training_with_due_updates,
        trigger=IntervalTrigger(hours=1),
        id="ml_training_due_check",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    _scheduler = scheduler
    api_logger.info("[ML_SCHED] APScheduler started (hourly due check)")


def shutdown_ml_training_scheduler() -> None:
    """Stop scheduler on app shutdown."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        api_logger.info("[ML_SCHED] APScheduler shut down")
