from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.auth_dependencies import get_current_user_from_token
from core.logging_config import api_logger
from database import get_db
from models import ExamAttempt, Student, User

router = APIRouter()


def _admin_ids_from_env() -> set[int]:
    raw: str = os.getenv("ADMIN_USER_IDS", "")
    result: set[int] = set()
    for item in raw.split(","):
        value = item.strip()
        if not value:
            continue
        try:
            result.add(int(value))
        except ValueError:
            continue
    return result


def _ensure_admin(user: User) -> None:
    admin_ids: set[int] = _admin_ids_from_env()
    if admin_ids and user.id not in admin_ids:
        raise HTTPException(status_code=403, detail="Admin yetkisi gerekli")


@router.get("/summary")
def get_admin_summary(
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        _ensure_admin(current_user)
        return {
            "users": db.query(User).count(),
            "students": db.query(Student).count(),
            "exam_attempts": db.query(ExamAttempt).count(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        api_logger.exception("[ADMIN] Summary failed: user_id=%s error=%s", current_user.id, exc)
        raise HTTPException(status_code=500, detail="Admin ozeti alinamadi")


@router.get("/users")
def list_users(
    limit: int = Query(default=50, ge=1, le=500),
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    try:
        _ensure_admin(current_user)
        users: list[User] = db.query(User).order_by(User.id.desc()).limit(limit).all()
        return [
            {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "phone": user.phone,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }
            for user in users
        ]
    except HTTPException:
        raise
    except Exception as exc:
        api_logger.exception("[ADMIN] List users failed: user_id=%s error=%s", current_user.id, exc)
        raise HTTPException(status_code=500, detail="Kullanicilar listelenemedi")


@router.patch("/users/{user_id}/status")
def update_user_status(
    user_id: int,
    is_active: bool,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        _ensure_admin(current_user)
        user: User | None = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(status_code=404, detail="Kullanici bulunamadi")
        user.is_active = is_active
        db.commit()
        db.refresh(user)
        return {"id": user.id, "is_active": user.is_active}
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        api_logger.exception(
            "[ADMIN] Update user status failed: admin_id=%s target_user_id=%s error=%s",
            current_user.id,
            user_id,
            exc,
        )
        raise HTTPException(status_code=500, detail="Kullanici durumu guncellenemedi")
