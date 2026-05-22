"""
✅ BASİT VE ÇALIŞAN: Agenda Router - Ajanda öğeleri yönetimi
Direkt DB sorgusu kullanır, karmaşık servis katmanları yok
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from sqlalchemy import text
from typing import List
from datetime import datetime, timedelta

from database import get_db
from models import AgendaItem, Student, ExamAttempt
from schemas.agenda import (
    AgendaItemCreate,
    AgendaItemUpdate,
    AgendaItemResponse,
    AgendaAiRecommendationResponse,
    AgendaAiProgramItem,
    AgendaAiApplyRequest,
)

router = APIRouter()


def _row_to_agenda_response(row) -> AgendaItemResponse:
    data = dict(row._mapping)
    return AgendaItemResponse(**data)


def _ensure_agenda_table(db: Session) -> None:
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS agenda_items (
                id SERIAL PRIMARY KEY,
                student_id INTEGER NOT NULL,
                title VARCHAR(200) NOT NULL,
                description TEXT NULL,
                due_date TIMESTAMP NULL,
                is_completed BOOLEAN NOT NULL DEFAULT FALSE,
                priority VARCHAR(20) NOT NULL DEFAULT 'medium',
                category VARCHAR(50) NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NULL
            )
            """
        )
    )
    db.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_agenda_items_student_due_date "
            "ON agenda_items (student_id, due_date)"
        )
    )
    db.commit()


def _subject_from_field(field_type: str) -> List[str]:
    upper = (field_type or "").upper()
    if upper == "SAY":
        return ["AYT Matematik", "AYT Fizik", "AYT Kimya", "AYT Biyoloji", "TYT Matematik"]
    if upper == "EA":
        return ["AYT Matematik", "AYT Edebiyat", "AYT Tarih", "TYT Türkçe", "TYT Matematik"]
    if upper in {"SÖZ", "SOZ"}:
        return ["AYT Edebiyat", "AYT Tarih", "AYT Coğrafya", "TYT Türkçe"]
    return ["TYT Türkçe", "TYT Matematik", "TYT Fen", "TYT Sosyal"]


def _analyze_exam_trend(attempts: List[ExamAttempt]) -> List[str]:
    if not attempts:
        return ["Henüz deneme verisi yok. Program başlangıç seviyesi üzerinden üretildi."]
    ordered = list(reversed(attempts))
    latest = ordered[-1]
    first = ordered[0]
    lines: List[str] = []
    total_delta = float(latest.total_score or 0.0) - float(first.total_score or 0.0)
    lines.append(
        f"Son {len(ordered)} denemede toplam puan değişimi: {total_delta:+.2f} "
        f"(ilk: {float(first.total_score or 0.0):.2f}, son: {float(latest.total_score or 0.0):.2f})"
    )
    bio_delta = float(latest.ayt_biology_net or 0.0) - float(first.ayt_biology_net or 0.0)
    math_delta = float(latest.tyt_math_net or 0.0) - float(first.tyt_math_net or 0.0)
    lines.append(f"TYT Matematik net trendi: {math_delta:+.2f}")
    lines.append(f"AYT Biyoloji net trendi: {bio_delta:+.2f}")
    return lines


