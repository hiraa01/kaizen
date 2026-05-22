"""Helpers for ML training schedule display and validation."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Optional

ALLOWED_ML_FREQUENCIES = frozenset({3, 5, 7, 30})


def normalize_ml_frequency(value: int) -> int:
    if value not in ALLOWED_ML_FREQUENCIES:
        return 7
    return value


def compute_days_until_next_ml_training(
    ml_last_trained_at: Optional[datetime],
    ml_update_frequency: int,
    now: Optional[datetime] = None,
) -> Optional[int]:
    """
    Days remaining until the next scheduled training window closes.
    None if training has never completed for this profile (scheduler will pick up soon).
    """
    frequency = normalize_ml_frequency(ml_update_frequency)
    if now is None:
        now = datetime.now(timezone.utc)
    if ml_last_trained_at is None:
        return None
    last = ml_last_trained_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    next_due = last + timedelta(days=frequency)
    delta_seconds = (next_due - now).total_seconds()
    if delta_seconds <= 0:
        return 0
    return max(1, int(math.ceil(delta_seconds / 86400.0)))
