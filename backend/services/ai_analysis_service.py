"""
Builds AI analysis payloads (trends, aggregate ML signals, Turkish advice).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from core.logging_config import api_logger
from models import ExamAttempt, Student
from services.ml_recommendation_engine import MLRecommendationEngine
from services.score_calculator import ScoreCalculator

_ATTEMPT_NET_FIELDS: Tuple[str, ...] = (
    "tyt_turkish_net",
    "tyt_math_net",
    "tyt_social_net",
    "tyt_science_net",
    "ayt_math_net",
    "ayt_physics_net",
    "ayt_chemistry_net",
    "ayt_biology_net",
    "ayt_literature_net",
    "ayt_history1_net",
    "ayt_geography1_net",
    "ayt_philosophy_net",
    "ayt_history2_net",
    "ayt_geography2_net",
    "ayt_religion_net",
    "ayt_foreign_language_net",
)


@dataclass(frozen=True)
class PeriodWindow:
    key: str
    days: int


def resolve_period(period: str) -> PeriodWindow:
    normalized = (period or "weekly").lower().strip()
    if normalized == "daily":
        return PeriodWindow("daily", 1)
    if normalized == "monthly":
        return PeriodWindow("monthly", 30)
    return PeriodWindow("weekly", 7)


def _attempt_timestamp(row: ExamAttempt) -> datetime:
    if row.exam_date is not None:
        ts = row.exam_date
    else:
        ts = row.created_at
    if ts is None:
        return datetime.now(timezone.utc)
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def _total_tyt_net(row: object) -> float:
    return float(
        (getattr(row, "tyt_turkish_net", 0.0) or 0.0)
        + (getattr(row, "tyt_math_net", 0.0) or 0.0)
        + (getattr(row, "tyt_social_net", 0.0) or 0.0)
        + (getattr(row, "tyt_science_net", 0.0) or 0.0)
    )


def _safe_ml_signals(ml_engine: MLRecommendationEngine, like: object) -> dict:
    try:
        return ml_engine.compute_aggregate_ml_signals_for_student_like(like)
    except Exception as exc:
        api_logger.warning(
            "ML aggregate signals failed; using neutral defaults",
            error=str(exc),
        )
        return {"max_success_probability": 0.5, "mean_compatibility": 0.5}


def _student_like_from_base(student: Student, attempt: Optional[ExamAttempt]) -> SimpleNamespace:
    data = {column.key: getattr(student, column.key) for column in Student.__table__.columns}
    if attempt is not None:
        for field_name in _ATTEMPT_NET_FIELDS:
            data[field_name] = getattr(attempt, field_name, 0.0) or 0.0
    score_block = ScoreCalculator.calculate_all_scores(data)
    data.update(score_block)
    return SimpleNamespace(**data)


def _percent_change(first: float, last: float) -> float:
    if first == 0:
        return 0.0 if last == 0 else 100.0
    return round((last - first) / max(abs(first), 1e-9) * 100.0, 2)


def _build_critical_advice(
    net_change_pct: float,
    success_change_pct: float,
    avg_compat: float,
    period: PeriodWindow,
) -> str:
    parts: List[str] = []
    if net_change_pct > 3 and success_change_pct < 1:
        parts.append(
            "Matematik ve TYT netlerinde iyileşme görülüyor; ML başarı olasılığı henüz stabil. "
            "Hedef bölüm puanlarını bir kademe yukarı deneyebilirsin."
        )
    elif net_change_pct < -3:
        parts.append(
            "Son dönemde toplam TYT netlerinde düşüş var. Zayıf derslere göre haftalık tekrar planı önerilir."
        )
    elif success_change_pct > 5:
        parts.append(
            "ML modelinin gördüğü başarı olasılığı güçleniyor; mevcut tempo ve deneme sıklığını koru."
        )
    elif success_change_pct < -5:
        parts.append(
            "Başarı olasılığı tahminlerinde gerileme var. Hedef bölümlerin taban puanlarıyla netlerini yeniden hizala."
        )
    else:
        parts.append(
            f"{period.days} günlük pencerede performansın görece dengeli; haftalık deneme ile trendi netleştir."
        )

    if avg_compat >= 0.72:
        parts.append("Genel uyumluluk ortalaman yüksek; tercih listeni güvenli–realistik–hayal üçlüsüyle dengele.")
    elif avg_compat <= 0.45:
        parts.append("Uyumluluk ortalaması düşük; şehir ve üniversite tipi filtrelerini gözden geçirmek faydalı olur.")

    return " ".join(parts)


def build_ai_analysis(db: Session, student_id: int, period_key: str) -> dict:
    window = resolve_period(period_key)
    student = db.query(Student).filter(Student.id == student_id).first()
    if student is None:
        raise ValueError("student_not_found")

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=window.days)

    attempts: List[ExamAttempt] = (
        db.query(ExamAttempt)
        .filter(ExamAttempt.student_id == student_id)
        .order_by(ExamAttempt.attempt_number.asc())
        .all()
    )

    filtered: List[ExamAttempt] = [
        a for a in attempts if _attempt_timestamp(a) >= start
    ]
    if len(attempts) >= 2 and len(filtered) < 2:
        ordered = sorted(attempts, key=_attempt_timestamp)
        filtered = ordered[-min(12, len(ordered)) :]
    elif len(attempts) == 1 and not filtered:
        filtered = list(attempts)

    ml_engine = MLRecommendationEngine(db)

    net_series: List[dict] = []
    success_series: List[dict] = []
    compat_samples: List[float] = []

    for att in filtered:
        ts = _attempt_timestamp(att)
        like = _student_like_from_base(student, att)
        signals = _safe_ml_signals(ml_engine, like)
        compat_samples.append(signals["mean_compatibility"])
        iso = ts.isoformat()
        net_series.append(
            {"date_iso": iso, "total_tyt_net": _total_tyt_net(att), "success_probability": 0.0}
        )
        success_series.append(
            {
                "date_iso": iso,
                "total_tyt_net": _total_tyt_net(att),
                "success_probability": signals["max_success_probability"],
            }
        )

    current_like = _student_like_from_base(student, None)
    current_signals = _safe_ml_signals(ml_engine, current_like)
    compat_samples.append(current_signals["mean_compatibility"])
    now_iso = now.isoformat()
    net_series.append(
        {
            "date_iso": now_iso,
            "total_tyt_net": _total_tyt_net(student),
            "success_probability": 0.0,
        }
    )
    success_series.append(
        {
            "date_iso": now_iso,
            "total_tyt_net": _total_tyt_net(student),
            "success_probability": current_signals["max_success_probability"],
        }
    )

    average_compatibility = (
        sum(compat_samples) / len(compat_samples) if compat_samples else 0.5
    )

    nets = [p["total_tyt_net"] for p in net_series]
    probs = [p["success_probability"] for p in success_series if p["success_probability"] > 0]
    if len(nets) >= 2:
        net_change = _percent_change(nets[0], nets[-1])
    else:
        net_change = 0.0
    if len(probs) >= 2:
        success_change = _percent_change(probs[0], probs[-1])
    else:
        success_change = 0.0

    advice = _build_critical_advice(
        net_change, success_change, average_compatibility, window
    )

    return {
        "period": window.key,
        "window_days": window.days,
        "average_compatibility": round(average_compatibility, 4),
        "improvement_rate_net_percent": net_change,
        "improvement_rate_success_percent": success_change,
        "critical_advice": advice,
        "net_trend_series": net_series,
        "success_probability_series": success_series,
    }
