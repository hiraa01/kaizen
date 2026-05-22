from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class AiAnalysisPoint(BaseModel):
    """Single point for time-series charts."""

    date_iso: str = Field(description="ISO-8601 timestamp for the sample")
    total_tyt_net: float
    success_probability: float


class AiAnalysisResponse(BaseModel):
    period: str
    window_days: int
    average_compatibility: float
    improvement_rate_net_percent: float
    improvement_rate_success_percent: float
    critical_advice: str
    net_trend_series: List[AiAnalysisPoint]
    success_probability_series: List[AiAnalysisPoint]
