from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Tuple
import re

from database import get_db
from core.logging_config import api_logger
from models import Student
from services.recommendation_engine import RecommendationEngine
from services.ml_recommendation_engine import MLRecommendationEngine
from services.ai_service import get_ai_service


class ChatRequest(BaseModel):
    student_id: int
    message: str = Field(..., min_length=1, max_length=4000)
    use_ml: bool = True
    limit: int = 20
    w_c: Optional[float] = 0.4
    w_s: Optional[float] = 0.4
    w_p: Optional[float] = 0.2
    target_department_id: Optional[int] = None
    conversation_history: Optional[List[Dict[str, str]]] = None


class ChatResponse(BaseModel):
    reply: str
    used_weights: Tuple[float, float, float]
    used_ml: bool
    detected_style: Optional[str] = None


router = APIRouter()


def _as_float(value: Any, default: float = 0.0) -> float:
    """Coerce ORM/scalar values to float for type checkers and runtime safety."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    """Coerce ORM/scalar values to int for type checkers and runtime safety."""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_weights(w_c: Optional[float], w_s: Optional[float], w_p: Optional[float]) -> Tuple[float, float, float]:
    wc = float(w_c or 0.0)
    ws = float(w_s or 0.0)
    wp = float(w_p or 0.0)
    total = wc + ws + wp
    if total <= 0:
        return (0.4, 0.4, 0.2)
    return (wc / total, ws / total, wp / total)


def _detect_response_style(user_message: str) -> str:
    """
    Detect response style with weighted keyword matching.
    Returns one of: plan, calculation, decision, chat
    """
    text = (user_message or "").casefold()
    if not text:
        return "chat"

    score: Dict[str, int] = {
        "plan": 0,
        "calculation": 0,
        "decision": 0,
        "chat": 0,
    }

    weighted_patterns: Dict[str, List[Tuple[str, int]]] = {
        "plan": [
            (r"\b(plan|program|calisma plani|çalışma planı)\b", 4),
            (r"\b(haftalik|haftalık|gunluk|günlük|rutin)\b", 3),
            (r"\b(net art(ir)?|nasil gelis(tir)?|nasil iyiles(tir)?)\b", 3),
            (r"\b(kac saat|kaç saat|ders programi|ders programı)\b", 3),
        ],
        "calculation": [
            (r"\b(puan|hesap|hesapla|obp)\b", 4),
            (r"\b(siralama|sıralama|yuzdelik|yüzdelik|netten puan)\b", 4),
            (r"\b(kac gelir|kaç gelir|hesaplanir|hesaplanır)\b", 3),
        ],
        "decision": [
            (r"\b(tercih|yerles(ir)?|yerleş(ir)?)\b", 4),
            (r"\b(bolum|bölüm|universite|üniversite)\b", 3),
            (r"\b(mantikli mi|mantıklı mı|uygun mu|secmeli miyim|seçmeli miyim)\b", 4),
            (r"\b(hangisi|kararsizim|kararsızım)\b", 3),
        ],
    }

    for style, patterns in weighted_patterns.items():
        for pattern, weight in patterns:
            if re.search(pattern, text):
                score[style] += weight

    # Heuristic tie-breakers for question tone
    if "?" in text and score["chat"] == 0:
        score["chat"] += 1

    best_style = "chat"
    best_score = -1
    for style_name, style_score in score.items():
        if style_score > best_score:
            best_style = style_name
            best_score = style_score
    if best_score <= 1:
        return "chat"
    return best_style


@router.post("/coach", response_model=ChatResponse)
async def coach_chat(payload: ChatRequest, db: Session = Depends(get_db)):
    try:
        print("🚀 AI İsteği Başladı - student_id:", payload.student_id)
        api_logger.info("Coach chat requested", user_id=payload.student_id)

        # Öğrenciyi getir
        print("📊 Veritabanından öğrenci bilgileri çekiliyor...")
        student = db.query(Student).filter(Student.id == payload.student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
        print("✅ Öğrenci bilgileri çekildi")

        weights = _normalize_weights(payload.w_c, payload.w_s, payload.w_p)

        # ✅ Önce mevcut önerileri kontrol et (cache'den)
        from models import Recommendation
        existing_recs = db.query(Recommendation).filter(
            Recommendation.student_id == payload.student_id
        ).order_by(Recommendation.final_score.desc()).limit(payload.limit).all()
        
        recs: List[Dict[str, Any]] = []
        
        # Eğer öneriler varsa, cache'den kullan; yoksa yeni oluştur.
        # Not: Önceden len >= limit (20) şartı vardı; az sayıda kayıt kaldığında
        # (ör. hedef bölüm değişince öneriler silindiğinde) her mesajda tam ML
        # üretimi tetikleniyor ve sohbet dakikalarca donuyordu. En az 1 kayıt
        # yeterli — bağlam için üst N öneri yine sıralamadan alınır.
        print(f"📋 Mevcut öneriler kontrol ediliyor... (limit: {payload.limit})")
        if existing_recs:
            print(f"✅ Cache'den {len(existing_recs)} öneri kullanılıyor (tam {payload.limit} şartı yok)")
            api_logger.info(
                "Using cached recommendations for coach chat",
                user_id=payload.student_id,
            )
            # Cache'den gelen önerileri dict formatına çevir
            for rec in existing_recs:
                rec_dict = {
                    'final_score': rec.final_score,
                    'compatibility_score': rec.compatibility_score,
                    'success_probability': rec.success_probability,
                    'preference_score': rec.preference_score,
                    'is_safe_choice': rec.is_safe_choice,
                    'is_dream_choice': rec.is_dream_choice,
                    'is_realistic_choice': rec.is_realistic_choice,
                    'department': rec.department if hasattr(rec, 'department') else None,
                }
                recs.append(rec_dict)
        else:
            # Önerileri hazırla (ML tercihiyle)
            print(f"🔄 Yeni öneriler oluşturuluyor... (use_ml: {payload.use_ml})")
            if payload.use_ml:
                print("🤖 ML Engine kullanılıyor...")
                ml_engine = MLRecommendationEngine(db)
                recs = ml_engine.generate_recommendations(student_id=payload.student_id, limit=payload.limit, weights=weights)
                print(f"✅ ML Engine {len(recs)} öneri oluşturdu")
            else:
                print("📐 Rule Engine kullanılıyor...")
                rule_engine = RecommendationEngine(db)
                rule_recs = rule_engine.generate_recommendations(student_id=payload.student_id, limit=payload.limit, weights=weights)
                print(f"✅ Rule Engine {len(rule_recs)} öneri oluşturdu")
                # ✅ RecommendationResponse'ları Dict'e çevir
                recs = []
                for rec in rule_recs:
                    rec_dict = {
                        'final_score': rec.final_score,
                        'compatibility_score': rec.compatibility_score,
                        'success_probability': rec.success_probability,
                        'preference_score': rec.preference_score,
                        'is_safe_choice': rec.is_safe_choice,
                        'is_dream_choice': rec.is_dream_choice,
                        'is_realistic_choice': rec.is_realistic_choice,
                        'department': rec.department,
                    }
                    recs.append(rec_dict)

        # Özetlenmiş öneri metni hazırla ve kategorize et
        def summarize_recs(rlist: List[Any]) -> str:
            lines: List[str] = []
            for r in rlist[: payload.limit]:
                try:
                    if isinstance(r, dict):
                        d = r
                        dept_name = d['department'].name
                        uni_id = d['department'].university_id
                        lines.append(f"- {dept_name} (uni_id={uni_id}) | final={d['final_score']:.2f} comp={d['compatibility_score']:.2f} succ={d['success_probability']:.2f} pref={d['preference_score']:.2f}")
                    else:
                        dept_name = getattr(r.department, 'name', '') if hasattr(r, 'department') else ''
                        lines.append(f"- {dept_name} | final={r.final_score:.2f} comp={r.compatibility_score:.2f} succ={r.success_probability:.2f} pref={r.preference_score:.2f}")
                except Exception:
                    continue
            return "\n".join(lines)

        rec_text = summarize_recs(recs)

        # Kategorize edilmiş kısa özet
        def to_dict(r: Any) -> Dict[str, Any]:
            if isinstance(r, dict):
                return r
            return {
                'is_safe_choice': r.is_safe_choice,
                'is_realistic_choice': r.is_realistic_choice,
                'is_dream_choice': r.is_dream_choice,
                'final_score': r.final_score,
                'success_probability': r.success_probability,
                'department': getattr(r, 'department', None),
            }

        dlist = [to_dict(r) for r in recs]
        def topk(lst: List[Dict[str, Any]], k: int = 3) -> List[str]:
            out: List[str] = []
            for d in lst[:k]:
                dept = d.get('department')
                name = getattr(dept, 'name', '') if dept is not None else ''
                out.append(f"- {name} | final={float(d['final_score']):.2f} succ={float(d['success_probability']):.2f}")
            return out

        safe_list = [x for x in dlist if x.get('is_safe_choice')]
        realistic_list = [x for x in dlist if x.get('is_realistic_choice')]
        dream_list = [x for x in dlist if x.get('is_dream_choice')]

        categorized_text = (
            f"Güvenli (ilk 3):\n" + ("\n".join(topk(safe_list)) or "- yok") + "\n\n"
            f"Realistik (ilk 3):\n" + ("\n".join(topk(realistic_list)) or "- yok") + "\n\n"
            f"Hayal (ilk 3):\n" + ("\n".join(topk(dream_list)) or "- yok")
        )

        # Hedef yakınlığı (opsiyonel)
        proximity_text = ""
        if payload.target_department_id:
            try:
                from services.score_calculator import ScoreCalculator
                from models import Department
                dept = db.query(Department).filter(Department.id == payload.target_department_id).first()
                if dept:
                    t_tyt = 0.0
                    t_ayt = _as_float(dept.min_score)
                    prox = ScoreCalculator.calculate_goal_proximity(
                        student_tyt_score=_as_float(student.tyt_total_score),
                        student_ayt_score=_as_float(student.ayt_total_score),
                        target_tyt_score=t_tyt,
                        target_ayt_score=t_ayt,
                    )
                    proximity_text = (
                        f"Hedef yakınlık: overall={prox['overall_proximity']}% ayt_gap={prox['ayt_gap']} hazır_mı={'evet' if prox['is_ready'] else 'hayır'}\n\n"
                    )
            except Exception:
                proximity_text = ""

        # ✅ Tarihsel veri context injection - Bölüm isimlerini mesajdan çıkar ve trend analizi yap
        historical_context = ""
        try:
            from models import Department, DepartmentYearlyStats
            
            department_keywords = []
            
            # Önerilerden bölüm isimlerini al
            for rec in recs[:10]:  # İlk 10 öneri
                try:
                    dept = rec.get('department') if isinstance(rec, dict) else getattr(rec, 'department', None)
                    if dept:
                        dept_name = getattr(dept, 'normalized_name', None) or getattr(dept, 'name', '')
                        if dept_name and dept_name.lower() not in [k.lower() for k in department_keywords]:
                            department_keywords.append(dept_name)
                except:
                    continue
            
            # Her bölüm için yıllara göre trend analizi yap
            if department_keywords:
                historical_data = []
                for dept_name in department_keywords[:5]:  # İlk 5 bölüm
                    # Normalize edilmiş isme göre bölümleri bul
                    depts = db.query(Department).filter(
                        Department.normalized_name == dept_name
                    ).limit(1).all()
                    
                    if depts:
                        dept = depts[0]
                        # Yıllık istatistikleri getir
                        yearly_stats = db.query(DepartmentYearlyStats).filter(
                            DepartmentYearlyStats.department_id == dept.id
                        ).order_by(DepartmentYearlyStats.year).all()
                        
                        if yearly_stats:
                            stats_summary = []
                            for stat in yearly_stats:
                                stats_summary.append(
                                    f"{stat.year}: min_score={stat.min_score or 'N/A'}, "
                                    f"min_rank={stat.min_rank or 'N/A'}, quota={stat.quota or 'N/A'}"
                                )
                            
                            # Trend analizi
                            scores = [
                                _as_float(s.min_score)
                                for s in yearly_stats
                                if s.min_score is not None
                            ]
                            if len(scores) >= 2:
                                first_score = scores[0]
                                last_score = scores[-1]
                                trend = (
                                    "artış"
                                    if last_score > first_score
                                    else "azalış"
                                    if last_score < first_score
                                    else "stabil"
                                )
                                trend_pct = (
                                    abs((last_score - first_score) / first_score * 100)
                                    if first_score > 0
                                    else 0.0
                                )
                                historical_data.append(
                                    f"Bölüm: {dept_name}\n"
                                    f"Yıllık Veriler: {' | '.join(stats_summary)}\n"
                                    f"Trend: {trend} (%{trend_pct:.1f} değişim)\n"
                                )
                
                if historical_data:
                    historical_context = (
                        f"\n\n📊 TARİHSEL VERİ ANALİZİ (2022-2025):\n"
                        f"{''.join(historical_data)}\n"
                        f"Bu verileri kullanarak trend analizi yap ve öğrenciye stratejik tavsiyeler ver.\n"
                    )
        except Exception as e:
            api_logger.warning(f"Historical context extraction failed: {str(e)[:100]}", user_id=payload.student_id)
            historical_context = ""

        # Öğrencinin tercih ve deneme geçmişini bağlama ekle
        exam_summary = ""
        preference_summary = ""
        performance_analysis = ""
        personalized_plan_request = ""
        try:
            from models import ExamAttempt, Preference

            recent_attempts = (
                db.query(ExamAttempt)
                .filter(ExamAttempt.student_id == payload.student_id)
                .order_by(ExamAttempt.attempt_number.desc())
                .limit(5)
                .all()
            )
            if recent_attempts:
                exam_lines: List[str] = []
                ordered_attempts = list(reversed(recent_attempts))
                for attempt in recent_attempts:
                    exam_lines.append(
                        f"Deneme {_as_int(attempt.attempt_number)}: "
                        f"TYT={_as_float(attempt.tyt_score):.2f}, "
                        f"AYT={_as_float(attempt.ayt_score):.2f}, "
                        f"TOPLAM={_as_float(attempt.total_score):.2f}, "
                        f"TYT Matematik Net={_as_float(attempt.tyt_math_net):.2f}"
                    )
                exam_summary = "\n".join(exam_lines)

                subject_map: Dict[str, str] = {
                    "tyt_math_net": "TYT Matematik",
                    "tyt_turkish_net": "TYT Turkce",
                    "tyt_science_net": "TYT Fen",
                    "tyt_social_net": "TYT Sosyal",
                    "ayt_math_net": "AYT Matematik",
                    "ayt_physics_net": "AYT Fizik",
                    "ayt_chemistry_net": "AYT Kimya",
                    "ayt_biology_net": "AYT Biyoloji",
                }
                metrics: List[Dict[str, Any]] = []
                for attr, label in subject_map.items():
                    values = [_as_float(getattr(a, attr, None)) for a in ordered_attempts]
                    if not values:
                        continue
                    avg_value = sum(values) / len(values)
                    trend_value = values[-1] - values[0]
                    metrics.append(
                        {
                            "label": label,
                            "last": values[-1],
                            "avg": avg_value,
                            "best": max(values),
                            "trend": trend_value,
                        }
                    )

                message_lower = payload.message.casefold()
                requested_subject_keywords: Dict[str, str] = {
                    "biyoloji": "AYT Biyoloji",
                    "bio": "AYT Biyoloji",
                    "matematik": "TYT Matematik",
                    "mat": "TYT Matematik",
                    "fizik": "AYT Fizik",
                    "kimya": "AYT Kimya",
                    "turkce": "TYT Turkce",
                    "türkçe": "TYT Turkce",
                }
                requested_subject = ""
                for key, label in requested_subject_keywords.items():
                    if key in message_lower:
                        requested_subject = label
                        break

                analysis_lines: List[str] = []
                selected_metrics: List[Dict[str, Any]]
                if requested_subject:
                    selected_metrics = [m for m in metrics if m["label"] == requested_subject]
                else:
                    selected_metrics = sorted(metrics, key=lambda m: m["last"])[:3]

                for metric in selected_metrics:
                    trend_word = "yukselis" if metric["trend"] > 0 else "dusus" if metric["trend"] < 0 else "stabil"
                    analysis_lines.append(
                        f"{metric['label']}: son_net={metric['last']:.2f}, "
                        f"ortalama={metric['avg']:.2f}, en_iyi={metric['best']:.2f}, "
                        f"trend={trend_word} ({metric['trend']:+.2f})"
                    )
                performance_analysis = "\n".join(analysis_lines)

                if requested_subject:
                    personalized_plan_request = (
                        f"Kullanici ozellikle '{requested_subject}' gelistirmek istiyor. "
                        "Plani bu derse agirlik vererek ama diger dersleri tamamen birakmadan dengele."
                    )
                else:
                    personalized_plan_request = (
                        "Plan, son denemelerde en dusuk net gelen 3 dersi iyilestirecek sekilde olusturulmali."
                    )

            preferred_rows = (
                db.query(Preference)
                .filter(Preference.student_id == payload.student_id)
                .order_by(Preference.order.asc().nulls_last(), Preference.id.asc())
                .limit(5)
                .all()
            )
            if preferred_rows:
                pref_names: List[str] = []
                for pref in preferred_rows:
                    dept_name = (
                        getattr(pref.department, "normalized_name", None)
                        or getattr(pref.department, "name", "")
                    )
                    if dept_name:
                        pref_names.append(str(dept_name))
                if pref_names:
                    preference_summary = ", ".join(pref_names)
        except Exception as context_error:
            api_logger.warning(
                f"Coach context enrichment failed: {str(context_error)[:120]}",
                user_id=payload.student_id,
            )

        user_message = payload.message.strip()
        response_style = _detect_response_style(user_message)

        # ✅ Provider-aware AI service (Groq/Gemini) kullan
        print("🤖 AI Service ile yanıt oluşturuluyor...")
        ai_service = get_ai_service()
        ai_result = ai_service.chat(
            message=user_message,
            student_id=payload.student_id,
            student_context={
                'id': student.id,
                'name': student.name,
                'field_type': student.field_type,
                'tyt_score': student.tyt_total_score,
                'ayt_score': student.ayt_total_score,
                'total_score': student.total_score,
                'target_university': student.target_university,
                'target_department': getattr(student, 'target_department', None),
                'preferred_cities': [],
                'interest_areas': [],
                'recommendation_summary': rec_text if rec_text else '- (öneri bulunamadı)',
                'category_summary': categorized_text,
                'goal_proximity': proximity_text.strip(),
                'historical_trends': historical_context.strip(),
                'weights': f"uyumluluk={weights[0]:.2f}, başarı={weights[1]:.2f}, tercih={weights[2]:.2f}",
                'exam_summary': exam_summary,
                'preference_summary': preference_summary,
                'performance_analysis': performance_analysis,
                'personalized_plan_request': personalized_plan_request,
                'response_style': response_style,
            },
            conversation_history=payload.conversation_history,
        )
        if not ai_result.get('success'):
            error_detail = ai_result.get('error') or ai_result.get('response') or 'AI servisinde hata'
            raise HTTPException(status_code=500, detail=f"AI servisinde hata: {error_detail}")
        reply = str(ai_result.get('response') or "")

        print("✅ AI cevabı hazır, response döndürülüyor...")
        return ChatResponse(
            reply=reply.strip(),
            used_weights=weights,
            used_ml=payload.use_ml,
            detected_style=response_style,
        )

    except HTTPException:
        raise
    except Exception as e:
        api_logger.error("Coach chat failed", error=str(e), user_id=payload.student_id)
        raise HTTPException(status_code=500, detail=f"Sohbet yanıtı üretilemedi: {str(e)}")