def _build_ai_program(student: Student, period: str, attempts: List[ExamAttempt]) -> AgendaAiRecommendationResponse:
    now = datetime.now()
    subjects = _subject_from_field(str(student.field_type or ""))
    analysis = _analyze_exam_trend(attempts)
    items: List[AgendaAiProgramItem] = []
    period_norm = (period or "weekly").lower()
    category_name = (
        "AI Daily Program"
        if period_norm == "daily"
        else "AI Monthly Program"
        if period_norm == "monthly"
        else "AI Weekly Program"
    )

    focus_templates = [
        "Konu tekrari + karma soru seti + yanlis analiz notu",
        "Cikis yapilan konudan mini tekrar + yeni nesil soru uygulamasi",
        "Kisa tekrar + deneme parcasi + eksik konu kapatma calismasi",
        "Soru cozumu + kavram haritasi olusturma + gun sonu ozet",
    ]
    weekly_titles = [
        "odak tekrar oturumu",
        "soru kampi",
        "deneme analizi",
        "hedef net calismasi",
        "zayif konu guclendirme",
        "karma tekrar",
        "performans toparlama",
    ]

    if period_norm == "daily":
        for idx, subject in enumerate(subjects[:3]):
            items.append(
                AgendaAiProgramItem(
                    title=f"{subject} {weekly_titles[idx % len(weekly_titles)]}",
                    description=f"{subject} icin {focus_templates[idx % len(focus_templates)]}.",
                    due_date=now.replace(hour=10 + (idx * 3), minute=0, second=0, microsecond=0),
                    priority="high" if idx == 0 else "medium",
                    category=category_name,
                )
            )
    elif period_norm == "monthly":
        for day in range(30):
            subject = subjects[day % max(len(subjects), 1)]
            due = (now + timedelta(days=day)).replace(hour=19, minute=0, second=0, microsecond=0)
            if due.weekday() == 6:
                # Pazar günleri daha hafif görev
                description = f"{subject} icin hafif tekrar + haftalik ozet + eksik konu listesi."
            else:
                description = f"{subject} icin {focus_templates[day % len(focus_templates)]}."
            items.append(
                AgendaAiProgramItem(
                    title=f"{subject} aylik gelisim plani",
                    description=description,
                    due_date=due,
                    priority="medium",
                    category=category_name,
                )
            )
    else:  # weekly
        for day in range(7):
            subject = subjects[day % max(len(subjects), 1)]
            due = (now + timedelta(days=day)).replace(hour=18, minute=0, second=0, microsecond=0)
            items.append(
                AgendaAiProgramItem(
                    title=f"{subject} {weekly_titles[day % len(weekly_titles)]}",
                    description=f"{subject} icin {focus_templates[day % len(focus_templates)]}.",
                    due_date=due,
                    priority="high" if day in {1, 3, 5} else "medium",
                    category=category_name,
                )
            )

    return AgendaAiRecommendationResponse(
        period=period_norm,
        student_id=int(student.id),
        summary=(
            f"{student.name} icin {period_norm} programi olusturuldu. "
            f"Program son deneme trendlerine gore daha cesitli ve hedef net odakli gorevler icerir."
        ),
        analysis=analysis,
        items=items,
    )


def _apply_recommendation_variation(
    recommendation: AgendaAiRecommendationResponse, refresh_token: int | None
) -> AgendaAiRecommendationResponse:
    if refresh_token is None or not recommendation.items:
        return recommendation

    items = list(recommendation.items)
    shift = abs(int(refresh_token)) % max(len(items), 1)
    rotated = items[shift:] + items[:shift]
    hour_offset = (abs(int(refresh_token)) % 3) - 1  # -1, 0, +1

    varied_items: List[AgendaAiProgramItem] = []
    for item in rotated:
        due = item.due_date
        if due is not None:
            due = due + timedelta(hours=hour_offset)
        varied_items.append(
            AgendaAiProgramItem(
                title=item.title,
                description=item.description,
                due_date=due,
                priority=item.priority,
                category=item.category,
            )
        )

    return AgendaAiRecommendationResponse(
        period=recommendation.period,
        student_id=recommendation.student_id,
        summary=recommendation.summary,
        analysis=recommendation.analysis,
        items=varied_items,
    )


@router.get("", response_model=List[AgendaItemResponse])
def get_agenda_items(
    student_id: int = Query(..., description="Öğrenci ID"),
    db: Session = Depends(get_db)
):
    """
    ✅ BASİT VE ÇALIŞAN: Öğrencinin ajanda öğelerini listele - Direkt DB sorgusu
    """
    _ensure_agenda_table(db)
    # ✅ Direkt DB sorgusu - Karmaşık servis katmanları yok
    rows = db.execute(
        text(
            """
            SELECT id, student_id, title, description, due_date, is_completed, priority, category, created_at, updated_at
            FROM agenda_items
            WHERE student_id = :student_id
            ORDER BY due_date DESC NULLS LAST, created_at DESC
            """
        ),
        {"student_id": student_id},
    ).fetchall()
    return [_row_to_agenda_response(row) for row in rows]


@router.post("", response_model=AgendaItemResponse)
def create_agenda_item(
    item: AgendaItemCreate,
    db: Session = Depends(get_db)
):
    """
    ✅ BASİT VE ÇALIŞAN: Yeni ajanda öğesi oluştur - Direkt DB sorgusu
    """
    _ensure_agenda_table(db)
    # ✅ Direkt DB sorgusu - Karmaşık servis katmanları yok
    row = db.execute(
        text(
            """
            INSERT INTO agenda_items (student_id, title, description, due_date, priority, category, is_completed)
            VALUES (:student_id, :title, :description, :due_date, :priority, :category, false)
            RETURNING id, student_id, title, description, due_date, is_completed, priority, category, created_at, updated_at
            """
        ),
        {
            "student_id": item.student_id,
            "title": item.title,
            "description": item.description,
            "due_date": item.due_date,
            "priority": item.priority,
            "category": item.category,
        },
    ).fetchone()
    db.commit()
    return _row_to_agenda_response(row)


