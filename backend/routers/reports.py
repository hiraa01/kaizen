from __future__ import annotations

import csv
from datetime import datetime
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session

from core.logging_config import api_logger
from database import get_db
from models import ExamAttempt, Student

router = APIRouter()


@router.get("/student/{student_id}/exam-attempts.csv")
def download_exam_attempts_report(student_id: int, db: Session = Depends(get_db)) -> StreamingResponse:
    try:
        student: Student | None = db.query(Student).filter(Student.id == student_id).first()
        if student is None:
            raise HTTPException(status_code=404, detail="Ogrenci bulunamadi")

        attempts: list[ExamAttempt] = (
            db.query(ExamAttempt)
            .filter(ExamAttempt.student_id == student_id)
            .order_by(ExamAttempt.attempt_number.asc())
            .all()
        )

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "attempt_number",
                "exam_date",
                "tyt_score",
                "ayt_score",
                "total_score",
                "tyt_math_net",
                "ayt_math_net",
                "ayt_biology_net",
            ]
        )
        for attempt in attempts:
            writer.writerow(
                [
                    attempt.attempt_number,
                    attempt.exam_date.isoformat() if attempt.exam_date else "",
                    attempt.tyt_score,
                    attempt.ayt_score,
                    attempt.total_score,
                    attempt.tyt_math_net,
                    attempt.ayt_math_net,
                    attempt.ayt_biology_net,
                ]
            )
        output.seek(0)

        filename = f"student_{student_id}_exam_attempts_{datetime.now().strftime('%Y%m%d')}.csv"
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers=headers)
    except HTTPException:
        raise
    except Exception as exc:
        api_logger.exception("[REPORT] CSV report generation failed: student_id=%s error=%s", student_id, exc)
        raise HTTPException(status_code=500, detail="Rapor olusturulamadi")


@router.get("/student/{student_id}/summary-print", response_class=HTMLResponse)
def printable_student_summary(student_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    try:
        student: Student | None = db.query(Student).filter(Student.id == student_id).first()
        if student is None:
            raise HTTPException(status_code=404, detail="Ogrenci bulunamadi")

        attempts: list[ExamAttempt] = (
            db.query(ExamAttempt)
            .filter(ExamAttempt.student_id == student_id)
            .order_by(ExamAttempt.attempt_number.desc())
            .limit(5)
            .all()
        )
        latest: ExamAttempt | None = attempts[0] if attempts else None
        average_total: float = 0.0
        if attempts:
            average_total = sum(float(a.total_score or 0.0) for a in attempts) / len(attempts)

        rows: str = ""
        for a in attempts:
            rows += (
                f"<tr><td>{a.attempt_number}</td>"
                f"<td>{(a.exam_date.date().isoformat() if a.exam_date else '-')}</td>"
                f"<td>{a.tyt_score:.2f}</td><td>{a.ayt_score:.2f}</td><td>{a.total_score:.2f}</td></tr>"
            )

        html_content = f"""
<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="utf-8"/>
  <title>Ogrenci Ozet Raporu</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; }}
    h1 {{ margin-bottom: 4px; }}
    .meta {{ color: #555; margin-bottom: 16px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    th {{ background: #f3f3f3; }}
    @media print {{
      button {{ display: none; }}
      body {{ margin: 0; }}
    }}
  </style>
</head>
<body>
  <button onclick="window.print()">Yazdir</button>
  <h1>Ogrenci Ozet Raporu</h1>
  <div class="meta">
    Ogrenci: {student.name} (ID: {student.id})<br/>
    Alan: {student.field_type} | Son puan: {(latest.total_score if latest else 0):.2f} | Son 5 deneme ort.: {average_total:.2f}
  </div>
  <table>
    <thead>
      <tr><th>Deneme</th><th>Tarih</th><th>TYT</th><th>AYT</th><th>Toplam</th></tr>
    </thead>
    <tbody>{rows or "<tr><td colspan='5'>Kayit bulunamadi</td></tr>"}</tbody>
  </table>
</body>
</html>
"""
        return HTMLResponse(content=html_content)
    except HTTPException:
        raise
    except Exception as exc:
        api_logger.exception("[REPORT] Printable report generation failed: student_id=%s error=%s", student_id, exc)
        raise HTTPException(status_code=500, detail="Yazdirilabilir rapor olusturulamadi")
