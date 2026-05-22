"""
Runs global ML model training in a dedicated DB session (thread-safe).
Used by FastAPI BackgroundTasks, APScheduler, and student update hooks.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy.orm import Session

from core.logging_config import api_logger
from database import SessionLocal
from models import Student


def execute_ml_training() -> None:
    """Train and persist global ML models (synchronous, CPU-bound)."""
    from scripts.train_ml_models import generate_training_data
    from services.ml_recommendation_engine import MLRecommendationEngine

    training_db: Session = SessionLocal()
    try:
        api_logger.info("[ML_TRAIN] Starting global model training")
        training_data = generate_training_data()
        ml_engine = MLRecommendationEngine(training_db)
        ml_engine.train_models(training_data)
        api_logger.info("[ML_TRAIN] Global model training finished successfully")
    except Exception as exc:
        api_logger.error("[ML_TRAIN] Global model training failed", error=str(exc))
        raise
    finally:
        training_db.close()


def _collect_due_student_ids(db: Session, now: datetime) -> List[int]:
    """Return student IDs whose ml_update_frequency window has elapsed."""
    allowed = {3, 5, 7, 30}
    due_ids: List[int] = []
    students: List[Student] = db.query(Student).all()
    for student in students:
        frequency_days: int = student.ml_update_frequency or 7
        if frequency_days not in allowed:
            frequency_days = 7
        last_trained = student.ml_last_trained_at
        if last_trained is None:
            due_ids.append(student.id)
            continue
        if last_trained.tzinfo is None:
            last_trained = last_trained.replace(tzinfo=timezone.utc)
        if last_trained + timedelta(days=frequency_days) <= now:
            due_ids.append(student.id)
    return due_ids


def execute_ml_training_with_due_updates() -> None:
    """
    If any student is due for a refresh window, run one global training pass
    and stamp ml_last_trained_at only for due students.
    """
    schedule_db: Session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        due_ids = _collect_due_student_ids(schedule_db, now)
        if not due_ids:
            api_logger.debug("[ML_SCHED] No students due for ML training")
            return
        api_logger.info("[ML_SCHED] Running ML training", due_count=len(due_ids))
        execute_ml_training()
        for student_id in due_ids:
            row = schedule_db.query(Student).filter(Student.id == student_id).first()
            if row is not None:
                row.ml_last_trained_at = now
        schedule_db.commit()
    except Exception as exc:
        schedule_db.rollback()
        api_logger.error("[ML_SCHED] Scheduled ML training tick failed", error=str(exc))
    finally:
        schedule_db.close()