@router.patch("/{item_id}", response_model=AgendaItemResponse)
def update_agenda_item(
    item_id: int,
    item_update: AgendaItemUpdate,
    db: Session = Depends(get_db)
):
    """
    ✅ BASİT VE ÇALIŞAN: Ajanda öğesini güncelle - Direkt DB sorgusu
    """
    _ensure_agenda_table(db)
    existing = db.execute(
        text("SELECT id FROM agenda_items WHERE id = :id"),
        {"id": item_id},
    ).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Ajanda öğesi bulunamadı")
    
    # Güncelleme
    update_data = item_update.dict(exclude_unset=True)
    if not update_data:
        row = db.execute(
            text(
                """
                SELECT id, student_id, title, description, due_date, is_completed, priority, category, created_at, updated_at
                FROM agenda_items WHERE id = :id
                """
            ),
            {"id": item_id},
        ).fetchone()
        return _row_to_agenda_response(row)
    set_clauses = []
    params = {"id": item_id}
    for key, value in update_data.items():
        set_clauses.append(f"{key} = :{key}")
        params[key] = value
    query = f"""
        UPDATE agenda_items
        SET {", ".join(set_clauses)}, updated_at = NOW()
        WHERE id = :id
        RETURNING id, student_id, title, description, due_date, is_completed, priority, category, created_at, updated_at
    """
    row = db.execute(text(query), params).fetchone()
    db.commit()
    return _row_to_agenda_response(row)


@router.delete("/{item_id}")
def delete_agenda_item(
    item_id: int,
    db: Session = Depends(get_db)
):
    """
    ✅ BASİT VE ÇALIŞAN: Ajanda öğesini sil - Direkt DB sorgusu
    """
    _ensure_agenda_table(db)
    existing = db.execute(
        text("SELECT id FROM agenda_items WHERE id = :id"),
        {"id": item_id},
    ).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Ajanda öğesi bulunamadı")
    db.execute(text("DELETE FROM agenda_items WHERE id = :id"), {"id": item_id})
    db.commit()
    return {"message": "Ajanda öğesi başarıyla silindi", "id": item_id}


@router.get("/ai-recommendation", response_model=AgendaAiRecommendationResponse)
def get_ai_agenda_recommendation(
    student_id: int = Query(..., description="Öğrenci ID"),
    period: str = Query("weekly", description="daily|weekly|monthly"),
    refresh_token: int | None = Query(None, description="Yeni öneri varyasyonu için"),
    db: Session = Depends(get_db),
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    attempts = (
        db.query(ExamAttempt)
        .filter(ExamAttempt.student_id == student_id)
        .order_by(desc(ExamAttempt.attempt_number))
        .limit(5)
        .all()
    )
    recommendation = _build_ai_program(student, period, attempts)
    return _apply_recommendation_variation(recommendation, refresh_token)


@router.post("/ai-apply", response_model=List[AgendaItemResponse])
def apply_ai_agenda_program(
    payload: AgendaAiApplyRequest,
    db: Session = Depends(get_db),
):
    _ensure_agenda_table(db)
    student = db.query(Student).filter(Student.id == payload.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    attempts = (
        db.query(ExamAttempt)
        .filter(ExamAttempt.student_id == payload.student_id)
        .order_by(desc(ExamAttempt.attempt_number))
        .limit(5)
        .all()
    )
    recommendation = _build_ai_program(student, payload.period, attempts)
    created: List[AgendaItemResponse] = []
    for item in recommendation.items:
        row = db.execute(
            text(
                """
                INSERT INTO agenda_items (student_id, title, description, due_date, priority, category, is_completed)
                VALUES (:student_id, :title, :description, :due_date, :priority, :category, false)
                RETURNING id, student_id, title, description, due_date, is_completed, priority, category, created_at, updated_at
                """
            ),
            {
                "student_id": payload.student_id,
                "title": item.title,
                "description": item.description,
                "due_date": item.due_date,
                "priority": item.priority,
                "category": item.category,
            },
        ).fetchone()
        created.append(_row_to_agenda_response(row))
    db.commit()
    return created

