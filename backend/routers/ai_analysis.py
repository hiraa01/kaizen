from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.auth_dependencies import get_current_user_from_token
from core.logging_config import api_logger
from database import get_db
from models import Student, User
from schemas.ai_analysis import AiAnalysisResponse
from services.ai_analysis_service import build_ai_analysis

router = APIRouter()


def _get_owned_student_or_404(student_id: int, current_user: User, db: Session) -> Student:
    student: Student | None = (
        db.query(Student).filter(Student.id == student_id).first()
    )
    if student is None:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    if student.user_id is None or student.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Bu öğrenci profiline erişim yetkiniz yok")
    return student


@router.get("/analysis/{student_id}", response_model=AiAnalysisResponse)
async def get_ai_analysis(
    student_id: int,
    period: Literal["daily", "weekly", "monthly"] = "weekly",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token),
) -> AiAnalysisResponse:
    """Öğrenci için seçilen periyotta AI analiz özetini ve serilerini döndürür."""
    _get_owned_student_or_404(student_id, current_user, db)
    try:
        payload = build_ai_analysis(db, student_id, period)
        return AiAnalysisResponse(**payload)
    except ValueError as exc:
        if str(exc) == "student_not_found":
            raise HTTPException(status_code=404, detail="Öğrenci bulunamadı") from exc
        raise HTTPException(status_code=400, detail="Geçersiz analiz isteği") from exc
    except Exception as exc:
        api_logger.error("AI analysis failed", user_id=student_id, error=str(exc))
        raise HTTPException(
            status_code=500,
            detail="Analiz oluşturulurken bir hata oluştu",
        ) from exc
